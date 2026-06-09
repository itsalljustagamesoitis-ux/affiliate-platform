# Platform Fix: Empty Article Content Validator

**Type:** Build validator / pre-deploy gate  
**Severity if missed:** SEV-1 (empty article bodies ship to production undetected)  
**First surfaced:** Site 15 (rmflyfishing) Phase 4 UAT — 76 articles in dist had empty `article-page__content` divs; no existing validator caught it  
**Status:** Backlog — check does not yet exist in `build-validator.mjs`

---

## Problem

The existing `build-validator.mjs` validates ASIN presence, hub-product match, CTA density, and structural schema compliance. None of these checks confirm that article body prose actually rendered. A build can exit 0, pass all existing checks, and deploy 91 empty articles to production.

The empty-content failure mode is silent because:
- Astro's glob loader catches render errors internally
- The resulting HTML is structurally valid — just empty
- HTTP status checks (200 OK) pass on an empty article page
- No existing check reads the rendered body text

This validator closes that gap.

## Check to Add to `build-validator.mjs`

### Implementation

```javascript
// In build-validator.mjs, after existing checks:

import { readFileSync, readdirSync } from 'fs'
import { join } from 'path'

const DIST_DIR = join(process.cwd(), 'dist')
const CONTENT_DIV_RE = /class="article-page__content"[^>]*>\s*<\/div>/

function checkEmptyContentDivs(results) {
  const articleFiles = findArticleHtmlFiles(DIST_DIR)
  const emptyFiles = []

  for (const filePath of articleFiles) {
    const html = readFileSync(filePath, 'utf-8')
    if (CONTENT_DIV_RE.test(html)) {
      emptyFiles.push(filePath.replace(DIST_DIR, ''))
    }
  }

  if (emptyFiles.length > 0) {
    for (const f of emptyFiles) {
      results.push({ level: 'FAIL', check: 'empty-content', file: f, message: 'article-page__content div is empty' })
    }
  } else {
    results.push({ level: 'PASS', check: 'empty-content', message: `${articleFiles.length} articles have content` })
  }
}

function findArticleHtmlFiles(dir) {
  // Recursively find all index.html files under dist/ that are article pages
  // Article pages are any directory that isn't root-level (index.html, 404.html, etc.)
  const results = []
  function walk(current) {
    const entries = readdirSync(current, { withFileTypes: true })
    for (const entry of entries) {
      const full = join(current, entry.name)
      if (entry.isDirectory()) {
        walk(full)
      } else if (entry.name === 'index.html' && current !== dir) {
        // Check if it's a content article (has article-page__content div at all)
        const html = readFileSync(full, 'utf-8')
        if (html.includes('article-page__content')) {
          results.push(full)
        }
      }
    }
  }
  walk(dir)
  return results
}
```

### Shell one-liner for manual check

```bash
# Quick pre-deploy audit — must return 0
grep -rl 'article-page__content' dist/ | \
  xargs grep -l 'article-page__content"></div>' | \
  wc -l
```

Or with detail:
```bash
grep -rl 'article-page__content' dist/ | \
  xargs grep -l 'article-page__content"></div>'
```
Must return no output. Any filenames returned → investigation required before deploy.

## Severity: FAIL, not WARN

This check must be FAIL-level. A WARN would allow the deploy to proceed on the reasoning that "some content missing is acceptable." It is not. An article with an empty body is a broken page. It will be discovered by readers, crawled by bots as thin content, and potentially penalized.

The cost of a false positive (blocking a deploy when content is actually fine) is lower than the cost of a false negative (shipping empty pages). If this check fires on a false positive, investigate; do not disable or demote to WARN.

## What Triggers the Empty Content Div

Documented causes (see `platform-fix-data-store-cache.md`):
1. `rehypeProductLinks` throws on an unknown `product:<slug>` reference in article body
2. Any other rehype/remark plugin throws during markdown rendering
3. Astro content layer cache (`node_modules/.astro/data-store.json`) contains stale `rendered: undefined` entries

## Recovery When This Validator Fires

```bash
# 1. Identify the empty articles
grep -rl 'article-page__content' dist/ | \
  xargs grep -l 'article-page__content"></div>'

# 2. Map to source files (strip dist path, resolve slug)
# e.g., dist/best-fly-rod/index.html → content/articles/best-fly-rod.md

# 3. Check for bad product slug references in each flagged article
grep -oP 'product:[a-z0-9-]+' content/articles/<slug>.md | sort -u

# 4. Cross-check slugs against products.yaml
python3 -c "
import yaml, re, sys
products = yaml.safe_load(open('content/products/products.yaml'))
article = open(sys.argv[1]).read()
refs = set(re.findall(r'product:([a-z0-9-]+)', article))
missing = refs - set(products.keys())
print('MISSING:', missing or 'none')
" content/articles/<slug>.md

# 5. Fix: add missing products to products.yaml OR fix typo in article slug

# 6. Delete data-store cache and rebuild
rm node_modules/.astro/data-store.json && npm run build

# 7. Re-run validator — must return 0 empty articles
```

## Done Criteria

- `build-validator.mjs` has `checkEmptyContentDivs()` function that runs as part of `npm run build`
- Any article with an empty `article-page__content` div produces a `FAIL` line in build output
- Build exit code is non-zero when any FAIL is present (existing behavior — no change needed)
- `npm run build` on a clean Site 15 dist returns PASS for `empty-content` check
- `CHANGELOG.md` updated with validator addition

## Related

- `platform-fix-data-store-cache.md` — root cause of the empty-content failure mode
- `platform-fix-product-slug-resolution.md` — upstream fix that prevents the slug errors that trigger empty content
