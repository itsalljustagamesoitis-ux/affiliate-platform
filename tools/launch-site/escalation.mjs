/**
 * escalation.mjs — Retry, escalate, and halt policies.
 *
 * Hierarchy per §16.6:
 *   1. Retry with backoff — transient failures
 *   2. Apply alternate policy — documented fallbacks
 *   3. Escalate to Keith with diagnostic — policy exhausted
 *   4. Halt cleanly — state preserved, resumable
 *
 * The ritual never proceeds with degraded state.
 */

// ── Retry ─────────────────────────────────────────────────────────────────────

export async function withRetry(fn, opts = {}) {
  const {
    maxAttempts = 3,
    backoffMs   = [2000, 10000, 30000],
    label       = 'operation',
    log         = console,
  } = opts

  let lastErr
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      return await fn(attempt)
    } catch (err) {
      lastErr = err
      if (attempt < maxAttempts) {
        const delay = backoffMs[attempt - 1] ?? backoffMs[backoffMs.length - 1]
        log.warn?.(`${label} attempt ${attempt}/${maxAttempts} failed: ${err.message}. Retrying in ${delay}ms…`)
        await new Promise(r => setTimeout(r, delay))
      }
    }
  }
  throw new Error(`${label} failed after ${maxAttempts} attempts: ${lastErr.message}`)
}

// ── Structured halt requests ──────────────────────────────────────────────────

export function buildHaltRequest(point, title, actions, estimatedMinutes = 5) {
  return {
    point:              String(point),
    title,
    actions,
    estimated_minutes:  estimatedMinutes,
  }
}

export function formatHaltMessage(request, slug) {
  const lines = [
    '',
    `RITUAL HALT — Point ${request.point}: ${request.title}`,
    '',
    'Action required from Keith:',
  ]
  request.actions.forEach((action, i) => lines.push(`${i + 1}. ${action}`))
  lines.push('')
  lines.push(`Estimated time: ${request.estimated_minutes} minutes.`)
  lines.push('')
  lines.push(`Resume: node tools/launch-site.mjs --resume ${slug}`)
  return lines.join('\n')
}

// ── Validator retry loop ──────────────────────────────────────────────────────

/**
 * Run a validator and regenerate failing articles up to maxAttempts times.
 * regenerateFn receives an array of failing article IDs and returns void.
 * validatorFn returns { failCount, failIds, output }.
 *
 * After maxAttempts, moves articles to skip-list and returns 'skip_listed'.
 */
export async function validatorLoop(validatorFn, regenerateFn, opts = {}) {
  const { maxAttempts = 3, label = 'validator', log = console } = opts
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    const result = await validatorFn()
    if (result.failCount === 0) return { status: 'pass' }
    if (attempt < maxAttempts) {
      log.warn?.(`${label}: ${result.failCount} failures on attempt ${attempt}/${maxAttempts} — regenerating`)
      await regenerateFn(result.failIds)
    } else {
      return { status: 'skip_listed', skipIds: result.failIds }
    }
  }
}
