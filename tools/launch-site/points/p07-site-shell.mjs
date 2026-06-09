/**
 * Point 7 — Site shell
 * Bucket A: initialise-site.mjs + portfolio bootstrap + verify-site-shell.mjs
 */

import { existsSync, readFileSync } from 'fs'
import yaml from 'js-yaml'

export const POINT_ID = '7'
export const BUCKET = 'A'

export async function run(ctx) {
  const { slug, siteDir, platformDir, dryRun, log, execTool } = ctx

  // initialise-site.mjs — requires spec file at ~/affiliate-platform/sites/<slug>.spec.yaml
  const initTool   = `${platformDir}/tools/initialise-site.mjs`
  const updateTool = `${platformDir}/tools/portfolio-update.mjs`
  const shellTool  = `${platformDir}/tools/verify-site-shell.mjs`
  const specPath   = `${platformDir}/sites/${slug}.spec.yaml`

  log.info('Running initialise-site.mjs…')
  if (!dryRun) {
    if (!existsSync(specPath)) {
      return { status: 'fail', message: `Spec file not found: ${specPath}. Create spec before launching.` }
    }
    // Skip scaffold if site directory already exists (idempotent re-run after prior partial failure)
    const homedir = (await import('os')).homedir()
    const siteDirPath = `${homedir}/${slug}`
    if (existsSync(siteDirPath)) {
      log.info(`Site directory ${siteDirPath} already exists — skipping initialise-site.mjs`)
    } else {
      const r = execTool(`node "${initTool}" --spec "${specPath}"`)
      if (!r.ok) {
        return { status: 'fail', message: `initialise-site failed: ${r.stderr.slice(0, 200)}` }
      }
      log.info(r.stdout.split('\n').find(l => l.includes('✓')) ?? 'initialise-site complete')
    }
  } else {
    log.info(`(dry-run) would run initialise-site.mjs --spec sites/${slug}.spec.yaml`)
  }

  // Bootstrap portfolio.yaml entry — verify-site-shell requires the site to be registered.
  // initialise-site.mjs Phase 5 (which does this normally) only runs under --proceed (cloud
  // resource creation). We register a minimal pre_launch entry here so the shell check can run.
  log.info('Bootstrapping portfolio.yaml entry…')
  if (!dryRun) {
    let domain = slug  // fallback
    try {
      const spec = yaml.load(readFileSync(specPath, 'utf-8'))
      if (spec?.domain) domain = spec.domain
    } catch { /* spec parse error — continue with slug fallback */ }

    const r1 = execTool(`node "${updateTool}" --site ${slug} --set domain=${domain}`)
    if (!r1.ok) {
      return { status: 'fail', message: `portfolio-update (domain) failed: ${r1.stderr.slice(0, 200)}` }
    }
    const r2 = execTool(`node "${updateTool}" --site ${slug} --set status=pre_launch`)
    if (!r2.ok) {
      return { status: 'fail', message: `portfolio-update (status) failed: ${r2.stderr.slice(0, 200)}` }
    }
    const r3 = execTool(`node "${updateTool}" --site ${slug} --set deploy_pattern=direct_upload`)
    if (!r3.ok) log.warn('Could not set deploy_pattern — non-blocking')
    log.info('portfolio.yaml entry bootstrapped')
  } else {
    log.info('(dry-run) would bootstrap portfolio.yaml entry')
  }

  // verify-site-shell.mjs — structural check only (no --strict).
  // Checks 12 (pipeline empty), 23 (portfolio fields), 30 (submodule pin), 32/33 (SVG placeholders)
  // are expected failures at Point 7 and are resolved by later points (8, 16, 11 respectively).
  const P7_EXPECTED_FAILS = new Set([12, 23, 30, 32, 33])
  log.info('Running verify-site-shell.mjs (structural check)…')
  if (!dryRun) {
    const r = execTool(`node "${shellTool}" --site ${slug} --json`)
    let parsed
    try {
      parsed = JSON.parse(r.stdout)
    } catch {
      return { status: 'fail', message: `verify-site-shell returned unparseable output: ${r.stdout.slice(0, 100)}` }
    }
    const siteData = parsed?.sites?.[slug] ?? parsed
    const checks = siteData.checks ?? []
    const realBlockers = checks.filter(c => c.status === 'fail' && !P7_EXPECTED_FAILS.has(c.id))
    if (realBlockers.length > 0) {
      const ids = realBlockers.map(c => c.id).join(', ')
      return { status: 'fail', message: `Site shell has unexpected blockers (checks ${ids})` }
    }
    const expectedFails = checks.filter(c => c.status === 'fail' && P7_EXPECTED_FAILS.has(c.id))
    if (expectedFails.length > 0) {
      log.info(`Expected-at-stage failures (will be resolved by later points): checks ${expectedFails.map(c => c.id).join(', ')}`)
    }
    const warnings = siteData.warnings ?? 0
    if (warnings > 0) log.info(`${warnings} warning(s) (non-blocking)`)
  } else {
    log.info('(dry-run) would run verify-site-shell.mjs --json')
  }

  return { status: 'pass', logFields: { tool: 'initialise-site+verify-site-shell' } }
}
