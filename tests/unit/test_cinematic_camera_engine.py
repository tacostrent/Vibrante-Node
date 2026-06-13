"""
Tests for src.runtime.cinematic_camera_engine
No bridge, no LLM. Pure unit tests.
"""
import pytest
from src.runtime.cinematic_camera_engine import (
    CinematicCameraEngine,
    get_cinematic_camera_engine,
    reset_cinematic_camera_engine_for_tests,
    _CAMERA_MODES,
    _DEFAULT_MODE,
    _ZONE_CAMERA_POSITIONS,
)


@pytest.fixture(autouse=True)
def reset():
    reset_cinematic_camera_engine_for_tests()
    yield
    reset_cinematic_camera_engine_for_tests()


def _zones_full():
    return {
        "hero_area":  ["robot_1"],
        "midground":  ["crate_1"],
        "background": ["wall_1"],
    }


def _zones_no_hero():
    return {"hero_area": [], "midground": ["crate_1"], "background": ["wall_1"]}


def _zones_empty():
    return {"hero_area": [], "midground": [], "background": []}


def _layout_rules():
    return {"fog_density": "medium"}


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton():
    a = get_cinematic_camera_engine()
    b = get_cinematic_camera_engine()
    assert a is b


def test_reset_creates_new():
    a = get_cinematic_camera_engine()
    reset_cinematic_camera_engine_for_tests()
    b = get_cinematic_camera_engine()
    assert a is not b


# ---------------------------------------------------------------------------
# _CAMERA_MODES constant
# ---------------------------------------------------------------------------

def test_camera_modes_has_required_keys():
    required = {"cinematic_push_in", "orbital_reveal", "hero_focus",
                "atmospheric_tracking", "handheld_subtle"}
    assert required <= set(_CAMERA_MODES.keys())


def test_default_mode_exists():
    assert _DEFAULT_MODE in _CAMERA_MODES


def test_each_mode_has_fov():
    for name, mode in _CAMERA_MODES.items():
        assert "fov" in mode, f"Mode '{name}' missing fov"


def test_each_mode_has_motion_type():
    for name, mode in _CAMERA_MODES.items():
        assert "motion_type" in mode, f"Mode '{name}' missing motion_type"


def test_zone_camera_positions_exist():
    for zone in ("hero_area", "midground", "background"):
        assert zone in _ZONE_CAMERA_POSITIONS


# ---------------------------------------------------------------------------
# generate_camera_plan
# ---------------------------------------------------------------------------

def test_camera_plan_returns_dict():
    e = CinematicCameraEngine()
    result = e.generate_camera_plan(_zones_full(), _layout_rules(), "cinematic_push_in")
    assert isinstance(result, dict)


def test_camera_plan_has_required_keys():
    e = CinematicCameraEngine()
    result = e.generate_camera_plan(_zones_full(), _layout_rules(), "cinematic_push_in")
    for key in ("plan_id", "camera_mode", "targets", "motion", "focus_strategy",
                "operations", "readability", "generated_at"):
        assert key in result, f"Missing key: {key}"


def test_camera_plan_unknown_mode_falls_back():
    e = CinematicCameraEngine()
    result = e.generate_camera_plan(_zones_full(), _layout_rules(), "unknown_xyz")
    assert result["camera_mode"] == _DEFAULT_MODE


def test_camera_plan_none_mode_falls_back():
    e = CinematicCameraEngine()
    result = e.generate_camera_plan(_zones_full(), _layout_rules(), None)
    assert result["camera_mode"] == _DEFAULT_MODE


def test_camera_plan_plan_id_is_string():
    e = CinematicCameraEngine()
    result = e.generate_camera_plan(_zones_full(), _layout_rules(), "cinematic_push_in")
    assert isinstance(result["plan_id"], str)


def test_camera_plan_targets_is_list():
    e = CinematicCameraEngine()
    result = e.generate_camera_plan(_zones_full(), _layout_rules())
    assert isinstance(result["targets"], list)


def test_camera_plan_operations_is_list():
    e = CinematicCameraEngine()
    result = e.generate_camera_plan(_zones_full(), _layout_rules())
    assert isinstance(result["operations"], list)


def test_camera_plan_increments_plan_count():
    e = CinematicCameraEngine()
    e.generate_camera_plan(_zones_full(), _layout_rules())
    e.generate_camera_plan(_zones_no_hero(), _layout_rules())
    assert e.stats()["plan_count"] == 2


def test_camera_plan_all_modes():
    e = CinematicCameraEngine()
    for mode in _CAMERA_MODES:
        result = e.generate_camera_plan(_zones_full(), _layout_rules(), mode)
        assert result["camera_mode"] == mode


# ---------------------------------------------------------------------------
# calculate_camera_targets
# ---------------------------------------------------------------------------

def test_targets_always_has_establishing():
    e = CinematicCameraEngine()
    targets = e.calculate_camera_targets(_zones_full(), _layout_rules())
    shot_types = [t["shot_type"] for t in targets]
    assert "wide_establishing" in shot_types


def test_targets_has_hero_focus_when_hero_present():
    e = CinematicCameraEngine()
    targets = e.calculate_camera_targets(_zones_full(), _layout_rules())
    shot_types = [t["shot_type"] for t in targets]
    assert "hero_focus" in shot_types


def test_targets_no_hero_focus_when_no_hero():
    e = CinematicCameraEngine()
    targets = e.calculate_camera_targets(_zones_no_hero(), _layout_rules())
    shot_types = [t["shot_type"] for t in targets]
    assert "hero_focus" not in shot_types


def test_targets_establishing_only_when_empty():
    e = CinematicCameraEngine()
    targets = e.calculate_camera_targets(_zones_empty(), _layout_rules())
    assert len(targets) >= 1
    shot_types = [t["shot_type"] for t in targets]
    assert "wide_establishing" in shot_types


def test_targets_hero_focus_priority_1():
    e = CinematicCameraEngine()
    targets = e.calculate_camera_targets(_zones_full(), _layout_rules())
    hero_targets = [t for t in targets if t["shot_type"] == "hero_focus"]
    assert hero_targets[0]["priority"] == 1


def test_targets_establishing_priority_2_when_hero_present():
    e = CinematicCameraEngine()
    targets = e.calculate_camera_targets(_zones_full(), _layout_rules())
    est = [t for t in targets if t["shot_type"] == "wide_establishing"][0]
    assert est["priority"] == 2


def test_targets_establishing_priority_1_when_no_hero():
    e = CinematicCameraEngine()
    targets = e.calculate_camera_targets(_zones_no_hero(), _layout_rules())
    est = [t for t in targets if t["shot_type"] == "wide_establishing"][0]
    assert est["priority"] == 1


def test_targets_mid_shot_when_midground_populated():
    e = CinematicCameraEngine()
    targets = e.calculate_camera_targets(_zones_full(), _layout_rules())
    shot_types = [t["shot_type"] for t in targets]
    assert "mid_shot" in shot_types


def test_targets_each_has_position():
    e = CinematicCameraEngine()
    targets = e.calculate_camera_targets(_zones_full(), _layout_rules())
    for t in targets:
        assert "position" in t
        assert len(t["position"]) == 3


# ---------------------------------------------------------------------------
# generate_camera_motion
# ---------------------------------------------------------------------------

def test_camera_motion_returns_dict():
    e = CinematicCameraEngine()
    targets = e.calculate_camera_targets(_zones_full(), _layout_rules())
    result = e.generate_camera_motion("cinematic_push_in", targets)
    assert isinstance(result, dict)


def test_camera_motion_has_required_keys():
    e = CinematicCameraEngine()
    targets = e.calculate_camera_targets(_zones_full(), _layout_rules())
    result = e.generate_camera_motion("cinematic_push_in", targets)
    for key in ("mode", "motion_type", "motion_axis", "motion_start",
                "motion_end", "motion_frames", "shake_intensity",
                "description", "primary_target"):
        assert key in result, f"Missing key: {key}"


def test_camera_motion_mode_recorded():
    e = CinematicCameraEngine()
    targets = e.calculate_camera_targets(_zones_full(), _layout_rules())
    result = e.generate_camera_motion("orbital_reveal", targets)
    assert result["mode"] == "orbital_reveal"


def test_camera_motion_unknown_mode_falls_back():
    e = CinematicCameraEngine()
    targets = e.calculate_camera_targets(_zones_full(), _layout_rules())
    result = e.generate_camera_motion("unknown_xyz", targets)
    assert result["mode"] == _DEFAULT_MODE


def test_camera_motion_primary_target_is_lowest_priority():
    e = CinematicCameraEngine()
    targets = e.calculate_camera_targets(_zones_full(), _layout_rules())
    result = e.generate_camera_motion("cinematic_push_in", targets)
    primary = result["primary_target"]
    assert primary is not None
    assert primary["priority"] == 1  # hero_focus is priority 1


def test_camera_motion_no_targets_primary_none():
    e = CinematicCameraEngine()
    result = e.generate_camera_motion("cinematic_push_in", [])
    assert result["primary_target"] is None


def test_camera_motion_handheld_has_shake():
    e = CinematicCameraEngine()
    targets = e.calculate_camera_targets(_zones_full(), _layout_rules())
    result = e.generate_camera_motion("handheld_subtle", targets)
    assert result["shake_intensity"] > 0


# ---------------------------------------------------------------------------
# build_focus_strategy
# ---------------------------------------------------------------------------

def test_focus_strategy_returns_dict():
    e = CinematicCameraEngine()
    targets = e.calculate_camera_targets(_zones_full(), _layout_rules())
    result = e.build_focus_strategy(_zones_full(), targets)
    assert isinstance(result, dict)


def test_focus_strategy_has_required_keys():
    e = CinematicCameraEngine()
    targets = e.calculate_camera_targets(_zones_full(), _layout_rules())
    result = e.build_focus_strategy(_zones_full(), targets)
    for key in ("primary_subject", "focus_mode", "dof_aperture",
                "focus_distance", "rack_focus"):
        assert key in result, f"Missing key: {key}"


def test_focus_strategy_hero_locked():
    e = CinematicCameraEngine()
    targets = e.calculate_camera_targets(_zones_full(), _layout_rules())
    result = e.build_focus_strategy(_zones_full(), targets)
    assert result["focus_mode"] == "hero_locked"
    assert result["dof_aperture"] == pytest.approx(2.8)


def test_focus_strategy_soft_focus_no_hero():
    e = CinematicCameraEngine()
    targets = e.calculate_camera_targets(_zones_no_hero(), _layout_rules())
    result = e.build_focus_strategy(_zones_no_hero(), targets)
    assert result["focus_mode"] == "soft_focus"
    assert result["dof_aperture"] == pytest.approx(8.0)


def test_focus_strategy_rack_focus_multiple_z_depths():
    e = CinematicCameraEngine()
    targets = e.calculate_camera_targets(_zones_full(), _layout_rules())
    result = e.build_focus_strategy(_zones_full(), targets)
    # With hero (z=8), midground (z=20), background (z=40) — multiple z depths
    assert result["rack_focus"] is True


def test_focus_strategy_no_rack_focus_single_target():
    e = CinematicCameraEngine()
    targets = [{"name": "only", "zone": "hero_area",
                "position": (0.0, 1.5, 8.0), "shot_type": "hero_focus", "priority": 1}]
    result = e.build_focus_strategy(_zones_full(), targets)
    assert result["rack_focus"] is False


def test_focus_strategy_primary_subject_from_hero():
    e = CinematicCameraEngine()
    zones = {"hero_area": [{"name": "robot_1", "category": "robot"}]}
    targets = e.calculate_camera_targets(zones, _layout_rules())
    result = e.build_focus_strategy(zones, targets)
    assert result["primary_subject"] == "robot_1"


def test_focus_strategy_primary_subject_none_when_no_hero():
    e = CinematicCameraEngine()
    targets = e.calculate_camera_targets(_zones_no_hero(), _layout_rules())
    result = e.build_focus_strategy(_zones_no_hero(), targets)
    assert result["primary_subject"] is None


# ---------------------------------------------------------------------------
# evaluate_composition_readability
# ---------------------------------------------------------------------------

def test_readability_returns_dict():
    e = CinematicCameraEngine()
    plan = e.generate_camera_plan(_zones_full(), _layout_rules(), "cinematic_push_in")
    result = e.evaluate_composition_readability(plan)
    assert isinstance(result, dict)


def test_readability_has_required_keys():
    e = CinematicCameraEngine()
    plan = e.generate_camera_plan(_zones_full(), _layout_rules())
    result = e.evaluate_composition_readability(plan)
    for key in ("readable", "readability_score", "issues", "strengths"):
        assert key in result, f"Missing key: {key}"


def test_readability_with_establishing_shot_adds_strength():
    e = CinematicCameraEngine()
    plan = {"camera_mode": "cinematic_push_in",
            "targets": [{"shot_type": "wide_establishing", "priority": 2}],
            "motion": {"shake_intensity": 0.0, "motion_type": "translate"}}
    result = e.evaluate_composition_readability(plan)
    assert any("establishing" in s.lower() for s in result["strengths"])


def test_readability_no_targets_lowers_score():
    e = CinematicCameraEngine()
    plan = {"camera_mode": "cinematic_push_in", "targets": [],
            "motion": {"shake_intensity": 0.0, "motion_type": "static"}}
    result = e.evaluate_composition_readability(plan)
    assert result["readability_score"] < 1.0


def test_readability_high_shake_adds_issue():
    e = CinematicCameraEngine()
    plan = {"camera_mode": "handheld_subtle",
            "targets": [{"shot_type": "wide_establishing", "priority": 1}],
            "motion": {"shake_intensity": 0.9, "motion_type": "handheld"}}
    result = e.evaluate_composition_readability(plan)
    assert len(result["issues"]) > 0


def test_readability_push_in_adds_strength():
    e = CinematicCameraEngine()
    plan = {"camera_mode": "cinematic_push_in",
            "targets": [{"shot_type": "wide_establishing", "priority": 2}],
            "motion": {"shake_intensity": 0.0, "motion_type": "translate"}}
    result = e.evaluate_composition_readability(plan)
    assert any("push-in" in s.lower() or "cinematic" in s.lower() for s in result["strengths"])


def test_readability_score_range():
    e = CinematicCameraEngine()
    plan = e.generate_camera_plan(_zones_full(), _layout_rules())
    result = e.evaluate_composition_readability(plan)
    assert 0.0 <= result["readability_score"] <= 1.0


def test_readability_issues_is_list():
    e = CinematicCameraEngine()
    plan = e.generate_camera_plan(_zones_full(), _layout_rules())
    result = e.evaluate_composition_readability(plan)
    assert isinstance(result["issues"], list)


def test_readability_strengths_is_list():
    e = CinematicCameraEngine()
    plan = e.generate_camera_plan(_zones_full(), _layout_rules())
    result = e.evaluate_composition_readability(plan)
    assert isinstance(result["strengths"], list)


# ---------------------------------------------------------------------------
# Operations structure
# ---------------------------------------------------------------------------

def test_operations_contain_create_node():
    e = CinematicCameraEngine()
    result = e.generate_camera_plan(_zones_full(), _layout_rules())
    ops = result["operations"]
    create_ops = [o for o in ops if o.get("op") == "create_node"]
    assert len(create_ops) >= 1


def test_operations_contain_layout_children():
    e = CinematicCameraEngine()
    result = e.generate_camera_plan(_zones_full(), _layout_rules())
    ops = result["operations"]
    layout_ops = [o for o in ops if o.get("op") == "layout_children"]
    assert len(layout_ops) >= 1


def test_operations_camera_parent_is_camera():
    e = CinematicCameraEngine()
    result = e.generate_camera_plan(_zones_full(), _layout_rules())
    ops = result["operations"]
    create_ops = [o for o in ops if o.get("op") == "create_node"]
    for op in create_ops:
        assert op.get("parent") == "/obj/camera"


def test_operations_camera_type_is_cam():
    e = CinematicCameraEngine()
    result = e.generate_camera_plan(_zones_full(), _layout_rules())
    ops = result["operations"]
    create_ops = [o for o in ops if o.get("op") == "create_node"]
    for op in create_ops:
        assert op.get("type") == "cam"


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

def test_stats_has_plan_count():
    e = CinematicCameraEngine()
    assert "plan_count" in e.stats()


def test_stats_starts_zero():
    e = CinematicCameraEngine()
    assert e.stats()["plan_count"] == 0


def test_stats_increments():
    e = CinematicCameraEngine()
    e.generate_camera_plan(_zones_full(), _layout_rules())
    assert e.stats()["plan_count"] == 1
