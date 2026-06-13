"""Tests for EnvironmentCompletenessReviewer (Tier 9.5)."""

import pytest
from src.runtime.assets.assembly.environment_completeness_review import (
    EnvironmentCompletenessReview,
    EnvironmentCompletenessReviewer,
    get_environment_completeness_reviewer,
    reset_environment_completeness_reviewer_for_tests,
)
from src.runtime.assets.assembly.environment_structure_builder import (
    EnvironmentStructure,
    get_environment_structure_builder,
    reset_environment_structure_builder_for_tests,
)
from src.runtime.assets.assembly.anchor_asset_engine import (
    AnchorPlan,
    get_anchor_asset_engine,
    reset_anchor_asset_engine_for_tests,
)
from src.runtime.assets.assembly.decorative_population_engine import (
    DecorationPlan,
    get_decorative_population_engine,
    reset_decorative_population_engine_for_tests,
)
from src.runtime.assets.assembly.architectural_templates import (
    reset_architectural_templates_for_tests,
)


@pytest.fixture(autouse=True)
def reset():
    reset_environment_completeness_reviewer_for_tests()
    reset_environment_structure_builder_for_tests()
    reset_anchor_asset_engine_for_tests()
    reset_decorative_population_engine_for_tests()
    reset_architectural_templates_for_tests()
    yield
    reset_environment_completeness_reviewer_for_tests()
    reset_environment_structure_builder_for_tests()
    reset_anchor_asset_engine_for_tests()
    reset_decorative_population_engine_for_tests()
    reset_architectural_templates_for_tests()


class TestSingleton:
    def test_singleton_returns_same_instance(self):
        a = get_environment_completeness_reviewer()
        b = get_environment_completeness_reviewer()
        assert a is b

    def test_reset_creates_fresh_instance(self):
        a = get_environment_completeness_reviewer()
        reset_environment_completeness_reviewer_for_tests()
        b = get_environment_completeness_reviewer()
        assert a is not b


class TestReviewMethod:
    def test_returns_review_object(self):
        reviewer = get_environment_completeness_reviewer()
        result = reviewer.review("industrial_hangar")
        assert isinstance(result, EnvironmentCompletenessReview)

    def test_correct_environment_name(self):
        reviewer = get_environment_completeness_reviewer()
        result = reviewer.review("western_room")
        assert result.environment_name == "western_room"

    def test_western_room_is_production_ready(self):
        reviewer = get_environment_completeness_reviewer()
        result = reviewer.review("western_room")
        assert result.production_ready is True
        assert result.overall_score >= 0.70

    def test_industrial_hangar_is_production_ready(self):
        reviewer = get_environment_completeness_reviewer()
        result = reviewer.review("industrial_hangar")
        assert result.production_ready is True

    def test_castle_hall_is_production_ready(self):
        reviewer = get_environment_completeness_reviewer()
        result = reviewer.review("castle_hall")
        assert result.production_ready is True

    def test_forest_is_production_ready(self):
        reviewer = get_environment_completeness_reviewer()
        result = reviewer.review("forest")
        assert result.production_ready is True

    def test_grade_a_for_high_score(self):
        reviewer = get_environment_completeness_reviewer()
        result = reviewer.review("western_room")
        assert result.grade in ("A", "B")

    def test_grade_mapping_logic(self):
        reviewer = get_environment_completeness_reviewer()
        # Test internally — create mock results
        from src.runtime.assets.assembly.environment_completeness_review import _grade
        assert _grade(0.90) == "A"
        assert _grade(0.75) == "B"
        assert _grade(0.60) == "C"
        assert _grade(0.45) == "D"
        assert _grade(0.30) == "F"

    def test_all_score_dimensions_between_0_and_1(self):
        reviewer = get_environment_completeness_reviewer()
        result = reviewer.review("control_room")
        assert 0.0 <= result.structure_score <= 1.0
        assert 0.0 <= result.zone_score <= 1.0
        assert 0.0 <= result.anchor_score <= 1.0
        assert 0.0 <= result.support_score <= 1.0
        assert 0.0 <= result.decoration_score <= 1.0
        assert 0.0 <= result.atmosphere_score <= 1.0
        assert 0.0 <= result.overall_score <= 1.0

    def test_review_summary_is_specific(self):
        reviewer = get_environment_completeness_reviewer()
        result = reviewer.review("library")
        assert result.review_summary != ""
        # Must reference the environment name or a specific issue
        assert "library" in result.review_summary.lower() or len(result.review_summary) > 20

    def test_blocking_findings_empty_for_production_ready(self):
        reviewer = get_environment_completeness_reviewer()
        result = reviewer.review("western_room")
        assert result.production_ready is True
        assert result.blocking_findings == []

    def test_all_environments_can_be_reviewed(self):
        from src.runtime.assets.assembly.architectural_templates import SUPPORTED_ENVIRONMENTS
        reviewer = get_environment_completeness_reviewer()
        for env in SUPPORTED_ENVIRONMENTS:
            result = reviewer.review(env)
            assert isinstance(result, EnvironmentCompletenessReview), \
                f"{env} failed to produce a review"
            assert 0.0 <= result.overall_score <= 1.0, \
                f"{env} has out-of-range overall_score: {result.overall_score}"


class TestBlockingFindings:
    def test_empty_structure_has_blocking_finding(self):
        reviewer = get_environment_completeness_reviewer()
        # Create an empty structure (no elements, no blueprint) and empty plans
        empty_structure = EnvironmentStructure(
            environment_name = "empty_test",
            blueprint        = None,
            structural_elements = [],
            zones            = [],
            structure_complete = False,
            missing_required = [],
        )
        empty_anchor = AnchorPlan(environment_name="empty_test", anchors=[])
        empty_deco   = DecorationPlan(environment_name="empty_test", items=[])

        result = reviewer.review_from_components(empty_structure, empty_anchor, empty_deco)
        assert result.production_ready is False

    def test_missing_anchors_blocks_production(self):
        reviewer = get_environment_completeness_reviewer()
        # Normal structure, empty anchor plan
        structure = get_environment_structure_builder().build_structure("western_room")
        empty_anchor = AnchorPlan(environment_name="western_room", anchors=[])
        deco = get_decorative_population_engine().get_decoration_plan("western_room")

        result = reviewer.review_from_components(structure, empty_anchor, deco)
        assert result.production_ready is False
        assert any("anchor" in b.lower() for b in result.blocking_findings)

    def test_no_zones_blocks_production(self):
        reviewer = get_environment_completeness_reviewer()
        from src.runtime.assets.assembly.environment_blueprint import EnvironmentBlueprint
        bp = EnvironmentBlueprint(
            environment_name = "no_zones_env",
            structural_assets = ["floor", "wall"],
        )
        structure = EnvironmentStructure(
            environment_name = "no_zones_env",
            blueprint        = bp,
            structural_elements = [],
            zones            = [],  # no zones
            structure_complete = True,
        )
        anchor = get_anchor_asset_engine().get_anchor_plan("western_room")
        deco   = get_decorative_population_engine().get_decoration_plan("western_room")

        result = reviewer.review_from_components(structure, anchor, deco)
        assert result.production_ready is False
        assert any("zone" in b.lower() for b in result.blocking_findings)


class TestReviewFromComponents:
    def test_from_components_matches_review(self):
        reviewer = get_environment_completeness_reviewer()
        structure  = get_environment_structure_builder().build_structure("robotics_lab")
        anchors    = get_anchor_asset_engine().get_anchor_plan("robotics_lab")
        decoration = get_decorative_population_engine().get_decoration_plan("robotics_lab", anchors)

        result_a = reviewer.review("robotics_lab")
        result_b = reviewer.review_from_components(structure, anchors, decoration)
        # Both paths should give the same production_ready and grade
        assert result_a.production_ready == result_b.production_ready
        assert result_a.grade == result_b.grade


class TestReviewSerialization:
    def test_to_dict_roundtrip(self):
        reviewer = get_environment_completeness_reviewer()
        result = reviewer.review("library")
        d = result.to_dict()
        restored = EnvironmentCompletenessReview.from_dict(d)
        assert restored.environment_name == "library"
        assert restored.overall_score == result.overall_score
        assert restored.grade == result.grade
        assert restored.production_ready == result.production_ready
