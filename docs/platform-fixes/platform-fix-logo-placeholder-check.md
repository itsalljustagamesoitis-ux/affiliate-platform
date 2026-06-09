# Platform Fix: Logo Placeholder Check

**Type:** Pre-promotion gate  
**Severity if missed:** SEV-1 (brand-breaking on live site)  
**First surfaced:** Site 15 (rmflyfishing) Phase 4 UAT  
**Status:** Backlog — not yet implemented

---

## Problem

SVG logo files can ship to production with unfilled template placeholders (`{{BRAND_NAME}}`, `{{SITE_TAGLINE}}`, etc.) when a new site's brand assets are generated from templates but the substitution step is missed or partial. The build succeeds because the SVG is syntactically valid. The validator passes because it checks structure, not brand identity. The live site shows a literal `{{BRAND_NAME}}` text as its logo.

This is editorially indistinguishable from a blank logo — a visitor seeing `{{BRAND_NAME}}` in the header nav understands immediately that the site is broken.

## Where It Happens

Any file in `public/` that originates from a template:

- `public/images/brand/logo.svg`
- `public/images/brand/logo-dark.svg`
- `public/images/brand/favicon.svg`
- Any other SVG referencing site identity fields

The affected text renders as-is in the browser because SVG `<text>` elements containing `{{...}}` are valid XML.

## Detection Check

Pre-promotion gate (runs before any production deploy from a new site):

```bash
# Fail if any brand asset contains an unfilled placeholder
grep -rE '\{\{[A-Z_]+\}\}' public/images/brand/ && echo "FAIL: placeholder found" && exit 1 || echo "PASS: no placeholders"
```

Also check the built dist:

```bash
grep -rE '\{\{[A-Z_]+\}\}' dist/ && echo "FAIL: placeholder in dist" && exit 1 || echo "PASS"
```

## Fix

Replace placeholder strings in the SVG with the actual site brand values from `site.config.yaml`:

```bash
BRAND=$(python3 -c "import yaml; print(yaml.safe_load(open('site.config.yaml'))['site']['brand_name'])")
sed -i '' "s/{{BRAND_NAME}}/$BRAND/g" public/images/brand/logo.svg
```

Or regenerate brand assets from the spin-up checklist (`npm run brand:generate` once that tooling exists).

## Permanent Fix

Add to `build-validator.mjs` as a FAIL check:

```javascript
const brandAssets = glob.sync('dist/**/*.svg')
for (const file of brandAssets) {
  const content = fs.readFileSync(file, 'utf8')
  if (/\{\{[A-Z_]+\}\}/.test(content)) {
    results.push({ level: 'FAIL', check: 'logo-placeholder', file })
  }
}
```

This fires at build time, before deploy, and blocks the deploy pipeline.

## Related

- `platform-fix-empty-content-validator.md` — same class of validator gap (structure valid, content broken)
