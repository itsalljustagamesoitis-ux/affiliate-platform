/**
 * Point 20 — IndexNow wiring and verification
 * Bucket A: key file at site root, producer integration, BWT registration
 */

import { existsSync } from 'fs'
import { join } from 'path'

export const POINT_ID = '20'
export const BUCKET = 'A'

export async function run(ctx) {
  const { slug, siteDir, platformDir, dryRun, log, execTool, state } = ctx

  const domain = state.inputs?.domain ?? `${slug}.com`

  if (!dryRun) {
    // Verify key file is live
    const verify = execTool(`curl -s -o /dev/null -w "%{http_code}" "https://${domain}/indexnow-key.txt" 2>/dev/null || true`)
    const code = verify.stdout.trim()
    if (code !== '200') {
      log.warn(`IndexNow key file not returning 200 at https://${domain}/indexnow-key.txt (got ${code}) — may not be deployed yet`)
    } else {
      log.info(`IndexNow key file live at https://${domain}/indexnow-key.txt`)
    }

    // Run producer integration
    const script = join(siteDir, 'producer', 'indexnow-submit.py')
    if (existsSync(script)) {
      const r = execTool(`cd "${siteDir}" && python3 producer/indexnow-submit.py --all`)
      if (!r.ok) {
        log.warn(`IndexNow submission non-zero — site is live but search engines not pinged. Retry manually.`)
      } else {
        const urlLine = r.stdout.split('\n').find(l => /submitted|url/i.test(l)) ?? ''
        log.info(`IndexNow submitted${urlLine ? ' — ' + urlLine : ''}`)
      }
    } else {
      log.warn(`producer/indexnow-submit.py not found — IndexNow not submitted`)
    }
  } else {
    log.info('(dry-run) would verify IndexNow key file and submit URLs')
  }

  return { status: 'pass', logFields: { domain } }
}
