#!/usr/bin/env python3
"""
scope-dollar-figures.py — Discovery scoping tool for Amazon ToS dollar-figure cleanup.
One-off analysis tool; not a permanent validator.

Usage:
    python3 scripts/scope-dollar-figures.py /path/to/site
    python3 scripts/scope-dollar-figures.py --sites FSG MLT
"""

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

PATTERNS = {
    'specific_price_cents': r'\$\d{1,4}\.\d{2}\b',
    'specific_price_whole': r'\$\d{1,4}\b(?!\s*[-–to]+\s*\$)',
    'range_dash':           r'\$\d{1,4}[–-]\$?\d{1,4}\b',
    'range_to':             r'\$\d{1,4}\s+to\s+\$?\d{1,4}\b',
    'range_in':             r'in\s+the\s+\$\d{1,4}(?:[–-]\$?\d{1,4})?\s*(?:range|price\s+range)',
    'plus_suffix':          r'\$\d{1,4}\+',
    'plus_word':            r'\$\d{1,4}\s+(?:plus|or\s+more)\b',
    'under_over':           r'(?:under|over|above|below)\s+\$\d{1,4}\b',
    'hedge_around':         r'(?:around|approximately|about|roughly|nearly|some)\s+\$\d{1,4}\b',
    'hedge_just':           r'just\s+(?:under|over|around|about)\s+\$\d{1,4}\b',
    'k_suffix':             r'\$\d{1,2}(?:\.\d+)?\s*[Kk]\b',
    'budget_of':            r'budget\s+(?:of|around|under|near)\s+\$\d{1,4}\b',
}

# Combined catch-all to avoid double-counting in total
COMBINED_RE = re.compile(
    r'(?:' + '|'.join(f'(?P<p{i}>{p})' for i, p in enumerate(PATTERNS.values())) + r')',
    re.IGNORECASE,
)

PATTERN_RES = {name: re.compile(pat, re.IGNORECASE) for name, pat in PATTERNS.items()}

FRONTMATTER_RE = re.compile(r'^---\s*\n.*?\n---\s*\n', re.DOTALL)


def strip_frontmatter(text: str) -> str:
    return FRONTMATTER_RE.sub('', text, count=1)


def scan_article(path: Path):
    text = path.read_text(encoding='utf-8', errors='replace')
    body = strip_frontmatter(text)
    lines = body.splitlines()

    by_pattern = defaultdict(list)
    for line_no, line in enumerate(lines, 1):
        for name, rx in PATTERN_RES.items():
            for m in rx.finditer(line):
                by_pattern[name].append({
                    'line': line_no,
                    'match': m.group(),
                    'context': line.strip()[:120],
                })
    return by_pattern


def scan_site(site_path: Path):
    articles_dir = site_path / 'content' / 'articles'
    if not articles_dir.exists():
        print(f"  ERROR: {articles_dir} not found", file=sys.stderr)
        return {}

    results = {}
    for md in sorted(articles_dir.glob('*.md')):
        hits = scan_article(md)
        if hits:
            results[md.name] = hits
    return results


def pattern_total(hits_by_name):
    return sum(len(v) for v in hits_by_name.values())


def report_site(slug: str, results: dict, all_articles: int, verbose: bool = False):
    articles_with = len(results)
    total_instances = sum(pattern_total(h) for h in results.values())

    # Aggregate by pattern
    by_pattern = defaultdict(int)
    for hits in results.values():
        for pat, instances in hits.items():
            by_pattern[pat] += len(instances)

    # Heaviest articles
    heaviest = sorted(results.items(), key=lambda kv: pattern_total(kv[1]), reverse=True)[:10]

    print(f"\n{'='*70}")
    print(f"SITE: {slug}")
    print(f"{'='*70}")
    print(f"  Total articles scanned : {all_articles}")
    print(f"  Articles with $ figures: {articles_with}  ({100*articles_with/max(all_articles,1):.1f}%)")
    print(f"  Total instances        : {total_instances}")

    print(f"\n  --- By pattern ---")
    for pat in PATTERNS:
        n = by_pattern.get(pat, 0)
        if n:
            print(f"    {pat:<30} {n:>5}")

    print(f"\n  --- Heaviest articles (top 10) ---")
    for fname, hits in heaviest:
        n = pattern_total(hits)
        print(f"    {fname:<55} {n:>4} instances")

    if verbose:
        print(f"\n  --- Per-article detail ---")
        for fname, hits in sorted(results.items()):
            n = pattern_total(hits)
            print(f"\n  {fname}  ({n} instances)")
            for pat, instances in sorted(hits.items()):
                for inst in instances[:3]:
                    print(f"    [{pat}] line {inst['line']}: {inst['match']!r}")
                    print(f"      > {inst['context']}")
                if len(instances) > 3:
                    print(f"    ... and {len(instances)-3} more [{pat}]")

    return {
        'slug': slug,
        'all_articles': all_articles,
        'articles_with': articles_with,
        'total_instances': total_instances,
        'by_pattern': dict(by_pattern),
        'heaviest': [(f, pattern_total(h)) for f, h in heaviest],
    }


def sample_excerpts(results: dict, pattern: str, n: int = 8) -> list:
    """Return up to n (article, line, match, context) examples for a given pattern."""
    out = []
    for fname, hits in results.items():
        for inst in hits.get(pattern, []):
            out.append((fname, inst['line'], inst['match'], inst['context']))
            if len(out) >= n:
                return out
    return out


SITE_PATHS = {
    'FSG': Path('/Users/keithlacy/four-season-gardener'),
    'MLT': Path('/Users/keithlacy/my-little-tablespoon'),
    'OHT': Path('/Users/keithlacy/one-happy-table'),
    'BHH': Path('/Users/keithlacy/betterhearinghub'),
    'FFC': Path('/Users/keithlacy/fourfernscare'),
    'TCD': Path('/Users/keithlacy/the-coffee-dispatch'),
}


def main():
    parser = argparse.ArgumentParser(description='Scope dollar-figure patterns in article content')
    parser.add_argument('site_path', nargs='?', help='Path to site root')
    parser.add_argument('--sites', nargs='+', metavar='SLUG',
                        help='Named sites to scan (FSG MLT OHT etc.)')
    parser.add_argument('--verbose', '-v', action='store_true')
    parser.add_argument('--samples', action='store_true',
                        help='Print sample excerpts for each pattern')
    args = parser.parse_args()

    targets = []
    if args.sites:
        for s in args.sites:
            if s.upper() not in SITE_PATHS:
                print(f"Unknown site slug: {s}. Known: {list(SITE_PATHS)}", file=sys.stderr)
                sys.exit(1)
            targets.append((s.upper(), SITE_PATHS[s.upper()]))
    elif args.site_path:
        p = Path(args.site_path)
        targets.append((p.name, p))
    else:
        parser.print_help()
        sys.exit(1)

    summaries = []
    all_results = {}

    for slug, site_path in targets:
        articles_dir = site_path / 'content' / 'articles'
        all_articles = len(list(articles_dir.glob('*.md'))) if articles_dir.exists() else 0
        results = scan_site(site_path)
        all_results[slug] = results
        summary = report_site(slug, results, all_articles, verbose=args.verbose)
        summaries.append(summary)

        if args.samples:
            print(f"\n  --- Sample excerpts by pattern ({slug}) ---")
            for pat in PATTERNS:
                examples = sample_excerpts(results, pat, n=5)
                if examples:
                    print(f"\n  [{pat}]")
                    for fname, ln, match, ctx in examples:
                        print(f"    {fname}:{ln}  {match!r}")
                        print(f"    > {ctx}")

    if len(summaries) > 1:
        print(f"\n{'='*70}")
        print("PORTFOLIO SUMMARY")
        print(f"{'='*70}")
        total_arts = sum(s['all_articles'] for s in summaries)
        total_with = sum(s['articles_with'] for s in summaries)
        total_inst = sum(s['total_instances'] for s in summaries)
        print(f"  Sites scanned     : {len(summaries)}")
        print(f"  Total articles    : {total_arts}")
        print(f"  Articles with $   : {total_with}  ({100*total_with/max(total_arts,1):.1f}%)")
        print(f"  Total instances   : {total_inst}")
        print(f"\n  By pattern (all sites combined):")
        combined_by_pat = defaultdict(int)
        for s in summaries:
            for pat, n in s['by_pattern'].items():
                combined_by_pat[pat] += n
        for pat in PATTERNS:
            n = combined_by_pat.get(pat, 0)
            if n:
                print(f"    {pat:<30} {n:>5}")


if __name__ == '__main__':
    main()
