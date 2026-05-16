/**
 * Writes dist/build-info.json after astro build.
 * Records build timestamp and git SHA for post-deploy freshness verification.
 * Also adds Cache-Control: no-store to dist/_headers so CDNs don't cache the file.
 *
 * Run via: node node_modules/@platform/core/scripts/build-info.mjs
 */

import { writeFileSync, readFileSync, existsSync } from 'fs'
import { resolve } from 'path'
import { execSync } from 'child_process'
import yaml from 'js-yaml'

const SITE_ROOT = process.cwd()
const DIST = resolve(SITE_ROOT, 'dist')

if (!existsSync(DIST)) {
  console.error('build-info: dist/ not found — run after astro build')
  process.exit(1)
}

const cfg = yaml.load(readFileSync(resolve(SITE_ROOT, 'site.config.yaml'), 'utf8'))
const domain = cfg?.site?.domain ?? ''

let gitSha = 'unknown'
try {
  gitSha = execSync('git rev-parse --short HEAD', { cwd: SITE_ROOT, encoding: 'utf8' }).trim()
} catch {}

const info = {
  build_timestamp: new Date().toISOString(),
  git_sha: gitSha,
  site_domain: domain,
}

writeFileSync(resolve(DIST, 'build-info.json'), JSON.stringify(info, null, 2) + '\n')

// Inject Cache-Control: no-store into _headers so Cloudflare Pages doesn't cache this file
const headersPath = resolve(DIST, '_headers')
const noStoreEntry = '/build-info.json\n  Cache-Control: no-store, no-cache\n'
if (existsSync(headersPath)) {
  const existing = readFileSync(headersPath, 'utf8')
  if (!existing.includes('/build-info.json')) {
    writeFileSync(headersPath, existing.trimEnd() + '\n\n' + noStoreEntry)
  }
} else {
  writeFileSync(headersPath, noStoreEntry)
}

console.log(`✓ build-info.json written — ${info.build_timestamp} @ ${gitSha} (${domain})`)
