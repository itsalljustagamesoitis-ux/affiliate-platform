# Furniture Page Template Families

Furniture pages are the static, non-article pages every site ships with:
`about`, `disclaimer`, `affiliate-disclosure`, `privacy-policy`, `terms`, `contact`, `how-we-research`.

Each template family is a set of Astro source files pre-authored for a specific vertical type.
Phase 2 scaffolding copies the appropriate family into the new site's `src/pages/`.

---

## Available families

### `lifestyle/`
Non-YMYL editorial sites. Examples: Ten27 (e-bikes), Northwoods (overlanding), sauna.

- Standard affiliate disclosure
- Research-based editorial framing (no medical/financial advice disclaimers)
- Sourced-framing methodology (no false testing claims)

Source: extracted from Ten27 post-remediation (2026-05-20). Cleaned for persona-claim violations.

### `ymyl/`
YMYL editorial sites (medical, health-adjacent, financial decisions). Examples: BetterHearingHub.

All `lifestyle/` features plus:
- Explicit medical advice disclaimer in `disclaimer.astro` and `about.astro`
- YMYL-specific methodology statement in `how-we-research.astro` (sourced framing, OTC vs prescription distinction)
- Health data privacy note in `privacy-policy.astro`
- Liability limitation in `terms.astro`
- AAA referral in `contact.astro`
- Meta description without "tested" language

---

## Usage in Phase 2

```bash
# Declare in site.config.yaml:
#   furniture_template_family: ymyl   (or: lifestyle)

# Phase 2 scaffolding:
FAMILY=$(grep furniture_template_family site.config.yaml | awk '{print $2}')
cp affiliate-platform/templates/furniture/$FAMILY/*.astro src/pages/
```

After copying, run:
```bash
node affiliate-platform/scripts/validate-furniture-pages.mjs --site <slug>
```
Pages must pass before Phase 2 closes.

---

## Adding a new family

1. Create `templates/furniture/<family-name>/` with the 6 standard pages
2. Test against the furniture validator: `node scripts/validate-furniture-pages.mjs --site <test-site>`
3. Document it in this README
4. Add `furniture_template_family: <family-name>` to the example site.config.yaml

---

## Validator

`affiliate-platform/scripts/validate-furniture-pages.mjs` checks furniture pages for:
- HARD persona-claim violations (FTC risk)
- Previous-vertical vocabulary bleed (configured in `config/furniture-validation.yaml`)

Run at Phase 2 close and Phase 5 UAT gate.
