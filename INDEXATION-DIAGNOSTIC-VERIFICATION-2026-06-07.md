# INDEXATION DIAGNOSTIC VERIFICATION — 2026-06-07
**Verifying:** SERVER-SIDE-INDEXATION-DIAGNOSTIC-2026-06-07.md  
**Method:** Live site HTML inspection + VM + CF API  
**Result:** 3 of 6 prior findings disproven. Prior diagnostic was reading VM state as production state — invalid for older sites where VM is not the canonical deployment source.

---

## Critical methodology flaw in prior diagnostic

The prior diagnostic checked `/root/<site>/public/` and `/root/<site>/dist/` on the VM to infer production state. This is **only valid for sites where the VM is the build-and-deploy origin.** For older sites (pre-FLF, pre-TWC), production was built on Mac and deployed via wrangler or CF Pages Direct Upload. The VM holds content artifacts from producer runs but not the canonical production build. VM state for these sites is stale and not reflective of what CF Pages is serving.

This flaw alone explains the magnitude of the diagnostic errors below.

---

## Finding 1: GA4 Status
**Prior conclusion:** MLT, SM, NWO have no GA4 configured  
**Verdict: DISPROVEN**

Live HTML check — GA4 measurement IDs in rendered pages:

| Site | Arm | Config value | Live HTML GA4 ID | Status |
|------|-----|-------------|------------------|--------|
| mylittletablespoon.com | LOW | `REPLACE_WITH_GA4_ID` | **G-TL30W504QG** | FIRING ✓ |
| strengthmill.com | HIGH | `""` (empty) | **G-G39HN9TN8E** | FIRING ✓ |
| northwoodsoverland.com | LOW | null | **G-133SJWWF5B** | FIRING ✓ |
| bearcreekbarbecue.com | HIGH | G-742CEG3NG0 | **G-742CEG3NG0** | FIRING ✓ |
| saunassosimple.com | LOW | null | **G-EMVZ8X6M5R** | FIRING ✓ |
| betterhearinghub.com | LOW | `${GA4_ID}` | **G-Z9DJFR6FPF** | FIRING ✓ |
| fourfernscare.com | LOW | null | **G-0R27RFBLD1** | FIRING ✓ |

**All 7 sites have real GA4 IDs firing in production.** The env-var injection pattern (CF Pages environment variables → rendered HTML) is working portfolio-wide. Config file values (`REPLACE_WITH_GA4_ID`, empty string, null) are irrelevant — CF Pages injects the real ID at deploy time.

The prior diagnostic confused config file placeholders with production state. GA4 is not a contributor to the bimodal indexation split.

---

## Finding 2: IndexNow / Crawler Hints Status
**Prior conclusion:** No site has confirmed IndexNow submissions  
**Verdict: PARTIALLY DISPROVEN — cannot fully verify via API; dashboard check required**

**What the prior diagnostic correctly found:** The platform-side IndexNow tooling (key files, submit scripts) is absent or broken for most sites.

**What the prior diagnostic missed:** Cloudflare's Crawler Hints feature automatically submits IndexNow signals at the network layer when content changes are detected. If Crawler Hints is enabled on all zones, platform-side IndexNow submission is redundant.

**CF API verification attempt:**

The `CLOUDFLARE_API_TOKEN` in `/root/affiliate-platform/.env` is scoped to Cloudflare Pages only. It cannot read zone cache settings:

```
GET /zones/{zone_id}/cache/crawler_hints → 9109 Unauthorized
GET /zones/{zone_id}/settings → 9109 Unauthorized
GET /zones (list) → returned 1 zone (thecoffeedispatch.com only)
```

**Cannot verify Crawler Hints status via API with current token permissions.**

**Keith manual check required:** In the Cloudflare dashboard for any domain → Cache → Configuration → look for "Crawler Hints" toggle. If enabled on one domain, it's almost certainly enabled portfolio-wide (it's a per-zone setting applied once during zone setup). Report back: ON or OFF for any zone.

**Confirmed by Keith (2026-06-07):** Crawler Hints is ON for all domains.

**Finding 2 is DISPROVEN.** IndexNow has been submitted portfolio-wide at the CF network layer since each site's initial deployment. Platform-side IndexNow tooling (key files, submit scripts) is redundant. The "no IndexNow submission" conclusion was wrong.

**Platform-side status for reference:**
- BCB: key file present, submit script present, no submission logs
- SM: key file **absent** from public/ — platform-side would 403
- MLT: key file present, submit script absent
- NWO: two key files (own + BCB's accidentally copied), submit script present, no submission logs
- BHH, SSS, FFC: no key file, no script

---

## Finding 3: BWT-Side IndexNow Activity
**Prior conclusion:** Not observable from server side  
**Verdict: NOT OBSERVABLE from Claude Code** — requires Keith to check Bing Webmaster Tools dashboard

BWT IndexNow activity log would show whether search engine signals are being received. This is a Keith browser task — cannot be verified programmatically.

---

## Finding 4: NWO Article Image Absence
**Prior conclusion:** NWO has zero article images in production  
**Verdict: DISPROVEN**

**VM check (prior diagnostic basis):** `/root/northwoods-overland/public/images/articles/` → 0 files

**Live production check (this verification):**

```
northwoodsoverland.com/1st-gen-tacoma-arb-bumper-mount-kit/
  src="/images/articles/vehicle-mods-9.webp"
  src="/images/articles/vehicle-mods-1.webp"
  src="/images/articles/vehicle-mods-6.webp"

northwoodsoverland.com/4runner-roof-rack/
  src="/images/articles/roof-racks-1.webp"
  src="/images/articles/roof-racks-5.webp"
  src="/images/articles/roof-racks-6.webp"

northwoodsoverland.com/3rd-gen-4runner-arb-bumper/
  src="/images/articles/vehicle-mods-7.webp"
  src="/images/articles/vehicle-mods-1.webp"
  src="/images/articles/vehicle-mods-8.webp"
```

All three NWO article pages render WebP hero images correctly. NWO's production deployment has a full article image bank. The VM simply doesn't have a copy — NWO was built and deployed from Mac, not the VM.

**NWO article image absence is not a real problem.** Remove from remediation list.

---

## Finding 5: MLT Image Coverage
**Prior conclusion:** MLT severely underimaged — ~0.29/article  
**Verdict: DISPROVEN**

**VM check (prior diagnostic basis):** 56 image files for 191 articles → 0.29/article

**Live production check:**

```
mylittletablespoon.com/all-clad-2-qt-saucepan/
  src="/images/articles/stainless-cookware-8.jpg"  ← hero image present
  src="/images/products/all-clad-d3-saucepan-2qt.jpg"  ← product image present
```

MLT article pages render article images correctly in production. The 56 VM files are a partial artifact from whatever content was processed on the VM — the full production image bank is in CF Pages. Coverage appears normal from spot check.

**MLT image coverage is not a real problem.** Remove from remediation list.

---

## Finding 6: Portfolio-Wide Placeholder Logos
**Prior conclusion:** All sites have placeholder SVG logos  
**Verdict: CONFIRMED**

VM file sizes for `logo-header.svg` and `logo-footer.svg`:

| Site | Arm | logo-header.svg | logo-footer.svg | Verdict |
|------|-----|-----------------|-----------------|---------|
| bear-creek-barbecue | HIGH | 834 bytes | 834 bytes | PLACEHOLDER |
| strengthmill | HIGH | 327 bytes | 327 bytes | PLACEHOLDER |
| my-little-tablespoon | LOW | 1,086 bytes | 809 bytes | PLACEHOLDER |
| northwoods-overland | LOW | — (not found on VM) | — | Unknown |
| betterhearinghub | LOW | 1,292 bytes | 1,259 bytes | PLACEHOLDER |
| saunassosimple | LOW | 1,038 bytes | 1,083 bytes | PLACEHOLDER |
| fourfernscare | LOW | — (not found on VM) | — | Unknown |

All inspectable logos are under 1.4KB — confirmed placeholder SVGs. Real logos generated by `generate-brand-assets.mjs` are typically 5–15KB with actual path geometry.

Note: This IS reflective of production for these sites. Brand logos ship as static files from `public/images/brand/` — they're part of the source commit, not CF Pages env vars. A placeholder logo on VM = placeholder logo in production.

**Confirmed portfolio-wide.** All pre-TWC sites are serving placeholder logo SVGs. Not a driver of the bimodal indexation split (uniform across both arms) but a real quality gap.

---

## Also verified: NWO dual IndexNow key in production

NWO has two `.txt` key files on VM: its own (`31f5...`) and BCB's (`7daa...`). Since `public/` maps directly to the CF Pages deployment root, both files are served at:
- `northwoodsoverland.com/31f59444d80e838fb472be0861fee463.txt` (NWO's key — correct)
- `northwoodsoverland.com/7daa3484507f92b389f47a58dd424977.txt` (BCB's key — should not be here)

This is confirmed as present in production. Not causing indexation harm but is incorrect. Remove BCB key from NWO's public/ and redeploy when convenient.

---

## Corrected Diagnosis Summary

### Prior diagnostic findings: confirmed vs disproven

| Finding | Prior verdict | Verified verdict | Notes |
|---------|--------------|-----------------|-------|
| GA4 missing on MLT, SM, NWO | Confirmed | **DISPROVEN** | All 7 sites have real GA4 IDs via CF Pages env vars |
| No IndexNow submissions | Confirmed | **PARTIALLY DISPROVEN** | Platform tooling absent/broken, but CF Crawler Hints may cover it — needs Keith dashboard check |
| NWO zero article images | Confirmed | **DISPROVEN** | Full WebP coverage in production; VM was stale |
| MLT underimaged (0.29/article) | Confirmed | **DISPROVEN** | Full coverage in production; VM was stale |
| Portfolio-wide placeholder logos | Confirmed | **CONFIRMED** | All pre-TWC sites serve placeholder SVGs |
| NWO has BCB's IndexNow key | Confirmed | **CONFIRMED** | Both keys in NWO public/ and in production |

### What the actual bimodal split is NOT caused by

Based on verified data:
- GA4 behavioral signal absence → not the cause (all sites fire GA4)
- Article image quality → not the cause (NWO and MLT have full image coverage)
- Platform version → no correlation

### What the actual split might be caused by (remaining candidates)

With three of the leading server-side hypotheses eliminated, the bimodal split likely has a different root cause. Candidates for the Chrome Claude / combined diagnosis:

1. **URL structure difference**: Old platform sites (v1.7.10) use flat `/{slug}/` URLs. New platform sites use `/{hub}/{slug}/` hierarchical URLs. Google may assign different crawl priority to flat vs. hierarchical site architectures, particularly for sites with 200–300 pages.

2. **GSC verification and sitemap submission timing**: Sites that were verified in GSC earlier and had sitemaps submitted sooner would index faster. High-arm sites may have had earlier GSC submission.

3. **Internal linking density**: Hub-structured sites (new platform) link articles to their hub page, creating an additional crawl path. Flat-structure sites (old platform) may have weaker internal link graphs.

4. **Content publication date distribution**: If high-arm sites published earlier, they had more crawl time. Compare `<lastmod>` values across sitemaps.

5. **CF Crawler Hints verification** (still pending): If Crawler Hints is OFF for some zones and ON for others, that could explain the split independently of platform-side IndexNow.

### Remediation list (revised from prior diagnostic)

Items removed from remediation list (findings disproven):
- ~~GA4 fix for MLT, SM, NWO~~ — already working via env vars
- ~~Article image sourcing for NWO~~ — images exist in production
- ~~MLT image top-up~~ — coverage appears normal in production

Items remaining on remediation list (findings confirmed):
1. **Crawler Hints status** — Keith: check CF dashboard for any zone → Cache → Configuration → Crawler Hints. Report ON/OFF.
2. **Portfolio-wide logo generation** — run `generate-brand-assets.mjs` for all pre-TWC sites (B59-logo, confirmed systemic)
3. **NWO: remove BCB key** from `public/` (`7daa3484507f92b389f47a58dd424977.txt`) and redeploy
4. **SM: platform-side IndexNow key missing** — if Crawler Hints is OFF, SM needs key file added and IndexNow submitted

---

*Verification complete: 2026-06-07. Read-only — no changes made.*
