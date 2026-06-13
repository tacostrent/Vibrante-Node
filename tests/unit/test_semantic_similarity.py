"""Tests for semantic_similarity.py (Tier 12.8)."""
from __future__ import annotations
import math
import pytest
from src.runtime.assets.vector_search import (
    cosine_similarity, rank_similarity, score_match, normalize_scores, l2_normalize,
)


class TestCosineSimilarity:
    def test_identical_vectors(self):
        v = [1.0, 0.0, 0.0]
        assert abs(cosine_similarity(v, v) - 1.0) < 1e-9

    def test_orthogonal_vectors(self):
        v1 = [1.0, 0.0]
        v2 = [0.0, 1.0]
        assert abs(cosine_similarity(v1, v2)) < 1e-9

    def test_opposite_vectors(self):
        v1 = [1.0, 0.0]
        v2 = [-1.0, 0.0]
        assert abs(cosine_similarity(v1, v2) + 1.0) < 1e-9

    def test_zero_vector_returns_zero(self):
        assert cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0
        assert cosine_similarity([1.0, 0.0], [0.0, 0.0]) == 0.0

    def test_empty_returns_zero(self):
        assert cosine_similarity([], []) == 0.0

    def test_different_lengths_returns_zero(self):
        assert cosine_similarity([1.0, 2.0], [1.0]) == 0.0

    def test_range_bounded(self):
        import random
        random.seed(42)
        for _ in range(10):
            a = [random.gauss(0, 1) for _ in range(128)]
            b = [random.gauss(0, 1) for _ in range(128)]
            s = cosine_similarity(a, b)
            assert -1.0 <= s <= 1.0

    def test_similar_vectors_high_score(self):
        v1 = [1.0, 1.0, 0.0, 0.0]
        v2 = [1.0, 0.9, 0.1, 0.0]
        assert cosine_similarity(v1, v2) > 0.9


class TestRankSimilarity:
    def test_returns_sorted_descending(self):
        query = [1.0, 0.0]
        candidates = [
            ("a", [0.5, 0.5]),
            ("b", [1.0, 0.0]),
            ("c", [0.0, 1.0]),
        ]
        ranked = rank_similarity(query, candidates)
        assert ranked[0][0] == "b"
        assert ranked[-1][0] == "c"

    def test_empty_candidates(self):
        assert rank_similarity([1.0], []) == []

    def test_scores_in_order(self):
        query = [1.0, 0.0, 0.0]
        candidates = [("a", [0.9, 0.1, 0.0]), ("b", [0.1, 0.9, 0.0])]
        ranked = rank_similarity(query, candidates)
        assert ranked[0][1] >= ranked[1][1]


class TestScoreMatch:
    def test_perfect_environment_match(self):
        q = {"environments": ["industrial_hangar"]}
        c = {"environments": ["industrial_hangar"]}
        score = score_match(q, c)
        assert score > 0.2

    def test_no_match(self):
        q = {"environments": ["industrial_hangar"]}
        c = {"environments": ["robotics_lab"]}
        score = score_match(q, c)
        assert score == 0.0

    def test_empty_query_returns_zero(self):
        score = score_match({}, {"environments": ["hangar"]})
        assert score == 0.0

    def test_scalar_storytelling_field(self):
        q = {"storytelling": "hero_object"}
        c = {"storytelling": "hero_object"}
        score = score_match(q, c)
        assert score > 0.0


class TestNormalizeScores:
    def test_basic_normalization(self):
        scores = [0.0, 0.5, 1.0]
        normed = normalize_scores(scores)
        assert normed[0] == 0.0
        assert normed[-1] == 1.0

    def test_all_equal_returns_zeros(self):
        scores = [0.5, 0.5, 0.5]
        normed = normalize_scores(scores)
        assert all(s == 0.0 for s in normed)

    def test_empty_returns_empty(self):
        assert normalize_scores([]) == []

    def test_single_element(self):
        assert normalize_scores([0.7]) == [0.0]


class TestL2Normalize:
    def test_unit_vector_unchanged(self):
        v = [1.0, 0.0, 0.0]
        n = l2_normalize(v)
        assert abs(n[0] - 1.0) < 1e-9

    def test_non_unit_normalized(self):
        v = [3.0, 4.0]
        n = l2_normalize(v)
        norm = sum(x * x for x in n) ** 0.5
        assert abs(norm - 1.0) < 1e-9

    def test_zero_vector_unchanged(self):
        v = [0.0, 0.0, 0.0]
        n = l2_normalize(v)
        assert n == v
