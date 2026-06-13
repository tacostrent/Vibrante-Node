"""Tests for LayoutSpacingEngine (Tier 9.6)."""

import math
import pytest
from src.runtime.assets.assembly.layout_spacing_engine import (
    SpacedPosition,
    LayoutSpacingEngine,
    get_layout_spacing_engine,
    reset_layout_spacing_engine_for_tests,
)
from src.runtime.assets.assembly.asset_scale_analyzer import (
    AssetScaleProfile,
    get_asset_scale_analyzer,
    reset_asset_scale_analyzer_for_tests,
)
from src.runtime.assets.assembly.unit_normalizer import reset_unit_normalizer_for_tests
from src.runtime.assets.assembly.bounding_box_extractor import reset_bbox_extractor_for_tests


@pytest.fixture(autouse=True)
def reset():
    reset_layout_spacing_engine_for_tests()
    reset_asset_scale_analyzer_for_tests()
    reset_unit_normalizer_for_tests()
    reset_bbox_extractor_for_tests()
    yield
    reset_layout_spacing_engine_for_tests()
    reset_asset_scale_analyzer_for_tests()
    reset_unit_normalizer_for_tests()
    reset_bbox_extractor_for_tests()


def _profile(asset_id, radius, scale_class="medium"):
    return AssetScaleProfile(
        asset_id=asset_id, asset_name=asset_id,
        placement_radius=radius, asset_scale_class=scale_class,
        bbox_meters=(radius*2, 1.0, radius*2),
    )


class TestSingleton:
    def test_singleton_same_instance(self):
        assert get_layout_spacing_engine() is get_layout_spacing_engine()

    def test_reset_new_instance(self):
        a = get_layout_spacing_engine()
        reset_layout_spacing_engine_for_tests()
        assert a is not get_layout_spacing_engine()


class TestLinearPositions:
    def test_single_asset_at_start_x(self):
        eng = get_layout_spacing_engine()
        p = _profile("a", 0.30)
        result = eng.linear_positions([p], start_x=0.0)
        assert len(result) == 1

    def test_two_assets_not_overlapping(self):
        eng = get_layout_spacing_engine()
        pa = _profile("a", 0.30)
        pb = _profile("b", 0.35)
        result = eng.linear_positions([pa, pb], centre=False)
        assert len(result) == 2
        dist = abs(result[1].position[0] - result[0].position[0])
        # Must be >= radius_a + radius_b (no overlap)
        assert dist >= pa.placement_radius + pb.placement_radius - 1e-6

    def test_three_assets_increasing_x(self):
        eng = get_layout_spacing_engine()
        profiles = [_profile(f"a{i}", 0.25) for i in range(3)]
        result = eng.linear_positions(profiles, centre=False)
        assert result[0].position[0] < result[1].position[0] < result[2].position[0]

    def test_empty_list_returns_empty(self):
        eng = get_layout_spacing_engine()
        assert eng.linear_positions([]) == []

    def test_depth_z_applied(self):
        eng = get_layout_spacing_engine()
        p = _profile("a", 0.3)
        result = eng.linear_positions([p], depth_z=5.0)
        assert result[0].position[2] == 5.0

    def test_source_is_scale_aware(self):
        eng = get_layout_spacing_engine()
        p = _profile("a", 0.3)
        result = eng.linear_positions([p])
        assert result[0].source == "scale_aware"

    def test_spacing_smaller_than_3m(self):
        # The old fixed offset was 3.0 m; chairs should be much closer
        eng = get_layout_spacing_engine()
        profiles = [_profile(f"c{i}", 0.25, "medium") for i in range(2)]
        result = eng.linear_positions(profiles, centre=False)
        dist = abs(result[1].position[0] - result[0].position[0])
        # Two chairs with radius 0.25 → spacing ~ 0.25 + 0.20 + 0.25 = 0.70 m
        assert dist < 2.0, f"Chair spacing {dist:.2f} m is too large (old fixed-offset behavior)"


class TestClusterPositions:
    def test_four_chairs_around_table(self):
        eng = get_layout_spacing_engine()
        table = _profile("table", 0.45, "medium")
        chairs = [_profile(f"chair{i}", 0.25, "medium") for i in range(4)]
        result = eng.cluster_positions(table, chairs, anchor_pos=(0.0, 0.0, 0.0))
        assert len(result) == 4
        for r in result:
            # All chairs should be > 0 distance from origin
            dist = math.sqrt(r.position[0]**2 + r.position[2]**2)
            # dist ≈ table_radius + margin + chair_radius ≈ 0.45 + 0.20 + 0.25 = 0.90
            assert dist > 0.5, f"Chair too close to table centre: {dist:.2f} m"

    def test_empty_children_returns_empty(self):
        eng = get_layout_spacing_engine()
        table = _profile("table", 0.45)
        assert eng.cluster_positions(table, []) == []

    def test_cluster_evenly_distributed(self):
        eng = get_layout_spacing_engine()
        anchor = _profile("anchor", 0.5)
        children = [_profile(f"c{i}", 0.2) for i in range(4)]
        result = eng.cluster_positions(anchor, children)
        # Angles should be ~90° apart → check no two are in the same position
        positions = [r.position for r in result]
        for i, p1 in enumerate(positions):
            for j, p2 in enumerate(positions):
                if i != j:
                    dx = p1[0] - p2[0]
                    dz = p1[2] - p2[2]
                    dist = math.sqrt(dx**2 + dz**2)
                    assert dist > 0.01, f"Positions {i} and {j} are identical"


class TestOverflowPosition:
    def test_overflow_advances_x(self):
        eng = get_layout_spacing_engine()
        prev = _profile("prev", 0.35, "medium")
        curr = _profile("curr", 0.30, "medium")
        result = eng.overflow_position(curr, (2.0, 0.0, 0.0), prev, axis="x")
        # New x should be > 2.0
        assert result.position[0] > 2.0

    def test_overflow_step_smaller_than_old_3m(self):
        eng = get_layout_spacing_engine()
        prev = _profile("chair", 0.25, "medium")
        curr = _profile("chair2", 0.25, "medium")
        result = eng.overflow_position(curr, (0.0, 0.0, 0.0), prev)
        # Step ≈ 0.25 + 0.20 + 0.25 = 0.70 m — much less than old 3.0 m
        assert result.spacing_used < 3.0

    def test_overflow_z_axis(self):
        eng = get_layout_spacing_engine()
        prev = _profile("p", 0.3)
        curr = _profile("c", 0.3)
        result = eng.overflow_position(curr, (0.0, 0.0, 5.0), prev, axis="z")
        assert result.position[2] < 5.0  # Z decreases (into the scene)


class TestSpaceAssets:
    def test_structural_assets_skipped(self):
        eng = get_layout_spacing_engine()
        assets = [
            {"name": "Chair", "bbox_x": 48.9, "bbox_y": 83.8, "bbox_z": 43.3, "category": "furniture"},
            {"name": "Old Wooden Beam", "bbox_x": 377.7, "bbox_y": 36.6, "bbox_z": 36.2, "category": "structure"},
            {"name": "Table", "bbox_x": 69.7, "bbox_y": 49.9, "bbox_z": 69.8, "category": "furniture"},
        ]
        result = eng.space_assets(assets)
        # Only chair and table should be spaced (beam is structural)
        assert len(result) == 2

    def test_chair_and_table_not_overlapping(self):
        eng = get_layout_spacing_engine()
        assets = [
            {"name": "Chair", "bbox_x": 48.9, "bbox_y": 83.8, "bbox_z": 43.3, "category": "furniture"},
            {"name": "Table", "bbox_x": 69.7, "bbox_y": 49.9, "bbox_z": 69.8, "category": "furniture"},
        ]
        result = eng.space_assets(assets)
        assert len(result) == 2
        dist = abs(result[1].position[0] - result[0].position[0])
        # Both assets have radius ~0.25–0.35 m → spacing < 2 m
        assert 0.3 <= dist <= 2.0
