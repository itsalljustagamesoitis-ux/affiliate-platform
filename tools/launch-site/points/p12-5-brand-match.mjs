/**
 * Point 12.5 — Brand-match audit gate
 * Bucket A: run validator; FAILs → re-source; second-pass FAILs → escalate to Keith (D)
 */

import { existsSync } from 'fs'

export const POINT_ID = '12.5'
export const BUCKET = 'A'

const MAX_SOURCING_PASSES = 2

export async function run(ctx) {
  const { slug, siteDir, platformDir, dryRun, log, execTool } = ctx

  const validator = `${platformDir}/scripts/validate-brand-match.mjs`
  const sourceTool = `${platformDir}/tools/source-products-rainforest.py`

  if (!existsSync(validator)) {
    return { status: 'fail', message: `validate-brand-match.mjs not found` }
  }

  for (let pass = 1; pass <= MAX_SOURCING_PASSES; pass++) {
    log.info(`Brand-match audit pass ${pass}/${MAX_SOURCING_PASSES}…`)

    if (dryRun) {
      log.info('(dry-run) would run validate-brand-match.mjs')
      return { status: 'pass', logFields: { pass: 1 } }
    }

    const r = execTool(`node "${validator}" --site ${slug}`)
    // Validator outputs styled text; parse FAIL count from output.
    // Success: "No FAIL articles" or "FAIL:    0"
    const combined = (r.stdout + r.stderr).replace(/\x1b\[[0-9;]*m/g, '')
    if (!r.ok && !combined.includes('FAIL:')) {
      return { status: 'fail', message: `validate-brand-match errored: ${combined.slice(0, 200)}` }
    }
    const failMatch = combined.match(/FAIL:\s+(\d+)/)
    const failCount = failMatch ? parseInt(failMatch[1], 10) : 0
    if (failCount === 0) {
      log.info(`Brand-match: 0 failures — pass`)
      return { status: 'pass', logFields: { pass, fail_count: 0 } }
    }

    if (pass < MAX_SOURCING_PASSES) {
      log.warn(`Brand-match: ${failCount} failures — re-sourcing with brand-specific queries…`)
      execTool(`cd "${siteDir}" && python3 "${sourceTool}" --site ${slug} --brand-queries-only`)
    } else {
      log.warn(`Brand-match: ${failCount} failures after ${MAX_SOURCING_PASSES} passes — escalating to Keith`)
      return {
        status: 'halt',
        message: `Brand-match has ${failCount} persistent failures after re-sourcing. Manual review required.`,
        logFields: { pass, fail_count: failCount },
      }
    }
  }
}
