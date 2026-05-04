# @platform/core — Changelog

## [Unreleased]

Corpus backlog logged in CORPUS-BACKLOG.md following v1.2.0 calibration self-test. No corpus changes — OHT launch takes priority over remediation.

FSG buyer_guide corpus (22 articles) carries the same dollar-figure A03 violation noted in CORPUS-BACKLOG.md. No new flag — same backlog item.

## [1.3.0] — 2026-05-05

### Buyer guide prompt — `article-buyer-guide.v1.md`

**New prompt**: `prompts/article-buyer-guide.v1.md` — full production spec for `type: "buyer_guide"` articles across FSG, MLT, and OHT.

#### Structure differences from roundup

- Four-section H2 body: `## What to Look For in {category_noun}` → `## Top Picks` → `## {STYLE_POLICY.buying_guide_heading.style}` → `## Frequently Asked Questions`
- "What to Look For" section (400–600 words, 3–5 H3 subsections) teaches evaluation criteria before any product is named
- Layout: `BuyerGuideLayout.astro` — no `<ComparisonTable />`; `<ProductCard showRole />` rendered below body under `<h2>Detailed Reviews</h2>`
- Tags: `["{hub_slug}", "buyer_guide"]` (not `"roundup"`)

#### Intro lock (D4 amendment)

Intro structure is fixed: paragraph 1 establishes search intent + product category + hub link (link must appear in paragraph 1, not deferred); paragraph 2 frames evaluation criteria at principle level; optional paragraph 3 only if paragraph 2 cannot contain the framing naturally. Prevents model from inflating the intro into a soft mini-buyer-guide that competes with "What to Look For".

#### Brief additions (D6 amendment)

New required brief field `category_noun` provides the product category noun for the `## What to Look For in {category_noun}` H2. Generating script halts if absent. If brief contains `h2_structure`, it is ignored — the prompt defines structure authoritatively.

#### Banned patterns (D8 amendment)

AI-tell phrase ban includes implementation note: enforcement applies to prose only; validator must exclude `<script type="application/ld+json">` blocks to avoid double-triggering on FAQ answer text echoed verbatim in JSON-LD.

#### Structural bans added vs roundup

- No `**Price:**` or `**Best for:**` codas at end of product sections
- No role label in H3 product headings (`### Best Overall: Product Name` form banned)
- No bold role subtitle below H3 product headings

#### Style policy

All five `{{STYLE_POLICY.*}}` placeholders carry over from the roundup spec unchanged. No new policy fields introduced.

## [1.2.0] — 2026-05-04

### Per-site style policy — footprint diversification

**Architecture change**: A new required `style_policy` block in each site's `site.config.yaml` governs per-site structural calibration. The roundup prompt and validator now read from this block instead of using hardcoded values. No silent defaults — build fails with a clear error if the block is absent.

#### New `style_policy` schema (`SiteConfig.style_policy`)

- `word_count.{min,max}` — article body word count bounds (was hardcoded 2600–3200 everywhere)
- `dollar_figures.allowed` — boolean; when `false`, the full dollar-figure ban in the validator and prompt applies; when `true`, sparse dollar references in prose are permitted
- `buying_guide_heading.style` — `'How to Choose' | 'Buying Guide'`; controls the H2 heading for the buying guide section site-wide
- `in_body_images.policy` — `'per_product' | 'fixed_count' | 'none'`; controls how in-body images appear in product sections
- `in_body_images.fixed_count` — integer or null; required when policy is `fixed_count`

#### Per-site values set

| Site | heading | images | word count |
|---|---|---|---|
| FSG | `Buying Guide` | `fixed_count: 5` | 2000–3000 |
| MLT | `How to Choose` | `none` | 2000–3000 |
| OHT | `How to Choose` | `per_product` | 2000–3000 |

#### `config.ts` changes

- New `StylePolicy` interface exported from `src/lib/config.ts`
- `SiteConfig` gains required `style_policy: StylePolicy` field
- `getSiteConfig()` throws `'style_policy block missing in site.config.yaml'` if block absent

#### Validator changes (`validators/validate-roundup.mjs`)

- New `--site <path>` flag; auto-detects site root by walking up from article path if omitted
- Exit code 2 on missing or malformed `style_policy` (config error, not article failure)
- Policy header printed per file: `style_policy: words M–N | dollars X | buying guide "## H" | images P`
- `L01` word count bounds now come from `style_policy.word_count`
- `A03` dollar pattern check gated on `style_policy.dollar_figures.allowed`
- `B07` / `B05` buying guide heading check uses `style_policy.buying_guide_heading.style`
- `B11` three-way image policy: per_product (one per section), fixed_count (N total), none (zero)
- `B13` comma separator check skipped for `none` policy; per-section for `per_product`; per-placed-image for `fixed_count`

#### Prompt changes (`prompts/article-roundup.v1.md` → v1.1)

- Word count section updated to reference `STYLE_POLICY.word_count.{min,max}`
- Dollar figure ban made conditional on `STYLE_POLICY.dollar_figures.allowed`
- Buying guide H2 references updated to `{STYLE_POLICY.buying_guide_heading.style}`
- In-body image section now describes all three policies with explicit rules per policy
- New Section 9: Style Policy Injection Point with field reference table
- Old Section 9 (style guide reference) renumbered to Section 10

## [1.1.0] — 2026-05-04

### Phase 3 — products.yaml as single source of truth for ASINs and affiliate URLs

**Architecture change**: Article bodies no longer contain hardcoded Amazon ASINs or affiliate tags. Products are referenced by slug; URL resolution happens at build time.

#### New components

- `affiliate-platform/src/components/ProductLink.astro` — Renders a product reference in Astro templates. Props: `slug` (required), `articleSlug` (optional, derived from page URL if omitted). Throws a loud build error on unknown slugs. Resolves `NOT_ON_AMAZON` to `<span data-unavailable>`, real ASINs to `<a rel="sponsored noopener">`. Intended for use in `.astro` layout and hub templates, not article markdown bodies.
- `affiliate-platform/src/components/Price.astro` — Renders `current_price` from products.yaml by slug. Falls back to "Check current price" if field absent. Non-critical — missing price is not a build error.

#### New plugin

- `affiliate-platform/src/plugins/rehype-product-links.mjs` — Rehype plugin that transforms `[text](product:slug)` markdown links at build time. Runs before `rehypeExternalLinks` so resolved Amazon URLs get `rel="sponsored noopener"` added automatically. Resolves: AWIN product URLs, Amazon ASINs, or strips to `<span data-unavailable>` for NOT_ON_AMAZON. Throws on unknown slugs — drift is caught at build time, not silently rendered as broken links. Exported via `@platform/core/src/plugins/*`.

#### New migration tool

- `affiliate-platform/tools/markdown-to-productlink.mjs` — Migrates article bodies from `[text](amazon.com/dp/ASIN?tag=...)` to `[text](product:slug)`. Builds ASIN→slug reverse map from products.yaml. CLI: `node tools/markdown-to-productlink.mjs --site <path> [--dry-run] [--verbose]`. Idempotent; skips files with no Amazon links; reports unresolved ASINs and exits non-zero.

#### New validator rules (fail the build)

- `hardcoded-asin-source` — `amazon.com/dp/{ASIN}` found in any `.md/.mdx` article body. Use `[text](product:slug)` instead.
- `hardcoded-affiliate-tag-source` — `?tag=` found in any `.md/.mdx` article body. Affiliate tags are injected at build time via the plugin.

#### MLT migration applied

- 200 articles migrated; 1143 links resolved; 2 unresolvable products added to products.yaml (`fat-daddios-round-cake-pan-9`, `nordic-ware-round-cake-pan-9`); 0 unresolved after catalog expansion.
- Deployed build `e74db37f`, `https://mylittletablespoon.com`. Post-deploy spot-check: 0 `dp/VERIFY`, affiliate tag on all Amazon links, `data-product` slug attributes present, `NOT_ON_AMAZON` renders correctly.

#### FSG migration applied

- Pre-flight: 0 VERIFY entries, 736 hardcoded ASIN links across 198 articles, 198 products in catalog, affiliate tag `fourseasong-20`.
- 10 orphan ASINs resolved: 10 new products added to products.yaml (hiland-wgthg-patio-heater, orbit-yard-enforcer-sprinkler, liquid-fence-concentrate, litom-solar-motion-spotlights, birdies-metal-raised-garden-bed, mammotion-luba-2-awd × 3 variants, hartman-mow-house, f273702-propane-adapter-hose).
- Duplicate slug collision resolved: `hiland-pyramid-patio-heater` existed for ASIN B07B94686C; B004KH4LAE variant renamed to `hiland-wgthg-patio-heater`; 3 affected articles updated.
- 197 articles migrated; 792 links resolved; 0 unresolved.
- Pushed to main branch `d4f6d4d`, Cloudflare Pages build triggered via Git integration (`https://fourseasongardener.com`).
- Post-build spot-check (5 articles): affiliate tag on all Amazon links, `data-product` slug attributes present, 0 `product:` href leaks in rendered HTML.

#### Implementation note

MDX was evaluated and rejected for this corpus due to inline JSON-LD `<script type="application/ld+json">` blocks in article bodies — the MDX acorn parser treats `{` in script content as JSX expression delimiters. The rehype plugin approach (articles stay as `.md`) is cleaner for this use case. `ProductLink.astro` and `Price.astro` remain valuable for `.astro` layout templates.

#### Rollout

- ✅ MLT — migrated and deployed `e74db37f`
- ✅ FSG — migrated and deployed `d4f6d4d`
- ⏳ OHT — deferred; should receive migration before article generation begins so new articles are born with the `product:slug` pattern

## [1.0.5] — 2026-05-04

### MLT VERIFY ASIN remediation — deployed to production

- MLT deployed to Cloudflare Pages (build `76d8e932`, `https://mylittletablespoon.com`). All acceptance criteria met: 0 `dp/VERIFY` on live site, affiliate tag `mylittletbsp-20` present on all Amazon links, `NOT_ON_AMAZON` products render as plain text (no broken anchors).
- **Platform bug fixed:** `affiliate-platform/src/lib/config.ts` `buildAffiliateUrl()` was naively constructing `amazon.com/dp/NOT_ON_AMAZON` URLs for products with the `NOT_ON_AMAZON` sentinel. Added guard: `amazon_asin !== 'NOT_ON_AMAZON'` before URL construction. `ProductCard` and all other components consuming `affiliate_url` now correctly receive `null` for un-linkable products — renders name as plain text, no button.
- Post-deploy spot-check (5 articles): `staub-7-qt` (B000RWGAYG ✓), `breville-the-infuser-espresso-machine` (B0089SSOR6 ✓), `kitchenaid-ceramic-bowl-for-mixer` (B0B4T54RPB ✓), `demeyere-atlantis-fry-pan` (B09YHZ18FL ✓), `masutani-vg1-nakiri-165mm` (B000FR2YWK ✓). All 0 VERIFY, all carrying affiliate tag.
- `NOT_ON_AMAZON` plain-text verification: `hexclad-baking-sheet` — 0 `dp/NOT_ON_AMAZON` links, product name renders as text; other Amazon links in that article are for co-referenced products that ARE on Amazon. Confirmed correct.
- **Note for future sites:** `buildAffiliateUrl` guard must be applied before any new site clone that may have `NOT_ON_AMAZON` entries in `products.yaml`. The fix is now in platform source.

### MLT VERIFY ASIN remediation — Phase 1 prep complete

- Audit exported to `my-little-tablespoon/VERIFY-ASIN-AUDIT.md`: 90 VERIFY ASINs across 7 hubs, 83 products referenced in article bodies, 169 article `.md` files containing hardcoded `dp/VERIFY` links.
- `my-little-tablespoon/VERIFY-ASIN-FILL.csv` — 90-row worksheet for manual ASIN lookup. Columns: product_id, product_name, brand, hub, article_count, blast_radius_rank (1=highest impact), amazon_search_url (convenience link, pre-filled), asin (user fills), notes. Sorted by blast_radius_rank ascending.
- `affiliate-platform/tools/fill-asins-yaml.mjs` — limited-scope Phase 1 tool (272 lines). Updates `products.yaml` only. CLI: `node tools/fill-asins-yaml.mjs --site <site-path> --input <csv-path> [--dry-run]`. Validates ASIN format (`B0[A-Z0-9]{8}` or `[0-9]{10}`), accepts `NOT_ON_AMAZON` sentinel (writes literally), refuses to overwrite existing non-VERIFY ASINs, idempotent. Regex fix: key-detection pattern extended to include `.` for product IDs like `staub-braiser-3.5qt`. Prints prominent Phase 2 warning after every run.
- Phase 1 applied: `my-little-tablespoon/content/products/products.yaml` patched. 90 VERIFY entries resolved — 84 real ASINs, 6 `NOT_ON_AMAZON`. Zero VERIFY entries remain in `products.yaml`.
- Duplicate product IDs flagged: `kitchenaid-pasta-attachment` and `kitchenaid-pasta-roller-attachment` are identical entries (same name, brand, hub, ASIN `B01DBGQR1K`). `kitchenaid-pasta-attachment` is referenced in 4 articles; `kitchenaid-pasta-roller-attachment` in 1. Recommend removing `kitchenaid-pasta-roller-attachment` from `products.yaml` and updating the 1 article that references it — deferred to Phase 2.
- `affiliate-platform/tools/rewrite-article-asins.mjs` — Phase 2 tool (≈310 lines). Rewrites `dp/VERIFY` links in article bodies using `products.yaml` as source of truth. Strips `NOT_ON_AMAZON` links to plain text. Applies frontmatter slug rewrites from `tools/slug-rewrites.json`. CLI: `node tools/rewrite-article-asins.mjs --site <path> [--slug-rewrites <json>] [--dry-run] [--verbose]`. Multi-level name resolution: exact → Jaccard/coverage scoped → Jaccard/coverage global. Parser bug fixed: section-comment boundary products are now saved before context reset.
- `affiliate-platform/tools/slug-rewrites.json` — `kitchenaid-pasta-roller-attachment → kitchenaid-pasta-attachment` (dedup entry). Extend this file for future slug merges.
- Phase 2 applied to MLT. Run result: 169 files changed, 461 VERIFY links resolved, 34 NOT_ON_AMAZON links stripped, 1 slug rewrite applied. 2 generic-anchor links ("This Dutch oven", "spiral dough hook upgrade") resolved manually. Post-run: 0 `dp/VERIFY` in article corpus, 0 occurrences of removed slug.
- `my-little-tablespoon/content/products/products.yaml`: duplicate `kitchenaid-pasta-roller-attachment` block removed.
- **MLT affiliate link status:** 84 working Amazon affiliate links (`dp/{ASIN}?tag=mylittletbsp-20`), 4 NOT_ON_AMAZON products stripped to plain text (hexclad-baking-sheet, masutani-vg1-nakiri, all-clad-pressure-cooker-6qt, made-in-nonstick-frying-pan-10). 2 orphan NOT_ON_AMAZON products (kitchenaid-range/oven) have no article references — no action needed. Live site ready to deploy.

## [1.0.4] — 2026-05-04

### Roundup validator added

- `affiliate-platform/validators/validate-roundup.mjs` — mechanical enforcement of `article-roundup.v1.md`. 708 lines, pure Node, no external deps beyond platform package.json.
- New dep: `gray-matter@^4.0.3` (frontmatter parsing).
- 63 mechanical checks across 6 categories: frontmatter (F01–F11), body structure (B01–B16 plus per-product sub-checks), anti-patterns (A01–A09), FAQ (Q01–Q08), length (L01). 13 manual-review items (M01–M13) reported but do not cause failure.
- CLI: `node validators/validate-roundup.mjs <file-or-directory>`. Exit 0 = all pass, exit 1 = any fail.
- ⚠️ **FSG corpus flag (carried from [1.0.3]):** ~198 FSG roundup articles contain inline `**Pros:**` / `**Cons:**` bullet lists duplicating `<ProductCard />` rendering. Self-test confirms validator correctly flags A02 on all three FSG corpus articles. Remediation deferred — not addressed here.

## [1.0.3] — 2026-05-04

### Roundup article prompt added

- `affiliate-platform/prompts/article-roundup.v1.md` written as canonical versioned prompt for `type: "roundup"` articles.
- Nine sections: output contract, component injection points, voice rules, banned patterns, length contract, FAQ contract, persona injection point, brief injection point, style guide reference.
- Key decisions locked: H3s under single `## Top Picks` H2 (tier grouping exception at 8+ products); no prose Quick Picks glance block (layout renders `<QuickPicks />` automatically); no inline Pros/Cons bullets (layout renders `<ProductCard />` with full pros/cons); hard ban on all dollar figures; 12 AI-tell phrases banned.
- ⚠️ **FSG corpus flag:** Approximately 198 FSG roundup articles contain inline `**Pros:**` / `**Cons:**` bullet lists in the article body that duplicate what `<ProductCard />` already renders. These articles produce doubled pros/cons on the rendered page. Remediation deferred to a separate session — not addressed here.

## [1.0.2] — 2026-05-04

### Visual distinctiveness gap resolved — MLT site.config.yaml

- `my-little-tablespoon/site.config.yaml` visual block updated:
  - `primary_color`: `#2D5016` (forest green, shared with FSG) → `#2B4A7C` (slate blue, hue 217° — 123° from FSG green, 121° from OHT burgundy)
  - `accent_color`: `#C19A4B` (gold, shared with FSG) → `#C27A3B` (copper)
  - `font_headings`: `Lora` (shared with FSG) → `Bitter` (slab serif; categorically distinct from Lora and Playfair Display; weight-complete on Google Fonts)
  - `font_body`: `Source Sans 3` — unchanged (body font is a weaker fingerprint signal)
- No platform files modified. `BaseLayout.astro` already injects font and colour from config dynamically.
- MLT build passes. Verified: `Bitter:ital,wght@0,400;0,600;0,700;1,400` loads in output HTML; `--color-primary: #2B4A7C` set in `:root`.
- `affiliate-platform/CLAUDE.md` Section 6 table updated with actual per-site visual values.
- FSG CLAUDE.md Known Issues cleared (visual gap was the only open item).
- All three sites now have no open footprint violations. Footprint audit from 2026-05-04 fully resolved.

## [1.0.1] — 2026-05-04

### Rule 1 violation resolved — MLT persona background

- `my-little-tablespoon/config/personas/emily.yaml`: `background` changed from `"Senior HR Director, financial services"` to `"Food scientist, consumer packaged goods"`.
- `career_note` updated: fifteen years in food product development in the Boston corridor, moved to Portland, Maine.
- `bio_short` updated: credential-first structure replaces the "N years — and has the [regrets] to prove it" accumulation formula that duplicated FSG's Wendy Hartley.
- `bio_full` updated: leads with professional domain authority (heat-transfer trials, spec sheets, materials knowledge), pivots to personal practice, ends dry. Structurally distinct from FSG bio.
- `voice_notes` updated: technically precise register, not evaluative-sceptical register. Different authority base from Wendy Hartley.
- Region unchanged: Portland, Maine (206 body-copy occurrences, cannot change).
- Name unchanged: Emily Prescott (breaks 200+ bylines if changed).
- `affiliate-platform/CLAUDE.md` Rule 1 status updated to resolved; diversification table updated with actual values.
- FSG and MLT site stubs updated: MLT Known Issues cleared; FSG Known Issues updated to reflect remaining visual gap.

### OHT Wendy Collins drift assessment (no action taken)

- Wendy Collins (OHT) confirmed structurally distinct from Wendy Hartley (FSG): different schema, origin-story bio formula, warm/celebratory register vs. sceptical/evaluative, no `background` or `career_note` fields. No changes required.

## [1.0.0] — 2026-05-04

### First formal contract release

- Added `CLAUDE.md` as the canonical operating contract for all Claude Code sessions in this monorepo.
- Defines six sections: repo ownership boundaries, three non-negotiable rules (persona background uniqueness, product-hub match, no VERIFY ASINs in production), build and run contract, decision authority, done-criteria for five task types, footprint diversification policy.
- All 1,708 words; every rule stated as a yes/no check.
- Site CLAUDE.md files for FSG, MLT, and OHT replaced with thin stubs referencing this file.

### Platform established

- `@platform/core` package created from canonical FSG source (layouts, components, lib, styles, scripts).
- FSG, MLT, and OHT migrated to consume `@platform/core` via `file:../affiliate-platform` dependency.
- Local `src/layouts/`, `src/components/`, `src/lib/`, `src/styles/` deleted from all three site repos.
- All three sites build successfully from platform package.

### Known issues documented

- ~~FSG and MLT share `background: "Senior HR Director, financial services"` — Rule 1 violation.~~ Resolved in [1.0.1].
- FSG and MLT share `primary_color: "#2D5016"` and `font_headings: "Lora"` — visual distinctiveness gap, flagged.
- OHT: `ga4_measurement_id` null, persona images missing, Bing verification not set — all flagged in OHT stub.
