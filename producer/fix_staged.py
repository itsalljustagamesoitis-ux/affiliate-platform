#!/usr/bin/env python3
"""
fix_staged.py — Targeted fixer for staged articles with known validator failures.

Reads *.failures sidecar files from staging/failed/, applies mechanical or
AI-assisted fixes to the corresponding articles in staging/, then re-validates.

Handled failure codes:
  A04  Banned AI-tell phrase ("in this article", "in this guide")  — text replacement
  B02  Missing hub link in intro                                   — AI insert
  B03  Intro has > 3 paragraph blocks                             — AI consolidate
  B20  Missing contextual hub link in buying guide section        — AI insert
  Q05  FAQ answer is ~1 sentence (Q05.1–Q05.5)                   — AI expand + JSON-LD sync

Skipped (need full regeneration or title/desc re-run):
  F03/F04  Title/description length  B04/B15/B17/L01  Word count  F08  Product count

Usage:
  python3 producer/fix_staged.py --site /path/to/site
  python3 producer/fix_staged.py --site /path/to/site --dry-run
  python3 producer/fix_staged.py --site /path/to/site --slug camping-sleeping-pad
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import anthropic
import yaml


def _get_api_key(site_root: Path) -> str:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key
    cred_path = site_root / "config" / "credentials.env"
    if cred_path.exists():
        for line in cred_path.read_text().splitlines():
            if line.startswith("ANTHROPIC_API_KEY="):
                return line.split("=", 1)[1].strip()
    print("[ERROR] ANTHROPIC_API_KEY not found. Set env var or add to config/credentials.env", file=sys.stderr)
    sys.exit(2)

PLATFORM_ROOT = Path(__file__).parent.parent

VALIDATOR_MAP = {
    "roundup":    PLATFORM_ROOT / "validators/validate-roundup.mjs",
    "buyer_guide": PLATFORM_ROOT / "validators/validate-buyer-guide.mjs",
}

FIXABLE_CODES = {"A04", "B02", "B03", "B20", "Q05"}

A04_REPLACEMENTS = [
    (re.compile(r"\bin this article\b", re.IGNORECASE), "here"),
    (re.compile(r"\bin this guide\b",   re.IGNORECASE), "here"),
    (re.compile(r"\bin this roundup\b", re.IGNORECASE), "here"),
]


# ── Markdown helpers ──────────────────────────────────────────────────────────

def parse_md(text: str) -> tuple[dict, str]:
    """Returns (frontmatter_dict, body_str)."""
    if not text.startswith("---\n"):
        return {}, text
    end = text.index("\n---\n", 4)
    fm = yaml.safe_load(text[4:end])
    body = text[end + 5:]
    return fm, body


def render_md(fm: dict, body: str) -> str:
    return "---\n" + yaml.dump(fm, allow_unicode=True, sort_keys=False) + "---\n" + body


# ── Validator ─────────────────────────────────────────────────────────────────

def run_validator(article_type: str, md_path: Path, site_root: Path) -> tuple[bool, str]:
    vpath = VALIDATOR_MAP.get(article_type.lower())
    if not vpath or not vpath.exists():
        return True, f"(no validator for type '{article_type}')"
    try:
        result = subprocess.run(
            ["node", str(vpath), "--site", str(site_root), str(md_path)],
            capture_output=True, text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        return False, "[ERROR] validator timed out after 60s"
    output = result.stdout + (("\n" + result.stderr) if result.stderr else "")
    return result.returncode == 0, output


# ── A04 — Banned phrase replacement (no AI) ───────────────────────────────────

def fix_a04(body: str, _failure_msg: str, _client) -> str:
    for pat, repl in A04_REPLACEMENTS:
        body = pat.sub(repl, body)
    return body


# ── B02 — Missing hub link in intro ──────────────────────────────────────────

def fix_b02(body: str, failure_msg: str, client: anthropic.Anthropic) -> str:
    url_match = re.search(r"markdown link to (/[^\s]+/)", failure_msg)
    if not url_match:
        return body
    hub_url = url_match.group(1)
    hub_label = hub_url.strip("/").replace("-", " ").title()

    h2_match = re.search(r"\n## ", body)
    if not h2_match:
        return body
    intro = body[:h2_match.start()].strip()
    rest = body[h2_match.start():]

    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=600,
        messages=[{"role": "user", "content":
            f"The following article intro is missing a link to {hub_url}. "
            f"Weave a markdown link [{hub_label}]({hub_url}) naturally into one existing sentence "
            f"near the end of the intro. Do not add new paragraphs. Do not change any other text. "
            f"Return only the revised intro.\n\nINTRO:\n{intro}"}],
    )
    new_intro = resp.content[0].text.strip()
    return "\n" + new_intro + "\n" + rest


# ── B03 — Too many intro paragraph blocks ────────────────────────────────────

def fix_b03(body: str, _failure_msg: str, client: anthropic.Anthropic) -> str:
    h2_match = re.search(r"\n## ", body)
    if not h2_match:
        return body
    intro = body[:h2_match.start()].strip()
    rest = body[h2_match.start():]

    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        messages=[{"role": "user", "content":
            f"Consolidate the following article intro into exactly 2 paragraphs. "
            f"Preserve all information and links. "
            f"Separate paragraphs with a single blank line. Return only the result.\n\nINTRO:\n{intro}"}],
    )
    new_intro = resp.content[0].text.strip()
    return "\n" + new_intro + "\n" + rest


# ── B20 — Missing hub link in buying guide section ────────────────────────────

def fix_b20(body: str, failure_msg: str, client: anthropic.Anthropic) -> str:
    url_match = re.search(r"hub link to (/[^\s]+/)", failure_msg)
    if not url_match:
        return body
    hub_url = url_match.group(1)
    hub_label = hub_url.strip("/").replace("-", " ").title()

    section_match = re.search(
        r"\n(## (?:What to Look For|Buying Guide|How to Choose)[^\n]*\n)", body
    )
    if not section_match:
        return body
    section_start = section_match.start()
    next_h2 = re.search(r"\n## ", body[section_start + 1:])
    section_end = (section_start + 1 + next_h2.start()) if next_h2 else len(body)

    section = body[section_start:section_end]

    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        messages=[{"role": "user", "content":
            f"The following section is missing a link to {hub_url}. "
            f"Add a single markdown link [{hub_label}]({hub_url}) into one existing sentence — "
            f"descriptive anchor text only, not 'click here'. "
            f"Do not add new paragraphs or subsections. Return only the revised section.\n\nSECTION:\n{section.strip()}"}],
    )
    new_section = "\n" + resp.content[0].text.strip() + "\n"
    return body[:section_start] + new_section + body[section_end:]


# ── Q05 — Short FAQ answer + JSON-LD sync ────────────────────────────────────

def _sync_jsonld(body: str, question_text: str, new_answer: str) -> str:
    """Update the matching FAQ entry in the JSON-LD schema block."""
    script_match = re.search(
        r'<script type="application/ld\+json">(.*?)</script>', body, re.DOTALL
    )
    if not script_match:
        return body
    try:
        schema = json.loads(script_match.group(1))
    except json.JSONDecodeError:
        return body  # malformed — leave untouched
    for entity in schema.get("mainEntity", []):
        if entity.get("name", "").strip() == question_text.strip():
            entity["acceptedAnswer"]["text"] = new_answer
            break
    new_json = json.dumps(schema, indent=2, ensure_ascii=False)
    new_script = f'<script type="application/ld+json">\n{new_json}\n</script>'
    return body[:script_match.start()] + new_script + body[script_match.end():]


def fix_q05(body: str, failure_msg: str, client: anthropic.Anthropic) -> str:
    """Expand a short FAQ answer (1 sentence → 3) and sync JSON-LD."""
    faq_num_match = re.search(r"Q05\.(\d+)", failure_msg)
    if not faq_num_match:
        return body
    # Q05.N corresponds to FAQ[N] which is 0-indexed — h3_matches[N] is the right target
    faq_idx = int(faq_num_match.group(1))

    faq_section_match = re.search(r"\n## Frequently Asked Questions\n", body)
    if not faq_section_match:
        return body
    faq_start = faq_section_match.end()
    faq_body = body[faq_start:]

    h3_matches = list(re.finditer(r"\n(### .+)\n", faq_body))
    if faq_idx >= len(h3_matches):
        return body

    target = h3_matches[faq_idx]
    question_text = target.group(1).lstrip("#").strip()
    answer_start = target.end()

    if faq_idx + 1 < len(h3_matches):
        answer_end = h3_matches[faq_idx + 1].start()
    else:
        end_match = re.search(r"\n<script|\n## ", faq_body[answer_start:])
        answer_end = answer_start + (end_match.start() if end_match else len(faq_body))

    current_answer = faq_body[answer_start:answer_end].strip()

    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        messages=[{"role": "user", "content":
            f"Expand this FAQ answer to 3 sentences. Match the existing tone. "
            f"Plain prose only — no bullets, no new topics introduced. "
            f"Return only the expanded answer.\n\nQ: {question_text}\nA: {current_answer}"}],
    )
    expanded = resp.content[0].text.strip()

    new_faq_body = (
        faq_body[:target.start()]
        + f"\n{target.group(1)}\n\n{expanded}\n"
        + faq_body[answer_end:]
    )
    new_body = body[:faq_start] + new_faq_body
    return _sync_jsonld(new_body, question_text, expanded)


# ── Dispatcher ────────────────────────────────────────────────────────────────

FIXERS = {
    "A04": fix_a04,
    "B02": fix_b02,
    "B03": fix_b03,
    "B20": fix_b20,
    "Q05": fix_q05,
}


def failure_code(line: str) -> str | None:
    """Extract the base failure code from a [FAIL] line (e.g. 'Q05' from 'Q05.4')."""
    m = re.match(r"\[FAIL\]\s+([A-Z]\d+)", line)
    if not m:
        return None
    code = m.group(1)
    # Normalise Q05.N → Q05
    return re.sub(r"\.\d+$", "", code)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Fix staged articles with known validator failures")
    parser.add_argument("--site", required=True, help="Path to site root")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be fixed without writing")
    parser.add_argument("--slug", help="Fix only this slug")
    args = parser.parse_args()

    site_root = Path(args.site).resolve()
    staging_dir = site_root / "staging"
    failed_dir  = site_root / "staging" / "failed"

    if not staging_dir.exists():
        print(f"[ERROR] staging/ not found at {staging_dir}", file=sys.stderr)
        sys.exit(2)

    client = anthropic.Anthropic(api_key=_get_api_key(site_root))

    # Collect .failures files
    if args.slug:
        failures_files = list(failed_dir.glob(f"{args.slug}.failures"))
    else:
        failures_files = sorted(failed_dir.glob("*.failures"))

    if not failures_files:
        print("No .failures files found — nothing to fix.")
        return

    totals = {"fixed": 0, "still_failing": 0, "skipped": 0, "not_in_staging": 0}

    for ffile in failures_files:
        slug = ffile.stem
        md_path = staging_dir / f"{slug}.md"

        if not md_path.exists():
            print(f"[SKIP] {slug} — not in staging/ (may be in staging/failed/)")
            totals["not_in_staging"] += 1
            continue

        fail_lines = [l for l in ffile.read_text().splitlines() if l.startswith("[FAIL]")]
        codes_needed = []
        for line in fail_lines:
            code = failure_code(line)
            if code and code in FIXERS:
                codes_needed.append((code, line))

        if not codes_needed:
            skippable_codes = {failure_code(l) for l in fail_lines if failure_code(l)}
            print(f"[SKIP] {slug} — failures are {skippable_codes or 'unknown'} (not auto-fixable)")
            totals["skipped"] += 1
            continue

        text = md_path.read_text(encoding="utf-8")
        fm, body = parse_md(text)
        article_type = fm.get("type", "")

        print(f"\n{'[DRY-RUN] ' if args.dry_run else ''}Fixing: {slug}")
        for code, line in codes_needed:
            print(f"  → {code}: {line[7:60]}...")
            fixer = FIXERS[code]
            body = fixer(body, line, client)

        if args.dry_run:
            print(f"  (dry-run — not written)")
            continue

        md_path.write_text(render_md(fm, body), encoding="utf-8")

        passed, output = run_validator(article_type, md_path, site_root)
        if passed:
            print(f"  ✓ validator pass — {slug}.md stays in staging/")
            # Remove .failures sidecar
            ffile.unlink(missing_ok=True)
            totals["fixed"] += 1
        else:
            print(f"  ✗ still failing after fix:")
            fail_summary = [l for l in output.splitlines() if "[FAIL]" in l]
            for l in fail_summary:
                print(f"    {l}")
            # Update .failures sidecar with new output
            ffile.write_text(output, encoding="utf-8")
            totals["still_failing"] += 1

    print(f"\n── Summary ──────────────────────────────────")
    print(f"  Fixed:           {totals['fixed']}")
    print(f"  Still failing:   {totals['still_failing']}")
    print(f"  Skipped (code):  {totals['skipped']}")
    print(f"  Not in staging:  {totals['not_in_staging']}")


if __name__ == "__main__":
    main()
