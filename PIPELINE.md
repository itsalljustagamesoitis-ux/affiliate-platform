# PIPELINE.md — v1.8

**Version:** v1.8 — updated 2026-06-08. Platform v2.3.0 fixes: closes B62a/B62b/B62c/B62d (sourcer completion, coverage pre-flight, round-robin ordering, producer dupe guard). Adds `verify-coverage.py`. See section 18 for full changelog. Previous version: v1.7 (2026-06-07, SITE-LAUNCH-PROTOCOL.md + Site 18 + B59/B60).

The complete operational specification for building, launching, and operating affiliate sites in the portfolio.

This document is the source of truth. Every site follows the same sequence. No skipping, no reordering, no deviation. When this document and reality diverge, fix reality or update this document — never silently work around it.

---

## Table of contents

1. Meta-rules
2. The launch-site ritual (the ONE entry point)
3. The 21-point per-site launch pipeline
4. Operational layer — recurring tasks
5. Operational automation tiering
6. Platform additions required before site 4
7. Validator hard fail vs soft fail framework
8. Technical SEO documentation task
9. Homepage strategy
10. Pending operational fixes for current sites
11. Document maintenance
12. v1.2 changelog — Ten27 UAT hardening
13. v1.4 changelog — SaunasSoSimple UAT hardening
14. v1.5 changelog — Pre-site-13 platform cleanup
15. v1.6 changelog — Autonomous launch hardening
16. Autonomous launch enforcement
17. v1.7 changelog — Day 18 close (SITE-LAUNCH-PROTOCOL.md + Site 18 LAUNCHED + B59/B60)

---

## 1. Meta-rules

These rules apply to every step of every site build. They exist to prevent the operational drift that compounds when sequence is variable.

### 1.1 Sequential execution with hard pause

Steps are sequential. Every site follows the same order. No skipping, no reordering, even when dependencies would technically allow it.

When a step cannot be completed, the build halts at that step. No proceeding with placeholders or known gaps. Nothing in the sequence moves forward until the step is genuinely complete.

### 1.2 Categories → hubs → articles

Every site has the same hierarchy: categories at the top, hubs within categories, articles within hubs.

Sites that are naturally flat (one category, multiple hubs) just have N=1 categories. The structure is consistent even when the data is simple.

### 1.3 One persona per site

Each site has exactly one persona. Persona file at `config/personas/<persona-slug>.yaml`, photos at `public/images/brand/<persona-slug>-byline.jpg` and `<persona-slug>-about.jpg`. The producer reads this single persona for all article generation. About page is one page about one person.

### 1.4 Deploy pattern (v1.6 updated)

Sites deploy via direct upload to Cloudflare Pages using wrangler. The command pattern is:

```
wrangler pages deploy dist --project-name <slug> --branch main
```

Direct upload to the main branch is production deploy. No GitHub repo is required for sites going forward.

**Historical note (Sites 1–10):** Sites 1–10 use the older Git push → Cloudflare auto-deploy pattern. Their GitHub repos remain operational. The pattern was changed for Sites 11+ to eliminate GitHub App permission failure modes and reduce moving parts. Sites 1–10 are preserved in their current pattern; no migration required.

`wrangler.toml`: Declares the Cloudflare Pages project name (`name = "<slug>"`) and NODE_VERSION. Lives in the repo for configuration consistency, but is not the deploy trigger.

**Environment variables** (AMAZON_TAG, NODE_VERSION, etc.): Set via Cloudflare API by `tools/cloudflare-pages-config.mjs` during Point 16 (push live). No manual dashboard configuration required. Production and Preview environments configured in a single tool invocation.

**Custom domain attachment:** Performed by Claude Code during Point 16 via `tools/cloudflare-pages-config.mjs attach-domain`. Not a manual Keith step.

### 1.5 Deploy completion criterion

After every Claude Code task that produces deployable changes, the task is not complete until:

1. Changes committed locally with a meaningful message
2. Pushed to GitHub origin
3. Cloudflare Pages deployment fired and reached green
4. Live verification passes

Live verification consists of 9 hard checks. All 9 must pass. Single failure = deploy not complete:

1. `curl https://<domain>` returns 200
2. `curl https://<domain>/sitemap-index.xml` returns 200
3. Sample 3 article URLs return 200
4. HTML source contains GA4 measurement ID
5. HTML source contains correct AMAZON_TAG in affiliate links
6. (v1.6) Custom domain attached to Cloudflare Pages project (curl -I returns cf-ray header indicating Cloudflare termination)
7. (v1.6) Environment variables AMAZON_TAG present on both Production and Preview environments (verified via Cloudflare API)
8. (v1.6) Content-existence validator passes on built dist/ (zero placeholder leaks, zero empty article-page__content divs)
9. (v1.6) Skip-list URLs return 404 or 301 (no articles on producer's skip-list returning 200)

Tool retries once after 30 seconds before final fail. State is binary — pass or fail.

Cloudflare deploy timeout: 10 minutes. Past timeout = hard fail.

Tooling: `tools/deploy-and-verify.mjs --site <slug>` automates steps 2-4. Step 1 stays in Claude Code's normal flow.

### 1.6 Catalog seeded from real Amazon search

Per-article product sourcing. For each article topic, search Amazon, pick listings, capture real ASINs at creation time. No invented brand names, no products generated from memory, no pre-built bucket of products distributed across articles.

Catalog populated before article generation runs, with all entries verified-on-Amazon at the moment of creation.

### 1.7 Domain registered through Cloudflare

Every domain registered through Cloudflare's registrar. DNS managed natively by Cloudflare.

### 1.8 AMAZON_TAG source of truth

The Amazon Associates tracking ID lives in `site.config.yaml` under `affiliate.amazon_tracking_id` as the primary source of truth. The Astro layout reads this value at build time and renders it into affiliate links via the rehype-product-links plugin.

Optionally, AMAZON_TAG may also be set as a Cloudflare Pages encrypted Secret on Production and Preview environments as an override mechanism. When present, the Cloudflare env var takes precedence over site.config.yaml. When absent, site.config.yaml is used.

Per-site tracking ID format: `<site-slug-truncated-to-fit-amazon-limit>-20`. Amazon Associates enforces a 20-character maximum for tracking IDs, so longer slugs are truncated (e.g. `four-season-gardener` becomes `fourseasong-20`, `my-little-tablespoon` becomes `mylittletbsp-20`).

Verification: `tools/verify-bindings.mjs` checks the live rendered HTML on each site, confirming the actual tracking ID in deployed affiliate links matches portfolio.yaml expectations. This catches both source-of-truth issues and Cloudflare env var override mismatches.

### 1.9 No backlinks, social, or PR strategy

Quantity over per-site optimization. Backlinks, social presence, PR outreach are explicitly not part of the launch or operational pipeline.

### 1.10 Validators classify as hard fail or soft fail

Validator rules are classified at definition time. See VALIDATORS.md for full rule classification.

- **Hard fail** — blocks publication, regenerate or hand-edit
- **Soft fail** — ships with logged warning to `~/affiliate-platform/calibration-log.yaml`

10% deviation boundary: `abs(observed - target) / target * 100`. Under 10% = soft. 10% or more = hard. For "exactly N" count rules, ±1 is soft.

Regeneration pass only — no iterative validator widening per site. Hard fail rate consistently above threshold across multiple sites becomes a platform-level review.

**v1.6 new validator classifications:**

| Validator | Classification |
|---|---|
| `validate-content-existence` | Hard fail |
| `validate-persona-spec-compliance` | Hard fail |
| `validate-product-slug-resolution` | Hard fail |
| `validate-meta-leakage` | Hard fail |
| `validate-card-voice` | Soft fail |
| `validate-catalog-category-coherence` | Hard fail |

### 1.11 Placeholders are obvious, not plausible

All template content uses obvious placeholder tokens (`{{TOKEN_NAME}}`) or visibly-broken text (`LOREM_IPSUM_REPLACE_ME`), never realistic-but-wrong content. Templates that inherit content from another site are forbidden — site shells start empty of content and get filled, never copy-and-edit.

Build verification at multiple points (site shell verification, local build smoke, deploy-and-verify) checks for remaining placeholder tokens and hard-fails if any found.

### 1.12 Affiliate link format

Articles use the `product:slug` markdown protocol for affiliate links:

```
[Product Name](product:product-slug)
[Check current price on Amazon.](product:product-slug)
```

The platform's rehype plugin (`src/plugins/rehype-product-links.mjs`) resolves these to affiliate URLs at build time using `buildAffiliateUrl()`. The `ProductLink.astro` component exists as a parallel resolution mechanism but is not used in article bodies.

Producer emits `product:slug` directly. No raw Amazon URLs, no `?tag=` strings should ever appear in article source files. Build-validator blocks these as `hardcoded-asin-source` and `hardcoded-affiliate-tag-source` errors.

### 1.13 Locked vs judgment vs TBC

**Locked specifications cannot be overridden site-by-site:**

- Sequential execution with hard pause (1.1)
- Categories → hubs → articles hierarchy (1.2)
- One persona per site (1.3)
- wrangler.toml + Git push deploy pattern (1.4)
- All 5 deploy verification checks hard required (1.5)
- AMAZON_TAG single source of truth (1.8)
- 10% hard/soft fail boundary (1.10)
- Placeholders obvious, not plausible (1.11)
- product:slug affiliate link format (1.12)
- Cookie consent platform default (Consent Mode v2)
- Image bank: minimum 150 images per site, 1200x630, hub-based naming, hub-balanced (no hub >2x average) (v1.6: ceiling removed, floor + balance constraint replaces)
- Image assignment: random within hub
- Producer run mode: foreground with `tee` to log file
- Producer output destination: `staging/` (not `content/articles/`)
- Regeneration pass once, then publish (no iterative calibration per site)
- Cloudflare deploy timeout: 10 minutes hard fail
- Dashboard phase transitions: Phase 1 sites 1-10, Phase 2 sites 11-30, Phase 3 sites 31+
- Persona-lock-before-producer-run discipline mandatory (v1.6)
- `launch-site.mjs` is the only entry point for new site builds (v1.6)
- Direct upload deploy pattern for Sites 11+ (Section 1.4 v1.6 update)
- Cloudflare API automation for custom domain attachment, env vars, DNS TXT records (v1.6)
- Astro data-store cache deletion before every production build (v1.6)
- portfolio.yaml updated at every phase transition (v1.6)

**Judgment with documented defaults:**

- Niche selection: 60% Amazon density typical default
- Keyword research thresholds: 300 launch / 500 reserve / 100 vol min / KD 40 max / Commercial+Transactional+Informational intent
- Domain selection: guidance, not gates
- Brand colors: Claude Code derives from niche, you override if needed
- Source products workflow: Rainforest API canonical; scraping deprecated for production runs
- Legal text source: Claude Code generates from master templates with token substitution

**Moved from Judgment to Locked (v1.6):**

- Persona photo source: AI-generated via documented prompt template (`~/affiliate-platform/templates/persona-photo-prompt.md`), never user-provided. The "judgment per site" framing produced inconsistent quality across the cohort.

**TBC (deferred until real decisions need making):**

- Pause point assessment criteria after 10 sites
- Operational task cadences
- Automation tiering build targets
- Phase 2 sweep timing and fix priority
- De-footprinting strategy for sites 11+

---

## 2. The launch-site ritual

The 21-point pipeline executes as a single ritual prompt that Claude Code follows from end to end. There is ONE entry point for launching a new site.

### 2.1 The ritual concept

A single launch prompt — `/launch-site` — that Claude Code follows step by step, pausing only for required inputs at defined gates. Each point's completion criteria are verified before moving to the next. State persists between sessions so an interrupted launch can resume from where it left off.

### 2.2 Tool

`tools/launch-site.mjs` — orchestrator that reads PIPELINE.md, runs each point's logic, persists state, surfaces required inputs through structured questionnaires.

### 2.3 Principles

**One site at a time.** Ritual checks portfolio.yaml for in-progress sites; refuses to start a new launch if another is in flight.

**State file persistence.** Each completed point recorded in `~/affiliate-platform/sites/<slug>/state.yaml`. Resumable from any point.

**Hard pauses are real.** When user input is required, ritual halts and surfaces clear "next action" instructions. No fudging forward.

**Rigid questionnaires.** When asking user for input, format is structured (numbered questions, expected answer types), not freeform conversation.

**Verification at every step.** Each point ends with verification checks. Fails → halt and surface. No moving forward until verification passes.

**No skipping.** Even if user says "I already did that" — ritual verifies state file. If state file says incomplete, the step runs.

### 2.4 Questionnaire pattern

For inputs requiring human judgment, the ritual presents a structured checklist:

```
POINT 5: PERSONA INPUT REQUIRED

Please provide the following:

1. First name:
2. Last name:
3. Location (city, state/country):
4. Domain expertise (one sentence):
5. Voice characteristics (warm/direct/formal/technical/playful — multiple OK):
6. Brief bio (2-3 sentences):
7. Path to byline photo:
8. Path to about photo:

Photos must be real (not template placeholders). Build will halt if MD5 matches existing portfolio persona photos.
```

User answers each. Ritual proceeds only when all required fields are populated and verification passes.

### 2.5 Resumability

State file at `~/affiliate-platform/sites/<slug>/state.yaml` records:

```yaml
slug: example-site
domain: example.com
started: 2026-05-08T10:00:00Z
current_point: 5
points_complete: [1, 2, 3, 4]
inputs:
  niche_statement: "..."
  density_score: 70
  keyword_research_xlsx: "/path/to/file.xlsx"
  domain: example.com
  persona_name: "Sarah Collins"
```

Running `/launch-site --resume <slug>` picks up at the current_point. Inputs already provided don't get re-asked.

### 2.6 What this gives you

- Every site goes through the same gates
- No "I forgot to set up X" — gates enforce
- Resumable from any point if interrupted
- Observable progress via state file
- Operational discipline encoded in the tool, not in your head

The ritual is the highest-priority platform addition before site 4.

### 2.7 Autonomous-launch enforcement model (v1.6)

The ritual now operates under explicit autonomy boundaries. Every step is either:

- **Autonomous** — Claude Code executes without asking. Decision policy documented in this PIPELINE.md.
- **Keith identity-bound** — Requires Keith's credentials, accounts, or identity. Ritual halts and surfaces a structured request.
- **Keith decision-bound** — Requires Keith's strategic judgment (niche selection, domain selection, persona biographical details). Ritual halts and surfaces a structured questionnaire.

The ritual never defers decisions to Keith that have a documented default policy. If the runbook says Claude Code derives brand colors from niche, the ritual derives them. Keith reviews and overrides at preview time, not at decision time.

Section 16 (Autonomous launch enforcement) specifies which decisions fall into which bucket and what the policies are for each autonomous decision.

---

## 3. The 21-point per-site launch pipeline

Each point describes: what it does, what it produces, what tools are involved, what's automatable, what requires judgment, decision points, verification, and failure modes.

These are the steps the launch-site ritual executes.

---

### Point 1: Niche selection

**What it does:** Pick the topic the site will be about.

A niche is narrow enough to credibly own, broad enough to support 250-300+ articles.

**What it produces:** A one-line niche statement.

**Critical check — Amazon density:**

Search Amazon for 10 representative product types in the niche. Count clean Amazon-sold listings with strong reviews.

**Default threshold:** 60%+ density (6 of 10) is the typical comfortable zone. Below 60% is a judgment call requiring conscious decision about monetization path before proceeding. The ritual surfaces below-60% as a halt-and-confirm, not auto-reject.

**Tools:** External — Amazon search via browser. `tools/check-niche-density.mjs` could automate this; currently manual.

**Verification:**

- Niche statement written
- Amazon density check performed and documented
- If density < 60%, explicit override with justification documented

**Failure modes:**

- Niche too narrow (can't generate 300 articles)
- Niche overlaps existing portfolio sites
- Low Amazon density without alternative monetization path

---

### Point 1.5: Amazon availability assessment

**What it does:** Quantifies what share of the niche's products are actually sold on Amazon before committing to keyword research or catalog sourcing.

**Why it matters:** Niches vary dramatically in Amazon coverage. A site built assuming 80% Amazon availability that turns out to be 40% Amazon will have thin product cards, high NOT_ON_AMAZON rates, and low affiliate revenue. This assessment sets expectations and determines the sourcing strategy before any catalog work begins.

**Method:** Run Rainforest API on 20-30 representative search queries from the niche (not individual ASINs — keyword searches). Count the fraction that return ≥3 qualified Amazon-sold listings.

**Three-tier response framework:**

| Amazon rate | Strategy |
|---|---|
| ≥70% Amazon | Launch Amazon-only. Honest editorial framing: "the best [category] you can buy on Amazon." No pre-seeding needed. |
| 50–70% Amazon | Pre-seed 10–20 priority brand-direct products (via brand affiliate programs or brand.com links) before producer run. These cover the most-searched premium brands that don't sell on Amazon. |
| <50% Amazon | Pre-seed extensively or explicitly position the site as the "Amazon tier of [niche]." Consider whether the niche is viable without broader affiliate programs. |

**Northwoods Overland example (validated 2026-05-18):** Overlanding sits at ~55–60% Amazon. Premium brands (Prinsu, ARB specialty hardware) are DTC-only. Correct response: source Amazon products for the bulk catalog, retitle brand-specific articles to generic alternatives where the brand has no Amazon presence.

**Output:** Single documented decision — which tier, what sourcing strategy, any pre-seeding list.

**Failure modes:**

- Skipping this step leads to post-generation brand-mismatch audits (fixable but expensive — see brand-mismatch audit Northwoods remediation)
- Treating NOT_ON_AMAZON as a per-article surprise rather than a niche-level characteristic

---

### Point 2: Keyword research

**What it does:** Generate the article topic list with full metrics for each keyword.

**What it produces:** An xlsx file with one row per article, plus three supporting sheets.

**Required columns:**

Category, Hub, Hub Slug, Hub URL, Keyword, Slug, Locked URL, Article Type, Required Product Count, Angle, H2 Structure, Volume, KD, CPC, Intent, Quality, AI Overview flag, Premium Brand flag, Source Seed.

**Required sheets:**

- Launch — articles being built at launch
- Site Architecture — categories, hubs, article counts per hub
- Hub Strategy — AOV tier, notes per hub
- Reserve Pool — additional keywords for future expansion

**Default targets (judgment, override per niche):**

- Launch article count: 300
- Reserve Pool count: 500
- Minimum search volume: 100/month
- Maximum keyword difficulty: KD 40
- Intent filter: Commercial + Transactional + Informational

**Tools:** External keyword research tool (Ahrefs, SEMrush).

**Verification:**

- xlsx exists with all required columns populated
- All four sheets present
- Launch sheet row count matches target
- No duplicate slugs across Launch and Reserve Pool

**Failure modes:**

- Keyword volume estimates inflated
- Keywords accepted with no real Amazon affiliate path
- Slug duplicates
- Article type misassigned

---

### Point 3: Article pipeline (pipeline.json)

**What it does:** Convert the keyword research xlsx into pipeline.json.

**What it produces:** `data/pipeline.json` in the site repo. One JSON object per article with: id, slug, hub, category, type, keyword, angle, H2 structure, product_count target, products array (initially empty), hero_image (empty until point 12), body_images (empty until point 12).

**Tools:** `tools/xlsx-to-pipeline.mjs --input <xlsx> --output data/pipeline.json` (needs to be built).

**Verification:**

- Total article count matches xlsx row count
- Every article has a valid hub from site config
- Every article has a valid type
- Every slug is unique

**Failure modes:**

- xlsx has a hub not present in site config
- Article type column has invalid value
- Pipeline.json schema mismatch

---

### Point 4: Domain / brand name

**What it does:** Source a suitable domain, verify its profile, register it.

**Process:**

1. Search expireddomains.net filtered against the niche
2. Check backlink profile in SEMrush for candidates
3. Optional: Wayback Machine check
4. Apply judgment — does this domain have enough residual SEO value?
5. If no suitable expired domain exists, register a fresh domain
6. Register through Cloudflare

**Domain selection is judgment, not gates.** Considerations: age, backlink quality, referring domains count, TLD preference, Wayback content history.

**Tools:** External — expireddomains.net, SEMrush, Cloudflare.

**Hard pause if:** No suitable domain available.

**Verification:**

- Domain shows in Cloudflare dashboard under Registrar
- WHOIS shows you as registrant
- DNS resolves
- Backlink profile reviewed

**Failure modes:**

- Suitable expired domain not found within reasonable search effort
- Toxicity discovered post-registration
- DNS misconfigured

---

### Point 5: Persona

**What it does:** Define the human voice readers will attribute the site's recommendations to.

**Required inputs (rigid questionnaire):**

1. First name
2. Last name
3. Location
4. Domain expertise (one sentence)
5. Voice characteristics
6. Banned phrases (or use platform defaults)
7. Brief bio (2-3 sentences)
8. Path to byline photo
9. Path to about photo

**What it produces:**

- `config/personas/<persona-slug>.yaml`
- `public/images/brand/<persona-slug>-byline.jpg`
- `public/images/brand/<persona-slug>-about.jpg`

**Photo source: AI-generated (v1.6 locked).** Tool: `tools/generate-persona-photos.mjs`. Template: `~/affiliate-platform/templates/persona-photo-prompt.md`. "Judgment per site" framing retired — inconsistent quality across cohort. Photos are generated, not user-provided.

**Photo presence: gated.** Hard pause if photos aren't in-place. No placeholder MD5 of another site's persona.

**Voice depth: basic notes + banned phrases default.** Detailed style guide override-able if specific niche warrants.

**v1.6 persona YAML required fields (in addition to base fields):**

```yaml
# v1.6 additions
persona_locked: false
locked_at: null
content_hash: null

# Voice inheritance — read by both narrative and card generators
voice_register: first_person
first_person_pronouns: ["I've owned", "I've used", "I've tested", "my", "I've found"]
forbidden_self_reference: ["the engineer", "the writer", "this site's author"]

# Spec compliance fields — read by validate-persona-spec-compliance
owned_gear: [<list of products persona has used>]
home_territory: [<list of locations persona has experience in>]
defers_to:
  - name: <Expert Name>
    domain: <expertise area>
forbidden_claims: [<patterns persona must never make>]

# Demographic anchors — read by validate-persona-spec-compliance
family: {partner_name: null, kids: null, pets: null}
career: <profession>
tenure_years: <number>
tenure_start_year: <year>
```

**Persona lock procedure (v1.6 hard gate):**

1. All required fields populated
2. Both photos exist and pass MD5-uniqueness check against portfolio
3. Persona YAML committed to repo
4. Lock command: `tools/lock-persona.mjs --site <slug>` — sets `persona_locked: true`, `locked_at`, and `content_hash`
5. Producer at Point 13 verifies `persona_locked: true` AND content hash matches before running

**Unlock procedure (rare):** `tools/unlock-persona.mjs --site <slug> --reason "<rationale>"`. Reason logged to `~/affiliate-platform/persona-unlock-log.yaml`. Re-lock required before producer can run again.

**Verification:**

- Persona yaml exists at correct path
- All required fields populated including v1.6 additions (no `{{TOKEN}}` remaining)
- Both photos exist
- Photos are NOT placeholder MD5 of any other portfolio site's persona
- `persona_locked: true` set before producer runs
- Producer reads this persona file

**Failure modes:**

- Photo MD5 matches another portfolio site's persona
- Persona yaml has placeholder tokens remaining
- Voice notes inconsistent with niche
- Producer runs before persona is locked (v1.6 hard gate — producer refuses)

---

### Point 6: Visual identity

**What it does:** Establish the visual brand — colors, logo, favicon — before site shell consumes them.

**Brand colors: Claude Code derives from niche understanding.** You override if you don't like it.

**5 standardized visual slots** in `site.config.yaml` under `visual:`: 3 colors (`primary_color`, `accent_color`, `background_color`) and 2 typography fields (`font_headings`, `font_body`).

**Logo: Claude Code generates.** Header SVG (color on light) and footer SVG (white on dark). Favicon derived from logo mark.

**What it produces:**

- `public/images/brand/logo-header.svg`
- `public/images/brand/logo-footer.svg`
- `public/favicon.ico` and `public/favicon.svg`
- 5 visual slot values committed to `site.config.yaml` (repo root)

**Verification:**

- Both logo SVG files render correctly at 240x40 viewport
- Favicon displays in browser tab
- 5 visual slots populated (no `{{TOKEN}}` remaining)
- No FSG/MLT/OHT identifiers in logo or color values

**Failure modes:**

- Logo inherited from template
- Color values inherited from template
- Favicon missing

---

### Point 7: Site shell (technical scaffolding)

**What it does:** Build the technical site repo from template, configured for the new site identity.

**Tools:** `tools/initialise-site.mjs` — needs to be built.

**What it produces:**

- Astro config pointing at the right domain
- `site.config.yaml` (repo root) with site name, domain, brand colors, hubs, categories, GA4 placeholder
- `config/navigation.yaml` matching hub structure
- `config/personas/<persona-slug>.yaml` (from point 5)
- `producer/<site-slug>-producer-v2.py` thin shell calling platform producer
- `producer/indexnow-submit.py` with site-specific User-Agent
- `producer/tests/*.py` with site-specific hub fixtures
- `public/images/brand/<persona>-byline.jpg`, `<persona>-about.jpg` (from point 5)
- `public/images/brand/logo-header.svg`, `logo-footer.svg` (from point 6)
- `public/<32-char-hex>.txt` IndexNow key file
- `wrangler.toml` with `name = "<site-slug>"` and `[vars] NODE_VERSION = "22"`
- `affiliate-platform/` submodule pinned to current platform commit
- `data/pipeline.json` populated (from point 3)
- `content/products/products.yaml` empty
- `content/articles/` empty (at shell creation; populated after Point 14 publish)
- `staging/` empty (producer's output destination)
- `.gitignore`, `package.json`, `tsconfig.json`

**Technical SEO included via platform defaults:**

- Schema markup (Article, Product, BreadcrumbList, FAQPage, Organization, Person)
- Meta tags (title, description, canonical, robots, Open Graph, Twitter Card, language)
- Sitemap structure
- robots.txt with sitemap reference
- URL structure (trailing slashes, kebab-case slugs)
- Image optimization (webp, sized variants, lazy loading)
- Internal linking
- Cookie consent (Consent Mode v2 with localStorage gating)
- Affiliate click tracking (GA4 events with link_position)
- Affiliate link resolution (rehype-product-links plugin transforms `product:slug` at build time)

**Verification:** `tools/verify-site-shell.mjs`:

- No FSG/MLT/OHT identifiers in the new site (template inheritance check)
- All required files exist
- Producer test fixtures match site hubs
- Submodule pin is current
- wrangler.toml name matches site slug
- 5 visual slots populated (`primary_color`, `accent_color`, `background_color`, `font_headings`, `font_body`)
- No `{{PLACEHOLDER_TOKEN}}` text remaining anywhere
- (v1.6) `grep "{{" public/images/brand/*.svg` returns no matches — no SVG asset contains unsubstituted placeholder tokens
- (v1.6) `package.json` build script includes `rm -f node_modules/.astro/data-store.json` as pre-build step
- (v1.6) `config/dtc-brands/<niche>.yaml` exists for the site's niche
- (v1.6) `config/category-types/<niche>.yaml` exists for the site's niche

**Failure modes:**

- Template inheritance not fully cleaned
- Wrangler.toml has wrong name
- Persona/logo files are placeholders
- Submodule not pinned, points to floating HEAD
- Placeholder tokens remaining
- (v1.6) SVG brand assets contain unsubstituted `{{` placeholder tokens
- (v1.6) Astro cache invalidation step missing from build pipeline
- (v1.6) Niche-specific config files missing (DTC brand list, category type list)

---

### Point 8: Site furniture (about, contact, compliance pages)

**What it does:** Create static content pages every site needs.

**Pages required:**

- About page — uses persona content from point 5, plus site mission statement
- Contact page — contact form (no email displayed)
- Affiliate disclosure
- Privacy policy
- Cookie policy (or merged into privacy)
- Terms of use (optional)

**Furniture template families (v1.2):** Furniture pages are generated from vertical-aware templates, not generic find-and-replace from prior sites. Site declares its template family in `site.config.yaml`:

```yaml
furniture_template_family: ymyl   # or: lifestyle
```

Available families:
- `lifestyle` — non-YMYL sites (e-bikes, overlanding, kitchen, gardening, sauna). Standard affiliate framing, research-based methodology.
- `ymyl` — YMYL sites (hearing aids, medical, health-adjacent). Adds explicit medical advice disclaimer, OTC-vs-prescription guidance, health data privacy note. Use for BetterHearingHub and any future health/financial vertical.

Templates live at `~/affiliate-platform/templates/furniture/<family>/`. Copy the appropriate family into `src/pages/` at Point 7 (site shell), then customise for the site's niche copy.

**Legal text source:** Claude Code generates from templates at `~/affiliate-platform/templates/furniture/` with the appropriate family selected for the vertical.

**Contact form:** FormSpree (existing portfolio pattern — single shared endpoint across portfolio routing to your personal email).

**Cookie consent:** Already implemented platform-wide via Consent Mode v2 with localStorage gating.

**Site mission statement input (rigid questionnaire):**

```
POINT 8: SITE MISSION STATEMENT REQUIRED

In 1-2 paragraphs, what does this site stand for? Who is it for?

Mission:
```

**Verification:**

- All required pages exist at expected URLs
- Footer links to all of them
- Affiliate disclosure visible above the fold on article pages
- Pages render with correct site name (no template inheritance, no placeholder tokens)

**Point 8 close gate — furniture-page validator (v1.2):**

```bash
node affiliate-platform/scripts/validate-furniture-pages.mjs --site <slug>
```

Must pass (exit 0) before Point 9. Checks:
- HARD persona-claim violations in all furniture pages (same FTC-risk patterns as Point 13.5 checks in articles)
- Previous-vertical vocabulary bleed (configure in `config/furniture-validation.yaml`)

If no `config/furniture-validation.yaml` exists, bleed detection is skipped. For sites where carryover risk exists, author the forbidden vocabulary config before Point 8 close.

**Failure modes:**

- Pages missing entirely (Amazon enforcement risk)
- Pages have wrong site name in copy (template inheritance)
- Contact form FormSpree endpoint wrong
- Persona-claim violations in furniture pages (FTC risk — same severity as article violations)
- Prior-vertical vocabulary bleed (professional credibility risk)

---

### Point 9: Amazon Associates tracking ID

**What it does:** Register a tracking ID with Amazon for the site, configure in code and Cloudflare.

**Process (v1.6 updated — split by actor):**

**Keith identity-bound (Bucket C):**
1. Log into Amazon Associates dashboard
2. Create a new tracking ID: `<site-slug>-20` (Claude Code proposes the string; Keith creates it with that exact string)
3. Confirm creation in dashboard; provide string to Claude Code

**Claude Code autonomous (Bucket A):**
1. Set `affiliate.amazon_tracking_id` in `site.config.yaml`
2. Configure env vars via Cloudflare API (no dashboard):
   ```
   tools/cloudflare-pages-config.mjs set-env --site <slug> --env production --key AMAZON_TAG --value <tracking-id>
   tools/cloudflare-pages-config.mjs set-env --site <slug> --env preview --key AMAZON_TAG --value <tracking-id>
   ```
3. Update `portfolio.yaml` via `tools/portfolio-update.mjs`

**Hard pause if:** Amazon Associates rejects the tracking ID application.

**Single Amazon Associates account supports up to 50 sites.** Portfolio of 100 sites can use one account; tracking IDs are the per-site identifier.

**Verification:**

- Tracking ID exists in Amazon Associates dashboard
- `site.config.yaml` `affiliate.amazon_tracking_id` matches Amazon Associates ID
- If Cloudflare env var is set: Production AND Preview match site.config.yaml value
- Live affiliate link contains correct `?tag=<tracking-id>` after rehype plugin resolution

**Failure modes:**

- Tracking ID copy-pasted from another site
- Cloudflare env var set but mismatches site.config.yaml value
- Tracking ID hardcoded in platform code

---

### Point 10: Source products + ASINs per article

**What it does:** For each article in pipeline.json, source 1-7 real Amazon-stocked products by searching for that article's keyword.

**The principle:** Per-article fresh sourcing. No bucket. No invented brands. No products generated from memory.

**Per-article product counts:**

- buyer_guide: 5 products
- roundup: 7 products
- comparison: 2 products
- review: 1 product

**Canonical workflow — Rainforest API (recommended for all production runs):**

**(v1.6) Policy filters apply automatically:** brand-string match required, category match required, known-DTC-brand fallback, seller-prefix scrub (e.g. `STOVER Patagonia` → `Patagonia`). Requires `config/dtc-brands/<niche>.yaml` and `config/category-types/<niche>.yaml` to be present; tool refuses to source without them.

```
# Step 1: Bulk source products for all articles with empty products[]
python3 tools/source-products-rainforest.py --site <slug>

# Step 2: Generate real pros/cons for every product via Claude Haiku
python3 tools/generate-product-pros-cons.py --site <slug>

# Step 3 (optional): Resolve any remaining VERIFY entries with a second Rainforest pass
python3 tools/resolve-verify-asins.py --site <slug>
```

**Prerequisites:** `RAINFOREST_KEY` and `ANTHROPIC_API_KEY` in `<site_root>/config/credentials.env`. The `config/credentials.env` stub is created by `initialise-site.mjs` Phase 1.

**Cost transparency (300-article site):**

| Step | Cost |
|---|---|
| source-products-rainforest.py | ~$1.50–3.00 (1 call/article × ~$0.005–0.01/call) |
| generate-product-pros-cons.py | ~$0.80–1.00 (1,300 products × ~$0.0007/product via Haiku) |
| resolve-verify-asins.py | ~$0.25–0.50 (typically 50–80 VERIFY entries) |
| **Total realistic** | **~$3–7 for a 300-article site** |

**Resume support:** All three tools write a state file to `/tmp/<tool-name>-<slug>-state.json`. If interrupted, rerun with `--resume` to skip already-processed entries.

**Deprecated alternative — Amazon scraping:**

`tools/source-products-per-article.mjs` uses LLM + Amazon scraping. It rate-limits at scale (hits blocks within ~30 articles on a 300-article run). Retained for small jobs (< 30 articles) and smoke testing. Do not use for production bulk runs.

**What it produces:**

- pipeline.json article entries with populated `products: []`
- `content/products/products.yaml` populated with unique products
- All ASINs are real (B0...) or NOT_ON_AMAZON
- All products have `default_pros` and `default_cons` (generated by step 2)

**Verification:**

- All articles have minimum products assigned for their type
- products.yaml has zero VERIFY entries
- All ASINs match format `B0[A-Z0-9]{8}` or value is `NOT_ON_AMAZON`
- All products have non-placeholder `default_pros` / `default_cons`
  (`grep -c "Well-reviewed\|Strong customer ratings" content/products/products.yaml` → 0)

**Brand-enrichment pass (required after sourcing):**

After Rainforest sourcing completes, every product in products.yaml must have a populated `brand:` field. Null brand entries suppress PASS scores in the brand-match audit, causing false FAILs and triggering unnecessary article regeneration.

```bash
# Check coverage — must return 0 before proceeding
node affiliate-platform/scripts/validate-catalog-brand-coverage.mjs --site <slug>
```

If non-zero: for each null-brand product, look up the manufacturer name and set `brand: <Name>` manually, or re-run Rainforest with a brand-specific query for that product.

**Northwoods Overland lesson:** 60%+ of initial catalog had `brand: null`. DECKED, ARB, and Yakima products existed in the catalog with correct ASINs but unbranded entries, which masked valid brand-match assignments and required a post-launch enrichment pass.

**Failure modes:**

- Picking product variants that don't match article topic
- High NOT_ON_AMAZON rate in premium-brand niches (judgment: accept or find substitutes)
- RAINFOREST_KEY not set — tool exits with clear error pointing to credentials.env
- Skipping brand-enrichment pass → false FAILs in brand-match audit
- (v1.6) DTC brand list missing for niche — `source-products-rainforest.py` refuses to source until `config/dtc-brands/<niche>.yaml` is present
- (v1.6) Category type list missing for niche — tool refuses to source until `config/category-types/<niche>.yaml` is present

---

### Point 11: Source image bank

**What it does:** Source 150 unique topical images from Pexels for the site, organized by hub.

**Locked specs:**

- **Minimum** 150 images per site (v1.6: no upper limit, but image bank must be hub-balanced — no hub >2x the average count per hub). Cohort showed counts 150–1,330; hard ceiling was removed as not beneficial.
- 1200x630, 16:9 aspect ratio
- Hub-based naming: `<hub>-1.jpg`, `<hub>-2.jpg`, etc.
- Sourced from Pexels API
- Stored at `public/images/articles/`

**Post-launch upgrade:** Traffic winners get DALL-E upgrades (operational layer, not launch).

**Tools:** `tools/source-images-pexels.mjs` — needs to be built.

**Verification:**

- 150 images downloaded
- Images are webp format
- Images organized by hub with sequential numbering
- All images at 1200x630 minimum

**Failure modes:**

- Pexels API rate limit hit
- Images not optimized
- Topic mismatches

---

### Point 12: Assign images per article

**What it does:** Walk pipeline.json, assign image references per article from the topical pool.

**Default:** 1 hero + 4 body images per article (5 total). Body images injected at 4 fixed structural positions (after intro H2, after Top Picks H2, after How to Choose H2, after FAQ H2).

**Per-site override:** `site.config.yaml` under `style_policy.in_body_images`. Permitted modes:
- `policy: 'fixed_count', fixed_count: N` — exact body image count per article
- `policy: 'per_product'` — one image per product mention in body
- `policy: 'none'` — no body images (hero only)

Sites pick a policy at initialisation and stick with it; changing policy mid-life requires regenerating affected articles.

**Selection algorithm:** Random within hub. Hero and body images selected from the hub's image pool.

**What it produces:**

- pipeline.json article entries with populated `hero_image:` and `body_images: [...]`

**Tools:** `tools/assign-article-images.mjs`

**Verification:**

- Every article has hero_image and body_images populated per site policy
- All referenced images exist in image bank

**Failure modes:**

- Image bank too small for article count
- Image references broken
- Policy changed after initial article generation without regeneration pass

---

### Point 12.5: Brand-match audit gate

**What it does:** Validates that every article whose headline keyword contains a brand name has at least one assigned product that carries that brand in products.yaml.

**Run:**

```bash
node affiliate-platform/scripts/validate-brand-match.mjs --site <slug>
```

Exits 0 if no FAILs. Exits 1 if any FAILs. Writes `brand-mismatch-audit.md` to the site root.

**Do not proceed to Point 13 (article generation) until this passes.**

**Remediation paths for FAIL articles:**

| Situation | Action |
|---|---|
| Brand sells on Amazon, products exist in catalog but unbranded | Enrich `brand:` field in products.yaml (Point 10 brand-enrichment pass) |
| Brand sells on Amazon, products not yet in catalog | Source via Rainforest using brand name as query; add to catalog; assign to article |
| Brand has no Amazon presence | Retitle article to remove brand from keyword; assign generic alternatives; regenerate |

**Retitle-to-generic strategy (validated Northwoods 2026-05-18):** When a brand has no Amazon presence (DTC-only, specialty-only), change the article's `keyword` in pipeline.json to a generic variation that covers the same search intent without naming the brand. The URL slug stays unchanged to preserve any links. Regenerate the article with `--force`.

- Example: `prinsu roof rack 4runner` → `platform roof rack 4runner`
- Example: `sherpa roof rack` → keep — Sherpa products were added as new ASINs

**PARTIAL articles** (exactly 1 brand-matching product): Not blocking — proceed to Point 13 and note in backlog. PARTIALs in a brand cluster are often resolved automatically when FAIL articles in the same cluster are fixed (the regenerated articles draw from the now-enriched catalog).

**Companion validator:**

```bash
# Also confirms all products have brand populated (prerequisite for accurate audit)
node affiliate-platform/scripts/validate-catalog-brand-coverage.mjs --site <slug>
```

---

### Point 13: Article generation

#### 13.0 Producer prerequisites (v1.6)

Before producer runs, the ritual confirms all of the following. Any missing prerequisite is HARD failure — producer refuses to start.

1. `persona_locked: true` in persona YAML **and** current content hash matches locked hash
2. All articles in pipeline.json have `products[]` assigned
3. All articles in pipeline.json have `hero_image` and `body_images[]` assigned
4. `products.yaml` has zero `VERIFY` entries
5. `products.yaml` has 100% `brand:` coverage (no null brand fields)
6. `products.yaml` has 100% `category_type` coverage
7. `config/dtc-brands/<niche>.yaml` exists
8. `config/category-types/<niche>.yaml` exists

**What it does:** Producer runs against fully populated pipeline.json (products + images + article configs), generates one .md file per article.

**Run mode:** Foreground with `tee` to log file.

**Output destination:** Producer writes to `staging/`. Articles move to `content/articles/` in point 14 after regeneration is complete.

**Command:**

```
python3 producer/<site-slug>-producer-v2.py --site ~/<site-slug> --count 300 2>&1 | tee logs/produce-300.log
```

Runs unattended for 1.5-3 hours.

**Producer changes needed for v1.8.0:**

- Embed `hero_image` in frontmatter from pipeline.json
- Embed body images at predictable positions in markdown (after intro H2, after Top Picks H2, after How to Choose H2, after FAQ H2 — 4 fixed positions)
- Affiliate links already use `product:slug` format (verified — no change needed)

**Verification:**

- All articles in pipeline.json got attempted (no silent skips)
- Pass/fail counts surfaced
- Failure distribution by validator rule surfaced

**Pipeline.json persistence (v1.2 — verified):** Manual edits to `pipeline.json` made while the producer is between runs (skip flags, product corrections, hub taxonomy) persist across restarts. `save_pipeline()` reads the current disk state and merges only status fields (`status`, `staged`, `published`, `fail_count`) from the in-memory pipeline — structural edits (products, keywords, hub) are never overwritten.

**Warning — `generate-pipeline.py` is destructive:** The `data/generate-pipeline.py` script in each site repo regenerates `pipeline.json` from scratch from the launch xlsx. Running it after manual patches are applied will lose all patches. Never run `generate-pipeline.py` after catalog sourcing (Points 10-12) has begun. If regeneration is needed, export manual patches first and reapply.

**Failure modes:**

- Producer skips articles silently
- Model rate limits / API errors mid-run
- Persona file missing or empty
- products.yaml missing for some pipeline products
- `generate-pipeline.py` run after manual patches applied (data loss)

---

### Point 13.5: Persona-claim audit gate

**What it does:** Scans all staged/published articles for first-person testing and editorial voice violations before deploy.

**Run:**

```bash
node affiliate-platform/scripts/validate-persona-claims.mjs --site <slug>
```

**Two violation tiers:**

| Tier | Patterns | Response |
|---|---|---|
| HARD | "I tested", "I've owned", "In my testing", "When I tested this", "after N weeks of testing this" | Fix before deploy. FTC risk. Exit 1. |
| SOFT | "I'd argue", "I'd move", "I'd recommend", "I'd suggest", "I'd lean", "I'd prefer" | Log to refinement backlog. Not blocking. Exit 0 with count. |

**HARD violations must be fixed before Point 14 (publish).** Acceptable fixes:
- Remove the claim entirely ("I'd argue the labor cost is justified" → "the labor cost is justified")
- Replace with sourced framing ("owner reviews report that...")
- Regenerate the article with `--force` (producer-side Check 6 catches the pattern at generation time)

SOFT violations are lower-urgency but represent editorial voice drift that weakens the persona's credibility. Add to refinement backlog and fix in the next editorial pass.

**Producer-side enforcement:** `check_output_shape()` in `article_builder.py` catches both HARD (Check 5) and SOFT (Check 6) patterns at generation time, causing immediate retry. The standalone audit tool serves as a second-pass sweep across the already-published catalog.

**V18 retroactive remediation — owned-place attribution pattern (validated 2026-06-05):**
When patching HARD V18 violations in published corpora, the most effective and persona-preserving technique is *owned-place attribution*: replace the personal ownership claim with a reference to the persona's location or context ("in this kitchen", "in this garage", "in use", "tested here"). This removes the fabricated ownership while keeping the persona's voice and authority intact. Examples from Day 8 remediation across 4 sites: "I've owned mine for six years" → "This knife has been in this kitchen for six years"; "I've tested several options in my own garage" → "Several options have been tested in this garage through Portland winters". Universal-truth framing ("Both were tested with béchamel...") and gerund subjects ("Testing covered three very different approaches...") are acceptable alternatives when place-anchoring feels forced. See Tier A/B/C decomposition in `COHORT_AUDIT_REPORT.md` for the full method.

**Relationship to 13.5b (v1.6):** This validator catches first-person testing claims by regex pattern. Point 13.5b performs semantic comparison against the locked persona YAML for owned-gear, partner-name, geographic, tenure, and defers-to claims. Both validators run — they catch different failure modes.

---

### Point 13.5b: Persona-spec compliance audit gate (v1.6)

**What it does:** Compares first-person claims in staged article bodies against the locked persona YAML. Catches the Site 13 class of fabrication: wrong gear (E50/L50 vs Modi+/Magni+), wrong partner name (Sam vs Hannah), wrong geography, wrong tenure, hallucinated defers-to names.

**Run:**

```bash
node affiliate-platform/scripts/validate-persona-spec-compliance.mjs --site <slug>
```

**What it checks against persona YAML fields:**

| Field | Check |
|---|---|
| `owned_gear` | Any gear claimed to be owned/used must be in this list |
| `family.partner_name` | Partner name in article must match this field |
| `home_territory` | Geographic claims must be in this list |
| `career` | Career/profession claims must match |
| `tenure_years` / `tenure_start_year` | Tenure duration claims must be consistent |
| `defers_to` | Any expert attribution must be in this list |
| `forbidden_claims` | Patterns in this list must never appear |

**HARD violation:** Any fabricated claim that contradicts the locked persona spec. Exit 1. Must fix before Point 14.

**Fix:** Regenerate with `--force --id <N>` (maximum 3 attempts). After 3 attempts, article moves to skip-list.

**Implementation note:** Requires an LLM-pass per article via Haiku. Estimated cost: ~$0.001–0.01 per article (~$0.30–3.00 for a 300-article site).

---

### Point 13.6: Image markdown validator gate (v1.2)

**What it does:** Scans all staged articles for image markdown with invalid URLs — specifically the producer bug that emits Python dict literals as image URLs (`![alt]({'alt': 'x', 'path': 'y.webp'})`).

**Run:**

```bash
node affiliate-platform/scripts/validate-image-markdown.mjs --site <slug>
```

**What it catches:**
- Dict-literal URLs (the Ten27/Northwoods bug: 919 and 1,155 instances respectively)
- Unresolved `{{ template syntax }}` in image URLs
- Whitespace in local image paths
- Local paths with no valid image extension (.webp, .png, .jpg, .jpeg, .gif, .svg, .avif)
- Empty URLs

**HARD violation:** Any image with an invalid URL will render as a broken `<img>` tag (literal placeholder text or no image). Exit 1. Must fix before Point 14.

**Fix:** Run `python3 affiliate-platform/scripts/fix-image-markdown.py --site <slug> --dry-run` to preview, then without `--dry-run` to apply.

**Failure modes:**
- Producer emits dict-literal URLs (older producer versions — check is the fix)
- Images with missing extensions get flagged — confirm the extension is intentional

---

### Point 13.7: Meta-leakage validator gate (v1.6)

**What it does:** Scans staged article bodies for producer-internal reasoning that leaked into article content. Catches the Site 14 class of issue where the producer's brief-reasoning appeared verbatim in the marantz-vs-anthem-vs-denon article body.

**Run:**

```bash
node affiliate-platform/scripts/validate-meta-leakage.mjs --site <slug>
```

**Patterns flagged (regex, case-insensitive):**

- `\bthe brief\b`
- `\bprompt system\b`
- `\bh2_structure\b`
- `\bbrief specifies\b`
- `\bpersona's defer-to\b`
- `\bbrief also specifies\b`
- `\barticle type defined in\b`
- `\bformat governs\b`

**HARD violation:** Exit 1. Must fix before Point 14. Fix: delete leaked reasoning block and regenerate with `--force`.

---

### Point 13.8: Card-voice density validator gate (v1.6)

**What it does:** Checks that product cards in buyer-guide articles use the persona's first-person voice, not third-person or agentless voice. Catches the Site 15 class of issue where Greg's locked persona produced first-person narrative prose but depersonalized buyer-guide card copy.

**Run:**

```bash
node affiliate-platform/scripts/validate-card-voice.mjs --site <slug>
```

**What it checks:** Proportion of product cards that contain first-person pronouns from `voice_register` / `first_person_pronouns` in persona YAML. Cards with zero first-person markers are flagged.

**SOFT violation:** Logged to calibration-log.yaml. Not blocking. Exit 0 with count.

---

### Point 13.9: Product slug resolution validator gate (v1.6)

**What it does:** Validates that every `product:<slug>` reference in staged article markdown resolves to a key in `products.yaml`. Catches the Site 15 class of issue where `product:aventik-eupheng-riverruns-yarn` was referenced but the products.yaml key was `aventik-eupheng-riverruns-yarn-strike` — build succeeded, but the rendered affiliate link was broken.

**Run:**

```bash
node affiliate-platform/scripts/validate-product-slug-resolution.mjs --site <slug>
```

**HARD violation:** Exit 1. Must fix before Point 14. Fix: correct the slug reference in the article or add the missing product to products.yaml.

---

### Point 14: Regeneration pass and publish

**What it does:** Regenerate failed articles once in staging, then move all staged articles to content/articles/.

**No iterative calibration cycles per site.**

**Process:**

1. Identify articles in `staging/failed/` after first generation
2. Regenerate each once with `--force --id N` (writes back to staging/)
3. Articles still failing after regeneration: hand-edit in staging/, drop, or accept (judgment per article)
4. Soft fails ship with logged warning to calibration-log.yaml
5. Strip any validator output appended to failed articles
6. **(v1.6) Skip-list check:** Before moving any article, `publish-staging.mjs` reads `data/skip-list.yaml`; any article on the skip-list is excluded from the staging-to-content move regardless of pass/fail status.
7. Move all non-skip-listed staged articles to `content/articles/` via `tools/publish-staging.mjs`
8. Verify count matches expected publish count

**Hard fail rate consistently above threshold (>5%) across multiple sites becomes a platform-level review.**

**Tools:** `tools/publish-staging.mjs` — needs to be built. Moves files from staging to content/articles/, strips validator output, reports counts.

**Verification:**

- All articles in content/articles/ are publishable
- Hard fail count = 0
- Soft fail count surfaced and accepted
- After a publish run completes, `staging/` and `staging/failed/` contain only files from the current pending batch (failed regenerations or unapproved drafts). Across the lifecycle of a live site, these directories accumulate artifacts of in-flight work — they are not asserted empty as a steady state.
- (v1.6) Skip-list cross-check: for each slug in `data/skip-list.yaml`, confirm no `.md` file exists in `content/articles/` for that slug

**Failure modes:**

- Persistent hard fails on a small set of articles
- Calibration drift if validators get widened during a site (forbidden)
- Validator output not stripped before publish (causes Astro build issues)

---

### Point 15: Local build smoke

**What it does:** Verify the site builds locally before pushing.

**Command:**

```
cd ~/<site-slug>
npm install  # first time only
npm run build
```

**(v1.6) Cache invalidation pre-step:** The `npm run build` command deletes `node_modules/.astro/data-store.json` before invoking `astro build`. This prevents the Site 15 class of failure (91 articles with empty body content from stale cache entries). Updated build script:

```json
"build": "rm -f node_modules/.astro/data-store.json && astro build && npx pagefind && node build-validator.mjs"
```

**Build runs build-validator** which checks for VERIFY entries, NOT_ON_AMAZON rendering, broken links, hardcoded affiliate tags, placeholder tokens.

**Verification:**

- `npm run build` exits 0
- `dist/` directory contains expected file count
- Build log has no errors
- No placeholder tokens in dist/

**Failure modes:**

- Article frontmatter malformed
- Image reference broken
- Internal link broken
- Build-validator finding raw Amazon URLs (shouldn't happen — producer emits product:slug)
- Placeholder tokens that escaped earlier checks
- (v1.6) Data-store cache contains stale entries from prior failed build — mitigated by v1.6 cache deletion pre-step

---

### Point 15.5: Pre-flight check (v1.4)

**What it does:** Runs 9 structural checks across the site before any production deploy. Catches the class of issues that produced SaunasSoSimple's 7-critical UAT.

**Run:**

```bash
python3 affiliate-platform/scripts/preflight.py --site <slug>
```

**Must exit 0 before proceeding to Point 16.** WARNs are non-blocking; FAILs block launch.

**Checks:**

| # | Check | UAT issue caught |
|---|-------|-----------------|
| 1 | scaffold-contamination | Hearing-aid vocabulary in sauna articles |
| 2 | state-sync | Empty content/articles/ when pipeline has articles |
| 3 | hub-descriptions | Boilerplate hub descriptions in navigation.yaml |
| 4 | json-ld-urls | Relative URLs in SchemaMarkup.astro |
| 5 | og-locale | Missing og:locale in BaseLayout.astro |
| 6 | persona-consistency | Wrong persona photo, implausible bio claims |
| 7 | url-slug-dedup | Near-duplicate slugs (same words, different order) |
| 8 | ymyl-hub-check | Health/medical hub labels or slugs |
| 9 | product-topic-match | Products from foreign verticals assigned to articles |

**scaffold-contamination requires configuration:** Create `config/furniture-validation.yaml` listing forbidden vocabulary for the site's vertical. Without it, check 1 produces a WARN and skips. See `validate-furniture-pages.mjs` for the format — the same file serves both tools.

**Retroactive coverage:** Running this against SaunasSoSimple after its UAT remediation produces LAUNCH CLEAR (0 FAIL, 3 WARN). The 3 WARNs are informational: scaffold-contamination unconfigured, persona byline small (valid compressed image), 12 within-site hub adjacency articles (sauna-brand-harvia articles using sauna-wood-fired products — valid cross-hub Harvia products).

**Failure modes:**

- Missing `config/furniture-validation.yaml` → check 1 WARNs, does not scan
- products.yaml not in sync with site (wrong hub values for replacement products)
- Navigation.yaml categories missing (hub enumeration fails)

---

### Point 15.6: Content-existence validator (v1.6)

**What it does:** Runs against `dist/` after build, before deploy. Checks rendered HTML for structurally valid but semantically empty content — the highest-priority new validator in v1.6. Catches placeholder leaks, empty article body divs, and low-word-count articles that escaped earlier validation.

**Run:**

```bash
node affiliate-platform/scripts/validate-content-existence.mjs --site <slug>
```

**Patterns flagged in rendered HTML body content:**

- `\[write [^\]]+\]` — unfilled write-here instructions
- `\{\{[^}]+\}\}` — unsubstituted template tokens
- `\[TODO\b`, `\[PENDING\b`, `\[FIXME\b` — editorial markers
- `\bplaceholder\b` (case-sensitive, in body content not navigation)
- `\bVERIFY\b`, `\bverify\b` (in product card contexts)
- `\bNOT_FOUND\b`, `\bNOT_ON_AMAZON\b` (rendered as visible text)
- `\bLOREM_IPSUM\b`

**Structural checks:**

- Empty `article-page__content` div (zero inner text)
- Articles with rendered body word count below 200 words

**HARD violation:** Exit 1. Blocks deploy. Fix: investigate build output for the affected article. Maximum 2 rebuild attempts before escalating to Keith.

---

### Point 16: Push live

**What it does:** Push to GitHub, Cloudflare auto-deploys, verify live.

**Tool:** `tools/deploy-and-verify.mjs --site <slug>` — needs to be built.

**Pre-condition gate: `tools/verify-bindings.mjs --site <slug>` runs first.**

This catches the OHT-style "wires connected to wrong endpoints" failures. Ten checks performed (v1.6 updated from eight):

1. Cloudflare project name = site slug
2. Cloudflare project's GitHub repo = expected repo (`itsalljustagamesoitis-ux/<site-slug>`) — skipped for Sites 11+ (no GitHub repo)
3. Cloudflare project's custom domain = site domain
4. AMAZON_TAG in Cloudflare Production env = `affiliate.amazon_tracking_id` in site.config.yaml (if env var is set)
5. AMAZON_TAG in Cloudflare Preview env = same value (if env var is set)
6. GA4 measurement ID unique across portfolio (cross-check against portfolio.yaml)
7. IndexNow key file at site root matches BWT registration
8. DNS for site domain points at correct Cloudflare Pages project
9. **(v1.6)** All SVG brand assets in `public/images/brand/` are free of placeholder tokens (`grep "{{" *.svg` returns empty)
10. **(v1.6)** Custom domain SSL certificate issued by Cloudflare (curl -I returns HTTPS response, not certificate error)

If any check fails, deploy doesn't even start. Tool reports specifically which binding is wrong.

**Process (after bindings verified):**

1. Commit any pending changes locally
1.5. **(v1.6)** Run `tools/cloudflare-pages-config.mjs attach-domain --site <slug> --domain <domain>` (idempotent — safe to run even if domain already attached)
2. Run `wrangler pages deploy dist --project-name <slug> --branch main`
3. Wait for Cloudflare Pages deployment (10-minute timeout, hard fail past it)
4. Verify deployment reaches green status
5. Run live verification (9 hard checks per Section 1.5)
6. Update portfolio.yaml via `tools/portfolio-update.mjs --site <slug> --set status=live`
7. Report outcome

**Hard pause if:** Any binding check fails or any verification check fails.

**Verification:** All 9 live checks pass (per Section 1.5).

**Failure modes (the OHT lessons, now caught by verify-bindings):**

- Cloudflare project doesn't exist
- Cloudflare project name mismatches wrangler.toml
- AMAZON_TAG missing on Preview environment
- NODE_VERSION not set
- Repo visibility unexpected
- Cloudflare GitHub App lost access after repo visibility changed

---

### Point 17: GA4 setup

**What it does:** Create GA4 property, inject measurement ID into site, update portfolio.yaml.

**Division of labor (v1.6 Keith identity-bound format):**

**Keith action (browser, ~10 minutes):**
1. Sign in to analytics.google.com
2. Admin → Create Property → name after site
3. Add web data stream pointing at site URL
4. Copy measurement ID (`G-XXXXXXXXXX`)
5. Reply with measurement ID string

**Claude Code action (after Keith provides ID):**
1. Add measurement ID to `site.config.yaml` under `analytics.ga4_measurement_id`
2. Redeploy via `wrangler pages deploy dist --project-name <slug> --branch main`
3. Update portfolio.yaml: `tools/portfolio-update.mjs --site <slug> --set ga4_id=<id>`
4. Verify HTML source contains correct `googletagmanager.com/gtag/js?id=G-XXXX`

**Platform defaults (already implemented):**

- IP anonymization: enabled
- Consent Mode v2: enabled
- Custom events: `affiliate_click` with link_position tracking

**Verification:**

- HTML source contains correct `googletagmanager.com/gtag/js?id=G-XXXX`
- DevTools shows requests to google-analytics.com firing on page load (after consent)
- GA4 Realtime shows traffic when site visited
- portfolio.yaml `ga4_id` populated

**Failure modes:**

- Measurement ID typo
- Property created but data stream not configured

---

### Point 18: Bing Webmaster Tools — verify and submit sitemap

**What it does:** Add site to BWT, verify ownership, submit sitemap, update portfolio.yaml.

**Division of labor (v1.6 Keith identity-bound format):**

**Keith action (browser, ~5-10 minutes):**
1. Sign in to bing.com/webmasters
2. Add a Site → enter domain
3. Note the DNS TXT verification string shown by BWT
4. Reply with the TXT verification string

**Claude Code action (after Keith provides verification string):**
1. Add DNS TXT record via `tools/cloudflare-pages-config.mjs add-dns-txt --site <slug> --name <domain> --value <string>`
2. Wait for BWT to verify (up to 24 hours for DNS propagation)
3. Submit sitemap: `https://<domain>/sitemap-index.xml` (Keith action in BWT UI)
4. Configure IndexNow integration in BWT (Keith action in BWT UI)
5. Update portfolio.yaml: `tools/portfolio-update.mjs --site <slug> --set bwt_verified=true`

**Verification:**

- Site appears as verified property
- Sitemap status: Success within 24 hours
- Discovered URL count matches site's article count
- portfolio.yaml `bwt_verified: true`

**Failure modes:**

- Sitemap URL wrong
- Sitemap blocked by robots.txt
- Verification fails (DNS propagation delay)

---

### Point 19: Google Search Console — verify and submit sitemap

**What it does:** Add site to GSC, verify ownership, submit sitemap, update portfolio.yaml.

**Division of labor (v1.6 Keith identity-bound format):**

**Keith action (browser, ~5-10 minutes):**
1. Sign in to search.google.com/search-console
2. Add property → enter domain (use Domain property)
3. Note the DNS TXT verification string shown by GSC
4. Reply with the TXT verification string
5. Optional: link to GA4 property

**Claude Code action (after Keith provides verification string):**
1. Add DNS TXT record via `tools/cloudflare-pages-config.mjs add-dns-txt --site <slug> --name <domain> --value <string>`
2. Wait for GSC to verify (DNS propagation, up to 48 hours)
3. Submit sitemap in GSC UI (Keith action): Sitemaps → Add `sitemap-index.xml`
4. Update portfolio.yaml: `tools/portfolio-update.mjs --site <slug> --set gsc_verified=true`

**Verification:**

- Property verified
- Sitemap status: Success within 24-48 hours
- Discovered URLs match article count
- portfolio.yaml `gsc_verified: true`

**Failure modes:**

- Sitemap "Couldn't fetch"
- Verification fails (DNS propagation)

---

### Point 20: IndexNow — wiring and verification

**What it does:** Set up IndexNow protocol for instant URL submission to Bing.

**Three pieces:**

1. IndexNow key file at site root — generated at point 7, deployed at point 16
2. Producer integration to fire IndexNow on publish — `producer/indexnow-submit.py`
3. Bing Webmaster Tools registration — register key in BWT (point 18)

**Trigger:** Batch after deploy-and-verify completes.

**Verification:**

- `curl https://<domain>/<key>.txt` returns the key string
- IndexNow submission logs show successful POST (200 response)
- BWT shows IndexNow as enabled
- Within 24-48 hours, BWT shows recent submissions

**Failure modes:**

- Key file content doesn't match what's submitted to API
- Producer integration not actually firing (FSG/MLT concern)
- BWT not registered with key

---

### Point 20.5: Pre-launch UAT — furniture-page re-validation (v1.2)

**What it does:** Re-runs the furniture-page validator before the site goes live, catching any drift between Point 8 (furniture creation) and the launch date.

Furniture pages can drift: editorial passes, config changes, and template updates may accidentally re-introduce persona claims or vocabulary bleed between Point 8 and Point 21.

**Run:**

```bash
node affiliate-platform/scripts/validate-furniture-pages.mjs --site <slug> --verbose
```

Must pass (exit 0). If violations found:
- HARD persona-claim violation: fix and redeploy. Do not launch.
- Vocabulary bleed: fix and redeploy. Do not launch.

**This catches the Ten27 UAT Blocker 2 and Blocker 3 class of issues** — furniture-page violations that were introduced or persisted between scaffolding and launch.

---

### Point 21: Plug into operational dashboard

**What it does:** Add site to portfolio operational dashboard.

**What it produces:** Entry in `~/affiliate-platform/portfolio.yaml` (v1.6 schema):

```yaml
sites:
  - slug: <site-slug>
    domain: <domain>
    persona: <persona-name>
    tracking_id: <amazon-tracking-id>
    ga4_id: <ga4-measurement-id>
    cloudflare_project: <cloudflare-project-name>
    github_repo: null                     # null for Sites 11+; repo path for Sites 1-10
    status: live
    launched: <date>
    # v1.6 additions
    persona_locked: true
    persona_locked_at: <ISO date>
    gsc_verified: true
    bwt_verified: true
    custom_domain_attached: true
    deploy_pattern: direct_upload         # direct_upload (Sites 11+) or git_push (Sites 1-10)
    affiliates:
      amazon: active
      brand_direct:
        - {name: <Brand>, status: pending|approved, applied: <date>}
```

**Writeback:** `tools/portfolio-update.mjs --site <slug> --set <field>=<value>` writes individual fields. Called automatically at Points 16, 17, 18, 19. Never let portfolio.yaml go stale — it is the source of truth for operational state.

Optional fields:
- `notes`: per-site operational notes (e.g., known deploy quirks, manual workarounds, anything an operator should know before touching the site)

**Dashboard implementation phases (locked):**

- Phase 1 (sites 1-10): YAML manifest + CLI tool. Refresh: on-demand.
- Phase 2 (sites 11-30): Static dashboard site. Refresh: scheduled rebuild.
- Phase 3 (sites 31+): Real web app with live data, history, alerts.

**Performance dashboard is separate and built later** when there's traffic data worth visualizing.

**Verification:**

- `node ~/affiliate-platform/tools/dashboard.mjs` shows new site
- Live status check passes
- Static config matches what's set in Cloudflare/GA4/BWT/GSC

---

### Move to next site

After 21 points complete and dashboard shows green:

- Site shifts from "in launch" to "operating"
- Site no longer in active build queue
- Goes into portfolio operations bucket

**Cadence: immediately to next site, no cool-off period.** Run sites in sequence at full pace until 10 sites live, then pause and assess.

**Pause point at 10 sites: judgment.**

---

## 4. Operational layer — recurring tasks

### 4.1 Per-site recurring tasks

- ASIN health checks
- Article freshness review
- Domain renewals (automatic via Cloudflare, monitor expiry 60 days out)
- SSL certificate monitoring (Cloudflare auto-renews)
- Article expansion (50-100 articles from Reserve Pool periodically)
- DALL-E image upgrades (traffic-driven for winning articles)

### 4.2 Cross-portfolio recurring tasks

- Uptime monitoring with alerts
- Earnings polling (Amazon Associates daily pull)
- GSC/Bing data ingestion
- Cloudflare deploy status
- Search ranking polling
- Calibration drift detection
- Platform updates / submodule pin bumps
- Bindings verification across portfolio (`tools/verify-bindings.mjs --all`)

### 4.3 Cadences

**TBC** — set when operational automation gets built. Annual domain renewal is the only locked cadence.

---

## 5. Operational automation tiering

Three tiers, sequenced by site count and value.

### Tier 1 — Hands-off operations

- Uptime monitoring + alerts
- ASIN monitoring (detection)
- ASIN auto-fix with confidence scoring + human escalation
- Deploy verification
- SSL/DNS monitoring
- Sitemap freshness checks
- Earnings polling
- Search ranking polling
- Bindings verification across portfolio

### Tier 2 — Performance optimization

- Article-level traffic analysis
- Underperformer flagging
- Content refresh suggestions
- DALL-E image upgrades for traffic winners
- Article expansion timing detection

### Tier 3 — Strategic intelligence

- Cross-site pattern detection
- Algorithmic risk monitoring
- New niche identification

### Build sequencing

**TBC** — built when manual operations start consuming meaningful weekly time.

---

## 6. Platform additions required before site 4

**Critical (must build before site 4):**

- `tools/launch-site.mjs` — the ritual orchestrator (Section 2)
- `tools/initialise-site.mjs` — site shell scaffolding (point 7)
- `tools/verify-site-shell.mjs` — verifies no template inheritance (point 7)
- `tools/verify-bindings.mjs` — pre-deploy binding verification + portfolio audit (point 16)
- `tools/source-products-per-article.mjs` — per-article ASIN lookup (point 10)
- `tools/source-images-pexels.mjs` — image bank from Pexels (point 11)
- `tools/assign-article-images.mjs` — per-article image assignment (point 12)
- `tools/publish-staging.mjs` — move from staging to content/articles/ (point 14)
- `tools/deploy-and-verify.mjs` — push, wait, verify live (point 16)
- `tools/dashboard.mjs` — operational dashboard CLI (point 21)
- `tools/xlsx-to-pipeline.mjs` — keyword research xlsx → pipeline.json (point 3)

**Producer changes (v1.8.0):**

- Embed `hero_image` in frontmatter from pipeline.json
- Embed body images at predictable positions in markdown (4 fixed positions: after intro, after Top Picks, after How to Choose, after FAQ)
- Hub-distributed homepage article selection (site template change, bundled with v1.8.0)

**Build-validator cleanup:**

- Update stale error messages from `<ProductLink>` references to `product:slug` (the actual format in use)

**Validator changes (from VALIDATORS.md):**

- Tag every rule with hard/soft/manual classification
- Implement soft fail logging to calibration-log.yaml
- Flip A09 from warning to hard fail
- Promote 11 M-rules from manual to auto-validated (M02, M04, M05, M06, M07, M09, M10, M11, M13, M15, M16)

**Important but not site-4-blocking:**

- `tools/check-niche-density.mjs` (point 1)
- `tools/expand-articles.mjs` (article expansion)
- `tools/asin-health-check.mjs` (Tier 1)
- `tools/earnings-poll.mjs` (Tier 1)

**Documentation:**

- `~/affiliate-platform/CATALOG-BEHAVIOUR.md` Section 7 — site initialisation: catalog seeding from Amazon search per article
- `~/affiliate-platform/TECHNICAL-SEO.md` — audit existing implementations
- `~/affiliate-platform/templates/legal/` — master legal templates with token placeholders
- `~/affiliate-platform/VALIDATORS.md` — validator rule classification (already drafted)

---

## 7. Validator hard fail vs soft fail framework

See `~/affiliate-platform/VALIDATORS.md` for full rule classification. Summary:

- **Hard fail** — breaks site functionality, violates legal/compliance, produces visibly broken content, embarrasses brand under scrutiny, breaks editorial contract
- **Soft fail** — produces editorially-fine content, arithmetic miss within 10% of target (exclusive)
- **Manual** — requires human judgment

10% deviation boundary calculated as `abs(observed - target) / target * 100`. Under 10% = soft. 10% or more = hard. For "exactly N" count rules, ±1 is soft.

Soft fails ship with logged warning to `~/affiliate-platform/calibration-log.yaml` for periodic editorial review.

Hard fail rate consistently above 5% across multiple sites = platform-level review.

---

## 8. Technical SEO documentation task

Audit existing platform/sites for technical SEO implementations and document findings.

**Areas to cover:**

- Schema markup types implemented
- Meta tag patterns
- Sitemap structure
- robots.txt content
- URL conventions
- Internal linking strategy
- Image optimization
- Performance baseline (Core Web Vitals)
- Cookie consent posture (Consent Mode v2 already confirmed implemented)
- Affiliate link resolution (rehype-product-links plugin already confirmed)

**Output:** `~/affiliate-platform/TECHNICAL-SEO.md`

**Approach:** Audit pass on FSG/MLT/OHT codebases and platform. Document findings. Surface gaps for decision. Don't fix in audit pass.

**Pairs with Phase 2 sweep** to verify existing sites are correctly configured.

---

## 9. Homepage strategy

Algorithmic, opinionated platform default, no manual curation.

**Logic:**

- Show ~12 articles on homepage
- Diversity enforcement: no more than 1-2 articles per hub
- For each hub, randomly pick 2-3 articles
- Combine, shuffle for visual variety

**OHT example of failure mode:** Homepage initially showed 4 Anchor Hocking articles in visible slice. Concentration looked weird.

**Adding to platform v1.8.0:** Update homepage component to do hub-distributed article selection.

---

## 10. Pending operational fixes for current sites

**Phase 2 sweep timing and priority: TBC.**

### 10.1 Across all live sites (FSG, MLT, OHT)

- Audit GA4 firing on live sites
- Audit IndexNow wiring and actual firing
- Audit GSC verification, sitemap submission status, indexed page count
- Audit Bing Webmaster Tools verification, sitemap submission status
- Run `tools/verify-bindings.mjs --all` once tool exists to catch any wrong-wiring issues
- Audit for template inheritance bugs (FSG content appearing in MLT/OHT)

### 10.2 FSG-specific

- 197 articles violate Amazon Operating Agreement on dollar figures
- 102 articles below 2000 words
- Sitemap issue (specifics to investigate)

### 10.3 MLT-specific

- Producer architecture: migrated to platform-shell pattern (`mlt-producer.py` delegates to `affiliate-platform/producer/producer_main.py`)
- IndexNow wiring verification

### 10.4 OHT-specific

- Catalog cleanup: re-resolve high-blast-radius NOT_ON_AMAZON entries (Lenox Opal Innocence in 15 articles is highest priority)
- Remove genuinely-fake products (Maison Arts, Bamboofest, Lillian Rose, Dwell Studio)
- Verify Sarah Collins persona photos installed correctly across both byline and about page
- Categories: retroactively add single category "Home Entertaining" wrapping the 5 hubs
- Site config description has FSG-inherited text. Update to OHT-appropriate description.

---

## 11. Document maintenance

This document is the source of truth. When reality diverges:

- If reality is wrong: fix reality
- If document is wrong: update the document
- Never silently work around a divergence

When new lessons emerge:

- Update relevant section
- Note the change in CHANGELOG.md at platform root

---

## 12. v1.2 changelog — Ten27 UAT hardening

**Date:** 2026-05-20  
**Trigger:** Four gaps surfaced during Ten27 Phase 5 UAT. Fixed before BetterHearingHub launch.

### 12.1 Image markdown validator (Point 13.6)

**Problem:** Producer emitted Python dict literals as image URLs (`![alt]({'alt': 'x', 'path': 'y.webp'})`). Validators checked "image present" but not "image URL valid." 919 instances leaked to Ten27 staging; 1,155 instances were live on Northwoods Overland.

**Fix:**
- `scripts/validate-image-markdown.mjs` — new validator, runs at Point 13.6 close, exits 1 on invalid image URL
- `scripts/fix-image-markdown.py` — bulk fixer for dict-literal pattern, handles both single and double-quoted alt values
- Northwoods Overland backport: 1,159 instances fixed and deployed 2026-05-20

### 12.2 Furniture-page validator (Points 8 and 20.5)

**Problem:** Validators ran on article content only. Furniture pages bypassed validation entirely. Two UAT blockers slipped through: (a) home page contained "Every review on this site is based on real use" — FTC-risk testing claim; (b) disclaimer/privacy policy had overlanding vocabulary from Northwoods Overland template carryover.

**Fix:**
- `scripts/validate-furniture-pages.mjs` — new validator, checks persona-claim violations and vocabulary bleed in all furniture pages
- Gate added at Point 8 close (furniture creation) and Point 20.5 (pre-launch UAT)
- `config/furniture-validation.yaml` per site — configures forbidden vocabulary for bleed detection
- Live violations found and fixed on Northwoods Overland (`index.astro`) and Ten27 (`index.astro`, `how-we-test.astro`) 2026-05-20

### 12.3 Furniture template families

**Problem:** Furniture pages were generated from generic templates with brand-name substitution. Generic templates carried vocabulary patterns from prior vertical (Northwoods → Ten27 carryover). YMYL verticals need different framing entirely (medical advice disclaimers, sourced-framing methodology).

**Fix:**
- `templates/furniture/lifestyle/` — cleaned Ten27 furniture pages, for non-YMYL sites (e-bikes, overlanding, sauna)
- `templates/furniture/ymyl/` — freshly authored for YMYL verticals (hearing aids, health-adjacent). Includes medical advice disclaimer, OTC-vs-prescription guidance, health data privacy note
- `templates/site-shell/src/pages/` — fixed for testing claims in `how-we-test.astro`, `disclaimer.astro`, `index.astro`
- Site declares template family via `furniture_template_family:` in `site.config.yaml`

### 12.4 Pipeline.json persistence

**Problem:** Concern that manual pipeline.json patches (skip flags, product corrections) would not survive across producer restarts.

**Finding:** `save_pipeline()` already has correct merge semantics as of v1.1 — reads disk state, only overwrites status fields (`status`, `staged`, `published`, `fail_count`) from memory, preserves all structural edits.

**Remaining risk documented:** `data/generate-pipeline.py` scripts do full overwrites from xlsx — running after manual patches loses all patches. Documented in Point 13 as a warning.

**Added:** 5 unit tests in `producer/tests/test_data_loader.py::TestSavePipelinePersistence` verifying merge correctness across all edge cases.

---

## 13. v1.4 changelog — SaunasSoSimple UAT hardening

**Date:** 2026-05-24  
**Trigger:** Seven critical issues surfaced during SaunasSoSimple (Site 11) UAT. Fixed post-launch; gap analysis performed to prevent recurrence on Site 12 (caregiver site).

### 13.1 Pre-flight script (Point 15.5)

**Problem:** Platform lacked a single-command structural check that could catch the full class of SSS UAT issues before deploy. Issues were found post-launch during manual UAT rather than during build.

**Fix:**
- `scripts/preflight.py` — 9-check pre-flight script, added as Point 15.5 in the pipeline
- Must exit 0 before Point 16 (push live)
- Distinguishes hard FAILs (cross-domain product mismatches, YMYL hubs, missing hub descriptions) from soft WARNs (within-site hub adjacency, unconfigured vocabulary check)

### 13.2 SSS UAT issue taxonomy (7 critical issues)

| Issue | Root cause | Pre-flight check | Fix |
|-------|-----------|-----------------|-----|
| 1. Scaffold contamination | hearing-aid vocabulary in sauna articles from shared template | scaffold-contamination | Step 1: delete 10 contaminated pages |
| 2. Hub descriptions boilerplate | 49 hubs had generic descriptions from site scaffold | hub-descriptions | Step 3: wrote Marcus-voice copy for all 49 hubs |
| 3. JSON-LD relative URLs | SchemaMarkup.astro used relative paths for schema urls | json-ld-urls | Platform fix: siteUrl prefix on all schema URL fields |
| 4. YMYL hubs | sauna-health and sauna-how-to hubs present (health risk) | ymyl-hub-check | Step 4: removed hubs, 301 redirects to accessories-extras |
| 5. URL slug duplicates | 55 near-duplicate slugs (same keywords, different order) | url-slug-dedup | Step 5: deleted 55 duplicates, 55 × 301 redirects |
| 6. Product mismatches | 11 Harvia articles had solar rope lights; 5 cedar articles had pet bedding | product-topic-match | Step 6: replaced wrong products with appropriate ones |
| 7. Persona/OG quality | Male persona had female headshot; og:locale missing; cookie banner overlap | persona-consistency + og-locale | Step 7: replaced headshot, platform-level og:locale + cookie fix |

### 13.3 Mac/VM state sync — VM is canonical (updated 2026-06-05)

**History:** SaunasSoSimple articles existed on VM (46.225.29.35) but not on the Mac build machine. All five early deploys in the session produced empty sites (77 dirs, 68 pages — no articles). Required rollback via CF REST API and rsync from VM to Mac. At that time the standing rule was "Mac is canonical." That rule is superseded.

**Updated standing rule (VM canonical, all sites):** The VM (46.225.29.35) is the canonical content store for all sites. Mac is the build machine but not the source of truth. The VM holds patched, validated article state; Mac may lag.

**Session sync protocol:**
- **Start of session:** `rsync -avz --delete root@46.225.29.35:/root/<site>/content/ /Users/keithlacy/<site>/content/` — pull VM state to Mac before any build or edit
- **End of session:** `rsync -avz --delete /Users/keithlacy/<site>/content/ root@46.225.29.35:/root/<site>/content/` — push Mac edits back to VM

Sites are reconciled as they're touched; no bulk force-sync of all sites at once.

**Pattern:** When Mac lags VM, always sync VM→Mac first. Do not build from Mac-only state for any site that has had VM-side patches applied.

**Rollback command (CF Pages REST API — wrangler v4 no longer has `pages deployment rollback`):**

```bash
curl -s -X POST \
  "https://api.cloudflare.com/client/v4/accounts/<account_id>/pages/projects/<project>/deployments/<deployment_id>/rollback" \
  -H "Authorization: Bearer <CF_API_TOKEN>" \
  -H "Content-Type: application/json"
```

### 13.4 Product hub values must match article hub after replacement

**Problem:** When products are replaced in articles (Step 6), the new product's `hub` field in products.yaml may not match the article's hub — either because the product was originally sourced for a different hub, or because hub assignments shifted (YMYL strip moved articles between hubs).

**Pattern found in SSS:**
- `harvia-smart-sensor-for-sauna-heaters-compatible` sourced for sauna-wood-fired, used in sauna-brand-harvia articles
- `western-red-cedar-sauna-door-71` sourced as sauna-components, used in sauna-materials articles
- 20 products with hub=sauna-health remained after the YMYL strip moved their articles to accessories-extras

**Fix:** After any product replacement or hub reassignment, run `scripts/preflight.py --check product-topic-match` to surface residual mismatches. Update `hub:` in products.yaml for replaced products to match where they're actually used.

**Distinction the pre-flight makes:**
- FAIL: product hub not in site navigation at all (cross-domain contamination — rope lights, pet bedding)
- WARN: product hub is a valid site hub but different from article hub (within-site adjacency — acceptable for brand-spanning products like Harvia sensors that span wood-fired and electric hubs)

---

---

## 14. v1.5 changelog — Pre-site-13 platform cleanup

**Date:** 2026-05-28  
**Trigger:** Pre-site-13 platform cleanup audit. Goal: close all platform/generator-level debt that would propagate into a freshly scaffolded site. Confirmed-open items only (no fixes from stale lists without audit verification).

### 14.1 V9 dollar-figure portfolio sweep (COMPLETE 2026-05-27)

**Problem:** 197+ articles across FSG, SSS, TCD, BCB, BHH contained hardcoded dollar amounts in article body and/or `title:` frontmatter — Amazon ToS Section 5(v) violation. Discovered during FSG V9 remediation 2026-05-27.

**Scope of violations fixed:**
- FSG: 154 → 0 (two sessions)
- SSS: 2 → 0
- TCD: 2 → 0
- BCB: 5 → 0
- BHH: 16 → 0 (dominant pattern: `[Budget Hearing Aids (Under $500)]` hub link text repeated across 7 articles)

**Enforcement:** `dollar_figures_enforcement: warn` temp overrides removed from FSG and BHH `site.config.yaml`. All sites now at FAIL enforcement. Added V9 standalone entry to `VALIDATORS.md` (was only documented as rule A03).

### 14.2 Template fixes — "tested reviews" phrasing and metaDescription bio-dump (COMPLETE 2026-05-28)

**Problem:** Three template-level issues propagated to all scaffolded sites via `templates/site-shell/src/pages/`:

**Issue 1 — `how-we-test.astro` URL mismatch:**
- Template had `how-we-test.astro` (creates `/how-we-test/` URL)
- `Footer.astro` links to `/how-we-research/` (set in an earlier platform fix)
- All sites scaffolded before this fix had a broken footer link

**Fix:** Renamed `how-we-test.astro` → `how-we-research.astro` in template. Updated `title:` from "How We Test" → "How We Research". Content body was already clean (used "verified owner research" framing). Deleted stale `how-we-test.astro` from 7 live sites (FSG, MLT, OHT, TCD, BCB, NWO, TEN27). 4 sites (BHH, CuratedCameras, SSS, FFC) already had only `how-we-research.astro`.

**Issue 2 — "Tested reviews of" in `[hub].astro`:**
- Template had: `description={`Honest, tested reviews of ${hub.label.toLowerCase()} for ${cfg.site.brand_name} readers.`}` and `Tested reviews of {hub.label.toLowerCase()} — what's worth buying and what to avoid.`
- 8 live sites retained this phrasing (FSG, MLT, OHT, TCD, BCB, NWO, TEN27, BHH). 3 sites (CuratedCameras, SSS, FFC) were already clean.
- FSG/MLT/OHT/TCD also had site-specific overrides with "from a gardener who actually uses them" (OHT/TCD showed FSG-origin cross-contamination)

**Fix:** Template and all 8 affected sites updated to `hub.description ?? \`Research-based guides on ${hub.label.toLowerCase()} from ${cfg.site.brand_name}.\`` pattern (matches SSS/FFC pattern, supports hub-description override from `navigation.yaml`).

**Issue 3 — `persona.bio_short` appended to metaDescription in `index.astro`:**
- Template had: `description={`Honest, tested reviews of ${cfg.site.niche} products. ${persona.bio_short}`}`
- All 11 live sites had some variant with `${persona.bio_short}` appended, making the homepage metaDescription a persona bio dump rather than a topic-focused description

**Fix:** Template updated to `description={`Research-based guidance on ${cfg.site.niche} products from ${cfg.site.brand_name}.`}` (no bio dump). All 11 live sites fixed (older 8 used "Honest, tested reviews" prefix; newer 3 used "Research-based guidance" prefix but retained bio_short). All deployed.

### 14.3 Clean-scaffold verification (Phase D)

A throwaway test site was scaffolded from the fixed templates and the full 14-check preflight run against it. Results:

- **10 PASS** — scaffold-contamination, json-ld-urls, og-locale, url-slug-dedup, ymyl-hub-check, brand-niche, spec-consistency, hub-consistency, product-coherence, dollar-figures
- **3 WARN** — state-sync (empty pipeline), persona-consistency (placeholder photos + short bio), product-topic-match (no articles yet)
- **1 FAIL** — hub-descriptions (empty navigation.yaml, expected empty-state before content generation)

The single FAIL (`hub-descriptions`) is expected pre-content-generation behavior — hub descriptions are written during Phase 2 pipeline work (Point 3 per-hub-description pass). This is not a template bug. The three WARNs are also expected for a zero-content fresh scaffold.

**Conclusion:** A freshly scaffolded site 13 inherits 0 template-level propagating bugs. The only pre-launch FAIL will be `hub-descriptions` until content generation Phase 2 is complete.

### 14.4 VALIDATORS.md and preflight.py documentation

- Added V9 (dollar-figures) standalone entry to `VALIDATORS.md` Section 10 (was only A03 in rule table)
- Added V13 (safe-deploy) standalone entry to `VALIDATORS.md` Section 10
- Preflight.py header updated to reflect 14 checks (was "9 checks" from SSS UAT)
- V14 (hub-consistency), V15 (product-coherence), V16 (spec-consistency) already documented in VALIDATORS.md Section 10 (SHIPPED 2026-05-26)

---

## 15. v1.6 changelog — Autonomous launch hardening

**Date:** 2026-06-01
**Trigger:** Sites 13/14/15 cohort surfaced systemic gaps between PIPELINE.md spec and actual launch behavior.

### 15.1 Persona-lock discipline confirmed and locked

**Finding:** Across three sites the relationship between persona-lock timing and editorial fabrication is now empirically established:

| Site | Persona timing | Fabrications in articles |
|---|---|---|
| Site 13 (Marcus) | Locked after content generated | Multiple (wrong gear, fabricated meetup, hallucinated engineer name, wrong partner name) |
| Site 14 (Adrian) | Locked 2 days before producer | Zero |
| Site 15 (Greg) | Locked before producer | Zero |

**Spec change:** Persona lock is now a hard gate at Point 5 close. Producer at Point 13 refuses to run unless persona is locked. Lock state stored as `persona_locked: true` in the persona YAML with `locked_at: ISO timestamp` and `content_hash`. If the YAML changes after lock, the producer refuses to run until re-locked.

### 15.2 Pipeline meta-leakage class identified (Site 14 finding)

**Finding:** Site 14's marantz-vs-anthem-vs-denon article shipped with the producer's internal brief-reasoning published verbatim as article body.

**Spec change:** New validator at Point 13.7 — `validate-meta-leakage.mjs`. HARD failure, exit 1, blocks publish.

Patterns flagged: `\bthe brief\b`, `\bprompt system\b`, `\bh2_structure\b`, `\bbrief specifies\b`, `\bpersona's defer-to\b`, `\bbrief also specifies\b`, `\barticle type defined in\b`, `\bformat governs\b`.

### 15.3 Buyer-guide card depersonalization class identified (Site 15 finding)

**Finding:** Greg's locked persona produced first-person voice in narrative prose but third-person/agentless voice in buyer-guide product cards specifically.

**Spec change:** Producer must inherit persona voice properties into the card generation code path. New validator at Point 13.8 — `validate-card-voice.mjs`. SOFT failure, logged to calibration-log.yaml.

### 15.4 Content-existence validator (highest-priority new validator)

**Finding:** Three sites shipped articles with structurally valid but semantically empty content. Existing validators check structure; none scan rendered HTML for content-existence patterns.

**Spec change:** New validator at Point 15.6 — `validate-content-existence.mjs`. Runs against `dist/` after build, before deploy. HARD failure, exit 1, blocks deploy.

### 15.5 Persona-spec compliance validator

**Finding:** No existing validator compares first-person claims in article bodies against the locked persona spec. Site 13's entire editorial fix session was for this class of violation.

**Spec change:** New validator at Point 13.5b — `validate-persona-spec-compliance.mjs`. HARD failure, exit 1, blocks publish. Implementation note: requires an LLM-pass per article via Haiku (~$0.001–0.01/article).

### 15.6 Product slug resolution validator

**Finding:** Site 15's `how-to-indicator-nymph.md` referenced `product:aventik-eupheng-riverruns-yarn` but the products.yaml key was `aventik-eupheng-riverruns-yarn-strike`. Build succeeded. Rendered HTML had a broken affiliate link.

**Spec change:** New validator at Point 13.9 — `validate-product-slug-resolution.mjs`. HARD failure, exit 1, blocks publish.

### 15.7 Astro data-store cache invalidation policy

**Finding:** Site 15 build produced 91 articles with empty body content despite valid markdown files. Root cause: `node_modules/.astro/data-store.json` contained stale entries with `rendered: undefined` from a prior failed build.

**Spec change:** `package.json` build script updated to delete `node_modules/.astro/data-store.json` before every production build.

### 15.8 SVG asset placeholder detection

**Finding:** Sites 14 and 15 both shipped with `logo-header.svg` containing `{{BRAND_NAME}}` as literal text.

**Spec change:** New check in `verify-site-shell.mjs` (Point 7 close) and `verify-bindings.mjs` (Point 16 pre-deploy): `grep "{{" public/images/brand/*.svg` — any match is HARD failure.

### 15.9 Sourcing tool DTC fallback policy

**Finding:** Site 15's catalog had 10 wrong-ASIN products where the Rainforest sourcing tool backfilled DTC products with unrelated Amazon results.

**Spec change:** `tools/source-products-rainforest.py` updated with three policies: brand-string match required, category match required, known-DTC-brand fallback. Seller-prefix scrub added (`STOVER Patagonia` → `Patagonia`).

**DTC config file naming:** The per-niche file path is `config/dtc-brands/<niche>.yaml` where `<niche>` is the exact value of `site.niche` in `site.config.yaml`. For example: a site with `site.niche: fly-fishing` requires `config/dtc-brands/fly-fishing.yaml` — not `fishing.yaml`. The niche value determines the filename; do not abbreviate or simplify it.

### 15.10 Catalog category-coherence filter

**Finding:** Site 15's `/best-saltwater-flies/` had a spin lure as Best Overall and a bait-catching rig as Also Consider.

**Spec change:** New `category_type` field in products.yaml per product. New validator at Point 12.5b — `validate-catalog-category-coherence.mjs`. HARD failure, exit 1.

### 15.11 Pipeline status writeback policy

**Finding:** Sites 13, 14, and 15 all shipped with all 300 articles in pipeline.json showing `status: not_started` despite being live.

**Spec change:** Producer updates pipeline.json status per article after successful publish. `publish-staging.mjs` updates `status: published` when articles move from staging to content/articles/.

### 15.12 Em-dash producer prompt fix and validator

**Finding:** Site 14 had 253/300 articles with em-dashes rendered as ` , ` (space-comma-space). Site 13 had ~30 articles with the same pattern.

**Spec change:** Producer prompt updated with explicit instruction to use `—` (U+2014). New post-generation check in `article_builder.py::check_output_shape()`. Build-validator soft-fail check (threshold: >10 per article).

### 15.13 Skip-list enforcement at deploy

**Finding:** Site 15's simms-g3-vs-g4.md was on the producer's skip-list but rendered live with 4 broken Amazon links.

**Spec change:** `publish-staging.mjs` reads `data/skip-list.yaml`. Articles on skip-list excluded from staging-to-content move. `verify-deploy.mjs` post-deploy check confirms skip-list URLs return 404/301, not 200.

### 15.14 Pages-API automation gaps (autonomous-launch tooling backlog)

**Finding:** Custom domain attachment, DNS TXT records for GSC/BWT, environment variables on Pages — all Claude Code's responsibility per spec but de facto manual Keith gates.

**Spec change:** New tool `tools/cloudflare-pages-config.mjs`. Single entry point for all Pages-API automation. `launch-site.mjs` invokes it at appropriate ritual points.

### 15.15 Deploy pattern reality vs spec (Section 1.4 correction)

**Finding:** PIPELINE.md Section 1.4 specified git push → CF auto-deploy. Actual pattern for Sites 11+ is `wrangler pages deploy dist` direct upload. `portfolio.yaml` shows `github_repo: null` for Sites 11–15.

**Spec change:** Section 1.4 updated to reflect actual deploy pattern. Sites 1–10: git push. Sites 11+: direct upload. Pattern locked at scaffold.

### 15.16 portfolio.yaml writeback policy

**Finding:** portfolio.yaml is consistently stale. Site 13 showed `status: pre_launch` and `ga4_id: null` on the day it was confirmed live with GA4 deployed.

**Spec change:** Every phase transition explicitly writes back to portfolio.yaml. New tool `tools/portfolio-update.mjs`. Each ritual point invokes it.

### 15.17 Tooling backlog audit

Status of tools as of v1.6:

| Tool | Status |
|---|---|
| `tools/launch-site.mjs` | NOT BUILT — Section 2 ritual never implemented |
| `tools/initialise-site.mjs` | Exists; inconsistently used |
| `tools/verify-site-shell.mjs` | Exists; photo MD5 check unconfirmed |
| `tools/verify-bindings.mjs` | Exists; pre-deploy invocation inconsistent |
| `tools/source-products-rainforest.py` | Exists; inconsistently used |
| `tools/source-images-pexels.mjs` | Exists; inconsistently used |
| `tools/assign-article-images.mjs` | Exists; standard usage |
| `tools/publish-staging.mjs` | Exists; some sites bypass |
| `tools/deploy-and-verify.mjs` | Exists; standard usage |
| `tools/dashboard.mjs` | Exists; runs against stale portfolio.yaml |
| `tools/xlsx-to-pipeline.mjs` | Exists; standard usage |
| `tools/check-niche-density.mjs` | NOT BUILT |
| `tools/expand-articles.mjs` | NOT BUILT |
| `tools/asin-health-check.mjs` | NOT BUILT |
| `tools/earnings-poll.mjs` | NOT BUILT |
| `tools/cloudflare-pages-config.mjs` | NOT BUILT — new in v1.6 |
| `tools/portfolio-update.mjs` | NOT BUILT — new in v1.6 |
| `tools/lock-persona.mjs` | NOT BUILT — new in v1.6 |
| `tools/generate-persona-photos.mjs` | NOT BUILT — new in v1.6 |
| `tools/generate-brand-assets.mjs` | NOT BUILT — new in v1.6 |
| `scripts/validate-content-existence.mjs` | NOT BUILT — new in v1.6 |
| `scripts/validate-persona-spec-compliance.mjs` | NOT BUILT — new in v1.6 |
| `scripts/validate-product-slug-resolution.mjs` | NOT BUILT — new in v1.6 |
| `scripts/validate-meta-leakage.mjs` | NOT BUILT — new in v1.6 |
| `scripts/validate-card-voice.mjs` | NOT BUILT — new in v1.6 |
| `scripts/validate-catalog-category-coherence.mjs` | NOT BUILT — new in v1.6 |

**Critical path for autonomous launch:** `launch-site.mjs`, `cloudflare-pages-config.mjs`, `portfolio-update.mjs`, `lock-persona.mjs`, and the six new validators must exist before Site 16 launches under the autonomous-launch model. Estimated build effort: ~2 weeks of focused platform work.

### 15.18 Editorial fix backlog from cohort

#### Validator calibration backlog

**B41 — Pre-flight slug collision check (2026-06-05)**
Article slug matching a hub slug causes the hub page to overwrite the article at the same URL in every Astro build. The article is never publicly accessible. Pre-flight currently does not detect this.
- Fix: add a slug-collision check to `preflight.py` that compares article slugs against hub names in `navigation.yaml`. FAIL if any collision found.
- Priority: before Site 17 launch. A site with keyword research producing hub-matching terms will silently dead-end articles.
- Discovery: SM `barbells.md` had `slug: "barbells"` matching the "barbells" hub. Article was never live — hub page shadowed it in every deploy.

**B42 — V18 possessive ownership patterns (2026-06-05)**
V18 v1.1 caught explicit testing/ownership language (`I've tested`, `I own`, `I've carried`) but missed first-person possessive place/equipment claims (`my garage`, `my kitchen`, `my workshop`, `my home gym`). These are ownership signals with equivalent FTC risk.
- Fix: V18 v1.2 adds `my (?:garage(?: gym)?|home gym|kitchen|workshop|listening room|workout room|setup)` as HARD with heading-skip (FAQ headers use `my garage` in question form — skip lines starting with `#`). **Shipped 2026-06-05** to `/root/affiliate-platform/scripts/validate-persona-claims.mjs`.
- Portfolio B42 HARD counts from V18 v1.2 first run (VM sites): SM 15, MLT 33, NWO 1, SSS 2. RBC 0 (Wesley's `my pack/kit` was already in REVIEW_PATTERNS). Mac-only sites not yet scanned.
- Remediation: same sentence-start rewrite pattern as Day 8 V18 patches. `my garage` → `in this garage`, `my kitchen` → `in this kitchen`. Day 10 remediation batch across SM + MLT + remaining sites.

**B43 — Portfolio Mac/VM divergence audit at v1.X validator transitions (2026-06-05)**
Day 4 patched RBC on VM (45 HARD). Day 8 patched MLT on Mac (38 HARD). Neither sync was propagated. When V18 v1.2 first ran, Mac RBC showed 52 HARD (stale) and VM MLT showed 33 HARD (stale). The canonical number was 0 and 11 respectively — wrong surface gave wrong count.
- Root cause: no sync protocol before Day 8's VM canonical policy decision. Each session patched wherever it ran and left the other side stale.
- Fix applied 2026-06-05: VM canonical policy documented in PIPELINE.md §13.3 + HETZNER-VM-STATE.md. Session-start VM→Mac sync + session-end Mac→VM sync now required. **Persona config (`config/personas/`) must also be synced** — persona YAML determines owned-gear suppression in V18; a stale persona file produces false positives/negatives even when article content is identical.
- Add to v1.X transition checklist: before running the new validator version portfolio-wide, sync all sites to canonical state first (VM→Mac or Mac→VM per site's history). Otherwise stale-state violations pollute the violation count.

**B44 — Portfolio VM/Mac article-count divergence (2026-06-05) — CLOSED 2026-06-05**
Divergence table surfaced 2026-06-05 as part of Day 9 B42 scope audit. Five sites had meaningful VM-ahead divergence: MLT +9, CC +8, NWO +19, BHH +24, SSS +69.
- Root cause: Sites deployed from VM had no Mac→VM or VM→Mac sync post-launch. Content accumulates on VM while Mac copy stays frozen at launch state.
- Day 10 resolution per site:
  - **SSS:** VM→Mac (+69 articles). All 69 V18-clean. Mac now 365 articles.
  - **CC:** VM→Mac (hygiene, +8 articles). All V18-clean. Mac now 255 articles.
  - **NWO:** All 19 VM-only articles are near-dup slug variants of existing Mac articles. No sync needed. Mac-canonical.
  - **MLT:** All 9 VM-only articles are near-dup slug variants of existing Mac articles. Mac→VM push (--delete) cleaned 9 VM near-dups. VM now 191 matching Mac.
  - **BHH:** Deferred to Day 11 — bidirectional divergence, near-dup investigation required. BHH is CLEAN for V18 so no FTC urgency.
- Going forward: VM canonical policy (§13.3) + session-start/end sync protocol prevents recurrence.

**B45 — NWO VM `maxtrax-boot.md` B38 contamination (2026-06-05) — CLOSED 2026-06-06**
VM-only article `maxtrax-boot.md` has title "MaxTRAX Boot Buyer's Guide: Orthopedic vs. Work Boots" — MaxTRAX is a traction recovery board brand; this article covers footwear (wrong niche). Deleted from VM during Day 11 Phase 2 cleanup. No Mac action needed (was never on Mac).

**B48 — Rainforest sourcing returns thin results for book-category articles — CLOSED 2026-06-06**
Book-keyword articles (astronomy-books, astronomy-books-for-beginners, childrens-astronomy-books, etc.) consistently return 0-2 sourced products despite Amazon having thousands of astronomy books. Root cause: `source-products-rainforest.py` uses a plain keyword search with no `category_id` parameter. Amazon's default search returns physical products (telescopes, mounts) ranked above books for astronomy queries. The book products that ARE found get sourced into the shared accessories hub, but each individual keyword only retrieves 1-2 unique books — not enough for the 3-product minimum.
- Fix shipped (Day 15): Added `is_book_article()` detection (keyword or slug contains "book") to `tools/source-products-rainforest.py`. When detected, `category_id=283155` (Amazon Books node) is added to the Rainforest API request. This restricts results to Amazon Books and surfaces 7+ matching results.
- Workaround applied (Site 17): Cross-assigned all 17 book products in the accessories catalog across 7 book articles (6 products each). All 7 articles now have sufficient products.
- Affects: Any site with reference/learning content where books are the natural product type.

**B45 — Semantic slug dedup in xlsx-to-pipeline.mjs — CLOSED 2026-06-06**
Fix shipped (Day 15): Added MODIFIER_WORDS stripping + semantic key comparison to `tools/xlsx-to-pipeline.mjs`. After pipeline.json is built, articles within each hub are grouped by their modifier-stripped token set (sorted). Articles whose stripped tokens match a higher-volume article in the same hub are marked `status: "dupe"` with a `dupe_of` reference. MODIFIER_WORDS: best, good, great, top, worst, affordable, cheap, budget, inexpensive, expensive, premium, basic, simple, easy, a, an, the. Test result: 6/12 Site 17 book-keyword articles correctly detected as near-dups (astronomy-books, good-astronomy-books, top-astronomy-books, great-astronomy-books, astronomy-books-for-beginners, good-astronomy-books-for-beginners). antique-astronomy-books and old-astronomy-books correctly NOT flagged.

**B45 update (2026-06-06) — Semantic near-duplicate slugs affecting Site 17 launch:**
Site 17 produced 10 astrophotography-telescope near-duplicate slugs that V1 dedup didn't catch at keyword research time: astrophotography-telescope, good-telescope-for-astrophotography, great-telescope-for-astrophotography, beginner-astrophotography-telescope, deep-sky-astrophotography-telescope, dobsonian-telescope-astrophotography, portable-astrophotography-telescope, starter-telescope-for-astrophotography, best-starter-telescope-for-astrophotography, best-beginner-telescope-for-astrophotography. All 10 dropped at launch (shortfall articles). V1 dedup uses token-set comparison within each hub — it catches exact synonym pairs but misses semantic equivalence across modifier chains (beginner/starter/good/great are not caught as duplicates of each other). Same shape as MLT KitchenAid 8-quart variants. B45 tooling fix (semantic-equivalence check) is now affecting launch quality, not just remediation. Elevate priority.

**B49 — Multi-hub product schema support — CLOSED 2026-06-06**
Products in `products.yaml` were limited to a single `hub: slug` field. Articles containing cross-hub products (e.g., a telescope that also appears in mounts articles) generated Rule 2 violations. Fix shipped (Day 15): Added `product_matches_hub(product, hub_slug)` helper to `data_loader.py` that checks both `hub: str` (single, backward-compatible) and `hubs: [list]` (new, multi-hub). Updated `get_hub_products()` and `article_builder.py` fallback path to use the helper. Updated three test assertions in `test_phase1_output_schema.py` to handle both schema variants. No migration required — existing `hub: str` products continue to work unchanged.

**B50 — `already_staged()` checks .docx extension instead of .md — CLOSED 2026-06-06**
`producer/producer_main.py` `already_staged()` checked `staging/{slug}.docx` which is never written (staging files are `.md`). This caused the skip gate to miss articles that were already staged, allowing re-production of completed articles. Fix shipped (Day 15): removed the `.docx` branch. Function now checks `staging/{slug}.md`, `staging/failed/{slug}.md`, and `articles/{slug}.md`.

**B54 — `initialise-site.mjs` destructively overwrites pipeline.json (2026-06-06)**
`initialise-site.mjs` writes an empty `data/pipeline.json` as part of Phase 1 scaffolding, without checking whether a non-empty pipeline already exists. If pipeline generation runs before scaffold (a reasonable workflow order), the scaffold silently destroys the pipeline. Discovered on Site 18: pipeline was generated in Phase 3, then scaffold ran in Phase 4 and overwrote it. Recovery required regenerating from intermediate `/tmp/site18_keywords_clean.json`. Nothing was permanently lost, but the ordering dependency is non-obvious.
- Fix: scaffold should check `existsSync(pipelinePath) && JSON.parse(readFileSync(pipelinePath)).articles?.length > 0` before writing. If true, skip overwrite and log a warning: `[INFO] pipeline.json already populated (N articles) — skipping empty scaffold`. Operator can pass `--reset-pipeline` to force overwrite if intentional.
- Priority: Medium — affects any site where pipeline generation precedes scaffold. Silent data loss in the common case where /tmp intermediates have been cleared.
- Status: **OPEN**

**B57 — `generate-product-pros-cons.py` not called as part of new site setup workflow (2026-06-07)**
`generate-product-pros-cons.py` exists in canonical platform tools and was used for Site 17 (FLF), but is not included in the Day 16 scaffold or Day 17 pre-producer checklist. When not run, `products.yaml` has `default_pros: []` / `default_cons: []` for every product. The `_derive_pros_cons` fallback in `article_builder.py` existed for AV/home theater hubs only — working-dog hubs fell through to empty arrays, causing 100% F09 validator failures on Site 18 (TWC). Producer killed after 3 articles to avoid burning API budget on content with identical hub-level fallback text for all products.
- Root cause: workflow gap, not script regression. The tool was already in canonical but was never added to the Day 16–17 checklist. `source-products-rainforest.py` always hardcodes `default_pros: []` by design — enrichment is a separate intentional step.
- Fix (process): Add `python3 affiliate-platform/tools/generate-product-pros-cons.py --site <slug>` as a required step before the producer run. Add to Phase 5 (pre-production) in §13.3. Cost: ~$0.0007/product (Haiku). Runtime: ~20–25 min for 1,000+ product catalogs.
- Fix (platform — fail-fast): Add pre-flight check at producer startup: if catalog has ≥10 products with `default_pros: []`, raise `WorkflowError("generate-product-pros-cons.py not run — stop and run enrichment before producing")`. Surfaces this failure in 5 seconds rather than after 3 failed articles.
- Fix (platform — safety net): Added hub-specific fallbacks to `_derive_pros_cons` in `article_builder.py` for all TWC working-dog hubs, and added `[WARN]` print to stderr when the fallback fires — visible in producer logs as a workflow-gap signal. Applied 2026-06-07.
- Portfolio audit (2026-06-07): Checked all 10 sites with `products.yaml` on VM. Result: 10/10 have `0 empty` — generate-product-pros-cons.py ran successfully for all prior sites. TWC is the only miss. Not a systemic gap across the portfolio.
- Scope: Any new site with Rainforest-sourced catalog. Expected to affect all pet/outdoor/sporting-goods niches on first launch.
- Priority: High — causes 100% producer failure rate on affected sites. Low detection cost once fail-fast check is added.
- Status: **OPEN** (process fix documented in SITE-LAUNCH-PROTOCOL.md §5 Phase 4 Point 10.5; TWC enrichment complete 2026-06-07; fail-fast check not yet built — platform v2.3)
- Note: B56 Mac-side patch applied 2026-06-07. B56 status updated below.

**B58 — `producer_main.py` processes `status: drop` articles instead of skipping them (2026-06-07)**
`producer_main.py` iterates over all articles in `data/pipeline.json` without checking the `status` field before processing. Articles with `status: drop` proceed through the full pipeline and fail at product-count validation (minimum 3 products required), logging errors identical to real article failures. On Site 18 (TWC), 24 `status: drop` articles inflated the failure count by 24 across Passes 1 and 2, masking the true failure rate in producer logs.
- Root cause: No status gate at the top of the article processing loop. The `status: drop` field is honoured by sourcing tools but not by the producer.
- Fix: Add early-exit check at top of article loop in `producer_main.py`: `if article.get("status") == "drop": continue`. Alternatively, filter the article list before the loop: `articles = [a for a in articles if a.get("status") != "drop"]`.
- Impact: Log noise only — `status: drop` articles produce no output. Zero content risk. But inflated fail counts make triage harder (operators see "35 failed" when only 11 are real failures).
- Priority: Low — cosmetic/diagnostic impact only. No content correctness risk.
- Status: **OPEN**

**B56 — `source-products-rainforest.py` appends duplicate product keys within article's assigned_keys (2026-06-07)**
When Rainforest API returns the same ASIN twice in a single product search result, the script appended the same key twice to `assigned_keys`, producing duplicate `id:` entries in `products:` frontmatter. Affected 93 of 316 TWC articles on the initial source pass. `article_builder.py` deduplicates at runtime (`valid = [k for k in assigned if k in products]`) preventing duplicate render, but the duplicate keys remained in `pipeline.json` and caused roundups to appear short on first validation.
- Fix (VM): Added dedup check on line ~472 in `/root/affiliate-platform/tools/source-products-rainforest.py`: `if asin_to_key[asin] in assigned_keys: continue` before appending.
- Fix (Mac): Applied 2026-06-07 — `/Users/keithlacy/affiliate-platform/tools/source-products-rainforest.py` patched with same dedup check.
- Recovery: Deduplicated 93 affected `pipeline.json` entries in-place; re-sourced 45 articles that fell below roundup minimum (6 products) after dedup.
- Status: **CLOSED** (both VM and Mac patched 2026-06-07)

**B55 — B45 semantic dedup misses brand-anchored qualifier variants (2026-06-07)**
B45 strips `MODIFIER_WORDS` from keyword tokens and sorts, then groups within hub. This collapses `best-gps-tracker-for-dogs` → `gps-tracker-dogs` and catches modifiers like `top`/`best`/`review`. It misses variants where the brand name itself is the qualifier: `tractive-gps-tracker-for-dogs` vs `tractive-gps-tracker` vs `tractive-smart-gps-tracker` all normalize to different token sets because `tractive` is not in `MODIFIER_WORDS`. Discovered on TWC: three Tractive variants and one Garmin variant escaped B45, requiring manual drop after sourcing.
- Root cause: B45 doesn't treat brand names as anchor tokens for variant consolidation. The brand token causes distinctness even when the base product concept is identical.
- Fix (tooling): Brand-anchored consolidation pass in B45. After standard dedup, group remaining slugs that share a brand name (from product title or a brand registry) and identical base product token set. Keep one canonical slug per brand+product combination.
- Scope: Affects all sites in niches where brand names are common in keyword variants (pet/sporting goods/outdoor gear). Less relevant for home theater where brand variants are less common.
- Priority: Medium — upstream issue (keyword research) mitigates most cases; B45 escape rate ~1-2% in practice. B53 (word-order sensitivity) and B55 together represent the remaining B45 coverage gap.
- Status: **OPEN**

**B53 — B34 reject patterns are word-order sensitive (2026-06-06)**
`config/reject-patterns.yaml` entries are case-insensitive substring matches. A pattern like `dog car seat` rejects keywords containing that exact phrase, but `car seat for dogs` — the same product, different word order — passes through. This affects all sites using B34 reject patterns going forward. Discovered during Site 18 pipeline generation: `dog car seat` was an explicit reject pattern, but `car seat for dogs` (3,600 vol) passed through and required manual review.
- Root cause: substring matching is phrase-order sensitive; no token normalization or set matching.
- Fix (tooling): Add a `reject_patterns_token` mode to `xlsx-to-pipeline.mjs` alongside the existing substring mode. In token mode, both the keyword and pattern are split into token sets; a keyword matches if its token set is a superset of the pattern's token set. Example: pattern tokens `{dog, car, seat}` would match `car seat for dogs` (tokens: `{car, seat, for, dogs}` — `dog`→`dogs` still fails exact match). May need stemming or a token-synonym layer.
- Scope: Affects all sites using `--reject-patterns`. Not blocking Site 18 (the specific `car seat for dogs` case was reviewed and kept intentionally — Derek owns Kurgo vehicle transport gear). Priority: Medium — applies to next new site's pipeline generation.
- Status: **OPEN**

**B47 — New site scaffold lands on Mac only; VM sync is manual (2026-06-05)**
`tools/initialise-site.mjs` creates the site directory on whichever machine Claude Code runs on (Mac). The VM is the canonical content store for production runs, but there is no automatic rsync step at the end of scaffold. Operator must manually rsync Mac→VM before launching the producer. This caused a delayed discovery on Site 17 (firstlightfield): full rsync + npm install + debug cycle added ~20 minutes to first launch.
- Fix (process): Add Mac→VM rsync as the final step in Phase 5 (pre-production) for any new site. Document in §13.3 session-start/end protocol.
- Fix (tooling): `initialise-site.mjs` could accept a `--sync-vm` flag that rsyncs to `root@46.225.29.35:/root/<slug>/` as the final scaffold step. Out of scope for Day 11 — note for Day 12+.
- Priority: Low — one-time cost per new site, easily worked around. But the friction is non-obvious (silent failure: producer runs on Mac fine, VM runs fail).

**B46 — V1 dedup Mac-only workflow causes systematic VM/Mac divergence (2026-06-05)**
Root cause of the VM/Mac divergence pattern observed across MLT, NWO, BHH, and CC (Day 9–11 investigation): V1 slug-dedup runs on Mac during keyword research and local content work. The deduped canonical slugs get deployed to production (Mac→CF Pages) but the pre-dedup slug variants persist on VM indefinitely. VM accumulates stale slug variants; Mac carries the canonical deduplicated state.
- Evidence: MLT 9 VM-only = near-dup variants; NWO 19 VM-only = near-dup variants; BHH 27 VM-only = near-dup variants. All three sites confirmed same pattern on Days 10–11.
- Fix (process): After V1 dedup runs on Mac, immediately rsync content to VM before any subsequent session work. This is a one-line addition to the session-start/end sync protocol (§13.3).
- Fix (tooling): Consider adding a V1 dedup check to the session-end sync: `node scripts/validate-slug-dups.mjs --check-vm-drift` that surfaces VM slugs with no Mac canonical. Add to Day 12+ workflow.
- Priority: Medium — the divergence is hygiene-level, not FTC-risk. All three confirmed cases are now resolved. Recurrence prevention is the remaining action.

Site-specific bugs confirmed across Sites 13/14/15 that should be propagated to template and checked on Sites 1–12:

- Persona byline image path-construction bug (page-relative vs root-absolute) — Sites 13, 14, 15
- Cookie consent persistence (fix shipped on Site 14, not propagated)
- SVG `currentColor` fill rendering invisible when loaded as `<img>` (fix shipped on Site 14, not propagated)
- Em-dash rendering as ` , ` (fixed on Site 14, root cause documented in 15.12)
- Boilerplate identical pros/cons across products in buyer guides — Site 14
- Renewed/refurbished SKUs as primary picks — Site 14
- Seller-prefix in product names (`STOVER Patagonia Swiftcurrent Waders`) — Site 15
- Doubled-apostrophe escape artifacts (`Greg''s`) — Site 15

---

## 16. Autonomous launch enforcement

### 16.1 Decision categorization framework

Every decision in the 21-point pipeline falls into one of four buckets:

- **Bucket A** — Autonomous with documented policy. Claude Code applies the policy. No human intervention.
- **Bucket B** — Autonomous with Keith review at preview gate. Claude Code applies the policy. Keith reviews preview deploy URL before promoting to production.
- **Bucket C** — Keith identity-bound. Requires Keith's account, credential, or signature. Ritual halts and surfaces structured request.
- **Bucket D** — Keith strategic decision. Requires Keith's judgment for the portfolio. Ritual halts and surfaces structured questionnaire.

### 16.2 Per-point decision categorization

| Point | Decision | Bucket | Policy if A or B |
|---|---|---|---|
| 1 | Niche selection | D | Keith decides; questionnaire elicits niche statement |
| 1.5 | Amazon availability assessment | A | Run Rainforest on 20-30 queries; apply three-tier framework |
| 2 | Keyword research | C | Keith provides XLSX; format validated by xlsx-to-pipeline |
| 3 | Pipeline.json generation | A | xlsx-to-pipeline.mjs runs autonomously |
| 4 | Domain selection | D | Keith decides; ritual receives domain as input |
| 5 | Persona | D (biographical) + A (technical) | Keith provides biographical core; Claude Code structures YAML |
| 5b | Persona photos | A | Generate via documented prompt template |
| 5c | Persona lock | A | After validation passes, lock-persona.mjs runs autonomously |
| 6 | Visual identity | B | Derive colors from niche per documented palette; Keith overrides at preview |
| 7 | Site shell | A | initialise-site.mjs runs autonomously |
| 8 | Site furniture | A | Generate from template family for niche |
| 9 | Amazon tracking ID | C | Keith creates ID; provides string; Claude Code wires |
| 10 | Source products | A | source-products-rainforest.py with documented policy filters |
| 11 | Source images | A | source-images-pexels.mjs runs autonomously |
| 12 | Assign images | A | assign-article-images.mjs runs autonomously |
| 12.5 | Brand match audit | A | Run validator; iterate sourcing until pass or escalate to D |
| 13 | Producer run | A | Producer runs with locked persona |
| 13.5 | Persona claim audit | A | Validator runs; HARD failures regenerate |
| 13.5b | Persona spec compliance | A | Validator runs; HARD failures regenerate |
| 13.6 | Image markdown validator | A | Validator runs; fix-image-markdown.py on HARD failures |
| 13.7 | Meta-leakage validator | A | Validator runs; HARD failures regenerate |
| 13.8 | Card-voice density | A | Validator runs; SOFT failures logged |
| 13.9 | Product slug resolution | A | Validator runs; HARD failures fix or regenerate |
| 14 | Publish staging | A | publish-staging.mjs runs autonomously |
| 15 | Local build | A | npm run build runs autonomously |
| 15.5 | Pre-flight | A | preflight.py runs autonomously |
| 15.6 | Content existence | A | validate-content-existence.mjs runs autonomously |
| 16 | Push live | A | deploy-and-verify.mjs + cloudflare-pages-config.mjs |
| 17a | GA4 property creation | C | Keith creates; provides measurement ID |
| 17b | GA4 injection | A | Claude Code injects ID, redeploys |
| 18a | BWT verification | C | Keith creates property; provides verification string |
| 18b | BWT DNS record | A | cloudflare-pages-config.mjs adds TXT record |
| 19a | GSC verification | C | Keith creates property; provides verification string |
| 19b | GSC DNS record | A | cloudflare-pages-config.mjs adds TXT record |
| 20 | IndexNow | A | Producer integration fires automatically |
| 20.5 | UAT furniture re-validation | A | Validator runs autonomously |
| 21 | Dashboard plug-in | A | portfolio-update.mjs writes entry |

**Summary (35 decisions):**
- Bucket A (autonomous): 25 (71%)
- Bucket B (autonomous + Keith preview review): 1 (3%)
- Bucket C (Keith identity-bound): 6 (17%)
- Bucket D (Keith strategic): 3 (9%)

**Keith's involvement consolidates to three touchpoints:**
1. Pre-launch input bundle: Niche + domain + keyword XLSX + persona biographical context
2. Mid-launch identity gates: Amazon ID, GA4 property, GSC property, BWT property
3. Pre-promotion review: Preview deploy URL review (default on; can graduate to autonomous)

### 16.3 Bucket A policy specifications

**1.5 Amazon density:** Run Rainforest on 20-30 representative queries. Apply tier framework: ≥70% Amazon → launch Amazon-only; 50–70% → pre-seed 10–20 DTC products; <50% → pre-seed extensively OR halt for Keith confirmation.

**5b Persona photos:** Generate via `~/affiliate-platform/templates/persona-photo-prompt.md`. Tool: `tools/generate-persona-photos.mjs`. Produces both photos, runs MD5 uniqueness check against portfolio.

**6 Visual identity:** Derive colors per niche from `~/affiliate-platform/config/niche-palettes.yaml`. Logo generation: `tools/generate-brand-assets.mjs`. Keith reviews at preview.

**9 Amazon tracking ID format:** `<slug-truncated-to-fit-20-char-limit>-20`. Claude Code derives the proposed string; Keith creates the ID in Amazon Associates with that exact string.

**10 Product sourcing:** source-products-rainforest.py with v1.6 policy filters. No manual confirmation per product. Brand enrichment runs immediately after.

**12.5 Brand match audit:** Validator runs. FAILs → re-run sourcing with brand-specific queries. Second-pass FAILs → escalate to Keith.

**13.5 / 13.5b / 13.7 / 13.9 Validators:** HARD failures trigger regeneration with `--force --id <N>`. Maximum 3 regeneration attempts. After 3 attempts, article moves to skip-list.

**15.6 Content existence:** HARD failures trigger investigation and rebuild. Maximum 2 rebuild attempts before escalating to Keith.

**16 Custom domain attachment:** Always attempt via API. Retry with exponential backoff (10s, 30s, 60s, 120s). After 5 minutes, escalate to Keith.

### 16.4 Bucket C structured request format

When the ritual hits a Keith identity-bound gate, it halts and surfaces a structured request in chat:

```
RITUAL HALT — Point 9: Amazon Associates tracking ID required

Action required from Keith:
1. Log in to Amazon Associates dashboard
2. Create new tracking ID with the exact string: <proposed-tracking-id>
3. Confirm creation in dashboard
4. Reply with: "tracking ID created" (or "tracking ID failed — <reason>")

Tool: tools/cloudflare-pages-config.mjs will wire AMAZON_TAG to production
and preview environments once you confirm. No further action from you after
confirmation.

Estimated time: 5 minutes.
```

### 16.5 Preview review graduation policy

By default, the ritual deploys to a preview URL and halts at "Awaiting preview review" before promoting to production DNS.

**Graduation:** After N consecutive sites launch through the autonomous ritual with zero SEV-1 findings in editorial UAT, the preview review gate may be graduated to autonomous promotion. Initial N = 3. The graduation decision is itself a Keith strategic decision (Bucket D) requiring explicit unlock via `tools/graduate-autonomous-launch.mjs --confirm`.

### 16.6 Failure escalation policy

Escalation hierarchy:
1. Retry with backoff — transient failures
2. Apply alternate policy — documented fallbacks
3. Escalate to Keith with diagnostic — policy exhausted
4. Halt ritual cleanly — preserves state in state.yaml, surfaces structured request, resumable

The ritual never proceeds with degraded state.

### 16.7 Concurrency policy

Only one site launches at a time. Ritual checks `~/affiliate-platform/active-launches.yaml` before starting; refuses if another launch is in progress.

### 16.8 Resumability and state

State file at `~/affiliate-platform/sites/<slug>/state.yaml`:

```yaml
slug: <slug>
started: <ISO>
last_updated: <ISO>
current_point: <number>
current_bucket: <A | B | C | D>
status: in_progress | awaiting_keith | failed | complete
points_complete: [<list>]
points_failed: [{point, reason}]
keith_pending: [<list of pending Bucket C/D requests>]
inputs:
  niche: <provided at Point 1>
  domain: <provided at Point 4>
  keyword_xlsx_path: <provided at Point 2>
  persona_context: <provided at Point 5>
  amazon_tracking_id: <set after Point 9>
  ga4_measurement_id: <set after Point 17>
artifacts:
  cloudflare_project: <slug>
  cloudflare_zone_id: <zone_id>
  preview_url: <set after first deploy>
  production_url: <set after DNS attach>
```

Resume via `tools/launch-site.mjs --resume <slug>`. State is the source of truth.

### 16.9 Audit trail

Every autonomous decision writes to `~/affiliate-platform/sites/<slug>/decisions.log`:

```
<ISO> [Point 1.5] decision=amazon_tier_tiered amazon_rate=58% strategy=pre_seed_dtc bucket=A
<ISO> [Point 6] decision=visual_identity_derived primary=#1A1F2E accent=#C0853A bucket=A
<ISO> [Point 9] halt=awaiting_keith request=amazon_tracking_id bucket=C
<ISO> [Point 9] resume=keith_provided value=undisclosedsounds-20 bucket=C
```

### 16.10 What this section locks

Added to Section 1.13:

- `launch-site.mjs` is the only entry point for new site builds
- Decision categorization framework (Buckets A/B/C/D)
- Sequential launches only (no concurrency)
- Preview review gate default (graduation requires explicit unlock)
- Audit trail per site in decisions.log
- State.yaml as source of truth for ritual progress

---

## 17. v1.8 changelog — Day 15-16 platform work (2026-06-06)

### 17.1 Day 15 platform fixes (B45/B48/B49/B50/Header.astro) — package v2.2.0

See `V1_8_RELEASE_NOTES.md` for full details.

- **B50 CLOSED:** `already_staged()` dead `.docx` check removed
- **B49 CLOSED:** Multi-hub product schema (`hubs: [list]` support)
- **B48 CLOSED:** Rainforest sourcing adds `category_id=283155` for book-keyword articles
- **B45 CLOSED:** `xlsx-to-pipeline.mjs` marks semantic near-dups (modifier-stripped token-set grouping) as `status:"dupe"`
- **Header.astro:** Single-category sites flatten hubs to top-level nav
- **V18/V20 portfolio verification:** 18 possessive-place violations fixed (SM 15, NWO 1, SSS 2); 0 HARD V18 / 0 V20 portfolio-wide
- **Site 17 (firstlightfield.com):** LIVE, 245 articles, 0 HARD V18, GA4 G-MEQ56RP85W

### 17.2 Day 16 new tooling

- **B34 CLOSED (new feature):** `xlsx-to-pipeline.mjs` now accepts `--reject-patterns <yaml>` flag. Site-level `config/reject-patterns.yaml` lists case-insensitive substring patterns; matching keywords are marked `status:"skip"` before B45 dedup runs. First deployed on Site 18 (The Working Coat) with 81 working-dog-specific patterns.

- **B53 OPEN:** B34 reject patterns are phrase-order sensitive. Pattern `dog car seat` rejects but `car seat for dogs` (same product, different word order) passes. Needs token-set matching for word-order variant detection. Affects all sites using `--reject-patterns`. Not blocking Site 18.

### 17.3 Site 18 — The Working Coat (theworkingcoat.com)

**Status: LAUNCHED 2026-06-07** — 315 articles live. Deployed to CF Pages. Custom domain active. GA4 firing. IndexNow submitted (315 URLs, 200 OK). verify-site-shell: 0 blockers.

- Persona: Derek Foss (derek-foss) — field wildlife manager, state wildlife agency, central PA. 48 years old, 30 years working dogs. Dutch Shepherd (IPO2) + GWP (NAVHDA-tested) + young Malinois.
- Background: "Field wildlife manager, state wildlife agency, central Pennsylvania" — Rule 1 compliant (unique portfolio-wide)
- Persona locked: 2026-06-06 (hash: a105a7a6)
- Pipeline: 337 articles (315 live / 22 status:drop) / 9 hubs
- Visual identity: primary #3D2A1E (field brown), accent #9C7025 (brass gold), DM Serif Display / Source Sans 3
- Amazon tag: theworkingcoat-20 ✓
- GA4: G-YYXQ7XLEWQ ✓
- IndexNow: submitted 2026-06-07, 315 URLs (key: 96652ffcff1b2bac495f766e80c49766)
- Persona photos: placeholder JPEGs deployed (DALL-E generation deferred)

**Pending (Keith):**
- GSC property setup + TXT verification (hand TXT value to Claude Code → CF DNS TXT record)
- BWT (Bing Webmaster Tools)

---

### 17.4 v1.7 changelog — Day 18 close (2026-06-07)

#### New platform artifact

**SITE-LAUNCH-PROTOCOL.md** added at `/root/affiliate-platform/SITE-LAUNCH-PROTOCOL.md` (2026-06-07, 407 lines). This document supersedes the ad-hoc checklists in §13 as the authoritative launch reference. It contains:
- §1 Tool Inventory: all 25 tools with purpose, launch point, inputs, outputs, failure modes
- §2 Scaffold Artifacts: what initialise-site.mjs creates, what requires replacement, verification gates
- §3 Config File Requirements: all required site.config.yaml fields including the two that broke Site 18 (`visual.logo_paths`, `deployment`)
- §4 External Integration Points: all 15 services, division of labor (Keith vs Claude Code)
- §5 Canonical Launch Checklist: 12 phases, each with tools, verification commands, and failure mode notes
- §6 Gap Cross-Reference: every Day 17 postmortem bug mapped to its §5 verification gate

PIPELINE.md §15 checklists remain the source of truth for validator calibration and platform decisions. SITE-LAUNCH-PROTOCOL.md is the launch execution reference.

#### B59 — Brand asset generation + Pexels image sourcing omitted from launch workflow (2026-06-07)

Two tools existed in the platform but were never documented as required launch steps:
- `generate-brand-assets.mjs`: outputs all 9 logo/favicon variants. Scaffold creates placeholder SVGs with `fill="none"` empty rects. Without this tool, logo is invisible in production (verified on Site 18: header showed blank space).
- `source-images-pexels.mjs` + `assign-article-images.mjs`: downloads hub-keyed images; assigns to pipeline.json. Without this pair, all article hero images are null → 404 broken images in production (verified on Site 18: all article cards showed broken image placeholder).

Root cause: both tools were discovered retroactively — neither appeared in any daily brief or checklist before Day 18.

Fix (process): Both are now explicit steps in SITE-LAUNCH-PROTOCOL.md §5 Phase 3 (brand assets) and Phase 5 (image sourcing), each with verification commands (`grep -c 'fill="none"' logo-header.svg` → 0; `ls public/images/articles/ | wc -l` → N > 0).

Recovery (Site 18 TWC): `generate-brand-assets.mjs` was not available (niche-palettes.yaml lacked `working-dog` entry) — hand-crafted SVG coat collar mark logos in brand colors via Python; committed to VM. `source-images-pexels.mjs --per-hub 20` run on VM: 180 images downloaded (9 hubs × 20). `assign-article-images.mjs` run: 315 articles assigned. Rebuild + redeploy: 336 pages built, all article images live.

- Scope: Any site where both tools were skipped. Site 18 is the only affected site — all prior sites had images and logos in production.
- Status: **CLOSED** (process fix via SITE-LAUNCH-PROTOCOL.md; niche-palettes.yaml `working-dog` entry still pending for retroactive generate-brand-assets support)

#### B60 — IndexNow URL construction missing hub prefix (2026-06-07)

`producer/indexnow-submit.py` `get_all_slugs()` returned bare slugs (`martingale-collar-dog`) and constructed URLs as `https://{domain}/{slug}/`. All platform sites serve articles at `/{hub}/{slug}/` (e.g., `/collars-and-leashes/martingale-collar-dog/`). Bare-slug URLs are 404. When submitted in bulk (315 URLs), IndexNow returned 403 (key validation failed against 404 URL list). Single-URL test with correct path returned 200.

Fix: Updated `get_all_slugs()` in `/root/the-working-coat/producer/indexnow-submit.py` to read both `slug` and `hub` fields from article frontmatter and return `{hub}/{slug}` paths. URL construction now produces `https://{domain}/{hub}/{slug}/`. Re-submit: 315 URLs, 200 OK (2026-06-07).

- Scope: All sites using `indexnow-submit.py`. Per-site copies need this fix applied. The fix should be propagated to the platform template for new sites.
- Status: **CLOSED on TWC** (fix applied to `/root/the-working-coat/producer/indexnow-submit.py`); platform template propagation pending.

#### B62a — `source-products-rainforest.py` doesn't verify completion (2026-06-08)

`source-products-rainforest.py` runs until it exhausts its candidate list but provides no post-run verification that all articles in the pipeline received the minimum required product count. The sourcer exits 0 even when large hub segments (e.g., sleep-optimization, stretching-and-mobility) received 0 products due to pipeline ordering — the tail-loaded hubs were never reached because the sourcer stopped at the default article limit.

- Root cause: No coverage gate is evaluated before the sourcer declares success. Exit 0 conflates "ran to completion" with "sourcing was adequate."
- Fix (tooling): Add a post-run coverage report and optional `--assert-min-coverage N` flag. Exit non-zero if any hub has fewer than N articles with products.
- Scope: All sites using `source-products-rainforest.py`. Discovered on Site 19 (The Back Pain Notebook) — 80 articles in the last two hubs received 0 products on the first sourcing pass.
- Status: **CLOSED 2026-06-08** — `source-products-rainforest.py` now (a) warns at startup when a partial state file exists but `--resume` was not passed, and (b) runs a post-completion report comparing processed slugs against all live pipeline articles; exits 1 with per-hub breakdown if any live articles still have no products. Fix in `tools/source-products-rainforest.py`.

#### B62b — Producer runs without pre-flight product coverage verification (2026-06-08)

`producer_main.py` begins article generation immediately without first checking that the product catalog covers the pending article list adequately. When called with `--count 200 --publish`, the producer encounters product shortfall errors for ~55% of articles and skips them silently. No pre-run gate prevents this expensive generation attempt when sourcing coverage is known to be incomplete.

- Root cause: No pre-flight step validates that each pending article has ≥ min_products before the LLM is called.
- Fix (tooling): Add a `--preflight` flag (or auto-run before generation) that prints a per-hub coverage table and exits non-zero if any article in the batch has fewer than `min_products` assigned. Mirrors the manual coverage check currently done by hand.
- Scope: All sites. Discovered on Site 19 — 110 of 200 producer attempts failed with product shortfall.
- Status: **CLOSED 2026-06-08** — New tool `tools/verify-coverage.py` added. Checks every live pipeline article for ≥ N products with non-empty `default_pros`, classifies as ok/shortfall/zero, prints per-hub table and overall verdict. `producer_main.py` now calls this as a pre-flight gate before any LLM spend; exits 3 on failure with instructions. Override available via `--skip-verification` for emergency use. Fix in `tools/verify-coverage.py` + `producer/producer_main.py`.

#### B62c — Pipeline ordering can starve tail-loaded hubs (2026-06-08)

`xlsx-to-pipeline.mjs` writes articles in hub-sequential order (all articles from hub 1, then hub 2, ..., hub N). `source-products-rainforest.py` processes articles in pipeline index order and stops when it hits its limit. If the last 2-3 hubs are large and the sourcer limit is set to the total article count minus those hubs, the tail hubs receive 0 products. On Site 19, hubs 6 (sleep-optimization, 54 articles) and 7 (stretching-and-mobility, 10 articles) both started at index 275+; the original sourcer stopped at 255.

- Root cause: Sequential hub ordering combined with index-ordered sourcing and a finite limit creates a deterministic starvation pattern for the last hubs in the pipeline.
- Fix (tooling): Source in hub-round-robin order (one article per hub per pass) rather than sequential hub order. Guarantees minimum coverage across all hubs before any hub is fully saturated.
- Scope: All new sites where article count approaches the sourcer's per-run limit. Site 19 is the discovered case; earlier sites (smaller pipeline counts) were not affected.
- Status: **CLOSED 2026-06-08** — `source-products-rainforest.py` now processes articles in round-robin hub order via `get_processing_order()`. Each pass takes one article from each hub in alphabetical hub order before cycling back. Guarantees proportional coverage across all hubs even when processing is cut short by time or cost limits. Fix in `tools/source-products-rainforest.py`.

#### B62d — Producer publishes `status: dupe` articles (2026-06-08)

`producer_main.py` calls `get_pending_articles(pipeline)` which correctly filters `status: dupe` articles from the queue. However, 31 articles marked `status: dupe` were found in `content/articles/` after the repair production run on Site 19. These articles were generated during an earlier producer run when the dupe status was not yet applied, or when `already_staged()` (which checks only for the `.md` file on disk) short-circuited the dupe check by finding no file. The producer's `already_staged` guard and the `get_pending_articles` filter are not equivalent — an article can be dupe-flagged in pipeline.json but still reach generation if it was first generated before the dupe flag was set.

- Root cause: Producer generation and dupe-flagging are not atomic. Articles generated before B45 dedup runs escape the dupe filter.
- Fix (tooling): Add an explicit `status: dupe` guard in the producer loop (after `select_articles`, before generation) that skips any article with `status: dupe` regardless of disk state. Also add a `preflight.py` check that detects published dupe articles.
- Scope: Any site where B45 dedup runs after an initial production pass. Site 19 had 31 dupe articles on disk at launch cleanup.
- Status: **CLOSED 2026-06-08** — `producer_main.py` now checks `article.get("status")` at the top of the article loop before any generation attempt; silently skips `dupe` and `drop` articles, warns on unknown statuses. End-of-run summary now shows skip counts broken down by reason (dupe, drop, bad-status, already-staged, no-products, fail-limit, generated). Fix in `producer/producer_main.py`.

#### B62e — No iterative coverage convergence (repair runs are one-shot) (2026-06-08)

The current repair workflow for product shortfall is: (1) identify zero-product articles, (2) re-source with `--resume`, (3) re-run producer. This is one-shot — if the second producer pass still has shortfall articles (because sourced products don't match the validity filter), there is no automatic third pass. On Site 19, the repair re-source achieved 0 zero-product articles per pipeline.json, but the producer still failed on 110/200 articles because `_ensure_products_in_catalog` filtered sourced products down below min threshold at generation time. The gap between "has products in pipeline" and "has valid products at generation time" is invisible until the producer runs.

- Root cause: The pipeline's product count (raw sourced products) and the producer's valid product count (filtered by topic match, ASIN validity, etc.) can diverge significantly. No pre-generation visibility into this divergence.
- Fix (tooling): Surface valid_product_count per article in the coverage gate check. After sourcing, run a dry-pass of `_ensure_products_in_catalog` for each pending article and report shortfall counts before any LLM spend occurs. This gives a real coverage number, not a misleading "articles still empty: 0."
- Scope: All sites using `source-products-rainforest.py` + `producer_main.py`. Discovered on Site 19 — repair re-source showed 0 empty articles but 55% of producer attempts still failed.
- Status: **OPEN** — platform v2.3 backlog.

---

## 18. v1.8 changelog — Platform v2.3.0 fixes (2026-06-08)

Triggered by Site 19 (The Back Pain Notebook) launch postmortem. Four bugs (B62a–B62d) caused 36% article loss (111 of 305 planned articles not produced). All four fixed before Site 20 launch.

### 18.1 New tool: verify-coverage.py

**Location:** `tools/verify-coverage.py`

Pre-producer product coverage gate. Checks every live pipeline article for ≥ N products with non-empty `default_pros`. Outputs per-hub table, overall verdict, optional JSON report.

```
Usage:
  python3 tools/verify-coverage.py --site <slug>
  python3 tools/verify-coverage.py --site <slug> --min-products 3
  python3 tools/verify-coverage.py --site <slug> --accept-skips skip-list.txt --strict
  python3 tools/verify-coverage.py --site <slug> --report /tmp/coverage.json

Exit codes:
  0 = all articles meet threshold (or all shortfalls accepted)
  1 = shortfalls exist without accepted skip list
  2 = configuration error
```

**Integration:** `producer_main.py` calls this automatically before any LLM spend. Override with `--skip-verification` (emergency only). Coverage gate requires ≥4 usable products per article by default.

### 18.2 producer_main.py changes

- **Status guard (B62d):** Explicit `status == "dupe"` / `status == "drop"` check at the top of the article loop, before generation. Silently skips. Unknown statuses (`not in live/pending/staged/skip`) log a warning and skip.
- **Skip summary:** End-of-run summary now shows counts by skip reason: dupe, drop, bad-status, already-staged, no-products, fail-limit, and generated.
- **Coverage pre-flight (B62b):** Calls `verify-coverage.py --strict` before article generation begins. Exits 3 on failure. Override: `--skip-verification`.
- **New flag:** `--skip-verification` — bypasses coverage gate for emergency use.

### 18.3 source-products-rainforest.py changes

- **Partial state warning (B62a):** At startup, if a state file exists but `--resume` was not passed, emits a stderr warning listing the count of previously processed articles and instructions to use `--resume`.
- **Completion report (B62a):** After the final save, compares all processed slugs against live pipeline articles (status not in dupe/drop/skip). If any live articles still have no products: prints per-hub breakdown of unprocessed articles and exits 1. If complete: prints success line and exits 0.
- **Round-robin ordering (B62c):** New `get_processing_order(pipeline_articles, already_processed, dtc_brands)` function. Interleaves articles across hubs in alphabetical hub order — one article per hub per pass. Guarantees all hubs get proportional coverage even when a run is cut short.

### 18.4 Canonical platform nav (Fix 5)

`affiliate-platform/src/components/Header.astro` already contains `flatNav` logic (added in v2.2.0): single-category sites have their hubs promoted to top-level nav items automatically. Site 19's submodule had an older version; patched manually. Site 20+ will pick up the canonical fix via fresh scaffold.

Portfolio-wide submodule refresh for Sites 1–18 is a separate tracked task (not Site 20 blocker).

### 18.5 Test results

Run against Site 19 (The Back Pain Notebook):

| Test | Expected | Result |
|------|----------|--------|
| `verify-coverage --site the-back-pain-notebook` | 5 shortfall, FAILED | PASSED — 5 shortfall articles (theragun × 2, homedics, teeter × 2; DTC/low-pros) |
| `producer --dry-run --slug best-massage-gun-uk` (dupe) | Skip with summary | PASSED — `Skipped (dupe): 1` |
| `source-products --site bpn --dry-run` (state exists, no --resume) | Stderr warning | PASSED — warning fires |
| Round-robin ordering | Hub-interleaved order | Code verified; not run live (Site 19 fully sourced) |

### 18.6 Version bump

Platform: v2.2.0 → v2.3.0. No breaking changes. All Sites 1–19 unaffected (producer `--skip-verification` not needed for already-complete sites; coverage gate passes immediately when all articles are published).

---

*End of PIPELINE.md*
