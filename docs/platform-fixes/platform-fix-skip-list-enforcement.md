# Platform Fix: Skip-List Article Enforcement

**Type:** Pre-deploy gate  
**Severity if missed:** SEV-2 (placeholder/draft content live)  
**First surfaced:** Site 15 (rmflyfishing) Phase 4 UAT  
**Status:** Backlog — not yet implemented

---

## Problem

Articles marked with `noindex: true` or placed on a producer skip list are not meant to be published. But Astro's static build generates an HTML file for every entry in the content collection, regardless of intent. If an article has `noindex: true` but IS present in the collection, it gets a URL and gets indexed by crawlers unless the `robots` meta tag is respected — which not all crawlers do, and which doesn't block direct access or sharing.

Worse: if a skip-list article is generated but the validator only checks whether the file exists, a "built but should 404" article can ship to production silently.

## Where It Happens

- Articles in the pipeline with `noindex: true` that were not supposed to be published yet
- Draft articles that accidentally got into `content/articles/` before editorial review
- Removed articles whose files weren't deleted from disk

The current build produces HTML for all of these and the validator passes.

## Detection Check

Pre-deploy gate — verifies that `noindex: true` articles either return 404 or are explicitly exempted:

```bash
# List all articles with noindex: true
python3 -c "
import os, yaml
for f in os.listdir('content/articles/'):
    if not f.endswith('.md'): continue
    content = open(f'content/articles/{f}').read()
    parts = content.split('---', 2)
    if len(parts) >= 2:
        fm = yaml.safe_load(parts[1])
        if fm.get('noindex'):
            print(fm.get('slug', f))
"
```

For each slug returned, verify it returns 404 on the live deploy:

```bash
curl -sI https://<deploy-url>/<slug>/ | head -1
# Expected: HTTP/2 404
```

## Fix

Two options depending on intent:

1. **Delete the article file** if it should never have been in the collection
2. **Exclude from `getStaticPaths`** by filtering `noindex: true` articles — then they generate no URL at all:

```astro
// [slug].astro
export async function getStaticPaths() {
  const articles = await getCollection('articles')
  return articles
    .filter(a => !a.data.noindex)  // ← add this
    .map(article => ({ ... }))
}
```

Option 2 is the correct platform behavior. `noindex` in the current system means "don't tell search engines about this URL" — it should mean "don't generate this URL at all" for draft/skip-list content.

## Permanent Fix

Add to `build-validator.mjs` as a WARN (or promote to FAIL for strict builds):

```javascript
const noindexPages = glob.sync('dist/**/index.html').filter(f => {
  const html = fs.readFileSync(f, 'utf8')
  return html.includes('content="noindex')
})
if (noindexPages.length > 0) {
  results.push({ level: 'WARN', check: 'skip-list', message: `${noindexPages.length} noindex page(s) generated — consider excluding from getStaticPaths` })
}
```

## Related

- `platform-fix-empty-content-validator.md` — same validator gap pattern
