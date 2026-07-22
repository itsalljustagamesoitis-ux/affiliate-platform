# Comparison Article Prompt — v1

**Version:** 1.0  
**Type:** `comparison`  
**Scope:** All sites consuming `@platform/core`  
**Status:** Active  
**Derived from:** Sleep Sound Guide corpus (soundcore-sleep-a20-vs-a30, ozlo-sleepbuds-vs-soundcore)  
**§255 status:** Hard-compliant — no testing claims at any point; sourced framing only

---

## 1. Output Contract

### Required frontmatter

**Title §255 constraint — hard ban in titles:** The following verbs must not appear in the `title` field: `tested`, `testing`, `hands-on`, `tried`, `road test`, `put through`, `field test`. Use "Which to Buy," "Spec Comparison," "Side-by-Side," or keyword-native phrasing instead.

**Description §255 constraint — hard ban in `description` / og:description:** The same verb list applies to the meta description. Never use "We tested," "I tested," "we compared by testing," or any testing verb in the description field. The build validator checks this field and fails loudly on any match. Use: "spec comparison and owner-consensus picks," "side-by-side spec and owner-report breakdown," etc.

```yaml
---
title: "{Product A} vs {Product B}: {decisive framing, 50–70 chars, no testing verbs}"
slug: "{product-a-vs-product-b}"
type: "comparison"
date: {YYYY-MM-DD}
author: "{persona_id}"
category: "{category_slug}"
hub: "{hub_slug}"
hero_image: "articles/{hub_slug}-{N}.webp"
hero_image_alt: "{full article title}"
description: "{140–160 chars, target keyword front-loaded, no 'tested' language}"
target_keyword: "{exact keyword from brief}"
products:
  - id: "{product_a_id}"
    role: "primary"
    article_specific_pros:
      - "{pro — sourced from spec sheet or owner consensus}"
      - "{pro}"
    article_specific_cons:
      - "{con — sourced from owner reports or spec gaps}"
      - "{con}"
  - id: "{product_b_id}"
    role: "alternative"
    article_specific_pros:
      - "{pro}"
      - "{pro}"
    article_specific_cons:
      - "{con}"
      - "{con}"
tags: ["{hub_slug}", "comparison"]
disclosure_required: true
noindex: false
product_a: "{product_a_id}"
product_b: "{product_b_id}"
# winner: product_a  # SET THIS after review — uncomment and set to product_a or product_b
# winner_reason: ""  # SET THIS — one plain sentence, e.g. "Better masking profile and longer battery life"
---
```

**`product_a` and `product_b` are required.** They must match the first and second entries in the `products:` list. The `winner` and `winner_reason` fields are commented out in the generated draft — a human reviewer sets them after reading the article. Until they are set, the verdict box in ComparisonLayout will not render.

**Role vocabulary for comparisons:** First product uses `primary`, second uses `alternative`. Do not use best_overall, best_value, etc. — those are roundup roles.

### Product count

```yaml
product_count:
  min: {{PRODUCT_COUNT.min}}
  max: {{PRODUCT_COUNT.max}}
```

The minimum for a head-to-head comparison is 2. Additional products (up to {{PRODUCT_COUNT.max}}) may appear in the "Alternatives to Consider" subsection of the body — referenced by name and product link but without their own top-level H2 section.

### Amazon link format

Use the product-slug format throughout the article body. The rehype plugin resolves these to affiliate URLs.

Format: `[Product Name](product:product-slug)`

Example: `[Soundcore Sleep A20](product:soundcore-sleep-a20)`

---

## 2. Body Component Order

ComparisonLayout renders the following before and after the article body. Do not duplicate any of these in the body.

```
[layout]  Verdict box — renders only if frontmatter winner field is set
[layout]  Comparison hero — Product A card | VS | Product B card (images, names, price buttons)
[body]    intro paragraph + hub link
[body]    ## Quick Verdict
[body]    ## Specs at a Glance   ← markdown table — this is the ONLY place a table is allowed
[body]    ## {Product A Full Name} — Strengths and Trade-offs
[body]    ## {Product B Full Name} — Strengths and Trade-offs
[body]    ## Which Should You Pick
[body]    ## Frequently Asked Questions
[body]    <script type="application/ld+json"> FAQPage schema
[layout]  BottomLineCTA — winner product (or product_a if winner not set)
[layout]  AuthorBio, RelatedArticles, PrevNext
```

### What the layout provides — never duplicate in body

**Comparison hero:** Renders Product A and Product B side-by-side with images, names, and "Check Price" buttons. Do not write a "Product A vs Product B at a Glance" prose header, an equivalency table of winner/loser, or any visual mimicry of the hero in text.

**Verdict box:** Renders the winner name, winner_reason text, and a "Check Price" button — but only if `winner` is uncommented in frontmatter. The body's "## Quick Verdict" section provides the prose reasoning that the layout cannot; it is not a duplicate of the verdict box.

**BottomLineCTA:** Renders automatically below the article body. Do not add a "Final Verdict" section or any closing CTA prose after the FAQ schema block.

### The spec table

The single markdown table lives under `## Specs at a Glance`. It compares the two products on 6–10 rows of factual spec data, sourced from manufacturer spec sheets and published product pages. Format:

```
| Spec | {Product A} | {Product B} |
|------|-------------|-------------|
| Battery life | X hours | Y hours |
| Driver size | Xmm | Ymm |
| IPX rating | IPX4 | IPX5 |
```

Source every row from manufacturer data. Do not include rows where you are uncertain of the value — omit rather than guess. Do not add a "Winner" column — the prose sections handle that. This is the ONLY table in the article body.

### Product H2 sections

Each product gets one H2: `## {Full Product Name} — Strengths and Trade-offs`

Under that H2, 3–4 paragraphs of prose covering:
- The product's genuine strengths (spec-sourced or owner-consensus-sourced)
- Its real limitations relative to the other product and its price tier
- Who this product is best suited for and why

End each product H2 section with: `[Check current price on Amazon.](product:product-slug)`

This is the literal last line — no prose, no sentences after it.

---

## 3. Voice Rules

### §255 hard constraint — no testing claims

This constraint is non-negotiable across all article types. The persona evaluates products from spec sheets, manufacturer data, owner reviews, and community consensus — never from personal testing or ownership.

**Hard ban — validator will reject:**
- "I tested..."
- "I wore / I slept in / I used / I tried"
- "In my testing / in our testing"
- "After [N] nights / weeks with this"
- "My experience with this product"
- "When I put these in / wore these / tried these"
- Any first-person claim of personally testing, wearing, or owning the specific product under review

**§255-safe framings for comparison articles:**
- "Spec sheets show the A30 delivering a longer claimed battery life..."
- "Owner threads on r/sleep consistently note that..."
- "Community consensus from long-term users points to..."
- "The masking profile on paper is more aggressive on the A20..."
- "Reported fit issues in owner forums suggest..."
- "Manufacturer data puts the noise-floor at..."

### Biographical fabrication — hard ban

Do not invent events, named personal relationships, or gear ownership not established in the persona YAML.

**Allowed biography:** The persona's documented background and experience from `{{PERSONA_YAML}}` — framed as general context ("years relying on sleep audio," "working through the toolkit") never as specific product-testing anecdotes.

### Sentence length and paragraph length

Vary sentence length. Target 12–18 words for declarative statements. Short sentences (5–9 words) used sparingly for emphasis, maximum two in sequence. No sentence over 35 words.

Paragraphs: 2–4 sentences. No paragraph over 5 sentences.

### Directness

State the verdict plainly and early. "## Quick Verdict" must open with a clear recommendation — not "it depends." Frame the nuance after declaring the winner, not instead of declaring one.

### Hedging

Minimize. Maximum one hedge per product section. Acceptable: "on paper," "owner reports suggest," "the spec data points to." Not acceptable: "I think," "I believe," "it seems," "perhaps," "arguably."

Validator will reject: `I'd recommend`, `I'd suggest`, `I'd lean`, `I'd prefer`, `I'd argue`, `I'd move`. Use: "the stronger choice is," "owner consensus favors," "the evidence points to."

---

## 4. Banned Patterns

### Price and dollar patterns

Governed by `STYLE_POLICY.dollar_figures.allowed` (injected via `{{STYLE_POLICY}}`).

**When `allowed: false`:** No dollar figures anywhere. No `$X` amounts, ranges, "around $," "starting at," "for under $," "at the $X price point."

**When `allowed: true`:** One dollar reference per product section maximum, used to anchor a decision. The "Check current price on Amazon." closing sentence still applies.

The spec table may include a "Price tier" row (budget / mid-range / premium) — not a dollar amount — regardless of the dollar_figures setting.

### AI-tell phrases — hard ban

- "in today's world"
- "when it comes to"
- "look no further"
- "let's dive in"
- "the perfect"
- "game-changer" / "game changer"
- "elevate your"
- "navigate the world of"
- "in this article" / "in this guide"
- "without further ado"

### Structural bans

- No `**Pros:**` or `**Cons:**` bullet lists in body — ProductCard handles those
- No role label in product H2 headings ("Best Overall: …")
- No bold role subtitle below product H2s
- No "Final Verdict" section after the FAQ block — BottomLineCTA handles that
- No second table anywhere in the body

---

## 5. Length Contract

### Total word count

`STYLE_POLICY.word_count.min`–`STYLE_POLICY.word_count.max` words. Count the article body only — frontmatter and JSON-LD blocks excluded.

### Intro

1–2 paragraphs, 60–100 words total. Establishes the decision the reader faces. Includes a contextual link to the hub page using a site-relative path (e.g., `[Sleepbuds](/sleepbuds/)`). One specific detail that signals the persona's domain knowledge without credential-dropping.

Do not open the intro with "So you're trying to decide between…" or any variant of that phrasing.

### ## Quick Verdict

2–3 paragraphs, 150–220 words. Opens with a plain declaration of the winner and the decisive reason. Paragraph 2 addresses the use case where the runner-up is actually the better choice. Paragraph 3 (optional) notes the most important shared characteristic so readers aren't choosing between two unknowns.

Do not open with "Both products are excellent." Name the winner in the first sentence.

### ## Specs at a Glance

Table only. No prose wrapper beyond the table. 6–10 rows. Immediately follows the H2.

### ## {Product Name} — Strengths and Trade-offs × 2

3–4 paragraphs per product section, 200–280 words each. End with "Check current price on Amazon." link. Do not open every product section with the product name in the first word — vary the entry point.

### ## Which Should You Pick

2–3 paragraphs, 150–200 words. Routes buyers to product A or B based on 2–3 distinct use cases. Does not repeat the spec table. Ends with a contextual hub link using different anchor text from the intro link.

### ## Frequently Asked Questions

5 questions. See Section 6.

---

## 6. FAQ Contract

### Count

Exactly 5 questions. No more, no fewer.

### Question selection

Each question is an H3 (full interrogative sentence). Requirements:

- At least two questions address a direct trade-off between the two specific products
- At least one question addresses a pre-purchase decision (compatibility, use case fit, wearing position, battery requirements)
- At least one question addresses the runner-up's best use case (so the article isn't one-sided)
- Questions must not duplicate the "Which Should You Pick" section verbatim

### Answer format

2–3 sentences of plain prose per answer, 50–80 words. No bullet lists. Where natural, name a specific product and link with the `product:slug` format. Do not end FAQ answers with "Check current price on Amazon." — that sentence is reserved for product sections only.

### Schema block

Immediately following the last FAQ answer, no intervening content:

```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "{exact H3 question text}",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "{exact answer prose text}"
      }
    }
  ]
}
</script>
```

`name` and `text` must exactly match rendered question and answer text. No truncation.

---

## 7. Persona Injection Point

The generating script passes `{{PERSONA_YAML}}` before generation. Fields used:

| Field | How it's used |
|-------|---------------|
| `background`, `voice_notes` | Governs register, sourcing framing, domain vocabulary |
| `forbidden_patterns` | Hard ban list — all patterns apply to this article type |
| `allowed_patterns` | Preferred sourcing phrases — use these rather than inventing new framings |
| `defers_to` | Authoritative sources to reference when citing specs or owner consensus |

The persona's `testing_claims: false` flag (if present) is an additional hard gate — if set, any testing-claim pattern in the body causes validation failure.

Do not use the persona's name in article body prose. Do not state credentials explicitly.

---

## 8. Style Policy Injection Point

The generating script passes `{{STYLE_POLICY}}`:

```yaml
{{STYLE_POLICY}}
```

If absent or malformed, the generating script exits with code 2. No silent defaults.

---

## 9. Brief Injection Point

The generating script passes the article brief. A valid comparison brief contains:

```yaml
target_keyword: "{exact keyword phrase}"
hub: "{hub_slug}"
category: "{category_slug}"
products:
  - id: "{product_a_id}"
    name: "{Product A display name}"
    role: "primary"
  - id: "{product_b_id}"
    name: "{Product B display name}"
    role: "alternative"
persona_id: "{persona_slug}"
amazon_tracking_id: "{site-specific tag}"
```

Pre-generation checks (halt on any failure):

1. **ASIN check:** All product ASINs must be non-VERIFY
2. **Product existence:** All product IDs must exist in `content/products/products.yaml`
3. **Hub match (Rule 2):** Each product's hub field must match the brief hub
4. **Cannibalization:** target_keyword must not already appear in any published article's frontmatter
