/**
 * Post-deploy live verification — confirms production is serving fresh, valid content.
 * Run from site root after wrangler pages deploy completes.
 *
 * Reads site.config.yaml → site.domain for the production hostname.
 * Override with DEPLOY_HOSTNAME env var for testing or staging checks.
 *
 * Check 1:  Homepage HTTP 200
 * Check 2:  SSL valid (HTTPS — bundled with Check 1)
 * Check 3:  Cache-bypass freshness (build_timestamp in dist/ vs production)
 * Check 4:  Article count (sitemap <loc> entries vs local content/articles/)
 * Check 5:  Sample article smoke test (up to 6 articles × 4 sub-checks)
 * Check 6:  Homepage structural elements (nav, footer, article card, disclosure)
 * Check 7:  Disclosure on sample article
 * Check 8:  Custom 404 page
 * Check 9:  Nav-target reachability (all navigation.yaml entries + furniture links → HTTP 200)
 */

import { readFileSync, existsSync, readdirSync } from 'fs'
import { resolve } from 'path'
import yaml from 'js-yaml'

const SITE_ROOT = process.cwd()
const cfg = yaml.load(readFileSync(resolve(SITE_ROOT, 'site.config.yaml'), 'utf8'))
const hostname = process.env.DEPLOY_HOSTNAME ?? cfg?.site?.domain ?? ''

if (!hostname) {
  console.error('verify-deploy: no hostname in site.config.yaml (site.domain) or DEPLOY_HOSTNAME env var')
  process.exit(1)
}

const BASE_URL = `https://${hostname}`
const DIST = resolve(SITE_ROOT, 'dist')
const ARTICLES_DIR = resolve(SITE_ROOT, 'content/articles')

let failures = 0
const errors = []
const warnings = []

function fail(check, msg) {
  errors.push(`  FAIL [${check}] ${msg}`)
  failures++
}

function warn(check, msg) {
  warnings.push(`  WARN [${check}] ${msg}`)
}

function pass(check, msg) {
  console.log(`  ✓ [${check}] ${msg}`)
}

// ── Propagation retry helper ──────────────────────────────────────────────────
// CDN edge invalidation is async; the first post-deploy request may hit a stale
// edge node. One retry after a short delay handles the common case without
// masking real failures (which persist on the second attempt).
//
// Apply to:  freshness check, redirect status checks.
// Do not apply to:  homepage/SSL (served from origin, always current),
//                   static content (already-cached assets).
//
// Three incidents confirming the pattern (2026-05-26, MED dedup batch):
//   FFC: /life-line-medical-alert-system/ returned 200 (expected 301), resolved after ~10s
//   NWO: /hardshell-rooftop-tent/ returned 200 (expected 301), resolved after ~10s
//   BCB: /build-info.json returned stale timestamp, resolved after ~15s
const PROPAGATION_RETRY_DELAY_MS = 10_000

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

// probeFn returns: true (pass), false (fail — retryable), null (skip — side effects already handled)
async function retryOnce(checkName, probeFn) {
  const first = await probeFn()
  if (first !== false) return first
  console.log(`  ↻ [retry] ${checkName} — propagation lag detected, retrying in ${PROPAGATION_RETRY_DELAY_MS / 1000}s`)
  await sleep(PROPAGATION_RETRY_DELAY_MS)
  return probeFn()
}

async function fetchPage(url) {
  const res = await fetch(url, { redirect: 'follow' })
  const text = await res.text()
  return { status: res.status, finalUrl: res.url, text }
}

// ── Check 1 + 2: Homepage resolves (HTTP 200) and SSL valid ──────────────────
console.log(`\nCheck 1+2  Homepage + SSL — ${BASE_URL}/`)
try {
  const { status, finalUrl } = await fetchPage(`${BASE_URL}/`)
  if (status !== 200) {
    fail('homepage-status', `Expected HTTP 200, got ${status} for ${BASE_URL}/`)
  } else {
    pass('homepage-status', `HTTP 200`)
  }
  if (!finalUrl.startsWith('https://')) {
    fail('ssl', `Final URL after redirect is not HTTPS: ${finalUrl}`)
  } else {
    pass('ssl', `HTTPS confirmed`)
  }
} catch (e) {
  fail('homepage-status', `Request failed: ${e.message}`)
}

// ── Check 3: Cache-bypass freshness ──────────────────────────────────────────
console.log(`\nCheck 3    Freshness — dist/build-info.json vs production`)
const BUILD_INFO_LOCAL = resolve(DIST, 'build-info.json')
if (!existsSync(BUILD_INFO_LOCAL)) {
  warn('freshness', `dist/build-info.json not found — rebuild with updated build script to enable this check`)
} else {
  const localInfo = JSON.parse(readFileSync(BUILD_INFO_LOCAL, 'utf8'))
  let prodTimestamp = null

  const result = await retryOnce('freshness', async () => {
    try {
      const { status, text } = await fetchPage(`${BASE_URL}/build-info.json?_=${Date.now()}`)
      if (status !== 200) {
        warn('freshness', `/build-info.json returned ${status} — site may predate build-info support`)
        return null
      }
      let prodInfo
      try { prodInfo = JSON.parse(text) } catch {
        fail('freshness', `/build-info.json is not valid JSON`)
        return null
      }
      prodTimestamp = prodInfo?.build_timestamp ?? null
      return prodTimestamp === localInfo.build_timestamp
    } catch (e) {
      warn('freshness', `Could not fetch /build-info.json: ${e.message}`)
      return null
    }
  })

  if (result === true) {
    pass('freshness', `build_timestamp matches: ${localInfo.build_timestamp}`)
  } else if (result === false) {
    fail('freshness',
      `Stale deploy — production build_timestamp (${prodTimestamp}) ≠ local (${localInfo.build_timestamp})`)
  }
  // result === null: warn or fail already registered inside probe
}

// ── Check 4: Article count ────────────────────────────────────────────────────
console.log(`\nCheck 4    Article count — sitemap vs local content/articles/`)
let sitemapSlugs = []
let localSlugs = []

if (existsSync(ARTICLES_DIR)) {
  localSlugs = readdirSync(ARTICLES_DIR)
    .filter(f => f.endsWith('.md') || f.endsWith('.mdx'))
    .map(f => f.replace(/\.mdx?$/, ''))
}

try {
  const { status: idxStatus, text: idxText } = await fetchPage(`${BASE_URL}/sitemap-index.xml`)
  if (idxStatus !== 200) {
    warn('article-count', `sitemap-index.xml returned ${idxStatus}`)
  } else {
    const sitemapUrl = idxText.match(/<loc>([^<]+)<\/loc>/)?.[1]
    if (!sitemapUrl) {
      warn('article-count', 'No <loc> found in sitemap-index.xml')
    } else {
      const { status: smStatus, text: smText } = await fetchPage(sitemapUrl)
      if (smStatus !== 200) {
        warn('article-count', `${sitemapUrl} returned ${smStatus}`)
      } else {
        const allLocs = [...smText.matchAll(/<loc>([^<]+)<\/loc>/g)].map(m => m[1])
        // Article URLs have exactly one path segment (no slash in the middle)
        const SKIP = new Set(['rss', 'sitemap', 'search', '404', 'pagefind'])
        sitemapSlugs = allLocs
          .map(url => url.replace(`${BASE_URL}/`, '').replace(/\/$/, ''))
          .filter(slug => slug && !slug.includes('/') && !SKIP.has(slug))

        if (localSlugs.length === 0) {
          warn('article-count', 'No local content/articles/ — cannot compare')
        } else if (sitemapSlugs.length === 0) {
          warn('article-count', 'No single-slug URLs found in sitemap — check sitemap config')
        } else {
          // Check that every local article slug appears in the sitemap.
          // Sitemap may have more slugs (hub pages, static pages) — that's expected.
          const sitemapSet = new Set(sitemapSlugs)
          const missing = localSlugs.filter(s => !sitemapSet.has(s))
          if (missing.length > 0) {
            fail('article-count',
              `${missing.length} local article(s) missing from sitemap — not deployed: ${missing.slice(0, 5).join(', ')}${missing.length > 5 ? ` … +${missing.length - 5} more` : ''}`)
          } else {
            const extra = sitemapSlugs.length - localSlugs.length
            pass('article-count',
              `All ${localSlugs.length} local articles present in sitemap (${extra > 0 ? `+${extra} hub/static pages` : 'exact match'})`)
          }
        }
      }
    }
  }
} catch (e) {
  warn('article-count', `Sitemap fetch failed: ${e.message}`)
}

// ── Check 5: Sample article smoke test ───────────────────────────────────────
console.log(`\nCheck 5    Sample articles — 6 × 4 sub-checks`)
const pool = sitemapSlugs.length > 0 ? sitemapSlugs : localSlugs
const step = Math.max(1, Math.floor(pool.length / 6))
const sampleSlugs = pool.filter((_, i) => i % step === 0).slice(0, 6)

if (sampleSlugs.length === 0) {
  warn('sample-articles', 'No article slugs available for sampling')
} else {
  for (const slug of sampleSlugs) {
    const url = `${BASE_URL}/${slug}/`
    try {
      const { status, text } = await fetchPage(url)

      // Sub-check 1: HTTP 200
      if (status !== 200) {
        fail('sample-articles', `${slug}: HTTP ${status} (expected 200)`)
        continue
      }

      // Sub-check 2: Has <h1> (content rendered, not a blank shell)
      if (!/<h1[\s>]/.test(text)) {
        fail('sample-articles', `${slug}: no <h1> — article body may not have rendered`)
      }

      // Sub-check 3: Has product card (WARN not FAIL — informational articles are exempt)
      if (!text.includes('class="product-card') && !text.includes("class='product-card")) {
        warn('sample-articles', `${slug}: no product-card — informational article or rendering gap`)
      }

      // Sub-check 4: Has disclosure
      if (!text.includes('As an Amazon Associate')) {
        fail('sample-articles', `${slug}: missing "As an Amazon Associate" disclosure`)
      } else {
        if (status === 200 && /<h1[\s>]/.test(text)) {
          pass('sample-articles', `${slug}`)
        }
      }
    } catch (e) {
      fail('sample-articles', `${slug}: request failed — ${e.message}`)
    }
  }
}

// ── Check 6: Homepage structural elements ────────────────────────────────────
console.log(`\nCheck 6    Homepage structural elements`)
try {
  const { text: homeText } = await fetchPage(`${BASE_URL}/`)
  const checks = [
    ['nav',          homeText.includes('class="site-header__nav"'),  'site-header__nav'],
    ['footer',       homeText.includes('<footer'),                    '<footer>'],
    ['article-card', homeText.includes('class="article-card"'),      'article-card'],
    ['disclosure',   homeText.includes('As an Amazon Associate'),     'Amazon disclosure'],
  ]
  for (const [name, ok, label] of checks) {
    if (!ok) {
      if (name === 'article-card' && localSlugs.length === 0)
        warn('homepage-elements', `Missing: ${label} (skeleton site — no articles yet)`)
      else fail('homepage-elements', `Missing: ${label}`)
    } else {
      pass('homepage-elements', label)
    }
  }
} catch (e) {
  fail('homepage-elements', `Homepage fetch failed: ${e.message}`)
}

// ── Check 7: Disclosure on sample article ────────────────────────────────────
console.log(`\nCheck 7    Article disclosure`)
const disclosureSlug = sampleSlugs[0]
if (!disclosureSlug) {
  warn('article-disclosure', 'No sample slug — skipping')
} else {
  try {
    const { status, text } = await fetchPage(`${BASE_URL}/${disclosureSlug}/`)
    if (status !== 200) {
      fail('article-disclosure', `/${disclosureSlug}/ returned ${status}`)
    } else if (!text.includes('As an Amazon Associate')) {
      fail('article-disclosure', `"As an Amazon Associate" not found on /${disclosureSlug}/`)
    } else {
      pass('article-disclosure', `disclosure found on /${disclosureSlug}/`)
    }
  } catch (e) {
    fail('article-disclosure', `Request failed: ${e.message}`)
  }
}

// ── Check 8: Custom 404 page ──────────────────────────────────────────────────
console.log(`\nCheck 8    Custom 404 page`)
try {
  const notFoundUrl = `${BASE_URL}/verify-this-page-does-not-exist-404xyz/`
  const { status, text } = await fetchPage(notFoundUrl)
  if (status !== 404) {
    fail('custom-404', `Expected HTTP 404, got ${status}`)
  } else if (text.length < 200) {
    fail('custom-404', `HTTP 404 but response is too small (${text.length} bytes) — not serving custom 404`)
  } else if (!/<html[\s>]/.test(text)) {
    fail('custom-404', `HTTP 404 but response is not HTML`)
  } else {
    pass('custom-404', `HTTP 404 with custom HTML page`)
  }
} catch (e) {
  fail('custom-404', `Request failed: ${e.message}`)
}

// ── Check 9: Nav-target reachability ─────────────────────────────────────────
console.log(`\nCheck 9    Nav targets — all navigation.yaml entries + furniture links`)
try {
  const navPath = resolve(SITE_ROOT, 'config', 'navigation.yaml')
  const navTargets = new Set()

  // Extract from navigation.yaml
  if (existsSync(navPath)) {
    const nav = yaml.load(readFileSync(navPath, 'utf8')) || {}
    for (const cat of (nav.categories || [])) {
      if (cat.slug) navTargets.add(`/${cat.slug}/`)
      for (const hub of (cat.hubs || [])) {
        if (hub.slug) navTargets.add(`/${hub.slug}/`)
      }
    }
    // Flat-nav format (hubs at root level)
    for (const hub of (nav.hubs || [])) {
      if (hub.slug) navTargets.add(`/${hub.slug}/`)
    }
  }

  // Add standard furniture-page links (from Footer.astro)
  for (const path of ['/how-we-research/', '/about/', '/privacy-policy/', '/disclaimer/', '/contact/', '/affiliate-disclosure/']) {
    navTargets.add(path)
  }

  if (navTargets.size === 0) {
    warn('nav-targets', 'No navigation targets found — config/navigation.yaml missing or empty')
  } else {
    // Parallelize with concurrency cap of 6
    const targets = [...navTargets]
    const CONCURRENCY = 6
    const results = []

    for (let i = 0; i < targets.length; i += CONCURRENCY) {
      const batch = targets.slice(i, i + CONCURRENCY)
      const batchResults = await Promise.all(batch.map(async (path) => {
        const url = `${BASE_URL}${path}`
        try {
          // Use retryOnce for the same CDN-propagation-lag resilience as other checks
          const outcome = await retryOnce(`nav-targets:${path}`, async () => {
            const { status } = await fetchPage(url)
            return status === 200 ? true : false
          })
          return { path, ok: outcome !== false }
        } catch (e) {
          return { path, ok: false, error: e.message }
        }
      }))
      results.push(...batchResults)
    }

    const failed = results.filter(r => !r.ok)
    const passed = results.filter(r => r.ok)

    if (failed.length === 0) {
      pass('nav-targets', `All ${passed.length} nav targets returned HTTP 200`)
    } else {
      for (const r of failed) {
        fail('nav-targets', `${r.path} — not HTTP 200${r.error ? ` (${r.error})` : ''}`)
      }
    }
  }
} catch (e) {
  warn('nav-targets', `Nav-target check failed: ${e.message}`)
}

// ── Summary ───────────────────────────────────────────────────────────────────
console.log()
if (warnings.length > 0) {
  console.warn(`⚠  ${warnings.length} warning(s):\n`)
  for (const w of warnings) console.warn(w)
  console.warn()
}

if (failures === 0) {
  console.log(warnings.length
    ? `✓ Deploy verification passed with ${warnings.length} warning(s) — ${hostname}\n`
    : `✓ Deploy verification passed — ${hostname}\n`)
  process.exit(0)
} else {
  console.error(`\n✗ Deploy verification FAILED — ${failures} issue(s) on ${hostname}:\n`)
  for (const e of errors) console.error(e)
  console.error(`\nInvestigate above and redeploy if needed.\n`)
  process.exit(1)
}
