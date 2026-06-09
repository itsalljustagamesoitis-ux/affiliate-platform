#!/usr/bin/env python3
"""
validate-hub-consistency.py — V14 hub-consistency validator
Affiliate Platform preflight Check 12.

Catches hub drift: articles referencing products whose hub field in products.yaml
does not match (or is hierarchically unrelated to) the article's own hub frontmatter.

Origin: Rule 2 in platform CLAUDE.md requires product hub == article hub. Manual
enforcement was brittle at portfolio scale; V14 automates detection.

Detection algorithm:
  1. Build hub hierarchy from config/navigation.yaml:
     {hub_slug: {parent: parent_category_slug or None, children: [sibling hub slugs]}}
  2. For each article, compare article hub (frontmatter) against each referenced
     product's hub (products.yaml)
  3. Classify relationship: same | parent_child | sibling | unrelated | cross_hub
  4. Severity: same/parent_child/cross_hub → skip, sibling → WARN, unrelated → FAIL

Product references are read from the article's frontmatter products: list (id field).

Cross-category products:
  Products that legitimately belong in multiple hub categories (e.g. a universal sensor
  compatible with both wood-fired and brand-specific heaters) can declare a cross_hubs:
  list in products.yaml. V14 treats any hub in that list as an intentional placement
  and skips it (same treatment as 'same' or 'parent_child').

  Example in products.yaml:
    my-universal-sensor:
      hub: sauna-brand-harvia
      cross_hubs:
        - sauna-wood-fired
        - sauna-traditional

Usage:
  python3 scripts/validate-hub-consistency.py /path/to/site
  python3 scripts/validate-hub-consistency.py /path/to/site --verbose
  python3 scripts/validate-hub-consistency.py --all
  python3 scripts/validate-hub-consistency.py --all --report-dir /tmp/v14-reports/

Exit codes:
  0 = no FAIL findings (WARNs are non-blocking)
  1 = one or more FAIL findings
  2 = tool error (missing site dir, missing files)
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Optional

import yaml


# ── Hub graph builder ─────────────────────────────────────────────────────────

def build_hub_graph(site_root: Path) -> dict:
    """Build hub hierarchy from config/navigation.yaml.

    Returns dict of {slug: {'parent': parent_slug_or_None, 'children': [child_slugs]}}.

    Two structural cases handled:
      - Flat/identical (OHT-style): category slug == hub slug → standalone node,
        parent=None, no sibling relationships possible within that category.
      - Multi-hub category (FFC-style): category has N>1 distinct hub slugs →
        category registered as parent, hubs registered as its children.
    """
    nav_path = site_root / 'config/navigation.yaml'
    if not nav_path.exists():
        return {}
    with open(nav_path, encoding='utf-8') as f:
        nav = yaml.safe_load(f) or {}

    graph: dict = {}
    for cat in nav.get('categories', []):
        cat_slug = cat.get('slug', '')
        hub_slugs = [h.get('slug', '') for h in cat.get('hubs', []) if h.get('slug')]

        if not hub_slugs:
            continue

        if hub_slugs == [cat_slug]:
            # OHT-style flat: category slug is also the hub slug → standalone
            if cat_slug not in graph:
                graph[cat_slug] = {'parent': None, 'children': []}
        else:
            # FFC-style multi-hub: register category as parent
            if cat_slug not in graph:
                graph[cat_slug] = {'parent': None, 'children': hub_slugs}
            for hub_slug in hub_slugs:
                if hub_slug not in graph:
                    graph[hub_slug] = {'parent': cat_slug, 'children': []}

    return graph


def classify_hub_relationship(article_hub: str, product_hub: str, graph: dict) -> str:
    """Classify the hub relationship between an article and a product.

    Returns one of: 'same', 'parent_child', 'sibling', 'unrelated'.
    """
    if article_hub == product_hub:
        return 'same'

    a_info = graph.get(article_hub, {})
    p_info = graph.get(product_hub, {})

    # parent_child: one is the direct parent of the other in the hierarchy
    if a_info.get('parent') == product_hub or p_info.get('parent') == article_hub:
        return 'parent_child'

    # sibling: both have the same non-None parent category
    a_parent = a_info.get('parent')
    p_parent = p_info.get('parent')
    if a_parent and p_parent and a_parent == p_parent:
        return 'sibling'

    return 'unrelated'


# ── Article parsing ───────────────────────────────────────────────────────────

def _parse_frontmatter(text: str) -> dict:
    if not text.startswith('---'):
        return {}
    end = text.find('\n---', 3)
    if end == -1:
        return {}
    try:
        return yaml.safe_load(text[3:end]) or {}
    except yaml.YAMLError:
        return {}


def load_products(site_root: Path) -> dict:
    p = site_root / 'content/products/products.yaml'
    if not p.exists():
        return {}
    with open(p, encoding='utf-8') as f:
        return yaml.safe_load(f) or {}


# ── Per-article scanner ───────────────────────────────────────────────────────

def scan_article(article_path: Path, products: dict, graph: dict) -> list[dict]:
    """Scan one article for hub inconsistencies. Returns list of finding dicts."""
    findings = []
    text = article_path.read_text(encoding='utf-8')
    fm = _parse_frontmatter(text)

    article_hub = fm.get('hub', '')
    if not article_hub:
        return []

    article_products = fm.get('products', []) or []

    for prod_entry in article_products:
        if not isinstance(prod_entry, dict):
            continue
        product_key = prod_entry.get('id', '')
        if not product_key or product_key not in products:
            continue

        product_entry = products[product_key]
        product_hub = product_entry.get('hub', '')
        if not product_hub:
            continue

        # cross_hubs: per-product whitelist for intentional cross-category placements
        cross_hubs = product_entry.get('cross_hubs', []) or []
        if article_hub in cross_hubs:
            continue

        relationship = classify_hub_relationship(article_hub, product_hub, graph)
        if relationship in ('same', 'parent_child'):
            continue

        if relationship == 'sibling':
            severity = 'WARN'
            suggestion = (
                f"product hub {product_hub!r} is a sibling of article hub {article_hub!r}. "
                f"Verify this cross-hub placement is intentional."
            )
        else:
            severity = 'FAIL'
            suggestion = (
                f"product hub {product_hub!r} is unrelated to article hub {article_hub!r}. "
                f"Update products.yaml hub to {article_hub!r}, or remove product from this article."
            )

        findings.append({
            'article':      article_path.name,
            'article_hub':  article_hub,
            'product_key':  product_key,
            'product_hub':  product_hub,
            'relationship': relationship,
            'severity':     severity,
            'suggestion':   suggestion,
        })

    return findings


# ── Site scanner ──────────────────────────────────────────────────────────────

def scan_site(site_root: Path, verbose: bool = False) -> Optional[dict]:
    """Scan all articles for hub inconsistencies.

    Returns None if content/articles/ does not exist.
    Returns dict: {total_articles, total_refs, fails: list[dict], warns: list[dict]}
    """
    articles_dir = site_root / 'content/articles'
    if not articles_dir.exists():
        return None

    products = load_products(site_root)
    if not products:
        return {'total_articles': 0, 'total_refs': 0, 'fails': [], 'warns': []}

    graph = build_hub_graph(site_root)

    all_fails: list[dict] = []
    all_warns: list[dict] = []
    total_refs = 0
    total_articles = 0

    for article_path in sorted(articles_dir.glob('*.md')):
        total_articles += 1
        text = article_path.read_text(encoding='utf-8')
        fm = _parse_frontmatter(text)
        prods = fm.get('products', []) or []
        total_refs += len([p for p in prods if isinstance(p, dict) and p.get('id')])

        findings = scan_article(article_path, products, graph)
        for f in findings:
            if f['severity'] == 'FAIL':
                all_fails.append(f)
            else:
                all_warns.append(f)

    return {
        'total_articles': total_articles,
        'total_refs':     total_refs,
        'fails':          all_fails,
        'warns':          all_warns,
    }


# ── CLI output helpers ────────────────────────────────────────────────────────

def print_site_report(site_name: str, result: dict, verbose: bool = False) -> None:
    fails = result['fails']
    warns = result['warns']
    arts  = result['total_articles']
    refs  = result['total_refs']

    if fails:
        status = 'FAIL'
        icon   = '❌'
    elif warns:
        status = 'WARN'
        icon   = '⚠ '
    else:
        status = 'PASS'
        icon   = '✓ '

    print(f"\n{icon} {site_name}  [{status}]  {arts} articles  {refs} product refs")

    if fails:
        from collections import defaultdict
        by_article: dict = defaultdict(list)
        for f in fails:
            by_article[f['article']].append(f)
        for article, findings in sorted(by_article.items()):
            print(f"   {article}")
            for f in findings:
                print(f"     [FAIL] {f['product_key']!r}  article_hub={f['article_hub']!r}  product_hub={f['product_hub']!r}")
                if verbose:
                    print(f"       suggestion: {f['suggestion']}")

    if warns:
        from collections import defaultdict
        by_article2: dict = defaultdict(list)
        for f in warns:
            by_article2[f['article']].append(f)
        for article, findings in sorted(by_article2.items()):
            print(f"   {article}")
            for f in findings:
                print(f"     [WARN] {f['product_key']!r}  article_hub={f['article_hub']!r}  product_hub={f['product_hub']!r}")
                if verbose:
                    print(f"       suggestion: {f['suggestion']}")

    if not fails and not warns and verbose:
        print(f"   No hub inconsistencies in {refs} product references ✓")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='V14 hub-consistency validator — affiliate platform',
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
                        help='Show suggestions for each finding')
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

    any_fail     = False
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

        n_fails = len(result['fails'])
        n_warns = len(result['warns'])
        if n_fails:
            any_fail = True

        summary_rows.append((site_dir.name, result['total_articles'], result['total_refs'],
                              n_fails, n_warns))

        if args.report_dir:
            rpath = Path(args.report_dir) / f'{site_dir.name}-hub-consistency.yaml'
            with open(rpath, 'w', encoding='utf-8') as f:
                yaml.dump(result, f, allow_unicode=True, sort_keys=False)

    if len(summary_rows) > 1:
        print(f"\n\n{'=' * 65}")
        print('PORTFOLIO SUMMARY — V14 Hub Consistency Validator')
        print(f"{'=' * 65}")
        print(f"  {'SITE':<33}  {'ARTS':>5}  {'REFS':>5}  {'FAIL':>5}  {'WARN':>5}")
        print(f"  {'-' * 63}")
        for slug, arts, refs, fails, warns in summary_rows:
            icon = '❌' if fails else ('⚠ ' if warns else '✓ ')
            print(f"  {slug:<33}  {arts:>5}  {refs:>5}  {fails:>5}  {warns:>5}  {icon}")
        total_arts  = sum(r[1] for r in summary_rows)
        total_refs  = sum(r[2] for r in summary_rows)
        total_fails = sum(r[3] for r in summary_rows)
        total_warns = sum(r[4] for r in summary_rows)
        print(f"  {'TOTAL':<33}  {total_arts:>5}  {total_refs:>5}  {total_fails:>5}  {total_warns:>5}")

    sys.exit(1 if any_fail else 0)


if __name__ == '__main__':
    main()
