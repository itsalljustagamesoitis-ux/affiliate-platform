#!/usr/bin/env python3
"""
validate-ymyl-endorsement.py — V12 YMYL unqualified clinical claim validator
Affiliate Platform preflight suite.

Detects unqualified clinical/medical claim language in YMYL sites. The two
current YMYL personas are Margaret Chen (Better Hearing Hub, "not an audiologist")
and Linda Hoffmann (Four Ferns Care, "not a nurse/therapist"). These personas must
not make statements that sound like professional medical judgment.

Non-YMYL sites are skipped immediately with {"skipped": True, "reason": "not YMYL"}.

Two check categories:

  Category A — Unqualified clinical claim (FAIL severity):
      Phrases asserting medical efficacy or clinical outcomes in the persona's
      voice without hedging language. Examples: "will improve your hearing",
      "clinically proven", "audiologist-recommended" (as bare claim).
      If a qualifying phrase appears within 200 characters of the match, the
      severity is downgraded from FAIL to WARN (hedged=True).

  Category B — Specialized product without framing (WARN severity):
      Prescription-adjacent product/concept terms (bone conduction, prescription
      hearing aid, audiologist fitting, etc.) appearing in a general consumer
      buying guide without nearby hedge language. Always WARN, never FAIL.

Usage:
  python3 scripts/validate-ymyl-endorsement.py /path/to/site
  python3 scripts/validate-ymyl-endorsement.py /path/to/site --verbose
  python3 scripts/validate-ymyl-endorsement.py --all

Exit codes:
  0 = PASS or WARN only (no unhedged clinical claims)
  1 = FAIL (unhedged clinical claim found)
  2 = tool error (missing site dir, missing required files)
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import yaml

PLATFORM_ROOT = Path(__file__).parent.parent

# ── Category A — clinical claim patterns (FAIL before hedge check) ────────────
# Each entry: (pattern_re, label)
# Patterns are searched in article body (post-frontmatter).

_CAT_A_PATTERNS_RAW = [
    # Direct efficacy assertions
    (r"\bwill\s+improve\s+your\s+hearing\b",       "will improve your hearing"),
    (r"\bwill\s+restore\s+your\s+hearing\b",        "will restore your hearing"),
    (r"\bwill\s+help\s+you\s+hear\b",               "will help you hear"),
    # Treatment/cure language
    (r"\btreats?\s+(hearing\s+loss|tinnitus|loss)\b",  "treats hearing loss / tinnitus"),
    (r"\bcures?\s+(hearing|tinnitus|hearing\s+loss)\b", "cures hearing / tinnitus"),
    # Unqualified "clinically proven"
    (r"\bclinically\s+proven\b",                    "clinically proven"),
    # Professional recommendation as bare assertion
    (r"\baudiologist[- ]recommended\b",             "audiologist-recommended (bare claim)"),
    (r"\bdoctor[- ]recommended\b",                  "doctor-recommended (bare claim)"),
    (r"\bphysician[- ]recommended\b",               "physician-recommended (bare claim)"),
    # Severity classification (clinical territory)
    (r"\b(recommended|suitable)\s+for\s+severe\b",  "recommended/suitable for severe (severity classification)"),
    # Blanket efficacy in medical/symptom context
    (r"\bwill\s+reduce\s+your\s+(tinnitus|hearing|symptoms?|loss)\b",
     "will reduce your [symptom]"),
    (r"\bwill\s+eliminate\s+your\s+(tinnitus|hearing|symptoms?|loss)\b",
     "will eliminate your [symptom]"),
    # Audiogram / prescription proximity (strong clinical language)
    (r"\bprescription[-\s]grade\s+(performance|hearing|amplification)\b",
     "prescription-grade [performance/hearing] (unqualified)"),
]

# ── Category A — hedge phrases (within 200 chars, downgrade to WARN) ─────────

_HEDGE_PATTERNS_RAW = [
    r"\baccording\s+to\b",
    r"\bstudies?\s+show\b",
    r"\bresearch\s+suggests?\b",
    r"\bconsult\b",
    r"\baudiologists?\b",
    r"\bhealthcare\s+professional\b",
    r"\bmedical\s+advice\b",
    r"\bmay\s+vary\b",
    r"\bnot\s+a\s+substitute\b",
    r"\bmanufacturer\b",
    r"\bmanufacturer'?s?\b",
    r"\baccording\s+to\s+the\b",
    r"\bindividual\s+(results?\s+may|needs?\s+vary)\b",
]

# ── Category B — specialized product/concept terms (WARN) ────────────────────
# Checked for nearby hedge language. If no hedge near term → WARN.

_CAT_B_TERMS_RAW = [
    r"\bbone\s+conduction\b",
    r"\bprescription\s+hearing\s+aid\b",
    r"\bprescription[-\s]grade\b",
    r"\bhearing\s+instrument\s+specialist\b",
    r"\baudiologist\s+fitting\b",
]

# Hedge language for Category B (article-level check: any occurrence in article)
_CAT_B_ARTICLE_HEDGES_RAW = [
    r"\bconsult\b",
    r"\baudiologist\b",
    r"\bhealthcare\s+professional\b",
    r"\bmedical\s+advice\b",
    r"\bseek\s+(professional|medical)\b",
    r"\bprofessional\s+evaluation\b",
    r"\bhearing\s+test\b",
    r"\bhearing\s+exam\b",
]

# ── Pre-compile patterns ──────────────────────────────────────────────────────

CAT_A_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(raw, re.IGNORECASE), label)
    for raw, label in _CAT_A_PATTERNS_RAW
]

HEDGE_RE = re.compile(
    "(?:" + "|".join(_HEDGE_PATTERNS_RAW) + ")",
    re.IGNORECASE,
)

CAT_B_PATTERNS: list[re.Pattern] = [
    re.compile(raw, re.IGNORECASE)
    for raw in _CAT_B_TERMS_RAW
]

CAT_B_HEDGE_RE = re.compile(
    "(?:" + "|".join(_CAT_B_ARTICLE_HEDGES_RAW) + ")",
    re.IGNORECASE,
)

# ── Negation tokens — suppress Cat-A if negation precedes match within window ─
# Tokens within ~40 chars BEFORE a clinical-claim match indicate disclaimer
# context ("not intended to treat...", "cannot legally be marketed to treat...")
# rather than an endorsement. Double negation (rare) is accepted as a false-
# negative trade-off — noise suppression value outweighs the miss rate.

_NEGATION_TOKENS_RAW = [
    r"\bnot\b",
    r"\bn't\b",       # contractions: doesn't, isn't, can't, won't, etc.
    r"\bcannot\b",
    r"\bnever\b",
    r"\bwithout\b",
    r"\bno\b",        # "no evidence of", "no device is approved to..."
]

NEGATION_RE = re.compile(
    "(?:" + "|".join(_NEGATION_TOKENS_RAW) + ")",
    re.IGNORECASE,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_site_config(site_dir: Path) -> dict:
    cfg_path = site_dir / "site.config.yaml"
    if not cfg_path.exists():
        raise FileNotFoundError(f"site.config.yaml not found at {cfg_path}")
    with open(cfg_path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def is_ymyl(cfg: dict) -> bool:
    """
    Return True if site is YMYL.
    Checks: ymyl.vertical: true  OR  ymyl: true  (both forms).
    """
    ymyl_block = cfg.get("ymyl", {})
    if isinstance(ymyl_block, dict):
        return bool(ymyl_block.get("vertical", False))
    if isinstance(ymyl_block, bool):
        return ymyl_block
    return False


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


def hedge_nearby(text: str, match: re.Match, window: int = 200) -> bool:
    """Return True if a hedge phrase appears within `window` chars of match,
    OR if the match is on a Markdown heading line and a hedge phrase appears
    anywhere in the answer block that follows (text until the next heading)."""
    start = max(0, match.start() - window)
    end   = min(len(text), match.end() + window)
    region = text[start:end]
    if HEDGE_RE.search(region):
        return True

    # FAQ-block check: if the match falls on a Markdown heading line (starts with #),
    # expand search to the entire answer block following the heading.
    line_start = text.rfind('\n', 0, match.start()) + 1
    line_end   = text.find('\n', match.end())
    if line_end == -1:
        line_end = len(text)
    current_line = text[line_start:line_end]
    if current_line.lstrip().startswith('#'):
        next_heading = re.search(r'\n#{1,6} ', text[match.end():])
        block_end = (match.end() + next_heading.start()) if next_heading else len(text)
        block = text[match.end():block_end]
        if HEDGE_RE.search(block):
            return True

    return False


def negation_nearby(text: str, match: re.Match, window: int = 40) -> bool:
    """Return True if a negation token appears within `window` chars BEFORE match.

    Used to suppress Cat-A matches that are preceded by clear negation/disclaimer
    language, e.g. "not intended to treat hearing loss" fires on 'treat hearing
    loss' but the preceding 'not' confirms this is a disclaimer, not an endorsement.
    Window of 40 chars covers 3–6 English tokens, sufficient for the common patterns
    without over-suppressing genuinely distant negations.
    """
    start = max(0, match.start() - window)
    region = text[start:match.start()]
    return bool(NEGATION_RE.search(region))


def get_context(text: str, match: re.Match, window: int = 100) -> str:
    """Return a short surrounding context string for a regex match."""
    start = max(0, match.start() - window)
    end   = min(len(text), match.end() + window)
    snippet = text[start:end].replace("\n", " ").strip()
    if start > 0:
        snippet = "…" + snippet
    if end < len(text):
        snippet = snippet + "…"
    return snippet


# ── Core scan ─────────────────────────────────────────────────────────────────

def scan_site(site_root: Path, verbose: bool = False) -> dict:
    """
    Scan all articles in site_root/content/articles/ for YMYL clinical claim
    violations. Returns findings dict.

    If site is not YMYL, returns {"skipped": True, "reason": "not YMYL"}.
    """
    try:
        cfg = load_site_config(site_root)
    except FileNotFoundError:
        return {"skipped": True, "reason": "site.config.yaml not found"}

    ymyl_vertical = is_ymyl(cfg)
    if not ymyl_vertical:
        return {"skipped": True, "reason": "not YMYL"}

    articles_dir = site_root / "content" / "articles"
    if not articles_dir.exists():
        return {
            "skipped": False,
            "reason": "",
            "clinical_fails": [],
            "category_b_warns": [],
            "total_articles": 0,
            "ymyl_vertical": ymyl_vertical,
        }

    clinical_fails = []
    category_b_warns = []
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

        # ── Category A: clinical claim patterns ──────────────────────────────
        for pattern, label in CAT_A_PATTERNS:
            for m in pattern.finditer(body):
                # Suppress if a negation token immediately precedes the match —
                # disclaimer phrasing ("not intended to treat...") is not an endorsement.
                if negation_nearby(body, m):
                    break
                hedged = hedge_nearby(body, m)
                clinical_fails.append({
                    "article": article_name,
                    "phrase": label,
                    "match": m.group(0),
                    "context": get_context(body, m),
                    "hedged": hedged,
                })
                # Report only first occurrence per pattern per article to avoid noise
                break

        # ── Category B: specialized product terms ─────────────────────────────
        # Article-level hedge check: if the article contains ANY hedge phrase
        # near the matched term is unnecessary — spec says article-level check.
        article_has_hedge = bool(CAT_B_HEDGE_RE.search(body))

        for pat in CAT_B_PATTERNS:
            m = pat.search(body)
            if m:
                category_b_warns.append({
                    "article": article_name,
                    "term": m.group(0).lower(),
                    "has_hedge": article_has_hedge,
                })
                # One entry per pattern per article
                continue

    return {
        "skipped": False,
        "reason": "",
        "clinical_fails": clinical_fails,
        "category_b_warns": category_b_warns,
        "total_articles": total_articles,
        "ymyl_vertical": ymyl_vertical,
    }


# ── Output ────────────────────────────────────────────────────────────────────

def print_site_report(result: dict, site_slug: str, verbose: bool = False):
    if result.get("skipped"):
        print(f"  SKIP {site_slug} — {result.get('reason', 'not YMYL')}")
        return

    clinical_fails = result["clinical_fails"]
    category_b_warns = result["category_b_warns"]
    total = result["total_articles"]

    hard_fails = [f for f in clinical_fails if not f["hedged"]]
    soft_warns = [f for f in clinical_fails if f["hedged"]]

    any_fail   = bool(hard_fails)
    any_warn   = bool(soft_warns) or bool(category_b_warns)
    total_issues = len(clinical_fails) + len(category_b_warns)

    status = "FAIL" if any_fail else ("WARN" if any_warn else "PASS")
    status_label = {"FAIL": "❌ FAIL", "WARN": "⚠  WARN", "PASS": "✓  PASS"}[status]

    print(f"\n{'=' * 70}")
    print(f"{status_label}  {site_slug}  [YMYL]  ({total} articles, {total_issues} issues)")
    print(f"{'=' * 70}")

    if not total_issues:
        if verbose:
            print("  No unqualified clinical claims or unframed prescription-adjacent terms.")
        return

    if hard_fails:
        print(f"\n  CATEGORY A — UNQUALIFIED CLINICAL CLAIM ({len(hard_fails)}) — FAIL")
        print(f"  {'ARTICLE':<50} PHRASE")
        print(f"  {'-' * 90}")
        for f in hard_fails:
            print(f"  {f['article']:<50} {f['phrase']}")
            if verbose:
                print(f"    Match:   {f['match']!r}")
                print(f"    Context: {f['context']}")

    if soft_warns:
        print(f"\n  CATEGORY A — HEDGED CLINICAL CLAIM ({len(soft_warns)}) — WARN")
        print(f"  {'ARTICLE':<50} PHRASE")
        print(f"  {'-' * 90}")
        for f in soft_warns:
            print(f"  {f['article']:<50} {f['phrase']}  [hedged]")
            if verbose:
                print(f"    Match:   {f['match']!r}")
                print(f"    Context: {f['context']}")

    if category_b_warns:
        print(f"\n  CATEGORY B — SPECIALIZED PRODUCT WITHOUT FRAMING ({len(category_b_warns)}) — WARN")
        print(f"  {'ARTICLE':<50} {'TERM':<35} HEDGE?")
        print(f"  {'-' * 90}")
        for w in category_b_warns:
            hedge_note = "yes" if w["has_hedge"] else "NO — add consult/audiologist framing"
            print(f"  {w['article']:<50} {w['term']:<35} {hedge_note}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="V12 YMYL unqualified clinical claim validator"
    )
    parser.add_argument(
        "site_dir",
        nargs="?",
        help="Path to site directory (omit if using --all)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Scan all YMYL sites listed in portfolio.yaml",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show full match context for each finding",
    )
    args = parser.parse_args()

    if not args.all and not args.site_dir:
        parser.print_help()
        sys.exit(2)

    if args.all:
        portfolio_path = PLATFORM_ROOT / "portfolio.yaml"
        if not portfolio_path.exists():
            print(f"ERROR: portfolio.yaml not found at {portfolio_path}", file=sys.stderr)
            sys.exit(2)
        with open(portfolio_path, encoding="utf-8") as f:
            portfolio = yaml.safe_load(f) or {}

        sites = portfolio.get("sites", [])
        parent_dir = portfolio_path.parent.parent
        site_dirs = [parent_dir / s["slug"] for s in sites]
    else:
        site_dirs = [Path(args.site_dir).resolve()]

    any_fail = False
    summary_rows = []

    for site_dir in site_dirs:
        if not site_dir.exists():
            print(f"  SKIP {site_dir.name} — directory not found")
            continue

        try:
            result = scan_site(site_dir, verbose=args.verbose)
        except Exception as e:
            print(f"  ERROR {site_dir.name}: {e}", file=sys.stderr)
            continue

        if result is None:
            continue

        if result.get("skipped"):
            if args.verbose:
                print(f"  SKIP {site_dir.name} — {result.get('reason', 'not YMYL')}")
            continue

        print_site_report(result, site_dir.name, verbose=args.verbose)

        clinical_fails = result["clinical_fails"]
        category_b_warns = result["category_b_warns"]
        hard_fails = [f for f in clinical_fails if not f["hedged"]]
        soft_warns = [f for f in clinical_fails if f["hedged"]]

        any_fail_this = bool(hard_fails)
        if any_fail_this:
            any_fail = True

        status = "FAIL" if hard_fails else ("WARN" if (soft_warns or category_b_warns) else "PASS")
        summary_rows.append((
            site_dir.name,
            result["total_articles"],
            len(hard_fails),
            len(soft_warns),
            len(category_b_warns),
            status,
        ))

    if len(summary_rows) > 1:
        print(f"\n\n{'=' * 70}")
        print("PORTFOLIO SUMMARY — YMYL clinical claim validator")
        print(f"{'=' * 70}")
        print(f"  {'SITE':<35} {'ARTS':>5} {'A-FAIL':>7} {'A-WARN':>7} {'B-WARN':>7}  STATUS")
        print(f"  {'-' * 70}")
        for slug, total, af, aw, bw, status in summary_rows:
            icon = "❌" if status == "FAIL" else ("⚠ " if status == "WARN" else "✓ ")
            print(f"  {slug:<35} {total:>5} {af:>7} {aw:>7} {bw:>7}  {icon} {status}")
        total_arts = sum(r[1] for r in summary_rows)
        total_af   = sum(r[2] for r in summary_rows)
        total_aw   = sum(r[3] for r in summary_rows)
        total_bw   = sum(r[4] for r in summary_rows)
        print(f"  {'TOTAL':<35} {total_arts:>5} {total_af:>7} {total_aw:>7} {total_bw:>7}")

    sys.exit(1 if any_fail else 0)


if __name__ == "__main__":
    main()
