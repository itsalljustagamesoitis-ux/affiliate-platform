#!/usr/bin/env node
/**
 * validate-persona-claims.mjs
 *
 * Audits published article markdown files for first-person persona-claim violations.
 *
 * Three violation tiers:
 *   HARD – FTC-risk claims of personal product testing or ownership.
 *           High-confidence patterns. Exit 1 if any found after bypass checks.
 *   REVIEW – Carry/kit/pack ownership signals needing human confirmation.
 *           Lower confidence; many legitimate uses. Exit 0, printed as review queue.
 *   SOFT – Editorial voice violations ("I'd argue", etc.).
 *           Exit 0 but print warning count.
 *
 * Suppression (applied to HARD only):
 *   OWNED GEAR BYPASS — if owned_gear item words appear within ±2 lines of a HARD
 *   match, suppress (persona is referencing legitimately owned gear).
 *   HEDGING BYPASS — if hedging language appears within ±3 lines of a HARD match,
 *   suppress (editorial_constraints permit hedged claims for non-owned gear).
 *
 * Usage:
 *   node scripts/validate-persona-claims.mjs --site ridgelinebushcraft
 *   node scripts/validate-persona-claims.mjs --site ridgelinebushcraft --persona config/personas/wesley-tate.yaml
 *   node scripts/validate-persona-claims.mjs --site ridgelinebushcraft --verbose
 *   node scripts/validate-persona-claims.mjs --site ridgelinebushcraft --soft-as-hard
 *
 * Exit codes:
 *   0 – no HARD violations (REVIEW/SOFT printed as informational)
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
const get        = flag => { const i = args.indexOf(flag); return i !== -1 ? args[i + 1] : null }
const siteArg    = get('--site')
const personaArg = get('--persona')
const verbose    = args.includes('--verbose')
const softAsHard = args.includes('--soft-as-hard')
const jsonMode   = args.includes('--json')
const logCalibration = args.includes('--log-calibration')

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
// Load owned gear list from persona YAML
// ---------------------------------------------------------------------------

function loadOwnedGear(siteRoot, personaArg) {
  let personaPath = personaArg ? join(siteRoot, personaArg) : null
  if (!personaPath) {
    const personaDir = join(siteRoot, 'config', 'personas')
    if (existsSync(personaDir)) {
      const yamlFiles = readdirSync(personaDir).filter(f => f.endsWith('.yaml'))
      if (yamlFiles.length === 1) personaPath = join(personaDir, yamlFiles[0])
    }
  }
  if (!personaPath || !existsSync(personaPath)) return []

  try {
    const text = readFileSync(personaPath, 'utf8')
    const match = text.match(/^owned_gear:\n((?:  - .+\n?)*)/m)
    if (!match) return []
    return match[1]
      .split('\n')
      .filter(l => l.trim().startsWith('- '))
      .map(l => l.replace(/^\s*- /, '').trim())
      .filter(Boolean)
  } catch {
    return []
  }
}

const ownedGear = loadOwnedGear(siteRoot, personaArg)

// Build keyword list: split each owned_gear item into individual words >= 4 chars.
// This handles model numbers like "Bahco BAH396LAP Laplander" where the exact phrase
// "Bahco Laplander" doesn't appear as a substring.
const ownedGearKeywords = [...new Set(
  ownedGear.flatMap(g => g.split(/\s+/).filter(w => w.length >= 4))
)]

// ---------------------------------------------------------------------------
// Pattern definitions
// ---------------------------------------------------------------------------

// HARD: high-confidence FTC-risk patterns.
// Original v1.0 patterns (explicit testing/ownership language) + v1.1 additions
// for "I've carried" and "I've worn" which the original missed.
// v1.2 (B42) — possessive place/equipment ownership: my garage, my kitchen, etc.
const HARD_PATTERNS = [
  // v1.0 — explicit testing/ownership
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
  // v1.1 — Wesley's primary carry/wear ownership signals missing from v1.0.
  // These are documented in allowed_patterns YAML but were never validated.
  // UAT Cases: "I've carried one into the GW" (katadyn); "I've worn" (clothing).
  { re: /\bI'?ve carried\b/gi,                         label: 'carried-ownership' },
  { re: /\bI'?ve worn\b/gi,                            label: 'worn-ownership' },
  // v1.2 — B42: possessive place/equipment ownership not caught by v1.1.
  // headingSkip skips lines starting with '#' (FAQ headers like
  // '### How do I heat my garage?' are questions, not ownership claims).
  { re: /\bmy (?:garage(?: gym)?|home gym|kitchen|workshop|listening room|workout room|setup)\b/gi,
    label: 'possessive-place', headingSkip: true },
]

// REVIEW: medium-confidence ownership signals. Higher false positive rate — Wesley
// legitimately says these about his owned gear. Printed separately for human triage.
// Example: "I carry a BIC lighter" (fabrication) vs "I carry the Bahco into the GW" (owned).
const REVIEW_PATTERNS = [
  { re: /\bI carry\b/gi,                               label: 'carry' },
  { re: /\bI keep\b/gi,                                label: 'keep' },
  { re: /\bin my (?:kit|pack|bag)\b/gi,                label: 'in-my-kit' },
  { re: /\bI pack\b/gi,                                label: 'pack' },
  { re: /\bI run (?:a|the|my)\b/gi,                    label: 'run-a' },
  { re: /\bI rely on (?:a|the|my)\b/gi,                label: 'rely-on' },
  { re: /\bI reach for (?:a|the|my)\b/gi,              label: 'reach-for' },
]

const SOFT_PATTERNS = [
  { re: /\bI'd (?:argue|move|recommend|suggest|lean|prefer)\b/gi, label: 'id-argue' },
]

// Hedging — if present within ±3 lines of a HARD match, suppress the violation.
const HEDGING_PATTERNS = [
  /\bI haven'?t (?:used|owned|tested|carried|handled|had hands on) (?:this|it|one|these)/i,
  /\bI don'?t own\b/i,
  /\bhaven'?t (?:put|had) (?:this |it |one )(?:in the field|hands on|personally)\b/i,
  /\bcan'?t speak from personal experience\b/i,
  /\bI haven'?t personally\b/i,
  /\bI don'?t have personal experience\b/i,
  /\bpulled from what I'?ve read\b/i,
  /\bmy experience ends\b/i,
  /\bhaven'?t personally (?:owned|tested|carried|used|worn)\b/i,
  /\bI haven'?t put (?:this|one) (?:in the field|through)\b/i,
]

// ---------------------------------------------------------------------------
// Context window helpers
// ---------------------------------------------------------------------------

function getLines(lines, idx, radius) {
  const start = Math.max(0, idx - radius)
  const end   = Math.min(lines.length - 1, idx + radius)
  return lines.slice(start, end + 1).join(' ')
}

// Word-by-word owned gear check: split gear item into words >= 4 chars,
// require ALL of them appear in context (handles "Bahco BAH396LAP Laplander"
// where exact phrase "Bahco Laplander" is not a substring).
function isOwnedGearContext(context) {
  if (ownedGear.length === 0) return false
  const lower = context.toLowerCase()
  return ownedGear.some(g => {
    const words = g.toLowerCase().split(/\s+/).filter(w => w.length >= 4)
    return words.length > 0 && words.every(w => lower.includes(w))
  })
}

function isHedgedContext(context) {
  return HEDGING_PATTERNS.some(p => p.test(context))
}

// ---------------------------------------------------------------------------
// Scan articles
// ---------------------------------------------------------------------------

const mdFiles = readdirSync(articlesDir)
  .filter(f => f.endsWith('.md'))
  .sort()

const hardViolations   = []
const reviewViolations = []
const softViolations   = []
let suppressedCount = 0

for (const filename of mdFiles) {
  const filepath = join(articlesDir, filename)
  const text = readFileSync(filepath, 'utf8')

  let body = text
  if (text.startsWith('---\n')) {
    const end = text.indexOf('\n---\n', 4)
    if (end !== -1) body = text.slice(end + 5)
  }

  const lines = body.split('\n')
  const slug = filename.replace(/\.md$/, '')

  for (const { re, label, headingSkip } of HARD_PATTERNS) {
    for (let i = 0; i < lines.length; i++) {
      if (headingSkip && /^#+\s/.test(lines[i])) continue
      re.lastIndex = 0
      const m = re.exec(lines[i])
      if (!m) continue

      const nearContext = getLines(lines, i, 2)
      if (isOwnedGearContext(nearContext)) { suppressedCount++; continue }

      const wideContext = getLines(lines, i, 3)
      if (isHedgedContext(wideContext)) { suppressedCount++; continue }

      hardViolations.push({ slug, filename, line: i + 1, match: m[0], label, context: lines[i].trim() })
    }
  }

  for (const { re, label } of REVIEW_PATTERNS) {
    for (let i = 0; i < lines.length; i++) {
      re.lastIndex = 0
      const m = re.exec(lines[i])
      if (!m) continue
      // Suppress REVIEW items that clearly reference owned gear
      const nearContext = getLines(lines, i, 2)
      if (isOwnedGearContext(nearContext)) continue
      reviewViolations.push({ slug, filename, line: i + 1, match: m[0], label, context: lines[i].trim() })
    }
  }

  for (const { re, label } of SOFT_PATTERNS) {
    for (let i = 0; i < lines.length; i++) {
      re.lastIndex = 0
      const m = re.exec(lines[i])
      if (m) softViolations.push({ slug, filename, line: i + 1, match: m[0], label, context: lines[i].trim() })
    }
  }
}

// ---------------------------------------------------------------------------
// JSON output (--json mode: used by orchestrator; suppresses all terminal output)
// ---------------------------------------------------------------------------

const hasHardFail = hardViolations.length > 0 || (softAsHard && softViolations.length > 0)

if (jsonMode) {
  process.stdout.write(JSON.stringify({
    fail_count: hardViolations.length + (softAsHard ? softViolations.length : 0),
    failures: hardViolations.map(v => ({ id: v.slug, file: v.filename, line: v.line, label: v.label, match: v.match })),
    review_count: reviewViolations.length,
    soft_count: softViolations.length,
    suppressed: suppressedCount,
  }) + '\n')
  process.exit(hasHardFail ? 1 : 0)
}

// ---------------------------------------------------------------------------
// Console output
// ---------------------------------------------------------------------------

const BOLD   = '\x1b[1m'
const GREEN  = '\x1b[32m'
const YELLOW = '\x1b[33m'
const RED    = '\x1b[31m'
const CYAN   = '\x1b[36m'
const DIM    = '\x1b[2m'
const RESET  = '\x1b[0m'

const ownedGearNote = ownedGear.length > 0
  ? `Owned gear: ${ownedGear.join(', ')}`
  : 'No owned_gear in persona YAML — all ownership claims evaluated'

console.log(`\n${BOLD}Persona-Claim Audit — ${siteArg}${RESET}`)
console.log(`${DIM}${ownedGearNote}${RESET}`)
console.log(`Articles scanned: ${mdFiles.length}`)
console.log(`Suppressed (owned gear or hedged): ${suppressedCount}`)
console.log(`HARD violations:  ${hardViolations.length}`)
console.log(`REVIEW items:     ${reviewViolations.length}  ${DIM}(need human triage — owned gear context may apply)${RESET}`)
console.log(`SOFT violations:  ${softViolations.length}\n`)

if (hardViolations.length > 0) {
  console.log(`${RED}${BOLD}HARD violations (FTC risk — exit 1):${RESET}`)
  for (const v of hardViolations) {
    console.log(`  ${RED}✗${RESET} ${v.slug}:${v.line}  [${v.label}]  "${v.match}"`)
    if (verbose) console.log(`      ${v.context}`)
  }
  console.log()
}

if (reviewViolations.length > 0 && verbose) {
  console.log(`${CYAN}${BOLD}REVIEW items (carry/keep/pack — human triage needed):${RESET}`)
  for (const v of reviewViolations) {
    console.log(`  ${CYAN}?${RESET} ${v.slug}:${v.line}  [${v.label}]  "${v.match}"`)
    console.log(`      ${v.context}`)
  }
  console.log()
}

if (softViolations.length > 0) {
  const severity = softAsHard ? RED : YELLOW
  const label = softAsHard ? 'SOFT (treated as HARD)' : 'SOFT violations (warnings):'
  console.log(`${severity}${BOLD}${label}${RESET}`)
  for (const v of softViolations) {
    console.log(`  ${severity}~${RESET} ${v.slug}:${v.line}  [${v.label}]  "${v.match}"`)
    if (verbose) console.log(`      ${v.context}`)
  }
  console.log()
}

if (logCalibration) {
  const { appendFileSync, mkdirSync } = await import('fs')
  const { join: pathJoin, dirname: pathDirname } = await import('path')
  const { homedir } = await import('os')
  const logPath = pathJoin(homedir(), 'affiliate-platform', 'logs', 'validator_calibration.jsonl')
  try {
    mkdirSync(pathDirname(logPath), { recursive: true })
    const record = JSON.stringify({
      ts:      new Date().toISOString(),
      site:    siteArg,
      hard:    hardViolations.length,
      review:  reviewViolations.length,
      soft:    softViolations.length,
      articles: mdFiles.length,
    })
    appendFileSync(logPath, record + '\n', 'utf8')
  } catch {}
}

if (hasHardFail) {
  console.log(`${RED}✗ Audit failed — fix HARD violations before deploying${RESET}`)
  process.exit(1)
} else if (softViolations.length > 0 || reviewViolations.length > 0) {
  console.log(`${YELLOW}⚠ Review queue: ${reviewViolations.length} carry/keep/pack items + ${softViolations.length} SOFT violations${RESET}`)
} else {
  console.log(`${GREEN}✓ No persona-claim violations found${RESET}`)
}
