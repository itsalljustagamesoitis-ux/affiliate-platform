# Site 16 Launch Postmortem — ridgelinebushcraft.com

**Launch window:** 2026-06-01T12:33Z → 2026-06-03T21:42Z  
**Total wall time:** ~57 hours  
**Status at close:** Live on production, 205/306 articles published  
**Postmortem date:** 2026-06-04  

---

## 1. Timeline Reconstruction

| Point | Status | Wall time | Notes |
|-------|--------|-----------|-------|
| 7 — Site shell verify | pass-with-friction | ~10 min | Two failures before pass. First: unparseable output from verify-site-shell. Second: 5 blockers in site shell (checks 12, 23, 30, 32, 33). Third invocation passed. Root cause not fully diagnosed — likely orchestrator calling the tool before the prior step had fully committed to disk. |
| 8 — Furniture + pipeline | pass-with-friction | ~12 min | Failed once with Node path error ("Usage: node tools/initialise-site") on second invocation. Passed on third. |
| 9 — Amazon tracking ID | required-intervention | ~7 hours | Bucket C halt. Orchestrator initially proposed wrong ID (`ridgelinebushcraf-20` — truncated). Keith corrected to `ridgelinebush-20`. CF set-env production failed on first attempt (portfolio.yaml hadn't been updated yet). Required manual `portfolio-update.mjs` run to register the CF project before CF env var could be set. |
| 10 — Product sourcing (Rainforest) | required-intervention | ~28 min | Failed 4 times before passing. Root cause: Python path issue (`/Users/keithlacy/Library/Python/3.9/...` not in execSync PATH). Required manual shell PATH fix. |
| 10.5 — Pros/cons generation | **failed-then-recovered** | ~3.5 hours | **This step did not exist in the v1.6 orchestrator.** Added as a new point during the launch after diagnosing F09 failures downstream. Haiku generation of ~1,180 products hit the original timeout (45 min). Timeout increased to 3h and step re-run. Cost: ~$0.90 estimated. |
| 11 — Pexels images | pass | ~1 min | Clean. |
| 12 — Assign article images | pass | <1 min | Clean. |
| 12.5 — Brand match validator | pass-with-friction | ~1 min | Failed once with unparseable output. Passed on retry. |
| 13 — Producer run | **failed-then-recovered** | ~26 hours across 3 attempts | See §5. Fundamentally broken via Node execSync for this article count. Required running the producer directly outside the orchestrator via nohup. |
| 13.5–13.9 — Post-producer validators | pass | <1 min each | All returned fail_count=0. See §3. |
| 14 — Publish to staging | pass-with-friction | ~2 min | Failed once (permission issue on second run after state reset). Passed on retry. |
| 15 — Build test | **failed-then-recovered** | ~40 min | Three failures: (1) `astro: command not found` — execSync PATH issue, fixed by switching to full npm path; (2)+(3) `GOOGLE_SITE_VERIFICATION not set` — build requires the CF env var but the Bucket C halt (GSC) does not explicitly instruct setting it. Keith's "GSC is done" confirmed the TXT record was in DNS but the CF env var was not set. Required manual CF Pages env var update. |
| 15.5 — Preflight | **failed-then-recovered** | ~20 min | Five FAILs on first run (see §3). All fixed manually. |
| 15.6 — Final validator sweep | pass | <1 min | Clean on first attempt. |
| 16 — Deploy + domain attach | required-intervention | ~7 min | Two failures: (1) SVG placeholder tokens (`{{BRAND_NAME}}`) in both logo files — replaced manually; (2) wrangler deploy failed because the CF Pages project did not exist yet. Created project via `wrangler pages project create`. Also: CF API token lacked zone:create permission, preventing zone creation. Domain was attached to the project but DNS resolution required registrar-side CNAME setup. |
| 17 — GA4 | required-intervention | ~22 min | Two halt firings. First halt at 21:06, second at 21:29 (orchestrator did not advance state between halts, causing duplicate). Keith provided `G-ES5D21E1K9`. |
| 18 — BWT | skipped | — | BWT deprecated. Keith confirmed, halt skipped. |
| 19 — GSC | passed-via-keith | — | Keith confirmed GSC verified out-of-band. State advanced manually. |
| 20 — DNS verify | pass | <1 min | Clean once DNS propagated. |
| 20.5 — Final integrity | pass | <1 min | 0 violations. |
| 21 — Close | pass | <1 min | State written as complete. |

---

## 2. Bugs Surfaced During Live Execution

### Bug 1: Point 10.5 (pros/cons generation) missing from orchestrator

**Affected point:** Between 10 and 11 — did not exist  
**Root cause:** The pros/cons generation step was never added to the v1.6 orchestrator spec. The tool `generate-product-pros-cons.py` existed but was not wired.  
**Fix:** Created `tools/launch-site/points/p10-5-generate-pros-cons.mjs` and added it to the POINTS array in `launch-site.mjs`.  
**Dry-run detectable?** No. Dry-run would have skipped the step silently. F09 failures only become visible after a full producer run.  
**Recurrence risk for 17–20:** **High.** The step is now in the orchestrator, but its absence went undetected across all prior sites because prior niches happened to pre-populate pros/cons via Rainforest data. Bushcraft was the first site where most products had empty pros.

---

### Bug 2: Producer run via Node execSync fundamentally broken for 300+ articles

**Affected point:** 13  
**Root cause:** Node `execSync` (and `child_process.spawn` with similar timeout config) sends SIGKILL at timeout. For a 306-article catalog at ~20–45 articles/hour, the 12-hour timeout is insufficient and corrupts articles in mid-generation. The process is not gracefully shut down.  
**Fix:** Ran producer directly via `nohup` on the Hetzner VM outside the orchestrator. The orchestrator's Point 13 was marked complete manually after direct run finished.  
**Dry-run detectable?** No.  
**Recurrence risk for 17–20:** **High.** Any site with 200+ articles will hit this. The current architecture is wrong for long-running producer runs. This is not a configuration fix — it requires replacing execSync with a non-blocking spawn+poll pattern.

---

### Bug 3: `how_to` not a valid content schema type

**Affected point:** 13 (preflight downstream)  
**Root cause:** `xlsx-to-pipeline.mjs` did not alias `how_to` → `informational`. 13 articles in the XLSX had `type: how_to`.  
**Fix:** Added `TYPE_ALIASES` map in `xlsx-to-pipeline.mjs`. Fixed 13 articles in `data/pipeline.json` via sed.  
**Dry-run detectable?** Yes, if Point 13.6 (type validator) were run against a dry-run pipeline.  
**Recurrence risk for 17–20:** **Low.** Alias is now in the tool. Existing sites are not affected.

---

### Bug 4: `site.config.yaml` missing `visual.logo_paths` block

**Affected point:** 15 (build failure)  
**Root cause:** Scaffold template did not emit the `visual.logo_paths` block when `site.config.yaml` was generated. Header.astro accessed `cfg.visual.logo_paths.header_svg` without a null guard.  
**Fix:** Added all 6 required fields to `site.config.yaml` on VM manually.  
**Dry-run detectable?** Yes, a build dry-run (even without content) would crash on the null dereference.  
**Recurrence risk for 17–20:** **Medium.** The scaffold template still doesn't emit this block. Every new site will hit this on first build.

---

### Bug 5: SVG brand assets contained `{{BRAND_NAME}}` placeholder tokens

**Affected point:** 16 (deploy gating check)  
**Root cause:** The scaffold generates SVG logos by substituting `{{BRAND_NAME}}` at initialisation time. The substitution was not applied — the SVGs were written with the raw token still present.  
**Fix:** Replaced tokens manually via `sed` on VM.  
**Dry-run detectable?** Yes — Point 16's token check caught it correctly. The issue is the scaffold's failure to substitute, not the check's failure to catch.  
**Recurrence risk for 17–20:** **Medium.** Root cause (scaffold substitution failure) not yet diagnosed.

---

### Bug 6: CF Pages project not created before first deploy

**Affected point:** 16  
**Root cause:** The orchestrator assumes the CF Pages project exists. No earlier point creates it. For Site 16, the project was not created because the `portfolio.yaml` entry was missing `cloudflare_project`.  
**Fix:** Ran `wrangler pages project create ridgelinebushcraft --production-branch main` manually.  
**Dry-run detectable?** No.  
**Recurrence risk for 17–20:** **Low** if `portfolio.yaml` entries are pre-populated with `cloudflare_project` before launch invocation. Currently this is a manual pre-requisite that isn't validated.

---

### Bug 7: CF API token lacks `zone:create` permission

**Affected point:** 16 (domain attach)  
**Root cause:** The API token used during the launch (`[REDACTED]`) does not have permission to create a new DNS zone. For sites where the domain is not already in CF as a zone, the orchestrator cannot complete domain attachment autonomously.  
**Fix:** Domain attached to the Pages project but full zone creation required registrar-side CNAME (`ridgelinebushcraft.com CNAME ridgelinebushcraft.pages.dev`).  
**Dry-run detectable?** No. Permission check would require a pre-flight API call.  
**Recurrence risk for 17–20:** **High.** All new domains will hit this unless the token is updated with zone:create before launch.

---

### Bug 8: Build fails on `GOOGLE_SITE_VERIFICATION not set`

**Affected point:** 15  
**Root cause:** The build pipeline requires `GOOGLE_SITE_VERIFICATION` to be set as a CF Pages env var. The Bucket C halt for GSC instructs Keith to verify the TXT record in DNS, but does not explicitly instruct setting the CF env var. Keith's response "GSC is done" addressed only DNS. The CF env var was never set.  
**Fix:** Manually set `GOOGLE_SITE_VERIFICATION` in CF Pages env vars via `cloudflare-pages-config.mjs`.  
**Dry-run detectable?** Yes, a local build with the same env var absent would fail identically.  
**Recurrence risk for 17–20:** **High.** The halt message needs to be updated to explicitly include the CF env var step.

---

### Bug 9: Navigation — flat single category with 12 hubs creates unusable dropdown

**Affected point:** Post-launch  
**Root cause:** `navigation.yaml` scaffold always creates one top-level category per niche. For a site with 12 hubs, this produces a dropdown that fills the entire viewport.  
**Fix:** Restructured `navigation.yaml` into 5 logical categories (Cutting Tools, Fire & Shelter, Food & Water, Gear & Kit, Navigate & Learn). Updated post-deployment.  
**Dry-run detectable?** Only by visual inspection — no automated check for hub count per category.  
**Recurrence risk for 17–20:** **High.** Any niche with >6 hubs will have this problem. The scaffold must generate a sensible category grouping rather than a single flat category.

---

### Bug 10: Doubled-brand in products.yaml (line 9181)

**Affected point:** 15.6 (preflight)  
**Root cause:** A product description contained "with with" — likely a copy-paste error in Rainforest data or the XLSX.  
**Fix:** `sed -i '9181s/with with/with/'` on VM.  
**Dry-run detectable?** Yes — the preflight doubled-brand check catches this.  
**Recurrence risk for 17–20:** **Medium.** Rainforest data quality issues will recur. The preflight check catches them correctly; this is working as designed.

---

## 3. Validator Performance

### V13.5–V13.9 (post-producer validators, pre-build)

All returned `fail_count=0` across 306 articles on both runs (decisions.log entries 2026-06-01 and 2026-06-03). No details on individual check breakdown are logged — the decision record only shows aggregate fail_count.

| Validator | Catches | False positive estimate | Cost | Notes |
|-----------|---------|------------------------|------|-------|
| V13.5 (content existence) | 0 | — | — | All 306 articles generated |
| V13.5b (persona spec) | 0 | — | Haiku: unknown | LLM pass cost not tracked in decisions.log |
| V13.6 (slug resolution) | 0 | — | — | |
| V13.7 (meta leakage) | 0 | — | — | |
| V13.8 (card voice) | 0 (severity=soft, fp_density=unknown) | — | — | fp_density field is always `unknown` — not being computed |
| V13.9 (catalog category) | 0 | — | — | |

**Assessment:** The 0-fail results across 306 articles are plausible for a clean first-run site, but the `fp_density=unknown` flag on V13.8 suggests the false-positive tracking logic is not implemented. Accuracy cannot be confirmed. The LLM spend on V13.5b is untracked — no way to audit cost.

### Point 15.5 preflight (post-build validators)

Five FAILs caught before deploy, all legitimate:

| Check | Finding | Resolution |
|-------|---------|------------|
| scaffold-contamination | `dutch oven` in `kitchen_cookware` forbidden vocab section | Added `exempt_sections: [kitchen_cookware]` to site.config.yaml |
| hub-descriptions | 12 hubs missing `description:` fields in navigation.yaml | Added descriptions to all hubs |
| url-slug-dedup | 5 duplicate slug pairs in pipeline | Added 5 × 301 redirects to `_redirects` |
| ymyl-hub-check | "Water Treatment" hub triggered YMYL flag on "treat" | Renamed to "Water Filtration" |
| dollar-figures | Product descriptions contained bare dollar amounts | Removed dollar figures from flagged descriptions |

Zero false positives in this pass. The preflight is working as designed.

### In-producer validator performance (post-build per article)

88 articles went to `staging/failed/` with `validator FAIL`. Most were legitimate catches. **Notable finding:** 17 articles were completely off-niche — the keyword source contained irrelevant queries that had no business in a bushcraft pipeline:

- TV show queries: "when does the new season of Chicago Fire start", "when does the new season of Fire Country start"
- Historical questions: "what started the Great Chicago Fire" (×2 variants)
- Gaming: "is it hard to kill a skilled Scout player" 
- Hotel/travel: "Casa de Campo map", university campus maps
- Unrelated products: produced articles like "When Does the New Season of Chicago Fire Start in 2024" with `type: buyer_guide`, `hub: fire`, products made up by the model

These 17 articles represent a **keyword data quality failure upstream of the orchestrator**. The validator correctly prevented them from publishing. They wasted approximately $4–5 in Sonnet API spend and contaminated the producer log.

Full validator FAIL breakdown (aggregated from 124 `.failures` files):

| Rule | Count | Assessment |
|------|-------|-----------|
| F08: products count > 6 | 30 | Pipeline configuration issue — articles sourced with too many products |
| B05–B20: completely malformed buyer_guides (no FAQ, no buying guide, no Top Picks) | 17 | Off-niche keyword data quality failure |
| F09: missing article_specific_pros/cons | 8 | Slipped through despite Point 10.5 running — likely articles generated in the first producer run before 10.5 was added |
| B15: buying guide word count < 475 | 7 | Prompt/model output quality |
| B02: intro hub link missing | 6 | Hub slug mismatch or article format issue |

---

## 4. Bucket Halt Experience

### Point 9 — Amazon tracking ID (Bucket C)

**Halt quality:** Awkward. The orchestrator's proposed ID (`ridgelinebushcraf-20`) was truncated — 20 characters was not enough. The halt message surfaced the proposed ID but not a warning about the truncation. Keith had to spot the error and correct it.  
**Resume command:** Obvious once corrected.  
**Timing:** 7-hour gap between halt and resume (Keith not at machine).  
**Keith attention required:** ~5 minutes.

### Point 13 (implicit) — Pre-producer review (Bucket B)

**Not invoked.** The v1.6 Bucket B preview halt was skipped — state advanced directly to producer run. There was no moment for Keith to review the persona lock, pipeline count, and persona YAML before 306 articles were committed. This is a spec gap.

### Point 17 — GA4 (Bucket C)

**Halt quality:** Fired twice without advancing state (duplicate halt firings 21:06 and 21:29, 23-minute gap). The second firing was redundant — the orchestrator did not recognise that the halt was already pending.  
**Resume command:** Worked after Keith provided the measurement ID.  
**Keith attention required:** ~5 minutes.

### Point 18 — BWT (Bucket C)

**Not applicable.** BWT deprecated. The halt itself fired but Keith confirmed out-of-band and the step was skipped. The halt message still says "provide BWT TXT record" which is confusing for a deprecated step. Should be removed from the orchestrator entirely.

### Point 19 — GSC (Bucket C)

**Halt quality:** The halt message instructed adding the TXT record to DNS, but did not explicitly say "also set GOOGLE_SITE_VERIFICATION in CF Pages env vars." This caused the Point 15 build failure (see Bug 8). The halt message is incomplete.  
**Keith attention required:** ~10 minutes total including the CF env var fix.

### Summary

Total Keith attention across all halts: approximately 30–45 minutes of direct engagement. The larger time cost was waiting — ~7 hours on Point 9, and the gap between GSC completion and the build re-run. The halt messages themselves are functional but two are incorrect or incomplete (BWT still present, GSC missing CF env var instruction).

---

## 5. Producer Run Characteristics

**Total wall time:** ~26 hours across 3 attempts.  
- Attempt 1 (orchestrator, 12h Node timeout): 2026-06-01T20:20 → 2026-06-02T~08:20. Estimated ~180 articles generated before SIGKILL.  
- Attempt 2 (orchestrator, 12h timeout again): 2026-06-02T~17:49 → 2026-06-03T03:36. Generated additional articles from where it was killed.  
- Attempt 3 (nohup direct): 2026-06-03T~04:00 → 2026-06-03T19:03. ~15 hours to finish remaining articles.

**Articles in pipeline:** 306  
**Generated (producer "done"):** 300  
**Hard failures (not generated):** 6  
**Validator FAILs (went to staging/failed/):** ~124  
**Published to content/articles/:** 205  

**TRIM warnings:** 221 out of 306 articles had products trimmed (exceeded per-type max). This rate (72%) indicates the pipeline.json was built with too many products per article. The trim logic is silent — no warning surfaced at Point 8 when the pipeline was populated.

**Regeneration cycles:** 0. The producer does not retry failed articles automatically. Articles that fail the validator go to `staging/failed/` permanently. No article was regenerated in this run.

**Persona lock gate:** Triggered correctly on first Point 13 attempt (persona_locked not set). Wesley Tate was locked before the orchestrator re-ran. This worked as designed.

**Persona voice quality:** Not assessed via V21 (card voice validator returned 0 fails, but fp_density is untracked). The 17 off-niche articles show the model will hallucinate product information when given a nonsensical keyword — the model fabricated a product called "chicago-fire" with pros like "Chicago branding suggests regional specialty fire product." Persona voice quality in these articles is not the primary concern; the keywords should never have been in the pipeline.

**Producer prompt tuning needed:** The `TRIM: 6 products exceeds max 3` warnings appearing on review-type articles (47 total) suggest the pipeline is building review articles with 6–7 products when reviews support max 3. The xlsx-to-pipeline tool does not enforce per-type product count limits at pipeline build time — it relies on the producer to trim. This is wasteful of sourcing work and produces inconsistent output.

---

## 6. Asset Generation Quality

**Persona photos:** The photo generation step (Point 11 / 12 area) for Wesley Tate used the platform's standard DALL-E generation. Number of generations required and cost are not recorded in decisions.log or producer.log. The photos (`wesley-tate-about.jpg`, `wesley-tate-byline.jpg`) exist at 327KB each, suggesting they were generated successfully. No Keith feedback received on photo quality.

**Brand assets (logo, favicon, OG default):**  
- Initial state: SVG logos contained `{{BRAND_NAME}}` placeholder (caught by Point 16 token check, fixed manually).  
- After fix: SVGs rendered "Ridgeline Bushcraft" as plain text in Merriweather. This was preview-acceptable for launch but Keith requested a proper logo post-live.  
- Post-launch logo created by Claude Code: ridgeline mountain mark + two-line wordmark (RIDGELINE / BUSHCRAFT). No confirmation from Keith yet on acceptance.  
- `site.config.yaml` references `favicon.ico` (which doesn't exist). BaseLayout hardcodes `/favicon.svg` and `/favicon.ico`. A `favicon.svg` was created and deployed post-launch.  
- OG default image still points to the header SVG — not a proper PNG. Social sharing cards will render the SVG wordmark, not an image.

**Visual quality gap:** The SVG-as-PNG substitution for `header_png`, `social_square`, and `open_graph_default` is not acceptable for production OG images. Real PNG assets are still needed.

---

## 7. Bucket A Overrides

These are actions that should have been autonomous per the v1.6 spec but required manual intervention.

| Override | What was done manually | Why it wasn't autonomous | Platform gap |
|----------|----------------------|--------------------------|-------------|
| Point 10.5 creation | Created entire new orchestrator step | Step did not exist | Missing from PIPELINE.md v1.6 |
| Node execSync SIGKILL recovery | Ran `nohup` producer directly on VM | execSync architecture cannot manage multi-hour processes | Fundamental architecture issue in Point 13 |
| Python PATH fix (Point 10) | Identified and fixed PATH in execSync environment | execSync does not inherit shell PATH | Configuration |
| `site.config.yaml` logo_paths | Added entire `visual.logo_paths` block | Scaffold template does not emit this block | Scaffold template gap |
| SVG `{{BRAND_NAME}}` replacement | sed on both SVG files | Scaffold substitution not applied | Scaffold initialisation bug |
| CF Pages project creation | `wrangler pages project create` | No orchestrator point creates the project | Missing pre-deploy step |
| CF API token permissions | Registrar-side CNAME instead of CF zone | Token lacks zone:create | Token configuration not validated pre-launch |
| GSC CF env var | `cloudflare-pages-config.mjs` manually | Bucket C halt message does not include this step | Halt message spec gap |
| Navigation multi-category restructure | Rewrote navigation.yaml into 5 categories | Scaffold generates single flat category | Scaffold nav structure gap |
| `how_to` type aliases in pipeline | sed + xlsx-to-pipeline.mjs fix | Missing TYPE_ALIASES | Tool schema gap |

**10 Bucket A overrides.** This is the primary finding of the postmortem. The v1.6 spec assumes autonomy for most of these. None of them were autonomous.

---

## 8. Editorial UAT Findings

**Not run.** No Chrome Claude UAT was conducted for Site 16. The 205 published articles have not been reviewed by the UAT agent described in PIPELINE.md. This section cannot be filled.

The 88 validator-failed articles in `staging/failed/` represent an implicit quality gate — the worst articles were not published. But the quality of the 205 that were published (including the 30 F08 articles that may have been manually approved) has not been assessed.

---

## 9. Total Cost Accounting

Exact API receipts are not available from decisions.log or producer.log. The following are estimates:

| Cost item | Estimate | Basis |
|-----------|---------|-------|
| Rainforest product sourcing | ~$2–5 | ~4 failed + 1 successful API session |
| OpenAI DALL-E (persona photos) | ~$0.08–0.20 | 2 photos, DALL-E 3, ~$0.04–0.08 each |
| Anthropic Haiku (Point 10.5 pros/cons) | ~$0.90 | ~1,180 products × $0.0007 (per 10.5 code comment) |
| Anthropic Haiku (V13.5b persona spec) | Unknown | LLM cost not tracked |
| Anthropic Sonnet (producer, 306 articles) | ~$75–80 | ~306 × $0.25/article (Keith's own estimate during session) |
| Cloudflare API calls | ~$0 | CF API is not billed per-call at this volume |
| Total estimated | **~$79–87** | |

**Missing:** Haiku cost for V13.5b is not tracked anywhere. For a 306-article run with LLM validation per article, this could be meaningful. This should be logged.

**Note on producer cost:** The 306-article figure includes 124 articles that ultimately failed validation and were not published. The effective cost per published article is ~$0.38–0.43 (79/205), not $0.25. The wasted spend on off-niche and malformed articles is part of the real per-site cost.

---

## 10. Time Accounting

| Phase | Wall time | Keith time | Claude Code time |
|-------|-----------|------------|-----------------|
| Points 7–9 (shell, furniture, Amazon) | ~7.5h (dominated by Point 9 wait) | ~20 min | ~30 min |
| Points 10–12 (sourcing, images) | ~30 min | ~10 min | ~20 min |
| Point 10.5 (pros/cons, added mid-launch) | ~3.5h | ~5 min | ~3.5h |
| Point 13 (producer, 3 attempts) | ~26h | ~20 min | ~26h (running on VM) |
| Points 13.5–14 (validators, staging) | <5 min | 0 | ~5 min |
| Points 15–15.6 (build, preflight) | ~1h | ~30 min | ~30 min |
| Points 16–21 (deploy, halts, DNS) | ~2h | ~45 min | ~1.25h |
| Post-launch (nav fix, logo) | ~1h | ~10 min | ~50 min |
| **Total** | **~57h** | **~2.5h** | **~32.5h** |

**Ratio:** Keith time / total wall time ≈ 4%. The producer run dominates the wall time and is entirely unattended once running. Keith's direct engagement was modest but concentrated in bursts (halts, bug diagnosis, preflight fixes).

**Important caveat:** "Claude Code time" here counts all automated execution including the producer run. Keith's opportunity cost (cannot close the laptop, site is in an in-progress state) is not captured by these numbers. The 57-hour wall time represents 2.5 days where the site was partially launched and the session was blocking.

---

## 11. v1.7 Backlog Candidates

These should be logged in PLATFORM_BACKLOG.md as specific work items:

**P0 — Must fix before Site 17:**

1. **Point 13: replace execSync with spawn+poll for producer run.** The current architecture fails for any site with >150 articles at normal Sonnet throughput. The correct fix is to spawn the producer process, tail its output, and poll for completion. This is a non-trivial change to `p13-producer.mjs` but it is blocking for all future large-catalog sites.

2. **GSC halt message: add CF env var step.** The Bucket C halt at Point 19 must explicitly instruct: "Set GOOGLE_SITE_VERIFICATION env var in CF Pages (production environment) before resuming." This is a one-line fix to the halt template.

**P1 — Should fix before Site 17:**

3. **Add Point 10.5 to PIPELINE.md v1.6.** The pros/cons generation step must be in the canonical spec, not improvised mid-launch.

4. **Scaffold template: add `visual.logo_paths` block.** Every new site will hit a build crash on the null dereference. The scaffold must emit all 6 required path fields.

5. **Scaffold: fix `{{BRAND_NAME}}` substitution in SVG assets.** The initialisation step is not applying the substitution.

6. **Keyword pre-filter in xlsx-to-pipeline.mjs.** Add a relevance check that flags or rejects keywords that are clearly off-niche (TV show titles, campus maps, historical questions with no commercial intent). The 17 off-niche articles in this launch cost ~$4–5 in API spend and time.

7. **CF Pages project creation: add as explicit orchestrator step.** Before Point 16, verify the CF Pages project exists; create it if not. This should be autonomous.

**P2 — Should fix before parallel launches:**

8. **Navigation scaffold: multi-category generation.** When a niche has >6 hubs, the scaffold must generate a sensible category grouping rather than a single flat category. This requires a category-grouping heuristic or a per-site nav spec.

9. **V13.8 (card voice): implement fp_density tracking.** The `fp_density=unknown` on every run means the false-positive rate of this validator is unknown. It should track and log this.

10. **V13.5b (persona spec): track Haiku cost per run.** Log the actual API spend in the decisions.log entry.

11. **BWT halt: remove or update.** The BWT step is deprecated. The orchestrator still fires a Bucket C halt for it. Either remove it from the POINTS array or convert it to a no-op pass.

12. **Duplicate Point 17 halt firing.** The orchestrator fired the Point 17 halt twice without advancing state. The halt idempotency check is broken.

---

## 12. Honest Readiness Assessment for Sites 17–20

### Q1: Can Sites 17–20 launch sequentially with high confidence?

**Yes, with caveats.** The 10 Bucket A overrides from Site 16 represent a known list of fixes. Most of them (scaffold gaps, halt messages, BWT removal) are straightforward. The two blocking items are:

1. **Point 13 execSync architecture** — If not fixed before Site 17, the operator must again run the producer directly on the VM. This is not autonomous but it's a known workaround.
2. **CF API token zone:create permission** — If not added, the domain attachment step will again fail and require registrar-side DNS.

With these two workarounds accepted as manual steps (or fixed before launch), Sites 17–20 can launch sequentially. Expected duration per site, with Site 16 bugs fixed:

- Active operator time: ~2–3 hours (halts + preflight fixes)
- Wall time: ~3 days (dominated by producer run at ~20–45 articles/hour depending on catalog size)

This estimate is only valid if the keyword source for Sites 17–20 is cleaner than Site 16's. The 17 off-niche articles suggest the bushcraft keyword XLSX had low-quality long-tail queries. If the same pattern appears in other niches, expect ~40% of generated articles to fail validation.

### Q2: Can Sites 17–20 launch in parallel with reasonable confidence?

**No.** PIPELINE.md §16.7's prohibition on parallel launches is reinforced by Site 16 evidence, not contradicted. Reasons:

- The producer run requires direct VM access and monitoring. Running two producers simultaneously on the same VM would create resource contention and likely corrupt both runs.
- The 10 Bucket A overrides require focused debugging. Debugging two sites simultaneously would cause confusion about which fix belongs to which site.
- The halt/resume loop requires Claude Code context. A single session cannot reliably track two sites' state machines.
- The keyword quality issue requires per-launch review of the off-niche failures before publish. That review cannot be parallelized without a second operator.

One specific compounding risk under parallel execution: the Point 10.5 pros/cons generation step was added mid-launch. If Sites 17 and 18 were running simultaneously when this was discovered, one site's producer would have started before 10.5 was wired, generating a first batch with F09 failures that would then be difficult to attribute to the right root cause.

### Q3: What single change would most improve Site 17's launch?

**Fix Point 13: replace execSync with spawn+poll for the producer run.**

This is the only change that directly reduces the 57-hour wall time. All other fixes reduce friction but the producer run is the dominant time cost. If the producer could be run inside the orchestrator without timeout risk, Site 17's wall time drops from ~3 days to ~1 day (the producer still takes the same time, but the orchestrator doesn't lose state and the operator doesn't need to babysit the nohup approach). It also removes the need for the manual "run nohup on VM" workaround, which is the messiest part of the current launch procedure.

---

*Postmortem written 2026-06-04. Data sources: decisions.log (VM), producer.log (VM), state.yaml, session memory.*
