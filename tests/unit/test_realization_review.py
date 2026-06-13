"""Tests for RealizationReview — §47 Layout Realization."""
import pytest
from src.runtime.layout_realization import (
    get_realization_review,
    reset_realization_review_for_tests,
)


@pytest.fixture(autouse=True)
def reset():
    reset_realization_review_for_tests()
    yield
    reset_realization_review_for_tests()


def _transform(asset_id, tx, ty, tz, relationship="scattered", is_collision_free=True):
    return {
        "asset_id": asset_id, "asset_name": asset_id,
        "tx": tx, "ty": ty, "tz": tz,
        "rx": 0.0, "ry": 0.0, "rz": 0.0,
        "sx": 1.0, "sy": 1.0, "sz": 1.0,
        "parent_id": "", "relationship": relationship, "cluster_id": "",
        "is_collision_free": is_collision_free, "constraint_ok": True, "notes": "",
    }


def _good_scene():
    return {
        "environment": "western_room",
        "collision_count": 0,
        "transforms": [
            _transform("poker_table",     0.0,  0.0,  0.0, "anchor"),
            _transform("chair_s",         0.0,  0.0,  0.9, "around"),
            _transform("chair_n",         0.0,  0.0, -0.9, "around"),
            _transform("whiskey_bottle",  0.1,  0.75, 0.0, "supports"),
            _transform("wanted_poster",   0.0,  1.6, -3.95, "attached_to"),
            _transform("wall_lantern",    3.95, 2.4,  0.0,  "attached_to"),
            _transform("barrel_01",      -2.5,  0.0,  2.5, "corner"),
        ],
    }


# ---- grade A scene ---------------------------------------------------------

def test_good_scene_grade_A():
    result = get_realization_review().review(_good_scene())
    assert result.overall_score >= 0.75
    assert result.grade in ("A", "B")


def test_good_scene_production_ready():
    result = get_realization_review().review(_good_scene())
    assert result.production_ready


def test_no_blocking_for_good_scene():
    result = get_realization_review().review(_good_scene())
    assert result.blocking == []


# ---- collision failure -----------------------------------------------------

def test_collision_degrades_score():
    scene = _good_scene()
    scene["collision_count"] = 3
    result = get_realization_review().review(scene)
    assert result.collision_quality < 0.5


# ---- bottle on floor blocking ----------------------------------------------

def test_bottle_on_floor_is_blocking():
    scene = _good_scene()
    # Move bottle to floor (ty=0)
    for t in scene["transforms"]:
        if t["asset_id"] == "whiskey_bottle":
            t["ty"] = 0.0
            t["relationship"] = "supports"
    result = get_realization_review().review(scene)
    assert "bottle on floor when table exists" in result.blocking
    assert not result.production_ready


# ---- poster outside wall blocking ------------------------------------------

def test_poster_outside_wall_is_blocking():
    scene = _good_scene()
    # Move ALL wall-attached items to room center (not near any wall)
    for t in scene["transforms"]:
        if t["relationship"] == "attached_to":
            t["tx"] = 0.0
            t["tz"] = 0.0
    result = get_realization_review().review(scene)
    assert "poster outside wall" in result.blocking


# ---- chair inside table blocking -------------------------------------------

def test_chair_inside_table_is_blocking():
    scene = _good_scene()
    scene["collision_count"] = 1
    # Place chair exactly at table position
    for t in scene["transforms"]:
        if "chair" in t["asset_id"]:
            t["tx"] = 0.0
            t["tz"] = 0.0
    result = get_realization_review().review(scene)
    assert "chair inside table" in result.blocking


# ---- empty scene -----------------------------------------------------------

def test_empty_transforms_blocking():
    result = get_realization_review().review({"transforms": [], "collision_count": 0})
    assert not result.production_ready
    assert result.blocking != []


# ---- score dimensions present ----------------------------------------------

def test_all_score_dimensions_present():
    result = get_realization_review().review(_good_scene())
    d = result.to_dict()
    for key in ("transform_accuracy", "relationship_accuracy", "collision_quality",
                "surface_quality", "wall_attachment_quality", "visibility_quality"):
        assert key in d
        assert isinstance(d[key], float)
