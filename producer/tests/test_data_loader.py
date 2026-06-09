"""
Tests for data_loader.py — enrich_article, get_hub_products, get_pending_articles,
save_pipeline persistence.
"""

import json
import pytest
from pathlib import Path
from data_loader import enrich_article, get_hub_products, get_pending_articles, save_pipeline


class TestEnrichArticle:
    def _first_hub(self, all_hub_slugs):
        return next(iter(sorted(all_hub_slugs)))

    def test_populates_hub_label(self, navigation, all_hub_slugs):
        hub_slug = self._first_hub(all_hub_slugs)
        article = {"hub": hub_slug}
        enrich_article(article, navigation)
        assert article.get("hub_label"), f"hub_label empty for hub '{hub_slug}'"

    def test_populates_hub_url(self, navigation, all_hub_slugs):
        hub_slug = self._first_hub(all_hub_slugs)
        article = {"hub": hub_slug}
        enrich_article(article, navigation)
        assert article.get("hub_url") == f"/{hub_slug}/"

    def test_populates_hub_slug(self, navigation, all_hub_slugs):
        hub_slug = self._first_hub(all_hub_slugs)
        article = {"hub": hub_slug}
        enrich_article(article, navigation)
        assert article.get("hub_slug") == hub_slug

    def test_populates_category_label(self, navigation, all_hub_slugs):
        hub_slug = self._first_hub(all_hub_slugs)
        article = {"hub": hub_slug}
        enrich_article(article, navigation)
        assert article.get("category_label"), f"category_label empty for hub '{hub_slug}'"

    def test_populates_category_slug(self, navigation, all_hub_slugs):
        hub_slug = self._first_hub(all_hub_slugs)
        article = {"hub": hub_slug}
        enrich_article(article, navigation)
        assert article.get("category_slug"), f"category_slug empty for hub '{hub_slug}'"

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

    def test_does_not_overwrite_existing_hub_label(self, navigation, all_hub_slugs):
        hub_slug = self._first_hub(all_hub_slugs)
        article_clean = {"hub": hub_slug}
        enrich_article(article_clean, navigation)
        expected_label = article_clean["hub_label"]
        article = {"hub": hub_slug, "hub_label": "Already Set"}
        enrich_article(article, navigation)
        assert article["hub_label"] == expected_label, \
            f"hub_label not overwritten: expected '{expected_label}', got '{article['hub_label']}'"


class TestGetHubProducts:
    def test_returns_only_matching_hub(self, products, all_hub_slugs):
        hub_slug = next(iter(sorted(all_hub_slugs)))
        result = get_hub_products(products, hub_slug)
        for key, p in result.items():
            assert p.get("category") == hub_slug or p.get("hub") == hub_slug, \
                f"Product '{key}' does not belong to '{hub_slug}'"

    def test_excludes_other_hubs(self, products, all_hub_slugs):
        sorted_hubs = sorted(all_hub_slugs)
        hub_a = sorted_hubs[0]
        hub_b = sorted_hubs[1] if len(sorted_hubs) > 1 else "nonexistent"
        result_a = get_hub_products(products, hub_a)
        result_b = get_hub_products(products, hub_b)
        overlap = set(result_a.keys()) & set(result_b.keys())
        assert not overlap, f"Products appear in both {hub_a} and {hub_b}: {overlap}"

    def test_returns_empty_for_unknown_hub(self, products):
        result = get_hub_products(products, "nonexistent")
        assert result == {}

    def test_all_pipeline_hubs_have_at_least_one_product(self, products, pipeline_hub_slugs):
        """Hubs referenced in the pipeline must have products — nav-only hubs are future work."""
        missing = []
        for hub_slug in pipeline_hub_slugs:
            if not get_hub_products(products, hub_slug):
                missing.append(hub_slug)
        assert not missing, f"These pipeline hubs have no products assigned: {missing}"


class TestGetPendingArticles:
    def test_excludes_published_articles(self, pipeline):
        pending = get_pending_articles(pipeline)
        for a in pending:
            assert not a.get("published", False), \
                f"Article {a['id']} is published but appeared in pending"

    def test_includes_unpublished_articles(self, pipeline):
        pending = get_pending_articles(pipeline)
        eligible_count = sum(
            1 for a in pipeline
            if not a.get("published", False) and a.get("status") != "skip"
        )
        assert len(pending) == eligible_count


class TestSavePipelinePersistence:
    """
    Verify that save_pipeline merges in-memory status updates without
    overwriting manual structural edits made to pipeline.json on disk.

    This guards against the Ten27 Phase 4 bug where manual skip flags and
    product corrections were lost when save_pipeline() was called mid-run.
    """

    def _make_site(self, tmp_path: Path) -> Path:
        """Create a minimal fake site root with data/ and content/products/."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (tmp_path / "content" / "products").mkdir(parents=True)
        (tmp_path / "content" / "products" / "products.yaml").write_text("")
        return tmp_path

    def _write_pipeline(self, site_root: Path, articles: list) -> None:
        path = site_root / "data" / "pipeline.json"
        path.write_text(json.dumps({"articles": articles}, indent=2))

    def _read_pipeline(self, site_root: Path) -> list:
        path = site_root / "data" / "pipeline.json"
        data = json.loads(path.read_text())
        return data.get("articles", data) if isinstance(data, dict) else data

    def test_status_update_written_to_disk(self, tmp_path):
        site_root = self._make_site(tmp_path)
        base = [{"id": 1, "slug": "a", "status": "pending", "products": ["p1"]}]
        self._write_pipeline(site_root, base)

        in_memory = [{"id": 1, "slug": "a", "status": "staged", "products": ["p1"]}]
        save_pipeline(in_memory, site_root)

        saved = self._read_pipeline(site_root)
        assert saved[0]["status"] == "staged"

    def test_manual_product_edit_survives(self, tmp_path):
        """
        Scenario: Keith manually edits products for article #1 in pipeline.json
        while the producer is between runs. save_pipeline() must not overwrite
        the product list.
        """
        site_root = self._make_site(tmp_path)

        # Initial pipeline (what was on disk when producer last ran)
        initial = [{"id": 1, "slug": "a", "status": "staged", "products": ["old-product"]}]
        self._write_pipeline(site_root, initial)

        # Keith manually updates products to ["new-product"] on disk
        disk_with_edit = [{"id": 1, "slug": "a", "status": "staged", "products": ["new-product"]}]
        self._write_pipeline(site_root, disk_with_edit)

        # Producer restarts, loads pipeline (gets new-product), generates another article
        # then calls save_pipeline() with the in-memory state (which has new-product)
        in_memory = [{"id": 1, "slug": "a", "status": "staged", "products": ["new-product"]}]
        save_pipeline(in_memory, site_root)

        saved = self._read_pipeline(site_root)
        assert saved[0]["products"] == ["new-product"], \
            "Manual product edit was overwritten by save_pipeline"

    def test_manual_skip_flag_survives(self, tmp_path):
        """
        Scenario: Keith sets status: skip for an article in pipeline.json.
        The producer loaded the pipeline at startup (so in-memory has status: skip).
        save_pipeline() must preserve the skip flag.
        """
        site_root = self._make_site(tmp_path)
        base = [
            {"id": 1, "slug": "keep", "status": "pending", "products": ["p1"]},
            {"id": 2, "slug": "skip-me", "status": "skip", "products": ["p2"]},
        ]
        self._write_pipeline(site_root, base)

        # In-memory after producer startup — includes the skip flag as loaded
        in_memory = [
            {"id": 1, "slug": "keep", "status": "staged", "products": ["p1"]},
            {"id": 2, "slug": "skip-me", "status": "skip", "products": ["p2"]},
        ]
        save_pipeline(in_memory, site_root)

        saved = self._read_pipeline(site_root)
        by_id = {a["id"]: a for a in saved}
        assert by_id[1]["status"] == "staged"
        assert by_id[2]["status"] == "skip", "Manual skip flag was overwritten by save_pipeline"

    def test_disk_only_articles_preserved(self, tmp_path):
        """
        Articles present on disk but absent from in-memory pipeline
        (e.g. added after producer loaded) must not be dropped.
        """
        site_root = self._make_site(tmp_path)
        disk = [
            {"id": 1, "slug": "a", "status": "pending", "products": ["p1"]},
            {"id": 2, "slug": "b", "status": "pending", "products": ["p2"]},
        ]
        self._write_pipeline(site_root, disk)

        # In-memory only has article 1 (article 2 was added to pipeline.json post-startup)
        in_memory = [{"id": 1, "slug": "a", "status": "staged", "products": ["p1"]}]
        save_pipeline(in_memory, site_root)

        saved = self._read_pipeline(site_root)
        assert len(saved) == 2, "Article added to disk after producer started was dropped"
        by_id = {a["id"]: a for a in saved}
        assert by_id[2]["status"] == "pending"

    def test_atomic_write_no_corruption_on_error(self, tmp_path):
        """save_pipeline writes to a .tmp file then os.replace — original survives if interrupted."""
        site_root = self._make_site(tmp_path)
        base = [{"id": 1, "slug": "a", "status": "pending", "products": ["p1"]}]
        self._write_pipeline(site_root, base)

        in_memory = [{"id": 1, "slug": "a", "status": "staged", "products": ["p1"]}]
        save_pipeline(in_memory, site_root)

        # Tmp file should not linger after successful save
        tmp_path_file = site_root / "data" / "pipeline.json.tmp"
        assert not tmp_path_file.exists(), ".tmp file was not cleaned up after save"
