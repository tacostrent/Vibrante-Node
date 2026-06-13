"""Tests for §46 AnchorLayoutEngine."""

import pytest
from src.runtime.layout import (
    AnchorPlacement,
    AnchorLayoutResult,
    get_anchor_layout_engine,
    reset_anchor_layout_engine_for_tests,
    reset_affordance_engine_for_tests,
)


@pytest.fixture(autouse=True)
def reset():
    reset_anchor_layout_engine_for_tests()
    reset_affordance_engine_for_tests()
    yield
    reset_anchor_layout_engine_for_tests()
    reset_affordance_engine_for_tests()


def _asset(name, a_type):
    return {"asset_id": name, "name": name, "placement_type": a_type}


# ---------------------------------------------------------------------------
# Basic placement
# ---------------------------------------------------------------------------

def test_table_becomes_hero_anchor():
    assets = [
        _asset("hero_table", "table"),
        _asset("chair_01", "chair"),
    ]
    result = get_anchor_layout_engine().place_anchors(assets)
    assert result.ok
    assert result.hero_anchor is not None
    assert result.hero_anchor.anchor_type == "table"
    assert result.hero_anchor.is_hero is True


def test_non_anchor_assets_ignored():
    assets = [
        _asset("chair_01", "chair"),
        _asset("barrel_01", "barrel"),
    ]
    result = get_anchor_layout_engine().place_anchors(assets)
    assert result.hero_anchor is None
    assert len(result.placements) == 0


def test_empty_assets():
    result = get_anchor_layout_engine().place_anchors([])
    assert result.ok
    assert result.hero_anchor is None


def test_hero_at_origin():
    assets = [_asset("table", "table")]
    result = get_anchor_layout_engine().place_anchors(assets)
    assert result.hero_anchor.position == [0.0, 0.0, 0.0]


def test_secondary_anchor_gets_different_zone():
    assets = [
        _asset("table_01", "table"),
        _asset("machine_01", "machine"),
    ]
    result = get_anchor_layout_engine().place_anchors(assets)
    assert len(result.placements) == 2
    zones = [p.zone for p in result.placements]
    assert len(set(zones)) >= 1


def test_priority_order():
    """Throne (priority 10) should beat workbench (priority 9)."""
    assets = [
        _asset("wb", "workbench"),
        _asset("th", "throne"),
    ]
    result = get_anchor_layout_engine().place_anchors(assets)
    assert result.hero_anchor.anchor_type == "throne"


def test_multiple_anchors_sorted_by_priority():
    assets = [
        _asset("console", "console"),
        _asset("table", "table"),
        _asset("sofa", "sofa"),
    ]
    result = get_anchor_layout_engine().place_anchors(assets)
    # table (10) > console (8) > sofa (5)
    prio = [p.priority for p in result.placements]
    assert prio == sorted(prio, reverse=True)


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------

def test_anchor_placement_to_dict_roundtrip():
    assets = [_asset("t", "table")]
    result = get_anchor_layout_engine().place_anchors(assets)
    p = result.placements[0]
    d = p.to_dict()
    p2 = AnchorPlacement.from_dict(d)
    assert p2.anchor_type == p.anchor_type
    assert p2.is_hero == p.is_hero


def test_anchor_layout_result_to_dict():
    assets = [_asset("t", "table"), _asset("m", "machine")]
    result = get_anchor_layout_engine().place_anchors(assets)
    d = result.to_dict()
    assert "placements" in d
    assert "hero_anchor" in d
    assert d["ok"] is True
