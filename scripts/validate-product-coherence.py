#!/usr/bin/env python3
"""
validate-product-coherence.py — V15 product-selection coherence validator
Affiliate Platform preflight Check 13.

Catches zero-overlap mismatches: articles recommending products with no topical
tokens in common with the article's slug, title, and primary keyword.

Origin: FFC audit found a collapsible-walking-canes article containing an ATV
product reference — zero semantic overlap. No existing validator caught it because
the product had a valid hub and passed V14 sibling/parent checks.

Detection algorithm:
  1. Extract article topic tokens from slug + title + primary_keyword (after
     filtering STOP_WORDS)
  2. Extract product tokens from product_key + product name
  3. Compute token overlap (intersection)
  4. Zero overlap AND product has ≥2 topical tokens → candidate mismatch
  5. Hub-affinity downgrade (Option B): if article hub and product hub share the
     same parent category in navigation.yaml, downgrade FAIL → WARN. This reduces
     false positives for complementary product pairings (e.g. decor in tablescaping
     articles) while preserving detection of truly incoherent placements (e.g. ATV
     in walking-cane articles, which cross unrelated nav branches).

Usage:
  python3 scripts/validate-product-coherence.py /path/to/site
  python3 scripts/validate-product-coherence.py /path/to/site --verbose
  python3 scripts/validate-product-coherence.py --all
  python3 scripts/validate-product-coherence.py --all --report-dir /tmp/v15-reports/

Exit codes:
  0 = no incoherent product placements found
  1 = one or more incoherent placements found
  2 = tool error (missing site dir, missing files)
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Optional

import yaml


# ── Hub graph (Option B affinity downgrade) ──────────────────────────────────

def _build_hub_graph(site_root: Path) -> dict:
    """Minimal hub graph from navigation.yaml for Option B hub-affinity check.

    Returns {hub_slug: {'parent': parent_category_slug or None}} so we can test
    whether two hubs share a common parent category.
    """
    nav_path = site_root / 'config/navigation.yaml'
    if not nav_path.exists():
        return {}
    try:
        with open(nav_path, encoding='utf-8') as f:
            nav = yaml.safe_load(f) or {}
    except yaml.YAMLError:
        return {}

    graph: dict = {}
    for cat in nav.get('categories', []):
        cat_slug = cat.get('slug', '')
        hub_slugs = [h.get('slug', '') for h in cat.get('hubs', []) if h.get('slug')]
        if not hub_slugs:
            continue
        if hub_slugs == [cat_slug]:
            graph.setdefault(cat_slug, {'parent': None})
        else:
            graph.setdefault(cat_slug, {'parent': None})
            for hub_slug in hub_slugs:
                graph.setdefault(hub_slug, {'parent': cat_slug})
    return graph


def _hubs_share_parent(article_hub: str, product_hub: str, graph: dict) -> bool:
    """Return True if both hubs have the same non-None parent category."""
    if not article_hub or not product_hub:
        return False
    a_parent = graph.get(article_hub, {}).get('parent')
    p_parent = graph.get(product_hub, {}).get('parent')
    return bool(a_parent and p_parent and a_parent == p_parent)


# ── Stop words ────────────────────────────────────────────────────────────────

STOP_WORDS = {
    # English function words
    'a', 'an', 'the', 'and', 'or', 'for', 'of', 'in', 'on', 'to', 'is', 'are',
    'was', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
    'will', 'would', 'could', 'should', 'may', 'might', 'shall', 'can',
    'with', 'by', 'at', 'as', 'from', 'that', 'this', 'it', 'its',
    'not', 'no', 'nor', 'but', 'if', 'so', 'yet', 'both', 'either', 'than',
    'into', 'over', 'after', 'before', 'between', 'up', 'out', 'about',
    'my', 'your', 'our', 'their', 'his', 'her', 'we', 'you', 'they', 'he', 'she',
    'me', 'us', 'him', 'them', 'who', 'which', 'what', 'when', 'where', 'how',
    'all', 'each', 'every', 'any', 'some', 'most', 'more', 'much', 'many',
    'other', 'another', 'such', 'own', 'same', 'than', 'too', 'very',
    'just', 'also', 'even', 'still', 'back', 'off', 'down',
    # Platform-generic tokens (appear in nearly every article/product)
    'set', 'piece', 'best', 'top', 'buy', 'guide', 'review', 'reviews',
    'pick', 'picks', 'choice', 'choices', 'option', 'options',
    'product', 'products', 'item', 'items',
    'vs', 'versus', 'compare', 'comparison',
    'new', 'good', 'great', 'better', 'right',
    # Numbers and counts (covered by spec-consistency V16)
    'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten',
    'pack', 'ct', 'pc', 'pcs',
    # Single characters / short noise
}


def _stem(token: str) -> str:
    """Light suffix normalization for common niche-vocabulary morphological variants.

    Handles the pattern where articles use compound or plural forms ('glassware',
    'linens', 'napkins') while product keys use root forms ('glass', 'linen',
    'napkin'). Rules applied in order:

    1. '-ware' compound suffix: 'glassware'→'glass', 'dinnerware'→'dinner'
    2. '-es' plural when the stem ends in a doubled consonant: 'glasses'→'glass',
       'addresses'→'address'. Skips words where the -es-stripped form would end in
       a vowel (e.g. 'vases' falls through to rule 3).
    3. Doubled-consonant protection: words already ending in 'ss', 'll', 'ff', 'tt'
       are treated as base forms — do NOT strip trailing 's' from 'glass', 'press'.
    4. Simple trailing 's': 'linens'→'linen', 'vases'→'vase', 'tablecloths'→'tablecloth'.
    """
    if len(token) <= 3:
        return token
    # Rule 1: '-ware' compound (e.g. 'glassware'→'glass', 'dinnerware'→'dinner')
    if token.endswith('ware') and len(token) > 6:
        return token[:-4]
    # Rule 2: '-es' when stripped form ends in doubled consonant
    # e.g. 'glasses'→'glass', 'addresses'→'address'
    if token.endswith('es') and len(token) > 4:
        candidate = token[:-2]
        if len(candidate) >= 2 and candidate[-1] == candidate[-2]:
            return candidate
    # Rule 3: protect base forms ending in doubled consonant (don't strip 's' from them)
    # e.g. 'glass', 'press', 'class', 'grass' — these are base forms, not plurals
    if len(token) >= 2 and token[-1] == token[-2]:
        return token
    # Rule 4: simple trailing 's' for plurals — require stem ≥4 chars to avoid
    # stripping 3-char foreign base forms like 'glas' (German for glass, used in
    # brand names like 'Zwiesel Glas') into meaningless 'gla'.
    if token.endswith('s') and len(token) > 4:
        return token[:-1]
    return token


# Explicit cross-language token equivalences — maps variant forms to canonical English.
# Only add entries that are clearly domain-specific with no false-positive risk.
_TOKEN_EQUIVALENCES: dict[str, str] = {
    # German 'Glas' (glass) appears as 'glas' in brand names like 'Zwiesel Glas'.
    # After stemming 'glas' remains 'glas' (4 chars, protected by rule 4).
    # Map it to 'glass' so glassware articles and glassware products share a token.
    'glas': 'glass',
    # 'knives' stems to 'knive' (rule 4: strip trailing 's').
    # 'knife' is already a base form and stays 'knife'.
    # Map 'knive' → 'knife' so knife-product names match articles with 'knives' in slug/title.
    'knive': 'knife',
    # 'birdbath' is a compound that tokenizes as one word; bird-bath articles split to 'bird' + 'bath'.
    # Map 'birdbath' → 'bird' so birdbath products match bird-bath and bird-feeder articles.
    'birdbath': 'bird',
    # 'composter' is the product-name form; composting articles use 'compost' as the stem.
    # Map 'composter' → 'compost' so composter products match compost/composting articles.
    'composter': 'compost',
    # 'lighting' is the product-name form; outdoor-light articles use 'light' as the stem.
    # Map 'lighting' → 'light' so landscape lighting products match outdoor-light articles.
    'lighting': 'light',
    # 'composting' and 'vermicomposting' don't stem to 'compost' (no -ing rule in this stemmer).
    # Map both to 'compost' so worm/composting products match compost-bin articles.
    'composting': 'compost',
    'vermicomposting': 'compost',
    # 'hummingbird' is a compound; bird-bath articles tokenize 'bird' separately.
    # Map 'hummingbird' → 'bird' so hummingbird feeders match bird-bath articles.
    'hummingbird': 'bird',
    # 'gardening' doesn't stem to 'garden' (no -ing rule).
    # Map 'gardening' → 'garden' so gardening-glove products match garden articles.
    'gardening': 'garden',
}


def _tokenize(text: str) -> set[str]:
    """Split text into lowercase alphanumeric tokens, filter stop words and length-1 tokens.
    Applies light suffix stemming so morphological variants ('glassware'/'glass',
    'linens'/'linen') share a common form for overlap comparison. Also applies
    explicit cross-language equivalences (e.g. German 'glas' → 'glass').
    """
    raw = re.findall(r'[a-z0-9]+', text.lower())
    result: set[str] = set()
    for t in raw:
        if len(t) <= 1 or t in STOP_WORDS:
            continue
        stemmed = _stem(t)
        result.add(_TOKEN_EQUIVALENCES.get(stemmed, stemmed))
    return result


# ── Token extractors ──────────────────────────────────────────────────────────

def extract_topic_tokens(article_fm: dict, article_slug: str) -> set[str]:
    """Extract meaningful tokens from article slug, title, and keyword fields."""
    sources = [
        article_slug,
        article_fm.get('title', '') or '',
        article_fm.get('primary_keyword', '') or '',
        article_fm.get('target_keyword', '') or '',
        article_fm.get('description', '') or '',
    ]
    tokens: set[str] = set()
    for s in sources:
        if s:
            tokens |= _tokenize(s)
    return tokens


def extract_product_tokens(product_entry: dict, product_key: str) -> set[str]:
    """Extract meaningful tokens from product key and product name.

    Falls back to 'title' when 'name' is absent — older sites use 'name:',
    newer pipeline-generated sites use 'title:' in products.yaml.
    """
    sources = [
        product_key,
        product_entry.get('name', '') or product_entry.get('title', '') or '',
    ]
    tokens: set[str] = set()
    for s in sources:
        if s:
            tokens |= _tokenize(s)
    return tokens


# ── Coherence check ───────────────────────────────────────────────────────────

def check_coherence(
    article_tokens: set[str],
    product_tokens: set[str],
    article_filename: str,
    product_key: str,
    article_hub: str = '',
    product_hub: str = '',
    graph: Optional[dict] = None,
) -> Optional[dict]:
    """Return a finding dict if product is incoherent with the article, else None.

    Products with fewer than 2 topical tokens are too generic to validate
    (e.g. a product named only "Premium Set" has no domain signal).

    Severity is FAIL unless Option B hub-affinity downgrade applies: if both hubs
    share the same parent category in the nav graph, severity is WARN (non-blocking).
    """
    if len(product_tokens) < 2:
        return None

    overlap = article_tokens & product_tokens
    if overlap:
        return None

    # Option B: downgrade to WARN when hubs share a parent category (complementary products)
    # Option B2: downgrade to WARN when article and product share the exact same hub —
    #   within-hub cross-references are editorial choices (e.g. a nakiri article listing
    #   a chef's knife as an alternative), not structural incoherence like an ATV in a
    #   walking-cane article (which crosses unrelated nav branches).
    if graph is not None and (
        _hubs_share_parent(article_hub, product_hub, graph)
        or (article_hub and product_hub and article_hub == product_hub)
    ):
        severity = 'WARN'
    else:
        severity = 'FAIL'

    return {
        'article':         article_filename,
        'product_key':     product_key,
        'article_tokens':  sorted(article_tokens)[:12],
        'product_tokens':  sorted(product_tokens)[:12],
        'overlap':         [],
        'severity':        severity,
    }


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


# ── Site scanner ──────────────────────────────────────────────────────────────

def scan_site(site_root: Path, verbose: bool = False) -> Optional[dict]:
    """Scan all articles for incoherent product placements.

    Returns None if content/articles/ does not exist.
    Returns dict: {total_articles, total_refs, mismatches: list[dict]}
    """
    articles_dir = site_root / 'content/articles'
    if not articles_dir.exists():
        return None

    products = load_products(site_root)
    if not products:
        return {'total_articles': 0, 'total_refs': 0, 'mismatches': []}

    graph = _build_hub_graph(site_root)

    all_mismatches: list[dict] = []
    total_refs = 0
    total_articles = 0

    for article_path in sorted(articles_dir.glob('*.md')):
        total_articles += 1
        text = article_path.read_text(encoding='utf-8')
        fm = _parse_frontmatter(text)

        article_slug   = article_path.stem
        article_hub    = fm.get('hub', '') or ''
        article_tokens = extract_topic_tokens(fm, article_slug)

        article_products = fm.get('products', []) or []
        for prod_entry in article_products:
            if not isinstance(prod_entry, dict):
                continue
            product_key = prod_entry.get('id', '')
            if not product_key or product_key not in products:
                continue

            total_refs += 1
            product_entry  = products[product_key]
            product_hub    = product_entry.get('hub', '') or ''
            product_tokens = extract_product_tokens(product_entry, product_key)

            finding = check_coherence(
                article_tokens, product_tokens,
                article_path.name, product_key,
                article_hub=article_hub, product_hub=product_hub, graph=graph,
            )
            if finding:
                all_mismatches.append(finding)

    return {
        'total_articles': total_articles,
        'total_refs':     total_refs,
        'mismatches':     all_mismatches,
    }


# ── CLI output helpers ────────────────────────────────────────────────────────

def print_site_report(site_name: str, result: dict, verbose: bool = False) -> None:
    mismatches = result['mismatches']
    fails      = [m for m in mismatches if m.get('severity') == 'FAIL']
    warns      = [m for m in mismatches if m.get('severity') == 'WARN']
    arts       = result['total_articles']
    refs       = result['total_refs']

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

    for severity_label, bucket in (('FAIL', fails), ('WARN', warns)):
        if not bucket:
            continue
        from collections import defaultdict
        by_article: dict = defaultdict(list)
        for m in bucket:
            by_article[m['article']].append(m)
        for article, findings in sorted(by_article.items()):
            print(f"   {article}")
            for f in findings:
                print(f"     [{severity_label}] product={f['product_key']!r}  zero token overlap")
                if verbose:
                    print(f"       article tokens: {f['article_tokens']}")
                    print(f"       product tokens: {f['product_tokens']}")

    if not mismatches and verbose:
        print(f"   No incoherent product placements in {refs} refs ✓")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='V15 product-selection coherence validator — affiliate platform',
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
                        help='Show token lists for each mismatch')
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

        n_fails = sum(1 for m in result['mismatches'] if m.get('severity') == 'FAIL')
        n_warns = sum(1 for m in result['mismatches'] if m.get('severity') == 'WARN')
        if n_fails:
            any_fail = True

        summary_rows.append((site_dir.name, result['total_articles'], result['total_refs'],
                              n_fails, n_warns))

        if args.report_dir:
            rpath = Path(args.report_dir) / f'{site_dir.name}-product-coherence.yaml'
            with open(rpath, 'w', encoding='utf-8') as f:
                yaml.dump(result, f, allow_unicode=True, sort_keys=False)

    if len(summary_rows) > 1:
        print(f"\n\n{'=' * 65}")
        print('PORTFOLIO SUMMARY — V15 Product-Selection Coherence Validator')
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
