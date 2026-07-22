# Persona Photo Prompt Template

Version: 1.0 (2026-05-31)
Used by: tools/generate-persona-photos.mjs

## Overview

This template generates DALL-E 3 prompts for persona byline and about page photographs.
The tool reads this file, extracts the prompt templates below, and interpolates variables
derived from the persona YAML and site config before sending to the API.

## Variables

| Variable | Source | Description |
|---|---|---|
| `{{name}}` | `persona.name_formal` | Full name |
| `{{role}}` | `persona.role` | Short role description |
| `{{location}}` | `persona.location` | City/region |
| `{{age_descriptor}}` | Parsed from `persona.background` | e.g. "a mid-30s person", "an early-50s person", "a person" |
| `{{setting_byline}}` | Niche default or override | Indoor portrait environment |
| `{{setting_about}}` | Niche default or override | Hobby/work environment |
| `{{action_description}}` | Niche default or override | What the persona is doing |

Age extraction: looks for `XX-year-old`, `age XX`, or `XX years old` in `persona.background`.
Falls back to `"a person in their 30s"` if no age is found.

## Byline prompt template

A candid portrait photograph of {{age_descriptor}}, {{role}}, based in {{location}}. Natural window light from the side, shallow depth of field. Warm, approachable expression with a slight smile, looking slightly off-camera. Professional-casual attire. Set in {{setting_byline}}. No text, no watermarks, no graphics. Photorealistic, editorial photography style.

## About page prompt template

A lifestyle photograph of {{age_descriptor}}, {{role}}. {{setting_about}}. {{action_description}}. Warm natural or ambient lighting. The subject is relaxed and engaged, in their element. Candid feel, not overly posed. Photorealistic lifestyle photography. No text or graphics.

## Niche defaults

Niche keys match the `site.niche` value in `site.config.yaml` exactly. Missing keys fall back to `default`.

### audiophile
setting_byline: home listening room, headphones and audio equipment softly visible on a shelf behind
setting_about: A well-organized home listening room with headphones on a stand, amplifier stack, and warm lamp lighting
action_description: Seated at a desk, listening through headphones with eyes closed

### fly-fishing
setting_byline: rustic home office or fly-tying bench, fly-tying materials in soft focus behind
setting_about: At the edge of a clear mountain river surrounded by cottonwoods and tall grass
action_description: Casting a fly rod over the water, line arcing in the air

### home-cinema
setting_byline: cozy home screening room, a large projection screen softly visible in the background
setting_about: A comfortable home theater room with a large projection screen showing a film
action_description: Leaning forward slightly, absorbed in the film

### astronomy
setting_byline: home office or study with star charts, a telescope eyepiece case, and astronomy books softly visible on shelves behind
setting_about: A backyard observatory or patio at dusk, telescope silhouetted against a deep blue twilight sky, milky way beginning to appear
action_description: Standing at a telescope eyepiece or adjusting a mount polar alignment, focused and in their element

### power-tools
setting_byline: a home garage workshop with a pegboard of tools softly visible out of focus behind, warm natural light from a side window
setting_about: A real home workshop or garage with a workbench, a few cordless power tools, and warm ambient light — no readable brand logos
action_description: Standing at a workbench examining a cordless drill, relaxed and in their element, sleeves pushed up

### bedroom-comfort
setting_byline: a cozy, lived-in bedroom, soft natural window light, a folded blanket and pillow softly visible out of focus behind
setting_about: A warm, lived-in bedroom with a mix of textures visible — a folded weighted blanket, a pillow, soft natural light through a window
action_description: Sitting on the edge of the bed adjusting a blanket or pillow, relaxed and mid-conversation, not posed

### watch-care
setting_byline: a small home workbench, a loupe, a few tools, and a couple of watches softly visible out of focus behind, warm desk-lamp lighting
setting_about: A home workbench setting with a loupe, small tools, and a couple of watches visible, warm desk-lamp lighting, candid 35mm look
action_description: Bent over a watch strap or tool at the workbench, focused mid-task, sleeves pushed up

### default
setting_byline: home office with bookshelves and soft natural light from a window
setting_about: A comfortable, well-appointed home workspace with personal objects visible
action_description: Engaged in their work or hobby, relaxed expression
