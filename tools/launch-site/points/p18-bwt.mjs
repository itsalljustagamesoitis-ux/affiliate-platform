/**
 * Point 18 — Bing Webmaster Tools
 * Bucket C (18a): Keith creates property + provides TXT verification string
 * Bucket A (18b): Claude Code adds DNS TXT record via cloudflare-pages-config.mjs
 */

// buildHaltRequest / formatHaltMessage removed — P18 is non-blocking (P2.5 2026-06-06)

export const POINT_ID = '18'
export const BUCKET = 'C'

export async function run(ctx) {
  const { slug, siteDir, platformDir, dryRun, log, execTool, state } = ctx

  const domain = state.inputs?.domain ?? `${slug}.com`
  const existingTxt = state.inputs?.bwt_txt_record

  if (existingTxt) {
    log.info(`BWT TXT record: ${existingTxt.slice(0, 30)}… — adding DNS record…`)
    return wireBwt(ctx, existingTxt, domain)
  }

  if (dryRun) {
    log.info('(dry-run) BWT verification deferred — no TXT record provided')
    return { status: 'pass', logFields: { bwt: 'deferred_dryrun', sub: '18a' } }
  }

  // Non-blocking: log the manual steps and continue the ritual.
  // Keith completes BWT post-launch; resume via --bwt-txt flag adds the DNS record.
  log.warn(
    `[P18] BWT verification deferred — complete manually post-launch:\n` +
    `  1. Sign in to bing.com/webmasters\n` +
    `  2. Add a Site → enter: https://${domain}\n` +
    `  3. Copy the DNS TXT verification string\n` +
    `  4. Resume: node tools/launch-site.mjs --resume ${slug} --bwt-txt <string>`,
  )
  return { status: 'pass', logFields: { bwt: 'deferred_manual', sub: '18a' } }
}

async function wireBwt(ctx, txtRecord, domain) {
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
    log.info('BWT verification pending DNS propagation (up to 24 hours)')
    log.info('After verification: submit sitemap and configure IndexNow in BWT UI')

    execTool(`node "${portTool}" --site ${slug} --set bwt_verified=true`)
    log.info('portfolio.yaml: bwt_verified=true')
  } else {
    log.info(`(dry-run) would add BWT DNS TXT record for ${domain}`)
  }

  return { status: 'pass', logFields: { domain, sub: '18b' } }
}
