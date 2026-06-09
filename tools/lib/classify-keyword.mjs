/**
 * Infers article type from keyword text.
 * Used as a fallback when Article Type is empty in the launch xlsx.
 *
 * Priority order: comparison → review → roundup → buyer_guide
 *
 * @param {string|null|undefined} keyword
 * @returns {'buyer_guide'|'roundup'|'comparison'|'review'}
 */
export function classifyKeyword(keyword) {
  if (!keyword) return 'buyer_guide'
  const kw = keyword.toLowerCase().trim()

  if (/\bvs\.?\b|\bversus\b|\bcompar(ed|ison)\b/.test(kw)) return 'comparison'
  if (/\breview\b|\bhands[- ]?on\b|\btested?\b/.test(kw)) return 'review'
  if (
    /^best\b.+\bfor\b/.test(kw) ||
    /^best\b.+\bunder\b/.test(kw) ||
    /^top\s+\d+\b/.test(kw)
  ) return 'roundup'
  if (
    /^best\b/.test(kw) ||
    /\bbuying[\s-]guide\b/.test(kw) ||
    /\bguide\b/.test(kw) ||
    /\bhow\s+to\s+(choose|pick|select)\b/.test(kw)
  ) return 'buyer_guide'

  return 'buyer_guide'
}
