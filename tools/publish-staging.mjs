#!/usr/bin/env node
/**
 * publish-staging.mjs — Move articles from staging/ to content/articles/.
 *
 * Usage:
 *   node tools/publish-staging.mjs --site <slug>
 *   node tools/publish-staging.mjs --site <slug> --dry-run
 *   node tools/publish-staging.mjs --site <slug> --include-failed
 *   node tools/publish-staging.mjs --site <slug> --json
 *
 * Point 14 of the launch-site ritual (PIPELINE.md).
 *
 * Staging layout (both forms supported):
 *   staging/*.md              — flat form (spec default)
 *   staging/approved/*.md     — subdir form (used by OHT and newer sites)
 *   staging/failed/*.md       — validation failures, skipped by default
 */

import { existsSync, readdirSync, readFileSync, writeFileSync, mkdirSync, unlinkSync, renameSync } from 'fs'
import { join, basename } from 'path'
import { homedir } from 'os'
import { loadPortfolio } from './lib/portfolio.mjs'
import yaml from 'js-yaml'

// ── ANSI helpers ──────────────────────────────────────────────────────────────

const c = {
  green:  s => `\x1b[32m${s}\x1b[0m`,
  red:    s => `\x1b[31m${s}\x1b[0m`,
  yellow: s => `\x1b[33m${s}\x1b[0m`,
  bold:   s => `\x1b[1m${s}\x1b[0m`,
  dim:    s => `\x1b[2m${s}\x1b[0m`,
}

// ── Skip-list ─────────────────────────────────────────────────────────────────
//
// data/skip-list.yaml format: a plain YAML list of article slugs.
// Articles whose slug appears in the list are excluded from publish.
//
// Example data/skip-list.yaml:
//   - some-article-slug
//   - another-article-slug
//
// Missing file = empty skip list (not an error).

function loadSkipList(siteDir) {
  const skipFile = join(siteDir, 'data', 'skip-list.yaml')
  if (!existsSync(skipFile)) return new Set()
  try {
    const raw = readFileSync(skipFile, 'utf-8')
    const list = yaml.load(raw)
    if (!Array.isArray(list)) return new Set()
    return new Set(list.map(String))
  } catch {
    return new Set()
  }
}

// ── Pipeline.json status writeback ────────────────────────────────────────────
//
// After publishing an article, writes status: published to the matching entry
// in data/pipeline.json. Atomic write (tmp → rename). No-op if pipeline.json
// is absent. Batched: callers accumulate slugs; writePipelineStatus() called once.

function readPipeline(siteDir) {
  const pipelinePath = join(siteDir, 'data', 'pipeline.json')
  if (!existsSync(pipelinePath)) return null
  try {
    return { path: pipelinePath, data: JSON.parse(readFileSync(pipelinePath, 'utf-8')) }
  } catch {
    return null
  }
}

function writePipelineStatus(pipeline, publishedSlugs) {
  if (!pipeline || publishedSlugs.size === 0) return
  const articles = pipeline.data?.articles ?? (Array.isArray(pipeline.data) ? pipeline.data : [])
  let updated = 0
  for (const article of articles) {
    if (publishedSlugs.has(article.slug) && article.status !== 'published') {
      article.status = 'published'
      updated++
    }
  }
  if (updated === 0) return
  const tmp = pipeline.path + '.tmp'
  try {
    writeFileSync(tmp, JSON.stringify(pipeline.data, null, 2) + '\n', 'utf-8')
    renameSync(tmp, pipeline.path)
  } catch { /* non-fatal — pipeline writeback is best-effort */ }
}

// ── Arg parsing ───────────────────────────────────────────────────────────────

const args = process.argv.slice(2)
const get  = flag => { const i = args.indexOf(flag); return i !== -1 ? args[i + 1] : null }
const has  = flag => args.includes(flag)

const siteSlug      = get('--site')
const dryRun        = has('--dry-run')
const includeFailed = has('--include-failed')
const jsonMode      = has('--json')

if (!siteSlug) {
  console.error('Usage: node tools/publish-staging.mjs --site <slug> [--dry-run] [--include-failed] [--json]')
  process.exit(2)
}

// ── Site path resolution ──────────────────────────────────────────────────────

let sites
try {
  sites = loadPortfolio()
} catch (err) {
  console.error(`${c.red('[ERROR]')} Cannot load portfolio.yaml: ${err.message}`)
  process.exit(2)
}

if (!sites.find(s => s.slug === siteSlug)) {
  console.error(`${c.red('[ERROR]')} Site "${siteSlug}" not found in portfolio.yaml`)
  process.exit(2)
}

const siteDir     = join(homedir(), siteSlug)
const stagingDir  = join(siteDir, 'staging')
const articlesDir = join(siteDir, 'content', 'articles')

// Load skip-list and pipeline once; both are used inside publishFile
const skipList       = loadSkipList(siteDir)
const pipeline       = readPipeline(siteDir)
const publishedSlugs = new Set()

if (!jsonMode && skipList.size > 0) {
  console.log(c.dim(`  Skip-list: ${skipList.size} slug(s) will be excluded`))
}

// ── Validator output stripping ────────────────────────────────────────────────

// Matches the start of an appended validator block in either format:
//   <!-- VALIDATOR FAILURES --> (OHT producer)
//   --- VALIDATOR REPORT ---
//   Lines starting with [FAIL], [PASS], [WARN], [MANUAL] after content
const VALIDATOR_BLOCK_RE = /^(<!--\s*VALIDATOR\s*(?:FAILURES|REPORT)\s*-->|---\s*VALIDATOR\s*(?:FAILURES|REPORT)\s*---|\[(?:FAIL|PASS|WARN|MANUAL)\])/m

/**
 * Strips appended validator output from article content.
 * Removes everything from the first validator marker to end of file.
 * Preserves a single trailing newline.
 * @param {string} content
 * @returns {{ cleaned: string, stripped: boolean }}
 */
function stripValidatorOutput(content) {
  const match = VALIDATOR_BLOCK_RE.exec(content)
  if (!match) return { cleaned: content, stripped: false }
  const cleaned = content.slice(0, match.index).trimEnd() + '\n'
  return { cleaned, stripped: true }
}

// ── Frontmatter + body validation ────────────────────────────────────────────

/**
 * Validates that content has intact frontmatter and at least one H2.
 * @param {string} content
 * @returns {{ valid: boolean, reason?: string }}
 */
function validateContent(content) {
  if (!content.startsWith('---')) {
    return { valid: false, reason: 'missing opening --- delimiter' }
  }
  const secondDelim = content.indexOf('\n---', 3)
  if (secondDelim === -1) {
    return { valid: false, reason: 'no closing --- delimiter' }
  }
  const body = content.slice(secondDelim + 4)
  if (!/^##\s+/m.test(body)) {
    return { valid: false, reason: 'no ## heading in body' }
  }
  return { valid: true }
}

// ── File discovery ────────────────────────────────────────────────────────────

/**
 * Returns .md file paths from a directory (non-recursive).
 * @param {string} dir
 * @returns {string[]} absolute paths
 */
function getMdFiles(dir) {
  if (!existsSync(dir)) return []
  return readdirSync(dir)
    .filter(f => f.endsWith('.md'))
    .map(f => join(dir, f))
}

// ── Main ──────────────────────────────────────────────────────────────────────

if (!existsSync(stagingDir)) {
  console.error(`${c.red('[ERROR]')} No staging directory at ${stagingDir}`)
  process.exit(2)
}

const approvedDir = join(stagingDir, 'approved')
const failedDir   = join(stagingDir, 'failed')

const topLevelFiles = getMdFiles(stagingDir)
const approvedFiles = getMdFiles(approvedDir)
const failedFiles   = getMdFiles(failedDir)

// Both flat (staging/*.md) and subdir (staging/approved/*.md) are ready to publish
const readyFiles = [...topLevelFiles, ...approvedFiles]

if (!jsonMode) {
  console.log()
  console.log(`${c.bold('Site:')} ${siteSlug}`)
  console.log(`${c.bold('Staging:')} ${stagingDir}`)
  if (dryRun) console.log(c.yellow('  DRY RUN — no files will be moved'))
  console.log()

  const approvedNote = approvedFiles.length > 0
    ? ` (${approvedFiles.length} from approved/, ${topLevelFiles.length} top-level)`
    : ''
  console.log(`Files ready to publish: ${readyFiles.length}${approvedNote}`)

  const failedNote = failedFiles.length > 0
    ? includeFailed
      ? ' (will be published with --include-failed)'
      : ' (will not be published — use --include-failed to override)'
    : ''
  console.log(`Files in staging/failed/: ${failedFiles.length}${failedNote}`)
  console.log()
}

const hasAnything = readyFiles.length > 0 || (includeFailed && failedFiles.length > 0)
if (!hasAnything) {
  if (!jsonMode) console.log('No articles to publish.')
  if (jsonMode) process.stdout.write(JSON.stringify({ site: siteSlug, dry_run: dryRun, published: 0, skipped: 0, failed_left: failedFiles.length }, null, 2) + '\n')
  process.exit(0)
}

if (!dryRun && !existsSync(articlesDir)) {
  mkdirSync(articlesDir, { recursive: true })
}

const results = {
  published:        [],
  skipped:          [],
  failed_published: [],
  failed_skipped:   [],
}

/**
 * Validates, strips validator output, and publishes a single file.
 * @param {string} filePath
 * @param {'ready'|'failed'} pool
 */
function publishFile(filePath, pool) {
  const filename = basename(filePath)
  const slug     = basename(filePath, '.md')

  // Skip-list check — intentional exclusion, not a validation failure
  if (skipList.has(slug)) {
    if (!jsonMode) console.log(`  ${c.yellow('[SKIP-LIST]')} ${filename} ${c.dim('(in data/skip-list.yaml)')}`)
    results.skipped.push({ file: filename, reason: 'skip-listed' })
    return
  }

  const raw = readFileSync(filePath, 'utf-8')

  const { cleaned, stripped } = stripValidatorOutput(raw)
  const { valid, reason } = validateContent(cleaned)

  if (!valid) {
    if (!jsonMode) console.log(`  ${c.yellow('[SKIP]   ')} ${filename} ${c.dim(`(${reason})`)}`)
    results.skipped.push({ file: filename, reason })
    return
  }

  const dest = join(articlesDir, filename)
  const tag = pool === 'failed' ? c.yellow('[PUBLISH-F]') : c.green('[PUBLISH]  ')
  const strippedNote = stripped ? c.dim(' (validator output stripped)') : ''
  if (!jsonMode) console.log(`  ${tag} ${filename}${strippedNote}`)

  if (!dryRun) {
    writeFileSync(dest, cleaned, 'utf-8')
    unlinkSync(filePath)
    publishedSlugs.add(slug)
  }

  if (pool === 'failed') {
    results.failed_published.push({ file: filename, stripped })
  } else {
    results.published.push({ file: filename, stripped })
  }
}

for (const f of readyFiles)  publishFile(f, 'ready')
for (const f of failedFiles) {
  if (includeFailed) {
    publishFile(f, 'failed')
  } else {
    results.failed_skipped.push({ file: basename(f) })
  }
}

// ── Pipeline.json status writeback ────────────────────────────────────────────

writePipelineStatus(pipeline, publishedSlugs)

// ── Summary ───────────────────────────────────────────────────────────────────

const totalPublished = results.published.length + results.failed_published.length

if (!jsonMode) {
  console.log()
  const parts = []
  if (results.published.length > 0)        parts.push(`${results.published.length} published`)
  if (results.failed_published.length > 0) parts.push(`${results.failed_published.length} published from failed/`)
  if (results.skipped.length > 0)          parts.push(`${results.skipped.length} skipped`)
  if (results.failed_skipped.length > 0)   parts.push(`${results.failed_skipped.length} left in failed/`)
  if (parts.length === 0)                  parts.push('0 published')
  console.log(`Summary: ${parts.join(', ')}`)

  if (!dryRun) {
    const remaining = getMdFiles(stagingDir).length + getMdFiles(approvedDir).length
    if (remaining === 0) {
      console.log(c.green('staging/ now contains 0 .md files (success)'))
    } else {
      console.log(c.yellow(`staging/ still contains ${remaining} .md file(s)`))
    }
  }
  console.log()
}

if (jsonMode) {
  const skipListedCount = results.skipped.filter(s => s.reason === 'skip-listed').length
  process.stdout.write(JSON.stringify({
    site: siteSlug,
    dry_run: dryRun,
    published: totalPublished,
    skipped: results.skipped.length,
    skip_listed: skipListedCount,
    failed_published: results.failed_published.length,
    failed_left: results.failed_skipped.length,
    details: results,
  }, null, 2) + '\n')
}

process.exit(results.skipped.length > 0 ? 1 : 0)
