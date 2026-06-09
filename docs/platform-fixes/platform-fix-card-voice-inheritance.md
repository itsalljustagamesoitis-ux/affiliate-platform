# Platform Fix: Buyer-Guide Card Voice Inheritance

**Type:** Producer / prompt fix  
**Severity if missed:** SEV-2 (generic third-person copy instead of persona voice in product cards)  
**First surfaced:** Site 15 (rmflyfishing) Phase 4 UAT — product cards in 10+ buyer guides used depersonalized "Greg uses X" construction instead of first-person voice  
**Status:** Backlog — partially addressed by manual fixes; structural fix not yet implemented

---

## Problem

The buyer guide article generator writes article body prose in the persona's first-person voice. But the `article_specific_pros` and `article_specific_cons` fields in the `products:` frontmatter block — which populate the ProductCard component's pros/cons section — are sometimes generated in third-person ("Greg has used this rod for two seasons") rather than first-person ("I've had this rod for two seasons").

The mismatch is jarring: the article body says "I" but the product card 10 lines down says "Greg." Readers notice the voice inconsistency, and it signals that the cards were auto-generated without editorial review.

## Root Cause

The article generator prompt for `article_specific_pros` and `article_specific_cons` does not explicitly instruct the model to use first-person voice. The model defaults to whatever emerges from context. When context includes the persona's name prominently in the system prompt, the model sometimes drifts to third-person reference.

The article body prompt explicitly says "write in first person as Greg" but the frontmatter block generation — which happens in the same pass or in a separate structured generation — may not inherit that instruction explicitly.

## Current State

Site 15 editorial fix: the most egregious instances in buyer guide articles were manually corrected during Phase 4. The underlying prompt is not yet updated to enforce first-person voice in frontmatter fields.

## Fix

### 1. Prompt update for `article_specific_pros` / `article_specific_cons`

In `prompts/article-buyer-guide.v1.md`, add explicit instruction to the frontmatter generation section:

```
For article_specific_pros and article_specific_cons:
- Write in FIRST PERSON as {persona_name}. Use "I", "my", "I've tested", "I've found."
- NEVER use the persona's name in third person in these fields ("Greg has..." → "I've...")
- These fields appear directly in product cards — voice consistency with the article body is required.
```

### 2. Validation check

In `scripts/preflight.py` or `producer/tests/`, add a check for third-person persona name in frontmatter pros/cons:

```python
persona_name = persona['name_used']  # e.g. "Greg"
for product_ref in article['products']:
    for pro in product_ref.get('article_specific_pros', []):
        if f"{persona_name} has" in pro or f"{persona_name}'s" in pro:
            warnings.append(f"Third-person voice in pro: {pro}")
    for con in product_ref.get('article_specific_cons', []):
        if f"{persona_name} has" in con or f"{persona_name}'s" in con:
            warnings.append(f"Third-person voice in con: {con}")
```

### 3. Post-generation review step

Add to the 5-article UAT batch review checklist:
- Open each article's product card section and confirm pros/cons use "I" not the persona name in third person.

## Done Criteria

- `prompts/article-buyer-guide.v1.md` updated with explicit first-person instruction for frontmatter fields
- `--count 5` batch run and all five files reviewed for voice consistency in product card pros/cons
- `producer/tests/` updated to flag third-person persona voice in pros/cons fields

## Related

- `platform-fix-apostrophe-escape.md` — another frontmatter field generation defect
