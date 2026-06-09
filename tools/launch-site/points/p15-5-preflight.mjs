/**
 * Point 15.5 — Pre-flight check
 * Bucket A: preflight.py runs autonomously — must exit 0 before Point 16
 */

import { existsSync } from 'fs'
import { join } from 'path'

export const POINT_ID = '15.5'
export const BUCKET = 'A'

export async function run(ctx) {
  const { slug, siteDir, platformDir, dryRun, log, execTool } = ctx

  const preflight = join(platformDir, 'scripts', 'preflight.py')
  const altPreflight = join(siteDir, 'producer', 'preflight.py')
  const tool = existsSync(preflight) ? preflight : existsSync(altPreflight) ? altPreflight : null

  if (!tool) {
    return { status: 'fail', message: `preflight.py not found in scripts/ or producer/` }
  }

  log.info('Running pre-flight checks…')

  if (!dryRun) {
    const r = execTool(`cd "${siteDir}" && python3 "${tool}" --site ${slug}`)
    const stdout = r.stdout ?? ''
    const failLines = stdout.split('\n').filter(l => l.includes('FAIL'))
    if (!r.ok || failLines.length > 0) {
      return {
        status: 'fail',
        message: `Pre-flight FAIL:\n${failLines.slice(0, 5).join('\n') || r.stderr.slice(0, 200)}`,
      }
    }
    const warnCount = (stdout.match(/WARN/g) ?? []).length
    if (warnCount > 0) log.warn(`Pre-flight: ${warnCount} WARNs (non-blocking)`)
    log.info('Pre-flight passed')
  } else {
    log.info('(dry-run) would run preflight.py')
  }

  return { status: 'pass', logFields: { tool: 'preflight' } }
}
