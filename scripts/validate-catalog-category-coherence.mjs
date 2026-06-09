#!/usr/bin/env node
/**
 * validate-catalog-category-coherence.mjs (V22) — Niche category coherence validator.
 *
 * Checks that products referenced in article markdown have category_type values
 * compatible with their article hub, per the niche config at
 * config/category-types/<niche>.yaml.
 *
 * Products without category_type are warned but not hard-failed (forward-looking
 * validator; existing catalog is tagged incrementally).
 *
 * Usage:
 *   node scripts/validate-catalog-category-coherence.mjs --site <path-to-site-root>
 *   node scripts/validate-catalog-category-coherence.mjs  # defaults to process.cwd()
 *
 * Exit: 0 = all tagged products coherent, 1 = one or more violations, 2 = tool error
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

// ── Args ──────────────────────────────────────────────────────────────────────

const args    = process.argv.slice(2)
const get     = flag => { const i = args.indexOf(flag); return i !== -1 ? args[i + 1] : null }
const siteDir = resolve(get('--site') ?? process.cwd())

const artDir   = join(siteDir, 'content', 'articles')
const prodFile = join(siteDir, 'content', 'products', 'products.yaml')
const cfgBase  = join(siteDir, 'config', 'category-types')
const siteCfg  = join(siteDir, 'site.config.yaml')

if (!existsSync(artDir))   { console.error(`${c.red('[ERROR]')} content/articles/ not found`); process.exit(2) }
if (!existsSync(prodFile)) { console.error(`${c.red('[ERROR]')} products.yaml not found`);     process.exit(2) }
if (!existsSync(siteCfg))  { console.error(`${c.red('[ERROR]')} site.config.yaml not found`);  process.exit(2) }

// ── Load site config to get niche slug ────────────────────────────────────────

let nicheSlug
try {
  const sc = yaml.load(readFileSync(siteCfg, 'utf-8'))
  nicheSlug = sc?.niche ?? sc?.site?.niche ?? sc?.content?.niche ?? null
} catch (err) {
  console.error(`${c.red('[ERROR]')} Cannot read site.config.yaml: ${err.message}`)
  process.exit(2)
}

if (!nicheSlug) {
  console.error(`${c.red('[ERROR]')} site.config.yaml has no niche: field`)
  process.exit(2)
}

// ── Load niche category config ────────────────────────────────────────────────

const nicheCfgPath = join(cfgBase, `${nicheSlug}.yaml`)

if (!existsSync(nicheCfgPath)) {
  console.log(`${c.yellow('[SKIP]')} No category-types config for niche "${nicheSlug}"`)
  console.log(`  Expected: ${nicheCfgPath}`)
  console.log(`  Create this file to enable V22 coherence checking.`)
  process.exit(0)
}

let nicheCfg
try {
  nicheCfg = yaml.load(readFileSync(nicheCfgPath, 'utf-8'))
} catch (err) {
  console.error(`${c.red('[ERROR]')} Cannot parse category-types config: ${err.message}`)
  process.exit(2)
}

const globallyForbidden = new Set(nicheCfg?.globally_forbidden ?? [])
const hubConstraints    = nicheCfg?.hub_constraints ?? {}

// ── Load products catalog ─────────────────────────────────────────────────────

let products
try {
  products = yaml.load(readFileSync(prodFile, 'utf-8'))
} catch (err) {
  console.error(`${c.red('[ERROR]')} Cannot load products.yaml: ${err.message}`)
  process.exit(2)
}

// ── Slug extraction (shared with V19) ─────────────────────────────────────────

const PRODUCT_BODY_RE = /product:([a-z0-9][a-z0-9-]*[a-z0-9]|[a-z0-9])/g

function extractAllSlugs(frontmatter, body) {
  const slugs = new Set()
  const prodList = frontmatter.products
  if (Array.isArray(prodList)) {
    for (const entry of prodList) {
      const id = entry?.id ?? entry
      if (typeof id === 'string' && id.trim()) slugs.add(id.trim())
    }
  }
  for (const match of body.matchAll(PRODUCT_BODY_RE)) {
    slugs.add(match[1])
  }
  return slugs
}

// ── Coherence check ───────────────────────────────────────────────────────────

function checkCoherence(slug, categoryType, hub) {
  // Global forbidden check
  if (globallyForbidden.has(categoryType)) {
    return {
      level: 'fail',
      reason: `category_type "${categoryType}" is globally forbidden in the ${nicheCfg.niche} niche`,
    }
  }

  const hubCfg = hubConstraints[hub]
  if (!hubCfg) return { level: 'ok' }

  // Per-hub forbidden check
  const hubForbidden = new Set(hubCfg.forbidden_category_types ?? [])
  if (hubForbidden.has(categoryType)) {
    return {
      level: 'fail',
      reason: `category_type "${categoryType}" is forbidden in hub "${hub}"`,
    }
  }

  // Per-hub allowed check (whitelist — only enforced when list is non-empty)
  const hubAllowed = hubCfg.allowed_category_types
  if (Array.isArray(hubAllowed) && hubAllowed.length > 0) {
    if (!hubAllowed.includes(categoryType)) {
      return {
        level: 'fail',
        reason: `category_type "${categoryType}" is not in the allowed list for hub "${hub}"`,
      }
    }
  }

  return { level: 'ok' }
}

// ── Main ──────────────────────────────────────────────────────────────────────

const files = readdirSync(artDir).filter(f => f.endsWith('.md'))
const failures = []
const warnings = []
let articleCount = 0
let taggedProductCount = 0
let untaggedCount = 0

console.log(`${c.dim('[V22]')} Checking catalog category coherence for niche ${c.bold(nicheSlug)}`)
console.log(`  Config: ${relative(process.cwd(), nicheCfgPath)}`)
console.log(`  Articles: ${files.length}\n`)

for (const file of files) {
  const filePath = join(artDir, file)
  let parsed
  try {
    parsed = matter(readFileSync(filePath, 'utf-8'))
  } catch {
    continue
  }

  articleCount++
  const hub = parsed.data.hub
  if (!hub) continue

  const slugs = extractAllSlugs(parsed.data, parsed.content)
  const articleFailures = []
  const articleUntagged = []

  for (const slug of slugs) {
    const product = products[slug]
    if (!product) continue // V19 handles missing slugs

    const categoryType = product.category_type ?? null

    if (!categoryType) {
      articleUntagged.push(slug)
      untaggedCount++
      continue
    }

    taggedProductCount++
    const result = checkCoherence(slug, categoryType, hub)
    if (result.level === 'fail') {
      articleFailures.push(`"${slug}" (category_type: ${categoryType}) — ${result.reason}`)
    }
  }

  if (articleFailures.length > 0) {
    failures.push({ file, hub, issues: articleFailures })
  }
  if (articleUntagged.length > 0) {
    warnings.push({ file, hub, slugs: articleUntagged })
  }
}

// ── Report ────────────────────────────────────────────────────────────────────

console.log(`  Articles checked:      ${c.bold(String(articleCount))}`)
console.log(`  Tagged products seen:  ${c.bold(String(taggedProductCount))}`)
console.log(`  Untagged (no type):    ${c.dim(String(untaggedCount))} ${untaggedCount > 0 ? c.yellow('(warnings only)') : ''}`)

if (warnings.length > 0) {
  console.log(`\n  ${c.yellow('[WARN]')} ${untaggedCount} product ref(s) have no category_type — tag to enable full coherence checking`)
  // Only print warnings if there's a manageable number
  if (untaggedCount <= 30) {
    for (const { file, hub, slugs } of warnings) {
      for (const slug of slugs) {
        console.log(`    ${c.yellow('⚠')} ${file} [hub: ${hub}]: "${slug}" has no category_type`)
      }
    }
  } else {
    console.log(`    (${untaggedCount} items — suppressed; run with --show-untagged to list)`)
  }
}

if (failures.length === 0) {
  console.log(`\n  ${c.green('✓')} All tagged products are category-coherent with their article hubs\n`)
  process.exit(0)
}

console.log(`\n  ${c.red('[FAIL]')} ${failures.length} article(s) have category-incoherent products:\n`)

for (const { file, hub, issues } of failures) {
  console.log(`  ${c.bold(file)} ${c.dim(`[hub: ${hub}]`)}`)
  for (const issue of issues) {
    console.log(`    ${c.red('✗')} ${issue}`)
  }
  console.log()
}

console.log(`  ${c.red('[V22 FAIL]')} ${failures.length}/${articleCount} articles have category coherence violations`)
process.exit(1)
