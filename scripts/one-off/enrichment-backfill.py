#!/usr/bin/env python3
"""
One-time backfill: enrich products.yaml with image and brand data from Rainforest API.

For each product entry, calls enrich_product (idempotent — skips already-populated entries).
Writes updates to products.yaml at every CHECKPOINT_EVERY products and at the end.

Usage:
    python3 affiliate-platform/scripts/enrichment-backfill.py <site-path>
    python3 affiliate-platform/scripts/enrichment-backfill.py <site-path> --limit 5
    python3 affiliate-platform/scripts/enrichment-backfill.py <site-path> --skip-image
    python3 affiliate-platform/scripts/enrichment-backfill.py <site-path> --skip-brand
    python3 affiliate-platform/scripts/enrichment-backfill.py <site-path> --dry-run

Exit codes:
    0 — completed (even if some products failed enrichment)
    1 — fatal setup error (no products.yaml, no RAINFOREST_KEY, etc.)
    2 — too many consecutive enrichment failures (Rainforest outage likely)
"""

import argparse
import os
import shutil
import sys
import time
from pathlib import Path

import yaml

# Make the platform producer importable from any working directory
SCRIPT_DIR = Path(__file__).parent
PLATFORM_PRODUCER = SCRIPT_DIR.parent / "producer"
if str(PLATFORM_PRODUCER) not in sys.path:
    sys.path.insert(0, str(PLATFORM_PRODUCER))

from lib.image_sourcer import enrich_product, load_rainforest_key

CHECKPOINT_EVERY = 50
MAX_CONSECUTIVE_FAILURES = 3


def _save_yaml(products: dict, path: Path) -> None:
    tmp = path.with_suffix(".yaml.tmp")
    bak = path.with_suffix(".yaml.bak")
    with open(tmp, "w", encoding="utf-8") as f:
        yaml.dump(products, f, allow_unicode=True, default_flow_style=False,
                  sort_keys=False, width=120)
    if path.exists():
        shutil.copy2(path, bak)
    os.replace(tmp, path)


def _load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def run(site_root: Path, limit: int, skip_image: bool, skip_brand: bool, dry_run: bool) -> int:
    products_path = site_root / "content/products/products.yaml"
    if not products_path.exists():
        print(f"ERROR: No products.yaml found at {products_path}", file=sys.stderr)
        return 1

    key = load_rainforest_key(site_root)
    if not key:
        print(
            "ERROR: RAINFOREST_KEY not found.\n"
            f"  Set RAINFOREST_KEY env var or add to {site_root}/config/credentials.env",
            file=sys.stderr,
        )
        return 1

    products = _load_yaml(products_path)
    total = len(products)

    # Select candidates: products missing brand or image (idempotency handled inside enrich_product)
    import re
    ASIN_RE = re.compile(r"^[A-Z0-9]{10}$")
    SENTINEL = frozenset(["NOT_ON_AMAZON", "NOT_FOUND", "VERIFY"])

    candidates = []
    skippable_no_asin = 0
    skippable_complete = 0

    for slug, p in products.items():
        if not isinstance(p, dict):
            continue
        has_brand = bool(p.get("brand") and str(p.get("brand", "")).strip()
                         and str(p.get("brand", "")).strip().lower() != "none")
        has_image = bool(p.get("default_image"))
        if has_brand and has_image:
            skippable_complete += 1
            continue
        asin = str(p.get("amazon_asin") or p.get("asin") or "").strip()
        if not asin or asin in SENTINEL or not ASIN_RE.match(asin):
            skippable_no_asin += 1
            continue
        candidates.append(slug)

    if limit:
        candidates = candidates[:limit]

    print(f"\nEnrichment backfill — {site_root.name}")
    print(f"  Total products:          {total}")
    print(f"  Already complete:        {skippable_complete}")
    print(f"  No usable ASIN (skip):   {skippable_no_asin}")
    print(f"  To process:              {len(candidates)}")
    if limit:
        print(f"  (limited to {limit} by --limit flag)")
    if dry_run:
        print("  DRY RUN — no changes will be written\n")
    else:
        print()

    images_updated = 0
    brands_updated = 0
    api_errors = 0
    consecutive_failures = 0
    start_time = time.monotonic()

    for i, slug in enumerate(candidates, 1):
        p = products[slug]
        prefix = f"[{i}/{len(candidates)}]"

        if dry_run:
            print(f"{prefix} DRY {slug}")
            continue

        updated, meta = enrich_product(
            slug, p, site_root, key,
            options={"skip_image": skip_image, "skip_brand": skip_brand},
        )

        changed = meta["image_updated"] or meta["brand_updated"]
        is_error = meta["image_source"] == "api_failed"

        if is_error:
            consecutive_failures += 1
            api_errors += 1
        else:
            consecutive_failures = 0

        if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            print(
                f"\n  HALT: {MAX_CONSECUTIVE_FAILURES} consecutive API failures — "
                "Rainforest may be down. Products saved so far. Re-run to resume.",
                file=sys.stderr,
            )
            _save_yaml(products, products_path)
            return 2

        if changed:
            products[slug] = updated
            if meta["image_updated"]:
                images_updated += 1
            if meta["brand_updated"]:
                brands_updated += 1

        status_parts = []
        if meta["brand_updated"]:
            status_parts.append(f"brand={updated.get('brand')!r}")
        if meta["image_updated"]:
            status_parts.append(f"image={meta['image_source']}")
        status = ", ".join(status_parts) if status_parts else meta["image_source"]

        result = "OK  " if changed else "SKIP"
        print(f"{prefix} {result} {slug}")
        print(f"       image: {meta['image_source']}, brand: {'updated' if meta['brand_updated'] else 'unchanged'}")
        for err in meta.get("errors", []):
            print(f"       WARN: {err}")

        # Checkpoint save
        if i % CHECKPOINT_EVERY == 0:
            print(f"\n  [checkpoint] saving after {i} products …\n")
            _save_yaml(products, products_path)

    if not dry_run:
        _save_yaml(products, products_path)

    elapsed = time.monotonic() - start_time
    print(f"\n{'─' * 60}")
    print(f"Done in {elapsed:.0f}s")
    print(f"  Processed:       {len(candidates)}")
    print(f"  Brands updated:  {brands_updated}")
    print(f"  Images updated:  {images_updated}")
    print(f"  API errors:      {api_errors}")

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Backfill product images and brands from Rainforest API."
    )
    parser.add_argument("site", help="Path to the site root directory")
    parser.add_argument("--limit", type=int, default=0, help="Process at most N products (0 = all)")
    parser.add_argument("--skip-image", action="store_true", help="Skip image fetching")
    parser.add_argument("--skip-brand", action="store_true", help="Skip brand population")
    parser.add_argument("--dry-run", action="store_true", help="Report candidates without calling API")
    args = parser.parse_args()

    site_root = Path(args.site).resolve()
    if not (site_root / "site.config.yaml").exists():
        print(f"ERROR: {site_root} does not look like a site root (no site.config.yaml)", file=sys.stderr)
        sys.exit(1)

    sys.exit(run(site_root, args.limit, args.skip_image, args.skip_brand, args.dry_run))


if __name__ == "__main__":
    main()
