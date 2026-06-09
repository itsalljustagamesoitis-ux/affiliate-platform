#!/usr/bin/env node
/**
 * cloudflare-pages-config.mjs — Single entry point for Cloudflare Pages API automation.
 *
 * All write operations Claude Code performs against Cloudflare during a site launch
 * go through this tool. Never use the Cloudflare dashboard to set env vars, attach
 * domains, or add DNS records for sites in this portfolio.
 *
 * Commands:
 *   set-env       Set a plain-text env var on a Pages project environment
 *   attach-domain Attach a custom domain to a Pages project
 *   add-dns-txt   Add a DNS TXT record to a zone (for GSC/BWT verification)
 *   list-envs     Show current env vars for a project
 *
 * Usage:
 *   node tools/cloudflare-pages-config.mjs set-env \
 *     --site <slug> --env production --key AMAZON_TAG --value <tag>
 *
 *   node tools/cloudflare-pages-config.mjs attach-domain \
 *     --site <slug> --domain <domain>
 *
 *   node tools/cloudflare-pages-config.mjs add-dns-txt \
 *     --site <slug> --name @ --value <txt-verification-string>
 *
 *   node tools/cloudflare-pages-config.mjs list-envs \
 *     --site <slug>
 *
 * Exit: 0 = success, 1 = operation failed, 2 = tool/auth error
 */

import { getCloudflareToken } from './lib/auth.mjs'
import { getSite } from './lib/portfolio.mjs'
import {
  getEnvVars,
  setEnvVar,
  attachCustomDomain,
  lookupZoneId,
  addDnsTxtRecord,
} from './lib/cloudflare-api.mjs'

// ── ANSI helpers ──────────────────────────────────────────────────────────────

const isTTY = process.stdout.isTTY
const esc   = isTTY ? (s, code) => `\x1b[${code}m${s}\x1b[0m` : s => s
const c = {
  green:  s => esc(s, '32'),
  red:    s => esc(s, '31'),
  yellow: s => esc(s, '33'),
  bold:   s => esc(s, '1'),
  dim:    s => esc(s, '2'),
  cyan:   s => esc(s, '36'),
}

// ── Retry with exponential backoff ────────────────────────────────────────────

async function withRetry(fn, { delays = [10000, 30000, 60000, 120000], label = 'operation' } = {}) {
  let lastErr
  for (let attempt = 0; attempt <= delays.length; attempt++) {
    try {
      return await fn()
    } catch (err) {
      lastErr = err
      if (attempt < delays.length) {
        const wait = delays[attempt]
        console.error(`  ${c.yellow('[RETRY]')} ${label} failed: ${err.message}`)
        console.error(`  ${c.dim(`  Waiting ${wait / 1000}s before retry ${attempt + 1}/${delays.length}...`)}`)
        await new Promise(r => setTimeout(r, wait))
      }
    }
  }
  throw lastErr
}

// ── Arg parsing ───────────────────────────────────────────────────────────────

const args = process.argv.slice(2)
const cmd  = args[0]
const has  = flag => args.includes(flag)
const get  = flag => { const i = args.indexOf(flag); return i !== -1 ? args[i + 1] : null }

const VALID_COMMANDS = ['set-env', 'attach-domain', 'add-dns-txt', 'list-envs']

if (!cmd || !VALID_COMMANDS.includes(cmd)) {
  console.error(`Usage: cloudflare-pages-config.mjs <command> [options]`)
  console.error(`Commands: ${VALID_COMMANDS.join(', ')}`)
  console.error()
  console.error(`  set-env       --site <slug> --env production|preview --key KEY --value VALUE`)
  console.error(`  attach-domain --site <slug> --domain <domain>`)
  console.error(`  add-dns-txt   --site <slug> --name <record-name> --value <txt-content>`)
  console.error(`  list-envs     --site <slug>`)
  process.exit(2)
}

// ── Auth ──────────────────────────────────────────────────────────────────────

let token
try {
  token = getCloudflareToken()
} catch (err) {
  console.error(`${c.red('[ERROR]')} Auth failed: ${err.message}`)
  process.exit(2)
}

// ── Resolve site ──────────────────────────────────────────────────────────────

const siteSlug = get('--site')
if (!siteSlug) {
  console.error(`${c.red('[ERROR]')} --site <slug> is required`)
  process.exit(2)
}

let site
try {
  site = getSite(siteSlug)
} catch (err) {
  console.error(`${c.red('[ERROR]')} ${err.message}`)
  process.exit(2)
}

const projectName = site.cloudflare_project
if (!projectName) {
  console.error(`${c.red('[ERROR]')} site "${siteSlug}" has no cloudflare_project in portfolio.yaml`)
  process.exit(2)
}

// ── Commands ──────────────────────────────────────────────────────────────────

// ── set-env ───────────────────────────────────────────────────────────────────

if (cmd === 'set-env') {
  const env   = get('--env')
  const key   = get('--key')
  const value = get('--value')

  if (!env || !key || value === null) {
    console.error(`${c.red('[ERROR]')} set-env requires --env, --key, --value`)
    process.exit(2)
  }
  if (env !== 'production' && env !== 'preview') {
    console.error(`${c.red('[ERROR]')} --env must be "production" or "preview"`)
    process.exit(2)
  }

  console.log(`${c.dim(`[${site.slug}]`)} Setting ${c.bold(key)} on ${c.bold(env)} environment of ${c.bold(projectName)}...`)

  let result
  try {
    result = await withRetry(
      () => setEnvVar(token, projectName, env, key, value),
      { label: `set-env ${key} on ${env}` }
    )
  } catch (err) {
    console.error(`${c.red('[FAIL]')} ${err.message}`)
    process.exit(1)
  }

  if (result.changed) {
    console.log(`${c.green('[OK]')} ${key} set on ${env} environment`)
  } else {
    console.log(`${c.dim('[NO-OP]')} ${key} already has this value on ${env} — no change made`)
  }
  process.exit(0)
}

// ── attach-domain ─────────────────────────────────────────────────────────────

if (cmd === 'attach-domain') {
  const domain = get('--domain') ?? site.domain

  console.log(`${c.dim(`[${site.slug}]`)} Attaching domain ${c.bold(domain)} to ${c.bold(projectName)}...`)

  let result
  try {
    result = await withRetry(
      () => attachCustomDomain(token, projectName, domain),
      { label: `attach-domain ${domain}` }
    )
  } catch (err) {
    console.error(`${c.red('[FAIL]')} ${err.message}`)
    process.exit(1)
  }

  if (result.alreadyAttached) {
    console.log(`${c.dim('[NO-OP]')} ${domain} is already attached (status: ${result.status})`)
  } else {
    console.log(`${c.green('[OK]')} ${domain} attached — status: ${result.status}`)
    if (result.status !== 'active') {
      console.log(`${c.yellow('[NOTE]')} Domain status is "${result.status}" — DNS propagation may take a few minutes`)
    }
  }
  process.exit(0)
}

// ── add-dns-txt ───────────────────────────────────────────────────────────────

if (cmd === 'add-dns-txt') {
  const name  = get('--name')  ?? '@'
  const value = get('--value')

  if (!value) {
    console.error(`${c.red('[ERROR]')} add-dns-txt requires --value <txt-content>`)
    process.exit(2)
  }

  // Use domain from portfolio.yaml to look up zone ID
  const zoneDomain = site.domain

  console.log(`${c.dim(`[${site.slug}]`)} Looking up zone ID for ${c.bold(zoneDomain)}...`)

  let zoneId
  try {
    zoneId = await withRetry(
      () => lookupZoneId(token, zoneDomain),
      { label: `zone lookup for ${zoneDomain}` }
    )
  } catch (err) {
    console.error(`${c.red('[FAIL]')} Zone lookup failed: ${err.message}`)
    console.error(`  Make sure the domain is managed by Cloudflare under account ${c.bold('fedb496b1addc0743cb2a84fa5a7ba67')}`)
    process.exit(1)
  }

  console.log(`${c.dim('  Zone ID:')} ${zoneId}`)
  console.log(`${c.dim(`[${site.slug}]`)} Adding TXT record: name=${c.bold(name)}, value=${c.dim(value.slice(0, 40) + (value.length > 40 ? '…' : ''))}`)

  let result
  try {
    result = await withRetry(
      () => addDnsTxtRecord(token, zoneId, name, value),
      { label: `add TXT record ${name}` }
    )
  } catch (err) {
    console.error(`${c.red('[FAIL]')} ${err.message}`)
    process.exit(1)
  }

  if (result.alreadyExists) {
    console.log(`${c.dim('[NO-OP]')} TXT record with this content already exists (id: ${result.id})`)
  } else {
    console.log(`${c.green('[OK]')} TXT record added (id: ${result.id})`)
    console.log(`${c.yellow('[NOTE]')} DNS propagation may take up to 5 minutes`)
  }
  process.exit(0)
}

// ── list-envs ─────────────────────────────────────────────────────────────────

if (cmd === 'list-envs') {
  console.log(`${c.dim(`[${site.slug}]`)} Environment variables for ${c.bold(projectName)}:\n`)

  let envVars
  try {
    envVars = await withRetry(
      () => getEnvVars(token, projectName),
      { label: 'list-envs' }
    )
  } catch (err) {
    console.error(`${c.red('[FAIL]')} ${err.message}`)
    process.exit(1)
  }

  for (const envName of ['production', 'preview']) {
    console.log(c.bold(`  ${envName}:`))
    const vars = envVars[envName] ?? {}
    const keys = Object.keys(vars)
    if (keys.length === 0) {
      console.log(`    ${c.dim('(none)')}`)
    } else {
      for (const [k, v] of Object.entries(vars)) {
        const display = v.type === 'secret_text'
          ? c.dim('[secret]')
          : c.cyan(v.value ?? '(empty)')
        console.log(`    ${c.bold(k)}: ${display}`)
      }
    }
    console.log()
  }
  process.exit(0)
}
