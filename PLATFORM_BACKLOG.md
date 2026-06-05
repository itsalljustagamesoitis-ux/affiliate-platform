# Platform Backlog — Issues Found During Sites 13/14/15 Editorial UAT

Last updated: 2026-06-05 (Day 8 V18/V20 remediation — B37–B40 added)
Source: Site 13–15 cohort UAT; Chrome Claude UAT sessions; post-rebuild editorial fix sessions

**v1.6 status column added below:** Every item is mapped to the v1.6 PIPELINE.md section that addresses it, or marked as still needing a fix.

---

## B1 — Cookie consent: declined state wiped on page load [FIXED]

**File:** `affiliate-platform/src/layouts/BaseLayout.astro`
**Status:** Fixed in this session (2026-05-31)

**Root cause:** The early GA4 consent check in BaseLayout.astro removed the localStorage key
when consent value was `'0'` (declined), wiping the declined state on every page load.
The `else` branch fired for ANY non-granted consent (including declined).

**Fix applied:** Changed logic to only remove the key if the entry is expired (≥365 days old),
not if it's a valid declined response.

---

## B2 — Producer: em-dash rendered as space-comma-space [REQUIRES PROMPT FIX]

**Scope:** 253/300 articles in Site 14 initial build (systemic)
**Status:** Fixed on Site 14 via global sed. Root cause NOT fixed.

**Root cause:** Producer LLM generates ` , ` (space-comma-space) in place of ` — ` (em-dash)
in article body prose. Likely a prompt tokenization artifact — the em-dash character may not
be reliably produced by the generation model used.

**Recommended fix:** Add post-generation validation in build-validator.mjs to detect ` , ` patterns
in article HTML output and WARN. Add to producer prompt: explicit instruction to use `—` (em-dash
character U+2014) rather than `,` for parenthetical insertions.

---

## B3 — Producer: unfilled price token in internal links [REQUIRES PROMPT FIX]

**Scope:** 54 articles in Site 14, 134 instances
**Status:** Fixed on Site 14 via Python script. Root cause NOT fixed.

**Root cause:** Producer generates internal links with blank price text:
`[best AV receivers under ](/best-av-receiver-under-500/)`. The price was supposed to be
filled in by the producer but was left blank. Combined with `dollar_figures: allowed: false`
policy, there is no correct price to insert anyway.

**Recommended fix:** Update producer prompt to use tier labels instead of prices in internal
link text (e.g., "entry-tier AV receiver picks" not "best AV receivers under $500"). Add
post-generation validation to detect `\[[^\]]*under \]\(` pattern in article markdown.

---

## B4 — Producer: internal brief-reasoning published in article body [REQUIRES PROMPT FIX]

**Scope:** 10 articles in Site 14 initial build
**Status:** Fixed on Site 14 by regeneration (8/10) and surgical deletion (2/10). Root cause NOT fixed.

**Root cause:** When a product list doesn't match the article keyword (e.g., keyword "polk vs klipsch"
but all products are Klipsch), the LLM writes its internal reasoning process into the article body
before generating content: "The keyword in the brief is X, but the products are Y..."

**Recommended fix:** 
1. Add pre-generation validation in producer to flag keyword-product brand mismatches before generation.
2. Update producer prompt with explicit instruction: never write meta-commentary about the brief, product
   list, or generation process into the article body.
3. Add post-generation regex check: detect patterns like "the brief", "the keyword is", "in this brief",
   "the article will" in article body and reject with SHAPE FAIL.

---

## B5 — Producer: article_specific_pros/cons left as null YAML [REQUIRES SCHEMA FIX]

**Scope:** ~166 articles in Site 14
**Status:** Fixed on Site 14 via Python scripts. Root cause partially fixed.

**Root cause:** When producer generates articles with empty pros/cons arrays, or when boilerplate
is stripped from pros/cons fields, the YAML format leaves bare null keys:
```yaml
article_specific_pros:
article_specific_cons:
```

YAML null values are treated as JavaScript `null` by the Astro YAML parser, which Zod reports
as type "object" (due to `typeof null === 'object'`). The schema `z.array(z.string()).optional()`
only accepts `undefined` (key absent) or string arrays, not `null`.

**Recommended fix (Option A — Schema):** Change schema to `z.array(z.string()).nullish()` to
accept both null and undefined. This is the least-effort fix.

**Recommended fix (Option B — Producer):** Ensure producer writes `article_specific_pros: []`
(explicit empty array) rather than bare keys when there is no content.

---

## B6 — Catalog: wrong-hub products assigned to articles [REQUIRES CATALOG VALIDATION]

**Scope:** Multiple articles in Site 14 (speaker stand in subwoofers hub, headphone in av-receivers hub)
**Status:** Fixed per-article. Root cause NOT fixed.

**Root cause:** During catalog ingestion, products were assigned to the wrong hub (e.g., Monolith
speaker stand assigned to `hub: subwoofers`, Bowers & Wilkins headphone assigned to `hub: av-receivers`).
These wrong-hub products then appeared in pipeline.json product lists for articles in those hubs.

**Recommended fix:** 
1. Add catalog ingestion validation to flag products where the product name doesn't match
   the assigned hub (e.g., "speaker stand" in `subwoofers` hub).
2. The existing `validate-product-coherence.py` should be expanded to cover this case.
3. Add preflight check: reject pipeline articles where any product's hub doesn't match the article hub.

---

## B7 — Producer: Renewed/Refurbished products as primary picks [EDITORIAL POLICY GAP]

**Scope:** Multiple articles across portfolio
**Status:** Disclosure added on Site 14 articles. No catalog-level fix.

**Root cause:** Catalog ingestion includes Renewed/Refurbished Amazon listings as primary products.
When these are assigned as `best_overall` or `primary` picks, the article needs explicit disclosure
but the producer doesn't automatically add it.

**Recommended fix:**
1. Add `condition: renewed` field to products.yaml for Renewed/Refurbished listings.
2. Add build-validator check: WARN when a `best_overall` product has `condition: renewed`.
3. Update producer prompt to automatically include Renewed condition disclosure when
   `condition: renewed` is set on the primary product.

---

## B8 — SVG logos: fill="currentColor" invisible when loaded as <img> [FIXED on HPC]

**File:** All logo SVGs in `public/images/brand/`
**Status:** Fixed on Site 14 (2026-05-30). NOT propagated to other sites.

**Root cause:** SVG files used `fill="currentColor"` which requires CSS `color` inheritance.
When loaded as `<img>` tags (as Astro's `<Image>` component does), SVGs don't inherit CSS,
causing invisible icons on any background that doesn't provide a contrasting `color` value.

**Recommended fix:** Any new site's logo SVGs must use hardcoded hex fill values, not
`currentColor`. Document in site spin-up checklist.

---

## Summary table — B1–B8 (original HPC findings)

| # | Issue | Scope | Status | v1.6 section |
|---|-------|-------|--------|--------------|
| B1 | Cookie consent: declined state wiped | Platform-wide | **Fixed** | — (template fix) |
| B2 | Em-dash rendered as ` , ` | Producer prompt | HPC fixed; prompt fix pending | §15.12 |
| B3 | Unfilled price tokens in links | Producer prompt | HPC fixed; prompt fix pending | §13.0 prereq #5 |
| B4 | Brief-reasoning in article body | Producer prompt | HPC fixed; prompt fix pending | §15.2, V20 |
| B5 | pros/cons null YAML schema mismatch | Schema or producer | HPC fixed; schema fix pending | §13.0 prereq; producer fix |
| B6 | Wrong-hub products in catalog | Catalog validation | HPC fixed per-article; validator pending | V22, §15.10 |
| B7 | Renewed products as primary picks | Editorial policy | HPC disclosed; catalog field pending | §15.18 backlog |
| B8 | SVG currentColor invisible as img | Site spin-up | HPC fixed; checklist update pending | §15.18 backlog |

---

## B9–B24 — Additional findings from Sites 13/14/15 cohort

### B9 — Pipeline status writeback never fires [REQUIRES TOOL FIX]

**Scope:** Sites 13, 14, 15 (and likely earlier sites)
**Status:** Not fixed. Root cause: producer and publish-staging.mjs don't write back to pipeline.json.
**v1.6 section:** §15.11

**Root cause:** All 300 articles in pipeline.json show `status: not_started` after publish. Neither the producer nor `publish-staging.mjs` updates pipeline.json status fields. Operational dashboard cannot reflect true published state.

**Fix:** Producer writes `status: generated` after staging; `publish-staging.mjs` writes `status: published` when article moves to content/articles/.

---

### B10 — Persona photo byline path-construction bug [REQUIRES TEMPLATE FIX]

**Scope:** Sites 13, 14, 15
**Status:** Not propagated to fix. Sites 1–12 unverified.
**v1.6 section:** §15.18

**Root cause:** Persona byline image uses page-relative path construction instead of root-absolute, causing broken image on any non-root URL depth.

**Fix:** Update byline image path construction in `AuthorBio.astro` to use root-absolute path (`/images/brand/<slug>-byline.jpg`).

---

### B11 — Seller-prefix in product names [REQUIRES SOURCING FIX]

**Scope:** Site 15 (10+ products: `STOVER Patagonia`, `SIMMS Waders`, etc.)
**Status:** Partially fixed per-article on Site 15. Root cause not fixed.
**v1.6 section:** §15.9

**Root cause:** Amazon's Rainforest API returns seller-prefixed product names (e.g., `STOVER Patagonia Swiftcurrent Waders`). Sourcing tool ingests name verbatim. Article title and brand matching fail or produce awkward prose.

**Fix:** Add seller-prefix scrub to `source-products-rainforest.py`. Scrub list derived from known third-party seller prefixes; also apply a heuristic: first word all-caps and not a known brand name → strip.

---

### B12 — Doubled-apostrophe escape artifacts [REQUIRES PRODUCER FIX]

**Scope:** Site 15 (Greg persona articles — `Greg''s` and similar)
**Status:** Not fixed.
**v1.6 section:** §15.18

**Root cause:** Producer template string escaping doubles apostrophes in persona name possessives when the persona name is injected into a YAML field that is itself single-quoted.

**Fix:** Audit producer persona name injection; fix apostrophe escaping in template rendering. Add `check_output_shape()` check for doubled-apostrophe patterns.

---

### B13 — Boilerplate identical pros/cons across products [REQUIRES PROMPT FIX]

**Scope:** Site 14 (multiple buyer guides)
**Status:** Not fixed. Root cause: `generate-product-pros-cons.py` using insufficiently product-specific prompts.
**v1.6 section:** §15.18

**Root cause:** Pros/cons generation uses a single product name as input without product description, category context, or differentiation signal. Result: semantically identical pros/cons across similar products in the same hub (e.g., all AV receivers get "easy to use interface" + "good build quality").

**Fix:** Update `generate-product-pros-cons.py` to include product description, ASIN-level spec data, and neighboring product context in the prompt. Add V18-style check: flag articles where >50% of products share identical pros/cons text.

---

### B14 — Astro data-store cache produces empty articles [REQUIRES BUILD SCRIPT FIX]

**Scope:** Site 15 (91 articles)
**Status:** Fixed per §15.7 spec change. Build script update required.
**v1.6 section:** §15.7

**Root cause:** `node_modules/.astro/data-store.json` retained stale `rendered: undefined` entries from a prior failed build. Next build used cached empty content instead of regenerating.

**Fix (DONE in spec):** `package.json` build script updated to `rm -f node_modules/.astro/data-store.json && astro build && ...`. All sites should apply this change.

---

### B15 — SVG logo placeholder tokens shipped in production [FIXED 2026-06-04]

**Scope:** Sites 14 and 15 (`logo-header.svg` with `{{BRAND_NAME}}`)
**Status:** **Fixed — Day 5, commit 3befc30.**
**v1.6 section:** §15.8

**Root cause:** `initialise-site.mjs` generates SVG files with `{{BRAND_NAME}}` as a template token. Token substitution step either failed silently or was not run before deploy.

**Fix applied:** `{{BRAND_NAME}}` added to `TOKENS` substitution dict in `initialise-site.mjs`. SVGs now have brand name substituted at scaffold time during Phase 1 token replacement. Point 16 SVG placeholder check (`grep "{{" public/images/brand/*.svg`) already existed as a hard gate — it will catch any remaining `{{` tokens before deploy.

---

### B16 — DTC products backfilled with wrong-ASIN Amazon results [REQUIRES SOURCING FIX]

**Scope:** Site 15 (10 products: Patagonia, SIMMS, Orvis sourced to unrelated Amazon products)
**Status:** Fixed per-article on Site 15. Tool not fixed.
**v1.6 section:** §15.9

**Root cause:** `source-products-rainforest.py` falls back to generic Amazon search when brand has no Amazon presence. Result: `Patagonia Stealth Waders` → `FURTALK Sun Hat` (highest-relevance Amazon result for wader search term).

**Fix:** DTC brand list per niche (`config/dtc-brands/<niche>.yaml`). When known-DTC brand is detected: either return `NOT_ON_AMAZON` explicitly, or look up a cross-sell Amazon product (waterproof jacket, wading sock) and flag as DTC-adjacent.

---

### B17 — Category-type mismatch in catalog (spin lure in fly-fishing) [REQUIRES VALIDATOR]

**Scope:** Site 15 (multiple articles)
**Status:** Fixed per-article on Site 15. Validator not built.
**v1.6 section:** §15.10, V22

**Root cause:** Products pass hub and brand checks but fail category-type coherence. Spin lure has correct hub (fishing) but wrong tackle type for a fly-fishing article.

**Fix:** `category_type:` field in products.yaml; `validate-catalog-category-coherence.mjs` (V22) as Point 12.5b gate.

---

### B18 — Skip-list articles deployed as live pages [REQUIRES PIPELINE FIX]

**Scope:** Site 15 (simms-g3-vs-g4.md)
**Status:** Fixed per-article. `publish-staging.mjs` and `verify-deploy.mjs` not updated.
**v1.6 section:** §15.13

**Root cause:** Producer's skip-list (`data/skip-list.yaml`) was respected during generation but `publish-staging.mjs` moved skip-listed articles to content/articles/ anyway.

**Fix:** `publish-staging.mjs` reads skip-list and excludes flagged articles. `verify-deploy.mjs` confirms skip-list URLs return 404/301 post-deploy.

---

### B19 — Product slug typo produces broken affiliate link without build error [REQUIRES VALIDATOR]

**Scope:** Site 15 (1 confirmed article)
**Status:** Fixed per-article. Validator not built.
**v1.6 section:** §15.6, V19

**Root cause:** Astro gracefully degrades on missing product slug — build succeeds, affiliate link renders as href="#" or empty. No existing validator scans for unresolved product slugs in staged markdown.

**Fix:** V19 `validate-product-slug-resolution.mjs` (Point 13.9 gate).

---

### B20 — Producer brief-reasoning in article body [REQUIRES PROMPT FIX + VALIDATOR]

**Scope:** Site 14 (marantz-vs-anthem-vs-denon; confirmed 10+ articles)
**Status:** Fixed by regeneration on Site 14. Root cause not fixed; validator not built.
**v1.6 section:** §15.2, V20

**Root cause:** When brief contains a keyword-product mismatch, LLM writes its internal reasoning into the article body before generating content.

**Fix:** Producer prompt update (never write meta-commentary). `check_output_shape()` post-generation check. V20 `validate-meta-leakage.mjs` (Point 13.7 gate).

---

### B21 — Persona lock after content generation (the Site 13 root cause) [FIXED BY v1.6 SPEC]

**Scope:** Site 13 (300 articles required retroactive editorial fix)
**Status:** Process gap fixed by v1.6 spec. Tool enforcement (`lock-persona.mjs`) not yet built.
**v1.6 section:** §15.1

**Root cause:** Marcus Tran's persona was finalized after 300 articles were generated. Articles fabricated gear (wrong model), partner name (Sam vs Hannah), and other details that weren't in the persona at generation time.

**Fix (in spec):** Producer refuses to run without `persona_locked: true`. `tools/lock-persona.mjs` runs at Point 5 close. Hash comparison prevents drift between lock and run.

---

### B22 — Card voice not inheriting persona first-person register [REQUIRES PRODUCER FIX]

**Scope:** Site 15 (Greg persona buyer guides)
**Status:** Not fixed. Validator not built.
**v1.6 section:** §15.3, V21

**Root cause:** Producer's narrative code path inherits persona voice; card generation code path uses a separate template that doesn't inject persona voice properties.

**Fix:** Producer injects `first_person_pronouns` from persona YAML into card generation prompt. V21 `validate-card-voice.mjs` (Point 13.8 gate).

---

### B23 — Renewed/refurbished products as primary picks without disclosure [EDITORIAL POLICY]

**Scope:** Multiple articles across Sites 13–15
**Status:** Manual disclosure added where found. No systematic detection.
**v1.6 section:** §15.18 backlog (deferred)

**Root cause:** Rainforest sourcing includes Amazon Renewed listings. When assigned as best_overall, article needs explicit disclosure but producer doesn't auto-add it.

**Fix:** Add `condition: renewed` field to products.yaml. Build-validator WARN when `best_overall` product has `condition: renewed`. Producer prompt: auto-include disclosure when field set.

---

### B24 — portfolio.yaml consistently stale [REQUIRES TOOL + DISCIPLINE FIX]

**Scope:** Portfolio-wide
**Status:** Not fixed. Tool not built.
**v1.6 section:** §15.16

**Root cause:** portfolio.yaml is manually updated and consistently lags reality. Site 13 showed `status: pre_launch`, `ga4_id: null` when confirmed live. No automated writeback at any phase transition.

**Fix:** `tools/portfolio-update.mjs`. Called at Points 16, 17, 18, 19, 21. Each call writes specific fields atomically.

---

---

### B25 — Pre-existing catalog rot in Sites 13/14/15 — V19 surfaced post-build

**Scope:** Sites 13 (UDS), 14 (HPC), 15 (RMF)
**Status:** Not fixed. Out of v1.6 build scope.
**v1.6 section:** V19 (§13.9)

**Root cause:** V19 (`validate-product-slug-resolution.mjs`), built 2026-05-31, surfaced product reference integrity failures across three sites that had never been validated:
- **RMF (Site 15):** 39 articles with malformed ASINs (9-digit truncated ISBNs like `811713571`, `NOT_FOUND` placeholders); 51 warnings for DTC products with `asin: NOT_ON_AMAZON` and no `buy_url`
- **HPC (Site 14):** 10 articles referencing product slugs absent from products.yaml
- **UDS (Site 13):** 61 articles referencing product slugs absent from products.yaml

**Severity:** Hard fail per V19 (broken affiliate links). V19 now gates new content; existing articles carry these issues but are not broken at the article level (Astro gracefully degrades on missing product references in the rendered HTML).

**Fix:** Per-site catalog audit required for each affected site. For each failure:
- Broken slug → find or add the product entry, or remove the reference
- Malformed ASIN → resolve correct ASIN via `validate-asins.mjs`
- NOT_ON_AMAZON + no buy_url → add `buy_url` for DTC product, or set `asin` to a valid ASIN if available on Amazon

**Remediation timing:** Not in v1.6 build scope. Resolve as part of retrospective UAT on Sites 1–12, or whenever each site next receives meaningful content attention. Do not block Phase 3–6 build work on this remediation.

---

### B26 — Portfolio-wide persona-spec violations surfaced by V18

**Scope:** Sites 13 (UDS), 14 (HPC), 15 (RMF)
**Status:** Not remediated. V18 now gates new content; existing violations documented here.
**v1.6 section:** V18 (§12.5b)
**Severity:** SEV-1 — fabrication claims (wrong gear, wrong partner, wrong tenure) are FTC-risk, same class as the Site 13 editorial fix work done 2026-05-31.

**Root cause:** V18 (`validate-persona-spec-compliance.mjs`), built 2026-05-31, ran retroactively across the three cohort sites. Violations are TRUE POSITIVES, not false positives:
- **UDS (Site 13):** 137/301 articles (45.5%) — persona locked AFTER content generation; fabricated gear chain (Topping E50/L50 stack, wrong IEM daily driver, wrong Sundara revision) throughout
- **HPC (Site 14):** 105/297 articles (35.4%) — editorial methodology violations and wrong model numbers
- **RMF (Site 15):** 162/281 articles (57.7%) — explicit forbidden phrases ("I'm an expert in saltwater fly fishing") throughout
- **Total:** 404 articles across three sites

**Cost note:** V18 costs ~$0.0011/article. A full portfolio scan of all 15 sites costs ~$5. Running V18 retroactively across the backlog is cheap — it should be run as part of each site's scheduled remediation sprint.

**Fix:** Per-site editorial remediation pass. Each failing article requires re-generation or manual editing to replace fabricated first-person claims with persona-compliant language or honest hedging. Do not attempt bulk auto-remediation — each violation requires editorial judgment.

**Remediation timing:** Scheduled remediation per site, sequenced by revenue priority. UDS (Site 13) is highest priority given the volume of fabrication. Do not block Phase 3–6 build work on this remediation.

---

### B28 — Validator orchestration JSON protocol mismatch — all v1.6 sites launched with no validator gating [PARTIALLY FIXED 2026-06-04]

**Scope:** All v1.6 sites (Sites 13, 14, 15, 16 confirmed; likely earlier sites via same orchestrator)
**Status:** Root cause fixed 2026-06-04 (--json mode added to V18 regex + V20; orchestrator parse-failure hardened). LLM V18 system prompt recalibrated. Sites 13-15 violations documented in B26 and not yet remediated.
**v1.6 section:** V18 (§13.5b), V20 (§13.7)
**Severity:** SEV-1 — every validator call during launch orchestration was silently discarded; no validator gated any launch.

**Root cause:** Launch orchestrator points `p13-5b-persona-spec.mjs` and `p13-7-meta-leakage.mjs` call validators with `--json` flag (`node "${validator}" --site ${slug} --json`), then immediately try to parse stdout as JSON. Neither V18 nor V20 implemented `--json` output mode — both wrote ANSI-colored terminal text to stdout. `JSON.parse()` threw on every call. The catch block silently set `parsed = {}`, `failIds = []`, `failCount = 0`. The orchestrator recorded all validation points as complete with zero failures. All launch decisions.log files show green validation checkmarks that were never meaningful.

**This explains the full Site 16 failure mode:** Validators were invoked (state.yaml confirms points 13.5, 13.5b, 13.7 all complete). They exited 0 (narrow patterns, no violations detected). Their output was unparseable JSON. The orchestrator saw `failCount = 0` in every case and proceeded. The v1.6 validator architecture was correct; the output contract between validator and orchestrator was never implemented.

**Fix (applied 2026-06-04):**
1. Added `--json` output mode to `validate-persona-claims.mjs` (V18 regex) and `validate-meta-leakage.mjs` (V20) — outputs `{"fail_count": N, "failures": [...]}` to stdout when `--json` flag present, suppresses terminal output
2. Added `--json` output mode to `validate-persona-spec-compliance.mjs` (V18 LLM)
3. Hardened orchestrator parse-failure handling in `p13-5b` and `p13-7` — parse failure now throws rather than silently passing
4. Updated V18 LLM system prompt to treat unhedged ownership of non-owned products as a violation (not just explicit contradictions)
5. Updated V18 regex to include owned_gear bypass and hedging bypass (v1.1 — done Day 3)

**Remaining gap:** Sites 13-16 are live with content that was never validator-gated. Remediation for Sites 13-15 is tracked in B26. Site 16 remediation is in progress (Day 4 brief).

---

### B27 — DTC sourcing policy may have been inactive during Sites 11–15 builds [OPEN QUESTION]

**Scope:** Sites 11–15 catalog sourcing history
**Status:** Open question — do not investigate now; log for Phase 6 / cohort retrospective.
**v1.6 section:** §15.9, Phase 4.1 (source-products-rainforest.py)
**Severity:** Low (sourcing correctness, not FTC risk) — but worth resolving before claiming v1.6 sourcing is retroactively clean

**Background:** During Phase 4.1 (2026-05-31), brand-match, category-match, and DTC fallback policies were found already implemented in `source-products-rainforest.py`. The Phase 4.1 spec had described these as new additions. Yet Site 15's catalog had 10 wrong-ASIN DTC products (Scott Centric, Orvis Helios, Patagonia Stealth) that the policies should have caught.

**Open question:** If the policies existed, why did Site 15 still produce 10 wrong-ASIN DTC products? Three plausible explanations:
1. The policies existed in code but were not invoked during Site 15's sourcing run (flag mismatch, env gap, code path not triggered)
2. Site 15's catalog was sourced before the policies were added to the file (older version used)
3. The policies were insufficient — false negatives (brand name not in DTC list at sourcing time; DTC list added later)

**Recommended investigation (Phase 6 or retrospective):** Run V22 and a sourcing audit against Sites 11–15 catalog to identify products whose sourcing metadata suggests the policies were bypassed. Check git history on `source-products-rainforest.py` for when DTC fallback was added. If Sites 11–14 ran on a pre-policy version, their catalogs may have the same class of wrong-ASIN problems as Site 15.

---

### B29 — Producer emits Python dict literals for image references; conversion is post-processor only [OPEN]

**Scope:** All sites using the V2 producer (Sites 16+)
**Status:** Not fixed — known behavior. Document only; do not fix today.
**v1.6 section:** v1.7+ scope
**Severity:** Low (affects unprocessed staging files only; fix-image-markdown.py converts before publish)

**Background:** The V2 producer (`ridgelinebushcraft-producer-v2.py`) emits inline images as Python dict literals rather than markdown image syntax. Example output: `![alt text]({'alt': 'camping tripod', 'path': 'articles/cooking-14.webp'})`. Day 1 fixed 812 instances across 203 existing articles via `fix-image-markdown.py`.

**Root cause:** The producer prompt or output formatter generates the dict syntax; the fix script is a post-processing step, not an in-producer correction.

**Required action (Phase 4 and beyond):** Any article regenerated via the V2 producer MUST pass through `fix-image-markdown.py` before V18/V20 validation and deployment. Pipeline sequence: producer → fix-image-markdown.py → V18 → V20 → publish.

**v1.7+ fix:** Move dict-to-markdown conversion into the producer output filter or prompt so the fix script is no longer necessary. Do not implement today — scope for the v1.7 prompt/producer refactor sprint.

---

### B30 — V18 REVIEW tier needs calibration audit [OPEN]

**Scope:** V18 regex validator (`validate-persona-claims.mjs`), all v1.6 sites
**Status:** Open — not blocking; defer to v1.7 calibration sprint.
**v1.6 section:** V18 §13.5b
**Severity:** Low (REVIEW items are informational, not auto-failed)

**Background:** Site 16 Phase 3 corpus re-run shows 84 REVIEW-tier items after fixing all 45 HARD violations. The REVIEW tier was designed for patterns V18 v1.1 can detect but cannot confidently classify as HARD failures. It's unclear whether these 84 items are:
1. Patterns that V18 is too conservative about (should be HARD)
2. Patterns that are genuinely borderline and need LLM V18 to adjudicate
3. False positives that should be suppressed with additional exclusion rules

**Recommended investigation (v1.7 calibration sprint):** Sample 20 REVIEW items from Site 16. Classify each as: true positive (should be HARD), true positive (acceptable at REVIEW), or false positive. Use the distribution to adjust REVIEW → HARD promotion criteria or add suppression rules. Goal: REVIEW count under 40 and no false positives promoted to HARD.

---

### B31 — Point 13 producer SIGKILL via execSync 12h timeout [FIXED 2026-06-04]

**Scope:** All sites using `launch-site.mjs` orchestrator (Site 16 was first to hit it)
**Status:** **Fixed — Day 5, commit 6a61158.**

**Root cause:** `p13-producer.mjs` used Node `execSync` with a 12-hour timeout. Producer runs for 300-article sites take 7–15 hours. Two of three Site 16 producer runs ended in SIGKILL corruption mid-generation. Third run was a manual `nohup` outside the orchestrator.

**Fix applied:** Replaced `execSync` with `child_process.spawn`. Producer runs as a long-lived child process; stdout/stderr piped to `/tmp/<slug>-producer.log`. Orchestrator awaits `child.on('exit')` with no timeout. Non-zero exit code surfaces as `{ status: fail }`.

---

### B32 — GSC verification halt missing CF Pages env var step [FIXED 2026-06-04]

**Scope:** All sites using `launch-site.mjs` orchestrator
**Status:** **Fixed — Day 5, commit 6a61158.**

**Root cause:** Point 19 halt message instructed Keith to add a DNS TXT record only. Astro build also requires `GOOGLE_SITE_VERIFICATION` as a CF Pages environment variable. Site 16's build failed twice because DNS was set but the env var was not.

**Fix applied:** Point 19 halt message now includes 11 numbered steps with explicit CF Pages env var step (step 6). `wireGsc` function now calls `cloudflare-pages-config.mjs set-env` to set `GOOGLE_SITE_VERIFICATION` on the CF Pages project after adding the DNS record. Resume flag changed to `--gsc-verification <hash>` (hash only; normalisation to full `google-site-verification=<hash>` string happens in code).

---

### B33 — Scaffold missing `logo_paths` block in `site.config.yaml` [FIXED 2026-06-04]

**Scope:** All sites scaffolded before Day 5 (Sites 11–16)
**Status:** **Fixed — Day 5, commit 3befc30.**

**Root cause:** `buildSiteConfig()` in `initialise-site.mjs` emitted `visual:` block without `logo_paths` sub-block. `Header.astro` dereferences `cfg.visual.logo_paths.header_svg` without a null guard — every new site crashed on first build.

**Fix applied:** `buildSiteConfig()` now emits `visual.logo_paths` with all 6 required fields: `header_svg`, `header_png`, `favicon`, `footer_svg`, `social_square`, `open_graph_default`. Placeholder values point to standard scaffold asset locations.

---

### B34 — Off-niche keywords pass through `xlsx-to-pipeline.mjs` unchecked [FIXED 2026-06-04]

**Scope:** All sites using `xlsx-to-pipeline.mjs` for pipeline generation
**Status:** **Fixed — Day 5, commit 3befc30.**

**Root cause:** `xlsx-to-pipeline.mjs` wrote all keywords to `pipeline.json` without filtering. Site 16 XLSX contained 13 off-niche keywords (TV scheduling queries, campus maps, entertainment/gaming/academic queries). Producer generated articles for these with fabricated products — costing ~$4-5 in API spend and requiring V18/V20 validation failures to surface them.

**Fix applied:** `isOffNiche()` filter function added to `xlsx-to-pipeline.mjs`. Rule-based patterns catch TV scheduling, campus navigation, named entertainment references, academic quiz questions, and gaming queries. Tested: 13/13 known Site 16 off-niche keywords rejected, 0 false positives on 21 legitimate bushcraft keywords. Rejected keywords logged to `<output>-rejected.log` for auditability.

---

### B35 — CF Pages project not auto-created before deploy at Point 16 [FIXED 2026-06-04]

**Scope:** All new sites using `launch-site.mjs` orchestrator
**Status:** **Fixed — Day 5, commit 3befc30.**

**Root cause:** `p16-push-live.mjs` assumed the CF Pages project already existed. No prior point created it. Site 16's first deploy failed; Claude Code manually ran `wrangler pages project create ridgelinebushcraft`.

**Fix applied:** Step 0 added to `p16-push-live.mjs`: runs `wrangler pages project list`, checks for the site slug, and creates the project with `wrangler pages project create <slug> --production-branch main` if absent.

---

### B36 — CF API token lacks `zone:create` permission [PENDING KEITH]

**Scope:** Platform-wide — affects all new site domain attachments
**Status:** Pending Keith action.

**Root cause:** Current token (`cfut_HutEvH...`) confirmed missing `com.cloudflare.api.account.zone.create` permission (verified 2026-06-04 via CF API). Site 16 domain attachment required a registrar-side CNAME workaround. Every new site will hit this until the token is replaced.

**Keith action required:**
1. CF Dashboard → My Profile → API Tokens → Create Token → Custom Token
2. Permissions:
   - Account → Cloudflare Pages → Edit
   - Account → Account Settings → Read
   - Zone (All zones) → Zone → Edit
   - Zone (All zones) → DNS → Edit
   - Zone (All zones) → SSL and Certificates → Edit
3. Copy new token value
4. `ssh root@46.225.29.35 "sed -i 's/^CLOUDFLARE_API_TOKEN=.*/CLOUDFLARE_API_TOKEN=<new-token>/' /root/affiliate-platform/.env"`
5. Update `/Users/keithlacy/affiliate-platform/.env.local` locally

**Acceptance test:** `curl -s -X POST 'https://api.cloudflare.com/client/v4/zones' -H 'Authorization: Bearer <new-token>' -H 'Content-Type: application/json' -d '{"name":"test-zone-check-only.invalid","account":{"id":"fedb496b1addc0743cb2a84fa5a7ba67"}}' | python3 -c "import json,sys; d=json.load(sys.stdin); print([e['message'] for e in d.get('errors',[])])"` — should return a domain validation error, NOT a permissions error.

---

## Site 16 incident log — Bug 14/15/16 (Day 2–4 post-launch remediation)

### Bug 14 — CLOUDFLARE_API_TOKEN not persisted on VM [FIXED 2026-06-04]

**Found:** 2026-06-04, Site 16 SEV-1 article pull.
**Status:** Workaround applied — token written to `/root/affiliate-platform/.env`. See B36 for permission upgrade (pending Keith).
**Shape:** Token was only available locally (Mac `.env.local`). VM had no token; wrangler deploys from server failed.
**Fix applied:** Token copied to VM `.env` on 2026-06-04.
**Permanent fix (B36):** Create new token with zone:create permission, update both Mac and VM.

---

### Bug 15 — V20 pattern list incomplete [FIXED 2026-06-04]

**Found:** 2026-06-04, Site 16 V20 audit.
**Status:** **Fixed** — V20 expanded to 17 patterns (2026-06-04, Day 2).
**Shape:** Original 8 verb patterns missed "the brief covers", "appears in this brief", "product-slug placed it here". 6 leakage articles in Site 16 corpus (2.9%).
**Fix applied:** V20 expanded to 17 patterns: added covers/names/describes/notes/mentions/lists/identifies/defines/includes; "this brief [verb]" form; "appears in this brief"; "in this brief"; "product-slug" data-layer term. Corpus after fix: 0 FAILs.

---

### Bug 16 — V18 persona-claim validator: three compounding failure modes [FIXED 2026-06-04]

**Found:** 2026-06-04, Site 16 V18 audit (Day 3 post-launch).
**Status:** **Fixed** — V18 expanded to v1.1 (2026-06-04, Day 3); 45 HARD violations fixed in corpus (Day 4).
**Shape A:** Missing patterns — "I've carried" (Wesley's primary ownership signal) not in original 10 patterns.
**Shape B:** LLM V18 design mismatch — "absence != contradiction" instruction blocked it from flagging non-owned products. Now deferred; regex V18 handles owned-gear claims.
**Shape C:** Orchestration gap — neither V18 nor V22 was wired into Site 16 launch ritual; both ran only when manually invoked.
**Fix applied:** V18 expanded to include `I've carried`, `I've worn`; owned_gear bypass and hedging bypass added; REVIEW tier for carry/pack patterns. `owned_gear:` structured field added to Wesley Tate persona YAML. 45 HARD violations fixed in 36 articles. Full corpus at 0 HARD post-fix.

---

---

### B37 — Near-homograph product matching (Barebells ≈ barbells) [OPEN]

**Scope:** SM (Strengthmill) — 12 wrong-niche products; pattern likely affects any gym/fitness site
**Status:** SM catalog manually cleaned 2026-06-05. Tool not fixed.
**Severity:** MODERATE — wrong-niche products produce V18 violations, affiliate dead-ends, and editorial confusion

**Root cause:** Rainforest product matching for the "barbells" keyword returned Barebells-brand protein bars. "Barebells" is visually and phonetically similar to "barbells" — close enough to pass through name-similarity scoring without triggering `isOffNiche()`. Twelve Barebells protein bar SKUs were ingested into SM's fitness-equipment catalog. Four articles were generated referencing them (three self-aware wrong-niche, one partially confused). `isOffNiche()` catches obvious off-niche keywords (TV schedules, campus maps) but does NOT catch near-homograph product type mismatches.

**Products removed from SM 2026-06-05:**
`barebells-protein-bars-cookies-cream`, `barebells-protein-bars-caramel-cashew`, `barebells-protein-bars-caramel-cashew-2`, `barebells-caramel-cashew-and-cookies`, `barebells-soft-protein-bars-salted`, `gatorade-whey-protein-recover-bars`, `barebells-protein-bars-peoples-choice`, `mezcla-puff-crispy-plant-based`, `one-protein-bars-lemon-cake`, `power-crunch-protein-energy-bar`, `lodge-double-play-reversible-cast` (cookware), `jump-rope-album-version` (music).

**Articles pulled from SM 2026-06-05:** `barbell-protein-bars.md`, `jump-rope-songs.md`, `cast-iron-plate.md`, `barbell-bars.md`. Redirects added in `public/_redirects`.

**Recommended fix:**
1. Add hub-coherence check at product-matching step in `source-products-rainforest.py` — if matched product's primary category (food/nutrition) doesn't match the hub's category domain (gym equipment), flag or reject rather than ingesting.
2. Add product-type metadata field (`product_type:`) to products.yaml; validate against expected types for the hub at catalog ingestion.
3. Consider expanding `isOffNiche()` to cover product-type mismatches, not just keyword patterns.

---

### B38 — Producer generates despite self-flagging brief incoherence [OPEN]

**Scope:** SM (Strengthmill) — 2 confirmed articles; pattern likely latent across all sites
**Status:** Affected articles pulled 2026-06-05. Producer behavior not fixed.
**Severity:** HIGH — producer recognizes the mismatch but generates anyway, creating V18/V20 violations and wrong-niche content at full API cost

**Root cause:** Two SM articles contained producer self-commentary acknowledging a fundamental brief mismatch:
- `jump-rope-songs.md` body: *"The brief asks for a buyer guide on 'jump rope songs', and the five products listed are music records."* — producer identified the incoherence but generated a children's music article in a gym site anyway.
- `barbell-bars.md` body: *"Zero products in this brief belong to the Barbells hub."* — producer identified the hub mismatch but generated anyway.

These are B4-class brief-leakage violations (already gated by V20) but they represent a deeper failure: the producer should treat self-flagged incoherence as a SHAPE FAIL rather than a content warning.

**Recommended fix:**
1. Update producer `check_output_shape()` to detect when the generated body begins with or contains a metacommentary paragraph starting with "The brief asks for...", "Zero products in this brief...", "The keyword in this brief is..." — treat as SHAPE FAIL, not output content.
2. Add pre-generation coherence check: if products list has zero items matching the hub keyword, halt generation with a logged warning rather than producing an article.
3. V20 already catches these if they survive to deployment — this fix prevents the API cost of generating wrong-niche articles in the first place.

---

### B39 — ProsConsBox null-safety: component crashes on undefined pros/cons [FIXED 2026-06-05]

**Scope:** SM (Strengthmill) — confirmed on `/barbell-vs-dumbbell/`; any site using ComparisonLayout with products that have no `article_specific_pros`
**Status:** **Fixed 2026-06-05** — `= []` defaults added to `ProsConsBox.astro` destructuring. Cross-repo change in `affiliate-platform`.
**Severity:** BUILD BLOCKER — TypeError crashes Astro build, blocking deploy

**Root cause:** `ProsConsBox.astro` destructured props without defaults:
```js
const { pros, cons, productName } = Astro.props
```
`ComparisonLayout` calls `<ProsConsBox pros={productA.pros}>` where `productA.pros` resolves to `undefined` when the product has no `article_specific_pros` and no `default_pros`. `undefined.map(p => <li>{p}</li>)` throws TypeError at build time.

**Fix applied:**
```js
const { pros = [], cons = [], productName } = Astro.props
```
Applied to `affiliate-platform/src/components/ProsConsBox.astro`. Cross-repo note: this component lives in `affiliate-platform`, not in the site repo. Any site using ComparisonLayout inherits the fix after the next `affiliate-platform` sync.

---

### B40 — V20 calibration gaps: "in the brief" variant and photography false positive [OPEN]

**Scope:** V20 validator (`validate-meta-leakage.mjs`) — two distinct calibration issues surfaced 2026-06-05
**Status:** Open — both identified during Day 8 SM/CC remediation. V20 at 17 patterns; gaps logged here for v1.7 calibration sprint.
**Severity:** LOW — V20 remains effective; these are edge cases, not systematic failures

**Gap 1 — "in the brief" variant not in pattern list:**
SM `half-rack-gym.md` contained: *"its appearance here indicates a product data error in the brief"* — "in the brief" (without "this") is NOT in V20's 17-pattern list; only "in this brief" is listed. V20 returned 0 FAIL for this article even though the phrase clearly leaked producer reasoning. Verified post-patch: the two other leaks were caught and fixed; this third instance was missed by V20 and survived to deploy.

**Recommended fix:** Add `in the brief` (without "this") as an 18th pattern. Confirm no false positives on poetry/music/photography niches where "brief" appears in legitimate professional context.

**Gap 2 — V20 over-fires on legitimate professional "brief" usage in photography/design niches:**
CC `film-camera-and-lens.md` used *"when the brief says 'cover everything at a professional standard'"* in the professional photography sense (client shoot brief). V20 correctly fires on this pattern, but the usage is domain-legitimate. Patch was applied (replaced with "when the job requires...") — no regression. But if a photography/film/design site is launched and articles routinely use "brief" in the professional-assignment sense, V20 false-positive rate could be meaningfully high.

**Recommended fix (v1.7 scope):** Consider niche-aware pattern exclusion for photography, film, design, and creative niches. Alternatively, tighten verb gating: "brief says/includes/lists" are strong signals of LLM reasoning leak; "the brief [job assignment]" usage tends to use nouns like "shoot brief", "design brief", "creative brief" — could suppress based on adjective-noun context.

---

## Full summary table — B1–B40


| # | Issue | Scope | Status | v1.6 section |
|---|-------|-------|--------|--------------|
| B1 | Cookie consent declined state wiped | Platform-wide | **Fixed** | Template fix |
| B2 | Em-dash → ` , ` | Producer | Site 14 fixed; prompt fix pending | §15.12 |
| B3 | Unfilled price tokens in links | Producer | Site 14 fixed; prompt fix pending | §13.0 prereq |
| B4 | Brief-reasoning in article body | Producer | Site 14 fixed; validator pending | §15.2, V20 |
| B5 | pros/cons null YAML mismatch | Schema | Site 14 fixed; schema fix pending | §13.0 prereq |
| B6 | Wrong-hub products in catalog | Catalog | Site 14 fixed per-article; V22 pending | V22, §15.10 |
| B7 | Renewed products as primary picks | Editorial | Site 14 disclosed; field pending | §15.18 |
| B8 | SVG currentColor invisible as img | Site spin-up | Site 14 fixed; checklist pending | §15.18 |
| B9 | Pipeline status writeback | Tool | Not fixed | §15.11 |
| B10 | Persona byline path bug | Template | Not propagated | §15.18 |
| B11 | Seller-prefix in product names | Sourcing | Site 15 fixed; tool not fixed | §15.9 |
| B12 | Doubled-apostrophe artifacts | Producer | Not fixed | §15.18 |
| B13 | Boilerplate identical pros/cons | Prompt | Not fixed | §15.18 |
| B14 | Astro data-store empty articles | Build | **Fixed in spec (§15.7)** | §15.7 |
| B15 | SVG placeholder shipped to prod | Scaffold | **Fixed 2026-06-04** — `{{BRAND_NAME}}` in TOKENS dict (3befc30) | §15.8 |
| B16 | DTC backfill with wrong ASIN | Sourcing | Site 15 fixed; tool not fixed | §15.9 |
| B17 | Category-type mismatch | Catalog | Site 15 fixed; V22 pending | §15.10, V22 |
| B18 | Skip-list articles deployed live | Pipeline | Site 15 fixed; tools not updated | §15.13 |
| B19 | Slug typo → broken link (no error) | Pipeline | Site 15 fixed; V19 pending | §15.6, V19 |
| B20 | Brief-reasoning in body | Producer | Site 14 fixed; V20 pending | §15.2, V20 |
| B21 | Persona lock after content gen | Process | **Fixed by v1.6 spec**; tool pending | §15.1 |
| B22 | Card voice not first-person | Producer | Not fixed; V21 pending | §15.3, V21 |
| B23 | Renewed picks without disclosure | Editorial | Disclosed ad hoc; no detection | §15.18 |
| B24 | portfolio.yaml chronically stale | Tool | Not fixed | §15.16 |
| B25 | Pre-existing catalog rot (Sites 13/14/15) | Catalog | Not fixed; V19 now gates new content | V19, §13.9 |
| B26 | Portfolio-wide persona-spec violations (Sites 13/14/15) | Editorial | Not remediated; V18 gates new content | V18, §12.5b |
| B27 | DTC sourcing policy activation unknown for Sites 11–15 | Catalog | Open question; investigate in Phase 6 | §15.9, 4.1 |
| B28 | Validator orchestration JSON protocol mismatch — all v1.6 sites launched with no gating | Orchestrator | **Partially fixed 2026-06-04** — --json mode added to V18+V20; sites 13-15 violations unmediated | V18 §13.5b, V20 §13.7 |
| B29 | Producer emits Python dict literals for image refs; relies on post-processing fix | Producer | Not fixed — fix-image-markdown.py is post-processor, not in producer | v1.7+ scope |
| B30 | V18 REVIEW tier needs calibration audit — 84 items on Site 16, classification unclear | V18 validator | Open — defer to v1.7 calibration sprint | V18 §13.5b |
| B31 | Point 13 producer SIGKILL via execSync 12h timeout | Orchestrator | **Fixed 2026-06-04** — spawn+poll, no timeout (6a61158) | §13 |
| B32 | GSC halt missing CF Pages env var step | Orchestrator | **Fixed 2026-06-04** — Point 19 halt updated, wireGsc sets env var (6a61158) | §19 |
| B33 | Scaffold missing `logo_paths` block in `site.config.yaml` | Scaffold | **Fixed 2026-06-04** — buildSiteConfig emits all 6 logo_paths fields (3befc30) | §15.8 |
| B34 | Off-niche keywords pass through xlsx-to-pipeline.mjs | Pipeline | **Fixed 2026-06-04** — isOffNiche() filter, 13/13 RBL cases caught (3befc30) | §3 |
| B35 | CF Pages project not created before Point 16 deploy | Orchestrator | **Fixed 2026-06-04** — auto-create at Point 16 start (3befc30) | §16 |
| B36 | CF API token lacks zone:create permission | Credentials | **Pending Keith** — token needs replacement; see B36 entry for steps | §16 |
| B37 | Near-homograph product matching (Barebells ≈ barbells) | Catalog sourcing | SM catalog manually cleaned 2026-06-05; tool not fixed | §15.9, V22 |
| B38 | Producer generates despite self-flagging brief incoherence | Producer | Articles pulled 2026-06-05; producer behavior not fixed | §15.2, B4 |
| B39 | ProsConsBox crash on undefined pros/cons | Component | **Fixed 2026-06-05** — `= []` defaults added to ProsConsBox.astro (cross-repo) | §13 |
| B40 | V20 calibration: "in the brief" variant + photography false positive | V20 validator | Open — defer to v1.7 calibration sprint | V20 §13.7 |
