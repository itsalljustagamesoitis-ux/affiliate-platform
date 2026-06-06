"""
Cross-file schema validation: pipeline.json × products.yaml × navigation.yaml.

These tests catch consistency errors that can't be caught by inspecting any single
file in isolation — e.g. a product hub that doesn't match the article hub it's
assigned to, or a pipeline type that hasn't been normalised to underscore form.
"""

import re
import pytest

VALID_TYPES   = {"roundup", "review", "comparison", "buyer_guide", "informational"}
KEBAB_RE      = re.compile(r'^[a-z0-9]+(-[a-z0-9]+)*$')
VALID_BANDS   = {"budget", "mid", "premium"}


class TestPipelineProductsCrossRef:
    """Verify every product key referenced in pipeline.json exists in products.yaml."""

    def test_all_pipeline_product_keys_exist_in_catalog(self, pipeline, products):
        bad = []
        for a in pipeline:
            for key in a.get("products", []):
                if key not in products:
                    bad.append(f"article '{a['slug']}' → product key '{key}' not in products.yaml")
        assert not bad, f"{len(bad)} dangling product references:\n" + "\n".join(bad[:10])

    def test_product_hub_matches_article_hub(self, pipeline, products):
        """Rule 2: a product's hub must match the article it is assigned to.
        Products may declare hub: single-string OR hubs: [list] (B49 multi-hub support).
        """
        bad = []
        for a in pipeline:
            article_hub = a.get("hub_slug") or a.get("hub", "")
            for key in a.get("products", []):
                p = products.get(key)
                if not p:
                    continue
                hubs_field = p.get("hubs")
                if isinstance(hubs_field, list):
                    product_hubs = hubs_field
                else:
                    single = p.get("hub") or p.get("category", "")
                    product_hubs = [single] if single else []
                if product_hubs and article_hub and article_hub not in product_hubs:
                    bad.append(
                        f"article '{a['slug']}' (hub={article_hub}) "
                        f"→ product '{key}' (hubs={product_hubs})"
                    )
        assert not bad, (
            f"{len(bad)} product-hub mismatches (Rule 2):\n" + "\n".join(bad[:10])
        )


class TestPipelineNavigationCrossRef:
    """Verify every hub slug referenced in pipeline.json exists in navigation.yaml."""

    def test_all_pipeline_hubs_in_navigation(self, pipeline, all_hub_slugs):
        bad = []
        for a in pipeline:
            hub = a.get("hub_slug") or a.get("hub", "")
            if hub and hub not in all_hub_slugs:
                bad.append(f"article '{a['slug']}': hub='{hub}'")
        assert not bad, (
            f"{len(bad)} pipeline articles reference hubs absent from navigation.yaml:\n"
            + "\n".join(bad[:10])
        )


class TestProductsNavigationCrossRef:
    """Verify every product's hub exists in navigation.yaml."""

    def test_all_product_hubs_in_navigation(self, products, all_hub_slugs):
        bad = []
        for key, p in products.items():
            hubs_field = p.get("hubs")
            if isinstance(hubs_field, list):
                check_hubs = hubs_field
            else:
                single = p.get("hub") or p.get("category", "")
                check_hubs = [single] if single else []
            for hub in check_hubs:
                if hub and hub not in all_hub_slugs:
                    bad.append(f"product '{key}': hub='{hub}'")
        assert not bad, (
            f"{len(bad)} products reference hubs absent from navigation.yaml:\n"
            + "\n".join(bad[:10])
        )


class TestTypeFieldFormat:
    """Pipeline type values must be lowercase_underscore — no spaces or Title Case."""

    def test_pipeline_types_are_normalised(self, pipeline):
        bad = []
        for a in pipeline:
            t = a.get("type", "")
            if t and t not in VALID_TYPES:
                bad.append(f"article '{a['slug']}': type='{t}'")
        assert not bad, (
            f"{len(bad)} articles have invalid or non-normalised type values:\n"
            + "\n".join(bad[:10])
        )

    def test_pipeline_types_contain_no_spaces(self, pipeline):
        bad = [
            f"article '{a['slug']}': type='{a['type']}'"
            for a in pipeline
            if " " in str(a.get("type", ""))
        ]
        assert not bad, f"Article types with spaces (should use underscore):\n" + "\n".join(bad)


class TestHubSlugFormat:
    """Hub slugs everywhere must be kebab-case."""

    def test_pipeline_hub_slugs_are_kebab(self, pipeline):
        bad = []
        for a in pipeline:
            hub = a.get("hub_slug") or a.get("hub", "")
            if hub and not KEBAB_RE.match(hub):
                bad.append(f"article '{a['slug']}': hub='{hub}'")
        assert not bad, (
            f"{len(bad)} pipeline articles have non-kebab hub slugs:\n" + "\n".join(bad[:10])
        )

    def test_product_hub_slugs_are_kebab(self, products):
        bad = []
        for key, p in products.items():
            hubs_field = p.get("hubs")
            if isinstance(hubs_field, list):
                check_hubs = hubs_field
            else:
                single = p.get("hub") or p.get("category", "")
                check_hubs = [single] if single else []
            for hub in check_hubs:
                if hub and not KEBAB_RE.match(hub):
                    bad.append(f"product '{key}': hub='{hub}'")
        assert not bad, (
            f"{len(bad)} products have non-kebab hub slugs:\n" + "\n".join(bad[:10])
        )

    def test_navigation_hub_slugs_are_kebab(self, navigation):
        bad = []
        for cat in navigation.get("categories", []):
            if not KEBAB_RE.match(cat.get("slug", "")):
                bad.append(f"category slug: '{cat.get('slug')}'")
            for hub in cat.get("hubs", []):
                if not KEBAB_RE.match(hub.get("slug", "")):
                    bad.append(f"hub slug: '{hub.get('slug')}'")
        assert not bad, f"Non-kebab slugs in navigation.yaml:\n" + "\n".join(bad)


class TestProductsCompleteness:
    """Products must have all fields required by the platform builder.

    Mirrors test_all_products_have_required_fields in test_pipeline_integrity.py
    but focused on sourced (Phase 1) products specifically — i.e. products that
    have a 'confidence' field set by source-products-rainforest.py.
    """

    def test_sourced_products_have_price_band(self, products):
        bad = []
        for key, p in products.items():
            if "confidence" not in p:
                continue  # skip manually-curated products
            band = p.get("price_band", "")
            if band not in VALID_BANDS:
                bad.append(f"'{key}': price_band='{band}'")
        assert not bad, (
            f"{len(bad)} sourced products have invalid price_band:\n" + "\n".join(bad[:10])
        )

    def test_sourced_products_have_amazon_asin_key(self, products):
        bad = []
        for key, p in products.items():
            if "confidence" not in p:
                continue
            if "amazon_asin" not in p and "asin" not in p:
                bad.append(f"'{key}': neither amazon_asin nor asin key present")
        assert not bad, (
            f"{len(bad)} sourced products missing ASIN field:\n" + "\n".join(bad[:10])
        )

    def test_sourced_products_have_editorial_data(self, products):
        bad = []
        for key, p in products.items():
            if "confidence" not in p:
                continue
            has_pros_cons = p.get("default_pros") and p.get("default_cons")
            has_notes = p.get("notes_for_writers")
            if not has_pros_cons and not has_notes:
                bad.append(f"'{key}': missing default_pros/default_cons or notes_for_writers")
        assert not bad, (
            f"{len(bad)} sourced products have no editorial data:\n" + "\n".join(bad[:10])
        )
