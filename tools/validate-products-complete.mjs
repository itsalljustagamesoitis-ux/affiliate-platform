#!/usr/bin/env node
/**
 * validate-products-complete.mjs — Check products.yaml completeness.
 *
 * Mirrors the Python test_all_products_have_required_fields check so it can
 * be run as a standalone tool (e.g. before a production run) without pytest.
 *
 * Usage:
 *   node tools/validate-products-complete.mjs --site <slug>
 *   node tools/validate-products-complete.mjs --site <slug> --strict
 *
 * Exit codes:
 *   0 = all products complete
 *   1 = completeness errors found
 *   2 = tool error (missing files, etc.)
 *
 * --strict: also require default_pros and default_cons to be non-empty arrays
 *           (by default, notes_for_writers satisfies the pros/cons requirement)
 */

import { readFileSync, existsSync } from 'fs'
import { resolve } from 'path'
import yaml from 'js-yaml'

// ── ANSI helpers ──────────────────────────────────────────────────────────────

const c = {
  green:  s => `\x1b[32m${s}\x1b[0m`,
  red:    s => `\x1b[31m${s}\x1b[0m`,
  yellow: s => `\x1b[33m${s}\x1b[0m`,
  bold:   s => `\x1b[1m${s}\x1b[0m`,
}

const VALID_PRICE_BANDS = new Set(['budget', 'mid', 'premium'])

// ── Arg parsing ───────────────────────────────────────────────────────────────

const args = process.argv.slice(2)
const get  = flag => { const i = args.indexOf(flag); return i !== -1 ? args[i + 1] : null }
const has  = flag => args.includes(flag)

const siteSlug = get('--site')
const strict   = has('--strict')

if (!siteSlug) {
  console.error('Usage: node tools/validate-products-complete.mjs --site <slug>')
  process.exit(2)
}

const siteRoot    = resolve(process.env.HOME, siteSlug)
const productsPath = resolve(siteRoot, 'content/products/products.yaml')

if (!existsSync(productsPath)) {
  console.error(`ERROR: products.yaml not found: ${productsPath}`)
  process.exit(2)
}

// ── Load ──────────────────────────────────────────────────────────────────────

const products = yaml.load(readFileSync(productsPath, 'utf8')) || {}
const keys     = Object.keys(products)

console.log()
console.log(c.bold(`Validating: ${productsPath}`))
console.log(`  Products: ${keys.length}`)
console.log()

// ── Checks ────────────────────────────────────────────────────────────────────

const errors   = []
const warnings = []

for (const key of keys) {
  const p = products[key]
  if (typeof p !== 'object' || p === null) {
    errors.push(`'${key}': not an object`)
    continue
  }

  const missing = []

  // name (or title as fallback)
  if (!p.name && !p.title) missing.push('name')

  // brand
  if (!p.brand) missing.push('brand')

  // price_band — must exist and be valid
  if (!p.price_band) {
    missing.push('price_band')
  } else if (!VALID_PRICE_BANDS.has(p.price_band)) {
    errors.push(`'${key}': price_band='${p.price_band}' (must be budget | mid | premium)`)
  }

  // amazon_asin key must exist (value may be null / VERIFY / NOT_ON_AMAZON)
  if (!('amazon_asin' in p) && !('asin' in p)) {
    missing.push('amazon_asin (key missing entirely)')
  }

  // editorial data: default_pros+cons OR notes_for_writers
  const hasProsCons = Array.isArray(p.default_pros) && p.default_pros.length > 0
                   && Array.isArray(p.default_cons) && p.default_cons.length > 0
  const hasNotes    = typeof p.notes_for_writers === 'string' && p.notes_for_writers.trim().length > 0

  if (strict) {
    if (!hasProsCons) missing.push('default_pros + default_cons (non-empty)')
  } else {
    if (!hasProsCons && !hasNotes) missing.push('default_pros/default_cons or notes_for_writers')
  }

  if (missing.length > 0) errors.push(`'${key}': missing ${missing.join(', ')}`)
}

// ── Report ────────────────────────────────────────────────────────────────────

if (errors.length === 0) {
  console.log(c.green(`  [PASS] All ${keys.length} products complete`))
  if (strict) console.log(`         (strict mode: default_pros/cons required)`)
  console.log()
  process.exit(0)
} else {
  console.error(c.red(`  [FAIL] ${errors.length} product(s) have completeness issues:\n`))
  for (const e of errors.slice(0, 20)) {
    console.error(`    ${e}`)
  }
  if (errors.length > 20) {
    console.error(`    ... and ${errors.length - 20} more`)
  }
  console.log()
  process.exit(1)
}
