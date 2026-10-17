/**
 * Rendered-HTML content-defect checks used by build-validator.mjs.
 *
 *   author-box-leak      author box renders internal persona-spec content
 *   credential-claim     unverifiable "contributes to / published articles / certified" claims
 *   testing-claim        "tested / hands-on" claims when persona.testing_claims is not true
 *   dash-corruption      numeric ranges broken into "28, 70mm"
 *   stale-year           past years in <title>/<h1>
 *   sitemap-lastmod      sitemap lastmod is the build timestamp, not the page date
 *
 * Each check can be set to 'fail' | 'warn' | 'off' per site via site.config.yaml:
 *   validators: { dash_corruption: warn, ... }
 * Defaults to 'fail'. Use 'warn' only as a documented, temporary exemption.
 */
import { readFileSync, readdirSync, existsSync } from 'fs'
import { join, resolve } from 'path'
import yaml from 'js-yaml'

const MODE_KEYS = {
  'author-box-leak': 'author_box',
  'credential-claim': 'credentials',
  'testing-claim': 'testing_claims',
  'dash-corruption': 'dash_corruption',
  'stale-year': 'stale_year',
  'sitemap-lastmod': 'sitemap_lastmod',
}

const NEG_RE = /(\bnot\b|n['’]t|\bnone\b|\bsubstitute\b|\breplaces?\b|\bno\b|\bnever\b|rather than|without|neither|\bnor\b|\bclaim(?:s|ing|ed)?\b|\bfake\b|\bpretend(?:s|ing)?\b|\bconsult\b|\bsee an?\b|\bask an?\b|\btalk to an?\b|\bspeak (?:to|with) an?\b|\bfind an?\b|\bhire an?\b)[^.]{0,40}$/i
const NEG_AFTER_RE = /^[^.]{0,30}(n['’]t|\bnot\b|\bnever\b)/i   // "hands-on experience I don't have"
const negBefore = (t, i, len = 0) => NEG_RE.test(t.slice(Math.max(0, i - 50), i)) || (len > 0 && NEG_AFTER_RE.test(t.slice(i + len, i + len + 40)))

const CRED_RE = /([Cc]ontributes? to [A-Z][\w&' .-]+|[Cc]ontributor (?:to|for|at) [A-Z]\w+|[Ww]rites? for [A-Z][\w&' .-]+|(?:\d+|[Ss]everal|[Mm]any|[Dd]ozens of) published (?:articles|pieces|stories)|[Pp]ublished (?:in|by|on) [A-Z]\w+|[Ff]eatured (?:in|on) [A-Z]\w+|[Aa]s seen (?:in|on)|(?:[Bb]oard[- ])?[Cc]ertified|[Ll]icensed|[Rr]egistered (?:nurse|dietitian)|[Mm]ember of [A-Z][\w ]+|[Ff]ormer(?:ly)? (?:editor|writer|reporter|staff)|[Aa]ward[- ]winning|\bPetaPixel\b|\bWirecutter\b|Outside Magazine|Backpacker|Field & Stream|Bon App|Serious Eats|America's Test Kitchen)/g

const PERSONA_KEY_RE = /(\br\/[A-Za-z0-9_]+|subreddits?\b|\breads:|\bactive in\b|\bprimary system\b|\bhome studio\b|\bworks from home\b|\balso owns\b|\bsecondary:|location_detail|voice_notes|\bbackground:|bio_short|bio_full|name_formal|\b(wife|husband|married|kids?|children|daughter|son)\b)/i

const STRONG_TEST_RE = /\b(we(?:'ve)? tested|i(?:'ve)? tested|we(?:'ve)? tried|i(?:'ve)? tried|after testing|our (?:hands-on )?testing|our tests?|hands-on (?:testing|review|test)|tried every|(?<![-\w])tested (?:and reviewed|& reviewed|top|every|dozens|over|\d+|picks|models|options|in real|for (?:fit|stability|durability|accuracy|comfort))|(?:reviewed|compared) (?:and|&) tested|(?:reviewed|options|picks|grinders) tested|testing (?:knee|braces|gear|and reviewing))\b/gi
const TITLE_TEST_RE = /\b(tested|testing|hands[- ]on|tried|lab[- ]tested|field[- ]tested)\b/i

const DASH_UNITS = '(?:mm|%|°|"|in\\b|ft\\b|lbs?\\b|kg\\b|W\\b|V\\b|mAh|GB|TB|fps|K\\b|stops?|hours?|minutes?|days?|weeks?|years?|people|inch|cm|oz|gal|psi|MP|ISO)'
const DASH_RE = new RegExp(`(?<![\\d,.$])(\\d+(?:\\.\\d+)?), (\\d+(?:\\.\\d+)?)(?=\\s?${DASH_UNITS})`, 'g')

const textOf = (frag) => frag.replace(/<script[\s\S]*?<\/script>|<style[\s\S]*?<\/style>/gi, ' ').replace(/<[^>]+>/g, ' ')
  .replace(/&amp;/g, '&').replace(/&#39;|&apos;/g, "'").replace(/&quot;/g, '"').replace(/&nbsp;/g, ' ').replace(/\s+/g, ' ').trim()

export function loadSiteContext(siteRoot) {
  let cfg = {}, persona = {}
  try { cfg = yaml.load(readFileSync(resolve(siteRoot, 'site.config.yaml'), 'utf8')) ?? {} } catch {}
  try {
    const pp = cfg?.persona?.config_path
    if (pp) persona = yaml.load(readFileSync(resolve(siteRoot, pp), 'utf8')) ?? {}
  } catch {}
  return { cfg, persona, modes: cfg?.validators ?? {}, currentYear: new Date().getFullYear() }
}

const norm = (s) => String(s ?? '').replace(/\s+/g, ' ').trim()

/** Returns [{check, msg}] for one rendered page. `rel` is the path relative to dist/. */
export function checkHtmlDefects(raw, rel, ctx) {
  const out = []
  const push = (check, msg) => {
    const mode = ctx.modes?.[MODE_KEYS[check]] ?? 'fail'
    if (mode !== 'off') out.push({ check, msg, level: mode })
  }
  const title = textOf((raw.match(/<title>([\s\S]*?)<\/title>/) ?? [])[1] ?? '')
  const metaRaw = (raw.match(/<meta name="description" content="([^"]*)"/) ?? [])[1] ?? ''
  const meta = textOf(metaRaw)
  const h1 = textOf((raw.match(/<h1[^>]*>([\s\S]*?)<\/h1>/) ?? [])[1] ?? '')
  const main = textOf((raw.match(/<main[^>]*>([\s\S]*?)<\/main>/) ?? [, raw])[1])

  // ── author box: internal persona spec must never render ───────────────────
  const ab = raw.match(/<div class="author-bio"[\s\S]*?<\/div>\s*<\/div>/)
  if (ab) {
    const abText = textOf(ab[0].replace(/<a [^>]*class="author-bio__link"[\s\S]*?<\/a>/, ''))
    const hit = PERSONA_KEY_RE.exec(abText)
    if (hit) push('author-box-leak', `Author box contains persona-spec content ("${hit[0]}"): ${abText.slice(0, 160)}`)
    else if (abText.length > 500) push('author-box-leak', `Author box is ${abText.length} chars (max 500); looks like a raw persona field`)
    for (const f of ['background', 'bio_short', 'bio_full']) {
      const v = norm(ctx.persona?.[f])
      if (v.length >= 40 && abText.includes(v.slice(0, 40))) push('author-box-leak', `Author box renders internal persona field "${f}"`)
    }
    for (const m of abText.matchAll(CRED_RE)) {
      if (!negBefore(abText, m.index)) push('credential-claim', `Author box credential claim: "${m[0]}"`)
    }
  }
  // ── internal persona fields must not render anywhere (home, about, reviews...) ──
  const pageText = textOf(raw)
  for (const f of ['background', 'bio_short']) {
    const v = norm(ctx.persona?.[f])
    if (v.length >= 40 && pageText.includes(v.slice(0, 40))) push('author-box-leak', `Page renders internal persona field "${f}"`)
  }
  // ── about page credentials ────────────────────────────────────────────────
  if (/^about(\/|$)/.test(rel)) {
    for (const m of main.matchAll(CRED_RE)) {
      if (!negBefore(main, m.index)) push('credential-claim', `About page credential claim: "${main.slice(Math.max(0, m.index - 30), m.index + m[0].length + 20)}"`)
    }
  }

  // ── testing claims (only when persona does not genuinely test) ────────────
  if (ctx.persona?.testing_claims !== true) {
    for (const [label, t] of [['title', title], ['meta description', meta], ['h1', h1]]) {
      const m = TITLE_TEST_RE.exec(t)
      if (m && !negBefore(t, m.index)) push('testing-claim', `"${m[0]}" in ${label}: ${t.slice(0, 120)}`)
    }
    for (const m of main.matchAll(STRONG_TEST_RE)) {
      if (negBefore(main, m.index, m[0].length)) continue
      push('testing-claim', `Testing claim in body: "...${main.slice(Math.max(0, m.index - 40), m.index + m[0].length + 30)}..."`)
      break // one per page is enough to fail the build
    }
  }

  // ── dash corruption: "28, 70mm" ──────────────────────────────────────────
  const dashHits = []
  // Amazon product titles legitimately contain lists ("Outlets x 5, 3600W"): ignore product-name text
  const mainDash = textOf((raw.replace(/class="[^"]*(?:__name|__title)[^"]*"[^>]*>[^<]*/g, '>').replace(/(<a [^>]*amazon\.com[^>]*>)[^<]*/g, '$1').match(/<main[^>]*>([\s\S]*?)<\/main>/) ?? [, raw])[1])
  for (const m of mainDash.matchAll(DASH_RE)) {
    const a = parseFloat(m[1]), b = parseFloat(m[2])
    const pre = mainDash.slice(Math.max(0, m.index - 3), m.index)
    const post = mainDash.slice(m.index + m[0].length, m.index + m[0].length + 6)
    if ((mainDash.slice(Math.max(0, m.index - 45), m.index).match(/\b[A-Z][\w-]*\b/g) ?? []).length >= 4) continue   // Title-Case product name
    if (/\b(?:set|pack|box|case|bundle|lot) of\s*$/i.test(mainDash.slice(Math.max(0, m.index - 12), m.index))) continue   // "Set of 4, 14 oz"
    const mixedDecimal = m[1].includes('.') !== m[2].includes('.')   // "VocClear 2.0, 30% Clearer" is a list, not a range
    if (a < b && !mixedDecimal && !pre.includes('/') && !/[x×]\s$/i.test(pre) && !pre.includes(':') && !pre.includes('(') && !/[A-Za-z]$/.test(pre) && !/^\s?(mm)?,\s\d/.test(post)) dashHits.push(m[0])
  }
  if (dashHits.length) push('dash-corruption', `${dashHits.length} likely broken range(s): ${dashHits.slice(0, 4).map(h => `"${h}"`).join(', ')}`)

  // ── stale years in title / h1 ─────────────────────────────────────────────
  for (const [label, t] of [['title', title], ['h1', h1]]) {
    // Freshness-style years only ("for 2024", "Picks 2025:", "(2024)"); not model years like "2024 Tacoma"
    const sm = t.match(/(?:\b(?:for|in|of|best|updated)\s+|:\s*|\(\s*)(20[12]\d)\b|\b(20[12]\d)(?=\s*(?::|\||\)|picks|guide|buyer|review|roundup|update|edition))/i)
    const yr = sm && (sm[1] ?? sm[2])
    if (yr && Number(yr) < ctx.currentYear) push('stale-year', `Past year ${yr} in ${label}: ${t.slice(0, 120)}`)
  }
  return out
}

/** Fails when sitemap lastmod values are build timestamps shared by most URLs. */
export function checkSitemapLastmod(dist, ctx) {
  const mode = ctx.modes?.sitemap_lastmod ?? 'fail'
  if (mode === 'off' || !existsSync(dist)) return []
  const stamps = []
  for (const f of readdirSync(dist)) {
    if (!/^sitemap-\d+\.xml$/.test(f)) continue
    stamps.push(...[...readFileSync(join(dist, f), 'utf8').matchAll(/<lastmod>([^<]+)<\/lastmod>/g)].map(m => m[1]))
  }
  if (stamps.length < 6) return []
  // Real page dates are date-only (T00:00:00.000Z). A shared non-midnight stamp is the build time.
  const buildStamped = stamps.filter(s => !/T00:00:00(\.000)?Z?$/.test(s) && /T/.test(s))
  const dayCounts = new Map()
  for (const s of buildStamped) dayCounts.set(s.slice(0, 16), (dayCounts.get(s.slice(0, 16)) ?? 0) + 1)
  const top = Math.max(0, ...dayCounts.values())
  if (top / stamps.length > 0.5) {
    return [{ check: 'sitemap-lastmod', level: mode, msg: `${top}/${stamps.length} sitemap URLs share one build-time lastmod; use each page's real updated/date` }]
  }
  return []
}
