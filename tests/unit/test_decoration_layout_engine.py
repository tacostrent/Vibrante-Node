"""Tests for §46 DecorationLayoutEngine."""

import pytest
from src.runtime.layout import (
    DecorativeItem,
    DecorationLayoutResult,
    get_decoration_layout_engine,
    reset_decoration_layout_engine_for_tests,
)


@pytest.fixture(autouse=True)
def reset():
    reset_decoration_layout_engine_for_tests()
    yield
    reset_decoration_layout_engine_for_tests()


def _asset(name, a_type):
    return {"asset_id": name, "name": name, "placement_type": a_type}


# ---------------------------------------------------------------------------
# Placement targets
# ---------------------------------------------------------------------------

def test_barrel_goes_to_corner():
    eng = get_decoration_layout_engine()
    result = eng.place_decorations([_asset("barrel_01", "barrel")], "western_room")
    assert result.items[0].placement_target == "corner"


def test_lantern_goes_to_wall():
    eng = get_decoration_layout_engine()
    result = eng.place_decorations([_asset("lantern_01", "lantern")], "western_room")
    assert result.items[0].placement_target == "wall_mounted"


def test_poster_goes_to_wall_only():
    eng = get_decoration_layout_engine()
    result = eng.place_decorations([_asset("poster_01", "poster")], "western_room")
    assert result.items[0].placement_target == "wall_only"


def test_bottle_goes_on_surface():
    eng = get_decoration_layout_engine()
    result = eng.place_decorations([_asset("bottle_01", "bottle")], "western_room")
    assert result.items[0].placement_target == "on_surface"


# ---------------------------------------------------------------------------
# Environment preference matching
# ---------------------------------------------------------------------------

def test_western_room_preferred_types():
    eng = get_decoration_layout_engine()
    pref = eng.get_preferred_types("western_room")
    assert "barrel" in pref
    assert "lantern" in pref
    assert "wanted_poster" in pref


def test_castle_hall_preferred_types():
    eng = get_decoration_layout_engine()
    pref = eng.get_preferred_types("castle_hall")
    assert "banner" in pref
    assert "torch" in pref


def test_contextual_flag_set_for_preferred_assets():
    eng = get_decoration_layout_engine()
    # barrel is preferred in western_room
    result = eng.place_decorations([_asset("barrel_01", "barrel")], "western_room")
    assert result.items[0].contextual is True


def test_non_contextual_asset_marked_false():
    eng = get_decoration_layout_engine()
    # "rock" not in western_room preferences
    result = eng.place_decorations([_asset("rock_01", "rock")], "western_room")
    assert result.items[0].contextual is False


def test_unknown_environment_falls_back_to_defaults():
    eng = get_decoration_layout_engine()
    pref = eng.get_preferred_types("unknown_place_xyz")
    assert len(pref) > 0


# ---------------------------------------------------------------------------
# Multiple items
# ---------------------------------------------------------------------------

def test_multiple_items_distinct_positions():
    eng = get_decoration_layout_engine()
    assets = [_asset(f"barrel_{i}", "barrel") for i in range(4)]
    result = eng.place_decorations(assets, "western_room")
    positions = [tuple(round(v, 2) for v in item.position) for item in result.items]
    assert len(set(positions)) == 4   # all corners distinct


def test_empty_assets_returns_empty():
    eng = get_decoration_layout_engine()
    result = eng.place_decorations([], "western_room")
    assert result.ok
    assert result.items == []


# ---------------------------------------------------------------------------
# Result fields
# ---------------------------------------------------------------------------

def test_result_has_environment():
    eng = get_decoration_layout_engine()
    result = eng.place_decorations([_asset("b", "barrel")], "castle_hall")
    assert result.environment == "castle_hall"


def test_result_has_preferred_types():
    eng = get_decoration_layout_engine()
    result = eng.place_decorations([], "western_room")
    assert len(result.preferred_types) > 0


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def test_decorative_item_to_dict_roundtrip():
    eng = get_decoration_layout_engine()
    result = eng.place_decorations([_asset("barrel_01", "barrel")], "western_room")
    item = result.items[0]
    d = item.to_dict()
    item2 = DecorativeItem.from_dict(d)
    assert item2.asset_id == item.asset_id
    assert item2.placement_target == item.placement_target
    assert item2.contextual == item.contextual


def test_decoration_layout_result_to_dict():
    eng = get_decoration_layout_engine()
    result = eng.place_decorations([_asset("b", "barrel")], "western_room")
    d = result.to_dict()
    assert "items" in d
    assert "preferred_types" in d
    assert d["ok"] is True
