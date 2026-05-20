#!/usr/bin/env node
/**
 * validate-image-markdown.mjs
 *
 * Scans article markdown files for image markdown with invalid URLs.
 * Catches the dict-literal producer bug: ![alt]({'alt': 'x', 'path': 'y.webp'})
 *
 * Checks:
 *   - URL starts with { (dict literal — the Ten27/Northwoods bug)
 *   - URL contains unresolved {{ template syntax }}
 *   - URL contains whitespace (except legitimate encoded spaces in external URLs)
 *   - URL has no recognisable image extension (local paths only)
 *   - URL is empty
 *
 * Exit codes:
 *   0 – all image markdown valid
 *   1 – ≥1 invalid image URL found
 *   2 – usage/config error
 *
 * Usage:
 *   node scripts/validate-image-markdown.mjs --site northwoods-overland
 *   node scripts/validate-image-markdown.mjs --site northwoods-overland --verbose
 */

import { readFileSync, readdirSync, existsSync } from 'node:fs'
import { resolve, join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const PLATFORM_ROOT = resolve(__dirname, '..')

const args = process.argv.slice(2)
const siteArg = args[args.indexOf('--site') + 1]
const verbose  = args.includes('--verbose')

if (!siteArg) {
  console.error('Usage: node scripts/validate-image-markdown.mjs --site <site-slug>')
  process.exit(2)
}

function findSiteRoot(slug) {
  const parentDir = resolve(PLATFORM_ROOT, '..')
  const candidates = [
    join(parentDir, slug),
    resolve(process.env.HOME || '/root', slug),
  ]
  for (const p of candidates) {
    if (existsSync(join(p, 'content', 'articles'))) return p
  }
  return null
}

const siteRoot = findSiteRoot(siteArg)
if (!siteRoot) {
  console.error(`[ERROR] Could not locate site root for "${siteArg}"`)
  process.exit(2)
}

const articlesDir = join(siteRoot, 'content', 'articles')
if (!existsSync(articlesDir)) {
  console.error(`[ERROR] articles dir not found: ${articlesDir}`)
  process.exit(2)
}

const VALID_IMAGE_EXTS = new Set(['.webp', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.avif'])

// Matches all ![...](url) markdown image patterns
const IMG_MD_RE = /!\[([^\]]*)\]\(([^)]+)\)/g

function validateUrl(url, altText, filepath, lineNum) {
  const issues = []

  // Dict-literal bug (the producer bug we're guarding against)
  if (url.startsWith('{')) {
    issues.push({ filepath, lineNum, issue: 'dict-literal URL', alt: altText, url })
    return issues
  }

  // Unresolved template variable
  if (/\{\{/.test(url)) {
    issues.push({ filepath, lineNum, issue: 'unresolved template syntax in URL', alt: altText, url })
  }

  // Empty URL
  if (!url.trim()) {
    issues.push({ filepath, lineNum, issue: 'empty URL', alt: altText, url })
    return issues
  }

  // External URLs: only basic sanity checks
  if (url.startsWith('http://') || url.startsWith('https://')) {
    // External images: just confirm no obviously broken patterns
    if (/\s/.test(url)) {
      issues.push({ filepath, lineNum, issue: 'whitespace in external URL', alt: altText, url })
    }
    return issues
  }

  // Local paths: whitespace is always wrong
  if (/\s/.test(url)) {
    issues.push({ filepath, lineNum, issue: 'whitespace in local URL', alt: altText, url })
  }

  // Local paths: must end with a recognised image extension
  const lower = url.toLowerCase().split('?')[0].split('#')[0]
  const hasExt = [...VALID_IMAGE_EXTS].some(ext => lower.endsWith(ext))
  if (!hasExt) {
    issues.push({ filepath, lineNum, issue: `no valid image extension (got: ${lower.slice(-10)})`, alt: altText, url })
  }

  return issues
}

function checkFile(filepath) {
  const content = readFileSync(filepath, 'utf8')
  const lines = content.split('\n')
  const issues = []

  // Walk line by line for accurate line numbers
  for (let i = 0; i < lines.length; i++) {
    let match
    const lineRe = /!\[([^\]]*)\]\(([^)]+)\)/g
    while ((match = lineRe.exec(lines[i])) !== null) {
      const altText = match[1]
      const url = match[2]
      issues.push(...validateUrl(url, altText, filepath, i + 1))
    }
  }

  return issues
}

const files = readdirSync(articlesDir)
  .filter(f => f.endsWith('.md'))
  .sort()

const allIssues = []
for (const filename of files) {
  const filepath = join(articlesDir, filename)
  const issues = checkFile(filepath)
  if (issues.length > 0) {
    allIssues.push(...issues)
    if (verbose) {
      for (const issue of issues) {
        console.warn(`  [${filename}:${issue.lineNum}] ${issue.issue}`)
        console.warn(`    URL: ${issue.url.substring(0, 100)}`)
      }
    }
  }
}

const RED   = '\x1b[31m'
const GREEN = '\x1b[32m'
const RESET = '\x1b[0m'

if (allIssues.length > 0) {
  console.error(`\n${RED}FAIL: ${allIssues.length} invalid image URL(s) found in ${siteArg}${RESET}`)

  // Group by issue type for readable summary
  const byType = {}
  for (const issue of allIssues) {
    byType[issue.issue] = (byType[issue.issue] ?? 0) + 1
  }
  for (const [type, count] of Object.entries(byType)) {
    console.error(`  ${RED}✗${RESET} ${count}× ${type}`)
  }

  if (!verbose) {
    console.error('\n  Run with --verbose for full details, or fix with:')
    console.error(`  python3 scripts/fix-image-markdown.py --site ${siteArg}`)
  }

  process.exit(1)
}

console.log(`${GREEN}PASS: All image markdown URLs valid in ${siteArg} (${files.length} articles checked)${RESET}`)
process.exit(0)
