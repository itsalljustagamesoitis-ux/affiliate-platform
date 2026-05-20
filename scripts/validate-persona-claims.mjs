#!/usr/bin/env node
/**
 * validate-persona-claims.mjs
 *
 * Audits published article markdown files for first-person persona-claim violations.
 *
 * Two violation tiers:
 *   HARD – FTC-risk claims of personal product testing or ownership.
 *           These are false if the persona hasn't physically owned/tested the item.
 *           Exit 1 if any found.
 *   SOFT – Editorial voice violations: "I'd argue", "I'd move", etc.
 *           Weaken editorial credibility and signal AI-generated voice.
 *           Exit 0 but print warning count.
 *
 * Usage:
 *   node scripts/validate-persona-claims.mjs --site northwoods-overland
 *   node scripts/validate-persona-claims.mjs --site northwoods-overland --verbose
 *   node scripts/validate-persona-claims.mjs --site northwoods-overland --soft-as-hard
 *
 * Exit codes:
 *   0 – no HARD violations (SOFT violations print as warnings)
 *   1 – ≥1 HARD violation found
 *   2 – usage/config error
 */

import { readFileSync, readdirSync, existsSync } from 'node:fs'
import { resolve, join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const PLATFORM_ROOT = resolve(__dirname, '..')

// ---------------------------------------------------------------------------
// Arg parsing
// ---------------------------------------------------------------------------

const args = process.argv.slice(2)
const siteArg    = args[args.indexOf('--site') + 1]
const verbose    = args.includes('--verbose')
const softAsHard = args.includes('--soft-as-hard')  // treat SOFT as HARD for CI gates

if (!siteArg) {
  console.error('Usage: node scripts/validate-persona-claims.mjs --site <site-slug>')
  process.exit(2)
}

// ---------------------------------------------------------------------------
// Locate site root
// ---------------------------------------------------------------------------

function findSiteRoot(slug) {
  const parentDir = resolve(PLATFORM_ROOT, '..')
  const candidates = [
    join(parentDir, slug),
    resolve(process.env.HOME || '/root', slug),
  ]
  for (const p of candidates) {
    if (existsSync(join(p, 'content', 'articles'))) return p
  }
  return null
}

const siteRoot = findSiteRoot(siteArg)
if (!siteRoot) {
  console.error(`[ERROR] Could not locate site root for "${siteArg}". Expected at ~/${siteArg}/`)
  process.exit(2)
}

const articlesDir = join(siteRoot, 'content', 'articles')
if (!existsSync(articlesDir)) {
  console.error(`[ERROR] Articles directory not found: ${articlesDir}`)
  process.exit(2)
}

// ---------------------------------------------------------------------------
// Pattern definitions
// ---------------------------------------------------------------------------

const HARD_PATTERNS = [
  { re: /\bI (?:personally )?tested\b/gi,              label: 'personal-test' },
  { re: /\bI'?ve (?:owned|tested)\b/gi,                label: 'personal-ownership' },
  { re: /\bIn my (?:testing|hands-on use|personal use)\b/gi, label: 'my-testing' },
  { re: /\bmy (?:personal )?(?:testing|hands-on)\b/gi, label: 'my-hands-on' },
  { re: /\bwhen I (?:tested|tried|installed) (?:this|it|the)\b/gi, label: 'when-i-tested' },
  { re: /\bI(?:'ve)? been (?:using|running|testing) this\b/gi, label: 'i-been-using' },
  { re: /\bafter (?:\d+ )?(?:weeks?|months?|nights?|trips?) of (?:using|testing|running) (?:this|it)\b/gi, label: 'after-N-testing' },
  { re: /\bIn my (?:experience|opinion) (?:with|using)\b/gi, label: 'my-experience-with' },
  { re: /\bMy experience with\b/gi,                    label: 'my-experience-with-2' },
  { re: /\bWhen I (?:tested|used|installed|ran)\b/gi,  label: 'when-i-used' },
]

const SOFT_PATTERNS = [
  { re: /\bI'd (?:argue|move|recommend|suggest|lean|prefer)\b/gi, label: 'id-argue' },
]

// ---------------------------------------------------------------------------
// Scan articles
// ---------------------------------------------------------------------------

const mdFiles = readdirSync(articlesDir)
  .filter(f => f.endsWith('.md'))
  .sort()

const hardViolations = []
const softViolations = []

for (const filename of mdFiles) {
  const filepath = join(articlesDir, filename)
  const text = readFileSync(filepath, 'utf8')

  // Strip frontmatter before scanning (violations in frontmatter are false positives)
  let body = text
  if (text.startsWith('---\n')) {
    const end = text.indexOf('\n---\n', 4)
    if (end !== -1) body = text.slice(end + 5)
  }

  const lines = body.split('\n')
  const slug = filename.replace(/\.md$/, '')

  for (const { re, label } of HARD_PATTERNS) {
    for (let i = 0; i < lines.length; i++) {
      re.lastIndex = 0
      const m = re.exec(lines[i])
      if (m) {
        hardViolations.push({ slug, filename, line: i + 1, match: m[0], label, context: lines[i].trim() })
      }
    }
  }

  for (const { re, label } of SOFT_PATTERNS) {
    for (let i = 0; i < lines.length; i++) {
      re.lastIndex = 0
      const m = re.exec(lines[i])
      if (m) {
        softViolations.push({ slug, filename, line: i + 1, match: m[0], label, context: lines[i].trim() })
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Console output
// ---------------------------------------------------------------------------

const BOLD   = '\x1b[1m'
const GREEN  = '\x1b[32m'
const YELLOW = '\x1b[33m'
const RED    = '\x1b[31m'
const RESET  = '\x1b[0m'

console.log(`\n${BOLD}Persona-Claim Audit — ${siteArg}${RESET}`)
console.log(`Articles scanned: ${mdFiles.length}`)
console.log(`HARD violations:  ${hardViolations.length}`)
console.log(`SOFT violations:  ${softViolations.length}\n`)

if (hardViolations.length > 0) {
  console.log(`${RED}${BOLD}HARD violations (FTC risk — exit 1):${RESET}`)
  for (const v of hardViolations) {
    console.log(`  ${RED}✗${RESET} ${v.slug}:${v.line}  [${v.label}]  "${v.match}"`)
    if (verbose) console.log(`      ${v.context}`)
  }
  console.log()
}

if (softViolations.length > 0) {
  const severity = softAsHard ? RED : YELLOW
  const label = softAsHard ? 'SOFT (treated as HARD via --soft-as-hard)' : 'SOFT violations (warnings):'
  console.log(`${severity}${BOLD}${label}${RESET}`)
  for (const v of softViolations) {
    console.log(`  ${severity}~${RESET} ${v.slug}:${v.line}  [${v.label}]  "${v.match}"`)
    if (verbose) console.log(`      ${v.context}`)
  }
  console.log()
}

const hasHardFail = hardViolations.length > 0 || (softAsHard && softViolations.length > 0)

if (hasHardFail) {
  console.log(`${RED}✗ Audit failed — fix HARD violations before deploying${RESET}`)
  process.exit(1)
} else if (softViolations.length > 0) {
  console.log(`${YELLOW}⚠ ${softViolations.length} SOFT violation(s) — add to refinement backlog${RESET}`)
} else {
  console.log(`${GREEN}✓ No persona-claim violations found${RESET}`)
}
