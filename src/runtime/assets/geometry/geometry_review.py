"""
Geometry Review (Tier 9.7 — Geometry Intelligence)
===================================================
Evaluates the quality of geometry intelligence for one asset across five
production dimensions:

  bbox_validity          (weight 0.30)
  pivot_validity         (weight 0.20)
  surface_detection      (weight 0.25)
  ground_contact_detection (weight 0.15)
  scale_accuracy         (weight 0.10)

Grade mapping:
  ≥ 0.85 → A  (production_ready, if no blocking findings)
  ≥ 0.70 → B  (production_ready, if no blocking findings)
  ≥ 0.55 → C
  ≥ 0.40 → D
  < 0.40 → F

Blocking findings (block production_ready regardless of score):
  "zero dimensions"    — bbox all zeros / below minimum
  "no support surfaces" — surface-providing type has no surfaces detected
  "invalid role"       — role is inconsistent with placement type

Role consistency rules:
  structural placement types  → role must NOT be "furniture" or "prop"
  door / window              → role must NOT be "prop"
  chair / table / bench      → role must NOT be "structure"

DESIGN RULES:
  1. No bridge calls. No Houdini imports.
  2. Deterministic — same AssetMetrics → same review.
  3. Never raises.
  4. Singleton pattern.

Public API:
    GeometryReviewResult
    GeometryReview
    get_geometry_review()
    reset_geometry_review_for_tests()
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.runtime.assets.geometry.asset_metrics import (
    AssetMetrics,
    STRUCTURAL_PLACEMENT_TYPES,
    _SURFACE_PROVIDING_TYPES,   # type: ignore[attr-defined]
)

_PRODUCTION_THRESHOLD = 0.70

# Weights
_W_BBOX    = 0.30
_W_PIVOT   = 0.20
_W_SURFACE = 0.25
_W_CONTACT = 0.15
_W_SCALE   = 0.10

# Placement types that MUST NOT have a furniture/prop role
_STRUCTURAL_ROLE_CONFLICT = frozenset({
    "wall", "column", "beam", "roof", "floor_panel",
    "ceiling", "platform", "door_frame", "arch",
})

# Placement types whose role must not be "structure"
_FURNITURE_TYPES = frozenset({
    "chair", "stool", "table", "desk", "bench", "sofa", "bed",
    "cabinet", "shelf", "wardrobe",
})

# Door/window must not be "prop"
_ARCHITECTURAL_OPENINGS = frozenset({"door", "window"})

# Minimum valid dimension in meters
_MIN_VALID_DIM = 0.001


@dataclass
class GeometryReviewResult:
    """5-dimension geometry quality review."""

    review_id:       str   = field(default_factory=lambda: f"geor_{uuid.uuid4().hex[:10]}")
    asset_id:        str   = ""

    # Dimension scores
    bbox_validity:              float = 0.0
    pivot_validity:             float = 0.0
    surface_detection:          float = 0.0
    ground_contact_detection:   float = 0.0
    scale_accuracy:             float = 0.0
    overall_score:              float = 0.0

    grade:            str  = "F"
    production_ready: bool = False

    findings:        List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    review_summary:  str  = ""
    generated_at:    float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "review_id":                self.review_id,
            "asset_id":                 self.asset_id,
            "bbox_validity":            self.bbox_validity,
            "pivot_validity":           self.pivot_validity,
            "surface_detection":        self.surface_detection,
            "ground_contact_detection": self.ground_contact_detection,
            "scale_accuracy":           self.scale_accuracy,
            "overall_score":            self.overall_score,
            "grade":                    self.grade,
            "production_ready":         self.production_ready,
            "findings":                 list(self.findings),
            "recommendations":          list(self.recommendations),
            "review_summary":           self.review_summary,
            "generated_at":             self.generated_at,
        }


class GeometryReview:
    """Evaluates geometry intelligence quality for one asset."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def review(self, metrics: AssetMetrics) -> GeometryReviewResult:
        """
        Review geometry quality.

        Args:
            metrics: AssetMetrics produced by GeometryAnalyzer.

        Returns:
            GeometryReviewResult. Never raises.
        """
        try:
            return self._review(metrics)
        except Exception as exc:
            r = GeometryReviewResult(asset_id=metrics.asset_id if metrics else "")
            r.findings.append(f"GeometryReview engine error: {exc}")
            r.review_summary = f"Review failed: {exc}"
            return r

    def _review(self, m: AssetMetrics) -> GeometryReviewResult:
        r = GeometryReviewResult(asset_id=m.asset_id)
        blocking: List[str] = []

        # ---- 1. BBox validity (0.30) -----------------------------------
        r.bbox_validity = self._score_bbox(m, r.findings, blocking)

        # ---- 2. Pivot validity (0.20) ----------------------------------
        r.pivot_validity = self._score_pivot(m, r.findings)

        # ---- 3. Surface detection (0.25) -------------------------------
        r.surface_detection = self._score_surfaces(m, r.findings, blocking)

        # ---- 4. Ground contact detection (0.15) ------------------------
        r.ground_contact_detection = self._score_contacts(m, r.findings)

        # ---- 5. Scale accuracy (0.10) ----------------------------------
        r.scale_accuracy = self._score_scale(m, r.findings, blocking)

        # ---- Overall ----------------------------------------------------
        r.overall_score = (
            r.bbox_validity            * _W_BBOX   +
            r.pivot_validity           * _W_PIVOT  +
            r.surface_detection        * _W_SURFACE +
            r.ground_contact_detection * _W_CONTACT +
            r.scale_accuracy           * _W_SCALE
        )

        r.grade = _grade(r.overall_score)
        r.production_ready = (
            r.overall_score >= _PRODUCTION_THRESHOLD
            and len(blocking) == 0
        )

        r.recommendations = _build_recommendations(r, m)
        r.review_summary  = _build_summary(r, blocking)
        return r

    # ------------------------------------------------------------------
    # Dimension scorers
    # ------------------------------------------------------------------

    @staticmethod
    def _score_bbox(
        m: AssetMetrics,
        findings: List[str],
        blocking: List[str],
    ) -> float:
        w, h, d = m.width_m, m.height_m, m.depth_m
        if w < _MIN_VALID_DIM and h < _MIN_VALID_DIM and d < _MIN_VALID_DIM:
            msg = "zero dimensions — all bbox dimensions are at or below minimum."
            findings.append(msg)
            blocking.append("zero dimensions")
            return 0.0

        invalid = sum(1 for v in (w, h, d) if v < _MIN_VALID_DIM)
        if invalid:
            findings.append(
                f"{invalid} bbox dimension(s) below minimum ({_MIN_VALID_DIM} m) — "
                "asset may be degenerate."
            )
            base = 0.5
        else:
            base = 1.0

        # Penalize estimated sources
        if m.source == "estimated":
            base *= 0.75
        elif m.source == "format_metadata":
            base *= 0.90

        return min(1.0, base)

    @staticmethod
    def _score_pivot(m: AssetMetrics, findings: List[str]) -> float:
        pt = m.placement_type

        # Ceiling-mounted types should have top_center
        ceiling_types = {"hanging_light", "pendant_light", "ceiling_mount"}
        if pt in ceiling_types:
            if m.pivot_type == "top_center":
                return 1.0
            findings.append(
                f"Pivot type '{m.pivot_type}' is unexpected for ceiling-mounted "
                f"asset type '{pt}' — expected 'top_center'."
            )
            return 0.6

        # Structural/modular types prefer bottom_left
        modular_types = {"floor_panel", "ceiling_panel", "wall_tile", "modular_wall"}
        if pt in modular_types:
            if m.pivot_type == "bottom_left":
                return 1.0
            return 0.8

        # Floor-placed assets should have bottom_center
        floor_types = {
            "table", "chair", "desk", "machine", "vehicle",
            "cabinet", "shelf", "workbench",
        }
        if pt in floor_types:
            if m.pivot_type == "bottom_center":
                return 1.0
            if m.pivot_type == "custom":
                return 0.7   # custom may be valid
            findings.append(
                f"Pivot type '{m.pivot_type}' may be suboptimal for floor-placed "
                f"type '{pt}' — 'bottom_center' is preferred."
            )
            return 0.7

        # Generic: any known pivot type is acceptable
        if m.pivot_type in ("bottom_center", "center", "bottom_left", "top_center"):
            return 0.9
        if m.pivot_type == "custom":
            return 0.8

        findings.append(f"Unknown pivot type '{m.pivot_type}'.")
        return 0.5

    @staticmethod
    def _score_surfaces(
        m: AssetMetrics,
        findings: List[str],
        blocking: List[str],
    ) -> float:
        pt = m.placement_type

        if pt in _SURFACE_PROVIDING_TYPES:
            if m.support_surfaces:
                return 1.0
            msg = (
                f"no support surfaces detected for surface-providing type '{pt}' — "
                "child asset placement will be disabled."
            )
            findings.append(msg)
            blocking.append("no support surfaces")
            return 0.0

        # Non-surface types: perfect score if empty, penalty if surfaces erroneously present
        if not m.support_surfaces:
            return 1.0

        # Unexpected surfaces on non-surface type
        findings.append(
            f"Unexpected support surfaces ({len(m.support_surfaces)}) on "
            f"type '{pt}' which is not expected to provide surfaces."
        )
        return 0.8

    @staticmethod
    def _score_contacts(m: AssetMetrics, findings: List[str]) -> float:
        # Hanging types: no ground contacts expected
        hanging = {"hanging_light", "pendant_light", "ceiling_mount", "floating_prop"}
        if m.placement_type in hanging:
            if not m.ground_contacts:
                return 1.0
            return 0.8

        if m.ground_contacts:
            total = sum(c.count for c in m.ground_contacts)
            if total >= 1:
                return 1.0
            findings.append("Ground contacts list is present but reports zero contact points.")
            return 0.5

        # No contacts at all for a floor-placed asset
        if m.placement_type and m.placement_type not in hanging:
            findings.append(
                f"No ground contacts detected for '{m.placement_type}' — "
                "floor snapping accuracy may be reduced."
            )
            return 0.6

        return 0.8

    @staticmethod
    def _score_scale(
        m: AssetMetrics,
        findings: List[str],
        blocking: List[str],
    ) -> float:
        pt = m.placement_type
        role = m.role

        # Structural placement type must not be classified as furniture or prop
        if pt in _STRUCTURAL_ROLE_CONFLICT:
            if role in ("furniture", "prop"):
                msg = (
                    f"invalid role '{role}' for structural type '{pt}' — "
                    "structural assets must not be classified as furniture or prop."
                )
                findings.append(msg)
                blocking.append("invalid role")
                return 0.0
            if m.scale_class not in ("structural", "large", "hero"):
                findings.append(
                    f"Structural type '{pt}' classified as '{m.scale_class}' — "
                    "expected structural/large."
                )
                return 0.6
            return 1.0

        # Furniture types must not be classified as structure
        if pt in _FURNITURE_TYPES:
            if role == "structure":
                msg = (
                    f"invalid role 'structure' for furniture type '{pt}' — "
                    "furniture must not be classified as structural."
                )
                findings.append(msg)
                blocking.append("invalid role")
                return 0.0
            return 1.0

        # Door/window must not be a generic prop
        if pt in _ARCHITECTURAL_OPENINGS:
            if role == "prop":
                findings.append(
                    f"Role 'prop' is imprecise for architectural element '{pt}'."
                )
                return 0.7

        # Hero types should be classified as hero or large
        if pt in ("machine", "vehicle", "crane"):
            if m.scale_class not in ("hero", "large", "structural"):
                findings.append(
                    f"Hero-type asset '{pt}' classified as '{m.scale_class}' — "
                    "expected hero/large."
                )
                return 0.7

        return 1.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _grade(score: float) -> str:
    if score >= 0.85: return "A"
    if score >= 0.70: return "B"
    if score >= 0.55: return "C"
    if score >= 0.40: return "D"
    return "F"


def _build_recommendations(r: GeometryReviewResult, m: AssetMetrics) -> List[str]:
    recs: List[str] = []
    if r.bbox_validity < 0.8:
        recs.append(
            "Provide explicit bbox_min / bbox_max fields in the asset metadata for "
            "precise geometry. Run hou_mcp_geometry_metrics to verify."
        )
    if r.surface_detection < 0.7 and m.placement_type in _SURFACE_PROVIDING_TYPES:
        recs.append(
            f"Add support_surfaces metadata to '{m.placement_type}' so child "
            "assets can be placed on it."
        )
    if r.ground_contact_detection < 0.7:
        recs.append(
            "Verify ground contacts — add ground_contacts metadata or correct "
            "placement_type for accurate floor snapping."
        )
    if r.scale_accuracy < 0.8:
        recs.append(
            f"Check scale classification for '{m.placement_type}' — ensure "
            "placement_type matches the asset's physical role."
        )
    if not recs:
        recs.append(
            "Geometry intelligence passed all checks — proceed to placement."
        )
    return recs


def _build_summary(r: GeometryReviewResult, blocking: List[str]) -> str:
    if r.production_ready:
        return (
            f"Grade {r.grade} — overall {r.overall_score:.2f}. "
            "Geometry intelligence validated. Asset ready for placement."
        )
    if blocking:
        return (
            f"Grade {r.grade} — overall {r.overall_score:.2f}. "
            f"Blocking issue(s): {', '.join(blocking)}."
        )
    return (
        f"Grade {r.grade} — overall {r.overall_score:.2f}. "
        "Geometry quality below production threshold."
    )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[GeometryReview] = None
_LOCK = threading.Lock()


def get_geometry_review() -> GeometryReview:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = GeometryReview()
        return _INSTANCE


def reset_geometry_review_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
