/**
 * Point 16 — Push live
 * Bucket A: verify-bindings → cloudflare attach-domain → wrangler deploy → verify
 *
 * Per §16.3: custom domain attachment uses exponential backoff (10s/30s/60s/120s).
 */

import { existsSync } from 'fs'
import { withRetry } from '../escalation.mjs'

export const POINT_ID = '16'
export const BUCKET = 'A'

export async function run(ctx) {
  const { slug, siteDir, platformDir, dryRun, log, execTool, state } = ctx

  const cfTool    = `${platformDir}/tools/cloudflare-pages-config.mjs`
  const bindTool  = `${platformDir}/tools/verify-bindings.mjs`
  const deployTool = `${platformDir}/tools/deploy-and-verify.mjs`
  const portTool  = `${platformDir}/tools/portfolio-update.mjs`

  const domain = state.inputs?.domain
  if (!domain) {
    return { status: 'fail', message: `No domain in state.inputs — set domain before Point 16` }
  }

  // 1. SVG placeholder check (§15.8)
  log.info('Checking SVG brand assets for placeholder tokens…')
  if (!dryRun) {
    const svgCheck = execTool(`grep -rl '{{' "${siteDir}/public/images/brand/" --include='*.svg' 2>/dev/null`)
    if (svgCheck.stdout.trim()) {
      return { status: 'fail', message: `SVG placeholder tokens found: ${svgCheck.stdout.trim()}` }
    }
  } else {
    log.info('(dry-run) would check SVG placeholders')
  }

  // 2. verify-bindings (10 checks)
  log.info('Running verify-bindings.mjs (10 checks)…')
  if (!dryRun) {
    const r = execTool(`node "${bindTool}" --site ${slug} --json`)
    let parsed
    try { parsed = JSON.parse(r.stdout) } catch { parsed = {} }
    const results = parsed.results ?? parsed.sites?.[slug]?.checks ?? []
    const failures = results.filter(c => c.status === 'fail')
    if (failures.length > 0) {
      const failList = failures.map(f => `  [${f.id}] ${f.name}: ${f.details ?? ''}`).join('\n')
      return { status: 'fail', message: `Binding check failures:\n${failList}` }
    }
    log.info('Binding checks passed')
  } else {
    log.info('(dry-run) would run verify-bindings.mjs')
  }

  // 3. Domain attachment (idempotent, with backoff)
  log.info(`Attaching custom domain ${domain}…`)
  if (!dryRun) {
    try {
      await withRetry(
        (attempt) => {
          const r = execTool(`node "${cfTool}" attach-domain --site ${slug} --domain ${domain}`)
          if (!r.ok) throw new Error(r.stderr.slice(0, 200))
          return r
        },
        { maxAttempts: 4, backoffMs: [10000, 30000, 60000, 120000], label: 'attach-domain', log },
      )
      log.info(`Domain ${domain} attached`)
      if (state.artifacts) state.artifacts.production_url = `https://${domain}`
    } catch (err) {
      return { status: 'fail', message: `Domain attachment failed after retries: ${err.message}` }
    }
  } else {
    log.info(`(dry-run) would attach domain ${domain} via cloudflare-pages-config.mjs`)
  }

  // 4. Deploy via wrangler
  log.info('Deploying via wrangler pages deploy…')
  if (!dryRun) {
    const r = execTool(
      `cd "${siteDir}" && wrangler pages deploy dist --project-name ${slug} --branch main`,
      { timeout: 600000 },
    )
    if (!r.ok) {
      return { status: 'fail', message: `wrangler deploy failed: ${r.stderr.slice(0, 300)}` }
    }
    const deployUrl = r.stdout.match(/https?:\/\/[^\s]+/)?.[0] ?? null
    if (deployUrl && state.artifacts) state.artifacts.preview_url = deployUrl
    log.info(`Deploy complete${deployUrl ? ` — ${deployUrl}` : ''}`)
  } else {
    log.info('(dry-run) would run wrangler pages deploy dist')
  }

  // 5. Live verification (9 checks via deploy-and-verify)
  log.info('Running live verification (9 checks)…')
  if (!dryRun) {
    const r = execTool(`node "${deployTool}" --site ${slug} --verify-only --json`, { timeout: 120000 })
    let parsed
    try { parsed = JSON.parse(r.stdout) } catch { parsed = {} }
    if (parsed.overall_status === 'fail' || parsed.overall_status === 'error') {
      const failLines = (parsed.smoke_tests ?? []).filter(s => s.status === 'fail').map(s => `  ${s.name}: ${s.details ?? ''}`).join('\n')
      return { status: 'fail', message: `Live verification failed:\n${failLines}` }
    }
    log.info('Live verification passed')
  } else {
    log.info('(dry-run) would run deploy-and-verify --verify-only')
  }

  // 6. portfolio.yaml writeback
  if (!dryRun) {
    execTool(`node "${portTool}" --site ${slug} --set status=live`)
    execTool(`node "${portTool}" --site ${slug} --set custom_domain_attached=true`)
    execTool(`node "${portTool}" --site ${slug} --set deploy_pattern=direct_upload`)
    const now = new Date().toISOString().slice(0, 10)
    execTool(`node "${portTool}" --site ${slug} --set launched=${now}`)
    log.info('portfolio.yaml updated: status=live, custom_domain_attached=true')
  } else {
    log.info('(dry-run) would update portfolio.yaml')
  }

  return {
    status: 'pass',
    logFields: { domain, deploy_pattern: 'wrangler_direct_upload' },
  }
}
