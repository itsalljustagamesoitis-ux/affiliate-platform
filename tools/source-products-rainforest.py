#!/usr/bin/env python3
"""
Bulk product sourcing via Rainforest API.

For each article in pipeline.json with an empty products[] field, searches
Rainforest for the article keyword, picks the top results, adds them to
products.yaml, and assigns product keys back to pipeline.json.

Usage:
  python3 tools/source-products-rainforest.py --site <slug>
  python3 tools/source-products-rainforest.py --site <slug> --limit 10
  python3 tools/source-products-rainforest.py --site <slug> --resume
  python3 tools/source-products-rainforest.py --site <slug> --dry-run

Cost:
  ~$0.005-0.01 per Rainforest API call (1 call per article keyword).
  A 300-article site costs approximately $1.50-3.00 total.

Prerequisites:
  RAINFOREST_KEY in <site_root>/config/credentials.env or RAINFOREST_KEY env var.

Exit:
  0 = complete
  1 = interrupted (state preserved for --resume)
  2 = tool error (missing credentials, files, etc.)
"""

import argparse
import json
import os
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
import yaml

MIN_RESULTS = 5
MAX_RESULTS = 7
MIN_REVIEWS = 50
CHECKPOINT_EVERY = 25
NOW = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z")
MAX_TITLE_LENGTH = 120   # cap product name length after scrubbing

TOOLS_DIR = Path(__file__).parent
HUB_TEMPLATES_PATH = TOOLS_DIR / "hub-templates.yaml"
DTC_BRANDS_DIR    = TOOLS_DIR.parent / "config/dtc-brands"   # per-niche dir (v1.6)
DTC_BRANDS_CONFIG = TOOLS_DIR.parent / "config/dtc-brands.yaml"  # legacy fallback
TRUSTED_BRANDS_DIR = TOOLS_DIR.parent / "config/trusted-brands"  # per-niche dir

# Title words that must appear in a result for each product hub.
# Hubs not listed here are informational; no category restriction is applied.
# Legacy hardcoded fallback -- rmflyfishing's hubs specifically. Kept so that
# site's behavior doesn't change, but this dict was never niche-configurable:
# apply_category_policy() looks a hub up here, and for every OTHER niche's
# hub (coops, feeders, waterers, ...) that lookup returns nothing, silently
# disabling category enforcement entirely for that niche. Confirmed live on
# thecluckpost: a waterer and a feeder both passed as "coops" hub results
# with zero filtering. See load_hub_category_terms() -- niches should define
# config/hub-category-terms/<niche>.yaml instead of relying on this fallback.
HUB_CATEGORY_TERMS: dict = {
    "rods":          ["rod", "rods"],
    "reels":         ["reel", "reels"],
    "lines-leaders": ["line", "lines", "leader", "leaders", "tippet"],
    "waders-boots":  ["wader", "waders", "boot", "boots", "wading"],
    "flies-patterns":["fly", "flies", "nymph", "streamer", "dry fly", "wet fly"],
    "fly-tying":     ["tying", "vise", "bobbin", "dubbing"],
    "accessories":   ["net", "pack", "vest", "bag", "pliers", "forceps", "sling"],
}
HUB_CATEGORY_TERMS_DIR = TOOLS_DIR.parent / "config/hub-category-terms"


def load_hub_templates() -> dict:
    if not HUB_TEMPLATES_PATH.exists():
        return {}
    with open(HUB_TEMPLATES_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


# ── Sourcing Policies ─────────────────────────────────────────────────────────

def load_dtc_brands(niche: str) -> list:
    """
    Return lowercased DTC brand names for the niche that are not sold on Amazon.

    Lookup order:
    1. config/dtc-brands/<niche>.yaml  — per-niche format (v1.6): plain list of brand names
    2. config/dtc-brands.yaml          — legacy format: dict keyed by niche
    """
    niche_file = DTC_BRANDS_DIR / f"{niche}.yaml"
    if niche_file.exists():
        with open(niche_file, encoding="utf-8") as f:
            data = yaml.safe_load(f) or []
        brands = [str(b).strip() for b in data if b]
    elif DTC_BRANDS_CONFIG.exists():
        with open(DTC_BRANDS_CONFIG, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        brands = list(data.get(niche, [])) + list(data.get("universal", []))
    else:
        return []
    return [b.lower() for b in brands if b]


def load_trusted_brands(niche: str) -> list:
    """
    Return lowercased trusted brand names for the niche that ARE sold on Amazon
    and should be preferred over generic/white-label listings when a search
    returns both. Unlike DTC brands (excluded entirely), trusted brands are a
    ranking preference, not a filter — a trusted-brand result is moved ahead
    of equally-qualified generic results, but generic results still fill
    remaining slots if too few trusted-brand results exist.

    Lookup: config/trusted-brands/<niche>.yaml — plain list of brand names.
    Absent file = no preference applied (existing behavior unchanged).
    """
    niche_file = TRUSTED_BRANDS_DIR / f"{niche}.yaml"
    if not niche_file.exists():
        return []
    with open(niche_file, encoding="utf-8") as f:
        data = yaml.safe_load(f) or []
    return [str(b).strip().lower() for b in data if b]


def _matches_trusted_brand(result: dict, trusted_brands: list) -> bool:
    if not trusted_brands:
        return False
    brand = (result.get("brand") or result.get("manufacturer") or "").strip().lower()
    title = (result.get("title") or "").strip().lower()
    for tb in trusted_brands:
        if tb == brand or re.search(r"\b" + re.escape(tb) + r"\b", title):
            return True
    return False


def load_hub_trusted_products(niche: str, hub: str) -> list:
    """
    Structured per-hub, pre-verified product list for HEAD-article sourcing:
    [{"brand": ..., "asin": ..., "name_hint": ...}]. Distinct from
    load_trusted_brands() (a flat niche-wide brand-name list used only as a
    ranking preference on generic spoke keyword search) -- this is a fixed
    ASIN catalog looked up directly, used instead of any search for HEAD
    articles.

    Stored as ASINs, not brand names to search, because search-term lookup
    is non-deterministic: the exact same query returned a real product on
    one run and nothing on the next (confirmed live, "Eglu Go Up"), and can
    be diluted by incidental word choice ("<brand> chicken coop" surfacing
    the brand's accessories instead of its coop -- also confirmed live). A
    human vets each product once, the ASIN goes in the config, and every
    future sourcing run gets the exact same listing with zero ranking step
    to vary or dilute.

    Lookup: config/trusted-brands/<niche>/<hub>.yaml. Absent file/dir = no
    per-hub product data for this hub -- caller falls back to normal keyword
    search (expected for hubs with no named Amazon-sold brands in the
    merchant check, e.g. bedding, runs, tractors).
    """
    hub_file = TRUSTED_BRANDS_DIR / niche / f"{hub}.yaml"
    if not hub_file.exists():
        return []
    with open(hub_file, encoding="utf-8") as f:
        data = yaml.safe_load(f) or []
    return [
        {"brand": str(e["brand"]).strip(), "asin": str(e["asin"]).strip(),
         "name_hint": str(e.get("name_hint", "")).strip()}
        for e in data if e.get("brand") and e.get("asin")
    ]


def lookup_trusted_products(entries: list, api_key: str, dry_run: bool) -> list:
    """Direct ASIN lookup for every configured trusted product -- see
    load_hub_trusted_products(). A stale/delisted ASIN degrades to a skipped
    entry (get_product_by_asin returns {}), not a crash or a silent
    off-category substitute."""
    collected = []
    for entry in entries:
        if dry_run:
            continue
        product = get_product_by_asin(entry["asin"], api_key, dry_run)
        time.sleep(0.4)
        if not product:
            print(f"         [asin-lookup] {entry['brand']} ({entry['asin']}) -> not found / delisted, skipping")
            continue
        if not product.get("sold_by_amazon_or_brand"):
            print(f"         [asin-lookup] {entry['brand']} ({entry['asin']}) -> sold by third party "
                  f"'{product.get('seller_name')}', not Amazon.com or the brand -- skipping")
            continue
        print(f"         [asin-lookup] {entry['brand']} ({entry['asin']}) -> "
              f"{product.get('title','')[:70]} (reviews={product.get('ratings_total','?')})")
        collected.append(product)
    return collected


def dtc_brands_in_keyword(keyword: str, dtc_brands: list) -> list:
    """Return any DTC brand names (lowercase) found as whole words in the keyword."""
    kw = keyword.lower()
    found = []
    for brand in sorted(dtc_brands, key=len, reverse=True):  # longest match first
        if re.search(r"\b" + re.escape(brand) + r"\b", kw) and brand not in found:
            found.append(brand)
    return found


def scrub_seller_prefix(title: str, brand: str = "") -> str:
    """
    Strip seller/marketing prefixes from Amazon product titles.

    Amazon listings frequently include:
    - Pipe-separated marketing copy: "fishpond Nomad Net | Rubber Mesh | float test..."
    - Brand-only prefix before pipe: "LAMSON | Ketchum Release Extractor | Big Bug..."

    Rules applied in order:
    1. Pipe (' | ') separator:
       - If text before first pipe is ≤2 words (brand/store-name only), use the
         text AFTER the first pipe as the title.
       - Otherwise keep text BEFORE the first pipe; discard marketing copy after.
    2. Truncate to MAX_TITLE_LENGTH characters at a word boundary.

    Note: brand duplication within the title (e.g., "fishpond Summit Sling") is
    intentionally kept — the brand is part of the product identity and the brand
    field captures it separately. Do not strip leading brand names; they make the
    title human-readable standalone.
    """
    if " | " in title:
        parts = title.split(" | ")
        first = parts[0].strip()
        if len(first.split()) <= 2 and len(parts) > 1:
            # Brand/store-name-only prefix — use the segment after the pipe
            title = parts[1].strip()
        else:
            # Product name portion precedes the pipe; discard marketing copy
            title = first

    if len(title) > MAX_TITLE_LENGTH:
        title = title[:MAX_TITLE_LENGTH].rsplit(" ", 1)[0]

    return title.strip()


def apply_brand_policy(results: list, keyword: str) -> list:
    """
    If a result's brand appears verbatim in the keyword, restrict to that brand only.
    Prevents "search for Brand X" from returning Brand Y products.
    Falls through (all results kept) when no brand cue is detectable in the keyword.
    """
    kw_lower = keyword.lower()
    matching_brand = None
    for r in results:
        rb = (r.get("brand") or r.get("manufacturer") or "").strip().lower()
        if rb and len(rb) >= 3 and rb in kw_lower:
            matching_brand = rb
            break
    if not matching_brand:
        return results
    filtered = [r for r in results
                if (r.get("brand") or r.get("manufacturer") or "").strip().lower() == matching_brand]
    return filtered if filtered else results  # fall back if filter kills everything


def load_hub_category_terms(niche: str) -> dict:
    """
    Per-niche hub -> {"require": [...], "exclude": [...]} for apply_category_policy().
    A result must contain >=1 require term (if any are set) AND 0 exclude terms.

    require alone is not enough in a niche where accessory hubs are coop-
    adjacent and legitimately reference the parent structure in their own
    title -- "Omlet Automatic Chicken Coop Door Opener" contains "coop" as
    a substring without being one. exclude terms (door opener, feeder,
    waterer, heater, ...) catch what a require-only list can't.

    Lookup: config/hub-category-terms/<niche>.yaml. Each hub's value can be
    a flat list (legacy shorthand, require-only) or a {require, exclude} dict.
    Falls back to the legacy hardcoded HUB_CATEGORY_TERMS (rmflyfishing-only,
    require-only) when no niche file exists, so that site's behavior is
    unchanged.
    """
    niche_file = HUB_CATEGORY_TERMS_DIR / f"{niche}.yaml"
    if not niche_file.exists():
        return {k: {"require": v, "exclude": []} for k, v in HUB_CATEGORY_TERMS.items()}
    with open(niche_file, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    out = {}
    for hub, val in data.items():
        if isinstance(val, list):
            out[hub] = {"require": [str(t).lower() for t in val], "exclude": []}
        else:
            out[hub] = {
                "require": [str(t).lower() for t in val.get("require", [])],
                "exclude": [str(t).lower() for t in val.get("exclude", [])],
            }
    return out


def apply_category_policy(results: list, hub: str, category_terms: dict = None) -> list:
    """Remove results that fail the hub's require/exclude terms. No-ops on info hubs
    (hubs with no configured terms) or if the require filter would kill every result
    (exclude terms still apply even then -- a wrong-category result should never survive
    just because everything else also failed the require check)."""
    spec = (category_terms or {k: {"require": v, "exclude": []} for k, v in HUB_CATEGORY_TERMS.items()}).get(hub)
    if not spec:
        return results
    require, exclude = spec.get("require", []), spec.get("exclude", [])
    if not require and not exclude:
        return results

    def excluded(r):
        title = r.get("title", "").lower()
        return any(t in title for t in exclude)

    survivors = [r for r in results if not excluded(r)]
    if not require:
        return survivors
    filtered = [r for r in survivors if any(t in r.get("title", "").lower() for t in require)]
    return filtered if filtered else survivors  # fall back within already-exclude-filtered set


# ── Credentials ───────────────────────────────────────────────────────────────

def load_rainforest_key(site_root: Path) -> str:
    key = os.environ.get("RAINFOREST_KEY")
    if not key:
        creds = site_root / "config/credentials.env"
        if creds.exists():
            for line in creds.read_text().splitlines():
                if line.startswith("RAINFOREST_KEY="):
                    key = line.split("=", 1)[1].strip()
    if not key:
        creds_path = site_root / "config/credentials.env"
        print(
            f"ERROR: RAINFOREST_KEY not set.\n"
            f"  Add it to {creds_path}\n"
            f"  or set the RAINFOREST_KEY environment variable.",
            file=sys.stderr,
        )
        sys.exit(2)
    return key


# ── Helpers ───────────────────────────────────────────────────────────────────

def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[''']", "", text)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def make_product_key(brand: str, title: str, used_keys: set) -> str:
    brand_s = slugify(brand or "")
    title_s = slugify(title or "")
    if brand_s and title_s.startswith(brand_s + "-"):
        title_s = title_s[len(brand_s) + 1:]
    parts = title_s.split("-")[:5]
    descriptor = "-".join(p for p in parts if p)
    base = f"{brand_s}-{descriptor}" if brand_s else descriptor
    base = base[:60].rstrip("-")
    key = base
    n = 2
    while key in used_keys:
        key = f"{base[:56]}-{n}"
        n += 1
    return key


# ── API ───────────────────────────────────────────────────────────────────────

def is_book_article(article: dict) -> bool:
    """True when keyword or slug signals a book/reading article (→ category 283155)."""
    keyword = (article.get("keyword") or "").lower()
    slug = (article.get("slug") or "").lower()
    return "book" in keyword or "book" in slug


def get_product_by_asin(asin: str, api_key: str, dry_run: bool) -> dict:
    """
    Direct, deterministic product lookup by ASIN (Rainforest type=product),
    not a keyword search. For pre-verified trusted-brand products stored as
    ASINs in config/trusted-brands/<niche>/<hub>.yaml -- a search-term lookup
    is inherently non-deterministic (Amazon's own ranking varies call to
    call, confirmed live: the same "Eglu Go Up" query returned the real
    product on one run and nothing on the next) and can be diluted by
    incidental word choice (see load_hub_trusted_products history). An ASIN
    lookup has no ranking step to get diluted or vary -- it's the same
    listing every time. Returns {} on any failure (missing ASIN, API error,
    delisted product) rather than raising, so a stale ASIN in config
    degrades to "skip this one," not a crash.
    """
    if dry_run:
        return {}
    try:
        resp = requests.get(
            "https://api.rainforestapi.com/request",
            params={"api_key": api_key, "type": "product", "amazon_domain": "amazon.com", "asin": asin},
            timeout=30,
        )
        resp.raise_for_status()
        product = resp.json().get("product", {})
        if not product or not product.get("title"):
            return {}
        buybox = product.get("buybox_winner", {}) or {}
        seller_name = ((buybox.get("seller") or {}).get("name") or "").strip()
        return {
            "asin": product.get("asin", asin),
            "title": product.get("title", ""),
            "brand": product.get("brand"),
            "manufacturer": product.get("manufacturer") or product.get("brand"),
            "ratings_total": product.get("ratings_total", 0),
            "link": product.get("link", f"https://www.amazon.com/dp/{asin}"),
            "seller_name": seller_name,
            "sold_by_amazon_or_brand": (
                seller_name.lower() in ("amazon.com", "")
                or (product.get("brand") or "").strip().lower() in seller_name.lower()
            ),
        }
    except Exception as e:
        print(f"    API error (ASIN {asin}): {e}")
        return {}


def search(keyword: str, api_key: str, dry_run: bool, category_id: str = "",
           trusted_brands: list = None) -> list:
    if dry_run:
        return []
    try:
        params = {
            "api_key": api_key,
            "type": "search",
            "amazon_domain": "amazon.com",
            "search_term": keyword,
        }
        if category_id:
            params["category_id"] = category_id
        resp = requests.get(
            "https://api.rainforestapi.com/request",
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        results = resp.json().get("search_results", [])
        qualified = [r for r in results if r.get("ratings_total", 0) >= MIN_REVIEWS]
        pool = qualified if len(qualified) >= MIN_RESULTS else results
        if trusted_brands:
            # Trusted-brand results move to the front of the pool (stable sort --
            # relative order within each group is preserved) before truncation to
            # MAX_RESULTS. A generic keyword like "chicken feeder" returns mostly
            # white-label listings by Rainforest's own relevance ranking; without
            # this, a trusted brand a few slots outside MAX_RESULTS never gets
            # sourced even though it's exactly the kind of pick the merchant check
            # identified as trustworthy. Preference, not a filter -- generic
            # results still fill remaining slots when too few trusted matches exist.
            pool = sorted(pool, key=lambda r: not _matches_trusted_brand(r, trusted_brands))
        return pool[:MAX_RESULTS]
    except Exception as e:
        print(f"    API error: {e}")
        return []


# ── I/O (atomic) ──────────────────────────────────────────────────────────────

def load_pipeline(pipeline_path: Path) -> dict:
    with open(pipeline_path) as f:
        data = json.load(f)
    if not isinstance(data, dict):
        data = {"articles": data}
    return data


def save_pipeline(data: dict, pipeline_path: Path) -> None:
    tmp = pipeline_path.with_suffix(".json.tmp")
    bak = pipeline_path.with_suffix(".json.bak")
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    if pipeline_path.exists():
        shutil.copy2(pipeline_path, bak)
    os.replace(tmp, pipeline_path)


def load_products(products_path: Path) -> dict:
    with open(products_path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save_products(products: dict, products_path: Path) -> None:
    tmp = products_path.with_suffix(".yaml.tmp")
    bak = products_path.with_suffix(".yaml.bak")
    with open(tmp, "w", encoding="utf-8") as f:
        yaml.dump(products, f, allow_unicode=True, default_flow_style=False,
                  sort_keys=False, width=120)
    if products_path.exists():
        shutil.copy2(products_path, bak)
    os.replace(tmp, products_path)


# ── State (resume) ────────────────────────────────────────────────────────────

def load_state(state_file: Path) -> set:
    if state_file.exists():
        try:
            return set(json.loads(state_file.read_text()))
        except Exception:
            pass
    return set()


def save_state(done: set, state_file: Path) -> None:
    state_file.write_text(json.dumps(sorted(done)))


# ── Main ──────────────────────────────────────────────────────────────────────

def get_processing_order(pipeline_articles: list, already_processed: set, dtc_brands: list) -> list:
    """Return articles to process in round-robin hub order.

    Guarantees proportional hub coverage even when processing stops early.
    Articles with no existing products and not yet processed are interleaved
    hub-by-hub so no single hub can be starved by a run cutoff.
    """
    from collections import defaultdict
    candidates = [
        a for a in pipeline_articles
        if not a.get("products") and a["slug"] not in already_processed
    ]
    by_hub = defaultdict(list)
    for a in candidates:
        by_hub[a.get("hub", "unknown")].append(a)
    hubs = sorted(by_hub.keys())
    result = []
    while any(by_hub[h] for h in hubs):
        for hub in hubs:
            if by_hub[hub]:
                result.append(by_hub[hub].pop(0))
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Bulk product sourcing via Rainforest API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--site", required=True, metavar="SLUG",
                        help="Site slug (site root is ~/SLUG)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Process at most N articles (test mode)")
    parser.add_argument("--resume", action="store_true",
                        help="Skip articles already sourced in a prior run")
    parser.add_argument("--dry-run", action="store_true",
                        help="Skip API calls; show what would be sourced")
    parser.add_argument("--reset-state", action="store_true",
                        help="Clear resume state file and start fresh")
    args = parser.parse_args()

    site_root = Path.home() / args.site
    pipeline_path = site_root / "data/pipeline.json"
    products_path = site_root / "content/products/products.yaml"
    state_file = Path(f"/tmp/source-products-rainforest-{args.site}-state.json")

    if not site_root.exists():
        print(f"ERROR: site root not found: {site_root}", file=sys.stderr)
        sys.exit(2)
    if not pipeline_path.exists():
        print(f"ERROR: pipeline.json not found: {pipeline_path}", file=sys.stderr)
        sys.exit(2)
    if not products_path.exists():
        print(f"ERROR: products.yaml not found: {products_path}", file=sys.stderr)
        sys.exit(2)

    api_key = load_rainforest_key(site_root)

    if args.reset_state and state_file.exists():
        state_file.unlink()
        print("State file cleared.")

    done = load_state(state_file) if args.resume else set()

    # Warn if a partial state exists but --resume wasn't passed
    if not args.resume and not args.reset_state and state_file.exists():
        partial = load_state(state_file)
        if partial:
            print(
                f"WARNING: state file found with {len(partial)} processed articles "
                f"but --resume was not passed. Starting fresh and IGNORING prior state.\n"
                f"  Pass --resume to continue from where you left off.\n"
                f"  Pass --reset-state to suppress this warning.",
                file=sys.stderr,
            )

    print(f"Site:       {args.site}")
    print(f"Site root:  {site_root}")
    if args.dry_run:
        print("Mode:       DRY RUN — no API calls")
    if args.resume:
        print(f"Resume:     {len(done)} articles already sourced")
    print()

    hub_templates = load_hub_templates()

    # Load DTC brands for this site's niche
    site_config_path = site_root / "site.config.yaml"
    site_niche = ""
    if site_config_path.exists():
        with open(site_config_path, encoding="utf-8") as f:
            sc = yaml.safe_load(f) or {}
            site_niche = sc.get("site", {}).get("niche", "")
    dtc_brands = load_dtc_brands(site_niche)
    if dtc_brands:
        print(f"DTC policy:  {len(dtc_brands)} brands → NOT_ON_AMAZON (niche: {site_niche or 'unknown'})")
        print()

    trusted_brands = load_trusted_brands(site_niche)
    if trusted_brands:
        print(f"Trusted-brand preference: {len(trusted_brands)} brands (niche: {site_niche or 'unknown'})")
        print()

    category_terms = load_hub_category_terms(site_niche)
    if category_terms is not HUB_CATEGORY_TERMS:
        print(f"Category policy: niche-specific terms loaded for {len(category_terms)} hub(s)")
        print()

    pipeline_data = load_pipeline(pipeline_path)
    products = load_products(products_path)
    articles = pipeline_data.get("articles", [])

    candidates = get_processing_order(articles, done, dtc_brands)
    if args.limit:
        candidates = candidates[:args.limit]

    total_empty = len([a for a in articles if not a.get("products")])
    print(f"Articles in pipeline: {len(articles)}")
    print(f"Need products:        {total_empty}")
    print(f"Already done (state): {len(done)}")
    print(f"To process this run:  {len(candidates)}")
    if args.limit:
        print(f"Limit:                {args.limit} (test mode)")
    print()

    if not candidates:
        print("Nothing to do.")
        return

    # Build ASIN → existing key map to avoid duplicates (handles both field names)
    asin_to_key = {
        (v.get("amazon_asin") or v.get("asin")): k
        for k, v in products.items()
        if isinstance(v, dict) and (v.get("amazon_asin") or v.get("asin"))
        and (v.get("amazon_asin") or v.get("asin")) not in ("VERIFY", "NOT_FOUND", "NOT_ON_AMAZON")
    }
    used_keys = set(products.keys())

    sourced = new_total = 0

    for i, article in enumerate(candidates, 1):
        slug = article["slug"]
        keyword = article.get("keyword") or slug.replace("-", " ")
        hub = article.get("hub", "")
        prefix = f"[{i}/{len(candidates)}]"

        print(f"{prefix} {slug}")
        print(f"         keyword: {keyword}")

        if args.dry_run:
            print(f"         [dry-run] would search Rainforest for: {keyword}")
            done.add(slug)
            continue

        # Policy 3 — DTC brand short-circuit: skip Amazon entirely for brands not sold there
        found_dtc = dtc_brands_in_keyword(keyword, dtc_brands)
        if found_dtc:
            assigned_keys = []
            for dtc_brand_lower in found_dtc:
                brand_name = dtc_brand_lower.title()
                key = make_product_key(brand_name, keyword, used_keys)
                used_keys.add(key)
                tmpl = hub_templates.get(hub, {})
                products[key] = {
                    "name": keyword.title(),
                    "brand": brand_name,
                    "amazon_asin": "NOT_ON_AMAZON",
                    "hub": hub,
                    "price_band": tmpl.get("price_band", "mid"),
                    "notes_for_writers": (
                        "DTC brand — add verified product name, specs, and retailer link manually."
                    ),
                    "default_pros": [],
                    "default_cons": [],
                    "sourced_at": NOW,
                    "confidence": 0.5,
                }
                assigned_keys.append(key)
            article["products"] = assigned_keys
            done.add(slug)
            sourced += 1
            new_total += len(assigned_keys)
            print(f"         → DTC brands {found_dtc}: {len(assigned_keys)} NOT_ON_AMAZON placeholder(s)")
            continue

        book_category = "283155" if is_book_article(article) else ""
        budget_pick_asin = None  # tracked so the single budget pick can be labeled below

        # HEAD articles with a configured per-hub product list: source by
        # direct ASIN lookup, not generic keyword search or brand-name search.
        # A generic head-term search structurally can't surface a brand that
        # doesn't compete on head-term search volume (see
        # load_hub_trusted_products docstring) -- this is the fix for HEAD
        # articles returning all-budget/flat-pack results. Spokes always use
        # keyword search, still subject to the fit checks below. Hubs with no
        # per-hub product file (no named Amazon-sold brands in the merchant
        # check) fall back to keyword search for their HEAD too.
        hub_products = load_hub_trusted_products(site_niche, hub) if article.get("role") == "HEAD" else []
        if hub_products:
            results = lookup_trusted_products(hub_products, api_key, args.dry_run)
            # Target 5 trusted products per HEAD article; a budget/generic supplement
            # (at most one, clearly labeled) fills the gap below that, down to a floor
            # of 4 total. Below 5 trusted matches is the expected case, not a failure --
            # not every brand sells every size/model, and one confirmed-unavailable
            # brand (e.g. no distinct "OverEZ Large" listing exists on Amazon) is fine.
            if len(results) < 5:
                budget_results = search(keyword, api_key, args.dry_run, category_id=book_category)
                time.sleep(0.4)
                budget_results = apply_category_policy(budget_results, hub, category_terms=category_terms)
                budget_results = [r for r in budget_results if not _matches_trusted_brand(r, [e["brand"].lower() for e in hub_products])]
                if budget_results:
                    budget_results.sort(key=lambda r: -(r.get("ratings_total") or 0))
                    picked = budget_results[0]
                    budget_pick_asin = picked.get("asin")
                    results.append(picked)
                    print(f"         [budget pick] {picked.get('title','')[:70]} (ASIN {budget_pick_asin})")
        else:
            results = search(keyword, api_key, args.dry_run, category_id=book_category,
                             trusted_brands=trusted_brands)
            time.sleep(0.4)

        if not results:
            print(f"         → no results, skipping")
            continue

        # Policy 1 — Brand match: reject competitor brands when keyword names a brand
        # Policy 2 — Category match: reject off-hub products (e.g. reels in a rods search)
        # Skipped for brand-lookup results -- apply_brand_policy assumes a generic
        # keyword search and would incorrectly restrict a multi-brand HEAD result
        # set down to whichever brand happens to appear in the bare keyword.
        if not hub_products:
            results = apply_brand_policy(results, keyword)
            results = apply_category_policy(results, hub, category_terms=category_terms)

        if not results:
            print(f"         → no results after policy filters, skipping")
            continue

        assigned_keys = []
        new_count = 0

        for r in results:
            asin = r.get("asin", "")
            if not asin:
                continue
            if asin in asin_to_key:
                if asin_to_key[asin] in assigned_keys:
                    continue
                assigned_keys.append(asin_to_key[asin])
                continue

            title = r.get("title", "")
            brand = r.get("brand") or r.get("manufacturer") or ""
            link = r.get("link") or f"https://www.amazon.com/dp/{asin}"

            title = scrub_seller_prefix(title)
            key = make_product_key(brand, title, used_keys)
            used_keys.add(key)
            asin_to_key[asin] = key
            tmpl = hub_templates.get(hub, {})
            notes = tmpl.get("notes_for_writers", "").strip() or None
            if budget_pick_asin and asin == budget_pick_asin:
                notes = (
                    "Budget/generic option, deliberately included alongside named-brand "
                    "picks above. Label it explicitly as the budget-tier choice in the "
                    "copy -- do not present it as equivalent build quality to the "
                    "named-brand options."
                )
            products[key] = {
                "name": title,
                "brand": brand or None,
                "amazon_asin": asin,
                "hub": hub,
                "price_band": tmpl.get("price_band", "mid"),
                "notes_for_writers": notes,
                "default_pros": [],
                "default_cons": [],
                "source_url": link,
                "sourced_at": NOW,
                "confidence": 0.75,
            }
            assigned_keys.append(key)
            new_count += 1

        article["products"] = assigned_keys
        done.add(slug)
        sourced += 1
        new_total += new_count
        reused = len(assigned_keys) - new_count
        print(f"         → {len(assigned_keys)} products ({new_count} new, {reused} reused)")

        if i % CHECKPOINT_EVERY == 0:
            print(f"\n  [checkpoint] saving at article {i}...\n")
            save_products(products, products_path)
            save_pipeline(pipeline_data, pipeline_path)
            save_state(done, state_file)

    print("\nFinal save...")
    save_products(products, products_path)
    save_pipeline(pipeline_data, pipeline_path)
    save_state(done, state_file)

    remaining = len([a for a in articles if not a.get("products")])
    print(f"\nDone.")
    print(f"  Articles sourced:     {sourced}/{len(candidates)}")
    print(f"  New products:         {new_total}")
    print(f"  Total in catalog:     {len(products)}")
    print(f"  Articles still empty: {remaining}")
    print(f"  State file:           {state_file}")

    # Completion check: compare processed slugs vs all expected live articles
    from collections import defaultdict
    live_articles = [
        a for a in articles
        if a.get("status") not in ("dupe", "drop") and a.get("status") != "skip"
    ]
    all_done = load_state(state_file)  # re-read to include this run
    unprocessed = [a for a in live_articles if a["slug"] not in all_done and not a.get("products")]

    if unprocessed:
        by_hub = defaultdict(list)
        for a in unprocessed:
            by_hub[a.get("hub", "unknown")].append(a["slug"])
        print(f"\n\u26a0\ufe0f  INCOMPLETE: {len(unprocessed)} live articles still have no products")
        for hub in sorted(by_hub):
            print(f"  {hub}: {len(by_hub[hub])} unprocessed")
        print(f"\n  To resume: re-run with --resume flag")
        sys.exit(1)
    else:
        print(f"\n\u2713 COMPLETE: all {len(live_articles)} live articles have products")
        sys.exit(0)


if __name__ == "__main__":
    main()
