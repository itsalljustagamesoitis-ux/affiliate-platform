#!/usr/bin/env node
/**
 * safe-deploy.mjs — Deploy-target validation wrapper for wrangler pages deploy
 *
 * Prevents the cwd-state bug: verifies dist/ was built from the current site
 * before uploading to Cloudflare Pages.
 *
 * Two incident shapes it catches:
 *   LOUD (ENOENT): cwd is wrong directory — no dist/ or no site.config.yaml → blocked
 *   SILENT (overlay): cwd drifted, dist/ exists but was built for a different site → blocked
 *
 * Usage (drop-in replacement for `npx wrangler pages deploy dist`):
 *   node node_modules/@platform/core/scripts/safe-deploy.mjs --project-name=X [--branch main]
 *
 * All args after the script name are forwarded verbatim to wrangler.
 */

import { readFileSync, existsSync } from 'node:fs'
import { resolve } from 'node:path'
import { spawnSync } from 'node:child_process'

const cwd = process.cwd()
const args = process.argv.slice(2)  // forwarded to wrangler

// ── Helpers ───────────────────────────────────────────────────────────────────

function die(msg, detail) {
  console.error(`\n❌ DEPLOY BLOCKED: ${msg}`)
  if (detail) console.error(`   ${detail}`)
  console.error()
  process.exit(1)
}

function extractYamlField(text, field) {
  const m = text.match(new RegExp(`^\\s*${field}:\\s*["']?([^"'\\n#]+?)["']?\\s*$`, 'm'))
  return m ? m[1].trim() : null
}

function parseProjectName(argv) {
  // handles both --project-name=X and --project-name X
  for (let i = 0; i < argv.length; i++) {
    if (argv[i].startsWith('--project-name=')) return argv[i].split('=')[1]
    if (argv[i] === '--project-name' && argv[i + 1]) return argv[i + 1]
  }
  return null
}

// ── Check 1: site.config.yaml in cwd ─────────────────────────────────────────

const cfgPath = resolve(cwd, 'site.config.yaml')
if (!existsSync(cfgPath)) {
  die(
    `no site.config.yaml in ${cwd}`,
    `Run deploy from the site directory, not from ${cwd.split('/').pop()}/`
  )
}

const cfgText = readFileSync(cfgPath, 'utf8')
const expectedProject = extractYamlField(cfgText, 'cloudflare_pages_project')
const expectedDomain   = extractYamlField(cfgText, 'domain')

// ── Check 2: dist/ exists ─────────────────────────────────────────────────────

const distPath = resolve(cwd, 'dist')
if (!existsSync(distPath)) {
  die(
    `dist/ not found in ${cwd}`,
    `Run npm run build before deploying`
  )
}

// ── Check 3: dist/index.html contains expected domain ────────────────────────

const indexPath = resolve(distPath, 'index.html')
if (!existsSync(indexPath)) {
  die(
    `dist/index.html missing — build may be incomplete`,
    `Run npm run build again`
  )
}

if (expectedDomain) {
  const indexHtml = readFileSync(indexPath, 'utf8')
  if (!indexHtml.includes(expectedDomain)) {
    const foundDomainMatch = indexHtml.match(/https?:\/\/([\w.-]+\.(?:com|net|org|io|co))\b/)
    const foundDomain = foundDomainMatch ? foundDomainMatch[1] : 'unknown'
    die(
      `dist/ was built for "${foundDomain}", not "${expectedDomain}"`,
      `cwd=${cwd}\n   dist contains a different site's build — check for stale cwd`
    )
  }
}

// ── Check 4: --project-name arg matches site.config.yaml ─────────────────────

const givenProject = parseProjectName(args)
if (givenProject && expectedProject && givenProject !== expectedProject) {
  die(
    `--project-name mismatch`,
    `site.config.yaml: "${expectedProject}"  |  arg given: "${givenProject}"`
  )
}

// ── All checks passed — forward to wrangler ───────────────────────────────────

const wranglerCmd = ['pages', 'deploy', 'dist', ...args]
console.log(`\n✓ Deploy target verified`)
console.log(`  site:    ${expectedDomain}`)
console.log(`  project: ${expectedProject}`)
console.log(`  cwd:     ${cwd}`)
console.log()

const result = spawnSync('npx', ['wrangler', ...wranglerCmd], { stdio: 'inherit', cwd })
process.exit(result.status ?? 1)
