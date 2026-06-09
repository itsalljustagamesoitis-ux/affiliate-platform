#!/usr/bin/env python3
"""
Bulk product sourcing via Rainforest API.

For each article in pipeline.json with an empty products[] field, searches
Rainforest for the article keyword, picks the top results, adds them to
products.yaml, and assigns product keys back to pipeline.json.

Usage:
  python3 tools/source-products-rainforest.py --site <slug>
  python3 tools/source-products-rainforest.py --site <slug> --limit 10
  python3 tools/source-products-rainforest.py --site <slug> --resume
  python3 tools/source-products-rainforest.py --site <slug> --dry-run

Cost:
  ~$0.005-0.01 per Rainforest API call (1 call per article keyword).
  A 300-article site costs approximately $1.50-3.00 total.

Prerequisites:
  RAINFOREST_KEY in <site_root>/config/credentials.env or RAINFOREST_KEY env var.

Exit:
  0 = complete
  1 = interrupted (state preserved for --resume)
  2 = tool error (missing credentials, files, etc.)
"""

import argparse
import json
import os
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
import yaml

MIN_RESULTS = 5
MAX_RESULTS = 7
MIN_REVIEWS = 50
CHECKPOINT_EVERY = 25
NOW = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z")
MAX_TITLE_LENGTH = 120   # cap product name length after scrubbing

TOOLS_DIR = Path(__file__).parent
HUB_TEMPLATES_PATH = TOOLS_DIR / "hub-templates.yaml"
DTC_BRANDS_DIR    = TOOLS_DIR.parent / "config/dtc-brands"   # per-niche dir (v1.6)
DTC_BRANDS_CONFIG = TOOLS_DIR.parent / "config/dtc-brands.yaml"  # legacy fallback

# Title words that must appear in a result for each product hub.
# Hubs not listed here are informational; no category restriction is applied.
HUB_CATEGORY_TERMS: dict = {
    "rods":          ["rod", "rods"],
    "reels":         ["reel", "reels"],
    "lines-leaders": ["line", "lines", "leader", "leaders", "tippet"],
    "waders-boots":  ["wader", "waders", "boot", "boots", "wading"],
    "flies-patterns":["fly", "flies", "nymph", "streamer", "dry fly", "wet fly"],
    "fly-tying":     ["tying", "vise", "bobbin", "dubbing"],
    "accessories":   ["net", "pack", "vest", "bag", "pliers", "forceps", "sling"],
}


def load_hub_templates() -> dict:
    if not HUB_TEMPLATES_PATH.exists():
        return {}
    with open(HUB_TEMPLATES_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


# ── Sourcing Policies ─────────────────────────────────────────────────────────

def load_dtc_brands(niche: str) -> list:
    """
    Return lowercased DTC brand names for the niche that are not sold on Amazon.

    Lookup order:
    1. config/dtc-brands/<niche>.yaml  — per-niche format (v1.6): plain list of brand names
    2. config/dtc-brands.yaml          — legacy format: dict keyed by niche
    """
    niche_file = DTC_BRANDS_DIR / f"{niche}.yaml"
    if niche_file.exists():
        with open(niche_file, encoding="utf-8") as f:
            data = yaml.safe_load(f) or []
        brands = [str(b).strip() for b in data if b]
    elif DTC_BRANDS_CONFIG.exists():
        with open(DTC_BRANDS_CONFIG, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        brands = list(data.get(niche, [])) + list(data.get("universal", []))
    else:
        return []
    return [b.lower() for b in brands if b]


def dtc_brands_in_keyword(keyword: str, dtc_brands: list) -> list:
    """Return any DTC brand names (lowercase) found as whole words in the keyword."""
    kw = keyword.lower()
    found = []
    for brand in sorted(dtc_brands, key=len, reverse=True):  # longest match first
        if re.search(r"\b" + re.escape(brand) + r"\b", kw) and brand not in found:
            found.append(brand)
    return found


def scrub_seller_prefix(title: str, brand: str = "") -> str:
    """
    Strip seller/marketing prefixes from Amazon product titles.

    Amazon listings frequently include:
    - Pipe-separated marketing copy: "fishpond Nomad Net | Rubber Mesh | float test..."
    - Brand-only prefix before pipe: "LAMSON | Ketchum Release Extractor | Big Bug..."

    Rules applied in order:
    1. Pipe (' | ') separator:
       - If text before first pipe is ≤2 words (brand/store-name only), use the
         text AFTER the first pipe as the title.
       - Otherwise keep text BEFORE the first pipe; discard marketing copy after.
    2. Truncate to MAX_TITLE_LENGTH characters at a word boundary.

    Note: brand duplication within the title (e.g., "fishpond Summit Sling") is
    intentionally kept — the brand is part of the product identity and the brand
    field captures it separately. Do not strip leading brand names; they make the
    title human-readable standalone.
    """
    if " | " in title:
        parts = title.split(" | ")
        first = parts[0].strip()
        if len(first.split()) <= 2 and len(parts) > 1:
            # Brand/store-name-only prefix — use the segment after the pipe
            title = parts[1].strip()
        else:
            # Product name portion precedes the pipe; discard marketing copy
            title = first

    if len(title) > MAX_TITLE_LENGTH:
        title = title[:MAX_TITLE_LENGTH].rsplit(" ", 1)[0]

    return title.strip()


def apply_brand_policy(results: list, keyword: str) -> list:
    """
    If a result's brand appears verbatim in the keyword, restrict to that brand only.
    Prevents "search for Brand X" from returning Brand Y products.
    Falls through (all results kept) when no brand cue is detectable in the keyword.
    """
    kw_lower = keyword.lower()
    matching_brand = None
    for r in results:
        rb = (r.get("brand") or r.get("manufacturer") or "").strip().lower()
        if rb and len(rb) >= 3 and rb in kw_lower:
            matching_brand = rb
            break
    if not matching_brand:
        return results
    filtered = [r for r in results
                if (r.get("brand") or r.get("manufacturer") or "").strip().lower() == matching_brand]
    return filtered if filtered else results  # fall back if filter kills everything


def apply_category_policy(results: list, hub: str) -> list:
    """Remove results whose title contains no hub-relevant terms. No-ops on info hubs."""
    terms = HUB_CATEGORY_TERMS.get(hub)
    if not terms:
        return results
    filtered = [r for r in results if any(t in r.get("title", "").lower() for t in terms)]
    return filtered if filtered else results  # fall back if filter kills everything


# ── Credentials ───────────────────────────────────────────────────────────────

def load_rainforest_key(site_root: Path) -> str:
    key = os.environ.get("RAINFOREST_KEY")
    if not key:
        creds = site_root / "config/credentials.env"
        if creds.exists():
            for line in creds.read_text().splitlines():
                if line.startswith("RAINFOREST_KEY="):
                    key = line.split("=", 1)[1].strip()
    if not key:
        creds_path = site_root / "config/credentials.env"
        print(
            f"ERROR: RAINFOREST_KEY not set.\n"
            f"  Add it to {creds_path}\n"
            f"  or set the RAINFOREST_KEY environment variable.",
            file=sys.stderr,
        )
        sys.exit(2)
    return key


# ── Helpers ───────────────────────────────────────────────────────────────────

def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[''']", "", text)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def make_product_key(brand: str, title: str, used_keys: set) -> str:
    brand_s = slugify(brand or "")
    title_s = slugify(title or "")
    if brand_s and title_s.startswith(brand_s + "-"):
        title_s = title_s[len(brand_s) + 1:]
    parts = title_s.split("-")[:5]
    descriptor = "-".join(p for p in parts if p)
    base = f"{brand_s}-{descriptor}" if brand_s else descriptor
    base = base[:60].rstrip("-")
    key = base
    n = 2
    while key in used_keys:
        key = f"{base[:56]}-{n}"
        n += 1
    return key


# ── API ───────────────────────────────────────────────────────────────────────

def is_book_article(article: dict) -> bool:
    """True when keyword or slug signals a book/reading article (→ category 283155)."""
    keyword = (article.get("keyword") or "").lower()
    slug = (article.get("slug") or "").lower()
    return "book" in keyword or "book" in slug


def search(keyword: str, api_key: str, dry_run: bool, category_id: str = "") -> list:
    if dry_run:
        return []
    try:
        params = {
            "api_key": api_key,
            "type": "search",
            "amazon_domain": "amazon.com",
            "search_term": keyword,
        }
        if category_id:
            params["category_id"] = category_id
        resp = requests.get(
            "https://api.rainforestapi.com/request",
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        results = resp.json().get("search_results", [])
        qualified = [r for r in results if r.get("ratings_total", 0) >= MIN_REVIEWS]
        pool = qualified if len(qualified) >= MIN_RESULTS else results
        return pool[:MAX_RESULTS]
    except Exception as e:
        print(f"    API error: {e}")
        return []


# ── I/O (atomic) ──────────────────────────────────────────────────────────────

def load_pipeline(pipeline_path: Path) -> dict:
    with open(pipeline_path) as f:
        data = json.load(f)
    if not isinstance(data, dict):
        data = {"articles": data}
    return data


def save_pipeline(data: dict, pipeline_path: Path) -> None:
    tmp = pipeline_path.with_suffix(".json.tmp")
    bak = pipeline_path.with_suffix(".json.bak")
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    if pipeline_path.exists():
        shutil.copy2(pipeline_path, bak)
    os.replace(tmp, pipeline_path)


def load_products(products_path: Path) -> dict:
    with open(products_path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save_products(products: dict, products_path: Path) -> None:
    tmp = products_path.with_suffix(".yaml.tmp")
    bak = products_path.with_suffix(".yaml.bak")
    with open(tmp, "w", encoding="utf-8") as f:
        yaml.dump(products, f, allow_unicode=True, default_flow_style=False,
                  sort_keys=False, width=120)
    if products_path.exists():
        shutil.copy2(products_path, bak)
    os.replace(tmp, products_path)


# ── State (resume) ────────────────────────────────────────────────────────────

def load_state(state_file: Path) -> set:
    if state_file.exists():
        try:
            return set(json.loads(state_file.read_text()))
        except Exception:
            pass
    return set()


def save_state(done: set, state_file: Path) -> None:
    state_file.write_text(json.dumps(sorted(done)))


# ── Main ──────────────────────────────────────────────────────────────────────

def get_processing_order(pipeline_articles: list, already_processed: set, dtc_brands: list) -> list:
    """Return articles to process in round-robin hub order.

    Guarantees proportional hub coverage even when processing stops early.
    Articles with no existing products and not yet processed are interleaved
    hub-by-hub so no single hub can be starved by a run cutoff.
    """
    from collections import defaultdict
    candidates = [
        a for a in pipeline_articles
        if not a.get("products") and a["slug"] not in already_processed
    ]
    by_hub = defaultdict(list)
    for a in candidates:
        by_hub[a.get("hub", "unknown")].append(a)
    hubs = sorted(by_hub.keys())
    result = []
    while any(by_hub[h] for h in hubs):
        for hub in hubs:
            if by_hub[hub]:
                result.append(by_hub[hub].pop(0))
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Bulk product sourcing via Rainforest API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--site", required=True, metavar="SLUG",
                        help="Site slug (site root is ~/SLUG)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Process at most N articles (test mode)")
    parser.add_argument("--resume", action="store_true",
                        help="Skip articles already sourced in a prior run")
    parser.add_argument("--dry-run", action="store_true",
                        help="Skip API calls; show what would be sourced")
    parser.add_argument("--reset-state", action="store_true",
                        help="Clear resume state file and start fresh")
    args = parser.parse_args()

    site_root = Path.home() / args.site
    pipeline_path = site_root / "data/pipeline.json"
    products_path = site_root / "content/products/products.yaml"
    state_file = Path(f"/tmp/source-products-rainforest-{args.site}-state.json")

    if not site_root.exists():
        print(f"ERROR: site root not found: {site_root}", file=sys.stderr)
        sys.exit(2)
    if not pipeline_path.exists():
        print(f"ERROR: pipeline.json not found: {pipeline_path}", file=sys.stderr)
        sys.exit(2)
    if not products_path.exists():
        print(f"ERROR: products.yaml not found: {products_path}", file=sys.stderr)
        sys.exit(2)

    api_key = load_rainforest_key(site_root)

    if args.reset_state and state_file.exists():
        state_file.unlink()
        print("State file cleared.")

    done = load_state(state_file) if args.resume else set()

    # Warn if a partial state exists but --resume wasn't passed
    if not args.resume and not args.reset_state and state_file.exists():
        partial = load_state(state_file)
        if partial:
            print(
                f"WARNING: state file found with {len(partial)} processed articles "
                f"but --resume was not passed. Starting fresh and IGNORING prior state.\n"
                f"  Pass --resume to continue from where you left off.\n"
                f"  Pass --reset-state to suppress this warning.",
                file=sys.stderr,
            )

    print(f"Site:       {args.site}")
    print(f"Site root:  {site_root}")
    if args.dry_run:
        print("Mode:       DRY RUN — no API calls")
    if args.resume:
        print(f"Resume:     {len(done)} articles already sourced")
    print()

    hub_templates = load_hub_templates()

    # Load DTC brands for this site's niche
    site_config_path = site_root / "site.config.yaml"
    site_niche = ""
    if site_config_path.exists():
        with open(site_config_path, encoding="utf-8") as f:
            sc = yaml.safe_load(f) or {}
            site_niche = sc.get("site", {}).get("niche", "")
    dtc_brands = load_dtc_brands(site_niche)
    if dtc_brands:
        print(f"DTC policy:  {len(dtc_brands)} brands → NOT_ON_AMAZON (niche: {site_niche or 'unknown'})")
        print()

    pipeline_data = load_pipeline(pipeline_path)
    products = load_products(products_path)
    articles = pipeline_data.get("articles", [])

    candidates = get_processing_order(articles, done, dtc_brands)
    if args.limit:
        candidates = candidates[:args.limit]

    total_empty = len([a for a in articles if not a.get("products")])
    print(f"Articles in pipeline: {len(articles)}")
    print(f"Need products:        {total_empty}")
    print(f"Already done (state): {len(done)}")
    print(f"To process this run:  {len(candidates)}")
    if args.limit:
        print(f"Limit:                {args.limit} (test mode)")
    print()

    if not candidates:
        print("Nothing to do.")
        return

    # Build ASIN → existing key map to avoid duplicates (handles both field names)
    asin_to_key = {
        (v.get("amazon_asin") or v.get("asin")): k
        for k, v in products.items()
        if isinstance(v, dict) and (v.get("amazon_asin") or v.get("asin"))
        and (v.get("amazon_asin") or v.get("asin")) not in ("VERIFY", "NOT_FOUND", "NOT_ON_AMAZON")
    }
    used_keys = set(products.keys())

    sourced = new_total = 0

    for i, article in enumerate(candidates, 1):
        slug = article["slug"]
        keyword = article.get("keyword") or slug.replace("-", " ")
        hub = article.get("hub", "")
        prefix = f"[{i}/{len(candidates)}]"

        print(f"{prefix} {slug}")
        print(f"         keyword: {keyword}")

        if args.dry_run:
            print(f"         [dry-run] would search Rainforest for: {keyword}")
            done.add(slug)
            continue

        # Policy 3 — DTC brand short-circuit: skip Amazon entirely for brands not sold there
        found_dtc = dtc_brands_in_keyword(keyword, dtc_brands)
        if found_dtc:
            assigned_keys = []
            for dtc_brand_lower in found_dtc:
                brand_name = dtc_brand_lower.title()
                key = make_product_key(brand_name, keyword, used_keys)
                used_keys.add(key)
                tmpl = hub_templates.get(hub, {})
                products[key] = {
                    "name": keyword.title(),
                    "brand": brand_name,
                    "amazon_asin": "NOT_ON_AMAZON",
                    "hub": hub,
                    "price_band": tmpl.get("price_band", "mid"),
                    "notes_for_writers": (
                        "DTC brand — add verified product name, specs, and retailer link manually."
                    ),
                    "default_pros": [],
                    "default_cons": [],
                    "sourced_at": NOW,
                    "confidence": 0.5,
                }
                assigned_keys.append(key)
            article["products"] = assigned_keys
            done.add(slug)
            sourced += 1
            new_total += len(assigned_keys)
            print(f"         → DTC brands {found_dtc}: {len(assigned_keys)} NOT_ON_AMAZON placeholder(s)")
            continue

        book_category = "283155" if is_book_article(article) else ""
        results = search(keyword, api_key, args.dry_run, category_id=book_category)
        time.sleep(0.4)

        if not results:
            print(f"         → no results, skipping")
            continue

        # Policy 1 — Brand match: reject competitor brands when keyword names a brand
        # Policy 2 — Category match: reject off-hub products (e.g. reels in a rods search)
        results = apply_brand_policy(results, keyword)
        results = apply_category_policy(results, hub)

        if not results:
            print(f"         → no results after policy filters, skipping")
            continue

        assigned_keys = []
        new_count = 0

        for r in results:
            asin = r.get("asin", "")
            if not asin:
                continue
            if asin in asin_to_key:
                if asin_to_key[asin] in assigned_keys:
                    continue
                assigned_keys.append(asin_to_key[asin])
                continue

            title = r.get("title", "")
            brand = r.get("brand") or r.get("manufacturer") or ""
            link = r.get("link") or f"https://www.amazon.com/dp/{asin}"

            title = scrub_seller_prefix(title)
            key = make_product_key(brand, title, used_keys)
            used_keys.add(key)
            asin_to_key[asin] = key
            tmpl = hub_templates.get(hub, {})
            products[key] = {
                "name": title,
                "brand": brand or None,
                "amazon_asin": asin,
                "hub": hub,
                "price_band": tmpl.get("price_band", "mid"),
                "notes_for_writers": tmpl.get("notes_for_writers", "").strip() or None,
                "default_pros": [],
                "default_cons": [],
                "source_url": link,
                "sourced_at": NOW,
                "confidence": 0.75,
            }
            assigned_keys.append(key)
            new_count += 1

        article["products"] = assigned_keys
        done.add(slug)
        sourced += 1
        new_total += new_count
        reused = len(assigned_keys) - new_count
        print(f"         → {len(assigned_keys)} products ({new_count} new, {reused} reused)")

        if i % CHECKPOINT_EVERY == 0:
            print(f"\n  [checkpoint] saving at article {i}...\n")
            save_products(products, products_path)
            save_pipeline(pipeline_data, pipeline_path)
            save_state(done, state_file)

    print("\nFinal save...")
    save_products(products, products_path)
    save_pipeline(pipeline_data, pipeline_path)
    save_state(done, state_file)

    remaining = len([a for a in articles if not a.get("products")])
    print(f"\nDone.")
    print(f"  Articles sourced:     {sourced}/{len(candidates)}")
    print(f"  New products:         {new_total}")
    print(f"  Total in catalog:     {len(products)}")
    print(f"  Articles still empty: {remaining}")
    print(f"  State file:           {state_file}")

    # Completion check: compare processed slugs vs all expected live articles
    from collections import defaultdict
    live_articles = [
        a for a in articles
        if a.get("status") not in ("dupe", "drop") and a.get("status") != "skip"
    ]
    all_done = load_state(state_file)  # re-read to include this run
    unprocessed = [a for a in live_articles if a["slug"] not in all_done and not a.get("products")]

    if unprocessed:
        by_hub = defaultdict(list)
        for a in unprocessed:
            by_hub[a.get("hub", "unknown")].append(a["slug"])
        print(f"\n\u26a0\ufe0f  INCOMPLETE: {len(unprocessed)} live articles still have no products")
        for hub in sorted(by_hub):
            print(f"  {hub}: {len(by_hub[hub])} unprocessed")
        print(f"\n  To resume: re-run with --resume flag")
        sys.exit(1)
    else:
        print(f"\n\u2713 COMPLETE: all {len(live_articles)} live articles have products")
        sys.exit(0)


if __name__ == "__main__":
    main()
