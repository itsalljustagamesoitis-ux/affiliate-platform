/**
 * Point 11 — Source image bank
 * Bucket A: source-images-pexels.mjs runs autonomously
 */

import { existsSync } from 'fs'

export const POINT_ID = '11'
export const BUCKET = 'A'

export async function run(ctx) {
  const { slug, siteDir, platformDir, dryRun, log, execTool } = ctx

  const tool = `${platformDir}/tools/source-images-pexels.mjs`
  if (!existsSync(tool)) {
    return { status: 'fail', message: `source-images-pexels.mjs not found` }
  }

  log.info('Sourcing image bank from Pexels…')

  if (!dryRun) {
    const r = execTool(`node "${tool}" --site ${slug}`)
    if (!r.ok) {
      return { status: 'fail', message: `Image sourcing failed: ${r.stderr.slice(0, 200)}` }
    }
    const countLine = r.stdout.split('\n').find(l => /image|downloaded|sourced/i.test(l)) ?? ''
    if (countLine) log.info(countLine)
  } else {
    log.info('(dry-run) would run source-images-pexels.mjs')
  }

  return { status: 'pass', logFields: { tool: 'source-images-pexels' } }
}
