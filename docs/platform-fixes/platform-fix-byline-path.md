# Platform Fix: Persona Byline Image Path

**Type:** Template / configuration fix  
**Severity if missed:** SEV-2 (broken persona photos site-wide)  
**First surfaced:** Third consecutive site to exhibit this bug (Sites 13, 14, 15)  
**Status:** Fixed on Site 15 — root cause not yet addressed at platform level

---

## Problem

Persona photo paths in `config/personas/*.yaml` are set as relative paths (`images/brand/persona-byline.jpg`) rather than root-absolute paths (`/images/brand/persona-byline.jpg`). When the `Byline.astro` and `AuthorBio.astro` components render `<img src={persona.photo_byline}>`, a relative path resolves correctly at the root (`/`) but 404s on any article page (e.g., `/best-fly-rod/`) because the browser resolves it relative to the current URL path.

This has now occurred on three consecutive site launches. The pattern is consistent: new site spun up, persona YAML written, photos upload, byline photo 404s on article pages, fix applied manually.

## Where It Happens

```yaml
# config/personas/greg.yaml (broken)
photo_about: images/brand/persona-about.jpg
photo_byline: images/brand/persona-byline.jpg

# config/personas/greg.yaml (correct)
photo_about: /images/brand/persona-about.jpg
photo_byline: /images/brand/persona-byline.jpg
```

The missing leading `/` is the entire bug.

## Fix

Add leading `/` to all persona photo paths:

```bash
# One-liner fix for any site
sed -i '' 's|photo_about: images/|photo_about: /images/|g' config/personas/*.yaml
sed -i '' 's|photo_byline: images/|photo_byline: /images/|g' config/personas/*.yaml
```

## Permanent Fix (platform-level)

**Option A — Normalize in the component:** In `Byline.astro` and `AuthorBio.astro`, prefix the path with `/` if it doesn't already start with one:

```astro
---
const photoSrc = persona.photo_byline?.startsWith('/') ? persona.photo_byline : `/${persona.photo_byline}`
---
<img src={photoSrc} ... />
```

This is defensive but hides a misconfiguration rather than preventing it.

**Option B — Validate in the schema:** In `config/personas` schema validation (wherever that runs), assert that photo paths start with `/`:

```python
if not persona['photo_byline'].startswith('/'):
    raise ValueError(f"photo_byline must be root-absolute (start with /): {persona['photo_byline']}")
```

**Option C — New site runbook enforcement:** Add to the new-site spin-up checklist:
- `[ ] Persona photo paths start with `/` (root-absolute)`

Option A is the most reliable because it catches existing sites and doesn't require schema changes.

## New-Site Runbook Entry

Add to new-site spin-up checklist:

```
- [ ] config/personas/*.yaml photo_about and photo_byline paths start with /
      Check: grep -E "^photo_(about|byline): [^/]" config/personas/*.yaml  → must return empty
```

## Related

- Recurred on Sites 13, 14, 15 consecutively — persistent failure mode in new site spin-up
