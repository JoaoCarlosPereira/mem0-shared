"""Tests for mem0.utils.scoring — BM25 parameter derivation, normalization, combined scoring."""

import math

from mem0.utils.scoring import (
    ENTITY_BOOST_WEIGHT,
    ENTITY_BOOST_SEARCH_TOP_K,
    normalize_bm25,
    score_and_rank,
    get_bm25_params,
)


class TestBM25Params:
    """Tests for get_bm25_params parameter selection."""

    def test_short_query_returns_correct_params(self):
        """Short queries (<=3 terms) return (5.0, 0.7)."""
        result = get_bm25_params("quick test")
        assert result == (5.0, 0.7)

    def test_medium_query_returns_correct_params(self):
        """Queries 4-6 terms return (7.0, 0.6)."""
        query = "one two three four five six"
        result = get_bm25_params(query)
        assert result == (7.0, 0.6)

    def test_long_query_returns_correct_params(self):
        """Queries 7-9 terms return (9.0, 0.5)."""
        query = "one two three four five six seven eight nine"
        result = get_bm25_params(query)
        assert result == (9.0, 0.5)

    def test_very_long_query_returns_correct_params(self):
        """Queries 10-15 terms return (10.0, 0.5)."""
        query = " ".join(str(i) for i in range(1, 16))
        result = get_bm25_params(query)
        assert result == (10.0, 0.5)

    def test_extremely_long_query_returns_correct_params(self):
        """Queries >15 terms return (12.0, 0.5)."""
        query = " ".join(str(i) for i in range(1, 21))
        result = get_bm25_params(query)
        assert result == (12.0, 0.5)

    def test_custom_lemmatized_overrides(self):
        """Custom lemmatized string overrides automatic tokenization."""
        result = get_bm25_params("hello world", lemmatized="hello world")
        assert result == (5.0, 0.7)

    def test_empty_lemmatized_defaults_to_one(self):
        """Empty lemmatized string defaults to num_terms=1."""
        result = get_bm25_params("hello", lemmatized="")
        assert result == (5.0, 0.7)


class TestNormalizeBM25:
    """Tests for normalize_bm25 sigmoid normalization."""

    def test_normalize_returns_zero_for_negative_infinity(self):
        """normalize_bm25 approaches 0 for very negative scores."""
        result = normalize_bm25(-1000, 5.0, 0.7)
        assert result < 1e-10

    def test_normalize_returns_one_for_positive_infinity(self):
        """normalize_bm25 approaches 1 for very large positive scores."""
        result = normalize_bm25(1000, 5.0, 0.7)
        assert result == 1.0

    def test_normalize_at_midpoint(self):
        """normalize_bm25 returns 0.5 at the midpoint."""
        result = normalize_bm25(5.0, 5.0, 0.7)
        assert abs(result - 0.5) < 0.001

    def test_normalize_steeper_sigmoid(self):
        """Steepness affects the slope but not the midpoint."""
        s1 = normalize_bm25(5.0, 5.0, 1.0)
        assert abs(s1 - 0.5) < 0.001

    def test_normalize_returns_in_range(self):
        """normalize_bm25 always returns a value in [0, 1]."""
        for score in [-10, -5, 0, 2, 5, 10, 20]:
            result = normalize_bm25(score, 5.0, 0.7)
            assert 0.0 <= result <= 1.0

    def test_normalize_sigmoid_shape(self):
        """Score above midpoint returns >0.5, below returns <0.5."""
        above = normalize_bm25(10.0, 5.0, 0.7)
        below = normalize_bm25(0.0, 5.0, 0.7)
        assert above > 0.5
        assert below < 0.5


class TestScoreAndRank:
    """Tests for score_and_rank additive scoring."""

    def test_basic_scoring(self):
        """score_and_rank scores candidates additively."""
        semantic_results = [
            {"id": "m1", "score": 0.8, "payload": {"text": "hello"}},
            {"id": "m2", "score": 0.9, "payload": {"text": "world"}},
        ]
        bm25_scores = {"m1": 0.3, "m2": 0.1}
        entity_boosts = {}

        result = score_and_rank(semantic_results, bm25_scores, entity_boosts, 0.5, 10)
        assert len(result) == 2
        assert result[0]["score"] > result[1]["score"]

    def test_threshold_filters_results(self):
        """Candidates below threshold are excluded even with BM25 boost."""
        semantic_results = [
            {"id": "m1", "score": 0.3, "payload": {"text": "low"}},
            {"id": "m2", "score": 0.8, "payload": {"text": "high"}},
        ]
        bm25_scores = {"m1": 0.9, "m2": 0.1}
        entity_boosts = {}

        result = score_and_rank(semantic_results, bm25_scores, entity_boosts, 0.5, 10)
        assert len(result) == 1
        assert result[0]["id"] == "m2"

    def test_entity_boost_applied(self):
        """Entity boosts are added to the combined score."""
        semantic_results = [
            {"id": "m1", "score": 0.8, "payload": {"text": "test"}},
        ]
        bm25_scores = {}
        entity_boosts = {"m1": 0.3}

        result = score_and_rank(semantic_results, bm25_scores, entity_boosts, 0.5, 10)
        assert len(result) == 1
        assert result[0]["score"] > 0.5  # 0.8/1.5 + 0.3/1.5 ~ 0.73

    def test_no_bm25_no_entity(self):
        """When no BM25 and no entity, max_possible is 1.0."""
        semantic_results = [{"id": "m1", "score": 0.8, "payload": {"text": "test"}}]
        result = score_and_rank(semantic_results, {}, {}, 0.5, 10)
        assert result[0]["score"] == 0.8

    def test_with_bm25_only(self):
        """When BM25 active, max_possible is 2.0."""
        semantic_results = [{"id": "m1", "score": 1.0, "payload": {"text": "test"}}]
        bm25_scores = {"m1": 1.0}
        result = score_and_rank(semantic_results, bm25_scores, {}, 0.5, 10)
        assert result[0]["score"] == 1.0  # min(2.0/2.0, 1.0) = 1.0

    def test_with_entity_only(self):
        """When entity active only, max_possible is 1.5."""
        semantic_results = [{"id": "m1", "score": 1.0, "payload": {"text": "test"}}]
        entity_boosts = {"m1": 1.0}
        result = score_and_rank(semantic_results, {}, entity_boosts, 0.5, 10)
        assert result[0]["score"] == 1.0  # min(2.0/1.5, 1.0) = 1.0

    def test_with_all_signals(self):
        """When all signals active, max_possible is 2.5."""
        semantic_results = [{"id": "m1", "score": 1.0, "payload": {"text": "test"}}]
        bm25_scores = {"m1": 1.0}
        entity_boosts = {"m1": ENTITY_BOOST_WEIGHT}
        result = score_and_rank(semantic_results, bm25_scores, entity_boosts, 0.5, 10)
        assert result[0]["score"] == 1.0  # min(2.5/2.5, 1.0) = 1.0

    def test_top_k_limiting(self):
        """score_and_rank respects the top_k limit."""
        semantic_results = [
            {"id": f"m{i}", "score": 0.9 - i * 0.1, "payload": {"text": f"test{i}"}}
            for i in range(5)
        ]
        result = score_and_rank(semantic_results, {}, {}, 0.5, 2)
        assert len(result) == 2

    def test_explain_includes_score_details(self):
        """When explain=True, score_details is included."""
        semantic_results = [{"id": "m1", "score": 0.8, "payload": {"text": "test"}}]
        result = score_and_rank(
            semantic_results,
            {"m1": 0.3},
            {},
            0.5,
            10,
            explain=True,
        )
        assert "score_details" in result[0]
        assert "semantic_score" in result[0]["score_details"]
        assert "bm25_score" in result[0]["score_details"]
        assert "raw_score" in result[0]["score_details"]

    def test_missing_id_skipped(self):
        """Results without 'id' are skipped."""
        semantic_results = [{"score": 0.8, "payload": {"text": "test"}}]
        result = score_and_rank(semantic_results, {}, {}, 0.5, 10)
        assert result == []

    def test_score_capped_at_one(self):
        """Combined score is capped at 1.0."""
        semantic_results = [{"id": "m1", "score": 1.0, "payload": {"text": "test"}}]
        bm25_scores = {"m1": 10.0}
        entity_boosts = {"m1": 10.0}
        result = score_and_rank(semantic_results, bm25_scores, entity_boosts, 0.5, 10)
        assert result[0]["score"] <= 1.0

    def test_empty_semantic_results(self):
        """Empty semantic_results returns empty list."""
        result = score_and_rank([], {}, {}, 0.5, 10)
        assert result == []

    def test_results_sorted_descending(self):
        """Results are sorted by score in descending order."""
        semantic_results = [
            {"id": "m1", "score": 0.6, "payload": {"text": "a"}},
            {"id": "m2", "score": 0.9, "payload": {"text": "b"}},
            {"id": "m3", "score": 0.7, "payload": {"text": "c"}},
        ]
        result = score_and_rank(semantic_results, {}, {}, 0.5, 10)
        assert result[0]["score"] >= result[1]["score"] >= result[2]["score"]

    def test_zero_semantic_score_skipped(self):
        """Results with zero/None semantic score are filtered by threshold."""
        semantic_results = [
            {"id": "m1", "score": None, "payload": {"text": "test"}}
        ]
        result = score_and_rank(semantic_results, {}, {}, 0.5, 10)
        assert result == []

    def test_entity_boost_default_zero(self):
        """Missing entity_boost defaults to 0.0."""
        semantic_results = [{"id": "m1", "score": 0.8, "payload": {"text": "test"}}]
        bm25_scores = {"m1": 0.3}
        result = score_and_rank(semantic_results, bm25_scores, {}, 0.5, 10)
        assert len(result) == 1

    def test_score_details_max_possible(self):
        """score_details includes correct max_possible_score."""
        semantic_results = [{"id": "m1", "score": 0.8, "payload": {"text": "test"}}]
        result = score_and_rank(
            semantic_results,
            {"m1": 0.3},
            {"m1": 0.5},
            0.5,
            10,
            explain=True,
        )
        assert result[0]["score_details"]["max_possible_score"] == 2.5
