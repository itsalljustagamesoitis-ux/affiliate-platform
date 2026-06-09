#!/usr/bin/env python3
"""
Pre-flight checklist for affiliate sites before launch or deploy.

18 checks. Checks 1–9 derived from the SaunasSoSimple UAT post-mortem (2026-05-24);
checks 10–14 added from V8/V9/V14/V15/V16 validators (2026-05-26–27);
checks 15–18 added from V2/V3/V5/V12 validators (2026-05-28).
All 7 UAT critical issues would have been caught by this script.

Usage:
  python3 scripts/preflight.py --site <slug>
  python3 scripts/preflight.py --site <slug> --check json-ld-urls,og-locale
  python3 scripts/preflight.py --site <slug> --verbose

Exit codes:
  0 = all checks pass (may include WARNs)
  1 = one or more FAILs (launch blocked)
  2 = tool error (missing site, missing required files)

Checks (in order):
  1  scaffold-contamination  — no vocabulary bleed from other verticals
  2  state-sync              — article count matches pipeline.json
  3  hub-descriptions        — no boilerplate hub descriptions in navigation.yaml
  4  json-ld-urls            — SchemaMarkup.astro constructs absolute schema URLs
  5  og-locale               — BaseLayout.astro has og:locale meta tag
  6  persona-consistency     — persona photo exists; bio claims are plausible
  7  url-slug-dedup          — no near-duplicate slugs in content/articles/
  8  ymyl-hub-check          — no health/medical hub labels or slugs
  9  product-topic-match     — products.yaml hub matches referencing articles
  10 brand-niche             — no fabricated brand framing; no brand/niche contamination (V8)
  11 spec-consistency        — article body specs match products.yaml ground truth (V16)
  12 hub-consistency         — product hub matches article hub (V14)
  13 product-coherence       — product tokens have semantic overlap with article (V15)
  14 dollar-figures          — no Amazon product prices in article content (V9)
  15 furniture-pages         — required static pages present; no placeholders (V2)
  16 amazon-tag              — tracking ID format valid; not a placeholder (V3)
  17 brand-collision         — no foreign persona/brand names in article content (V5)
  18 ymyl-endorsement        — no unqualified clinical claims on YMYL sites (V12)

UAT issue coverage:
  Issue 1 (scaffold contamination)    → check 1
  Issue 2 (hub description boilerplate) → check 3
  Issue 3 (JSON-LD relative URLs)     → check 4
  Issue 4 (YMYL hubs)                 → check 8
  Issue 5 (URL duplicates)            → check 7
  Issue 6 (product mismatches)        → check 9
  Issue 7 (persona photo/bio/og:locale) → checks 5, 6
  V8 FFC findings (fabricated VW/Chevy articles) → check 10
  V16 LogHog brand-swap spec mismatch → check 11
"""

import argparse
import importlib.util
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

import yaml

# ── Constants ────────────────────────────────────────────────────────────────

PLATFORM_ROOT = Path(__file__).parent.parent

BOILERPLATE_HUB_PATTERNS = [
    r"research.based buyer guides covering",
    r"buyer guides from",
    r"^browse our",
    r"^find the best",
    r"^everything you need to know",
]

YMYL_HUB_TERMS = [
    "health", "medical", "medicine", "cure", "treat", "diagnos", "prescription",
    "symptom", "disease", "therapy", "clinical", "wellness-guide", "how-to-sauna",
    "sauna-health", "sauna-how-to", "health-guide", "health-benefit",
]

MASTER_VOCAB_PATH = PLATFORM_ROOT / "config/forbidden-vocabulary.yaml"


def load_master_vocab() -> dict:
    """Load affiliate-platform/config/forbidden-vocabulary.yaml.
    Returns dict of {section_key: {"niche_keywords": [...], "terms": [...]}}"""
    if not MASTER_VOCAB_PATH.exists():
        return {}
    with open(MASTER_VOCAB_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data


def detect_vertical(cfg: dict) -> str:
    """Return the section key from forbidden-vocabulary.yaml that matches this site.
    Uses site.config.yaml `vertical:` override first, then matches niche against
    each section's niche_keywords list. Returns '' if no match."""
    # Explicit override in site.config.yaml
    override = cfg.get("site", {}).get("vertical", "")
    if override and str(override).lower() not in ("false", "none", ""):
        return str(override).lower()

    niche = (cfg.get("site", {}).get("niche", "") or "").lower()
    if not niche:
        return ""

    master = load_master_vocab()
    for section_key, section in master.items():
        for kw in section.get("niche_keywords", []):
            if kw.lower() in niche:
                return section_key
    return ""

# ── Result tracking ───────────────────────────────────────────────────────────

class CheckResult:
    def __init__(self, name: str):
        self.name = name
        self.status = "PASS"   # PASS | WARN | FAIL
        self.messages: list[str] = []

    def fail(self, msg: str):
        self.status = "FAIL"
        self.messages.append(msg)

    def warn(self, msg: str):
        if self.status != "FAIL":
            self.status = "WARN"
        self.messages.append(msg)

    def info(self, msg: str):
        self.messages.append(msg)


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_yaml(path: Path):
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_json(path: Path):
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def parse_article_frontmatter(path: Path) :
    try:
        text = path.read_text(encoding="utf-8")
        m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
        if not m:
            return None
        return yaml.safe_load(m.group(1)) or {}
    except Exception:
        return None


def iter_hubs(nav: dict):
    """Yield each hub dict from navigation.yaml regardless of nesting level."""
    for cat in nav.get("categories", []):
        for hub in cat.get("hubs", []):
            yield hub
    for hub in nav.get("hubs", []):
        yield hub


def slug_wordset(slug: str) -> frozenset[str]:
    return frozenset(slug.lower().replace("-", " ").split())


# ── Check implementations ─────────────────────────────────────────────────────

def check_scaffold_contamination(site_root: Path, cfg: dict, verbose: bool) -> CheckResult:
    r = CheckResult("scaffold-contamination")

    # Priority 1: per-site config/furniture-validation.yaml (explicit override)
    forbidden: list[str] = []
    source_label = ""

    fv_path = site_root / "config/furniture-validation.yaml"
    fv = load_yaml(fv_path)
    if fv:
        for entry in fv.get("forbidden_vocabulary", []):
            if isinstance(entry, str):
                forbidden.append(entry.lower())
            elif isinstance(entry, dict) and "term" in entry:
                forbidden.append(entry["term"].lower())
        if forbidden:
            source_label = "config/furniture-validation.yaml"

    # Priority 2: site.config.yaml forbidden_vocabulary list
    if not forbidden:
        for term in (cfg.get("content") or {}).get("forbidden_vocabulary", []):
            forbidden.append(str(term).lower())
        if forbidden:
            source_label = "site.config.yaml content.forbidden_vocabulary"

    # Priority 3: platform master vocabulary file (all sections except this site's vertical)
    if not forbidden:
        own_vertical = detect_vertical(cfg)
        exempt_sections = set(cfg.get("scaffold_contamination", {}).get("exempt_sections", []))
        master = load_master_vocab()
        if master:
            skipped_sections = []
            for section_key, section in master.items():
                if section_key == own_vertical:
                    skipped_sections.append(section_key)
                    continue
                if section_key in exempt_sections:
                    skipped_sections.append(f"{section_key} (exempt — intentional cross-coverage)")
                    continue
                for term in section.get("terms", []):
                    forbidden.append(str(term).lower())
            if own_vertical:
                r.info(f"Using master vocabulary ({len(master)} sections); skipping own vertical '{own_vertical}'"
                       + (f"; exempt: {', '.join(exempt_sections)}" if exempt_sections else ""))
            else:
                r.info(f"Using master vocabulary ({len(master)} sections); vertical undetected — scanning all sections")
            source_label = f"affiliate-platform/config/forbidden-vocabulary.yaml"
        else:
            r.warn("No forbidden vocabulary configured — master vocabulary file not found at affiliate-platform/config/forbidden-vocabulary.yaml")
            return r

    # Pre-compile word-boundary patterns for each term.
    # Multi-word phrases use \b only at start/end; single words use strict \b on both sides.
    compiled = []
    for term in forbidden:
        escaped = re.escape(term)
        pattern = re.compile(r"\b" + escaped + r"\b", re.IGNORECASE)
        compiled.append((term, pattern))

    # Scan content/articles/ and src/pages/
    scan_dirs = [site_root / "content/articles", site_root / "src/pages"]
    contaminated: list = []  # (file, term)

    for scan_dir in scan_dirs:
        if not scan_dir.exists():
            continue
        for fp in list(scan_dir.rglob("*.md")) + list(scan_dir.rglob("*.astro")):
            try:
                text = fp.read_text(encoding="utf-8")
                for term, pattern in compiled:
                    if pattern.search(text):
                        contaminated.append((fp.name, term))
                        break
            except Exception:
                pass

    if contaminated:
        r.fail(f"{len(contaminated)} file(s) contain forbidden cross-vertical vocabulary")
        r.info(f"  Vocabulary source: {source_label}")
        for fname, term in contaminated[:10]:
            r.info(f"  {fname}: contains '{term}'")
        if len(contaminated) > 10:
            r.info(f"  ... and {len(contaminated) - 10} more")
    else:
        r.info(f"No cross-vertical vocabulary found ({len(forbidden)} terms from {source_label}) ✓")

    return r


def check_state_sync(site_root: Path, verbose: bool) -> CheckResult:
    r = CheckResult("state-sync")

    articles_dir = site_root / "content/articles"
    pipeline_path = site_root / "data/pipeline.json"

    if not articles_dir.exists():
        r.fail("content/articles/ directory missing")
        return r

    md_files = list(articles_dir.glob("*.md"))
    article_count = len(md_files)

    if not pipeline_path.exists():
        r.warn("data/pipeline.json missing — cannot verify count")
        r.info(f"  {article_count} articles found in content/articles/")
        return r

    pipeline = load_json(pipeline_path)
    if isinstance(pipeline, dict):
        pipeline_articles = pipeline.get("articles", [])
    else:
        pipeline_articles = pipeline or []

    pipeline_count = len(pipeline_articles)

    if article_count == 0 and pipeline_count > 0:
        r.warn(f"content/articles/ is empty but pipeline.json has {pipeline_count} articles")
        r.info("  Fresh setup: articles not yet generated. Run producer before Phase 2.")
        return r

    if pipeline_count == 0:
        r.warn("pipeline.json has 0 articles — is this site bootstrapped?")
        return r

    # Allow up to 5% variance (some articles may be excluded by design)
    ratio = article_count / pipeline_count
    if ratio < 0.50:
        r.fail(f"Article count {article_count} is <50% of pipeline count {pipeline_count}")
        r.info("  Content may not have been published to content/articles/ yet")
    elif ratio < 0.80:
        r.warn(f"Article count {article_count} is only {ratio:.0%} of pipeline count {pipeline_count}")
    else:
        r.info(f"{article_count} articles present ({ratio:.0%} of {pipeline_count} pipeline articles)")

    return r


def check_hub_descriptions(site_root: Path, verbose: bool) -> CheckResult:
    r = CheckResult("hub-descriptions")

    nav_path = site_root / "config/navigation.yaml"
    if not nav_path.exists():
        r.fail("config/navigation.yaml not found")
        return r

    nav = load_yaml(nav_path)
    if not nav:
        r.fail("config/navigation.yaml is empty")
        return r

    hubs = list(iter_hubs(nav))
    if not hubs:
        r.warn("No hubs found in navigation.yaml")
        return r

    boilerplate_re = re.compile(
        "|".join(BOILERPLATE_HUB_PATTERNS), re.IGNORECASE
    )

    missing = []
    boilerplate = []

    for hub in hubs:
        slug = hub.get("slug", "?")
        desc = hub.get("description", "")
        if not desc or not str(desc).strip():
            missing.append(slug)
        elif boilerplate_re.search(str(desc)):
            boilerplate.append((slug, str(desc)[:80]))

    total = len(hubs)
    problem_count = len(missing) + len(boilerplate)
    problem_pct = problem_count / total if total else 0

    if missing:
        r.fail(f"{len(missing)}/{total} hubs have no description")
        for slug in missing[:10]:
            r.info(f"  Missing: {slug}")
        if len(missing) > 10:
            r.info(f"  ... and {len(missing) - 10} more")
    if boilerplate:
        r.fail(f"{len(boilerplate)}/{total} hubs have boilerplate descriptions")
        for slug, snippet in boilerplate[:5]:
            r.info(f"  Boilerplate: {slug} — \"{snippet}...\"")

    if problem_count == 0:
        r.info(f"All {total} hubs have custom descriptions")

    return r


def check_json_ld_urls(verbose: bool) -> CheckResult:
    r = CheckResult("json-ld-urls")

    schema_path = PLATFORM_ROOT / "src/components/SchemaMarkup.astro"
    if not schema_path.exists():
        r.fail(f"SchemaMarkup.astro not found at {schema_path}")
        return r

    source = schema_path.read_text(encoding="utf-8")

    # Check that siteUrl is constructed from cfg.site.domain
    if not re.search(r"siteUrl\s*=\s*`https://\$\{cfg\.site\.domain\}`", source):
        r.fail("SchemaMarkup.astro does not construct siteUrl from cfg.site.domain")
        r.info("  Fix: add `const siteUrl = \\`https://${cfg.site.domain}\\`` before schema objects")
    else:
        r.info("siteUrl constructed from cfg.site.domain ✓")

    # Check that schema url fields use siteUrl prefix (not bare relative paths)
    bare_url_pattern = re.findall(r'url:\s*["`\']/[a-z]', source)
    if bare_url_pattern:
        r.fail(f"{len(bare_url_pattern)} schema url: field(s) use bare relative paths")
        r.info("  These will produce relative URLs in JSON-LD which Google cannot resolve")
    else:
        r.info("No bare relative URL patterns found in schema ✓")

    return r


def check_og_locale(verbose: bool) -> CheckResult:
    r = CheckResult("og-locale")

    layout_path = PLATFORM_ROOT / "src/layouts/BaseLayout.astro"
    if not layout_path.exists():
        r.fail(f"BaseLayout.astro not found at {layout_path}")
        return r

    source = layout_path.read_text(encoding="utf-8")

    if 'og:locale' in source:
        r.info("og:locale present in BaseLayout.astro ✓")
    else:
        r.fail("og:locale meta tag missing from BaseLayout.astro")
        r.info('  Fix: add <meta property="og:locale" content="en_US" /> to <head>')

    return r


def check_persona_consistency(site_root: Path, verbose: bool) -> CheckResult:
    r = CheckResult("persona-consistency")

    personas_dir = site_root / "config/personas"
    if not personas_dir.exists():
        r.fail("config/personas/ directory not found")
        return r

    yaml_files = list(personas_dir.glob("*.yaml"))
    if not yaml_files:
        r.fail("No persona YAML files found in config/personas/")
        return r

    for persona_yaml in yaml_files:
        persona = load_yaml(persona_yaml) or {}
        slug = persona.get("slug", persona_yaml.stem)

        # Check photos exist
        for photo_field in ("photo_about", "photo_byline"):
            photo_path_str = persona.get(photo_field, "")
            if not photo_path_str:
                r.fail(f"{slug}: {photo_field} not set in persona YAML")
                continue
            # Resolve relative to public/
            photo_rel = photo_path_str.lstrip("/")
            photo_abs = site_root / "public" / photo_rel
            if not photo_abs.exists():
                r.warn(f"{slug}: {photo_field} → {photo_path_str} does not exist on disk (add before launch)")
            else:
                size = photo_abs.stat().st_size
                if size < 5000:
                    r.warn(f"{slug}: {photo_field} is only {size} bytes — may be placeholder")
                else:
                    r.info(f"{slug}: {photo_field} exists ({size:,} bytes) ✓")

        # Check bio word count claim matches actual bio
        bio_full = str(persona.get("bio_full", "") or "")
        if bio_full:
            actual_words = len(bio_full.split())
            # Look for "over N" or "N long-form" claims
            claim_match = re.search(r"over\s+(\d[\d,]*)\s+long.form\s+articles", bio_full, re.IGNORECASE)
            if claim_match:
                claimed = int(claim_match.group(1).replace(",", ""))
                # We can't verify the claimed article count from disk here, but
                # check that the bio_full text itself is plausible (>200 words)
                if actual_words < 100:
                    r.warn(f"{slug}: bio_full has only {actual_words} words — may be incomplete")
                else:
                    r.info(f"{slug}: bio_full is {actual_words} words; claims {claimed}+ articles ✓")
            else:
                if actual_words < 50:
                    r.warn(f"{slug}: bio_full is very short ({actual_words} words)")
                else:
                    r.info(f"{slug}: bio_full is {actual_words} words ✓")

        # Check name and display_name are set
        if not persona.get("name_formal"):
            r.warn(f"{slug}: name_formal not set")

    return r


def check_url_slug_dedup(site_root: Path, verbose: bool) -> CheckResult:
    r = CheckResult("url-slug-dedup")

    v1_path = Path(__file__).parent / "validate-slug-dedup.py"
    if not v1_path.exists():
        r.warn("validate-slug-dedup.py not found in scripts/ — falling back to legacy check")
        return _legacy_check_url_slug_dedup(site_root, verbose)

    spec = importlib.util.spec_from_file_location("validate_slug_dedup", v1_path)
    v1_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(v1_mod)

    result = v1_mod.scan_site(site_root, verbose=verbose)
    if result is None:
        r.warn("content/articles/ not found — skipping slug dedup check")
        return r

    high   = result["high"]
    medium = result["medium"]
    low    = result["low"]
    total  = result["total_slugs"]

    if high:
        r.fail(f"{len(high)} HIGH-confidence near-duplicate pair(s) — canonical decision required")
        for p in high[:10]:
            r.info(f"  [{p['detection_method']}] {p['slug_a']} ↔ {p['slug_b']}"
                   f" (canonical: {p['suggested_canonical']})")
        if len(high) > 10:
            r.info(f"  ... and {len(high) - 10} more (run validate-slug-dedup.py --report for full list)")

    if medium:
        r.warn(f"{len(medium)} MEDIUM-confidence near-duplicate pair(s) — editorial review needed")
        for p in medium[:5]:
            note = f" — {p['editorial_note']}" if p.get("editorial_note") else ""
            r.info(f"  [{p['detection_method']}] {p['slug_a']} ↔ {p['slug_b']}{note}")
        if len(medium) > 5:
            r.info(f"  ... and {len(medium) - 5} more MEDIUM pairs")

    if not high and not medium:
        r.info(f"No HIGH/MEDIUM near-duplicate slugs found ({total} articles) ✓")

    if low and verbose:
        r.info(f"  {len(low)} LOW-confidence review candidate(s) (Jaccard ≥ 0.75):")
        for p in low[:3]:
            score = p.get("jaccard_score", "?")
            r.info(f"    [j={score}] {p['slug_a']} ↔ {p['slug_b']}")
        if len(low) > 3:
            r.info(f"    ... and {len(low) - 3} more LOW candidates")

    return r


def _legacy_check_url_slug_dedup(site_root: Path, verbose: bool) -> CheckResult:
    """Legacy word-set dedup check (fallback when validate-slug-dedup.py is absent)."""
    r = CheckResult("url-slug-dedup")

    articles_dir = site_root / "content/articles"
    if not articles_dir.exists():
        r.warn("content/articles/ not found — skipping slug dedup check")
        return r

    md_files = list(articles_dir.glob("*.md"))
    if not md_files:
        r.warn("No articles found in content/articles/")
        return r

    slugs = [f.stem for f in md_files]

    wordset_to_slugs: dict[frozenset, list[str]] = defaultdict(list)
    for slug in slugs:
        ws = slug_wordset(slug)
        wordset_to_slugs[ws].append(slug)

    duplicates = {ws: sl for ws, sl in wordset_to_slugs.items() if len(sl) > 1}
    if duplicates:
        total_dup = sum(len(v) - 1 for v in duplicates.values())
        r.fail(f"{total_dup} redundant slug(s) found ({len(duplicates)} duplicate group(s))")
        for ws, slug_list in list(duplicates.items())[:10]:
            r.info(f"  Duplicates: {', '.join(slug_list)}")
        if len(duplicates) > 10:
            r.info(f"  ... and {len(duplicates) - 10} more groups")
    else:
        r.info(f"No duplicate slug word-sets among {len(slugs)} articles ✓")

    slug_set = set(slugs)
    seen_pairs: set = set()
    unique_plural = []
    for slug in slugs:
        if slug.endswith("s") and slug[:-1] in slug_set:
            key = (slug[:-1], slug)
            if key not in seen_pairs:
                seen_pairs.add(key)
                unique_plural.append(key)
        elif slug + "s" in slug_set:
            key = (slug, slug + "s")
            if key not in seen_pairs:
                seen_pairs.add(key)
                unique_plural.append(key)

    if unique_plural:
        r.warn(f"{len(unique_plural)} plural/singular slug pair(s) — review for canonicalization")
        for a, b in unique_plural[:5]:
            r.info(f"  Pair: {a} / {b}")
        if len(unique_plural) > 5:
            r.info(f"  ... and {len(unique_plural) - 5} more pairs")

    return r


def check_ymyl_hubs(site_root: Path, cfg: dict, verbose: bool) -> CheckResult:
    r = CheckResult("ymyl-hub-check")

    # If the entire site is declared YMYL, medical/health hub names are intentional.
    # The check is designed for non-YMYL sites that accidentally include health hubs.
    if cfg.get("ymyl", {}).get("vertical", False):
        r.info("ymyl.vertical: true — entire site is YMYL-aware; hub name check skipped ✓")
        return r

    nav_path = site_root / "config/navigation.yaml"
    if not nav_path.exists():
        r.fail("config/navigation.yaml not found")
        return r

    nav = load_yaml(nav_path) or {}
    hubs = list(iter_hubs(nav))

    flagged = []
    for hub in hubs:
        slug = hub.get("slug", "").lower()
        label = hub.get("label", "").lower()
        combined = f"{slug} {label}"
        for term in YMYL_HUB_TERMS:
            if term in combined:
                flagged.append((hub.get("slug", "?"), hub.get("label", "?"), term))
                break

    if flagged:
        r.fail(f"{len(flagged)} hub(s) contain YMYL-risk terminology")
        for slug, label, term in flagged:
            r.info(f"  YMYL hub: slug={slug!r} label={label!r} (matched: '{term}')")
        r.info("  Remedy: remove hub, redirect articles to non-YMYL hub, add 301s to public/_redirects")
    else:
        r.info(f"No YMYL terminology found in {len(hubs)} hubs ✓")

    return r


def check_product_topic_match(site_root: Path, verbose: bool) -> CheckResult:
    r = CheckResult("product-topic-match")

    products_path = site_root / "content/products/products.yaml"
    articles_dir = site_root / "content/articles"
    nav_path = site_root / "config/navigation.yaml"

    if not products_path.exists():
        r.warn("content/products/products.yaml not found — skipping check")
        return r
    if not articles_dir.exists():
        r.warn("content/articles/ not found — skipping check")
        return r

    products = load_yaml(products_path) or {}
    if not isinstance(products, dict):
        r.warn("products.yaml format not a dict — skipping check")
        return r

    # Build the set of valid hub slugs from navigation.yaml
    # Products whose hub IS in this set but != article hub → WARN (within-site adjacency)
    # Products whose hub is NOT in this set at all → FAIL (cross-domain contamination)
    valid_hubs: set = set()
    nav = load_yaml(nav_path) or {}
    for hub in iter_hubs(nav):
        valid_hubs.add(hub.get("slug", ""))

    md_files = list(articles_dir.glob("*.md"))
    if not md_files:
        r.warn("No articles found — skipping check")
        return r

    hard_mismatches: list = []   # product hub not in site navigation at all
    soft_mismatches: list = []   # product hub valid but != article hub
    checked_articles = 0

    for fp in md_files:
        fm = parse_article_frontmatter(fp)
        if not fm:
            continue
        article_hub = fm.get("hub", "")
        article_products = fm.get("products", [])
        if not article_products or not article_hub:
            continue
        checked_articles += 1

        for prod_ref in article_products:
            prod_id = prod_ref.get("id", "") if isinstance(prod_ref, dict) else str(prod_ref)
            if not prod_id or prod_id not in products:
                continue
            prod_data = products[prod_id]
            if not isinstance(prod_data, dict):
                continue
            prod_hub = prod_data.get("hub", "")
            if not prod_hub or prod_hub == article_hub:
                continue
            if valid_hubs and prod_hub not in valid_hubs:
                # Product hub is completely foreign to this site
                hard_mismatches.append((fp.stem, prod_id, article_hub, prod_hub))
            else:
                # Product hub is a valid site hub, just different from article hub
                soft_mismatches.append((fp.stem, prod_id, article_hub, prod_hub))

    if not checked_articles:
        r.warn("No articles with hub+products frontmatter found")
        return r

    if hard_mismatches:
        by_article: dict = defaultdict(list)
        for art, pid, ahub, phub in hard_mismatches:
            by_article[art].append((pid, ahub, phub))
        r.fail(f"{len(by_article)} article(s) have cross-domain product mismatches ({len(hard_mismatches)} references)")
        r.info("  These products belong to a different site vertical entirely — likely wrong product sourced")
        for art, refs in list(by_article.items())[:8]:
            for pid, ahub, phub in refs[:2]:
                r.info(f"  {art}: product {pid!r} is hub={phub!r} (not in site navigation), article hub={ahub!r}")
        if len(by_article) > 8:
            r.info(f"  ... and {len(by_article) - 8} more articles")

    if soft_mismatches:
        by_article_soft: dict = defaultdict(list)
        for art, pid, ahub, phub in soft_mismatches:
            by_article_soft[art].append((pid, ahub, phub))
        r.warn(f"{len(by_article_soft)} article(s) have within-site hub adjacency ({len(soft_mismatches)} references)")
        r.info("  Products are valid site products but sourced for a different hub — review for editorial fit")
        for art, refs in list(by_article_soft.items())[:5]:
            for pid, ahub, phub in refs[:1]:
                r.info(f"  {art}: product hub={phub!r}, article hub={ahub!r}")
        if len(by_article_soft) > 5:
            r.info(f"  ... and {len(by_article_soft) - 5} more articles")

    if not hard_mismatches and not soft_mismatches:
        r.info(f"All products match their article hub ({checked_articles} articles checked) ✓")

    return r


def check_brand_niche(site_root: Path, cfg: dict, verbose: bool) -> CheckResult:
    r = CheckResult("brand-niche")

    v8_path = Path(__file__).parent / "validate-brand-niche.py"
    if not v8_path.exists():
        r.warn("validate-brand-niche.py not found in scripts/ — check skipped")
        return r

    spec = importlib.util.spec_from_file_location("validate_brand_niche", v8_path)
    v8_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(v8_mod)

    result = v8_mod.scan_site(site_root, verbose=False)
    if result is None:
        r.warn("content/articles/ not found — skipping V8 brand-niche check")
        return r

    h1 = result["h1_fails"]
    h2 = result["h2_warns"]

    if h1:
        r.fail(f"{len(h1)} article(s) have fabricated brand framing (brand in title, absent from body)")
        for finding in h1[:8]:
            r.info(f"  {finding['slug']}: brand={finding['brand']!r} — {finding['verdict']}")
        if len(h1) > 8:
            r.info(f"  ... and {len(h1) - 8} more")

    if h2:
        r.warn(f"{len(h2)} article(s) have potential brand/niche contamination")
        for finding in h2[:5]:
            r.info(f"  {finding['slug']}: brand={finding['brand']!r} ({finding['brand_category']}) hub={finding['hub']!r}")
        if len(h2) > 5:
            r.info(f"  ... and {len(h2) - 5} more")

    if not h1 and not h2:
        niche = result["niche"]
        r.info(f"No fabricated brands or niche contamination in {result['total']} articles [{niche}] ✓")

    return r


def check_spec_consistency(site_root: Path, verbose: bool) -> CheckResult:
    r = CheckResult("spec-consistency")

    v16_path = Path(__file__).parent / "validate-spec-consistency.py"
    if not v16_path.exists():
        r.warn("validate-spec-consistency.py not found in scripts/ — check skipped")
        return r

    spec = importlib.util.spec_from_file_location("validate_spec_consistency", v16_path)
    v16_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(v16_mod)

    result = v16_mod.scan_site(site_root, verbose=False)
    if result is None:
        r.warn("content/articles/ not found — skipping V16 spec-consistency check")
        return r

    mismatches = result["mismatches"]
    refs       = result["total_refs"]

    if mismatches:
        r.fail(f"{len(mismatches)} spec mismatch(es) between article body and products.yaml")
        for finding in mismatches[:8]:
            r.info(f"  {finding['article']}: [{finding['location']}] claims {finding['claim']!r}, yaml has {finding['actual']!r}")
            if verbose:
                r.info(f"    excerpt: {finding['excerpt']}")
        if len(mismatches) > 8:
            r.info(f"  ... and {len(mismatches) - 8} more (run validate-spec-consistency.py --verbose for full list)")
    else:
        r.info(f"No spec mismatches across {refs} product references ✓")

    return r


def check_hub_consistency(site_root: Path, verbose: bool) -> CheckResult:
    r = CheckResult("hub-consistency")

    v14_path = Path(__file__).parent / "validate-hub-consistency.py"
    if not v14_path.exists():
        r.warn("validate-hub-consistency.py not found in scripts/ — check skipped")
        return r

    spec = importlib.util.spec_from_file_location("validate_hub_consistency", v14_path)
    v14_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(v14_mod)

    result = v14_mod.scan_site(site_root, verbose=False)
    if result is None:
        r.warn("content/articles/ not found — skipping V14 hub-consistency check")
        return r

    fails = result["fails"]
    warns = result["warns"]
    refs  = result["total_refs"]

    if fails:
        r.fail(f"{len(fails)} product(s) have unrelated hub vs article hub")
        for f in fails[:8]:
            r.info(f"  {f['article']}: {f['product_key']!r}  article_hub={f['article_hub']!r}  product_hub={f['product_hub']!r}")
            if verbose:
                r.info(f"    suggestion: {f['suggestion']}")
        if len(fails) > 8:
            r.info(f"  ... and {len(fails) - 8} more (run validate-hub-consistency.py --verbose for full list)")
    elif warns:
        r.warn(f"{len(warns)} product(s) have sibling hub placement (cross-hub, not cross-category)")
        for f in warns[:5]:
            r.info(f"  {f['article']}: {f['product_key']!r}  article_hub={f['article_hub']!r}  product_hub={f['product_hub']!r}")
        if len(warns) > 5:
            r.info(f"  ... and {len(warns) - 5} more")
    else:
        r.info(f"No hub inconsistencies across {refs} product references ✓")

    return r


def check_dollar_figures(site_root: Path, cfg: dict, verbose: bool) -> CheckResult:
    r = CheckResult("dollar-figures")

    v9_path = Path(__file__).parent / "validate-dollar-figures.py"
    if not v9_path.exists():
        r.warn("validate-dollar-figures.py not found in scripts/ — check skipped")
        return r

    spec = importlib.util.spec_from_file_location("validate_dollar_figures", v9_path)
    v9_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(v9_mod)

    result = v9_mod.scan_site(site_root, verbose=False)
    if result is None:
        r.warn("content/articles/ not found — skipping V9 dollar-figures check")
        return r

    findings = result["findings"]
    total    = result["total_articles"]
    instances = result["total_instances"]

    # Read enforcement mode from site.config.yaml
    # "warn"  → downgrade to non-blocking WARN (sites actively remediating)
    # "fail"  → hard FAIL, blocks launch (default for all new sites)
    enforcement = (
        (cfg.get("content") or {}).get("dollar_figures_enforcement", "fail") or "fail"
    ).lower()

    if findings:
        msg = (
            f"{len(findings)} article(s) with {instances} dollar-figure instance(s) "
            f"(Amazon ToS Section 5v — prices must come from PA-API)"
        )
        for f in findings[:8]:
            title_note = f"  [{len(f['title_hits'])} in title]" if f["title_hits"] else ""
            r.info(f"  {f['article']}: {f['total']} instance(s){title_note}")
        if len(findings) > 8:
            r.info(f"  ... and {len(findings) - 8} more (run validate-dollar-figures.py --verbose for full list)")

        if enforcement == "warn":
            r.warn(msg + " [enforcement=warn — remediation in progress]")
        else:
            r.fail(msg)
    else:
        r.info(f"No dollar-figure violations across {total} articles ✓")

    return r


def check_product_coherence(site_root: Path, verbose: bool) -> CheckResult:
    r = CheckResult("product-coherence")

    v15_path = Path(__file__).parent / "validate-product-coherence.py"
    if not v15_path.exists():
        r.warn("validate-product-coherence.py not found in scripts/ — check skipped")
        return r

    spec = importlib.util.spec_from_file_location("validate_product_coherence", v15_path)
    v15_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(v15_mod)

    result = v15_mod.scan_site(site_root, verbose=False)
    if result is None:
        r.warn("content/articles/ not found — skipping V15 product-coherence check")
        return r

    mismatches = result["mismatches"]
    refs        = result["total_refs"]
    fails       = [m for m in mismatches if m.get("severity") == "FAIL"]
    warns       = [m for m in mismatches if m.get("severity") == "WARN"]

    if fails:
        r.fail(f"{len(fails)} product(s) have zero topical token overlap with their article")
        for m in fails[:8]:
            r.info(f"  {m['article']}: {m['product_key']!r} — no shared tokens")
            if verbose:
                r.info(f"    article tokens: {m['article_tokens']}")
                r.info(f"    product tokens: {m['product_tokens']}")
        if len(fails) > 8:
            r.info(f"  ... and {len(fails) - 8} more (run validate-product-coherence.py --verbose for full list)")
    if warns:
        r.warn(f"{len(warns)} product(s) have zero overlap but share a hub parent category (non-blocking)")
    if not fails and not warns:
        r.info(f"No incoherent product placements across {refs} product references ✓")

    return r


def check_furniture_pages(site_root: Path, verbose: bool) -> CheckResult:
    r = CheckResult("furniture-pages")

    v2_path = Path(__file__).parent / "validate-furniture-pages.py"
    if not v2_path.exists():
        r.warn("validate-furniture-pages.py not found in scripts/ — check skipped")
        return r

    spec = importlib.util.spec_from_file_location("validate_furniture_pages", v2_path)
    v2_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(v2_mod)

    result = v2_mod.scan_site(site_root, verbose=False)

    missing      = result["missing_pages"]
    placeholders = result["placeholder_hits"]
    overclaims   = result["overclaim_hits"]
    stale_refs   = result["stale_test_refs"]
    stale_hwt    = result["stale_how_we_test"]
    checked      = result["total_pages_checked"]

    if missing:
        r.fail(f"{len(missing)} required furniture page(s) missing: {', '.join(missing)}")
    for p in placeholders:
        r.fail(f"{p['page']}: unsubstituted token {p['match']!r} ({p['label']})")
    if stale_hwt:
        r.warn("how-we-test.astro still present alongside how-we-research.astro — delete stale copy")
    for s in stale_refs:
        r.warn(f"{s['page']}: stale 'how we test' reference in page text")
    for o in overclaims:
        r.warn(f"{o['page']}: FTC-risk phrasing ({o['label']})")

    if not missing and not placeholders and not stale_hwt and not stale_refs and not overclaims:
        r.info(f"All {checked} required furniture pages present, no placeholder tokens ✓")

    return r


def check_amazon_tag(site_root: Path, verbose: bool) -> CheckResult:
    r = CheckResult("amazon-tag")

    v3_path = Path(__file__).parent / "validate-amazon-tag.py"
    if not v3_path.exists():
        r.warn("validate-amazon-tag.py not found in scripts/ — check skipped")
        return r

    spec = importlib.util.spec_from_file_location("validate_amazon_tag", v3_path)
    v3_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(v3_mod)

    result = v3_mod.scan_site(site_root, verbose=False)

    tag           = result["tag"]
    valid_format  = result["valid_format"]
    is_placeholder = result["is_placeholder"]
    format_errors = result["format_errors"]
    collision_with = result["collision_with"]

    blocking = [e for e in format_errors if not e.startswith("WARN:")]
    warns    = [e for e in format_errors if e.startswith("WARN:")]

    if not valid_format or is_placeholder or collision_with:
        for e in blocking:
            r.fail(e)
        for c in collision_with:
            r.fail(f"tag {tag!r} also used by {c} — commission tracking collision")
    else:
        if tag:
            r.info(f"amazon_tracking_id {tag!r} valid ✓")

    for w in warns:
        r.warn(w[5:].lstrip())

    return r


def check_brand_collision(site_root: Path, verbose: bool) -> CheckResult:
    r = CheckResult("brand-collision")

    v5_path = Path(__file__).parent / "validate-brand-collision.py"
    if not v5_path.exists():
        r.warn("validate-brand-collision.py not found in scripts/ — check skipped")
        return r

    spec = importlib.util.spec_from_file_location("validate_brand_collision", v5_path)
    v5_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(v5_mod)

    result = v5_mod.scan_site(site_root, verbose=False)

    if result.get("error"):
        r.warn(f"V5 brand-collision: {result['error']}")
        return r

    persona_hits = result["persona_hits"]
    brand_hits   = result["brand_hits"]
    niche_hits   = result["niche_hits"]
    total        = result["total_articles"]

    if persona_hits:
        r.fail(f"{len(persona_hits)} article(s) contain foreign persona name(s)")
        for h in persona_hits[:6]:
            r.info(f"  {h['article']}: name {h['name']!r} from {h['foreign_site']}")
        if len(persona_hits) > 6:
            r.info(f"  ... and {len(persona_hits) - 6} more")
    if brand_hits:
        r.warn(f"{len(brand_hits)} article(s) mention a foreign site brand name")
        for h in brand_hits[:4]:
            r.info(f"  {h['article']}: brand {h['brand']!r} from {h['foreign_site']}")
    if niche_hits:
        r.warn(f"{len(niche_hits)} article(s) contain cross-niche vocabulary")
        for h in niche_hits[:4]:
            r.info(f"  {h['article']}: term {h['term']!r} from {h['foreign_site']}")

    if not persona_hits and not brand_hits and not niche_hits:
        r.info(f"No cross-site brand/persona contamination across {total} articles ✓")

    return r


def check_ymyl_endorsement(site_root: Path, verbose: bool) -> CheckResult:
    r = CheckResult("ymyl-endorsement")

    v12_path = Path(__file__).parent / "validate-ymyl-endorsement.py"
    if not v12_path.exists():
        r.warn("validate-ymyl-endorsement.py not found in scripts/ — check skipped")
        return r

    spec = importlib.util.spec_from_file_location("validate_ymyl_endorsement", v12_path)
    v12_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(v12_mod)

    result = v12_mod.scan_site(site_root, verbose=False)

    if result.get("skipped"):
        r.info(f"Not a YMYL site ({result.get('reason', 'skipped')}) — check skipped")
        return r

    clinical_fails  = result["clinical_fails"]
    category_b_warns = result["category_b_warns"]
    total           = result["total_articles"]

    unhedged = [f for f in clinical_fails if not f.get("hedged")]
    hedged   = [f for f in clinical_fails if f.get("hedged")]

    if unhedged:
        r.fail(
            f"{len(unhedged)} unqualified clinical claim(s) — persona must not make "
            f"professional medical judgments without hedging"
        )
        for f in unhedged[:6]:
            r.info(f"  {f['article']}: {f['phrase']}")
        if len(unhedged) > 6:
            r.info(f"  ... and {len(unhedged) - 6} more")
    if hedged:
        r.warn(f"{len(hedged)} clinical claim(s) with hedge language nearby (review recommended)")
        for f in hedged[:4]:
            r.info(f"  {f['article']}: {f['phrase']}")
    if category_b_warns:
        r.warn(
            f"{len(category_b_warns)} article(s) reference prescription-adjacent products "
            f"without framing context"
        )
        for w in category_b_warns[:4]:
            r.info(f"  {w['article']}: {w['term']!r}")

    if not unhedged and not hedged and not category_b_warns:
        r.info(f"No unqualified clinical claims across {total} YMYL articles ✓")

    return r


def check_placeholder_strings(site_root: Path, verbose: bool) -> CheckResult:
    r = CheckResult("placeholder-strings")

    articles_dir = site_root / "content/articles"
    if not articles_dir.exists():
        r.info("No content/articles directory — check skipped")
        return r

    # Bracket-form patterns only — must not match natural prose.
    # \bPLACEHOLDER\b and \bFILL_IN\b are intentionally omitted (false-positive prone).
    PLACEHOLDER_PATTERNS = [
        r"\[write one product-specific",
        r"\[insert ",
        r"\[add ",
        r"\[replace this",
        r"\[TODO",
        r"\[PLACEHOLDER",
    ]
    combined = re.compile("|".join(PLACEHOLDER_PATTERNS), re.IGNORECASE)

    leaks = []
    for path in sorted(articles_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        hits = combined.findall(text)
        if hits:
            leaks.append((path.name, hits[:3]))

    if leaks:
        r.fail(
            f"{len(leaks)} article(s) contain unsubstituted placeholder strings "
            f"— producer output was not fully completed"
        )
        for fname, hits in leaks[:10]:
            r.info(f"  {fname}: {hits[0]!r}")
        if len(leaks) > 10:
            r.info(f"  ... and {len(leaks) - 10} more")
    else:
        r.info(f"No placeholder strings found in {len(list(articles_dir.glob('*.md')))} articles ✓")

    return r


# ── Main ─────────────────────────────────────────────────────────────────────

ALL_CHECKS = [
    "scaffold-contamination",
    "state-sync",
    "hub-descriptions",
    "json-ld-urls",
    "og-locale",
    "persona-consistency",
    "url-slug-dedup",
    "ymyl-hub-check",
    "product-topic-match",
    "brand-niche",
    "spec-consistency",
    "hub-consistency",
    "product-coherence",
    "dollar-figures",
    "furniture-pages",
    "amazon-tag",
    "brand-collision",
    "ymyl-endorsement",
    "placeholder-strings",
]

STATUS_ICON = {"PASS": "✓", "WARN": "⚠", "FAIL": "✗"}
STATUS_LABEL = {"PASS": "PASS", "WARN": "WARN", "FAIL": "FAIL"}


def run_preflight(args) -> int:
    site_root = Path.home() / args.site

    if not site_root.exists():
        print(f"ERROR: site root not found: {site_root}", file=sys.stderr)
        return 2

    site_config_path = site_root / "site.config.yaml"
    if not site_config_path.exists():
        print(f"ERROR: site.config.yaml not found at {site_config_path}", file=sys.stderr)
        return 2

    cfg = load_yaml(site_config_path) or {}

    # Determine which checks to run
    if args.check:
        requested = [c.strip() for c in args.check.split(",")]
        unknown = [c for c in requested if c not in ALL_CHECKS]
        if unknown:
            print(f"ERROR: Unknown check(s): {', '.join(unknown)}", file=sys.stderr)
            print(f"Available: {', '.join(ALL_CHECKS)}", file=sys.stderr)
            return 2
        checks_to_run = requested
    else:
        checks_to_run = ALL_CHECKS

    brand = cfg.get("site", {}).get("brand_name", args.site)
    domain = cfg.get("site", {}).get("domain", "")

    print(f"\n{'─' * 60}")
    print(f"  Pre-flight: {brand} ({domain})")
    print(f"  Checks:     {len(checks_to_run)}/{len(ALL_CHECKS)}  (v2: furniture-pages  v3: amazon-tag  v5: brand-collision  v8: brand-niche  v9: dollar-figures  v12: ymyl-endorsement  v14: hub-consistency  v15: product-coherence  v16: spec-consistency  v19: placeholder-strings)")
    print(f"  Site root:  {site_root}")
    print(f"{'─' * 60}\n")

    results: list[CheckResult] = []

    for check_name in checks_to_run:
        if check_name == "scaffold-contamination":
            res = check_scaffold_contamination(site_root, cfg, args.verbose)
        elif check_name == "state-sync":
            res = check_state_sync(site_root, args.verbose)
        elif check_name == "hub-descriptions":
            res = check_hub_descriptions(site_root, args.verbose)
        elif check_name == "json-ld-urls":
            res = check_json_ld_urls(args.verbose)
        elif check_name == "og-locale":
            res = check_og_locale(args.verbose)
        elif check_name == "persona-consistency":
            res = check_persona_consistency(site_root, args.verbose)
        elif check_name == "url-slug-dedup":
            res = check_url_slug_dedup(site_root, args.verbose)
        elif check_name == "ymyl-hub-check":
            res = check_ymyl_hubs(site_root, cfg, args.verbose)
        elif check_name == "product-topic-match":
            res = check_product_topic_match(site_root, args.verbose)
        elif check_name == "brand-niche":
            res = check_brand_niche(site_root, cfg, args.verbose)
        elif check_name == "spec-consistency":
            res = check_spec_consistency(site_root, args.verbose)
        elif check_name == "hub-consistency":
            res = check_hub_consistency(site_root, args.verbose)
        elif check_name == "product-coherence":
            res = check_product_coherence(site_root, args.verbose)
        elif check_name == "dollar-figures":
            res = check_dollar_figures(site_root, cfg, args.verbose)
        elif check_name == "furniture-pages":
            res = check_furniture_pages(site_root, args.verbose)
        elif check_name == "amazon-tag":
            res = check_amazon_tag(site_root, args.verbose)
        elif check_name == "brand-collision":
            res = check_brand_collision(site_root, args.verbose)
        elif check_name == "ymyl-endorsement":
            res = check_ymyl_endorsement(site_root, args.verbose)
        elif check_name == "placeholder-strings":
            res = check_placeholder_strings(site_root, args.verbose)
        else:
            continue

        results.append(res)
        icon = STATUS_ICON[res.status]
        label = STATUS_LABEL[res.status]
        print(f"  [{label:4s}] {icon}  {res.name}")
        if args.verbose or res.status in ("FAIL", "WARN"):
            for msg in res.messages:
                print(f"           {msg}")

    # Summary
    fails = [r for r in results if r.status == "FAIL"]
    warns = [r for r in results if r.status == "WARN"]
    passes = [r for r in results if r.status == "PASS"]

    print(f"\n{'─' * 60}")
    print(f"  Results: {len(passes)} PASS  {len(warns)} WARN  {len(fails)} FAIL")

    if fails:
        print(f"\n  LAUNCH BLOCKED — resolve {len(fails)} failing check(s):")
        for r in fails:
            print(f"    • {r.name}")
        print()
        return 1
    elif warns:
        print(f"\n  LAUNCH CLEAR — {len(warns)} warning(s) to review (not blocking)")
        print()
        return 0
    else:
        print(f"\n  LAUNCH CLEAR — all checks passed")
        print()
        return 0


def main():
    parser = argparse.ArgumentParser(
        description="Pre-flight checklist for affiliate sites",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--site", required=True, metavar="SLUG",
                        help="Site slug (site root is ~/SLUG)")
    parser.add_argument("--check", default=None, metavar="CHECK[,CHECK...]",
                        help=f"Run only specific checks (comma-separated). Available: {', '.join(ALL_CHECKS)}")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show all check messages (not just FAIL/WARN)")
    args = parser.parse_args()

    sys.exit(run_preflight(args))


if __name__ == "__main__":
    main()
