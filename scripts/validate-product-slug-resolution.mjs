#!/usr/bin/env node
/**
 * validate-product-slug-resolution.mjs (V19) — Product slug resolver.
 *
 * Scans staged article markdown for every product reference and verifies each
 * resolves to a key in content/products/products.yaml with a usable affiliate link.
 *
 * Checks:
 *   1. Every product:<slug> in article body resolves to a products.yaml key
 *   2. Every products.frontmatter id: resolves to a products.yaml key
 *   3. Each resolved product has a valid link (ASIN or buy_url — no VERIFY placeholders)
 *
 * Usage:
 *   node scripts/validate-product-slug-resolution.mjs --site <path-to-site-root>
 *   node scripts/validate-product-slug-resolution.mjs  # defaults to process.cwd()
 *
 * Exit: 0 = all slugs resolve, 1 = one or more failures, 2 = tool error
 */

import { readdirSync, existsSync, readFileSync } from 'fs'
import { join, resolve, relative } from 'path'
import { createRequire } from 'module'

const require = createRequire(import.meta.url)
const matter = require('gray-matter')
const yaml   = require('js-yaml')

// ── ANSI helpers ──────────────────────────────────────────────────────────────

const isTTY = process.stdout.isTTY
const esc   = isTTY ? (s, code) => `\x1b[${code}m${s}\x1b[0m` : s => s
const c = {
  green:  s => esc(s, '32'),
  red:    s => esc(s, '31'),
  yellow: s => esc(s, '33'),
  bold:   s => esc(s, '1'),
  dim:    s => esc(s, '2'),
}

// ── ASIN validation ───────────────────────────────────────────────────────────

const ASIN_RE = /^[A-Z0-9]{10}$/

// Returns { level: 'ok'|'fail'|'warn', reason?: string }
function productLinkStatus(product) {
  // products.yaml uses 'asin' (RMF) or 'amazon_asin' (UDS, HPC, etc.)
  const asin   = product.asin ?? product.amazon_asin ?? null
  const buyUrl = product.buy_url ?? null

  if (!asin && !buyUrl) {
    return { level: 'fail', reason: 'no asin and no buy_url' }
  }

  // VERIFY is a hard fail — placeholder not resolved before publishing
  if (asin === 'VERIFY') {
    return { level: 'fail', reason: 'ASIN is placeholder VERIFY — not resolved' }
  }

  if (asin && asin !== 'NOT_ON_AMAZON') {
    if (!ASIN_RE.test(asin)) {
      return { level: 'fail', reason: `ASIN "${asin}" is malformed (expected 10-char alphanumeric)` }
    }
    return { level: 'ok' }
  }

  // asin === 'NOT_ON_AMAZON' — warn if no buy_url, but don't hard-fail
  // (DTC products with no affiliate link still render; they just have no CTA button)
  if (!buyUrl || buyUrl.trim() === '') {
    return { level: 'warn', reason: 'asin is NOT_ON_AMAZON but buy_url is missing (no affiliate link)' }
  }
  return { level: 'ok' }
}

// ── Arg parsing ───────────────────────────────────────────────────────────────

const args    = process.argv.slice(2)
const get     = flag => { const i = args.indexOf(flag); return i !== -1 ? args[i + 1] : null }
const siteDir = resolve(get('--site') ?? process.cwd())
const artDir  = join(siteDir, 'content', 'articles')
const prodFile = join(siteDir, 'content', 'products', 'products.yaml')

if (!existsSync(artDir)) {
  console.error(`${c.red('[ERROR]')} content/articles/ not found at ${artDir}`)
  process.exit(2)
}
if (!existsSync(prodFile)) {
  console.error(`${c.red('[ERROR]')} products.yaml not found at ${prodFile}`)
  process.exit(2)
}

// ── Load products catalog ─────────────────────────────────────────────────────

let products
try {
  products = yaml.load(readFileSync(prodFile, 'utf-8'))
  if (!products || typeof products !== 'object') throw new Error('malformed or empty products.yaml')
} catch (err) {
  console.error(`${c.red('[ERROR]')} Cannot load products.yaml: ${err.message}`)
  process.exit(2)
}

const productKeys = new Set(Object.keys(products))

// ── Slug extraction helpers ───────────────────────────────────────────────────

// Matches both inline links [text](product:slug) and bare product:slug references
const PRODUCT_BODY_RE = /product:([a-z0-9][a-z0-9-]*[a-z0-9]|[a-z0-9])/g

function extractBodySlugs(body) {
  const slugs = new Set()
  for (const match of body.matchAll(PRODUCT_BODY_RE)) {
    slugs.add(match[1])
  }
  return slugs
}

function extractFrontmatterSlugs(frontmatter) {
  const slugs = new Set()
  const prodList = frontmatter.products
  if (!Array.isArray(prodList)) return slugs
  for (const entry of prodList) {
    const id = entry?.id ?? entry
    if (typeof id === 'string' && id.trim()) slugs.add(id.trim())
  }
  return slugs
}

// ── Main ──────────────────────────────────────────────────────────────────────

const failures = []
const articleWarnings = []
let articleCount = 0
let refCount = 0

const files = readdirSync(artDir).filter(f => f.endsWith('.md'))

console.log(`${c.dim('[V19]')} Checking ${c.bold(String(files.length))} articles in ${relative(process.cwd(), artDir)}...`)
console.log(`  Products catalog: ${c.bold(String(productKeys.size))} keys\n`)

for (const file of files) {
  const filePath = join(artDir, file)
  let parsed
  try {
    parsed = matter(readFileSync(filePath, 'utf-8'))
  } catch (err) {
    failures.push({ file, issues: [`could not parse: ${err.message}`] })
    continue
  }

  articleCount++
  const articleFailures = []

  // Collect all slugs referenced in this article (frontmatter + body)
  const bodySlug = extractBodySlugs(parsed.content)
  const fmSlugs  = extractFrontmatterSlugs(parsed.data)
  const allSlugs = new Set([...bodySlug, ...fmSlugs])

  const fileWarns = []

  for (const slug of allSlugs) {
    refCount++

    // Check 1: slug exists in products.yaml (hard fail)
    if (!productKeys.has(slug)) {
      articleFailures.push(`broken slug: "${slug}" not found in products.yaml`)
      continue
    }

    // Check 2: product has a usable link
    const linkStatus = productLinkStatus(products[slug])
    if (linkStatus.level === 'fail') {
      articleFailures.push(`"${slug}": ${linkStatus.reason}`)
    } else if (linkStatus.level === 'warn') {
      fileWarns.push(`"${slug}": ${linkStatus.reason}`)
    }
  }

  if (articleFailures.length > 0) {
    failures.push({ file, issues: articleFailures })
  }
  if (fileWarns.length > 0) {
    articleWarnings.push({ file, warns: fileWarns })
  }
}

// ── Report ────────────────────────────────────────────────────────────────────

console.log(`  Articles scanned:   ${c.bold(String(articleCount))}`)
console.log(`  Product refs found: ${c.bold(String(refCount))}`)

if (articleWarnings.length > 0) {
  const warnCount = articleWarnings.reduce((n, { warns }) => n + warns.length, 0)
  console.log(`  ${c.yellow('[WARN]')} ${warnCount} product(s) with no affiliate link (NOT_ON_AMAZON, no buy_url):`)
  for (const { file, warns } of articleWarnings) {
    for (const w of warns) {
      console.log(`    ${c.yellow('⚠')} ${file}: ${w}`)
    }
  }
  console.log()
}

if (failures.length === 0) {
  console.log(`  ${c.green('✓')} All product slugs resolve correctly (no broken references)\n`)
  process.exit(0)
}

console.log(`  ${c.red('[FAIL]')} ${failures.length} article(s) with broken product references:\n`)

for (const { file, issues } of failures) {
  console.log(`  ${c.bold(file)}`)
  for (const issue of issues) {
    console.log(`    ${c.red('✗')} ${issue}`)
  }
  console.log()
}

console.log(`  ${c.red('[V19 FAIL]')} ${failures.length}/${articleCount} articles failed slug resolution`)
process.exit(1)
