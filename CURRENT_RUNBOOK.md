# Current Runbook — How Affiliate Sites Currently Get Launched
Date: 2026-05-31
Based on: Sites 13/14/15 build experience + observed platform state across 15 live/near-live sites

---

## Overview

A new site starts with Keith providing a domain and keyword research XLSX. Claude Code takes the XLSX, scaffolds a site repo from a template, writes a persona YAML, sources products via Rainforest or Amazon scraping, generates 300 articles via an LLM-backed producer, runs validators, builds with Astro, and deploys to Cloudflare Pages via `wrangler`. Keith handles GA4, GSC, and BWT setup manually after the site is live. The 21-point pipeline in PIPELINE.md is the stated spec. The actual sequence described below is what happened on Sites 13, 14, and 15 — which diverge from the spec in several documented ways.

---

## Phase 0: Pre-launch inputs

**What Keith provides:**

- **Domain name**: Provided in conversation. May be an aged/expired domain picked up externally (Sites 13, 14) or a fresh hand-registered domain (Site 15). Domain is registered and DNS is live in Cloudflare before work begins — Claude Code does not register domains.
- **Niche and keyword research**: An XLSX file with one row per article, including columns for hub, slug, article type, target keyword, volume, KD, and intent signals. Format matches the spec in PIPELINE.md Point 2. Delivered as a file path in conversation.
- **Persona identity**: Provided via conversation — name, location, profession, voice characteristics, gear/hobby details. There is no rigid questionnaire enforced (PIPELINE.md Point 5 specifies one; in practice Keith and Claude Code design the persona collaboratively). Site 13 persona was partially drafted before the session and refined during it.
- **Amazon tracking ID format**: Always `<slug>-20`, typically derived from site slug. Keith registers the Amazon Associates tracking ID from his dashboard; the string is placed in `site.config.yaml`.

**What is NOT provided at Phase 0:**
- Persona photos — these are sourced during the session, not delivered by Keith upfront.
- Brand colors — Claude Code derives these from niche context.
- Google/CF credentials — Keith handles all browser-based account steps.

---

## Phase 1: Domain + infrastructure

**Domain registration:** By Keith, in Cloudflare's registrar, before Claude Code work begins. Claude Code does not register domains.

**Cloudflare Pages project creation:** Claude Code creates the project using the Cloudflare API (`tools/lib/cloudflare-api.mjs`) during site initialization. The API token lives in the platform-level `.env.local`. The project name matches the site slug exactly.

**DNS configuration:** Live when Claude Code begins work on Sites 13/14 (aged domains). DNS pointed at Cloudflare Pages is configured via the CF dashboard — this step is either done by Keith before the session or by Claude Code via CF API during initialization. The exact sequencing varied: on Site 13 DNS was confirmed live before content generation; on Site 15 (rmflyfishing) DNS state at generation time is [UNKNOWN — Keith activity].

**Production custom domain:** Set in the Cloudflare Pages dashboard (Production environment → Custom Domain). This is a separate step from DNS configuration; it wires the CF Pages project to the domain. Done by Claude Code via CF API or Keith via dashboard — not consistently documented across sessions.

[FLAG: domain steps that are manual Keith vs Claude Code]:
- Domain registration: Keith only (his registrar account)
- Cloudflare Pages project creation: Claude Code (CF API)
- DNS TXT record for GSC/BWT verification: Keith only (his Google/Bing accounts)
- Custom domain in CF Pages dashboard: Could be either; done by Keith on most sites based on `github_repo: null` pattern

---

## Phase 2: Site scaffolding

**Source:** `affiliate-platform/templates/site-shell/` is the canonical scaffold template. `tools/initialise-site.mjs` exists and should be the invocation point, but on Sites 13/14 there is no log of `initialise-site.mjs` being called — scaffolding may have been done manually or via an earlier invocation whose log isn't visible in session memory.

**What the scaffold contains at creation:**
- `site.config.yaml` — domain, brand name, tracking ID, visual config (colors, fonts), hub structure
- `config/navigation.yaml` — hub and category structure
- `config/personas/<slug>.yaml` — persona spec
- `wrangler.toml` — CF Pages project name
- `package.json` — with platform dependency `@platform/core`
- `producer/` — producer wrapper and tests
- `src/pages/` — Astro page stubs
- `data/pipeline.json` — populated from keyword XLSX
- `content/products/products.yaml` — empty at scaffold, populated in Phase 5
- `content/articles/` — empty at scaffold, populated in Phase 7
- `public/images/brand/` — placeholder brand images at scaffold; replaced during Phase 4

**What gets customized per-site at scaffolding:**
- `site.config.yaml`: domain, tracking ID, brand name, tagline, colors, fonts, hubs
- `wrangler.toml`: project name
- `config/navigation.yaml`: hub slugs, labels, descriptions
- Producer tests: fixture hubs in `producer/tests/`

**Files with placeholder values that need filling later:**
- `analytics.ga4_measurement_id` in `site.config.yaml` — set to null at scaffold, filled after Keith creates GA4 property
- `analytics.bing_uet_tag` — same
- Persona photos — placeholder at scaffold; replaced during Phase 3
- Hub descriptions in `navigation.yaml` — generic at scaffold; require site-specific copy before launch (preflight check 3 blocks on boilerplate)

---

## Phase 3: Persona

**When written:** The persona YAML gets a first pass during scaffolding, based on Keith's inputs in conversation. On Sites 13 and 14, the persona was written before producer runs but NOT LOCKED before producer runs. This was the root cause of the entire Site 13 editorial fix session: 300 articles were generated with the old/wrong persona spec (wrong primary chain, wrong IEMs, wrong partner name), then required a retroactive editorial pass after the persona was locked.

**Who writes it:** Collaborative — Keith provides the biographical details, gear list, and voice notes; Claude Code writes the YAML and validates it against other portfolio personas (name uniqueness, background uniqueness per CLAUDE.md Rule 1).

**Persona locked before or after producer:** 
- PIPELINE.md spec: Point 5 (persona) happens before Point 13 (producer run). Persona should be final before any generation.
- Site 13 reality: Persona was provisionally set at scaffold, generator ran, then persona was revised and locked AFTER all 300 articles were live. Required full editorial fix pass.
- Site 14 reality: Same pattern — persona spec changed during/after generation, requiring editorial fixes.
- [OBSERVATION]: The platform has no enforcement gate preventing producer runs with a non-locked persona. There is no `persona_locked: true` field in the YAML, no producer check that blocks generation until persona is finalized, and no validator that confirms persona spec hasn't changed since last generation.

**Persona photos:**
Sourced during the session, not at scaffold. Three patterns observed across the cohort:
1. AI-generated images: byline photo is tiny (Site 13: 13KB byline, 37KB about) — consistent with AI-generated compressed headshots
2. Stock photos at identical sizes: HPC byline and about are both 322,782 bytes — same file reused for both slots
3. Very small placeholder-class files: SSS byline is 3KB — likely a placeholder or thumbnail that never got replaced

[OBSERVATION]: PIPELINE.md Point 5 specifies "Photos must be real (not template placeholders). Build will halt if MD5 matches existing portfolio persona photos." There is no evidence this MD5 check is actually enforced by any tool; the `verify-site-shell.mjs` tool exists but whether it runs this check is not confirmed. The HPC pattern (identical byline and about using same source file) would have failed a real MD5-uniqueness check.

[FLAG: Photo generation is inconsistent across sessions]:
- Some sites: AI-generated via ChatGPT or similar, sized and placed by Claude Code
- Some sites: stock photo sourced by Keith and provided as file path
- Some sites: unclear sourcing, files present but small/suspect
- No consistent tool or workflow documented

---

## Phase 4: Brand assets

**Expected assets before deploy:**
- `logo-header.svg` (color on light background)
- `logo-header-dark.svg` (color on dark background, or white)
- `logo-mark.svg` (icon only)
- `logo-monochrome.svg`
- `logo-footer.svg`
- `favicon.ico`
- `favicon.svg`
- `apple-touch-icon.png`
- `og-default.jpg`
- `persona-byline.jpg`
- `persona-about.jpg`

**Source:** Claude Code generates SVG logos programmatically (writes inline SVG code). Favicons are derived from the logo mark. The og-default.jpg is a branded image created by Claude Code. Persona photos sourced as described in Phase 3.

**Consistency:** Brand assets are one of the most consistently broken areas at deploy time. The closeout verification for Site 13 (today) showed all 10 assets returning 200 — but that's after fixes. Earlier in the session, multiple assets were 404. The Site 14 session documented B8 (SVG using `fill="currentColor"` which renders invisible when loaded as `<img>`). This bug was fixed on Site 14 but was not checked on Sites 13 or 15.

[OBSERVATION]: The B8 SVG fill bug — logos invisible when loaded as `<img>` tag — was identified during Site 14 UAT and fixed on Site 14 only. Site 13 passed today's brand asset 200-check (assets load), but whether the SVGs render visibly in all contexts is unverified. The fix (hardcoded hex fills instead of `currentColor`) is documented in PLATFORM_BACKLOG.md as "not propagated to other sites."

[OBSERVATION]: There is no automated check that verifies SVG logos render visibly (return 200 is insufficient — a 200 SVG can be invisible). The build-validator checks for asset presence but not rendering correctness.

[FLAG: Assets routinely missed at various launch stages]:
- `persona-byline.jpg` and `persona-about.jpg`: often the last assets placed, sometimes after first deploy
- `og-default.jpg`: sometimes created as a placeholder JPG then updated
- `-dark` variants of logos: sometimes missed if the dark-background path in the site theme isn't tested during dev

---

## Phase 5: Catalog (products.yaml)

**Product sourcing — what actually happens:**

Three methods have been used across the portfolio; which one gets used on a given site is inconsistent:

1. **Rainforest API** (`tools/source-products-rainforest.py`): The documented canonical workflow for production runs. Costs ~$3–7 for a 300-article site. Requires `RAINFOREST_KEY` in `config/credentials.env`. When run, produces a well-populated catalog with real ASINs and `default_pros`/`default_cons` from a follow-on Haiku pass. 
   - Site 13 evidence: No Rainforest run evident in session logs or data directory. Products.yaml has 311 entries, 68 NOT_FOUND — possible that Rainforest was used early in the session but the log wasn't preserved.
   - [UNKNOWN — was Rainforest used for Sites 13/14/15? The session memory doesn't confirm it.]

2. **Amazon scraping** (`tools/source-products-per-article.mjs`): Uses LLM + Amazon scraping. Rate-limits at scale (hits blocks ~30 articles in). Documented as deprecated for production bulk runs; retained for small jobs. Observed being used in earlier sessions when Rainforest wasn't available or configured.

3. **Manual catalog construction**: Products sourced by Claude Code reading Amazon search results in conversation, writing YAML entries by hand. Used for individual product gaps, specialty categories with low Amazon coverage, and DTC-only brands.

**DTC product handling:**
Products not on Amazon are flagged `amazon_asin: NOT_ON_AMAZON` (for brands that have a direct channel) or `amazon_asin: NOT_FOUND` (for cases where Amazon was searched and came up empty). The `config/dtc-brands.yaml` at platform level lists known DTC-only brands. Site 13's catalog had 68 NOT_FOUND entries out of 311 products — audiophile brands like Schiit, JDS Labs, and several boutique IEM makers have no Amazon presence.

**Catalog validation before producer:**
- `tools/validate-products-complete.mjs` — checks for VERIFY ASINs, validates format
- `scripts/validate-brand-match.mjs` (Point 12.5) — confirms articles with brand keywords have brand products assigned
- `scripts/validate-catalog-brand-coverage.mjs` — checks for null brand fields
- These run at different points; not all are consistently invoked. Brand enrichment pass (null brand → populated brand) was required on multiple sites post-sourcing.

[OBSERVATION]: The brand enrichment pass requirement is documented in PIPELINE.md as "required after sourcing" but there is no automated gate that blocks producer from running with null brand entries. Site 13 had 311 products; whether all had `brand:` populated before producer ran is [UNKNOWN].

---

## Phase 6: Images

**Source:** Pexels API via `tools/source-images-pexels.mjs`.

**Spec:** 150 images per site, 1200×630, webp format, hub-based naming (`<hub>-N.webp`), stored at `public/images/articles/`.

**Actual counts observed:**
- undisclosedsounds (Site 13): 280 images
- homepicturescinema (Site 14): 209 images
- rmflyfishing (Site 15): 228 images
- saunassosimple (Site 11): 1,330 images
- ten27 (Site 8): 1,205 images
- fourfernscare (Site 12): 646 images

The 150-image spec is consistently exceeded, sometimes dramatically (SSS and Ten27 at 1,200+). The variance is large and unexplained. For older sites (Ten27, SSS) the image bank may have accumulated across multiple Pexels sourcing passes. For Sites 13/14/15, counts ~200–280 suggest a single larger pass that didn't enforce the 150 ceiling.

**Image assignment:** `tools/assign-article-images.mjs` assigns hero and body images from the bank to each article entry in pipeline.json. The producer then reads pipeline.json and injects image markdown at fixed positions. On Site 13, the image assignment was done and 280 images were available; the 300 articles reference images from this bank.

**What happens if articles reference images that don't exist:**
The build-validator catches broken image references at build time. Producer uses a dict-literal bug (tracked as B2-adjacent issue) that was patched in an earlier platform version — the `scripts/validate-image-markdown.mjs` tool (Point 13.6) catches this pattern before publish.

[OBSERVATION]: The Pexels sourcing tool is not always run explicitly in session — it may have been run in earlier sessions and the images committed. The session memory for Site 13 doesn't include a Pexels API call, but 280 images are present. Whether this is from the same or a prior session is unclear.

---

## Phase 7: Producer run

**Producer invocation:**
The actual command used for Sites 13/14 is via `run_producer.py` in the site root — a Python wrapper that pre-loads the site's `data_loader.py` into `sys.modules` before delegating to `affiliate-platform/producer/producer_main.py`. This wrapper exists because the platform producer needs to use the site-specific hub logic.

Site 13 invocation:
```
python3 run_producer.py --site ~/undisclosedsounds --count 300 2>&1 | tee logs/produce-300.log
```

Site 14 invocation was via the traditional `producer/homepicturescinema-producer-v2.py` wrapper — the older pattern is still present on Site 14.

**What the producer reads:**
- `data/pipeline.json` — article list with assigned products and images
- `config/personas/<slug>.yaml` — persona spec for voice, gear, constraints
- `content/products/products.yaml` — product details including pros/cons
- `affiliate-platform/prompts/article-buyer-guide.v1.md` and `article-roundup.v1.md` — the actual generation prompts

**Output destination:** `staging/` (not `content/articles/`). Articles move to `content/articles/` via `tools/publish-staging.mjs` after validation.

**Run duration:** 1.5–3 hours unattended for 300 articles. Runs in foreground with tee to log file.

**Failure handling:**
- Shape failures (wrong structure, missing sections): article written to `staging/failed/`, retried once with `--force`
- Model refusals: surfaced in log, treated as shape failure
- API rate limits: producer retries with backoff, eventually moves article to failed if retries exhausted
- Persistent failures: hand-edited in staging or dropped (judgment per article)

**How persona spec reaches the producer:**
The persona YAML is read by `data_loader.py` and injected into the prompt context. The article_builder.py `check_output_shape()` function applies post-generation checks including persona-claim violations (B2: `\bI tested\b`, `\bI've owned\b`). The biographical fabrication ban (Phase 1d fix) was added to the prompts in `affiliate-platform/prompts/` as a hard constraint. However, this ban was added AFTER Site 13's 300 articles were generated — it did not prevent the contamination that required the editorial fix session.

---

## Phase 8: Validation

**Validators and when they run:**

| Validator | When | Tool | What it catches |
|---|---|---|---|
| ASIN format check | Pre-producer | `grep "amazon_asin: VERIFY" products.yaml` | Unresolved VERIFY placeholders |
| Brand match audit | Point 12.5 (pre-producer) | `validate-brand-match.mjs` | Brand keyword articles without matching brand products |
| Image markdown | Point 13.6 (post-generation, pre-publish) | `validate-image-markdown.mjs` | Dict-literal image URLs from old producer bug |
| Persona claims | Point 13.5 (post-generation, pre-publish) | `validate-persona-claims.mjs` (documented) | "I tested", "I've owned", etc. |
| Build validator | During `npm run build` | `build-validator.mjs` | Shape violations, broken links, hardcoded ASINs, dollar figures, CTA density |
| Pre-flight | Point 15.5 (post-build, pre-deploy) | `preflight.py` | 18+ structural checks including scaffold contamination, hub consistency, product coherence, spec consistency, dollar figures, Amazon tag validity, furniture pages, brand collision, YMYL endorsements |
| Deploy verify | Post-deploy | `verify-deploy.mjs` | DNS, 200s, GA4 injection, Amazon tag in HTML, custom 404, freshness |

**What the validator stack misses:**

- **Persona-spec compliance**: No validator compares first-person claims in article bodies against the locked persona YAML. The `validate-persona-claims.mjs` catches fabricated testing claims but not gear ownership claims ("my Aria 2", "my E50/L50 stack", "my partner Sam"). Site 13's entire editorial fix session was for this class of violation, which no existing validator catches.
- **Em-dash errors (B2)**: No validator catches ` , ` (space-comma-space) used in place of ` — `. Documented in PLATFORM_BACKLOG.md, not yet implemented.
- **Price-token blank links (B3)**: No validator catches `[best X under ](<url>)` blank price in link text. Documented, not yet implemented.
- **Meta-commentary in article body (B4)**: No validator catches LLM internal reasoning written into article body ("the brief says X", "the keyword is Y"). Documented, not yet implemented.
- **SVG render validity**: No validator confirms SVG brand assets render visibly, only that they return 200.
- **Persona photo uniqueness**: PIPELINE.md specifies an MD5 check in `verify-site-shell.mjs`; not confirmed as implemented.
- **Rendered HTML placeholder scan**: The build-validator checks for `{{TOKEN}}` in markdown source, but a validator that scans rendered HTML output for placeholder strings (e.g., "LOREM_IPSUM", "PLACEHOLDER", template tokens that survived Astro rendering) does not exist. Site 14 shipped placeholder leaks that a rendered-HTML scan would have caught.

---

## Phase 9: Build + deploy

**Build command:** `npm run build`
This runs: `astro build → npx pagefind → node build-validator.mjs`
Must not be called as `astro build` directly — skips pagefind and the validator.

**Build output:** `dist/` in the site root.

**Deploy command:** `npm run deploy`
This runs: `npm run build → safe-deploy.mjs → verify-deploy.mjs`

The `safe-deploy.mjs` calls `wrangler pages deploy dist --project-name <slug> --branch main`. This is a **direct upload** to Cloudflare Pages, not a git push → auto-deploy. PIPELINE.md Section 1.4 describes a "wrangler.toml + Git push deploy pattern" where deploys are triggered by pushes. The actual observed pattern is direct wrangler upload.

[OBSERVATION]: There is a discrepancy between PIPELINE.md §1.4 (git push → CF auto-deploy) and the actual package.json deploy scripts (wrangler direct upload). The actual deploy is `wrangler pages deploy dist` — it does not push to GitHub first. `portfolio.yaml` shows `github_repo: null` for Sites 11 through 15, suggesting no GitHub repo was ever created for those sites. Sites 1–10 have `github_repo` set. The Git push → CF auto-deploy pattern described in PIPELINE.md does not apply to Sites 11+.

**Preview URL:** Each wrangler deploy generates a unique preview URL (`https://<hash>.undisclosedsounds.pages.dev`). This is how UAT is done — review the preview URL before promoting to production.

**Production promotion:** The site's custom domain is configured in CF Pages dashboard and receives traffic from the production branch. With direct uploads to `--branch main`, each new deploy updates production. There is no separate "promote preview to production" step — direct upload to main IS production.

---

## Phase 10: Manual gates (Keith)

| Step | Keith action | Could Claude Code do it? |
|---|---|---|
| GA4 property creation | Browser: analytics.google.com | No — requires Keith's Google account |
| GA4 measurement ID injection | After Keith provides ID, Claude Code adds to `site.config.yaml` and redeploys | Partial — Claude Code does the code side; Keith provides the ID |
| GSC property verification | Browser: DNS TXT record in Cloudflare | Technically Claude Code could add DNS record via CF API, but currently Keith does it |
| BWT property verification | Browser: DNS TXT record | Same as GSC |
| GSC sitemap submission | Browser: GSC dashboard | No — requires Keith's Google account |
| Disavow file submission | Browser: GSC → Disavow Links | No — requires Keith's Google account |
| Brand affiliate applications | Browser: each affiliate program's signup | No — requires Keith's accounts and payment info |
| CF custom domain wire-up | Browser: CF Pages dashboard | Claude Code can do via CF API but doesn't consistently |
| Amazon Associates tracking ID creation | Browser: Amazon Associates dashboard | No — Keith's Amazon account |

[FLAG: Genuinely Keith-only vs. capability gap]:
- GA4 property creation: Keith-only (his Google account)
- GSC/BWT DNS verification: Keith-only today, but Claude Code has CF API access and could add TXT records — current practice is Keith does it manually
- CF custom domain: Claude Code CAN do this via CF API; inconsistently done by Claude Code vs. Keith
- Disavow submission: Keith-only (his GSC account) but Claude Code builds the file
- Brand affiliates: Keith-only (his identity, payment, website ownership)

---

## Cross-cutting observations

### Things that are consistent across sessions

- Site slugs follow `<niche-keyword>` pattern, never contain personal names
- Amazon tracking IDs follow `<slug-truncated>-20` format
- All sites use Cloudflare Pages (direct upload for Sites 11+)
- 300 articles is the standard production volume
- Products sourced per-article (not a shared bucket)
- `npm run build` is the only permitted build entry point
- Preflight must pass (0 FAIL) before deploy is considered clean
- Staged articles go to `staging/`, not directly to `content/articles/`
- Platform validators are in `affiliate-platform/scripts/`, not in site repos
- One persona per site, persona YAML in `config/personas/`

### Things that vary across sessions

- **Rainforest vs. scraping vs. manual**: No consistent enforcement of which product sourcing method is used. Documented canonical workflow is Rainforest; actual practice varies by session.
- **Persona lock timing**: Spec says persona finalized before producer runs. Practice: persona is often refined during/after generation, leading to retroactive editorial fixes.
- **Image bank size**: Spec says 150. Practice: 209–1330 depending on site and how many Pexels passes were run.
- **Persona photo sourcing**: AI-generated, stock, or same-file-reused. No consistent method or quality gate.
- **SVG logo fill values**: `currentColor` vs. hardcoded hex. B8 bug was found on Site 14 and fixed there; not confirmed fixed elsewhere.
- **Preflight timing**: Should run at Point 15.5 (post-build, pre-deploy). In practice, often run reactively when a deploy is flagged rather than proactively as a gate.
- **portfolio.yaml accuracy**: Often out of date. Site 13 shows `status: pre_launch` and `ga4_id: null` despite being live with GA4 deployed. Multiple sites have `github_repo: null`.
- **`initialise-site.mjs` usage**: Documented as the scaffold entry point. Not confirmed as the actual invocation method for Sites 13/14/15.

### Decisions Claude Code currently defers to Keith on

- Whether to launch a new site
- Domain choice (aged vs fresh, niche fit)
- Niche selection and keyword research validation
- Persona identity (biographical details, not just YAML structure)
- Whether a failing article should be hand-edited, dropped, or regenerated
- Whether a non-zero NOT_ON_AMAZON rate in a niche is acceptable
- GA4, GSC, BWT setup (accounts, verification)
- Brand affiliate program applications
- Whether a preflight WARN is acceptable to ship
- Production article volume per session
- When a site is "ready" to move from pre-launch to live

### Tools that exist in `affiliate-platform/` but aren't consistently used

- `tools/launch-site.mjs` — the "ONE entry point" per PIPELINE.md §2; sessions start via conversation, not via this tool
- `tools/initialise-site.mjs` — exists, but scaffold on Sites 13/14/15 may have been done manually or in earlier un-logged sessions
- `tools/verify-site-shell.mjs` — exists, but persona photo MD5 check is not confirmed as enforced
- `tools/verify-bindings.mjs` — exists, wired into `npm run deploy`; whether it was used on Sites 13/14/15 pre-deploy is not confirmed from session logs
- `tools/source-products-rainforest.py` — documented as canonical; actual usage on Sites 13/14/15 [UNKNOWN]
- `tools/publish-staging.mjs` — exists; whether it was used or articles were manually moved from staging is [UNKNOWN] for Sites 13/14/15
- `tools/dashboard.mjs` — exists but portfolio.yaml is stale (pre_launch/null fields), suggesting the dashboard hasn't been updated post-launch

### Steps that have no tool yet

- **Persona-spec compliance scanner**: No tool exists that reads persona YAML and flags article body claims that contradict it (gear ownership, partner names, locations). This was the entire Site 13 editorial fix class.
- **Niche density check**: `tools/check-niche-density.mjs` documented as MISSING in PIPELINE.md; still missing.
- **Article expansion**: `tools/expand-articles.mjs` documented as a future Tier 1 operational tool; not built.
- **Em-dash post-generation fix**: B2 from PLATFORM_BACKLOG.md — no build-validator check and no producer prompt fix yet shipped.
- **Price token blank link detector**: B3 from PLATFORM_BACKLOG.md — no validator yet.
- **Meta-commentary detector**: B4 from PLATFORM_BACKLOG.md — no validator yet.
- **Rendered HTML placeholder scan**: No tool scans `dist/` HTML for placeholder strings that survived Astro rendering.
- **ASIN health check**: `tools/asin-health-check.mjs` documented as Tier 1 operational, not built.
- **Earnings polling**: `tools/earnings-poll.mjs` documented as Tier 1 operational, not built.

---

## My honest read

The platform works, but the gap between the documented pipeline (PIPELINE.md) and actual session behavior is wide. PIPELINE.md was written iteratively as lessons accumulated from Sites 1–12, and it reflects what the process *should* be more than what it *is*. The tools listed as "needs to be built" before Site 4 all exist now, which means the mechanical toolchain is largely in place. What's not in place is the discipline layer that enforces the sequence.

The persona lock problem is the most consequential recurring gap. Both Sites 13 and 14 had articles generated before the persona spec was finalized — Site 13 required a full editorial fix session (hours of work) to correct. There is no enforcement mechanism: no tool, no validator, no YAML field. The producer runs when you call it. If the persona is wrong, the producer outputs 300 articles with wrong facts. The fix is retroactive and expensive.

The second major gap is the product sourcing inconsistency. PIPELINE.md documents a clear three-step Rainforest workflow. Whether that workflow was actually followed for Sites 13, 14, and 15 is genuinely unknown — there are no session logs, no data directory artifacts confirming Rainforest API calls, and no validator that confirms pros/cons came from Haiku vs. placeholder generation. Sites 1–12 had documented Northwoods-style brand enrichment problems (60%+ null brand fields post-Rainforest). If Rainforest wasn't run, or ran partially, the catalog may have gaps that propagate into article quality.

The third gap is portfolio.yaml accuracy. It is consistently stale. Site 13 shows `status: pre_launch` and `ga4_id: null` on the day it was verified live with GA4 deployed. The dashboard.mjs tool that should surface portfolio state works against stale data. This isn't a tool problem — it's a discipline problem: the step that updates portfolio.yaml after each phase transition isn't wired into any automatic flow.

---

*End of CURRENT_RUNBOOK.md*
