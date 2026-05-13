# Publishing Workflow

How articles move from producer output to `content/articles/`. Follow this exactly — shortcuts here caused the validator-block live-site bleed incident (38 TCD articles, May 2026).

---

## The only approved path from staging → production

```
producer run (staging mode)
    ↓
staging/{slug}.md          ← clean article
staging/failed/{slug}.md   ← clean article  } if validation failed
staging/failed/{slug}.failures               } validator report (sidecar)
    ↓
human review
    ↓
move approved files to staging/approved/
    ↓
node tools/publish-staging.mjs --site <site-slug>
    ↓
content/articles/{slug}.md
```

`publish-staging.mjs` strips any residual validator output, validates frontmatter integrity, and logs `[PUBLISH]` or `[SKIP]` per file. It is the **only** tool that should write to `content/articles/`.

---

## What NOT to do

**Never `mv` or `cp` directly from staging → content/articles/.**

```bash
# WRONG — bypasses strip and validation
mv staging/approved/*.md content/articles/

# WRONG — same problem
cp staging/approved/my-article.md content/articles/
```

This is what caused the incident. Files in `staging/failed/` previously had validator output appended to the markdown body. When moved manually, that output rendered as live page content.

The sidecar fix (May 2026) means `staging/failed/{slug}.md` files are now clean, but the `publish-staging.mjs` workflow is still required — it handles pipeline.json state tracking and provides a `[SKIP]` safety check for malformed frontmatter.

---

## Approving failed articles

If you want to publish an article that failed R7 validation (validator FAIL is acceptable for the current batch):

1. Read `staging/failed/{slug}.failures` — understand what failed and why.
2. If the failures are acceptable (e.g. all `[MANUAL]` checks, content is otherwise sound):
   - Copy the clean `.md` to `staging/approved/`
   - Leave the `.failures` sidecar in `staging/failed/`
3. Run `node tools/publish-staging.mjs --site <site-slug>` — use `--include-failed` flag only if publishing directly from `staging/failed/` without moving first.

---

## Full pre-production checklist

From `affiliate-platform/CLAUDE.md` §3 — mandatory in order, no skipping:

1. `grep -c "amazon_asin: VERIFY" content/products/products.yaml` → `0`
2. `cd producer && python3 -m pytest tests/ -v` → all green
3. `node scripts/validate-asins.mjs` → exit 0
4. `--count 5` test batch → read all five staging files
5. Full production batch
6. Move approved to `staging/approved/`
7. `node tools/publish-staging.mjs --site <site-slug>`
8. `npm run build` → no FAIL lines
9. `git push origin main`
10. Confirm deploy URL responds 200
