#!/usr/bin/env node
/**
 * validate-card-voice.mjs (V21) — Product card first-person voice density check.
 *
 * Pattern-matching validator: scans buyer-guide product card sections for first-
 * person pronoun usage. Below-threshold articles are logged as WARN (soft fail).
 * Never exits 1 — does not block deploy.
 *
 * Card detection: H3 sections (###) whose body contains a "(product:slug)" CTA.
 * Any H3 section without that CTA (buying-guide subsections, FAQ headers, etc.)
 * is not counted as a product card.
 *
 * Persona pronouns: reads "first_person_pronouns" from the locked persona YAML
 * (v1.6 field). Falls back to English defaults if field is absent.
 *
 * Threshold: (cards with ≥1 first-person hit) / total_cards >= 1/3
 * i.e., at least one card in every group of three must have first-person voice.
 *
 * Usage:
 *   node scripts/validate-card-voice.mjs --site <siteDir>
 *   node scripts/validate-card-voice.mjs --site <siteDir> --file <article.md>
 *   node scripts/validate-card-voice.mjs --site <siteDir> --type buyer_guide,roundup
 *   node scripts/validate-card-voice.mjs --site <siteDir> --log-file <path>
 *
 * Exit: always 0 (SOFT fail — logs [WARN] but never blocks deploy)
 * Writes: <siteDir>/data/v21-calibration-log.yaml (or --log-file path)
 */

import { readdirSync, existsSync, readFileSync, writeFileSync, mkdirSync } from 'fs'
import { join, dirname } from 'path'
import { fileURLToPath } from 'url'
import { createRequire } from 'module'

const require = createRequire(import.meta.url)
const matter  = require('gray-matter')
const yaml    = require('js-yaml')

// ── ANSI helpers ──────────────────────────────────────────────────────────────

const isTTY = process.stdout.isTTY
const esc   = isTTY ? (s, code) => `\x1b[${code}m${s}\x1b[0m` : s => s
const c = {
  yellow: s => esc(s, '33'),
  green:  s => esc(s, '32'),
  dim:    s => esc(s, '2'),
  bold:   s => esc(s, '1'),
  cyan:   s => esc(s, '36'),
}

// ── Constants ─────────────────────────────────────────────────────────────────

// Minimum (fp_cards / total_cards) for an article to pass.
// "1 first-person card per 3 cards on average."
const THRESHOLD = 1 / 3

// Used when persona YAML lacks the v1.6 "first_person_pronouns" field.
const DEFAULT_PRONOUNS = [
  'I', 'my', 'me', 'myself', 'mine',
  "I've", "I'm", "I'd", "I'll",
]

// Matches the inline product CTA format: (product:slug)
const PRODUCT_CTA_RE = /\(product:[^)]+\)/

// ── CLI parsing ───────────────────────────────────────────────────────────────

const args = process.argv.slice(2)
const opts = {
  siteDir:    null,
  singleFile: null,
  types:      ['buyer_guide'],
  logFile:    null,
}

for (let i = 0; i < args.length; i++) {
  switch (args[i]) {
    case '--site':     opts.siteDir    = args[++i]; break
    case '--file':     opts.singleFile = args[++i]; break
    case '--type':     opts.types      = args[++i].split(',').map(t => t.trim()); break
    case '--log-file': opts.logFile    = args[++i]; break
    default:
      if (!args[i].startsWith('--')) opts.siteDir = args[i]
  }
}

if (!opts.siteDir) {
  console.error('[V21] Usage: validate-card-voice.mjs --site <siteDir> [--file <path>] [--type <types>] [--log-file <path>]')
  process.exit(0)
}

// ── Persona loading ───────────────────────────────────────────────────────────

function loadPersona(siteDir) {
  const siteCfg = join(siteDir, 'site.config.yaml')
  if (!existsSync(siteCfg)) return null

  let personaFile = null
  try {
    const sc = yaml.load(readFileSync(siteCfg, 'utf-8'))
    const personaVal = sc?.persona ?? sc?.site?.persona ?? null
    if (typeof personaVal === 'string') {
      personaFile = join(siteDir, 'config', 'personas', `${personaVal}.yaml`)
    } else if (personaVal?.config_path) {
      personaFile = join(siteDir, personaVal.config_path)
    }
  } catch { /* ignore */ }

  if (!personaFile || !existsSync(personaFile)) return null
  try {
    return yaml.load(readFileSync(personaFile, 'utf-8'))
  } catch {
    return null
  }
}

function getPronouns(persona) {
  const fp = persona?.first_person_pronouns
  if (Array.isArray(fp) && fp.length > 0) return fp
  return DEFAULT_PRONOUNS
}

// ── Card detection ────────────────────────────────────────────────────────────
//
// Walk the markdown body line by line tracking the current H3 heading and its
// accumulated lines. On every H2 or H3 boundary, commit the previous section.
// A section is classified as a product card only if its body contains the
// "(product:slug)" CTA pattern. H2 resets context without adding a card.
// H3 sections without a CTA (buying-guide subsections, etc.) are not cards.

function extractProductCards(body) {
  const lines  = body.split('\n')
  const cards  = []
  let heading  = null
  let accLines = []

  function commit() {
    if (heading === null) return
    const sectionBody = accLines.join('\n')
    if (PRODUCT_CTA_RE.test(sectionBody)) {
      cards.push({ heading, body: sectionBody })
    }
  }

  for (const line of lines) {
    if (line.startsWith('### ')) {
      commit()
      heading  = line.slice(4).trim()
      accLines = []
    } else if (line.startsWith('## ')) {
      commit()
      heading  = null   // H2 is a section divider; not itself a card
      accLines = []
    } else {
      accLines.push(line)
    }
  }
  commit()

  return cards
}

// ── First-person detection ────────────────────────────────────────────────────
//
// Build one regex per pronoun. For "I" (always capitalised as subject pronoun),
// match case-sensitively. All others match case-insensitively.
//
// Boundary: (?<![a-zA-Z0-9]) / (?![a-zA-Z0-9]) rather than \b, so that
// apostrophe-based contractions (I've, I'm) are handled correctly — the
// apostrophe is not a word character and does not create a false boundary.
//
// Curly apostrophes (U+2018, U+2019) are normalised to straight before matching.

function buildRegexes(pronouns) {
  return pronouns.map(pronoun => {
    const esc = pronoun
      .replace(/[.*+?^${}()|[\]\\]/g, '\\$&')  // escape regex special chars
      .replace(/'/g, "['’]")               // straight or right curly apostrophe
    const flags = (pronoun === 'I') ? '' : 'i'
    return new RegExp(`(?<![a-zA-Z0-9])${esc}(?![a-zA-Z0-9])`, flags)
  })
}

function cardHasFirstPerson(cardBody, regexes) {
  const text = cardBody.replace(/[‘‛]/g, "'")  // normalise left curly → straight
  return regexes.some(re => re.test(text))
}

// ── Article check ─────────────────────────────────────────────────────────────

function checkArticle(filePath, regexes) {
  let parsed
  try {
    parsed = matter(readFileSync(filePath, 'utf-8'))
  } catch {
    return null
  }

  const fm = parsed.data
  if (!opts.types.includes(fm.type)) return null   // skip non-target types

  const cards = extractProductCards(parsed.content)
  if (cards.length === 0) return null              // no product cards found

  let fpCards = 0
  const cardDetail = []
  for (const card of cards) {
    const hasFP = cardHasFirstPerson(card.body, regexes)
    if (hasFP) fpCards++
    cardDetail.push({ heading: card.heading.slice(0, 60), has_fp: hasFP })
  }

  const density = fpCards / cards.length
  const pass    = density >= THRESHOLD

  return {
    slug:        fm.slug ?? filePath.split('/').pop().replace('.md', ''),
    type:        fm.type,
    cards:       cards.length,
    fp_cards:    fpCards,
    density:     Math.round(density * 1000) / 1000,
    pass,
    card_detail: cardDetail,
  }
}

// ── Main ──────────────────────────────────────────────────────────────────────

function main() {
  const persona     = loadPersona(opts.siteDir)
  const pronouns    = getPronouns(persona)
  const regexes     = buildRegexes(pronouns)
  const personaSlug = persona?.slug ?? 'unknown'

  if (!persona) {
    console.warn(`[V21] ${c.yellow('[WARN]')} No persona found for site — using default pronouns`)
  } else if (!persona.first_person_pronouns) {
    console.log(`[V21] ${c.dim('[INFO]')} first_person_pronouns not in persona YAML (v1.6 field) — using defaults`)
  }

  // Collect files
  let files = []
  if (opts.singleFile) {
    files = [opts.singleFile]
  } else {
    const articlesDir = join(opts.siteDir, 'content', 'articles')
    if (!existsSync(articlesDir)) {
      console.error(`[V21] No articles directory: ${articlesDir}`)
      process.exit(0)
    }
    files = readdirSync(articlesDir)
      .filter(f => f.endsWith('.md'))
      .map(f => join(articlesDir, f))
  }

  let checked   = 0
  let warnCount = 0
  let skipped   = 0
  const entries = []

  for (const fp of files) {
    let result
    try {
      result = checkArticle(fp, regexes)
    } catch (err) {
      console.warn(`[V21] ${c.yellow('[WARN]')} Parse error ${fp.split('/').pop()}: ${err.message}`)
      skipped++
      continue
    }

    if (result === null) { skipped++; continue }

    checked++
    entries.push(result)

    if (!result.pass) {
      warnCount++
      console.log(
        `[V21] ${c.yellow('[WARN]')} ${result.slug}: ` +
        `${result.fp_cards}/${result.cards} fp-cards ` +
        `(density ${result.density.toFixed(3)} < ${THRESHOLD.toFixed(3)})`
      )
    }
  }

  // ── Summary ──────────────────────────────────────────────────────────────────
  const passCount  = checked - warnCount
  const passRate   = checked > 0 ? (passCount / checked * 100).toFixed(1) : 'N/A'
  const avgDensity = checked > 0
    ? entries.reduce((s, e) => s + e.density, 0) / checked
    : 0

  console.log('')
  console.log(`[V21] Persona:           ${c.bold(personaSlug)}`)
  console.log(`[V21] Pronouns:          ${pronouns.join(', ')}`)
  console.log(`[V21] Types checked:     ${opts.types.join(', ')}`)
  console.log(`[V21] Articles checked:  ${checked} (${skipped} skipped — wrong type or 0 cards)`)
  console.log(`[V21] Threshold:         ≥ ${THRESHOLD.toFixed(3)} fp-cards/card`)
  console.log(`[V21] Avg fp density:    ${avgDensity.toFixed(3)} fp-cards/card`)
  console.log(`[V21] WARN (low voice):  ${warnCount}/${checked} (${(warnCount / Math.max(checked, 1) * 100).toFixed(1)}%)`)
  console.log(`[V21] Pass rate:         ${passRate}%`)

  // ── Calibration log ───────────────────────────────────────────────────────────
  const logPath = opts.logFile ?? join(opts.siteDir, 'data', 'v21-calibration-log.yaml')

  const logData = {
    generated_at:   new Date().toISOString(),
    site:           opts.siteDir.split('/').pop(),
    persona:        personaSlug,
    pronouns_used:  pronouns,
    types_checked:  opts.types,
    threshold:      THRESHOLD,
    summary: {
      articles_checked: checked,
      articles_skipped: skipped,
      warn_count:       warnCount,
      warn_rate:        checked > 0 ? Math.round(warnCount / checked * 1000) / 1000 : 0,
      pass_count:       passCount,
      pass_rate:        checked > 0 ? Math.round(passCount / checked * 1000) / 1000 : 0,
      avg_fp_density:   Math.round(avgDensity * 1000) / 1000,
    },
    articles: entries,
  }

  try {
    const logDir = logPath.split('/').slice(0, -1).join('/')
    if (logDir && !existsSync(logDir)) mkdirSync(logDir, { recursive: true })
    writeFileSync(logPath, yaml.dump(logData, { lineWidth: 120 }))
    console.log(`[V21] Calibration log:   ${logPath}`)
  } catch (err) {
    console.warn(`[V21] ${c.yellow('[WARN]')} Could not write calibration log: ${err.message}`)
  }

  // SOFT fail — always exit 0
  process.exit(0)
}

main()
