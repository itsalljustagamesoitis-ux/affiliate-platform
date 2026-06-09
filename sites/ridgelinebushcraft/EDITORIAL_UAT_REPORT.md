# Site 16 — Ridgeline Bushcraft Editorial UAT Report

**Date:** 2026-06-04  
**Auditor:** Claude Code  
**Scope:** 21 articles sampled across all 12 hubs, 205 articles published  
**Persona spec:** Wesley Tate, finish carpenter, Lexington VA, 22 years Appalachian bushcraft  
**Persona reference:** `/root/ridgelinebushcraft/config/personas/wesley-tate.yaml`

---

## Severity Scale

| Label | Meaning |
|-------|---------|
| SEV-1 | Blocking — visible to readers, breaks trust or reveals platform machinery |
| SEV-2 | Quality — wrong niche, persona violation, or material content defect |
| SEV-3 | Minor — small persona slip, hedging gap, or low-priority cleanup |
| PASS  | No material issues found |

---

## Platform-Wide Issues (All Articles Affected)

### SEV-1 — Image Markdown Broken

Every article renders image syntax as raw Python dict text. Example from `best-diy-fire-starter.md`:

```
![hub product image]({'alt': 'diy fire starter', 'path': 'articles/fire-3.webp'})
```

This literal string appears in every article body. Images are not rendering. Affects all 205 published articles. The producer generated Python dict syntax instead of valid Markdown image syntax. A reader sees broken text, not an image, on every image placement.

**Severity:** SEV-1  
**Scope:** All 205 published articles  
**Fix required:** Regex replace or re-render all articles

---

### SEV-2 — Em-Dash Substitute Throughout

The producer replaced em-dashes with ` , ` (space-comma-space). Visible on nearly every sentence that would normally use an em-dash:

- "A poor fit , wrong weight, wrong geometry, wrong handle length , turns an hour of productive work into an hour of frustration"
- "Canvas is the right material for this category. It abrades reasonably well , the question isn't whether to get canvas , it's what weight and weave"
- "I lean toward unlined or lightly lined shells. In the GW or Jefferson, temperatures can swing twenty degrees in an afternoon , an unlined shell over a Filson Mackinaw"

Appears in every article reviewed, including FAQ schema JSON embedded in each file. Looks like a producer rendering artifact — ` , ` as em-dash fallback throughout.

**Severity:** SEV-2  
**Scope:** All 205 published articles  
**Fix required:** Platform-wide string replacement

---

## Article-by-Article Findings

### KNIVES HUB (3 articles sampled)

---

#### `bark-river-knife.md` — SEV-2
**Type:** review  
**Title:** "Bark River Review: Is This the Best Bushcraft Knife?"

Zero Bark River products in the article. Products found: Spyderco Bushcraft, Old Timer 8OT, BPSKNIVES. The article opens with "Bark River is a name that comes up in every serious bushcraft knife conversation" and then covers entirely different brands. A reader clicking this from search expecting a Bark River review is immediately misled. No geographic grounding (no GW, Jefferson, or Blue Ridge references). Wesley voice largely absent — generic product copy.

**Persona fidelity:** FAIL — no owned gear mentions, no geographic grounding, no defers_to citations  
**Content quality:** FAIL — title-product mismatch is a trust issue  
**Verdict:** SEV-2

---

#### `best-fixed-blade-utility-knife.md` — SEV-2
**Type:** buyer_guide  
**Target keyword:** "best fixed blade utility knife"

Products: IRWIN retractable utility knife, Grabber drywall knife, Stanley box cutter variants. These are contractor utility knives, not fixed-blade field knives. No bushcraft relevance. Wesley is a finish carpenter, so contractor knives are not alien to his world, but they have no place in a bushcraft knives hub. No Wesley voice present. No geographic grounding. No defers_to citations.

**Persona fidelity:** FAIL — no voice, no persona touchpoints  
**Content quality:** FAIL — wrong niche for the hub  
**Verdict:** SEV-2

---

#### `best-skinning-knife-2.md` — PASS
**Type:** buyer_guide  
**Target keyword:** "best skinning knife"

First-person voice present from the opening: "I've relied on dedicated skinning blades long enough…" Products are on-niche (dedicated skinning knives). Reasonable structure, pros/cons functional. No geographic grounding but not required for this article type. Wesley voice consistent through the piece.

**Persona fidelity:** PASS  
**Content quality:** PASS  
**Verdict:** PASS

---

### FIRE HUB (3 articles sampled)

---

#### `best-diy-fire-starter.md` — PASS
**Type:** buyer_guide

Strong. "I've started fires in the GW and Jefferson in November rain." Kochanski referenced. Products are on-niche (fatwood, tinder materials, fire tools). Voice consistent throughout. Geographic grounding appropriate. Proper hedging on non-owned gear.

**Persona fidelity:** PASS  
**Content quality:** PASS  
**Verdict:** PASS

---

#### `best-flint-and-steel-fire-starter.md` — PASS (exemplary)
**Type:** buyer_guide

Best persona execution in the sample. Wesley voice is distinct and sustained throughout. GW and Allegheny references placed naturally. Both Kochanski and Lars Fält cited correctly in context. "I've watched beginners struggle with undersized rods" — the kind of specific, earned observation a real practitioner would make. Products are precisely on-niche (ferro rods, flint sets, traditional fire kits). Full compliance with persona spec.

**Persona fidelity:** PASS — exemplary  
**Content quality:** PASS  
**Verdict:** PASS

---

#### `how-do-you-start-a-fire.md` — SEV-2 + SEV-3
**Type:** buyer_guide (informational framing)

Products include a Bible study devotional and a medical career book. The article acknowledges these are off-topic but includes them anyway. This is not a persona violation in itself, but an Amazon keyword mismatch that placed irrelevant products into a fire-starting article.

Additionally: "I carry a BIC classic lighter and a Light My Fire Scout 2.0 ferro rod as backup." Neither product is listed in the persona's `owned_gear` or `bio_full` known gear. These are presented as first-person gear claims without the hedging convention required for non-owned gear.

**Persona fidelity:** SEV-3 — non-owned gear claimed as owned  
**Content quality:** SEV-2 — Bible/career book products in a fire-starting article  
**Verdict:** SEV-2 (dominant)

---

### WATER HUB (2 articles sampled)

---

#### `are-nalgene-bottles-dishwasher-safe.md` — PASS
**Type:** review  
**Target keyword:** (domestic care keyword — low SEO value for bushcraft)

The domestic keyword is a soft concern, but the article itself handles it well. Kochanski HDPE reference placed naturally. "I've carried a wide mouth in my pack on multi-day stretches through the Alleghenies." Geographic grounding is appropriate. Wesley voice present. Products are the right products (Nalgene wide mouth, 32 oz variants).

**Persona fidelity:** PASS  
**Content quality:** PASS  
**Verdict:** PASS

---

#### `katadyn-pocket-water-filter.md` — SEV-1 + SEV-3
**Type:** review

**SEV-1:** The phrase "The brief covers three Katadyn options" appears in the published article body. This is producer internal reasoning that leaked into the output — the word "brief" is platform machinery. A reader sees this as editorial commentary, which breaks the first-person voice and reveals the production process.

**SEV-3:** "I've carried one into the GW more times than I've kept count" claims first-person ownership of a Katadyn Pocket filter. The persona's `bio_full` owned gear does not include this product. The hedging convention ("I haven't used this personally") was not applied.

**Persona fidelity:** SEV-3  
**Content quality:** SEV-1  
**Verdict:** SEV-1 (dominant)

---

### PACKS HUB (2 articles sampled)

---

#### `best-black-canvas-backpack.md` — SEV-2
**Type:** buyer_guide

Products: Supacool 17" laptop bag, drawstring bulk promotional packs, Muzee bag with USB charging port. These are urban/commuter or promotional products. No bushcraft relevance. Wesley voice absent. No geographic grounding. No Appalachian wilderness context anywhere in the article.

**Persona fidelity:** FAIL  
**Content quality:** FAIL — wrong niche  
**Verdict:** SEV-2

---

#### `best-mini-canvas-backpack.md` — SEV-2
**Type:** buyer_guide

Products: Phaoullzon teen girls mini backpack purse, JanSport Half Pint school bag, XPONNI backpack purse for teen, Sumleno boho canvas backpack, Makukke corduroy backpack purse. This is a teen fashion accessories article. The "boho," "grunge," and "style-forward silhouette" framing has no place in a bushcraft packs hub. Wesley voice completely absent, with one perverse exception: the hedging convention ("I haven't used this one personally") is applied to the Sumleno boho backpack, transplanting persona machinery into an off-niche article.

**Persona fidelity:** FAIL  
**Content quality:** FAIL — wrong niche  
**Verdict:** SEV-2

---

### AXES HUB (2 articles sampled)

---

#### `best-axe-for-splitting-wood.md` — PASS
**Type:** buyer_guide

Strong. "I've worked through enough cords in the Blue Ridge to have opinions." Products are correct: Fiskars, Hults Bruk, Helko Werk, Estwing. Proper hedging on Hults Bruk: "I haven't used this one personally." Voice sustained through the full article. No tactical/military framing.

**Persona fidelity:** PASS  
**Content quality:** PASS  
**Verdict:** PASS

---

#### `best-wood-splitting-axe-2.md` — PASS
**Type:** buyer_guide

First-person voice grounded: "I've put time in with this tool on ridge camps in the GW." Technical depth is real — HRC hardness range (50–55), axe vs. maul distinction, hickory vs. composite field replaceability argument. Proper hedging on the Fiskars 8lb maul: "I haven't swung an eight-pound maul regularly enough to give you a long-term wear assessment." Products on-niche throughout.

**Persona fidelity:** PASS  
**Content quality:** PASS  
**Verdict:** PASS

---

### SAWS HUB (1 article sampled)

---

#### `bahco-saw.md` — PASS (exemplary, tied for best)
**Type:** review

The Bahco Laplander is in Wesley's `bio_full` owned gear. This is the only article in the sample that covers a product Wesley is specified to own. The writing reflects it: "I've carried the Laplander in my pack through the George Washington and Jefferson National Forests long enough to have opinions worth sharing" and "I've owned one long enough to wear through two blades." These are credible, specific owned-gear claims. Kochanski cited appropriately for the pruning saw comparison. Proper hedging on non-personally-used models. Technical content (TPI, blade length, folding vs. fixed) is accurate.

**Persona fidelity:** PASS — exemplary, owned gear confirmed  
**Content quality:** PASS  
**Verdict:** PASS

---

### CLOTHING HUB (1 article sampled)

---

#### `best-waterproof-waxed-canvas-jacket.md` — PASS
**Type:** buyer_guide

Wesley's Filson Mackinaw cruiser jacket is in his `bio_full` owned gear. It's deployed naturally here: "An unlined shell over a Filson Mackinaw lets me add or shed insulation without changing jackets." Geographic grounding present: "In the GW or Jefferson, temperatures can swing twenty degrees in an afternoon." "I keep one in the shop" re: Otter Wax bar — specific, believable. Technical content on waxed canvas maintenance (paraffin wax, re-waxing frequency, seam stress points) is accurate. No tactical/military framing.

**Persona fidelity:** PASS — owned gear naturally deployed  
**Content quality:** PASS  
**Verdict:** PASS

---

### CORDAGE HUB (2 articles sampled)

---

#### `best-paracord-bracelet-designs.md` — SEV-2
**Type:** buyer_guide

Products include a soccer-themed bracelet (Lemo Treasure football/soccer bracelet). Wesley voice largely absent in the sections reviewed. The soccer bracelet has no bushcraft relevance. Content is generic craft-project writing without persona grounding.

**Persona fidelity:** FAIL  
**Content quality:** SEV-2 — off-niche product  
**Verdict:** SEV-2

---

#### `best-paracord-monkey-fist.md` — PASS
**Type:** buyer_guide

On-topic. Technical content about core weights, jig construction, and knot mechanics. Voice is minimal but not absent. Products are on-niche (monkey fist kits, weighted cores). No persona violations found.

**Persona fidelity:** PASS (limited voice sample)  
**Content quality:** PASS  
**Verdict:** PASS

---

### SHELTER HUB (1 article sampled)

---

#### `best-10x10-canvas-tarp.md` — PASS (frontmatter + structure reviewed)
**Type:** buyer_guide

Frontmatter and structure reviewed; full body not sampled. Products (canvas tarps) are on-niche. Hub assignment is correct.

**Persona fidelity:** Not fully assessed  
**Content quality:** PASS (partial)  
**Verdict:** PASS (partial)

---

### SKILLS HUB (1 article sampled)

---

#### `best-primitive-survival-skills.md` — PASS
**Type:** buyer_guide

Wesley voice sustained: "I've worked through sections of this over the years and found it consistently reliable at the technique level." Kochanski cited precisely and accurately: "Kochanski's argument for the 'survival attitude' over survival gear maps onto what this book teaches." Proper hedging on less-familiar material: "I haven't used this personally to the extent I've used the other books on this list." Products (Primitive Wilderness Living, Speir Outdoors, Hunting & Gathering Manual) are on-niche. No tactical/military framing.

**Persona fidelity:** PASS  
**Content quality:** PASS  
**Verdict:** PASS

---

### NAVIGATION HUB (1 article sampled)

---

#### `best-casa-blanca-map.md` — SEV-2
**Type:** buyer_guide

Products: National Geographic US wall map, Rand McNally US wall maps (×2), Swiftmaps world+USA set, Costa Blanca Spain Marco Polo pocket guide. This is a wall map buyer's guide for interior decoration and general geographic reference. No compasses, no topo maps, no orienteering, no wilderness navigation content. Wesley is entirely absent — no GW/Jefferson grounding, no first-person voice, no bushcraft framing. The navigation hub should cover field navigation tools (maps, compasses, GPS for backcountry use). This article does not address that use case in any way.

**Persona fidelity:** FAIL — Wesley voice completely absent  
**Content quality:** FAIL — wrong niche for hub  
**Verdict:** SEV-2

---

### COOKING HUB (1 article sampled)

---

#### `best-billy-can.md` — SEV-1
**Type:** buyer_guide

**SEV-1 meta-leakage:** The fifth product is Billy Jealousy Beard Control Leave-In Beard Conditioner. The article does not silently include this product — it explicitly acknowledges the error:

> "The Billy Jealousy Beard Control Leave-In Beard Conditioner appears in this brief due to what is clearly a data mismatch..."

The words "appears in this brief" are producer language. "Brief" is an internal production term. This is the production process explicitly described in the published article body — a more serious meta-leak than the Katadyn example, because it directly references platform machinery.

Otherwise: the article itself is competent. Wesley voice present ("I'd lean toward 1.1 liters as a practical solo target"), geographic grounding ("For weekend trips in the Blue Ridge or similar terrain"), and appropriate hedging on the Firemaple pot ("I haven't used this one personally in the GW or Jefferson"). The cooking content is technically sound.

**Persona fidelity:** PASS (article body, excluding the meta-leak section)  
**Content quality:** SEV-1 — beard conditioner as cookware + "appears in this brief" language  
**Verdict:** SEV-1 (dominant)

---

## Summary Table

| # | Slug | Hub | Type | Verdict |
|---|------|-----|------|---------|
| 1 | bahco-saw | saws | review | PASS (exemplary) |
| 2 | best-flint-and-steel-fire-starter | fire | buyer_guide | PASS (exemplary) |
| 3 | best-waterproof-waxed-canvas-jacket | clothing | buyer_guide | PASS |
| 4 | best-primitive-survival-skills | skills | buyer_guide | PASS |
| 5 | best-wood-splitting-axe-2 | axes | buyer_guide | PASS |
| 6 | best-axe-for-splitting-wood | axes | buyer_guide | PASS |
| 7 | best-diy-fire-starter | fire | buyer_guide | PASS |
| 8 | best-skinning-knife-2 | knives | buyer_guide | PASS |
| 9 | are-nalgene-bottles-dishwasher-safe | water | review | PASS |
| 10 | best-paracord-monkey-fist | cordage | buyer_guide | PASS |
| 11 | best-10x10-canvas-tarp | shelter | buyer_guide | PASS (partial) |
| 12 | katadyn-pocket-water-filter | water | review | SEV-1 |
| 13 | best-billy-can | cooking | buyer_guide | SEV-1 |
| 14 | bark-river-knife | knives | review | SEV-2 |
| 15 | best-fixed-blade-utility-knife | knives | buyer_guide | SEV-2 |
| 16 | how-do-you-start-a-fire | fire | buyer_guide | SEV-2 |
| 17 | best-black-canvas-backpack | packs | buyer_guide | SEV-2 |
| 18 | best-mini-canvas-backpack | packs | buyer_guide | SEV-2 |
| 19 | best-army-boonie-hat | clothing | buyer_guide | SEV-2 |
| 20 | best-paracord-bracelet-designs | cordage | buyer_guide | SEV-2 |
| 21 | best-casa-blanca-map | navigation | buyer_guide | SEV-2 |

**Pass rate (non-partial):** 10 / 20 = **50%**  
**SEV-1 (blocking):** 4 issues across 2 articles + all articles (image rendering)  
**SEV-2 (quality):** 9 articles with niche, persona, or content defects  

---

## Consolidated Finding List

### SEV-1 — Blocking

| ID | Finding | Scope |
|----|---------|-------|
| S1-01 | Image markdown broken: `![...]({'alt': '...', 'path': '...'})` renders as visible Python dict text instead of an image | All 205 articles |
| S1-02 | `katadyn-pocket-water-filter.md`: "The brief covers three Katadyn options" — producer reasoning in article body | 1 article |
| S1-03 | `best-billy-can.md`: "appears in this brief due to what is clearly a data mismatch" — production term in published body | 1 article |
| S1-04 | `best-billy-can.md`: Beard conditioner listed as camping cookware product | 1 article |

### SEV-2 — Quality

| ID | Finding | Scope |
|----|---------|-------|
| S2-01 | Em-dash substitute ` , ` throughout all articles | All 205 articles |
| S2-02 | `bark-river-knife.md`: "Bark River Review" title with zero Bark River products | 1 article |
| S2-03 | `best-fixed-blade-utility-knife.md`: Contractor utility knives (IRWIN, Grabber, Stanley) on a bushcraft knives hub | 1 article |
| S2-04 | `how-do-you-start-a-fire.md`: Bible study devotional and medical career book included as fire starting products | 1 article |
| S2-05 | `best-black-canvas-backpack.md`: Urban laptop bags (USB ports, school bags) on a bushcraft packs hub | 1 article |
| S2-06 | `best-mini-canvas-backpack.md`: Teen fashion purses, boho aesthetic bags on a bushcraft packs hub | 1 article |
| S2-07 | `best-army-boonie-hat.md`: Product pro reads "Tactical/military style suitable for both men and women" — conflicts with Wesley's explicitly anti-tactical persona | 1 article |
| S2-08 | `best-paracord-bracelet-designs.md`: Soccer bracelet included in cordage/paracord buyer guide | 1 article |
| S2-09 | `best-casa-blanca-map.md`: US wall maps for interior decoration on a wilderness navigation hub; no compasses, no topo maps, no backcountry content | 1 article |

### SEV-3 — Minor

| ID | Finding | Scope |
|----|---------|-------|
| S3-01 | `how-do-you-start-a-fire.md`: "I carry a BIC classic lighter and a Light My Fire Scout 2.0 ferro rod" — first-person ownership claimed for products not in persona's `owned_gear` without the required "I haven't used this personally" hedge | 1 article |
| S3-02 | `katadyn-pocket-water-filter.md`: "I've carried one into the GW more times than I've kept count" — Katadyn Pocket not in `bio_full` owned gear; hedging convention skipped | 1 article |

---

## Hub-Level Assessment

| Hub | Articles Sampled | Quality Signal | Notes |
|-----|-----------------|----------------|-------|
| Fire | 3 | **Strong** | Best persona execution in the sample. Two of three are solid. |
| Axes | 2 | **Strong** | Both pass. Technical depth, geographic grounding, hedging correct. |
| Saws | 1 | **Strong** | Bahco is owned gear — best article in the sample. |
| Clothing | 1 | **Strong** | Filson Mackinaw correctly deployed. |
| Skills | 1 | **Strong** | Kochanski citation correct, voice sustained. |
| Water | 2 | **Mixed** | One solid article; one SEV-1 meta-leak. |
| Knives | 3 | **Weak** | One pass, two fails. Title mismatch and wrong-niche products. |
| Cordage | 2 | **Mixed** | One pass, one SEV-2 soccer bracelet. |
| Packs | 2 | **Weak** | Both fail. Consistently wrong niche. |
| Navigation | 1 | **Weak** | Wall maps for interior decoration. No bushcraft content. |
| Cooking | 1 | **Mixed** | Solid underlying article; SEV-1 beard conditioner meta-leak. |
| Shelter | 1 | **Pass (partial)** | Frontmatter only reviewed. |

---

## Patterns and Systemic Observations

**Keyword targeting pulls non-bushcraft products.** The most severe content failures are not persona failures — they're product sourcing failures. The keyword "best mini canvas backpack" surfaces teen fashion bags. "Best fixed blade utility knife" surfaces contractor tools. "Casa blanca map" surfaces wall décor. The producer matched keywords to products correctly for those keywords, but many of the keywords have nothing to do with bushcraft. The problem is upstream: keyword selection pulled in queries that a bushcraft site should not rank for.

**Packs hub is systematically compromised.** Both packs articles sampled fail. The hub appears to be carrying a high proportion of articles targeting canvas bag keywords that have nothing to do with field carry. The keyword pool for packs likely needs auditing across the full hub.

**Navigation hub appears to cover map reference products, not field navigation tools.** The one navigation article sampled is a wall map buyer's guide. If this is representative of the navigation keyword pool, the entire hub may be targeting ambient "map" searches rather than orienteering, compass, or backcountry navigation.

**Voice quality correlates with product relevance.** Articles where the products are genuinely on-niche (Bahco saws, splitting axes, fire kits, waxed jackets) produce strong Wesley voice. Articles where the product pool is wrong (teen bags, contractor knives, wall maps) produce no Wesley voice at all. This is consistent: the producer needs correct product inputs to generate correct persona outputs.

**Meta-leakage is a recurring pattern.** Two independent SEV-1 meta-leaks found in 21 articles. Both are cases where the producer's reasoning about the brief appears in the published body. At 2/21 (roughly 10%), this may affect 20+ articles across the full 205 if consistent.

**Owned gear articles are significantly better.** The two best articles in the sample (bahco-saw.md and best-flint-and-steel-fire-starter.md) either cover owned gear directly or make specific geographic claims Wesley can credibly make. Articles where Wesley has no plausible relationship to the products being reviewed tend to be weaker.

---

## Recommended Triage Actions

Listed in priority order only — remediation scoping not included here.

1. **Fix image markdown globally (S1-01)** — all 205 articles have broken image rendering. No other fix matters more than this.
2. **Fix em-dash globally (S2-01)** — all 205 articles affected. String replacement.
3. **Pull or rewrite `best-billy-can.md` (S1-03, S1-04)** — beard conditioner + "appears in this brief" is SEV-1 and currently live.
4. **Pull or rewrite `katadyn-pocket-water-filter.md` (S1-02)** — "The brief covers three Katadyn options" is live.
5. **Audit packs hub keyword list** — both sampled articles are wrong niche. Likely systemic.
6. **Audit navigation hub keyword list** — one article sampled, wall maps for interior decoration.
7. **Review meta-leakage rate across full 205** — two found in 21 articles suggests 15–20 affected site-wide.

---

*Audited 2026-06-04. 21 articles reviewed across all 12 hubs.*
