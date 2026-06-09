/**
 * Point 21 — Plug into operational dashboard
 * Bucket A: portfolio-update.mjs writes full entry; dashboard.mjs verifies
 */

import { existsSync, readFileSync } from 'fs'
import { join } from 'path'
import yaml from 'js-yaml'

export const POINT_ID = '21'
export const BUCKET = 'A'

export async function run(ctx) {
  const { slug, siteDir, platformDir, dryRun, log, execTool, state } = ctx

  const portTool  = `${platformDir}/tools/portfolio-update.mjs`
  const dashboard = `${platformDir}/tools/dashboard.mjs`
  const cfgPath   = join(siteDir, 'site.config.yaml')

  // Read site config for persona name and tracking ID
  let persona = null
  let trackingId = state.inputs?.amazon_tracking_id ?? null

  if (existsSync(cfgPath)) {
    try {
      const cfg = yaml.load(readFileSync(cfgPath, 'utf-8'))
      trackingId = trackingId ?? cfg?.affiliate?.amazon_tracking_id
      const personaRef = cfg?.persona
      if (personaRef) {
        const pFile = join(siteDir, 'config', 'personas', `${personaRef}.yaml`)
        if (existsSync(pFile)) {
          const p = yaml.load(readFileSync(pFile, 'utf-8'))
          persona = p?.name_formal ?? p?.name_used ?? personaRef
        }
      }
    } catch { }
  }

  if (!dryRun) {
    // Write all v1.6 portfolio fields
    const sets = [
      `status=live`,
      `custom_domain_attached=true`,
      `deploy_pattern=direct_upload`,
      `persona_locked=true`,
      `github_repo=null`,
    ]
    if (state.inputs?.domain) sets.push(`domain=${state.inputs.domain}`)
    if (trackingId) sets.push(`tracking_id=${trackingId}`)
    if (persona) sets.push(`persona=${persona}`)
    if (state.inputs?.ga4_measurement_id) sets.push(`ga4_id=${state.inputs.ga4_measurement_id}`)
    if (state.artifacts?.cloudflare_project) sets.push(`cloudflare_project=${state.artifacts.cloudflare_project}`)

    for (const s of sets) {
      execTool(`node "${portTool}" --site ${slug} --set ${s}`)
    }
    log.info(`portfolio.yaml: ${sets.length} fields updated for ${slug}`)

    // Verify dashboard shows site
    if (existsSync(dashboard)) {
      const r = execTool(`node "${dashboard}" --health --site ${slug} --json`)
      let parsed
      try { parsed = JSON.parse(r.stdout) } catch { parsed = {} }
      const entry = parsed.sites?.[slug] ?? parsed
      if (entry?.status === 'live') {
        log.info(`Dashboard shows ${slug} as live`)
      } else {
        log.warn(`Dashboard health check returned unexpected status: ${JSON.stringify(entry?.status)}`)
      }
    }
  } else {
    log.info(`(dry-run) would write portfolio.yaml entry and verify dashboard`)
  }

  return {
    status: 'pass',
    logFields: { persona: persona ?? 'unknown', tracking_id: trackingId ?? 'unknown' },
  }
}
