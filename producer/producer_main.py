#!/usr/bin/env python3
"""
Platform producer — single entry point for all affiliate sites.

Usage (from site root):
  python3 affiliate-platform/producer/producer_main.py --site . --id 3
  python3 affiliate-platform/producer/producer_main.py --site . --count 10
  python3 affiliate-platform/producer/producer_main.py --site . --count 5 --type Roundup
  python3 affiliate-platform/producer/producer_main.py --site . --slug polywood-adirondack-chair-review
  python3 affiliate-platform/producer/producer_main.py --site . --dry-run --count 5

Or via site-side shell (sets --site automatically):
  python3 producer/mlt-producer.py --count 10

Flags:
  --site             Path to site root (default: current working directory)
  --id               Produce single article by pipeline ID
  --slug             Produce single article by slug
  --count            Number of articles to produce (default: ALL pending, with confirmation)
  --type             Filter by type: Roundup, Review, Comparison, Informational, Buyer Guide
  --hub              Filter by hub slug
  --dry-run          Plan without generating (no LLM calls, no file writes)
  --force            Regenerate even if already staged
  --publish          Write directly to content/articles/ without staging step
  --no-confirm       Skip the "produce all N pending?" confirmation (for scripted runs)
  --skip-verification  Skip pre-flight coverage check (emergency override only)

Exit codes:
  0  All articles generated successfully
  1  Completed with article-level skips or failures
  2  Configuration/environment error (missing site.config.yaml, no API key)
  3  Coverage gate failure
"""

import argparse
import os
import sys
import time
import tempfile
import traceback
from pathlib import Path


def _setup_platform_path():
    """Ensure platform producer/ is importable regardless of invocation path."""
    platform_producer = Path(__file__).parent
    if str(platform_producer) not in sys.path:
        sys.path.insert(0, str(platform_producer))


_setup_platform_path()

from data_loader import (
    load_pipeline, load_products, load_persona, load_eeat_vault,
    load_navigation, load_site_config,
    get_pending_articles, get_article_by_id, get_article_by_slug,
    get_eeat_for_cluster, save_pipeline,
    enrich_article, get_hub_products,
)
from article_builder import (
    generate_article, build_frontmatter, build_review_txt,
    _ensure_products_in_catalog, _run_validator, check_output_shape,
)
from prompt_loader import load_prompt


def get_api_key(site_root: Path) -> str:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key
    for creds_path in [
        site_root / "config/credentials.env",
        Path.home() / "ordinary-introvert/config/credentials.env",
    ]:
        if creds_path.exists():
            for line in creds_path.read_text().splitlines():
                if line.startswith("ANTHROPIC_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"')
    raise ValueError(
        "ANTHROPIC_API_KEY not found. Set env var or add to config/credentials.env"
    )


def already_staged(slug: str, staging_dir: Path, articles_dir: Path) -> bool:
    return (
        (staging_dir / f"{slug}.md").exists()
        or (staging_dir / "failed" / f"{slug}.md").exists()
        or (articles_dir / f"{slug}.md").exists()
    )


def mark_produced(pipeline: list, article_id: int) -> None:
    for a in pipeline:
        if a["id"] == article_id:
            a["status"] = "staged"
            break


def select_articles(pipeline: list, args) -> list:
    if args.id:
        a = get_article_by_id(pipeline, args.id)
        return [a] if a else []
    if args.slug:
        a = get_article_by_slug(pipeline, args.slug)
        return [a] if a else []

    pending = get_pending_articles(pipeline)

    if args.type:
        pending = [a for a in pending if a["type"].lower() == args.type.lower()]
    if args.hub:
        pending = [a for a in pending if a.get("hub") == args.hub]

    pending.sort(key=lambda a: (a.get("kd", 99), -a.get("volume", 0)))
    if args.count is None:
        return pending
    return pending[:args.count]


def verify_coverage(site_root: Path, min_products: int = 4) -> bool:
    """Run verify-coverage.py as a pre-flight check. Returns True if OK."""
    import subprocess
    tool = Path(__file__).parent.parent / "tools/verify-coverage.py"
    if not tool.exists():
        print("  WARNING: verify-coverage.py not found, skipping coverage check")
        return True
    site_slug = site_root.name
    result = subprocess.run(
        [sys.executable, str(tool),
         "--site", site_slug,
         "--min-products", str(min_products),
         "--pipeline", str(site_root / "data/pipeline.json"),
         "--products", str(site_root / "content/products/products.yaml"),
         "--report", f"/tmp/coverage-report-{site_slug}.json",
         "--strict"],
        capture_output=False,
    )
    return result.returncode == 0


def run(args, site_root: Path):
    pipeline = load_pipeline(site_root)
    all_products = load_products(site_root)
    persona = load_persona(site_root)
    vault = load_eeat_vault(site_root)
    nav = load_navigation(site_root)
    site_config = load_site_config(site_root)

    staging_dir = site_root / "staging"
    articles_dir = site_root / "content/articles"
    staging_dir.mkdir(exist_ok=True)
    (staging_dir / "approved").mkdir(exist_ok=True)
    articles_dir.mkdir(parents=True, exist_ok=True)

    articles = select_articles(pipeline, args)
    for a in articles:
        enrich_article(a, nav)

    if not articles:
        print("No matching pending articles found.")
        return

    # Finding A: when --count is not given, default is all pending — confirm before running
    if args.count is None and not args.id and not args.slug:
        print(f"No --count specified; will produce all {len(articles)} pending articles.")
        if not args.no_confirm and not args.dry_run:
            try:
                input("Press Enter to continue or Ctrl-C to abort: ")
            except KeyboardInterrupt:
                print("\nAborted by user.")
                sys.exit(0)

    # Pre-flight coverage check — refuse to run if products are insufficient
    if not args.dry_run and not args.skip_verification:
        print("Running pre-flight coverage check...")
        if not verify_coverage(site_root):
            print(
                "\nERROR: Coverage check failed. Fix product gaps before producing."
                "\n  Pass --skip-verification to override (emergency use only)."
            )
            sys.exit(3)
        print("Coverage: OK\n")

    print(f"Producing {len(articles)} article(s)...\n")

    client = None
    if not args.dry_run:
        import anthropic
        try:
            client = anthropic.Anthropic(api_key=get_api_key(site_root))
        except ValueError as e:
            print(f"ERROR (config): {e}", file=sys.stderr)
            sys.exit(2)

    errors = 0
    skip_counts = {"dupe": 0, "drop": 0, "unknown_status": 0,
                   "already_staged": 0, "no_products": 0, "fail_count": 0}
    generated = 0

    for i, article in enumerate(articles):
        slug = article["slug"]
        status = article.get("status", "")

        # Gate on article status before spending time on it
        if status == "dupe":
            skip_counts["dupe"] += 1
            continue
        if status == "drop":
            skip_counts["drop"] += 1
            continue
        if status and status not in ("live", "pending", "staged", "skip"):
            print(f"  SKIP — {slug}: unknown status={status!r}")
            skip_counts["unknown_status"] += 1
            continue

        print(
            f"[{i+1}/{len(articles)}] {article['type']} — "
            f"{article['keyword']} (id: {article['id']})"
        )

        if already_staged(slug, staging_dir, articles_dir) and not args.force:
            print(f"  SKIP — {slug}.md already staged. Use --force to regenerate.\n")
            skip_counts["already_staged"] += 1
            continue

        if article.get("fail_count", 0) >= 3 and not args.force:
            print(f"  SKIP — {slug} has failed {article['fail_count']} times. Use --force to retry.\n")
            skip_counts["fail_count"] += 1
            continue

        if "products" not in article:
            print(f"  SKIP — no product assignment. Run: python3 data/assign-products.py\n")
            skip_counts["no_products"] += 1
            continue

        if article.get("products") == [] and article.get("assignment_notes"):
            print(f"  SKIP — product gap: {article['assignment_notes'][:100]}\n")
            skip_counts["no_products"] += 1
            continue

        # Load prompt for this article type
        system_text, metadata = load_prompt(article["type"], site_config, persona)

        if args.dry_run:
            hub_prods = get_hub_products(all_products, article["hub"])
            print(f"  DRY RUN — would generate {slug}.md")
            print(
                f"  Products: {len(article.get('products', []))} assigned "
                f"| Hub has {len(hub_prods)} products"
            )
            print(f"  Hub: {article.get('hub_label')} ({article.get('hub_url')})")
            print(
                f"  System prompt: "
                f"{'platform ' + metadata.get('prompt_file', '') if system_text else 'fallback (per-site)'}"
            )
            if metadata.get("product_count"):
                print(f"  Product count limits: {metadata['product_count']}")
            print()
            continue

        # R6: Catalog-growth — add missing products with VERIFY ASINs
        try:
            all_products = _ensure_products_in_catalog(article, all_products, site_root)
        except ValueError as e:
            print(f"  ERROR (catalog): {e}\n")
            errors += 1
            continue

        eeat = get_eeat_for_cluster(vault, article["hub"])
        products = get_hub_products(all_products, article["hub"])

        # Attach published siblings for internal linking
        article["_siblings"] = [
            a for a in pipeline
            if a.get("hub") == article["hub"]
            and a.get("published", False)
            and a["slug"] != article["slug"]
        ]

        try:
            print("  Generating...", end="", flush=True)
            body, title, description, product_keys = generate_article(
                article, products, eeat, persona, client,
                site_config, site_root, system_text, metadata,
            )

            word_count = len(body.split())

            # Pre-write shape check — catches refusal content and grossly malformed output.
            shape_ok, shape_failures = check_output_shape(body, article["type"], product_keys)
            if not shape_ok:
                print(f"\n  SHAPE CHECK FAILED for '{slug}':")
                for msg in shape_failures:
                    print(f"    ✗ {msg}")
                failed_dir = staging_dir / "failed"
                failed_dir.mkdir(exist_ok=True)
                sidecar = failed_dir / f"{slug}.failures"
                sidecar.write_text("\n".join(shape_failures), encoding="utf-8")
                article["fail_count"] = article.get("fail_count", 0) + 1
                article.pop("_siblings", None)
                save_pipeline(pipeline, site_root)
                errors += 1
                continue

            frontmatter = build_frontmatter(
                article, product_keys, products, title, description, site_config
            )

            # Always write .md first — R7 validator needs it regardless of path
            md_content = frontmatter + body + "\n"

            if args.publish:
                # Publish path: validate .md, then move to content/articles/ on pass
                with tempfile.NamedTemporaryFile(
                    suffix=".md", dir=staging_dir, delete=False, mode="w", encoding="utf-8"
                ) as tmp_f:
                    tmp_path = Path(tmp_f.name)
                    tmp_f.write(md_content)

                valid, validator_output = _run_validator(article["type"], tmp_path, site_root)
                if not valid:
                    failed_dir = staging_dir / "failed"
                    failed_dir.mkdir(exist_ok=True)
                    failed_path = failed_dir / f"{slug}.md"
                    tmp_path.rename(failed_path)
                    sidecar_path = failed_dir / f"{slug}.failures"
                    sidecar_path.write_text(validator_output, encoding="utf-8")
                    print(f"\n  WARN: validator rejected '{slug}' (publish) — moved to staging/failed/")
                    errors += 1
                    continue

                out_path = articles_dir / f"{slug}.md"
                tmp_path.rename(out_path)
                article["published"] = True
                print(f" done. {word_count} words → content/articles/{slug}.md")
                generated += 1
            else:
                # Staging path: write .md, run R7 validator, route to staging/ or staging/failed/
                md_path = staging_dir / f"{slug}.md"
                md_path.write_text(md_content, encoding="utf-8")

                valid, validator_output = _run_validator(article["type"], md_path, site_root)
                if not valid:
                    failed_dir = staging_dir / "failed"
                    failed_dir.mkdir(exist_ok=True)
                    failed_path = failed_dir / f"{slug}.md"
                    failed_path.write_text(md_content, encoding="utf-8")
                    md_path.unlink(missing_ok=True)
                    sidecar_path = failed_dir / f"{slug}.failures"
                    sidecar_path.write_text(validator_output, encoding="utf-8")
                    article["fail_count"] = article.get("fail_count", 0) + 1
                    print(
                        f" done ({word_count} words) — validator FAIL → "
                        f"staging/failed/{slug}.md  (see {slug}.failures)"
                    )
                else:
                    print(f" done. {word_count} words → staging/{slug}.md")
                    article["staged"] = True
                    generated += 1

            article.pop("_siblings", None)
            save_pipeline(pipeline, site_root)

        except Exception as e:
            err_type = type(e).__name__
            print(f" ERROR: {err_type}: {e}")
            failed_dir = staging_dir / "failed"
            failed_dir.mkdir(exist_ok=True)
            tb_path = failed_dir / f"{slug}.traceback"
            tb_path.write_text(traceback.format_exc(), encoding="utf-8")
            errors += 1
            continue

        if i < len(articles) - 1:
            time.sleep(8)

    # Skip + generation summary
    total_skipped = sum(skip_counts.values())
    if total_skipped or generated:
        print("\n=== Producer Summary ===")
        print(f"  Total selected:        {len(articles)}")
        if skip_counts["dupe"]:          print(f"  Skipped (dupe):        {skip_counts['dupe']}")
        if skip_counts["drop"]:          print(f"  Skipped (drop):        {skip_counts['drop']}")
        if skip_counts["unknown_status"]:print(f"  Skipped (bad status):  {skip_counts['unknown_status']}")
        if skip_counts["already_staged"]:print(f"  Skipped (staged):      {skip_counts['already_staged']}")
        if skip_counts["no_products"]:   print(f"  Skipped (no products): {skip_counts['no_products']}")
        if skip_counts["fail_count"]:    print(f"  Skipped (fail limit):  {skip_counts['fail_count']}")
        print(f"  Generated:             {generated}")

    if args.publish:
        print(f"\nDone. {generated} article(s) written to content/articles/")
    else:
        print(f"\nDone. Review files in {staging_dir}/")
        if not args.dry_run:
            print(
                "Edit in Word or Pages, move to staging/approved/, "
                "then: python3 producer/publish.py --all"
            )

    if errors:
        print(f"\n{errors} article(s) failed. See errors above.")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Platform Article Producer")
    parser.add_argument(
        "--site",
        default=".",
        help="Path to site root (default: current directory)",
    )
    parser.add_argument("--id", type=int, help="Produce single article by pipeline ID")
    parser.add_argument("--slug", help="Produce single article by slug")
    parser.add_argument("--count", type=int, help="Number of articles to produce")
    parser.add_argument(
        "--type",
        help="Filter by type: Roundup, Review, Comparison, Informational, Buyer Guide",
    )
    parser.add_argument("--hub", help="Filter by hub slug")
    parser.add_argument(
        "--dry-run", action="store_true", help="Plan without generating (no LLM calls)"
    )
    parser.add_argument(
        "--force", action="store_true", help="Regenerate even if already staged"
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Write directly to content/articles/ (skips staging)",
    )
    parser.add_argument(
        "--skip-verification",
        action="store_true",
        help="Skip pre-flight coverage check (emergency override only)",
    )
    parser.add_argument(
        "--no-confirm",
        action="store_true",
        help="Skip confirmation prompt when --count is omitted (for scripted runs)",
    )
    args = parser.parse_args()

    site_root = Path(args.site).resolve()
    if not (site_root / "site.config.yaml").exists():
        print(
            f"ERROR: No site.config.yaml found at {site_root}. "
            f"Pass --site <path> to specify site root.",
            file=sys.stderr,
        )
        sys.exit(2)  # config error, not article-level failure

    run(args, site_root)


if __name__ == "__main__":
    main()
