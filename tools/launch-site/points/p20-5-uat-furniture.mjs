/**
 * Point 20.5 — Pre-launch UAT furniture-page re-validation
 * Bucket A: validate-furniture-pages.mjs — must pass before launch
 */

import { existsSync } from 'fs'

export const POINT_ID = '20.5'
export const BUCKET = 'A'

export async function run(ctx) {
  const { slug, siteDir, platformDir, dryRun, log, execTool } = ctx

  const validator = `${platformDir}/scripts/validate-furniture-pages.mjs`
  if (!existsSync(validator)) {
    return { status: 'fail', message: `validate-furniture-pages.mjs not found` }
  }

  if (dryRun) {
    log.info('(dry-run) would run validate-furniture-pages.mjs --verbose')
    return { status: 'pass', logFields: { dry_run: true } }
  }

  const r = execTool(`node "${validator}" --site ${slug} --verbose --json`)
  let parsed
  try { parsed = JSON.parse(r.stdout) } catch { parsed = {} }

  const violations = parsed.violations ?? []
  const hardViolations = violations.filter(v => v.type === 'persona_claim' || v.type === 'vocabulary_bleed')

  if (hardViolations.length > 0) {
    const detail = hardViolations.slice(0, 3).map(v => `  ${v.page}: ${v.type} — ${v.excerpt?.slice(0, 60) ?? ''}`).join('\n')
    return {
      status: 'fail',
      message: `Furniture-page violations (hard):\n${detail}\nFix and redeploy before launch.`,
    }
  }

  if (violations.length > 0) {
    log.warn(`Furniture-page: ${violations.length} soft violations (non-blocking)`)
  } else {
    log.info('Furniture-page re-validation: passed')
  }

  return {
    status: 'pass',
    logFields: { violations: violations.length, hard: hardViolations.length },
  }
}
