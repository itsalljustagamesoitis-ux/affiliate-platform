# Platform Fix: Astro Content Layer Data-Store Cache Corruption

**Type:** Build system / cache invalidation failure  
**Severity if missed:** SEV-1 (empty article bodies on live site, invisible to build pipeline)  
**First surfaced:** Site 15 (rmflyfishing) Phase 4 UAT — 76 articles in dist had empty `article-page__content` divs; 91 articles in data-store had `rendered: undefined`  
**Status:** Fixed on Site 15 (cache deleted, rebuild clean); permanent fix not yet implemented

---

## Problem

Astro 6's content layer stores rendered markdown in `node_modules/.astro/data-store.json`. When a rehype plugin throws during rendering (e.g., `rehypeProductLinks` throws for an unknown product slug), the glob loader silently catches the error, sets `rendered: undefined`, and writes that entry to the cache.

The cached `rendered: undefined` persists until the article file changes (digest-based invalidation). Fixing the underlying cause (adding the missing product to `products.yaml`) does NOT change article file digests. The broken cache entry survives every subsequent build.

The build passes. The deploy succeeds. The validator passes structural checks. The site is live with empty article bodies.

## Timeline of Site 15 Corruption

| Time | Event |
|------|-------|
| 19:06 | Batch 1 (articles referencing existing products): rendered clean |
| 19:47–19:53 | Batch 2 (91 articles): published to `content/articles/` referencing products not yet in `products.yaml` |
| 19:47–19:53 | Astro renders batch 2; `rehypeProductLinks` throws per article; glob loader catches silently; 91 entries stored as `rendered: undefined` |
| 19:57 | `products.yaml` updated with the missing products |
| All builds after 19:57 | Article digests unchanged → cache hit → `rendered: undefined` reused → empty bodies persist |

The build at 19:57+ showed no errors. There was nothing to indicate corruption until a human inspected the rendered HTML.

## Why It's Invisible

- **Build exits 0** — the glob loader catches render errors without propagating them
- **`build-validator.mjs` passes** — structural checks (ASIN, hub match, etc.) all pass; no check existed for empty content divs
- **`verify-deploy.mjs` passes** — checks HTTP status codes and page structure at URL level, not body content
- **The broken article count grows** — any subsequent article batch that references products with typos or missing entries compounds the problem

## Recovery Procedure

```bash
# 1. Delete the corrupted data store
rm node_modules/.astro/data-store.json

# 2. Verify count before rebuilding (confirms corruption was present)
# — this step only possible before deletion; document for future incidents

# 3. Rebuild from clean state
npm run build

# 4. Verify no empty content divs remain
grep -r 'article-page__content"></div>' dist/ | wc -l
# Must return 0

# 5. If non-zero after rebuild, find the article with the bad slug
grep -r 'article-page__content"></div>' dist/ | head -5
# Map dist filename back to content/articles/ slug
# Then find bad product references in that article:
grep -oP 'product:[a-z0-9-]+' content/articles/<slug>.md
# Cross-check each slug against products.yaml
```

## Root Cause: Timing of articles vs. products.yaml

The proximate cause is `rehypeProductLinks` throwing on unknown slugs. The structural cause is that `publish.py` wrote articles to `content/articles/` before ensuring all referenced products existed in `content/products/products.yaml`.

The data-store records the failure and never re-attempts it. The correction (adding products) happens after the damage is done.

## Permanent Fix

### 1. Enforce products-before-articles order in `publish.py`

Before writing any article file to `content/articles/`, validate that every `product:<slug>` reference in the article body exists in `products.yaml`:

```python
def validate_product_refs(article_body: str, products: dict) -> list[str]:
    """Return list of unresolved product slugs found in article body."""
    refs = re.findall(r'product:([a-z0-9-]+)', article_body)
    return [slug for slug in refs if slug not in products]

# In publish.py, before writing article file:
missing = validate_product_refs(article_body, products_yaml)
if missing:
    raise ValueError(f"Article references unknown product slugs: {missing}. Add to products.yaml first.")
```

This makes the failure loud and early instead of silent and persistent.

### 2. Add `node_modules/.astro/` to `.gitignore`

The data-store must never be committed. If a corrupted cache were committed and pulled by another developer or CI, it would propagate the corruption.

```bash
echo "node_modules/.astro/" >> .gitignore
```

Check (must return a line):
```bash
grep "node_modules/.astro" .gitignore
```

### 3. Add `rm -f node_modules/.astro/data-store.json` to the pre-production runbook

As a belt-and-suspenders measure before any full production run, clear the cache explicitly. Cold builds are slower (~3-5 min) but incorruptible.

Add to the mandatory pre-production sequence:
```
0. rm -f node_modules/.astro/data-store.json
```
before step 1 (VERIFY ASIN check).

### 4. Astro-agnostic note

Any site using glob loader + a custom rehype/remark plugin that throws on missing external data is vulnerable to this. The fix at the Astro level would be to not cache `rendered: undefined` — but since we cannot change Astro's behavior, the defense must be upstream (products-before-articles ordering) and downstream (empty-content validator).

## Related Platform Fixes

- `platform-fix-empty-content-validator.md` — post-build validator that catches empty `article-page__content` divs before deploy
- `platform-fix-product-slug-resolution.md` — pre-build static analysis that finds unresolved `product:<slug>` references in markdown before Astro processes them

## New-Site Runbook Entry

```
- [ ] Before each production article batch, confirm all product slugs referenced in
      article bodies exist in products.yaml
      Check: python3 scripts/validate-product-slugs.py  → must return 0 unresolved
- [ ] node_modules/.astro/ is in .gitignore
      Check: grep "node_modules/.astro" .gitignore  → must return a line
- [ ] If build behavior looks wrong (articles exist but render empty), run:
      rm node_modules/.astro/data-store.json && npm run build
      Then check: grep -r 'article-page__content"></div>' dist/ | wc -l  → must be 0
```
