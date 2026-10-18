#!/usr/bin/env node
/**
 * indexnow-diff.mjs — post-deploy IndexNow ping for NEW or CHANGED page URLs only.
 *
 *   node node_modules/@platform/core/scripts/indexnow-diff.mjs [--dry-run] [--all]
 *
 * Reads dist/sitemap-N.xml, hashes each page's built HTML, compares with data/indexnow-state.json
 * (written after each successful submission) and POSTs only pages that are new or whose HTML changed.
 * Needs the site's IndexNow key file at public/<key>.txt (32 hex chars, contents = the key).
 * Appends one JSON line per run to logs/indexnow.log: {ts, site, submitted, status}.
 * Exit code is non-zero when the POST fails so a deploy wrapper can surface it.
 */
import { readFileSync, readdirSync, existsSync, writeFileSync, mkdirSync, appendFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { createHash } from 'node:crypto'

const root = process.cwd()
const dist = resolve(root, 'dist')
const dry = process.argv.includes('--dry-run')
const all = process.argv.includes('--all')
const cfg = readFileSync(resolve(root, 'site.config.yaml'), 'utf8')
const domain = (cfg.match(/^\s*domain:\s*["']?([^"'\s#]+)/m) ?? [])[1]
if (!domain) { console.error('indexnow-diff: no site.domain in site.config.yaml'); process.exit(2) }
const keyFile = existsSync(dist) ? readdirSync(dist).find((f) => /^[a-f0-9]{32}\.txt$/.test(f)) : null
if (!keyFile) { console.error(`indexnow-diff: no IndexNow key file (<32 hex>.txt) in dist/ for ${domain}; add one under public/`); process.exit(2) }
const key = keyFile.replace('.txt', '')

const urls = []
for (const f of readdirSync(dist).filter((f) => /^sitemap-\d+\.xml$/.test(f))) {
  for (const m of readFileSync(join(dist, f), 'utf8').matchAll(/<loc>([^<]+)<\/loc>/g)) urls.push(m[1])
}
const statePath = resolve(root, 'data/indexnow-state.json')
const prev = existsSync(statePath) ? JSON.parse(readFileSync(statePath, 'utf8')) : {}
const next = {}, changed = []
for (const u of urls) {
  const p = new URL(u).pathname.replace(/\/$/, '')
  const f = [join(dist, p, 'index.html'), join(dist, p + '.html')].find(existsSync)
  if (!f) continue
  const h = createHash('sha1').update(readFileSync(f)).digest('hex')
  next[u] = h
  if (all || prev[u] !== h) changed.push(u)
}
const host = domain.replace(/^www\./, '')
const log = (rec) => { mkdirSync(resolve(root, 'logs'), { recursive: true }); appendFileSync(resolve(root, 'logs/indexnow.log'), JSON.stringify({ ts: new Date().toISOString(), site: host, ...rec }) + '\n') }
console.log(`indexnow-diff: ${host}: ${urls.length} sitemap URLs, ${changed.length} new or changed`)
if (dry || changed.length === 0) { if (!dry) log({ submitted: 0, status: 'nothing-changed' }); process.exit(0) }

async function post(list, attempt = 1) {
  const r = await fetch('https://api.indexnow.org/IndexNow', {
    method: 'POST', headers: { 'content-type': 'application/json; charset=utf-8' },
    body: JSON.stringify({ host, key, keyLocation: `https://${host}/${keyFile}`, urlList: list }),
  })
  if ((r.status === 403 || r.status === 422) && attempt < 3) { await new Promise((s) => setTimeout(s, 20000)); return post(list, attempt + 1) }
  return r.status
}
let ok = true, status = 0
for (let i = 0; i < changed.length; i += 9000) {
  status = await post(changed.slice(i, i + 9000))
  if (status !== 200 && status !== 202) ok = false
}
log({ submitted: changed.length, status })
if (ok) { mkdirSync(resolve(root, 'data'), { recursive: true }); writeFileSync(statePath, JSON.stringify(next)) }
console.log(`indexnow-diff: POST ${ok ? 'accepted' : 'FAILED'} (${status}) for ${changed.length} URL(s)`)
process.exit(ok ? 0 : 1)
