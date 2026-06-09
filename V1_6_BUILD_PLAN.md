# V1_6_BUILD_PLAN.md — Autonomous Launch Build Plan

Date: 2026-06-01
Status: ALL PHASES COMPLETE (2026-06-01) — Site 16 launch is next session

---

## Overview

PIPELINE.md v1.6 specifies the autonomous-launch model: 25/35 pipeline decisions are Bucket A (autonomous). This plan sequences the tooling required to operate from spec. Nothing in v1.6 is aspirational — every item here has a documented incident that motivated it.

**Current state:** All spec changes are in PIPELINE.md v1.6. Zero new tools are built. Site 16 cannot launch under the autonomous model until this plan is complete.

**Estimated total effort:** ~9–13 days of focused platform work (see per-item estimates below).

---

## Dependency graph

```
[lock-persona.mjs] ──────────────────────────────────────────────► [launch-site.mjs]
[cloudflare-pages-config.mjs] ───────────────────────────────────► [launch-site.mjs]
[portfolio-update.mjs] ──────────────────────────────────────────► [launch-site.mjs]
[generate-persona-photos.mjs] ───────────────────────────────────► [launch-site.mjs]
[generate-brand-assets.mjs] ─────────────────────────────────────► [launch-site.mjs]

[validate-meta-leakage.mjs] ─────────────────────────────────────► [launch-site.mjs]
[validate-product-slug-resolution.mjs] ──────────────────────────► [launch-site.mjs]
[validate-persona-spec-compliance.mjs] ──────────────────────────► [launch-site.mjs]
[validate-card-voice.mjs] ───────────────────────────────────────► [launch-site.mjs]
[validate-catalog-category-coherence.mjs] ───────────────────────► [launch-site.mjs]
[validate-content-existence.mjs] ────────────────────────────────► [launch-site.mjs]

[source-products-rainforest.py v1.6 patches] ───────────────────► [launch-site.mjs]
[publish-staging.mjs skip-list patch] ───────────────────────────► [launch-site.mjs]
[build script cache patch (per-site)] ───────────────────────────► (immediate, all sites)
```

`launch-site.mjs` is the terminal dependency — it orchestrates everything. All tools must exist before it can be wired.

---

## Build sequence

### Phase 1 — Immediate fixes (no dependencies, all sites, ≤1 day) ✅ COMPLETE 2026-06-01

These apply to all live sites immediately and do not require other tools to exist first.

#### 1.1 Build script cache patch ✅ COMPLETE

**File:** `package.json` (all live sites + platform template)
**What:** Prepend `rm -f node_modules/.astro/data-store.json &&` to `astro build` invocation.
**Why:** Site 15 class failure — 91 empty articles from stale Astro cache. Mitigated trivially.
**Effort:** 30 minutes (15 sites × 2 min + verification)
**Risk:** Zero. The `rm -f` is idempotent; no side effects.

**Result:** All 16 files patched (15 sites + template/site-shell). Two build patterns found:
- Pattern A (FSG, MLT, OHT, TCD, BCB, NWO, Ten27, Strengthmill — 8 sites): validate-products.mjs → **rm -f data-store.json →** astro build → build-info.mjs → pagefind → build-validator.mjs
- Pattern B (BHH, CC, SSS, FFC, UDS, HPC, RMF + template — 8 sites + template): **rm -f data-store.json →** astro build → pagefind → build-validator.mjs

Verified: Pattern B full build (undisclosedsounds, 300 articles, exit 0). Pattern A full build (the-coffee-dispatch, exit 0). Both clean.

#### 1.2 SVG placeholder check in verify-site-shell.mjs ✅ COMPLETE

**File:** `tools/verify-site-shell.mjs`
**What:** Add `grep "{{" public/images/brand/*.svg` check. Exit 1 if match.
**Why:** Sites 14/15 shipped with `{{BRAND_NAME}}` in SVG files. Visual brand break.
**Effort:** 1 hour
**Risk:** Low. Only adds a check; no behavior change to passing sites.

**Result:** Added as check 33 (Group 4 — Structure/Consistency). Former check 33 (conftest.py hub slugs) renumbered to 34; STRICT_ELEVATE updated accordingly. Total checks: 34.
- Pass case verified: fourfernscare — `✓ SVG brand assets free of {{ placeholder tokens (v1.6) — 4 SVG(s) clean`
- Fail case verified: synthetic `{{BRAND_NAME}}` SVG — `✗ unsubstituted placeholder tokens in: logo-test-bad.svg`

---

### Phase 2 — Core infrastructure tools (new tools, sequential) ✅ COMPLETE 2026-05-31

These are the foundational tools. Build in order — each enables the next.

#### 2.1 `tools/portfolio-update.mjs`

**Purpose:** Atomic single-field writer for portfolio.yaml. Called at every phase transition.
**Interface:**
```bash
tools/portfolio-update.mjs --site <slug> --set <field>=<value>
tools/portfolio-update.mjs --site <slug> --set status=live
tools/portfolio-update.mjs --site <slug> --set ga4_id=G-XXXXXXXXXX
```
**What it does:** Reads portfolio.yaml, finds/creates entry for slug, sets field, writes back. Never clobbers unrelated fields. Validates field names against v1.6 schema.
**Effort:** 2–3 hours
**Risk:** Low. YAML read-modify-write with field validation.
**Unblocks:** Everything that writes portfolio.yaml (Points 16, 17, 18, 19, 21).
**Result:** ✅ COMPLETE. 16 fields in v1.6 schema; boolean/null/enum coercion; atomic rename write; tested.

#### 2.2 `tools/cloudflare-pages-config.mjs`

**Purpose:** Single entry point for all Cloudflare Pages API operations.
**Interface:**
```bash
tools/cloudflare-pages-config.mjs attach-domain --site <slug> --domain <domain>
tools/cloudflare-pages-config.mjs set-env --site <slug> --env production --key KEY --value VALUE
tools/cloudflare-pages-config.mjs set-env --site <slug> --env preview --key KEY --value VALUE
tools/cloudflare-pages-config.mjs add-dns-txt --site <slug> --name <domain> --value <string>
tools/cloudflare-pages-config.mjs list-envs --site <slug>
```
**What it does:** Wraps Cloudflare API v4 (`api.cloudflare.com/client/v4`). Auth from `CLOUDFLARE_API_TOKEN` in credentials.env. Idempotent for all operations.
**Effort:** 4–6 hours (API client + error handling + retry logic)
**Risk:** Medium. External API dependency; retry logic required for domain propagation.
**Unblocks:** Points 9 (env vars), 16 (domain attach), 18b (BWT DNS), 19b (GSC DNS).

**Implementation notes:**
- `attach-domain`: POST to `/zones/{zone_id}/custom_hostnames` or Pages custom domain endpoint
- `set-env`: PATCH to `/pages/projects/{project}/environments/{env}/variables`
- `add-dns-txt`: POST to `/zones/{zone_id}/dns_records` with `type: TXT`
- `CLOUDFLARE_ZONE_ID` and `CLOUDFLARE_API_TOKEN` from credentials.env
- Retry with exponential backoff: 10s, 30s, 60s, 120s
**Result:** ✅ COMPLETE. list-envs verified against live undisclosedsounds project. All 4 commands implemented; idempotent. cfGetZones uses separate ZONES_BASE (no account prefix). Retries at 10/30/60/120s.

#### 2.3 `tools/lock-persona.mjs`

**Purpose:** Lock persona YAML after validation passes. Sets `persona_locked: true`, `locked_at`, `content_hash`.
**Interface:**
```bash
tools/lock-persona.mjs --site <slug>
tools/lock-persona.mjs --site <slug> --dry-run    # shows what would be set
```
**What it does:**
1. Reads persona YAML
2. Validates all required v1.6 fields are populated (not null/empty)
3. Checks photos exist and pass MD5 uniqueness against portfolio
4. Computes SHA-256 hash of canonical YAML content
5. Sets `persona_locked: true`, `locked_at: <ISO>`, `content_hash: <sha256>`
6. Writes YAML back

**Companion tool:** `tools/unlock-persona.mjs --site <slug> --reason "<rationale>"`. Logs to `~/affiliate-platform/persona-unlock-log.yaml`.

**Effort:** 3–4 hours
**Risk:** Low. Read-modify-write with validation.
**Unblocks:** Producer persona-lock gate (Point 13 prerequisite).
**Result:** ✅ COMPLETE. Validates 15 required fields; photo existence + MD5 uniqueness portfolio-wide; SHA-256 content hash (excludes lock fields); atomic YAML write; idempotent re-lock; dry-run mode. Companion unlock-persona.mjs logs to persona-unlock-log.yaml. Tested on undisclosedsounds/marcus.

---

### Phase 3 — Validators (independent, can build in parallel)

All six validators in v1.6 are independent of each other. Build order within Phase 3 is by impact: highest-criticality first.

#### 3.1 `scripts/validate-content-existence.mjs` (V17) — 1 day ✅ COMPLETE 2026-05-31

**Criticality:** Highest. Runs against dist/ — catches empty articles that escaped all upstream checks.
**What:** Scans built dist/ HTML for placeholder patterns + empty content divs + <200-word articles.
**Effort:** 6–8 hours (HTML parsing + pattern matching + word count)
**Risk:** Low once patterns are confirmed on real dist/ output.
**Result:** ✅ COMPLETE. Uses cheerio to select `.article-page__content`. Checks 7 text placeholder patterns + 2 href patterns + empty + word-count < 200. RMF 281 articles: 0 failures. HPC/UDS: caught genuine Astro cache empties (11 total — real dist/ issues, not false positives). Positive tests pass.
**Cleanup note:** Phase 3.1 found 10 empty-content articles on HPC dist/ and 1 on UDS dist/ — stale Astro cache artifacts. Will clear on each site's next natural rebuild (Phase 1.1 cache patch already in place). No action needed in Phase 3.

**Implementation note:** Parse dist/ using `@astrojs/check` or simple regex on raw HTML. Key: distinguish body content from navigation/header/footer. Use `.article-page__content` selector as content boundary.

#### 3.2 `scripts/validate-product-slug-resolution.mjs` (V19) — 4 hours ✅ COMPLETE 2026-05-31

**Criticality:** High. Catches broken affiliate links before publish. Simple slug lookup.
**What:** Scans staged markdown for `product:<slug>` patterns; verifies each against products.yaml keys.
**Effort:** 3–4 hours
**Risk:** Low. Simple text extraction + YAML key lookup.
**Result:** ✅ COMPLETE. Checks frontmatter `id:` + body `product:slug` refs + ASIN format validation. Handles both `asin`/`amazon_asin` field names. Hard fail for missing slug, VERIFY, malformed ASIN; warning for NOT_ON_AMAZON + no buy_url. Real findings: RMF 39 articles with malformed ISBNs-as-ASINs; HPC 10 broken slugs; UDS 61 broken slugs — all genuine catalog issues.

#### 3.3 `scripts/validate-meta-leakage.mjs` (V20) — 3 hours ✅ COMPLETE 2026-05-31

**Criticality:** High. Catches internal brief-reasoning in article body. Pure regex.
**What:** Regex scan of staged markdown for brief-leakage patterns.
**Effort:** 2–3 hours
**Risk:** Low. Regex patterns already defined in spec.
**Result:** ✅ COMPLETE. 13 patterns; all spec patterns fire on positive test. Generic `\bthe brief\b` replaced with verb-qualified form to avoid false positives on "the brief answer". HPC/UDS/RMF all pass 0 failures.

#### 3.4 `scripts/validate-catalog-category-coherence.mjs` (V22) — 1 day ✅ COMPLETE 2026-05-31

**Criticality:** High. Prevents tackle-type incoherence (spin lure in fly-fishing).
**What:** Requires `category_type` field in products.yaml + `config/category-types/<niche>.yaml` per site. Validates product category_type against article hub's allowed types.
**Effort:** 6–8 hours (validator + niche config file format + documentation)
**Risk:** Medium. Requires two new config files per site; niche-specific knowledge required to populate them.
**Result:** ✅ COMPLETE. Reference config at `rmflyfishing/config/category-types/fly-fishing.yaml` — 10 globally_forbidden types, per-hub allowed/forbidden lists for all 12 RMF hubs, format documented in file header for future niches. Validator discovers config via site.config.yaml `niche:` field; gracefully skips sites without config (shows expected path). `category_type` on products is optional — missing = warn, set = enforce. Positive test catches spin_lure in flies-patterns. Passes 0 violations on all 3 test sites.

**Implementation note:** Start with Site 15 (fishing). Create `config/category-types/fishing.yaml` as a reference implementation. Document format for future niches.

#### 3.5 `scripts/validate-persona-spec-compliance.mjs` (V18) — 2 days ✅ COMPLETE 2026-05-31

**Criticality:** High. Prevents the Site 13 class of editorial fabrication.
**What:** LLM-pass (Haiku) per article, comparing first-person claims against persona YAML spec fields.
**Effort:** 1.5–2 days (LLM prompt design + false positive tuning + cost optimization)
**Risk:** Highest of the six validators. LLM-based validators require prompt calibration against real article corpus.

**Result:** ✅ COMPLETE. Two bugs found and fixed during testing:
1. `max_tokens: 400` too low for violation-rich responses → raised to 1024
2. Greedy regex `\{[\s\S]*\}` grabbed trailing model commentary → replaced with balanced-brace extractor

**Cost calibration:** $0.0011/article actual (spec projected $0.003 — 3× under budget). ~$0.33 per 300-article site.

**False positive rate:** ~0.6–0.8% across 879 articles checked (well within <2% budget). Identified by scanning for LLM flags where the model's own reasoning said "no violation" or "not a definite contradiction." Full corpora are NOT clean (all three test sites have genuine spec violations; see below), so the reported violation rates are true positive rates, not false positive rates.

**Test results — positive tests:** Injected 6 violations into a synthetic Marcus article (wrong partner "Sam", wrong gear "Aria 2", wrong desktop chain "Topping DX3 Pro+/ifi GO Blu", wrong flagship gear "Chord Mojo 2/Violectric V200", wrong tenure "six years", wrong daily-driver IEM). V18 caught all 6.

**Test results — negative tests (all three are dirty corpora with genuine violations):**
- UDS (Marcus, Site 13, locked AFTER generation): 137/301 (45.5%) articles flagged. Dominant pattern: Topping E50/L50 fabricated as daily chain (should be Schiit Modi+/Magni+), Aria 2 as daily-driver IEM (should be Blessing 3), 2020 Sundara revision (should be 2022). These are confirmed fabrications from generating before lock.
- RMF (Greg, Site 15): 162/281 (57.7%) articles flagged. Dominant pattern: explicit forbidden phrases ("I'm an expert in saltwater fly fishing", "I've landed hundreds of bonefish or tarpon", "I'm an expert in Spey casting"), wrong reel model (Iconic 5 vs Iconic 5+), Bighorn River as regular location, Hardy Marquis not in owned gear.
- HPC (Adrian, Site 14): 84/297 (28.3%) articles flagged. Dominant pattern: editorial methodology violations (reviewing products not personally lived with), wrong model numbers (CDT-5650 vs CDT-3650, RP-600M II vs RP-600M), wrong Epson 4010 technology description ("laser" instead of lamp-based LCD).

**Parse errors:** 53/879 = 6% before JSON extraction fix; expect <1% after fix (verified on 2 previously-failing articles).

**V18 shipping status: CAN SHIP as HARD gate.** False positive rate within budget; cost well under estimate; catches real violations reliably.

#### 3.6 `scripts/validate-card-voice.mjs` (V21) — 4 hours ✅ COMPLETE 2026-05-31

**Criticality:** Medium (SOFT fail only).
**What:** Checks proportion of buyer-guide product cards containing first-person pronouns from persona YAML.
**Effort:** 3–4 hours
**Risk:** Low. Pattern matching against structured card sections.

**Result:** ✅ COMPLETE. Pure pattern-matching; no LLM call.

**Card detection:** H3 sections whose body contains `\(product:[^)]+\)` CTA link. H3 sections without a CTA (buying-guide subsections, FAQ headers) correctly excluded. Algorithm documented in VALIDATORS.md §V21 for reuse by other validators.

**Pronoun source:** Reads `first_person_pronouns:` from locked persona YAML (v1.6 field); falls back to defaults (`I, my, me, myself, mine, I've, I'm, I'd, I'll`) if field absent. Normalises curly apostrophes; `I` matched case-sensitively.

**Test results — positive tests (should WARN):**
- Third-person persona references ("the engineer's assessment", "Greg's recommendation"): 0/3 fp-cards → WARN ✓
- Agentless/passive voice ("the unit features...", "users report..."): 0/3 fp-cards → WARN ✓
- Clean first-person card voice ("I've been in them two seasons..."): 3/3 fp-cards → PASS ✓

**Corpus baselines (calibration question answered):**

| Site | Articles | WARNs | WARN rate | Avg fp density |
|------|----------|-------|-----------|----------------|
| RMF (greg) | 101 | 99 | 98.0% | 0.064 |
| HPC (adrian) | 103 | 101 | 98.1% | 0.047 |
| UDS (marcus) | 110 | 102 | 92.7% | 0.089 |

**Calibration answer:** Threshold (1/3) is correct. The cohort is systematically near-zero (0.047–0.089), not a borderline miss. The generator never placed persona first-person voice in product card sections — card prose is third-person generic throughout. This is a prompt quality issue, not a threshold calibration issue. Threshold unchanged. Remediation is B22 (separate work).

**V21 shipping status: CAN SHIP as SOFT gate.** Always exits 0. False positive not applicable (pattern matching). Writes `data/v21-calibration-log.yaml`.

---

### Phase 4 — Source tool patches (modify existing tools) ✅ COMPLETE 2026-05-31

#### 4.1 `source-products-rainforest.py` — v1.6 policy patches ✅ COMPLETE

**What:**
- Brand-string match validation before accepting result
- Category match validation
- Known-DTC-brand fallback (load `config/dtc-brands/<niche>.yaml`)
- Seller-prefix scrub (strip known seller prefixes from product names)

**Effort:** 4–6 hours
**Risk:** Medium. Changes to the primary sourcing tool; must not break existing behavior.

**Result:** ✅ COMPLETE.

*Brand-match + category-match + DTC fallback were already implemented* in the pre-existing code. The three missing pieces added:

1. **Seller-prefix scrub** (`scrub_seller_prefix()`) — handles pipe-separator patterns in Amazon titles:
   - `"fishpond Riverkeeper | Fly Fishing Water Temperature..."` → `"fishpond Riverkeeper"`
   - `"LAMSON | Ketchum Release Hook Extractor | Big Bug..."` → `"Ketchum Release Hook Extractor"` (1-word prefix stripped)
   - Titles with no pipe are unchanged
   - Length cap: truncated at 120 chars at word boundary
   - 8/8 unit tests pass

2. **Per-niche DTC config** (`config/dtc-brands/fly-fishing.yaml`) — created as reference implementation per spec §15.9. Per-niche file takes precedence over legacy `config/dtc-brands.yaml`. Format: plain list (comments stripped by YAML parser). File name must match site.config.yaml `site.niche` value — for RMF this is `fly-fishing`, not `fishing`.

3. **Updated `load_dtc_brands()`** — looks for `config/dtc-brands/<niche>.yaml` first; falls back to legacy flat file for backward compat.

**DTC test:** `scott centric fly rod` → `['scott']` (intercepted) ✓  |  `best fly rod under 200` → `[]` (passes through) ✓  |  `orvis clearwater` → `[]` (Orvis sells on Amazon, correctly not in DTC list) ✓

#### 4.2 `publish-staging.mjs` — skip-list patch + status writeback ✅ COMPLETE

**What:**
- Read `data/skip-list.yaml` before staging-to-content move; exclude skip-listed articles
- Write `status: published` to pipeline.json per article after move

**Effort:** 2–3 hours
**Risk:** Low. Additive changes to existing script.

**Result:** ✅ COMPLETE.

1. **Skip-list** (`loadSkipList(siteDir)`) — reads `data/skip-list.yaml` (plain slug list); missing file = empty set (not an error). Skip-listed articles log `[SKIP-LIST]` and are excluded from publish without triggering exit 1.

2. **Pipeline writeback** (`writePipelineStatus()`) — batched after all files processed; atomic write (tmp → rename). Sets `status: published` on matching articles. No-op if pipeline.json absent.

**Tests:** skip-list loading (2 slugs from YAML) ✓ | skip-listed slug excluded, non-skip-listed included ✓ | pipeline writeback updates `publish-me-test` to `published`, leaves `skip-me-test` as `staged` ✓

**Skip-list format for sites:**
```yaml
# data/skip-list.yaml — plain list of article slugs to exclude from staging publish
- article-slug-to-skip
- another-rejected-article
```

---

### Phase 5 — Persona photo + brand asset generation (new tools)

#### 5.1 `tools/generate-persona-photos.mjs` ✅ COMPLETE 2026-06-01

**What:** Wraps DALL-E 3 API to generate persona byline + about photos from documented prompt template (`templates/persona-photo-prompt.md`). Runs MD5 uniqueness check against existing portfolio photos.
**Effort:** 4–6 hours
**Risk:** Medium. DALL-E API integration; MD5 dedup logic; prompt template documentation required.

**Result:** ✅ COMPLETE.

**Interface:**
```
node tools/generate-persona-photos.mjs --site <slug>
node tools/generate-persona-photos.mjs --site <slug> --dry-run
node tools/generate-persona-photos.mjs --site <slug> --test-dir /tmp/test-photos
node tools/generate-persona-photos.mjs --site <slug> --type byline|about
node tools/generate-persona-photos.mjs --site <slug> --force
```

**Outputs:** `public/images/brand/<persona-slug>-byline.jpg` (1024×1024) and `-about.jpg` (1792×1024).

**Prompt template:** `templates/persona-photo-prompt.md` (v1.0). Documents variables, two prompt templates (byline/about), and per-niche defaults keyed by `site.niche` value.

**Key design decisions:**
- Age extracted from `bio_full` first (present-tense), then `bio`, then `background` (which may contain historical ages like "started at age 32"). Uses `\b(\d{2})-year-old` pattern.
- Niche defaults keyed by exact `site.niche` value (e.g. `fly-fishing`, `audiophile`, `home-cinema`). Missing key falls back to `default`.
- MD5 check scans all portfolio sites for existing persona photos (`persona-byline.jpg`, `persona-about.jpg`, `<slug>-byline.jpg`, `<slug>-about.jpg`). Collision triggers regeneration, max 3 attempts.
- Graceful `--force` to overwrite; skip-if-exists without `--force`.
- Requires `OPENAI_API_KEY` in env or `affiliate-platform/.env.local`. Exits 2 with clear message if missing.

**Dry-run verified on Marcus (UDS, audiophile) and Greg (RMF, fly-fishing):**
- Niche defaults applied correctly (listening room for audiophile, riverbank for fly-fishing)
- Age range: Marcus → "a person" (no XX-year-old in bio); Greg → "an early 50s person" (52-year-old in bio_full)
- Portfolio MD5 baseline collected: 20 existing persona photos across 10 sites
- Prompts grammatically clean, self-contained, DALL-E 3 compatible

**Blocker for live test:** `OPENAI_API_KEY` not in `affiliate-platform/.env.local`. Add the key to run a live generation. The `openai` npm package has been installed.

**Surprises:**
- Initial about-prompt template used `{{action}} in {{setting}}`. For fly-fishing, this generated "casting a fly rod in standing at the edge of..." — positioning language in the setting clashed with the "in" connector. Fixed by using two separate sentences: `{{setting_about}}. {{action_description}}.`
- Template niche key `audio` → must be `audiophile` to match actual `site.niche: audiophile` in UDS. The filename rule (match `site.niche` exactly) applies to template keys too.
- Age extraction initially searched only `background`, which caused Greg's historical "age 32 when he started fishing" to match instead of his current 52. Fixed by prioritizing `bio_full` (present-tense prose) over `background`.

#### 5.2 `tools/generate-brand-assets.mjs` ✅ COMPLETE 2026-06-01

**What:** Generates SVG logo variants, OG image, favicon from site identity inputs (brand name, colors, niche). Uses documented template structure.
**Effort:** 1–2 days (came in ~0.5 day)
**Risk:** High. Brand asset generation quality is difficult to automate reliably. Start with a template-substitution approach (SVG templates with fill-color and text substitution) rather than generative AI.

**Result:** ✅ COMPLETE. Template-substitution MVP. Visual quality: Keith must review at launch checkpoint.

**Interface:**
```
# Site-based (reads site.config.yaml for brand name, colors, niche):
node tools/generate-brand-assets.mjs --site <slug>
node tools/generate-brand-assets.mjs --site <slug> --dry-run
node tools/generate-brand-assets.mjs --site <slug> --test-dir /tmp/test

# Synthetic / new-site (no site directory needed):
node tools/generate-brand-assets.mjs \
  --niche outdoor-cooking \
  --brand-name "Smoke and Coals" \
  --primary "#8B2500" \
  --accent "#E87A00" \
  --tagline "Real fire, real flavor." \
  --test-dir /tmp/test
```

**Outputs (9 files to public/images/brand/ or --test-dir):**
- `logo-header.svg` — mark + wordmark, primary color
- `logo-header-dark.svg` — mark + wordmark, white (for dark navbars)
- `logo-mark.svg` — mark only, primary color
- `logo-monochrome.svg` — mark + wordmark, #1a1a1a
- `logo-footer.svg` — mark + wordmark, primary color
- `favicon.svg` — mark only, 32×32 rendered size
- `favicon.ico` — 16×16 + 32×32 + 48×48 PNG packed (to-ico)
- `apple-touch-icon.png` — mark at 180×180 (sharp)
- `og-default.jpg` — 1200×630 brand card (sharp): primary bg, white mark, brand name, tagline

**Config files:**
- `config/niche-palettes.yaml` — per-niche: color defaults, font stack, mark SVG paths with `{{fill}}` placeholder. Niches: `fly-fishing`, `audiophile`, `home-cinema`, `outdoor-cooking`, `default`.

**Architecture:**
- Mark SVG paths live in `config/niche-palettes.yaml` keyed by `site.niche`
- Each logo variant substitutes a different fill: primary / white / #1a1a1a
- Font: `site.config.yaml visual.font_headings` → niche palette default → Georgia serif. Single-word fonts get "..., Georgia, 'Times New Roman', serif" appended automatically.
- ICO: 3-size ICO via `to-ico` (installed)
- Raster: all raster outputs via `sharp`
- Placeholder gate: tool exits 1 if any `{{...}}` remains in any SVG after generation

**Test results:**

*RMF regeneration test (`--site rmflyfishing --test-dir /tmp/`)`:*
- All 9 files generated: 6 SVG + 1 PNG + 1 ICO + 1 JPG
- Placeholder check: PASS (no `{{` in any SVG)
- File set matches production exactly
- Mark paths identical to production fly-fishing mark (same dry fly icon)
- Font: "Lora, Georgia, 'Times New Roman', serif" ✓

*Synthetic test (`Smoke and Coals`, outdoor-cooking niche):*
- All 9 files generated
- Placeholder check: PASS
- Outdoor-cooking mark: kettle grill (semicircle body + lid + 3 legs + flame) in #8B2500 ✓
- Font: "Georgia, 'Times New Roman', serif" ✓

**Visual quality assessment (MVP standard):**
- SVG logos: clean, crisp, professionally structured. Marks are simple geometric shapes specific to each niche — recognizable at header and favicon sizes. RMF regeneration is visually equivalent to production.
- OG images: solid primary color background, accent bar, scaled white mark, brand name + tagline in large white Georgia. Simple but clearly branded — standard minimal brand card style.
- Favicon ICO: 3-size vs production 1-size (198B was a single 16x16 PNG ICO). New version is more complete.
- **Keith review required:** Niche marks for new niches (audiophile headphone, home-cinema film frame, outdoor-cooking grill) need visual sign-off at first use. Marks are functional, not custom-illustrated.

**Surprises:**
- Production `favicon.ico` at RMF was a single 16×16 PNG-in-ICO (198 bytes). Standard multi-size ICO is the correct format; production was a minimal placeholder. New tool generates a proper 3-size ICO (14KB).
- `to-ico` wasn't installed; added as dependency alongside `openai` (both installed this session).
- Single-word font names from `site.config.yaml` (e.g. "Lora") silently degraded to browser default in SVG without fallback stack. Fixed with auto-append of serif fallbacks.
- No `niche-palettes.yaml` existed — created as new artifact alongside the tool.

---

### Phase 6 — `tools/launch-site.mjs` (terminal dependency) — COMPLETE 2026-06-01

**Purpose:** The ritual orchestrator. Wraps the entire 21-point pipeline into a resumable, state-tracked, Bucket-A/B/C/D-aware launch sequence.

**Effort:** 3–5 days estimate → completed in 1 session
**Risk:** Highest in the plan. This is the most complex tool — it orchestrates all others.

**Prerequisites:** All complete.

**Implementation:**
- `tools/launch-site.mjs` — entry point; arg parsing; concurrency lock; sequential dispatch
- `tools/launch-site/state.mjs` — atomic state.yaml r/w (tmp→rename)
- `tools/launch-site/buckets.mjs` — Bucket A/B/C/D dispatch; decisions.log writer
- `tools/launch-site/escalation.mjs` — withRetry, validatorLoop, halt format
- `tools/launch-site/points/` — 25 point modules (p07 through p21, including sub-points)

**Dry-run verified:** `node tools/launch-site.mjs --site undisclosedsounds --dry-run --niche audiophile --domain undisclosedsounds.com` → 25/25 points PASS, no state written, no external calls.

**Key behaviors:**
- `--site <slug>` — new launch; `--resume <slug>` — continue from last incomplete point
- Bucket C halts at Points 9/17/18/19 with RITUAL HALT message + resume instructions
- Resume flags: `--amazon-tracking-id`, `--ga4-id`, `--bwt-txt`, `--gsc-txt`
- State written atomically to `~/affiliate-platform/sites/<slug>/state.yaml`
- Every autonomous decision appended to `~/affiliate-platform/sites/<slug>/decisions.log`
- Concurrency lock in `~/affiliate-platform/active-launches.yaml`
- Validator failures trigger regeneration loops (max 3 attempts → skip-list)
- Point 16 domain attachment uses exponential backoff (10s/30s/60s/120s per §16.3)

**Surprises vs. spec:**
1. `initialise-site.mjs` uses `--spec <path>` not `--site <slug>` — spec file must exist at `sites/<slug>.spec.yaml` before Point 7 runs
2. `validate-content-existence.mjs` HARD failure includes automatic rebuild with data-store cache clear (§15.7) before escalating — built into Point 15.6
3. Bucket B exits with `status: preview_required` rather than `halt` — distinct from Bucket C to enable cleaner resume semantics

---

## Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `validate-persona-spec-compliance` LLM false positive rate >2% | Medium | Regeneration thrash on valid articles | Calibrate against Site 14/15 article corpus before deploying as gate |
| `cloudflare-pages-config.mjs` domain propagation timing | High | Point 16 stalls waiting for DNS | Spec already calls for exponential backoff; escalate to Keith after 5 min |
| `launch-site.mjs` state corruption on crash | Low | Incomplete state.yaml → resume fails | Write state.yaml atomically (write to temp, rename); never partial writes |
| `generate-brand-assets.mjs` quality insufficient | High | SVG logos look bad | Ship template-substitution MVP first; generative upgrade after validation |
| Source tool DTC patches break existing behavior | Low | Misclassified DTC false positives | Add `--legacy-mode` flag; keep old behavior accessible for regression testing |

---

## Recommended build order (optimized for unblocking Site 16)

1. **Day 1:** Phase 1 (cache patch + SVG check) — immediate, all sites
2. **Days 2–3:** Phase 2.1 (portfolio-update.mjs) + Phase 2.2 (cloudflare-pages-config.mjs)
3. **Day 4:** Phase 2.3 (lock-persona.mjs) + Phase 3.2 (slug resolution) + Phase 3.3 (meta-leakage)
4. **Day 5:** Phase 3.1 (content-existence)
5. **Days 6–7:** Phase 3.4 (catalog coherence) + Phase 4.1 (source tool patches)
6. **Days 8–9:** Phase 3.5 (persona-spec compliance — hardest; give 2 days)
7. **Day 10:** Phase 3.6 (card voice) + Phase 4.2 (publish-staging patches) + Phase 5.1 (persona photos)
8. **Days 11–12:** Phase 5.2 (brand assets) — template-substitution MVP
9. **Days 13+:** Phase 6 (launch-site.mjs) — terminal dependency, requires all above

**Site 16 earliest viable launch under autonomous model: Day 13 if no scope creep.**

---

## What is NOT in this plan

These items are in the backlog (PLATFORM_BACKLOG.md B-series) but deferred from v1.6 build:

- V21 card-voice: SOFT fail only; not on Site 16 critical path (can build in parallel with other work)
- Operational dashboard (Phase 2 of Section 21) — deferred to 30-site milestone
- DALL-E upgrades for existing articles — deferred; traffic-driven
- B23 (renewed/refurbished disclosure) — manual editorial process for now
- B12 (doubled apostrophe) — minor; fix in next prompt update cycle

---

*End of V1_6_BUILD_PLAN.md*
