/**
 * Point 10 — Source products + ASINs per article
 * Bucket A: source-products-rainforest.py with v1.6 policy filters
 */

import { existsSync } from 'fs'
import { join } from 'path'

export const POINT_ID = '10'
export const BUCKET = 'A'

export async function run(ctx) {
  const { slug, siteDir, platformDir, dryRun, log, execTool, state } = ctx

  const niche = state.inputs?.niche ?? null
  const sourceTool = `${platformDir}/tools/source-products-rainforest.py`

  if (!existsSync(sourceTool)) {
    return { status: 'fail', message: `source-products-rainforest.py not found at ${sourceTool}` }
  }

  const dtcConfig = niche ? `${siteDir}/config/dtc-brands/${niche}.yaml` : null
  const hasDtc = dtcConfig && existsSync(dtcConfig)

  log.info(`Sourcing products via Rainforest${hasDtc ? ` (DTC config: ${niche})` : ' (no DTC config)'}…`)

  if (!dryRun) {
    const dtcFlag = hasDtc ? `--dtc-config "${dtcConfig}"` : ''
    // --resume: skip articles already sourced in prior runs (state at /tmp/source-products-*-state.json)
    // Timeout: 90 min — 306 articles × ~3s/article
    const r = execTool(
      `cd "${siteDir}" && python3 "${sourceTool}" --site ${slug} --resume ${dtcFlag}`,
      { timeout: 5400000 },
    )
    if (!r.ok) {
      return { status: 'fail', message: `Product sourcing failed: ${r.stderr.slice(0, 800)}` }
    }
    const summaryLine = r.stdout.split('\n').find(l => /products?.*sourced|complete|done/i.test(l)) ?? ''
    if (summaryLine) log.info(summaryLine)
  } else {
    log.info(`(dry-run) would run source-products-rainforest.py${hasDtc ? ' with DTC config' : ''}`)
  }

  return {
    status: 'pass',
    logFields: { niche: niche ?? 'none', dtc_config: hasDtc ? niche : 'none' },
  }
}
