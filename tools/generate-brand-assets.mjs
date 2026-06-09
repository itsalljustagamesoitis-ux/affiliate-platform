#!/usr/bin/env node
/**
 * generate-brand-assets.mjs — Generate SVG logo variants + favicon + OG image.
 *
 * Usage:
 *   node tools/generate-brand-assets.mjs --site <slug>
 *   node tools/generate-brand-assets.mjs --site <slug> --dry-run
 *   node tools/generate-brand-assets.mjs --site <slug> --test-dir /tmp/test-assets
 *   node tools/generate-brand-assets.mjs --site <slug> --only logo-header,favicon.ico
 *   node tools/generate-brand-assets.mjs \
 *     --niche outdoor-cooking \
 *     --brand-name "Smoke and Coals" \
 *     --primary "#8B2500" \
 *     --accent "#E87A00" \
 *     --tagline "Real fire, real flavor." \
 *     --test-dir /tmp/test-assets
 *
 * Outputs (to public/images/brand/ or --test-dir):
 *   logo-header.svg          — mark + wordmark, primary color
 *   logo-header-dark.svg     — mark + wordmark, white (for dark navbars)
 *   logo-mark.svg            — mark only, primary color
 *   logo-monochrome.svg      — mark + wordmark, near-black
 *   logo-footer.svg          — mark + wordmark, primary color (same palette as header)
 *   favicon.svg              — mark only, 32×32 rendered size
 *   favicon.ico              — 16×16 + 32×32 + 48×48 PNG packed into ICO
 *   apple-touch-icon.png     — mark at 180×180 PNG
 *   og-default.jpg           — 1200×630 brand card JPEG
 *
 * Color sources (in priority order):
 *   1. --primary / --accent CLI flags (for synthetic tests)
 *   2. site.config.yaml visual.primary_color / visual.accent_color
 *   3. config/niche-palettes.yaml default_primary_color / default_accent_color
 *
 * Mark SVG paths: keyed by niche in config/niche-palettes.yaml.
 * Font: site.config.yaml visual.font_headings → niche palette default → 'Georgia, serif'
 *
 * Placeholder check: all generated SVG must pass grep for '{{' — exit 1 if any remain.
 *
 * Exit: 0 = all assets generated cleanly, 1 = one or more failures
 */

import { existsSync, readdirSync, readFileSync, writeFileSync, mkdirSync } from 'fs'
import { join, dirname, resolve, basename } from 'path'
import { fileURLToPath } from 'url'
import { createRequire } from 'module'
import { homedir } from 'os'
import { loadPortfolio } from './lib/portfolio.mjs'

const require      = createRequire(import.meta.url)
const yaml         = require('js-yaml')
const sharp        = require('sharp')
const toIco        = require('to-ico')

const TOOLS_DIR    = dirname(fileURLToPath(import.meta.url))
const PLATFORM_DIR = join(TOOLS_DIR, '..')
const PALETTES_PATH = join(PLATFORM_DIR, 'config', 'niche-palettes.yaml')

// ── ANSI helpers ──────────────────────────────────────────────────────────────

const isTTY = process.stdout.isTTY
const esc   = isTTY ? (s, code) => `\x1b[${code}m${s}\x1b[0m` : s => s
const c = {
  green:  s => esc(s, '32'),
  red:    s => esc(s, '31'),
  yellow: s => esc(s, '33'),
  bold:   s => esc(s, '1'),
  dim:    s => esc(s, '2'),
}

// ── XML escaping ──────────────────────────────────────────────────────────────

function escXml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;')
}

// ── Arg parsing ───────────────────────────────────────────────────────────────

const argv    = process.argv.slice(2)
const get     = flag => { const i = argv.indexOf(flag); return i !== -1 ? argv[i + 1] : null }
const has     = flag => argv.includes(flag)

const siteSlug    = get('--site')
const testDir     = get('--test-dir') ? resolve(get('--test-dir')) : null
const dryRun      = has('--dry-run')
const onlyFilter  = get('--only')?.split(',').map(s => s.trim()) ?? null

// Synthetic-test overrides (no --site needed)
const cliNiche    = get('--niche')
const cliBrand    = get('--brand-name')
const cliPrimary  = get('--primary')
const cliAccent   = get('--accent')
const cliTagline  = get('--tagline')

const syntheticMode = !siteSlug && (cliBrand || cliNiche)

if (!siteSlug && !syntheticMode) {
  console.error('Usage: node tools/generate-brand-assets.mjs --site <slug> [--dry-run] [--test-dir <path>]')
  console.error('       node tools/generate-brand-assets.mjs --niche <niche> --brand-name "Name" [--primary "#color"] [--test-dir <path>]')
  process.exit(2)
}

// ── Niche palette loading ─────────────────────────────────────────────────────

function loadPalettes() {
  if (!existsSync(PALETTES_PATH)) {
    throw new Error(`config/niche-palettes.yaml not found at ${PALETTES_PATH}`)
  }
  const doc = yaml.load(readFileSync(PALETTES_PATH, 'utf-8'))
  if (!doc?.niches) throw new Error('niche-palettes.yaml missing niches key')
  return doc.niches
}

// ── Site config loading ───────────────────────────────────────────────────────

function loadSiteConfig(siteDir) {
  const cfgPath = join(siteDir, 'site.config.yaml')
  if (!existsSync(cfgPath)) throw new Error(`site.config.yaml not found at ${cfgPath}`)
  return yaml.load(readFileSync(cfgPath, 'utf-8'))
}

// ── Resolve brand params ──────────────────────────────────────────────────────

function resolveBrandParams(siteSlug, palettes, cliOverrides = {}) {
  let brandName, tagline, niche, primaryColor, accentColor, fontHeadings, siteDir

  if (siteSlug) {
    siteDir = join(homedir(), siteSlug)
    const sc = loadSiteConfig(siteDir)
    brandName    = sc?.site?.brand_name ?? siteSlug
    tagline      = sc?.site?.tagline    ?? ''
    niche        = sc?.site?.niche      ?? 'default'
    primaryColor = sc?.visual?.primary_color ?? null
    accentColor  = sc?.visual?.accent_color  ?? null
    fontHeadings = sc?.visual?.font_headings ?? null
  } else {
    brandName    = cliOverrides.brandName ?? 'Brand'
    tagline      = cliOverrides.tagline   ?? ''
    niche        = cliOverrides.niche     ?? 'default'
    primaryColor = cliOverrides.primary   ?? null
    accentColor  = cliOverrides.accent    ?? null
    fontHeadings = null
    siteDir      = null
  }

  // Override with CLI flags
  if (cliOverrides.primary) primaryColor = cliOverrides.primary
  if (cliOverrides.accent)  accentColor  = cliOverrides.accent

  // Fall back to niche palette defaults
  const palette = palettes[niche] ?? palettes['default'] ?? {}
  primaryColor = primaryColor ?? palette.default_primary_color ?? '#2D5016'
  accentColor  = accentColor  ?? palette.default_accent_color  ?? '#C19A4B'
  fontHeadings = fontHeadings ?? palette.default_font_headings ?? "Georgia, 'Times New Roman', serif"

  // If a single-word font name (no comma), append safe serif fallbacks
  if (!fontHeadings.includes(',')) {
    fontHeadings = `${fontHeadings}, Georgia, 'Times New Roman', serif`
  }

  return { brandName, tagline, niche, primaryColor, accentColor, fontHeadings, palette, siteDir }
}

// ── Mark SVG helpers ──────────────────────────────────────────────────────────

/**
 * Returns the mark paths string with {{fill}} substituted.
 */
function markPaths(palette, fill) {
  const raw = String(palette.mark_paths ?? '').trimEnd()
  return raw.replace(/\{\{fill\}\}/g, fill)
}

/**
 * Returns a <g> element containing the mark at its natural size.
 * The transform centers it vertically within logoHeight.
 */
function markGroup(palette, fill, logoHeight) {
  const mh = palette.mark_height ?? 40
  const dy = (logoHeight - mh) / 2
  const transform = dy !== 0 ? ` transform="translate(0,${dy.toFixed(1)})"` : ''
  return `<g${transform}>${markPaths(palette, fill)}</g>`
}

// ── SVG generators ────────────────────────────────────────────────────────────

/**
 * Estimate rendered text width: Georgia/Lora bold at given font-size.
 * Approximation: ~0.65 × fontSize per average character.
 */
function estimateTextWidth(text, fontSize) {
  return Math.ceil(text.length * fontSize * 0.65)
}

/**
 * Generates logo-header / logo-footer SVG (mark + wordmark).
 * @param {string} brandName
 * @param {object} palette
 * @param {string} fill — color for both mark and text
 * @param {string} fontStack
 * @returns {string}
 */
function generateLogoCombo(brandName, palette, fill, fontStack) {
  const mw = palette.mark_width  ?? 40
  const mh = palette.mark_height ?? 40
  const fontSize   = 19
  const gap        = 10
  const textX      = mw + gap
  const textY      = Math.round(mh / 2 + fontSize * 0.36)  // approximate vertical center
  const textWidth  = estimateTextWidth(brandName, fontSize) + 4  // small right pad
  const totalWidth = textX + textWidth
  const label      = escXml(brandName)

  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${totalWidth} ${mh}" width="${totalWidth}" height="${mh}" aria-label="${label}">
  ${markGroup(palette, fill, mh)}
  <text x="${textX}" y="${textY}" font-family="${fontStack}" font-size="${fontSize}" font-weight="bold" fill="${fill}">${label}</text>
</svg>`
}

/**
 * Generates logo-mark SVG (mark only, no text).
 */
function generateLogoMark(palette, fill, brandName) {
  const mw = palette.mark_width  ?? 40
  const mh = palette.mark_height ?? 40
  const label = escXml(brandName)
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${palette.mark_viewbox ?? `0 0 ${mw} ${mh}`}" width="${mw}" height="${mh}" aria-label="${label}">
  ${markPaths(palette, fill)}
</svg>`
}

/**
 * Generates favicon.svg — mark at 32×32 rendered size.
 */
function generateFaviconSvg(palette, fill) {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${palette.mark_viewbox ?? '0 0 40 40'}" width="32" height="32" aria-hidden="true">
  ${markPaths(palette, fill)}
</svg>`
}

/**
 * Renders mark SVG to a PNG buffer at the given pixel size.
 */
async function markToPng(palette, fill, size) {
  const mw = palette.mark_width  ?? 40
  const mh = palette.mark_height ?? 40
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${mw} ${mh}" width="${size}" height="${size}">${markPaths(palette, fill)}</svg>`
  return sharp(Buffer.from(svg)).png().toBuffer()
}

/**
 * Generates OG default image — 1200×630 brand card.
 * Uses sharp to render SVG → JPEG.
 */
async function generateOgDefaultJpeg(brandName, tagline, palette, primaryColor, accentColor, fontStack) {
  const mw     = palette.mark_width  ?? 40
  const mh     = palette.mark_height ?? 40
  const scale  = Math.round(630 * 0.45 / mh * 10) / 10   // mark occupies ~45% of image height
  const markX  = 90
  const markY  = Math.round((630 - mh * scale) / 2)
  const textX  = markX + Math.round(mw * scale) + 50
  const nameY  = tagline ? 280 : 315
  const tagY   = 360

  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 630" width="1200" height="630">
  <rect width="1200" height="630" fill="${primaryColor}"/>
  <rect x="0" y="0" width="8" height="630" fill="${accentColor}" opacity="0.6"/>
  <g transform="translate(${markX},${markY}) scale(${scale})">${markPaths(palette, 'white')}</g>
  <text x="${textX}" y="${nameY}" font-family="${fontStack}" font-size="68" font-weight="bold" fill="white">${escXml(brandName)}</text>
  ${tagline ? `<text x="${textX}" y="${tagY}" font-family="${fontStack}" font-size="26" fill="rgba(255,255,255,0.75)">${escXml(tagline)}</text>` : ''}
</svg>`

  return sharp(Buffer.from(svg)).jpeg({ quality: 85 }).toBuffer()
}

// ── Placeholder validation ────────────────────────────────────────────────────

function checkNoPlaceholders(content, filename) {
  const remaining = content.match(/\{\{[^}]+\}\}/g)
  if (remaining) {
    console.error(`  ${c.red('[FAIL]')} ${filename}: unreplaced placeholder(s): ${remaining.join(', ')}`)
    return false
  }
  return true
}

// ── Main ──────────────────────────────────────────────────────────────────────

let palettes
try { palettes = loadPalettes() } catch (err) {
  console.error(`${c.red('[ERROR]')} ${err.message}`)
  process.exit(2)
}

const params = resolveBrandParams(siteSlug, palettes, {
  niche:     cliNiche    ?? undefined,
  brandName: cliBrand    ?? undefined,
  primary:   cliPrimary  ?? undefined,
  accent:    cliAccent   ?? undefined,
  tagline:   cliTagline  ?? undefined,
})

const { brandName, tagline, niche, primaryColor, accentColor, fontHeadings, palette, siteDir } = params

const outDir = testDir ?? (siteDir ? join(siteDir, 'public', 'images', 'brand') : null)
if (!outDir) {
  console.error(`${c.red('[ERROR]')} Cannot determine output directory — provide --test-dir or --site`)
  process.exit(2)
}

console.log()
console.log(`${c.bold('Site:')}     ${siteSlug ?? c.dim('(synthetic)')}`)
console.log(`${c.bold('Brand:')}    ${brandName}`)
console.log(`${c.bold('Niche:')}    ${niche}`)
console.log(`${c.bold('Primary:')}  ${primaryColor}`)
console.log(`${c.bold('Accent:')}   ${accentColor}`)
console.log(`${c.bold('Font:')}     ${fontHeadings}`)
console.log(`${c.bold('Output:')}   ${testDir ? `${outDir} (test mode)` : outDir}`)
if (dryRun) console.log(c.yellow('  DRY RUN — no files written'))
console.log()

// ── Asset definitions ─────────────────────────────────────────────────────────

// Each asset: { name, type: 'svg'|'png'|'jpg'|'ico', generate: async fn → string|Buffer }
const assets = [
  {
    name: 'logo-header.svg',
    type: 'svg',
    generate: async () => generateLogoCombo(brandName, palette, primaryColor, fontHeadings),
  },
  {
    name: 'logo-header-dark.svg',
    type: 'svg',
    generate: async () => generateLogoCombo(brandName, palette, '#ffffff', fontHeadings),
  },
  {
    name: 'logo-mark.svg',
    type: 'svg',
    generate: async () => generateLogoMark(palette, primaryColor, brandName),
  },
  {
    name: 'logo-monochrome.svg',
    type: 'svg',
    generate: async () => generateLogoCombo(brandName, palette, '#1a1a1a', fontHeadings),
  },
  {
    name: 'logo-footer.svg',
    type: 'svg',
    generate: async () => generateLogoCombo(brandName, palette, primaryColor, fontHeadings),
  },
  {
    name: 'favicon.svg',
    type: 'svg',
    generate: async () => generateFaviconSvg(palette, primaryColor),
  },
  {
    name: 'apple-touch-icon.png',
    type: 'png',
    generate: async () => markToPng(palette, primaryColor, 180),
  },
  {
    name: 'favicon.ico',
    type: 'ico',
    generate: async () => {
      const [p16, p32, p48] = await Promise.all([
        markToPng(palette, primaryColor, 16),
        markToPng(palette, primaryColor, 32),
        markToPng(palette, primaryColor, 48),
      ])
      return toIco([p16, p32, p48])
    },
  },
  {
    name: 'og-default.jpg',
    type: 'jpg',
    generate: async () => generateOgDefaultJpeg(brandName, tagline, palette, primaryColor, accentColor, fontHeadings),
  },
].filter(a => !onlyFilter || onlyFilter.some(f => a.name.includes(f)))

if (dryRun) {
  console.log(`Assets that would be generated (${assets.length}):`)
  for (const a of assets) {
    console.log(`  ${c.dim(a.type.padEnd(4))}  ${a.name}`)
  }
  console.log()
  process.exit(0)
}

if (!existsSync(outDir)) mkdirSync(outDir, { recursive: true })

let exitCode = 0
let written = 0

for (const asset of assets) {
  try {
    const result = await asset.generate()

    if (asset.type === 'svg') {
      const svgStr = result
      if (!checkNoPlaceholders(svgStr, asset.name)) {
        exitCode = 1
        continue
      }
      writeFileSync(join(outDir, asset.name), svgStr, 'utf-8')
      console.log(`  ${c.green('[OK]')}  ${asset.name}  ${c.dim(`${svgStr.length}B`)}`)
    } else {
      const buf = result
      writeFileSync(join(outDir, asset.name), buf)
      const kb = (buf.length / 1024).toFixed(1)
      console.log(`  ${c.green('[OK]')}  ${asset.name}  ${c.dim(`${kb}KB`)}`)
    }
    written++
  } catch (err) {
    console.error(`  ${c.red('[FAIL]')} ${asset.name}: ${err.message}`)
    exitCode = 1
  }
}

console.log()
if (exitCode === 0) {
  console.log(c.green(`All ${written} assets generated.`))

  // Final placeholder check on all SVG files in outDir
  let placeholderFails = 0
  for (const a of assets.filter(x => x.type === 'svg')) {
    const content = readFileSync(join(outDir, a.name), 'utf-8')
    if (!checkNoPlaceholders(content, a.name)) placeholderFails++
  }
  if (placeholderFails > 0) {
    console.error(c.red(`\n${placeholderFails} SVG file(s) have unreplaced placeholders — check output.`))
    exitCode = 1
  }
} else {
  console.error(c.red(`${written} assets written, some failed — see above.`))
}

console.log()
process.exit(exitCode)
