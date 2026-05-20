#!/usr/bin/env node
/**
 * validate-catalog-brand-coverage.mjs
 *
 * Fails if any product in products.yaml has brand: null.
 * Null brand entries suppress brand-match audit PASS scores, causing false FAILs
 * and PARTIALs in validate-brand-match.mjs.
 *
 * Usage:
 *   node scripts/validate-catalog-brand-coverage.mjs --site northwoods-overland
 *   node scripts/validate-catalog-brand-coverage.mjs --site northwoods-overland --warn-only
 *
 * Exit codes:
 *   0 – all products have brand populated (or --warn-only)
 *   1 – ≥1 product has brand: null
 *   2 – usage/config error
 */

import { readFileSync, existsSync } from 'node:fs'
import { resolve, join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const PLATFORM_ROOT = resolve(__dirname, '..')

const args = process.argv.slice(2)
const siteArg  = args[args.indexOf('--site') + 1]
const warnOnly = args.includes('--warn-only')

if (!siteArg) {
  console.error('Usage: node scripts/validate-catalog-brand-coverage.mjs --site <site-slug>')
  process.exit(2)
}

function findSiteRoot(slug) {
  const candidates = [
    join(resolve(PLATFORM_ROOT, '..'), slug),
    join(process.env.HOME || '/root', slug),
  ]
  for (const p of candidates) {
    if (existsSync(join(p, 'content', 'products', 'products.yaml'))) return p
  }
  return null
}

const siteRoot = findSiteRoot(siteArg)
if (!siteRoot) {
  console.error(`[ERROR] Could not locate site root for "${siteArg}"`)
  process.exit(2)
}

const productsPath = join(siteRoot, 'content', 'products', 'products.yaml')
if (!existsSync(productsPath)) {
  console.error(`[ERROR] products.yaml not found: ${productsPath}`)
  process.exit(2)
}

const text = readFileSync(productsPath, 'utf8')
const nullBrandProducts = []
let currentId = null

for (const raw of text.split('\n')) {
  if (!raw.trim() || raw.trim().startsWith('#')) continue

  const topMatch = raw.match(/^([a-z0-9][a-z0-9_-]*):\s*$/)
  if (topMatch) { currentId = topMatch[1]; continue }

  if (currentId && /^\s+brand:\s*(null\s*)?$/.test(raw)) {
    nullBrandProducts.push(currentId)
  }
}

const BOLD   = '\x1b[1m'
const GREEN  = '\x1b[32m'
const YELLOW = '\x1b[33m'
const RED    = '\x1b[31m'
const RESET  = '\x1b[0m'

const total = (text.match(/^[a-z0-9][a-z0-9_-]*:\s*$/mg) ?? []).length

console.log(`\n${BOLD}Catalog Brand Coverage — ${siteArg}${RESET}`)
console.log(`Products checked: ${total}`)
console.log(`Null brand entries: ${nullBrandProducts.length}\n`)

if (nullBrandProducts.length > 0) {
  const color = warnOnly ? YELLOW : RED
  console.log(`${color}Products missing brand field:${RESET}`)
  for (const id of nullBrandProducts.slice(0, 30)) {
    console.log(`  ${color}·${RESET} ${id}`)
  }
  if (nullBrandProducts.length > 30) {
    console.log(`  … and ${nullBrandProducts.length - 30} more`)
  }
  console.log()
  console.log(`Fix: for each product, look up the manufacturer and set brand: <Name> in products.yaml.`)
  console.log(`Re-run Rainforest enrichment or edit manually.`)
  if (!warnOnly) {
    console.log(`\n${RED}✗ ${nullBrandProducts.length} unbranded product(s) — exit 1${RESET}`)
    process.exit(1)
  } else {
    console.log(`${YELLOW}⚠ ${nullBrandProducts.length} unbranded product(s) — warning only (--warn-only)${RESET}`)
  }
} else {
  console.log(`${GREEN}✓ All ${total} products have brand populated${RESET}`)
}
