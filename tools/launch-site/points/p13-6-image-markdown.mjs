/**
 * Point 13.6 — Image markdown validator
 * Bucket A: validate-image-markdown.mjs; HARD failures → fix-image-markdown.py
 */

import { existsSync } from 'fs'
import { join } from 'path'

export const POINT_ID = '13.6'
export const BUCKET = 'A'

export async function run(ctx) {
  const { slug, siteDir, platformDir, dryRun, log, execTool } = ctx

  const validator = `${platformDir}/scripts/validate-image-markdown.mjs`
  if (!existsSync(validator)) {
    return { status: 'fail', message: `validate-image-markdown.mjs not found` }
  }

  if (dryRun) {
    log.info('(dry-run) would run validate-image-markdown.mjs')
    return { status: 'pass', logFields: { dry_run: true } }
  }

  const r = execTool(`node "${validator}" --site ${slug} --json`)
  let parsed
  try { parsed = JSON.parse(r.stdout) } catch { parsed = {} }

  const failCount = parsed.fail_count ?? (parsed.failures ?? []).length
  if (failCount === 0) {
    return { status: 'pass', logFields: { fail_count: 0 } }
  }

  log.warn(`Image markdown: ${failCount} failures — running fix-image-markdown.py…`)

  const fixer = join(siteDir, 'producer', 'fix-image-markdown.py')
  if (existsSync(fixer)) {
    const fix = execTool(`cd "${siteDir}" && python3 producer/fix-image-markdown.py --all`)
    if (!fix.ok) {
      return { status: 'fail', message: `fix-image-markdown.py failed: ${fix.stderr.slice(0, 200)}` }
    }
    const check = execTool(`node "${validator}" --site ${slug} --json`)
    let rechk
    try { rechk = JSON.parse(check.stdout) } catch { rechk = {} }
    const remainFail = rechk.fail_count ?? (rechk.failures ?? []).length
    if (remainFail > 0) {
      return { status: 'fail', message: `Image markdown: ${remainFail} failures remain after auto-fix` }
    }
    log.info('Image markdown auto-fix applied — all clear')
  } else {
    return { status: 'fail', message: `Image markdown: ${failCount} failures, no fixer found at ${fixer}` }
  }

  return { status: 'pass', logFields: { auto_fixed: failCount } }
}
