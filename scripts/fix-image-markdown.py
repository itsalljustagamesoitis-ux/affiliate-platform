#!/usr/bin/env python3
"""
fix-image-markdown.py

Fixes dict-literal image markdown URLs produced by older producer versions.

Bad:  ![alt text]({'alt': 'some alt', 'path': 'articles/foo.webp'})
Good: ![some alt](/images/articles/foo.webp)

Uses the 'alt' value from the dict as the actual alt text (more accurate than
the outer bracket text which is often a generic "X product image" placeholder).

Usage:
  python3 scripts/fix-image-markdown.py --site northwoods-overland [--dry-run]
"""

import re
import os
import sys
import glob
import argparse

def fix_content(content: str) -> tuple[str, int]:
    """Replace all dict-literal image markdown with valid markdown."""
    count = 0
    # Match the full ![...]({...}) construct and extract via literal field parsing
    pattern = re.compile(r"!\[([^\]]*)\]\((\{[^)]+\})\)")
    results = []
    last = 0
    for m in pattern.finditer(content):
        outer_alt = m.group(1)
        dict_str = m.group(2)
        # Only process if it looks like a dict with 'alt' and 'path' keys
        if "'alt':" not in dict_str and '"alt":' not in dict_str:
            results.append(content[last:m.end()])
            last = m.end()
            continue
        alt = _extract_field(dict_str, "alt") or outer_alt.strip() or "product image"
        path = _extract_field(dict_str, "path") or ""
        if not path:
            results.append(content[last:m.end()])
            last = m.end()
            continue
        url = f"/images/{path.lstrip('/')}"
        results.append(content[last:m.start()])
        results.append(f"![{alt}]({url})")
        last = m.end()
        count += 1
    results.append(content[last:])
    return "".join(results), count

def _extract_field(dict_str: str, key: str) -> str:
    """Extract value for a given key from a Python-dict-like string."""
    # Try single-quoted value: 'key': 'value' or "key": 'value'
    m = re.search(rf"['\"]?{re.escape(key)}['\"]?\s*:\s*'([^']*)'", dict_str)
    if m:
        return m.group(1)
    # Try double-quoted value
    m = re.search(rf"['\"]?{re.escape(key)}['\"]?\s*:\s*\"([^\"]*)\"", dict_str)
    if m:
        return m.group(1)
    return ""

def main():
    parser = argparse.ArgumentParser(description="Fix dict-literal image markdown")
    parser.add_argument("--site", required=True, help="Site slug (e.g. northwoods-overland)")
    parser.add_argument("--dry-run", action="store_true", help="Report only, no writes")
    args = parser.parse_args()

    site_root = os.path.expanduser(f"~/{args.site}")
    if not os.path.isdir(site_root):
        print(f"ERROR: site root not found: {site_root}", file=sys.stderr)
        sys.exit(2)

    articles_dir = os.path.join(site_root, "content", "articles")
    if not os.path.isdir(articles_dir):
        print(f"ERROR: articles dir not found: {articles_dir}", file=sys.stderr)
        sys.exit(2)

    pattern = os.path.join(articles_dir, "*.md")
    files = sorted(glob.glob(pattern))

    total_fixed = 0
    files_changed = 0

    for filepath in files:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        fixed, count = fix_content(content)
        if count > 0:
            total_fixed += count
            files_changed += 1
            if args.dry_run:
                print(f"[DRY-RUN] Would fix {count:4d} instances: {os.path.basename(filepath)}")
            else:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(fixed)
                print(f"Fixed {count:4d} instances: {os.path.basename(filepath)}")

    print(f"\n{'DRY-RUN — ' if args.dry_run else ''}{'Done. ' if not args.dry_run else ''}"
          f"Fixed {total_fixed} image markdown instances across {files_changed} files.")

    if total_fixed == 0:
        print("No dict-literal image markdown found.")

if __name__ == "__main__":
    main()
