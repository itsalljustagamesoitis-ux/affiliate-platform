/**
 * Point 19 — Google Search Console
 * Bucket C (19a): Keith creates Domain property + provides TXT verification string
 * Bucket A (19b): Claude Code adds DNS TXT record via cloudflare-pages-config.mjs
 */

import { buildHaltRequest, formatHaltMessage } from '../escalation.mjs'

export const POINT_ID = '19'
export const BUCKET = 'C'

export async function run(ctx) {
  const { slug, siteDir, platformDir, dryRun, log, execTool, state } = ctx

  const domain = state.inputs?.domain ?? `${slug}.com`
  const existingTxt = state.inputs?.gsc_txt_record

  if (existingTxt) {
    log.info(`GSC TXT record: ${existingTxt.slice(0, 30)}… — adding DNS record…`)
    return wireGsc(ctx, existingTxt, domain)
  }

  const request = buildHaltRequest(
    '19',
    'Google Search Console verification required',
    [
      'Sign in to search.google.com/search-console',
      `Add property → Domain property → enter: ${domain}`,
      'Note the DNS TXT verification string shown by GSC',
      `Reply with the TXT string, then resume:`,
      `  node tools/launch-site.mjs --resume ${slug} --gsc-txt <verification-string>`,
      '(Optional: link to GA4 property once both are set up)',
    ],
    10,
  )

  if (dryRun) {
    log.info('(dry-run) would halt for GSC TXT verification string')
    return { status: 'pass', logFields: { halt: 'skipped_dryrun', sub: '19a' } }
  }

  log.warn(formatHaltMessage(request, slug))
  return { status: 'halt', haltRequest: request }
}

async function wireGsc(ctx, txtRecord, domain) {
  const { slug, platformDir, dryRun, log, execTool } = ctx
  const cfTool   = `${platformDir}/tools/cloudflare-pages-config.mjs`
  const portTool = `${platformDir}/tools/portfolio-update.mjs`

  if (!dryRun) {
    const r = execTool(
      `node "${cfTool}" add-dns-txt --site ${slug} --name ${domain} --value "${txtRecord}"`,
    )
    if (!r.ok) {
      return { status: 'fail', message: `CF add-dns-txt failed: ${r.stderr.slice(0, 200)}` }
    }
    log.info(`DNS TXT record added for ${domain}`)
    log.info('GSC verification pending DNS propagation (up to 48 hours)')
    log.info('After verification: submit sitemap-index.xml in GSC Sitemaps panel')

    execTool(`node "${portTool}" --site ${slug} --set gsc_verified=true`)
    log.info('portfolio.yaml: gsc_verified=true')
  } else {
    log.info(`(dry-run) would add GSC DNS TXT record for ${domain}`)
  }

  return { status: 'pass', logFields: { domain, sub: '19b' } }
}
