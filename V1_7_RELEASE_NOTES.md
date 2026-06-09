# PIPELINE.md v1.7 — Release Notes

**Released:** 2026-06-04
**Previous version:** v1.6 (2026-06-01)
**Commits:** a5c7c4c (Day 4), 6a61158 (Day 5 P0), 3befc30 (Day 5 P1)

---

## What's new since v1.6

### Day 1 — Universal corpus fixes (image markdown + em-dash)

Applied to all 203 live Site 16 articles before any validator work.

- `fix-image-markdown.py`: converted 812 Python dict literal image references `![]({'alt': '...', 'path': '...'})` to valid markdown `![alt](/images/path)` across 203 articles. Root cause: producer emits dict literals; post-processor now required in regeneration pipeline.
- `fix-em-dash.py`: replaced 6,473 em-dash substitution artifacts (` , ` / ` — `) across 192 articles. Root cause: producer prompt used an em-dash example that the model learned to replicate as a separator.

### Day 2 — V20 meta-leakage validator recalibration

- V20 (`validate-meta-leakage.mjs`) expanded from 8 to 17 patterns covering "the brief [verb]", "this brief [verb]", "appears in this brief", "in this brief", and "product-slug" data-layer terms.
- Corpus after fix: 0 FAILs on 203 articles. Previously: 6 FAILs (2.9%).
- Added `--json` output mode for orchestrator consumption.

### Day 3 — V18 persona-claims validator rework (3-tier HARD/REVIEW/SOFT)

- V18 (`validate-persona-claims.mjs`) expanded to v1.1: added `I've carried`, `I've worn` to HARD patterns; owned_gear word-by-word bypass (handles model-number variations); hedging bypass (±3 lines); REVIEW tier for carry/pack/keep patterns.
- Added `owned_gear:` structured YAML field to Wesley Tate persona. Only Mora Companion, Council Tool Hudson Bay, Bahco Laplander, Filson Mackinaw may have unhedged first-person ownership claims.
- Added `--json` output mode.
- 45 HARD violations found across 36 articles; all fixed in Day 4.

### Day 4 — Platform fixes (prompt injection, orchestrator JSON contract)

- `article-roundup.v1.md` line 135: removed bad example ("I've owned one long enough to say that without hedging"). Added `{{OWNED_GEAR_CONSTRAINT}}` placeholder.
- `prompt_loader.py`: injects `{{OWNED_GEAR_CONSTRAINT}}` dynamically from persona YAML `owned_gear` field at prompt render time.
- Validator orchestration: added `--json` mode to V18, V20. Orchestrator now parses structured exit codes rather than stdout scraping.
- Site 16 corpus after Day 4: 0 HARD V18 violations, 0 V20 FAILs across 204 articles.
- `best-billy-can` and `katadyn-pocket-water-filter` regenerated via fixed pipeline (producer → fix-image-markdown.py → V18 → V20 → publish). Both live at HTTP 200.

### Day 5 P0 — Blocking orchestrator fixes

**Fix 1: Point 13 spawn+poll** (commit 6a61158, resolves B31)
- `p13-producer.mjs`: replaced `execSync` (12h timeout → SIGKILL) with `child_process.spawn`.
- Producer runs as child process. Stdout/stderr piped to `/tmp/<slug>-producer.log` in real-time.
- Orchestrator awaits `child.on('exit')`. No timeout — runs until natural completion.
- Non-zero exit → `{ status: fail, message: 'Producer exited with code N. See /tmp/...log' }`.

**Fix 2: GSC halt message — CF Pages env var step** (commit 6a61158, resolves B32)
- `p19-gsc.mjs`: halt message expanded to 11 steps including explicit CF Pages `GOOGLE_SITE_VERIFICATION` env var instruction.
- `wireGsc` now calls `cloudflare-pages-config.mjs set-env` after DNS TXT record.
- Resume flag changed to `--gsc-verification <hash>` (hash only; code constructs full TXT string).
- Legacy `--gsc-txt` alias kept for backward compatibility.

### Day 5 P1 — Pipeline and scaffold fixes

**Fix 3: PIPELINE.md Point 10.5 documentation** (commit 3befc30)
- Added Point 10.5 spec section: position in ritual (after Point 10, before Point 11), timeout (3h), cost (~$0.70–1.00 for 1,500 products at Haiku rates), idempotency, failure modes, placeholder detection logic.
- Version stamp: v1.6 → v1.7.

**Fix 4: Scaffold `logo_paths` block** (commit 3befc30, resolves B33)
- `initialise-site.mjs` `buildSiteConfig()` now emits `visual.logo_paths` with all 6 fields: `header_svg`, `header_png`, `favicon`, `footer_svg`, `social_square`, `open_graph_default`.
- Eliminates `Header.astro` / `SchemaMarkup.astro` null dereference on every new site's first build.

**Fix 5: Scaffold `{{BRAND_NAME}}` SVG substitution** (commit 3befc30, resolves B15)
- `{{BRAND_NAME}}` added to `TOKENS` dict in `initialise-site.mjs`.
- SVG logo templates (`logo-header.svg`, `logo-footer.svg`) now have brand name substituted at scaffold time.
- Eliminates manual `sed` substitution that was previously required after Point 7.

**Fix 6: Keyword pre-filter in `xlsx-to-pipeline.mjs`** (commit 3befc30, resolves B34)
- `isOffNiche()` function rejects TV scheduling queries, campus maps, named entertainment references, academic quiz questions, and gaming queries before `pipeline.json` is written.
- Tested against Site 16 XLSX: 13/13 off-niche keywords rejected, 0 false positives on 21 legitimate bushcraft keywords.
- Rejected keywords logged to `<output>-rejected.log` for auditability.

**Fix 7: CF Pages project auto-create at Point 16** (commit 3befc30, resolves B35)
- `p16-push-live.mjs` Step 0: checks `wrangler pages project list`, creates project if absent.
- Eliminates manual `wrangler pages project create` that blocked Site 16's first deploy.

**Fix 8: CF API token zone:create permission** (pending Keith, see B36)
- Current token confirmed missing `com.cloudflare.api.account.zone.create`.
- Steps to create replacement token documented in B36.
- Site 17+ domain attachment will work without registrar CNAME workaround once token is replaced.

---

## Backlog items remaining (P2 + deferred)

| # | Issue | Status |
|---|-------|--------|
| B29 | Producer image dict syntax — post-processor dependency | v1.7+ scope |
| B30 | V18 REVIEW tier calibration audit (84 items, Site 16) | v1.7 sprint |
| B36 | CF API token zone:create permission | Pending Keith |
| B2 | Em-dash producer prompt fix | Not fixed |
| B9 | Pipeline status writeback | Not fixed |
| B11 | Seller-prefix in product names (tool fix) | Not fixed |
| B12 | Doubled-apostrophe artifacts | Not fixed |
| B13 | Boilerplate identical pros/cons | Not fixed |
| B22 | Card voice not first-person (tool fix) | Not fixed |
| B24 | portfolio.yaml stale (automation) | Not fixed |

---

## Site 17 readiness

All P0 and P1 platform fixes are live in `/root/affiliate-platform/` as of commit `3befc30`. Site 17 can launch against this baseline. Outstanding B36 (CF token) will require the CNAME workaround for domain attachment until Keith creates the new token.
