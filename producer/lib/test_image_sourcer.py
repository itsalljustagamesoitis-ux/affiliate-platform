"""
Tests for image_sourcer.enrich_product.

Unit tests use mocked API calls. The real-ASIN integration test only runs
when RAINFOREST_KEY is set in the environment or SM credentials.env.
"""

import io
import os
import sys
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Make lib/ importable when running from affiliate-platform/producer/
sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.image_sourcer import enrich_product, load_rainforest_key

DUMMY_KEY = "TEST_KEY_NOT_REAL"

# Minimal 8×8 JPEG bytes (valid non-placeholder image)
def _tiny_jpeg_bytes():
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), color=(255, 0, 0)).save(buf, "JPEG")
    return buf.getvalue()


# A 1×1 "placeholder" JPEG
def _placeholder_jpeg_bytes():
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (1, 1), color=(255, 255, 255)).save(buf, "JPEG")
    return buf.getvalue()


def _fake_rf_response(brand="Acme", title="Acme Blaster 3000", img_url="https://example.com/img.jpg"):
    return {
        "product": {
            "brand": brand,
            "title": title,
            "main_image": {"link": img_url},
        }
    }


@pytest.fixture()
def tmp_site(tmp_path):
    """Minimal site directory with images/products/ and credentials.env."""
    (tmp_path / "public/images/products").mkdir(parents=True)
    (tmp_path / "config").mkdir()
    (tmp_path / "config/credentials.env").write_text(f"RAINFOREST_KEY={DUMMY_KEY}\n")
    return tmp_path


# ── 1. Idempotency ────────────────────────────────────────────────────────────

def test_idempotency_already_complete(tmp_site):
    """Calling enrich_product twice on an already-populated entry returns skipped_already_complete."""
    img_path = tmp_site / "public/images/products/my-product.jpg"
    img_path.write_bytes(_tiny_jpeg_bytes())

    entry = {
        "name": "Acme Blaster 3000",
        "brand": "Acme",
        "default_image": "/images/products/my-product.jpg",
        "amazon_asin": "B0012345AB",
    }

    with patch("lib.image_sourcer._call_rainforest") as mock_rf:
        _, meta = enrich_product("my-product", entry, tmp_site, DUMMY_KEY)
        _, meta2 = enrich_product("my-product", entry, tmp_site, DUMMY_KEY)

    assert meta["image_source"] == "skipped_already_complete"
    assert meta2["image_source"] == "skipped_already_complete"
    mock_rf.assert_not_called()


# ── 2. ASIN gating ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("asin", ["NOT_ON_AMAZON", "NOT_FOUND", "VERIFY", "", None, "TOOSHORT", "has-hyphen-0"])
def test_asin_gating_skips_api_call(tmp_site, asin):
    """Products with unusable ASINs never call the Rainforest API."""
    entry = {"name": "Test", "brand": None, "amazon_asin": asin}
    with patch("lib.image_sourcer._call_rainforest") as mock_rf:
        _, meta = enrich_product("test-product", entry, tmp_site, DUMMY_KEY)
    assert meta["image_source"] == "skipped_no_asin"
    mock_rf.assert_not_called()


# ── 3. Force mode ─────────────────────────────────────────────────────────────

def test_force_mode_refetches_despite_populated(tmp_site):
    """force=True triggers a Rainforest call even when both fields are already set."""
    img_path = tmp_site / "public/images/products/lodge-dutch.jpg"
    img_path.write_bytes(_tiny_jpeg_bytes())

    entry = {
        "name": "Lodge Dutch Oven",
        "brand": "Lodge",
        "default_image": "/images/products/lodge-dutch.jpg",
        "amazon_asin": "B00A0FMQQK",
    }

    with patch("lib.image_sourcer._call_rainforest", return_value=_fake_rf_response("Lodge", "Lodge Dutch Oven")):
        with patch("lib.image_sourcer._download_image", return_value=(True, "ok")):
            _, meta = enrich_product("lodge-dutch", entry, tmp_site, DUMMY_KEY, options={"force": True})

    assert meta["image_source"].startswith("rainforest_")


# ── 4. Brand population ───────────────────────────────────────────────────────

def test_brand_populated_from_rainforest(tmp_site):
    """Brand is populated when missing and Rainforest returns one."""
    entry = {"name": "Lodge Dutch Oven", "brand": None, "amazon_asin": "B00A0FMQQK"}

    with patch("lib.image_sourcer._call_rainforest", return_value=_fake_rf_response(brand="Lodge")):
        with patch("lib.image_sourcer._download_image", return_value=(True, "ok")):
            updated, meta = enrich_product("lodge-dutch", entry, tmp_site, DUMMY_KEY)

    assert updated["brand"] == "Lodge"
    assert meta["brand_updated"] is True


def test_brand_not_overwritten_when_already_set(tmp_site):
    """Existing brand is not overwritten unless force=True."""
    entry = {"name": "Lodge Dutch Oven", "brand": "Lodge", "amazon_asin": "B00A0FMQQK"}

    with patch("lib.image_sourcer._call_rainforest", return_value=_fake_rf_response(brand="DIFFERENT")):
        with patch("lib.image_sourcer._download_image", return_value=(True, "ok")):
            updated, meta = enrich_product("lodge-dutch", entry, tmp_site, DUMMY_KEY)

    assert updated["brand"] == "Lodge"
    assert meta["brand_updated"] is False


# ── 5. Image handling ─────────────────────────────────────────────────────────

def test_placeholder_image_not_saved(tmp_site):
    """1×1 pixel image is identified as placeholder and not saved."""
    entry = {"name": "Test", "brand": None, "amazon_asin": "B00A0FMQQK"}

    img_resp = MagicMock()
    img_resp.ok = True
    img_resp.content = _placeholder_jpeg_bytes()

    with patch("lib.image_sourcer._call_rainforest", return_value=_fake_rf_response()):
        with patch("requests.get", return_value=img_resp):
            updated, meta = enrich_product("test-prod", entry, tmp_site, DUMMY_KEY)

    assert meta["image_source"] == "placeholder_returned"
    assert "default_image" not in updated or updated.get("default_image") is None
    assert not (tmp_site / "public/images/products/test-prod.jpg").exists()


def test_valid_image_saved_to_disk(tmp_site):
    """Valid image is saved and default_image is populated."""
    entry = {"name": "Test", "brand": None, "amazon_asin": "B00A0FMQQK"}

    img_resp = MagicMock()
    img_resp.ok = True
    img_resp.content = _tiny_jpeg_bytes()

    with patch("lib.image_sourcer._call_rainforest", return_value=_fake_rf_response()):
        with patch("requests.get", return_value=img_resp):
            updated, meta = enrich_product("test-prod", entry, tmp_site, DUMMY_KEY)

    assert meta["image_updated"] is True
    assert updated["default_image"] == "/images/products/test-prod.jpg"
    assert (tmp_site / "public/images/products/test-prod.jpg").exists()


# ── 6. Title mismatch warning ─────────────────────────────────────────────────

def test_title_mismatch_warning_in_errors(tmp_site):
    """Warning appears in errors when local name and Rainforest title share no significant words."""
    entry = {"name": "Espresso Grinder Pro", "brand": None, "amazon_asin": "B00A0FMQQK"}

    with patch("lib.image_sourcer._call_rainforest",
               return_value=_fake_rf_response(title="Completely Unrelated Toaster Oven 500W")):
        with patch("lib.image_sourcer._download_image", return_value=(True, "ok")):
            _, meta = enrich_product("espresso-grinder", entry, tmp_site, DUMMY_KEY)

    assert any("Title mismatch" in e for e in meta["errors"])


def test_title_match_no_warning(tmp_site):
    """No title-mismatch warning when names share significant words."""
    entry = {"name": "Lodge Cast Iron Dutch Oven", "brand": None, "amazon_asin": "B00A0FMQQK"}

    with patch("lib.image_sourcer._call_rainforest",
               return_value=_fake_rf_response(title="Lodge 5-Quart Cast Iron Dutch Oven")):
        with patch("lib.image_sourcer._download_image", return_value=(True, "ok")):
            _, meta = enrich_product("lodge-dutch", entry, tmp_site, DUMMY_KEY)

    assert not any("Title mismatch" in e for e in meta["errors"])


# ── 7. API failure handling ───────────────────────────────────────────────────

def test_api_failure_returns_entry_unchanged(tmp_site):
    """When API returns None (terminal failure), entry is returned unchanged."""
    entry = {"name": "Test", "brand": None, "amazon_asin": "B00A0FMQQK"}

    with patch("lib.image_sourcer._call_rainforest", return_value=None):
        updated, meta = enrich_product("test-prod", entry, tmp_site, DUMMY_KEY)

    assert meta["image_source"] == "api_failed"
    assert len(meta["errors"]) == 1
    assert updated["brand"] is None


# ── 8. Real ASIN integration test (requires RAINFOREST_KEY) ──────────────────

def _get_rainforest_key():
    key = os.environ.get("RAINFOREST_KEY")
    if not key:
        creds = Path.home() / "strengthmill/config/credentials.env"
        if creds.exists():
            for line in creds.read_text().splitlines():
                if line.startswith("RAINFOREST_KEY="):
                    return line.split("=", 1)[1].strip()
    return key


@pytest.mark.skipif(not _get_rainforest_key(), reason="RAINFOREST_KEY not configured")
def test_real_asin_major_fitness_power_rack(tmp_site):
    """
    Live Rainforest call: MAJOR FITNESS F22 Power Rack (B0C7QZ17C8).
    Confirms brand is populated and image is saved with valid dimensions.
    """
    key = _get_rainforest_key()
    slug = "major-fitness-f22-power-rack"
    entry = {
        "name": "MAJOR FITNESS F22 Power Rack",
        "brand": None,
        "amazon_asin": "B0C7QZ17C8",
        "hub": "racks",
    }

    updated, meta = enrich_product(slug, entry, tmp_site, key)

    print(f"\nLive test result: brand={updated.get('brand')!r}, "
          f"image_source={meta['image_source']}, errors={meta['errors']}")

    # API must have reached Rainforest successfully
    assert meta["image_source"] not in ("api_failed", "skipped_no_asin"), (
        f"API call failed unexpectedly: {meta}"
    )

    # Brand must be populated (Rainforest returns 'MAJOR FITNESS' for this ASIN)
    assert updated.get("brand"), f"brand not populated — meta: {meta}"
    assert meta["brand_updated"] is True

    # Image file must exist on disk with valid dimensions
    img_path = tmp_site / "public/images/products" / f"{slug}.jpg"
    if meta["image_updated"]:
        from PIL import Image
        assert img_path.exists(), "Image file not saved to disk"
        w, h = Image.open(img_path).size
        assert w > 2 and h > 2, f"Image dimensions too small: {w}×{h}"
