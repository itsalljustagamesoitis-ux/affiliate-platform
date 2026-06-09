#!/usr/bin/env node
/**
 * portfolio-update.mjs — Atomic single-field writer for portfolio.yaml.
 *
 * Called at every phase transition to keep portfolio.yaml in sync with reality.
 * Never clobbers fields not explicitly set. Creates the site entry if absent.
 *
 * Usage:
 *   node tools/portfolio-update.mjs --site <slug> --set <field>=<value>
 *   node tools/portfolio-update.mjs --site <slug> --set status=live
 *   node tools/portfolio-update.mjs --site <slug> --set ga4_id=G-XXXXXXXXXX
 *   node tools/portfolio-update.mjs --site <slug> --set persona_locked=true
 *   node tools/portfolio-update.mjs --site <slug> --set launched=2026-06-01
 *   node tools/portfolio-update.mjs --site <slug>   # print current entry
 *
 * Exit: 0 = success, 1 = validation error, 2 = tool error
 */

import { readFileSync, writeFileSync, existsSync, renameSync } from 'fs'
import { join, dirname } from 'path'
import { fileURLToPath } from 'url'
import { tmpdir } from 'os'
import { randomBytes } from 'crypto'
import yaml from 'js-yaml'

// ── Platform paths ────────────────────────────────────────────────────────────

const PLATFORM_ROOT  = join(dirname(fileURLToPath(import.meta.url)), '..')
const PORTFOLIO_PATH = join(PLATFORM_ROOT, 'portfolio.yaml')

// ── ANSI helpers ──────────────────────────────────────────────────────────────

const isTTY = process.stdout.isTTY
const esc   = isTTY ? (s, c) => `\x1b[${c}m${s}\x1b[0m` : (s) => s
const c = {
  green:  s => esc(s, '32'),
  red:    s => esc(s, '31'),
  yellow: s => esc(s, '33'),
  bold:   s => esc(s, '1'),
  dim:    s => esc(s, '2'),
}

// ── v1.6 field schema ─────────────────────────────────────────────────────────

// All valid top-level fields for a portfolio.yaml entry.
// 'type' is used for coercion; 'required' means it must be present on a new entry.
const FIELD_SCHEMA = {
  // Core fields (Sites 1+)
  slug:                   { type: 'string',  required: true  },
  domain:                 { type: 'string',  required: true  },
  persona:                { type: 'string',  required: false },
  tracking_id:            { type: 'string',  required: false },
  ga4_id:                 { type: 'string',  required: false, nullable: true },
  cloudflare_project:     { type: 'string',  required: false },
  github_repo:            { type: 'string',  required: false, nullable: true },
  status:                 { type: 'string',  required: false,
                            enum: ['pre_launch', 'launched', 'live', 'paused', 'retired'] },
  launched:               { type: 'string',  required: false, nullable: true },
  notes:                  { type: 'string',  required: false, nullable: true },
  // v1.6 additions
  persona_locked:         { type: 'boolean', required: false, nullable: true },
  persona_locked_at:      { type: 'string',  required: false, nullable: true },
  gsc_verified:           { type: 'boolean', required: false, nullable: true },
  bwt_verified:           { type: 'boolean', required: false, nullable: true },
  custom_domain_attached: { type: 'boolean', required: false, nullable: true },
  deploy_pattern:         { type: 'string',  required: false, nullable: true,
                            enum: ['direct_upload', 'git_push', null] },
}

// ── Value coercion ────────────────────────────────────────────────────────────

function coerce(field, rawValue) {
  const schema = FIELD_SCHEMA[field]
  if (!schema) throw new Error(`Unknown field: "${field}"`)

  if (rawValue === 'null') {
    if (!schema.nullable) throw new Error(`Field "${field}" is not nullable`)
    return null
  }

  switch (schema.type) {
    case 'boolean':
      if (rawValue === 'true')  return true
      if (rawValue === 'false') return false
      throw new Error(`Field "${field}" expects true or false, got "${rawValue}"`)

    case 'number':
      if (isNaN(Number(rawValue))) throw new Error(`Field "${field}" expects a number, got "${rawValue}"`)
      return Number(rawValue)

    case 'string':
      if (schema.enum) {
        const valid = schema.enum.filter(v => v !== null)
        if (!valid.includes(rawValue))
          throw new Error(`Field "${field}" must be one of: ${valid.join(', ')}`)
      }
      return rawValue

    default:
      return rawValue
  }
}

// ── Portfolio read/write ──────────────────────────────────────────────────────

function readPortfolio() {
  try {
    const raw = readFileSync(PORTFOLIO_PATH, 'utf-8')
    const doc = yaml.load(raw)
    if (!doc?.sites || !Array.isArray(doc.sites)) {
      throw new Error('portfolio.yaml missing or malformed sites array')
    }
    return { doc, raw }
  } catch (err) {
    throw new Error(`Cannot read portfolio.yaml: ${err.message}`)
  }
}

// Atomic write: write to temp, rename over target.
function writePortfolio(doc) {
  const serialised = yaml.dump(doc, {
    lineWidth: 120,
    quotingType: '"',
    forceQuotes: false,
    indent: 2,
  })
  const tmp = join(tmpdir(), `portfolio-${randomBytes(6).toString('hex')}.yaml`)
  writeFileSync(tmp, serialised, 'utf-8')
  renameSync(tmp, PORTFOLIO_PATH)
}

// ── Main ──────────────────────────────────────────────────────────────────────

const args    = process.argv.slice(2)
const has     = flag => args.includes(flag)
const get     = flag => { const i = args.indexOf(flag); return i !== -1 ? args[i + 1] : null }

const slug    = get('--site')
const setExpr = get('--set')

if (!slug) {
  console.error('Usage: portfolio-update.mjs --site <slug> [--set <field>=<value>]')
  process.exit(2)
}

// ── Validate field=value expression ──────────────────────────────────────────

let field, value
if (setExpr) {
  const eqIdx = setExpr.indexOf('=')
  if (eqIdx === -1) {
    console.error(`[ERROR] --set expects <field>=<value>, got "${setExpr}"`)
    process.exit(1)
  }
  field = setExpr.slice(0, eqIdx)
  const rawValue = setExpr.slice(eqIdx + 1)

  if (!FIELD_SCHEMA[field]) {
    console.error(`[ERROR] Unknown field "${field}". Valid fields: ${Object.keys(FIELD_SCHEMA).join(', ')}`)
    process.exit(1)
  }

  try {
    value = coerce(field, rawValue)
  } catch (err) {
    console.error(`[ERROR] ${err.message}`)
    process.exit(1)
  }
}

// ── Read portfolio.yaml ───────────────────────────────────────────────────────

let portfolio
try {
  portfolio = readPortfolio()
} catch (err) {
  console.error(`[ERROR] ${err.message}`)
  process.exit(2)
}

const { doc } = portfolio
const entryIdx = doc.sites.findIndex(s => s.slug === slug)

// Read-only mode: no --set flag — just print the current entry
if (!setExpr) {
  if (entryIdx === -1) {
    console.log(`${c.yellow('[WARN]')} "${slug}" not in portfolio.yaml`)
  } else {
    console.log(c.bold(`portfolio.yaml entry for ${slug}:`))
    console.log(yaml.dump(doc.sites[entryIdx], { indent: 2 }))
  }
  process.exit(0)
}

// ── Apply update ──────────────────────────────────────────────────────────────

let entry
if (entryIdx === -1) {
  // Create minimal new entry
  entry = { slug }
  doc.sites.push(entry)
  console.log(`${c.dim('[NEW]')} Created entry for "${slug}"`)
} else {
  entry = doc.sites[entryIdx]
}

const prev = entry[field]
entry[field] = value

// ── Write back ────────────────────────────────────────────────────────────────

try {
  writePortfolio(doc)
} catch (err) {
  console.error(`[ERROR] Failed to write portfolio.yaml: ${err.message}`)
  process.exit(2)
}

const prevStr  = prev  === undefined ? '(unset)' : JSON.stringify(prev)
const valueStr = JSON.stringify(value)

console.log(`${c.green('[OK]')} ${slug}: ${c.bold(field)} ${c.dim(prevStr)} → ${c.bold(valueStr)}`)
