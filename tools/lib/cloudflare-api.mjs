/**
 * Cloudflare Pages API client — thin fetch wrapper with auth and error handling.
 *
 * Read operations (GET): getProject, getCustomDomains, getEnvVars
 * Write operations (POST/PATCH): setEnvVar, attachCustomDomain, addDnsTxtRecord, lookupZoneId
 */

const ACCOUNT_ID = 'fedb496b1addc0743cb2a84fa5a7ba67'
const BASE       = `https://api.cloudflare.com/client/v4/accounts/${ACCOUNT_ID}`
const ZONES_BASE = `https://api.cloudflare.com/client/v4`

// ── Generic request helpers ───────────────────────────────────────────────────

async function cfGet(token, path) {
  const url = `${BASE}${path}`
  let res
  try {
    res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } })
  } catch (err) {
    throw new Error(`Network error fetching ${url}: ${err.message}`)
  }
  const body = await res.json()
  if (!body.success) {
    const msg = body.errors?.map(e => `${e.code}: ${e.message}`).join(', ') ?? 'unknown error'
    throw new Error(`Cloudflare API error on ${path}: ${msg}`)
  }
  return body.result
}

async function cfPost(token, path, data, { base = BASE } = {}) {
  const url = `${base}${path}`
  let res
  try {
    res = await fetch(url, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })
  } catch (err) {
    throw new Error(`Network error posting to ${url}: ${err.message}`)
  }
  const body = await res.json()
  if (!body.success) {
    const msg = body.errors?.map(e => `${e.code}: ${e.message}`).join(', ') ?? 'unknown error'
    throw new Error(`Cloudflare API error on POST ${path}: ${msg}`)
  }
  return body.result
}

async function cfPatch(token, path, data, { base = BASE } = {}) {
  const url = `${base}${path}`
  let res
  try {
    res = await fetch(url, {
      method: 'PATCH',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })
  } catch (err) {
    throw new Error(`Network error patching ${url}: ${err.message}`)
  }
  const body = await res.json()
  if (!body.success) {
    const msg = body.errors?.map(e => `${e.code}: ${e.message}`).join(', ') ?? 'unknown error'
    throw new Error(`Cloudflare API error on PATCH ${path}: ${msg}`)
  }
  return body.result
}

async function cfGetZones(token, path) {
  const url = `${ZONES_BASE}${path}`
  let res
  try {
    res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } })
  } catch (err) {
    throw new Error(`Network error fetching ${url}: ${err.message}`)
  }
  const body = await res.json()
  if (!body.success) {
    const msg = body.errors?.map(e => `${e.code}: ${e.message}`).join(', ') ?? 'unknown error'
    throw new Error(`Cloudflare API error on ${path}: ${msg}`)
  }
  return body.result
}

/**
 * Returns the Pages project object for the given project name.
 * @param {string} token
 * @param {string} projectName
 */
export async function getProject(token, projectName) {
  return cfGet(token, `/pages/projects/${projectName}`)
}

/**
 * Returns the list of custom domains for a Pages project.
 * @param {string} token
 * @param {string} projectName
 * @returns {Promise<Array<{name: string, status: string}>>}
 */
export async function getCustomDomains(token, projectName) {
  return cfGet(token, `/pages/projects/${projectName}/domains`)
}

/**
 * @typedef {{ value: string|null, type: 'plain_text'|'secret_text' }} EnvBinding
 */

/**
 * Returns the environment variable bindings for a Pages project.
 * Secrets have type "secret_text" and value "" (Cloudflare does not expose secret values).
 * Plain env vars have type "plain_text" and a readable value.
 *
 * @param {string} token
 * @param {string} projectName
 * @returns {Promise<{production: Record<string, EnvBinding>, preview: Record<string, EnvBinding>}>}
 */
export async function getEnvVars(token, projectName) {
  const project = await getProject(token, projectName)
  const extract = (envVars) => {
    if (!envVars) return {}
    return Object.fromEntries(
      Object.entries(envVars).map(([k, v]) => [k, {
        value: v?.value ?? null,
        type: v?.type ?? 'plain_text',
      }])
    )
  }
  return {
    production: extract(project.deployment_configs?.production?.env_vars),
    preview: extract(project.deployment_configs?.preview?.env_vars),
  }
}

// ── Write operations ──────────────────────────────────────────────────────────

/**
 * Sets a plain-text environment variable on a Pages project environment.
 * Idempotent: if the key already exists with the same value, does nothing.
 *
 * @param {string} token
 * @param {string} projectName
 * @param {'production'|'preview'} env
 * @param {string} key
 * @param {string} value
 * @returns {Promise<{changed: boolean}>}
 */
export async function setEnvVar(token, projectName, env, key, value) {
  // Read current value first to implement idempotency
  const current = await getEnvVars(token, projectName)
  const existing = current[env]?.[key]
  if (existing?.type === 'plain_text' && existing.value === value) {
    return { changed: false }
  }

  // PATCH the project with the new env var
  const envConfig = {}
  envConfig[key] = { value, type: 'plain_text' }

  const body = { deployment_configs: {} }
  body.deployment_configs[env] = { env_vars: envConfig }

  await cfPatch(token, `/pages/projects/${projectName}`, body)
  return { changed: true }
}

/**
 * Attaches a custom domain to a Cloudflare Pages project.
 * Idempotent: if the domain is already attached, returns {alreadyAttached: true}.
 *
 * @param {string} token
 * @param {string} projectName
 * @param {string} domain  — e.g. "example.com"
 * @returns {Promise<{alreadyAttached: boolean, domain: string, status: string}>}
 */
export async function attachCustomDomain(token, projectName, domain) {
  // Check if already attached
  const existing = await getCustomDomains(token, projectName)
  const found = (existing ?? []).find(d => d.name === domain)
  if (found) {
    return { alreadyAttached: true, domain: found.name, status: found.status ?? 'active' }
  }

  const result = await cfPost(token, `/pages/projects/${projectName}/domains`, { name: domain })
  return { alreadyAttached: false, domain: result.name, status: result.status ?? 'pending' }
}

/**
 * Returns the Cloudflare Zone ID for a given domain name.
 * Searches the account's zones for an exact name match.
 * Throws if no zone is found.
 *
 * @param {string} token
 * @param {string} domain  — e.g. "example.com"
 * @returns {Promise<string>}  — zone ID
 */
export async function lookupZoneId(token, domain) {
  // Zones API is at /client/v4/zones (not under account path)
  const result = await cfGetZones(token, `/zones?name=${encodeURIComponent(domain)}&per_page=5`)
  const zones  = Array.isArray(result) ? result : result?.result ?? []
  const match  = zones.find(z => z.name === domain)
  if (!match) throw new Error(`No Cloudflare zone found for domain "${domain}"`)
  return match.id
}

/**
 * Adds a DNS TXT record to a zone.
 * Idempotent: if a TXT record with the same content already exists, returns {alreadyExists: true}.
 *
 * @param {string} token
 * @param {string} zoneId
 * @param {string} name     — record name, "@" for root
 * @param {string} content  — TXT record content string
 * @returns {Promise<{alreadyExists: boolean, id: string}>}
 */
export async function addDnsTxtRecord(token, zoneId, name, content) {
  // List existing TXT records to check for duplicates
  const existing = await cfGetZones(token, `/zones/${zoneId}/dns_records?type=TXT&name=${encodeURIComponent(name)}&per_page=100`)
  const records  = Array.isArray(existing) ? existing : []
  const dup      = records.find(r => r.content === content)
  if (dup) return { alreadyExists: true, id: dup.id }

  const result = await cfPost(token, `/zones/${zoneId}/dns_records`, {
    type: 'TXT',
    name,
    content,
    ttl: 60,
  }, { base: ZONES_BASE })

  return { alreadyExists: false, id: result.id }
}
