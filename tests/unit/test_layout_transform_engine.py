"""
Tests for src.runtime.layout_transform_engine
No bridge, no LLM. Pure unit tests.
Validates determinism: same input → same output always.
"""
import pytest
from src.runtime.layout_transform_engine import (
    LayoutTransformEngine,
    get_layout_transform_engine,
    reset_layout_transform_engine_for_tests,
    _ZONE_DEPTHS,
    _ZONE_WIDTHS,
)


@pytest.fixture(autouse=True)
def reset():
    reset_layout_transform_engine_for_tests()
    yield
    reset_layout_transform_engine_for_tests()


def _assets(names, categories=None):
    if categories is None:
        categories = ["misc"] * len(names)
    return [{"name": n, "category": c} for n, c in zip(names, categories)]


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton():
    a = get_layout_transform_engine()
    b = get_layout_transform_engine()
    assert a is b


def test_reset_creates_new():
    a = get_layout_transform_engine()
    reset_layout_transform_engine_for_tests()
    b = get_layout_transform_engine()
    assert a is not b


# ---------------------------------------------------------------------------
# calculate_spacing_offsets — pure arithmetic
# ---------------------------------------------------------------------------

def test_spacing_empty():
    e = LayoutTransformEngine()
    assert e.calculate_spacing_offsets(0, 30.0) == []


def test_spacing_single_centred():
    e = LayoutTransformEngine()
    offsets = e.calculate_spacing_offsets(1, 30.0)
    assert offsets == [0.0]


def test_spacing_two_symmetric():
    e = LayoutTransformEngine()
    offsets = e.calculate_spacing_offsets(2, 30.0)
    assert len(offsets) == 2
    assert abs(offsets[0] + offsets[1]) < 1e-6  # symmetric about 0


def test_spacing_three_symmetric():
    e = LayoutTransformEngine()
    offsets = e.calculate_spacing_offsets(3, 30.0)
    assert len(offsets) == 3
    assert abs(offsets[1]) < 1e-6  # middle is at 0


def test_spacing_is_evenly_spaced():
    e = LayoutTransformEngine()
    offsets = e.calculate_spacing_offsets(4, 40.0)
    diffs = [offsets[i+1] - offsets[i] for i in range(len(offsets)-1)]
    assert all(abs(d - diffs[0]) < 1e-4 for d in diffs)


def test_spacing_deterministic():
    e = LayoutTransformEngine()
    r1 = e.calculate_spacing_offsets(5, 50.0)
    r2 = e.calculate_spacing_offsets(5, 50.0)
    assert r1 == r2


# ---------------------------------------------------------------------------
# calculate_asset_positions
# ---------------------------------------------------------------------------

def test_positions_returns_dict():
    e = LayoutTransformEngine()
    assets = _assets(["a1", "a2"])
    result = e.calculate_asset_positions(assets, "hero_area", {})
    assert isinstance(result, dict)


def test_positions_key_per_asset():
    e = LayoutTransformEngine()
    assets = _assets(["a1", "a2", "a3"])
    result = e.calculate_asset_positions(assets, "hero_area", {})
    assert set(result.keys()) == {"a1", "a2", "a3"}


def test_positions_hero_zone_depth():
    e = LayoutTransformEngine()
    assets = _assets(["hero"])
    result = e.calculate_asset_positions(assets, "hero_area", {})
    _, _, tz = result["hero"]
    expected_z = _ZONE_DEPTHS.get("hero_area", 0.0)
    assert abs(tz - expected_z) < 1e-4


def test_positions_background_zone_depth():
    e = LayoutTransformEngine()
    assets = _assets(["bg1"])
    result = e.calculate_asset_positions(assets, "background", {})
    _, _, tz = result["bg1"]
    expected_z = _ZONE_DEPTHS.get("background", -30.0)
    assert tz <= expected_z + 0.1  # at or behind bg depth


def test_positions_single_asset_at_centre():
    e = LayoutTransformEngine()
    assets = _assets(["solo"])
    result = e.calculate_asset_positions(assets, "midground", {})
    tx, _, _ = result["solo"]
    assert abs(tx) < 1e-4


def test_positions_three_tuple():
    e = LayoutTransformEngine()
    assets = _assets(["a1"])
    result = e.calculate_asset_positions(assets, "hero_area", {})
    pos = result["a1"]
    assert len(pos) == 3


def test_positions_empty_assets():
    e = LayoutTransformEngine()
    result = e.calculate_asset_positions([], "hero_area", {})
    assert result == {}


def test_positions_deterministic():
    e = LayoutTransformEngine()
    assets = _assets(["a", "b", "c"])
    r1 = e.calculate_asset_positions(assets, "midground", {})
    r2 = e.calculate_asset_positions(assets, "midground", {})
    assert r1 == r2


def test_positions_increments_calc_count():
    e = LayoutTransformEngine()
    e.calculate_asset_positions(_assets(["a"]), "hero_area", {})
    e.calculate_asset_positions(_assets(["b"]), "background", {})
    assert e.stats()["calc_count"] == 2


def test_positions_y_for_sky_category():
    e = LayoutTransformEngine()
    assets = _assets(["sky1"], ["sky"])
    result = e.calculate_asset_positions(assets, "background", {})
    _, ty, _ = result["sky1"]
    assert ty > 10.0  # sky is high up


# ---------------------------------------------------------------------------
# calculate_asset_rotations
# ---------------------------------------------------------------------------

def test_rotations_returns_dict():
    e = LayoutTransformEngine()
    assets = _assets(["r1"])
    result = e.calculate_asset_rotations(assets, "hero_area")
    assert isinstance(result, dict)


def test_rotations_key_per_asset():
    e = LayoutTransformEngine()
    assets = _assets(["a", "b"])
    result = e.calculate_asset_rotations(assets, "background")
    assert set(result.keys()) == {"a", "b"}


def test_rotations_three_tuple():
    e = LayoutTransformEngine()
    assets = _assets(["a"])
    result = e.calculate_asset_rotations(assets, "hero_area")
    rot = result["a"]
    assert len(rot) == 3


def test_rotations_hero_first_asset_subtle_angle():
    e = LayoutTransformEngine()
    assets = _assets(["hero1"])
    result = e.calculate_asset_rotations(assets, "hero_area")
    rx, ry, rz = result["hero1"]
    # First hero gets 0° (first in _HERO_FACING_ANGLES)
    assert abs(ry) < 1.0


def test_rotations_hero_second_asset_angled():
    e = LayoutTransformEngine()
    assets = _assets(["hero1", "hero2"])
    result = e.calculate_asset_rotations(assets, "hero_area")
    _, ry2, _ = result["hero2"]
    # Second hero gets -15°
    assert abs(ry2) > 0.0


def test_rotations_ceiling_category_rx():
    e = LayoutTransformEngine()
    assets = _assets(["ceil1"], ["ceiling"])
    result = e.calculate_asset_rotations(assets, "ceiling")
    rx, _, _ = result["ceil1"]
    assert rx == -90.0


def test_rotations_tech_panel_base_rotation():
    e = LayoutTransformEngine()
    assets = _assets(["panel1"], ["tech_panel"])
    result = e.calculate_asset_rotations(assets, "background")
    _, ry, _ = result["panel1"]
    assert ry == 90.0


def test_rotations_deterministic():
    e = LayoutTransformEngine()
    assets = _assets(["a", "b", "c"])
    r1 = e.calculate_asset_rotations(assets, "background")
    r2 = e.calculate_asset_rotations(assets, "background")
    assert r1 == r2


# ---------------------------------------------------------------------------
# generate_depth_layers
# ---------------------------------------------------------------------------

def test_depth_layers_has_required_keys():
    e = LayoutTransformEngine()
    result = e.generate_depth_layers(
        {"hero_area": [], "midground": [], "background": []},
        ["hero_area", "midground", "background"],
    )
    assert {"layer_order", "zone_depths", "layer_bounds"} <= set(result.keys())


def test_depth_layers_render_order_back_to_front():
    e = LayoutTransformEngine()
    result = e.generate_depth_layers(
        {"hero_area": [], "midground": [], "background": []},
        ["hero_area", "midground", "background"],  # hero-first per env_rules
    )
    ro = result["layer_order"]
    # reversed → background first
    assert ro.index("background") < ro.index("hero_area")


def test_depth_layers_zone_depths_populated():
    e = LayoutTransformEngine()
    result = e.generate_depth_layers(
        {"hero_area": [], "background": []},
        ["hero_area", "background"],
    )
    assert "hero_area" in result["zone_depths"]
    assert "background" in result["zone_depths"]


def test_depth_layers_bounds_have_min_max_width():
    e = LayoutTransformEngine()
    result = e.generate_depth_layers(
        {"hero_area": []},
        ["hero_area"],
    )
    bounds = result["layer_bounds"]["hero_area"]
    assert "min_z" in bounds
    assert "max_z" in bounds
    assert "width" in bounds


def test_depth_layers_hero_shallower_than_background():
    e = LayoutTransformEngine()
    result = e.generate_depth_layers({}, ["hero_area", "background"])
    hero_z = result["zone_depths"]["hero_area"]
    bg_z = result["zone_depths"]["background"]
    assert hero_z > bg_z  # hero is closer (less negative Z)


# ---------------------------------------------------------------------------
# calculate_camera_focus_targets
# ---------------------------------------------------------------------------

def test_camera_targets_returns_list():
    e = LayoutTransformEngine()
    targets = e.calculate_camera_focus_targets(
        {"hero_area": [{"name": "mech", "category": "robot"}]},
        {},
    )
    assert isinstance(targets, list)


def test_camera_targets_always_has_establishing():
    e = LayoutTransformEngine()
    targets = e.calculate_camera_focus_targets({}, {})
    shot_types = [t["shot_type"] for t in targets]
    assert "wide_establishing" in shot_types


def test_camera_targets_hero_focus_when_hero_present():
    e = LayoutTransformEngine()
    targets = e.calculate_camera_focus_targets(
        {"hero_area": [{"name": "mech"}]},
        {},
    )
    shot_types = [t["shot_type"] for t in targets]
    assert "hero_focus" in shot_types


def test_camera_targets_required_keys():
    e = LayoutTransformEngine()
    targets = e.calculate_camera_focus_targets({}, {})
    for t in targets:
        assert "name" in t
        assert "zone" in t
        assert "position" in t
        assert "shot_type" in t
        assert "priority" in t


def test_camera_targets_priority_ordered():
    e = LayoutTransformEngine()
    targets = e.calculate_camera_focus_targets(
        {"hero_area": [{"name": "mech"}], "midground": [{"name": "crate"}]},
        {},
    )
    priorities = [t["priority"] for t in targets]
    assert priorities == sorted(priorities)


# ---------------------------------------------------------------------------
# calculate_spacing_offsets — extended
# ---------------------------------------------------------------------------

def test_spacing_larger_width_bigger_gaps():
    e = LayoutTransformEngine()
    narrow = e.calculate_spacing_offsets(3, 10.0)
    wide   = e.calculate_spacing_offsets(3, 40.0)
    if len(narrow) > 1 and len(wide) > 1:
        narrow_gap = abs(narrow[1] - narrow[0])
        wide_gap   = abs(wide[1] - wide[0])
        assert wide_gap > narrow_gap


def test_spacing_large_n_symmetric():
    e = LayoutTransformEngine()
    offsets = e.calculate_spacing_offsets(8, 80.0)
    assert len(offsets) == 8
    assert abs(offsets[0] + offsets[-1]) < 1e-4


# ---------------------------------------------------------------------------
# calculate_asset_positions — extended
# ---------------------------------------------------------------------------

def test_positions_midground_depth():
    e = LayoutTransformEngine()
    assets = _assets(["m1"])
    result = e.calculate_asset_positions(assets, "midground", {})
    _, _, tz = result["m1"]
    expected_z = _ZONE_DEPTHS.get("midground", -10.0)
    assert tz <= expected_z + 0.1


def test_positions_multiple_assets_different_x():
    e = LayoutTransformEngine()
    assets = _assets(["a1", "a2"])
    result = e.calculate_asset_positions(assets, "midground", {})
    tx1, _, _ = result["a1"]
    tx2, _, _ = result["a2"]
    assert abs(tx1 - tx2) > 0.1


def test_positions_background_multiple_z_stagger():
    e = LayoutTransformEngine()
    assets = _assets(["b1", "b2"])
    result = e.calculate_asset_positions(assets, "background", {})
    _, _, tz1 = result["b1"]
    _, _, tz2 = result["b2"]
    # Both at or behind background depth
    assert tz1 <= _ZONE_DEPTHS.get("background", -30.0) + 0.1
    assert tz2 <= _ZONE_DEPTHS.get("background", -30.0) + 0.1


# ---------------------------------------------------------------------------
# calculate_asset_rotations — extended
# ---------------------------------------------------------------------------

def test_rotations_empty_assets():
    e = LayoutTransformEngine()
    result = e.calculate_asset_rotations([], "hero_area")
    assert result == {}


def test_rotations_floor_category():
    e = LayoutTransformEngine()
    assets = _assets(["floor1"], ["floor"])
    result = e.calculate_asset_rotations(assets, "floor")
    # Floor assets should have some specific rotation
    assert "floor1" in result
    assert len(result["floor1"]) == 3


def test_rotations_rx_ry_rz_all_numeric():
    e = LayoutTransformEngine()
    assets = _assets(["x1", "x2"])
    result = e.calculate_asset_rotations(assets, "midground")
    for name, rot in result.items():
        rx, ry, rz = rot
        assert isinstance(rx, (int, float))
        assert isinstance(ry, (int, float))
        assert isinstance(rz, (int, float))


# ---------------------------------------------------------------------------
# generate_depth_layers — extended
# ---------------------------------------------------------------------------

def test_depth_layers_empty_zones_and_layers():
    e = LayoutTransformEngine()
    result = e.generate_depth_layers({}, [])
    assert "layer_order" in result
    assert result["layer_order"] == []


def test_depth_layers_midground_depth_between_hero_and_bg():
    e = LayoutTransformEngine()
    result = e.generate_depth_layers(
        {}, ["hero_area", "midground", "background"]
    )
    zd = result["zone_depths"]
    assert zd["hero_area"] > zd["midground"] > zd["background"]


# ---------------------------------------------------------------------------
# calculate_camera_focus_targets — extended
# ---------------------------------------------------------------------------

def test_camera_targets_no_hero_no_hero_focus():
    e = LayoutTransformEngine()
    targets = e.calculate_camera_focus_targets(
        {"background": [{"name": "wall"}]}, {}
    )
    shot_types = [t["shot_type"] for t in targets]
    assert "hero_focus" not in shot_types


def test_camera_targets_position_is_tuple_or_list():
    e = LayoutTransformEngine()
    targets = e.calculate_camera_focus_targets({}, {})
    for t in targets:
        assert len(t["position"]) == 3


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

def test_stats_shape():
    e = LayoutTransformEngine()
    s = e.stats()
    assert "calc_count" in s


def test_stats_starts_zero():
    e = LayoutTransformEngine()
    assert e.stats()["calc_count"] == 0
