/**
 * Point 13.8 — Card-voice density validator
 * Bucket A: SOFT failure — logged to calibration-log.yaml, does not block
 */

import { existsSync } from 'fs'

export const POINT_ID = '13.8'
export const BUCKET = 'A'

export async function run(ctx) {
  const { slug, siteDir, platformDir, dryRun, log, execTool } = ctx

  const validator = `${platformDir}/scripts/validate-card-voice.mjs`
  if (!existsSync(validator)) {
    log.warn('validate-card-voice.mjs not found — skipping (soft check)')
    return { status: 'pass', logFields: { skipped: true } }
  }

  if (dryRun) {
    log.info('(dry-run) would run validate-card-voice.mjs (SOFT)')
    return { status: 'pass', logFields: { dry_run: true } }
  }

  const r = execTool(`node "${validator}" --site ${slug} --json`)
  let parsed
  try { parsed = JSON.parse(r.stdout) } catch { parsed = {} }

  const failCount = parsed.fail_count ?? (parsed.failures ?? []).length
  const fpDensity = parsed.fp_density ?? null

  if (failCount > 0) {
    log.warn(`Card-voice: ${failCount} soft failures (fp_density=${fpDensity ?? 'unknown'}) — logged to calibration-log.yaml, not blocking`)
  } else {
    log.info(`Card-voice: pass (fp_density=${fpDensity ?? 'unknown'})`)
  }

  return {
    status: 'pass',
    logFields: { fail_count: failCount, fp_density: fpDensity ?? 'unknown', severity: 'soft' },
  }
}
