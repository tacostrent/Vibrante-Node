"""Tests for EnvironmentArchitectureReview (Tier 10.5)."""

import pytest
from src.runtime.architectural_features import (
    ArchitecturalPlan,
    ArchitecturalOpening,
    FireplacePlacement,
    BeamPlacement,
    WallShelfPlacement,
    WALL_THICKNESS,
    ARCHITECTURE_STATUS_PASS,
    ARCHITECTURE_STATUS_FAIL,
    ArchitectureReviewResult,
    EnvironmentArchitectureReview,
    get_environment_architecture_review,
    reset_environment_architecture_review_for_tests,
    get_architectural_plan_builder,
    reset_architectural_plan_builder_for_tests,
)


@pytest.fixture(autouse=True)
def reset():
    reset_environment_architecture_review_for_tests()
    reset_architectural_plan_builder_for_tests()
    yield
    reset_environment_architecture_review_for_tests()
    reset_architectural_plan_builder_for_tests()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _full_shell():
    return {
        "environment":    "western_room",
        "ceiling_height": 4.0,
        "room_width":     10.0,
        "room_length":    12.0,
        "is_outdoor":     False,
        "ceiling_type":   "beam_ceiling",
        "anchors": [
            {"anchor_id": "door_anchor_0",   "anchor_type": "door_anchor",
             "wall_face": "south", "tx": 0.0, "ty": 1.8, "tz": 6.0,
             "door_width": 0.9, "door_height": 2.1},
            {"anchor_id": "window_anchor_0", "anchor_type": "window_anchor",
             "wall_face": "east",  "tx": 5.0, "ty": 2.2, "tz": 0.0,
             "window_width": 1.0, "window_height": 1.2},
            {"anchor_id": "beam_anchor_0",   "anchor_type": "beam_anchor",
             "tx": -2.5, "ty": 3.9, "tz": 0.0, "beam_span": 12.0},
            {"anchor_id": "fireplace_anchor_0", "anchor_type": "fireplace_anchor",
             "wall_face": "north", "tx": 0.0, "ty": 0.0, "tz": -5.7,
             "fireplace_width": 1.2, "fireplace_height": 1.5},
        ],
    }


def _good_plan() -> ArchitecturalPlan:
    shell = _full_shell()
    return get_architectural_plan_builder().build(shell)


def _door_opening(anchor_id="door_anchor_0"):
    return ArchitecturalOpening(
        opening_id="door_opening_0", opening_type="door",
        anchor_id=anchor_id, wall_face="south",
        wall_normal=[0.0, 0.0, 1.0],
        cx=0.0, cy=1.05, cz=6.0,
        width=0.9, height=2.1, depth=WALL_THICKNESS + 0.2,
        houdini_node_name="sh_door_opening_0",
    )


def _window_opening(anchor_id="window_anchor_0"):
    return ArchitecturalOpening(
        opening_id="window_opening_0", opening_type="window",
        anchor_id=anchor_id, wall_face="east",
        wall_normal=[1.0, 0.0, 0.0],
        cx=5.0, cy=2.2, cz=0.0,
        width=1.0, height=1.2, depth=WALL_THICKNESS + 0.2,
        houdini_node_name="sh_window_opening_0",
    )


def _good_fireplace():
    # North wall at z=-6.0; fireplace tz=-5.7, depth=0.6
    # back_face_coord = -5.7 - 0.3 = -6.0  →  distance = 0.0
    return FireplacePlacement(
        feature_id="fireplace_0", anchor_id="fireplace_anchor_0",
        wall_face="north", wall_normal=[0.0, 0.0, -1.0],
        forward_axis=[0.0, 0.0, 1.0],
        tx=0.0, ty=0.0, tz=-5.7,
        width=1.2, height=1.5, depth=0.6,
        wall_coord=-6.0, back_face_coord=-6.0,
        back_face_distance=0.0,
        center_offset=0.0,
        houdini_node_name="sh_fireplace_0",
    )


def _good_beam():
    return BeamPlacement(
        feature_id="beam_0", anchor_id="beam_anchor_0",
        tx=0.0, ty=3.675, tz=0.0,
        long_axis="z", length=12.0, width=0.20, height=0.30,
        ceiling_height=4.0, beam_top_y=3.825,
        gap_to_ceiling=0.02,
        intersects_wall=False, is_below_ceiling=True,
        houdini_node_name="sh_beam_0",
    )


def _good_shelf():
    return WallShelfPlacement(
        feature_id="shelf_0", anchor_id="wa_0",
        wall_face="west", tx=-4.87, ty=1.20, tz=0.0,
        width=1.0, depth=0.30, thickness=0.05,
        wall_coord=-5.0, is_floating=False,
        houdini_node_name="sh_shelf_0",
    )


# ── Singleton ──────────────────────────────────────────────────────────────────

class TestSingleton:
    def test_same_instance(self):
        a = get_environment_architecture_review()
        b = get_environment_architecture_review()
        assert a is b

    def test_reset_creates_new_instance(self):
        a = get_environment_architecture_review()
        reset_environment_architecture_review_for_tests()
        b = get_environment_architecture_review()
        assert a is not b


# ── Full PASS — western_room canonical ────────────────────────────────────────

class TestCanonicalPass:
    def test_western_room_passes(self):
        plan = _good_plan()
        shell = _full_shell()
        result = get_environment_architecture_review().review(plan, shell)
        assert result.status == ARCHITECTURE_STATUS_PASS

    def test_western_room_production_ready(self):
        plan = _good_plan()
        shell = _full_shell()
        result = get_environment_architecture_review().review(plan, shell)
        assert result.production_ready is True

    def test_western_room_score_gte_0_80(self):
        plan = _good_plan()
        shell = _full_shell()
        result = get_environment_architecture_review().review(plan, shell)
        assert result.architecture_score >= 0.80

    def test_all_feature_flags_true_on_good_plan(self):
        plan = _good_plan()
        shell = _full_shell()
        result = get_environment_architecture_review().review(plan, shell)
        assert result.door_openings_valid   is True
        assert result.window_openings_valid is True
        assert result.fireplace_valid       is True
        assert result.beams_valid           is True
        assert result.shelves_valid         is True

    def test_no_missing_openings_on_good_plan(self):
        plan = _good_plan()
        shell = _full_shell()
        result = get_environment_architecture_review().review(plan, shell)
        assert result.missing_door_openings   == []
        assert result.missing_window_openings == []


# ── Missing door opening — hard block ─────────────────────────────────────────

class TestMissingDoorOpening:
    def test_missing_door_fails_status(self):
        plan = ArchitecturalPlan(
            environment="western_room",
            door_openings=[],        # no openings for door_anchor_0
            window_openings=[_window_opening()],
            room_width=10.0, room_length=12.0, room_height=4.0,
        )
        shell = _full_shell()
        result = get_environment_architecture_review().review(plan, shell)
        assert result.status == ARCHITECTURE_STATUS_FAIL

    def test_missing_door_blocks_production_ready(self):
        plan = ArchitecturalPlan(
            environment="western_room",
            door_openings=[],
            window_openings=[_window_opening()],
        )
        shell = _full_shell()
        result = get_environment_architecture_review().review(plan, shell)
        assert result.production_ready is False

    def test_missing_door_anchor_listed(self):
        plan = ArchitecturalPlan(
            environment="western_room",
            door_openings=[],
            window_openings=[_window_opening()],
        )
        shell = _full_shell()
        result = get_environment_architecture_review().review(plan, shell)
        assert "door_anchor_0" in result.missing_door_openings

    def test_door_score_zero_when_no_openings(self):
        shell = {**_full_shell(), "anchors": [
            {"anchor_id": "door_anchor_0", "anchor_type": "door_anchor",
             "wall_face": "south", "tx": 0.0, "ty": 1.8, "tz": 6.0}
        ]}
        plan = ArchitecturalPlan(environment="western_room", door_openings=[])
        result = get_environment_architecture_review().review(plan, shell)
        assert result.door_score == pytest.approx(0.0, abs=1e-4)


# ── Missing window opening — hard block ───────────────────────────────────────

class TestMissingWindowOpening:
    def test_missing_window_fails_status(self):
        plan = ArchitecturalPlan(
            environment="western_room",
            door_openings=[_door_opening()],
            window_openings=[],      # missing window
        )
        shell = _full_shell()
        result = get_environment_architecture_review().review(plan, shell)
        assert result.status == ARCHITECTURE_STATUS_FAIL

    def test_missing_window_blocks_production(self):
        plan = ArchitecturalPlan(
            environment="western_room",
            door_openings=[_door_opening()],
            window_openings=[],
        )
        shell = _full_shell()
        result = get_environment_architecture_review().review(plan, shell)
        assert result.production_ready is False

    def test_missing_window_anchor_listed(self):
        plan = ArchitecturalPlan(
            environment="western_room",
            door_openings=[_door_opening()],
            window_openings=[],
        )
        shell = _full_shell()
        result = get_environment_architecture_review().review(plan, shell)
        assert "window_anchor_0" in result.missing_window_openings


# ── Fireplace validation ───────────────────────────────────────────────────────

class TestFireplaceValidation:
    def test_good_fireplace_passes(self):
        plan = ArchitecturalPlan(
            environment="western_room",
            door_openings=[_door_opening()],
            window_openings=[_window_opening()],
            fireplace_placements=[_good_fireplace()],
        )
        shell = _full_shell()
        result = get_environment_architecture_review().review(plan, shell)
        assert result.fireplace_valid is True
        assert result.fireplace_score == pytest.approx(1.0, abs=1e-4)

    def test_bad_back_face_distance_fails(self):
        fp = _good_fireplace()
        fp.back_face_distance = 0.20    # exceeds 0.05m limit
        plan = ArchitecturalPlan(
            environment="western_room",
            door_openings=[_door_opening()],
            window_openings=[_window_opening()],
            fireplace_placements=[fp],
        )
        shell = _full_shell()
        result = get_environment_architecture_review().review(plan, shell)
        assert result.fireplace_valid is False
        assert len(result.fireplace_failures) == 1

    def test_wrong_forward_axis_fails(self):
        fp = _good_fireplace()
        fp.forward_axis = [0.0, 0.0, -1.0]   # wrong — points away from interior
        plan = ArchitecturalPlan(
            environment="western_room",
            door_openings=[_door_opening()],
            window_openings=[_window_opening()],
            fireplace_placements=[fp],
        )
        shell = _full_shell()
        result = get_environment_architecture_review().review(plan, shell)
        assert result.fireplace_valid is False

    def test_no_fireplaces_vacuously_passes(self):
        plan = ArchitecturalPlan(
            environment="western_room",
            door_openings=[_door_opening()],
            window_openings=[_window_opening()],
            fireplace_placements=[],
        )
        shell = _full_shell()
        result = get_environment_architecture_review().review(plan, shell)
        assert result.fireplace_valid is True
        assert result.fireplace_score == pytest.approx(1.0, abs=1e-4)


# ── Beam validation ────────────────────────────────────────────────────────────

class TestBeamValidation:
    def test_good_beam_passes(self):
        plan = ArchitecturalPlan(
            environment="western_room",
            door_openings=[_door_opening()],
            window_openings=[_window_opening()],
            beam_placements=[_good_beam()],
        )
        shell = _full_shell()
        result = get_environment_architecture_review().review(plan, shell)
        assert result.beams_valid is True

    def test_beam_exceeding_ceiling_gap_fails(self):
        beam = _good_beam()
        beam.gap_to_ceiling = 0.20   # exceeds 0.05m limit
        plan = ArchitecturalPlan(
            environment="western_room",
            door_openings=[_door_opening()],
            window_openings=[_window_opening()],
            beam_placements=[beam],
        )
        result = get_environment_architecture_review().review(plan, {})
        assert result.beams_valid is False
        assert len(result.beam_failures) == 1

    def test_beam_intersecting_wall_fails(self):
        beam = _good_beam()
        beam.intersects_wall = True
        plan = ArchitecturalPlan(
            environment="western_room",
            door_openings=[_door_opening()],
            window_openings=[_window_opening()],
            beam_placements=[beam],
        )
        result = get_environment_architecture_review().review(plan, {})
        assert result.beams_valid is False
        assert beam.feature_id in result.wall_intersections

    def test_beam_above_ceiling_fails(self):
        beam = _good_beam()
        beam.is_below_ceiling = False
        plan = ArchitecturalPlan(
            environment="western_room",
            door_openings=[_door_opening()],
            window_openings=[_window_opening()],
            beam_placements=[beam],
        )
        result = get_environment_architecture_review().review(plan, {})
        assert result.beams_valid is False

    def test_no_beams_vacuously_passes(self):
        plan = ArchitecturalPlan(
            environment="forest",
            door_openings=[],
            window_openings=[],
            beam_placements=[],
        )
        result = get_environment_architecture_review().review(plan, {})
        assert result.beams_valid is True
        assert result.beam_score == pytest.approx(1.0, abs=1e-4)


# ── Shelf validation ───────────────────────────────────────────────────────────

class TestShelfValidation:
    def test_non_floating_shelf_passes(self):
        plan = ArchitecturalPlan(
            environment="library",
            door_openings=[_door_opening()],
            window_openings=[_window_opening()],
            shelf_placements=[_good_shelf()],
        )
        result = get_environment_architecture_review().review(plan, {})
        assert result.shelves_valid is True

    def test_floating_shelf_fails(self):
        shelf = _good_shelf()
        shelf.is_floating = True
        plan = ArchitecturalPlan(
            environment="library",
            door_openings=[_door_opening()],
            window_openings=[_window_opening()],
            shelf_placements=[shelf],
        )
        result = get_environment_architecture_review().review(plan, {})
        assert result.shelves_valid is False
        assert shelf.feature_id in result.floating_assets


# ── Score weights ─────────────────────────────────────────────────────────────

class TestScoreWeights:
    def test_perfect_plan_scores_1_0(self):
        plan = ArchitecturalPlan(
            environment="western_room",
            door_openings=[_door_opening()],
            window_openings=[_window_opening()],
            fireplace_placements=[_good_fireplace()],
            beam_placements=[_good_beam()],
            shelf_placements=[_good_shelf()],
        )
        shell = {
            "anchors": [
                {"anchor_id": "door_anchor_0",    "anchor_type": "door_anchor"},
                {"anchor_id": "window_anchor_0",  "anchor_type": "window_anchor"},
            ]
        }
        result = get_environment_architecture_review().review(plan, shell)
        assert result.architecture_score == pytest.approx(1.0, abs=1e-4)

    def test_empty_anchors_shell_vacuously_passes_if_no_features(self):
        plan = ArchitecturalPlan(environment="forest")
        result = get_environment_architecture_review().review(plan, {})
        assert result.architecture_score == pytest.approx(1.0, abs=1e-4)


# ── Report format ─────────────────────────────────────────────────────────────

class TestReportFormat:
    def test_report_contains_status(self):
        plan = _good_plan()
        result = get_environment_architecture_review().review(plan, _full_shell())
        assert result.status in result.architecture_report

    def test_report_contains_environment_name(self):
        plan = _good_plan()
        result = get_environment_architecture_review().review(plan, _full_shell())
        assert "western_room" in result.architecture_report


# ── Never raises ──────────────────────────────────────────────────────────────

class TestNeverRaises:
    def test_none_shell(self):
        plan = ArchitecturalPlan(environment="western_room")
        result = get_environment_architecture_review().review(plan, None)
        assert isinstance(result, ArchitectureReviewResult)

    def test_empty_plan_and_shell(self):
        plan = ArchitecturalPlan(environment="")
        result = get_environment_architecture_review().review(plan, {})
        assert isinstance(result, ArchitectureReviewResult)


# ── to_dict ────────────────────────────────────────────────────────────────────

class TestToDict:
    def test_to_dict_contains_required_keys(self):
        plan = _good_plan()
        result = get_environment_architecture_review().review(plan, _full_shell())
        d = result.to_dict()
        for key in ("status", "production_ready", "architecture_score",
                    "architecture_report", "door_openings_valid",
                    "window_openings_valid", "fireplace_valid",
                    "beams_valid", "shelves_valid"):
            assert key in d

    def test_to_dict_status_is_string(self):
        plan = _good_plan()
        result = get_environment_architecture_review().review(plan, _full_shell())
        assert isinstance(result.to_dict()["status"], str)
