#!/usr/bin/env python3
"""
validate-slug-dedup.py — V1 slug near-duplicate detector
Affiliate Platform preflight suite.

Detects four classes of near-duplicate URL slugs that escape the legacy wordset check:

  Method 1 — WORD ORDER:     same tokens, different order
      ada-toilet-grab-bar ↔ ada-grab-bar-toilet
  Method 2 — PLURAL:         differ only in trailing pluralisation
      wedge-cushion ↔ wedge-cushions
  Method 3 — HYPHENATION:    differ only in hyphen placement
      go-go-mobility-scooter ↔ gogo-mobility-scooter
  Method 4 — NUMERAL/WORD:   digit vs spelled-out number (+ unit synonyms)
      three-wheel-mobility-scooter ↔ 3-wheel-mobility-scooter

Combined signatures also fire:
  M1+M2  — word-order + plural normalisation (catches order swaps AND plural variants)
  M3+M2  — dehyphen + plural normalisation   (catches 45lb- vs 45-lbs- patterns)
  M4+M2  — numeral + plural normalisation

Confidence tiers:
  HIGH   — virtually certain duplicate; same token count after normalisation → FAIL in preflight
  MEDIUM — likely duplicate with extra modifier token (possible distinct scope) → WARN
  LOW    — Jaccard similarity ≥ 0.75 on normalised token sets → INFO (review candidate)

Usage:
  python3 scripts/validate-slug-dedup.py /path/to/site
  python3 scripts/validate-slug-dedup.py /path/to/site --report /tmp/site-dedup.yaml
  python3 scripts/validate-slug-dedup.py --all
  python3 scripts/validate-slug-dedup.py --all --report-dir /tmp/dedup-reports/

Exit codes:
  0 = all clear (MEDIUM/LOW candidates are warnings, not failures)
  1 = one or more HIGH-confidence pairs found
  2 = tool error (missing files, bad arguments)
"""

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

import yaml


# ── Normalisation tables ──────────────────────────────────────────────────────

# Number-word ↔ digit and unit synonyms (all normalise to the shorter/digit form).
_TOKEN_MAP: dict[str, str] = {
    'one': '1', 'two': '2', 'three': '3', 'four': '4', 'five': '5',
    'six': '6', 'seven': '7', 'eight': '8', 'nine': '9', 'ten': '10',
    'eleven': '11', 'twelve': '12',
    # unit synonyms
    'lbs': 'lb', 'pound': 'lb', 'pounds': 'lb',
    'ounce': 'oz', 'ounces': 'oz',
    'quart': 'qt', 'quarts': 'qt',
    'foot': 'ft', 'feet': 'ft',
    'inch': 'in', 'inches': 'in',
}


# ── Token-level functions ─────────────────────────────────────────────────────

def _singularize(token: str) -> str:
    t = token.lower()
    if t.endswith('ies') and len(t) > 3:
        return t[:-3] + 'y'
    if t.endswith('ves') and len(t) > 4:
        return t[:-3] + 'f'
    if t.endswith('es') and len(t) > 3 and not t.endswith('ss'):
        return t[:-2]
    if t.endswith('s') and len(t) > 2 and not t.endswith('ss'):
        return t[:-1]
    return t


def _norm_num(token: str) -> str:
    return _TOKEN_MAP.get(token.lower(), token.lower())


def _norm(token: str) -> str:
    """Full normalisation: lowercase → numeral/unit map → singularise."""
    return _singularize(_norm_num(token.lower()))


def _tokens(slug: str) -> list[str]:
    return slug.lower().split('-')


# ── Slug signatures ───────────────────────────────────────────────────────────

def _sig_wordorder(slug: str) -> frozenset:
    """M1: frozenset of raw tokens (order-independent)."""
    return frozenset(_tokens(slug))


def _sig_wordorder_norm(slug: str) -> frozenset:
    """M1+M2+M4: frozenset of fully-normalised tokens."""
    return frozenset(_norm(t) for t in _tokens(slug))


def _sig_plural(slug: str) -> str:
    """M2: singularise each token, preserve order."""
    return '-'.join(_singularize(t) for t in _tokens(slug))


def _sig_dehyphen(slug: str) -> str:
    """M3: strip all hyphens."""
    return slug.lower().replace('-', '')


def _sig_dehyphen_norm(slug: str) -> str:
    """M3+M2: strip hyphens then singularise the whole string."""
    return _singularize(slug.lower().replace('-', ''))


def _sig_numword(slug: str) -> str:
    """M4: normalise numerals and units, preserve order."""
    return '-'.join(_norm_num(t) for t in _tokens(slug))


def _sig_numword_norm(slug: str) -> str:
    """M4+M2: normalise numerals + singularise, preserve order."""
    return '-'.join(_norm(t) for t in _tokens(slug))


# All signature descriptors: (name, function, sig_type)
_METHODS: list[tuple] = [
    ('word_order',         _sig_wordorder,      'frozenset'),
    ('word_order_norm',    _sig_wordorder_norm, 'frozenset'),
    ('plural',             _sig_plural,         'string'),
    ('hyphenation',        _sig_dehyphen,       'string'),
    ('hyphenation_plural', _sig_dehyphen_norm,  'string'),
    ('numeral_word',       _sig_numword,        'string'),
    ('numeral_word_norm',  _sig_numword_norm,   'string'),
]


# ── Jaccard similarity ────────────────────────────────────────────────────────

def _jaccard(slug_a: str, slug_b: str) -> float:
    ta = frozenset(_norm(t) for t in _tokens(slug_a))
    tb = frozenset(_norm(t) for t in _tokens(slug_b))
    if not ta and not tb:
        return 1.0
    return len(ta & tb) / len(ta | tb)


# ── Confidence heuristic ──────────────────────────────────────────────────────

def _confidence(method: str, slug_a: str, slug_b: str) -> str:
    diff = abs(len(_tokens(slug_a)) - len(_tokens(slug_b)))
    if method in ('word_order', 'plural', 'hyphenation', 'hyphenation_plural'):
        return 'high' if diff == 0 else ('medium' if diff <= 2 else 'low')
    # numeral/word and combined-norm methods: same token count = HIGH, otherwise MEDIUM
    return 'high' if diff == 0 else 'medium'


# ── Article metadata ──────────────────────────────────────────────────────────

def _read_article(path: Path) -> dict:
    try:
        text = path.read_text(encoding='utf-8')
        m = re.match(r'^---\n([\s\S]*?)\n---', text)
        fm: dict = {}
        body = text
        if m:
            try:
                fm = yaml.safe_load(m.group(1)) or {}
            except yaml.YAMLError:
                pass
            body = text[m.end():]
        return {
            'word_count': len(body.split()),
            'hub': str(fm.get('hub', '')),
            'type': str(fm.get('type', '')),
        }
    except Exception:
        return {'word_count': 0, 'hub': '', 'type': ''}


# ── Canonical suggestion ──────────────────────────────────────────────────────

def _suggest_canonical(slug_a: str, meta_a: dict, slug_b: str, meta_b: dict) -> str:
    # 1. Higher word count
    if meta_a['word_count'] != meta_b['word_count']:
        return slug_a if meta_a['word_count'] > meta_b['word_count'] else slug_b
    # 2. Plural preferred for roundup articles
    if 'roundup' in (meta_a.get('type', '') + meta_b.get('type', '')):
        if slug_a.endswith('s') and not slug_b.endswith('s'):
            return slug_a
        if slug_b.endswith('s') and not slug_a.endswith('s'):
            return slug_b
    # 3. Shorter slug
    if len(slug_a) != len(slug_b):
        return slug_a if len(slug_a) < len(slug_b) else slug_b
    # 4. Stable alphabetical tiebreaker
    return slug_a if slug_a < slug_b else slug_b


# ── Editorial note ────────────────────────────────────────────────────────────

def _editorial_note(method: str, slug_a: str, slug_b: str, canonical: str) -> str:
    diff = set(_tokens(slug_a)).symmetric_difference(set(_tokens(slug_b)))
    extra = [t for t in sorted(diff) if t not in _tokens(canonical)]
    if extra:
        return f"Verify '{', '.join(extra)}' modifier doesn't indicate distinct product scope"
    return ''


# ── Core detection ────────────────────────────────────────────────────────────

def detect_pairs(article_metas: dict) -> list:
    """
    article_metas: {slug: {'word_count': int, 'hub': str, 'type': str}}
    Returns list of pair findings sorted HIGH → MEDIUM → LOW.
    """
    slugs = sorted(article_metas)

    # Pre-compute all signatures
    sigs = {slug: {name: fn(slug) for name, fn, _ in _METHODS} for slug in slugs}

    # Group slugs by each signature
    seen: set = set()
    findings: list = []

    for method_name, _, _ in _METHODS:
        groups: dict = defaultdict(list)
        for slug in slugs:
            groups[sigs[slug][method_name]].append(slug)

        for slug_list in groups.values():
            if len(slug_list) < 2:
                continue
            for i in range(len(slug_list)):
                for j in range(i + 1, len(slug_list)):
                    sa, sb = slug_list[i], slug_list[j]
                    if sa == sb:
                        continue
                    pair_key = (min(sa, sb), max(sa, sb))
                    if pair_key in seen:
                        continue
                    seen.add(pair_key)

                    conf = _confidence(method_name, sa, sb)
                    meta_a, meta_b = article_metas[sa], article_metas[sb]
                    canon = _suggest_canonical(sa, meta_a, sb, meta_b)
                    redirect = sb if canon == sa else sa

                    findings.append({
                        'detection_method': method_name,
                        'slug_a': sa,
                        'slug_b': sb,
                        'word_count_a': meta_a['word_count'],
                        'word_count_b': meta_b['word_count'],
                        'hub_a': meta_a['hub'],
                        'hub_b': meta_b['hub'],
                        'suggested_canonical': canon,
                        'suggested_redirect': f"{redirect} → {canon}",
                        'confidence': conf,
                        'editorial_note': _editorial_note(method_name, sa, sb, canon) if conf == 'medium' else '',
                    })

    # Jaccard pass — only slugs not yet caught
    for i, sa in enumerate(slugs):
        for sb in slugs[i + 1:]:
            pair_key = (min(sa, sb), max(sa, sb))
            if pair_key in seen:
                continue
            score = _jaccard(sa, sb)
            if score < 0.75:
                continue
            seen.add(pair_key)
            meta_a, meta_b = article_metas[sa], article_metas[sb]
            canon = _suggest_canonical(sa, meta_a, sb, meta_b)
            redirect = sb if canon == sa else sa
            findings.append({
                'detection_method': 'jaccard',
                'slug_a': sa,
                'slug_b': sb,
                'word_count_a': meta_a['word_count'],
                'word_count_b': meta_b['word_count'],
                'hub_a': meta_a['hub'],
                'hub_b': meta_b['hub'],
                'suggested_canonical': canon,
                'suggested_redirect': f"{redirect} → {canon}",
                'confidence': 'low',
                'jaccard_score': round(score, 3),
                'editorial_note': '',
            })

    # Sort: HIGH first, then MEDIUM, then LOW; alphabetical within tier
    _order = {'high': 0, 'medium': 1, 'low': 2}
    findings.sort(key=lambda p: (_order.get(p['confidence'], 3), p['slug_a'], p['slug_b']))

    # Assign pair IDs
    for idx, f in enumerate(findings, 1):
        f['pair_id'] = idx

    return findings


# ── Site scanner ──────────────────────────────────────────────────────────────

def scan_site(site_root: Path, report_path: Path = None, verbose: bool = False):
    """
    Scan site_root/content/articles/ for near-duplicate slugs.
    Returns dict with keys: site, total_slugs, high, medium, low, all_pairs.
    Returns None if content/articles/ doesn't exist.
    """
    articles_dir = site_root / 'content' / 'articles'
    if not articles_dir.exists():
        return None

    md_files = sorted(articles_dir.glob('*.md'))
    if not md_files:
        return {'site': site_root.name, 'total_slugs': 0,
                'high': [], 'medium': [], 'low': [], 'all_pairs': []}

    article_metas = {f.stem: _read_article(f) for f in md_files}
    pairs = detect_pairs(article_metas)

    high   = [p for p in pairs if p['confidence'] == 'high']
    medium = [p for p in pairs if p['confidence'] == 'medium']
    low    = [p for p in pairs if p['confidence'] == 'low']

    result = {
        'site': site_root.name,
        'total_slugs': len(article_metas),
        'high': high,
        'medium': medium,
        'low': low,
        'all_pairs': pairs,
    }

    if report_path:
        _write_report(site_root.name, len(article_metas), pairs, report_path)

    return result


def _write_report(site: str, total: int, pairs: list, path: Path):
    high   = [p for p in pairs if p['confidence'] == 'high']
    medium = [p for p in pairs if p['confidence'] == 'medium']
    low    = [p for p in pairs if p['confidence'] == 'low']
    path.parent.mkdir(parents=True, exist_ok=True)
    report = {
        'site': site,
        'total_articles': total,
        'summary': {
            'high_confidence': len(high),
            'medium_confidence': len(medium),
            'low_confidence': len(low),
            'total_pairs': len(pairs),
        },
        'pairs': pairs,
    }
    with open(path, 'w', encoding='utf-8') as f:
        yaml.dump(report, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


# ── Reporting ─────────────────────────────────────────────────────────────────

def print_site_report(result: dict, verbose: bool = False):
    site  = result['site']
    total = result['total_slugs']
    high  = result['high']
    med   = result['medium']
    low   = result['low']

    status = 'FAIL' if high else ('WARN' if med else 'PASS')
    label  = {'FAIL': '❌ FAIL', 'WARN': '⚠  WARN', 'PASS': '✓  PASS'}[status]

    print(f"\n{'=' * 70}")
    print(f"{label}  {site}  ({total} slugs | {len(high)} HIGH {len(med)} MED {len(low)} LOW)")
    print(f"{'=' * 70}")

    if high:
        print(f"\n  HIGH — FAIL ({len(high)} pair(s)) — canonical decision required")
        col = 42
        print(f"  {'SLUG_A':<{col}}  {'SLUG_B':<{col}}  METHOD")
        print(f"  {'-' * (col * 2 + 14)}")
        for p in high:
            print(f"  {p['slug_a']:<{col}}  {p['slug_b']:<{col}}  {p['detection_method']}")
            print(f"    canonical: {p['suggested_canonical']}")
            print(f"    redirect:  {p['suggested_redirect']}")

    if med:
        cap = None if verbose else 10
        shown = med[:cap] if cap else med
        print(f"\n  MEDIUM — WARN ({len(med)} pair(s)) — editorial review needed")
        for p in shown:
            print(f"  [{p['detection_method']}]  {p['slug_a']}  ↔  {p['slug_b']}")
            if p.get('editorial_note'):
                print(f"    → {p['editorial_note']}")
        if cap and len(med) > cap:
            print(f"  … and {len(med) - cap} more (use --report for full list)")

    if low and verbose:
        print(f"\n  LOW — INFO ({len(low)} candidate(s)) — Jaccard ≥ 0.75")
        for p in low[:15]:
            score = p.get('jaccard_score', '?')
            print(f"  [j={score}]  {p['slug_a']}  ↔  {p['slug_b']}")
        if len(low) > 15:
            print(f"  … and {len(low) - 15} more")

    if not high and not med:
        print(f"  No HIGH/MEDIUM near-duplicate slugs found ✓")
        if low and not verbose:
            print(f"  {len(low)} LOW-confidence review candidate(s) (use --verbose to list)")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='V1 slug near-duplicate detector — affiliate platform preflight',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument('site_dir', nargs='?', help='Path to site directory')
    parser.add_argument('--all', action='store_true',
                        help='Scan all sites in portfolio.yaml')
    parser.add_argument('--report', metavar='FILE',
                        help='Write structured YAML report to FILE (single-site mode)')
    parser.add_argument('--report-dir', metavar='DIR',
                        help='Write per-site YAML reports + portfolio-summary.yaml to DIR (--all mode)')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Show MEDIUM detail + LOW-confidence candidates')
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

    any_fail = False
    summary_rows: list = []

    for site_dir in site_dirs:
        if not site_dir.exists():
            print(f'  SKIP {site_dir.name} — directory not found')
            continue

        report_path = None
        if args.report and not args.all:
            report_path = Path(args.report)
        elif args.report_dir and args.all:
            report_path = Path(args.report_dir) / f'{site_dir.name}.yaml'

        result = scan_site(site_dir, report_path=report_path, verbose=args.verbose)
        if result is None:
            print(f'  SKIP {site_dir.name} — no content/articles/ directory')
            continue

        print_site_report(result, verbose=args.verbose)

        h, m, l = len(result['high']), len(result['medium']), len(result['low'])
        if h:
            any_fail = True
        status = 'FAIL' if h else ('WARN' if m else 'PASS')
        summary_rows.append((site_dir.name, result['total_slugs'], h, m, l, status))

    # Portfolio summary table
    if len(summary_rows) > 1:
        print(f"\n\n{'=' * 70}")
        print('PORTFOLIO SUMMARY — V1 Slug Near-Duplicate Validator')
        print(f"{'=' * 70}")
        print(f"  {'SITE':<33}  {'ARTS':>5}  {'HIGH':>5}  {'MED':>5}  {'LOW':>5}  STATUS")
        print(f"  {'-' * 65}")
        for slug, arts, h, m, l, status in summary_rows:
            icon = '❌' if status == 'FAIL' else ('⚠ ' if status == 'WARN' else '✓ ')
            print(f"  {slug:<33}  {arts:>5}  {h:>5}  {m:>5}  {l:>5}  {icon} {status}")
        ta = sum(r[1] for r in summary_rows)
        th = sum(r[2] for r in summary_rows)
        tm = sum(r[3] for r in summary_rows)
        tl = sum(r[4] for r in summary_rows)
        print(f"  {'TOTAL':<33}  {ta:>5}  {th:>5}  {tm:>5}  {tl:>5}")

        if args.report_dir:
            report_dir = Path(args.report_dir)
            report_dir.mkdir(parents=True, exist_ok=True)
            summary_path = report_dir / 'portfolio-summary.yaml'
            with open(summary_path, 'w', encoding='utf-8') as f:
                yaml.dump({
                    'sites': [
                        {'site': s, 'total_articles': a, 'high': h, 'medium': m,
                         'low': l, 'status': st}
                        for s, a, h, m, l, st in summary_rows
                    ],
                    'totals': {
                        'articles': ta,
                        'high_confidence_pairs': th,
                        'medium_confidence_pairs': tm,
                        'low_confidence_pairs': tl,
                        'total_pairs': th + tm + tl,
                    },
                }, f, default_flow_style=False, sort_keys=False)
            print(f"\n  Portfolio summary → {summary_path}")

    sys.exit(1 if any_fail else 0)


if __name__ == '__main__':
    main()
