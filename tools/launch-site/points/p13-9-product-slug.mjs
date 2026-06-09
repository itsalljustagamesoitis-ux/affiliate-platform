/**
 * Point 13.9 — Product slug resolution validator
 * Bucket A: HARD failure, blocks publish; fix or regenerate on failure
 */

import { existsSync } from 'fs'
import { validatorLoop } from '../escalation.mjs'

export const POINT_ID = '13.9'
export const BUCKET = 'A'

export async function run(ctx) {
  const { slug, siteDir, platformDir, dryRun, log, execTool } = ctx

  const validator = `${platformDir}/scripts/validate-product-slug-resolution.mjs`
  if (!existsSync(validator)) {
    return { status: 'fail', message: `validate-product-slug-resolution.mjs not found` }
  }

  if (dryRun) {
    log.info('(dry-run) would run validate-product-slug-resolution.mjs')
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
      log.warn(`Product slug: ${failIds.length} unresolved slugs — regenerating articles…`)
      for (const id of failIds) {
        execTool(`cd "${siteDir}" && python3 producer/article_builder.py --force --id "${id}"`)
      }
    },
    { label: 'validate-product-slug-resolution', log },
  )

  if (result.status === 'skip_listed') {
    log.warn(`Product slug: ${result.skipIds.length} articles moved to skip-list`)
    for (const id of result.skipIds) {
      execTool(`node "${platformDir}/tools/publish-staging.mjs" --site ${slug} --skip-list-add "${id}"`)
    }
    return { status: 'pass', logFields: { skip_listed: result.skipIds.length } }
  }

  return { status: 'pass', logFields: { fail_count: 0 } }
}
