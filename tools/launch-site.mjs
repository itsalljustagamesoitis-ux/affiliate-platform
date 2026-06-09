#!/usr/bin/env node
/**
 * launch-site.mjs — 21-point ritual orchestrator (v1.6)
 *
 * Manages a full site launch from Point 7 (site shell) through Point 21 (dashboard).
 * Points 1–6 are Keith strategic inputs — supplied as CLI arguments or via state.yaml.
 *
 * Usage:
 *   node tools/launch-site.mjs --site <slug> [options]
 *   node tools/launch-site.mjs --resume <slug> [--amazon-tracking-id <id>] [--ga4-id <id>] [--bwt-txt <txt>] [--gsc-txt <txt>]
 *   node tools/launch-site.mjs --site <slug> --dry-run
 *
 * Point 1–6 inputs (new launch):
 *   --niche <niche>              Site niche (fly-fishing, audiophile, etc.)
 *   --domain <domain>            Site domain (e.g. undisclosedsounds.com)
 *   --xlsx <path>                Path to keyword XLSX (Point 2/3)
 *   --persona <description>      Persona biographical context (Point 5)
 *
 * Identity-gate inputs (resume path):
 *   --amazon-tracking-id <id>    Inject at Point 9 resume
 *   --ga4-id <id>                Inject at Point 17 resume
 *   --bwt-txt <string>           Inject at Point 18 resume
 *   --gsc-txt <string>           Inject at Point 19 resume
 *
 * Exit codes:
 *   0 — complete or clean halt (awaiting Keith)
 *   1 — hard failure — check state.yaml
 *   2 — tool error (bad args, concurrency conflict, corrupt state)
 */

import { existsSync, readFileSync, writeFileSync, renameSync, mkdirSync } from 'fs'
import { join, dirname } from 'path'
import { homedir } from 'os'
import { fileURLToPath } from 'url'
import { execSync } from 'child_process'
import yaml from 'js-yaml'

import {
  loadState,
  saveState,
  initState,
  markPointComplete,
  markPointFailed,
  addKeithPending,
  resolveKeithPending,
  isPointComplete,
  statePath,
  stateDir,
} from './launch-site/state.mjs'

import { dispatch, logDecision } from './launch-site/buckets.mjs'

import { run as runP07, BUCKET as B07 } from './launch-site/points/p07-site-shell.mjs'
import { run as runP08, BUCKET as B08 } from './launch-site/points/p08-furniture.mjs'
import { run as runP09, BUCKET as B09 } from './launch-site/points/p09-amazon-tracking-id.mjs'
import { run as runP10, BUCKET as B10 } from './launch-site/points/p10-source-products.mjs'
import { run as runP10_5, BUCKET as B10_5 } from './launch-site/points/p10-5-generate-pros-cons.mjs'
import { run as runP11, BUCKET as B11 } from './launch-site/points/p11-source-images.mjs'
import { run as runP12, BUCKET as B12 } from './launch-site/points/p12-assign-images.mjs'
import { run as runP12_5, BUCKET as B12_5 } from './launch-site/points/p12-5-brand-match.mjs'
import { run as runP13, BUCKET as B13 } from './launch-site/points/p13-producer.mjs'
import { run as runP13_5, BUCKET as B13_5 } from './launch-site/points/p13-5-persona-claim.mjs'
import { run as runP13_5b, BUCKET as B13_5b } from './launch-site/points/p13-5b-persona-spec.mjs'
import { run as runP13_6, BUCKET as B13_6 } from './launch-site/points/p13-6-image-markdown.mjs'
import { run as runP13_7, BUCKET as B13_7 } from './launch-site/points/p13-7-meta-leakage.mjs'
import { run as runP13_8, BUCKET as B13_8 } from './launch-site/points/p13-8-card-voice.mjs'
import { run as runP13_9, BUCKET as B13_9 } from './launch-site/points/p13-9-product-slug.mjs'
import { run as runP14, BUCKET as B14 } from './launch-site/points/p14-publish-staging.mjs'
import { run as runP15, BUCKET as B15 } from './launch-site/points/p15-local-build.mjs'
import { run as runP15_5, BUCKET as B15_5 } from './launch-site/points/p15-5-preflight.mjs'
import { run as runP15_6, BUCKET as B15_6 } from './launch-site/points/p15-6-content-existence.mjs'
import { run as runP16, BUCKET as B16 } from './launch-site/points/p16-push-live.mjs'
import { run as runP17, BUCKET as B17 } from './launch-site/points/p17-ga4.mjs'
import { run as runP18, BUCKET as B18 } from './launch-site/points/p18-bwt.mjs'
import { run as runP19, BUCKET as B19 } from './launch-site/points/p19-gsc.mjs'
import { run as runP20, BUCKET as B20 } from './launch-site/points/p20-indexnow.mjs'
import { run as runP20_5, BUCKET as B20_5 } from './launch-site/points/p20-5-uat-furniture.mjs'
import { run as runP21, BUCKET as B21 } from './launch-site/points/p21-dashboard.mjs'

// ── Constants ─────────────────────────────────────────────────────────────────

const PLATFORM_DIR       = join(dirname(fileURLToPath(import.meta.url)), '..')
const ACTIVE_LAUNCHES    = join(PLATFORM_DIR, 'active-launches.yaml')

// ── ANSI ──────────────────────────────────────────────────────────────────────

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

// ── Arg parsing ───────────────────────────────────────────────────────────────

const args   = process.argv.slice(2)
const has    = flag => args.includes(flag)
const get    = flag => { const i = args.indexOf(flag); return i !== -1 ? args[i + 1] : null }

const slug       = get('--site') ?? get('--resume')
const isResume   = has('--resume')
const dryRun     = has('--dry-run')

const inputs = {
  niche:               get('--niche'),
  domain:              get('--domain'),
  keyword_xlsx_path:   get('--xlsx'),
  persona_context:     get('--persona'),
  amazon_tracking_id:  get('--amazon-tracking-id'),
  ga4_measurement_id:  get('--ga4-id'),
  bwt_txt_record:      get('--bwt-txt'),
  gsc_txt_record:      get('--gsc-txt'),
}

// ── Ordered point sequence (7–21) ─────────────────────────────────────────────

const POINTS = [
  { id: '7',    bucket: B07,    run: runP07 },
  { id: '8',    bucket: B08,    run: runP08 },
  { id: '9',    bucket: B09,    run: runP09 },
  { id: '10',   bucket: B10,    run: runP10 },
  { id: '10.5', bucket: B10_5,  run: runP10_5 },
  { id: '11',   bucket: B11,    run: runP11 },
  { id: '12',   bucket: B12,    run: runP12 },
  { id: '12.5', bucket: B12_5,  run: runP12_5 },
  { id: '13',   bucket: B13,    run: runP13 },
  { id: '13.5', bucket: B13_5,  run: runP13_5 },
  { id: '13.5b',bucket: B13_5b, run: runP13_5b },
  { id: '13.6', bucket: B13_6,  run: runP13_6 },
  { id: '13.7', bucket: B13_7,  run: runP13_7 },
  { id: '13.8', bucket: B13_8,  run: runP13_8 },
  { id: '13.9', bucket: B13_9,  run: runP13_9 },
  { id: '14',   bucket: B14,    run: runP14 },
  { id: '15',   bucket: B15,    run: runP15 },
  { id: '15.5', bucket: B15_5,  run: runP15_5 },
  { id: '15.6', bucket: B15_6,  run: runP15_6 },
  { id: '16',   bucket: B16,    run: runP16 },
  { id: '17',   bucket: B17,    run: runP17 },
  { id: '18',   bucket: B18,    run: runP18 },
  { id: '19',   bucket: B19,    run: runP19 },
  { id: '20',   bucket: B20,    run: runP20 },
  { id: '20.5', bucket: B20_5,  run: runP20_5 },
  { id: '21',   bucket: B21,    run: runP21 },
]

// ── Logger ────────────────────────────────────────────────────────────────────

function makeLogger(pointId) {
  const prefix = c.dim(`[Point ${pointId}]`)
  return {
    info:  msg => console.log(`${prefix} ${msg}`),
    warn:  msg => console.log(`${prefix} ${c.yellow(msg)}`),
    error: msg => console.error(`${prefix} ${c.red(msg)}`),
  }
}

// ── execTool helper ───────────────────────────────────────────────────────────

function execTool(cmd, opts = {}) {
  const { timeout = 300000, cwd } = opts
  try {
    const out = execSync(cmd, { encoding: 'utf-8', stdio: 'pipe', timeout, cwd })
    return { ok: true, stdout: out?.trim() ?? '', stderr: '' }
  } catch (err) {
    return { ok: false, stdout: err.stdout?.trim() ?? '', stderr: err.stderr?.trim() ?? err.message }
  }
}

// ── Concurrency lock ──────────────────────────────────────────────────────────

function acquireLock(slug) {
  if (dryRun) return
  let active = {}
  if (existsSync(ACTIVE_LAUNCHES)) {
    try { active = yaml.load(readFileSync(ACTIVE_LAUNCHES, 'utf-8')) ?? {} } catch { }
  }
  if (active.current_slug && active.current_slug !== slug) {
    console.error(c.red(`Concurrency conflict: ${active.current_slug} is already in progress.`))
    console.error(c.dim(`  Only one site launches at a time (§16.7).`))
    console.error(c.dim(`  If the prior launch is stale, remove active-launches.yaml manually.`))
    process.exit(2)
  }
  active.current_slug = slug
  active.started = new Date().toISOString()
  writeFileSync(ACTIVE_LAUNCHES, yaml.dump(active), 'utf-8')
}

function releaseLock() {
  if (dryRun) return
  try {
    writeFileSync(ACTIVE_LAUNCHES, yaml.dump({ current_slug: null }), 'utf-8')
  } catch { }
}

// ── State helpers ─────────────────────────────────────────────────────────────

let _state
let _slug

function ctx_saveState() {
  if (!dryRun) saveState(_slug, PLATFORM_DIR, _state)
}

// ── Main orchestrator ─────────────────────────────────────────────────────────

async function main() {
  if (!slug) {
    console.error(c.red('Usage: node tools/launch-site.mjs --site <slug> [--dry-run]'))
    console.error(c.red('       node tools/launch-site.mjs --resume <slug> [--ga4-id <id>] …'))
    process.exit(2)
  }

  _slug = slug
  const siteDir = join(homedir(), slug)

  console.log(c.bold(`\nlaunch-site.mjs — v1.6 ritual orchestrator`))
  console.log(c.dim(`  Site:    ${slug}`))
  console.log(c.dim(`  Mode:    ${isResume ? 'resume' : 'new launch'}${dryRun ? ' (DRY RUN)' : ''}`))
  console.log(c.dim(`  Time:    ${new Date().toISOString()}\n`))

  // Concurrency check
  acquireLock(slug)

  // Load or init state
  let state
  if (isResume) {
    state = loadState(slug, PLATFORM_DIR)
    if (!state) {
      console.error(c.red(`No state.yaml found for "${slug}" — cannot resume. Start with --site instead.`))
      releaseLock()
      process.exit(2)
    }
    // Inject any Keith-provided inputs
    const resumeInputs = Object.fromEntries(
      Object.entries(inputs).filter(([, v]) => v !== null),
    )
    if (Object.keys(resumeInputs).length > 0) {
      Object.assign(state.inputs, resumeInputs)
      console.log(c.dim(`  Injected: ${Object.keys(resumeInputs).join(', ')}`))
    }
    // Resolve any Keith pending for points that now have their inputs
    const pendingPoints = state.keith_pending.map(r => r.point)
    for (const pp of pendingPoints) {
      const inputKey = { '9': 'amazon_tracking_id', '17': 'ga4_measurement_id', '18': 'bwt_txt_record', '19': 'gsc_txt_record' }[pp]
      if (inputKey && state.inputs[inputKey]) {
        resolveKeithPending(state, pp)
      }
    }
    if (!dryRun) saveState(slug, PLATFORM_DIR, state)
  } else {
    const existing = loadState(slug, PLATFORM_DIR)
    if (existing && existing.status !== 'complete') {
      console.error(c.yellow(`Warning: state.yaml already exists for "${slug}" (status: ${existing.status}).`))
      console.error(c.dim(`  Use --resume ${slug} to continue, or delete sites/${slug}/state.yaml to restart.`))
      releaseLock()
      process.exit(2)
    }
    state = initState(slug, inputs)
    if (!dryRun) saveState(slug, PLATFORM_DIR, state)
  }

  _state = state

  // Build shared context
  const ctx = {
    slug,
    siteDir,
    platformDir: PLATFORM_DIR,
    state,
    dryRun,
    execTool,
    log: makeLogger('?'),  // replaced per-point below
    saveState: ctx_saveState,
  }

  // Run points in sequence
  let halted = false
  for (const point of POINTS) {
    const pointId = point.id

    if (isPointComplete(state, pointId)) {
      console.log(c.dim(`  [Point ${pointId}] ${c.green('✓')} already complete — skipping`))
      continue
    }

    // Skip points prior to the current state point on resume (belt-and-suspenders)
    // (isPointComplete covers this, but guard here too)

    const pointCtx = {
      ...ctx,
      log: makeLogger(pointId),
    }

    const header = `Point ${pointId} (Bucket ${point.bucket})`
    console.log(c.bold(`\n── ${header} ${'─'.repeat(Math.max(0, 56 - header.length))}`))

    const result = await dispatch(pointCtx, pointId, point.bucket, point.run)

    if (result.status === 'pass' || result.status === 'preview_required') {
      markPointComplete(state, pointId)
      if (!dryRun) saveState(slug, PLATFORM_DIR, state)
      console.log(c.green(`  ✓ Point ${pointId} complete`))

      if (result.status === 'preview_required') {
        console.log(c.yellow(`\n  Preview review required (Bucket B).`))
        console.log(c.dim(`  Review preview URL in state.yaml, then resume to promote to production.`))
        state.status = 'awaiting_keith'
        if (!dryRun) saveState(slug, PLATFORM_DIR, state)
        halted = true
        break
      }
    } else if (result.status === 'halt') {
      if (result.haltRequest) {
        addKeithPending(state, result.haltRequest)
      } else {
        state.status = 'awaiting_keith'
      }
      if (!dryRun) saveState(slug, PLATFORM_DIR, state)
      halted = true
      break
    } else if (result.status === 'fail') {
      markPointFailed(state, pointId, result.message ?? 'unknown failure')
      if (!dryRun) saveState(slug, PLATFORM_DIR, state)
      console.error(c.red(`\n  ✗ Point ${pointId} failed: ${result.message ?? 'unknown'}`))
      releaseLock()
      process.exit(1)
    }
  }

  releaseLock()

  if (!halted) {
    state.status = 'complete'
    if (!dryRun) saveState(slug, PLATFORM_DIR, state)
    printCompleteSummary(state)
    process.exit(0)
  } else {
    printHaltSummary(state)
    process.exit(0)  // clean halt — not an error
  }
}

// ── Summary printers ──────────────────────────────────────────────────────────

function printCompleteSummary(state) {
  const domain = state.inputs?.domain ?? `${state.slug}.com`
  console.log(c.bold('\n  ┌─ RITUAL COMPLETE ─────────────────────────────────────────────┐'))
  console.log(`  │  Site:         ${state.slug}`)
  console.log(`  │  Domain:       ${c.cyan(`https://${domain}`)}`)
  console.log(`  │  Points:       ${state.points_complete.length}/25 complete`)
  console.log(`  │  Status:       ${c.green('live')}`)
  if (dryRun) {
    console.log(`  │  `)
    console.log(`  │  This was a dry run. No APIs were called.`)
    console.log(`  │  Re-run without --dry-run to launch for real.`)
  } else {
    console.log(`  │  `)
    console.log(`  │  State: ~/affiliate-platform/sites/${state.slug}/state.yaml`)
    console.log(`  │  Log:   ~/affiliate-platform/sites/${state.slug}/decisions.log`)
  }
  console.log(c.bold('  └───────────────────────────────────────────────────────────────┘'))
}

function printHaltSummary(state) {
  const pending = state.keith_pending ?? []
  console.log(c.bold('\n  ┌─ RITUAL HALTED ───────────────────────────────────────────────┐'))
  console.log(`  │  Site:         ${state.slug}`)
  console.log(`  │  Status:       ${c.yellow(state.status)}`)
  console.log(`  │  At point:     ${state.current_point}`)
  console.log(`  │  Complete:     ${state.points_complete.join(', ') || '(none)'}`)
  if (pending.length > 0) {
    console.log(`  │  `)
    console.log(`  │  Keith actions required:`)
    for (const r of pending) {
      console.log(`  │    Point ${r.point}: ${r.title}`)
    }
  }
  console.log(`  │  `)
  console.log(`  │  Resume: node tools/launch-site.mjs --resume ${state.slug} [--<input> <value>]`)
  console.log(c.bold('  └───────────────────────────────────────────────────────────────┘'))
}

// ── Entry ─────────────────────────────────────────────────────────────────────

main().catch(err => {
  releaseLock()
  console.error(c.red(`\nFatal: ${err.message}`))
  if (process.env.DEBUG) console.error(err.stack)
  process.exit(1)
})
