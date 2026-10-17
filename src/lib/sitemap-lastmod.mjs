/**
 * Real per-page <lastmod> for @astrojs/sitemap.
 *
 *   import { makeLastmod } from '@platform/core/src/lib/sitemap-lastmod.mjs'
 *   const lastmodFor = makeLastmod()
 *   ...sitemap({ serialize(item) { item.lastmod = lastmodFor(item.url); return item } })
 *
 * Article pages use frontmatter `updated` (falling back to `date`). Every other
 * page (home, hubs, static) uses the newest article date, never the build time,
 * so lastmod only moves when content does.
 */
import { readFileSync, readdirSync } from 'fs'
import { resolve } from 'path'

export function makeLastmod(articleDir = './content/articles') {
  const dates = new Map()
  let newest = 0
  try {
    const dir = resolve(process.cwd(), articleDir)
    for (const f of readdirSync(dir)) {
      if (!f.endsWith('.md')) continue
      const fm = readFileSync(resolve(dir, f), 'utf8').match(/^---\n([\s\S]*?)\n---/)
      if (!fm) continue
      const get = (k) => (fm[1].match(new RegExp(`^${k}:\\s*["']?([^"'\\n]+)`, 'm')) ?? [])[1]?.trim()
      const slug = get('slug') ?? f.replace(/\.md$/, '')
      const t = Date.parse(get('updated') ?? get('date') ?? '')
      if (Number.isNaN(t)) continue
      dates.set(slug, t)
      if (t > newest) newest = t
    }
  } catch (e) {
    console.warn(`sitemap-lastmod: could not read ${articleDir}: ${e.message}`)
  }
  return (url) => {
    const slug = url.replace(/\/$/, '').split('/').pop() ?? ''
    const t = dates.get(slug) ?? newest
    return t ? new Date(t).toISOString() : undefined
  }
}
