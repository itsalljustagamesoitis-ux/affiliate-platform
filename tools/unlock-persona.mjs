#!/usr/bin/env node
/**
 * unlock-persona.mjs — Remove the persona lock for a site.
 *
 * Clears persona_locked, locked_at, and content_hash from the persona YAML,
 * then appends an entry to ~/affiliate-platform/persona-unlock-log.yaml.
 * Requires --reason to be supplied.
 *
 * Usage:
 *   node tools/unlock-persona.mjs --site <slug> --reason "<rationale>"
 *
 * Exit: 0 = success/already-unlocked, 1 = validation error, 2 = tool error
 */

import { readFileSync, writeFileSync, existsSync, appendFileSync, renameSync } from 'fs'
import { homedir, tmpdir } from 'os'
import { join, dirname } from 'path'
import { fileURLToPath } from 'url'
import { randomBytes } from 'crypto'
import yaml from 'js-yaml'
import { getSite } from './lib/portfolio.mjs'

const PLATFORM_ROOT   = join(dirname(fileURLToPath(import.meta.url)), '..')
const UNLOCK_LOG_PATH = join(PLATFORM_ROOT, 'persona-unlock-log.yaml')

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

// ── Helpers ───────────────────────────────────────────────────────────────────

function siteRoot(slug) {
  return join(homedir(), slug)
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

function appendUnlockLog(entry) {
  const line = yaml.dump([entry], { lineWidth: 120, indent: 2 })
  // Ensure file ends with newline before appending
  let prefix = ''
  if (existsSync(UNLOCK_LOG_PATH)) {
    const existing = readFileSync(UNLOCK_LOG_PATH, 'utf-8')
    if (existing.length > 0 && !existing.endsWith('\n')) prefix = '\n'
  }
  appendFileSync(UNLOCK_LOG_PATH, prefix + line, 'utf-8')
}

// ── Arg parsing ───────────────────────────────────────────────────────────────

const args     = process.argv.slice(2)
const get      = flag => { const i = args.indexOf(flag); return i !== -1 ? args[i + 1] : null }

const siteSlug = get('--site')
const reason   = get('--reason')

if (!siteSlug || !reason) {
  console.error('Usage: unlock-persona.mjs --site <slug> --reason "<rationale>"')
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

// ── Already-unlocked check ────────────────────────────────────────────────────

if (!persona.persona_locked) {
  console.log(`${c.dim('[NO-OP]')} Persona is not currently locked — nothing to do`)
  process.exit(0)
}

const previousLockedAt = persona.locked_at ?? null

// ── Clear lock fields ─────────────────────────────────────────────────────────

delete persona.persona_locked
delete persona.locked_at
delete persona.content_hash

try {
  writePersonaYaml(personaFile, persona)
} catch (err) {
  console.error(`${c.red('[ERROR]')} Failed to write persona YAML: ${err.message}`)
  process.exit(2)
}

// ── Append to unlock log ──────────────────────────────────────────────────────

const logEntry = {
  site:              siteSlug,
  persona:           site.persona,
  unlocked_at:       new Date().toISOString(),
  previous_locked_at: previousLockedAt,
  reason,
}

try {
  appendUnlockLog(logEntry)
} catch (err) {
  console.error(`${c.yellow('[WARN]')} Persona unlocked but failed to write unlock log: ${err.message}`)
  process.exit(0)
}

console.log(`${c.yellow('[UNLOCKED]')} ${siteSlug}/${site.persona}`)
console.log(`  previous locked_at: ${previousLockedAt ?? '(unknown)'}`)
console.log(`  reason: ${reason}`)
console.log(`  log: ${UNLOCK_LOG_PATH}`)
