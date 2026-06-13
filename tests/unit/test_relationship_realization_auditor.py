"""Tests for Tier 14.4.3 — RelationshipRealizationAuditor."""

import math
import pytest

from src.runtime.layout_realization.transform_resolver import ResolvedTransform
from src.runtime.layout.relationship_realization_auditor import (
    AssetAuditRecord,
    RealizationAuditResult,
    RelationshipRealizationAuditor,
    REALIZATION_AUDIT_PASS,
    REALIZATION_AUDIT_FAIL,
    get_relationship_realization_auditor,
    reset_relationship_realization_auditor_for_tests,
    _SURFACE_MIN_TY,
    _SURFACE_TOLERANCE,
    _CHAIR_MAX_ANGLE_ERR,
    _STOOL_MAX_DIST,
    _FIREPLACE_WALL_TOL,
    _LANTERN_WALL_MIN_TY,
    _BEAM_HALF_H,
    _BEAM_CEILING_TOL,
    _HARD_TRANSLATION_THRESHOLD,
    _HARD_ROTATION_THRESHOLD,
)
from src.runtime.layout import reset_affordance_engine_for_tests


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_all():
    reset_relationship_realization_auditor_for_tests()
    reset_affordance_engine_for_tests()
    yield
    reset_relationship_realization_auditor_for_tests()
    reset_affordance_engine_for_tests()


def _xf(
    asset_id: str,
    tx: float = 0.0, ty: float = 0.0, tz: float = 0.0,
    ry: float = 0.0,
    relationship: str = "",
    parent_id: str = "",
) -> ResolvedTransform:
    return ResolvedTransform(
        asset_id=asset_id, asset_name=asset_id,
        tx=tx, ty=ty, tz=tz, ry=ry,
        relationship=relationship, parent_id=parent_id,
    )


def _actual(tx=0.0, ty=0.0, tz=0.0, rx=0.0, ry=0.0, rz=0.0,
            sx=1.0, sy=1.0, sz=1.0):
    return {"tx": tx, "ty": ty, "tz": tz, "rx": rx, "ry": ry, "rz": rz,
            "sx": sx, "sy": sy, "sz": sz}


def _asset(name: str, ptype: str = "") -> dict:
    d: dict = {"name": name}
    if ptype:
        d["placement_type"] = ptype
    return d


def _audit(planned, actual_map, assets=None, room=None):
    return get_relationship_realization_auditor().audit(
        planned_transforms=planned,
        actual_transforms=actual_map,
        asset_metadata=assets or [],
        room_geometry=room or {},
    )


def _find_record(result: RealizationAuditResult, asset_id: str) -> AssetAuditRecord:
    for r in result.realized_relationships + result.failed_relationships:
        if r.asset_id == asset_id:
            return r
    pytest.fail(f"No record found for {asset_id}")


# ---------------------------------------------------------------------------
# Smoke tests
# ---------------------------------------------------------------------------

class TestSmoke:
    def test_empty_returns_pass(self):
        result = _audit([], {})
        assert isinstance(result, RealizationAuditResult)
        assert result.status == REALIZATION_AUDIT_PASS

    def test_never_raises(self):
        planned = [_xf("x")]
        result  = _audit(planned, {"x": _actual()})
        assert isinstance(result, RealizationAuditResult)

    def test_to_dict_is_json_serialisable(self):
        import json
        planned = [_xf("Table", ty=0.0), _xf("Bottle", ty=0.75)]
        actual  = {
            "Table":  _actual(ty=0.0),
            "Bottle": _actual(ty=0.75),
        }
        assets = [_asset("Table", "table"), _asset("Bottle", "bottle")]
        result = _audit(planned, actual, assets)
        json.dumps(result.to_dict())


# ---------------------------------------------------------------------------
# Delta computation
# ---------------------------------------------------------------------------

class TestDeltas:
    def test_zero_delta_when_actual_equals_planned(self):
        planned = [_xf("Table", tx=1.0, ty=0.0, tz=-2.0, ry=45.0)]
        actual  = {"Table": _actual(tx=1.0, ty=0.0, tz=-2.0, ry=45.0)}
        result  = _audit(planned, actual, [_asset("Table", "table")])
        rec = _find_record(result, "Table")
        assert rec.delta_translation == [0.0, 0.0, 0.0]
        assert rec.delta_rotation    == [0.0, 0.0, 0.0]

    def test_nonzero_delta_when_actual_differs(self):
        planned = [_xf("Table", tx=0.0, ty=0.0, tz=0.0)]
        actual  = {"Table": _actual(tx=1.5, ty=0.3, tz=-0.2)}
        result  = _audit(planned, actual, [_asset("Table", "table")])
        rec = _find_record(result, "Table")
        assert abs(rec.delta_translation[0] - 1.5) < 0.001
        assert abs(rec.delta_translation[1] - 0.3) < 0.001
        assert abs(rec.delta_translation[2] - (-0.2)) < 0.001

    def test_delta_rotation_normalised(self):
        # ry diff of 350° should be reported as -10° (normalised to ±180)
        planned = [_xf("Chair", ry=10.0)]
        actual  = {"Chair": _actual(ry=360.0)}   # 360 - 10 = 350 → normalised -10
        result  = _audit(planned, actual, [_asset("Chair", "chair")])
        rec = _find_record(result, "Chair")
        assert abs(rec.delta_rotation[1] - (-10.0)) < 0.5

    def test_no_data_status_when_asset_missing_from_actual(self):
        planned = [_xf("Ghost")]
        result  = _audit(planned, {}, [_asset("Ghost", "table")])
        assert result.failed_relationships == []  # NO_DATA, not FAIL
        assert result.total_skipped == 1


# ---------------------------------------------------------------------------
# Hard rule: planned ≠ actual → production_ready = False
# ---------------------------------------------------------------------------

class TestHardRule:
    def test_production_ready_true_when_transforms_match(self):
        planned = [_xf("Table", tx=1.0, ty=0.0, tz=-2.0)]
        actual  = {"Table": _actual(tx=1.0, ty=0.0, tz=-2.0)}
        result  = _audit(planned, actual, [_asset("Table", "table")])
        assert result.production_ready is True

    def test_production_ready_false_when_translation_mismatch(self):
        planned = [_xf("Table", tx=1.0)]
        actual  = {"Table": _actual(tx=2.0)}   # 1m mismatch
        result  = _audit(planned, actual, [_asset("Table", "table")])
        assert result.production_ready is False

    def test_mismatch_flag_set_on_record(self):
        planned = [_xf("Table", tx=0.0)]
        actual  = {"Table": _actual(tx=5.0)}
        result  = _audit(planned, actual, [_asset("Table", "table")])
        rec = _find_record(result, "Table")
        assert rec.transform_mismatch is True

    def test_tiny_rounding_delta_does_not_trigger_hard_rule(self):
        planned = [_xf("Table", tx=1.0)]
        actual  = {"Table": _actual(tx=1.0 + 0.0005)}  # 0.5 mm < threshold
        result  = _audit(planned, actual, [_asset("Table", "table")])
        assert result.production_ready is True


# ---------------------------------------------------------------------------
# Rule 1: Bottle — surface support
# ---------------------------------------------------------------------------

class TestBottleRule:
    def test_bottle_pass_on_table_surface(self):
        planned = [_xf("Bottle", ty=0.75, relationship="supports")]
        actual  = {"Bottle": _actual(ty=0.75)}
        result  = _audit(planned, actual, [_asset("Bottle", "bottle")])
        rec = _find_record(result, "Bottle")
        assert rec.realization_status == "PASS"

    def test_bottle_fail_on_floor(self):
        planned = [_xf("Bottle", ty=0.75)]
        actual  = {"Bottle": _actual(ty=0.0)}   # placed on floor!
        result  = _audit(planned, actual, [_asset("Bottle", "bottle")])
        rec = _find_record(result, "Bottle")
        assert rec.realization_status == "FAIL"
        assert "floor" in rec.failure_reason.lower()

    def test_bottle_fail_ty_below_min(self):
        planned = [_xf("Bottle", ty=0.75)]
        actual  = {"Bottle": _actual(ty=0.05)}
        result  = _audit(planned, actual, [_asset("Bottle", "bottle")])
        rec = _find_record(result, "Bottle")
        assert rec.realization_status == "FAIL"

    def test_bottle_fail_when_ty_drifts_more_than_tolerance(self):
        planned = [_xf("Bottle", ty=0.75)]
        actual  = {"Bottle": _actual(ty=0.75 + _SURFACE_TOLERANCE + 0.01)}
        result  = _audit(planned, actual, [_asset("Bottle", "bottle")])
        rec = _find_record(result, "Bottle")
        assert rec.realization_status == "FAIL"

    def test_bottle_pass_within_tolerance(self):
        planned = [_xf("Bottle", ty=0.75)]
        actual  = {"Bottle": _actual(ty=0.75 + _SURFACE_TOLERANCE - 0.01)}
        result  = _audit(planned, actual, [_asset("Bottle", "bottle")])
        rec = _find_record(result, "Bottle")
        assert rec.realization_status == "PASS"

    @pytest.mark.parametrize("ptype", ["whiskey_bottle", "cup", "mug", "glass", "plate", "bowl"])
    def test_surface_rule_applies_to_related_types(self, ptype):
        planned = [_xf("Item", ty=0.75)]
        actual  = {"Item": _actual(ty=0.0)}
        result  = _audit(planned, actual, [_asset("Item", ptype)])
        rec = _find_record(result, "Item")
        assert rec.realization_status == "FAIL"


# ---------------------------------------------------------------------------
# Rule 2: Chair — facing table
# ---------------------------------------------------------------------------

class TestChairRule:
    def test_chair_pass_exact_ry(self):
        planned = [_xf("Chair1", ry=180.0)]
        actual  = {"Chair1": _actual(ry=180.0)}
        result  = _audit(planned, actual, [_asset("Chair1", "chair")])
        rec = _find_record(result, "Chair1")
        assert rec.realization_status == "PASS"

    def test_chair_pass_within_angle_tolerance(self):
        planned = [_xf("Chair1", ry=180.0)]
        actual  = {"Chair1": _actual(ry=180.0 + _CHAIR_MAX_ANGLE_ERR - 1.0)}
        result  = _audit(planned, actual, [_asset("Chair1", "chair")])
        rec = _find_record(result, "Chair1")
        assert rec.realization_status == "PASS"

    def test_chair_fail_angle_error_exceeds_threshold(self):
        planned = [_xf("Chair1", ry=180.0)]
        actual  = {"Chair1": _actual(ry=180.0 + _CHAIR_MAX_ANGLE_ERR + 1.0)}
        result  = _audit(planned, actual, [_asset("Chair1", "chair")])
        rec = _find_record(result, "Chair1")
        assert rec.realization_status == "FAIL"
        assert "facing" in rec.failure_reason.lower() or "error" in rec.failure_reason.lower()

    def test_chair_fail_180_degree_flip(self):
        planned = [_xf("Chair1", ry=0.0)]
        actual  = {"Chair1": _actual(ry=180.0)}  # facing completely wrong direction
        result  = _audit(planned, actual, [_asset("Chair1", "chair")])
        rec = _find_record(result, "Chair1")
        assert rec.realization_status == "FAIL"

    def test_chair_pass_when_ry_wraps_360(self):
        # planned=350°, actual=5° → diff=15° (within threshold)
        planned = [_xf("Chair1", ry=350.0)]
        actual  = {"Chair1": _actual(ry=5.0)}
        result  = _audit(planned, actual, [_asset("Chair1", "chair")])
        rec = _find_record(result, "Chair1")
        assert rec.realization_status == "PASS"


# ---------------------------------------------------------------------------
# Rule 3: Stool — bar proximity
# ---------------------------------------------------------------------------

class TestStoolRule:
    def test_stool_pass_within_distance(self):
        planned = [
            _xf("Bar",   tx=0.0, tz=-5.0, relationship="anchor"),
            _xf("Stool", tx=0.0, tz=-4.5, relationship="around", parent_id="Bar"),
        ]
        actual = {
            "Bar":   _actual(tx=0.0, tz=-5.0),
            "Stool": _actual(tx=0.0, tz=-4.5),  # 0.5m from bar
        }
        assets = [_asset("Bar", "bar_counter"), _asset("Stool", "stool")]
        result = _audit(planned, actual, assets)
        rec    = _find_record(result, "Stool")
        assert rec.realization_status == "PASS"

    def test_stool_fail_too_far_from_bar(self):
        planned = [
            _xf("Bar",   tx=0.0, tz=-5.0),
            _xf("Stool", tx=0.0, tz=-5.5),
        ]
        actual = {
            "Bar":   _actual(tx=0.0, tz=-5.0),
            "Stool": _actual(tx=8.0, tz=0.0),   # far away
        }
        assets = [_asset("Bar", "bar_counter"), _asset("Stool", "stool")]
        result = _audit(planned, actual, assets)
        rec    = _find_record(result, "Stool")
        assert rec.realization_status == "FAIL"
        assert "distance" in rec.failure_reason.lower()

    def test_stool_skip_when_no_bar_in_scene(self):
        planned = [_xf("Stool", tx=0.0)]
        actual  = {"Stool": _actual(tx=0.0)}
        assets  = [_asset("Stool", "stool")]
        result  = _audit(planned, actual, assets)
        # No bar_counter → rule skipped → PASS
        rec = _find_record(result, "Stool")
        assert rec.realization_status == "PASS"

    def test_stool_pass_exactly_at_max_distance(self):
        planned = [
            _xf("Bar",   tx=0.0, tz=0.0),
            _xf("Stool", tx=_STOOL_MAX_DIST, tz=0.0),
        ]
        actual = {
            "Bar":   _actual(tx=0.0, tz=0.0),
            "Stool": _actual(tx=_STOOL_MAX_DIST, tz=0.0),
        }
        assets = [_asset("Bar", "bar_counter"), _asset("Stool", "stool")]
        result = _audit(planned, actual, assets)
        rec    = _find_record(result, "Stool")
        assert rec.realization_status == "PASS"


# ---------------------------------------------------------------------------
# Rule 4: Fireplace — wall snap
# ---------------------------------------------------------------------------

class TestFireplaceRule:
    def test_fireplace_pass_when_tz_matches(self):
        planned = [_xf("FP", tz=-5.71, relationship="attached_to", parent_id="wall_north")]
        actual  = {"FP": _actual(tz=-5.71)}
        result  = _audit(planned, actual, [_asset("FP", "fireplace")])
        rec = _find_record(result, "FP")
        assert rec.realization_status == "PASS"

    def test_fireplace_pass_within_wall_tolerance(self):
        planned = [_xf("FP", tz=-5.71)]
        actual  = {"FP": _actual(tz=-5.71 + _FIREPLACE_WALL_TOL - 0.01)}
        result  = _audit(planned, actual, [_asset("FP", "fireplace")])
        rec = _find_record(result, "FP")
        assert rec.realization_status == "PASS"

    def test_fireplace_fail_wall_snap_not_applied(self):
        planned = [_xf("FP", tz=-5.71)]
        actual  = {"FP": _actual(tz=-3.0)}   # not snapped to wall
        result  = _audit(planned, actual, [_asset("FP", "fireplace")])
        rec = _find_record(result, "FP")
        assert rec.realization_status == "FAIL"
        assert "wall snap" in rec.failure_reason.lower()

    def test_fireplace_fail_delta_exceeds_tolerance(self):
        planned = [_xf("FP", tz=-5.71)]
        actual  = {"FP": _actual(tz=-5.71 + _FIREPLACE_WALL_TOL + 0.01)}
        result  = _audit(planned, actual, [_asset("FP", "fireplace")])
        rec = _find_record(result, "FP")
        assert rec.realization_status == "FAIL"


# ---------------------------------------------------------------------------
# Rule 5: Lantern — valid attachment
# ---------------------------------------------------------------------------

class TestLanternRule:
    def test_lantern_pass_on_surface(self):
        planned = [_xf("Lantern", ty=0.75, relationship="supports")]
        actual  = {"Lantern": _actual(ty=0.75)}
        result  = _audit(planned, actual, [_asset("Lantern", "lantern")])
        rec = _find_record(result, "Lantern")
        assert rec.realization_status == "PASS"

    def test_lantern_pass_wall_mounted(self):
        planned = [_xf("Lantern", ty=2.40, relationship="attached_to")]
        actual  = {"Lantern": _actual(ty=2.40)}
        result  = _audit(planned, actual, [_asset("Lantern", "lantern")])
        rec = _find_record(result, "Lantern")
        assert rec.realization_status == "PASS"

    def test_lantern_fail_floating(self):
        planned = [_xf("Lantern", ty=0.75)]
        actual  = {"Lantern": _actual(ty=0.0)}   # on floor
        result  = _audit(planned, actual, [_asset("Lantern", "lantern")])
        rec = _find_record(result, "Lantern")
        assert rec.realization_status == "FAIL"
        assert "floating" in rec.failure_reason.lower() or "ty" in rec.failure_reason.lower()

    def test_lantern_pass_at_exact_wall_height(self):
        planned = [_xf("Lantern", ty=_LANTERN_WALL_MIN_TY)]
        actual  = {"Lantern": _actual(ty=_LANTERN_WALL_MIN_TY)}
        result  = _audit(planned, actual, [_asset("Lantern", "lantern")])
        rec = _find_record(result, "Lantern")
        assert rec.realization_status == "PASS"


# ---------------------------------------------------------------------------
# Rule 6: Beam — ceiling attachment
# ---------------------------------------------------------------------------

class TestBeamRule:
    def test_beam_pass_at_correct_ceiling_height(self):
        ceiling_h = 4.0
        # ty = ceiling_h - BEAM_HALF_H - 0.0 (touching)
        ty = ceiling_h - _BEAM_HALF_H
        planned = [_xf("Beam", ty=ty, relationship="attached_to")]
        actual  = {"Beam": _actual(ty=ty)}
        result  = _audit(planned, actual, [_asset("Beam", "beam")],
                         room={"height": ceiling_h})
        rec = _find_record(result, "Beam")
        assert rec.realization_status == "PASS"

    def test_beam_fail_too_far_from_ceiling(self):
        ceiling_h = 4.0
        ty = 1.0  # far from ceiling
        planned = [_xf("Beam", ty=ty)]
        actual  = {"Beam": _actual(ty=ty)}
        result  = _audit(planned, actual, [_asset("Beam", "beam")],
                         room={"height": ceiling_h})
        rec = _find_record(result, "Beam")
        assert rec.realization_status == "FAIL"
        assert "ceiling" in rec.failure_reason.lower()

    def test_beam_pass_within_ceiling_tolerance(self):
        ceiling_h = 4.0
        ty = ceiling_h - _BEAM_HALF_H - _BEAM_CEILING_TOL + 0.01
        planned = [_xf("Beam", ty=ty)]
        actual  = {"Beam": _actual(ty=ty)}
        result  = _audit(planned, actual, [_asset("Beam", "beam")],
                         room={"height": ceiling_h})
        rec = _find_record(result, "Beam")
        assert rec.realization_status == "PASS"


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

class TestScoring:
    def test_score_one_when_all_pass(self):
        planned = [
            _xf("Table",  ty=0.0, relationship="anchor"),
            _xf("Bottle", ty=0.75, relationship="supports"),
        ]
        actual = {
            "Table":  _actual(ty=0.0),
            "Bottle": _actual(ty=0.75),
        }
        assets = [_asset("Table", "table"), _asset("Bottle", "bottle")]
        result = _audit(planned, actual, assets)
        assert result.relationship_realization_score == pytest.approx(1.0)
        assert result.status == REALIZATION_AUDIT_PASS

    def test_score_zero_when_all_fail(self):
        planned = [
            _xf("Bottle1", ty=0.75),
            _xf("Bottle2", ty=0.75),
        ]
        actual = {
            "Bottle1": _actual(ty=0.0),
            "Bottle2": _actual(ty=0.0),
        }
        assets = [_asset("Bottle1", "bottle"), _asset("Bottle2", "bottle")]
        result = _audit(planned, actual, assets)
        assert result.relationship_realization_score == pytest.approx(0.0)
        assert result.status == REALIZATION_AUDIT_FAIL

    def test_status_fail_below_threshold(self):
        # 2 pass, 3 fail → score = 0.4 < 0.95
        planned = [_xf(f"Bottle{i}", ty=0.75) for i in range(5)]
        actual  = {
            "Bottle0": _actual(ty=0.75),
            "Bottle1": _actual(ty=0.75),
            "Bottle2": _actual(ty=0.0),
            "Bottle3": _actual(ty=0.0),
            "Bottle4": _actual(ty=0.0),
        }
        assets = [_asset(f"Bottle{i}", "bottle") for i in range(5)]
        result = _audit(planned, actual, assets)
        assert result.status == REALIZATION_AUDIT_FAIL
        assert result.relationship_realization_score < 0.95

    def test_status_pass_at_threshold(self):
        # 19 pass, 1 fail → score = 0.95
        planned = [_xf(f"B{i}", ty=0.75) for i in range(20)]
        actual  = {f"B{i}": _actual(ty=0.75) for i in range(19)}
        actual["B19"] = _actual(ty=0.0)
        assets  = [_asset(f"B{i}", "bottle") for i in range(20)]
        result  = _audit(planned, actual, assets)
        assert result.relationship_realization_score == pytest.approx(0.95)
        # Exactly at threshold — PASS (≥ 0.95)
        assert result.status == REALIZATION_AUDIT_PASS

    def test_total_counts_correct(self):
        planned = [
            _xf("Bottle", ty=0.75),
            _xf("Chair",  ry=180.0),
            _xf("Ghost"),           # no actual → NO_DATA
        ]
        actual = {
            "Bottle": _actual(ty=0.75),
            "Chair":  _actual(ry=180.0),
        }
        assets = [_asset("Bottle", "bottle"), _asset("Chair", "chair")]
        result = _audit(planned, actual, assets)
        assert result.total_passed  >= 2
        assert result.total_skipped >= 1


# ---------------------------------------------------------------------------
# Categorised outputs
# ---------------------------------------------------------------------------

class TestOutputCategories:
    def test_realized_relationships_contains_pass_records(self):
        planned = [_xf("Bottle", ty=0.75)]
        actual  = {"Bottle": _actual(ty=0.75)}
        result  = _audit(planned, actual, [_asset("Bottle", "bottle")])
        assert any(r.asset_id == "Bottle" for r in result.realized_relationships)

    def test_failed_relationships_contains_fail_records(self):
        planned = [_xf("Bottle", ty=0.75)]
        actual  = {"Bottle": _actual(ty=0.0)}
        result  = _audit(planned, actual, [_asset("Bottle", "bottle")])
        assert any(r.asset_id == "Bottle" for r in result.failed_relationships)

    def test_no_overlap_between_realized_and_failed(self):
        planned = [
            _xf("BottleOk",   ty=0.75),
            _xf("BottleBad",  ty=0.75),
        ]
        actual = {
            "BottleOk":  _actual(ty=0.75),
            "BottleBad": _actual(ty=0.0),
        }
        assets = [_asset("BottleOk", "bottle"), _asset("BottleBad", "bottle")]
        result = _audit(planned, actual, assets)
        realized_ids = {r.asset_id for r in result.realized_relationships}
        failed_ids   = {r.asset_id for r in result.failed_relationships}
        assert realized_ids.isdisjoint(failed_ids)


# ---------------------------------------------------------------------------
# Audit table
# ---------------------------------------------------------------------------

class TestAuditTable:
    def test_audit_table_is_non_empty(self):
        planned = [_xf("Bottle", ty=0.75)]
        actual  = {"Bottle": _actual(ty=0.75)}
        result  = _audit(planned, actual, [_asset("Bottle", "bottle")])
        assert isinstance(result.audit_table, str)
        assert len(result.audit_table) > 0

    def test_audit_table_contains_asset_id(self):
        planned = [_xf("Bottle", ty=0.75)]
        actual  = {"Bottle": _actual(ty=0.0)}
        result  = _audit(planned, actual, [_asset("Bottle", "bottle")])
        assert "Bottle" in result.audit_table

    def test_audit_table_contains_fail_status(self):
        planned = [_xf("Bottle", ty=0.75)]
        actual  = {"Bottle": _actual(ty=0.0)}
        result  = _audit(planned, actual, [_asset("Bottle", "bottle")])
        assert "FAIL" in result.audit_table

    def test_audit_table_contains_score(self):
        planned = [_xf("Bottle", ty=0.75)]
        actual  = {"Bottle": _actual(ty=0.75)}
        result  = _audit(planned, actual, [_asset("Bottle", "bottle")])
        assert "Score" in result.audit_table


# ---------------------------------------------------------------------------
# Full western-room scene integration
# ---------------------------------------------------------------------------

class TestWesternRoomIntegration:
    def _western_room_planned(self):
        return [
            _xf("Table",     tx=0.0, ty=0.0, tz=0.0,   ry=0.0,   relationship="anchor"),
            _xf("Chair1",    tx=0.0, ty=0.0, tz=0.95,  ry=180.0, relationship="around",    parent_id="Table"),
            _xf("Chair2",    tx=0.0, ty=0.0, tz=-0.95, ry=0.0,   relationship="around",    parent_id="Table"),
            _xf("Bottle",    tx=0.0, ty=0.75,tz=0.0,   ry=0.0,   relationship="supports",  parent_id="Table"),
            _xf("Fireplace", tx=0.0, ty=0.0, tz=-5.71, ry=0.0,   relationship="attached_to",parent_id="wall_north"),
            _xf("Barrel",    tx=0.0, ty=0.0, tz=-5.5,  ry=0.0,   relationship="belongs_near"),
            _xf("Poster",    tx=-4.96,ty=1.6,tz=-2.4,  ry=270.0, relationship="attached_to",parent_id="wall_west"),
        ]

    def _western_room_actual_perfect(self):
        return {
            "Table":     _actual(tx=0.0, ty=0.0, tz=0.0,    ry=0.0),
            "Chair1":    _actual(tx=0.0, ty=0.0, tz=0.95,   ry=180.0),
            "Chair2":    _actual(tx=0.0, ty=0.0, tz=-0.95,  ry=0.0),
            "Bottle":    _actual(tx=0.0, ty=0.75,tz=0.0,    ry=0.0),
            "Fireplace": _actual(tx=0.0, ty=0.0, tz=-5.71,  ry=0.0),
            "Barrel":    _actual(tx=0.0, ty=0.0, tz=-5.5,   ry=0.0),
            "Poster":    _actual(tx=-4.96,ty=1.6,tz=-2.4,   ry=270.0),
        }

    def _western_assets(self):
        return [
            _asset("Table",     "table"),
            _asset("Chair1",    "chair"),
            _asset("Chair2",    "chair"),
            _asset("Bottle",    "bottle"),
            _asset("Fireplace", "fireplace"),
            _asset("Barrel",    "barrel"),
            _asset("Poster",    "poster"),
        ]

    def test_perfect_realization_scores_one(self):
        result = _audit(
            self._western_room_planned(),
            self._western_room_actual_perfect(),
            self._western_assets(),
        )
        assert result.relationship_realization_score == pytest.approx(1.0)
        assert result.status         == REALIZATION_AUDIT_PASS
        assert result.production_ready is True
        assert result.failed_relationships == []

    def test_bottle_on_floor_fails_scene(self):
        actual = self._western_room_actual_perfect()
        actual["Bottle"] = _actual(tx=0.0, ty=0.0, tz=0.0)   # floor!
        result = _audit(
            self._western_room_planned(),
            actual,
            self._western_assets(),
        )
        assert any(r.asset_id == "Bottle" for r in result.failed_relationships)
        assert result.status == REALIZATION_AUDIT_FAIL

    def test_chair_wrong_facing_fails_scene(self):
        actual = self._western_room_actual_perfect()
        actual["Chair1"] = _actual(ry=90.0)   # facing wrong direction (90° off)
        result = _audit(
            self._western_room_planned(),
            actual,
            self._western_assets(),
        )
        assert any(r.asset_id == "Chair1" for r in result.failed_relationships)

    def test_fireplace_not_snapped_fails_scene(self):
        actual = self._western_room_actual_perfect()
        actual["Fireplace"] = _actual(tx=0.0, ty=0.0, tz=-2.0)  # not snapped
        result = _audit(
            self._western_room_planned(),
            actual,
            self._western_assets(),
        )
        assert any(r.asset_id == "Fireplace" for r in result.failed_relationships)
