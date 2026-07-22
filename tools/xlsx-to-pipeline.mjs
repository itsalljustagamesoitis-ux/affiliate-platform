#!/usr/bin/env node
/**
 * xlsx-to-pipeline.mjs — Convert keyword research xlsx into pipeline.json.
 *
 * Usage:
 *   node tools/xlsx-to-pipeline.mjs --input <path-to-xlsx> --output <path-to-pipeline.json>
 *   node tools/xlsx-to-pipeline.mjs --input <path-to-xlsx> --output <path-to-pipeline.json> --json
 *
 * Point 3 of the launch-site ritual (PIPELINE.md).
 */

import { readFileSync, writeFileSync, existsSync } from 'fs'
import { basename, resolve } from 'path'
import { fileURLToPath } from 'url'
import XLSX from 'xlsx'
import yaml from 'js-yaml'
import { classifyKeyword } from './lib/classify-keyword.mjs'

// ── ANSI helpers ──────────────────────────────────────────────────────────────

const c = {
  green:  s => `\x1b[32m${s}\x1b[0m`,
  red:    s => `\x1b[31m${s}\x1b[0m`,
  yellow: s => `\x1b[33m${s}\x1b[0m`,
  bold:   s => `\x1b[1m${s}\x1b[0m`,
}

const pass = label => console.log(`  ${c.green('[PASS]')} ${label}`)
const fail = label => console.error(`  ${c.red('[FAIL]')} ${label}`)

// ── Arg parsing ───────────────────────────────────────────────────────────────

const args = process.argv.slice(2)
const get = flag => { const i = args.indexOf(flag); return i !== -1 ? args[i + 1] : null }
const has = flag => args.includes(flag)

const inputPath         = get('--input')
const outputPath        = get('--output')
const rejectPatternsPath = get('--reject-patterns')
const jsonMode          = has('--json')

if (!inputPath || !outputPath) {
  console.error('Usage: node tools/xlsx-to-pipeline.mjs --input <xlsx> --output <pipeline.json> [--reject-patterns <yaml>]')
  process.exit(2)
}

const absInput  = resolve(inputPath)
const absOutput = resolve(outputPath)

// ── Required columns ──────────────────────────────────────────────────────────

const REQUIRED_COLS = [
  '#', 'Hub', 'Hub Slug', 'Hub URL', 'Cluster', 'Keyword', 'Slug',
  'Locked URL', 'Article Type', 'Required Product Count', 'Angle',
  'H2 Structure', 'Volume', 'KD', 'CPC', 'Intent', 'Quality',
  'AI Overview', 'Premium Brand', 'Source Seed',
]

const VALID_TYPES = new Set(['buyer_guide', 'roundup', 'comparison', 'review', 'informational'])

/**
 * Normalizes a type string to the platform's lowercase_underscore form.
 * Handles both space-separated ("Buyer Guide") and hyphenated ("buyer-guide") input.
 * @param {string} raw
 * @returns {string}
 */
// Cross-site type aliases (e.g. 'guide' → 'informational')
const TYPE_ALIASES = {
  guide: 'informational', 'how-to': 'informational', 'how to': 'informational', how_to: 'informational',
  how_to_guide: 'informational',
}

function normalizeType(raw) {
  if (!raw) return raw
  const normalized = raw.trim().toLowerCase().replace(/[-\s]+/g, '_')
  return TYPE_ALIASES[normalized] ?? normalized
}

/**
 * Converts a keyword to a URL slug.
 * @param {string} keyword
 * @returns {string}
 */
function slugifyKeyword(keyword) {
  return keyword
    .toLowerCase()
    .replace(/['']/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 80)
}

/**
 * Humanizes a hub slug to a display label.
 * "sauna-brand-harvia" → "Harvia"
 * "sauna-infrared"     → "Infrared"
 * "cameras-mirrorless" → "Mirrorless"
 * @param {string} hubSlug
 * @returns {string}
 */
function humanizeHubSlug(hubSlug) {
  const parts = hubSlug.split('-')
  const known = ['sauna', 'cameras', 'lenses', 'bags', 'lens']
  const start = known.includes(parts[0]) ? 1 : 0
  const meaningful = parts.slice(start)
  if (meaningful[0] === 'brand' && meaningful.length > 1) {
    return meaningful.slice(1).map(p => p.charAt(0).toUpperCase() + p.slice(1)).join(' ')
  }
  return meaningful.map(p => p.charAt(0).toUpperCase() + p.slice(1)).join(' ')
}

/**
 * Coerces a cell value to integer or null.
 * @param {any} v
 * @returns {number|null}
 */
function toInt(v) {
  if (v === null || v === undefined || v === '') return null
  const n = parseInt(v, 10)
  return isNaN(n) ? null : n
}

/**
 * Coerces a cell value to float or null.
 * @param {any} v
 * @returns {number|null}
 */
function toFloat(v) {
  if (v === null || v === undefined || v === '') return null
  const n = parseFloat(v)
  return isNaN(n) ? null : n
}

/**
 * Interprets a cell value as boolean.
 * Treats "$", "yes", "true", "1", and any non-empty non-None string as true.
 * Treats null, undefined, "", "none", "no", "false", "0" as false.
 * @param {any} v
 * @returns {boolean}
 */
function toBool(v) {
  if (v === null || v === undefined || v === '') return false
  const s = String(v).trim().toLowerCase()
  return !['none', 'no', 'false', '0', ''].includes(s)
}

/**
 * Derives the site slug from the xlsx filename.
 * e.g. "thecoffeedispatch-launch-300.xlsx" → "thecoffeedispatch"
 * @param {string} filename
 * @returns {string}
 */
function deriveSiteSlug(filename) {
  return basename(filename, '.xlsx').replace(/-launch-\d+$/i, '')
}

// ── Main ──────────────────────────────────────────────────────────────────────

console.log()
console.log(c.bold(`Reading: ${basename(absInput)}`))

// Validation 1: file exists
if (!existsSync(absInput)) {
  fail(`Input file not found: ${absInput}`)
  process.exit(2)
}

let wb
try {
  wb = XLSX.readFile(absInput)
} catch (err) {
  fail(`Cannot read xlsx: ${err.message}`)
  process.exit(2)
}

// Validation 2: find sheet (Launch-N preferred; fall back to first sheet)
const launchSheet = wb.SheetNames.find(n => /^Launch-\d+$/i.test(n))
const sheetName   = launchSheet ?? wb.SheetNames[0]
if (!launchSheet) {
  console.log(c.yellow(`  [WARN] No "Launch-N" sheet found — using first sheet: "${sheetName}"`))
}

const expectedCount = launchSheet ? parseInt(launchSheet.replace(/^Launch-/i, ''), 10) : null
const ws      = wb.Sheets[sheetName]
const rawRows = XLSX.utils.sheet_to_json(ws, { defval: null })

console.log(`  Found sheet: ${sheetName} (${rawRows.length} rows)`)

// ── Column normalization (CC schema variants) ─────────────────────────────────
// Some keyword research exports use slightly different column names.
// Normalize before schema detection so all downstream logic uses canonical names.
{
  const cols = Object.keys(rawRows[0] ?? {})
  const has = c => cols.includes(c)
  for (let i = 0; i < rawRows.length; i++) {
    const row = rawRows[i]
    // '#' — auto-generate row index if absent
    if (!has('#')) row['#'] = i + 1
    // 'Cluster' — alias from 'Category'
    if (!has('Cluster') && has('Category')) row['Cluster'] = row['Category']
    // 'AI Overview' — alias from 'AI Overview flag'
    if (!has('AI Overview') && has('AI Overview flag')) row['AI Overview'] = row['AI Overview flag']
    // 'Premium Brand' — alias from 'Premium Brand flag'
    if (!has('Premium Brand') && has('Premium Brand flag')) row['Premium Brand'] = row['Premium Brand flag']
    // 'Hub' — alias from 'Hub Label' (minimal-schema exports carry Hub Slug + Hub Label but no 'Hub' column)
    if (!has('Hub') && has('Hub Label')) row['Hub'] = row['Hub Label']
  }
  if (!has('#') || !has('Cluster') || !has('AI Overview') || !has('Premium Brand') || !has('Hub')) {
    const mapped = []
    if (!has('#'))            mapped.push('# (auto-generated)')
    if (!has('Cluster'))      mapped.push('Cluster ← Category')
    if (!has('AI Overview'))  mapped.push('AI Overview ← AI Overview flag')
    if (!has('Premium Brand')) mapped.push('Premium Brand ← Premium Brand flag')
    if (!has('Hub'))          mapped.push('Hub ← Hub Label')
    console.log(`  [INFO] Column aliases applied: ${mapped.join(', ')}`)
  }
}

// Columns that are genuinely optional metadata in the CC schema — the row
// mapper below already defaults these to null/false when absent per-row, so
// a minimal export that omits the columns entirely (not just leaves cells
// blank) should not fail validation.
const OPTIONAL_COLS = [
  'Hub URL', 'Locked URL', 'Required Product Count', 'Angle', 'H2 Structure',
  'Quality', 'AI Overview', 'Premium Brand', 'Source Seed',
]

// ── Schema detection ──────────────────────────────────────────────────────────
// Simple schema: has 'archetype' + 'hub' columns but not 'Article Type'.
// Used by research-tool exports (e.g. sauna-site11-pipeline-v2.xlsx).
// CC schema:     has full column set produced by keyword research template.

const firstRowCols = new Set(Object.keys(rawRows[0] ?? {}))
const isSimpleSchema = firstRowCols.has('archetype') && !firstRowCols.has('Article Type')
if (isSimpleSchema) {
  console.log(c.yellow(`  [INFO] Simple schema detected (archetype/hub columns) — using simplified validation`))
}

// Auto-classify rows whose type column is empty (CC schema only)
let autoClassified = 0
if (!isSimpleSchema) {
  for (const row of rawRows) {
    if (!row['Article Type'] && row['Keyword']) {
      row['Article Type'] = classifyKeyword(String(row['Keyword']))
      autoClassified++
    }
  }
  if (autoClassified > 0) {
    console.log(c.yellow(`  [WARN] ${autoClassified} row(s) had empty Article Type — inferred from keyword`))
  }
}
console.log()

let errors = 0

// ── Schema-specific validations ───────────────────────────────────────────────

const HUB_SLUG_PATTERN = /^[a-z0-9]+(-[a-z0-9]+)*$/

if (isSimpleSchema) {
  // Simple schema: only require Keyword, archetype, hub
  const SIMPLE_REQUIRED = ['Keyword', 'archetype', 'hub']
  const missingSimple = SIMPLE_REQUIRED.filter(col => !firstRowCols.has(col))
  if (missingSimple.length > 0) {
    fail(`Missing required columns: ${missingSimple.join(', ')}`)
    errors++
  } else {
    pass('Required columns present')
  }

  // Every row must have Keyword, archetype, hub
  const missingRows = rawRows
    .map((row, i) => ({ row, i }))
    .filter(({ row }) => !row['Keyword'] || !row['archetype'] || !row['hub'])
    .map(({ i }) => i + 2)
  if (missingRows.length > 0) {
    fail(`Rows missing Keyword/archetype/hub: rows ${missingRows.slice(0, 5).join(', ')}${missingRows.length > 5 ? '...' : ''}`)
    errors++
  }

  // Types valid
  const badTypes = rawRows
    .map(row => normalizeType(row['archetype']))
    .filter(t => t && !VALID_TYPES.has(t))
  const uniqueBadTypes = [...new Set(badTypes)]
  if (uniqueBadTypes.length > 0) {
    fail(`Invalid archetype values: ${uniqueBadTypes.join(', ')}`)
    errors++
  } else {
    pass('Article types valid')
  }

  // Hub slugs are kebab-case
  const badHubSlugs = rawRows
    .map((row, i) => ({ slug: row['hub'] ? String(row['hub']).trim() : '', i }))
    .filter(({ slug }) => slug && !HUB_SLUG_PATTERN.test(slug))
    .map(({ slug, i }) => `row ${i + 2}: '${slug}'`)
  if (badHubSlugs.length > 0) {
    fail(`Hub slugs not in kebab-case format: ${badHubSlugs.slice(0, 5).join(', ')}`)
    errors++
  } else {
    pass('Hub slugs are valid kebab-case')
  }

  // Slugs unique (generated from keywords — check for keyword duplicates)
  const keywordsSeen = new Map()
  const dupKeywords = []
  for (const row of rawRows) {
    const kw = row['Keyword'] ? String(row['Keyword']).trim().toLowerCase() : ''
    if (!kw) continue
    if (keywordsSeen.has(kw)) dupKeywords.push(kw)
    else keywordsSeen.set(kw, true)
  }
  if (dupKeywords.length > 0) {
    fail(`Duplicate keywords: ${dupKeywords.slice(0, 5).join(', ')}${dupKeywords.length > 5 ? '...' : ''}`)
    errors++
  } else {
    pass(`All keywords unique (${rawRows.length} articles)`)
  }

} else {
  // CC schema validations (original)

  // Validation 3: required columns (OPTIONAL_COLS may be entirely absent — the
  // row mapper defaults those to null/false per-row regardless)
  const missingCols = REQUIRED_COLS.filter(col => !firstRowCols.has(col) && !OPTIONAL_COLS.includes(col))
  const missingOptionalCols = OPTIONAL_COLS.filter(col => !firstRowCols.has(col))
  if (missingCols.length > 0) {
    fail(`Missing required columns: ${missingCols.join(', ')}`)
    errors++
  } else {
    pass('Required columns present')
  }
  if (missingOptionalCols.length > 0) {
    console.log(c.yellow(`  [INFO] Optional columns absent, defaulting to null/false: ${missingOptionalCols.join(', ')}`))
  }

  // Validation 4: every row has #, Slug, Hub, Cluster, Article Type
  const missingRequired = rawRows
    .map((row, i) => ({ row, i }))
    .filter(({ row }) => !row['#'] || !row['Slug'] || !row['Hub'] || !row['Cluster'] || !row['Article Type'])
    .map(({ i }) => i + 2)
  if (missingRequired.length > 0) {
    fail(`Rows missing required fields (#, Slug, Hub, Cluster, Article Type): rows ${missingRequired.slice(0, 5).join(', ')}${missingRequired.length > 5 ? '...' : ''}`)
    errors++
  }

  // Validation 5: slugs unique
  const slugsSeen = new Map()
  const dupSlugs = []
  for (const row of rawRows) {
    const slug = row['Slug']
    if (!slug) continue
    if (slugsSeen.has(slug)) dupSlugs.push(slug)
    else slugsSeen.set(slug, true)
  }
  if (dupSlugs.length > 0) {
    fail(`Duplicate slugs: ${dupSlugs.slice(0, 5).join(', ')}${dupSlugs.length > 5 ? '...' : ''}`)
    errors++
  } else {
    pass(`All slugs unique (${rawRows.length} articles)`)
  }

  // Validation 6: article types valid
  const badTypes = rawRows
    .map(row => normalizeType(row['Article Type']))
    .filter(t => t && !VALID_TYPES.has(t))
  const uniqueBadTypes = [...new Set(badTypes)]
  if (uniqueBadTypes.length > 0) {
    fail(`Invalid Article Type values: ${uniqueBadTypes.join(', ')} — expected: ${[...VALID_TYPES].join(', ')}`)
    errors++
  } else {
    pass('Article types valid')
  }

  // Validation 7: count matches suffix
  if (expectedCount !== null && rawRows.length !== expectedCount) {
    fail(`Article count mismatch: sheet is ${sheetName} but contains ${rawRows.length} rows (expected ${expectedCount})`)
    errors++
  } else {
    pass(`Article count: ${rawRows.length}${expectedCount !== null ? ` (matches ${sheetName})` : ''}`)
  }

  // Validation 8: hub slugs are kebab-case
  const badHubSlugs = []
  for (let i = 0; i < rawRows.length; i++) {
    const row = rawRows[i]
    const hubSlug = row['Hub Slug'] ? String(row['Hub Slug']).trim() : String(row['Cluster']).trim()
    if (hubSlug && !HUB_SLUG_PATTERN.test(hubSlug)) {
      badHubSlugs.push(`row ${i + 2}: '${hubSlug}'`)
    }
  }
  if (badHubSlugs.length > 0) {
    fail(`Hub slugs not in kebab-case format: ${badHubSlugs.slice(0, 5).join(', ')}${badHubSlugs.length > 5 ? '...' : ''}`)
    errors++
  } else {
    pass('Hub slugs are valid kebab-case')
  }
}

if (errors > 0) {
  console.error(`\n${c.red(`${errors} validation error(s). Aborting.`)}`)
  process.exit(1)
}

// ── Build output ──────────────────────────────────────────────────────────────

const articles = isSimpleSchema
  ? rawRows.map((row, idx) => {
      const keyword  = String(row['Keyword']).trim()
      const hub      = String(row['hub']).trim()
      return {
        id:          idx + 1,
        slug:        slugifyKeyword(keyword),
        keyword,
        type:        normalizeType(row['archetype']),
        hub,
        hub_slug:    hub,
        hub_label:   humanizeHubSlug(hub),
        category:    humanizeHubSlug(hub),
        volume:      toInt(row['Volume']),
        kd:          toInt(row['Keyword Difficulty']),
        cpc:         toFloat(row['CPC (USD)']),
        intent:      row['Intent'] ? String(row['Intent']).trim() : null,
        kd_tier:     row['kd_tier'] ? String(row['kd_tier']).trim() : null,
        cpc_tier:    row['cpc_tier'] ? String(row['cpc_tier']).trim() : null,
        source_seed: row['source_seed'] ? String(row['source_seed']).trim() : null,
        products:    [],
        hero_image:  null,
        body_images: [],
      }
    })
  : rawRows.map(row => ({
      id:                     toInt(row['#']),
      slug:                   String(row['Slug']).trim(),
      category:               String(row['Hub']).trim(),
      hub:                    row['Hub Slug'] ? String(row['Hub Slug']).trim() : String(row['Cluster']).trim(),
      hub_slug:               row['Hub Slug'] ? String(row['Hub Slug']).trim() : null,
      hub_label:              String(row['Hub']).trim(),
      cluster:                String(row['Cluster']).trim(),
      locked_url:             row['Locked URL'] ? String(row['Locked URL']).trim() : null,
      type:                   normalizeType(row['Article Type']),
      keyword:                row['Keyword'] ? String(row['Keyword']).trim() : null,
      angle:                  row['Angle'] ? String(row['Angle']).trim() : null,
      h2_structure:           row['H2 Structure'] ? String(row['H2 Structure']).trim() : null,
      required_product_count: toInt(row['Required Product Count']),
      volume:                 toInt(row['Volume']),
      kd:                     toInt(row['KD']),
      cpc:                    toFloat(row['CPC']),
      intent:                 row['Intent'] ? String(row['Intent']).trim() : null,
      quality_score:          toInt(row['Quality']),
      ai_overview:            toBool(row['AI Overview']),
      premium_brand:          toBool(row['Premium Brand']),
      source_seed:            row['Source Seed'] ? String(row['Source Seed']).trim() : null,
      products:               [],
      hero_image:             null,
      body_images:            [],
    }))

// ── B34: Reject-pattern filter ────────────────────────────────────────────────
// Optional --reject-patterns <yaml> adds site-specific keyword filters.
// Keywords matching any pattern (case-insensitive substring) are marked
// status:"skip" with skip_reason before B45 dedup runs.

let rejectPatterns = []
if (rejectPatternsPath) {
  const absRejectPath = resolve(rejectPatternsPath)
  if (!existsSync(absRejectPath)) {
    console.error(c.red(`  [B34] Reject-patterns file not found: ${absRejectPath}`))
    process.exit(1)
  }
  const rpDoc = yaml.load(readFileSync(absRejectPath, 'utf8'))
  rejectPatterns = Array.isArray(rpDoc?.reject_patterns) ? rpDoc.reject_patterns : []
  console.log(c.yellow(`  [B34] Loaded ${rejectPatterns.length} reject pattern(s) from ${basename(absRejectPath)}`))
}

if (rejectPatterns.length > 0) {
  let skipCount = 0
  for (const a of articles) {
    if (a.status) continue
    const kw = (a.keyword || a.slug.replace(/-/g, ' ')).toLowerCase()
    for (const pattern of rejectPatterns) {
      if (kw.includes(pattern.toLowerCase())) {
        a.status = 'skip'
        a.skip_reason = `reject-pattern: ${pattern}`
        skipCount++
        break
      }
    }
  }
  if (skipCount > 0) {
    console.log(c.yellow(`  [B34] ${skipCount} article(s) marked status:skip by reject patterns`))
  } else {
    console.log(`  [B34] No articles matched reject patterns`)
  }
}

// ── B45: Semantic slug dedup ──────────────────────────────────────────────────
// Strip common modifier words from keyword tokens; within each hub, any two
// articles whose stripped token-sets match are near-duplicates. Keep the
// highest-volume article; mark the rest status:"dupe" (they won't be produced).

const MODIFIER_WORDS = new Set([
  'best', 'good', 'great', 'top', 'worst',
  'affordable', 'cheap', 'budget', 'inexpensive', 'expensive',
  'premium', 'basic', 'simple', 'easy',
  'a', 'an', 'the',
])

function semanticKey(keyword) {
  return keyword
    .toLowerCase()
    .replace(/['']/g, '')
    .replace(/[^a-z0-9\s]+/g, ' ')
    .split(/\s+/)
    .filter(t => t && !MODIFIER_WORDS.has(t))
    .sort()
    .join(' ')
}

{
  // Group by (hub, semanticKey) — only consider articles with a volume to rank by
  const groups = new Map()
  for (const a of articles) {
    const key = `${a.hub}::${semanticKey(a.keyword || a.slug.replace(/-/g, ' '))}`
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key).push(a)
  }

  let dupeCount = 0
  for (const group of groups.values()) {
    if (group.length < 2) continue
    // Sort: highest volume first; null volume treated as 0
    group.sort((x, y) => (y.volume ?? 0) - (x.volume ?? 0))
    // Keep first (highest volume); mark rest as dupe
    for (let i = 1; i < group.length; i++) {
      group[i].status = 'dupe'
      group[i].dupe_of = group[0].slug
      dupeCount++
    }
  }

  if (dupeCount > 0) {
    console.log(c.yellow(`  [B45] ${dupeCount} semantic near-duplicate(s) marked status:dupe`))
  } else {
    console.log(`  [B45] No semantic near-duplicates found`)
  }
}

const categories = [...new Set(articles.map(a => a.category))].sort()
const hubs       = [...new Set(articles.map(a => a.hub))].sort()

console.log()
console.log(`  Categories: ${categories.length} (${categories.join(', ')})`)
console.log(`  Hubs: ${hubs.length} (${hubs.join(', ')})`)
console.log()

const site = deriveSiteSlug(basename(absInput))

const output = {
  version:      1,
  site,
  generated_at: new Date().toISOString(),
  source_xlsx:  basename(absInput),
  articles,
}

if (jsonMode) {
  // Write structured JSON summary to stdout for --json callers
  const summary = {
    site,
    source_xlsx: basename(absInput),
    article_count: articles.length,
    categories,
    hubs,
    output_path: absOutput,
  }
  process.stdout.write(JSON.stringify(summary, null, 2) + '\n')
}

try {
  writeFileSync(absOutput, JSON.stringify(output, null, 2), 'utf-8')
} catch (err) {
  fail(`Cannot write output: ${err.message}`)
  process.exit(2)
}

console.log(c.green(`  Wrote ${articles.length} articles to: ${absOutput}`))
console.log()
