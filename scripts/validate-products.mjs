/**
 * Pre-build products validator — fails the build if critical issues are found in products.yaml.
 * Run via: node scripts/validate-products.mjs
 *
 * Hard-fail rules (exit code 1):
 *   placeholder-title   — VERIFY/PLACEHOLDER/TODO token in name or title field
 *   no-buy-url-fallback — non-discontinued product has no usable ASIN and no buy_url (CTA silently suppressed)
 *   missing-hub         — product has no hub field
 *
 * Warning rules (exit code 0):
 *   missing-brand              — brand is null or empty (data quality debt, does not block build)
 *   missing-name               — name and title both absent (structural oddity)
 *   unenriched-amazon-product  — valid Amazon ASIN but no default_image and no local image file;
 *                                product renders as a text-only card (enrichment gap)
 */

import { readFileSync, existsSync } from 'fs'
import { resolve, join } from 'path'
import yaml from 'js-yaml'

const SITE_ROOT = process.cwd()
const PRODUCTS_YAML = resolve(SITE_ROOT, 'content/products/products.yaml')

const SENTINEL_ASINS = new Set(['NOT_ON_AMAZON', 'NOT_FOUND', 'VERIFY'])
// Tokens that mean "someone forgot to fill this in" — hard-fail in name/title
const PLACEHOLDER_TOKEN_RE = /\bVERIFY\b|\bPLACEHOLDER\b|\bTODO\b/i
// Valid Amazon ASIN: exactly 10 uppercase alphanumeric characters
const ASIN_RE = /^[A-Z0-9]{10}$/

let failures = 0
const errors = []
const warnings = []

function fail(check, id, msg) {
  errors.push(`  FAIL [${check}] ${id}\n       ${msg}`)
  failures++
}

function warn(check, id, msg) {
  warnings.push(`  WARN [${check}] ${id}\n       ${msg}`)
}

if (!existsSync(PRODUCTS_YAML)) {
  console.log('No products.yaml found — skipping product validation.')
  process.exit(0)
}

let products
try {
  products = yaml.load(readFileSync(PRODUCTS_YAML, 'utf8'))
} catch (e) {
  console.error(`FAIL: products.yaml could not be parsed: ${e.message}`)
  process.exit(1)
}

if (!products || typeof products !== 'object') {
  console.error('FAIL: products.yaml is empty or not a valid YAML object.')
  process.exit(1)
}

for (const [id, p] of Object.entries(products)) {
  if (!p || typeof p !== 'object') {
    fail('malformed-entry', id, 'Entry is null or not an object')
    continue
  }

  const discontinued = p.discontinued === true
  const name = typeof p.name === 'string' ? p.name.trim() : ''
  const title = typeof p.title === 'string' ? p.title.trim() : ''
  const displayName = name || title

  // ── 1. Placeholder tokens in name / title ─────────────────────────────────
  if (name && PLACEHOLDER_TOKEN_RE.test(name)) {
    fail('placeholder-title', id, `name contains placeholder token: "${name}"`)
  }
  if (title && PLACEHOLDER_TOKEN_RE.test(title)) {
    fail('placeholder-title', id, `title contains placeholder token: "${title}"`)
  }

  // ── 2. Non-discontinued must have usable ASIN or buy_url ──────────────────
  if (!discontinued) {
    const asin = p.amazon_asin ?? p.asin ?? null
    const asinUnusable = !asin || SENTINEL_ASINS.has(String(asin))
    if (asinUnusable && !p.buy_url) {
      const asinLabel = asin ?? 'missing'
      fail('no-buy-url-fallback', id,
        `Non-discontinued product has no usable ASIN (${asinLabel}) and no buy_url — CTA will be silently suppressed`)
    }
  }

  // ── 3. Hub / category required ────────────────────────────────────────────
  // FSG uses `category:` while newer sites use `hub:` — accept either.
  const routing = p.hub ?? p.category ?? null
  if (!routing || !String(routing).trim()) {
    fail('missing-hub', id, 'Product has no hub or category field — cannot be routed to a category page')
  }

  // ── WARNINGS ──────────────────────────────────────────────────────────────

  // W1. Brand null or empty
  const brand = p.brand
  if (brand === null || brand === undefined || (typeof brand === 'string' && !brand.trim())) {
    warn('missing-brand', id, `brand is ${JSON.stringify(brand)} — set a brand name to improve CTA rendering`)
  }

  // W2. No name and no title
  if (!displayName) {
    warn('missing-name', id, 'Product has neither name nor title field')
  }

  // W3. Valid Amazon ASIN but no image — product renders as text-only card
  // Distinguishes enrichment gaps (should have image, Rainforest couldn't resolve it)
  // from legitimate Category-D cases (NOT_ON_AMAZON / sentinel — no image expected).
  const asinRaw = p.amazon_asin ?? p.asin ?? null
  const asinStr = asinRaw ? String(asinRaw).trim() : ''
  if (ASIN_RE.test(asinStr)) {
    const hasImageField = p.default_image && String(p.default_image).trim()
    const imgFile = join(SITE_ROOT, 'public/images/products', `${id}.jpg`)
    if (!hasImageField && !existsSync(imgFile)) {
      warn('unenriched-amazon-product', id,
        `ASIN ${asinStr} but no default_image and no local file — renders as text-only card (enrichment gap)`)
    }
  }
}

const total = Object.keys(products).length
const passCount = total - failures

if (warnings.length > 0) {
  // Cap warning output to 20 lines to avoid flooding the terminal on large catalogs
  const shown = warnings.slice(0, 20)
  const hidden = warnings.length - shown.length
  console.warn(`\n⚠  ${warnings.length} warning(s) — non-blocking:\n`)
  for (const w of shown) console.warn(w)
  if (hidden > 0) {
    console.warn(`\n   … and ${hidden} more warning(s). Fix the flagged fields to silence these.\n`)
  } else {
    console.warn()
  }
}

if (failures === 0) {
  console.log(warnings.length
    ? `✓ Product validation passed with ${warnings.length} warning(s) — ${total} products checked.\n`
    : `✓ Product validation passed — ${total} products checked, no issues found.\n`)
  process.exit(0)
} else {
  console.error(`\n✗ Product validation failed — ${failures} issue(s) found in ${total} products:\n`)
  for (const e of errors) console.error(e)
  console.error(`\nFix the issues above before building.\n`)
  process.exit(1)
}
