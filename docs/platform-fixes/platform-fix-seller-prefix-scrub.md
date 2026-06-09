# Platform Fix: Amazon Seller Prefix in Product Brand Field

**Type:** Data quality / Rainforest sourcing fix  
**Severity if missed:** SEV-3 (wrong brand name rendered to readers)  
**First surfaced:** Site 15 (rmflyfishing) Phase 4 UAT — `patagonia-swiftcurrent` had `brand: STOVER` instead of `brand: Patagonia`  
**Status:** Fixed manually on Site 15 (single product); sourcing tool fix not yet implemented

---

## Problem

The Rainforest API (`tools/source-products-rainforest.py`) populates the `brand` field of `products.yaml` entries from the Amazon product listing's brand attribute. Amazon product listings sometimes show the *marketplace seller* name rather than the *brand* as the brand attribute. Common examples:

- `STOVER` (an Amazon third-party seller) instead of `Patagonia`
- Generic seller names like `DEALS` or vendor codes instead of the actual manufacturer

The result: `ProductCard.astro` and `ComparisonTable.astro` render the seller name to readers as the brand. A reader sees "STOVER" where they expect "Patagonia."

## Site 15 Instance

`patagonia-swiftcurrent` had `brand: STOVER` in `products.yaml`. Fixed manually:
```yaml
# Before
brand: STOVER

# After
brand: Patagonia
```

## Root Cause

Rainforest's `brand` field on sponsored or third-party Amazon listings can return the seller name when the brand is not explicitly set on the listing. The sourcing tool accepts this value without validation.

## Fix

### 1. Sourcing-time scrub

In `tools/source-products-rainforest.py`, after fetching brand:

```python
KNOWN_SELLER_PREFIXES = [
    'STOVER', 'DEALS', 'WAREHOUSE', 'SELLER', 'DIRECT',
    # Add others as discovered
]

def scrub_brand(brand: str, product_title: str) -> str:
    """Return brand, falling back to name inference if brand looks like a seller."""
    if not brand or brand.upper() in KNOWN_SELLER_PREFIXES:
        # Attempt to infer brand from title
        # Most product titles start with brand name
        return product_title.split()[0] if product_title else None
    return brand
```

This is heuristic and imperfect — but catches obvious cases.

### 2. Build-time validator

In `build-validator.mjs` or `scripts/preflight.py`:

```javascript
// Flag brand values that are all-caps 3-8 character codes (likely seller prefixes)
const ALL_CAPS_CODE = /^[A-Z]{3,8}$/
for (const [id, product] of Object.entries(products)) {
  if (product.brand && ALL_CAPS_CODE.test(product.brand)) {
    results.push({ level: 'WARN', check: 'seller-prefix', product: id, brand: product.brand })
  }
}
```

This fires on obvious seller codes like `STOVER`, `DEALS`, etc.

### 3. Post-sourcing review

Add to the new-product review checklist:
- `[ ] No brand field contains an all-caps 3-8 char code (seller prefix)`

## Done Criteria

- `tools/source-products-rainforest.py` runs brand through `scrub_brand()` before writing to products.yaml
- `build-validator.mjs` WARNs on all-caps brand codes
- `products.yaml` has 0 all-caps brand entries: `python3 -c "import yaml,re; p=yaml.safe_load(open('content/products/products.yaml')); [print(k,v['brand']) for k,v in p.items() if v.get('brand') and re.match(r'^[A-Z]{3,8}$', str(v['brand']))]"`

## Related

- `platform-fix-catalog-tackle-filter.md` — related product data quality issue from Rainforest sourcing
