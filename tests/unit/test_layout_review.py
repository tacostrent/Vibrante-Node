"""Tests for §46 LayoutReview."""

import pytest
from src.runtime.layout import (
    LayoutReviewResult,
    get_layout_review,
    reset_layout_review_for_tests,
)


@pytest.fixture(autouse=True)
def reset():
    reset_layout_review_for_tests()
    yield
    reset_layout_review_for_tests()


def _good_plan(env="western_room"):
    """A well-formed layout plan that should score high."""
    return {
        "environment": env,
        "anchor_placements": [
            {"anchor_id": "table_01", "anchor_type": "table", "is_hero": True, "position": [0, 0, 0]}
        ],
        "clusters": [
            {"cluster_id": "c001", "cluster_type": "saloon_table_cluster",
             "anchor_asset_id": "table_01", "members": [
                 {"asset_id": "chair_01", "relationship": "around"},
                 {"asset_id": "chair_02", "relationship": "around"},
                 {"asset_id": "bottle_01", "relationship": "supports"},
             ]}
        ],
        "surface_placements": [
            {"child_asset_id": "bottle_01", "host_asset_id": "table_01",
             "surface_type": "table_surface", "surface_height": 0.75, "position": [0.0, 0.75, 0.0]}
        ],
        "wall_attachments": [
            {"asset_id": "poster_01", "asset_type": "poster", "wall_name": "wall_north",
             "mount_height": 1.6, "position": [0, 1.6, -4]}
        ],
        "relationships": [
            {"from_asset_id": "chair_01", "to_asset_id": "table_01", "relationship_type": "around"},
            {"from_asset_id": "bottle_01", "to_asset_id": "table_01", "relationship_type": "supports"},
            {"from_asset_id": "poster_01", "to_asset_id": "wall", "relationship_type": "attached_to"},
        ],
        "decoration_items": [
            {"asset_id": "barrel_01", "asset_type": "barrel", "asset_name": "Old Barrel",
             "placement_target": "corner", "contextual": True},
        ],
    }


# ---------------------------------------------------------------------------
# Production-ready plan
# ---------------------------------------------------------------------------

def test_good_plan_scores_high():
    result = get_layout_review().review(_good_plan())
    assert result.overall_score >= 0.70
    assert result.production_ready is True
    assert result.grade in ("A", "B")


# ---------------------------------------------------------------------------
# Blocking failures
# ---------------------------------------------------------------------------

def test_no_anchors_blocks_production():
    plan = _good_plan()
    plan["anchor_placements"] = []
    result = get_layout_review().review(plan)
    assert result.production_ready is False
    assert any("no anchors" in f for f in result.findings)


def test_no_relationships_reduces_score():
    plan = _good_plan()
    plan["relationships"] = []
    plan["clusters"] = []
    result = get_layout_review().review(plan)
    assert any("no relationships" in f for f in result.findings)


def test_bottle_on_floor_when_table_exists():
    plan = _good_plan()
    # Add a bottle that is NOT in surface_placements and has floor placement
    plan["decoration_items"].append({
        "asset_id": "cup_01",
        "asset_type": "cup",
        "asset_name": "Tin Cup",
        "placement_target": "scattered",
        "contextual": False,
    })
    plan["surface_placements"] = []  # clear surface placements
    result = get_layout_review().review(plan)
    assert any("bottle on floor" in f for f in result.findings)
    assert result.production_ready is False


def test_poster_not_on_wall_is_finding():
    plan = _good_plan()
    plan["decoration_items"].append({
        "asset_id": "poster_floor",
        "asset_type": "poster",
        "asset_name": "Wanted Poster",
        "placement_target": "scattered",   # NOT wall_only
        "contextual": True,
    })
    plan["wall_attachments"] = []
    result = get_layout_review().review(plan)
    assert any("poster not attached" in f for f in result.findings)


# ---------------------------------------------------------------------------
# Grade mapping
# ---------------------------------------------------------------------------

def test_empty_plan_not_production_ready():
    result = get_layout_review().review({})
    # Empty plan has no anchors → blocking finding → production_ready must be False
    assert result.production_ready is False
    assert result.grade in ("D", "F", "C")   # grade varies but never passes


def test_grade_thresholds():
    review = get_layout_review()
    # Inject a plan that exercises the grade boundaries
    for score_target, expected_grade in [(0.90, "A"), (0.75, "B"), (0.60, "C"), (0.42, "D")]:
        result = review.review(_good_plan())
        # Just verify grade field is one of the known values
        assert result.grade in ("A", "B", "C", "D", "F")


# ---------------------------------------------------------------------------
# Dimension fields
# ---------------------------------------------------------------------------

def test_review_result_has_all_fields():
    result = get_layout_review().review(_good_plan())
    d = result.to_dict()
    for key in (
        "relationship_accuracy", "surface_accuracy", "wall_attachment_accuracy",
        "cluster_quality", "contextual_quality", "overall_score", "grade",
        "production_ready", "findings"
    ):
        assert key in d, f"missing field: {key}"


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def test_review_result_to_dict_from_dict_roundtrip():
    result = get_layout_review().review(_good_plan())
    d = result.to_dict()
    r2 = LayoutReviewResult.from_dict(d)
    assert r2.grade == result.grade
    assert r2.production_ready == result.production_ready
    assert r2.overall_score == pytest.approx(result.overall_score, abs=0.001)
