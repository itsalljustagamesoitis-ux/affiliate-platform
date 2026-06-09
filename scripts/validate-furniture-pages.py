#!/usr/bin/env python3
"""
validate-furniture-pages.py — V2 furniture-page validator
Affiliate Platform preflight Check 15.

Validates site "furniture pages" (static non-article pages in src/pages/) for:

  1. PAGE EXISTENCE — checks that all required pages are present.
     Missing pages → FAIL (one FAIL per missing page).
     Severity: FAIL

  2. PLACEHOLDER TOKENS — scans each furniture page for unsubstituted template
     tokens: {{DOUBLE_BRACE}} mustache-style, "Lorem ipsum", "PLACEHOLDER".
     Does NOT flag valid Astro template syntax like ${cfg.site.brand_name}.
     Severity: FAIL

  3. OVERCLAIM LANGUAGE — scans extracted static text (frontmatter stripped,
     JSX expressions stripped, HTML tags stripped) for FTC-risk first-person
     testing claims identical to the HARD_PATTERNS in validate-furniture-pages.mjs.
     Severity: WARN (editorial, not a blocking FAIL)

  4. STALE HOW-WE-TEST SELF-REFERENCE — if any furniture page's static text
     contains "how we test" (case-insensitive) but the page is not
     how-we-test.astro, this may be a stale internal link or copy fragment.
     Severity: WARN

  NOTE: This validator does NOT duplicate the vocabulary-bleed checks from
  validate-furniture-pages.mjs. That Node.js tool handles forbidden_vocabulary
  from config/furniture-validation.yaml. This Python V2 extends the suite with
  the checks above.

Usage:
  python3 scripts/validate-furniture-pages.py /path/to/site
  python3 scripts/validate-furniture-pages.py /path/to/site --verbose
  python3 scripts/validate-furniture-pages.py --all

Exit codes:
  0 = all checks PASS or WARN only (no blocking failures)
  1 = one or more FAIL (missing required page or placeholder token found)
  2 = tool error (missing site dir, usage error)
"""

import argparse
import re
import sys
from pathlib import Path

import yaml

# ── Required furniture pages ──────────────────────────────────────────────────

REQUIRED_PAGES = [
    "index.astro",
    "about.astro",
    "how-we-research.astro",
    "privacy-policy.astro",
    "disclaimer.astro",
    "contact.astro",
    "404.astro",
]

# ── Placeholder token patterns ────────────────────────────────────────────────
# Double-brace Mustache tokens, Lorem ipsum, PLACEHOLDER.
# Explicitly NOT ${...} — that is valid Astro/JSX template syntax.

PLACEHOLDER_PATTERNS = [
    (re.compile(r'\{\{[^}]+\}\}'),         "double-brace token"),
    (re.compile(r'lorem\s+ipsum', re.I),   "lorem-ipsum"),
    (re.compile(r'\bPLACEHOLDER\b(?!\s*=)', re.I), "placeholder-literal"),
]

# ── Overclaim (HARD) patterns — mirrors validate-furniture-pages.mjs ─────────

OVERCLAIM_PATTERNS = [
    (re.compile(r'\bI (?:personally )?tested\b', re.I),                      "personal-test"),
    (re.compile(r"\bI'?ve (?:owned|tested)\b", re.I),                        "personal-ownership"),
    (re.compile(r'\bIn my (?:testing|hands-on use|personal use)\b', re.I),   "my-testing"),
    (re.compile(r'\bmy (?:personal )?(?:testing|hands-on)\b', re.I),         "my-hands-on"),
    (re.compile(r'\bwhen I (?:tested|tried|installed) (?:this|it|the)\b', re.I), "when-i-tested"),
    (re.compile(r"\bI(?:'ve)? been (?:using|running|testing) this\b", re.I), "i-been-using"),
    (re.compile(r'\bafter (?:\d+ )?(?:weeks?|months?|nights?|trips?) of '
                r'(?:using|testing|running) (?:this|it)\b', re.I),           "after-N-testing"),
    (re.compile(r'\bIn my (?:experience|opinion) (?:with|using)\b', re.I),   "my-experience-with"),
    (re.compile(r'\bMy experience with\b', re.I),                            "my-experience-with-2"),
    (re.compile(r'\bWhen I (?:tested|used|installed|ran)\b', re.I),          "when-i-used"),
    (re.compile(r'\bEvery review (?:on this site )?is based on real use\b', re.I), "every-review-real-use"),
    (re.compile(r'\bbased on direct (?:\w+ )?(?:testing|use|experience|ownership)\b', re.I),
                                                                              "based-on-direct-testing"),
]

# ── Negation suppressor ───────────────────────────────────────────────────────
# Overclaim patterns that appear inside negated/disclaimer sentences should not
# fire. E.g. "intentionally not 'I tested everything'" matches personal-test but
# is an explicit disclaimer — same approach as V12 negation tuning.

_NEGATION_RE = re.compile(
    r"\b(?:not|no|never|n't|rather\s+than|instead\s+of|without|intentionally)\b",
    re.I,
)


def _negation_before(text: str, match_start: int, window: int = 40) -> bool:
    """Return True if a negation token appears within `window` chars before the match."""
    start = max(0, match_start - window)
    return bool(_NEGATION_RE.search(text[start:match_start]))


# ── Static text extractor ─────────────────────────────────────────────────────

def extract_static_text(source: str) -> str:
    """Strip Astro frontmatter, JSX expressions, and HTML tags, returning plain text."""
    text = source

    # 1. Remove Astro frontmatter block (--- ... ---)
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            text = text[end + 5:]

    # 2. Remove self-closing tags: <Component />, <script ... />
    text = re.sub(r'<[a-zA-Z][^>]*/>', ' ', text)

    # 3. Remove <style> blocks entirely
    text = re.sub(r'<style[^>]*>[\s\S]*?</style>', ' ', text, flags=re.I)

    # 4. Remove <script> blocks entirely
    text = re.sub(r'<script[^>]*>[\s\S]*?</script>', ' ', text, flags=re.I)

    # 5. Remove JSX/template expressions: {expression} — iteratively to handle nesting.
    #    This removes ${...} and {cfg.site.brand_name} style expressions.
    prev = None
    while prev != text:
        prev = text
        text = re.sub(r'\{[^{}]*\}', ' ', text)

    # 6. Remove remaining HTML/JSX tags
    text = re.sub(r'<[^>]+>', ' ', text)

    # 7. Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    return text


# ── Core scan ─────────────────────────────────────────────────────────────────

def scan_site(site_root: Path, verbose: bool = False) -> dict:
    """
    Scan src/pages/ in site_root for furniture-page issues.

    Returns:
        {
            "missing_pages": [str],
            "placeholder_hits": [{"page": str, "match": str, "label": str}],
            "overclaim_hits": [{"page": str, "label": str, "match": str, "context": str}],
            "stale_test_refs": [{"page": str, "context": str}],
            "stale_how_we_test": bool,
            "total_pages_checked": int,
        }
    """
    pages_dir = site_root / "src" / "pages"

    missing_pages: list = []
    placeholder_hits: list = []
    overclaim_hits: list = []
    stale_test_refs: list = []
    total_pages_checked = 0

    # ── 1. Page existence ─────────────────────────────────────────────────────
    for page in REQUIRED_PAGES:
        if not (pages_dir / page).exists():
            missing_pages.append(page)

    # ── how-we-test.astro legacy check ────────────────────────────────────────
    how_we_test_path = pages_dir / "how-we-test.astro"
    how_we_research_path = pages_dir / "how-we-research.astro"
    stale_how_we_test = False

    if how_we_test_path.exists():
        if how_we_research_path.exists():
            # Both exist: how-we-test.astro is stale and should be deleted
            stale_how_we_test = True
        else:
            # Only how-we-test.astro exists (pre-rename site): treat as existence
            # PASS but remove it from missing_pages if how-we-research.astro was
            # listed as missing (it was because it doesn't exist here)
            # We leave how-we-research.astro in missing_pages as a WARN signal,
            # but we note the rename is needed rather than it being an absent page.
            # The stale_how_we_test flag stays False (not "stale", just "un-renamed").
            pass  # missing_pages already contains how-we-research.astro

    # ── 2 & 3 & 4. Scan each furniture page that exists ───────────────────────
    # Scan required pages + how-we-test.astro if present
    pages_to_scan = list(REQUIRED_PAGES)
    if how_we_test_path.exists() and "how-we-test.astro" not in pages_to_scan:
        pages_to_scan.append("how-we-test.astro")

    for page_name in pages_to_scan:
        page_path = pages_dir / page_name
        if not page_path.exists():
            continue
        total_pages_checked += 1

        source = page_path.read_text(encoding="utf-8")
        static_text = extract_static_text(source)

        # 2. Placeholder tokens — scan the RAW source (not stripped text) so that
        #    {{TOKEN}} patterns inside JSX attributes are also caught.
        for pattern, label in PLACEHOLDER_PATTERNS:
            m = pattern.search(source)
            if m:
                placeholder_hits.append({
                    "page": page_name,
                    "match": m.group(0),
                    "label": label,
                })

        # 3. Overclaim language — scan extracted static text only
        for pattern, label in OVERCLAIM_PATTERNS:
            m = pattern.search(static_text)
            if m:
                if _negation_before(static_text, m.start()):
                    continue  # suppressed — negation/disclaimer context
                start = max(0, m.start() - 60)
                end = min(len(static_text), m.end() + 60)
                overclaim_hits.append({
                    "page": page_name,
                    "label": label,
                    "match": m.group(0),
                    "context": static_text[start:end].strip(),
                })

        # 4. Stale "how we test" self-reference — flag in any page except
        #    how-we-test.astro itself
        if page_name != "how-we-test.astro":
            m = re.search(r'\bhow\s+we\s+test\b', static_text, re.I)
            if m:
                start = max(0, m.start() - 60)
                end = min(len(static_text), m.end() + 60)
                stale_test_refs.append({
                    "page": page_name,
                    "context": static_text[start:end].strip(),
                })

    return {
        "missing_pages": missing_pages,
        "placeholder_hits": placeholder_hits,
        "overclaim_hits": overclaim_hits,
        "stale_test_refs": stale_test_refs,
        "stale_how_we_test": stale_how_we_test,
        "total_pages_checked": total_pages_checked,
    }


# ── Output ────────────────────────────────────────────────────────────────────

def print_site_report(site_name: str, result: dict, verbose: bool = False) -> None:
    missing = result["missing_pages"]
    placeholders = result["placeholder_hits"]
    overclaims = result["overclaim_hits"]
    stale_refs = result["stale_test_refs"]
    stale_hwt = result["stale_how_we_test"]
    checked = result["total_pages_checked"]

    has_fail = bool(missing) or bool(placeholders)
    has_warn = bool(overclaims) or bool(stale_refs) or stale_hwt

    if has_fail:
        status, icon = "FAIL", "x"
    elif has_warn:
        status, icon = "WARN", "!"
    else:
        status, icon = "PASS", "v"

    n_issues = len(missing) + len(placeholders) + len(overclaims) + len(stale_refs) + (1 if stale_hwt else 0)
    print(f"\n{'=' * 70}")
    print(f"[{icon}] [{status}]  {site_name}  ({checked} pages checked, {n_issues} issues)")
    print(f"{'=' * 70}")

    if missing:
        print(f"\n  MISSING REQUIRED PAGES ({len(missing)}) — FAIL")
        for page in missing:
            print(f"    - {page}")

    if placeholders:
        print(f"\n  PLACEHOLDER TOKENS ({len(placeholders)}) — FAIL")
        for hit in placeholders:
            print(f"    - {hit['page']}  [{hit['label']}]  {hit['match']!r}")

    if overclaims:
        print(f"\n  OVERCLAIM LANGUAGE ({len(overclaims)}) — WARN (FTC risk)")
        for hit in overclaims:
            print(f"    - {hit['page']}  [{hit['label']}]  {hit['match']!r}")
            if verbose:
                print(f"        ...{hit['context']}...")

    if stale_hwt:
        print("\n  STALE how-we-test.astro STILL PRESENT — WARN")
        print("    how-we-research.astro exists; delete how-we-test.astro")

    if stale_refs:
        print(f"\n  STALE 'HOW WE TEST' SELF-REFERENCES ({len(stale_refs)}) — WARN")
        for ref in stale_refs:
            print(f"    - {ref['page']}")
            if verbose:
                print(f"        ...{ref['context']}...")

    if not has_fail and not has_warn:
        if verbose:
            print("  All furniture pages present and clean.")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="V2 furniture-page validator — affiliate platform preflight Check 15",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "site_dir",
        nargs="?",
        default=None,
        help="Path to site root (omit with --all)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Scan all sites listed in portfolio.yaml",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show context snippets for each finding",
    )
    args = parser.parse_args()

    if not args.all and not args.site_dir:
        parser.print_help()
        sys.exit(2)

    platform_root = Path(__file__).parent.parent

    if args.all:
        portfolio_path = platform_root / "portfolio.yaml"
        if not portfolio_path.exists():
            print(f"ERROR: portfolio.yaml not found at {portfolio_path}", file=sys.stderr)
            sys.exit(2)
        with open(portfolio_path) as f:
            portfolio = yaml.safe_load(f)
        parent_dir = Path.home()
        site_dirs = [parent_dir / s["slug"] for s in portfolio.get("sites", [])]
    else:
        site_dirs = [Path(args.site_dir).resolve()]

    any_fail = False
    summary_rows: list = []

    for site_dir in site_dirs:
        if not site_dir.exists():
            print(f"  SKIP {site_dir.name} — directory not found")
            continue
        pages_dir = site_dir / "src" / "pages"
        if not pages_dir.exists():
            print(f"  SKIP {site_dir.name} — no src/pages/ directory")
            continue

        result = scan_site(site_dir, verbose=args.verbose)
        print_site_report(site_dir.name, result, verbose=args.verbose)

        n_missing = len(result["missing_pages"])
        n_placeholders = len(result["placeholder_hits"])
        n_overclaims = len(result["overclaim_hits"])
        n_stale_refs = len(result["stale_test_refs"])
        n_stale_hwt = 1 if result["stale_how_we_test"] else 0

        has_fail = bool(n_missing or n_placeholders)
        has_warn = bool(n_overclaims or n_stale_refs or n_stale_hwt)

        if has_fail:
            any_fail = True
            status = "FAIL"
        elif has_warn:
            status = "WARN"
        else:
            status = "PASS"

        summary_rows.append((
            site_dir.name,
            result["total_pages_checked"],
            n_missing,
            n_placeholders,
            n_overclaims + n_stale_refs + n_stale_hwt,
            status,
        ))

    if len(summary_rows) > 1:
        print(f"\n\n{'=' * 70}")
        print("PORTFOLIO SUMMARY — V2 Furniture-Page Validator (Check 15)")
        print(f"{'=' * 70}")
        print(f"  {'SITE':<33}  {'PGS':>4}  {'MISS':>5}  {'PH':>4}  {'WARN':>5}  STATUS")
        print(f"  {'-' * 67}")
        for slug, pgs, miss, ph, warns, status in summary_rows:
            icon = "x" if status == "FAIL" else ("!" if status == "WARN" else "v")
            print(f"  {slug:<33}  {pgs:>4}  {miss:>5}  {ph:>4}  {warns:>5}  [{icon}] {status}")
        total_pgs  = sum(r[1] for r in summary_rows)
        total_miss = sum(r[2] for r in summary_rows)
        total_ph   = sum(r[3] for r in summary_rows)
        total_warn = sum(r[4] for r in summary_rows)
        print(f"  {'TOTAL':<33}  {total_pgs:>4}  {total_miss:>5}  {total_ph:>4}  {total_warn:>5}")

    sys.exit(1 if any_fail else 0)


if __name__ == "__main__":
    main()
