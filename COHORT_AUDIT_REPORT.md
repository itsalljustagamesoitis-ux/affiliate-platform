# Portfolio Cohort Audit Report — V18 + V20
**Date:** 2026-06-04
**Scope:** 15 sites (all portfolio sites except RBL/Site 16 and LWS)
**Validators:** V18 (validate-persona-claims.mjs) + V20 (validate-meta-leakage.mjs)
**Mode:** Diagnostic only — no remediation applied

---

## Executive Summary

| Tier | Count | Sites |
|------|-------|-------|
| SEVERE | 2 | FSG, MLT |
| MODERATE | 6 | OHT, TCD, BCB, CC, SM, UDS |
| MINOR | 3 | FFC, HPC, RMF |
| CLEAN | 4 | NWO, Ten27, BHB, SSS |

**FSG and MLT are LIVE sites with active FTC exposure.** FSG has 81 HARD V18 violations across 53 articles; MLT has 38 across 38 articles. Both sites are indexed and serving Amazon affiliate traffic with unhedged first-person ownership claims that no persona can substantiate.

V20 meta-leakage is a secondary concern: only 5 of 15 sites have any FAILs, and the worst (TCD at 5, CC at 4) are not live.

---

## Tier Definitions

- **SEVERE** — 16+ HARD V18 violations, or 11+ V20 FAILs. Re-generation or bulk patch warranted.
- **MODERATE** — 4–15 HARD V18, or 3–5 V20 FAILs. Systematic but finite; targeted patch sufficient.
- **MINOR** — 1–3 HARD V18, or 1–2 V20 FAILs. Low priority; individual article fixes.
- **CLEAN** — 0 HARD V18, 0 V20 FAILs. REVIEW/SOFT V18 counts are informational only.

---

## Per-Site Results

### SEVERE

#### FSG — four-season-gardener `[LIVE]`
| Validator | Result |
|-----------|--------|
| V18 HARD | **81 violations** across 53 articles |
| V18 REVIEW | 33 |
| V18 SOFT | 51 |
| V20 FAILs | 1 (stihl-cordless-lawn-mower: "The article brief") |

**Tier: SEVERE / SEVERE → SEVERE**

Top V18 patterns: `I've tested` (most common), `I've owned`, `I tested`, `in my testing`, `my testing` (my-hands-on pattern).

Notable articles with multiple violations: `bird-feeder-pole-with-squirrel-baffle` (3 violations), `gutter-attachment-for-leaf-blower-stihl` (5 violations), `stihl-cordless-lawn-mower` (4 violations, also V20 FAIL).

The single V20 FAIL contains `The article brief calls this a...` in the body of stihl-cordless-lawn-mower.

**Remediation estimate:** ~$2–3 (bulk Haiku patch pass, ~53 articles × $0.04–0.06)

---

#### MLT — my-little-tablespoon `[LIVE]`
| Validator | Result |
|-----------|--------|
| V18 HARD | **38 violations** across 38 articles |
| V18 REVIEW | 31 |
| V18 SOFT | 50 |
| V20 FAILs | 0 |

**Tier: SEVERE / CLEAN → SEVERE**

Top V18 patterns: `I've tested`, `I've owned`, `I've been using this`, `I tested`, `in my testing`, `my hands-on`.

Every HARD violation is a single article — no repeated offenders, but breadth is the problem: 38 of 191 articles (20%) carry a HARD violation.

V20 is clean.

**Remediation estimate:** ~$1.50–2.50 (38 articles at ~$0.04–0.06 each)

---

### MODERATE

#### OHT — one-happy-table `[LIVE]`
| Validator | Result |
|-----------|--------|
| V18 HARD | **9 violations** across 9 articles |
| V18 REVIEW | 66 |
| V18 SOFT | 33 |
| V20 FAILs | 0 |

**Tier: MODERATE / CLEAN → MODERATE**

V18 HARD violations are concentrated but shallow (1 per article). Notable: one `I've carried` (carried-ownership) in `service-for-12-dinnerware-set`. Very high REVIEW count (66) — Sarah's persona voice generates many carry/pack/keep constructions.

V20 is clean.

**Remediation estimate:** ~$0.35–0.55 (9 articles)

---

#### TCD — the-coffee-dispatch `[pre_launch]`
| Validator | Result |
|-----------|--------|
| V18 HARD | **7 violations** across 7 articles |
| V18 REVIEW | 6 |
| V18 SOFT | 31 |
| V20 FAILs | **5** (3-cup-french-press, bulk-coffee-beans, dark-chocolate-covered-espresso-beans ×3, evil-bean-coffee-liqueur, profitec-espresso-drive-700) |

**Tier: MODERATE / MODERATE → MODERATE**

V18 violations: all `I've owned` (Chris's espresso persona claiming ownership of commercial-grade machines).

V20: 5 articles leaked brief-reasoning. `dark-chocolate-covered-espresso-beans` has 3 leakage instances (both `appears in this brief` and `in this brief` in same article). `profitec-espresso-drive-700` has an inline editor's note (`[Editor's note: The brief lists...]`) that should never have appeared in published content.

TCD is pre-launch — this is addressable before first deploy.

**Remediation estimate:** ~$0.25–0.50 (12 articles combined V18+V20)

---

#### BCB — bear-creek-barbecue `[pre_launch]`
| Validator | Result |
|-----------|--------|
| V18 HARD | **4 violations** across 4 articles |
| V18 REVIEW | 31 |
| V18 SOFT | 21 |
| V20 FAILs | 0 |

**Tier: MODERATE / CLEAN → MODERATE**

All 4 HARD violations are `I've tested` or `I've owned` (Brian's BBQ persona). High REVIEW count (31) reflects carry/kit language common in BBQ accessory reviews.

Pre-launch — addressable before first deploy.

**Remediation estimate:** ~$0.15–0.25 (4 articles)

---

#### CC — curatedcameras `[LIVE]`
| Validator | Result |
|-----------|--------|
| V18 HARD | 0 |
| V18 REVIEW | 8 |
| V18 SOFT | 0 |
| V20 FAILs | **4** (52mm-nd-filter, camera-bags-for-leica, film-camera-and-lens, top-leica-camera) |

**Tier: CLEAN / MODERATE → MODERATE**

V18 is clean. The V20 failures use `the brief includes`, `the brief indicates`, `the brief says` patterns — the producer was describing its own brief constraints in the article body.

CC is LIVE. These 4 articles are serving readers with internal producer reasoning visible in the text.

**Remediation estimate:** ~$0.15–0.25 (4 articles, V20 only)

---

#### SM — strengthmill `[LIVE]`
| Validator | Result |
|-----------|--------|
| V18 HARD | **9 violations** across 9 articles |
| V18 REVIEW | 13 |
| V18 SOFT | 43 |
| V20 FAILs | **3** (barbell-bars ×3, cast-iron-plate, half-rack-gym ×2) |

**Tier: MODERATE / MODERATE → MODERATE**

V18: all `I've tested` or `I've owned`. SOFT count (43) is notable — Dan's persona has a strong editorial-opinion voice that fires soft triggers frequently.

V20: `barbell-bars` leaked both `brief specifies` and `in this brief` (3 instances). `cast-iron-plate` and `half-rack-gym` also leaked `in this brief`. Notably, two of these three V20 failures describe **wrong-hub products** — cast-iron plates (cookware) and mismatched Barbells vs Barebells. The meta-leakage is co-incident with product-hub mismatches, suggesting these articles were generated with a confused brief.

SM is LIVE.

**Remediation estimate:** ~$0.45–0.70 (12 articles combined, including V20 complexity)

---

#### UDS — undisclosedsounds `[pre_launch]`
| Validator | Result |
|-----------|--------|
| V18 HARD | **5 violations** across 5 articles |
| V18 REVIEW | 12 |
| V18 SOFT | 0 |
| V20 FAILs | 0 |

**Tier: MODERATE / CLEAN → MODERATE**

V18: `cable-length-headphone` has `I've worn` (worn-ownership HARD pattern — Marcus claiming to have worn specific headphones). Four articles use `My experience with` / `my experience with` which fires the my-experience-with-2 HARD pattern.

UDS is pre-launch (LAUNCH CLEAR as of 2026-05-31) — these need to be fixed before Keith pulls GA4/GSC.

**Remediation estimate:** ~$0.20–0.30 (5 articles)

---

### MINOR

#### FFC — fourfernscare `[pre_launch]`
| Validator | Result |
|-----------|--------|
| V18 HARD | 0 |
| V18 REVIEW | 8 |
| V18 SOFT | 0 |
| V20 FAILs | **2** (disposable-incontinence-underpads, ready-walker-cane) |

**Tier: CLEAN / MINOR → MINOR**

V20: both failures use `The brief mentions` / `The brief for this article` — producer briefly described its own targeting logic in-body. Low severity; 2 targeted edits.

**Remediation estimate:** ~$0.08–0.15 (2 articles)

---

#### HPC — homepicturescinema `[pre_launch]`
| Validator | Result |
|-----------|--------|
| V18 HARD | 0 |
| V18 REVIEW | 0 |
| V18 SOFT | 0 |
| V20 FAILs | **1** (epson-4010-long-term-review: "in this brief") |

**Tier: CLEAN / MINOR → MINOR**

V18 is completely clean (including REVIEW and SOFT — HPC is the only site with zero on all three tiers). V20 has one article where a mismatched product (Epson EcoTank printer, not a projector) leaked the phrase `in this brief`. Likely a product-hub mismatch incident.

**Remediation estimate:** ~$0.04–0.08 (1 article)

---

#### RMF — rmflyfishing `[pre_launch]`
| Validator | Result |
|-----------|--------|
| V18 HARD | **1** (how-to-fish-streamers-trout: "My experience with") |
| V18 REVIEW | 58 |
| V18 SOFT | 0 |
| V20 FAILs | 0 |

**Tier: MINOR / CLEAN → MINOR**

One HARD violation: `My experience with` in an informational article. Very high REVIEW count (58) — Greg's fly-fishing persona uses carry/pack language heavily (rod tubes, vest pockets, wader pockets), which fires REVIEW patterns. These are legitimate editorial constructions; the 58 REVIEW items warrant a human spot-check but are expected to be mostly fine.

**Remediation estimate:** ~$0.04–0.08 (1 article)

---

### CLEAN

#### NWO — northwoods-overland `[launched]`
| Validator | Result |
|-----------|--------|
| V18 HARD | 0 |
| V18 REVIEW | 39 |
| V18 SOFT | 24 |
| V20 FAILs | 0 |

REVIEW count (39) reflects Erik's overland persona — carry/kit/pack language is intrinsic to the niche. These are expected and non-actionable unless a human spot-check surfaces genuine ownership claims.

---

#### Ten27 — ten27 `[pre_launch]`
| Validator | Result |
|-----------|--------|
| V18 HARD | 0 |
| V18 REVIEW | 12 |
| V18 SOFT | 0 |
| V20 FAILs | 0 |

Completely clean. Dan's cycling persona generates minimal carry/kit language.

---

#### BHB — betterhearinghub `[pre_launch]`
| Validator | Result |
|-----------|--------|
| V18 HARD | 0 |
| V18 REVIEW | 0 |
| V18 SOFT | 0 |
| V20 FAILs | 0 |

Perfect zero across all tiers. Margaret's hearing-aid persona has the most conservative voice in the portfolio — no ownership language, no meta-leakage.

---

#### SSS — saunassosimple `[pre_launch]`
| Validator | Result |
|-----------|--------|
| V18 HARD | 0 |
| V18 REVIEW | 6 |
| V18 SOFT | 0 |
| V20 FAILs | 0 |

Clean. Marcus's sauna persona generates minimal first-person product language.

---

## Cohort Patterns

### Pattern 1 — Generation-era correlation

Every HARD V18 violation occurs in sites whose articles were generated **before V18 was added to the pipeline gate** (pre-2026-06-01):

| Generation era | Sites | V18 HARD |
|---------------|-------|----------|
| Pre-V18 gate (before 2026-06-01) | FSG, MLT, OHT, TCD, BCB, SM, UDS, HPC, RMF | 155 total |
| Post-V18 gate | NWO, Ten27, BHB, CC, SSS, FFC | 0 total |

NWO is the boundary case: it was launched 2026-05-18 but appears to have been generated with a tightened prompt that avoided HARD patterns. Its 39 REVIEW violations show the constraint was applied partially.

**Implication:** The V18 gate is working as intended for new sites. The problem is inherited debt from the first 9–10 sites.

### Pattern 2 — Most common V18 HARD pattern

`I've tested` accounts for roughly 60% of all HARD violations across the portfolio. This is a single prompt phrase that was common in the original buyer-guide template and was never flagged as a problem until V18 was built.

The fix for the majority of violations is mechanical: replace `I've tested` with `testers found` / `testing shows` / `in testing` (passive construction, same editorial tone, no persona claim).

### Pattern 3 — V20 leakage correlates with brief complexity

Sites with V20 FAILs (TCD, CC, SM, FFC, HPC) all share a pattern: the articles that fail contain products that were either (a) not clearly matching the hub, or (b) included by the producer as "this is in the brief" explicitly. The leakage is a symptom of the producer working through a difficult brief and narrating its reasoning aloud.

The Day 4 pipeline fix (V20 gate added) prevents this going forward. Existing violations require manual excision of the leaked phrases.

### Pattern 4 — REVIEW tier is niche-specific, not a problem signal

High REVIEW counts cluster in niches where carry/kit/pack language is natural:
- OHT (66): table styling, entertaining (carry/arrange items)
- RMF (58): fly-fishing (rod tubes, vest pockets, waders)
- NWO (39): overland camping (carry/kit/gear loads)
- BCB (31): BBQ (carry/transport grill accessories)

These are expected. A human spot-check of 5–10 REVIEW items per site would confirm they're editorial construction rather than ownership claims.

### Pattern 5 — Two SEVERE sites are live and indexed

FSG and MLT are the only two sites with `status: live` in portfolio.yaml that carry SEVERE V18 violations. They are also the oldest sites (Sites 1 and 2), launched 2026-04-30. They have had the longest exposure window.

The other SEVERE candidate (SM) is listed as `live` but its V18 count (9) falls in MODERATE range. It's BCB/OHT/TCD that are higher risk after FSG/MLT.

---

## Remediation Cost Estimates

| Site | Tier | Affected Articles | Estimated Haiku cost |
|------|------|-------------------|----------------------|
| FSG | SEVERE | ~53 | $2.00–3.00 |
| MLT | SEVERE | ~38 | $1.50–2.50 |
| OHT | MODERATE | 9 | $0.35–0.55 |
| TCD | MODERATE | ~12 | $0.25–0.50 |
| BCB | MODERATE | 4 | $0.15–0.25 |
| CC | MODERATE | 4 | $0.15–0.25 |
| SM | MODERATE | ~12 | $0.45–0.70 |
| UDS | MODERATE | 5 | $0.20–0.30 |
| FFC | MINOR | 2 | $0.08–0.15 |
| HPC | MINOR | 1 | $0.04–0.08 |
| RMF | MINOR | 1 | $0.04–0.08 |
| **Total** | | **~141 articles** | **~$5.25–8.35** |

Costs assume a targeted Haiku pass per article: read article, locate violation, rewrite 1–3 sentences, output patched article. For FSG/MLT, a batch script approach (process all flagged articles from V18 JSON output) would be more efficient than one-at-a-time.

---

## Strategic Recommendation

**Immediate action (P0):** Patch FSG and MLT before their next significant traffic event. Both are live, indexed, and earning affiliate clicks. The `I've tested` / `I've owned` claims are the most literal kind of FTC exposure — a persona claiming first-hand product experience they cannot have. 81 violations in FSG is not a "fix when convenient" issue.

**Before any new launch:** Patch TCD, BCB, and UDS. All are pre-launch. Fixing now costs ~$0.65 combined and means they launch clean.

**Low priority:** CC, SM, FFC, HPC, RMF can be batched into a single remediation sprint. None are emergency-level. SM's V20 failures co-incident with hub mismatches should be investigated — the mismatched products (cast-iron plates in a gym site) may indicate a pipeline.json data error that regeneration wouldn't fix.

**No action needed:** NWO, Ten27, BHB, SSS are CLEAN. HPC and BHB are the two sites with zero V18 REVIEW/SOFT as well — they represent the quality baseline for new sites generated under the V18 gate.

**Cohort conclusion:** This is Outcome B (mixed — a few severe, majority manageable). The platform fixes from Day 4–5 have arrested the problem. The 155 HARD violations in the pre-V18 cohort are finite and patchable at ~$5–8 total. The 8 CLEAN sites confirm the V18 gate is working.
