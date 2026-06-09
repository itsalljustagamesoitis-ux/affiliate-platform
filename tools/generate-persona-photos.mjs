#!/usr/bin/env node
/**
 * generate-persona-photos.mjs — Generate DALL-E 3 persona byline and about photos.
 *
 * Usage:
 *   node tools/generate-persona-photos.mjs --site <slug>
 *   node tools/generate-persona-photos.mjs --site <slug> --dry-run
 *   node tools/generate-persona-photos.mjs --site <slug> --test-dir /tmp/test-photos
 *   node tools/generate-persona-photos.mjs --site <slug> --type byline
 *   node tools/generate-persona-photos.mjs --site <slug> --type about
 *
 * Requires: OPENAI_API_KEY in environment or ~/affiliate-platform/.env.local
 *
 * Outputs (production mode):
 *   <siteDir>/public/images/brand/<persona-slug>-byline.jpg   (1024×1024)
 *   <siteDir>/public/images/brand/<persona-slug>-about.jpg    (1792×1024)
 *
 * Outputs (test mode --test-dir):
 *   <testDir>/<persona-slug>-byline.jpg
 *   <testDir>/<persona-slug>-about.jpg
 *
 * MD5 uniqueness check: Generated images are compared against all existing
 * portfolio persona photos. A collision triggers a regeneration (max 3 tries).
 * In practice, DALL-E 3 collision probability is negligible; this check confirms
 * the file was actually generated fresh and differs from any existing image.
 *
 * Prompt template: templates/persona-photo-prompt.md
 * See that file for variable documentation and niche-specific defaults.
 *
 * Exit: 0 = success, 1 = generation issue, 2 = tool error
 */

import { existsSync, readFileSync, writeFileSync, mkdirSync } from 'fs'
import { join, dirname, resolve } from 'path'
import { fileURLToPath } from 'url'
import { createHash } from 'crypto'
import { homedir } from 'os'
import { createRequire } from 'module'
import OpenAI from 'openai'
import { loadPortfolio } from './lib/portfolio.mjs'

const require      = createRequire(import.meta.url)
const yaml         = require('js-yaml')
const TOOLS_DIR    = dirname(fileURLToPath(import.meta.url))
const PLATFORM_DIR = join(TOOLS_DIR, '..')
const TEMPLATE_PATH = join(PLATFORM_DIR, 'templates', 'persona-photo-prompt.md')

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

// ── Auth ──────────────────────────────────────────────────────────────────────

function getApiKey() {
  if (process.env.OPENAI_API_KEY) return process.env.OPENAI_API_KEY
  const candidates = [
    join(PLATFORM_DIR, '.env.local'),
    join(process.cwd(), '.env.local'),
  ]
  for (const p of candidates) {
    if (existsSync(p)) {
      const match = readFileSync(p, 'utf-8').match(/^OPENAI_API_KEY=(.+)$/m)
      if (match) return match[1].trim()
    }
  }
  return null
}

// ── Args ──────────────────────────────────────────────────────────────────────

const args    = process.argv.slice(2)
const get     = flag => { const i = args.indexOf(flag); return i !== -1 ? args[i + 1] : null }
const has     = flag => args.includes(flag)

const siteSlug  = get('--site')
const testDir   = get('--test-dir') ? resolve(get('--test-dir')) : null
const dryRun    = has('--dry-run')
const typeFilter = get('--type')   // 'byline', 'about', or null (both)
const force     = has('--force')

if (!siteSlug) {
  console.error('Usage: node tools/generate-persona-photos.mjs --site <slug> [--dry-run] [--test-dir <path>] [--type byline|about] [--force]')
  console.error('Requires: OPENAI_API_KEY in environment or affiliate-platform/.env.local')
  process.exit(2)
}

// ── Resolve site ──────────────────────────────────────────────────────────────

let sites
try { sites = loadPortfolio() } catch (err) {
  console.error(`${c.red('[ERROR]')} Cannot load portfolio.yaml: ${err.message}`)
  process.exit(2)
}
if (!sites.find(s => s.slug === siteSlug)) {
  console.error(`${c.red('[ERROR]')} Site "${siteSlug}" not found in portfolio.yaml`)
  process.exit(2)
}

const siteDir = join(homedir(), siteSlug)
const siteCfg = join(siteDir, 'site.config.yaml')
if (!existsSync(siteCfg)) {
  console.error(`${c.red('[ERROR]')} site.config.yaml not found at ${siteCfg}`)
  process.exit(2)
}

// ── Load persona ──────────────────────────────────────────────────────────────

let personaSlug, personaFile, persona, siteConfig
try {
  siteConfig = yaml.load(readFileSync(siteCfg, 'utf-8'))
  const personaVal = siteConfig?.persona ?? siteConfig?.site?.persona ?? null
  if (typeof personaVal === 'string') {
    personaSlug = personaVal
  } else if (personaVal?.config_path) {
    personaFile = join(siteDir, personaVal.config_path)
    personaSlug = personaVal.config_path.replace(/^.*\//, '').replace(/\.yaml$/, '')
  }
  if (!personaFile) personaFile = join(siteDir, 'config', 'personas', `${personaSlug}.yaml`)
  persona = yaml.load(readFileSync(personaFile, 'utf-8'))
} catch (err) {
  console.error(`${c.red('[ERROR]')} Cannot load persona: ${err.message}`)
  process.exit(2)
}

// ── Template loading ──────────────────────────────────────────────────────────

/**
 * Parses templates/persona-photo-prompt.md.
 * Returns { byline: string, about: string, niches: {[key]: {setting_byline, setting_about, action_description}} }
 */
function loadTemplate() {
  if (!existsSync(TEMPLATE_PATH)) {
    throw new Error(`Prompt template not found at ${TEMPLATE_PATH}`)
  }
  const raw = readFileSync(TEMPLATE_PATH, 'utf-8')

  const bylineMatch = raw.match(/## Byline prompt template\n\n(.+?)(?=\n\n##|\n\n---)/s)
  const aboutMatch  = raw.match(/## About page prompt template\n\n(.+?)(?=\n\n##|\n\n---)/s)
  if (!bylineMatch || !aboutMatch) {
    throw new Error('Template missing required "## Byline prompt template" or "## About page prompt template" section')
  }

  // Split on ### headers within the Niche defaults section
  const nicheSection = raw.match(/## Niche defaults\n[\s\S]+/)?.[0] ?? ''
  const niches = {}
  for (const block of nicheSection.split(/(?=^### )/m).filter(s => s.startsWith('### '))) {
    const lines = block.split('\n').filter(Boolean)
    const nicheKey = lines[0].replace(/^### /, '').trim()
    const fields = {}
    for (const line of lines.slice(1)) {
      const m = line.match(/^(setting_byline|setting_about|action_description):\s+(.+)$/)
      if (m) fields[m[1]] = m[2]
    }
    if (nicheKey) niches[nicheKey] = fields
  }

  return { byline: bylineMatch[1].trim(), about: aboutMatch[1].trim(), niches }
}

// ── Variable derivation ───────────────────────────────────────────────────────

function extractAgeRange(personaObj) {
  // Search bio_full first (present-tense current age), then background (may have historical ages)
  const sources = [
    String(personaObj.bio_full ?? ''),
    String(personaObj.bio ?? ''),
    String(personaObj.background ?? ''),
  ]
  const AGE_RE = /\b(\d{2})-year-old/

  for (const text of sources) {
    const match = text.match(AGE_RE)
    if (match) {
      const age = parseInt(match[1])
      if (age < 25) return 'early 20s'
      if (age < 30) return 'late 20s'
      if (age < 35) return 'early 30s'
      if (age < 40) return 'late 30s'
      if (age < 45) return 'early 40s'
      if (age < 50) return 'late 40s'
      if (age < 55) return 'early 50s'
      if (age < 60) return 'late 50s'
      return 'early 60s'
    }
  }
  return null
}

function buildVariables(tmpl, personaObj, siteCfgObj) {
  const niche    = siteCfgObj?.site?.niche ?? 'default'
  const defaults = tmpl.niches[niche] ?? tmpl.niches['default'] ?? {}
  const ageRange = extractAgeRange(personaObj)

  return {
    name:               personaObj.name_formal ?? personaObj.name_used ?? 'the subject',
    role:               personaObj.role ?? 'hobbyist',
    location:           personaObj.location ?? '',
    age_descriptor:     ageRange
      ? `${/^[aeiou]/i.test(ageRange) ? 'an' : 'a'} ${ageRange} person`
      : 'a person',
    setting_byline:     defaults.setting_byline     ?? 'home office with soft natural light',
    setting_about:      defaults.setting_about      ?? 'a well-appointed workspace',
    action_description: defaults.action_description ?? 'engaged in their hobby',
  }
}

function renderPrompt(template, vars) {
  return template.replace(/\{\{(\w+)\}\}/g, (_, key) => vars[key] ?? `{{${key}}}`)
}

// ── MD5 helpers ───────────────────────────────────────────────────────────────

function md5file(filePath) {
  return createHash('md5').update(readFileSync(filePath)).digest('hex')
}

function md5buf(buf) {
  return createHash('md5').update(buf).digest('hex')
}

/**
 * Collects MD5s of all existing persona photos across the portfolio,
 * optionally excluding the current site's own photos (used for "is this a
 * re-generation?" check — we want to know if it differs from the old photo).
 */
function collectPortfolioMd5s(excludeSiteDir) {
  const hashes = new Map()   // md5 → filepath
  let allSites
  try { allSites = loadPortfolio() } catch { return hashes }

  for (const site of allSites) {
    const dir = join(homedir(), site.slug)
    const brandDir = join(dir, 'public', 'images', 'brand')
    if (!existsSync(brandDir)) continue
    for (const name of ['persona-byline.jpg', 'persona-about.jpg',
                        `${site.persona}-byline.jpg`, `${site.persona}-about.jpg`]) {
      const p = join(brandDir, name)
      if (existsSync(p)) hashes.set(md5file(p), p)
    }
  }
  return hashes
}

// ── Image generation ──────────────────────────────────────────────────────────

/**
 * Calls DALL-E 3 and returns the image buffer.
 * Retries on MD5 collision with portfolio (max 3 attempts).
 */
async function generateImage(client, prompt, size, portfolioMd5s, label) {
  const MAX_ATTEMPTS = 3

  for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
    const response = await client.images.generate({
      model:           'dall-e-3',
      prompt,
      n:               1,
      size,
      quality:         'standard',
      response_format: 'b64_json',
    })

    const buf  = Buffer.from(response.data[0].b64_json, 'base64')
    const hash = md5buf(buf)

    if (portfolioMd5s.has(hash)) {
      const collision = portfolioMd5s.get(hash)
      console.log(c.yellow(`  [WARN] ${label}: MD5 collision with ${collision} (attempt ${attempt})`))
      if (attempt === MAX_ATTEMPTS) {
        throw new Error(`${label}: MD5 collision on all ${MAX_ATTEMPTS} attempts`)
      }
      continue
    }

    return { buf, md5: hash, attempts: attempt }
  }
}

// ── Main ──────────────────────────────────────────────────────────────────────

let tmpl
try { tmpl = loadTemplate() } catch (err) {
  console.error(`${c.red('[ERROR]')} ${err.message}`)
  process.exit(2)
}

const vars           = buildVariables(tmpl, persona, siteConfig)
const bylinePrompt   = renderPrompt(tmpl.byline, vars)
const aboutPrompt    = renderPrompt(tmpl.about, vars)

const outDir = testDir ?? join(siteDir, 'public', 'images', 'brand')

const targets = [
  { type: 'byline', prompt: bylinePrompt, size: '1024x1024',  file: `${personaSlug}-byline.jpg` },
  { type: 'about',  prompt: aboutPrompt,  size: '1792x1024',  file: `${personaSlug}-about.jpg`  },
].filter(t => !typeFilter || t.type === typeFilter)

console.log()
console.log(`${c.bold('Site:')}    ${siteSlug}`)
console.log(`${c.bold('Persona:')} ${personaSlug} (${vars.name})`)
console.log(`${c.bold('Niche:')}   ${siteConfig?.site?.niche ?? 'unknown'}`)
console.log(`${c.bold('Age:')}     ${vars.age_descriptor}`)
console.log(`${c.bold('Output:')}  ${testDir ? `${testDir} (test mode)` : outDir}`)
if (dryRun) console.log(c.yellow('  DRY RUN — prompts shown, no API calls'))
console.log()

if (dryRun) {
  for (const t of targets) {
    console.log(`${c.bold(`[${t.type.toUpperCase()}]`)} ${t.file} (${t.size})`)
    console.log(`  ${c.dim(t.prompt)}`)
    console.log()
  }

  // Dry-run MD5 check: show existing photos and their hashes
  const existing = collectPortfolioMd5s()
  console.log(`Portfolio persona photos (MD5 uniqueness baseline):`)
  for (const [hash, path] of existing) {
    const shortPath = path.replace(homedir(), '~')
    console.log(`  ${hash}  ${c.dim(shortPath)}`)
  }

  // Check if current site already has persona photos
  const ownByline = join(outDir, `${personaSlug}-byline.jpg`)
  const ownAbout  = join(outDir, `${personaSlug}-about.jpg`)
  console.log()
  console.log('Current site photos:')
  for (const [label, p] of [['byline', ownByline], ['about', ownAbout]]) {
    if (existsSync(p)) {
      console.log(`  ${label}: ${c.green('EXISTS')} (${md5file(p)})`)
    } else {
      console.log(`  ${label}: ${c.yellow('NOT FOUND')}`)
    }
  }
  console.log()
  process.exit(0)
}

// ── Live run ──────────────────────────────────────────────────────────────────

const apiKey = getApiKey()
if (!apiKey) {
  console.error(`${c.red('[ERROR]')} No OPENAI_API_KEY found.`)
  console.error('  Add OPENAI_API_KEY=sk-... to affiliate-platform/.env.local')
  process.exit(2)
}

const client = new OpenAI({ apiKey })

if (!existsSync(outDir)) mkdirSync(outDir, { recursive: true })

const portfolioMd5s = collectPortfolioMd5s()

let exitCode = 0
for (const t of targets) {
  const outputPath = join(outDir, t.file)

  if (existsSync(outputPath) && !force) {
    const existingHash = md5file(outputPath)
    console.log(`  ${c.yellow('[SKIP]')} ${t.file} already exists (MD5: ${existingHash}) — use --force to overwrite`)
    continue
  }

  console.log(`  Generating ${t.type} (${t.size})...`)
  try {
    const result = await generateImage(client, t.prompt, t.size, portfolioMd5s, t.type)
    writeFileSync(outputPath, result.buf)
    const kb = (result.buf.length / 1024).toFixed(0)
    const attempts = result.attempts > 1 ? ` (${result.attempts} attempts)` : ''
    console.log(`  ${c.green('[OK]')} ${t.file}  ${kb}KB  MD5: ${result.md5}${attempts}`)

    // Add new hash to portfolio set so subsequent generates in this run also avoid it
    portfolioMd5s.set(result.md5, outputPath)
  } catch (err) {
    console.error(`  ${c.red('[FAIL]')} ${t.type}: ${err.message}`)
    exitCode = 1
  }
}

console.log()
process.exit(exitCode)
