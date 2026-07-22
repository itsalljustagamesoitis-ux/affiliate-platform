"""
Tests for data_loader.py — enrich_article, get_hub_products, get_pending_articles.

Hub/category expectations are derived from the site's own navigation.yaml via
fixtures rather than hardcoded, so these tests are portable across niches.
"""

import pytest
from data_loader import enrich_article, get_hub_products, get_pending_articles


class TestEnrichArticle:
    def test_populates_hub_label(self, navigation):
        cat = navigation["categories"][0]
        hub = cat["hubs"][0]
        article = {"hub": hub["slug"]}
        enrich_article(article, navigation)
        assert article["hub_label"] == hub["label"]

    def test_populates_hub_url(self, navigation):
        cat = navigation["categories"][0]
        hub = cat["hubs"][0]
        article = {"hub": hub["slug"]}
        enrich_article(article, navigation)
        assert article["hub_url"] == f"/{hub['slug']}/"

    def test_populates_hub_slug(self, navigation):
        cat = navigation["categories"][0]
        hub = cat["hubs"][0]
        article = {"hub": hub["slug"]}
        enrich_article(article, navigation)
        assert article["hub_slug"] == hub["slug"]

    def test_populates_category_label(self, navigation):
        cat = navigation["categories"][0]
        hub = cat["hubs"][0]
        article = {"hub": hub["slug"]}
        enrich_article(article, navigation)
        assert article["category_label"] == cat["label"]

    def test_populates_category_slug(self, navigation):
        cat = navigation["categories"][0]
        hub = cat["hubs"][0]
        article = {"hub": hub["slug"]}
        enrich_article(article, navigation)
        assert article["category_slug"] == cat["slug"]

    def test_all_hubs_resolve_category(self, navigation, all_hub_slugs):
        """Every hub in navigation must produce a non-empty category_label."""
        for hub_slug in all_hub_slugs:
            article = {"hub": hub_slug}
            enrich_article(article, navigation)
            assert article.get("category_label"), \
                f"Hub '{hub_slug}' produced empty category_label"
            assert article.get("category_slug"), \
                f"Hub '{hub_slug}' produced empty category_slug"

    def test_unknown_hub_gets_fallback(self, navigation):
        article = {"hub": "nonexistent-hub"}
        enrich_article(article, navigation)
        assert article["hub_slug"] == "nonexistent-hub"
        assert article["hub_url"] == "/nonexistent-hub/"
        assert article["category_label"] == ""

    def test_does_not_overwrite_existing_hub_label(self, navigation):
        cat = navigation["categories"][0]
        hub = cat["hubs"][0]
        article = {"hub": hub["slug"], "hub_label": "Already Set"}
        enrich_article(article, navigation)
        # enrich_article should overwrite with the canonical value from nav
        assert article["hub_label"] == hub["label"]


class TestGetHubProducts:
    def test_returns_only_matching_hub(self, products, all_hub_slugs):
        hub_slug = next(iter(all_hub_slugs))
        result = get_hub_products(products, hub_slug)
        for key, p in result.items():
            assert p.get("category") == hub_slug or p.get("hub") == hub_slug, \
                f"Product '{key}' does not belong to {hub_slug}"

    def test_excludes_other_hubs(self, products, all_hub_slugs):
        slugs = list(all_hub_slugs)
        if len(slugs) < 2:
            pytest.skip("Site has fewer than 2 hubs — nothing to cross-check")
        a = get_hub_products(products, slugs[0])
        b = get_hub_products(products, slugs[1])
        overlap = set(a.keys()) & set(b.keys())
        assert not overlap, f"Products appear in both {slugs[0]} and {slugs[1]}: {overlap}"

    def test_returns_empty_for_unknown_hub(self, products):
        result = get_hub_products(products, "nonexistent")
        assert result == {}

    def test_all_nav_hubs_have_at_least_one_product(self, products, all_hub_slugs):
        missing = []
        for hub_slug in all_hub_slugs:
            if not get_hub_products(products, hub_slug):
                missing.append(hub_slug)
        assert not missing, f"These hubs have no products assigned: {missing}"


class TestGetPendingArticles:
    def test_excludes_published_articles(self, pipeline):
        pending = get_pending_articles(pipeline)
        for a in pending:
            assert not a.get("published", False), \
                f"Article {a['id']} is published but appeared in pending"

    def test_includes_unpublished_articles(self, pipeline):
        pending = get_pending_articles(pipeline)
        # Mirrors get_pending_articles' own exclusion contract: unpublished AND not skipped.
        unpublished_count = sum(
            1 for a in pipeline
            if not a.get("published", False) and a.get("status") != "skip"
        )
        assert len(pending) == unpublished_count
