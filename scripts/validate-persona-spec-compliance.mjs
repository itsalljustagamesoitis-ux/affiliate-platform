#!/usr/bin/env node
/**
 * validate-persona-spec-compliance.mjs (V18) — Persona claim compliance validator.
 *
 * LLM-pass (Claude Haiku) per article. Compares first-person claims in article body
 * against the persona YAML spec. Catches semantic spec violations that regex-based
 * validators miss (e.g., wrong gear, wrong partner name, wrong location, wrong tenure).
 *
 * Usage:
 *   node scripts/validate-persona-spec-compliance.mjs --site <path>
 *   node scripts/validate-persona-spec-compliance.mjs --site <path> --file <article.md>
 *   node scripts/validate-persona-spec-compliance.mjs --site <path> --dry-run
 *   node scripts/validate-persona-spec-compliance.mjs --site <path> --concurrency 3
 *
 * Exit: 0 = all articles compliant, 1 = violations found, 2 = tool error
 *
 * Requires: ANTHROPIC_API_KEY env var or affiliate-platform/.env.local
 * Model: claude-haiku-4-5-20251001 (~$0.001/article)
 */

import { readdirSync, existsSync, readFileSync } from 'fs'
import { join, resolve, relative, dirname } from 'path'
import { fileURLToPath } from 'url'
import { createRequire } from 'module'

const require = createRequire(import.meta.url)
const matter    = require('gray-matter')
const yaml      = require('js-yaml')
import Anthropic from '@anthropic-ai/sdk'

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

// ── Auth ──────────────────────────────────────────────────────────────────────

function getApiKey() {
  if (process.env.ANTHROPIC_API_KEY) return process.env.ANTHROPIC_API_KEY

  // Fallback: read from .env.local in platform root
  const envPaths = [
    join(dirname(fileURLToPath(import.meta.url)), '..', '.env.local'),
    join(process.cwd(), '.env.local'),
  ]
  for (const p of envPaths) {
    if (existsSync(p)) {
      const match = readFileSync(p, 'utf-8').match(/^ANTHROPIC_API_KEY=(.+)$/m)
      if (match) return match[1].trim()
    }
  }
  return null
}

// ── Args ──────────────────────────────────────────────────────────────────────

const args        = process.argv.slice(2)
const get         = flag => { const i = args.indexOf(flag); return i !== -1 ? args[i + 1] : null }
const has         = flag => args.includes(flag)
const siteDir     = resolve(get('--site') ?? process.cwd())
const singleFile  = get('--file')
const dryRun      = has('--dry-run')
const concurrency = parseInt(get('--concurrency') ?? '2', 10)

const artDir   = join(siteDir, 'content', 'articles')
const prodFile = join(siteDir, 'content', 'products', 'products.yaml')
const siteCfg  = join(siteDir, 'site.config.yaml')

for (const [label, p] of [['content/articles/', artDir], ['site.config.yaml', siteCfg]]) {
  if (!existsSync(p)) {
    console.error(`${c.red('[ERROR]')} ${label} not found at ${p}`)
    process.exit(2)
  }
}

// ── Load persona YAML ─────────────────────────────────────────────────────────

let personaSlug
let personaFile
try {
  const sc = yaml.load(readFileSync(siteCfg, 'utf-8'))
  const personaVal = sc?.persona ?? sc?.site?.persona ?? null
  if (typeof personaVal === 'string') {
    personaSlug = personaVal
  } else if (personaVal && typeof personaVal === 'object' && personaVal.config_path) {
    // persona: {config_path: "config/personas/marcus.yaml"}
    personaFile = join(siteDir, personaVal.config_path)
    personaSlug = personaVal.config_path.replace(/^.*\//, '').replace(/\.yaml$/, '')
  }
  if (!personaSlug) {
    // Try portfolio.yaml for persona slug
    const portfolioPath = join(dirname(fileURLToPath(import.meta.url)), '..', 'portfolio.yaml')
    if (existsSync(portfolioPath)) {
      const port = yaml.load(readFileSync(portfolioPath, 'utf-8'))
      const siteEntry = port?.sites?.find(s => siteDir.includes(s.slug))
      personaSlug = siteEntry?.persona ?? null
    }
  }
} catch (err) {
  console.error(`${c.red('[ERROR]')} Cannot read site.config.yaml: ${err.message}`)
  process.exit(2)
}

if (!personaSlug) {
  console.error(`${c.red('[ERROR]')} Cannot determine persona slug for this site`)
  console.error('  Set persona: in site.config.yaml or portfolio.yaml')
  process.exit(2)
}

if (!personaFile) personaFile = join(siteDir, 'config', 'personas', `${personaSlug}.yaml`)
if (!existsSync(personaFile)) {
  console.error(`${c.red('[ERROR]')} Persona file not found: ${personaFile}`)
  process.exit(2)
}

let persona
try {
  persona = yaml.load(readFileSync(personaFile, 'utf-8'))
} catch (err) {
  console.error(`${c.red('[ERROR]')} Cannot parse persona YAML: ${err.message}`)
  process.exit(2)
}

// ── Persona summary builder ───────────────────────────────────────────────────

// Extract partner name from background prose using common patterns
function extractPartner(background) {
  if (!background) return null
  const m = background.match(/(?:partner|wife|husband|spouse|girlfriend|boyfriend)\s+([A-Z][a-z]+)/i)
  return m ? m[1] : null
}

// Build a compact, LLM-readable persona fact sheet
function buildPersonaSummary(persona) {
  const lines = []

  lines.push(`PERSONA: ${persona.name_formal ?? persona.slug}`)
  if (persona.role) lines.push(`ROLE: ${persona.role}`)
  if (persona.location) lines.push(`LOCATION: ${persona.location}${persona.location_detail ? ` (${persona.location_detail})` : ''}`)

  // Partner (structured field or extracted from background)
  const partnerExtracted = extractPartner(persona.background)
  if (partnerExtracted) lines.push(`PARTNER NAME: ${partnerExtracted}`)

  // Experience start
  if (persona.hobby_start_year) {
    lines.push(`HOBBY START YEAR: ${persona.hobby_start_year}`)
  }

  // Structured gear (e.g., Adrian's gear: section)
  if (persona.gear && typeof persona.gear === 'object') {
    lines.push(`\nOWNED GEAR (structured):`)
    for (const [k, v] of Object.entries(persona.gear)) {
      if (typeof v === 'string') {
        lines.push(`  ${k}: ${v}`)
      } else if (Array.isArray(v)) {
        lines.push(`  ${k}: ${v.join(', ')}`)
      }
    }
  }

  // Background prose (truncated — rich source of gear/partner/location facts)
  if (persona.background) {
    const bg = String(persona.background).replace(/\s+/g, ' ').trim().slice(0, 800)
    lines.push(`\nBACKGROUND (authoritative source for gear and personal facts):\n${bg}`)
  }

  // Defers-to list
  if (Array.isArray(persona.defers_to) && persona.defers_to.length > 0) {
    lines.push(`\nDEFERS TO (must not claim other sources as equally authoritative):`)
    for (const d of persona.defers_to) {
      const name = typeof d === 'string' ? d : d.name ?? JSON.stringify(d)
      lines.push(`  - ${name}`)
    }
  }

  // Forbidden patterns
  if (Array.isArray(persona.forbidden_patterns) && persona.forbidden_patterns.length > 0) {
    lines.push(`\nFORBIDDEN PHRASES (must never appear verbatim or paraphrased):`)
    for (const p of persona.forbidden_patterns.slice(0, 15)) {
      lines.push(`  - "${p}"`)
    }
  }

  // Editorial constraints
  if (Array.isArray(persona.editorial_constraints) && persona.editorial_constraints.length > 0) {
    lines.push(`\nEDITORIAL CONSTRAINTS:`)
    for (const ec of persona.editorial_constraints.slice(0, 8)) {
      lines.push(`  - ${ec}`)
    }
  }

  // Refuses-to-claim (e.g., Adrian)
  if (Array.isArray(persona.refuses_to_claim) && persona.refuses_to_claim.length > 0) {
    lines.push(`\nREFUSES TO CLAIM (must not pretend to own or have extensive experience with):`)
    for (const r of persona.refuses_to_claim.slice(0, 8)) {
      lines.push(`  - ${r}`)
    }
  }

  // Skipped v1.6 structured fields — warn caller
  const missingFields = []
  const v16Fields = ['owned_gear', 'family', 'home_territory', 'career', 'tenure_years']
  for (const f of v16Fields) {
    if (!persona[f]) missingFields.push(f)
  }

  return { summary: lines.join('\n'), missingFields }
}

const { summary: personaSummary, missingFields } = buildPersonaSummary(persona)

// ── Article word count helper ─────────────────────────────────────────────────

const MAX_BODY_WORDS = 1800

function prepareBody(body) {
  const words = body.trim().split(/\s+/)
  if (words.length <= MAX_BODY_WORDS) return body
  return words.slice(0, MAX_BODY_WORDS).join(' ') + '\n\n[article truncated for validation]'
}

// ── Haiku prompt ──────────────────────────────────────────────────────────────

const SYSTEM_PROMPT = `You are a fact-checker for a content review site. Your job is to detect first-person claims in articles that directly contradict a documented author persona spec.

IMPORTANT RULES:
1. Only flag DEFINITE contradictions — where the article states a specific name, product, place, or fact that directly differs from the spec.
2. Do NOT flag: ambiguous cases, style inconsistencies, products merely not mentioned in the spec (absence ≠ contradiction), hedged or uncertain claims.
3. A claim is a DEFINITE contradiction only if you can point to the specific spec line it violates.
4. False positives are worse than missed violations. When in doubt, do not flag.

Return ONLY a valid JSON object. No markdown, no explanation outside the JSON.`

function buildUserPrompt(personaSummary, articleBody) {
  return `PERSONA SPEC:
${personaSummary}

---

ARTICLE BODY (first ~${MAX_BODY_WORDS} words):
${articleBody}

---

Identify any first-person claims in the article that DIRECTLY CONTRADICT the persona spec above.

Return this JSON object:
{
  "violations": [
    {
      "category": "gear|partner|location|career|experience|defers_to|forbidden",
      "claim": "exact or near-exact quote from article (15-50 words)",
      "contradiction": "what the persona spec says that this contradicts (cite specific field)"
    }
  ]
}

If no definite contradictions found: {"violations": []}`
}

// ── JSON extraction (balanced-brace, handles trailing model commentary) ────────

function extractBalancedJson(text) {
  const start = text.indexOf('{')
  if (start === -1) return null
  let depth = 0
  let inString = false
  let escape = false
  for (let i = start; i < text.length; i++) {
    const ch = text[i]
    if (escape) { escape = false; continue }
    if (ch === '\\' && inString) { escape = true; continue }
    if (ch === '"') { inString = !inString; continue }
    if (inString) continue
    if (ch === '{') depth++
    else if (ch === '}') {
      depth--
      if (depth === 0) {
        try { return JSON.parse(text.slice(start, i + 1)) } catch { return null }
      }
    }
  }
  return null
}

// ── API client ────────────────────────────────────────────────────────────────

const apiKey = getApiKey()
if (!apiKey && !dryRun) {
  console.error(`${c.red('[ERROR]')} ANTHROPIC_API_KEY not found. Set env var or add to .env.local`)
  process.exit(2)
}

const anthropic = apiKey ? new Anthropic({ apiKey }) : null

// Cost tracking: Haiku pricing (per token)
const COST_INPUT_PER_TOKEN  = 0.00000025  // $0.25/M input
const COST_OUTPUT_PER_TOKEN = 0.00000125  // $1.25/M output
let totalInputTokens = 0
let totalOutputTokens = 0

async function checkArticle(file, body) {
  if (dryRun) {
    return { violations: [], usage: { input_tokens: 0, output_tokens: 0 } }
  }

  const prompt = buildUserPrompt(personaSummary, prepareBody(body))

  let resp
  try {
    resp = await anthropic.messages.create({
      model: 'claude-haiku-4-5-20251001',
      max_tokens: 1024,
      system: SYSTEM_PROMPT,
      messages: [{ role: 'user', content: prompt }],
    })
  } catch (err) {
    throw new Error(`API error on ${file}: ${err.message}`)
  }

  totalInputTokens  += resp.usage.input_tokens
  totalOutputTokens += resp.usage.output_tokens

  // Parse JSON response — extract balanced braces to avoid greedy-regex parse failures
  // when the model appends explanatory text after the JSON object.
  const text = resp.content[0]?.text ?? ''
  const parsed = extractBalancedJson(text)
  if (!parsed) {
    throw new Error(`Non-JSON response for ${file}: ${text.slice(0, 100)}`)
  }

  return {
    violations: Array.isArray(parsed.violations) ? parsed.violations : [],
    usage: resp.usage,
  }
}

// ── Concurrency pool ──────────────────────────────────────────────────────────

async function runPool(tasks, concurrency) {
  const results = new Array(tasks.length)
  let idx = 0

  async function worker() {
    while (idx < tasks.length) {
      const i = idx++
      results[i] = await tasks[i]()
    }
  }

  await Promise.all(Array.from({ length: concurrency }, worker))
  return results
}

// ── Main ──────────────────────────────────────────────────────────────────────

// Article list
let files
if (singleFile) {
  files = [singleFile]
} else {
  files = readdirSync(artDir).filter(f => f.endsWith('.md'))
}

console.log(`${c.dim('[V18]')} Persona spec compliance — ${c.bold(persona.name_formal ?? personaSlug)}`)
console.log(`  Site: ${relative(process.cwd(), siteDir)}`)
console.log(`  Articles: ${c.bold(String(files.length))}${dryRun ? c.yellow(' [DRY-RUN]') : ''}`)
console.log(`  Model: claude-haiku-4-5-20251001`)
if (missingFields.length > 0) {
  console.log(`  ${c.yellow('[WARN]')} v1.6 persona fields not present (skip): ${missingFields.join(', ')}`)
}
console.log()

const failures = []
const errors = []
let checkedCount = 0

const tasks = files.map(file => async () => {
  const filePath = existsSync(join(artDir, file)) ? join(artDir, file) : file
  let parsed
  try {
    parsed = matter(readFileSync(filePath, 'utf-8'))
  } catch (err) {
    errors.push(`${file}: ${err.message}`)
    return
  }

  checkedCount++
  const articleName = file.replace(/\.md$/, '')

  let result
  try {
    result = await checkArticle(file, parsed.content)
  } catch (err) {
    errors.push(`${file}: ${err.message}`)
    return
  }

  if (result.violations.length > 0) {
    failures.push({ file: articleName, violations: result.violations })
  }
})

await runPool(tasks, concurrency)

// ── Report ────────────────────────────────────────────────────────────────────

const totalCost = (totalInputTokens * COST_INPUT_PER_TOKEN) + (totalOutputTokens * COST_OUTPUT_PER_TOKEN)
const costPerArticle = checkedCount > 0 ? totalCost / checkedCount : 0

console.log(`  Articles checked:    ${c.bold(String(checkedCount))}`)
console.log(`  Tokens used:         ${totalInputTokens} in / ${totalOutputTokens} out`)
console.log(`  Total cost:          $${totalCost.toFixed(4)} (${c.dim(`$${costPerArticle.toFixed(4)}/article`)})`)

if (errors.length > 0) {
  console.log(`\n  ${c.yellow('[WARN]')} ${errors.length} article(s) had errors:`)
  for (const e of errors) console.log(`    ${c.yellow('⚠')} ${e}`)
}

const fpRate = checkedCount > 0 ? (failures.length / checkedCount * 100).toFixed(1) : '0.0'

if (failures.length === 0) {
  console.log(`\n  ${c.green('✓')} All ${checkedCount} articles comply with persona spec`)
  console.log(`  ${c.dim(`False positive rate: 0/${checkedCount} (0.0%)`)}`)
  process.exit(0)
}

console.log(`\n  ${c.red('[FAIL]')} ${failures.length}/${checkedCount} articles have persona spec violations (${fpRate}% rate):\n`)

for (const { file, violations } of failures) {
  console.log(`  ${c.bold(file)}`)
  for (const v of violations) {
    console.log(`    ${c.red('✗')} [${v.category}] "${v.claim}"`)
    console.log(`      ${c.dim('→')} ${v.contradiction}`)
  }
  console.log()
}

const budgetStatus = parseFloat(fpRate) <= 2.0 ? c.green('within budget (<2%)') : c.red('OVER BUDGET (>2%)')
console.log(`  False positive rate: ${fpRate}% — ${budgetStatus}`)
console.log(`  ${c.red('[V18 FAIL]')} ${failures.length}/${checkedCount} articles failed persona spec compliance`)
process.exit(1)
