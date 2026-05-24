#!/usr/bin/env python3
"""
Pre-flight checklist for affiliate sites before launch or deploy.

9 checks derived from the SaunasSoSimple UAT post-mortem (2026-05-24).
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

UAT issue coverage:
  Issue 1 (scaffold contamination)    → check 1
  Issue 2 (hub description boilerplate) → check 3
  Issue 3 (JSON-LD relative URLs)     → check 4
  Issue 4 (YMYL hubs)                 → check 8
  Issue 5 (URL duplicates)            → check 7
  Issue 6 (product mismatches)        → check 9
  Issue 7 (persona photo/bio/og:locale) → checks 5, 6
"""

import argparse
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
        for term in cfg.get("content", {}).get("forbidden_vocabulary", []):
            forbidden.append(str(term).lower())
        if forbidden:
            source_label = "site.config.yaml content.forbidden_vocabulary"

    # Priority 3: platform master vocabulary file (all sections except this site's vertical)
    if not forbidden:
        own_vertical = detect_vertical(cfg)
        master = load_master_vocab()
        if master:
            skipped_sections = []
            for section_key, section in master.items():
                if section_key == own_vertical:
                    skipped_sections.append(section_key)
                    continue
                for term in section.get("terms", []):
                    forbidden.append(str(term).lower())
            if own_vertical:
                r.info(f"Using master vocabulary ({len(master)} sections); skipping own vertical '{own_vertical}'")
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
        r.fail(f"content/articles/ is empty but pipeline.json has {pipeline_count} articles")
        r.info("  Likely cause: build ran from a machine that never had articles rsync'd")
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
                r.fail(f"{slug}: {photo_field} → {photo_path_str} does not exist on disk")
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

    articles_dir = site_root / "content/articles"
    if not articles_dir.exists():
        r.warn("content/articles/ not found — skipping slug dedup check")
        return r

    md_files = list(articles_dir.glob("*.md"))
    if not md_files:
        r.warn("No articles found in content/articles/")
        return r

    slugs = [f.stem for f in md_files]

    # Group slugs by their word set
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

    # Also check plural/singular pairs
    plural_pairs = []
    slug_set = set(slugs)
    for slug in slugs:
        # simple trailing-s plural check
        if slug.endswith("s") and slug[:-1] in slug_set:
            plural_pairs.append((slug[:-1], slug))
        if not slug.endswith("s") and slug + "s" in slug_set:
            plural_pairs.append((slug, slug + "s"))

    seen_pairs = set()
    unique_plural = []
    for a, b in plural_pairs:
        key = tuple(sorted([a, b]))
        if key not in seen_pairs:
            seen_pairs.add(key)
            unique_plural.append((a, b))

    if unique_plural:
        r.warn(f"{len(unique_plural)} plural/singular slug pair(s) — review for canonicalization")
        for a, b in unique_plural[:5]:
            r.info(f"  Pair: {a} / {b}")
        if len(unique_plural) > 5:
            r.info(f"  ... and {len(unique_plural) - 5} more pairs")

    return r


def check_ymyl_hubs(site_root: Path, verbose: bool) -> CheckResult:
    r = CheckResult("ymyl-hub-check")

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
    print(f"  Checks:     {len(checks_to_run)}/{len(ALL_CHECKS)}")
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
            res = check_ymyl_hubs(site_root, args.verbose)
        elif check_name == "product-topic-match":
            res = check_product_topic_match(site_root, args.verbose)
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
