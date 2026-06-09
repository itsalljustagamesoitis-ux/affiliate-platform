/**
 * Point 13.7 — Meta-leakage validator
 * Bucket A: HARD failure, exit 1, blocks publish
 */

import { existsSync } from 'fs'
import { validatorLoop } from '../escalation.mjs'

export const POINT_ID = '13.7'
export const BUCKET = 'A'

export async function run(ctx) {
  const { slug, siteDir, platformDir, dryRun, log, execTool } = ctx

  const validator = `${platformDir}/scripts/validate-meta-leakage.mjs`
  if (!existsSync(validator)) {
    return { status: 'fail', message: `validate-meta-leakage.mjs not found` }
  }

  if (dryRun) {
    log.info('(dry-run) would run validate-meta-leakage.mjs')
    return { status: 'pass', logFields: { dry_run: true } }
  }

  const result = await validatorLoop(
    () => {
      const r = execTool(`node "${validator}" --site ${slug} --json`)
      let parsed
      try { parsed = JSON.parse(r.stdout) } catch { parsed = {} }
      const failIds = (parsed.failures ?? []).map(f => f.id ?? f.slug)
      return { failCount: failIds.length, failIds, output: r.stdout }
    },
    (failIds) => {
      log.warn(`Meta-leakage: regenerating ${failIds.length} articles…`)
      for (const id of failIds) {
        execTool(`cd "${siteDir}" && python3 producer/article_builder.py --force --id "${id}"`)
      }
    },
    { label: 'validate-meta-leakage', log },
  )

  if (result.status === 'skip_listed') {
    log.warn(`Meta-leakage: ${result.skipIds.length} articles moved to skip-list`)
    for (const id of result.skipIds) {
      execTool(`node "${platformDir}/tools/publish-staging.mjs" --site ${slug} --skip-list-add "${id}"`)
    }
    return { status: 'pass', logFields: { skip_listed: result.skipIds.length } }
  }

  return { status: 'pass', logFields: { fail_count: 0 } }
}
