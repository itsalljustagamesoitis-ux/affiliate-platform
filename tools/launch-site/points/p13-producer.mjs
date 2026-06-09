/**
 * Point 13 — Article generation (producer run)
 * Bucket A: Producer runs with locked persona
 *
 * Pre-condition: persona must be locked (persona_locked: true in persona YAML).
 * Hard gate — producer refuses to run without lock.
 */

import { existsSync, readFileSync, readdirSync } from 'fs'
import { join } from 'path'
import yaml from 'js-yaml'

export const POINT_ID = '13'
export const BUCKET = 'A'

function isPersonaLocked(siteDir) {
  const dir = join(siteDir, 'config', 'personas')
  if (!existsSync(dir)) return { locked: false, reason: 'personas directory not found' }

  let files
  try {
    files = readdirSync(dir).filter(f => f.endsWith('.yaml'))
  } catch {
    return { locked: false, reason: 'Cannot read personas directory' }
  }

  if (files.length === 0) {
    return { locked: false, reason: 'No YAML files in config/personas/' }
  }

  for (const name of files) {
    const p = join(dir, name)
    try {
      const persona = yaml.load(readFileSync(p, 'utf-8'))
      if (persona?.persona_locked === true) return { locked: true, file: name }
      return { locked: false, reason: `persona_locked not true in ${name}` }
    } catch {
      return { locked: false, reason: `Cannot parse ${name}` }
    }
  }
  return { locked: false, reason: 'No persona YAML found' }
}

export async function run(ctx) {
  const { slug, siteDir, platformDir, dryRun, log, execTool } = ctx

  // Persona lock check (§15.1 hard gate)
  const lockStatus = isPersonaLocked(siteDir)
  if (!lockStatus.locked) {
    return {
      status: 'fail',
      message: `Persona lock required. ${lockStatus.reason}. Run tools/lock-persona.mjs --site ${slug} first.`,
    }
  }
  log.info(`Persona locked (${lockStatus.file}) — proceeding with producer run`)

  const pipeline = join(siteDir, 'data', 'pipeline.json')
  if (!existsSync(pipeline)) {
    return { status: 'fail', message: `data/pipeline.json not found — run xlsx-to-pipeline.mjs first` }
  }

  // Producer entry point: <slug>-producer-v2.py (not article_builder.py)
  const producerPy = join(siteDir, 'producer', `${slug}-producer-v2.py`)
  if (!existsSync(producerPy)) {
    return { status: 'fail', message: `producer/${slug}-producer-v2.py not found` }
  }

  let articleCount = 0
  try {
    const pl = JSON.parse(readFileSync(pipeline, 'utf-8'))
    articleCount = (pl.articles ?? []).length
  } catch {
    return { status: 'fail', message: 'Cannot parse data/pipeline.json' }
  }

  if (articleCount < 150) {
    return { status: 'fail', message: `Pipeline has only ${articleCount} articles — minimum 150 required (§1.11)` }
  }

  log.info(`Producer run: ${articleCount} articles in pipeline`)

  if (!dryRun) {
    // --count 9999: generate all remaining pending articles (already-staged are skipped automatically)
    // Timeout: 12h — large catalogs at ~45 articles/hr need 6-7h for 306 articles
    const r = execTool(`cd "${siteDir}" && python3 producer/${slug}-producer-v2.py --count 9999`, { timeout: 43200000 })
    if (!r.ok) {
      return { status: 'fail', message: `Producer run failed: ${r.stderr.slice(0, 300)}` }
    }
    const countLine = r.stdout.split('\n').find(l => /generated|written|complete/i.test(l)) ?? ''
    if (countLine) log.info(countLine)
  } else {
    log.info(`(dry-run) would run producer/article_builder.py --all (${articleCount} articles)`)
  }

  return {
    status: 'pass',
    logFields: { article_count: articleCount, persona_locked: true },
  }
}
