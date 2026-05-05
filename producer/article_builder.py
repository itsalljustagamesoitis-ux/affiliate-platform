"""
Platform article builder.
Takes a pipeline article + loaded data, calls Claude, returns (body, title, description).

Key changes from per-site builders:
  - No embedded SYSTEM constant — system prompt comes from prompt_loader (R1)
  - No TYPE_WORD_COUNTS — word count comes from style_policy (R2)
  - No H2_STRUCTURES — pipeline h2_structure ignored with warning (R3/R4)
  - product_count enforcement: halt on shortfall, trim on excess (R5)
  - Catalog-growth path: writes VERIFY entries for unknown product slugs (R6)
  - Validator integration: roundup articles validated before write (R7)
  - author/category read from site_config (R10)
  - _fix_punctuation and _americanize preserved verbatim from MLT (R9)
"""

import json
import os
import re
import shutil
import subprocess
import sys
import yaml
from datetime import date, datetime
from pathlib import Path

PLATFORM_ROOT = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# Catalog-growth helpers (CATALOG-BEHAVIOUR.md Section 2)
# ---------------------------------------------------------------------------

def _slugify(brand: str, name: str) -> str:
    """Derive product slug per CATALOG-BEHAVIOUR.md slug derivation rules."""
    stop_words = {"the", "a", "an", "and", "for", "of", "in", "with", "by"}
    combined = f"{brand} {name}".lower()
    combined = re.sub(r"[^a-z0-9]+", "-", combined)
    parts = [p for p in combined.split("-") if p and p not in stop_words]
    slug = "-".join(parts)
    return re.sub(r"-+", "-", slug).strip("-")


def _ensure_products_in_catalog(article: dict, products: dict, site_root: Path) -> dict:
    """
    For any product slug in article["products"] missing from products dict:
      - Write a VERIFY entry to products.yaml (CATALOG-BEHAVIOUR.md §2)
      - Log a prominent warning
      - Return reloaded products dict

    Raises ValueError on slug collision (same slug, different name/brand).
    """
    missing = [k for k in article.get("products", []) if k not in products]
    if not missing:
        return products

    products_path = site_root / "content/products/products.yaml"
    with open(products_path) as f:
        raw = yaml.safe_load(f) or {}

    hub = article.get("hub_slug", article.get("hub", ""))
    timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    for slug in missing:
        parts = slug.split("-")
        display_name = " ".join(p.title() for p in parts)
        brand = parts[0].title() if parts else slug

        if slug in raw:
            ex = raw[slug]
            if ex.get("name") == display_name and ex.get("brand") == brand:
                continue
            raise ValueError(
                f"Slug collision: '{slug}' exists in products.yaml with "
                f"name='{ex.get('name')}' / brand='{ex.get('brand')}' but "
                f"auto-derived entry would be name='{display_name}' / brand='{brand}'. "
                f"Resolve manually before generating."
            )

        raw[slug] = {
            "name": display_name,
            "brand": brand,
            "hub": hub,
            "amazon_asin": "VERIFY",
            "price_band": "mid",
            "default_pros": ["[PLACEHOLDER — update before next build]"],
            "default_cons": ["[PLACEHOLDER — update before next build]"],
            "notes_for_writers": (
                f"added by producer during {article['slug']} generation, {timestamp}"
            ),
        }
        print(
            f"  CATALOG GROWTH: Added VERIFY entry for '{slug}' "
            f"(auto-derived name: '{display_name}')"
        )
        print(
            f"  WARNING: Review and update this products.yaml entry "
            f"(name, brand, pros, cons) before the next build."
        )

    tmp = products_path.with_suffix(".yaml.tmp")
    bak = products_path.with_suffix(".yaml.bak")
    with open(tmp, "w") as f:
        yaml.dump(raw, f, default_flow_style=False, allow_unicode=True, sort_keys=True)
    if products_path.exists():
        shutil.copy2(products_path, bak)
    os.replace(tmp, products_path)

    # Reload
    from data_loader import load_products
    return load_products(site_root)


# ---------------------------------------------------------------------------
# Product-count enforcement (CATALOG-BEHAVIOUR.md + prompt §1)
# ---------------------------------------------------------------------------

def _enforce_product_count(article: dict, products: dict, metadata: dict) -> list:
    """
    Returns the final list of product keys for generation.

    Rules:
      - Shortfall (assigned < min): halt with clear error message
      - Excess (assigned > max): trim to max (highest-rated then most relevant)
      - No assigned products: use hub-matched products (min-max enforced)
    """
    assigned = article.get("products", [])
    pc = metadata.get("product_count", {"min": 3, "max": 6})
    min_count = pc["min"]
    max_count = pc["max"]

    if assigned:
        # Filter to products that actually exist in catalog
        valid = [k for k in assigned if k in products]
        if len(valid) < min_count:
            raise ValueError(
                f"Product shortfall for '{article['slug']}': "
                f"brief has {len(valid)} valid products "
                f"(min required: {min_count}). "
                f"Add products to products.yaml or update the pipeline brief."
            )
        if len(valid) > max_count:
            print(
                f"  TRIM: {len(valid)} products exceeds max {max_count}. "
                f"Trimming to first {max_count}."
            )
            valid = valid[:max_count]
        return valid
    else:
        # Fall back to hub-matched products
        hub_slug = article.get("hub_slug", article.get("hub", ""))
        hub_prods = {k: v for k, v in products.items() if v.get("hub") == hub_slug}
        if len(hub_prods) < min_count:
            raise ValueError(
                f"Insufficient hub products for '{article['slug']}' (hub: {hub_slug}): "
                f"found {len(hub_prods)}, need at least {min_count}."
            )
        keys = list(hub_prods.keys())[:max_count]
        return keys


# ---------------------------------------------------------------------------
# Validator integration (CATALOG-BEHAVIOUR.md §3)
# ---------------------------------------------------------------------------

def _run_validator(article_type: str, md_path: Path, site_root: Path) -> bool:
    """
    Run platform validator for this article type. Returns True if valid (or no validator).
    Logs result. Does NOT sys.exit — caller handles exit on False.
    """
    norm_type = article_type.lower().replace(" ", "_")
    validator_map = {
        "roundup": PLATFORM_ROOT / "validators/validate-roundup.mjs",
    }
    validator_path = validator_map.get(norm_type)

    if not validator_path:
        print(f"  VALIDATOR: No platform validator for type '{article_type}' — skipping.")
        return True

    if not validator_path.exists():
        print(f"  VALIDATOR: {validator_path.name} not found — skipping.")
        return True

    result = subprocess.run(
        ["node", str(validator_path), "--site", str(site_root), str(md_path)],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"  VALIDATOR FAIL ({validator_path.name}) exit={result.returncode}")
        if result.stdout:
            print(result.stdout[-1500:])
        if result.stderr:
            print(result.stderr[-500:])
        return False

    print(f"  VALIDATOR: {validator_path.name} PASS")
    return True


# ---------------------------------------------------------------------------
# EEAT brief builder
# ---------------------------------------------------------------------------

def build_eeat_brief(eeat: dict, persona: dict) -> str:
    persona_name = persona.get("name", "PERSONA").upper()
    lines = []
    if eeat.get("experiences"):
        lines.append(f"{persona_name}'S RELEVANT EXPERIENCES:")
        for e in eeat["experiences"]:
            lines.append(f"- {e.get('story', '')}")
    if eeat.get("failures"):
        lines.append(f"\n{persona_name}'S FAILURES TO REFERENCE:")
        for f in eeat["failures"]:
            lines.append(f"- {f.get('lesson', '')}")
    if eeat.get("opinions"):
        lines.append(f"\n{persona_name}'S STRONG OPINIONS:")
        for o in eeat["opinions"]:
            lines.append(f"- {o.get('opinion', '')}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Products brief builder
# ---------------------------------------------------------------------------

def build_products_brief(product_keys: list, products: dict, amazon_tag: str) -> str:
    lines = []
    for key in product_keys:
        p = products.get(key)
        if not p:
            continue
        asin = p.get("amazon_asin", "")
        amazon_url = (
            f"https://www.amazon.com/dp/{asin}?tag={amazon_tag}"
            if asin and asin not in ("VERIFY", "NOT_ON_AMAZON")
            else ""
        )
        lines.append(
            f"- **{p['name']}** (key: {key})\n"
            f"  Brand: {p.get('brand', '')} | Price band: {p.get('price_band', '')} | ASIN: {asin}\n"
            f"  Amazon link: {amazon_url}\n"
            f"  Pros: {'; '.join(p.get('default_pros', []))}\n"
            f"  Cons: {'; '.join(p.get('default_cons', []))}\n"
            f"  Writer notes: {p.get('notes_for_writers', '')}"
        )
    return "\n\n".join(lines) if lines else "No products assigned."


# ---------------------------------------------------------------------------
# Prompt builder (user message / {{BRIEF}})
# ---------------------------------------------------------------------------

def build_prompt(
    article: dict,
    product_keys: list,
    products: dict,
    eeat: dict,
    persona: dict,
    site_config: dict,
    metadata: dict,
) -> str:
    """
    Build the user-message ({{BRIEF}}) for the model.
    The system message comes from prompt_loader.load_prompt().

    For article types with a platform prompt, h2_structure from the pipeline
    is ignored (R4) — the platform prompt defines structure.
    """
    article_type = article["type"]
    norm_type = article_type.lower().replace(" ", "_")

    # R4: Ignore pipeline h2_structure for platform-prompted types
    has_platform_prompt = metadata.get("article_type") in ("roundup", "buyer_guide")
    if has_platform_prompt and article.get("h2_structure"):
        print(
            f"  NOTE: Ignoring pipeline h2_structure for {norm_type} "
            f"(platform prompt defines structure per CATALOG-BEHAVIOUR spec)."
        )

    # Word count from style_policy (R2)
    wc = metadata.get("word_count", site_config.get("style_policy", {}).get("word_count", {}))
    word_count_str = f"{wc.get('min', 2000):,}–{wc.get('max', 3000):,}"

    amazon_tag = site_config.get("affiliate", {}).get("amazon_tracking_id", "")
    products_brief = build_products_brief(product_keys, products, amazon_tag)
    eeat_brief = build_eeat_brief(eeat, persona)

    hub_url = article.get("hub_url", f"/{article.get('hub_slug', '')}/")
    hub_label = article.get("hub_label", "")
    category_label = article.get("category_label", "")

    comparison_note = ""
    if norm_type == "comparison" and len(product_keys) >= 2:
        p1 = products.get(product_keys[0], {})
        p2 = products.get(product_keys[1], {})
        comparison_note = (
            f"\nThis is a head-to-head comparison: "
            f"**{p1.get('name', 'Product A')}** vs **{p2.get('name', 'Product B')}**."
        )

    siblings = article.get("_siblings", [])
    sibling_block = ""
    if siblings:
        sibling_lines = "\n".join(
            f'- [{s["keyword"].title()}](/{s["slug"]}/)'
            for s in siblings[:6]
        )
        sibling_block = (
            f"\nINTERNAL LINKS — SIBLING ARTICLES:\n"
            f"These articles are already published on the site in the same topic area.\n"
            f"Link to 2-3 of them naturally where relevant in the body "
            f"— not in a list, but as contextual anchor text mid-sentence.\n"
            f"{sibling_lines}\n"
        )

    # For non-platform-prompted types, include H2 structure in prompt
    h2_block = ""
    if not has_platform_prompt:
        h2_structure = article.get("h2_structure", "")
        if h2_structure:
            h2_block = f"\nH2 STRUCTURE TO FOLLOW:\n{h2_structure}\n"

    prompt = f"""Write a {article_type} article for {site_config.get('site', {}).get('brand_name', 'this site')}.

TARGET KEYWORD: {article['keyword']}
ARTICLE TYPE: {article_type}
ANGLE / PERSONA HOOK: {article['angle']}
TARGET WORD COUNT: {word_count_str} words
CATEGORY: {category_label}
HUB: {hub_label} ({hub_url})
{comparison_note}
{h2_block}
PRODUCTS TO COVER:
{products_brief}

{eeat_brief}

HUB LINK REQUIREMENT:
Include a contextual link to the hub page ({hub_url} — "{hub_label}") at least twice:
once naturally in the first half of the article (before or just after the first H2),
and once in the second half (before the FAQ or in a closing paragraph).
Use varied phrasing — don't repeat the same anchor text.
{sibling_block}
AFFILIATE LINKS:
When mentioning a product by name, link to its Amazon URL using the product name as anchor text.
Format: [Product Name](https://www.amazon.com/dp/ASIN?tag={amazon_tag})

FAQ SECTION:
End with an H2 "Frequently Asked Questions" section containing exactly 5 Q&A pairs.
Use H3 for each question. Questions should be the kind a real buyer would search.

Write the full article body now. Do not include frontmatter. Start with the intro paragraph."""

    return prompt


# ---------------------------------------------------------------------------
# Title + meta description (Haiku, two-model pattern preserved)
# ---------------------------------------------------------------------------

def generate_title_and_desc(article: dict, body: str, client) -> tuple:
    """Draft title (<65 chars) and meta description (150-160 chars) from body."""
    import anthropic

    prompt = f"""Write a title and meta description for this article.

Keyword: {article['keyword']}
Type: {article['type']}
Article opening:
{body[:600]}

Rules:
- Title: under 65 characters, keyword near the front, specific and honest (no "ultimate", no "best ever")
- Meta description: 150–160 characters exactly, plain sentence, no em dashes, no exclamation marks

Return JSON only:
{{"title": "...", "description": "..."}}"""

    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.content[0].text.strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    data = json.loads(text[start:end])
    return data.get("title", ""), data.get("description", "")


# ---------------------------------------------------------------------------
# Main generation entry point
# ---------------------------------------------------------------------------

def generate_article(
    article: dict,
    products: dict,
    eeat: dict,
    persona: dict,
    client,
    site_config: dict,
    site_root: Path,
    system_text: str,
    metadata: dict,
) -> tuple:
    """
    Returns (body_text, title, description).

    system_text: rendered platform prompt (from prompt_loader.load_prompt()).
      If None (unsupported article type), falls back to a minimal persona-based system.
    """
    if system_text is None:
        # Fallback for non-platform-prompted types: build minimal system from persona
        system_text = _build_fallback_system(persona, site_config)

    # R5: product count enforcement (after catalog-growth in caller)
    try:
        product_keys = _enforce_product_count(article, products, metadata)
    except ValueError as e:
        raise

    prompt = build_prompt(article, product_keys, products, eeat, persona, site_config, metadata)

    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=system_text,
        messages=[{"role": "user", "content": prompt}],
    )
    body = resp.content[0].text.strip()
    body = _fix_punctuation(body)
    body = _americanize(body)
    title, description = generate_title_and_desc(article, body, client)
    return body, title, description, product_keys


def _build_fallback_system(persona: dict, site_config: dict) -> str:
    """Minimal system prompt for article types without a platform prompt."""
    brand = site_config.get("site", {}).get("brand_name", "this site")
    name = persona.get("name", "")
    voice_notes = persona.get("voice_notes", "")
    background = persona.get("background", "")
    banned_words = "unlock, navigate, navigating, journey, transformative, holistic, robust, seamless, dive deep, elevate, game-changer"
    dollar_allowed = site_config.get("style_policy", {}).get("dollar_figures", {}).get("allowed", False)
    dollar_rule = (
        "Dollar figures are permitted in prose to anchor a recommendation. Use sparingly."
        if dollar_allowed
        else "NO dollar figures anywhere. Use price band (budget/mid/premium/luxury) and relative language only."
    )

    return f"""You are a ghostwriter for {brand}, writing as {name}.

PERSONA BACKGROUND: {background}

VOICE: {voice_notes}

PRICE RULE: {dollar_rule}

BANNED WORDS: {banned_words}

FORMATTING:
- H1: article title only (do not include in body)
- H2 for all main sections, H3 for subsections
- NO em dashes (—) or double dashes (--) anywhere. Use commas, periods, or parentheses instead.
- No horizontal rules.
- FAQ section: exactly 5 Q&A pairs.

LANGUAGE: American English throughout.

OUTPUT FORMAT: Return the article body only (no frontmatter). Start with the intro paragraph directly."""


# ---------------------------------------------------------------------------
# Frontmatter builder
# ---------------------------------------------------------------------------

def build_frontmatter(
    article: dict,
    product_keys: list,
    products: dict,
    title: str,
    description: str,
    site_config: dict,
) -> str:
    """Build YAML frontmatter. Reads author from site_config persona path (R10)."""
    today = date.today().isoformat()
    article_type = article["type"].lower().replace(" ", "_")
    layout_type = article_type  # buyer_guide maps 1:1 in platform

    # R10: derive author ID from persona config_path
    persona_path = site_config.get("persona", {}).get("config_path", "config/personas/unknown.yaml")
    author_id = Path(persona_path).stem  # "config/personas/emily.yaml" → "emily"

    # Build products list
    assigned_keys = product_keys
    if article_type == "comparison" and len(assigned_keys) >= 2:
        roles = ["primary", "alternative"]
    elif article_type == "roundup":
        roles = ["best_overall"] + ["also_consider"] * (len(assigned_keys) - 1)
    elif article_type == "review":
        roles = ["primary"]
    elif article_type == "buyer_guide":
        roles = ["best_overall"] + ["also_consider"] * (len(assigned_keys) - 1)
    else:
        roles = ["also_consider"] * len(assigned_keys)

    def _cy(s):
        return s.replace("\u2014", ",").replace("\u2013", ",").replace('"', '\\"')

    prod_refs = []
    for i, key in enumerate(assigned_keys):
        role = roles[i] if i < len(roles) else "also_consider"
        p = products.get(key, {})
        pros = [_cy(x) for x in p.get("default_pros", [])[:2]]
        cons = [_cy(x) for x in p.get("default_cons", [])[:1]]
        ref = f'  - id: "{key}"\n    role: "{role}"'
        if pros:
            ref += "\n    article_specific_pros:\n" + "\n".join(f'      - "{pr}"' for pr in pros)
        if cons:
            ref += "\n    article_specific_cons:\n" + "\n".join(f'      - "{c}"' for c in cons)
        prod_refs.append(ref)

    products_yaml = "\n".join(prod_refs) if prod_refs else "  []"

    comparison_fields = ""
    if article_type == "comparison" and len(assigned_keys) >= 2:
        comparison_fields = (
            f'product_a: "{assigned_keys[0]}"\n'
            f'product_b: "{assigned_keys[1]}"\n'
            f'# winner: product_a  # SET THIS after review\n'
            f'# winner_reason: ""  # SET THIS after review\n'
        )

    cluster = article.get("cluster", "")
    tags = [cluster, article["type"].lower()]

    def _clean_yaml(s: str) -> str:
        return s.replace("\u2014", ",").replace("\u2013", ",").replace('"', '\\"')

    safe_title = _clean_yaml(title) if title else article["keyword"].title()
    safe_desc = _clean_yaml(description) if description else ""
    hub = article.get("hub_slug", article.get("hub", ""))
    img_n = (article.get("id", 1) - 1) % 8 + 1
    hero_image = article.get("hero_image") or f"articles/{hub}-{img_n}.jpg"
    hero_alt = _clean_yaml(article.get("hero_image_alt", "") or safe_title)

    # R10: category from article (populated by enrich_article)
    category = article.get("category_label", article.get("category_slug", ""))

    return f"""---
title: "{safe_title}"
slug: "{article['slug']}"
type: "{layout_type}"
date: {today}
author: "{author_id}"
category: "{category}"
hub: "{hub}"
hero_image: "{hero_image}"
hero_image_alt: "{hero_alt}"
description: "{safe_desc}"
target_keyword: "{article['keyword']}"
products:
{products_yaml}
tags: {json.dumps(tags)}
disclosure_required: true
noindex: false
{comparison_fields}---

"""


# ---------------------------------------------------------------------------
# Review .txt builder
# ---------------------------------------------------------------------------

def build_review_txt(
    article: dict, product_keys: list, body: str, title: str, description: str
) -> str:
    products_line = ", ".join(product_keys) or "none"
    return f"""TITLE: {title}
DESC: {description}

---
Article ID {article['id']} | {article['type']} | Cluster: {article['cluster']}
Hub: {article.get('hub_label', '')} ({article.get('hub_url', '')}) | KD: {article.get('kd', 0)} | Vol: {article.get('volume', 0)}
Products: {products_line}
---

{body}
"""


# ---------------------------------------------------------------------------
# Post-processing (preserved verbatim from MLT — R9)
# ---------------------------------------------------------------------------

def _americanize(text: str) -> str:
    """Convert British spellings to American English."""
    replacements = [
        (r"\bcolours?\b", lambda m: "colors" if m.group().endswith("s") else "color"),
        (r"\bcolour(ed|ing|ful|less|s)?\b", lambda m: "color" + (m.group(1) or "")),
        (r"\bflavours?\b", lambda m: "flavors" if m.group().endswith("s") else "flavor"),
        (r"\bhonours?\b", lambda m: "honors" if m.group().endswith("s") else "honor"),
        (r"\bhumours?\b", lambda m: "humors" if m.group().endswith("s") else "humor"),
        (r"\blabours?\b", lambda m: "labors" if m.group().endswith("s") else "labor"),
        (r"\bneighbou?rs?\b", lambda m: "neighbors" if m.group().endswith("s") else "neighbor"),
        (r"\bfavou?r(ite|s|ed|ing)?\b", lambda m: "favor" + (m.group(1) or "")),
        (r"\brealise(d|s|r|rs|ing)?\b", lambda m: "realize" + (m.group(1) or "")),
        (r"\brecognise(d|s|r|rs|ing)?\b", lambda m: "recognize" + (m.group(1) or "")),
        (r"\borganise(d|s|r|rs|ing|ation|ations)?\b", lambda m: "organize" + (m.group(1) or "")),
        (r"\bprioritise(d|s|ing)?\b", lambda m: "prioritize" + (m.group(1) or "")),
        (r"\bminimise(d|s|ing)?\b", lambda m: "minimize" + (m.group(1) or "")),
        (r"\bmaximise(d|s|ing)?\b", lambda m: "maximize" + (m.group(1) or "")),
        (r"\bemphasise(d|s|ing)?\b", lambda m: "emphasize" + (m.group(1) or "")),
        (r"\bspecialise(d|s|ing)?\b", lambda m: "specialize" + (m.group(1) or "")),
        (r"\bcentralise(d|s|ing)?\b", lambda m: "centralize" + (m.group(1) or "")),
        (r"\bcentre(d|s|ing)?\b", lambda m: "center" + (m.group(1) or "")),
        (r"\bmetres?\b", lambda m: "meters" if m.group().endswith("s") else "meter"),
        (r"\bfibres?\b", lambda m: "fibers" if m.group().endswith("s") else "fiber"),
        (r"\btheatres?\b", lambda m: "theaters" if m.group().endswith("s") else "theater"),
        (r"\bfertiliser(s)?\b", lambda m: "fertilizer" + (m.group(1) or "")),
        (r"\bfertilise(d|s|ing)?\b", lambda m: "fertilize" + (m.group(1) or "")),
        (r"\btravell(ing|ed|er|ers)\b", lambda m: "travel" + m.group(1)),
        (r"\bcancell(ed|ing)\b", lambda m: "cancel" + m.group(1)),
        (r"\blabelled?\b", "labeled"),
        (r"\bchannelled?\b", "channeled"),
        (r"\bcatalogued?\b", "cataloged"),
        (r"\baluminium\b", "aluminum"),
        (r"\bgrey\b", "gray"),
        (r"\bGrey\b", "Gray"),
        (r"\bwhilst\b", "while"),
        (r"\bamongst\b", "among"),
        (r"\btowards\b", "toward"),
        (r"\bafterwards\b", "afterward"),
        (r"\bdefence\b", "defense"),
        (r"\blicence\b", "license"),
        (r"\bpractise\b", "practice"),
        (r"\btyre(s)?\b", lambda m: "tires" if m.group().endswith("s") else "tire"),
        (r"\bkerb(s)?\b", lambda m: "curbs" if m.group().endswith("s") else "curb"),
    ]
    for pattern, repl in replacements:
        if callable(repl):
            text = re.sub(pattern, repl, text, flags=re.IGNORECASE)
        else:
            text = re.sub(pattern, repl, text, flags=re.IGNORECASE)
    return text


def _fix_punctuation(text: str) -> str:
    """Hard-fix punctuation the model generates despite instructions."""
    text = text.replace("\u2014", ",")
    text = text.replace("\u2013", ",")
    text = text.replace("---", ",")
    text = text.replace(" -- ", ", ")
    text = text.replace("--", ",")
    text = re.sub(r"\(\s*\)", "", text)
    text = re.sub(r",\s*\)", ")", text)
    text = re.sub(r"\(\s*,", "(", text)
    text = re.sub(r",\s*,", ",", text)
    text = re.sub(r",\s*\.", ".", text)
    text = re.sub(r"[^\S\n]{2,}", " ", text)
    return text
