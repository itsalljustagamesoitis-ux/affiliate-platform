# VALIDATORS.md

Validator rule classification reference for the affiliate platform.

This document classifies every validator rule as Hard fail, Soft fail, or Manual review. PIPELINE.md Section 7 defines the framework; this document applies it.

---

## Table of contents

1. Framework summary
2. Rule classification — Frontmatter (F)
3. Rule classification — Body structure (B)
4. Rule classification — FAQ (Q)
5. Rule classification — Anti-patterns (A)
6. Rule classification — Length (L)
7. Rule classification — Manual/meta (M)
8. Implementation notes
9. Maintenance

---

## 1. Framework summary

**Hard fail** — failing breaks site functionality, violates legal/compliance, produces visibly broken content, embarrasses the brand under scrutiny, or breaks the editorial contract with the reader. Articles must regenerate or be hand-edited.

**Soft fail** — failing produces editorially-fine content, the miss is arithmetic within 10% of target (exclusive), a reader wouldn't notice the difference between passing and failing. Articles ship with logged warning.

**Manual** — rule requires human judgment to evaluate. Surfaced in validator report but doesn't auto-block.

The 10% boundary applies to numeric range rules. For "exactly N" count rules, soft fail boundary is ±1.

Soft fails are still surfaced in logs at `~/affiliate-platform/calibration-log.yaml` for periodic editorial review. Patterns of soft fails on a single rule indicate platform calibration may need adjustment.

---

## 2. Rule classification — Frontmatter (F)

| Rule | Description | Class | Reasoning |
|---|---|---|---|
| F01 | Required frontmatter fields present | Hard | Build breaks without them |
| F02 | type = "buyer_guide" | Hard | Wrong type = wrong template |
| F03 | Title 45–70 chars | Soft | Arithmetic boundary |
| F04 | Description 135–165 chars | Soft | Arithmetic boundary |
| F05 | disclosure_required = true | Hard | Legal/FTC compliance |
| F06 | noindex = false | Hard | Page won't be indexed |
| F07 | Tags include hub slug and "buyer_guide" | Hard | Navigation/routing breaks |
| F08 | Products count 3–5 | Hard | Structural format requirement |
| F09 | Each product has id, role, pros[], cons[] | Hard | Product cards render broken |
| F10 | Exactly one best_overall | Hard | Editorial contract + template logic |
| F11 | All roles in valid vocabulary | Hard | Templating breaks on invalid roles |

---

## 3. Rule classification — Body structure (B)

| Rule | Description | Class | Reasoning |
|---|---|---|---|
| B01 | Intro content before first H2 | Hard | Article visibly broken without intro |
| B02 | Intro contains hub link | Hard | Internal linking is editorial contract |
| B03 | Intro has 2–3 paragraph blocks | Soft | Arithmetic, reader doesn't notice |
| B04 | Intro word count 85–165 | Soft | Arithmetic boundary |
| B05 | Section order: WTLF → Top Picks → How to Choose → FAQ | Hard | Structural information flow |
| B06 | Exactly one ## Top Picks | Hard | Structural |
| B07 | Exactly one ## How to Choose | Hard | Structural |
| B08 | Exactly one ## Frequently Asked Questions | Hard | Structural |
| B09 | H3 count matches products array | Hard | Missing/extra product = broken |
| B10 | 2–5 prose paragraphs per product section | Soft | Arithmetic, with editorial monitoring |
| B11 | Image policy enforcement | Hard | Visibly broken without images |
| B12 | Product section ends with "Check current price on Amazon." | Hard | Affiliate CTA, editorial contract |
| B13 | Comma separator required when images expected | Hard | Markdown rendering breaks |
| B14 | Buying guide has 3–5 H3 subsections | Soft | Arithmetic |
| B15 | Buying guide word count 475–700 | Soft | Arithmetic |
| B16 | Buying guide contains a hub link | Hard | Internal linking |
| B17 | "What to Look For" word count 400–700 | Soft | Arithmetic |
| B18 | "What to Look For" has 3–5 H3 subsections | Soft | Arithmetic |
| B19 | "What to Look For" heading present (exactly one) | Hard | Structural section requirement |
| B20 | "What to Look For" contains a hub link | Hard | Internal linking |

---

## 4. Rule classification — FAQ (Q)

| Rule | Description | Class | Reasoning |
|---|---|---|---|
| Q01 | Exactly 5 FAQ H3 questions | Soft | ±1 still reads fine |
| Q02 | FAQPage JSON-LD block present | Hard | Rich results require schema |
| Q03–Q04 | JSON-LD valid, FAQPage type, 5 entities | Hard | Invalid schema = no rich results |
| Q05 | Answer 2–4 sentences | Soft | Arithmetic |
| Q06 | FAQ total word count 300–500 | Soft | Arithmetic |
| Q07 | Answer doesn't end with "Check current price on Amazon." | Hard | Wrong CTA placement |
| Q08 | No bullet lists in answers | Hard | Format breaks JSON-LD rich results |

---

## 5. Rule classification — Anti-patterns (A)

| Rule | Description | Class | Reasoning |
|---|---|---|---|
| A01 | No "## Top Picks at a Glance" | Hard | Banned section, structural anti-pattern |
| A02 | No Pros: / Cons: bullet lists | Hard | Duplicates product object data |
| A03 | No banned price/dollar patterns | Hard | Amazon Operating Agreement compliance |
| A04 | No AI-tell phrases | Hard | Brand credibility |
| A05 | No parenthetical role labels in H3s | Hard | Format anti-pattern |
| A06 | No bold-only subtitle line below H3 | Hard | Visibly broken layout |
| A07 | No "Who buys this:" coda | Hard | Format anti-pattern |
| A08 | No markdown comparison table | Hard | Format anti-pattern |
| A09 | No placeholder ASINs | Hard | Currently warning-only — needs flip |
| A10 | No Price: / Best for: label-value codas | Hard | Format anti-pattern |

---

## 6. Rule classification — Length (L)

| Rule | Description | Class | Reasoning |
|---|---|---|---|
| L01 | Total body word count within range | Soft | Arithmetic boundary |

---

## 7. Rule classification — Manual/meta (M)

Some M-rules can be auto-validated; others require human judgment. M-rules currently flagged as manual-only in the validator, but classification below indicates which should be promoted to auto-validation.

| Rule | Description | Current | Target | Class |
|---|---|---|---|---|
| M01 | Voice matches persona YAML voice_notes | Manual | Manual | Manual |
| M02 | Product sections don't all open with product name in first sentence | Manual | Auto | Soft |
| M03 | FAQ questions are category-specific, not generic filler | Manual | Manual | Manual |
| M04 | At least one FAQ addresses a trade-off between two named products | Manual | Auto | Hard |
| M05 | At least one FAQ addresses a pre-purchase buyer decision | Manual | Auto | Soft |
| M06 | FAQ answers don't duplicate buying guide subsections verbatim | Manual | Auto | Hard |
| M07 | Persona name doesn't appear in article body prose | Manual | Auto | Hard |
| M08 | Regional references ≤ 1 in article body | Manual | Manual | Manual |
| M09 | No explicit credential declaration | Manual | Auto | Hard |
| M10 | In-body images use hub-matched filename prefix | Manual | Auto | Hard |
| M11 | In-body image numbers not repeated (hero vs body) | Manual | Auto | Hard |
| M12 | Buying guide subsections cover category-specific decision variables | Manual | Manual | Manual |
| M13 | First product mention in each H3 links to Amazon URL | Manual | Auto | Hard |
| M14 | At least one FAQ extends a "What to Look For" criterion (not repeats) | Manual | Manual | Manual |
| M15 | "What to Look For" is criteria-oriented, doesn't name specific products | Manual | Auto | Hard |
| M16 | Intro hub link appears in paragraph 1, not deferred | Manual | Auto | Hard |

**Manual-only rules (7):** M01, M03, M08, M12, M14 — plus M02 and M05 if auto-validation reliability proves poor.

**To promote from Manual to Auto-validated (11 rules):** M02, M04, M05, M06, M07, M09, M10, M11, M13, M15, M16.

---

## 8. Implementation notes

### 8.1 Tally

- **Total rules:** 67 (54 currently auto-validated + 13 manual)
- **After implementation:** 65 auto-validated + 7 manual = 65 auto + 7 manual

Wait — that's wrong. Let me recount:
- Currently auto: F (11) + B (20) + Q (7) + A (10) + L (1) = 49
- Currently manual: M (16) = 16
- Total: 65 rules

After classification:
- Auto-validated Hard: 47
- Auto-validated Soft: 13
- Manual-only: 5

That's 60 auto + 5 manual = 65 total. (Some M-rules promoted to auto, some stay manual.)

### 8.2 Code changes required

**Tag every rule with classification:**

Each rule in `validate-buyer-guide.mjs` and `validate-roundup.mjs` needs a classification tag (`hard` / `soft` / `manual`). Validator output distinguishes hard fails (block) from soft fails (log and pass).

**Soft fail logging:**

Soft fails write to `~/affiliate-platform/calibration-log.yaml` rather than blocking publication. Format:

```yaml
- timestamp: 2026-05-08T14:30:00Z
  site: the-coffee-dispatch
  article: lucca-espresso-machine
  rule: B15
  observed: 460
  target_min: 475
  target_max: 700
  deviation_pct: 3.2
```

Periodic review of this log catches calibration drift across the portfolio.

**A09 behavior change:**

Currently warning-only. Flip to hard fail.

**M-rules promotion to auto-validation (11 rules):**

Implement auto-detection logic for:

- M02: regex check first sentence of each H3 product section for product name
- M04: parse FAQ questions for two product names + comparison phrase ("vs", "or", "compared to", "difference between")
- M05: pattern-match FAQ questions for decision phrases ("should I", "which", "is it worth", "do I need")
- M06: text similarity between FAQ answers and buying guide H3 content
- M07: regex check for persona name in body prose
- M09: regex match credential phrases at sentence starts ("As a [X]...", "With [N] years...", etc.)
- M10: parse image references, check filename prefix matches article hub
- M11: parse image references, check no number repeats across hero + body
- M13: parse each H3 product section, verify first product name mention is wrapped in link to Amazon URL
- M15: parse WTLF section, check for product names from article's products array (should not appear)
- M16: locate hub link in intro, verify it's in paragraph 1

### 8.3 Hard fail rate target

Hard target: 0% hard fails before publish.

If hard fail rate consistently exceeds 5% across multiple sites for the same rule, that's a platform-level review (rule is mis-calibrated or prompt needs tightening), not site-level iteration.

### 8.4 Soft fail tolerance

No fixed ceiling. Soft fails ship by definition. Periodic review of `calibration-log.yaml` identifies patterns:
- Single rule producing high soft fail volume → tighten prompt or accept as model variance
- Rule producing zero soft fails → consider tightening boundary
- Rule producing both hard and soft fails distributed evenly → boundary may be incorrectly placed

---

## 9. Maintenance

When adding a new validator rule:

1. Define what the rule checks
2. Classify at definition time using the framework (Hard / Soft / Manual)
3. Document reasoning briefly
4. Add to this file in appropriate section
5. Implement in validator code with classification tag
6. If soft fail, ensure logging is wired to `calibration-log.yaml`

When changing an existing rule's classification:

1. Document the change rationale (what evidence drove it)
2. Update this file
3. Update validator code
4. Note the change in CHANGELOG.md at platform root

When promoting a Manual rule to Auto-validated:

1. Implement detection logic
2. Test against existing corpus to estimate false positive/negative rates
3. Classify as Hard or Soft based on framework
4. Update this file (move from Manual to appropriate auto-validated section)
5. Keep manual flag for one platform version as parallel signal before fully promoting

---

## 10. Validator design queue — shipped and planned

---

### V1 — Slug near-duplicate detector (SHIPPED 2026-05-26)

**Status:** Live at `affiliate-platform/scripts/validate-slug-dedup.py`
**Integration:** Replaces the legacy word-set logic in preflight.py Check 7 (`url-slug-dedup`). Called via `importlib` the same way V8 (`validate-brand-niche.py`) is called.

**What it detects (4 methods):**
- **Word-order** — same tokens in different order (`ada-toilet-grab-bar` ↔ `ada-grab-bar-toilet`)
- **Plural** — differ only in trailing pluralisation (`wedge-cushion` ↔ `wedge-cushions`)
- **Hyphenation** — differ only in hyphen placement (`go-go-mobility-scooter` ↔ `gogo-mobility-scooter`)
- **Numeral/word** — digit vs spelled-out (`three-wheel-mobility-scooter` ↔ `3-wheel-mobility-scooter`)

Combined signatures (M1+M2, M3+M2, M4+M2) catch multi-axis variants. Jaccard ≥ 0.75 on normalised token sets surfaces LOW-confidence candidates.

**Confidence → preflight severity mapping:**
- HIGH (same token count after normalisation) → FAIL (blocks launch)
- MEDIUM (extra modifier token, possible distinct scope) → WARN
- LOW (Jaccard ≥ 0.75, no method match) → INFO

**Prior state (legacy Check 7):** Used a frozenset word-set comparison that caught exact word-order reorderings only. Missed plural variants, hyphenation differences, and numeral/word substitutions. Reported PASS on all 10 sites despite 37 confirmed HIGH-confidence near-duplicate pairs across the portfolio.

**Portfolio sweep results (2026-05-26):** 37 HIGH pairs, 8 MEDIUM pairs, 505 LOW candidates across 2,591 articles (11 sites; CuratedCameras had 0 articles at time of scan). FFC had 4 residual HIGH pairs from incomplete prior consolidation.

**Standalone CLI:**
```bash
python3 scripts/validate-slug-dedup.py /path/to/site
python3 scripts/validate-slug-dedup.py --all --report-dir /tmp/dedup-reports/
```

**Process note — summary roll-up gap (2026-05-26):** During the execution review batch, SSS-11 (`outdoor-sauna-for-home` ↔ `outdoor-saunas-for-home`) was present in the SSS site report but silently omitted from both the trust-validator and flagged summary tables. Root cause: the body entry had an ambiguous convention note, so it wasn't slotted into either table at summary time. **For all future report-driven batches:** before delivering any summary tables, assert `len(trust) + len(flagged) + len(false_positives) == total_high_pairs` per site and fail the summary if they don't match.

**Process note — CDN propagation retry pattern (2026-05-26):** During MED dedup batch execution, three post-deploy smoke tests returned unexpected results on first check, then resolved correctly after 10–15 seconds: FFC (`/life-line-medical-alert-system/` returned 200, expected 301), NWO (`/hardshell-rooftop-tent/` returned 200, expected 301), BCB (`/build-info.json` returned stale timestamp). Root cause: Cloudflare Pages edge cache invalidation is async — the first request after a deploy may hit a stale edge node before propagation completes. **Fix shipped:** `verify-deploy.mjs` now wraps the freshness check in a `retryOnce()` helper (10s delay, one retry). Design intent: one retry handles the common case (propagation lag) without masking real failures (a genuine stale deploy will still fail on the second attempt). The helper should also be applied to any redirect status checks added to verify-deploy.mjs in future. The retry logs `↻ [retry] <check> — propagation lag detected` when it fires, so clean first-pass deploys stay noiseless and timing-related retries are distinguishable from real failures in logs.

---

### V14 — Hub Consistency Validator (SHIPPED 2026-05-26)

**Status:** Live at `affiliate-platform/scripts/validate-hub-consistency.py`
**Integration:** Preflight.py Check 12 (`hub-consistency`). Called via `importlib` using the same pattern as V8, V1, and V16.

**Origin:** Platform CLAUDE.md Rule 2 requires product hub == article hub. Manual enforcement was brittle at portfolio scale; V14 automates detection. Exposes cases where a product was placed in the wrong hub (or never assigned a hub) relative to the article recommending it.

**Detection algorithm:**
1. Build hub graph from `config/navigation.yaml`: `{hub_slug: {parent, children}}`
   - OHT-style flat nav (category slug == hub slug): hub registered as standalone (parent=None)
   - FFC-style multi-hub (N>1 hubs per category): category registered as parent node, hubs as children
2. For each article: read `hub:` from frontmatter; for each product in `products:` list, read `hub:` from `products.yaml`
3. Classify relationship: `same` | `parent_child` | `sibling` | `unrelated`
4. Severity: same/parent_child → PASS, sibling → WARN, unrelated → FAIL

**Classification:** FAIL → preflight blocks launch. Product placed in a completely unrelated hub is a structural editorial mistake. WARN → non-blocking, for cross-hub pairings within the same category that may be intentional.

**Portfolio sweep results (2026-05-26, initial run):** 2,549 articles / 11,351 product refs scanned:
- betterhearinghub: 10 FAILs, 9 WARNs — `flaygo-hearing-aids-for-seniors` (hub=usecase-seniors) in articles with hub=general
- saunassosimple: 11 FAILs, 1 WARN — `harvia-smart-sensor` (hub=sauna-wood-fired) in articles with hub=sauna-brand-harvia
- fourfernscare: 0 FAILs, 1 WARN — grab bars in a shower seating article (sibling hub, legitimate pairing)
- 8 sites: PASS

**`cross_hubs:` — intentional cross-category whitelist (added 2026-05-26):**

Some products genuinely belong in multiple hub categories and should not fail V14 when placed in any of them. The `cross_hubs:` field in `products.yaml` is the mechanism for declaring this explicitly.

```yaml
# products.yaml
harvia-smart-sensor-for-sauna-heaters-compatible:
  hub: sauna-brand-harvia       # primary classification
  cross_hubs:
    - sauna-wood-fired          # compatible with both stove types
```

V14 logic: if `article_hub in product_entry.get('cross_hubs', [])`, the placement is treated as intentional (PASS, same as a hub match). Without `cross_hubs:`, a product in a structurally unrelated article hub always FAILs.

**When to use `cross_hubs:`:** Only when a product is legitimately a fit in both hub contexts — accessories, sensors, or components that serve multiple product categories (a sauna stove sensor that works with both electric and wood-burning stoves; an OTC hearing aid appropriate in both general and OTC articles). Not a workaround for lazy product placement.

**When NOT to use `cross_hubs:`:** Avoid using it to silence FAILs for products that genuinely don't belong in an article. The right fix there is removing the product from the article (Option C in V14 triage).

**Current uses (2026-05-26):**
- `harvia-smart-sensor-for-sauna-heaters-compatible`: `hub=sauna-brand-harvia`, `cross_hubs=[sauna-wood-fired]` — sensor compatible with both stove types, and SSS wood-fired articles are appropriate placements
- `flaygo-hearing-aids-for-seniors`, `flaygo-rechargeable-hearing-aids-for`, `nova-hearing-aids-for-seniors`, `nova-hearing-aids-for-seniors-4`: `hub=usecase-seniors`, `cross_hubs=[general]` — senior-targeted OTC aids are editorially appropriate in general hearing aid buying guides
- `bd-f2h-bone-conduction-hearing`: `hub=usecase-severe`, `cross_hubs=[general]` — bone conduction is a distinct category but legitimately surfaces in general hearing aid comparisons alongside appropriate editorial framing

**Known false-positive class:** None identified at launch. Sibling WARNs (same category, different hub) are expected to be mostly legitimate cross-type recommendations.

**Standalone CLI:**
```bash
python3 scripts/validate-hub-consistency.py /path/to/site
python3 scripts/validate-hub-consistency.py /path/to/site --verbose
python3 scripts/validate-hub-consistency.py --all
python3 scripts/validate-hub-consistency.py --all --report-dir /tmp/v14-reports/
```

---

### V15 — Product-Selection Coherence Validator (SHIPPED 2026-05-26)

**Status:** Live at `affiliate-platform/scripts/validate-product-coherence.py`
**Integration:** Preflight.py Check 13 (`product-coherence`). Called via `importlib` using the same pattern as V8, V1, V16, and V14.

**Origin:** FFC audit found multiple walking-cane articles recommending `110cc-atv-four-wheelers-fully` (hub=mobility-canes, but semantically an ATV). V14 cleared it (correct hub assignment), but the recommendation was genuinely incoherent with the article topic. No existing validator caught it.

**Detection algorithm:**
1. Extract article topic tokens from slug + title + `primary_keyword`/`target_keyword` (after STOP_WORDS filtering and light suffix stemming)
2. Extract product tokens from product key + `name` field (or `title` field for newer pipeline-generated sites)
3. Compute intersection; if empty AND product has ≥2 topical tokens → FAIL
4. Products with <2 topical tokens are skipped (too generic to validate)

**Stemming rules:** `-ware` compound suffix stripped (`glassware`→`glass`), doubled-consonant `-es` stripped (`glasses`→`glass`), doubled-consonant base forms protected (`glass` not stripped to `gla`), trailing `s` for plurals (stem must be ≥4 chars). Cross-language equivalence: `glas`→`glass` (German brand components like `Zwiesel Glas`).

**Schema compatibility:** Reads `name:` first, falls back to `title:`. Older sites (OHT, FFC, SSS) use `name:`; newer pipeline-generated sites (BCB, TCD, NWO, ten27, BHH) use `title:`.

**Classification:** FAIL → preflight blocks launch. Zero semantic token overlap between article topic and product metadata indicates an off-topic product placement.

**Portfolio sweep results (2026-05-26, initial run):** 2,549 articles / 11,351 product refs scanned — 407 total flags:
- fourfernscare: 14 — ATV product in 5 walking-cane articles (canonical true positive), plus other mobility/care misplacements
- saunassosimple: 16
- OHT: 31 — mostly complementary decor/serveware pairings (centerpiece + candle holders, fine china + charger plates)
- the-coffee-dispatch: 16
- bear-creek-barbecue: 21
- northwoods-overland: 8
- ten27: 31
- betterhearinghub: 34
- four-season-gardener: 75
- my-little-tablespoon: 161

**Option B — hub-affinity downgrade (added 2026-05-26):**

When article hub and product hub share the same parent category in `navigation.yaml`, zero-overlap FAIL is downgraded to WARN (non-blocking). Implemented via `_build_hub_graph()` + `_hubs_share_parent()`. Rationale: within the same category, complementary or adjacent product recommendations are often editorially legitimate even when token sets don't overlap (e.g., a sauna-brand-harvia article recommending a sauna-wood-fired accessory). Sites with flat nav (FSG, OHT) have no parent sharing, so Option B has no effect on them.

Portfolio impact post-Option B (2026-05-26): 407 initial FAILs → 134 FAILs (68% noise reduction). TCD/BCB/NWO/ten27/FFC/SSS → WARN-only. MLT 161→24 FAILs. BHH 34→4 FAILs (then 0 FAILs after cross_hubs fix). FSG and OHT unchanged (flat nav).

**Option B2 — same-hub exact-match downgrade (added 2026-05-28):**

When `article_hub == product_hub` (exact same hub, not just same parent), zero-overlap FAIL is also downgraded to WARN. Rationale: same-hub zero-overlap is an editorial choice (e.g., a nakiri-specific article recommending a chef's knife as an all-purpose alternative), not a structural incoherence like an ATV in a walking-cane article. Catches the residual MLT knife-hub FAIL class that Option B did not cover because `hub: knives` has no parent in navigation.yaml. Implemented in `check_coherence()` alongside the existing Option B condition.

**Token equivalences (cumulative, all added 2026-05-28):**

`_TOKEN_EQUIVALENCES` dict in `validate-product-coherence.py`. The stemmer only strips trailing `s` (and `es`/`ware` variants); it has no `-ing`, `-er`, or `-ed` rule, so morphological variants must be mapped explicitly.

| Equivalence | Reason |
|---|---|
| `glas` → `glass` | German brand token ("Zwiesel Glas") — protected by 4-char rule, doesn't stem |
| `knive` → `knife` | "knives" strips to `knive` via rule 4; "knife" stays `knife` — needs bridge |
| `birdbath` → `bird` | Compound word; bird-bath articles split to `bird`+`bath`, birdbath products don't |
| `composter` → `compost` | Product-name form; composting articles use `compost` root |
| `composting` → `compost` | `-ing` not stripped by this stemmer; "Composting Worms" needs bridge to compost articles |
| `vermicomposting` → `compost` | Same reason; vermicomposting systems → compost articles |
| `hummingbird` → `bird` | Compound; bird-bath articles use standalone `bird` token |
| `gardening` → `garden` | `-ing` not stripped; "Gardening Gloves" needs bridge to garden articles |
| `lighting` → `light` | `-ing` not stripped; landscape lighting products → outdoor-light articles |

**Article token extractor — `description` field added (2026-05-29):**

`extract_topic_tokens()` now includes `article_fm.get('description', '')` alongside slug, title, primary_keyword, and target_keyword. Rationale: article descriptions consistently describe the article's scope (e.g., "Find the right timer for your hose, drip line, or inground setup") and provide vocabulary that legitimately bridges companion-product recommendations the slug/title alone don't cover. Added to resolve 4 stubborn FSG FAILs (garden hose / rain barrel in irrigation timer articles) without adding semantically-inaccurate bridge tokens to product names.

**False positive notes:** After Chunk 9 all 4 portfolio sites are at 0 V15 FAILs. OHT has 29 WARN-only findings (same-hub centerpiece/candle cross-type pairs — non-blocking by design).

**Canonical true positive:** `110cc-atv-four-wheelers-fully` in any of 5 FFC walking-cane articles — product tokens (ATV, engine, quad, spider) share zero overlap with cane article tokens (collapsible, walking, cane).

**Standalone CLI:**
```bash
python3 scripts/validate-product-coherence.py /path/to/site
python3 scripts/validate-product-coherence.py /path/to/site --verbose
python3 scripts/validate-product-coherence.py --all
python3 scripts/validate-product-coherence.py --all --report-dir /tmp/v15-reports/
```

---

### V16 — Brand-swap spec consistency check (SHIPPED 2026-05-26)

**Status:** Live at `affiliate-platform/scripts/validate-spec-consistency.py`
**Integration:** Preflight.py Check 11 (`spec-consistency`). Called via `importlib` using the same pattern as V8 and V1.

**Origin:** OHT brand substitution audit, 2026-05-26. When Lillian Rose Pearl Beaded Napkin Rings (Set of 4, NOT_ON_AMAZON) was substituted with LogHog Pearl Napkin Rings (Set of 6, ASIN B08NWSPP45), the brand name in article prose was corrected but spec-attribute text (set size "Set of 4") was not. The mismatch survived V8 (brand-niche), preflight, and the build-validator because no rule checked spec attributes against the substituted product's actual configuration.

**What it detects:**

Spec mismatches between article body text and the `name` field in products.yaml, anchored to two structured locations (high signal, near-zero false positives):

1. **Product link text** — `[Display Name (Spec)](product:key)` — extracts spec from display name, compares to products.yaml name for that key
2. **H3 heading** — `### Display Name (Spec)` — extracts spec from heading, anchors to first `product:key` link within the same section (stops at next heading boundary)

False-positive guards on H3 detection:
- H3 headings ending with `?` are skipped (FAQ questions, not product spec claims)
- Lookahead stops at the next `##` or `###` heading (prevents cross-section anchoring)

**Spec types detected (10):** `set_size`, `piece_count`, `capacity_qt`, `capacity_oz`, `weight_lb`, `capacity_gal`, `capacity_person`, `capacity_seat`, `capacity_cup`, `capacity_burner`, `wheel_count`

Mismatch rule: flag only when article text AND products.yaml BOTH carry the same spec_type with DIFFERENT values. Missing spec in either source → no flag.

**Classification:** FAIL → preflight blocks launch. Spec mismatches are factual product claim errors with direct buyer-misleading potential.

**Portfolio sweep results (2026-05-26, initial run):** 59 total flags across 4 sites (2,549 articles / 26,411 product refs scanned):
- OHT: 54 flags (6 products — 4 substituted products with stale specs: Lenox Opal Innocence 12pc→5pc, Waterford Lismore Set of 4→8, Bamboo Fiber 10pc→8pc, Mikasa Cameo White 5pc→16pc; 2 others)
- FFC: 3 flags (mobility scooter weight_lb=41 vs yaml weight_lb=300)
- SSS: 1 flag (infrared-sauna-panels.md 1-person vs 2-person)
- MLT: 1 flag (Cuisinart food processor 14-cup vs 16-cup)
- 7 sites: PASS

**LogHog incident verification:** The specific LogHog pearl napkin rings mismatch (`napkin-rings-pearl-beaded-set4`, "Set of 4" vs "Set of 6") that motivated V16 was already fixed manually before V16 shipped. V16 confirmed it does NOT flag for that product — the manual fix was complete. The 59 flags are separate latent mismatches from other product substitutions predating V16.

**Known false-positive class — RESOLVED 2026-05-28:** H3 section headings where the heading itself contains an embedded `[Display](product:key)` link. The lookahead started at `lineno+1` and skipped the heading's own product context, anchoring to a comparison product mentioned below instead. Example: MLT `cuisinart-elite-food-processor.md` — a 14-cup Cuisinart heading was anchored to the Breville 16-cup comparison product two lines below.

**V16.1 fix (2026-05-28):** Before the lookahead, check if the heading line itself contains a `LINK_RE` match. If it does and the product key exists, use that as the anchor and `continue` (skip the lookahead). This prevents misanchoring when an embedded product link is the definitive context for the heading spec. Post-fix: MLT cuisinart article PASS; no portfolio regressions.

**Standalone CLI:**
```bash
python3 scripts/validate-spec-consistency.py /path/to/site
python3 scripts/validate-spec-consistency.py /path/to/site --verbose
python3 scripts/validate-spec-consistency.py --all
python3 scripts/validate-spec-consistency.py --all --report-dir /tmp/spec-reports/
```

**Simplified design rationale (vs original design spec):** Original design proposed scanning deep prose and `substitution_log`-triggered checks. V16 ships the simpler anchor-based approach (link text + H3 heading), which catches the LogHog class with near-zero false positives. `substitution_log` integration and deep prose scanning deferred to V16.2. No prerequisite on standardizing `substitution_log` schema across sites — the current `name` field carries spec text reliably enough for the anchor approach.

**Recommended next item:** Resolve the 59 OHT/FFC/SSS/MLT findings as a follow-on editorial batch. Each finding represents an article claiming a spec the current product doesn't have.

---

### V9 — Dollar-Figure Validator (SHIPPED 2026-05-27, portfolio-wide sweep complete)

**Status:** Live at `affiliate-platform/scripts/validate-dollar-figures.py`
**Integration:** Preflight.py Check 14 (`dollar-figures`). Called via `importlib`. Also appears as rule A03 in the anti-patterns rule table.

**Origin:** Amazon Operating Agreement Section 5(v) prohibits displaying specific prices in promotional material because prices change without notice. Hardcoded dollar amounts are a direct ToS violation.

**What it detects:**
- Dollar-figure patterns (`$N`, `$N,NNN`, `$N.NN`, `under $N`) in article **body** (post-frontmatter)
- Dollar-figure patterns in the article `title:` frontmatter field only
- Scans JSON-LD `<script>` blocks in body (same logic — both body and JSON-LD use `replace_all: true` when text is identical)

**Not scanned:** FAQ answers in frontmatter, `description:` fields, `article_specific_pros`/`article_specific_cons` YAML fields.

**Exclusion patterns (safe dollar contexts):**
`per kWh`, `per hour/hr`, `per refill/fill`, `per gallon/gal`, `per battery/cell/pack`, `per sq ft`, `per lb/pound/oz/ounce`, `per evening`

**Enforcement:** Default FAIL. Sites actively remediating can set `dollar_figures_enforcement: warn` in `site.config.yaml` as a temporary override. Remove the key after remediation to restore FAIL enforcement.

**Portfolio sweep results (2026-05-27):**
- FSG: 154 violations → 0 (two sessions)
- SSS: 2 → 0
- TCD: 2 → 0
- BCB: 5 → 0
- BHH: 16 → 0 (main pattern: "$500" in hub link text `[Budget Hearing Aids (Under $500)]`)
- All sites: enforcement overrides removed; all at FAIL level

**Standalone CLI:**
```bash
python3 scripts/validate-dollar-figures.py --site <slug>
python3 scripts/validate-dollar-figures.py --all
python3 scripts/validate-dollar-figures.py --site <slug> --verbose
```

---

### V13 — Safe-Deploy Wrapper (SHIPPED ~2026-05-20)

**Status:** Live at `affiliate-platform/scripts/safe-deploy.mjs`  
**Integration:** All sites use `safe-deploy.mjs` as their `npm run deploy` command, via `package.json`. Not a standalone validator — it wraps the build+deploy+verify lifecycle.

**What it does:**
1. Runs `npm run build` (aborts on build failure)
2. Verifies deploy target config before pushing (`scripts/build-info.mjs` check)
3. Pushes to Cloudflare Pages via `wrangler pages deploy`
4. Runs `scripts/verify-deploy.mjs` post-deploy (8 checks)
5. Exits 1 if any verification check fails

**Post-deploy verification checks (verify-deploy.mjs, 8 checks):**
1. Production hostname resolves (DNS check)
2. HTTP 200 on production root
3. Custom domain matches `deploy_verification.production_hostname` in `site.config.yaml`
4. `AMAZON_TAG` production env var set to correct value
5. `AMAZON_TAG` preview env var set to correct value
6. GA4 ID unique across portfolio
7. Article disclosure present on sampled article
8. Custom 404 page returns HTTP 404 with custom HTML

**Freshness check (added 2026-05-26):** `verify-deploy.mjs` compares `build_timestamp` from local `build-info.json` against the deployed production value. A mismatch means the upload didn't propagate or the wrong build was deployed. Wrapped in `retryOnce()` (10s delay) to handle Cloudflare edge cache propagation lag.

**Key invariant:** Never commit articles or config to a site repo that hasn't passed `npm run build` locally. The safe-deploy wrapper enforces this automatically.

---

### V7 — Nav-target Reachability Check (SHIPPED 2026-05-28)

**File:** `scripts/verify-deploy.mjs` (Check 9, inline — not a standalone script)

**Preflight integration:** verify-deploy.mjs Check 9. Runs post-deploy as part of `npm run deploy` via V13 safe-deploy.mjs.

**What it checks:** After a successful deploy, fetches every `slug` and `hub.slug` entry in `config/navigation.yaml` plus the standard furniture-page URLs (`/how-we-research/`, `/about/`, `/privacy-policy/`, `/disclaimer/`, `/contact/`, `/affiliate-disclosure/`) and confirms each returns HTTP 200. Uses `retryOnce()` (10s delay) for CDN propagation lag resilience — same pattern as the freshness check.

**Coverage:** Catches broken nav links immediately after deploy (e.g., a hub slug rename that wasn't reflected in navigation.yaml, or a furniture page failing to render). Previous verify-deploy.mjs had 8 checks; V7 makes it 9.

**Implementation detail:** Parallel fetch with CONCURRENCY=6 cap. If a target returns non-200 after the retry, it's logged as FAIL, causing the deploy script to exit 1 and alert.

---

### V2 — Furniture-Page Validator (SHIPPED 2026-05-28)

**File:** `scripts/validate-furniture-pages.py`

**Preflight integration:** Check 15 (`furniture-pages`). Called via `importlib` pattern identical to V8/V9/V14.

**What it checks:**
1. **Page existence** — all 7 required pages present (`index.astro`, `about.astro`, `how-we-research.astro`, `privacy-policy.astro`, `disclaimer.astro`, `contact.astro`, `404.astro`). Missing → FAIL.
2. **Placeholder tokens** — `{{TOKEN}}`, `Lorem ipsum`, `PLACEHOLDER` in raw source → FAIL.
3. **Overclaim language** — 12 FTC-risk phrases in extracted static text → WARN.
4. **Stale how-we-test reference** — `how we test` text in any page (other than `how-we-test.astro`) → WARN. Also flags if both `how-we-test.astro` and `how-we-research.astro` exist simultaneously → WARN.

**Standalone CLI:** `python3 scripts/validate-furniture-pages.py /path/to/site [--verbose]` or `--all`

**Portfolio baseline (2026-05-28):** All 11 live sites PASS. No missing pages, no placeholder tokens found. The Phase B template rename (how-we-test → how-we-research) is fully propagated.

**SM calibration (2026-05-28):** Strengthmill had `src/pages/how-we-test.astro` coexisting with `how-we-research.astro` (stale duplicate). V2 correctly flagged this as a WARN. Deleted `how-we-test.astro` during Phase B cleanup; post-delete preflight returns PASS. Confirmed: V2 WARN is actionable for SM.

**Homepage scope (confirmed 2026-05-28):** V2 scans all 7 `REQUIRED_PAGES`, which includes `index.astro`. The homepage hero claim ("Every review on this site is based on real use") fires the `every-review-real-use` overclaim pattern correctly. Portfolio-wide fix applied: replaced "Every review...is based on real use" with "Every recommendation...is researched against verified buyer reports, manufacturer specs, and expert sources" on TCD, FSG, MLT, BCB (2026-05-28). Strengthmill was already clean with equivalent framing.

**V2 negation suppressor (added 2026-05-28):** `_negation_before()` looks for negation tokens (`not`, `no`, `never`, `n't`, `rather than`, `instead of`, `without`, `intentionally`) within a 40-char window BEFORE an overclaim match. If found, the match is suppressed — it's a disclaimer context, not an overclaim. Covers the false positive on TCD/MLT `how-we-research.astro` where "I tested" and "I've owned" appear inside explicitly negated/conditional methodology disclosures (e.g., "intentionally not 'I tested everything'"). Pattern: same architecture as V12 `negation_nearby()`.

---

### V3 — Amazon Tag Validator (SHIPPED 2026-05-28)

**File:** `scripts/validate-amazon-tag.py`

**Preflight integration:** Check 16 (`amazon-tag`). Called via `importlib` pattern.

**What it checks:**
1. **Format** — `^[a-zA-Z0-9][a-zA-Z0-9-]*-[0-9]{2}$`. Tags >60 chars emit WARN (not FAIL — Amazon doesn't enforce a ceiling, but flags suspicious length).
2. **Placeholder detection** — 7 known sentinel values (`yourtag-20`, `example-20`, `placeholder-20`, etc.) → FAIL.
3. **Portfolio uniqueness** — in `--all` mode, flags any tag shared by two or more sites → FAIL (commission routing collision).

**Standalone CLI:** `python3 scripts/validate-amazon-tag.py /path/to/site [--verbose]` or `--all`

**Portfolio sweep (2026-05-28):** All 11 sites PASS. All tags unique, all formats valid. `northwoodsoverland-20` confirmed valid (no phantom 20-char length limit — the long tag is fine).

| Site | Tag | Status |
|---|---|---|
| FSG | fourseasong-20 | PASS |
| MLT | mylittletbsp-20 | PASS |
| OHT | onehappytable-20 | PASS |
| TCD | thecoffeedis-20 | PASS |
| BCB | bearcreekbbq-20 | PASS |
| NWO | northwoodsoverland-20 | PASS |
| Ten27 | ten27cycles-20 | PASS |
| BHH | betterhearinghub-20 | PASS |
| CC | curatedcameras-20 | PASS |
| SSS | saunassosimple-20 | PASS |
| FFC | fourfernscare-20 | PASS |

---

### V5 — Cross-Site Brand/Persona Collision Validator (SHIPPED 2026-05-28)

**File:** `scripts/validate-brand-collision.py`

**Preflight integration:** Check 17 (`brand-collision`). Called via `importlib` pattern.

**What it checks:**
- **C1 — Persona name hit** (FAIL): A foreign persona's `name_used` or first name appears in another site's article body. The original contamination class: "from a gardener who actually uses them" (Wendy) in OHT/TCD hub.astro files.
- **C2 — Brand name hit** (WARN): A foreign site's `brand_name` appears in an article body at a different site.
- **C3 — Niche term hit** (WARN): A foreign site's distinctive niche keyword appears in an article where the site's own niche is clearly incompatible. Uses `niche_compatible()` guard to suppress same-category hits.

**Registry:** Built from `portfolio.yaml` at runtime — scans each site's `site.config.yaml` and persona YAML automatically. Accepts a pre-built registry via `registry=` param for efficiency in `--all` sweeps.

**Standalone CLI:** `python3 scripts/validate-brand-collision.py /path/to/site [--verbose]` or `--all`

**Portfolio sweep (2026-05-28):**
- C1 (persona name): **0 hits across all 11 sites** — Phase B template cleanup fully effective.
- C2 (brand name): **0 hits across all 11 sites** — no foreign brand contamination.
- C3 (niche terms): **5,113 WARN hits** across all 11 sites — all non-blocking. High count is expected: generic terms like "outdoor", "electric", "home", "comfort" match multiple sites' niche keywords but are not real contamination. C3 is always WARN; only C1 can FAIL.

**False positive note on C3:** Sites with broad niches (FFC: senior caregiving, BHH: hearing health) generate more C3 WARNs because their topics overlap with general home/outdoor/health vocabulary. This is expected behavior. C3 WARNs are review signals, not blocks.

**SM calibration (2026-05-28):** Strengthmill initially generated a false C1 FAIL from V5 because SM was absent from portfolio.yaml and both SM ("Dan Kowalski") and Ten27 ("Dan Reeves") use the first name "Dan". Root cause: V5's registry-based own-site lookup returned None for sites absent from portfolio.yaml, so Ten27's "Dan" pattern wasn't suppressed when scanning SM. Fix applied: `scan_site()` now reads own persona names directly from the site's config YAML and passes them to `compile_foreign_patterns()` as `own_persona_names`, bypassing the registry dependency for own-site suppression. This workaround is retained as a defensive layer for future sites not yet in portfolio.yaml.

**SM added to portfolio.yaml (2026-05-28):** SM is now in the registry as site 13. V5 re-run post-add confirms: 0 C1/C2 FAILs, 83 C3 WARNs (unchanged). Registry correctly shows 11 foreign sites when scanning SM (SM excluded from own foreign list). Ten27's "Dan" cross-suppression works correctly via Ten27's `own_persona_names = {"dan", "dan reeves"}`.

---

### V12 — YMYL Unqualified Clinical Claim Validator (SHIPPED 2026-05-28)

**File:** `scripts/validate-ymyl-endorsement.py`

**Preflight integration:** Check 18 (`ymyl-endorsement`). Called via `importlib` pattern. Non-YMYL sites return `{"skipped": True}` immediately (PASS displayed, check note shown).

**What it checks (YMYL sites only — `ymyl.vertical: true` in site.config.yaml):**
- **Category A — Unqualified clinical claim** (FAIL): 13 phrase patterns asserting medical efficacy or clinical outcomes (e.g., "clinically proven", "treats hearing loss", "audiologist-recommended"). If a hedge phrase ("consult an audiologist", "consult your doctor", "professional recommendation") appears within 200 characters of the match, severity is downgraded from FAIL to WARN (`hedged: True`).
- **Category B — Prescription-adjacent product term without framing** (WARN): Terms like "prescription hearing aid", "audiologist fitting", "bone conduction" in a general consumer guide. Severity checked at article level (any hedge phrase anywhere in article → `has_hedge: True`).

**YMYL sites in portfolio:** BHH (`betterhearinghub`) and FFC (`fourfernscare`). Both have `ymyl.vertical: true` in site.config.yaml.

**Negation suppressor (added 2026-05-28):** `negation_nearby()` looks for negation tokens (`not`, `n't`, `cannot`, `never`, `without`, `no`) within a 40-char window BEFORE a Cat-A match. If found, the match is silently suppressed — it's a disclaimer context, not an endorsement. Covers 3–6 English tokens. Double-negation false-negative accepted as a low-cost trade-off.

**Portfolio findings (2026-05-28, post-negation-tuning — editorial backlog input):**

BHH — **14 → 10 Cat-A FAILs** after negation tuning. Suppressed 4 articles with "not intended to treat hearing loss" / "cannot legally be marketed to treat hearing loss" patterns. Remaining 10:
- 5× `suitable for severe` in **FAQ question form** ("Are these OTC hearing aids suitable for severe hearing loss? No.") — the "No." answer follows the match, not precedes it, so negation window misses these. Resolution: add "consult an audiologist if you have severe hearing loss" to the FAQ answer.
- 3× `prescription-grade performance/amplification` — comparative product tier descriptions. Resolution: reframe as "approaches prescription-device performance in quiet environments" or similar hedged language.
- 2× factual product category definitions ("designed to treat hearing loss across a range of listening environments") — generic hearing aid definitions. Resolution: reframe as "intended to address hearing difficulty" or add attribution ("per the FDA's device classification").

FFC — **2 Cat-A FAILs (unchanged)** — both are product names containing "Doctor Recommended" as a brand trademark ("Everlasting Comfort Doctor Recommended Memory Foam Seat Cushion", TV Ears "doctor recommended" designation). Negation correctly does not suppress these — the trademark name itself contains the clinical phrase. Resolution: reframe as brand-reported designation ("labeled by the manufacturer as 'Doctor Recommended'") or omit the phrase from article body text.

**These are editorial backlog items, not launch blockers for existing deployed sites.** V12 runs at preflight (pre-deploy), not post-deploy. Sites already live are not affected retroactively.

**V12 hedge detection calibration (2026-05-28):**
- `hedge_nearby()` originally checked only `\baudiologist\b` (singular). Updated to `\baudiologists?\b` to match plural form — "most audiologists advise" is an equivalent hedge.
- `hedge_nearby()` now includes a FAQ-block expansion: if the match falls on a Markdown heading line (line starts with `#`), the hedge search expands to the entire answer block (text from match.end() to the next heading), not just ±200 chars. FAQ Cat-A matches typically fire on the question heading ("Are these hearing aids suitable for severe hearing loss?") where the answer body starts ~50 chars after the question text ends — the answer's hedge at sentence 2–3 falls outside the 200-char window without this expansion. The original article edits (BHH Phase B, 2026-05-28) already placed "consult an audiologist" in the first sentence of each affected FAQ answer as a belt-and-suspenders fix; the FAQ-block expansion is the validator-level complement.

---

## 11. Retired / Decided-unnecessary

These validators were proposed in earlier planning iterations and are formally closed here. A decided "no" with documented reasoning is as clean as a shipped validator — it prevents the queue from accumulating open ambiguity.

| Validator | Original purpose | Decision | Reason |
|---|---|---|---|
| **V4** | Post-deploy redirect smoke test | **Retired** | Covered by V13 verify-deploy.mjs (freshness + HTTP checks post-deploy). V7 nav-target curl now adds systematic check of all navigation targets. No coverage gap remains. |
| **V6** | Brand-mismatch inverse (body brand matches title) | **Retired** | V8 (brand-niche: fabricated brand in title absent from body) covers fabrication. V16 (spec-consistency) covers article-vs-products.yaml mismatch from both directions. V6 would add a third overlapping detector with no distinct coverage gap. |
| **V10** | Sitemap lastmod uniformity | **Retired** | Fixed at the generator level in Phase 1 (per-article lastmod now emitted from pipeline.json dates). No incident history post-fix. A validator for an already-resolved generator behavior adds maintenance cost with no incident value. |
| **V11** | Vertical-swap sanitization gate | **Retired** | D17 resolved 2026-05-25: the v1.4 generator is confirmed CLEAN for vertical swap. FFC/SSS/OHT contamination post-mortem traced to deploy-time cwd error (wrong site in cwd during deploy), not scaffold/generator logic. The pre-site-13 clean-scaffold dry run (2026-05-28) verified fresh scaffolds inherit zero contamination. V11 would guard against a problem that doesn't exist at the generator level. |

---

## 12. Portfolio-wide preflight discipline

**Rule:** Whenever a new validator ships (any preflight check, even WARNs-only), run `preflight.py` against all live sites and capture the results. Do not rely on per-site close-out state — previously-declared-closed sites may have new FAILs from a validator that didn't exist at their close-out date.

**Why:** V1 (slug-dedup) shipped 2026-05-26, one day after SSS Phase 1 declared CLOSED (2026-05-25). SSS was never swept and carried a HIGH-confidence dedup pair undetected until the Chunk 11 portfolio-wide audit (2026-05-29). Same pattern held for Ten27, which was never in any chunk and had 2 FAIL types when first swept.

**How to apply:** After any `--check` is added to `preflight.py`, run: `for site in four-season-gardener my-little-tablespoon one-happy-table the-coffee-dispatch bear-creek-barbecue strengthmill northwoods-overland ten27 curatedcameras betterhearinghub saunassosimple fourfernscare; do echo -n "$site: "; python3 scripts/preflight.py --site "$site" 2>&1 | grep "Results:"; done`

---

## 13. v1.6 validators — Queued (NOT BUILT)

Six new validators added in PIPELINE.md v1.6. None are built as of 2026-06-01. All required before Site 16 autonomous launch.

| # | Validator | File | Pipeline point | Class | Origin |
|---|---|---|---|---|---|
| V17 | Content-existence | `scripts/validate-content-existence.mjs` | 15.6 | Hard | Site 15: 91 empty articles from stale Astro data-store |
| V18 | Persona-spec compliance | `scripts/validate-persona-spec-compliance.mjs` | 13.5b | Hard | Site 13: wrong gear, wrong partner name, wrong geography in 300 articles |
| V19 | Product slug resolution | `scripts/validate-product-slug-resolution.mjs` | 13.9 | Hard | Site 15: broken affiliate link from slug typo that build didn't catch |
| V20 | Meta-leakage | `scripts/validate-meta-leakage.mjs` | 13.7 | Hard | Site 14: brief-reasoning in marantz-vs-anthem-vs-denon article body |
| V21 | Card-voice density | `scripts/validate-card-voice.mjs` | 13.8 | Soft | Site 15: third-person product cards despite first-person persona lock |
| V22 | Catalog category coherence | `scripts/validate-catalog-category-coherence.mjs` | 12.5b | Hard | Site 15: spin lure as Best Overall in fly-fishing article |

### V17 — Content-Existence Validator ✅ BUILT 2026-05-31

**Status:** BUILT — `scripts/validate-content-existence.mjs`
**File:** `scripts/validate-content-existence.mjs`
**Integration:** Point 15.6 — runs against `dist/` after build, before deploy.
**Classification:** Hard fail, exit 1

**What it checks:**
- Placeholder patterns in article body text: `[write ...]`, `{{TEMPLATE_TOKEN}}`, `[TODO ...]`, `NOT_ON_AMAZON`, `lorem ipsum`, `[insert ...]`, `[add ... here]`
- Placeholder patterns in link hrefs: `/dp/VERIFY`, `/dp/NOT_ON_AMAZON`
- Empty `article-page__content` div (0 words)
- Rendered body word count < 200 words

**Implementation notes:**
- Uses cheerio to parse HTML; selects `.article-page__content` for content boundary
- Pages without `.article-page__content` are skipped (hub, about, disclosure pages)
- `--site <path>` arg or defaults to `process.cwd()`

**Test results (2026-05-31):**
- Positive: `[write one product-specific paragraph...]` → caught; `{{BRAND_NAME}}` → caught; short articles (<200 words) → caught
- RMF (281 articles): ✓ 0 failures (clean baseline)
- HPC (297 articles): 10 empty-content failures — genuine Astro cache artifacts pre-Phase-1.1 rebuild (source markdown populated, `<div class="article-page__content"></div>` in rendered HTML). V17 correctly catches these.
- UDS (301 articles): 1 empty-content failure — `headphone-carrying-strap` (2702-word source, empty dist/ div). Same cache artifact.

**Origin:** Three cohort sites (13, 14, 15) shipped structurally valid but semantically empty articles. Existing validators check markdown structure at generation time; none scan rendered dist/ HTML.

---

### V18 — Persona-Spec Compliance Validator ✅ BUILT 2026-05-31

**Status:** BUILT — `scripts/validate-persona-spec-compliance.mjs`
**File:** `scripts/validate-persona-spec-compliance.mjs`
**Integration:** Point 13.5b — runs against staged articles before publish.
**Classification:** Hard fail, exit 1

**What it checks (via LLM-pass per article, Haiku):**
- Owned gear claims match persona YAML background (owned_gear, gear:, background: prose)
- Partner name extracted from background prose (regex on partner/wife/husband/spouse patterns)
- Geographic claims consistent with location/location_detail
- Tenure/experience duration consistent with hobby_start_year
- Defers-to attributions match defers_to: list
- No patterns from forbidden_patterns: / refuses_to_claim: lists
- Gracefully handles missing v1.6 structured fields — warns and skips that dimension rather than failing

**Implementation notes:**
- Persona slug resolved from `persona: {config_path: ...}` pattern in site.config.yaml (or plain string)
- `buildPersonaSummary()` extracts available fields; missing v1.6 fields emitted as `[WARN] v1.6 persona fields not present (skip): ...`
- Articles truncated to 1800 words for cost control
- Concurrency pool default 2, configurable with `--concurrency N`
- `--dry-run` mode for testing without API calls
- Balanced-brace JSON extraction (not greedy regex) to handle model commentary after JSON object
- max_tokens: 1024 (raised from 400 to handle violation-rich responses)

**Cost calibration (2026-05-31):**
- Actual: $0.0011/article (spec projected $0.003 — 3× under budget)
- ~$0.33 per 300-article site; ~$0.97 per 879-article portfolio run

**False positive rate:**
- ~0.6–0.8% across 879 articles (5–7 articles incorrectly flagged out of 879)
- Identified by scanning for LLM flags where model's own reasoning said "not a contradiction"
- **Within the <2% budget; V18 can ship as a HARD gate**

**Test results (2026-05-31):**
- Positive test: 6/6 injected Marcus violations caught (wrong partner, wrong gear, wrong chain, wrong tenure, wrong IEM)
- UDS (301 articles): 137 flagged (45.5%) — TRUE POSITIVES, not false positives. Generated with persona locked AFTER generation. Dominant: Topping E50/L50 fabricated as desktop chain (should be Schiit Modi+/Magni+), Aria 2 as daily-driver IEM (should be Blessing 3), 2020 Sundara revision (should be 2022).
- RMF (281 articles): 162 flagged (57.7%) — TRUE POSITIVES. Dominant: explicit forbidden phrases ("I'm an expert in saltwater fly fishing", "I've landed hundreds of bonefish or tarpon", "I'm an expert in Spey casting"), wrong reel model (Iconic 5 vs Iconic 5+), undocumented fishing locations.
- HPC (297 articles): 84 flagged (28.3%) — TRUE POSITIVES. Dominant: editorial methodology violations, wrong model numbers (CDT-5650 vs CDT-3650), wrong projector technology ("laser" vs lamp-based LCD).
- Parse errors: 53/879 = 6% before fix; expect <1% after balanced-brace extractor fix (verified on 2 previously-failing articles).

**Origin:** Site 13 required a full editorial fix session to remove Marcus Tran's wrong gear (E50/L50), wrong partner (Sam vs Hannah), wrong Sundara revision, and hallucinated engineer from 300 articles. Persona-claim audit (V exists, Point 13.5) catches regex testing patterns; this validator catches semantic spec violations.

---

### V19 — Product Slug Resolution Validator ✅ BUILT 2026-05-31

**Status:** BUILT — `scripts/validate-product-slug-resolution.mjs`
**File:** `scripts/validate-product-slug-resolution.mjs`
**Integration:** Point 13.9 — runs against staged article markdown before publish.
**Classification:** Hard fail, exit 1

**What it checks:**
- Every `product:<slug>` in article body resolves to a products.yaml key (hard fail)
- Every `id:` in frontmatter products list resolves to a products.yaml key (hard fail)
- ASIN is not `VERIFY` placeholder (hard fail)
- ASIN format is valid 10-char alphanumeric or `NOT_ON_AMAZON` (hard fail)
- `NOT_ON_AMAZON` without `buy_url` (warning — renders but has no CTA button)

**Implementation notes:**
- Handles both `asin` (RMF) and `amazon_asin` (UDS, HPC) field names
- Uses gray-matter to parse frontmatter; regex for body `product:<slug>` references
- `--site <path>` arg or defaults to `process.cwd()`

**Test results (2026-05-31):**
- Positive: broken slug → caught; `VERIFY` ASIN → caught (hard fail); `NOT_ON_AMAZON` + no `buy_url` → caught (warning)
- RMF: 39 articles with malformed ASINs (9-digit truncated ISBNs, `NOT_FOUND` values) — real data quality issues exposed, not false positives. Also 51 warnings for DTC products with no buy_url.
- HPC: 10 broken slug references (products referenced in articles that don't exist in products.yaml)
- UDS: 61 articles with broken references
- These are genuine catalog data issues across the portfolio, not V19 false positives.

**Origin:** Site 15's `how-to-indicator-nymph.md` referenced `product:aventik-eupheng-riverruns-yarn` but products.yaml key was `aventik-eupheng-riverruns-yarn-strike`. Astro build succeeded (graceful degradation on missing product); rendered HTML had a broken affiliate link that was only discovered post-deploy.

---

### V20 — Meta-Leakage Validator ✅ BUILT 2026-05-31

**Status:** BUILT — `scripts/validate-meta-leakage.mjs`
**File:** `scripts/validate-meta-leakage.mjs`
**Integration:** Point 13.7 — runs against staged articles before publish.
**Classification:** Hard fail, exit 1

**What it checks (13 regex patterns, case-insensitive):**
- `\bprompt system\b`, `\bh2_structure\b`, `\bbrief specifies\b`, `\bpersona's defer-to\b`
- `\bbrief also specifies\b`, `\barticle type defined in\b`, `\bformat governs\b`
- `\bper the brief\b`, `\bthe prompt requires\b`, `\bthe article brief\b`, `\bsystem prompt\b`
- `\bthe brief (specifies|requires|states|calls for|...)\b` (verb-qualified — avoids "the brief answer" false positives)
- `\bthe brief for this article\b`

**Calibration note:** Generic `\bthe brief\b` produced false positives on "the brief answer is", "brief experience supports". Replaced with verb-qualified form. All 3 negative-test sites pass clean.

**Test results (2026-05-31):**
- Positive: all 7 spec patterns caught in synthetic article. Multiple patterns fire per article. ✓
- HPC (297 articles): ✓ 0 failures
- UDS (301 articles): ✓ 0 failures
- RMF (281 articles): ✓ 0 failures

**Origin:** Site 14's marantz-vs-anthem-vs-denon article shipped with 3 paragraphs of the producer's internal reasoning about the brief verbatim in the article body. No validator caught this.

---

### V21 — Card-Voice Density Validator ✅ BUILT 2026-05-31

**Status:** BUILT — `scripts/validate-card-voice.mjs`
**File:** `scripts/validate-card-voice.mjs`
**Integration:** Point 13.8 — runs against staged articles before publish.
**Classification:** Soft fail, logged to `data/v21-calibration-log.yaml`. Always exits 0.

**What it checks:** Proportion of buyer-guide product cards containing first-person pronouns from persona YAML. Below-threshold articles are WARNed and logged for editorial review. Does not block deploy.

**Card detection algorithm:**
Walks markdown body line-by-line. On every `### ` heading boundary, commits the previous section. A section is classified as a **product card** iff its body contains the pattern `\(product:[^)]+\)` (the inline product CTA format). H2 headings reset context; H3 sections without a product CTA (buying-guide subsections, FAQ headers) are not counted as cards.

**Threshold:** `fp_cards / total_cards >= 1/3` — at least 1 card in every 3 must contain a first-person pronoun hit.

**Pronoun source:** Reads `first_person_pronouns:` array from locked persona YAML (v1.6 field). Falls back to English defaults if field absent: `I, my, me, myself, mine, I've, I'm, I'd, I'll`. Normalises curly apostrophes before matching. `I` matched case-sensitively (always capitalized as subject pronoun); all others case-insensitively. Boundary: `(?<![a-zA-Z0-9])` / `(?![a-zA-Z0-9])` rather than `\b` so apostrophe-based contractions don't create false boundaries.

**Test results (2026-05-31):**

Positive tests (should WARN):
- Article with third-person persona references ("the engineer's assessment", "Greg's recommendation"): 0/3 fp-cards, density 0.000 → WARN ✓
- Article with agentless/passive voice ("the unit features...", "users report..."): 0/3 fp-cards, density 0.000 → WARN ✓

Negative test (should PASS):
- Article with correct first-person card voice ("I've been in them two seasons...", "I recommend..."): 3/3 fp-cards, density 1.000 → PASS ✓

**Corpus baselines (calibration):**

| Site | Persona | Buyer-guides checked | WARNs | WARN rate | Avg fp density |
|------|---------|---------------------|-------|-----------|----------------|
| RMF (Site 15) | greg | 101 | 99 | 98.0% | 0.064 |
| HPC (Site 14) | adrian | 103 | 101 | 98.1% | 0.047 |
| UDS (Site 13) | marcus | 110 | 102 | 92.7% | 0.089 |

**Calibration conclusion — threshold question:** The spec asks "if cohort density is below threshold, is the threshold wrong, or does the cohort need remediation?" Answer: **the threshold is correct; the cohort needs remediation.** Observed density (0.047–0.089 average) is 14–27% of the 0.333 threshold — not a borderline miss but a systematic near-zero. The generator never placed persona first-person voice in product card sections; the card prose is third-person generic throughout. This is a prompt and editorial quality issue, not a threshold calibration issue. Threshold stays at 1/3. Remediation is separate work (see B22 in PLATFORM_BACKLOG.md).

**Ship status:** CAN SHIP as SOFT gate. False positive risk not applicable (pattern matching, not LLM). Always exits 0.

**Origin:** Site 15's Greg persona produced first-person narrative prose but depersonalized product cards in buyer-guide articles. The voice inherited to narrative code path but not card generation code path.

---

### V22 — Catalog Category Coherence Validator ✅ BUILT 2026-05-31

**Status:** BUILT — `scripts/validate-catalog-category-coherence.mjs`
**File:** `scripts/validate-catalog-category-coherence.mjs`
**Integration:** Point 12.5b — runs after brand-match audit, before Point 13.
**Classification:** Hard fail, exit 1

**What it checks:** Product's `category_type:` field in products.yaml must be compatible with the hub it's used in, per `config/category-types/<niche>.yaml`. Products without `category_type` are warned but not hard-failed (forward-looking validator).

**Niche config:** `config/category-types/fly-fishing.yaml` is the reference implementation for RMF. Discoverable by `niche:` field in `site.config.yaml` (looks at `sc.niche` and `sc.site.niche`). Sites without a config file skip with a `[SKIP]` message and exit 0. The config format (globally_forbidden + per-hub forbidden + optional per-hub allowed whitelist) is documented in the file header for future niches.

**Test results (2026-05-31):**
- Positive: `spin_lure` product in `flies-patterns` hub → caught globally_forbidden violation ✓
- RMF (281 articles, 0 tagged products): 0 failures + 816 untagged-product warnings (expected) ✓
- HPC, UDS (no niche config): graceful skip + message pointing to expected config path ✓

**Origin:** Site 15's `/best-saltwater-flies/` had a spin lure (category_type: spin_lure) as Best Overall and a bait-catching rig (category_type: bait_rig) as Also Consider. Both passed V14 (hub match) and V15 (brand coherence) but were semantically incompatible with the fly-fishing article category.

---

*End of VALIDATORS.md*
