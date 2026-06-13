"""Tests for §46 AffordanceEngine."""

import pytest
from src.runtime.layout import (
    AffordanceProfile,
    get_affordance_engine,
    reset_affordance_engine_for_tests,
    ANCHOR_TYPES,
    PLACEMENT_MODES,
)


@pytest.fixture(autouse=True)
def reset():
    reset_affordance_engine_for_tests()
    yield
    reset_affordance_engine_for_tests()


# ---------------------------------------------------------------------------
# Surface affordances
# ---------------------------------------------------------------------------

def test_table_provides_surface():
    eng = get_affordance_engine()
    p = eng.get_affordances("table")
    assert p.provides_surface is True
    assert "bottle" in p.surface_children
    assert "cup" in p.surface_children


def test_shelf_provides_surface():
    eng = get_affordance_engine()
    p = eng.get_affordances("shelf")
    assert p.provides_surface is True
    assert "book" in p.surface_children


def test_chair_has_no_surface():
    eng = get_affordance_engine()
    p = eng.get_affordances("chair")
    assert p.provides_surface is False


# ---------------------------------------------------------------------------
# Around affordances
# ---------------------------------------------------------------------------

def test_table_attracts_chairs():
    eng = get_affordance_engine()
    p = eng.get_affordances("table")
    assert p.provides_around is True
    assert "chair" in p.around_children


def test_bar_counter_attracts_stools():
    eng = get_affordance_engine()
    p = eng.get_affordances("bar_counter")
    assert "stool" in p.around_children


def test_barrel_no_around():
    eng = get_affordance_engine()
    p = eng.get_affordances("barrel")
    assert p.provides_around is False


# ---------------------------------------------------------------------------
# Anchor detection
# ---------------------------------------------------------------------------

def test_anchor_types():
    eng = get_affordance_engine()
    for t in ("table", "workbench", "machine", "fireplace", "console"):
        assert eng.get_affordances(t).is_anchor is True, f"{t} should be anchor"


def test_non_anchor_types():
    eng = get_affordance_engine()
    for t in ("chair", "bottle", "barrel", "poster"):
        assert eng.get_affordances(t).is_anchor is False, f"{t} should not be anchor"


# ---------------------------------------------------------------------------
# Wall / ceiling flags
# ---------------------------------------------------------------------------

def test_poster_is_wall_attachable():
    eng = get_affordance_engine()
    assert eng.get_affordances("poster").is_wall_attachable is True


def test_wanted_poster_is_wall_attachable():
    eng = get_affordance_engine()
    assert eng.get_affordances("wanted_poster").is_wall_attachable is True


def test_lantern_is_ceiling_hangable():
    eng = get_affordance_engine()
    assert eng.get_affordances("lantern").is_ceiling_hangable is True


def test_chair_not_wall_attachable():
    eng = get_affordance_engine()
    assert eng.get_affordances("chair").is_wall_attachable is False


# ---------------------------------------------------------------------------
# Placement modes
# ---------------------------------------------------------------------------

def test_chair_around_anchor():
    eng = get_affordance_engine()
    assert eng.get_placement_mode("chair") == "around_anchor"


def test_bottle_on_surface():
    eng = get_affordance_engine()
    assert eng.get_placement_mode("bottle") == "on_surface"


def test_poster_wall_only():
    eng = get_affordance_engine()
    assert eng.get_placement_mode("poster") == "wall_only"


def test_table_hero_center():
    eng = get_affordance_engine()
    assert eng.get_placement_mode("table") == "hero_center"


def test_barrel_corner():
    eng = get_affordance_engine()
    assert eng.get_placement_mode("barrel") == "corner"


def test_bench_against_wall():
    eng = get_affordance_engine()
    assert eng.get_placement_mode("bench") == "against_wall"


# ---------------------------------------------------------------------------
# can_support / can_surround
# ---------------------------------------------------------------------------

def test_table_can_support_bottle():
    eng = get_affordance_engine()
    assert eng.can_support("table", "bottle") is True


def test_table_cannot_support_machine():
    eng = get_affordance_engine()
    assert eng.can_support("table", "machine") is False


def test_table_can_surround_chair():
    eng = get_affordance_engine()
    assert eng.can_surround("table", "chair") is True


def test_shelf_cannot_surround_chair():
    eng = get_affordance_engine()
    assert eng.can_surround("shelf", "chair") is False


# ---------------------------------------------------------------------------
# infer_type
# ---------------------------------------------------------------------------

def test_infer_type_from_placement_type():
    eng = get_affordance_engine()
    assert eng.infer_type({"placement_type": "table"}) == "table"


def test_infer_type_from_name():
    eng = get_affordance_engine()
    t = eng.infer_type({"name": "Old Wooden Chair"})
    assert t == "chair"


def test_infer_type_fallback_prop():
    eng = get_affordance_engine()
    assert eng.infer_type({}) == "prop"


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def test_profile_to_dict_from_dict_roundtrip():
    eng = get_affordance_engine()
    p = eng.get_affordances("table")
    d = p.to_dict()
    p2 = AffordanceProfile.from_dict(d)
    assert p2.asset_type == "table"
    assert p2.is_anchor is True
    assert p2.provides_surface is True
    assert "chair" in p2.around_children
