"""Tests for ScoringEngine — relevancy and trust score computation."""

import pytest
from core.models import ScoringConfig
from core.scoring import ScoringEngine


class TestComputeRelevancy:
    """Tests for whole-word keyword relevancy scoring."""

    def test_full_match(self, engine):
        text = "Renewable energy from solar and wind power."
        keywords = ["renewable", "energy", "solar", "wind"]
        result = engine.compute_relevancy(text, keywords)
        assert result == 1.0

    def test_partial_match(self, engine):
        text = "Solar panels are great."
        keywords = ["solar", "wind", "energy", "renewable"]
        result = engine.compute_relevancy(text, keywords)
        assert result == 0.25  # 1 out of 4

    def test_no_match(self, engine):
        text = "The weather is nice today."
        keywords = ["solar", "wind", "energy"]
        result = engine.compute_relevancy(text, keywords)
        assert result == 0.0

    def test_empty_keywords_returns_half(self, engine):
        text = "Some text content."
        result = engine.compute_relevancy(text, [])
        assert result == 0.5

    def test_case_insensitive(self, engine):
        text = "SOLAR and WIND energy is RENEWABLE."
        keywords = ["solar", "wind", "energy", "renewable"]
        result = engine.compute_relevancy(text, keywords)
        assert result == 1.0

    def test_whole_word_no_substring(self, engine):
        """'sun' should not match 'sunny', 'sunrise', etc."""
        text = "It was a sunny sunrise over the sunflower field."
        keywords = ["sun"]
        result = engine.compute_relevancy(text, keywords)
        assert result == 0.0

    def test_whole_word_exact(self, engine):
        """'sun' should match the standalone word 'sun'."""
        text = "The sun provides solar energy."
        keywords = ["sun"]
        result = engine.compute_relevancy(text, keywords)
        assert result == 1.0

    def test_rounding(self, engine):
        text = "Renewable energy is important."
        keywords = ["renewable", "energy", "solar"]
        result = engine.compute_relevancy(text, keywords)
        assert result == round(2 / 3, 4)


class TestComputeTrustScore:
    """Tests for trust score formula."""

    def test_basic_computation(self, engine):
        # 0.6 * 0.8 + 0.4 * 1.0 = 0.48 + 0.40 = 0.88
        result = engine.compute_trust_score(0.8, 1.0)
        assert result == 0.88

    def test_zero_inputs(self, engine):
        result = engine.compute_trust_score(0.0, 0.0)
        assert result == 0.0

    def test_perfect_inputs(self, engine):
        result = engine.compute_trust_score(1.0, 1.0)
        assert result == 1.0

    def test_clamps_inputs(self, engine):
        """Inputs beyond [0, 1] are clamped."""
        result = engine.compute_trust_score(1.5, -0.3)
        assert result == engine.compute_trust_score(1.0, 0.0)

    def test_custom_weights(self):
        config = ScoringConfig(w_reputation=0.5, w_relevancy=0.5)
        eng = ScoringEngine(config)
        # 0.5 * 0.6 + 0.5 * 0.4 = 0.3 + 0.2 = 0.5
        result = eng.compute_trust_score(0.6, 0.4)
        assert result == 0.5

    def test_rounding(self, engine):
        # 0.6 * 0.333 + 0.4 * 0.667 = 0.1998 + 0.2668 = 0.4666
        result = engine.compute_trust_score(0.333, 0.667)
        assert result == round(0.6 * 0.333 + 0.4 * 0.667, 4)


class TestScoringConfigValidation:
    """Tests for config weight validation."""

    def test_valid_weights(self):
        config = ScoringConfig(w_reputation=0.6, w_relevancy=0.4)
        assert config.w_reputation == 0.6
        assert config.w_relevancy == 0.4

    def test_invalid_weights_raises(self):
        with pytest.raises(ValueError, match="must sum to 1.0"):
            ScoringConfig(w_reputation=0.5, w_relevancy=0.3)

    def test_tolerance(self):
        # Should pass: 0.6000001 + 0.4 is within 1e-6 tolerance
        config = ScoringConfig(w_reputation=0.6000001, w_relevancy=0.4)
        assert config is not None
