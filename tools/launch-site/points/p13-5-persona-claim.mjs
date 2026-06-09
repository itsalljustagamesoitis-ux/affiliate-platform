/**
 * Point 13.5 — Persona-claim audit gate
 * Bucket A: validate-persona-claims.mjs; HARD failures regenerate (max 3 attempts)
 */

import { existsSync } from 'fs'
import { validatorLoop } from '../escalation.mjs'

export const POINT_ID = '13.5'
export const BUCKET = 'A'

export async function run(ctx) {
  const { slug, siteDir, platformDir, dryRun, log, execTool } = ctx

  const validator = `${platformDir}/scripts/validate-persona-claims.mjs`
  if (!existsSync(validator)) {
    return { status: 'fail', message: `validate-persona-claims.mjs not found` }
  }

  if (dryRun) {
    log.info('(dry-run) would run validate-persona-claims.mjs')
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
      for (const id of failIds) {
        execTool(`cd "${siteDir}" && python3 producer/article_builder.py --force --id "${id}"`)
      }
    },
    { label: 'validate-persona-claims', log },
  )

  if (result.status === 'skip_listed') {
    log.warn(`Persona-claim validator: ${result.skipIds.length} articles moved to skip-list after 3 attempts`)
    for (const id of result.skipIds) {
      execTool(`node "${platformDir}/tools/publish-staging.mjs" --site ${slug} --skip-list-add "${id}"`)
    }
    return { status: 'pass', logFields: { skip_listed: result.skipIds.length } }
  }

  return { status: 'pass', logFields: { fail_count: 0 } }
}
