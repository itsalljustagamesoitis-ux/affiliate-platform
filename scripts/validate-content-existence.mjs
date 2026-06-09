#!/usr/bin/env node
/**
 * validate-content-existence.mjs (V17) — Post-build content existence validator.
 *
 * Scans dist/ HTML for three failure modes in article pages:
 *   1. Placeholder patterns in article body (unresolved writer prompts)
 *   2. Empty article-page__content div (zero words)
 *   3. Article body word count < 200 words
 *
 * Only pages with a `.article-page__content` div are checked — hub/about/disclosure
 * pages are skipped automatically.
 *
 * Usage:
 *   node scripts/validate-content-existence.mjs --site <path-to-site-root>
 *   node scripts/validate-content-existence.mjs  # defaults to process.cwd()
 *
 * Exit: 0 = all articles pass, 1 = one or more failures, 2 = tool error
 */

import { readdirSync, statSync, existsSync, readFileSync } from 'fs'
import { join, resolve, relative } from 'path'
import { createRequire } from 'module'
import { fileURLToPath } from 'url'

const require = createRequire(import.meta.url)
const cheerio = require('cheerio')

// ── ANSI helpers ──────────────────────────────────────────────────────────────

const isTTY = process.stdout.isTTY
const esc   = isTTY ? (s, code) => `\x1b[${code}m${s}\x1b[0m` : s => s
const c = {
  green:  s => esc(s, '32'),
  red:    s => esc(s, '31'),
  yellow: s => esc(s, '33'),
  bold:   s => esc(s, '1'),
  dim:    s => esc(s, '2'),
  cyan:   s => esc(s, '36'),
}

// ── Placeholder patterns ──────────────────────────────────────────────────────

// Each entry: { pattern: RegExp, label: string }
// These should never appear in rendered article text.
const PLACEHOLDER_PATTERNS = [
  { pattern: /\[write [^\]]{3,}\]/i,          label: '[write ...] prompt stub' },
  { pattern: /\[\s*TODO[^\]]*\]/i,             label: '[TODO ...] stub' },
  { pattern: /\{\{[A-Z_]{3,}\}\}/,             label: '{{TEMPLATE_TOKEN}} unsubstituted' },
  { pattern: /\bNOT_ON_AMAZON\b/,              label: 'NOT_ON_AMAZON ASIN placeholder' },
  { pattern: /\bLOREM\s+IPSUM\b/i,             label: 'lorem ipsum filler' },
  { pattern: /\[\s*insert [^\]]{3,}\]/i,       label: '[insert ...] stub' },
  { pattern: /\[\s*add [^\]]{3,}here[^\]]*\]/i, label: '[add ... here] stub' },
]

// Patterns to check in href attributes (not visible text)
const HREF_PLACEHOLDER_PATTERNS = [
  { pattern: /\/dp\/VERIFY\b/,               label: 'VERIFY ASIN in Amazon link' },
  { pattern: /\/dp\/NOT_ON_AMAZON\b/,        label: 'NOT_ON_AMAZON ASIN in Amazon link' },
]

const WORD_COUNT_THRESHOLD = 200

// ── Args ──────────────────────────────────────────────────────────────────────

const args    = process.argv.slice(2)
const get     = flag => { const i = args.indexOf(flag); return i !== -1 ? args[i + 1] : null }
const siteDir = resolve(get('--site') ?? process.cwd())
const distDir = join(siteDir, 'dist')

if (!existsSync(distDir)) {
  console.error(`${c.red('[ERROR]')} dist/ not found at ${distDir}`)
  console.error('  Run npm run build first, or pass --site <path-to-site-root>')
  process.exit(2)
}

// ── File discovery ────────────────────────────────────────────────────────────

function* walkHtml(dir) {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry)
    const stat = statSync(full)
    if (stat.isDirectory()) {
      yield* walkHtml(full)
    } else if (entry === 'index.html' || entry.endsWith('.html')) {
      yield full
    }
  }
}

// ── Word count helper ─────────────────────────────────────────────────────────

function wordCount(text) {
  return text.trim().split(/\s+/).filter(Boolean).length
}

// ── Main ──────────────────────────────────────────────────────────────────────

const failures = []
const warnings = []
let articleCount = 0
let checkedCount = 0

console.log(`${c.dim('[V17]')} Scanning ${c.bold(relative(process.cwd(), distDir))} for content existence issues...\n`)

for (const htmlPath of walkHtml(distDir)) {
  const relPath = relative(distDir, htmlPath)

  // Skip root-level non-article files
  if (htmlPath === join(distDir, '404.html')) continue

  let html
  try {
    html = readFileSync(htmlPath, 'utf-8')
  } catch (err) {
    warnings.push(`${relPath}: could not read file (${err.message})`)
    continue
  }

  // Only process pages with an article content div
  if (!html.includes('article-page__content')) continue

  articleCount++
  const $ = cheerio.load(html)
  const $content = $('.article-page__content')

  if ($content.length === 0) {
    // Shouldn't happen after the includes() check, but be defensive
    continue
  }

  checkedCount++
  const relDisplay = relPath.replace(/\/index\.html$/, '') || '(root)'
  const articleFailures = []

  // ── Check 1: Placeholder patterns in text ────────────────────────────────

  const bodyText = $content.text()

  for (const { pattern, label } of PLACEHOLDER_PATTERNS) {
    const match = bodyText.match(pattern)
    if (match) {
      articleFailures.push(`placeholder: ${label} — matched: ${JSON.stringify(match[0].slice(0, 60))}`)
    }
  }

  // ── Check 2: Placeholder patterns in href attributes ─────────────────────

  $content.find('a[href]').each((_, el) => {
    const href = $(el).attr('href') ?? ''
    for (const { pattern, label } of HREF_PLACEHOLDER_PATTERNS) {
      if (pattern.test(href)) {
        articleFailures.push(`placeholder in link: ${label} — href: ${href.slice(0, 80)}`)
      }
    }
  })

  // ── Check 3: Empty content ────────────────────────────────────────────────

  const wc = wordCount(bodyText)

  if (wc === 0) {
    articleFailures.push('content is empty (0 words)')
  } else if (wc < WORD_COUNT_THRESHOLD) {
    articleFailures.push(`content too short: ${wc} words (minimum ${WORD_COUNT_THRESHOLD})`)
  }

  if (articleFailures.length > 0) {
    failures.push({ path: relDisplay, issues: articleFailures })
  }
}

// ── Report ────────────────────────────────────────────────────────────────────

console.log(`  Scanned: ${c.bold(String(articleCount))} article pages`)

if (warnings.length > 0) {
  for (const w of warnings) {
    console.log(`  ${c.yellow('[WARN]')} ${w}`)
  }
}

if (failures.length === 0) {
  console.log(`  ${c.green('✓')} All ${articleCount} articles passed content-existence check\n`)
  process.exit(0)
}

console.log(`\n  ${c.red('[FAIL]')} ${failures.length} article(s) failed:\n`)

for (const { path, issues } of failures) {
  console.log(`  ${c.bold(path)}`)
  for (const issue of issues) {
    console.log(`    ${c.red('✗')} ${issue}`)
  }
  console.log()
}

console.log(`  ${c.red('[V17 FAIL]')} ${failures.length}/${articleCount} articles failed content-existence check`)
process.exit(1)
