#!/usr/bin/env python3
"""
validate-brand-collision.py — V5 cross-site brand/persona collision validator
Affiliate Platform preflight suite.

Detects three classes of cross-site vocabulary contamination where one site's
identifiers have leaked into another site's article content:

  C1 PERSONA NAME HIT — A foreign persona's name (name_used or first name from
      name_formal) appears in the article body of a different site. The original
      contamination class: "from a gardener who actually uses them" (Wendy) in
      OHT and TCD hub.astro files.
      Severity: FAIL

  C2 BRAND NAME HIT — A foreign site's brand_name appears in an article body
      at another site. Often a legitimate cross-mention (product review), but
      worth flagging for review.
      Severity: WARN

  C3 NICHE TERM HIT — A foreign site's distinctive niche term (e.g. "sauna",
      "hearing aid") appears in an article whose own site niche is clearly
      incompatible (e.g. "sauna" on a camera site).
      Severity: WARN

Usage:
  python3 scripts/validate-brand-collision.py /path/to/site
  python3 scripts/validate-brand-collision.py --all            (all sites via portfolio.yaml)
  python3 scripts/validate-brand-collision.py --all --verbose
  python3 scripts/validate-brand-collision.py /path/to/site --verbose

Exit codes:
  0 = all checks PASS or WARN only
  1 = one or more FAIL (persona name collision confirmed)
  2 = tool error (missing site dir, missing required files)
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import yaml

# ── Stop words for niche term extraction ──────────────────────────────────────

NICHE_STOP_WORDS = {
    "of", "for", "the", "and", "or", "a", "an", "in", "on", "at", "to",
    "by", "with", "from", "into", "about", "over", "under", "between",
    "through", "during", "including", "products", "equipment", "devices",
    "gear", "tools", "items", "accessories", "guide", "guides",
}

PLATFORM_ROOT = Path(__file__).parent.parent


# ── Registry helpers ──────────────────────────────────────────────────────────

def load_site_config(site_dir: Path) -> dict:
    cfg_path = site_dir / "site.config.yaml"
    if not cfg_path.exists():
        raise FileNotFoundError(f"site.config.yaml not found at {cfg_path}")
    with open(cfg_path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_persona_names(site_dir: Path, persona_slug: str) -> tuple[str, str]:
    """
    Return (name_used, first_name_from_formal) for the given persona slug.
    Searches config/personas/<slug>.yaml.
    Falls back to (persona_slug, persona_slug) if file not found.
    """
    personas_dir = site_dir / "config" / "personas"
    persona_path = personas_dir / f"{persona_slug}.yaml"
    if not persona_path.exists():
        # Try any YAML in personas dir
        if personas_dir.exists():
            yamls = list(personas_dir.glob("*.yaml"))
            if yamls:
                persona_path = yamls[0]
            else:
                return persona_slug, persona_slug
        else:
            return persona_slug, persona_slug
    try:
        with open(persona_path, encoding="utf-8") as f:
            persona = yaml.safe_load(f) or {}
        name_used = persona.get("name_used", persona_slug)
        name_formal = persona.get("name_formal", "")
        first_name = name_formal.split()[0] if name_formal else name_used
        return name_used, first_name
    except Exception:
        return persona_slug, persona_slug


def extract_niche_terms(niche: str) -> list[str]:
    """
    Extract 2-4 content-distinctive words from a niche string.
    Filters stop words, keeps multi-character meaningful tokens.
    """
    words = re.split(r"[\s,/]+", niche.lower())
    terms = [w for w in words if w and w not in NICHE_STOP_WORDS and len(w) >= 3]
    # Also try common 2-word phrases: keep pairs for meaningful compound terms
    # e.g. "hearing aids" → add as a 2-token phrase too
    phrases = []
    for i in range(len(terms) - 1):
        pair = f"{terms[i]} {terms[i + 1]}"
        phrases.append(pair)
    return terms[:4] + phrases[:2]


def build_registry(portfolio_path: Path) -> list[dict]:
    """
    Build a list of site identifier dicts from all sites in portfolio.yaml.
    Each entry: {slug, brand_name, persona_name_used, persona_first_name, niche, niche_terms, site_dir}
    Sites whose directory does not exist on disk are skipped.
    """
    with open(portfolio_path, encoding="utf-8") as f:
        portfolio = yaml.safe_load(f) or {}

    sites = portfolio.get("sites", [])
    parent_dir = portfolio_path.parent.parent  # ~/affiliate-platform/../ = ~/

    registry = []
    for site_entry in sites:
        slug = site_entry.get("slug", "")
        persona_slug = site_entry.get("persona", slug)
        site_dir = parent_dir / slug

        if not site_dir.exists():
            continue

        try:
            cfg = load_site_config(site_dir)
        except FileNotFoundError:
            continue

        brand_name = cfg.get("site", {}).get("brand_name", slug)
        niche = cfg.get("site", {}).get("niche", "")
        name_used, first_name = load_persona_names(site_dir, persona_slug)
        niche_terms = extract_niche_terms(niche) if niche else []

        registry.append({
            "slug": slug,
            "brand_name": brand_name,
            "persona_name_used": name_used,
            "persona_first_name": first_name,
            "niche": niche.lower(),
            "niche_terms": niche_terms,
            "site_dir": site_dir,
        })

    return registry


# ── Content helpers ───────────────────────────────────────────────────────────

def extract_frontmatter(raw: str) -> tuple[dict | None, str]:
    """Strip YAML frontmatter and return (frontmatter_dict, body_text)."""
    m = re.match(r"^---\n([\s\S]*?)\n---\s*\n?", raw)
    if not m:
        return None, raw
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        fm = {}
    body = raw[m.end():]
    return fm, body


def niche_compatible(own_niche: str, foreign_niche: str) -> bool:
    """
    Return True if the own_niche already includes or overlaps the foreign niche
    (meaning a hit is NOT contamination — it's within-scope).
    """
    own = own_niche.lower()
    foreign = foreign_niche.lower()
    # Extract key terms from the foreign niche and check if they're in own niche
    foreign_terms = [w for w in re.split(r"\s+", foreign) if w and w not in NICHE_STOP_WORDS]
    overlap = sum(1 for t in foreign_terms if t in own)
    if overlap >= 1:
        return True
    return False


def get_context(text: str, match: re.Match, window: int = 80) -> str:
    """Return a short surrounding context string for a regex match."""
    start = max(0, match.start() - window)
    end = min(len(text), match.end() + window)
    snippet = text[start:end].replace("\n", " ").strip()
    if start > 0:
        snippet = "…" + snippet
    if end < len(text):
        snippet = snippet + "…"
    return snippet


# ── Pre-compiled regex builder ────────────────────────────────────────────────

def compile_foreign_patterns(
    registry: list[dict],
    own_slug: str,
    own_persona_names: set[str] | None = None,
) -> list[dict]:
    """
    For all registry entries that are NOT the own site, compile regex patterns.
    Returns list of dicts: {slug, brand_name, persona_name_used, persona_first_name,
                             niche, niche_terms, persona_re, brand_re, niche_res}

    own_persona_names: lowercase set of own-site persona name tokens. Any foreign
    persona name that matches an own-persona name token is excluded from the C1
    scan — two sites sharing a common first name (e.g. both named "Dan") would
    otherwise produce guaranteed false positives on every persona mention.
    """
    if own_persona_names is None:
        # Fallback: derive from registry (works when own site is in portfolio.yaml)
        own_entry = next((e for e in registry if e["slug"] == own_slug), None)
        own_persona_names = set()
        if own_entry:
            own_persona_names.add(own_entry.get("persona_name_used", "").lower())
            own_persona_names.add(own_entry.get("persona_first_name", "").lower())
        own_persona_names.discard("")

    compiled = []
    for entry in registry:
        if entry["slug"] == own_slug:
            continue

        persona_names = set()
        persona_names.add(entry["persona_name_used"])
        persona_names.add(entry["persona_first_name"])
        persona_names.discard("")
        # Exclude foreign names that match the own persona to prevent false positives
        persona_names = {n for n in persona_names if n.lower() not in own_persona_names}

        persona_re = re.compile(
            r"\b(" + "|".join(re.escape(n) for n in sorted(persona_names, key=len, reverse=True)) + r")\b",
            re.IGNORECASE,
        ) if persona_names else None

        brand_re = re.compile(
            r"\b" + re.escape(entry["brand_name"]) + r"\b",
            re.IGNORECASE,
        ) if entry["brand_name"] else None

        niche_res = []
        for term in entry["niche_terms"]:
            if len(term.split()) > 1:
                # Multi-word: use simple re.escape, word boundary at start/end only
                pat = re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)
            else:
                pat = re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)
            niche_res.append((term, pat))

        compiled.append({
            **entry,
            "persona_re": persona_re,
            "brand_re": brand_re,
            "niche_res": niche_res,
        })

    return compiled


# ── Core scan ─────────────────────────────────────────────────────────────────

def scan_site(site_root: Path, verbose: bool = False, registry: list[dict] | None = None) -> dict:
    """
    Scan all articles in site_root/content/articles/ for cross-site identifier
    contamination. Returns findings dict.

    registry: optional pre-built registry (list of dicts from build_registry).
              If None, the function builds its own from portfolio.yaml. Callers
              that scan multiple sites should build the registry once and pass it in.
    """
    articles_dir = site_root / "content" / "articles"
    if not articles_dir.exists():
        return None

    try:
        cfg = load_site_config(site_root)
    except FileNotFoundError:
        return None

    own_slug = site_root.name
    own_brand = cfg.get("site", {}).get("brand_name", own_slug)
    own_niche = cfg.get("site", {}).get("niche", "").lower()

    # Read own persona names directly from the site (don't rely on portfolio.yaml
    # presence — sites under active cleanup may not yet be listed there).
    own_persona_slug = cfg.get("persona", own_slug)
    own_name_used, own_first_name = load_persona_names(site_root, own_persona_slug)
    own_persona_names: set[str] = {own_name_used.lower(), own_first_name.lower()}
    own_persona_names.discard("")

    # Build registry if caller didn't supply one
    if registry is None:
        portfolio_path = PLATFORM_ROOT / "portfolio.yaml"
        if not portfolio_path.exists():
            return {
                "persona_hits": [],
                "brand_hits": [],
                "niche_hits": [],
                "total_articles": 0,
                "foreign_registry_size": 0,
                "error": "portfolio.yaml not found",
            }
        registry = build_registry(portfolio_path)

    foreign_patterns = compile_foreign_patterns(registry, own_slug, own_persona_names)

    persona_hits = []
    brand_hits = []
    niche_hits = []
    total_articles = 0

    for fname in sorted(os.listdir(articles_dir)):
        if not fname.endswith(".md"):
            continue
        total_articles += 1
        article_name = fname[:-3]

        try:
            raw = (articles_dir / fname).read_text(encoding="utf-8")
        except Exception:
            continue

        _fm, body = extract_frontmatter(raw)
        if not body.strip():
            continue

        for entry in foreign_patterns:
            foreign_slug = entry["slug"]
            foreign_niche = entry["niche"]

            # C1: Persona name — FAIL
            if entry["persona_re"]:
                m = entry["persona_re"].search(body)
                if m:
                    persona_hits.append({
                        "article": article_name,
                        "foreign_site": foreign_slug,
                        "name": m.group(0),
                        "context": get_context(body, m),
                    })

            # C2: Brand name — WARN (only if it doesn't match own brand)
            if entry["brand_re"]:
                m = entry["brand_re"].search(body)
                if m and entry["brand_name"].lower() != own_brand.lower():
                    brand_hits.append({
                        "article": article_name,
                        "foreign_site": foreign_slug,
                        "brand": entry["brand_name"],
                    })

            # C3: Niche terms — WARN (skip if own niche already covers the foreign niche)
            if not niche_compatible(own_niche, foreign_niche):
                for term, pat in entry["niche_res"]:
                    if len(term) < 4:
                        continue  # Skip very short terms (too many false positives)
                    m = pat.search(body)
                    if m:
                        niche_hits.append({
                            "article": article_name,
                            "foreign_site": foreign_slug,
                            "term": term,
                        })
                        break  # One niche hit per foreign site per article is enough

    return {
        "persona_hits": persona_hits,
        "brand_hits": brand_hits,
        "niche_hits": niche_hits,
        "total_articles": total_articles,
        "foreign_registry_size": len(foreign_patterns),
    }


# ── Output ────────────────────────────────────────────────────────────────────

def print_site_report(result: dict, site_slug: str, verbose: bool = False):
    persona_hits = result["persona_hits"]
    brand_hits   = result["brand_hits"]
    niche_hits   = result["niche_hits"]
    total        = result["total_articles"]
    reg_size     = result["foreign_registry_size"]

    total_issues = len(persona_hits) + len(brand_hits) + len(niche_hits)
    status = "FAIL" if persona_hits else ("WARN" if (brand_hits or niche_hits) else "PASS")
    status_label = {"FAIL": "❌ FAIL", "WARN": "⚠  WARN", "PASS": "✓  PASS"}[status]

    print(f"\n{'=' * 70}")
    print(f"{status_label}  {site_slug}  ({total} articles, {reg_size} foreign sites, {total_issues} issues)")
    print(f"{'=' * 70}")

    if not total_issues:
        if verbose:
            print("  No cross-site persona, brand, or niche contamination detected.")
        return

    if persona_hits:
        print(f"\n  C1 PERSONA NAME COLLISION ({len(persona_hits)}) — FAIL")
        print(f"  {'ARTICLE':<50} {'FOREIGN SITE':<25} NAME")
        print(f"  {'-' * 90}")
        for h in persona_hits:
            print(f"  {h['article']:<50} {h['foreign_site']:<25} {h['name']}")
            if verbose:
                print(f"    Context: {h['context']}")

    if brand_hits:
        print(f"\n  C2 BRAND NAME IN FOREIGN CONTENT ({len(brand_hits)}) — WARN")
        print(f"  {'ARTICLE':<50} {'FOREIGN SITE':<25} BRAND")
        print(f"  {'-' * 90}")
        for h in brand_hits:
            print(f"  {h['article']:<50} {h['foreign_site']:<25} {h['brand']}")

    if niche_hits:
        print(f"\n  C3 FOREIGN NICHE TERM ({len(niche_hits)}) — WARN")
        print(f"  {'ARTICLE':<50} {'FOREIGN SITE':<25} TERM")
        print(f"  {'-' * 90}")
        for h in niche_hits:
            print(f"  {h['article']:<50} {h['foreign_site']:<25} {h['term']}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="V5 cross-site brand/persona collision validator"
    )
    parser.add_argument(
        "site_dir",
        nargs="?",
        help="Path to site directory (omit if using --all)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Scan all sites listed in portfolio.yaml",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show full details for each finding",
    )
    args = parser.parse_args()

    if not args.all and not args.site_dir:
        parser.print_help()
        sys.exit(2)

    portfolio_path = PLATFORM_ROOT / "portfolio.yaml"
    if not portfolio_path.exists():
        print(f"ERROR: portfolio.yaml not found at {portfolio_path}", file=sys.stderr)
        sys.exit(2)

    # Build registry once for all scans
    registry = build_registry(portfolio_path)

    if args.all:
        parent_dir = portfolio_path.parent.parent
        with open(portfolio_path, encoding="utf-8") as f:
            portfolio = yaml.safe_load(f) or {}
        site_dirs = [parent_dir / s["slug"] for s in portfolio.get("sites", [])]
    else:
        site_dirs = [Path(args.site_dir).resolve()]

    any_fail = False
    summary_rows = []

    for site_dir in site_dirs:
        if not site_dir.exists():
            print(f"  SKIP {site_dir.name} — directory not found")
            continue
        articles_dir = site_dir / "content" / "articles"
        if not articles_dir.exists():
            print(f"  SKIP {site_dir.name} — no content/articles/ directory")
            continue

        result = scan_site(site_dir, verbose=args.verbose, registry=registry)
        if result is None:
            continue

        print_site_report(result, site_dir.name, verbose=args.verbose)

        p_count = len(result["persona_hits"])
        b_count = len(result["brand_hits"])
        n_count = len(result["niche_hits"])
        status = "FAIL" if p_count else ("WARN" if (b_count or n_count) else "PASS")
        if p_count:
            any_fail = True
        summary_rows.append((site_dir.name, result["total_articles"], p_count, b_count, n_count, status))

    if len(summary_rows) > 1:
        print(f"\n\n{'=' * 70}")
        print("PORTFOLIO SUMMARY — cross-site collision")
        print(f"{'=' * 70}")
        print(f"  {'SITE':<35} {'ARTS':>5} {'C1':>4} {'C2':>4} {'C3':>4}  STATUS")
        print(f"  {'-' * 65}")
        for slug, total, pc, bc, nc, status in summary_rows:
            icon = "❌" if status == "FAIL" else ("⚠ " if status == "WARN" else "✓ ")
            print(f"  {slug:<35} {total:>5} {pc:>4} {bc:>4} {nc:>4}  {icon} {status}")
        total_arts = sum(r[1] for r in summary_rows)
        total_pc   = sum(r[2] for r in summary_rows)
        total_bc   = sum(r[3] for r in summary_rows)
        total_nc   = sum(r[4] for r in summary_rows)
        print(f"  {'TOTAL':<35} {total_arts:>5} {total_pc:>4} {total_bc:>4} {total_nc:>4}")

    sys.exit(1 if any_fail else 0)


if __name__ == "__main__":
    main()
