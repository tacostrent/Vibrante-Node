"""
Tests for PlanSerializer (Tier 7).

Covers:
 - to_json / from_json round-trip
 - sorted keys in JSON
 - compact mode
 - from_json lenient on error
 - from_json raises PlanSerializationError when lenient=False
 - save / load round-trip (tmp file)
 - to_json_list / from_json_list
 - singleton / reset
"""

import json
import os
import tempfile
import pytest

from src.runtime.planning.serialization.plan_serializer import (
    PlanSerializationError,
    PlanSerializer,
    get_plan_serializer,
    reset_plan_serializer_for_tests,
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
    reset_plan_serializer_for_tests()
    yield
    reset_plan_serializer_for_tests()


def _make_plan():
    z = SceneZonePlan(zone_type="midground", asset_categories=["building"], priority=7)
    q = AssetQuery(category="building", zone="midground", quantity=2)
    cam = CameraTarget(name="overview", shot_type="establishing")
    rule = CompositionRule(rule_type="hero_focal_point")
    return ScenePlan(
        environment="urban",
        style="cinematic",
        mood="dramatic",
        zones=[z],
        asset_queries=[q],
        camera_targets=[cam],
        composition_rules=[rule],
        estimated_asset_count=2,
    )


class TestPlanSerializerSingleton:
    def test_singleton(self):
        assert get_plan_serializer() is get_plan_serializer()

    def test_reset_creates_new(self):
        a = get_plan_serializer()
        reset_plan_serializer_for_tests()
        assert a is not get_plan_serializer()


class TestPlanSerializerToFromJson:
    def test_to_json_returns_string(self):
        plan = _make_plan()
        s = get_plan_serializer().to_json(plan)
        assert isinstance(s, str)

    def test_json_is_valid(self):
        plan = _make_plan()
        s = get_plan_serializer().to_json(plan)
        data = json.loads(s)
        assert isinstance(data, dict)

    def test_json_sorted_keys(self):
        plan = _make_plan()
        data = json.loads(get_plan_serializer().to_json(plan))
        keys = list(data.keys())
        assert keys == sorted(keys)

    def test_compact_mode_no_whitespace(self):
        plan = _make_plan()
        s = get_plan_serializer().to_json(plan, compact=True)
        assert " " not in s.split("{")[1]  # no spaces in object body

    def test_round_trip(self):
        plan = _make_plan()
        plan2 = get_plan_serializer().from_json(get_plan_serializer().to_json(plan))
        assert plan2.environment == "urban"
        assert plan2.style == "cinematic"
        assert len(plan2.zones) == 1
        assert len(plan2.asset_queries) == 1
        assert len(plan2.camera_targets) == 1
        assert len(plan2.composition_rules) == 1

    def test_from_json_corrupt_lenient_returns_empty(self):
        plan = get_plan_serializer().from_json("not json at all", lenient=True)
        assert plan.environment is None

    def test_from_json_corrupt_strict_raises(self):
        with pytest.raises(PlanSerializationError):
            get_plan_serializer().from_json("not json at all", lenient=False)

    def test_from_json_empty_lenient_returns_empty(self):
        plan = get_plan_serializer().from_json("{}", lenient=True)
        assert isinstance(plan, ScenePlan)


class TestPlanSerializerSaveLoad:
    def test_save_load_round_trip(self, tmp_path):
        plan = _make_plan()
        p = str(tmp_path / "test_plan.json")
        get_plan_serializer().save(plan, p)
        plan2 = get_plan_serializer().load(p)
        assert plan2.environment == plan.environment
        assert len(plan2.zones) == len(plan.zones)

    def test_load_missing_file_lenient_returns_empty(self, tmp_path):
        plan = get_plan_serializer().load(str(tmp_path / "nonexistent.json"), lenient=True)
        assert isinstance(plan, ScenePlan)

    def test_load_missing_file_strict_raises(self, tmp_path):
        with pytest.raises((FileNotFoundError, PlanSerializationError)):
            get_plan_serializer().load(str(tmp_path / "nonexistent.json"), lenient=False)


class TestPlanSerializerList:
    def test_to_json_list_returns_array(self):
        plans = [_make_plan(), _make_plan()]
        s = get_plan_serializer().to_json_list(plans)
        data = json.loads(s)
        assert isinstance(data, list)
        assert len(data) == 2

    def test_from_json_list_round_trip(self):
        plans = [_make_plan(), _make_plan()]
        s = get_plan_serializer().to_json_list(plans)
        plans2 = get_plan_serializer().from_json_list(s)
        assert len(plans2) == 2
        assert all(p.environment == "urban" for p in plans2)

    def test_from_json_list_not_array_lenient(self):
        result = get_plan_serializer().from_json_list("{}", lenient=True)
        assert result == []

    def test_from_json_list_corrupt_lenient(self):
        result = get_plan_serializer().from_json_list("bad json", lenient=True)
        assert result == []
