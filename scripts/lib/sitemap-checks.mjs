/**
 * Post-build checks for sitemaps, robots.txt and RSS. Used by build-validator.mjs.
 * Per-site modes via site.config.yaml `validators:` (fail | warn | off):
 *   sitemap_urls, sitemap_lastmod_shared, robots_sitemaps, rss_urls
 */
import { readFileSync, readdirSync, existsSync } from 'fs'
import { join, resolve } from 'path'

const norm = (u) => u.replace(/^https?:\/\/(www\.)?/, '').replace(/\/$/, '').toLowerCase()

function articleDates(siteRoot) {
  const set = new Set()
  const dir = resolve(siteRoot, 'content/articles')
  if (!existsSync(dir)) return set
  for (const f of readdirSync(dir)) {
    if (!f.endsWith('.md')) continue
    const fm = readFileSync(join(dir, f), 'utf8').match(/^---\n([\s\S]*?)\n---/)?.[1] ?? ''
    for (const k of ['date', 'updated']) {
      const v = (fm.match(new RegExp(`^${k}:\\s*["']?(\\d{4}-\\d{2}-\\d{2})`, 'm')) ?? [])[1]
      if (v) set.add(v)
    }
  }
  return set
}

function redirectSources(siteRoot, dist) {
  const out = new Set()
  for (const p of [join(dist, '_redirects'), resolve(siteRoot, 'public/_redirects')]) {
    if (!existsSync(p)) continue
    for (const l of readFileSync(p, 'utf8').split('\n')) {
      const m = l.trim().match(/^(\/[^\s*:]*)\s+\S+/)
      if (m && !l.trim().startsWith('#')) out.add(m[1].replace(/\/$/, '') || '/')
    }
  }
  return out
}

function distFileFor(dist, urlPath) {
  const p = urlPath.replace(/\/$/, '')
  for (const c of [join(dist, p, 'index.html'), join(dist, p + '.html'), join(dist, p)]) if (existsSync(c) && !/\/$/.test(c)) { try { if (readFileSync(c).length) return c } catch {} }
  return null
}

function problemsFor(dist, siteHost, urlStr, redirects) {
  let path
  try { path = new URL(urlStr).pathname } catch { return ['not a valid URL'] }
  const probs = []
  if (redirects.has(path.replace(/\/$/, '') || '/')) probs.push('redirect source in _redirects')
  const f = distFileFor(dist, path)
  if (!f) { probs.push('no built page'); return probs }
  if (!f.endsWith('.html')) return probs
  const html = readFileSync(f, 'utf8')
  if (/http-equiv=["']refresh["']/i.test(html)) probs.push('meta-refresh redirect page')
  if (/<meta[^>]+name=["']robots["'][^>]+content=["'][^"']*noindex/i.test(html) || /<meta[^>]+content=["'][^"']*noindex[^"']*["'][^>]+name=["']robots["']/i.test(html)) probs.push('renders noindex')
  const can = (html.match(/<link[^>]+rel=["']canonical["'][^>]+href=["']([^"']+)["']/i) ?? html.match(/<link[^>]+href=["']([^"']+)["'][^>]+rel=["']canonical["']/i) ?? [])[1]
  if (!can) probs.push('no canonical')
  else if (norm(can) !== norm(urlStr)) probs.push(`canonical points elsewhere (${can})`)
  return probs
}

export function checkSitemapsRobotsRss(dist, siteRoot, ctx) {
  const out = []
  const mode = (key, def = 'fail') => ctx.modes?.[key] ?? def
  if (!existsSync(dist)) return out
  const add = (key, check, msg, def = 'fail') => { const m = mode(key, def); if (m !== 'off') out.push({ check, msg, level: m }) }

  const files = readdirSync(dist).filter((f) => /^sitemap-\d+\.xml$/.test(f))
  const urls = []
  for (const f of files) {
    const xml = readFileSync(join(dist, f), 'utf8')
    for (const m of xml.matchAll(/<url>([\s\S]*?)<\/url>/g)) {
      urls.push({ loc: (m[1].match(/<loc>([^<]+)<\/loc>/) ?? [])[1], lastmod: (m[1].match(/<lastmod>([^<]+)<\/lastmod>/) ?? [])[1] })
    }
  }
  const redirects = redirectSources(siteRoot, dist)

  // lastmod concentration
  if (urls.length > 20) {
    const counts = new Map()
    for (const u of urls) { const k = u.lastmod ? u.lastmod.slice(0, 10) : '(none)'; counts.set(k, (counts.get(k) ?? 0) + 1) }
    const [topDate, top] = [...counts.entries()].sort((a, b) => b[1] - a[1])[0]
    if (top / urls.length > 0.8) {
      const genuine = articleDates(siteRoot).has(topDate)
      if (topDate === '(none)') add('sitemap_lastmod_shared', 'sitemap-lastmod', `${top}/${urls.length} sitemap URLs have no lastmod`, 'warn')
      else if (genuine) add('sitemap_lastmod_shared', 'sitemap-lastmod', `${top}/${urls.length} URLs share lastmod ${topDate}; it matches the articles' own frontmatter dates (a real publishing batch), not the build time`, 'warn')
      else add('sitemap_lastmod_shared', 'sitemap-lastmod', `${top}/${urls.length} URLs share lastmod ${topDate} which is not any article's frontmatter date (build-time stamp)`)
    }
  }

  // every sitemap URL must be a live, indexable, self-canonical page
  const bad = []
  for (const u of urls) {
    if (!u.loc) continue
    const p = problemsFor(dist, null, u.loc, redirects)
    if (p.length) bad.push(`${new URL(u.loc).pathname} (${p.join('; ')})`)
  }
  if (bad.length) add('sitemap_urls', 'sitemap-url', `${bad.length} sitemap URL(s) are not live self-canonical indexable pages, e.g. ${bad.slice(0, 4).join(' | ')}`)

  // robots.txt must list the index and the child sitemap(s)
  const rp = join(dist, 'robots.txt')
  if (existsSync(rp)) {
    const r = readFileSync(rp, 'utf8')
    const have = [...r.matchAll(/^Sitemap:\s*(\S+)/gim)].map((m) => m[1])
    const need = ['sitemap-index.xml', ...files]
    const missing = need.filter((n) => !have.some((h) => h.endsWith('/' + n)))
    if (missing.length) add('robots_sitemaps', 'robots-sitemaps', `robots.txt is missing Sitemap line(s) for: ${missing.join(', ')}`)
  }

  // RSS/feeds: only live canonical pages
  for (const f of ['rss.xml', 'feed.xml']) {
    const p = join(dist, f)
    if (!existsSync(p)) continue
    const xml = readFileSync(p, 'utf8')
    const links = [...xml.matchAll(/<item>[\s\S]*?<link>([^<]+)<\/link>/g)].map((m) => m[1])
    const badR = []
    for (const l of links) { const pr = problemsFor(dist, null, l, redirects); if (pr.length) badR.push(`${new URL(l).pathname} (${pr.join('; ')})`) }
    if (badR.length) add('rss_urls', 'rss-url', `${f}: ${badR.length}/${links.length} item link(s) are not live canonical pages, e.g. ${badR.slice(0, 3).join(' | ')}`)
  }
  return out
}
