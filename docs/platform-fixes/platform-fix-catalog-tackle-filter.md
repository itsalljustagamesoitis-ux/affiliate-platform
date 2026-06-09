# Platform Fix: Catalog Tackle-Type Filter

**Type:** Producer-side content gate  
**Severity if missed:** SEV-1 (wrong product category on live article)  
**First surfaced:** Site 15 (rmflyfishing) Phase 4 UAT — bait fishing products (Tigofly minnow lure, Sabiki rigs) in a fly fishing article  
**Status:** Backlog — partially addressed by manual product replacement; structural fix not yet implemented

---

## Problem

The Rainforest product sourcing tool (`tools/source-products-rainforest.py`) retrieves products by Amazon search query. For fly fishing content, a query like "fly fishing flies bass" can return conventional bait fishing products alongside genuine fly fishing products because Amazon's catalog is not structured around this distinction.

Products sourced this way land in `products.yaml` with hub and category metadata set by the sourcing query. If the sourcing result includes tackle that is incompatible with the content's editorial focus (e.g., a bait-cast lure in a fly pattern article), and that product gets assigned to an article without a per-product review, the article ships with editorially wrong product recommendations.

On Site 15, `best-saltwater-flies.md` shipped with:
- `tigofly-10-pcs-10-colors` — a lure set for conventional tackle
- `sabiki-rigs-set-20-pack` — bait fishing rigs incompatible with fly fishing

Both were sourced from Amazon under fly fishing queries but are not fly fishing products.

## Root Cause

`products.yaml` has no `tackle_type` field to distinguish fly fishing products from conventional bait/lure products. The sourcing tool and producer accept any product in the catalog for any article in the matching hub. The build validates hub match but not product-category fit.

## Fix

### 1. Add `tackle_type` field to `products.yaml` schema

```yaml
# In products.yaml, for each product:
tackle_type: fly_fishing  # or: conventional, bait, lure, trolling, general
```

Default: `fly_fishing` (most products in this catalog are correct). Flag anything else explicitly.

### 2. Add Rainforest sourcing filter

In `tools/source-products-rainforest.py`, after fetching results:

```python
FORBIDDEN_KEYWORDS = [
    'sabiki', 'bait rig', 'spinning lure', 'treble hook',
    'live bait', 'crankbait', 'spinnerbait', 'jig head',
]

def is_fly_fishing_product(product_title: str) -> bool:
    title_lower = product_title.lower()
    return not any(kw in title_lower for kw in FORBIDDEN_KEYWORDS)
```

### 3. Add validator check

In `scripts/preflight.py` or `build-validator.mjs`:

```python
# Flag products with tackle_type != fly_fishing appearing in fly fishing articles
for product_ref in article.products:
    product = products[product_ref.id]
    if product.get('tackle_type', 'fly_fishing') != 'fly_fishing':
        raise ValidationError(f"Product {product_ref.id} is {product['tackle_type']} tackle in fly fishing article {article.slug}")
```

## Permanent Fix

The `tackle_type` field should be added to the `products.yaml` schema and populated during sourcing. The validator should FAIL any article that references a non-fly-fishing product in a fly-fishing context (or be made hub-aware: `fly_fishing` products can only appear in fly fishing hubs).

This is a broader instance of the "product-hub coherence" validator that already exists in Rule 2 of CLAUDE.md, but extended to product category within a hub.

## Related

- `platform-fix-product-slug-resolution.md` — related static analysis for product references
