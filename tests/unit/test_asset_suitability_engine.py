"""Tests for AssetSuitabilityEngine — §45 Semantic Asset Suitability Ranking.

Validates the core success criteria:
  western_room + chair → Wooden Saloon Chair >> Modern Plastic Chair
  lantern slot       → Oil Lantern >> Bottle
  poster slot        → Wanted Poster >> Rock / Terrain
"""

import pytest
from src.runtime.assets.suitability.asset_suitability_engine import (
    AssetSuitabilityScore,
    SuitabilityRequest,
    SuitabilityResult,
    get_asset_suitability_engine,
    reset_asset_suitability_engine_for_tests,
    WEIGHTS,
)
from src.runtime.assets.suitability import (
    reset_environment_affinity_for_tests,
    reset_role_affinity_for_tests,
    reset_style_affinity_for_tests,
    reset_material_affinity_for_tests,
    reset_scale_affinity_for_tests,
    reset_placement_affinity_for_tests,
    reset_story_affinity_for_tests,
)

# ---------------------------------------------------------------------------
# Test assets
# ---------------------------------------------------------------------------

WOODEN_SALOON_CHAIR = {
    "asset_id": "wooden_saloon_chair_001",
    "name": "Wooden Saloon Chair",
    "category": "furniture",
    "type": "chair",
    "placement_type": "chair",
    "scale_class": "medium",
    "tags": ["wooden", "saloon", "chair", "weathered", "rustic"],
    "style_tags": ["weathered", "rustic", "aged"],
    "material_tags": ["wood", "leather"],
    "environment_tags": ["western_room", "saloon"],
}

MODERN_PLASTIC_CHAIR = {
    "asset_id": "modern_plastic_chair_001",
    "name": "Modern Plastic Chair",
    "category": "furniture",
    "type": "chair",
    "placement_type": "chair",
    "scale_class": "medium",
    "tags": ["modern", "plastic", "office"],
    "style_tags": ["clean", "modern", "minimal"],
    "material_tags": ["plastic", "chrome"],
    "environment_tags": ["office"],
}

INDUSTRIAL_STOOL = {
    "asset_id": "industrial_stool_001",
    "name": "Industrial Stool",
    "category": "furniture",
    "type": "stool",
    "placement_type": "stool",
    "scale_class": "small",
    "tags": ["industrial", "stool", "metal"],
    "style_tags": ["industrial", "worn"],
    "material_tags": ["steel"],
    "environment_tags": ["industrial_hangar", "warehouse"],
}

OIL_LANTERN = {
    "asset_id": "oil_lantern_001",
    "name": "Oil Lantern",
    "category": "light",
    "type": "lantern",
    "placement_type": "lantern",
    "scale_class": "small",
    "tags": ["oil", "lantern", "lamp", "western"],
    "style_tags": ["weathered", "aged"],
    "material_tags": ["iron", "glass"],
    "environment_tags": ["western_room"],
}

GENERIC_BOTTLE = {
    "asset_id": "bottle_001",
    "name": "Generic Bottle",
    "category": "prop",
    "type": "bottle",
    "placement_type": "bottle",
    "scale_class": "tiny",
    "tags": ["bottle", "glass"],
    "material_tags": ["glass"],
}

WANTED_POSTER = {
    "asset_id": "wanted_poster_001",
    "name": "Wanted Poster",
    "category": "decor",
    "type": "poster",
    "placement_type": "poster",
    "scale_class": "small",
    "tags": ["wanted", "poster", "paper", "sign", "western"],
    "style_tags": ["aged", "weathered"],
    "environment_tags": ["western_room"],
}

TERRAIN_ROCK = {
    "asset_id": "terrain_rock_001",
    "name": "Desert Rock",
    "category": "terrain",
    "type": "terrain",
    "placement_type": "terrain",
    "scale_class": "structural",
    "tags": ["rock", "terrain", "stone", "natural"],
}


@pytest.fixture(autouse=True)
def reset_all():
    for fn in (
        reset_asset_suitability_engine_for_tests,
        reset_environment_affinity_for_tests,
        reset_role_affinity_for_tests,
        reset_style_affinity_for_tests,
        reset_material_affinity_for_tests,
        reset_scale_affinity_for_tests,
        reset_placement_affinity_for_tests,
        reset_story_affinity_for_tests,
    ):
        fn()
    yield
    for fn in (
        reset_asset_suitability_engine_for_tests,
        reset_environment_affinity_for_tests,
        reset_role_affinity_for_tests,
        reset_style_affinity_for_tests,
        reset_material_affinity_for_tests,
        reset_scale_affinity_for_tests,
        reset_placement_affinity_for_tests,
        reset_story_affinity_for_tests,
    ):
        fn()


# ---------------------------------------------------------------------------
# Success criteria tests
# ---------------------------------------------------------------------------

class TestCoreSuccessCriteria:
    """These are the primary spec requirements."""

    def test_wooden_chair_beats_modern_chair_for_western_room(self):
        eng = get_asset_suitability_engine()
        req = SuitabilityRequest(environment="western_room", role="chair")
        s_wooden = eng.score_asset(WOODEN_SALOON_CHAIR, req).final_score
        s_modern = eng.score_asset(MODERN_PLASTIC_CHAIR, req).final_score
        assert s_wooden > s_modern, (
            f"Wooden Chair ({s_wooden:.3f}) must beat Modern Chair ({s_modern:.3f})"
        )

    def test_oil_lantern_beats_bottle_for_lantern_slot(self):
        eng = get_asset_suitability_engine()
        req = SuitabilityRequest(environment="western_room", role="lantern")
        s_lantern = eng.score_asset(OIL_LANTERN, req).final_score
        s_bottle = eng.score_asset(GENERIC_BOTTLE, req).final_score
        assert s_lantern > s_bottle, (
            f"Oil Lantern ({s_lantern:.3f}) must beat Bottle ({s_bottle:.3f})"
        )

    def test_wanted_poster_beats_terrain_for_poster_slot(self):
        eng = get_asset_suitability_engine()
        req = SuitabilityRequest(environment="western_room", role="poster")
        s_poster = eng.score_asset(WANTED_POSTER, req).final_score
        s_rock = eng.score_asset(TERRAIN_ROCK, req).final_score
        assert s_poster > s_rock, (
            f"Wanted Poster ({s_poster:.3f}) must beat Terrain Rock ({s_rock:.3f})"
        )

    def test_wooden_chair_significantly_beats_industrial_stool_for_western(self):
        eng = get_asset_suitability_engine()
        req = SuitabilityRequest(environment="western_room", role="chair")
        s_wooden = eng.score_asset(WOODEN_SALOON_CHAIR, req).final_score
        s_industrial = eng.score_asset(INDUSTRIAL_STOOL, req).final_score
        assert s_wooden > s_industrial + 0.05


class TestRankAssets:
    def test_rank_puts_wooden_chair_first(self):
        eng = get_asset_suitability_engine()
        req = SuitabilityRequest(environment="western_room", role="chair")
        result = eng.rank_assets(
            [MODERN_PLASTIC_CHAIR, INDUSTRIAL_STOOL, WOODEN_SALOON_CHAIR], req
        )
        assert result.best.asset_id == "wooden_saloon_chair_001"

    def test_rank_result_sorted_descending(self):
        eng = get_asset_suitability_engine()
        req = SuitabilityRequest(environment="western_room", role="chair")
        result = eng.rank_assets(
            [MODERN_PLASTIC_CHAIR, WOODEN_SALOON_CHAIR, INDUSTRIAL_STOOL], req
        )
        scores = [s.final_score for s in result.scores]
        assert scores == sorted(scores, reverse=True)

    def test_total_candidates_count_correct(self):
        eng = get_asset_suitability_engine()
        req = SuitabilityRequest(environment="western_room", role="chair")
        result = eng.rank_assets(
            [WOODEN_SALOON_CHAIR, MODERN_PLASTIC_CHAIR], req
        )
        assert result.total_candidates == 2

    def test_empty_candidates_returns_empty_result(self):
        eng = get_asset_suitability_engine()
        req = SuitabilityRequest(environment="western_room", role="chair")
        result = eng.rank_assets([], req)
        assert result.best is None
        assert result.total_candidates == 0


class TestSelectBest:
    def test_select_best_returns_highest_score(self):
        eng = get_asset_suitability_engine()
        req = SuitabilityRequest(environment="western_room", role="chair")
        best = eng.select_best(
            [MODERN_PLASTIC_CHAIR, WOODEN_SALOON_CHAIR, INDUSTRIAL_STOOL], req
        )
        assert best is not None
        assert best.asset_id == "wooden_saloon_chair_001"

    def test_select_best_empty_returns_none(self):
        eng = get_asset_suitability_engine()
        req = SuitabilityRequest(environment="western_room", role="chair")
        assert eng.select_best([], req) is None


class TestValidateSelection:
    def test_wooden_chair_valid_for_chair_slot(self):
        eng = get_asset_suitability_engine()
        req = SuitabilityRequest(environment="western_room", role="chair")
        v = eng.validate_selection(WOODEN_SALOON_CHAIR, req)
        assert v["valid"] is True
        assert len(v["findings"]) == 0

    def test_terrain_rock_invalid_for_poster_slot(self):
        eng = get_asset_suitability_engine()
        req = SuitabilityRequest(environment="western_room", role="poster")
        v = eng.validate_selection(TERRAIN_ROCK, req)
        assert v["valid"] is False
        assert len(v["findings"]) > 0


class TestScoreAsset:
    def test_all_score_fields_populated(self):
        eng = get_asset_suitability_engine()
        req = SuitabilityRequest(environment="western_room", role="chair")
        s = eng.score_asset(WOODEN_SALOON_CHAIR, req)
        for attr in (
            "environment_score", "role_score", "style_score", "material_score",
            "scale_score", "placement_score", "story_score", "final_score",
        ):
            val = getattr(s, attr)
            assert 0.0 <= val <= 1.0, f"{attr} out of range: {val}"

    def test_similarity_score_stored(self):
        eng = get_asset_suitability_engine()
        req = SuitabilityRequest(environment="western_room", role="chair")
        s = eng.score_asset(WOODEN_SALOON_CHAIR, req, similarity_score=0.77)
        assert s.similarity_score == 0.77

    def test_final_score_is_weighted_sum(self):
        eng = get_asset_suitability_engine()
        req = SuitabilityRequest(environment="western_room", role="chair")
        s = eng.score_asset(WOODEN_SALOON_CHAIR, req)
        expected = (
            WEIGHTS["environment"] * s.environment_score
            + WEIGHTS["role"]        * s.role_score
            + WEIGHTS["style"]       * s.style_score
            + WEIGHTS["material"]    * s.material_score
            + WEIGHTS["scale"]       * s.scale_score
            + WEIGHTS["placement"]   * s.placement_score
            + WEIGHTS["story"]       * s.story_score
        )
        assert abs(s.final_score - expected) < 1e-6


class TestSerialization:
    def test_suitability_score_roundtrip(self):
        eng = get_asset_suitability_engine()
        req = SuitabilityRequest(environment="western_room", role="chair")
        s = eng.score_asset(WOODEN_SALOON_CHAIR, req)
        restored = AssetSuitabilityScore.from_dict(s.to_dict())
        assert abs(restored.final_score - s.final_score) < 1e-4

    def test_request_roundtrip(self):
        req = SuitabilityRequest(
            environment="western_room", role="chair",
            placement_context="around_table", expected_scale="medium"
        )
        restored = SuitabilityRequest.from_dict(req.to_dict())
        assert restored.environment == req.environment
        assert restored.role == req.role

    def test_result_selection_report(self):
        eng = get_asset_suitability_engine()
        req = SuitabilityRequest(environment="western_room", role="chair")
        result = eng.rank_assets([WOODEN_SALOON_CHAIR, MODERN_PLASTIC_CHAIR], req)
        report = result.selection_report
        assert report["role"] == "chair"
        assert "selected_asset" in report
        assert isinstance(report["candidates"], list)


class TestWeightSum:
    def test_weights_sum_to_one(self):
        assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9
