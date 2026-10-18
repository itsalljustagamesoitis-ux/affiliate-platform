/**
 * Sitemap helpers for @astrojs/sitemap: real per-page <lastmod>, and a filter that keeps
 * noindex pages and redirect sources out of the sitemap.
 *
 *   import { makeLastmod, platformSitemap } from '@platform/core/src/lib/sitemap-lastmod.mjs'
 *   const lastmodFor = makeLastmod()
 *   sitemap(platformSitemap({ siteUrl, lastmodFor }))
 *
 * lastmod rules (never the build time, never one site-wide date):
 *   article   frontmatter `updated`, else `date`; if neither, the git commit date of the file; else omitted
 *   hub       newest date among that hub's articles
 *   category  newest date among that category's articles
 *   home      newest article date
 *   other (about, privacy, search, ...)  omitted
 */
import { readFileSync, readdirSync, existsSync } from 'fs'
import { resolve } from 'path'
import { execFileSync } from 'child_process'

const slugify = (s) => String(s ?? '').toLowerCase().replace(/&/g, 'and').replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')

function readArticles(articleDir) {
  const out = []
  const dir = resolve(process.cwd(), articleDir)
  if (!existsSync(dir)) return out
  for (const f of readdirSync(dir)) {
    if (!f.endsWith('.md')) continue
    const path = resolve(dir, f)
    const fm = readFileSync(path, 'utf8').match(/^---\n([\s\S]*?)\n---/)
    if (!fm) continue
    const get = (k) => (fm[1].match(new RegExp(`^${k}:\\s*["']?([^"'\\n]+)`, 'm')) ?? [])[1]?.trim()
    let t = Date.parse(get('updated') ?? get('date') ?? '')
    if (Number.isNaN(t)) {
      try {
        const d = execFileSync('git', ['log', '-1', '--format=%cI', '--', path], { cwd: process.cwd(), stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim()
        t = Date.parse(d)
      } catch { t = NaN }
    }
    out.push({ slug: get('slug') ?? f.replace(/\.md$/, ''), hub: get('hub'), category: get('category'), noindex: get('noindex') === 'true', t })
  }
  return out
}

export function makeLastmod(articleDir = './content/articles') {
  const bySlug = new Map(), byHub = new Map(), byCat = new Map()
  let newest = 0
  for (const a of readArticles(articleDir)) {
    if (Number.isNaN(a.t)) continue
    bySlug.set(a.slug, a.t)
    if (a.t > newest) newest = a.t
    if (a.hub) byHub.set(a.hub, Math.max(byHub.get(a.hub) ?? 0, a.t))
    if (a.category) byCat.set(slugify(a.category), Math.max(byCat.get(slugify(a.category)) ?? 0, a.t))
  }
  return (url) => {
    const path = new URL(url).pathname.replace(/\/$/, '')
    if (path === '') return newest ? new Date(newest).toISOString() : undefined
    const slug = path.split('/').pop() ?? ''
    const t = bySlug.get(slug) ?? byHub.get(slug) ?? byCat.get(slug)
    return t ? new Date(t).toISOString() : undefined
  }
}

/** Paths that must never be in the sitemap: noindex routes, redirect sources, utility pages. */
export function makeSitemapFilter(articleDir = './content/articles') {
  const blocked = new Set(['/search', '/privacy', '/404', '/thank-you'])
  for (const a of readArticles(articleDir)) if (a.noindex) blocked.add('/' + a.slug)
  try {
    const rd = resolve(process.cwd(), 'public/_redirects')
    if (existsSync(rd)) {
      for (const line of readFileSync(rd, 'utf8').split('\n')) {
        const m = line.trim().match(/^(\/[^\s*:]*)\s+\S+/)
        if (m && !line.trim().startsWith('#')) blocked.add(m[1].replace(/\/$/, ''))
      }
    }
  } catch { /* no redirects file */ }
  return (page) => {
    const p = new URL(page).pathname.replace(/\/$/, '')
    return !blocked.has(p)
  }
}

/** Options object for sitemap({...}); keeps the existing home/category priorities. */
export function platformSitemap({ siteUrl, lastmodFor, articleDir } = {}) {
  const filter = makeSitemapFilter(articleDir)
  return {
    filter,
    serialize(item) {
      const lm = lastmodFor ? lastmodFor(item.url) : undefined
      if (lm) item.lastmod = lm
      else delete item.lastmod
      if (item.url === `${siteUrl}/`) { item.changefreq = 'weekly'; item.priority = 1.0 }
      else if (!item.url.includes('.')) { item.changefreq = 'monthly'; item.priority = 0.8 }
      return item
    },
  }
}

/** Articles that belong in feeds: not noindex and not a redirect source. Pass the getCollection('articles') result. */
export function publishedArticles(articles) {
  const blocked = new Set()
  try {
    const rd = resolve(process.cwd(), 'public/_redirects')
    if (existsSync(rd)) {
      for (const line of readFileSync(rd, 'utf8').split('\n')) {
        const m = line.trim().match(/^(\/[^\s*:]*)\s+\S+/)
        if (m && !line.trim().startsWith('#')) blocked.add(m[1].replace(/\/$/, ''))
      }
    }
  } catch { /* no redirects file */ }
  return articles.filter((a) => !a.data.noindex && !blocked.has('/' + a.data.slug))
}
