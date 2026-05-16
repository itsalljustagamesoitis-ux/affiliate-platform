#!/usr/bin/env python3
"""
Product enrichment library — fetches image and brand data from Rainforest API.

Idempotent: products already fully populated are returned unchanged.
ASIN-gated: products without a valid Amazon ASIN are skipped without an API call.

Usage:
    from lib.image_sourcer import enrich_product, load_rainforest_key

    key = load_rainforest_key(site_root)  # returns None if not configured
    if key:
        entry, meta = enrich_product(slug, entry, site_root, key)
        if meta['image_updated'] or meta['brand_updated']:
            # write entry back to products.yaml
"""

import io
import os
import re
import time
from datetime import date
from pathlib import Path
from typing import Optional

import requests

_ASIN_RE = re.compile(r"^[A-Z0-9]{10}$")
_SENTINEL_ASINS = frozenset(["NOT_ON_AMAZON", "NOT_FOUND", "VERIFY"])
_MIN_CALL_INTERVAL = 0.5  # 500ms between Rainforest calls
_last_call_at: float = 0.0


# ── Public helpers ────────────────────────────────────────────────────────────

def load_rainforest_key(site_root) -> Optional[str]:
    """Load RAINFOREST_KEY from env var or <site_root>/config/credentials.env."""
    key = os.environ.get("RAINFOREST_KEY")
    if not key:
        creds = Path(site_root) / "config/credentials.env"
        if creds.exists():
            for line in creds.read_text(encoding="utf-8").splitlines():
                if line.startswith("RAINFOREST_KEY="):
                    key = line.split("=", 1)[1].strip()
    return key or None


# ── Core function ─────────────────────────────────────────────────────────────

def enrich_product(
    slug: str,
    product_entry: dict,
    site_root,
    rainforest_key: str,
    options: Optional[dict] = None,
) -> tuple[dict, dict]:
    """
    Enrich a product entry with image and brand data from Rainforest API.

    Args:
        slug: product slug (used for the image filename on disk)
        product_entry: the product's current yaml entry dict
        site_root: path to the site root directory
        rainforest_key: Rainforest API key string
        options:
            skip_image (bool, default False) — don't fetch/save image
            skip_brand (bool, default False) — don't populate brand
            force (bool, default False) — re-fetch even if already populated

    Returns:
        (updated_entry, metadata) where metadata is:
            image_updated (bool)
            brand_updated (bool)
            image_source  (str)  — 'skipped_already_complete', 'skipped_no_asin',
                                    'api_failed', 'rainforest_asin_not_found',
                                    'rainforest_YYYY-MM-DD', 'placeholder_returned',
                                    'no_image_url', 'image_url_failed_NNN', ...
            errors        (list[str]) — warnings / non-fatal issues
    """
    opts = options or {}
    skip_image = opts.get("skip_image", False)
    skip_brand = opts.get("skip_brand", False)
    force = opts.get("force", False)

    site_root = Path(site_root)
    entry = dict(product_entry)
    meta: dict = {
        "image_updated": False,
        "brand_updated": False,
        "image_source": "skipped",
        "errors": [],
    }

    # ── Idempotency check ─────────────────────────────────────────────────────
    has_brand = bool(
        entry.get("brand") and str(entry.get("brand", "")).strip()
        and str(entry.get("brand", "")).strip().lower() != "none"
    )
    image_field = entry.get("default_image")
    image_path = site_root / "public" / "images" / "products" / f"{slug}.jpg"
    has_image_field = bool(image_field)
    has_image_on_disk = image_path.exists() and image_path.stat().st_size > 100

    if not force:
        needs_image = not skip_image and (not has_image_field or not has_image_on_disk)
        needs_brand = not skip_brand and not has_brand
        if not needs_image and not needs_brand:
            meta["image_source"] = "skipped_already_complete"
            return entry, meta

    # ── ASIN gating ───────────────────────────────────────────────────────────
    asin = str(entry.get("amazon_asin") or entry.get("asin") or "").strip()
    if not asin or asin in _SENTINEL_ASINS or not _ASIN_RE.match(asin):
        meta["image_source"] = "skipped_no_asin"
        return entry, meta

    # ── Rainforest API call ───────────────────────────────────────────────────
    rf_data = _call_rainforest(asin, rainforest_key)

    if rf_data is None:
        meta["errors"].append(f"Rainforest API call failed (ASIN {asin})")
        meta["image_source"] = "api_failed"
        return entry, meta

    if rf_data.get("_asin_not_found"):
        meta["image_source"] = "rainforest_asin_not_found"
        return entry, meta

    product = rf_data.get("product") or {}

    # ── Title sanity check ────────────────────────────────────────────────────
    rf_title = product.get("title", "")
    local_name = entry.get("name") or entry.get("title") or ""
    if rf_title and local_name:
        significant = {w.lower() for w in local_name.split() if len(w) > 3}
        rf_words = {w.lower() for w in re.sub(r"[^a-z0-9 ]", " ", rf_title.lower()).split()}
        if significant and not significant.intersection(rf_words):
            meta["errors"].append(
                f'Title mismatch: local="{local_name[:60]}" vs '
                f'rainforest="{rf_title[:60]}" — possible ASIN/product mismatch'
            )

    # ── Brand population ──────────────────────────────────────────────────────
    if not skip_brand and (force or not has_brand):
        rf_brand = (product.get("brand") or "").strip()
        if rf_brand:
            entry["brand"] = rf_brand
            meta["brand_updated"] = True

    # ── Image population ──────────────────────────────────────────────────────
    if not skip_image and (force or not has_image_field or not has_image_on_disk):
        img_url = _extract_image_url(product)
        if img_url:
            ok, status = _download_image(img_url, image_path)
            meta["image_source"] = (
                f"rainforest_{date.today().isoformat()}" if ok else status
            )
            if ok:
                entry["default_image"] = f"/images/products/{slug}.jpg"
                meta["image_updated"] = True
            elif status not in ("placeholder_returned",):
                meta["errors"].append(f"Image download failed: {status} — {img_url[:80]}")
        else:
            meta["image_source"] = "no_image_url"

    return entry, meta


# ── Private helpers ───────────────────────────────────────────────────────────

def _throttle():
    global _last_call_at
    elapsed = time.monotonic() - _last_call_at
    if elapsed < _MIN_CALL_INTERVAL:
        time.sleep(_MIN_CALL_INTERVAL - elapsed)
    _last_call_at = time.monotonic()


def _call_rainforest(asin: str, api_key: str) -> Optional[dict]:
    """Call Rainforest product endpoint with exponential backoff. Returns None on terminal failure."""
    url = "https://api.rainforestapi.com/request"
    params = {
        "api_key": api_key,
        "type": "product",
        "amazon_domain": "amazon.com",
        "asin": asin,
        "fields": "product.main_image,product.images,product.brand,product.title",
    }
    backoff = [0, 2, 4, 8, 16]
    for attempt, delay in enumerate(backoff):
        if delay:
            time.sleep(delay)
        try:
            _throttle()
            resp = requests.get(url, params=params, timeout=30)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 404:
                return {"_asin_not_found": True}
            if resp.status_code in (429, 500, 502, 503):
                if attempt < len(backoff) - 1:
                    continue
                return None
            return None
        except requests.exceptions.Timeout:
            if attempt < len(backoff) - 1:
                continue
            return None
        except Exception:
            return None
    return None


def _extract_image_url(product: dict) -> str:
    main = (product.get("main_image") or {}).get("link", "")
    if main:
        return main
    images = product.get("images") or []
    if images and isinstance(images[0], dict):
        return images[0].get("link", "")
    return ""


def _download_image(url: str, dest: Path) -> tuple[bool, str]:
    """Download URL, validate dimensions > 2×2 with PIL, write JPEG. Returns (ok, status)."""
    try:
        from PIL import Image

        resp = requests.get(url, timeout=30)
        if not resp.ok:
            return False, f"image_url_failed_{resp.status_code}"

        img = Image.open(io.BytesIO(resp.content))
        w, h = img.size
        if w <= 2 or h <= 2:
            return False, "placeholder_returned"

        dest.parent.mkdir(parents=True, exist_ok=True)
        img.convert("RGB").save(dest, "JPEG", quality=90)
        return True, "ok"

    except Exception as e:
        return False, f"image_error_{type(e).__name__}"
