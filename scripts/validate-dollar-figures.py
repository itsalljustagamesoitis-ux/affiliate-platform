#!/usr/bin/env python3
"""
V9 — Dollar-Figure Validator (validate-dollar-figures.py)

Detects Amazon product price claims in article content.
Amazon Operating Agreement Section 5(v) prohibits displaying prices
except via official Amazon APIs (PA-API, SiteStripe).

Scans:
  - Article body text (post-frontmatter)
  - Frontmatter title: field (dollar figures in titles are also ToS risk)

Excludes (not Amazon product prices — preserve these):
  - Electricity/utility rates:  $X per kWh, $X per hour
  - Propane/fuel costs:         $X to refill, $X per gallon, $X per tank
  - Battery commodity prices:   $X per battery, $X per cell, $X per pack
  - Material cost rates:        $X per sq ft, $X per square foot
  - Percentage comparisons:     "X% lower", "X% more expensive"

Usage:
    python3 scripts/validate-dollar-figures.py /path/to/site
    python3 scripts/validate-dollar-figures.py /path/to/site --verbose
    python3 scripts/validate-dollar-figures.py --all
"""

import argparse
import re
import sys
from pathlib import Path


# ── Patterns ──────────────────────────────────────────────────────────────────

# Dollar figure patterns — match any $X in article content
_DOLLAR_RE = re.compile(
    r'\$\d{1,4}(?:[,\.\d]*)?(?:\+)?',
    re.IGNORECASE,
)

# Commodity/operating cost exclusion patterns.
# A line matching ANY of these contains costs that are NOT Amazon product prices.
_EXCLUDE_LINE_RE = re.compile(
    r'(?:'
    r'\$[\d.,]+\s*(?:per|/)\s*(?:kWh|kwh|kilowatt)'           # electricity: $0.16/kWh
    r'|(?:per\s+hour|/\s*hour|per\s*hr|/hr)\b'                 # operating $/hour
    r'|\$[\d.,]+\s+(?:per|to)\s+(?:refill|fill)\b'             # propane: $20 to refill
    r'|\$[\d.,]+\s+per\s+(?:gallon|gal)\b'                     # fuel/liquid $/gal
    r'|\$[\d.,]+\s+per\s+(?:battery|cell|pack)\b'              # battery: $1.50 per battery
    r'|\$[\d.,]+\s+per\s+(?:sq(?:uare)?\s*f(?:oot|t|eet)?)\b' # material: $/sq ft
    r'|\$[\d.,]+\s+per\s+(?:lb|pound|oz|ounce)\b'              # commodity: $/lb
    r'|per\s+evening\b'                                         # operating: per evening
    r')',
    re.IGNORECASE,
)

# Frontmatter block
_FRONTMATTER_RE = re.compile(r'^---\s*\n.*?\n---\s*\n', re.DOTALL)
_TITLE_RE = re.compile(r'^title:\s*["\']?(.+?)["\']?\s*$', re.MULTILINE)


def _line_is_excluded(line: str) -> bool:
    """Return True if the line contains a commodity/operating cost context."""
    return bool(_EXCLUDE_LINE_RE.search(line))


def scan_article(path: Path) -> dict:
    """Scan a single article for dollar-figure violations.

    Returns:
        {
          "title_violations": [(match_text, context)],
          "body_violations": [(line_no, match_text, context)],
        }
    """
    text = path.read_text(encoding='utf-8', errors='replace')

    # Extract frontmatter title
    title_violations = []
    title_m = _TITLE_RE.search(text[:500])
    if title_m:
        title_text = title_m.group(1)
        for m in _DOLLAR_RE.finditer(title_text):
            title_violations.append((m.group(), title_text.strip()[:100]))

    # Strip frontmatter before scanning body
    body = _FRONTMATTER_RE.sub('', text, count=1)
    lines = body.splitlines()

    body_violations = []
    for line_no, line in enumerate(lines, 1):
        if not _DOLLAR_RE.search(line):
            continue
        if _line_is_excluded(line):
            continue
        for m in _DOLLAR_RE.finditer(line):
            body_violations.append((line_no, m.group(), line.strip()[:120]))

    return {
        'title_violations': title_violations,
        'body_violations': body_violations,
    }


def scan_site(site_root: Path, verbose: bool = False) -> dict:
    articles_dir = site_root / 'content' / 'articles'
    if not articles_dir.exists():
        return None

    findings = []   # list of {article, title_hits, body_hits}
    total_articles = 0
    total_instances = 0

    for md in sorted(articles_dir.glob('*.md')):
        total_articles += 1
        result = scan_article(md)
        t = result['title_violations']
        b = result['body_violations']
        n = len(t) + len(b)
        if n:
            total_instances += n
            findings.append({
                'article': md.name,
                'title_hits': t,
                'body_hits': b,
                'total': n,
            })

    return {
        'findings': findings,
        'total_articles': total_articles,
        'total_flagged': len(findings),
        'total_instances': total_instances,
    }


def print_site_report(slug: str, result: dict, verbose: bool = False):
    findings = result['findings']
    total = result['total_articles']
    flagged = result['total_flagged']
    instances = result['total_instances']

    if not findings:
        print(f"  ✓  {slug}  [{total} articles — 0 dollar-figure violations]")
        return

    print(f"\n{'='*70}")
    print(f"SITE: {slug}")
    print(f"{'='*70}")
    print(f"  Total articles  : {total}")
    print(f"  Articles flagged: {flagged}  ({100*flagged/max(total,1):.1f}%)")
    print(f"  Total instances : {instances}")

    if verbose:
        for f in sorted(findings, key=lambda x: -x['total'])[:30]:
            print(f"\n  {f['article']}  ({f['total']} instances)")
            for match, ctx in f['title_hits']:
                print(f"    [TITLE] {match!r}")
                print(f"    > {ctx}")
            for ln, match, ctx in f['body_hits'][:5]:
                print(f"    [line {ln}] {match!r}")
                print(f"    > {ctx}")
            if len(f['body_hits']) > 5:
                print(f"    ... and {len(f['body_hits']) - 5} more instances")
    else:
        # Show heaviest 10 articles
        top = sorted(findings, key=lambda x: -x['total'])[:10]
        print(f"\n  Heaviest articles:")
        for f in top:
            title_note = f"  [{len(f['title_hits'])} in title]" if f['title_hits'] else ""
            print(f"    {f['article']:<55} {f['total']:>4} instances{title_note}")
        if len(findings) > 10:
            print(f"  ... and {len(findings) - 10} more articles")


SITE_PATHS = {
    'FSG': Path('/Users/keithlacy/four-season-gardener'),
    'MLT': Path('/Users/keithlacy/my-little-tablespoon'),
    'OHT': Path('/Users/keithlacy/one-happy-table'),
    'FFC': Path('/Users/keithlacy/fourfernscare'),
    'TCD': Path('/Users/keithlacy/the-coffee-dispatch'),
    'BHH': Path('/Users/keithlacy/betterhearinghub'),
    'SSS': Path('/Users/keithlacy/saunassosimple'),
    'BCB': Path('/Users/keithlacy/bear-creek-barbecue'),
    'NWO': Path('/Users/keithlacy/northwoods-overland'),
    'CC':  Path('/Users/keithlacy/curatedcameras'),
    'TEN27': Path('/Users/keithlacy/ten27cycles'),
}


def main():
    parser = argparse.ArgumentParser(description='V9 — Dollar-figure validator')
    parser.add_argument('site_path', nargs='?', help='Path to site root')
    parser.add_argument('--sites', nargs='+', metavar='SLUG', help='Named sites (FSG MLT ...)')
    parser.add_argument('--all', action='store_true', help='Scan all known sites')
    parser.add_argument('--verbose', '-v', action='store_true')
    args = parser.parse_args()

    targets = []
    if args.all:
        for slug, path in SITE_PATHS.items():
            if path.exists():
                targets.append((slug, path))
    elif args.sites:
        for s in args.sites:
            if s.upper() not in SITE_PATHS:
                print(f"Unknown site: {s}", file=sys.stderr)
                sys.exit(1)
            targets.append((s.upper(), SITE_PATHS[s.upper()]))
    elif args.site_path:
        p = Path(args.site_path)
        targets.append((p.name, p))
    else:
        parser.print_help()
        sys.exit(1)

    any_fail = False
    for slug, path in targets:
        result = scan_site(path, verbose=args.verbose)
        if result is None:
            print(f"  ERROR: content/articles/ not found in {path}", file=sys.stderr)
            continue
        print_site_report(slug, result, verbose=args.verbose)
        if result['total_flagged']:
            any_fail = True

    sys.exit(1 if any_fail else 0)


if __name__ == '__main__':
    main()
