#!/usr/bin/env node
/**
 * lock-persona.mjs — Validate and lock a site's persona YAML.
 *
 * Reads the persona YAML for the given site, validates all required v1.6 fields,
 * checks that persona photos exist and are MD5-unique across the portfolio, then
 * writes persona_locked: true, locked_at, and content_hash back to the YAML.
 *
 * Usage:
 *   node tools/lock-persona.mjs --site <slug>
 *   node tools/lock-persona.mjs --site <slug> --dry-run
 *
 * Exit: 0 = success/already-locked, 1 = validation failed, 2 = tool error
 */

import { readFileSync, writeFileSync, existsSync, renameSync } from 'fs'
import { createHash } from 'crypto'
import { homedir, tmpdir } from 'os'
import { join, dirname } from 'path'
import { fileURLToPath } from 'url'
import { randomBytes } from 'crypto'
import yaml from 'js-yaml'
import { getSite, loadPortfolio } from './lib/portfolio.mjs'

const PLATFORM_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..')

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

// ── Required persona fields ───────────────────────────────────────────────────

// Fields that must be present and non-empty for a persona to be lock-eligible.
const REQUIRED_FIELDS = [
  'slug',
  'name_formal',
  'name_used',
  'display_name',
  'role',
  'background',
  'bio',
  'bio_short',
  'voice_notes',
  'defers_to',
  'forbidden_patterns',
  'allowed_patterns',
  'editorial_constraints',
  'photo_about',
  'photo_byline',
]

// ── Helpers ───────────────────────────────────────────────────────────────────

function siteRoot(slug) {
  return join(homedir(), slug)
}

function resolvePhotoPath(siteSlug, personaPhotoValue) {
  // personaPhotoValue is an absolute-rooted web path like /images/brand/persona-about.jpg
  const rel = personaPhotoValue.startsWith('/') ? personaPhotoValue.slice(1) : personaPhotoValue
  return join(siteRoot(siteSlug), 'public', rel)
}

function md5File(filePath) {
  const buf = readFileSync(filePath)
  return createHash('md5').update(buf).digest('hex')
}

function contentHash(personaDoc) {
  // Hash of the persona content, excluding the lock fields themselves.
  const copy = { ...personaDoc }
  delete copy.persona_locked
  delete copy.locked_at
  delete copy.content_hash
  const canonical = yaml.dump(copy, { lineWidth: 120, sortKeys: true })
  return createHash('sha256').update(canonical).digest('hex')
}

function isEmpty(val) {
  if (val === null || val === undefined) return true
  if (typeof val === 'string' && val.trim() === '') return true
  if (Array.isArray(val) && val.length === 0) return true
  return false
}

function writePersonaYaml(filePath, doc) {
  const serialised = yaml.dump(doc, {
    lineWidth: 120,
    quotingType: '"',
    forceQuotes: false,
    indent: 2,
  })
  const tmp = join(tmpdir(), `persona-${randomBytes(6).toString('hex')}.yaml`)
  writeFileSync(tmp, serialised, 'utf-8')
  renameSync(tmp, filePath)
}

// ── Arg parsing ───────────────────────────────────────────────────────────────

const args    = process.argv.slice(2)
const get     = flag => { const i = args.indexOf(flag); return i !== -1 ? args[i + 1] : null }
const has     = flag => args.includes(flag)

const siteSlug = get('--site')
const dryRun   = has('--dry-run')

if (!siteSlug) {
  console.error('Usage: lock-persona.mjs --site <slug> [--dry-run]')
  process.exit(2)
}

// ── Resolve site ──────────────────────────────────────────────────────────────

let site
try {
  site = getSite(siteSlug)
} catch (err) {
  console.error(`${c.red('[ERROR]')} ${err.message}`)
  process.exit(2)
}

if (!site.persona) {
  console.error(`${c.red('[ERROR]')} site "${siteSlug}" has no persona field in portfolio.yaml`)
  process.exit(2)
}

const personaFile = join(siteRoot(siteSlug), 'config', 'personas', `${site.persona}.yaml`)

if (!existsSync(personaFile)) {
  console.error(`${c.red('[ERROR]')} Persona file not found: ${personaFile}`)
  process.exit(2)
}

// ── Read persona YAML ─────────────────────────────────────────────────────────

let persona
try {
  persona = yaml.load(readFileSync(personaFile, 'utf-8'))
} catch (err) {
  console.error(`${c.red('[ERROR]')} Failed to parse persona YAML: ${err.message}`)
  process.exit(2)
}

console.log(`${c.dim(`[${siteSlug}]`)} Checking persona ${c.bold(site.persona)} (${personaFile})`)
if (dryRun) console.log(`${c.yellow('[DRY-RUN]')} No changes will be written`)

// ── Already-locked check ──────────────────────────────────────────────────────

const expectedHash = contentHash(persona)

if (persona.persona_locked === true && persona.content_hash) {
  if (persona.content_hash === expectedHash) {
    console.log(`${c.dim('[NO-OP]')} Persona already locked (hash match). locked_at: ${persona.locked_at}`)
    process.exit(0)
  } else {
    console.log(`${c.yellow('[WARN]')} persona_locked is true but content_hash does not match current content.`)
    console.log(`  Stored: ${persona.content_hash}`)
    console.log(`  Current: ${expectedHash}`)
    console.log(`  Persona content has changed since last lock. Re-validating and re-locking...`)
  }
}

// ── Validate required fields ──────────────────────────────────────────────────

const fieldFails = []
for (const field of REQUIRED_FIELDS) {
  if (isEmpty(persona[field])) {
    fieldFails.push(field)
  }
}

if (fieldFails.length > 0) {
  console.error(`${c.red('[FAIL]')} Required fields missing or empty:`)
  for (const f of fieldFails) {
    console.error(`  ${c.red('✗')} ${f}`)
  }
  process.exit(1)
}

console.log(`${c.green('  ✓')} All ${REQUIRED_FIELDS.length} required fields present`)

// ── Photo existence check ─────────────────────────────────────────────────────

const photoFields = ['photo_about', 'photo_byline']
const photoFails = []
const photoPaths = {}

for (const field of photoFields) {
  const absPath = resolvePhotoPath(siteSlug, persona[field])
  if (!existsSync(absPath)) {
    photoFails.push(`${field}: ${absPath}`)
  } else {
    photoPaths[field] = absPath
  }
}

if (photoFails.length > 0) {
  console.error(`${c.red('[FAIL]')} Persona photo files not found:`)
  for (const f of photoFails) {
    console.error(`  ${c.red('✗')} ${f}`)
  }
  process.exit(1)
}

console.log(`${c.green('  ✓')} Both persona photos exist`)

// ── MD5 uniqueness check across portfolio ─────────────────────────────────────

const thisHashes = {}
for (const [field, absPath] of Object.entries(photoPaths)) {
  thisHashes[field] = md5File(absPath)
}

const allSites = loadPortfolio()
const collisions = []

for (const otherSite of allSites) {
  if (otherSite.slug === siteSlug) continue
  if (!otherSite.persona) continue

  const otherRoot = siteRoot(otherSite.slug)
  const otherPersonaFile = join(otherRoot, 'config', 'personas', `${otherSite.persona}.yaml`)
  if (!existsSync(otherPersonaFile)) continue

  let otherPersona
  try {
    otherPersona = yaml.load(readFileSync(otherPersonaFile, 'utf-8'))
  } catch { continue }

  for (const field of photoFields) {
    const otherPhotoValue = otherPersona[field]
    if (!otherPhotoValue) continue
    const otherAbsPath = resolvePhotoPath(otherSite.slug, otherPhotoValue)
    if (!existsSync(otherAbsPath)) continue

    const otherHash = md5File(otherAbsPath)
    for (const [thisField, thisHash] of Object.entries(thisHashes)) {
      if (thisHash === otherHash) {
        collisions.push(
          `${siteSlug}/${thisField} matches ${otherSite.slug}/${field} (${otherHash.slice(0, 8)}…)`
        )
      }
    }
  }
}

if (collisions.length > 0) {
  console.error(`${c.red('[FAIL]')} Persona photo MD5 collision(s) found:`)
  for (const col of collisions) {
    console.error(`  ${c.red('✗')} ${col}`)
  }
  process.exit(1)
}

console.log(`${c.green('  ✓')} Persona photos are MD5-unique across portfolio`)

// ── Compute content hash ──────────────────────────────────────────────────────

const hash = expectedHash
const now  = new Date().toISOString()

console.log(`${c.dim('  SHA-256:')} ${hash}`)

// ── Write lock fields ─────────────────────────────────────────────────────────

if (dryRun) {
  console.log(`\n${c.yellow('[DRY-RUN]')} Would set:`)
  console.log(`  persona_locked: true`)
  console.log(`  locked_at:      ${now}`)
  console.log(`  content_hash:   ${hash}`)
  process.exit(0)
}

persona.persona_locked = true
persona.locked_at      = now
persona.content_hash   = hash

try {
  writePersonaYaml(personaFile, persona)
} catch (err) {
  console.error(`${c.red('[ERROR]')} Failed to write persona YAML: ${err.message}`)
  process.exit(2)
}

console.log(`\n${c.green('[LOCKED]')} ${siteSlug}/${site.persona}`)
console.log(`  locked_at:    ${now}`)
console.log(`  content_hash: ${hash}`)
