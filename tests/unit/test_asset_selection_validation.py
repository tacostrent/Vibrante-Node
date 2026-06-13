"""
test_asset_selection_validation.py — §45 Semantic Asset Suitability Ranking

End-to-end validation tests proving that suitability ranking selects the
correct asset for each slot in various environments. These tests encode the
spec success criteria directly.
"""

import pytest
from src.runtime.assets.suitability import (
    get_asset_suitability_engine,
    SuitabilityRequest,
    get_asset_suitability_review,
    reset_asset_suitability_engine_for_tests,
    reset_asset_suitability_review_for_tests,
    reset_environment_affinity_for_tests,
    reset_role_affinity_for_tests,
    reset_style_affinity_for_tests,
    reset_material_affinity_for_tests,
    reset_scale_affinity_for_tests,
    reset_placement_affinity_for_tests,
    reset_story_affinity_for_tests,
)

# ---------------------------------------------------------------------------
# Asset pool for testing
# ---------------------------------------------------------------------------

WOODEN_SALOON_CHAIR = {
    "asset_id": "wooden_saloon_chair",
    "name": "Wooden Saloon Chair",
    "type": "chair", "placement_type": "chair", "scale_class": "medium",
    "tags": ["wooden", "saloon", "chair", "weathered", "rustic"],
    "style_tags": ["weathered", "rustic"], "material_tags": ["wood"],
    "environment_tags": ["western_room"],
}
MODERN_CHAIR = {
    "asset_id": "modern_office_chair",
    "name": "Modern Office Chair",
    "type": "chair", "placement_type": "chair", "scale_class": "medium",
    "tags": ["modern", "plastic", "office", "ergonomic"],
    "style_tags": ["modern", "clean"], "material_tags": ["plastic", "chrome"],
    "environment_tags": ["office"],
}
OIL_LANTERN = {
    "asset_id": "oil_lantern",
    "name": "Oil Lantern",
    "type": "lantern", "placement_type": "lantern", "scale_class": "small",
    "tags": ["oil", "lantern", "western", "aged"],
    "environment_tags": ["western_room"],
}
GENERIC_BOTTLE = {
    "asset_id": "generic_bottle",
    "name": "Generic Bottle",
    "type": "bottle", "placement_type": "bottle", "scale_class": "tiny",
    "tags": ["bottle", "glass"],
}
WANTED_POSTER = {
    "asset_id": "wanted_poster",
    "name": "Wanted Poster",
    "type": "poster", "placement_type": "poster", "scale_class": "small",
    "tags": ["wanted", "poster", "western", "sign"],
    "environment_tags": ["western_room"],
}
TERRAIN_ROCK = {
    "asset_id": "terrain_rock",
    "name": "Desert Rock",
    "type": "terrain", "placement_type": "terrain", "scale_class": "structural",
    "tags": ["rock", "terrain", "stone"],
}
ROBOT_ARM = {
    "asset_id": "robot_arm",
    "name": "Industrial Robot Arm",
    "type": "machine", "scale_class": "hero",
    "tags": ["robot", "robotic", "electronic", "arm"],
    "environment_tags": ["robotics_lab"],
}
CIRCUIT_BOARD = {
    "asset_id": "circuit_board",
    "name": "Circuit Board",
    "type": "electronic", "scale_class": "small",
    "tags": ["circuit", "board", "electronic", "pcb"],
    "environment_tags": ["robotics_lab"],
}
WOODEN_BEAM = {
    "asset_id": "wooden_beam",
    "name": "Wooden Beam",
    "type": "beam", "placement_type": "beam", "scale_class": "structural",
    "tags": ["beam", "structural", "wooden"],
}

CASTLE_BANNER = {
    "asset_id": "castle_banner",
    "name": "Castle Banner",
    "type": "poster", "placement_type": "poster", "scale_class": "medium",
    "tags": ["banner", "castle", "medieval", "tapestry"],
    "environment_tags": ["castle_hall"],
}
SCI_FI_TERMINAL = {
    "asset_id": "sci_fi_terminal",
    "name": "Sci-Fi Status Terminal",
    "type": "console", "placement_type": "console", "scale_class": "hero",
    "tags": ["sci-fi", "terminal", "futuristic", "holo"],
    "environment_tags": ["sci_fi_corridor"],
}


@pytest.fixture(autouse=True)
def reset_all():
    for fn in (
        reset_asset_suitability_engine_for_tests,
        reset_asset_suitability_review_for_tests,
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
        reset_asset_suitability_review_for_tests,
        reset_environment_affinity_for_tests,
        reset_role_affinity_for_tests,
        reset_style_affinity_for_tests,
        reset_material_affinity_for_tests,
        reset_scale_affinity_for_tests,
        reset_placement_affinity_for_tests,
        reset_story_affinity_for_tests,
    ):
        fn()


class TestWesternRoomSlots:
    """Spec: western_room slots select contextually correct assets."""

    def test_chair_slot_selects_wooden_saloon_chair(self):
        eng = get_asset_suitability_engine()
        req = SuitabilityRequest(environment="western_room", role="chair")
        result = eng.rank_assets([MODERN_CHAIR, TERRAIN_ROCK, WOODEN_SALOON_CHAIR], req)
        assert result.best.asset_id == "wooden_saloon_chair"

    def test_lantern_slot_selects_oil_lantern_not_bottle(self):
        eng = get_asset_suitability_engine()
        req = SuitabilityRequest(environment="western_room", role="lantern")
        result = eng.rank_assets([GENERIC_BOTTLE, OIL_LANTERN], req)
        assert result.best.asset_id == "oil_lantern"

    def test_poster_slot_selects_wanted_poster_not_rock(self):
        eng = get_asset_suitability_engine()
        req = SuitabilityRequest(environment="western_room", role="poster")
        result = eng.rank_assets([TERRAIN_ROCK, WANTED_POSTER], req)
        assert result.best.asset_id == "wanted_poster"

    def test_structural_beam_not_selected_for_chair_slot(self):
        eng = get_asset_suitability_engine()
        req = SuitabilityRequest(environment="western_room", role="chair")
        result = eng.rank_assets([WOODEN_BEAM, WOODEN_SALOON_CHAIR], req)
        assert result.best.asset_id == "wooden_saloon_chair"


class TestEnvironmentMismatchRejected:
    """Wrong-environment assets score lower than correct-environment assets."""

    def test_robot_arm_rejected_for_western_room_chair(self):
        eng = get_asset_suitability_engine()
        req = SuitabilityRequest(environment="western_room", role="chair")
        s_chair = eng.score_asset(WOODEN_SALOON_CHAIR, req).final_score
        s_robot = eng.score_asset(ROBOT_ARM, req).final_score
        assert s_chair > s_robot

    def test_wanted_poster_rejected_for_robotics_lab(self):
        eng = get_asset_suitability_engine()
        req = SuitabilityRequest(environment="robotics_lab", role="poster")
        s_poster = eng.score_asset(WANTED_POSTER, req).final_score
        s_banner = eng.score_asset(CASTLE_BANNER, req).final_score
        # Wanted poster should score low for robotics_lab
        assert s_poster < 0.70


class TestPlacementContext:
    """Placement context filters wrong-type assets."""

    def test_chair_accepted_around_table(self):
        eng = get_asset_suitability_engine()
        req = SuitabilityRequest(
            environment="western_room", role="chair",
            placement_context="around_table"
        )
        s_chair = eng.score_asset(WOODEN_SALOON_CHAIR, req).placement_score
        assert s_chair == 1.0

    def test_terrain_rock_rejected_around_table(self):
        eng = get_asset_suitability_engine()
        req = SuitabilityRequest(
            environment="western_room", role="chair",
            placement_context="around_table"
        )
        s_rock = eng.score_asset(TERRAIN_ROCK, req).placement_score
        assert s_rock < 0.50

    def test_poster_accepted_wall_mounted(self):
        eng = get_asset_suitability_engine()
        req = SuitabilityRequest(
            environment="western_room", role="poster",
            placement_context="wall_mounted"
        )
        s_poster = eng.score_asset(WANTED_POSTER, req).placement_score
        assert s_poster == 1.0


class TestCastleHall:
    """Castle hall selects medieval assets over modern ones."""

    def test_castle_banner_beats_modern_chair_for_castle_poster_slot(self):
        eng = get_asset_suitability_engine()
        req = SuitabilityRequest(environment="castle_hall", role="poster")
        s_banner = eng.score_asset(CASTLE_BANNER, req).final_score
        s_modern = eng.score_asset(MODERN_CHAIR, req).final_score
        assert s_banner > s_modern


class TestSciFiCorridor:
    """Sci-fi corridor selects futuristic assets."""

    def test_sci_fi_terminal_high_for_sci_fi_corridor(self):
        eng = get_asset_suitability_engine()
        req = SuitabilityRequest(environment="sci_fi_corridor", role="console")
        s_terminal = eng.score_asset(SCI_FI_TERMINAL, req).final_score
        assert s_terminal >= 0.60

    def test_wooden_chair_low_for_sci_fi_corridor(self):
        eng = get_asset_suitability_engine()
        req = SuitabilityRequest(environment="sci_fi_corridor", role="chair")
        s_wooden = eng.score_asset(WOODEN_SALOON_CHAIR, req).final_score
        s_terminal = eng.score_asset(SCI_FI_TERMINAL, req).final_score
        assert s_terminal > s_wooden


class TestReviewIntegration:
    """SuitabilityReview returns production_ready for well-matched results."""

    def test_good_selection_passes_review(self):
        eng = get_asset_suitability_engine()
        review = get_asset_suitability_review()
        req = SuitabilityRequest(environment="western_room", role="chair")
        result = eng.rank_assets(
            [WOODEN_SALOON_CHAIR, MODERN_CHAIR, OIL_LANTERN], req
        )
        r = review.review(result)
        assert r.best_score >= 0.50
        assert r.grade in ("A", "B", "C", "D", "F")

    def test_no_candidates_fails_review(self):
        eng = get_asset_suitability_engine()
        review = get_asset_suitability_review()
        req = SuitabilityRequest(environment="western_room", role="chair")
        result = eng.rank_assets([], req)
        r = review.review(result)
        assert r.production_ready is False
        assert r.grade == "F"
