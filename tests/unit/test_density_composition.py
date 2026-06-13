"""Tests for the §54 Density and Composition Rules (Tier 15.0+)."""

import pytest

from src.runtime.reality.density_engine import (
    get_environment_density_engine,
    reset_environment_density_engine_for_tests,
)
from src.runtime.reality.composition_engine import (
    MIN_NEGATIVE_SPACE,
    get_composition_engine,
    reset_composition_engine_for_tests,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_environment_density_engine_for_tests()
    reset_composition_engine_for_tests()
    yield
    reset_environment_density_engine_for_tests()
    reset_composition_engine_for_tests()


def _props(n):
    return [
        {"asset_id": f"crate_{i}", "asset_name": "Wooden Crate",
         "tx": (i % 8) - 4.0, "ty": 0.4, "tz": (i // 8) - 4.0,
         "bbox_half_x": 0.4, "bbox_half_y": 0.4, "bbox_half_z": 0.4}
        for i in range(n)
    ]


class TestDensity:
    def test_empty_room_invalid(self):
        result = get_environment_density_engine().evaluate(
            {"environment": "western_room", "transforms": []})
        assert result.is_empty
        assert not result.density_ok
        assert any("EMPTY_ROOM" in f for f in result.findings)

    def test_room_classes_and_targets(self):
        engine = get_environment_density_engine()
        small = engine.evaluate({"environment": "western_room", "transforms": []})
        assert small.room_class == "small"
        assert (small.target_min, small.target_max) == (10, 20)
        medium = engine.evaluate({"environment": "saloon", "transforms": []})
        assert medium.room_class == "medium"
        assert (medium.target_min, medium.target_max) == (20, 40)
        large = engine.evaluate({"environment": "industrial_hangar", "transforms": []})
        assert large.room_class == "large"
        assert (large.target_min, large.target_max) == (40, 80)

    def test_under_dressed_room_flagged(self):
        result = get_environment_density_engine().evaluate(
            {"environment": "western_room", "transforms": _props(4)})
        assert not result.density_ok
        assert any("UNDER_DRESSED" in f for f in result.findings)

    def test_density_score_formula(self):
        result = get_environment_density_engine().evaluate(
            {"environment": "western_room", "transforms": _props(12)})
        assert result.density_ok
        assert result.density_score == pytest.approx(12 / 120.0)

    def test_overcrowded_room_flagged(self):
        result = get_environment_density_engine().evaluate(
            {"environment": "western_room", "transforms": _props(25)})
        assert result.overcrowded
        assert result.density_ok   # over max is a warning, not a failure

    def test_canonical_scene_density_ok(self, western_room_scene):
        result = get_environment_density_engine().evaluate(western_room_scene)
        assert result.density_ok
        assert result.asset_count == 19


class TestComposition:
    def test_fireplace_is_primary_table_secondary(self, western_room_scene):
        result = get_composition_engine().evaluate(western_room_scene)
        assert result.has_primary
        assert result.primary_focal["asset_type"] == "fireplace"
        assert result.has_secondary
        assert result.secondary_focal["asset_type"] == "table"
        assert result.composition_ok

    def test_negative_space_preserved(self, western_room_scene):
        result = get_composition_engine().evaluate(western_room_scene)
        assert result.has_negative_space
        assert result.negative_space_ratio >= MIN_NEGATIVE_SPACE

    def test_empty_room_has_no_focal_points(self):
        result = get_composition_engine().evaluate(
            {"environment": "western_room", "transforms": []})
        assert not result.has_primary
        assert not result.composition_ok
        assert any("NO_PRIMARY_FOCAL" in f for f in result.findings)

    def test_single_focal_point_flagged(self):
        result = get_composition_engine().evaluate({
            "environment": "western_room",
            "transforms": [
                {"asset_id": "t", "asset_name": "Table", "tx": 0, "ty": 0.375, "tz": 0,
                 "bbox_half_x": 1.1, "bbox_half_y": 0.375, "bbox_half_z": 0.65},
            ],
        })
        assert result.has_primary
        assert not result.has_secondary
        assert any("NO_SECONDARY_FOCAL" in f for f in result.findings)

    def test_packed_room_loses_negative_space(self):
        # 4×4 grid of 2×2 m crates in a 10×12 room → 64 m² occupied of 120 m²
        # leaves 47% — pack more: 24 crates of 2×2 → 96 m² → 20% < 25%
        crates = [
            {"asset_id": f"c{i}", "asset_name": "Wooden Crate",
             "tx": (i % 5) * 2.0 - 4.0, "ty": 1.0, "tz": (i // 5) * 2.0 - 4.0,
             "bbox_half_x": 1.0, "bbox_half_y": 1.0, "bbox_half_z": 1.0}
            for i in range(24)
        ]
        result = get_composition_engine().evaluate(
            {"environment": "western_room", "transforms": crates})
        assert not result.has_negative_space
        assert not result.composition_ok
