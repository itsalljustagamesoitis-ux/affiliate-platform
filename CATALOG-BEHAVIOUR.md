# Catalog-Growth Behaviour — Platform Spec

**Scope:** All sites consuming `@platform/core` (FSG, MLT, OHT)  
**Status:** Active  
**Applies to:** Producer implementations, ASIN-fill tooling, build validator

---

## 1. Statement of Intent

The producer generates articles from briefs. A brief references products by `id`. Those products must exist in `content/products/products.yaml` before the article can be generated. But the catalog grows during generation: as new article types and niches are added, new products are needed that don't yet have confirmed ASINs.

This spec defines the contract for how that growth happens without blocking generation and without compromising build integrity.

The key design decision: **ASIN resolution is a separate batch operation that runs after generation, not before.** The producer writes `amazon_asin: VERIFY` as a sentinel. The build fails on VERIFY — but generation doesn't. The gap between generation and a clean build is closed by the ASIN-fill cycle described in Section 4.

---

## 2. Producer Responsibility — Adding Products to the Catalog

When the producer needs a product that does not yet exist in `content/products/products.yaml`, it adds the entry itself before generating the article. This is not optional: an article that references a non-existent product id will fail the pre-generation check (Rule 2).

### Entry format

New entries must follow the dict-keyed-by-slug format used across all sites:

```yaml
{product-slug}:
  name: "{Full product display name}"
  brand: "{Brand name}"
  hub: "{hub_slug}"                          # must match article's hub field
  amazon_asin: VERIFY                        # always VERIFY at creation; resolved in fill cycle
  price_band: "{budget | mid | premium | luxury}"
  default_pros:
    - "{pro — product-specific, not generic}"
  default_cons:
    - "{con — product-specific, not generic}"
  notes_for_writers: "added by producer during {article_slug} generation, {ISO-8601 timestamp}"
```

### Required fields at creation

| Field | Rule |
|-------|------|
| slug (YAML key) | Derived from brand + product name: lowercase, kebab-case, stop-words stripped. See slug derivation below. |
| `name` | Full product display name as it will appear in article prose. |
| `brand` | Brand name only — no model numbers. |
| `hub` | Must match the article's `hub` frontmatter field exactly. Any mismatch → Rule 2 violation. |
| `amazon_asin` | Always `VERIFY` at creation. Never invent an ASIN. |
| `price_band` | One of: `budget`, `mid`, `premium`, `luxury`. |
| `default_pros` | At least one product-specific pro. Not generic ("durable", "easy to use"). |
| `default_cons` | At least one product-specific con. |
| `notes_for_writers` | Must record when and why the entry was added. |

### Slug derivation

Slugify `"{brand} {product_name}"`:
1. Lowercase the combined string
2. Replace non-alphanumeric characters with hyphens
3. Strip common stop words: `the`, `a`, `an`, `and`, `for`, `of`, `in`, `with`, `by`
4. Collapse consecutive hyphens to one
5. Strip leading/trailing hyphens

Examples:
- `"Lodge 12-Inch Cast Iron Skillet"` → `lodge-12-inch-cast-iron-skillet`
- `"All-Clad D3 Stainless 2-Quart Saucepan"` → `all-clad-d3-stainless-2-quart-saucepan`
- `"Waterford Lismore Crystal Champagne Flute Pair"` → `waterford-lismore-crystal-champagne-flute-pair`

### Conflict check

Before adding a new entry, the producer must check whether the derived slug already exists in `products.yaml`:

- **Slug exists, same name and brand:** The product is already in the catalog. Use the existing entry, do not add a duplicate.
- **Slug exists, different name or brand:** Collision. The producer halts and surfaces the conflict. Does not silently overwrite; does not silently accept either candidate. Requires human resolution before generation proceeds.
- **Slug does not exist:** Add the entry.

### What the producer must NOT do

- Invent an ASIN. If the brief contains a confirmed ASIN, the producer uses it. Otherwise, `amazon_asin: VERIFY` — always.
- Add a product with a `hub` that does not match the article's hub (Rule 2).
- Silently overwrite an existing entry that has a different name/brand.
- Leave `default_pros` or `default_cons` empty — a product with no pros or cons logged is not ready for article generation.

---

## 3. Validator Responsibility

This section is specified for the validator implementation session. It does not need to be implemented now; it records the intended contract so the validator catches up to the producer's behaviour.

### Article-level checks

`validate-roundup.mjs` and `validate-buyer-guide.mjs` (when built) must verify:

- Every `product:slug` link in the article body resolves to an entry in `content/products/products.yaml`.
- Every product `id` in the article's `products:` frontmatter array has a matching entry in `products.yaml`.
- Every product's `hub` field in `products.yaml` matches the article's `hub` frontmatter field.

### VERIFY is not a validator error

Producer-added entries with `amazon_asin: VERIFY` pass the article-level validator. VERIFY is a sentinel meaning "real product, ASIN not yet confirmed." It is expected state during the generation → fill cycle.

### VERIFY is a build error

The build-time validator (`scripts/build-validator.mjs`) fails on any article that references a product with `amazon_asin: VERIFY`. This is the gate that prevents VERIFY from reaching production. The separation is intentional:

| Stage | VERIFY verdict |
|-------|---------------|
| Generation | Permitted |
| Article validation | Permitted |
| Build (`npm run build`) | **FAIL** |
| Production deploy | **Blocked** (build must be clean first) |

---

## 4. The ASIN-Fill Cycle

After a generation run produces articles that reference VERIFY products, the following cycle resolves them before the next build.

### Step 1 — Audit

Run the VERIFY audit tool to produce a fill sheet:

```bash
node tools/audit-verify.mjs --site <site-path>
```

`audit-verify.mjs` does not exist yet — it is specified here for a future session. When built, it will:
- Walk `content/products/products.yaml`
- Identify all entries with `amazon_asin: VERIFY`
- Cross-reference each against `content/articles/` to count how many published articles reference the product (blast radius)
- Emit a fill sheet in the format used by `VERIFY-ASIN-FILL.csv` (see `one-happy-table/VERIFY-ASIN-FILL.csv` for the format)
- Sort by blast radius descending (highest impact first)

Until `audit-verify.mjs` exists, the fill sheet is produced manually by the process documented in `one-happy-table/VERIFY-ASIN-FILL.csv`.

### Step 2 — Populate

The operator opens the fill sheet in any spreadsheet tool and populates the `asin` column:
- Real ASINs confirmed via Amazon lookup
- `NOT_ON_AMAZON` for products that exist but are not on Amazon
- Leave blank to skip (the fill tool silently skips blank rows)

### Step 3 — Apply

```bash
node tools/fill-asins-yaml.mjs --site <site-path> --input <csv-path>
```

`fill-asins-yaml.mjs` applies the populated fill sheet back to `products.yaml`, replacing `VERIFY` entries with confirmed values. It validates ASIN format before writing. See `affiliate-platform/tools/fill-asins-yaml.mjs` for implementation.

### Step 4 — Verify and build

```bash
grep -c "amazon_asin: VERIFY" content/products/products.yaml
# must return 0

npm run build
# must exit 0 with no FAIL lines
```

---

## 5. The NOT_ON_AMAZON Contract

Some products that belong in articles are not available on Amazon — manufacturer direct-only, region-limited availability, or platform exclusions. The editorial position is to write about the best products regardless of affiliate availability, and route monetization separately when traffic justifies it.

### How to mark

In `products.yaml`, set `amazon_asin: NOT_ON_AMAZON` for any product confirmed not available on Amazon.

### How it renders

The rehype plugin (`src/plugins/rehype-product-links.mjs`) handles `NOT_ON_AMAZON` explicitly:
- `[product name](product:slug)` links where the product has `amazon_asin: NOT_ON_AMAZON` render as `<span data-product="{slug}" data-unavailable="true">product name</span>`
- No affiliate link is generated
- No dead link is rendered — the anchor text is preserved as plain text

This is confirmed behaviour (implemented in `rehype-product-links.mjs` line 85).

### Future routing

The `data-unavailable="true"` attribute is the hook for future non-Amazon affiliate routing (AWIN, Impact, CJ). When traffic on a NOT_ON_AMAZON product justifies direct retailer integration, the rehype plugin or a post-processing step can upgrade `data-unavailable` spans to the appropriate affiliate URL format. No article edits needed.

### What NOT_ON_AMAZON is NOT

- NOT_ON_AMAZON is not an error state. It is a confirmed editorial decision.
- NOT_ON_AMAZON entries do not trigger build failures.
- NOT_ON_AMAZON entries do not count against the VERIFY audit. `audit-verify.mjs` targets only `VERIFY`, not `NOT_ON_AMAZON`.
