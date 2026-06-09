/**
 * Point 15 — Local build smoke
 * Bucket A: npm run build (includes data-store cache invalidation per §15.7)
 */

import { existsSync } from 'fs'
import { join } from 'path'

export const POINT_ID = '15'
export const BUCKET = 'A'

export async function run(ctx) {
  const { slug, siteDir, platformDir, dryRun, log, execTool } = ctx

  const pkg = join(siteDir, 'package.json')
  if (!existsSync(pkg)) {
    return { status: 'fail', message: `package.json not found in ${siteDir}` }
  }

  log.info('Running npm run build (includes data-store cache clear)…')

  if (!dryRun) {
    const r = execTool(`cd "${siteDir}" && npm run build`, { timeout: 600000 })
    if (!r.ok) {
      const failLine = r.stdout.split('\n').find(l => /FAIL|error/i.test(l)) ?? r.stderr.slice(0, 200)
      return { status: 'fail', message: `Build failed: ${failLine}` }
    }
    const failLines = r.stdout.split('\n').filter(l => l.includes('FAIL'))
    if (failLines.length > 0) {
      return { status: 'fail', message: `Build validator FAILs:\n${failLines.slice(0, 5).join('\n')}` }
    }
    const warnCount = (r.stdout.match(/WARN/g) ?? []).length
    if (warnCount > 0) log.warn(`Build passed with ${warnCount} WARNs (non-blocking)`)
    log.info('Build passed — no FAILs')
  } else {
    log.info('(dry-run) would run npm run build')
  }

  return { status: 'pass', logFields: { tool: 'npm_run_build' } }
}
