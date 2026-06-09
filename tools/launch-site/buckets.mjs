/**
 * buckets.mjs — Bucket A/B/C/D dispatch and decisions.log writer.
 *
 * Every autonomous decision is appended to decisions.log.
 * Bucket C/D halts surface structured requests; in dry-run they print and continue.
 */

import { appendFileSync, existsSync, mkdirSync } from 'fs'
import { dirname } from 'path'
import { decisionsLogPath } from './state.mjs'

// ── decisions.log ─────────────────────────────────────────────────────────────

export function logDecision(ctx, pointId, fields) {
  if (ctx.dryRun) return
  const line = `${new Date().toISOString()} [Point ${pointId}] ${Object.entries(fields).map(([k, v]) => `${k}=${v}`).join(' ')}\n`
  const p = decisionsLogPath(ctx.slug, ctx.platformDir)
  const dir = dirname(p)
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true })
  appendFileSync(p, line, 'utf-8')
}

// ── Bucket dispatch ────────────────────────────────────────────────────────────

/**
 * Run a point with bucket awareness.
 * runFn receives ctx and returns { status: 'pass'|'halt'|'fail', message?, haltRequest? }
 *
 * Bucket A: run autonomously, log decision, return result
 * Bucket B: run autonomously + log, but result.status='pass' triggers 'preview_required'
 * Bucket C: check if keith has already provided input; if yes, run; if no, halt
 * Bucket D: always halt for strategic decision
 */
export async function dispatch(ctx, pointId, bucket, runFn) {
  ctx.state.current_point = String(pointId)
  ctx.state.current_bucket = bucket
  if (!ctx.dryRun) ctx.saveState()

  if (bucket === 'D') {
    const msg = `Keith strategic decision required at Point ${pointId}`
    ctx.log.warn(msg)
    logDecision(ctx, pointId, { halt: 'awaiting_keith_strategic', bucket })
    return { status: 'halt', message: msg }
  }

  const result = await runFn(ctx)

  if (result.status === 'pass') {
    logDecision(ctx, pointId, { decision: 'complete', bucket, ...(result.logFields ?? {}) })
  } else if (result.status === 'halt') {
    logDecision(ctx, pointId, { halt: 'awaiting_keith', bucket, ...(result.logFields ?? {}) })
  } else if (result.status === 'fail') {
    logDecision(ctx, pointId, { decision: 'failed', bucket, reason: result.message?.replace(/\s+/g, '_').slice(0, 60) ?? 'unknown' })
  }

  if (bucket === 'B' && result.status === 'pass') {
    return { ...result, status: 'preview_required' }
  }

  return result
}
