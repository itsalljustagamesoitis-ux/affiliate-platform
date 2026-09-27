import { defineCollection, z } from 'astro:content'
import { glob } from 'astro/loaders'

// ── Shared sub-schemas ────────────────────────────────────────────────────────

const ProductRefSchema = z.object({
  id: z.string(),
  role: z.enum([
    'best_overall', 'best_value', 'best_budget', 'best_premium',
    'best_for_beginners', 'best_for_professionals', 'honorable_mention',
    'also_consider', 'primary', 'alternative',
  ]).optional(),
  article_specific_pros: z.array(z.string()).optional(),
  article_specific_cons: z.array(z.string()).optional(),
})

// ── Articles collection ───────────────────────────────────────────────────────

const ArticleSchema = z.object({
  title: z.string(),
  slug: z.string(),
  type: z.enum(['roundup', 'review', 'comparison', 'buyer_guide', 'informational']),
  date: z.date(),
  updated: z.date().optional(),
  author: z.string().default('{{PERSONA_SLUG}}'),
  category: z.string(),
  hub: z.string(),
  hero_image: z.string(),
  hero_image_alt: z.string().optional(),
  description: z.string().max(200),
  target_keyword: z.string(),
  // Head-term / spoke structure (Fix 1 / Fix 4). role and parent_head are optional
  // so existing content without this structure keeps validating; build-validator.mjs
  // enforces the head-term/orphan rules once a site opts in by setting these fields.
  role: z.enum(['HEAD', 'spoke']).optional(),
  parent_head: z.string().optional(),
  // Editorial axis a spoke covers relative to its HEAD (e.g. "price" —
  // exempts it from price-word stripping in the keyword-variant collision
  // check; see build-validator.mjs semanticSignature()). Open string, not an
  // enum, since axes are additive as new ones come up (size, material, etc.).
  axis: z.string().optional(),
  products: z.array(ProductRefSchema).default([]),
  tags: z.array(z.string()).default([]),
  rating: z.number().min(1).max(5).optional(),
  disclosure_required: z.boolean().default(true),
  noindex: z.boolean().default(false),
  // Comparison-type only
  product_a: z.string().optional(),
  product_b: z.string().optional(),
  winner: z.enum(['product_a', 'product_b']).optional(),
  winner_reason: z.string().optional(),
})

// ── Collections ───────────────────────────────────────────────────────────────

export const collections = {
  articles: defineCollection({
    loader: glob({ pattern: '**/*.md', base: './content/articles' }),
    schema: ArticleSchema,
  }),
}
