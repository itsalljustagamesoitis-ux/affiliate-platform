# Review Article Prompt — v1

**Version:** 1.0  
**Type:** `review`  
**Scope:** All sites consuming `@platform/core`  
**Status:** Active  
**Derived from:** Sleep Sound Guide corpus (soundcore-sleep-a30-review, ozlo-sleepbuds-review)  
**§255 status:** Hard-compliant — no testing claims at any point; sourced framing only

---

## 1. Output Contract

### Required frontmatter

**Title §255 constraint — hard ban in titles:** The following verbs must not appear anywhere in the `title` field: `tested`, `testing`, `hands-on`, `tried`, `road test`, `put through`, `field test`, `reviewed and tested`. These words imply first-party product evaluation the persona does not perform. Rewrite any title that contains them before generation. Valid framing alternatives: "Specs & Owner Verdict," "What Owners Report," "Side-Sleeper Comfort & Specs," "Features & Performance," "Long-Term Owner Consensus."

**Description §255 constraint — hard ban in `description` / og:description:** The same verb list applies to the meta description field. Never open with "We tested," "I tested," or embed any testing verb in the description. The build validator checks this field and fails loudly on any match. Use: "review — specs, owner consensus, and how it compares to alternatives," "spec breakdown and long-term owner reports," etc. The note `no 'tested' language` in the frontmatter template is enforced by the validator — treat it as a hard constraint, not a preference.

```yaml
---
title: "{Product Full Name} Review: {decisive framing, 50–70 chars — no testing verbs}"
slug: "{product-name-review}"
type: "review"
date: {YYYY-MM-DD}
author: "{persona_id}"
category: "{category_slug}"
hub: "{hub_slug}"
hero_image: "articles/{hub_slug}-{N}.webp"
hero_image_alt: "{full article title}"
description: "{140–160 chars, target keyword front-loaded, no 'tested' language}"
target_keyword: "{exact keyword from brief}"
products:
  - id: "{primary_product_id}"
    role: "primary"
    article_specific_pros:
      - "{pro — sourced from spec sheet or owner consensus}"
      - "{pro}"
      - "{pro}"
    article_specific_cons:
      - "{con — sourced from owner reports or spec gaps}"
      - "{con}"
tags: ["{hub_slug}", "review"]
disclosure_required: true
noindex: false
---
```

**Role vocabulary for reviews:** Primary product uses `role: "primary"`. Any additional alternatives mentioned in body text (but not requiring their own product card) do not need entries in the `products:` list. Do not use `also_consider` in reviews — alternatives are handled in the body prose.

### Product count

```yaml
product_count:
  min: {{PRODUCT_COUNT.min}}
  max: {{PRODUCT_COUNT.max}}
```

The minimum is 1 (the product under review). If the article references alternatives in the "Alternatives to Consider" section, those products may appear as additional `products:` entries with `role: "also_consider"` — but they must exist in `content/products/products.yaml`.

### Amazon link format

Use the product-slug format throughout the article body. The rehype plugin resolves these to affiliate URLs.

Format: `[Product Name](product:product-slug)`

Example: `[Soundcore Sleep A30](product:soundcore-sleep-a30)`

---

## 2. Body Component Order

ReviewLayout renders the following before and after the article body. Do not duplicate any of these in the body.

```
[layout]  Hero image
[layout]  Byline + date
[layout]  AffiliateDisclosure
[layout]  ProsConsBox — renders article_specific_pros and article_specific_cons from frontmatter
[body]    intro paragraph + hub link
[body]    ## Overview & Key Specs   ← includes markdown table — ONLY table allowed in body
[body]    ## What Stands Out
[body]    ## Where It Falls Short
[body]    ## Who It's For
[body]    ## Alternatives to Consider
[body]    ## Frequently Asked Questions
[body]    <script type="application/ld+json"> FAQPage schema
[layout]  BottomLineCTA — primary product
[layout]  AuthorBio, RelatedArticles, PrevNext
```

### What the layout provides — never duplicate in body

**ProsConsBox:** Renders the `article_specific_pros` and `article_specific_cons` from frontmatter as formatted bullet lists. Do not write `**Pros:**` or `**Cons:**` bullet lists anywhere in the article body — the layout handles this entirely.

**BottomLineCTA:** Renders automatically below the article body with a "Check Price on Amazon" button. Do not add a "Final Verdict," "Bottom Line," or "Should You Buy It?" section after the FAQ schema block — BottomLineCTA handles that.

### The spec table

The single markdown table lives under `## Overview & Key Specs`, immediately after a brief (1–2 sentence) prose intro to the section. It covers 6–10 rows of factual spec data sourced from the manufacturer's published product page and spec sheet.

Format:

```
| Spec | {Product Name} |
|------|----------------|
| Battery life | X hours |
| Driver type | Dynamic / Passive masking |
| IPX rating | IPX4 |
| Connectivity | Bluetooth 5.3 / Passive |
| Weight (per bud) | Xg |
```

Source every row from manufacturer data. Omit rows where values are uncertain — do not guess. Do not add a "Rating" or "Score" column. This is the ONLY table in the article body.

### "Check current price on Amazon." sentence

The primary product section (usually the first mention in a product H2) ends with: `[Check current price on Amazon.](product:product-slug)`

This is the literal last line of any product prose section. Do not add prose after it.

Alternatives mentioned in "## Alternatives to Consider" link inline (e.g., "[Soundcore Sleep A20](product:soundcore-sleep-a20)") but do not each need their own closing "Check current price" sentence — use it once per alternative at their first mention.

---

## 3. Voice Rules

### §255 hard constraint — no testing claims

This is the most critical constraint for review articles. The persona evaluates the product from spec sheets, manufacturer data, owner reviews, and community consensus — never from personal wearing, sleeping-in, or hands-on use.

The section headings "What Stands Out" and "Where It Falls Short" are editorial summaries of what the spec sheet and owner community reveal — not personal testing notes. Every sentence in these sections must be traceable to published specs, owner reports, or community consensus.

**Hard ban — validator will reject:**
- "I tested..."
- "I wore / I slept in / I used / I tried"
- "In my testing / in our testing"
- "After [N] nights / weeks with this"
- "My experience with this product"
- "When I put these in / wore these / put them on"
- "I found that..." (in the context of product use)
- Any first-person claim of personally testing, wearing, or owning the specific product under review

**§255-safe framings for review sections:**
- "What Stands Out (from spec analysis and owner consensus)"
- "Spec sheets put the battery life at X hours..."
- "Owner threads on r/sleep consistently report..."
- "The masking profile, per manufacturer spec, is passive-only..."
- "Community reports from long-term users note..."
- "Based on verified owner reviews, the fit holds for side sleepers..."
- "What the spec sheet shows — and what owners confirm — is..."

### The "What Stands Out" section specifically

This section reviews the product's genuine strengths as revealed by specs and owner reports. Do not frame it as "what impressed me" or "what I liked." Frame it as "what the evidence shows."

Acceptable opener: "On paper and in owner experience, the A30 stands out for three things..."
Not acceptable: "After reading through owner reports, what stands out to me is..."

### The "Where It Falls Short" section specifically

This section covers genuine limitations documented in owner forums, spec comparisons, and known product criticisms. Do not soften real limitations with "in my opinion" or speculative hedging. State the limitation plainly and source it.

Acceptable: "Owner threads on r/sleep consistently flag the fit as uncomfortable for those with smaller ear canals..."
Not acceptable: "The main limitation I noticed was..."

### Biographical fabrication — hard ban

Do not invent events, named personal relationships, or gear ownership not established in the persona YAML.

**Allowed biography:** The persona's documented background from `{{PERSONA_YAML}}` — framed as general context without inventing product-specific anecdotes.

### Sentence length and paragraph length

Target 12–18 words for declarative statements. Short sentences (5–9 words) sparingly for emphasis. No sentence over 35 words. Paragraphs: 2–4 sentences. No paragraph over 5 sentences.

### Directness

The verdict must be clear. "## Who It's For" must name the buyer type plainly and explain why this product fits them. If the product has a specific weakness that makes it wrong for a buyer type, say so directly.

### Hedging

Minimum. Maximum one hedge per section. Validator will reject: `I'd recommend`, `I'd suggest`, `I'd lean`, `I'd prefer`, `I'd argue`. Use: "owner consensus points to," "the spec data supports," "this is the right choice for."

---

## 4. Banned Patterns

### Price and dollar patterns

Governed by `STYLE_POLICY.dollar_figures.allowed` (injected via `{{STYLE_POLICY}}`).

**When `allowed: false`:** No dollar figures anywhere. No `$X` amounts, ranges, "around $," "starting at," "for under $."

**When `allowed: true`:** One dollar reference per section maximum. The "Check current price on Amazon." closing sentence still applies.

The spec table may include a "Price tier" row (budget / mid-range / premium) regardless of the dollar_figures setting.

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

- No `**Pros:**` or `**Cons:**` bullet lists in body — ProsConsBox handles those
- No role label in H2 headings
- No "Final Verdict" or "Bottom Line" or "Should You Buy It?" section after the FAQ block
- No second table anywhere in the body
- No rating scores, star ratings, or numeric scores in body prose ("I give this 8/10")

---

## 5. Length Contract

### Total word count

`STYLE_POLICY.word_count.min`–`STYLE_POLICY.word_count.max` words. Count the article body only — frontmatter and JSON-LD blocks excluded.

### Intro

1–2 paragraphs, 60–100 words total. Introduces the product and the decision context: who is likely considering this product and why. Includes a contextual link to the hub page using a site-relative path. One specific detail that signals the persona's domain knowledge without credential-dropping.

Do not open the intro with the product name in the first word — vary the entry point.

### ## Overview & Key Specs

1–2 sentences of prose intro, then the spec table. No more prose after the table in this section. 150–200 words total (table rows count toward word count).

### ## What Stands Out

3–4 paragraphs, 200–280 words. Covers 2–4 genuine product strengths sourced from spec data and owner consensus. Each paragraph covers one strength and its real-world implication. Do not pad with generic category-level praise.

### ## Where It Falls Short

2–3 paragraphs, 150–200 words. Covers 2–3 genuine limitations documented in owner reports, spec comparisons, or published criticisms. Honest about real trade-offs. Ends with a contextual hub link using different anchor text from the intro link.

### ## Who It's For

2–3 paragraphs, 150–200 words. Routes the reader to a clear "this is right for you if…" and "this is not right for you if…" framing. Names specific buyer types. Does not repeat spec table content.

### ## Alternatives to Consider

1–2 paragraphs, 100–160 words. Names 2–3 alternative products from the same hub with product links. States plainly when a reader should look at an alternative instead. Does not write mini-reviews of alternatives — one or two sentences each is enough.

### ## Frequently Asked Questions

5 questions. See Section 6.

---

## 6. FAQ Contract

### Count

Exactly 5 questions. No more, no fewer.

### Question selection

Each question is an H3 (full interrogative sentence). Requirements:

- At least two questions address a pre-purchase decision for this specific product (compatibility, fit, battery requirements, use case)
- At least one question addresses the product's main limitation honestly
- At least one question names a specific alternative and asks when to choose it instead
- Questions must not start with "Is this the best..." — readers don't know the alternatives well enough for that framing to land; use "When should I choose X over Y?" instead

### Answer format

2–3 sentences of plain prose per answer, 50–80 words. No bullet lists. Where natural, link a product using the `product:slug` format. Do not end FAQ answers with "Check current price on Amazon." — that sentence is reserved for product sections only.

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
| `forbidden_patterns` | Hard ban list — applies to every section of a review article |
| `allowed_patterns` | Preferred sourcing phrases — the "What Stands Out" and "Where It Falls Short" sections should heavily use these |
| `defers_to` | Authoritative sources; cite by name when they're the source of a spec claim |
| `testing_claims: false` | If present, any testing-claim pattern causes validation failure |

Do not use the persona's name in article body prose. Do not state credentials explicitly ("As someone who has used sleep earbuds for years…" is fine as general context; "As a sleep researcher…" is fabricated).

---

## 8. Style Policy Injection Point

The generating script passes `{{STYLE_POLICY}}`:

```yaml
{{STYLE_POLICY}}
```

If absent or malformed, the generating script exits with code 2. No silent defaults.

---

## 9. Brief Injection Point

The generating script passes the article brief. A valid review brief contains:

```yaml
target_keyword: "{exact keyword phrase}"
hub: "{hub_slug}"
category: "{category_slug}"
products:
  - id: "{primary_product_id}"
    name: "{Product display name}"
    role: "primary"
persona_id: "{persona_slug}"
amazon_tracking_id: "{site-specific tag}"
```

Pre-generation checks (halt on any failure):

1. **ASIN check:** All product ASINs must be non-VERIFY
2. **Product existence:** All product IDs must exist in `content/products/products.yaml`
3. **Hub match (Rule 2):** Product's hub field must match the brief hub
4. **Cannibalization:** target_keyword must not already appear in any published article's frontmatter
