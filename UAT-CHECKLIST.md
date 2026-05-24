# UAT Checklist — Site Launch Scorecard

**Version:** v1.0 — created 2026-05-24 from SaunasSoSimple post-mortem.

This checklist replaces ad-hoc UAT with a scored, reproducible gate. Score the site before signing it as production-ready.

**Launch bar:** 0 Critical | ≤2 Quality  
**If Critical > 0:** Blocked. Fix before proceeding.  
**If Quality > 2:** Review and decide — each is documented with a recommended remedy.

---

## How to score

For each item, mark:
- **PASS** — criterion met, no action needed
- **FAIL** — criterion not met (counts toward Critical or Quality total)
- **N/A** — not applicable to this site or article type
- **SKIP** — deferred with documented reason

---

## Section A — Automated (run pre-flight first)

Run `python3 affiliate-platform/scripts/preflight.py --site <slug> --verbose` before scoring Section A.
All Section A items with FAIL status from the pre-flight script are automatically Critical below.

| # | Item | Severity | Pre-flight check | Status |
|---|------|----------|-----------------|--------|
| A1 | No scaffold contamination from other verticals | Critical | scaffold-contamination | |
| A2 | Article count ≥80% of pipeline.json count | Quality | state-sync | |
| A3 | All hubs have non-boilerplate descriptions | Critical | hub-descriptions | |
| A4 | SchemaMarkup.astro uses absolute schema URLs | Critical | json-ld-urls | |
| A5 | og:locale present in BaseLayout.astro | Quality | og-locale | |
| A6 | Persona photo files exist and are non-trivial size | Quality | persona-consistency | |
| A7 | No near-duplicate slugs (same words, different order) | Critical | url-slug-dedup | |
| A8 | No YMYL-risk hub slugs or labels | Critical | ymyl-hub-check | |
| A9 | No cross-domain product references (FAIL-level) | Critical | product-topic-match | |
| A10 | No within-site hub adjacency issues (WARN-level) | Quality | product-topic-match | |

---

## Section B — Build output

Run `npm run build` and check `dist/`.

| # | Item | Severity | Check | Status |
|---|------|----------|-------|--------|
| B1 | Build exits 0 with no FAIL lines | Critical | `npm run build` | |
| B2 | Build-validator produces 0 FAIL lines | Critical | build-validator.mjs output | |
| B3 | `grep -c "amazon_asin: VERIFY" content/products/products.yaml` → 0 | Critical | manual | |
| B4 | Sitemap-index.xml present in dist/ | Quality | `ls dist/sitemap-index.xml` | |
| B5 | At least 1 article per hub in dist/ | Quality | `ls dist/*/` count | |
| B6 | 404 page present and branded | Quality | `curl -o /dev/null -s -w "%{http_code}" https://<domain>/nonexistent` | |

---

## Section C — Platform checks

Spot-check 5 random articles (use `shuf content/articles/*.md | head -5`).

| # | Item | Severity | Method | Status |
|---|------|----------|--------|--------|
| C1 | GA4 measurement ID present in page source | Critical | `grep -l "G-" dist/index.html` | |
| C2 | Amazon affiliate tag correct in affiliate links | Critical | `grep -o "tag=[^&\"]*" dist/*/index.html \| sort -u` | |
| C3 | og:locale en_US present | Quality | `grep "og:locale" dist/index.html` | |
| C4 | Cookie consent banner present in HTML | Quality | `grep "cookie-banner" dist/index.html` | |
| C5 | Canonical URL is absolute (starts with https://) | Quality | `grep "rel=\"canonical\"" dist/*/index.html \| head -3` | |
| C6 | JSON-LD schema present and @type populated | Quality | `grep -l '"@type"' dist/*/index.html \| wc -l` | |
| C7 | No hardcoded hearing-aid/prior-site vocabulary in HTML | Critical | `grep -ri "hearing aid\|audiologist" dist/ \| wc -l` must be 0 | |

---

## Section D — Content quality (sample 10 articles)

Open 10 random articles from the live site. Check each against these criteria.

| # | Item | Severity | Check | Status |
|---|------|----------|-------|--------|
| D1 | Persona name appears in byline | Quality | visual inspection | |
| D2 | Persona photo renders (not broken image) | Quality | visual inspection | |
| D3 | Products referenced in text match products in product cards | Quality | read article | |
| D4 | No first-person testing claims ("I tested", "I installed", "I've owned") | Critical | `node scripts/validate-persona-claims.mjs --site <slug>` | |
| D5 | Affiliate disclosure visible above first affiliate link | Critical | visual inspection | |
| D6 | No placeholder text visible (`{{TOKEN}}`, `LOREM_IPSUM`, `REPLACE_ME`) | Critical | `grep -ri "{{.*}}\|LOREM_IPSUM\|REPLACE_ME" dist/ \| wc -l` must be 0 | |
| D7 | Article word count ≥1500 for buyer_guide/roundup types | Quality | spot check 3 articles | |
| D8 | All product cards show name, image placeholder or actual image | Quality | visual inspection | |
| D9 | Hub page shows articles (not empty listing) | Quality | visit 3 hub URLs | |
| D10 | No obviously off-niche content (gardening article on sauna site, etc.) | Critical | spot check 5 articles | |

---

## Section E — Technical SEO

| # | Item | Severity | Check | Status |
|---|------|----------|-------|--------|
| E1 | robots.txt present and allows Googlebot | Quality | `curl https://<domain>/robots.txt` | |
| E2 | Sitemap submitted to GSC | Quality | GSC → Sitemaps panel | |
| E3 | Sitemap submitted to Bing Webmaster | Quality | BWT → Sitemaps panel | |
| E4 | GSC ownership verified | Quality | GSC → Domain property | |
| E5 | Bing ownership verified | Quality | BWT → My sites | |
| E6 | No duplicate title tags across sampled pages | Quality | `grep -h "<title>" dist/*/index.html \| sort \| uniq -d` → few results | |

---

## Section F — Furniture pages

Run `node affiliate-platform/scripts/validate-furniture-pages.mjs --site <slug>` before scoring.

| # | Item | Severity | Check | Status |
|---|------|----------|-------|--------|
| F1 | About page exists and uses persona name | Critical | `curl https://<domain>/about/` → 200 | |
| F2 | Privacy policy exists | Critical | `curl https://<domain>/privacy/` → 200 | |
| F3 | Affiliate disclosure page exists | Critical | `curl https://<domain>/affiliate-disclosure/` → 200 | |
| F4 | No first-person testing claims in furniture pages | Critical | validate-furniture-pages.mjs HARD output | |
| F5 | No prior-vertical vocabulary bleed in furniture pages | Quality | validate-furniture-pages.mjs output | |
| F6 | Footer links to About, Privacy, Disclosure | Quality | visual inspection | |

---

## Scoring summary

After scoring all items, tally here:

| Section | Critical FAILs | Quality FAILs |
|---------|----------------|---------------|
| A — Automated | | |
| B — Build output | | |
| C — Platform checks | | |
| D — Content quality | | |
| E — Technical SEO | | |
| F — Furniture pages | | |
| **TOTAL** | | |

**Launch decision:**

| Result | Action |
|--------|--------|
| 0 Critical, 0 Quality | Launch. Document date. |
| 0 Critical, 1–2 Quality | Launch. Quality items to backlog. |
| 0 Critical, 3+ Quality | Judgment call. Document each deferred Quality item and rationale. |
| 1+ Critical | BLOCKED. Fix Critical items, re-score affected sections. |

---

## SaunasSoSimple baseline (2026-05-24, post-remediation)

Scored after Steps 1–7 of UAT remediation were complete.

| Section | Critical FAILs | Quality FAILs | Notes |
|---------|----------------|---------------|-------|
| A — Automated (pre-flight) | 0 | 3 | A2 WARN: 80% article count (76 pipeline articles are reserve pool). A6 WARN: byline photo 3KB (valid compressed JPEG). A10 WARN: 12 within-site hub adjacency (Harvia sensor cross-hub). |
| B — Build output | 0 | 0 | Build exits 0, 0 FAIL lines |
| C — Platform checks | 0 | 0 | GA4 G-EMVZ8X6M5R, tag=saunassosimple-20, og:locale present |
| D — Content quality | 0 | 0 | 10 sampled articles clean |
| E — Technical SEO | 0 | 0 | GSC + Bing verified 2026-05-24 |
| F — Furniture pages | 0 | 0 | All furniture pages present and clean |
| **TOTAL** | **0** | **3** | **LAUNCH CLEAR** |

**Decision:** LAUNCH CLEAR — 0 Critical, 3 Quality (all non-blocking, documented above).

---

## Caregiver site target

UAT goal per Platform Stabilization Brief: ≤2 Critical issues at first UAT pass.

The 5-check pre-flight (A1–A10) catches structural issues before manual UAT. If the pre-flight passes, Section A should contribute 0 Critical FAILs. Target remaining Critical exposure: Sections D and F (content claims, furniture pages).
