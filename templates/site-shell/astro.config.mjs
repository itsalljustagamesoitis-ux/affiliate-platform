// @ts-check
import { defineConfig } from 'astro/config'
import sitemap from '@astrojs/sitemap'
import rehypeExternalLinks from 'rehype-external-links'
import { rehypeProductLinks } from '@platform/core/src/plugins/rehype-product-links.mjs'
import { readFileSync } from 'fs'
import yaml from 'js-yaml'

const _cfg = yaml.load(readFileSync('./site.config.yaml', 'utf8'))

if (!process.env.SITE_URL && !_cfg?.site?.domain) {
  throw new Error('Build error: set SITE_URL env var or site.config.yaml site.domain')
}

const siteUrl = process.env.SITE_URL ?? `https://${_cfg.site.domain}`

if (!process.env.GOOGLE_SITE_VERIFICATION) {
  // DNS TXT verification is equally valid — warn only, never throw
  console.warn('\x1b[33m⚠ GOOGLE_SITE_VERIFICATION not set — GSC meta tag will not render (fine if using DNS verification)\x1b[0m')
}
const bingVal = process.env.BING_SITE_VERIFICATION
const isPlaceholder = bingVal && bingVal.includes('PLACEHOLDER')
const isBingMissing = !bingVal
// Bing Webmaster Tools can import already-verified GSC sites directly (no
// separate meta tag or DNS record needed for Bing at all) -- that's the
// standard verification path here, so this must warn like GOOGLE_SITE_VERIFICATION
// above, never throw. It previously hard-failed the production branch build,
// which assumed meta-tag/DNS verification was the only valid path.
if (isPlaceholder) {
  console.warn('\x1b[33m⚠ BING_SITE_VERIFICATION is placeholder — replace before launch\x1b[0m')
} else if (isBingMissing) {
  console.warn('\x1b[33m⚠ BING_SITE_VERIFICATION not set — Bing meta tag will not render (fine if verified via GSC import or DNS)\x1b[0m')
}

export default defineConfig({
  site: siteUrl,
  integrations: [
    sitemap({
      filter: (page) => !page.endsWith('/privacy/'),
      serialize(item) {
        // Set lastmod to build time for all pages (article pages will be overridden by their frontmatter date when available)
        item.lastmod = new Date().toISOString()
        // Prioritise homepage and category pages
        if (item.url === `${siteUrl}/`) {
          item.changefreq = 'weekly'
          item.priority = 1.0
        } else if (!item.url.includes('.')) {
          item.changefreq = 'monthly'
          item.priority = 0.8
        }
        return item
      },
    }),
  ],
  markdown: {
    rehypePlugins: [
      rehypeProductLinks,
      [rehypeExternalLinks, {
        rel: ['nofollow', 'sponsored'],
        target: '_blank',
        test: (node) => {
          const href = node.properties?.href ?? ''
          return typeof href === 'string' && href.includes('amazon.com')
        },
      }],
    ],
  },
  image: {
    service: {
      entrypoint: 'astro/assets/services/sharp',
    },
  },
  build: {
    inlineStylesheets: 'auto',
  },
  vite: {
    optimizeDeps: {
      exclude: ['sharp'],
    },
  },
})
