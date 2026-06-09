# Platform Fix: Product Slug Resolution Validator

**Type:** Pre-build static analysis / content integrity gate  
**Severity if missed:** SEV-1 (article renders empty; Astro silently caches failed render)  
**First surfaced:** Site 15 (rmflyfishing) Phase 4 — `how-to-indicator-nymph.md` referenced `aventik-eupheng-riverruns-yarn` (correct: `aventik-eupheng-riverruns-yarn-strike`); 91 articles also affected by batch-2 timing (products not yet in products.yaml)  
**Status:** Backlog — no static slug validation exists; gap between publishing articles and validating their product refs

---

## Problem

Articles in `content/articles/` contain `product:<slug>` references in their body markdown:

```markdown
The [AVENTIK Yarn Strike Indicators](product:aventik-eupheng-riverruns-yarn-strike) is a yarn-style option...
```

The `rehypeProductLinks` plugin resolves these references at build time. If a slug doesn't exist in `content/products/products.yaml`, the plugin throws, Astro silently catches it, stores `rendered: undefined` in `node_modules/.astro/data-store.json`, and the article renders as an empty page.

There is no pre-build check that catches unresolved slugs before Astro processes the markdown. The failure is invisible until a human inspects the rendered HTML — or until `build-validator.mjs` gains the empty-content check (see `platform-fix-empty-content-validator.md`).

## Two Failure Modes Covered by This Fix

### Mode A: Slug typo
`aventik-eupheng-riverruns-yarn` in article body; correct slug is `aventik-eupheng-riverruns-yarn-strike`. One article fails to render.

### Mode B: Timing (products.yaml not updated before articles published)
91 articles published to `content/articles/` at 19:47–19:53. `products.yaml` updated at 19:57. Articles reference products that didn't exist at render time. All 91 fail to render. Cache persists the failure indefinitely.

Both modes are caught by static slug validation run before `npm run build`.

## Validator Script

Create `scripts/validate-product-slugs.py`:

```python
#!/usr/bin/env python3
"""
Pre-build validator: every product:<slug> reference in article body markdown
must resolve to a key in content/products/products.yaml.

Exit 0 if all slugs resolve. Exit 1 if any slug is unresolved.
"""

import re
import sys
from pathlib import Path
import yaml

ARTICLES_DIR = Path("content/articles")
PRODUCTS_FILE = Path("content/products/products.yaml")
SLUG_PATTERN = re.compile(r'product:([a-z0-9][a-z0-9-]*)')

def load_products(path: Path) -> set[str]:
    data = yaml.safe_load(path.read_text())
    return set(data.keys())

def check_article(path: Path, known_slugs: set[str]) -> list[tuple[str, str]]:
    body = path.read_text()
    refs = SLUG_PATTERN.findall(body)
    return [(str(path), slug) for slug in refs if slug not in known_slugs]

def main():
    if not PRODUCTS_FILE.exists():
        print(f"FAIL: {PRODUCTS_FILE} not found", file=sys.stderr)
        sys.exit(1)

    known_slugs = load_products(PRODUCTS_FILE)
    article_files = sorted(ARTICLES_DIR.glob("**/*.md"))

    if not article_files:
        print("WARN: no article files found")
        sys.exit(0)

    failures = []
    for article in article_files:
        failures.extend(check_article(article, known_slugs))

    if failures:
        print(f"FAIL: {len(failures)} unresolved product slug(s):")
        for file_path, slug in failures:
            print(f"  {file_path}: product:{slug}")
        sys.exit(1)
    else:
        print(f"PASS: {len(article_files)} articles, all product slugs resolved")
        sys.exit(0)

if __name__ == "__main__":
    main()
```

## Integration Points

### 1. Mandatory pre-production sequence (add before step 1)

```bash
python3 scripts/validate-product-slugs.py
# Must exit 0 before running npm run build
```

### 2. `npm run build` pre-hook (optional — belt and suspenders)

In `package.json`:
```json
{
  "scripts": {
    "prebuild": "python3 scripts/validate-product-slugs.py",
    "build": "..."
  }
}
```

This makes slug validation a prerequisite for every build, not just production runs. Adds ~1 second to build time.

### 3. `publish.py` integration

Before writing any article file to `content/articles/`, run the same validation inline:

```python
# After generating article body, before write:
missing = validate_product_refs(article_body, products_yaml)
if missing:
    raise ValueError(
        f"Article '{slug}' references unknown product slugs: {missing}. "
        f"Add these to products.yaml before publishing."
    )
```

This catches timing failures (Mode B) at the source — before the article file is written — so the data-store never sees an unresolvable article.

## Manual Check (no script required)

```bash
# Find all product slug references across all articles
grep -rhoP 'product:[a-z0-9-]+' content/articles/ | sort -u

# Cross-check each against products.yaml keys
python3 -c "
import yaml, re, glob
products = set(yaml.safe_load(open('content/products/products.yaml')).keys())
refs = set()
for f in glob.glob('content/articles/**/*.md', recursive=True):
    refs.update(re.findall(r'product:([a-z0-9-]+)', open(f).read()))
missing = refs - products
print('MISSING:', sorted(missing) or 'none')
"
```
Output must be `MISSING: none`.

## Site 15 Instance

`content/articles/how-to-indicator-nymph.md` had:
```markdown
product:aventik-eupheng-riverruns-yarn        # wrong
product:aventik-eupheng-riverruns-yarn-strike  # correct
```

Fix applied: both body occurrences corrected to the full slug. Data-store cache deleted. Rebuild confirmed clean.

Had this validator existed, it would have caught the typo immediately on the first build attempt — before the broken cache entry was written.

## Done Criteria

- `scripts/validate-product-slugs.py` exists and exits 0 on a clean Site 15
- Validator is called in the mandatory pre-production sequence (before `npm run build`)
- `publish.py` validates product slug references before writing article files to disk
- `producer/tests/` includes a test that verifies `validate_product_refs()` returns the correct missing slugs
- `CHANGELOG.md` updated

## Related

- `platform-fix-data-store-cache.md` — explains how unresolved slugs corrupt the Astro data-store cache
- `platform-fix-empty-content-validator.md` — downstream check that catches the resulting empty content divs in dist
