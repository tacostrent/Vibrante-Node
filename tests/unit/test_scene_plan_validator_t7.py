"""
Tests for ScenePlanValidator (Tier 7).

Covers:
 - valid plan passes all checks
 - missing zones → error
 - zone with no asset_categories → error
 - missing camera_targets → error
 - missing composition_rules → error
 - zero estimated_asset_count → warning
 - out-of-range zone priority → error
 - duplicate zone types → warning
 - invalid asset_query priority → warning
 - invalid camera shot_type → warning
 - invalid composition rule_type → warning
 - check_count always 10
 - validator mutates plan fields
 - singleton / reset
"""

import pytest

from src.runtime.planning.validators.scene_plan_validator import (
    ScenePlanValidator,
    ValidationReport,
    get_scene_plan_validator,
    reset_scene_plan_validator_for_tests,
)
from src.runtime.planning.schema.scene_plan import (
    AssetQuery,
    CameraTarget,
    CompositionRule,
    ScenePlan,
    SceneZonePlan,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_scene_plan_validator_for_tests()
    yield
    reset_scene_plan_validator_for_tests()


def _valid_plan() -> ScenePlan:
    """Return a minimal plan that passes all checks."""
    fg = SceneZonePlan(zone_type="foreground", asset_categories=["debris"], priority=10)
    mg = SceneZonePlan(zone_type="midground",  asset_categories=["building"], priority=7)
    q  = AssetQuery(category="building", zone="midground", quantity=2, priority="recommended")
    cam = CameraTarget(name="overview", shot_type="establishing")
    rule = CompositionRule(rule_type="hero_focal_point", priority=0.9)
    plan = ScenePlan(
        environment="urban",
        zones=[fg, mg],
        asset_queries=[q],
        camera_targets=[cam],
        composition_rules=[rule],
        estimated_complexity="moderate",
        estimated_asset_count=3,
    )
    return plan


class TestScenePlanValidatorSingleton:
    def test_singleton(self):
        assert get_scene_plan_validator() is get_scene_plan_validator()

    def test_reset_creates_new(self):
        a = get_scene_plan_validator()
        reset_scene_plan_validator_for_tests()
        assert a is not get_scene_plan_validator()


class TestScenePlanValidatorValidPlan:
    def test_valid_plan_returns_valid_true(self):
        plan = _valid_plan()
        report = get_scene_plan_validator().validate(plan)
        assert report.valid is True

    def test_valid_plan_zero_errors(self):
        plan = _valid_plan()
        report = get_scene_plan_validator().validate(plan)
        assert report.errors == []

    def test_check_count_is_ten(self):
        plan = _valid_plan()
        report = get_scene_plan_validator().validate(plan)
        assert report.check_count == 10

    def test_mutates_plan_validated(self):
        plan = _valid_plan()
        assert plan.validated is False
        get_scene_plan_validator().validate(plan)
        assert plan.validated is True

    def test_mutates_plan_validation_errors(self):
        plan = _valid_plan()
        get_scene_plan_validator().validate(plan)
        assert isinstance(plan.validation_errors, list)

    def test_mutates_plan_validation_warnings(self):
        plan = _valid_plan()
        get_scene_plan_validator().validate(plan)
        assert isinstance(plan.validation_warnings, list)


class TestScenePlanValidatorErrors:
    def test_no_zones_is_error(self):
        plan = _valid_plan()
        plan.zones = []
        report = get_scene_plan_validator().validate(plan)
        assert report.valid is False
        assert any("no zones" in e.lower() for e in report.errors)

    def test_zone_with_no_categories_is_error(self):
        plan = _valid_plan()
        plan.zones[0].asset_categories = []
        report = get_scene_plan_validator().validate(plan)
        assert report.valid is False
        assert any("asset categories" in e for e in report.errors)

    def test_no_camera_targets_is_error(self):
        plan = _valid_plan()
        plan.camera_targets = []
        report = get_scene_plan_validator().validate(plan)
        assert report.valid is False
        assert any("camera" in e.lower() for e in report.errors)

    def test_no_composition_rules_is_error(self):
        plan = _valid_plan()
        plan.composition_rules = []
        report = get_scene_plan_validator().validate(plan)
        assert report.valid is False
        assert any("composition" in e.lower() for e in report.errors)

    def test_out_of_range_zone_priority_is_error(self):
        plan = _valid_plan()
        plan.zones[0].priority = 11
        report = get_scene_plan_validator().validate(plan)
        assert report.valid is False
        assert any("priority" in e.lower() for e in report.errors)

    def test_priority_zero_is_error(self):
        plan = _valid_plan()
        plan.zones[0].priority = 0
        report = get_scene_plan_validator().validate(plan)
        assert report.valid is False


class TestScenePlanValidatorWarnings:
    def test_zero_estimated_asset_count_is_warning(self):
        plan = _valid_plan()
        plan.estimated_asset_count = 0
        report = get_scene_plan_validator().validate(plan)
        assert any("estimated_asset_count" in w for w in report.warnings)

    def test_duplicate_zone_types_is_warning(self):
        plan = _valid_plan()
        plan.zones.append(SceneZonePlan(zone_type="foreground", asset_categories=["pipe"]))
        report = get_scene_plan_validator().validate(plan)
        assert any("duplicate" in w.lower() for w in report.warnings)

    def test_invalid_asset_query_priority_is_warning(self):
        plan = _valid_plan()
        plan.asset_queries[0].priority = "ultra"
        report = get_scene_plan_validator().validate(plan)
        assert any("priority" in w.lower() for w in report.warnings)

    def test_invalid_camera_shot_type_is_warning(self):
        plan = _valid_plan()
        plan.camera_targets[0].shot_type = "flying_camera"
        report = get_scene_plan_validator().validate(plan)
        assert any("shot_type" in w.lower() for w in report.warnings)

    def test_invalid_composition_rule_type_is_warning(self):
        plan = _valid_plan()
        plan.composition_rules[0].rule_type = "magic_framing"
        report = get_scene_plan_validator().validate(plan)
        assert any("rule_type" in w.lower() for w in report.warnings)


class TestValidationReport:
    def test_to_dict_keys(self):
        r = ValidationReport(valid=True, errors=[], warnings=["minor"], check_count=10)
        d = r.to_dict()
        for k in ("valid", "errors", "warnings", "check_count", "error_count", "warning_count"):
            assert k in d

    def test_counts_correct(self):
        r = ValidationReport(valid=False, errors=["e1", "e2"], warnings=["w1"], check_count=10)
        d = r.to_dict()
        assert d["error_count"] == 2
        assert d["warning_count"] == 1
