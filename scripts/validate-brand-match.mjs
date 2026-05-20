#!/usr/bin/env node
/**
 * validate-brand-match.mjs
 *
 * Audits a site's pipeline.json articles to verify that when a brand name
 * appears in the article's headline keyword, at least one assigned product
 * carries that brand in products.yaml.
 *
 * Classification:
 *   PASS    – headline brand is present in ≥1 assigned product
 *   PARTIAL – exactly 1 product matches (ambiguous, flag for review)
 *   FAIL    – headline brand present in keyword but 0 products match
 *   NO_BRAND – keyword contains no known brand (skipped in brand check)
 *
 * Exit codes:
 *   0 – no FAILs (PARTIALs are warnings only)
 *   1 – ≥1 FAIL article found
 *   2 – usage/config error
 *
 * Usage:
 *   node scripts/validate-brand-match.mjs --site northwoods-overland
 *   node scripts/validate-brand-match.mjs --site northwoods-overland --verbose
 *   node scripts/validate-brand-match.mjs --site northwoods-overland --report-only
 */

import { readFileSync, writeFileSync, existsSync, readdirSync } from 'node:fs'
import { resolve, join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const PLATFORM_ROOT = resolve(__dirname, '..')
const PORTFOLIO_PATH = join(PLATFORM_ROOT, 'portfolio.yaml')

// ---------------------------------------------------------------------------
// Arg parsing
// ---------------------------------------------------------------------------

const args = process.argv.slice(2)
const siteArg  = args[args.indexOf('--site') + 1]
const verbose  = args.includes('--verbose')
const reportOnly = args.includes('--report-only')  // skip exit-code enforcement

if (!siteArg) {
  console.error('Usage: node scripts/validate-brand-match.mjs --site <site-slug>')
  process.exit(2)
}

// ---------------------------------------------------------------------------
// Locate site root via portfolio.yaml
// ---------------------------------------------------------------------------

function parseYamlSimple(text) {
  // Minimal YAML parser sufficient for flat-ish portfolio.yaml and site.config.yaml.
  // Only handles the structures we know exist in those files.
  const lines = text.split('\n')
  const result = {}
  let currentKey = null
  let listTarget = null

  for (const raw of lines) {
    const line = raw.replace(/\s*#.*$/, '') // strip inline comments
    if (!line.trim()) continue

    const listMatch = line.match(/^(\s*)- (.+)$/)
    if (listMatch) {
      const value = listMatch[2].trim().replace(/^['"]|['"]$/g, '')
      if (Array.isArray(listTarget)) listTarget.push(value)
      continue
    }

    const kvMatch = line.match(/^(\s*)([^:]+):\s*(.*)$/)
    if (!kvMatch) continue
    const indent = kvMatch[1].length
    const key   = kvMatch[2].trim()
    let value   = kvMatch[3].trim().replace(/^['"]|['"]$/g, '')

    if (indent === 0) {
      currentKey = key
      result[key] = value || {}
      listTarget = null
    } else if (indent === 2 && currentKey) {
      if (value === '') {
        if (!result[currentKey] || typeof result[currentKey] !== 'object') result[currentKey] = {}
        listTarget = null
      } else {
        if (typeof result[currentKey] !== 'object') result[currentKey] = {}
        result[currentKey][key] = value === 'null' ? null : value
      }
    }
  }
  return result
}

function findSiteRoot(slug) {
  // Try common locations relative to PLATFORM_ROOT parent
  const parentDir = resolve(PLATFORM_ROOT, '..')
  const candidates = [
    join(parentDir, slug),
    join(parentDir, slug.replace(/-/g, '_')),
    resolve(process.env.HOME || '~', slug),
  ]
  for (const p of candidates) {
    if (existsSync(join(p, 'data', 'pipeline.json'))) return p
    if (existsSync(join(p, 'content', 'products', 'products.yaml'))) return p
  }
  // Fallback: read portfolio.yaml for hints
  if (existsSync(PORTFOLIO_PATH)) {
    // portfolio.yaml doesn't store site root paths, but we can infer from cloudflare_project
    // Just throw — better error than silent wrong result
  }
  return null
}

const siteRoot = findSiteRoot(siteArg)
if (!siteRoot) {
  console.error(`[ERROR] Could not locate site root for "${siteArg}". Expected at ~/${siteArg}/`)
  process.exit(2)
}

const pipelinePath = join(siteRoot, 'data', 'pipeline.json')
const productsPath = join(siteRoot, 'content', 'products', 'products.yaml')

if (!existsSync(pipelinePath)) { console.error(`[ERROR] pipeline.json not found: ${pipelinePath}`); process.exit(2) }
if (!existsSync(productsPath)) { console.error(`[ERROR] products.yaml not found: ${productsPath}`); process.exit(2) }

// ---------------------------------------------------------------------------
// Load pipeline.json
// ---------------------------------------------------------------------------

const pipelineRaw = JSON.parse(readFileSync(pipelinePath, 'utf8'))
const articles = Array.isArray(pipelineRaw) ? pipelineRaw : (pipelineRaw.articles ?? [])

// ---------------------------------------------------------------------------
// Load products.yaml — mapping of {product_id: {brand, hub, ...}}
// ---------------------------------------------------------------------------

function parseProductsYaml(text) {
  // products.yaml is a top-level mapping: product_id: { brand: X, hub: Y, ... }
  const map = {}
  let currentId = null
  let currentObj = {}

  for (const raw of text.split('\n')) {
    if (!raw.trim() || raw.trim().startsWith('#')) continue

    // Top-level key (no leading spaces, ends with colon)
    const topMatch = raw.match(/^([a-z0-9][a-z0-9_-]*):\s*$/)
    if (topMatch) {
      if (currentId) map[currentId] = currentObj
      currentId = topMatch[1]
      currentObj = {}
      continue
    }

    // Nested field (2-space indent)
    if (currentId && raw.startsWith('  ')) {
      const kvMatch = raw.match(/^\s+([^:]+):\s*(.*)$/)
      if (kvMatch) {
        const key = kvMatch[1].trim()
        let val = kvMatch[2].trim().replace(/^['"]|['"]$/g, '')
        if (val === 'null' || val === '') val = null
        currentObj[key] = val
      }
    }
  }
  if (currentId) map[currentId] = currentObj
  return map
}

const products = parseProductsYaml(readFileSync(productsPath, 'utf8'))

// Collect every distinct brand value (case-insensitive) for brand-in-keyword detection
const allBrands = new Set()
for (const info of Object.values(products)) {
  if (info && info.brand) allBrands.add(info.brand.toLowerCase())
}

// ---------------------------------------------------------------------------
// Brand detection helpers
// ---------------------------------------------------------------------------

// Canonical brand list — brands worth checking in keyword headlines.
// Must be kept up-to-date as catalog grows.
const KNOWN_BRANDS = [
  // rooftop tents
  'iKamper', 'Roofnest', 'Yakima', 'Thule', 'Napier', 'ARB', 'CVT',
  // roof racks
  'Prinsu', 'Sherpa', 'Rhino-Rack', 'Front Runner', 'Hooke Road',
  // recovery
  'Maxtrax', 'TRED', 'ARB', 'Hi-Lift',
  // drawer systems
  'Decked', 'DECKED',
  // power
  'Anker', 'Goal Zero', 'EcoFlow', 'Jackery', 'REDARC',
  // lighting
  'RIGID', 'Baja Designs', 'KC HiLiTES', 'Warn',
]

// Build word-boundary regex per brand (case-insensitive)
const brandPatterns = KNOWN_BRANDS.map(b => ({
  brand: b,
  re: new RegExp(`\\b${b.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, 'i'),
}))

function extractHeadlineBrands(keyword) {
  if (!keyword) return []
  const found = []
  for (const { brand, re } of brandPatterns) {
    if (re.test(keyword)) {
      const canonical = brand.toLowerCase()
      if (!found.some(f => f.toLowerCase() === canonical)) found.push(brand)
    }
  }
  return found
}

function productMatchesBrand(productId, brandName) {
  const info = products[productId]
  if (!info || !info.brand) return false
  // Bidirectional substring match handles brand name variations:
  // "Sherpa Equipment Co" matches keyword brand "Sherpa"
  // "EcoFlow Power Inc" matches keyword brand "EcoFlow"
  const productBrand = info.brand.toLowerCase()
  const keywordBrand = brandName.toLowerCase()
  return productBrand === keywordBrand
    || productBrand.includes(keywordBrand)
    || keywordBrand.includes(productBrand)
}

// ---------------------------------------------------------------------------
// Load published article frontmatter product assignments (if articles exist)
// Published articles are the source of truth post-generation; pipeline.json
// is the source of truth pre-generation (Point 12.5 gate).
// ---------------------------------------------------------------------------

const articlesDir = join(siteRoot, 'content', 'articles')
const publishedProducts = new Map()  // slug → [productId, ...]

if (existsSync(articlesDir)) {
  const mdFiles = readdirSync(articlesDir).filter(f => f.endsWith('.md'))
  for (const filename of mdFiles) {
    const slug = filename.replace(/\.md$/, '')
    const text = readFileSync(join(articlesDir, filename), 'utf8')
    if (!text.startsWith('---\n')) continue
    const end = text.indexOf('\n---\n', 4)
    if (end === -1) continue
    const fmText = text.slice(4, end)
    // Parse products array from frontmatter (YAML-like, minimal)
    const pids = []
    let inProducts = false
    for (const line of fmText.split('\n')) {
      if (/^products:/.test(line)) { inProducts = true; continue }
      if (inProducts) {
        if (/^[a-z]/.test(line) && !/^\s*-/.test(line)) { inProducts = false; continue }
        const pidMatch = line.match(/^\s*-?\s*id:\s*['"]?([a-z0-9-]+)['"]?/)
        if (pidMatch) pids.push(pidMatch[1])
        // Also handle bare string list: "  - product-id"
        const bareMatch = line.match(/^\s*-\s+([a-z0-9-]+)\s*$/)
        if (bareMatch) pids.push(bareMatch[1])
      }
    }
    if (pids.length > 0) publishedProducts.set(slug, pids)
  }
}

// ---------------------------------------------------------------------------
// Classify each article
// ---------------------------------------------------------------------------

const results = {
  PASS: [],
  PARTIAL: [],
  FAIL: [],
  NO_BRAND: [],
  SKIPPED: [],
}

const usingPublished = publishedProducts.size > 0

for (const article of articles) {
  const slug    = article.slug ?? '(no-slug)'
  const keyword = article.keyword ?? article.target_keyword ?? ''
  const hub     = article.hub ?? ''
  const status  = article.status ?? ''

  if (status === 'removed' || status === 'deleted') {
    results.SKIPPED.push({ slug, keyword, reason: 'removed' })
    continue
  }

  const headlineBrands = extractHeadlineBrands(keyword)
  if (headlineBrands.length === 0) {
    results.NO_BRAND.push({ slug, keyword, hub })
    continue
  }

  // Prefer published article frontmatter over pipeline.json for product IDs
  // (pipeline.json is pre-generation planning; articles may have been reseeded since)
  let productIds
  if (usingPublished && publishedProducts.has(slug)) {
    productIds = publishedProducts.get(slug)
  } else {
    productIds = (article.products ?? []).map(p =>
      typeof p === 'string' ? p : (p.id ?? '')
    ).filter(Boolean)
  }

  // For each headline brand, check how many products match
  const brandResults = headlineBrands.map(brand => {
    const matches = productIds.filter(pid => productMatchesBrand(pid, brand))
    return { brand, total: productIds.length, matches: matches.length, matchedIds: matches }
  })

  // Overall classification: PASS if any brand has ≥2 matches; PARTIAL if any has exactly 1; FAIL if 0
  const maxMatches = Math.max(...brandResults.map(r => r.matches))

  const entry = { slug, keyword, hub, headlineBrands, productIds, brandResults }

  if (maxMatches >= 2) {
    results.PASS.push(entry)
  } else if (maxMatches === 1) {
    results.PARTIAL.push(entry)
  } else {
    results.FAIL.push(entry)
  }
}

// ---------------------------------------------------------------------------
// Report generation
// ---------------------------------------------------------------------------

const total = articles.filter(a => (a.status ?? '') !== 'removed').length
const branded = results.PASS.length + results.PARTIAL.length + results.FAIL.length
const date = new Date().toISOString().slice(0, 10)

let report = `# ${siteArg} Brand-Match Audit — ${date}\n\n`
report += `## Headline numbers\n`
report += `- Total articles (active): ${total}\n`
report += `- Articles with brand-in-headline: ${branded}\n`
report += `- PASS (≥2 products match headline brand): ${results.PASS.length}\n`
report += `- PARTIAL (exactly 1 product matches): ${results.PARTIAL.length}\n`
report += `- FAIL (0 products match headline brand): ${results.FAIL.length}\n`
report += `- NO_BRAND (no brand detected in keyword): ${results.NO_BRAND.length}\n\n`

if (results.FAIL.length > 0) {
  report += `## FAIL articles\n`
  report += `| Slug | Headline brand | Hub | Products | Brand matches |\n`
  report += `|---|---|---|---|---|\n`
  for (const a of results.FAIL) {
    const brands = a.headlineBrands.join(', ')
    report += `| ${a.slug} | ${brands} | ${a.hub} | ${a.productIds.length} | 0 |\n`
  }
  report += `\n`
}

if (results.PARTIAL.length > 0) {
  report += `## PARTIAL articles\n`
  report += `| Slug | Headline brand | Hub | Match ratio |\n`
  report += `|---|---|---|---|\n`
  for (const a of results.PARTIAL) {
    for (const br of a.brandResults) {
      report += `| ${a.slug} | ${br.brand} | ${a.hub} | ${br.matches}/${a.productIds.length} |\n`
    }
  }
  report += `\n`
}

report += `## Recommended actions\n\n`
if (results.FAIL.length === 0 && results.PARTIAL.length === 0) {
  report += `All branded articles are correctly seeded. No action required.\n\n`
} else {
  if (results.FAIL.length > 0) {
    report += `**FAIL articles (${results.FAIL.length}):** For each FAIL:\n`
    report += `1. Source brand-specific products via Rainforest API using the brand name as search query\n`
    report += `2. Add products to products.yaml with correct \`brand:\` field\n`
    report += `3. Assign brand products to article in pipeline.json (position 0)\n`
    report += `4. Regenerate article with \`--force\`\n`
    report += `5. If brand has no Amazon presence: retitle article to remove brand from keyword, assign generic products, regenerate\n\n`
  }
  if (results.PARTIAL.length > 0) {
    report += `**PARTIAL articles (${results.PARTIAL.length}):** Add 1-2 more brand-matching products to each article to reach ≥2 matches.\n\n`
  }
}

report += `## Methodology\n\n`
report += `- Brand detection uses word-boundary regex (\`\\\\b<brand>\\\\b\`, case-insensitive)\n`
report += `- PASS requires ≥2 brand-matching products (prevents single-product false positives)\n`
report += `- Brand field in products.yaml must be populated; \`null\` entries suppress PASS scores\n`
report += `- Run \`node scripts/validate-catalog-brand-coverage.mjs --site ${siteArg}\` to find unbranded products\n`

// ---------------------------------------------------------------------------
// Console output
// ---------------------------------------------------------------------------

const BOLD = '\x1b[1m'
const GREEN = '\x1b[32m'
const YELLOW = '\x1b[33m'
const RED = '\x1b[31m'
const RESET = '\x1b[0m'

console.log(`\n${BOLD}Brand-Match Audit — ${siteArg}${RESET}`)
console.log(`Site root: ${siteRoot}\n`)
console.log(`  Total articles: ${total}`)
console.log(`  Brand-in-headline: ${branded}`)
console.log(`  ${GREEN}PASS:${RESET}    ${results.PASS.length}`)
console.log(`  ${YELLOW}PARTIAL:${RESET} ${results.PARTIAL.length}`)
console.log(`  ${RED}FAIL:${RESET}    ${results.FAIL.length}`)
console.log(`  NO_BRAND: ${results.NO_BRAND.length}\n`)

if (results.FAIL.length > 0) {
  console.log(`${RED}FAIL articles:${RESET}`)
  for (const a of results.FAIL) {
    console.log(`  ${RED}✗${RESET} ${a.slug} (brand: ${a.headlineBrands.join(', ')}, hub: ${a.hub}, products: ${a.productIds.length})`)
  }
  console.log()
}

if (results.PARTIAL.length > 0 && verbose) {
  console.log(`${YELLOW}PARTIAL articles:${RESET}`)
  for (const a of results.PARTIAL) {
    const ratio = a.brandResults.map(r => `${r.brand} ${r.matches}/${a.productIds.length}`).join(', ')
    console.log(`  ${YELLOW}~${RESET} ${a.slug} (${ratio})`)
  }
  console.log()
}

// Write report file
const reportPath = join(siteRoot, 'brand-mismatch-audit.md')
writeFileSync(reportPath, report, 'utf8')
console.log(`Report written: ${reportPath}`)

if (results.FAIL.length > 0) {
  console.log(`\n${RED}✗ ${results.FAIL.length} FAIL article(s) — exit 1${RESET}`)
  if (!reportOnly) process.exit(1)
} else {
  console.log(`\n${GREEN}✓ No FAIL articles — brand-match audit passed${RESET}`)
  if (results.PARTIAL.length > 0) {
    console.log(`${YELLOW}  ${results.PARTIAL.length} PARTIAL article(s) — review recommended but not blocking${RESET}`)
  }
}
