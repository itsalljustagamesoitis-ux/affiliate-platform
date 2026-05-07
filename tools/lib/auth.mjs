/**
 * Reads the Cloudflare oauth_token from the wrangler config file.
 *
 * TODO: migrate to dedicated CLOUDFLARE_API_TOKEN env var
 */

import { readFileSync } from 'fs'
import { homedir } from 'os'
import { join } from 'path'

const WRANGLER_CONFIG = join(homedir(), 'Library/Preferences/.wrangler/config/default.toml')

/**
 * Returns the oauth_token string from the wrangler default.toml.
 * Throws if the file is missing or the token field is absent.
 * @returns {string}
 */
export function getCloudflareToken() {
  if (process.env.CLOUDFLARE_API_TOKEN) {
    return process.env.CLOUDFLARE_API_TOKEN
  }
  let raw
  try {
    raw = readFileSync(WRANGLER_CONFIG, 'utf-8')
  } catch {
    throw new Error(`Cannot read wrangler config at ${WRANGLER_CONFIG}`)
  }
  const match = raw.match(/oauth_token\s*=\s*"([^"]+)"/)
  if (!match) throw new Error(`oauth_token not found in ${WRANGLER_CONFIG}`)
  return match[1]
}
