/**
 * Point 14 — Regeneration pass and publish
 * Bucket A: publish-staging.mjs runs autonomously (skip-list enforced)
 */

import { existsSync } from 'fs'

export const POINT_ID = '14'
export const BUCKET = 'A'

export async function run(ctx) {
  const { slug, siteDir, platformDir, dryRun, log, execTool } = ctx

  const tool = `${platformDir}/tools/publish-staging.mjs`
  if (!existsSync(tool)) {
    return { status: 'fail', message: `publish-staging.mjs not found` }
  }

  log.info('Publishing staging → content/articles/ (skip-list enforced)…')

  if (!dryRun) {
    const r = execTool(`node "${tool}" --site ${slug} --all`)
    if (!r.ok) {
      return { status: 'fail', message: `publish-staging failed: ${r.stderr.slice(0, 200)}` }
    }
    const countLine = r.stdout.split('\n').find(l => /published|moved|skipped/i.test(l)) ?? ''
    if (countLine) log.info(countLine)
  } else {
    log.info('(dry-run) would run publish-staging.mjs --all')
  }

  return { status: 'pass', logFields: { tool: 'publish-staging' } }
}
