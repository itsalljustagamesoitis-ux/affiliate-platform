/**
 * Point 12 — Assign images per article
 * Bucket A: assign-article-images.mjs runs autonomously
 */

import { existsSync } from 'fs'

export const POINT_ID = '12'
export const BUCKET = 'A'

export async function run(ctx) {
  const { slug, siteDir, platformDir, dryRun, log, execTool } = ctx

  const tool = `${platformDir}/tools/assign-article-images.mjs`
  if (!existsSync(tool)) {
    return { status: 'fail', message: `assign-article-images.mjs not found` }
  }

  log.info('Assigning images per article…')

  if (!dryRun) {
    const r = execTool(`node "${tool}" --site ${slug}`)
    if (!r.ok) {
      return { status: 'fail', message: `Image assignment failed: ${r.stderr.slice(0, 200)}` }
    }
    const countLine = r.stdout.split('\n').find(l => /assigned|article/i.test(l)) ?? ''
    if (countLine) log.info(countLine)
  } else {
    log.info('(dry-run) would run assign-article-images.mjs')
  }

  return { status: 'pass', logFields: { tool: 'assign-article-images' } }
}
