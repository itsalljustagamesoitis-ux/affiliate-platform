/**
 * state.mjs — Atomic state.yaml reader/writer for launch-site orchestrator.
 *
 * State file lives at ~/affiliate-platform/sites/<slug>/state.yaml.
 * Writes are atomic: tmp file + rename.
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync, renameSync } from 'fs'
import { join, dirname } from 'path'
import yaml from 'js-yaml'

export function statePath(slug, platformDir) {
  return join(platformDir, 'sites', slug, 'state.yaml')
}

export function decisionsLogPath(slug, platformDir) {
  return join(platformDir, 'sites', slug, 'decisions.log')
}

export function stateDir(slug, platformDir) {
  return join(platformDir, 'sites', slug)
}

export function loadState(slug, platformDir) {
  const p = statePath(slug, platformDir)
  if (!existsSync(p)) return null
  try {
    return yaml.load(readFileSync(p, 'utf-8'))
  } catch (err) {
    throw new Error(`Cannot parse state.yaml for ${slug}: ${err.message}`)
  }
}

export function saveState(slug, platformDir, state) {
  const dir = stateDir(slug, platformDir)
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true })
  state.last_updated = new Date().toISOString()
  const p = statePath(slug, platformDir)
  const tmp = p + '.tmp'
  writeFileSync(tmp, yaml.dump(state, { lineWidth: 120 }), 'utf-8')
  renameSync(tmp, p)
}

export function initState(slug, inputs) {
  return {
    slug,
    started: new Date().toISOString(),
    last_updated: new Date().toISOString(),
    current_point: '7',
    current_bucket: null,
    status: 'in_progress',
    points_complete: [],
    points_failed: [],
    keith_pending: [],
    inputs: {
      niche: inputs.niche ?? null,
      domain: inputs.domain ?? null,
      keyword_xlsx_path: inputs.keyword_xlsx_path ?? null,
      persona_context: inputs.persona_context ?? null,
      amazon_tracking_id: inputs.amazon_tracking_id ?? null,
      ga4_measurement_id: inputs.ga4_measurement_id ?? null,
    },
    artifacts: {
      cloudflare_project: slug,
      cloudflare_zone_id: null,
      preview_url: null,
      production_url: null,
    },
  }
}

export function markPointComplete(state, pointId) {
  if (!state.points_complete.includes(String(pointId))) {
    state.points_complete.push(String(pointId))
  }
  state.current_point = String(pointId)
}

export function markPointFailed(state, pointId, reason) {
  state.points_failed = state.points_failed.filter(f => f.point !== String(pointId))
  state.points_failed.push({ point: String(pointId), reason })
  state.status = 'failed'
}

export function addKeithPending(state, request) {
  state.keith_pending = state.keith_pending.filter(r => r.point !== request.point)
  state.keith_pending.push(request)
  state.status = 'awaiting_keith'
}

export function resolveKeithPending(state, pointId) {
  state.keith_pending = state.keith_pending.filter(r => r.point !== String(pointId))
  if (state.keith_pending.length === 0 && state.status === 'awaiting_keith') {
    state.status = 'in_progress'
  }
}

export function isPointComplete(state, pointId) {
  return state.points_complete.includes(String(pointId))
}
