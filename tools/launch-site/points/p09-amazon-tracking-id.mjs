/**
 * Point 9 — Amazon Associates tracking ID
 * Bucket C: Keith identity-bound halt
 *
 * Halts with structured request. On resume with --amazon-tracking-id <id>,
 * wires AMAZON_TAG to Cloudflare Pages via cloudflare-pages-config.mjs and
 * updates site.config.yaml.
 */

import { readFileSync, writeFileSync } from 'fs'
import { join } from 'path'
import { existsSync } from 'fs'
import yaml from 'js-yaml'
import { buildHaltRequest, formatHaltMessage } from '../escalation.mjs'

export const POINT_ID = '9'
export const BUCKET = 'C'

function deriveProposedTrackingId(slug, platformDir) {
  // Prefer spec file value if present and non-placeholder
  const specPath = join(platformDir, 'sites', `${slug}.spec.yaml`)
  try {
    if (existsSync(specPath)) {
      const spec = yaml.load(readFileSync(specPath, 'utf-8'))
      const specId = spec?.amazon_associates_id
      if (specId && /^[a-z0-9-]+-20$/i.test(specId)) return specId
    }
  } catch { /* fall through to derived */ }
  // Derive from slug: Amazon tracking IDs up to 20 chars, format <prefix>-20
  const clean = slug.replace(/[^a-z0-9-]/gi, '').toLowerCase()
  const maxSlugLen = 17  // leaves room for '-20'
  return `${clean.slice(0, maxSlugLen)}-20`
}

function getSiteConfigPath(siteDir) {
  return join(siteDir, 'site.config.yaml')
}

export async function run(ctx) {
  const { slug, siteDir, platformDir, dryRun, log, execTool, state } = ctx

  const existingId = state.inputs?.amazon_tracking_id
  const proposed = deriveProposedTrackingId(slug, platformDir)

  // If ID already provided (resume path), wire it
  if (existingId) {
    log.info(`Amazon tracking ID: ${existingId} (from state) — wiring…`)
    return wireTrackingId(ctx, existingId)
  }

  // Halt — Keith must create the tracking ID
  const request = buildHaltRequest(
    '9',
    'Amazon Associates tracking ID required',
    [
      'Log in to Amazon Associates dashboard (affiliate-program.amazon.com)',
      `Create new tracking ID with the exact string: ${proposed}`,
      'Confirm creation in the dashboard',
      `Reply with: "tracking ID created" then resume:`,
      `  node tools/launch-site.mjs --resume ${slug} --amazon-tracking-id ${proposed}`,
    ],
    5,
  )

  if (dryRun) {
    log.info(`(dry-run) would halt — proposed tracking ID: ${proposed}`)
    return { status: 'pass', logFields: { halt: 'skipped_dryrun', proposed_id: proposed } }
  }

  log.warn(formatHaltMessage(request, slug))
  return {
    status: 'halt',
    haltRequest: request,
    logFields: { proposed_id: proposed },
  }
}

async function wireTrackingId(ctx, trackingId) {
  const { slug, siteDir, platformDir, dryRun, log, execTool } = ctx
  const cfTool = `${platformDir}/tools/cloudflare-pages-config.mjs`
  const configPath = getSiteConfigPath(siteDir)

  // Update site.config.yaml
  if (!dryRun) {
    if (!existsSync(configPath)) {
      return { status: 'fail', message: `site.config.yaml not found at ${configPath}` }
    }
    const cfg = yaml.load(readFileSync(configPath, 'utf-8'))
    if (!cfg.affiliate) cfg.affiliate = {}
    cfg.affiliate.amazon_tracking_id = trackingId
    writeFileSync(configPath, yaml.dump(cfg, { lineWidth: 120 }), 'utf-8')
    log.info(`Updated site.config.yaml: affiliate.amazon_tracking_id = ${trackingId}`)

    // Wire AMAZON_TAG to Cloudflare Pages if project already exists.
    // If not (project created at Point 16), wiring happens during Point 16 deploy setup.
    const rProd = execTool(`node "${cfTool}" set-env --site ${slug} --env production --key AMAZON_TAG --value ${trackingId}`)
    if (!rProd.ok) {
      if (rProd.stderr.includes('no cloudflare_project') || rProd.stderr.includes('not found')) {
        log.info('CF Pages project not yet created — AMAZON_TAG will be wired at Point 16 deploy')
      } else {
        return { status: 'fail', message: `CF set-env production failed: ${rProd.stderr.slice(0, 200)}` }
      }
    } else {
      const rPrev = execTool(`node "${cfTool}" set-env --site ${slug} --env preview --key AMAZON_TAG --value ${trackingId}`)
      if (!rPrev.ok) return { status: 'fail', message: `CF set-env preview failed: ${rPrev.stderr.slice(0, 200)}` }
      log.info(`AMAZON_TAG wired to Cloudflare Pages (production + preview)`)
    }
  } else {
    log.info(`(dry-run) would set AMAZON_TAG=${trackingId} in site.config.yaml + CF Pages`)
  }

  return {
    status: 'pass',
    logFields: { tracking_id: trackingId },
  }
}
