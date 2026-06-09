#!/usr/bin/env python3
"""
Pre-producer product coverage verification.

Checks that every live article in pipeline.json has sufficient products
(with non-empty pros) in products.yaml before the producer is run.

Usage:
  python3 tools/verify-coverage.py --site <slug>
  python3 tools/verify-coverage.py --site <slug> --min-products 3
  python3 tools/verify-coverage.py --site <slug> --accept-skips skip-list.txt --strict
  python3 tools/verify-coverage.py --site <slug> --report /tmp/coverage.json

Exit codes:
  0 = All live articles meet minimum product threshold (or all shortfalls accepted)
  1 = Some articles below threshold without accepted skip list
  2 = Configuration error (file not found, invalid arguments)
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import yaml


def load_pipeline(path: Path) -> list:
    with open(path) as f:
        data = json.load(f)
    if isinstance(data, dict):
        return data.get("articles", [])
    return data


def load_products(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def count_usable_products(article: dict, products: dict) -> int:
    """Count products assigned to this article that exist AND have non-empty default_pros."""
    assigned = article.get("products", [])
    count = 0
    for key in assigned:
        prod = products.get(key)
        if prod and isinstance(prod, dict):
            pros = prod.get("default_pros") or []
            if pros:  # non-empty list means usable
                count += 1
    return count


def run_check(args) -> int:
    site_root = Path.home() / args.site
    pipeline_path = args.pipeline or (site_root / "data/pipeline.json")
    products_path = args.products or (site_root / "content/products/products.yaml")

    for p, label in [(Path(pipeline_path), "pipeline.json"), (Path(products_path), "products.yaml")]:
        if not p.exists():
            print(f"ERROR: {label} not found: {p}", file=sys.stderr)
            return 2

    pipeline = load_pipeline(Path(pipeline_path))
    products = load_products(Path(products_path))

    # Load accepted skip list if provided
    accepted_skips = set()
    if args.accept_skips:
        skip_path = Path(args.accept_skips)
        if not skip_path.exists():
            print(f"ERROR: accept-skips file not found: {skip_path}", file=sys.stderr)
            return 2
        for line in skip_path.read_text().splitlines():
            slug = line.strip()
            if slug and not slug.startswith("#"):
                accepted_skips.add(slug)

    # Only check live articles (exclude dupe/drop/skip)
    exclude_statuses = {"dupe", "drop", "skip"}
    live_articles = [
        a for a in pipeline
        if a.get("status", "") not in exclude_statuses
    ]

    min_products = args.min_products

    ok_articles = []
    shortfall_articles = []
    zero_articles = []

    by_hub_counts = defaultdict(lambda: {"ok": 0, "shortfall": 0, "zero": 0, "total": 0})

    for article in live_articles:
        slug = article["slug"]
        hub = article.get("hub", "unknown")
        usable = count_usable_products(article, products)

        by_hub_counts[hub]["total"] += 1

        if usable >= min_products:
            ok_articles.append((slug, hub, usable))
            by_hub_counts[hub]["ok"] += 1
        elif usable > 0:
            shortfall_articles.append((slug, hub, usable))
            by_hub_counts[hub]["shortfall"] += 1
        else:
            zero_articles.append((slug, hub, usable))
            by_hub_counts[hub]["zero"] += 1

    total = len(live_articles)
    problem_articles = shortfall_articles + zero_articles
    unaccepted = [(s, h, u) for s, h, u in problem_articles if s not in accepted_skips]

    # ── Print report ──────────────────────────────────────────────────────────
    site_label = args.site
    print(f"\n=== Coverage Report: {site_label} ===")
    print(f"Min products required: {min_products}")
    print(f"Total live articles:   {total}")
    print()
    print("Status:")
    ok_pct = int(len(ok_articles) / total * 100) if total else 0
    sf_pct = int(len(shortfall_articles) / total * 100) if total else 0
    z_pct  = int(len(zero_articles) / total * 100) if total else 0
    print(f"  OK (≥{min_products} products):  {len(ok_articles)} articles ({ok_pct}%)")
    print(f"  Shortfall (1-{min_products-1}):    {len(shortfall_articles)} articles ({sf_pct}%)")
    print(f"  Zero products:      {len(zero_articles)} articles ({z_pct}%)")
    print()

    if by_hub_counts:
        hub_col = max(len(h) for h in by_hub_counts) + 2
        print(f"By hub:")
        header = f"  {'Hub':<{hub_col}}  {'OK':>5}  {'Short':>6}  {'Zero':>5}  {'Total':>6}"
        print(header)
        print("  " + "-" * (hub_col + 28))
        for hub in sorted(by_hub_counts):
            c = by_hub_counts[hub]
            print(f"  {hub:<{hub_col}}  {c['ok']:>5}  {c['shortfall']:>6}  {c['zero']:>5}  {c['total']:>6}")
        print()

    # ── Verdict ───────────────────────────────────────────────────────────────
    if not problem_articles:
        print("VERIFICATION: PASSED")
        print(f"All {total} live articles meet the minimum of {min_products} products.")
        verdict = 0
    elif not unaccepted:
        print("VERIFICATION: PASSED (with accepted skips)")
        print(f"{len(problem_articles)} articles below threshold — all in accepted skip list.")
        verdict = 0
    else:
        print("VERIFICATION: FAILED")
        print(f"{len(unaccepted)} articles do not have sufficient products to produce.")
        if accepted_skips:
            print(f"({len(problem_articles) - len(unaccepted)} were in accepted skip list)")
        print()
        print("To fix:")
        print("  1. Run source-products-rainforest.py --resume to source missing products")
        print("  2. Run generate-product-pros-cons.py to fill empty pros/cons")
        print("  3. OR add affected slugs to a skip-list.txt and pass --accept-skips")
        print("  4. Re-run verify-coverage.py to confirm")
        verdict = 1

    # ── JSON report ───────────────────────────────────────────────────────────
    if args.report:
        report = {
            "site": args.site,
            "min_products": min_products,
            "total_live": total,
            "ok": len(ok_articles),
            "shortfall": len(shortfall_articles),
            "zero": len(zero_articles),
            "unaccepted": len(unaccepted),
            "verdict": "PASSED" if verdict == 0 else "FAILED",
            "by_hub": {h: dict(c) for h, c in by_hub_counts.items()},
            "problem_articles": [
                {"slug": s, "hub": h, "usable_products": u,
                 "accepted": s in accepted_skips}
                for s, h, u in problem_articles
            ],
        }
        report_path = Path(args.report)
        report_path.write_text(json.dumps(report, indent=2))
        print(f"\nDetailed report: {report_path}")

    if args.strict and verdict != 0:
        return 1
    return verdict


def main():
    parser = argparse.ArgumentParser(
        description="Pre-producer product coverage verification",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--site", required=True, metavar="SLUG",
                        help="Site slug (site root is ~/SLUG)")
    parser.add_argument("--min-products", type=int, default=4, metavar="N",
                        help="Minimum usable products per article (default: 4)")
    parser.add_argument("--pipeline", metavar="PATH",
                        help="Override path to pipeline.json")
    parser.add_argument("--products", metavar="PATH",
                        help="Override path to products.yaml")
    parser.add_argument("--accept-skips", metavar="FILE",
                        help="File listing slugs explicitly accepted as skipped (one per line)")
    parser.add_argument("--strict", action="store_true",
                        help="Exit non-zero if any unaccepted shortfalls exist")
    parser.add_argument("--report", metavar="PATH",
                        help="Write coverage report as JSON to this path")
    args = parser.parse_args()

    sys.exit(run_check(args))


if __name__ == "__main__":
    main()
