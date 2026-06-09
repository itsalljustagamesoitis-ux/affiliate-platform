# Portfolio Closeout Campaign

---

## Part 8 — Campaign Closure (2026-05-29)

### Closure state

As of 2026-05-29, the portfolio remediation campaign is **complete**.

| Metric | State |
|---|---|
| Sites at 0 preflight FAILs | **12 / 12** |
| Preflight checks | 18 (Checks 1–9 from SSS UAT post-mortem; 10–18 from V8/V9/V12–V16) |
| Post-deploy checks | 9 (verify-deploy.mjs) |
| Platform templates | Clean — clean-scaffold dry run verified (2026-05-28) |
| PIPELINE.md | v1.5 (section 14 added 2026-05-28) |
| VALIDATORS.md | Sections 10–12 current (V12 editorial notes, retired validators, portfolio-wide preflight discipline) |

---

### Per-chunk final state

| Chunk | Scope | Status | Notes |
|---|---|---|---|
| 1 | Validators | **CLOSED** | V2, V3, V5, V7, V12 built; V4, V6, V10, V11 formally retired |
| 2 | Strengthmill | **CLOSED** | 12–17 hr est → ~3–4 hr actual; 273 articles live, 0 FAILs |
| 3 | BHB | **CLOSED** | 8–13 hr est → ~3 hr actual; 270 articles, V12/V15 tuned |
| 4 | TCD + portfolio FTC sweep | **CLOSED** | Cross-portfolio FTC overclaim fix on FSG/MLT/TCD/BCB; V2 negation suppressor added |
| 5 | MLT | **CLOSED** | 4–5 hr est → ~2 hr actual; V15 `knive→knife` + Option B2; V16 heading-anchor fix |
| 6 | BCB | **CLOSED** | Campaign-plan items confirmed stale; V1 dedup pair only; 266 articles |
| 7 | NWO | **PARKED** | K3 (your decision when convenient); NWO already 0 preflight FAILs |
| 8 | CC | **CLOSED** | Gap-discovered-then-closed; 8 dedup pairs + dollar-figure title fix; D18 sync resolved |
| 9 | V15 flat-nav (FSG + OHT) | **CLOSED** | 9 token equivalences + description extractor + 18 FSG product name bridges; MLT handled in Chunk 5 |
| 10 | FFC DTC integration | **BLOCKED** | K2 (affiliate approvals: Pride, Bruno, Stannah, Drive Medical, Carex, Medline); ~4–8 hr when unblocked |
| 11 | SSS + Ten27 | **CLOSED** | Added during closure verification; SSS had 1 V1 pair (timing gap); Ten27 had 1 V1 pair + 6 V9 articles |

---

### Methodology findings

**Audit-first pattern.** Original estimates totaled 67–95 hr; actual execution ~15–25 hr. Piecemeal work across the campaign consistently closed more than trackers captured. Auditing before executing avoids effort spent on already-resolved items and surfaces correct scope before time is committed.

**Specificity vs. staleness.** Well-defined campaign items (specific URLs, ASINs, validator findings) reliably represented real work. Vague items ("pellet H1", "hedging items", "TCD quality items") were universally stale or already-resolved on first inspection. Vague backlog items are a leading indicator of staleness, not a leading indicator of work.

**Validator-shipping discipline.** When a new validator ships, run portfolio-wide immediately and surface findings against every site, including previously-closed ones. The gap: V1 shipped 2026-05-26, one day after SSS declared closed (2026-05-25). SSS carried a HIGH-confidence dedup pair undetected until Chunk 11. Same pattern held for Ten27, which had never been in any chunk scope. Rule documented in VALIDATORS.md Section 12.

**Negation and hedge-context detection as a cross-validator pattern.** V12 negation suppression, V2 negation suppressor, V12 `hedge_nearby()` tuning, and the FAQ-block expansion all solved variants of the same problem: surface the clinical claim, but don't fire when the article itself supplies the correct context. Pattern is worth applying to any future YMYL-adjacent validator.

---

### Three items correctly outside campaign closure

| Item | Blocker | ETA |
|---|---|---|
| K2 — FFC DTC affiliate applications (Pride, Bruno, Stannah, Drive Medical, Carex, Medline) | External approval clock, multi-week | When approvals land |
| K3 — NWO ARB/Sherpa/iKamper affiliate account factual question | Keith parked | When convenient |
| Chunk 10 — FFC DTC integration (~4–8 hr) | Unblocks when K2 approvals land | Dependent on K2 |

---

### Campaign state: **CLOSED**

All 12 sites live. 12 of 12 at 0 preflight FAILs. Validator infrastructure complete. Documentation current. Site 13 clear to build whenever Keith resumes.
