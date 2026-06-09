#!/usr/bin/env python3
"""
validate-amazon-tag.py — V3 Amazon tracking-tag validator
Affiliate Platform preflight Check 16.

Validates the Amazon Associates tracking tag (affiliate.amazon_tracking_id in
site.config.yaml) for:

  1. FORMAT — tag must match ^[a-zA-Z0-9][a-zA-Z0-9-]*-[0-9]{2}$
     (only alphanumeric and hyphens; must end in a two-digit marketplace suffix
     such as -20 for the US marketplace). No length ceiling — tags up to 60 chars
     are accepted; >60 chars triggers a WARN. A null/empty value → FAIL.
     Severity: FAIL on format violation, WARN on absurd length.

  2. NOT A PLACEHOLDER — tag must not be a well-known sentinel/test value:
     yourtag-20, example-20, placeholder-20, testsite-20, test-20,
     yoursitename-20, testsite13-20 (case-insensitive).
     Severity: FAIL

  3. PORTFOLIO UNIQUENESS — in --all mode, build a registry across all sites
     and flag any tag that appears for more than one site slug.
     Severity: FAIL (commissions route to wrong reporting bucket).
     Note: collision_with is populated by the --all sweep, not by scan_site().

Usage:
  python3 scripts/validate-amazon-tag.py /path/to/site
  python3 scripts/validate-amazon-tag.py --all
  python3 scripts/validate-amazon-tag.py --all --verbose

Exit codes:
  0 = all checks PASS
  1 = one or more FAIL
  2 = tool error (missing site dir, missing required files, usage error)
"""

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Optional

import yaml

# ── Constants ─────────────────────────────────────────────────────────────────

# Must match: start with alphanumeric, body is alphanumeric+hyphen, end with -NN
TAG_FORMAT_RE = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9-]*-[0-9]{2}$')

# Warn (not fail) on absurdly long tags — Amazon doesn't enforce a ceiling, but
# anything over 60 characters is almost certainly an error.
TAG_ABSURD_LENGTH = 60

# Known sentinel / placeholder tag values (compared case-insensitively)
PLACEHOLDER_TAGS = {
    "yourtag-20",
    "example-20",
    "placeholder-20",
    "testsite-20",
    "test-20",
    "yoursitename-20",
    "testsite13-20",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_site_config(site_root: Path) -> dict:
    cfg_path = site_root / "site.config.yaml"
    if not cfg_path.exists():
        raise FileNotFoundError(f"site.config.yaml not found at {cfg_path}")
    with open(cfg_path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


# ── Core scan ─────────────────────────────────────────────────────────────────

def scan_site(site_root: Path, verbose: bool = False) -> dict:
    """
    Validate the Amazon tracking tag for site_root.

    Returns:
        {
            "tag": str | None,
            "valid_format": bool,
            "is_placeholder": bool,
            "format_errors": [str],
            "collision_with": [str],   # populated externally by --all sweep
        }
    """
    cfg = load_site_config(site_root)
    affiliate = cfg.get("affiliate") or {}
    tag: Optional[str] = affiliate.get("amazon_tracking_id") or None

    format_errors: list = []
    valid_format = True
    is_placeholder = False

    if not tag:
        format_errors.append("amazon_tracking_id is missing or null")
        valid_format = False
        return {
            "tag": None,
            "valid_format": False,
            "is_placeholder": False,
            "format_errors": format_errors,
            "collision_with": [],
        }

    # Normalise to string in case YAML parsed it as a non-string scalar
    tag = str(tag).strip()

    # Check for placeholder sentinel values
    if tag.lower() in PLACEHOLDER_TAGS:
        is_placeholder = True
        format_errors.append(
            f"tag {tag!r} is a known placeholder sentinel — replace with real tracking ID"
        )
        valid_format = False

    if not TAG_FORMAT_RE.match(tag):
        valid_format = False
        # Produce targeted error messages for the most common format violations
        if not re.search(r'-[0-9]{2}$', tag):
            format_errors.append(
                f"tag {tag!r} does not end with a two-digit marketplace suffix "
                f"(e.g. -20 for US, -03 for CA)"
            )
        if re.search(r'[^a-zA-Z0-9-]', tag):
            bad_chars = set(re.findall(r'[^a-zA-Z0-9-]', tag))
            format_errors.append(
                f"tag {tag!r} contains invalid character(s): "
                + ", ".join(repr(c) for c in sorted(bad_chars))
            )
        if tag and not re.match(r'^[a-zA-Z0-9]', tag):
            format_errors.append(
                f"tag {tag!r} must start with an alphanumeric character"
            )
        if not format_errors:
            # Fallback: report the full pattern
            format_errors.append(
                f"tag {tag!r} does not match required pattern "
                r"^[a-zA-Z0-9][a-zA-Z0-9-]*-[0-9]{2}$"
            )

    # Absurd length: WARN (recorded in format_errors with prefix WARN so callers
    # can distinguish it from blocking failures)
    if len(tag) > TAG_ABSURD_LENGTH:
        format_errors.append(
            f"WARN: tag {tag!r} is {len(tag)} characters — "
            f"unusually long (>{TAG_ABSURD_LENGTH}); verify this is intentional"
        )

    return {
        "tag": tag,
        "valid_format": valid_format,
        "is_placeholder": is_placeholder,
        "format_errors": format_errors,
        "collision_with": [],  # populated externally by --all sweep
    }


# ── Output ────────────────────────────────────────────────────────────────────

def _is_fail(result: dict) -> bool:
    return (
        not result["valid_format"]
        or result["is_placeholder"]
        or bool(result["collision_with"])
    )


def print_site_report(site_name: str, result: dict, verbose: bool = False) -> None:
    tag = result["tag"]
    errors = result["format_errors"]
    collisions = result["collision_with"]

    # Separate blocking errors from WARN-only entries
    blocking_errors = [e for e in errors if not e.startswith("WARN:")]
    warn_errors = [e for e in errors if e.startswith("WARN:")]

    has_fail = _is_fail(result)

    if has_fail:
        status, icon = "FAIL", "x"
    elif warn_errors or not result["valid_format"]:
        status, icon = "WARN", "!"
    else:
        status, icon = "PASS", "v"

    tag_display = repr(tag) if tag else "(none)"
    print(f"\n  [{icon}] [{status}]  {site_name}  tag={tag_display}")

    for err in blocking_errors:
        print(f"       FAIL: {err}")

    for warn in warn_errors:
        print(f"       {warn}")

    for other_slug in collisions:
        print(
            f"       FAIL: tag collision with {other_slug!r} — "
            "commissions route to wrong reporting bucket"
        )

    if not has_fail and not warn_errors and verbose:
        print(f"       Tag format valid; no collisions detected.")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="V3 Amazon tracking-tag validator — affiliate platform preflight Check 16",
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
        help="Scan all sites in portfolio.yaml and check for tag collisions",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show pass confirmation for clean sites",
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
        with open(portfolio_path, encoding="utf-8") as f:
            portfolio = yaml.safe_load(f)
        parent_dir = Path.home()
        site_dirs = [parent_dir / s["slug"] for s in portfolio.get("sites", [])]
    else:
        site_dirs = [Path(args.site_dir).resolve()]

    # ── First pass: collect all scan results ──────────────────────────────────
    results: dict = {}  # site_slug -> result dict

    for site_dir in site_dirs:
        if not site_dir.exists():
            print(f"  SKIP {site_dir.name} — directory not found")
            continue
        try:
            result = scan_site(site_dir, verbose=args.verbose)
        except FileNotFoundError as e:
            print(f"  ERROR {site_dir.name}: {e}", file=sys.stderr)
            continue
        results[site_dir.name] = result

    # ── Collision detection (--all mode only) ─────────────────────────────────
    if args.all and len(results) > 1:
        tag_to_slugs: dict = defaultdict(list)
        for slug, result in results.items():
            tag = result.get("tag")
            if tag:
                tag_to_slugs[tag.lower()].append(slug)

        for tag_lower, slugs in tag_to_slugs.items():
            if len(slugs) > 1:
                for slug in slugs:
                    others = [s for s in slugs if s != slug]
                    results[slug]["collision_with"].extend(others)

    # ── Output ────────────────────────────────────────────────────────────────
    any_fail = False
    summary_rows: list = []

    print(f"\n{'=' * 70}")
    print("Amazon Tag Validator — V3 (Check 16)")
    print(f"{'=' * 70}")

    for slug, result in results.items():
        print_site_report(slug, result, verbose=args.verbose)
        if _is_fail(result):
            any_fail = True
            status = "FAIL"
        else:
            warn_entries = [e for e in result["format_errors"] if e.startswith("WARN:")]
            status = "WARN" if warn_entries else "PASS"
        summary_rows.append((slug, result.get("tag") or "(none)", status))

    if len(summary_rows) > 1:
        print(f"\n\n{'=' * 70}")
        print("PORTFOLIO SUMMARY — V3 Amazon Tag Validator (Check 16)")
        print(f"{'=' * 70}")
        print(f"  {'SITE':<33}  {'TAG':<28}  STATUS")
        print(f"  {'-' * 68}")
        for slug, tag, status in summary_rows:
            icon = "x" if status == "FAIL" else ("!" if status == "WARN" else "v")
            print(f"  {slug:<33}  {tag:<28}  [{icon}] {status}")

    sys.exit(1 if any_fail else 0)


if __name__ == "__main__":
    main()
