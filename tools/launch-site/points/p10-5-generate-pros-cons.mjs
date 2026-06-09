/**
 * Point 10.5 — Generate default_pros / default_cons via Claude Haiku
 * Bucket A: idempotent, resumable (state at /tmp/generate-product-pros-cons-<slug>-state.json)
 *
 * Runs generate-product-pros-cons.py against all products that have empty pros.
 * Cost: ~$0.90 for 1,000–1,500 products at Haiku rates.
 * Required before the producer run — article_builder.py reads these fields for buyer_guide
 * article_specific_pros/cons frontmatter; empty fields → F09 failures on every buyer_guide.
 */

import { existsSync, readFileSync } from 'fs'
import { join } from 'path'
import yaml from 'js-yaml'

export const POINT_ID = '10.5'
export const BUCKET = 'A'

function countNeedingGeneration(productsPath) {
  try {
    const data = yaml.load(readFileSync(productsPath, 'utf-8')) ?? {}
    const placeholderRe = /^(Well-reviewed|From |Strong customer ratings|Verify specifications)/i
    let count = 0
    for (const [, v] of Object.entries(data)) {
      if (typeof v !== 'object' || !v) continue
      const asin = String(v.asin || v.amazon_asin || '')
      if (['', 'NOT_ON_AMAZON', 'NOT_FOUND', 'VERIFY'].includes(asin)) continue
      const pros = v.default_pros ?? []
      const isEmpty = pros.length === 0 || pros.some(p => placeholderRe.test(String(p)))
      if (isEmpty) count++
    }
    return count
  } catch {
    return -1
  }
}

export async function run(ctx) {
  const { slug, siteDir, platformDir, dryRun, log, execTool } = ctx

  const tool = join(platformDir, 'tools', 'generate-product-pros-cons.py')
  if (!existsSync(tool)) {
    return { status: 'fail', message: `generate-product-pros-cons.py not found at ${tool}` }
  }

  const productsPath = join(siteDir, 'content', 'products', 'products.yaml')
  if (!existsSync(productsPath)) {
    return { status: 'fail', message: `content/products/products.yaml not found` }
  }

  const needCount = countNeedingGeneration(productsPath)
  if (needCount < 0) {
    return { status: 'fail', message: `Cannot parse products.yaml` }
  }

  if (needCount === 0) {
    log.info(`All products already have pros/cons — skipping generation`)
    return { status: 'pass', logFields: { generated: 0 } }
  }

  log.info(`${needCount} products need pros/cons generation (Claude Haiku)…`)
  log.info(`Est. cost: $${(needCount * 0.0007).toFixed(2)} | Est. time: ${Math.ceil(needCount * 0.2 / 60)} min`)

  if (!dryRun) {
    // Timeout: 3 hours for up to 1,500 products (0.15s sleep + API latency per product)
    const r = execTool(
      `cd "${siteDir}" && python3 "${tool}" --site ${slug}`,
      { timeout: 10800000 },
    )
    if (!r.ok) {
      return { status: 'fail', message: `Pros/cons generation failed: ${r.stderr.slice(0, 500)}` }
    }
    const summaryLine = r.stdout.split('\n').find(l => /processed|complete|run complete/i.test(l)) ?? ''
    if (summaryLine) log.info(summaryLine)

    const remaining = countNeedingGeneration(productsPath)
    if (remaining > 0) {
      log.warn(`${remaining} products still have no pros/cons after generation (errors/skips) — proceeding`)
    } else {
      log.info(`All products now have pros/cons`)
    }
  } else {
    log.info(`(dry-run) would run generate-product-pros-cons.py for ${needCount} products`)
  }

  return {
    status: 'pass',
    logFields: { generated: needCount },
  }
}
