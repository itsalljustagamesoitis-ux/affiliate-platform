"""
Deliberate-failure tests for check_output_shape() — producer pre-write guard.

Tests A, B, C, D as specified in Day 7 Item 6.
"""

import pytest
from article_builder import check_output_shape

GOOD_BODY = """## Top Picks

A solid opening paragraph that introduces the buying guide with enough substance.

### Best Overall Pick

This product is an excellent choice for most buyers. It comes with robust features
and a competitive price point. The build quality is exceptional.

## How to Choose

Look for these key factors when evaluating your options.

## Frequently Asked Questions

**Q: What should I look for?**
A: Focus on durability and value.
""" * 3  # repeat to exceed 1500 words


def make_body(word_count: int = 2000, include_h2: bool = True) -> str:
    h2 = "## Top Picks\n\n" if include_h2 else ""
    words = " ".join(["word"] * word_count)
    return f"{h2}{words}"


class TestRefusalPattern:
    """Test A — refusal content is rejected."""

    def test_i_need_to_pause(self):
        body = "I need to pause before writing this article because the topic is complex."
        ok, failures = check_output_shape(body, "buyer_guide", ["product-a"])
        assert not ok
        assert any("refusal-pattern" in f for f in failures)

    def test_as_an_ai(self):
        body = "As an AI, I cannot provide personal recommendations."
        ok, failures = check_output_shape(body, "buyer_guide", ["product-a"])
        assert not ok
        assert any("refusal-pattern" in f for f in failures)

    def test_i_cannot_write(self):
        body = "I cannot write an article about this topic."
        ok, failures = check_output_shape(body, "buyer_guide", ["product-a"])
        assert not ok
        assert any("refusal-pattern" in f for f in failures)

    def test_as_a_language_model(self):
        body = "As a language model, I don't have personal experience with these products."
        ok, failures = check_output_shape(body, "buyer_guide", ["product-a"])
        assert not ok
        assert any("refusal-pattern" in f for f in failures)

    def test_no_false_positive_on_air_conditioner(self):
        body = make_body(2000) + " This works as an air conditioner and heater."
        ok, failures = check_output_shape(body, "informational", [])
        refusal_failures = [f for f in failures if "refusal-pattern" in f]
        assert not refusal_failures, "Should not flag 'as an air conditioner'"

    def test_no_false_positive_on_ai_prefix_word(self):
        body = make_body(1000) + " The AirFlow system works well."
        ok, failures = check_output_shape(body, "informational", [])
        refusal_failures = [f for f in failures if "refusal-pattern" in f]
        assert not refusal_failures


class TestWordCount:
    """Test B — short articles are rejected."""

    def test_200_word_article_rejected(self):
        body = make_body(word_count=200)
        ok, failures = check_output_shape(body, "buyer_guide", ["product-a"])
        assert not ok
        assert any("word-count" in f for f in failures)

    def test_informational_800_word_minimum(self):
        body = make_body(word_count=500)
        ok, failures = check_output_shape(body, "informational", [])
        assert not ok
        assert any("word-count" in f for f in failures)

    def test_informational_800_word_passes(self):
        body = make_body(word_count=850, include_h2=True)
        ok, failures = check_output_shape(body, "informational", [])
        wc_failures = [f for f in failures if "word-count" in f]
        assert not wc_failures

    def test_buyer_guide_1500_word_minimum(self):
        body = make_body(word_count=1200)
        ok, failures = check_output_shape(body, "buyer_guide", ["product-a"])
        assert not ok
        assert any("word-count" in f for f in failures)

    def test_buyer_guide_1500_words_passes(self):
        body = make_body(word_count=1600, include_h2=True)
        ok, failures = check_output_shape(body, "buyer_guide", ["product-a"])
        wc_failures = [f for f in failures if "word-count" in f]
        assert not wc_failures


class TestMissingH2:
    """Test for missing section structure."""

    def test_no_h2_rejected(self):
        body = make_body(word_count=2000, include_h2=False)
        ok, failures = check_output_shape(body, "buyer_guide", ["product-a"])
        assert not ok
        assert any("missing-h2" in f for f in failures)

    def test_has_h2_passes_this_check(self):
        body = make_body(word_count=2000, include_h2=True)
        ok, failures = check_output_shape(body, "buyer_guide", ["product-a"])
        h2_failures = [f for f in failures if "missing-h2" in f]
        assert not h2_failures

    def test_h3_without_h2_still_fails(self):
        body = "### Product Section\n\n" + " ".join(["word"] * 2000)
        ok, failures = check_output_shape(body, "buyer_guide", ["product-a"])
        assert any("missing-h2" in f for f in failures)


class TestNoProducts:
    """Test C — commercial articles with no product references are rejected."""

    def test_buyer_guide_empty_products_rejected(self):
        body = make_body(word_count=2000)
        ok, failures = check_output_shape(body, "buyer_guide", [])
        assert not ok
        assert any("no-products" in f for f in failures)

    def test_roundup_empty_products_rejected(self):
        body = make_body(word_count=2000)
        ok, failures = check_output_shape(body, "roundup", [])
        assert not ok
        assert any("no-products" in f for f in failures)

    def test_buyer_guide_with_product_keys_passes(self):
        body = make_body(word_count=2000)
        ok, failures = check_output_shape(body, "buyer_guide", ["product-a", "product-b"])
        prod_failures = [f for f in failures if "no-products" in f]
        assert not prod_failures

    def test_buyer_guide_with_inline_link_passes(self):
        body = make_body(word_count=2000) + "\n\n(product:my-product-slug)"
        ok, failures = check_output_shape(body, "buyer_guide", [])
        prod_failures = [f for f in failures if "no-products" in f]
        assert not prod_failures

    def test_informational_empty_products_allowed(self):
        body = make_body(word_count=900)
        ok, failures = check_output_shape(body, "informational", [])
        prod_failures = [f for f in failures if "no-products" in f]
        assert not prod_failures, "Informational articles don't require products"


class TestNormalArticle:
    """Test D — well-formed article passes all checks."""

    def test_good_buyer_guide_passes(self):
        body = make_body(word_count=2000, include_h2=True)
        ok, failures = check_output_shape(body, "buyer_guide", ["product-a", "product-b"])
        assert ok, f"Expected pass but got failures: {failures}"
        assert failures == []

    def test_good_informational_passes(self):
        body = make_body(word_count=1000, include_h2=True)
        ok, failures = check_output_shape(body, "informational", [])
        assert ok, f"Expected pass but got failures: {failures}"

    def test_multiple_failures_reported(self):
        body = "As an AI I cannot write this."
        ok, failures = check_output_shape(body, "buyer_guide", [])
        assert not ok
        assert len(failures) >= 2, "Should report refusal + word-count + missing-h2 + no-products"
