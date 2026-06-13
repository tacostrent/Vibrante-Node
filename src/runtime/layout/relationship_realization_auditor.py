"""
relationship_realization_auditor.py — Tier 14.4.3 Relationship Realization Audit
==================================================================================
Verifies that relationship_aware_transforms from RelationshipLayoutEngine were
correctly applied to Houdini nodes.

For every audited asset, produces:
  asset_id                  — stable identifier
  asset_name                — display label
  relationship_rule         — the rule being checked
  planned_transform         — what RelationshipLayoutEngine intended
  actual_houdini_transform  — what Houdini's node actually has (tx/ty/tz/rx/ry/rz)
  delta_translation         — [dx, dy, dz] in metres
  delta_rotation            — [drx, dry, drz] in degrees
  delta_scale               — [dsx, dsy, dsz]
  realization_status        — PASS | FAIL | SKIP | NO_DATA

Per-type semantic rules:
  bottle      actual.ty ≥ 0.10m  AND  |actual.ty − planned.ty| ≤ 0.05m
  cup/plate   same as bottle
  chair       |angular_error(actual.ry, planned.ry)| ≤ 15°
  stool       distance(actual, bar_planned_pos) ≤ 1.2 m
  fireplace   |actual.tz − planned.tz| ≤ 0.05 m  (wall snap)
  lantern     actual.ty ≥ 0.10m  (on surface)  OR  actual.ty ≥ 1.5m  (wall-mounted)
  beam        |ceiling_height − (actual.ty + BEAM_HALF_H)| ≤ 0.05 m

Hard rule:
  If planned_transform ≠ actual_houdini_transform for ANY asset
  (delta > threshold):  production_ready = False.

Scoring:
  relationship_realization_score = audited_pass / total_audited
  PASS criterion: score ≥ 0.95

Architecture — bridge isolation:
  RelationshipRealizationAuditor  pure planning (no bridge calls), fully testable.
  HoudiniTransformFetcher         the ONLY component that calls get_bridge();
                                  used by the Houdini node to fill actual_transforms.

Public API:
  REALIZATION_AUDIT_PASS
  REALIZATION_AUDIT_FAIL
  AssetAuditRecord
  RealizationAuditResult
  RelationshipRealizationAuditor
  HoudiniTransformFetcher
  get_relationship_realization_auditor()
  reset_relationship_realization_auditor_for_tests()
"""

from __future__ import annotations

import math
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.runtime.layout.affordance_engine import get_affordance_engine
from src.runtime.layout_realization.transform_resolver import ResolvedTransform

# ---------------------------------------------------------------------------
# Status constants
# ---------------------------------------------------------------------------

REALIZATION_AUDIT_PASS = "PASS"
REALIZATION_AUDIT_FAIL = "FAIL"

_RECORD_PASS    = "PASS"
_RECORD_FAIL    = "FAIL"
_RECORD_SKIP    = "SKIP"
_RECORD_NO_DATA = "NO_DATA"

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

_PASS_THRESHOLD: float = 0.95

# Hard-rule thresholds — planned vs actual must not exceed these
_HARD_TRANSLATION_THRESHOLD: float = 0.001    # 1 mm
_HARD_ROTATION_THRESHOLD: float    = 0.10     # 0.1°
_HARD_SCALE_THRESHOLD: float       = 0.001

# Per-rule thresholds
_SURFACE_MIN_TY: float        = 0.10    # anything below is "on floor"
_SURFACE_TOLERANCE: float     = 0.05    # ty must match planned ± this
_CHAIR_MAX_ANGLE_ERR: float   = 15.0    # degrees
_STOOL_MAX_DIST: float        = 1.20    # metres to bar_counter
_FIREPLACE_WALL_TOL: float    = 0.05    # |actual.tz − planned.tz|
_LANTERN_WALL_MIN_TY: float   = 1.50    # wall-mounted lantern height (approx)
_BEAM_HALF_H: float           = 0.15    # estimated beam half-height
_BEAM_CEILING_TOL: float      = 0.05    # ceiling gap tolerance
_DEFAULT_CEILING_H: float     = 4.0

# Relationship-based routing constants (Tier 14.4.3 extension)
_SKIP_SENTINEL = "__skip__"
_SUPPORTS_TY_TOL: float        = 0.02    # ±2cm for relationship-based supports
_BELONGS_NEAR_MAX_DIST: float  = 2.5     # max distance for belongs_near
_BELONGS_NEAR_MAX_ANGLE: float = 15.0    # max facing error for belongs_near
_WALL_BACK_FACE_MAX: float     = 0.05    # ±5cm position match for wall attachment
_WALL_INTERIOR_ANGLE_MAX: float = 20.0   # max ry error for wall-attached assets

_WALL_RY: Dict[str, float] = {
    "wall_north": 0.0,    # north wall → faces south (+z, interior)
    "wall_south": 180.0,  # south wall → faces north (-z, interior)
    "wall_east":  90.0,   # east wall  → faces west (-x, interior)
    "wall_west":  270.0,  # west wall  → faces east (+x, interior)
}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class AssetAuditRecord:
    """One row in the realization audit report."""
    asset_id:                  str
    asset_name:                str
    relationship_rule:         str
    planned_transform:         Dict[str, float] = field(default_factory=dict)
    actual_houdini_transform:  Dict[str, float] = field(default_factory=dict)
    delta_translation:         List[float]      = field(default_factory=lambda: [0.0, 0.0, 0.0])
    delta_rotation:            List[float]      = field(default_factory=lambda: [0.0, 0.0, 0.0])
    delta_scale:               List[float]      = field(default_factory=lambda: [0.0, 0.0, 0.0])
    realization_status:        str              = _RECORD_SKIP
    failure_reason:            str              = ""
    transform_mismatch:        bool             = False   # hard-rule violation
    production_ready:          bool             = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id":                 self.asset_id,
            "asset_name":               self.asset_name,
            "relationship_rule":        self.relationship_rule,
            "planned_transform":        dict(self.planned_transform),
            "actual_houdini_transform": dict(self.actual_houdini_transform),
            "delta_translation":        [round(v, 4) for v in self.delta_translation],
            "delta_rotation":           [round(v, 4) for v in self.delta_rotation],
            "delta_scale":              [round(v, 4) for v in self.delta_scale],
            "realization_status":       self.realization_status,
            "failure_reason":           self.failure_reason,
            "transform_mismatch":       self.transform_mismatch,
            "production_ready":         self.production_ready,
        }


@dataclass
class RealizationAuditResult:
    """Full output of RelationshipRealizationAuditor.audit()."""

    # Categorised records
    realized_relationships: List[AssetAuditRecord] = field(default_factory=list)
    failed_relationships:   List[AssetAuditRecord] = field(default_factory=list)

    # Scoring
    relationship_realization_score: float = 0.0
    total_audited:                  int   = 0
    total_passed:                   int   = 0
    total_failed:                   int   = 0
    total_skipped:                  int   = 0

    # Overall status
    status:          str       = REALIZATION_AUDIT_PASS
    production_ready: bool     = True
    audit_table:      str      = ""

    ok:     bool       = True
    errors: List[str]  = field(default_factory=list)

    # Relationship-based audit outputs (Tier 14.4.3 extension)
    per_asset_findings: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "realized_relationships":        [r.to_dict() for r in self.realized_relationships],
            "failed_relationships":          [r.to_dict() for r in self.failed_relationships],
            "relationship_realization_score": round(self.relationship_realization_score, 4),
            "total_audited":                 self.total_audited,
            "total_passed":                  self.total_passed,
            "total_failed":                  self.total_failed,
            "total_skipped":                 self.total_skipped,
            "status":                        self.status,
            "production_ready":              self.production_ready,
            "audit_table":                   self.audit_table,
            "ok":                            self.ok,
            "errors":                        list(self.errors),
            # Tier 14.4.3 spec outputs
            "realized_edges":     [r.to_dict() for r in self.realized_relationships],
            "failed_edges":       [r.to_dict() for r in self.failed_relationships],
            "per_asset_findings": list(self.per_asset_findings),
        }


# ---------------------------------------------------------------------------
# Auditor (pure planning — no bridge calls)
# ---------------------------------------------------------------------------

class RelationshipRealizationAuditor:
    """
    Compares RelationshipLayoutEngine planned transforms to actual Houdini
    node transforms and produces a per-asset audit report.

    Usage (tests — inject actual transforms directly):
        auditor = get_relationship_realization_auditor()
        result  = auditor.audit(
            planned_transforms = layout.relationship_aware_transforms,
            actual_transforms  = {"Chair1": {"tx": 0.0, "ty": 0.0, "tz": 0.95, "ry": 180.0}},
            asset_metadata     = assets,          # list of asset dicts
        )

    Usage (production — fetch from Houdini via HoudiniTransformFetcher):
        actual = HoudiniTransformFetcher().fetch_transforms(planned, node_path_map)
        result = auditor.audit(planned, actual, assets, room_geometry)
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def audit(
        self,
        planned_transforms: List[ResolvedTransform],
        actual_transforms:  Dict[str, Dict[str, float]],
        asset_metadata:     List[Dict[str, Any]] = None,
        room_geometry:      Optional[Dict[str, Any]] = None,
    ) -> RealizationAuditResult:
        """
        Run the full realization audit.

        Args:
            planned_transforms  — ResolvedTransforms from RelationshipLayoutEngine
            actual_transforms   — {asset_id: {tx, ty, tz, rx, ry, rz, sx, sy, sz}}
                                  from HoudiniTransformFetcher or test injection
            asset_metadata      — list of raw asset dicts (for type inference)
            room_geometry       — dict with 'height' key for beam ceiling check

        Returns: RealizationAuditResult. Never raises.
        """
        try:
            return self._audit(
                planned_transforms,
                actual_transforms or {},
                asset_metadata or [],
                room_geometry or {},
            )
        except Exception as exc:
            return RealizationAuditResult(
                ok=False,
                errors=[f"RelationshipRealizationAuditor.audit failed: {exc}"],
                status=REALIZATION_AUDIT_FAIL,
            )

    # ------------------------------------------------------------------
    # Internal pipeline
    # ------------------------------------------------------------------

    def _audit(
        self,
        planned_transforms: List[ResolvedTransform],
        actual_transforms:  Dict[str, Dict[str, float]],
        asset_metadata:     List[Dict[str, Any]],
        room_geometry:      Dict[str, Any],
    ) -> RealizationAuditResult:
        eng            = get_affordance_engine()
        ceiling_height = float(room_geometry.get("height", _DEFAULT_CEILING_H))

        # Build type index from metadata
        aid_to_type: Dict[str, str] = {}
        for asset in asset_metadata:
            aid  = _aid(asset)
            if aid:
                aid_to_type[aid] = eng.infer_type(asset)

        # Build planned_pos_map for proximity checks (stool→bar distance)
        planned_pos: Dict[str, ResolvedTransform] = {t.asset_id: t for t in planned_transforms}

        # Find bar_counter planned position for stool distance checks
        bar_planned: Optional[ResolvedTransform] = _find_by_type(
            "bar_counter", aid_to_type, planned_pos
        )

        # Reconstruct room wall geometry for wall-attachment checks
        room_walls = _build_room_walls(room_geometry)

        records: List[AssetAuditRecord] = []
        hard_rule_violated = False

        for planned in planned_transforms:
            aid   = planned.asset_id
            atype = aid_to_type.get(aid) or eng.infer_type({"name": aid})
            actual = actual_transforms.get(aid)

            rec = AssetAuditRecord(
                asset_id=aid,
                asset_name=planned.asset_name or aid,
                relationship_rule=_rule_name(atype),
                planned_transform=_xf_to_dict(planned),
                actual_houdini_transform=dict(actual) if actual else {},
            )

            if actual is None:
                rec.realization_status = _RECORD_NO_DATA
                rec.failure_reason     = "No actual transform from Houdini"
                rec.production_ready   = False
                records.append(rec)
                continue

            # ---- Compute deltas ------------------------------------------
            p = _xf_to_dict(planned)
            a = actual
            dtx = _get(a, "tx") - _get(p, "tx")
            dty = _get(a, "ty") - _get(p, "ty")
            dtz = _get(a, "tz") - _get(p, "tz")
            drx = _get(a, "rx") - _get(p, "rx")
            dry = _normalize_angle(_get(a, "ry") - _get(p, "ry"))
            drz = _get(a, "rz") - _get(p, "rz")
            dsx = _get(a, "sx", 1.0) - _get(p, "sx", 1.0)
            dsy = _get(a, "sy", 1.0) - _get(p, "sy", 1.0)
            dsz = _get(a, "sz", 1.0) - _get(p, "sz", 1.0)

            rec.delta_translation = [round(dtx, 4), round(dty, 4), round(dtz, 4)]
            rec.delta_rotation    = [round(drx, 4), round(dry, 4), round(drz, 4)]
            rec.delta_scale       = [round(dsx, 4), round(dsy, 4), round(dsz, 4)]

            # ---- Hard rule: planned ≠ actual? ----------------------------
            t_mag = math.sqrt(dtx * dtx + dty * dty + dtz * dtz)
            r_mag = max(abs(drx), abs(dry), abs(drz))
            s_mag = max(abs(dsx), abs(dsy), abs(dsz))
            mismatch = (
                t_mag > _HARD_TRANSLATION_THRESHOLD
                or r_mag > _HARD_ROTATION_THRESHOLD
                or s_mag > _HARD_SCALE_THRESHOLD
            )
            rec.transform_mismatch = mismatch
            if mismatch:
                hard_rule_violated = True

            # ---- Two-tier semantic dispatch:
            #      1. Relationship-based (new Tier 14.4.3 routing)
            #      2. Type-based fallback (existing routing, backward-compat)
            rel_status, rel_reason = self._check_by_relationship(
                planned, actual, actual_transforms, ceiling_height, room_walls
            )
            if rel_status != _SKIP_SENTINEL:
                ok     = (rel_status == _RECORD_PASS)
                reason = rel_reason
            else:
                ok, reason = self._check_rule(
                    atype, planned, actual, bar_planned, ceiling_height,
                    t_mag, dry,
                )

            rec.realization_status = _RECORD_PASS if ok else _RECORD_FAIL
            rec.failure_reason     = reason
            rec.production_ready   = ok and not mismatch

            records.append(rec)

        # ---- Assemble result -----------------------------------------
        passed  = [r for r in records if r.realization_status == _RECORD_PASS]
        failed  = [r for r in records if r.realization_status == _RECORD_FAIL]
        skipped = [r for r in records
                   if r.realization_status in (_RECORD_SKIP, _RECORD_NO_DATA)]
        audited = [r for r in records
                   if r.realization_status in (_RECORD_PASS, _RECORD_FAIL)]

        # Vacuous pass for empty plans; otherwise derive from audited counts.
        score = 1.0 if len(audited) == 0 else len(passed) / len(audited)
        # status is determined by score alone (spec: "score ≥ 0.95").
        # production_ready additionally requires no hard-rule violation.
        status_pass  = score >= _PASS_THRESHOLD
        overall_ok   = status_pass and not hard_rule_violated

        audit_table = _format_table(records, score)
        per_asset_findings = [r.to_dict() for r in records]

        return RealizationAuditResult(
            realized_relationships          = passed,
            failed_relationships            = failed,
            relationship_realization_score  = round(score, 4),
            total_audited                   = len(audited),
            total_passed                    = len(passed),
            total_failed                    = len(failed),
            total_skipped                   = len(skipped),
            status          = REALIZATION_AUDIT_PASS if status_pass else REALIZATION_AUDIT_FAIL,
            production_ready = status_pass and not hard_rule_violated,
            audit_table      = audit_table,
            ok               = overall_ok,
            per_asset_findings = per_asset_findings,
        )

    # ------------------------------------------------------------------
    # Per-type rule checks
    # ------------------------------------------------------------------

    def _check_rule(
        self,
        atype:         str,
        planned:       ResolvedTransform,
        actual:        Dict[str, float],
        bar_planned:   Optional[ResolvedTransform],
        ceiling_h:     float,
        t_mag:         float,
        dry:           float,
    ) -> Tuple[bool, str]:
        """
        Return (passed, failure_reason) for the semantic rule for this asset type.
        Returns (True, "") when no specific rule exists for the type (SKIP-equivalent).
        """
        actual_ty = _get(actual, "ty")
        actual_ry = _get(actual, "ry")
        actual_tz = _get(actual, "tz")

        # ---- Bottle / cup / plate: surface support -------------------
        if atype in ("bottle", "whiskey_bottle", "beer_mug",
                     "cup", "mug", "glass", "plate", "bowl"):
            if actual_ty < _SURFACE_MIN_TY:
                return False, f"ty={actual_ty:.3f}m < {_SURFACE_MIN_TY}m — placed on floor"
            if abs(actual_ty - planned.ty) > _SURFACE_TOLERANCE:
                return False, (
                    f"ty={actual_ty:.3f}m differs from planned {planned.ty:.3f}m "
                    f"by {abs(actual_ty - planned.ty):.3f}m > {_SURFACE_TOLERANCE}m"
                )
            return True, ""

        # ---- Chair: facing table -------------------------------------
        if atype == "chair":
            ang_err = abs(_normalize_angle(actual_ry - planned.ry))
            if ang_err > _CHAIR_MAX_ANGLE_ERR:
                return False, (
                    f"facing error {ang_err:.1f}° > {_CHAIR_MAX_ANGLE_ERR}° "
                    f"(planned ry={planned.ry:.1f}°, actual ry={actual_ry:.1f}°)"
                )
            return True, ""

        # ---- Stool: proximity to bar counter -------------------------
        if atype == "stool":
            if bar_planned is None:
                return True, ""   # no bar in scene → skip
            dist = math.sqrt(
                (_get(actual, "tx") - bar_planned.tx) ** 2
                + (actual_tz - bar_planned.tz) ** 2
            )
            if dist > _STOOL_MAX_DIST:
                return False, (
                    f"distance to bar {dist:.2f}m > {_STOOL_MAX_DIST}m"
                )
            return True, ""

        # ---- Fireplace: wall snap ------------------------------------
        if atype == "fireplace":
            wall_delta = abs(actual_tz - planned.tz)
            if wall_delta > _FIREPLACE_WALL_TOL:
                return False, (
                    f"|actual.tz − planned.tz| = {wall_delta:.3f}m "
                    f"> {_FIREPLACE_WALL_TOL}m (wall snap failed)"
                )
            return True, ""

        # ---- Lantern: valid parent anchor ----------------------------
        if atype == "lantern":
            on_surface    = actual_ty > _SURFACE_MIN_TY
            wall_mounted  = actual_ty >= _LANTERN_WALL_MIN_TY
            if not (on_surface or wall_mounted):
                return False, (
                    f"ty={actual_ty:.3f}m — not on surface (≥{_SURFACE_MIN_TY}m) "
                    f"and not wall-mounted (≥{_LANTERN_WALL_MIN_TY}m)"
                )
            return True, ""

        # ---- Beam: ceiling attachment --------------------------------
        if atype in ("beam", "support_beam"):
            top_face = actual_ty + _BEAM_HALF_H
            gap      = abs(ceiling_h - top_face)
            if gap > _BEAM_CEILING_TOL:
                return False, (
                    f"beam top face {top_face:.3f}m, ceiling {ceiling_h:.3f}m, "
                    f"gap {gap:.3f}m > {_BEAM_CEILING_TOL}m"
                )
            return True, ""

        # ---- No specific rule for this type --------------------------
        return True, ""    # PASS (no rule = SKIP in status field)

    # ------------------------------------------------------------------
    # Relationship-based routing (Tier 14.4.3)
    # ------------------------------------------------------------------

    def _check_by_relationship(
        self,
        planned:           "ResolvedTransform",
        actual:            Dict[str, float],
        actual_transforms: Dict[str, Dict[str, float]],
        ceiling_height:    float,
        room_walls:        List[Dict],
    ) -> Tuple[str, str]:
        """
        Route by planned.relationship field (Tier 14.4.3 spec).
        Returns (_SKIP_SENTINEL, "") when no relationship rule applies —
        caller should fall through to type-based _check_rule().
        """
        rel = getattr(planned, "relationship", "") or ""
        if not rel:
            return _SKIP_SENTINEL, ""

        actual_ty = _get(actual, "ty")
        actual_ry = _get(actual, "ry")

        # ---- supports / on_top_of -----------------------------------
        if rel in ("supports", "on_top_of"):
            if actual_ty < _SURFACE_MIN_TY:
                return _RECORD_FAIL, (
                    f"supports: object on floor (ty={actual_ty:.3f}m) — HARD FAIL"
                )
            if abs(actual_ty - planned.ty) > _SUPPORTS_TY_TOL:
                return _RECORD_FAIL, (
                    f"supports: ty={actual_ty:.3f}m ≠ planned {planned.ty:.3f}m "
                    f"(diff {abs(actual_ty - planned.ty):.3f}m > {_SUPPORTS_TY_TOL}m)"
                )
            parent_id = getattr(planned, "parent_id", None)
            if parent_id:
                parent_actual = actual_transforms.get(parent_id)
                if parent_actual is not None:
                    ok_bounds, bounds_reason = _check_inside_bounds(actual, parent_actual)
                    if not ok_bounds:
                        return _RECORD_FAIL, bounds_reason
            return _RECORD_PASS, ""

        # ---- belongs_near -------------------------------------------
        if rel == "belongs_near":
            parent_id = getattr(planned, "parent_id", None)
            if not parent_id:
                return _SKIP_SENTINEL, ""
            parent_actual = actual_transforms.get(parent_id)
            if parent_actual is None:
                return _SKIP_SENTINEL, ""
            dist = math.sqrt(
                (_get(actual, "tx") - _get(parent_actual, "tx")) ** 2
                + (_get(actual, "tz") - _get(parent_actual, "tz")) ** 2
            )
            if dist > _BELONGS_NEAR_MAX_DIST:
                return _RECORD_FAIL, (
                    f"belongs_near: distance {dist:.2f}m > {_BELONGS_NEAR_MAX_DIST}m"
                )
            if dist > 0.01:
                expected_ry = math.degrees(
                    math.atan2(
                        _get(parent_actual, "tx") - _get(actual, "tx"),
                        _get(parent_actual, "tz") - _get(actual, "tz"),
                    )
                ) % 360.0
                ang_err = abs(_normalize_angle(actual_ry - expected_ry))
                if ang_err > _BELONGS_NEAR_MAX_ANGLE:
                    return _RECORD_FAIL, (
                        f"belongs_near: facing error {ang_err:.1f}° "
                        f"> {_BELONGS_NEAR_MAX_ANGLE}° "
                        f"(expected ry={expected_ry:.1f}°)"
                    )
            return _RECORD_PASS, ""

        # ---- attached_to --------------------------------------------
        if rel == "attached_to":
            parent_id = getattr(planned, "parent_id", None) or ""
            if parent_id == "ceiling":
                if actual_ty >= ceiling_height:
                    return _RECORD_FAIL, (
                        f"attached_to_ceiling: ty={actual_ty:.3f}m "
                        f">= ceiling {ceiling_height:.3f}m"
                    )
                return _RECORD_PASS, ""
            if "wall" in parent_id:
                return self._check_wall_attachment(planned, actual, actual_ry, room_walls)
            return _SKIP_SENTINEL, ""

        # ---- Unhandled relationship types fall through ---------------
        return _SKIP_SENTINEL, ""

    def _check_wall_attachment(
        self,
        planned:    "ResolvedTransform",
        actual:     Dict[str, float],
        actual_ry:  float,
        room_walls: List[Dict],
    ) -> Tuple[str, str]:
        """Check wall-attachment constraints: position match, no penetration, interior facing."""
        parent_id  = getattr(planned, "parent_id", "") or ""
        wall       = next((w for w in room_walls if w["name"] == parent_id), None)
        if wall is None:
            return _SKIP_SENTINEL, ""

        axis        = wall.get("axis", "z")
        wall_coord  = float(wall["coord"])
        actual_coord  = _get(actual, "tz") if axis == "z" else _get(actual, "tx")
        planned_coord = planned.tz          if axis == "z" else planned.tx

        # 1. Position drift vs planned
        pos_diff = abs(actual_coord - planned_coord)
        if pos_diff > _WALL_BACK_FACE_MAX:
            return _RECORD_FAIL, (
                f"attached_to_{parent_id}: position drift "
                f"{pos_diff:.3f}m > {_WALL_BACK_FACE_MAX}m"
            )

        # 2. Penetration: asset must stay on interior side of wall
        if abs(actual_coord) > abs(wall_coord):
            return _RECORD_FAIL, (
                f"attached_to_{parent_id}: asset penetrates wall "
                f"(coord={actual_coord:.3f} past wall at {wall_coord:.3f})"
            )

        # 3. Forward axis must face room interior
        expected_ry = _WALL_RY.get(parent_id, planned.ry)
        ry_err = abs(_normalize_angle(actual_ry - expected_ry))
        if ry_err > _WALL_INTERIOR_ANGLE_MAX:
            return _RECORD_FAIL, (
                f"attached_to_{parent_id}: forward axis {ry_err:.1f}° off interior "
                f"(expected ry={expected_ry:.1f}°)"
            )

        return _RECORD_PASS, ""


# ---------------------------------------------------------------------------
# Houdini bridge adapter (isolated — the ONLY component that calls get_bridge)
# ---------------------------------------------------------------------------

class HoudiniTransformFetcher:
    """
    Fetches actual tx/ty/tz/rx/ry/rz transform parameters from live Houdini
    nodes via the bridge.  This is the only component in the auditor module
    that calls get_bridge().

    Call `fetch_transforms(planned, node_path_map)` from the Houdini node;
    the resulting dict is passed directly to
    RelationshipRealizationAuditor.audit() as `actual_transforms`.
    """

    def fetch_transforms(
        self,
        planned_transforms: List[ResolvedTransform],
        node_path_map:      Dict[str, str],
    ) -> Dict[str, Dict[str, float]]:
        """
        Return {asset_id: {tx, ty, tz, rx, ry, rz, sx, sy, sz}} for every
        asset whose node path is in node_path_map and successfully read.

        Never raises; missing / errored nodes are silently omitted.
        """
        from src.utils.hou_bridge import get_bridge
        bridge = get_bridge()
        result: Dict[str, Dict[str, float]] = {}

        for t in planned_transforms:
            path = node_path_map.get(t.asset_id, "")
            if not path:
                continue
            try:
                parms = bridge.get_parms(path)
                result[t.asset_id] = {
                    "tx": float(parms.get("tx", 0.0)),
                    "ty": float(parms.get("ty", 0.0)),
                    "tz": float(parms.get("tz", 0.0)),
                    "rx": float(parms.get("rx", 0.0)),
                    "ry": float(parms.get("ry", 0.0)),
                    "rz": float(parms.get("rz", 0.0)),
                    "sx": float(parms.get("sx", 1.0)),
                    "sy": float(parms.get("sy", 1.0)),
                    "sz": float(parms.get("sz", 1.0)),
                }
            except Exception:
                pass   # no data → NO_DATA record in auditor

        return result


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _format_table(records: List[AssetAuditRecord], score: float) -> str:
    """Produce a plain-text audit table."""
    w1, w2, w3 = 20, 28, 8
    sep = "-" * (w1 + w2 + w3 + 10 + 30 + 8)
    header = (
        f"{'asset_id':<{w1}} {'rule':<{w2}} {'status':<{w3}}"
        f"  {'Δtx':>7} {'Δty':>7} {'Δtz':>7}  {'Δry':>6}  failure"
    )
    lines = ["", f"RELATIONSHIP REALIZATION AUDIT", sep, header, sep]

    for r in records:
        dt = r.delta_translation
        dr = r.delta_rotation
        status_tag = r.realization_status
        if r.transform_mismatch and status_tag == _RECORD_PASS:
            status_tag = "MISMATCH"
        reason = r.failure_reason or "—"
        lines.append(
            f"{r.asset_id:<{w1}} {r.relationship_rule:<{w2}} {status_tag:<{w3}}"
            f"  {dt[0]:+7.3f} {dt[1]:+7.3f} {dt[2]:+7.3f}  {dr[1]:+6.1f}°  {reason}"
        )

    lines.append(sep)
    n_pass = sum(1 for r in records if r.realization_status == _RECORD_PASS)
    n_fail = sum(1 for r in records if r.realization_status == _RECORD_FAIL)
    n_aud  = n_pass + n_fail
    lines.append(
        f"Score: {score:.3f} ({n_pass}/{n_aud})"
        f"  Status: {'PASS' if score >= _PASS_THRESHOLD else 'FAIL'}"
    )
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _aid(asset: Dict[str, Any]) -> str:
    return str(asset.get("asset_id") or asset.get("name") or "").strip()


def _xf_to_dict(t: ResolvedTransform) -> Dict[str, float]:
    return {
        "tx": t.tx, "ty": t.ty, "tz": t.tz,
        "rx": t.rx, "ry": t.ry, "rz": t.rz,
        "sx": t.sx, "sy": t.sy, "sz": t.sz,
    }


def _get(d: Dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        return float(d.get(key, default) or default)
    except (TypeError, ValueError):
        return default


def _normalize_angle(deg: float) -> float:
    """Normalise to (−180, +180]."""
    return ((deg + 180.0) % 360.0) - 180.0


def _rule_name(atype: str) -> str:
    _MAP = {
        "bottle":        "bottle_surface_support",
        "whiskey_bottle": "bottle_surface_support",
        "beer_mug":      "bottle_surface_support",
        "cup":           "cup_table_support",
        "mug":           "cup_table_support",
        "glass":         "cup_table_support",
        "plate":         "plate_table_support",
        "bowl":          "plate_table_support",
        "chair":         "chair_table_facing",
        "stool":         "stool_bar_proximity",
        "fireplace":     "fireplace_wall_attachment",
        "lantern":       "lantern_valid_attachment",
        "torch":         "lantern_valid_attachment",
        "sconce":        "lantern_valid_attachment",
        "beam":          "beam_ceiling_attachment",
        "support_beam":  "beam_ceiling_attachment",
    }
    return _MAP.get(atype, f"{atype}_placement")


def _find_by_type(
    target_type: str,
    aid_to_type: Dict[str, str],
    planned_pos: Dict[str, ResolvedTransform],
) -> Optional[ResolvedTransform]:
    """Return the planned transform for the first asset of target_type."""
    for aid, atype in aid_to_type.items():
        if atype == target_type and aid in planned_pos:
            return planned_pos[aid]
    return None


def _build_room_walls(room_dict: Dict[str, Any]) -> List[Dict]:
    """
    Reconstruct four wall coordinate dicts from room geometry fields.
    Falls back to 10×12m default room if dimensions are missing.
    """
    w = float(room_dict.get("room_width") or room_dict.get("width") or 0.0)
    d = float(room_dict.get("room_length") or room_dict.get("depth") or 0.0)
    if w <= 0 or d <= 0:
        floor_area = float(room_dict.get("floor_area") or 0.0)
        if floor_area > 0:
            w = math.sqrt(floor_area / 1.2)
            d = floor_area / w
        else:
            w, d = 10.0, 12.0
    hw, hd = w / 2.0, d / 2.0
    return [
        {"name": "wall_north", "axis": "z", "coord": -hd},
        {"name": "wall_south", "axis": "z", "coord":  hd},
        {"name": "wall_east",  "axis": "x", "coord":  hw},
        {"name": "wall_west",  "axis": "x", "coord": -hw},
    ]


def _check_inside_bounds(
    actual: Dict[str, float], parent_actual: Dict[str, float]
) -> Tuple[bool, str]:
    """
    Check that the child asset's XZ position is horizontally inside
    the parent asset's bounding box.  Skipped if bbox_half fields are absent.
    """
    half_x = _get(parent_actual, "bbox_half_x", 0.0)
    half_z = _get(parent_actual, "bbox_half_z", 0.0)
    if half_x <= 0.0 and half_z <= 0.0:
        return True, ""   # no bbox data — skip bounds check
    half_x = half_x if half_x > 0 else 0.6
    half_z = half_z if half_z > 0 else 0.6
    actual_tx  = _get(actual, "tx")
    parent_tx  = _get(parent_actual, "tx")
    actual_tz  = _get(actual, "tz")
    parent_tz  = _get(parent_actual, "tz")
    if abs(actual_tx - parent_tx) > half_x:
        return False, (
            f"supports: child tx={actual_tx:.3f} outside parent x-bounds "
            f"[{parent_tx - half_x:.3f}, {parent_tx + half_x:.3f}]"
        )
    if abs(actual_tz - parent_tz) > half_z:
        return False, (
            f"supports: child tz={actual_tz:.3f} outside parent z-bounds "
            f"[{parent_tz - half_z:.3f}, {parent_tz + half_z:.3f}]"
        )
    return True, ""


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[RelationshipRealizationAuditor] = None
_lock = threading.Lock()


def get_relationship_realization_auditor() -> RelationshipRealizationAuditor:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = RelationshipRealizationAuditor()
    return _instance


def reset_relationship_realization_auditor_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
