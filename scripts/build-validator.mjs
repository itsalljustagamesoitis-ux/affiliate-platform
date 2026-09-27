/**
 * Post-build validator — fails the build if critical issues are found in dist/.
 * Checks: empty pages, missing images, empty product cards, unreplaced template tokens,
 * untagged affiliate links, hardcoded prices, refusal-pattern content, CTA density,
 * sentinel image hashes, placeholder ASINs, duplicate breadcrumbs, doubled brand names,
 * duplicate product-card rationale, blank comparison-table cells, head-term/spoke
 * internal linking, missing head-term articles, orphaned spokes, keyword-variant collisions.
 * Run via: node scripts/build-validator.mjs
 */

import { readFileSync, readdirSync, statSync, existsSync } from 'fs'
import { join, relative, resolve } from 'path'
import yaml from 'js-yaml'

// All paths resolve relative to the site CWD (where `npm run build` is invoked),
// not relative to this script file — the script lives in node_modules/@platform/core/scripts/
const SITE_ROOT = process.cwd()
const DIST = resolve(SITE_ROOT, 'dist')
const MIN_HTML_BYTES = 500

// Resolve the configured Amazon tag so we can verify it's actually in affiliate URLs
const _cfg = yaml.load(readFileSync(resolve(SITE_ROOT, 'site.config.yaml'), 'utf8'))
const CONFIGURED_TAG = process.env.AMAZON_TAG ?? _cfg?.affiliate?.amazon_tracking_id ?? ''

// Article type map: slug → type — populated in the article source check block below,
// used for CTA density (Check 7) and comparison card count (Check 9)
const ARTICLE_TYPE_MAP = new Map()

// Head-term / spoke maps (Fix 1 / Fix 4) — populated in the article source check
// block below from each article's `role:` and `parent_head:` frontmatter fields.
const ROLE_MAP = new Map()          // slug -> 'HEAD' | 'spoke'
const PARENT_HEAD_MAP = new Map()   // spoke slug -> parent_head slug
const HUB_MAP = new Map()           // slug -> hub slug
const KEYWORD_MAP = new Map()       // slug -> target_keyword
const AXIS_MAP = new Map()          // slug -> axis (e.g. 'price') -- exempts specific modifier
                                     // subsets from collision stripping; see semanticSignature()
const SPOKES_BY_HEAD = new Map()    // head slug -> [spoke slug, ...] (built after the walk, below)

// AI refusal phrases that should never appear in published article content.
// Use regex with word boundaries so "as an ai" doesn't match "as an air conditioner" etc.
const REFUSAL_PATTERNS = [
  /\bi need to pause\b/,
  /\bas an ai\b/,
  /\bi can'?t write\b/,
  /\bi cannot write\b/,
  /\bi'?m unable to\b/,
  /\bi am unable to\b/,
  /\bas a language model\b/,
  /\bas an llm\b/,
]

const BUYER_ARTICLE_TYPES = new Set(['buyer_guide', 'roundup', 'comparison'])

let failures = 0
const errors = []
const warnings = []

function fail(check, file, msg) {
  errors.push(`  FAIL [${check}] ${file}\n       ${msg}`)
  failures++
}

function checkFile(fullPath) {
  const rel = relative(DIST, fullPath)
  const raw = readFileSync(fullPath, 'utf8')
  const size = Buffer.byteLength(raw, 'utf8')

  // ── 1. Empty page ────────────────────────────────────────────────────────
  // Skip intentional Astro redirect pages (they're tiny but valid)
  if (raw.includes('http-equiv="refresh"')) return

  if (size < MIN_HTML_BYTES) {
    fail('empty-page', rel, `${size} bytes — minimum is ${MIN_HTML_BYTES}`)
    return // Nothing else to check on a near-empty file
  }

  // ── 2. Missing local images ──────────────────────────────────────────────
  // Use pre-cached DIST_FILE_SET for O(1) lookups instead of existsSync per image.
  const imgRe = /<img[^>]+src="(\/images\/[^"]+)"[^>]*>/gi
  let imgMatch
  while ((imgMatch = imgRe.exec(raw)) !== null) {
    const imgPath = imgMatch[1]
    const diskPath = DIST + imgPath
    if (!DIST_FILE_SET.has(diskPath)) {
      fail('missing-image', rel, `Image not found on disk: ${imgPath}`)
    }
  }

  // ── 3. Empty product card images ─────────────────────────────────────────
  // A product-card__image div with no <img> means the image failed to render
  // or the product was never backfilled with an image. WARN so builds succeed
  // while the catalog gap is visible in CI output.
  const pcImgRe = /class="product-card__image"[^>]*>([\s\S]*?)<\/div>/g
  let pcMatch
  let emptyCardCount = 0
  while ((pcMatch = pcImgRe.exec(raw)) !== null) {
    if (!/<img\b/i.test(pcMatch[1])) emptyCardCount++
  }
  if (emptyCardCount > 0) {
    warnings.push(`  WARN [empty-product-card] ${rel}\n       ${emptyCardCount} product-card__image div(s) contain no <img> — product image(s) not yet backfilled`)
  }

  // ── 4. Unreplaced template tokens ────────────────────────────────────────
  // Catches {{TOKENS}}, PLACEHOLDER_X, PERSONA_LOCATION, SITE_NICHE etc. that
  // should have been substituted at build time. Exempt the affiliate disclosure
  // page (contains literal placeholder text as examples).
  if (!rel.startsWith('affiliate-disclosure')) {
    const stripped = raw
      .replace(/<script[\s\S]*?<\/script>/gi, '')
      .replace(/<style[\s\S]*?<\/style>/gi, '')
    const PLACEHOLDER_RE = /\{\{[A-Z_]{3,}\}\}|PLACEHOLDER_[A-Z_]+|PERSONA_LOCATION|SITE_NICHE/
    const phMatch = PLACEHOLDER_RE.exec(stripped)
    if (phMatch) {
      fail('unreplaced-placeholder', rel, `Unreplaced template token in rendered HTML: "${phMatch[0]}"`)
    }
  }

  // ── 5. Untagged Amazon affiliate links ───────────────────────────────────
  const anchorRe = /<a\s[^>]*href="([^"]*amazon\.com[^"]*)"[^>]*>/gi
  let m
  while ((m = anchorRe.exec(raw)) !== null) {
    const tag = m[0]
    const href = m[1]
    if (!/rel="[^"]*sponsored[^"]*"/.test(tag)) {
      const snippet = tag.replace(/\s+/g, ' ').slice(0, 120)
      fail('untagged-affiliate', rel, `Amazon link missing rel="sponsored": ${snippet}`)
    }
    if (CONFIGURED_TAG && !/[?&]tag=/.test(href)) {
      fail('missing-tag', rel, `Amazon link has no tag= parameter: ${href.slice(0, 120)}`)
    } else if (CONFIGURED_TAG && !href.includes(`tag=${CONFIGURED_TAG}`)) {
      fail('wrong-tag', rel, `Amazon link has wrong affiliate tag (expected ${CONFIGURED_TAG}): ${href.slice(0, 120)}`)
    }
  }

  // ── 6. Hardcoded prices (Amazon Associates ToS) ──────────────────────────
  // Only check article pages; only check the article-page__content div (prose body).
  if (raw.includes('article-page__content')) {
    const proseRe = /class="article-page__content"[^>]*>([\s\S]*?)<\/div>/i
    const proseMatch = proseRe.exec(raw)
    if (proseMatch) {
      const proseText = proseMatch[1].replace(/<script[\s\S]*?<\/script>/gi, '')
      const priceRe = /\$\s*\d[\d,]*(?:\s*[-–]\s*\$?\s*\d[\d,]*)?/g
      const priceMatches = proseText.match(priceRe)
      if (priceMatches && priceMatches.length >= 3) {
        warnings.push(`  WARN [hardcoded-price] ${rel}\n       ${priceMatches.length} dollar amount(s) in prose: ${[...new Set(priceMatches)].slice(0, 5).join(', ')}`)
      }
    }
  }

  // ── 7. Refusal-pattern content ───────────────────────────────────────────
  // AI-generated articles should never contain these phrases.
  if (raw.includes('article-page__content')) {
    const contentIdx = raw.indexOf('class="article-page__content"')
    if (contentIdx !== -1) {
      const contentSlice = raw.slice(contentIdx, contentIdx + 100_000).toLowerCase()
      for (const pattern of REFUSAL_PATTERNS) {
        if (pattern.test(contentSlice)) {
          fail('refusal-content', rel, `AI refusal pattern found in article content: "${pattern.source}"`)
          break
        }
      }
    }
  }

  // ── 8. CTA density ───────────────────────────────────────────────────────
  // Buyer-intent articles (buyer_guide, roundup, comparison) must have CTAs.
  // FAIL if 0 CTAs; WARN if density falls below 1.5 per 1000 words.
  if (raw.includes('article-page__content')) {
    const slug = rel.replace(/\/index\.html$/, '')
    const articleType = ARTICLE_TYPE_MAP.get(slug)

    if (articleType && BUYER_ARTICLE_TYPES.has(articleType)) {
      const ctaCount = (raw.match(/class="btn btn--amazon"/g) ?? []).length +
                       (raw.match(/class="btn btn--primary"/g) ?? []).length

      if (ctaCount === 0) {
        fail('cta-density', rel, `${articleType} article has 0 CTAs — buyer articles must have at least 1`)
      } else {
        const contentIdx = raw.indexOf('class="article-page__content"')
        if (contentIdx !== -1) {
          const contentSlice = raw.slice(contentIdx, contentIdx + 100_000)
          const textContent = contentSlice.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim()
          const wordCount = textContent.split(' ').filter(w => w.length > 1).length
          if (wordCount > 500) {
            const density = (ctaCount / wordCount) * 1000
            if (density < 1.5) {
              warnings.push(`  WARN [cta-density] ${rel}\n       ${ctaCount} CTA(s) / ${wordCount} words = ${density.toFixed(1)}/1000 (min 1.5)`)
            }
          }
        }
      }
    }
  }

  // ── 9. Sentinel Amazon image hashes ─────────────────────────────────────
  const sentinelImgRe = /m\.media-amazon\.com\/images\/I\/(7[01]Q[0-9Q]{6,}L)[^"']*/g
  let siMatch
  while ((siMatch = sentinelImgRe.exec(raw)) !== null) {
    fail('sentinel-image', rel, `Placeholder Amazon image hash detected: ${siMatch[1]}`)
  }

  // ── 10. Placeholder ASINs ─────────────────────────────────────────────────
  const placeholderAsinRe = /VERIFY-|TODO-|PLACEHOLDER-/g
  if (placeholderAsinRe.test(raw)) {
    fail('placeholder-asin', rel, `Placeholder ASIN value found in rendered HTML`)
  }

  // ── 11. Duplicate consecutive breadcrumb hrefs ────────────────────────────
  const breadcrumbRe = /<nav[^>]*breadcrumb[^>]*>([\s\S]*?)<\/nav>/i
  const bcMatch = breadcrumbRe.exec(raw)
  if (bcMatch) {
    const hrefs = [...bcMatch[1].matchAll(/href="([^"]+)"/g)].map(m => m[1])
    for (let i = 1; i < hrefs.length; i++) {
      if (hrefs[i] === hrefs[i - 1]) {
        fail('duplicate-breadcrumb', rel, `Duplicate consecutive breadcrumb href: "${hrefs[i]}"`)
      }
    }
  }

  // ── 12. Doubled brand names in product card names ─────────────────────────
  // Catches "Perky-Pet Perky-Pet", "EGO Power+ EGO Power+" in product card titles.
  // WARN only — product name data quality, not a revenue-impacting bug.
  const cardNameRe = /class="product-card__name"[^>]*>([\s\S]*?)<\/h3>/gi
  let cnMatch
  while ((cnMatch = cardNameRe.exec(raw)) !== null) {
    const text = cnMatch[1].replace(/<[^>]+>/g, '').trim()
    if (/(\b[\w-]{2,}\b)\s+\1\b/i.test(text)) {
      warnings.push(`  WARN [doubled-brand] ${rel}\n       Product name contains repeated word: "${text.slice(0, 100)}"`)
    }
  }

  // ── 13.5 Duplicate product-card rationale (Fix 3 — recycled pros/cons) ────
  // Same pros/cons line repeated across ≥2 product cards in one article is the
  // "Well-reviewed X option" boilerplate signature — a soft prompt rule drifts
  // (see article title-builder audit); this is a hard, exact-string check.
  const cardBlockRe = /class="product-card__pros-cons"[^>]*>([\s\S]*?)<\/div>\s*<\/div>/gi
  const seenLines = new Map() // line text -> count
  let cardBlockMatch
  while ((cardBlockMatch = cardBlockRe.exec(raw)) !== null) {
    const liRe = /<li>([\s\S]*?)<\/li>/gi
    let liMatch
    const linesInThisCard = new Set()
    while ((liMatch = liRe.exec(cardBlockMatch[1])) !== null) {
      const text = liMatch[1].replace(/<[^>]+>/g, '').trim()
      if (text) linesInThisCard.add(text)
    }
    for (const text of linesInThisCard) {
      seenLines.set(text, (seenLines.get(text) ?? 0) + 1)
    }
  }
  for (const [text, count] of seenLines) {
    if (count > 1) {
      fail('duplicate-card-rationale', rel,
        `Pros/cons line "${text.slice(0, 80)}" appears on ${count} different product cards in this article`)
    }
  }

  // ── 13.6 Blank comparison-table cells (Fix 3) ─────────────────────────────
  // ComparisonTable.astro renders nothing when a product's price_band/pros/cons
  // value is missing — a silently blank <td>, not a build error. Catch it here.
  const compTableRe = /<table class="comparison-table">([\s\S]*?)<\/table>/i
  const compMatch = compTableRe.exec(raw)
  if (compMatch) {
    const rowRe = /<tbody>([\s\S]*?)<\/tbody>/i
    const bodyMatch = rowRe.exec(compMatch[1])
    if (bodyMatch) {
      const trRe = /<tr>([\s\S]*?)<\/tr>/gi
      let trMatch
      let rowIdx = 0
      while ((trMatch = trRe.exec(bodyMatch[1])) !== null) {
        rowIdx++
        const tdRe = /<td>([\s\S]*?)<\/td>/gi
        let tdMatch
        let colIdx = 0
        const cells = []
        while ((tdMatch = tdRe.exec(trMatch[1])) !== null) {
          colIdx++
          cells.push(tdMatch[1])
        }
        // Last <td> is the Buy column — legitimately renders "—" for no affiliate_url,
        // not a blank-attribute bug. Only check the attribute columns before it.
        for (let i = 0; i < cells.length - 1; i++) {
          const text = cells[i].replace(/<[^>]+>/g, '').trim()
          if (text === '') {
            fail('blank-comparison-cell', rel,
              `Comparison table row ${rowIdx}, column ${i + 1} is blank — missing price_band/pros/cons value on this product`)
          }
        }
      }
    }
  }

  // ── 13.7 Head-term / spoke internal linking (Fix 4) ───────────────────────
  // HEAD articles must link to every spoke that names them as parent_head;
  // spokes must link back to their parent_head. Structural presence only —
  // ROLE_MAP/PARENT_HEAD_MAP populated from source in the pre-flight block below.
  {
    const slug = rel.replace(/\/index\.html$/, '')
    const role = ROLE_MAP.get(slug)
    if (role === 'HEAD') {
      const expectedSpokes = SPOKES_BY_HEAD.get(slug) ?? []
      for (const spokeSlug of expectedSpokes) {
        if (!raw.includes(`href="/${spokeSlug}/"`) && !raw.includes(`href="/${spokeSlug}"`)) {
          fail('orphaned-spoke-link', rel,
            `HEAD article does not link to its spoke "${spokeSlug}" (declared via that spoke's parent_head)`)
        }
      }
    } else if (role === 'spoke') {
      const parentHead = PARENT_HEAD_MAP.get(slug)
      if (parentHead && !raw.includes(`href="/${parentHead}/"`) && !raw.includes(`href="/${parentHead}"`)) {
        fail('orphaned-parent-link', rel,
          `Spoke article does not link back to its parent_head "${parentHead}"`)
      }
    }
  }

  // ── 13.8 §255 testing-language sweep ──────────────────────────────────────
  // Hard ban: FTC §255 prohibits testing claims the persona cannot substantiate.
  // Checks title, meta description, og/twitter fields, h1, JSON-LD text fields,
  // and img alt attributes. A match in any field is a FAIL.
  //
  // Verb list (order: most specific multi-word first, then single-word fallbacks):
  const S255_PATTERNS = [
    /\bwe\s+tested\b/i,
    /\bi\s+tested\b/i,
    /\bwe\s+used\b/i,
    /\bi\s+used\b/i,
    /\bin\s+our\s+testing\b/i,
    /\bin\s+my\s+testing\b/i,
    /\bhands[- ]on\b/i,
    /\broad[- ]?test(ed|ing)?\b/i,
    /\bfield[- ]?test(ed|ing)?\b/i,
    /\bput\s+through\b/i,
    /\bslept\s+with\b/i,
    /\bslept\s+in\b/i,
    /\btested\b/i,
    /\btesting\b/i,
  ]

  // Collect targeted fields (metadata + structured data only — body prose handled elsewhere).
  const s255Fields = []

  // <title>
  const titleM255 = raw.match(/<title>([^<]+)<\/title>/i)
  if (titleM255) s255Fields.push({ field: 'title', text: titleM255[1] })

  // <meta name/property="..."> — both attr orderings
  const metaPat = /<meta\b([^>]+)>/gi
  let metaTag
  while ((metaTag = metaPat.exec(raw)) !== null) {
    const attrs = metaTag[1]
    const nameM = attrs.match(/(?:name|property)="([^"]+)"/i)
    const contM = attrs.match(/content="([^"]+)"/i)
    if (!nameM || !contM) continue
    const prop = nameM[1].toLowerCase()
    if (['description','og:title','og:description','twitter:title','twitter:description'].includes(prop)) {
      s255Fields.push({ field: prop, text: contM[1] })
    }
  }

  // <h1> (strip inner tags)
  const h1M255 = raw.match(/<h1[^>]*>([\s\S]*?)<\/h1>/i)
  if (h1M255) s255Fields.push({ field: 'h1', text: h1M255[1].replace(/<[^>]+>/g, '').trim() })

  // JSON-LD: headline, description, name at the top level of each schema block
  const jldPat = /<script[^>]+type="application\/ld\+json"[^>]*>([\s\S]*?)<\/script>/gi
  let jldTag
  while ((jldTag = jldPat.exec(raw)) !== null) {
    try {
      const obj = JSON.parse(jldTag[1])
      for (const key of ['headline', 'description', 'name']) {
        if (typeof obj[key] === 'string') s255Fields.push({ field: `json-ld:${key}`, text: obj[key] })
      }
    } catch {}
  }

  // img alt attributes
  const altPat = /<img\b[^>]+\balt="([^"]+)"/gi
  let altTag
  while ((altTag = altPat.exec(raw)) !== null) {
    s255Fields.push({ field: 'img-alt', text: altTag[1] })
  }

  // Check each field against every pattern; report first match per field
  for (const { field, text } of s255Fields) {
    for (const pat of S255_PATTERNS) {
      const m = pat.exec(text)
      if (m) {
        fail('255-testing-language', rel,
          `§255 violation in [${field}]: matched "${m[0]}" — value: "${text.slice(0, 120)}"`)
        break  // one FAIL per field is enough
      }
    }
  }
}

function walk(dir) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name)
    if (entry.isDirectory()) walk(full)
    else if (entry.name.endsWith('.html')) checkFile(full)
  }
}

// Pre-cache all files in dist/ so checkFile can do O(1) image lookups.
// Populated just before walk(DIST) is called at the bottom of this script.
const DIST_FILE_SET = new Set()
function buildDistFileSet(dir) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name)
    if (entry.isDirectory()) buildDistFileSet(full)
    else DIST_FILE_SET.add(full)
  }
}

// ── Pre-flight: IndexNow key file check ───────────────────────────────────
const INDEXNOW_KEY = process.env.INDEXNOW_KEY
const isCloudflareProduction =
  process.env.CF_PAGES === '1' && process.env.CF_PAGES_BRANCH === 'main'

if (INDEXNOW_KEY) {
  const keyFilePath = join(DIST, `${INDEXNOW_KEY}.txt`)
  if (!existsSync(keyFilePath)) {
    fail('indexnow-key-missing', `dist/${INDEXNOW_KEY}.txt`, 'Key file not found in dist — ensure public/<key>.txt is committed to the repo')
  } else {
    const keyFileContents = readFileSync(keyFilePath, 'utf8').replace(/\n$/, '')
    if (keyFileContents !== INDEXNOW_KEY) {
      fail('indexnow-key-mismatch', `dist/${INDEXNOW_KEY}.txt`, `Key file contents "${keyFileContents}" do not match INDEXNOW_KEY env var`)
    }
  }
} else if (isCloudflareProduction) {
  warnings.push('  WARN [indexnow-key] INDEXNOW_KEY not set — IndexNow submissions disabled for this clone.\n       Set INDEXNOW_KEY in Cloudflare Pages → Settings → Environment Variables.')
}

// ── Pre-flight: source file checks (before scanning dist/) ────────────────
const PRODUCTS_YAML = resolve(SITE_ROOT, 'content/products/products.yaml')
if (existsSync(PRODUCTS_YAML)) {
  const productsRaw = readFileSync(PRODUCTS_YAML, 'utf8')
  const productsFiltered = productsRaw.split('\n').filter(l => !l.includes('source_url:')).join('\n')
  if (/VERIFY-|TODO-|PLACEHOLDER-/.test(productsFiltered)) {
    fail('placeholder-asin-source', 'content/products/products.yaml', 'Placeholder ASIN (VERIFY-/TODO-/PLACEHOLDER-) found in source — fix before building')
  }
  if (/7[01]Q[0-9Q]{6,}[A-Z0-9]L/.test(productsRaw)) {
    fail('sentinel-image-source', 'content/products/products.yaml', 'Sentinel Amazon image hash found in source — fix before building')
  }
}

// ── Pre-flight: article source checks + build ARTICLE_TYPE_MAP ───────────
const ARTICLES_DIR = resolve(SITE_ROOT, 'content/articles')
if (existsSync(ARTICLES_DIR)) {
  function walkArticleSource(dir) {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const full = join(dir, entry.name)
      if (entry.isDirectory()) walkArticleSource(full)
      else if (entry.name.endsWith('.md') || entry.name.endsWith('.mdx')) {
        const src = readFileSync(full, 'utf8')
        const rel = 'content/articles/' + entry.name
        // Strip frontmatter before checking body
        const body = src.replace(/^---[\s\S]*?---\n/, '')
        if (/https?:\/\/(?:www\.)?amazon\.com\/dp\/[A-Z0-9]{10}/.test(body)) {
          fail('hardcoded-asin-source', rel, 'Hardcoded Amazon ASIN URL found in article body — use <ProductLink slug="..."> instead')
        }
        if (/\?tag=[a-z0-9-]+-\d{2}/.test(body)) {
          fail('hardcoded-affiliate-tag-source', rel, 'Hardcoded affiliate tag (?tag=...) found in article body — use <ProductLink> which injects the correct tag at build time')
        }
        // Populate ARTICLE_TYPE_MAP for use in CTA density and comparison checks
        const slugMatch = src.match(/^slug:\s*["']?([^"'\s]+)["']?/m)
        const typeMatch = src.match(/^type:\s*["']?([^"'\s]+)["']?/m)
        if (slugMatch && typeMatch) ARTICLE_TYPE_MAP.set(slugMatch[1], typeMatch[1])

        // Populate role/parent_head/hub/keyword maps (Fix 1 / Fix 2 / Fix 4)
        const roleMatch = src.match(/^role:\s*["']?([^"'\s]+)["']?/m)
        const parentHeadMatch = src.match(/^parent_head:\s*["']?([^"'\s]+)["']?/m)
        const hubMatch = src.match(/^hub:\s*["']?([^"'\s]+)["']?/m)
        const keywordMatch = src.match(/^target_keyword:\s*["']?([^"'\n]+?)["']?\s*$/m)
        const axisMatch = src.match(/^axis:\s*["']?([^"'\s]+)["']?/m)
        if (slugMatch && roleMatch) ROLE_MAP.set(slugMatch[1], roleMatch[1])
        if (slugMatch && parentHeadMatch) PARENT_HEAD_MAP.set(slugMatch[1], parentHeadMatch[1])
        if (slugMatch && hubMatch) HUB_MAP.set(slugMatch[1], hubMatch[1])
        if (slugMatch && keywordMatch) KEYWORD_MAP.set(slugMatch[1], keywordMatch[1])
        if (slugMatch && axisMatch) AXIS_MAP.set(slugMatch[1], axisMatch[1])
      }
    }
  }
  walkArticleSource(ARTICLES_DIR)
}

// Build SPOKES_BY_HEAD from PARENT_HEAD_MAP now that both maps are populated.
for (const [spokeSlug, headSlug] of PARENT_HEAD_MAP) {
  if (!SPOKES_BY_HEAD.has(headSlug)) SPOKES_BY_HEAD.set(headSlug, [])
  SPOKES_BY_HEAD.get(headSlug).push(spokeSlug)
}

// ── Pre-flight: head-term enforcement (Fix 1) ─────────────────────────────
// Every hub must have ≥1 published article with role: HEAD, and that article's
// slug must not equal the hub's own slug (a HEAD article is a dedicated page,
// distinct from the [hub].astro index — see head-term coverage audit).
const NAV_PATH = resolve(SITE_ROOT, 'config/navigation.yaml')
let allHubSlugs = []
if (existsSync(NAV_PATH)) {
  const nav = yaml.load(readFileSync(NAV_PATH, 'utf8'))
  for (const cat of nav?.categories ?? []) {
    for (const hub of cat.hubs ?? []) allHubSlugs.push(hub.slug)
  }
}
if (allHubSlugs.length > 0 && ROLE_MAP.size > 0) {
  for (const hubSlug of allHubSlugs) {
    const headsInHub = [...ROLE_MAP.entries()]
      .filter(([slug, role]) => role === 'HEAD' && HUB_MAP.get(slug) === hubSlug)
      .map(([slug]) => slug)
    if (headsInHub.length === 0) {
      fail('missing-head-term', `config/navigation.yaml`,
        `Hub "${hubSlug}" has no article with role: HEAD — the hub index page is the only thing targeting this term`)
      continue
    }
    for (const headSlug of headsInHub) {
      if (headSlug === hubSlug) {
        fail('head-slug-collides-with-hub', `content/articles/`,
          `HEAD article "${headSlug}" has the same slug as its hub "${hubSlug}" — route collision with [hub].astro`)
      }
    }
  }
}

// ── Pre-flight: orphan check (Fix 4) ──────────────────────────────────────
// Every spoke's parent_head must resolve to a real, same-hub HEAD article.
for (const [spokeSlug, headSlug] of PARENT_HEAD_MAP) {
  if (!ROLE_MAP.has(headSlug)) {
    fail('orphaned-spoke', `content/articles/`,
      `Spoke "${spokeSlug}" declares parent_head "${headSlug}", which does not exist as an article`)
  } else if (ROLE_MAP.get(headSlug) !== 'HEAD') {
    fail('orphaned-spoke', `content/articles/`,
      `Spoke "${spokeSlug}" declares parent_head "${headSlug}", which is not a HEAD article (role: ${ROLE_MAP.get(headSlug)})`)
  } else if (HUB_MAP.get(spokeSlug) && HUB_MAP.get(headSlug) && HUB_MAP.get(spokeSlug) !== HUB_MAP.get(headSlug)) {
    fail('orphaned-spoke', `content/articles/`,
      `Spoke "${spokeSlug}" (hub "${HUB_MAP.get(spokeSlug)}") declares parent_head "${headSlug}" from a different hub ("${HUB_MAP.get(headSlug)}")`)
  }
}
for (const [slug, role] of ROLE_MAP) {
  if (role === 'HEAD' && (SPOKES_BY_HEAD.get(slug) ?? []).length === 0) {
    warnings.push(`  WARN [head-with-no-spokes] content/articles/${slug}.md\n       role: HEAD but no spoke declares it as parent_head — nothing links to it internally`)
  }
}

// ── Pre-flight: semantic keyword-variant collision (Fix 2) ────────────────
// Upgrades xlsx-to-pipeline.mjs's B45 dedup with singularization and repeated-
// token collapse, and — unlike B45's silent status:"dupe" skip at import time —
// hard-fails the build and reports the exact colliding pair.
const MODIFIER_WORDS = new Set([
  'best', 'good', 'great', 'top', 'worst',
  'affordable', 'cheap', 'budget', 'inexpensive', 'expensive',
  'premium', 'basic', 'simple', 'easy', 'a', 'an', 'the',
])
// Price-tier words are a real editorial axis, not noise -- "cheap chicken coop"
// and "chicken coop" can both be intentional, separate spokes when the site is
// deliberately covering that axis. The modifier list itself does NOT get
// weakened (it still strips these for every non-exempt article); instead a
// spoke opts out per-article via `axis: price` in its frontmatter.
const PRICE_WORDS = new Set(['affordable', 'cheap', 'budget', 'inexpensive', 'expensive', 'premium'])
function semanticSignature(keyword, axis) {
  const stripSet = axis === 'price'
    ? new Set([...MODIFIER_WORDS].filter(w => !PRICE_WORDS.has(w)))
    : MODIFIER_WORDS
  const tokens = keyword
    .toLowerCase()
    .replace(/['']/g, '')
    .replace(/[^a-z0-9\s]+/g, ' ')
    .split(/\s+/)
    .filter(t => t && !stripSet.has(t))
    .map(t => (t.length > 3 && t.endsWith('s') ? t.slice(0, -1) : t)) // singularize
  return [...new Set(tokens)].sort().join(' ') // Set collapses repeated tokens
}
if (KEYWORD_MAP.size > 0) {
  const seenSignatures = new Map() // `${hub}::${signature}` -> slug
  for (const [slug, keyword] of KEYWORD_MAP) {
    const hub = HUB_MAP.get(slug) ?? ''
    const sig = semanticSignature(keyword, AXIS_MAP.get(slug))
    const key = `${hub}::${sig}`
    if (seenSignatures.has(key)) {
      fail('keyword-variant-collision', `content/articles/`,
        `"${slug}" (keyword: "${keyword}") and "${seenSignatures.get(key)}" normalise to the same signature "${sig}" in hub "${hub}" — reword one or merge`)
    } else {
      seenSignatures.set(key, slug)
    }
  }
}

// ── Pre-flight: products with unusable ASIN and no buy_url fallback ───────
const SENTINEL_ASINS = new Set(['NOT_ON_AMAZON', 'NOT_FOUND', 'VERIFY'])
try {
  const productsRaw2 = readFileSync(resolve(SITE_ROOT, 'content/products/products.yaml'), 'utf8')
  const products = yaml.load(productsRaw2)
  const missing = []
  for (const [id, p] of Object.entries(products)) {
    const asin = p.amazon_asin ?? p.asin ?? null
    if (asin && SENTINEL_ASINS.has(asin) && !p.buy_url) {
      missing.push(id)
    }
  }
  if (missing.length > 0) {
    warnings.push(`  WARN [no-buy-url-fallback] ${missing.length} product(s) have unusable ASIN and no buy_url — CTA silently suppressed:\n       ${missing.slice(0, 5).join(', ')}${missing.length > 5 ? ` … +${missing.length - 5} more` : ''}`)
  }
} catch (e) {
  // products.yaml may not exist on all sites
}

// ── Pre-flight: comparison articles must have ≥2 product-card blocks ──────
for (const [slug, type] of ARTICLE_TYPE_MAP) {
  if (type !== 'comparison') continue
  const htmlPath = join(DIST, slug, 'index.html')
  if (!existsSync(htmlPath)) continue
  const html = readFileSync(htmlPath, 'utf8')
  const cardCount = (html.match(/class="product-card"/g) ?? []).length
  if (cardCount < 2) {
    fail('comparison-product-cards', `${slug}/index.html`, `Comparison article has ${cardCount} product-card block(s) — minimum 2 required`)
  }
}

// ── Pre-flight: article count contract ────────────────────────────────────
// Every article in content/articles/ must have a corresponding dist/ directory.
// One-directional check: dist/ can have extra directories (hub pages, static pages).
if (ARTICLE_TYPE_MAP.size > 0 && existsSync(DIST)) {
  const missingFromDist = []
  for (const slug of ARTICLE_TYPE_MAP.keys()) {
    if (!existsSync(join(DIST, slug, 'index.html'))) {
      missingFromDist.push(slug)
    }
  }
  if (missingFromDist.length > 0) {
    fail('article-count-mismatch', 'content/articles/',
      `${missingFromDist.length} article(s) in content/ have no dist/ output: ${missingFromDist.slice(0, 3).join(', ')}${missingFromDist.length > 3 ? ` …+${missingFromDist.length - 3} more` : ''}`)
  }
}

// ── Run ───────────────────────────────────────────────────────────────────
console.log(`\nValidating build output in ${DIST} …\n`)
if (existsSync(DIST)) buildDistFileSet(DIST)
walk(DIST)

if (warnings.length > 0) {
  console.warn(`⚠ ${warnings.length} warning(s) — these are non-blocking but should be fixed:\n`)
  for (const w of warnings) console.warn(w)
  console.warn()
}

if (failures === 0) {
  console.log(warnings.length
    ? `✓ Build validation passed with warnings (see above).\n`
    : `✓ Build validation passed — no issues found.\n`)
  process.exit(0)
} else {
  console.error(`✗ Build validation failed — ${failures} issue(s):\n`)
  for (const e of errors) console.error(e)
  console.error(`\nFix the issues above and rebuild.\n`)
  process.exit(1)
}
