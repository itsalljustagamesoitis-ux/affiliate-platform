# Site Spec YAML — Reference

Consumed by `tools/initialise-site.mjs --spec <path>` (Point 7 of launch-site.mjs).

Each new site gets one spec file at `~/affiliate-platform/sites/<slug>.spec.yaml`.
Existing examples: `bear-creek-barbecue.spec.yaml`, `the-coffee-dispatch.spec.yaml`.

---

## Pre-conditions before running the orchestrator

Two things must exist before `launch-site.mjs --site <slug>` is invoked:

1. **Spec file** at `~/affiliate-platform/sites/<slug>.spec.yaml`
2. **Persona photos** at the exact paths listed in `persona.photo_source` and
   `persona.about_photo_source` — the spec validator calls `existsSync()` on these.
   Run `tools/generate-persona-photos.mjs --site <slug> --test-dir <tmp>` first,
   then move the approved photos to their target paths and update the spec.

---

## Full annotated example

```yaml
# ── Identity ────────────────────────────────────────────────────────────────

slug: smoke-and-coals                  # REQUIRED. /^[a-z][a-z0-9-]+$/
                                       # Must match site directory name and CF Pages project name.

domain: smokeandcoals.com              # REQUIRED. No https:// prefix. Must contain a dot.

brand_name: Smoke and Coals            # REQUIRED. Displayed in header, footer, OG tags.

tagline: "The equipment guide for backyard cooks who aren't afraid of smoke"
                                       # REQUIRED. Used in meta descriptions and OG tags.

niche: outdoor-cooking                 # REQUIRED. Must exactly match the key in
                                       # config/niche-palettes.yaml AND the DTC config file
                                       # config/dtc-brands/<niche>.yaml (if niche has DTC brands).
                                       # Do not abbreviate — e.g. 'outdoor-cooking' not 'cooking'.

description: "Outdoor cooking and barbecue equipment guides"
                                       # OPTIONAL. Defaults to niche value if omitted.
                                       # Used as site.description in site.config.yaml.

# ── Affiliate ────────────────────────────────────────────────────────────────

amazon_associates_id: smokeandcoals-20 # REQUIRED. Must end in -20.
                                       # Created by Keith in Amazon Associates dashboard.
                                       # Becomes AMAZON_TAG in Cloudflare Pages env.

# ── Analytics ────────────────────────────────────────────────────────────────

ga4_measurement_id: G-XXXXXXXXXX       # REQUIRED. Must start with G-.
                                       # Created by Keith in analytics.google.com.

# ── Persona ──────────────────────────────────────────────────────────────────

persona:
  slug: ryan                           # REQUIRED. Lowercase kebab. /^[a-z][a-z0-9-]*$/
                                       # Used for: persona YAML filename, photo filenames,
                                       # config/personas/<slug>.yaml, and URLs.

  display_name: Ryan Caldwell          # REQUIRED. Full name. First word used as name_used.

  bio: >-                              # REQUIRED. 1–3 sentence present-tense bio.
    Ryan Caldwell has been cooking with fire for twenty years. He's burned through
    three smokers, ruined a brisket or two along the way, and learned what actually
    matters when you're choosing equipment that has to work.

  bio_full: |                          # OPTIONAL. Longer version used in About page and
    Ryan Caldwell is a 47-year-old ...  # age extraction for photo prompts. If omitted,
                                       # falls back to bio. Include the persona's age here
                                       # in the format "NN-year-old" for correct photo prompts.

  location: Austin, Texas              # REQUIRED. Used in photo prompts and persona YAML.

  location_detail: "South Austin"      # OPTIONAL. More specific location for persona YAML.
                                       # Defaults to location if omitted.

  background: "Operations manager, manufacturing"
                                       # OPTIONAL but STRONGLY RECOMMENDED.
                                       # Written to persona.yaml background field.
                                       # Must be unique across all portfolio personas (Rule 1).
                                       # Check: grep -h "^background:" ~/*/config/personas/*.yaml | sort | uniq -d

  voice_notes: |                       # REQUIRED. Producer prompt injection. Be specific.
    Ryan writes from two decades of practical experience — close enough to remember
    the mistakes, experienced enough to know the difference between genuine quality
    and marketing. He doesn't assume readers are experts; he assumes they want to
    get it right without burning $400 on the wrong smoker.

  photo_source: /tmp/ryan-byline-approved.jpg
                                       # REQUIRED. ABSOLUTE PATH. File must exist at spec
                                       # validation time. Copied to public/images/brand/.
                                       # Generate with tools/generate-persona-photos.mjs.

  about_photo_source: /tmp/ryan-about-approved.jpg
                                       # REQUIRED. Same rules as photo_source.

# ── Visual identity ───────────────────────────────────────────────────────────

visual:
  primary_color: "#8B2500"             # REQUIRED. #RRGGBB hex. Main brand color.
                                       # Sourced from config/niche-palettes.yaml defaults;
                                       # override here for site-specific variation.

  accent_color: "#C4A265"              # REQUIRED. #RRGGBB hex. Secondary/highlight color.

  background_color: "#FAFAF7"          # REQUIRED. #RRGGBB hex. Page background.

  font_headings: "Lora"                # REQUIRED. Single font name or full CSS stack.
                                       # If single name, orchestrator appends fallback stack.

  font_body: "Source Serif 4"          # REQUIRED. Same rules as font_headings.

# ── Keyword source ───────────────────────────────────────────────────────────

keyword_source:
  xlsx_path: /Users/keithlacy/Desktop/smoke-and-coals-300.xlsx
                                       # OPTIONAL. Path to keyword XLSX for xlsx-to-pipeline.mjs.
                                       # Can also be passed via --xlsx flag at launch time.
                                       # Stored in spec for reproducibility.

# ── Infrastructure ────────────────────────────────────────────────────────────

dns_provider: cloudflare               # OPTIONAL. Defaults to cloudflare.
                                       # Only cloudflare is supported by cloudflare-pages-config.mjs.

github:                                # OPTIONAL. Only relevant for Sites 1-10 (git-push deploys).
  owner: itsalljustagamesoitis-ux      # Sites 11+: github is irrelevant; portfolio.yaml will have
  visibility: public                   # github_repo: null and deploy_pattern: direct_upload.

pre_launch: true                       # OPTIONAL. Set to true for sites not yet live.
                                       # portfolio.yaml status will be pre_launch until Point 16.

# ── Navigation ───────────────────────────────────────────────────────────────

categories:                            # REQUIRED. Non-empty array.
  - slug: smokers                      # REQUIRED. URL-safe slug.
    label: Smokers                     # REQUIRED. Display label.
    hubs:                              # REQUIRED. Non-empty array.
      - slug: offset-smokers
        label: Offset Smokers
        description: >-               # OPTIONAL but recommended (avoids hub-descriptions FAIL
          Research-based guides on    # in preflight). The validator treats missing hub
          offset smokers.             # descriptions as a FAIL pre-launch.

      - slug: pellet-grills
        label: Pellet Grills

  - slug: grills
    label: Grills
    hubs:
      - slug: charcoal-grills
        label: Charcoal Grills
      - slug: gas-grills
        label: Gas Grills

  - slug: accessories
    label: Accessories
    hubs:
      - slug: thermometers
        label: Thermometers
      - slug: wood-chips
        label: Wood & Pellets
```

---

## Field reference (quick lookup)

| Field | Required | Constraint |
|---|---|---|
| `slug` | yes | `/^[a-z][a-z0-9-]+$/` — no uppercase, no underscores |
| `domain` | yes | no `https://`, must contain `.` |
| `brand_name` | yes | non-empty string |
| `tagline` | yes | non-empty string |
| `niche` | yes | exact match to `config/niche-palettes.yaml` key and DTC filename |
| `description` | no | defaults to `niche` |
| `amazon_associates_id` | yes | must end in `-20` |
| `ga4_measurement_id` | yes | must start with `G-` |
| `persona.slug` | yes | `/^[a-z][a-z0-9-]*$/` |
| `persona.display_name` | yes | non-empty string |
| `persona.bio` | yes | non-empty string; used in bio_short if bio_full absent |
| `persona.bio_full` | no | longer version; include `NN-year-old` for photo age extraction |
| `persona.location` | yes | non-empty string |
| `persona.location_detail` | no | defaults to `persona.location` |
| `persona.background` | no | must be portfolio-unique (Rule 1); omitting risks collision |
| `persona.voice_notes` | yes | non-empty string; injected directly into producer prompt |
| `persona.photo_source` | yes | absolute path; file must exist at validation time |
| `persona.about_photo_source` | yes | absolute path; file must exist at validation time |
| `visual.primary_color` | yes | `#RRGGBB` |
| `visual.accent_color` | yes | `#RRGGBB` |
| `visual.background_color` | yes | `#RRGGBB` |
| `visual.font_headings` | yes | non-empty string |
| `visual.font_body` | yes | non-empty string |
| `categories` | yes | non-empty array |
| `categories[].slug` | yes | URL-safe string |
| `categories[].label` | yes | non-empty string |
| `categories[].hubs` | yes | non-empty array |
| `categories[].hubs[].slug` | yes | URL-safe string |
| `categories[].hubs[].label` | yes | non-empty string |
| `categories[].hubs[].description` | no | omitting → hub-descriptions FAIL in preflight |
| `keyword_source.xlsx_path` | no | absolute path to keyword XLSX; also settable via `--xlsx` flag |
| `dns_provider` | no | defaults to `cloudflare` |
| `github.owner` | no | only needed for Sites 1–10 (git-push deploy pattern) |
| `github.visibility` | no | only needed for Sites 1–10 |
| `pre_launch` | no | set true; portfolio status will be `pre_launch` until Point 16 |

---

## Pre-launch checklist (before `launch-site.mjs --site <slug>`)

- [ ] `slug` is unique — not in `portfolio.yaml`
- [ ] `domain` is registered and pointing at Cloudflare nameservers
- [ ] `amazon_associates_id` created in Amazon Associates dashboard
- [ ] `ga4_measurement_id` created in Google Analytics
- [ ] `persona.background` is unique across all portfolio personas:
      `grep -h "^background:" ~/*/config/personas/*.yaml | sort | uniq -d` → empty
- [ ] `persona.photo_source` and `persona.about_photo_source` files exist at the stated paths
- [ ] Hub descriptions written (omitting them = preflight FAIL at Point 15.5)
- [ ] `niche` value matches an entry in `config/niche-palettes.yaml`
      (if niche is new, add it to niche-palettes.yaml before launch)
- [ ] If niche has DTC brands: `config/dtc-brands/<niche>.yaml` exists

---

## What initialise-site.mjs does with the spec

Phase 1 (local scaffolding):
- Clones `templates/site-shell/` into `~/<slug>/`
- Generates `site.config.yaml` from spec fields
- Generates `config/navigation.yaml` from `categories`
- Generates `config/personas/<persona.slug>.yaml` from `persona.*`
- Copies `photo_source` → `public/images/brand/<persona.slug>-byline.jpg`
- Copies `about_photo_source` → `public/images/brand/<persona.slug>-about.jpg`
- Substitutes `{{BRAND_NAME}}`, `{{DOMAIN}}`, etc. throughout all template files

Phase 2 (git initialization):
- `git init`, `git submodule add affiliate-platform`, initial commit

Phase 3+ (cloud resources, `--proceed` flag required):
- Creates Cloudflare Pages project
- Registers in portfolio.yaml
