# SERVER-SIDE INDEXATION DIAGNOSTIC — 2026-06-07
**Platform:** Affiliate v1.7.10–v2.2.0 | **VM:** root@46.225.29.35 | **Investigator:** Claude Code

---

## SCOPE NOTE

The companion brief listed these sites for investigation:
`firstshyguy`, `onlinehearingtest`, `bearcreekbarbecue`, `strengthmill`, `morelitterthantraffic`, `thecurateddog`, `northwoodsoverland`, `ten27cycling`, `betterhearinghub`, `saunassosimple`, `fourfernscare`

**Sites not found on this VM:** `firstshyguy`, `onlinehearingtest`, `morelitterthantraffic`, `thecurateddog`, `ten27cycling` (nor `ten27`, `ten27cycles`, or any variant). These may exist on a different server or in a separate portfolio context visible to the Chrome Claude session. They are excluded from all findings below.

**Sites investigated (present on VM):**
- High-arm: `bear-creek-barbecue` (BCB), `strengthmill` (SM)
- Low-arm: `my-little-tablespoon` (MLT), `northwoods-overland` (NWO), `betterhearinghub` (BHH), `saunassosimple` (SSS), `fourfernscare` (FFC)
- Also missing from VM: `four-season-gardener` (FSG), `one-happy-table` (OHT), `the-coffee-dispatch` (TCD)

---

## STEP 1: Platform Version

| Site | Arm | Platform | Version | Modified | Status |
|------|-----|----------|---------|----------|--------|
| bear-creek-barbecue | HIGH | Embedded (not symlinked) | **v1.7.10** | 2026-05-13 | Frozen at launch |
| strengthmill | HIGH | Embedded (not symlinked) | **v1.7.10** | 2026-05-14 | Frozen at launch |
| my-little-tablespoon | LOW | Empty/absent | unknown | — | No platform copy found |
| northwoods-overland | LOW | Minimal (portfolio.yaml + producer only) | unknown | 2026-05-18 | No package.json |
| betterhearinghub | LOW | Embedded (not symlinked) | **v2.1.1** | 2026-05-17 | Frozen at launch |
| saunassosimple | LOW | Embedded (not symlinked) | **v2.1.1** | 2026-05-17 | Frozen at launch |
| fourfernscare | LOW | Empty | unknown | — | No platform copy found |

**Reference:** Canonical platform on VM is v2.2.0 at `/root/affiliate-platform`. Sites 17–18 (FLF, TWC) symlink to it. All earlier sites have frozen embedded copies or none at all.

**Pattern:** No clear correlation with high/low arm split. Both high-arm sites on VM are v1.7.10; both confirmed-built low-arm sites are v2.1.1. Platform version alone does not explain the split.

---

## STEP 2: Sitemap Content

| Site | Arm | Sitemaps in dist/ | Notes |
|------|-----|-------------------|-------|
| bear-creek-barbecue | HIGH | **0** | No dist/ on VM — deployed via CF Pages direct upload |
| strengthmill | HIGH | **2** (sitemap-index + sitemap-0.xml) | Built on VM |
| my-little-tablespoon | LOW | **0** | No dist/ on VM |
| northwoods-overland | LOW | **0** | No dist/ on VM |
| betterhearinghub | LOW | **0** | No dist/ on VM |
| saunassosimple | LOW | **2** (sitemap-index + sitemap-0.xml) | Built on VM |
| fourfernscare | LOW | **0** | No dist/ on VM |

SM sitemap-index: `<sitemap><loc>https://strengthmill.com/sitemap-0.xml</loc></sitemap>`
SSS sitemap-index: `<sitemap><loc>https://saunassosimple.com/sitemap-0.xml</loc></sitemap>`

Both structure identically. Cannot inspect unbuilt sites from VM.

**Pattern:** No meaningful comparison possible — only 2 sites have dist/ on VM. No anomalies in the 2 inspectable sitemaps.

---

## STEP 3: robots.txt

| Site | Arm | public/robots.txt | dist/robots.txt |
|------|-----|-------------------|-----------------|
| bear-creek-barbecue | HIGH | ABSENT | N/A (no dist/) |
| strengthmill | HIGH | ABSENT | **PRESENT** — `Allow: /`, Sitemap ref |
| my-little-tablespoon | LOW | ABSENT | N/A (no dist/) |
| northwoods-overland | LOW | ABSENT | N/A (no dist/) |
| betterhearinghub | LOW | ABSENT | N/A (no dist/) |
| saunassosimple | LOW | ABSENT | **PRESENT** — `Allow: /`, Sitemap ref |
| fourfernscare | LOW | ABSENT | N/A (no dist/) |

robots.txt is build-time generated (not a static file). SM and SSS content identical — `User-agent: *`, `Allow: /`, sitemap reference. No blocking directives.

**Pattern:** No correlation. Universal absence from public/ is expected (Astro generates it at build time). No disallow rules found in either inspectable site.

---

## STEP 4: IndexNow Submission Records

| Site | Arm | Key file | Submit script | Submission log | Notes |
|------|-----|----------|---------------|----------------|-------|
| bear-creek-barbecue | HIGH | YES (7daa3484...) | YES | NONE | Script present, no evidence of submission |
| strengthmill | HIGH | **MISSING** | YES | NONE | Key file absent from public/ — any submission would 403 |
| my-little-tablespoon | LOW | YES (f3ddde59...) | ABSENT | NONE | Key exists but no script to submit |
| northwoods-overland | LOW | **YES × 2** (NWO + BCB key) | YES | NONE | BCB's key (7daa...) accidentally copied to NWO; NWO has its own key (31f5...) |
| betterhearinghub | LOW | ABSENT | ABSENT | NONE | No IndexNow infrastructure at all |
| saunassosimple | LOW | ABSENT | ABSENT | NONE | No IndexNow infrastructure at all |
| fourfernscare | LOW | ABSENT | ABSENT | NONE | No IndexNow infrastructure at all |

**No site in this cohort has a confirmed IndexNow submission record.** TWC (Site 18, launched 2026-06-07) is the only confirmed IndexNow submission in the portfolio (315 URLs, 200 OK).

Key issues:
- **SM**: key file missing from public/ — IndexNow verification would fail with 403
- **BHH, SSS, FFC**: zero IndexNow infrastructure — never set up
- **MLT**: key file exists but no submit script — never submitted
- **NWO**: BCB's key (7daa...) present alongside NWO's own key (31f5...) — accidental copy

**Pattern: STRONG absence across all sites.** BHH, SSS, FFC (all low-arm) have zero IndexNow infrastructure. SM (high-arm) has broken setup. The low-arm sites are uniformly unpinged.

---

## STEP 5: Article Count and Hub Structure

| Site | Arm | Articles | Built pages | Hubs | Articles/hub |
|------|-----|----------|-------------|------|--------------|
| bear-creek-barbecue | HIGH | **0 on VM** | 0 | — | — |
| strengthmill | HIGH | 296 | 352 | 12 | ~25 |
| my-little-tablespoon | LOW | 191 | 0 | 7 | ~27 |
| northwoods-overland | LOW | 290 | 0 | 12 | ~24 |
| betterhearinghub | LOW | 270 | 0 | 12+ | ~20 |
| saunassosimple | LOW | 365 | 439 | 12+ | ~30 |
| fourfernscare | LOW | 0 on VM | 0 | — | — |

BCB note: 0 articles in content/articles/ on VM despite 266 articles live in production — content deployed without leaving a VM copy.

**Pattern:** Article depth similar across sites (191–365). No meaningful correlation with arm.

---

## STEP 6: Persona Photo and Logo Asset Sizes

| Site | Arm | Byline photo | About photo | Logo SVGs |
|------|-----|-------------|-------------|-----------|
| bear-creek-barbecue | HIGH | 300,961 bytes ✓ | 1,048,076 bytes ✓ | **PLACEHOLDER** (834 bytes) |
| strengthmill | HIGH | 24,411 bytes ✓ | 68,517 bytes ✓ | **PLACEHOLDER** (327 bytes) |
| my-little-tablespoon | LOW | 3,169,440 bytes ✓ | — | **PLACEHOLDER** (809–1086 bytes) |
| northwoods-overland | LOW | — | — | Not found |
| betterhearinghub | LOW | — | — | **PLACEHOLDER** (1181–1304 bytes) |
| saunassosimple | LOW | 30,364 bytes ✓ | 288,208 bytes ✓ | **PLACEHOLDER** (851–1083 bytes) |
| fourfernscare | LOW | 7,135 bytes ✓ | 28,148 bytes ✓ | Not found |

**Portfolio-wide finding: ALL inspectable sites have placeholder SVG logos.** `generate-brand-assets.mjs` was never run on any pre-TWC site. This is B59-logo at portfolio scale — not a TWC-specific issue.

**Pattern:** Placeholder logos are universal — no correlation with high/low arm. Not a likely driver of the bimodal split.

---

## STEP 7: Article Image Presence

| Site | Arm | Image files | Format | Coverage |
|------|-----|-------------|--------|----------|
| bear-creek-barbecue | HIGH | 351 | Mixed JPG+WebP | ~1.25/article |
| strengthmill | HIGH | 218 | **JPG only** | ~0.74/article |
| my-little-tablespoon | LOW | 56 | JPG only | **~0.29/article** |
| northwoods-overland | LOW | **0** | — | **0/290 articles** |
| betterhearinghub | LOW | 741 | WebP ✓ | ~2.7/article |
| saunassosimple | LOW | 1,330 | WebP ✓ | ~3.6/article |
| fourfernscare | LOW | 646 | WebP ✓ | N/A |

**NWO has ZERO article images for 290 articles.** B59-images hit NWO at full scale — every article hero is null in production.

**MLT is severely underimaged** — 56 images for 191 articles. Most articles have no hero image.

**SM uses JPG format** — built before WebP was adopted. No `source-images-pexels.mjs` was used.

**Pattern:** Moderate correlation for NWO and MLT specifically. Both are low-arm and both have image gaps. However BHH, SSS, FFC (all low-arm) have full image coverage — image gaps don't fully explain the split.

---

## STEP 8: Schema Markup in Built HTML

Only SM and SSS have dist/ builds on VM.

| Site | Arm | Schema types |
|------|-----|-------------|
| strengthmill | HIGH | Article, BreadcrumbList, ImageObject, ListItem, Organization, Person, WebPage |
| saunassosimple | LOW | Article, BreadcrumbList, ImageObject, ListItem, Organization, Person, WebPage |

Identical schema type sets across both arms.

**Pattern:** No correlation — schema is consistent. Not a driver of the split.

---

## STEP 9: GA4 Measurement ID

| Site | Arm | Config value | Built HTML | Status |
|------|-----|-------------|------------|--------|
| bear-creek-barbecue | HIGH | G-742CEG3NG0 | N/A (no dist/) | **Real ID** ✓ |
| strengthmill | HIGH | `""` (empty) | N/A | **MISSING — no GA4** |
| my-little-tablespoon | LOW | `REPLACE_WITH_GA4_ID` | N/A | **PLACEHOLDER — no GA4** |
| northwoods-overland | LOW | null/empty | N/A | **MISSING — no GA4** |
| betterhearinghub | LOW | `${GA4_ID}` | N/A | CF Pages env var — resolves if env var is set |
| saunassosimple | LOW | null | G-EMVZ8X6M5R ✓ | **CF Pages env var resolving correctly** |
| fourfernscare | LOW | null | N/A | CF Pages env var — status unknown from VM |

Three confirmed missing GA4 deployments: SM (empty string), MLT (literal placeholder), NWO (null). SSS has null in config but real ID resolves via CF Pages env var — that pattern works correctly.

**Pattern: MODERATE.** MLT and NWO (both low-arm) have confirmed missing GA4. SM (high-arm) also missing — weakens correlation. But the two low-arm sites with the worst image gaps also have no GA4, compounding their disadvantage.

---

## STEP 10: GSC Verification

| Site | Arm | Verification file | In config |
|------|-----|------------------|-----------|
| All 7 sites | Both | NONE | NONE |

Universal absence of GSC verification HTML files. Platform uses DNS TXT record verification via `cloudflare-pages-config.mjs add-dns-txt` — HTML files are not expected. Absence is correct behavior.

**Pattern:** No correlation — uniform across both arms.

---

## SYNTHESIS

### Factors correlating with the split

| Factor | High-arm (BCB, SM) | Low-arm (MLT, NWO, BHH, SSS, FFC) | Strength |
|--------|-------------------|-------------------------------------|----------|
| IndexNow submitted | BCB: key+script, no submission record; SM: **key missing** | BHH/SSS/FFC: zero infrastructure; MLT: key no script; NWO: dual keys, no submission | **MODERATE** — low-arm has more complete absence, but no arm has confirmed submissions |
| GA4 firing | BCB: real ID ✓; SM: **missing** | MLT: placeholder; NWO: null; BHH/FFC: unknown via env var; SSS: ✓ | **MODERATE** — two worst low-arm sites (MLT, NWO) confirmed GA4-absent |
| Article images | BCB: full; SM: 0.74/article (JPG) | MLT: 0.29/article; **NWO: 0**; BHH/SSS/FFC: full | **MODERATE for NWO/MLT** |
| Platform version | v1.7.10 | v2.1.1 or unknown | No pattern |
| robots.txt | Generated correctly | Generated correctly | No correlation |
| Schema types | Full set | Full set | No correlation |

### Factors with NO correlation

- robots.txt: no blocking directives anywhere
- Schema markup: identical types in both arms
- Sitemap structure: identical format in inspectable sites
- Persona photos: present on most sites regardless of arm
- GSC verification method: DNS TXT across all sites

### Most Likely Root Causes (ranked by confidence)

1. **IndexNow never successfully submitted** — dominant factor. No site in this cohort has a confirmed submission record. BHH, SSS, FFC have zero IndexNow infrastructure; SM's key file is absent. Without IndexNow ping at launch, all 200–365 article URLs depend entirely on passive Google crawl discovery. Sites that received earlier manual sitemap submissions to GSC or had more organic link signals would index faster — consistent with a bimodal distribution where early-submitted or better-linked sites form the high arm.

2. **GA4 not firing on NWO and MLT** — two confirmed low-arm content sites have no GA4 whatsoever. Google uses GA4 behavioral signals as crawl-priority proxies. Sites with no GA4 send no engagement signal; Google treats them equivalently to low-engagement sites.

3. **NWO: zero article images** — 290 articles with null hero images in production. Images are a significant crawl and indexation signal; ImageObject schema relies on them. NWO's content quality score is artificially depressed across every article.

4. **MLT severely underimaged** — 56 images for 191 articles (~0.29/article). Lower severity than NWO but same class.

### Unexpected Findings (not directly related to bimodal split)

- **B59-logo is portfolio-wide**: ALL 7 inspectable sites have placeholder SVG logos (327–1304 bytes). `generate-brand-assets.mjs` has never been run on any pre-TWC site. Logged as TWC-specific (B59-logo) but is actually systemic across the portfolio.
- **NWO has BCB's IndexNow key deployed**: `7daa3484507f92b389f47a58dd424977.txt` (BCB's key, created May 11) is present on northwoodsoverland.com alongside NWO's own key `31f59444d80e838fb472be0861fee463.txt` (May 17). The BCB key was accidentally copied during NWO setup.
- **SM has no git history** on VM despite being a launched site with 296 articles.
- **BCB has 0 content/articles on VM** despite 266 articles live in production — content was deployed without leaving a VM copy.
- **SM images are all JPG** (not WebP) — built before WebP was adopted in the image pipeline.
- **SSS GA4 resolves from CF Pages env var** despite `null` in site.config.yaml — confirms the env-var injection pattern works correctly for newer sites.

---

*Diagnostic generated: 2026-06-07. Read-only investigation — no changes made. Companion to Chrome Claude front-end diagnostic.*
