# PIPELINE.md v1.8 — Release Notes

**Released:** 2026-06-06
**Previous version:** v1.7 (2026-06-04)
**Package version:** 2.2.0

---

## What's new since v1.7

### B50 — `already_staged()` extension bug fixed

`producer/producer_main.py` `already_staged()` was checking for `{slug}.docx` instead of
`{slug}.md`. The `.docx` branch was dead code (staging files are always `.md`), meaning the
skip gate could miss already-staged articles under certain code paths.

Fix: removed the `.docx` check. Function now correctly checks `staging/{slug}.md`,
`staging/failed/{slug}.md`, and `articles/{slug}.md`.

**Propagated:** canonical VM `affiliate-platform/producer/producer_main.py` updated. Verified
with dry-run on firstlightfield (all 245 staged articles correctly skipped).

---

### B49 — Multi-hub product schema support

Products in `products.yaml` were limited to a single `hub: slug` field. Products that
legitimately appear in multiple hub contexts (e.g. a telescope mount that belongs in both
`telescopes` and `mounts` hubs) always generated Rule 2 violations.

**Schema change (backward-compatible):**
- Existing `hub: single-string` — continues to work unchanged
- New `hubs: [list, of, slugs]` — products matching any of the listed hubs pass Rule 2

**Files changed:**
- `producer/data_loader.py`: Added `product_matches_hub(product, hub_slug)` helper;
  updated `get_hub_products()` to use it
- `producer/article_builder.py`: Updated hub fallback filtering path
- `producer/tests/test_phase1_output_schema.py`: Updated `test_product_hub_matches_article_hub`,
  `test_all_product_hubs_in_navigation`, `test_product_hub_slugs_are_kebab` to handle both schema forms

---

### B48 — Rainforest book category parameter

Book-keyword articles returned 0–2 products from Rainforest sourcing because plain keyword
searches return physical products (telescopes, cameras) ranked above books. Added
`is_book_article()` detection and `category_id=283155` (Amazon Books node) parameter.

**File changed:** `tools/source-products-rainforest.py`

When keyword or slug contains "book", the Rainforest search is scoped to the Amazon Books
category, returning 7+ relevant results.

---

### B45 — Semantic slug dedup in xlsx-to-pipeline.mjs

The V1 slug dedup caught exact keyword duplicates but missed semantic near-duplicates where
modifier words differ (best/good/great/top/starter/beginner). Site 17 launched with 10 such
near-dups in the telescopes hub (all fell through to "product shortfall" at production time).

**Fix:** Post-processing step added to `tools/xlsx-to-pipeline.mjs`. After pipeline.json is
built, articles within each hub are grouped by their modifier-stripped token set. Articles
whose stripped tokens match a higher-volume article in the same hub are marked `status: "dupe"`
with a `dupe_of` reference.

**MODIFIER_WORDS stripped:** best, good, great, top, worst, affordable, cheap, budget,
inexpensive, expensive, premium, basic, simple, easy, a, an, the

**Test result against Site 17 book seeds:** 6/12 articles correctly detected as near-dups
(astronomy-books, good-astronomy-books, top-astronomy-books, great-astronomy-books,
astronomy-books-for-beginners, good-astronomy-books-for-beginners). antique-astronomy-books
and old-astronomy-books correctly NOT flagged (non-modifier differentiators).

---

### Header.astro — Single-category nav flatten

Sites with a single navigation category (e.g. firstlightfield: Astronomy) rendered as a
single dropdown containing all hubs instead of showing hubs directly at the top level.

**Fix:** Added single-category detection to canonical `src/components/Header.astro`:
```astro
const flatNav = nav.categories.length === 1 && nav.categories[0].hubs?.length > 0
const navItems = flatNav
  ? nav.categories[0].hubs.map(h => ({ ...h, hubs: [] }))
  : nav.categories
```
Multi-category sites are unaffected (`flatNav = false`, `navItems = nav.categories`).

---

### Portfolio V18/V20 verification — 2026-06-06

- **V18 (persona-claims):** 0 HARD violations across all 12 sites (3 previously-unresolved
  violations fixed: 15 strengthmill "my garage" instances, 1 northwoods-overland "my garage",
  2 saunassosimple "my setup")
- **V20 (meta-leakage):** 0 violations across all 12 sites
- **Build checks:** FSG ✓ (WARNs only), Strengthmill ✓ (WARNs only), firstlightfield ✓ (0 FAIL)

---

### Site 17 — firstlightfield.com — LIVE

- 245 articles, 6 hubs (telescopes, mounts, eyepieces, astrophotography, binoculars, accessories)
- Custom domain: firstlightfield.com (HTTP 200)
- GA4: G-MEQ56RP85W confirmed firing
- V18: 0 HARD, V20: 0 leakage
