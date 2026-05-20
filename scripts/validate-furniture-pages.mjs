#!/usr/bin/env node
/**
 * validate-furniture-pages.mjs
 *
 * Validates site "furniture pages" (static non-article pages) for:
 *
 *   1. HARD persona-claim violations — same FTC-risk patterns as validate-persona-claims.mjs
 *      catches in articles (fabricated testing claims). Furniture pages carry the same risk.
 *
 *   2. Previous-vertical vocabulary bleed — terms that belong to a prior site's vertical
 *      and have accidentally leaked into this site's templates.
 *      Configured via config/furniture-validation.yaml or site.config.yaml:forbidden_vocabulary.
 *
 * Exit codes:
 *   0 – all checks pass
 *   1 – ≥1 HARD violation or ≥1 vocabulary-bleed match
 *   2 – usage/config error
 *
 * Usage:
 *   node scripts/validate-furniture-pages.mjs --site northwoods-overland
 *   node scripts/validate-furniture-pages.mjs --site ten27 --verbose
 */

import { readFileSync, existsSync, readdirSync } from 'node:fs'
import { resolve, join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const PLATFORM_ROOT = resolve(__dirname, '..')

const args = process.argv.slice(2)
const siteArg = args[args.indexOf('--site') + 1]
const verbose  = args.includes('--verbose')

if (!siteArg) {
  console.error('Usage: node scripts/validate-furniture-pages.mjs --site <site-slug>')
  process.exit(2)
}

// ---------------------------------------------------------------------------
// Site root resolution
// ---------------------------------------------------------------------------

function findSiteRoot(slug) {
  const parentDir = resolve(PLATFORM_ROOT, '..')
  const candidates = [
    join(parentDir, slug),
    resolve(process.env.HOME || '/root', slug),
  ]
  for (const p of candidates) {
    if (existsSync(join(p, 'src', 'pages'))) return p
  }
  return null
}

const siteRoot = findSiteRoot(siteArg)
if (!siteRoot) {
  console.error(`[ERROR] Could not locate site root for "${siteArg}"`)
  process.exit(2)
}

// ---------------------------------------------------------------------------
// Furniture pages — the static pages that carry editorial/legal copy
// ---------------------------------------------------------------------------

const FURNITURE_FILENAMES = [
  'index.astro',
  'about.astro',
  'privacy-policy.astro',
  'terms.astro',
  'disclaimer.astro',
  'affiliate-disclosure.astro',
  'contact.astro',
  'how-we-test.astro',
  'how-we-research.astro',
]

const pagesDir = join(siteRoot, 'src', 'pages')

// ---------------------------------------------------------------------------
// Text extraction — strip Astro/JSX syntax, leaving only static text content
// ---------------------------------------------------------------------------

function extractStaticText(source) {
  // 1. Remove Astro frontmatter block
  let text = source
  if (text.startsWith('---\n')) {
    const end = text.indexOf('\n---\n', 4)
    if (end !== -1) text = text.slice(end + 5)
  }

  // 2. Remove self-closing tags first (avoids cross-block greediness)
  //    e.g. <script type="..." set:html={...} /> and <Component />
  text = text.replace(/<[a-zA-Z][^>]*\/>/g, ' ')

  // 3. Remove <style> blocks entirely
  text = text.replace(/<style[^>]*>[\s\S]*?<\/style>/gi, ' ')

  // 4. Remove <script> blocks entirely (non-self-closing)
  text = text.replace(/<script[^>]*>[\s\S]*?<\/script>/gi, ' ')

  // 5. Remove JSX/template expressions: {expression}
  //    Iteratively remove balanced braces to handle nesting
  let prev = ''
  while (prev !== text) {
    prev = text
    text = text.replace(/\{[^{}]*\}/g, ' ')
  }

  // 6. Remove HTML/JSX tags
  text = text.replace(/<[^>]+>/g, ' ')

  // 7. Collapse whitespace
  text = text.replace(/\s+/g, ' ').trim()

  return text
}

// ---------------------------------------------------------------------------
// Pattern definitions (matches validate-persona-claims.mjs)
// ---------------------------------------------------------------------------

const HARD_PATTERNS = [
  { re: /\bI (?:personally )?tested\b/gi,              label: 'personal-test' },
  { re: /\bI'?ve (?:owned|tested)\b/gi,                label: 'personal-ownership' },
  { re: /\bIn my (?:testing|hands-on use|personal use)\b/gi, label: 'my-testing' },
  { re: /\bmy (?:personal )?(?:testing|hands-on)\b/gi, label: 'my-hands-on' },
  { re: /\bwhen I (?:tested|tried|installed) (?:this|it|the)\b/gi, label: 'when-i-tested' },
  { re: /\bI(?:'ve)? been (?:using|running|testing) this\b/gi, label: 'i-been-using' },
  { re: /\bafter (?:\d+ )?(?:weeks?|months?|nights?|trips?) of (?:using|testing|running) (?:this|it)\b/gi, label: 'after-N-testing' },
  { re: /\bIn my (?:experience|opinion) (?:with|using)\b/gi, label: 'my-experience-with' },
  { re: /\bMy experience with\b/gi,                    label: 'my-experience-with-2' },
  { re: /\bWhen I (?:tested|used|installed|ran)\b/gi,  label: 'when-i-used' },
  // Home page / furniture-specific pattern that passed through Ten27 UAT
  { re: /Every review (?:on this site )?is based on real use\b/gi, label: 'every-review-real-use' },
  { re: /\bbased on direct (?:\w+ )?(?:testing|use|experience|ownership)\b/gi, label: 'based-on-direct-testing' },
]

// ---------------------------------------------------------------------------
// Load forbidden vocabulary from config
// (config/furniture-validation.yaml or site.config.yaml forbidden_vocabulary key)
// ---------------------------------------------------------------------------

function parseSimpleYaml(text) {
  const result = {}
  let currentKey = null
  let currentList = null
  for (const raw of text.split('\n')) {
    const line = raw.replace(/\s*#.*$/, '')
    if (!line.trim()) continue
    const listMatch = line.match(/^(\s*)- (.+)$/)
    if (listMatch && currentList !== null) {
      currentList.push(listMatch[2].trim().replace(/^['"]|['"]$/g, ''))
      continue
    }
    const kvMatch = line.match(/^([a-z_][a-z0-9_]*):\s*(.*)$/)
    if (kvMatch) {
      currentKey = kvMatch[1]
      const val = kvMatch[2].trim()
      if (val === '' || val === '[]') {
        result[currentKey] = []
        currentList = result[currentKey]
      } else {
        result[currentKey] = val.replace(/^['"]|['"]$/g, '')
        currentList = null
      }
    }
  }
  return result
}

let forbiddenTerms = []

const validationConfigPath = join(siteRoot, 'config', 'furniture-validation.yaml')
const siteConfigPath = join(siteRoot, 'site.config.yaml')

if (existsSync(validationConfigPath)) {
  try {
    const raw = parseSimpleYaml(readFileSync(validationConfigPath, 'utf8'))
    if (Array.isArray(raw.forbidden_vocabulary)) {
      forbiddenTerms = raw.forbidden_vocabulary.filter(Boolean)
    }
  } catch (e) {
    console.warn(`[WARN] Could not parse config/furniture-validation.yaml: ${e.message}`)
  }
} else if (existsSync(siteConfigPath)) {
  try {
    const raw = parseSimpleYaml(readFileSync(siteConfigPath, 'utf8'))
    if (Array.isArray(raw.forbidden_vocabulary)) {
      forbiddenTerms = raw.forbidden_vocabulary.filter(Boolean)
    }
  } catch (_) { /* ok — site.config.yaml is complex YAML, simple parser may fail */ }
}

if (forbiddenTerms.length > 0 && verbose) {
  console.log(`Forbidden vocabulary loaded: ${forbiddenTerms.length} terms`)
}

// ---------------------------------------------------------------------------
// Scan furniture pages
// ---------------------------------------------------------------------------

const hardViolations = []
const bleedMatches   = []
const checkedPages   = []
const missingPages   = []

for (const filename of FURNITURE_FILENAMES) {
  const filepath = join(pagesDir, filename)
  if (!existsSync(filepath)) {
    missingPages.push(filename)
    continue
  }

  checkedPages.push(filename)
  const source = readFileSync(filepath, 'utf8')
  const text   = extractStaticText(source)
  const lines  = text.split('. ')  // approximate sentence-level context for reporting

  // Persona-claim patterns
  for (const { re, label } of HARD_PATTERNS) {
    re.lastIndex = 0
    const m = re.exec(text)
    if (m) {
      hardViolations.push({
        filename,
        label,
        match: m[0],
        context: text.slice(Math.max(0, m.index - 60), m.index + m[0].length + 60).trim(),
      })
    }
  }

  // Vocabulary bleed
  for (const term of forbiddenTerms) {
    const re = new RegExp(`\\b${term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, 'i')
    const m  = re.exec(text)
    if (m) {
      bleedMatches.push({
        filename,
        term,
        match: m[0],
        context: text.slice(Math.max(0, m.index - 60), m.index + m[0].length + 60).trim(),
      })
    }
  }
}

// ---------------------------------------------------------------------------
// Output
// ---------------------------------------------------------------------------

const RED    = '\x1b[31m'
const GREEN  = '\x1b[32m'
const YELLOW = '\x1b[33m'
const BOLD   = '\x1b[1m'
const RESET  = '\x1b[0m'

console.log(`\n${BOLD}Furniture-Page Audit — ${siteArg}${RESET}`)
console.log(`Pages checked:       ${checkedPages.join(', ')}`)
if (missingPages.length > 0) {
  console.log(`Pages absent:        ${missingPages.join(', ')} (skipped)`)
}
console.log(`HARD violations:     ${hardViolations.length}`)
console.log(`Vocabulary bleed:    ${bleedMatches.length}`)
if (forbiddenTerms.length === 0) {
  console.log(`${YELLOW}(No forbidden vocabulary configured — add config/furniture-validation.yaml for bleed detection)${RESET}`)
}
console.log()

let hasFail = false

if (hardViolations.length > 0) {
  hasFail = true
  console.log(`${RED}${BOLD}HARD persona-claim violations:${RESET}`)
  for (const v of hardViolations) {
    console.log(`  ${RED}✗${RESET} ${v.filename}  [${v.label}]  "${v.match}"`)
    if (verbose) console.log(`      …${v.context}…`)
  }
  console.log()
}

if (bleedMatches.length > 0) {
  hasFail = true
  console.log(`${RED}${BOLD}Vocabulary bleed (prior-vertical terms found):${RESET}`)
  for (const b of bleedMatches) {
    console.log(`  ${RED}✗${RESET} ${b.filename}  [forbidden: "${b.term}"]  matched: "${b.match}"`)
    if (verbose) console.log(`      …${b.context}…`)
  }
  console.log()
}

if (hasFail) {
  console.log(`${RED}✗ Furniture-page audit FAILED — fix violations before Phase 2 / Phase 5 close${RESET}`)
  process.exit(1)
}

console.log(`${GREEN}✓ Furniture-page audit passed — no persona-claim violations or vocabulary bleed${RESET}`)
process.exit(0)
