#!/usr/bin/env python3
"""
fix-v20-leakage.py — Surgical V20 meta-leakage phrase fixes.

Applies targeted string replacements to the 3 regex-fixable V20 FAILs found
in the Site 16 editorial UAT (2026-06-04). Operates on article body only
(skips frontmatter). The 1 SEV-1 article (best-water-purification-tablets-2.md)
is NOT handled here — it requires a manual editorial rewrite.

Usage:
  python3 scripts/fix-v20-leakage.py --site ridgelinebushcraft [--dry-run]
"""

import argparse
import sys
from pathlib import Path

SITE_ROOTS = {
    'ridgelinebushcraft': Path('/root/ridgelinebushcraft'),
}

FIXES = [
    {
        'file': 'best-wilderness-survival-shows.md',
        'find': 'The limitation the brief names is accurate:',
        'replace': 'That limitation is real:',
        'rationale': 'S1-02 class: brief-attribution verb "names" caught by V20 expanded pattern',
    },
    {
        'file': 'fiskars-x27-splitting-axe.md',
        'find': 'log range the brief describes',
        'replace': 'that same log range',
        'rationale': 'S1-02 class: brief-attribution verb "describes" caught by V20 expanded pattern',
    },
    {
        'file': 'wood-splitting-axe-vs-maul.md',
        'find': 'and the brief notes this',
        'replace': 'worth noting',
        'rationale': 'S1-02 class: brief-attribution verb "notes" caught by V20 expanded pattern',
    },
]


def fix_body(content: str, find: str, replace: str) -> tuple[str, int]:
    parts = content.split('---', 2)
    if len(parts) < 3:
        body, prefix = content, ''
    else:
        prefix = '---' + parts[1] + '---'
        body = parts[2]
    count = body.count(find)
    if count:
        body = body.replace(find, replace)
    return prefix + body, count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--site', required=True)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    site_root = SITE_ROOTS.get(args.site)
    if not site_root:
        print(f'Unknown site: {args.site}. Known: {list(SITE_ROOTS)}', file=sys.stderr)
        sys.exit(1)

    art_dir = site_root / 'content' / 'articles'
    if not art_dir.exists():
        print(f'content/articles/ not found at {art_dir}', file=sys.stderr)
        sys.exit(1)

    mode = 'DRY RUN' if args.dry_run else 'APPLYING'
    print(f'[fix-v20-leakage] {mode} — {len(FIXES)} targeted fixes\n')

    total_replaced = 0
    for fix in FIXES:
        path = art_dir / fix['file']
        if not path.exists():
            print(f'  SKIP  {fix["file"]} (not found)')
            continue

        content = path.read_text(encoding='utf-8')
        new_content, count = fix_body(content, fix['find'], fix['replace'])

        if count == 0:
            print(f'  WARN  {fix["file"]} — phrase not found (already fixed?)')
        elif args.dry_run:
            print(f'  WOULD FIX  {fix["file"]} ({count} instance)')
            print(f'    find:    {fix["find"]}')
            print(f'    replace: {fix["replace"]}')
        else:
            path.write_text(new_content, encoding='utf-8')
            print(f'  FIXED  {fix["file"]} ({count} instance)')
            total_replaced += count

    if not args.dry_run:
        print(f'\n[fix-v20-leakage] Done — {total_replaced} replacements across {len(FIXES)} files')
    else:
        print(f'\n[fix-v20-leakage] Dry run complete — no files written')


if __name__ == '__main__':
    main()
