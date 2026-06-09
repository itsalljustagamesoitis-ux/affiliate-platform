/**
 * Point 17 — GA4 setup
 * Bucket C (17a): Keith creates property + provides measurement ID
 * Bucket A (17b): Claude Code injects ID, redeploys, verifies
 */

import { existsSync, readFileSync, writeFileSync } from 'fs'
import { join } from 'path'
import yaml from 'js-yaml'
import { buildHaltRequest, formatHaltMessage } from '../escalation.mjs'

export const POINT_ID = '17'
export const BUCKET = 'C'

export async function run(ctx) {
  const { slug, siteDir, platformDir, dryRun, log, execTool, state } = ctx

  const domain = state.inputs?.domain ?? `${slug}.com`
  const existingId = state.inputs?.ga4_measurement_id

  if (existingId) {
    log.info(`GA4 measurement ID: ${existingId} (from state) — wiring…`)
    return wireGA4(ctx, existingId, domain)
  }

  // Halt — Keith must create the GA4 property
  const request = buildHaltRequest(
    '17',
    'GA4 property required',
    [
      'Sign in to analytics.google.com',
      'Admin → Create Property → name after site',
      `Add web data stream pointing at: https://${domain}`,
      'Copy the measurement ID (format: G-XXXXXXXXXX)',
      `Reply with measurement ID, then resume:`,
      `  node tools/launch-site.mjs --resume ${slug} --ga4-id G-XXXXXXXXXX`,
    ],
    10,
  )

  if (dryRun) {
    log.info('(dry-run) would halt for GA4 property creation')
    return { status: 'pass', logFields: { halt: 'skipped_dryrun', sub: '17a' } }
  }

  log.warn(formatHaltMessage(request, slug))
  return { status: 'halt', haltRequest: request }
}

async function wireGA4(ctx, measurementId, domain) {
  const { slug, siteDir, platformDir, dryRun, log, execTool } = ctx
  const cfgPath = join(siteDir, 'site.config.yaml')
  const portTool = `${platformDir}/tools/portfolio-update.mjs`

  if (!dryRun) {
    if (!existsSync(cfgPath)) {
      return { status: 'fail', message: `site.config.yaml not found` }
    }
    const cfg = yaml.load(readFileSync(cfgPath, 'utf-8'))
    if (!cfg.analytics) cfg.analytics = {}

    // Idempotency: skip write + redeploy if ID is already set to the same value
    if (cfg.analytics.ga4_measurement_id === measurementId) {
      log.info(`GA4 already set to ${measurementId} — skipping write and redeploy`)
      return { status: 'pass', logFields: { ga4_id: measurementId, sub: '17b', idempotent: true } }
    }

    cfg.analytics.ga4_measurement_id = measurementId
    writeFileSync(cfgPath, yaml.dump(cfg, { lineWidth: 120 }), 'utf-8')
    log.info(`Updated site.config.yaml: analytics.ga4_measurement_id = ${measurementId}`)

    // Redeploy
    const r = execTool(
      `cd "${siteDir}" && npm run build && wrangler pages deploy dist --project-name ${slug} --branch main`,
      { timeout: 600000 },
    )
    if (!r.ok) {
      return { status: 'fail', message: `Redeploy with GA4 failed: ${r.stderr.slice(0, 200)}` }
    }

    // Verify HTML source contains GA4 tag
    const verify = execTool(`curl -s "https://${domain}" | grep -c "googletagmanager.com/gtag/js?id=${measurementId}"`)
    if (verify.stdout.trim() === '0') {
      log.warn(`GA4 tag not found in HTML source for ${domain} — may need cache clear`)
    } else {
      log.info(`GA4 tag verified in HTML source`)
    }

    execTool(`node "${portTool}" --site ${slug} --set ga4_id=${measurementId}`)
    log.info(`portfolio.yaml updated: ga4_id=${measurementId}`)
  } else {
    log.info(`(dry-run) would inject GA4 ID ${measurementId} and redeploy`)
  }

  return {
    status: 'pass',
    logFields: { ga4_id: measurementId, sub: '17b' },
  }
}
