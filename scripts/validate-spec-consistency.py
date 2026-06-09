#!/usr/bin/env python3
"""
validate-spec-consistency.py — V16 spec-consistency validator
Affiliate Platform preflight Check 11.

Catches spec mismatches between article body text and products.yaml ground truth.
Origin incident: LogHog brand swap introduced "Set of 4" claims in articles while
products.yaml carried the correct "Set of 6" value after substitution.

Detection anchors (structured locations — high signal, near-zero false positives):
  1. Product link text  — [Display Name (Spec)](product:key)
  2. H3 heading text    — ### Display Name (Spec) → matched to nearest product:key
     within next 80 lines of heading

Spec types detected:
  set_size, piece_count, capacity_volume, capacity_oz, weight_lb,
  capacity_gallon, capacity_person, capacity_cup, capacity_burner, wheel_count

Mismatch rule: flag only when article text and products.yaml BOTH carry the same
spec_type but with DIFFERENT values. If the products.yaml name omits the spec,
or the article link text omits it, no comparison is possible → no flag.

Usage:
  python3 scripts/validate-spec-consistency.py /path/to/site
  python3 scripts/validate-spec-consistency.py /path/to/site --verbose
  python3 scripts/validate-spec-consistency.py --all
  python3 scripts/validate-spec-consistency.py --all --report-dir /tmp/spec-reports/

Exit codes:
  0 = no mismatches found (or site has no articles)
  1 = one or more spec mismatches found
  2 = tool error (missing site dir, missing files)
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Optional

import yaml


# ── Spec pattern registry ─────────────────────────────────────────────────────
# Each entry: (regex, spec_type)
# Group 1 must capture the quantity value (digit or word form).

WORD_NUM_ALTS = r'one|two|three|four|five|six|seven|eight|nine|ten|twelve|sixteen|twenty-four'

SPEC_PATTERNS = [
    (r'\bset\s+of\s+(\d+)\b',                                    'set_size'),
    (rf'\bset\s+of\s+({WORD_NUM_ALTS})\b',                       'set_size'),
    (r'\b(\d+)\s*-\s*piece\b',                                    'piece_count'),
    (r'\b(\d+)\s+piece\b',                                        'piece_count'),
    (r'\b(\d+)\s*-?\s*(qt|quart)\b',                             'capacity_qt'),
    (r'\b(\d+)\s*-?\s*(oz|ounce)\b',                             'capacity_oz'),
    (r'\b(\d+)\s*-?\s*(lb|pound)\b',                             'weight_lb'),
    (r'\b(\d+)\s*-?\s*(gal|gallon)\b',                           'capacity_gal'),
    (rf'\b(\d+|{WORD_NUM_ALTS})\s*-?\s*person\b',                'capacity_person'),
    (rf'\b(\d+|{WORD_NUM_ALTS})\s*-?\s*seat(?:er)?\b',          'capacity_seat'),
    (rf'\b(\d+|{WORD_NUM_ALTS})\s*-?\s*cup\b',                  'capacity_cup'),
    (rf'\b(\d+|{WORD_NUM_ALTS})\s*-?\s*burner\b',               'capacity_burner'),
    (rf'\b(\d+|{WORD_NUM_ALTS})\s*-?\s*wheel\b',                'wheel_count'),
]

_COMPILED = [(re.compile(pat, re.IGNORECASE), stype) for pat, stype in SPEC_PATTERNS]

WORD_TO_NUM = {
    'one': '1', 'two': '2', 'three': '3', 'four': '4', 'five': '5',
    'six': '6', 'seven': '7', 'eight': '8', 'nine': '9', 'ten': '10',
    'twelve': '12', 'sixteen': '16', 'twenty-four': '24',
}

LINK_RE = re.compile(r'\[([^\]]+)\]\(product:([\w-]+)\)')
H3_RE   = re.compile(r'^### (.+)$')


def _normalize(v: str) -> str:
    return WORD_TO_NUM.get(v.lower(), v.lower())


def extract_specs(text: str) -> list[tuple[str, str]]:
    """Return list of (spec_type, normalized_value) from text. May contain duplicates."""
    specs = []
    for pattern, spec_type in _COMPILED:
        for m in pattern.finditer(text):
            specs.append((spec_type, _normalize(m.group(1))))
    return specs


def load_products(site_root: Path) -> dict:
    p = site_root / 'content/products/products.yaml'
    if not p.exists():
        return {}
    with open(p, encoding='utf-8') as f:
        return yaml.safe_load(f) or {}


def _compare(article_specs: list, product_name: str) -> list[tuple[str, str, str]]:
    """Compare article_specs against specs extracted from product_name.
    Returns list of (spec_type, article_val, product_val) for each mismatch."""
    prod_specs = dict(extract_specs(product_name))
    mismatches = []
    seen = set()
    for spec_type, article_val in article_specs:
        key = (spec_type, article_val)
        if key in seen:
            continue
        seen.add(key)
        if spec_type in prod_specs and prod_specs[spec_type] != article_val:
            mismatches.append((spec_type, article_val, prod_specs[spec_type]))
    return mismatches


def scan_article(article_path: Path, products: dict) -> list[dict]:
    """Scan a single article for spec mismatches. Returns list of mismatch dicts."""
    mismatches = []
    text = article_path.read_text(encoding='utf-8')
    lines = text.splitlines()

    # ── Detection 1: product link text ───────────────────────────────────────
    # Pattern: [Display Name (Spec)](product:key)
    # The spec may be in parens or inline in the display name.
    for lineno, line in enumerate(lines, 1):
        for m in LINK_RE.finditer(line):
            display = m.group(1)
            key = m.group(2)
            if key not in products:
                continue
            prod_name = (products[key].get('name') or '')
            article_specs = extract_specs(display)
            if not article_specs:
                continue
            for spec_type, article_val, prod_val in _compare(article_specs, prod_name):
                mismatches.append({
                    'article':           article_path.name,
                    'product_key':       key,
                    'product_yaml_name': prod_name,
                    'location':          f'link_text_line_{lineno}',
                    'claim':             f'{spec_type}={article_val}',
                    'actual':            f'{spec_type}={prod_val}',
                    'severity':          'critical',
                    'excerpt':           line.strip()[:120],
                })

    # ── Detection 2: H3 heading anchored to nearest product link ─────────────
    # Find H3 headings with spec patterns, then look ahead for the first
    # product:key link in that section. Compare heading specs to that product.
    #
    # False-positive guards:
    #   - Skip headings that end with "?" (FAQ questions, not product section titles)
    #   - Stop lookahead at the next H2/H3 boundary (don't cross into adjacent sections)
    HEADING_RE = re.compile(r'^#{2,3} ')
    for lineno, line in enumerate(lines):
        h3_m = H3_RE.match(line)
        if not h3_m:
            continue
        heading_text = h3_m.group(1).strip()
        if heading_text.endswith('?'):
            continue  # FAQ question — not a product spec claim
        heading_specs = extract_specs(heading_text)
        if not heading_specs:
            continue

        # Check if the heading line itself contains an embedded product link — use it as
        # the anchor directly. This prevents misanchoring: without this check, when a
        # heading contains [Name (Spec)](product:key), the lookahead starts at lineno+1
        # and may anchor to a comparison product mentioned below, producing a false positive.
        heading_link_m = LINK_RE.search(line)
        if heading_link_m:
            key = heading_link_m.group(2)
            if key in products:
                prod_name = (products[key].get('name') or '')
                for spec_type, heading_val, prod_val in _compare(heading_specs, prod_name):
                    mismatches.append({
                        'article':           article_path.name,
                        'product_key':       key,
                        'product_yaml_name': prod_name,
                        'location':          f'h3_heading_line_{lineno + 1}',
                        'claim':             f'{spec_type}={heading_val}',
                        'actual':            f'{spec_type}={prod_val}',
                        'severity':          'critical',
                        'excerpt':           line.strip()[:120],
                    })
                continue  # heading handled — skip lookahead

        # Lookahead: stop at next heading or end of file
        for j in range(lineno + 1, min(lineno + 81, len(lines))):
            wline = lines[j]
            if HEADING_RE.match(wline):
                break  # hit the next section — stop
            lm = LINK_RE.search(wline)
            if not lm:
                continue
            key = lm.group(2)
            if key not in products:
                continue
            prod_name = (products[key].get('name') or '')
            for spec_type, heading_val, prod_val in _compare(heading_specs, prod_name):
                mismatches.append({
                    'article':           article_path.name,
                    'product_key':       key,
                    'product_yaml_name': prod_name,
                    'location':          f'h3_heading_line_{lineno + 1}',
                    'claim':             f'{spec_type}={heading_val}',
                    'actual':            f'{spec_type}={prod_val}',
                    'severity':          'critical',
                    'excerpt':           line.strip()[:120],
                })
            break  # only anchor to the first product found in this section

    return mismatches


def scan_site(site_root: Path, verbose: bool = False) -> Optional[dict]:
    """Scan all articles in site_root for spec mismatches.

    Returns None if content/articles/ does not exist.
    Returns dict: {total_refs, total_articles, mismatches: list[dict]}
    """
    articles_dir = site_root / 'content/articles'
    if not articles_dir.exists():
        return None

    products = load_products(site_root)
    if not products:
        return {'total_refs': 0, 'total_articles': 0, 'mismatches': []}

    all_mismatches: list[dict] = []
    total_refs = 0
    total_articles = 0

    for article_path in sorted(articles_dir.glob('*.md')):
        total_articles += 1
        text = article_path.read_text(encoding='utf-8')
        total_refs += len(LINK_RE.findall(text))
        mismatches = scan_article(article_path, products)
        all_mismatches.extend(mismatches)

    return {
        'total_refs':     total_refs,
        'total_articles': total_articles,
        'mismatches':     all_mismatches,
    }


# ── CLI output helpers ────────────────────────────────────────────────────────

def print_site_report(site_name: str, result: dict, verbose: bool = False) -> None:
    mismatches = result['mismatches']
    refs       = result['total_refs']
    arts       = result['total_articles']
    status     = 'FAIL' if mismatches else 'PASS'
    icon       = '❌' if mismatches else '✓ '

    print(f"\n{icon} {site_name}  [{status}]  {arts} articles  {refs} product refs")

    if mismatches:
        # Group by article for cleaner output
        from collections import defaultdict
        by_article: dict = defaultdict(list)
        for m in mismatches:
            by_article[m['article']].append(m)

        for article, findings in sorted(by_article.items()):
            print(f"   {article}")
            for f in findings:
                print(f"     [{f['location']}]  claims {f['claim']!r}  →  yaml has {f['actual']!r}")
                if verbose:
                    print(f"       excerpt: {f['excerpt']}")
    elif verbose:
        print(f"   No spec mismatches in {refs} product references ✓")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='V16 spec-consistency validator — affiliate platform',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument('site_dir', nargs='?', default=None,
                        help='Path to site root (omit with --all)')
    parser.add_argument('--all', action='store_true',
                        help='Scan all sites in portfolio.yaml')
    parser.add_argument('--report-dir', default=None, metavar='DIR',
                        help='Write per-site YAML reports to DIR (--all mode)')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Show excerpts for each mismatch')
    args = parser.parse_args()

    if not args.all and not args.site_dir:
        parser.print_help()
        sys.exit(2)

    platform_root = Path(__file__).parent.parent

    if args.all:
        portfolio_path = platform_root / 'portfolio.yaml'
        if not portfolio_path.exists():
            print(f'ERROR: portfolio.yaml not found at {portfolio_path}', file=sys.stderr)
            sys.exit(2)
        with open(portfolio_path) as f:
            portfolio = yaml.safe_load(f)
        parent_dir = platform_root.parent
        site_dirs = [parent_dir / s['slug'] for s in portfolio.get('sites', [])]
    else:
        site_dirs = [Path(args.site_dir).resolve()]

    if args.report_dir:
        Path(args.report_dir).mkdir(parents=True, exist_ok=True)

    any_fail  = False
    summary_rows: list = []

    for site_dir in site_dirs:
        if not site_dir.exists():
            print(f'  SKIP {site_dir.name} — directory not found')
            continue

        result = scan_site(site_dir, verbose=args.verbose)
        if result is None:
            print(f'  SKIP {site_dir.name} — no content/articles/')
            continue

        print_site_report(site_dir.name, result, verbose=args.verbose)

        n = len(result['mismatches'])
        if n:
            any_fail = True

        summary_rows.append((site_dir.name, result['total_articles'], result['total_refs'], n))

        if args.report_dir:
            rpath = Path(args.report_dir) / f'{site_dir.name}-spec-consistency.yaml'
            with open(rpath, 'w', encoding='utf-8') as f:
                yaml.dump(result, f, allow_unicode=True, sort_keys=False)

    if len(summary_rows) > 1:
        print(f"\n\n{'=' * 65}")
        print('PORTFOLIO SUMMARY — V16 Spec Consistency Validator')
        print(f"{'=' * 65}")
        print(f"  {'SITE':<33}  {'ARTS':>5}  {'REFS':>5}  {'FAIL':>5}")
        print(f"  {'-' * 60}")
        for slug, arts, refs, fails in summary_rows:
            icon = '❌' if fails else '✓ '
            print(f"  {slug:<33}  {arts:>5}  {refs:>5}  {fails:>5}  {icon}")
        total_arts  = sum(r[1] for r in summary_rows)
        total_refs  = sum(r[2] for r in summary_rows)
        total_fails = sum(r[3] for r in summary_rows)
        print(f"  {'TOTAL':<33}  {total_arts:>5}  {total_refs:>5}  {total_fails:>5}")

    sys.exit(1 if any_fail else 0)


if __name__ == '__main__':
    main()
