/**
 * Point 15.6 — Content-existence validator
 * Bucket A: runs against dist/ after build, before deploy; HARD failure blocks deploy
 */

import { existsSync } from 'fs'

export const POINT_ID = '15.6'
export const BUCKET = 'A'

const MAX_REBUILD_ATTEMPTS = 2

export async function run(ctx) {
  const { slug, siteDir, platformDir, dryRun, log, execTool } = ctx

  const validator = `${platformDir}/scripts/validate-content-existence.mjs`
  if (!existsSync(validator)) {
    return { status: 'fail', message: `validate-content-existence.mjs not found` }
  }

  if (dryRun) {
    log.info('(dry-run) would run validate-content-existence.mjs against dist/')
    return { status: 'pass', logFields: { dry_run: true } }
  }

  for (let attempt = 1; attempt <= MAX_REBUILD_ATTEMPTS + 1; attempt++) {
    const r = execTool(`node "${validator}" --site ${slug} --json`)
    let parsed
    try { parsed = JSON.parse(r.stdout) } catch { parsed = {} }

    const failCount = parsed.fail_count ?? (parsed.failures ?? []).length
    if (failCount === 0) {
      log.info('Content-existence: all articles have content')
      return { status: 'pass', logFields: { fail_count: 0, attempt } }
    }

    if (attempt <= MAX_REBUILD_ATTEMPTS) {
      log.warn(`Content-existence: ${failCount} empty articles on attempt ${attempt} — clearing data-store and rebuilding…`)
      execTool(`rm -f "${siteDir}/node_modules/.astro/data-store.json"`)
      const build = execTool(`cd "${siteDir}" && npm run build`, { timeout: 600000 })
      if (!build.ok) {
        return { status: 'fail', message: `Rebuild attempt ${attempt} failed: ${build.stderr.slice(0, 200)}` }
      }
    } else {
      return {
        status: 'fail',
        message: `Content-existence: ${failCount} empty articles remain after ${MAX_REBUILD_ATTEMPTS} rebuild attempts — escalate to Keith`,
      }
    }
  }
}
