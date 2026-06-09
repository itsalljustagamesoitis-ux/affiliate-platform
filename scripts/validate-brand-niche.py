#!/usr/bin/env python3
"""
validate-brand-niche.py — V8 fake-brand / niche-contamination validator
Affiliate Platform preflight suite.

Detects two classes of generator errors that evade other validators:

  H1 FABRICATED BRAND — Brand token appears in slug/title but is absent from the
      article body. The article has a branded headline with no supporting content.
      Classic VW case: "Volkswagen Mobility Scooter Buyer's Guide" but the body
      contains only generic Drive Medical products.
      Severity: FAIL

  H2 NICHE CONTAMINATION — Brand token in slug/title belongs to an industry
      incompatible with the site's niche. Caught by cross-referencing against a
      per-niche brand taxonomy.
      Classic Chevy case: "Chevy Colorado Bed Rails" filed under bedroom-safety
      in a senior caregiving site.
      Severity: WARN (requires human triage — context can make this legitimate)

Usage:
  python3 scripts/validate-brand-niche.py /path/to/site
  python3 scripts/validate-brand-niche.py --all            (all sites via portfolio.yaml)
  python3 scripts/validate-brand-niche.py /path/to/site --verbose

Exit codes:
  0 = all checks PASS or WARN (no fabrication confirmed)
  1 = one or more FAIL (fabricated brand confirmed)
  2 = tool error (missing site dir, missing required files)
"""

import argparse
import os
import re
import sys
from pathlib import Path

import yaml

# ── Brand taxonomy ────────────────────────────────────────────────────────────
# Universal suspect brands by category. Whitelisted per niche below.

SUSPECT_BRANDS = {
    # Automotive manufacturers — don't make senior care, sauna, coffee, cookware, etc.
    # Exception: overlanding niche (vehicle mods/gear), cycling (some e-bikes), gardening (Honda)
    "volkswagen":  "automotive",
    "vw":          "automotive",
    "toyota":      "automotive",
    "ford":        "automotive",
    "bmw":         "automotive",
    "mercedes":    "automotive",
    "mercedes-benz": "automotive",
    "chevy":       "automotive",
    "chevrolet":   "automotive",
    "nissan":      "automotive",
    "hyundai":     "automotive",
    "kia":         "automotive",
    "subaru":      "automotive",
    "dodge":       "automotive",
    "jeep":        "automotive",
    "tesla":       "automotive",
    "ram":         "automotive",
    "audi":        "automotive",
    "lexus":       "automotive",
    "acura":       "automotive",
    "cadillac":    "automotive",
    "buick":       "automotive",

    # Tech giants — don't make niche products in most verticals
    # Exception: cameras (Sony/Samsung), hearing aids (Sony/Apple Watch), senior care (Apple Watch)
    "microsoft":   "tech_giant",
    "facebook":    "tech_giant",
    "meta":        "tech_giant",

    # Pure entertainment / toy brands
    "lego":        "entertainment",
    "disney":      "entertainment",
    "mattel":      "entertainment",

    # Fast fashion — only relevant to fitness/sports niche
    "h&m":         "fashion",
    "zara":        "fashion",
    "gap":         "fashion",
    "forever21":   "fashion",
}

# ── Per-niche configs ─────────────────────────────────────────────────────────
# Maps site.niche → brands that are LEGITIMATE in that niche (override suspect list).
# Also captures notes for reviewer context.

NICHE_WHITELIST = {
    # Overlanding: vehicle brands ARE the product category (Toyota 4Runner mods, Jeep lifts)
    "overlanding": {
        "brands": {"toyota", "ford", "jeep", "chevy", "chevrolet", "nissan", "subaru",
                   "dodge", "ram", "mercedes", "honda"},
        "note": "Vehicle brands are the primary product category in overlanding gear",
    },
    # Cycling: some manufacturers cross automotive → e-bikes
    "cycling": {
        "brands": {"honda", "yamaha", "kawasaki"},
        "note": "Honda/Yamaha produce e-bikes; Kawasaki produces some utility bikes",
    },
    # Cameras: Sony, Samsung, Google, Apple all make cameras or camera-adjacent devices
    "camera": {
        "brands": {"sony", "samsung", "google", "apple", "microsoft"},
        "note": "Major tech companies produce cameras and camera software",
    },
    "cameras": {
        "brands": {"sony", "samsung", "google", "apple", "microsoft"},
        "note": "Major tech companies produce cameras and camera software",
    },
    # Hearing aids: Sony makes OTC hearing aids; Apple Watch has hearing health features
    "hearing": {
        "brands": {"sony", "samsung", "apple"},
        "note": "Sony/Apple produce OTC hearing aids and hearing-health wearables",
    },
    "hearing aid": {
        "brands": {"sony", "samsung", "apple"},
        "note": "Sony/Apple produce OTC hearing aids and hearing-health wearables",
    },
    # Senior caregiving: Apple Watch fall detection; Amazon as search modifier is common
    "caregiving": {
        "brands": {"apple", "amazon"},
        "note": "Apple Watch used for fall detection; Amazon appears as search modifier",
    },
    "senior caregiving": {
        "brands": {"apple", "amazon"},
        "note": "Apple Watch used for fall detection; Amazon appears as search modifier",
    },
    # Gardening: Honda makes lawn mowers; Husqvarna (Swedish automotive → outdoor power)
    "gardening": {
        "brands": {"honda", "husqvarna"},
        "note": "Honda/Husqvarna produce lawn mowers and outdoor power equipment",
    },
    # Sauna, coffee, barbecue, kitchen, entertaining: no automotive/tech overrides needed
    "home sauna": {"brands": set(), "note": ""},
    "sauna":      {"brands": set(), "note": ""},
    "coffee":     {"brands": set(), "note": ""},
    "barbecue":   {"brands": set(), "note": ""},
    "kitchen":    {"brands": set(), "note": ""},
    "home entertaining": {"brands": set(), "note": ""},
    "fitness":    {
        "brands": {"nike", "adidas", "under armour", "puma", "reebok"},
        "note": "Sports apparel brands are legitimate in fitness niche",
    },
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_site_config(site_dir: Path) -> dict:
    cfg_path = site_dir / "site.config.yaml"
    if not cfg_path.exists():
        raise FileNotFoundError(f"site.config.yaml not found at {cfg_path}")
    with open(cfg_path) as f:
        return yaml.safe_load(f)


def niche_whitelist_for(niche: str) -> set:
    """Return the set of whitelisted brand tokens for a given niche string."""
    niche_lower = niche.lower()
    # Try exact match first, then prefix match
    for key, cfg in NICHE_WHITELIST.items():
        if key in niche_lower or niche_lower in key:
            return cfg["brands"]
    return set()


def extract_frontmatter(raw: str):
    m = re.match(r'^---\n([\s\S]*?)\n---', raw)
    if not m:
        return None, raw
    try:
        fm = yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        return None, raw
    body = raw[m.end():]
    return fm, body


def word_boundary_search(pattern: str, text: str) -> bool:
    return bool(re.search(r'\b' + re.escape(pattern) + r'\b', text, re.IGNORECASE))


# ── Core scan ─────────────────────────────────────────────────────────────────

def scan_site(site_dir: Path, verbose: bool = False) -> dict:
    """
    Scan all articles in site_dir/content/articles/ and return findings.
    Returns: {'site': str, 'niche': str, 'total': int, 'h1_fails': list, 'h2_warns': list}
    """
    articles_dir = site_dir / "content" / "articles"
    if not articles_dir.exists():
        return None

    cfg = load_site_config(site_dir)
    niche = cfg.get("site", {}).get("niche", "unknown")
    brand_name = cfg.get("site", {}).get("brand_name", site_dir.name)

    whitelist = niche_whitelist_for(niche)
    h1_fails = []
    h2_warns = []
    total = 0

    for fname in sorted(os.listdir(articles_dir)):
        if not fname.endswith(".md"):
            continue
        total += 1
        slug = fname[:-3]
        raw = (articles_dir / fname).read_text()
        fm, body = extract_frontmatter(raw)
        if fm is None:
            continue

        title = str(fm.get("title", ""))
        category = str(fm.get("category", ""))
        hub = str(fm.get("hub", ""))
        check_text = f"{slug} {title}".lower()

        for brand, brand_category in SUSPECT_BRANDS.items():
            if brand in whitelist:
                continue
            if not word_boundary_search(brand, check_text):
                continue

            brand_in_body = word_boundary_search(brand, body)

            # H1: brand in title/slug but absent from body → fabrication
            if not brand_in_body:
                h1_fails.append({
                    "slug": slug,
                    "title": title,
                    "brand": brand,
                    "brand_category": brand_category,
                    "hub": hub,
                    "article_category": category,
                    "verdict": "FABRICATED — brand in headline, absent from body",
                })
            else:
                # H2: brand present but category is incompatible with niche
                # Heuristic: if article is NOT about that brand's category of products
                # (e.g., chevy brand present + article category is bedroom-safety)
                niche_tokens = niche.lower().split()
                brand_cat_tokens = brand_category.lower().replace("_", " ").split()
                hub_lower = hub.lower()
                cat_lower = category.lower()

                # Contamination signals: hub/category uses niche vocab, not brand-category vocab
                niche_vocab_in_hub = any(t in hub_lower or t in cat_lower for t in niche_tokens)
                brand_vocab_in_hub = any(t in hub_lower or t in cat_lower for t in brand_cat_tokens)

                if niche_vocab_in_hub and not brand_vocab_in_hub:
                    h2_warns.append({
                        "slug": slug,
                        "title": title,
                        "brand": brand,
                        "brand_category": brand_category,
                        "hub": hub,
                        "article_category": category,
                        "verdict": "CONTAMINATION — brand category incompatible with hub/article category",
                    })
                elif verbose:
                    pass  # brand present + body + compatible hub → likely legitimate

    return {
        "site": brand_name,
        "site_slug": site_dir.name,
        "niche": niche,
        "total": total,
        "h1_fails": h1_fails,
        "h2_warns": h2_warns,
    }


# ── Output ────────────────────────────────────────────────────────────────────

def print_site_report(result: dict, verbose: bool = False):
    site = result["site"]
    niche = result["niche"]
    total = result["total"]
    h1 = result["h1_fails"]
    h2 = result["h2_warns"]

    total_issues = len(h1) + len(h2)
    status = "FAIL" if h1 else ("WARN" if h2 else "PASS")
    status_label = {"FAIL": "❌ FAIL", "WARN": "⚠  WARN", "PASS": "✓  PASS"}[status]

    print(f"\n{'='*70}")
    print(f"{status_label}  {site}  [{niche}]  ({total} articles, {total_issues} issues)")
    print(f"{'='*70}")

    if not h1 and not h2:
        if verbose:
            print("  No brand fabrication or niche contamination detected.")
        return

    if h1:
        print(f"\n  H1 FABRICATED BRAND ({len(h1)} articles) — FAIL")
        print(f"  {'SLUG':<50} {'BRAND':<15} {'HUB'}")
        print(f"  {'-'*80}")
        for r in h1:
            print(f"  {r['slug']:<50} {r['brand']:<15} {r['hub']}")
            if verbose:
                print(f"    Title: {r['title']}")
                print(f"    Note:  {r['verdict']}")

    if h2:
        print(f"\n  H2 NICHE CONTAMINATION ({len(h2)} articles) — WARN (triage required)")
        print(f"  {'SLUG':<50} {'BRAND':<15} {'HUB'}")
        print(f"  {'-'*80}")
        for r in h2:
            print(f"  {r['slug']:<50} {r['brand']:<15} {r['hub']}")
            if verbose:
                print(f"    Title: {r['title']}")
                print(f"    Note:  {r['verdict']}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="V8 fake-brand / niche-contamination validator"
    )
    parser.add_argument(
        "site_dir",
        nargs="?",
        help="Path to site directory (omit if using --all)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Scan all sites listed in portfolio.yaml",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show full details for each finding",
    )
    args = parser.parse_args()

    if not args.all and not args.site_dir:
        parser.print_help()
        sys.exit(2)

    if args.all:
        platform_root = Path(__file__).parent.parent
        portfolio_path = platform_root / "portfolio.yaml"
        if not portfolio_path.exists():
            print(f"ERROR: portfolio.yaml not found at {portfolio_path}", file=sys.stderr)
            sys.exit(2)
        with open(portfolio_path) as f:
            portfolio = yaml.safe_load(f)

        sites = portfolio.get("sites", [])
        parent_dir = platform_root.parent
        site_dirs = [(parent_dir / s["slug"]) for s in sites]
    else:
        site_dirs = [Path(args.site_dir).resolve()]

    any_fail = False
    summary_rows = []

    for site_dir in site_dirs:
        if not site_dir.exists():
            print(f"  SKIP {site_dir.name} — directory not found")
            continue
        articles_dir = site_dir / "content" / "articles"
        if not articles_dir.exists():
            print(f"  SKIP {site_dir.name} — no content/articles/ directory")
            continue

        try:
            result = scan_site(site_dir, verbose=args.verbose)
        except FileNotFoundError as e:
            print(f"  ERROR {site_dir.name}: {e}", file=sys.stderr)
            continue

        if result is None:
            continue

        print_site_report(result, verbose=args.verbose)

        h1_count = len(result["h1_fails"])
        h2_count = len(result["h2_warns"])
        status = "FAIL" if h1_count else ("WARN" if h2_count else "PASS")
        if h1_count:
            any_fail = True
        summary_rows.append((result["site_slug"], result["niche"], result["total"], h1_count, h2_count, status))

    if len(summary_rows) > 1:
        print(f"\n\n{'='*70}")
        print("PORTFOLIO SUMMARY")
        print(f"{'='*70}")
        print(f"  {'SITE':<35} {'NICHE':<22} {'ARTS':>5} {'H1':>4} {'H2':>4}  STATUS")
        print(f"  {'-'*75}")
        for slug, niche, total, h1c, h2c, status in summary_rows:
            icon = "❌" if status == "FAIL" else ("⚠ " if status == "WARN" else "✓ ")
            print(f"  {slug:<35} {niche:<22} {total:>5} {h1c:>4} {h2c:>4}  {icon} {status}")
        total_arts = sum(r[2] for r in summary_rows)
        total_h1 = sum(r[3] for r in summary_rows)
        total_h2 = sum(r[4] for r in summary_rows)
        print(f"  {'TOTAL':<35} {'':22} {total_arts:>5} {total_h1:>4} {total_h2:>4}")

    sys.exit(1 if any_fail else 0)


if __name__ == "__main__":
    main()
