/**
 * Post-build validator — fails the build if critical issues are found in dist/.
 * Checks: empty pages, missing images, empty product cards, unreplaced template tokens,
 * untagged affiliate links, hardcoded prices, refusal-pattern content, CTA density,
 * sentinel image hashes, placeholder ASINs, duplicate breadcrumbs, doubled brand names.
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
      }
    }
  }
  walkArticleSource(ARTICLES_DIR)
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
