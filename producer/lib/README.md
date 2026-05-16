# producer/lib — shared enrichment utilities

## image_sourcer.py

Fetches product image and brand data from the Rainforest API and writes them into
a product catalog entry. Designed to be called by any site producer or backfill script.

### Quick start

```python
from pathlib import Path
from lib.image_sourcer import enrich_product, load_rainforest_key

site_root = Path("/Users/keithlacy/strengthmill")
key = load_rainforest_key(site_root)   # reads RAINFOREST_KEY from env or config/credentials.env

entry = products["major-fitness-f22-power-rack"]   # dict from products.yaml
updated, meta = enrich_product("major-fitness-f22-power-rack", entry, site_root, key)

if meta["image_updated"] or meta["brand_updated"]:
    products["major-fitness-f22-power-rack"] = updated
    # write products back to disk
```

### Function signature

```python
def enrich_product(
    slug: str,
    product_entry: dict,
    site_root: Path | str,
    rainforest_key: str,
    options: dict | None = None,
) -> tuple[dict, dict]:
```

**Returns** `(updated_entry, metadata)`. The returned entry is a copy — the original is
never mutated.

### Options

| Key | Default | Effect |
|-----|---------|--------|
| `skip_image` | `False` | Do not fetch or save image |
| `skip_brand` | `False` | Do not populate brand field |
| `force` | `False` | Re-fetch even if both fields are already populated |

### Metadata dict

| Key | Type | Values |
|-----|------|--------|
| `image_updated` | bool | `True` if `default_image` was set in this call |
| `brand_updated` | bool | `True` if `brand` was set in this call |
| `image_source` | str | See status codes below |
| `errors` | list[str] | Non-fatal warnings (title mismatch, download failures) |

### image_source status codes

| Code | Meaning |
|------|---------|
| `skipped_already_complete` | Both brand and image already populated; no API call made |
| `skipped_no_asin` | ASIN is missing, sentinel (NOT_ON_AMAZON / NOT_FOUND / VERIFY), or not a valid 10-char ASIN |
| `api_failed` | Rainforest API call failed after retries |
| `rainforest_asin_not_found` | Rainforest returned 404 for this ASIN |
| `rainforest_YYYY-MM-DD` | Image fetched successfully on this date |
| `placeholder_returned` | Image URL resolved to a 1×1 pixel placeholder; not saved |
| `no_image_url` | Rainforest returned no image URL in response |
| `image_url_failed_NNN` | Image download returned HTTP NNN |
| `image_error_ExceptionType` | Unexpected error during image download/save |

### Rate limiting

The library enforces a minimum 500ms gap between Rainforest API calls internally.
Callers do not need to add their own `time.sleep()` between calls.

### Retries

Rainforest 429 / 5xx → exponential backoff: 2s, 4s, 8s, 16s (max 4 retries).
Network timeout → up to 3 retries, then the entry is returned unchanged.

### ASIN field name

The library checks both `amazon_asin` (used by newer sites) and `asin` (used by TCD / older
Rainforest-sourced catalogs). No changes needed to existing catalog entries.

### Image path

Images are saved to:
```
<site_root>/public/images/products/<slug>.jpg
```
at JPEG quality 90 after passing a PIL dimension check (width > 2, height > 2).

The `default_image` field is set to `/images/products/<slug>.jpg` (relative URL
for Astro to serve).

### Credentials

`load_rainforest_key(site_root)` checks (in order):
1. `RAINFOREST_KEY` environment variable
2. `<site_root>/config/credentials.env` — line starting with `RAINFOREST_KEY=`

Returns `None` if not found. Callers should check for `None` and skip enrichment
gracefully when the key is not configured (backwards-compatible for sites that
don't yet have Rainforest access).

### Tests

```bash
cd affiliate-platform/producer
python3 -m pytest lib/test_image_sourcer.py -v
```

The live integration test requires `RAINFOREST_KEY` to be set and makes a real
Rainforest API call. All other tests are fully mocked and run without credentials.
