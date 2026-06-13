"""Tests for PlacementTemplates (Tier 9 — §29)."""
import pytest
from src.runtime.assets.assembly.placement_templates import (
    PlacementTemplates,
    get_placement_templates,
    reset_placement_templates_for_tests,
    _BUILTIN_NAMES,
    _REQUIRED_FIELDS,
)


@pytest.fixture(autouse=True)
def reset():
    reset_placement_templates_for_tests()
    yield
    reset_placement_templates_for_tests()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton_returns_same_instance():
    a = get_placement_templates()
    b = get_placement_templates()
    assert a is b


def test_reset_returns_new_instance():
    a = get_placement_templates()
    reset_placement_templates_for_tests()
    b = get_placement_templates()
    assert a is not b


# ---------------------------------------------------------------------------
# Built-ins
# ---------------------------------------------------------------------------

def test_five_builtin_templates():
    pt = get_placement_templates()
    names = pt.list_templates()
    for env in ("industrial_hangar", "robotics_lab", "control_room", "sci_fi_corridor", "abandoned_factory"):
        assert env in names


def test_builtin_templates_have_required_fields():
    pt = get_placement_templates()
    for name in _BUILTIN_NAMES:
        tmpl = pt.get_template(name)
        assert tmpl is not None
        for f in _REQUIRED_FIELDS:
            assert f in tmpl, f"{name!r} missing required field {f!r}"


def test_is_builtin():
    pt = get_placement_templates()
    assert pt.is_builtin("industrial_hangar")
    assert not pt.is_builtin("custom_env")


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def test_get_template_returns_copy():
    pt = get_placement_templates()
    tmpl = pt.get_template("industrial_hangar")
    assert tmpl is not None
    tmpl["zone_depths"]["mutated"] = 99.0
    fresh = pt.get_template("industrial_hangar")
    assert "mutated" not in fresh["zone_depths"]


def test_get_template_or_default_returns_default_for_unknown():
    pt = get_placement_templates()
    tmpl = pt.get_template_or_default("does_not_exist")
    assert "hero_zone" in tmpl


def test_get_template_returns_none_for_unknown():
    pt = get_placement_templates()
    assert pt.get_template("no_such_env") is None


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def test_register_custom_template():
    pt = get_placement_templates()
    custom = {
        "hero_zone":  {"max_assets": 2, "slots": {}},
        "midground":  {"max_assets": 3, "slots": []},
        "background": {"max_assets": 3, "slots": []},
        "zone_depths": {"hero_zone": 0.0},
        "zone_widths": {"hero_zone": 10.0},
    }
    pt.register_template("my_env", custom)
    assert "my_env" in pt.list_templates()
    assert not pt.is_builtin("my_env")


def test_register_template_missing_field_raises():
    pt = get_placement_templates()
    with pytest.raises(ValueError, match="missing required fields"):
        pt.register_template("bad_env", {"hero_zone": {}})


def test_deregister_custom_template():
    pt = get_placement_templates()
    custom = {f: {} for f in _REQUIRED_FIELDS}
    pt.register_template("temp_env", custom)
    assert pt.deregister_template("temp_env")
    assert "temp_env" not in pt.list_templates()


def test_deregister_builtin_raises():
    pt = get_placement_templates()
    with pytest.raises(ValueError, match="Cannot deregister built-in"):
        pt.deregister_template("industrial_hangar")


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def test_validate_template_valid():
    pt = get_placement_templates()
    tmpl = pt.get_template("industrial_hangar")
    result = pt.validate_template(tmpl)
    assert result["valid"]
    assert not result["errors"]


def test_validate_template_missing_required_field():
    pt = get_placement_templates()
    result = pt.validate_template({"hero_zone": {}})
    assert not result["valid"]
    assert result["errors"]


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def test_stats():
    pt = get_placement_templates()
    s = pt.stats()
    assert s["builtin_count"] == 5
    assert s["custom_count"] == 0
    assert s["total"] == 5
    assert len(s["template_names"]) == 5


# ---------------------------------------------------------------------------
# Industrial hangar template structure
# ---------------------------------------------------------------------------

def test_industrial_hangar_hero_zone_slots_by_count():
    pt  = get_placement_templates()
    tmpl = pt.get_template("industrial_hangar")
    hero = tmpl["hero_zone"]
    slots = hero["slots"]
    assert isinstance(slots, dict)
    assert 1 in slots
    assert 3 in slots
    assert len(slots[1]) == 1
    assert len(slots[3]) == 3


def test_industrial_hangar_wall_runs():
    pt   = get_placement_templates()
    tmpl = pt.get_template("industrial_hangar")
    assert "wall_run_left" in tmpl
    assert "wall_run_right" in tmpl
    left = tmpl["wall_run_left"]
    assert len(left) == 5
    # All x should be negative
    assert all(s[0] < 0 for s in left)
