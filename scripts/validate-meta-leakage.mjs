#!/usr/bin/env node
/**
 * validate-meta-leakage.mjs (V20) — Brief-reasoning leakage detector.
 *
 * Scans staged article markdown bodies for internal producer reasoning that
 * should never appear in published article text. All patterns are case-insensitive.
 *
 * Usage:
 *   node scripts/validate-meta-leakage.mjs --site <path-to-site-root>
 *   node scripts/validate-meta-leakage.mjs  # defaults to process.cwd()
 *
 * Exit: 0 = no leakage found, 1 = one or more articles contain leakage, 2 = tool error
 */

import { readdirSync, existsSync, readFileSync } from 'fs'
import { join, resolve, relative } from 'path'
import { createRequire } from 'module'

const require = createRequire(import.meta.url)
const matter  = require('gray-matter')

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

// ── Leakage patterns ──────────────────────────────────────────────────────────

// Any of these in the article body indicates producer brief-reasoning leaked into
// the published content. Origin: Site 14's marantz-vs-anthem-vs-denon shipped with
// 3 paragraphs of producer internal reasoning verbatim.
//
// Expanded 2026-06-04 after Site 16 editorial UAT (S1-02, S1-03) revealed
// 4 verb variants and 3 phrase patterns missing from original 13-pattern list.
const LEAKAGE_PATTERNS = [
  // Specific meta-reasoning phrases — unlikely to appear in editorial prose
  /\bprompt system\b/i,
  /\bh2_structure\b/i,
  /\bbrief specifies\b/i,
  /\bpersona'?s defer-to\b/i,
  /\bbrief also specifies\b/i,
  /\barticle type defined in\b/i,
  /\bformat governs\b/i,
  /\bper the brief\b/i,
  /\bthe prompt requires\b/i,
  /\bthe article brief\b/i,
  /\bsystem prompt\b/i,
  // "the brief" only when followed by meta-reasoning verbs (not "brief answer", "brief experience")
  // Expanded verb list: added covers, names, describes, notes, mentions, lists, identifies, defines, includes
  /\bthe brief (specifies|requires|states|calls for|says|indicates|mandates|asks for|covers|names|describes|notes|mentions|lists|identifies|defines|includes)\b/i,
  /\bthe brief for this article\b/i,
  // "this brief" as noun with verb — catches "The brief covers three Katadyn options"
  // Phrase "keep this brief" is not matched because "keep" is absent from the verb list
  /\bthis brief (covers|names|describes|notes|mentions|specifies|requires|states|says|indicates|includes|lists|calls for|asks for)\b/i,
  // Direct phrase matches from Site 16 SEV-1 articles (S1-02, S1-03)
  /\bappears in this brief\b/i,
  /\bin this brief\b/i,
  // Producer data-layer terminology — "the product-slug placed it here by category tag"
  /\bproduct[-_]slug\b/i,
]

// ── Args ──────────────────────────────────────────────────────────────────────

const args     = process.argv.slice(2)
const get      = flag => { const i = args.indexOf(flag); return i !== -1 ? args[i + 1] : null }
const siteDir  = resolve(get('--site') ?? process.cwd())
const jsonMode = args.includes('--json')
const artDir  = join(siteDir, 'content', 'articles')

if (!existsSync(artDir)) {
  console.error(`${c.red('[ERROR]')} content/articles/ not found at ${artDir}`)
  process.exit(2)
}

// ── Main ──────────────────────────────────────────────────────────────────────

const files = readdirSync(artDir).filter(f => f.endsWith('.md'))
const failures = []
let articleCount = 0

if (!jsonMode) console.log(`${c.dim('[V20]')} Scanning ${c.bold(String(files.length))} articles in ${relative(process.cwd(), artDir)} for brief-leakage...\n`)

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
  const body = parsed.content
  const articleFailures = []

  for (const pattern of LEAKAGE_PATTERNS) {
    const match = body.match(pattern)
    if (match) {
      // Find the line containing the match for context
      const lines = body.split('\n')
      const matchLine = lines.find(l => pattern.test(l)) ?? ''
      const snippet = matchLine.trim().slice(0, 100)
      articleFailures.push(`"${match[0]}" — ${snippet}${snippet.length >= 100 ? '…' : ''}`)
    }
  }

  if (articleFailures.length > 0) {
    failures.push({ file, issues: articleFailures })
  }
}

// ── JSON output (--json mode: used by orchestrator; suppresses terminal output) ──

if (jsonMode) {
  process.stdout.write(JSON.stringify({
    fail_count: failures.length,
    failures: failures.map(f => ({
      id: f.file.replace(/\.md$/, ''),
      file: f.file,
      issues: f.issues,
    })),
  }) + '\n')
  process.exit(failures.length > 0 ? 1 : 0)
}

// ── Report ────────────────────────────────────────────────────────────────────

console.log(`  Articles scanned: ${c.bold(String(articleCount))}`)
console.log(`  Patterns checked: ${c.bold(String(LEAKAGE_PATTERNS.length))}`)

if (failures.length === 0) {
  console.log(`  ${c.green('✓')} No brief-leakage patterns found\n`)
  process.exit(0)
}

console.log(`\n  ${c.red('[FAIL]')} ${failures.length} article(s) contain brief-leakage patterns:\n`)

for (const { file, issues } of failures) {
  console.log(`  ${c.bold(file)}`)
  for (const issue of issues) {
    console.log(`    ${c.red('✗')} ${issue}`)
  }
  console.log()
}

console.log(`  ${c.red('[V20 FAIL]')} ${failures.length}/${articleCount} articles contain brief-leakage`)
process.exit(1)
