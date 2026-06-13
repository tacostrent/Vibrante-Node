"""
Spatial Review (Tier 9.4 — Real Asset Spatial Intelligence)
===========================================================
Evaluates the spatial quality of a placed-asset scene across five
production dimensions:

  - Collision    — are any assets intersecting?   (weight 0.35)
  - Clearance    — are minimum separation rules met?  (weight 0.25)
  - Semantic     — are assets in semantically preferred zones?  (weight 0.20)
  - Walkability  — is sufficient floor space preserved?  (weight 0.20)
  - Layout       — composite of the above four.

Hard rule: collision_count > 0 → production_ready = False regardless of score.

DESIGN RULES:
  1. No Houdini imports.  No bridge calls.  Advisory only.
  2. Deterministic — same input → same review.
  3. collision_count > 0 is a hard block on production_ready.
  4. Every finding names the specific failing criterion.
  5. Never raises.

Public API:
    SpatialReviewResult
    SpatialReview
    get_spatial_review()
    reset_spatial_review_for_tests()
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.runtime.assets.assembly.spatial_metadata import SpatialMetadata
from src.runtime.assets.assembly.collision_detector import get_collision_detector
from src.runtime.assets.assembly.clearance_validator import get_clearance_validator
from src.runtime.assets.assembly.semantic_placement_rules import get_semantic_placement_rules

_PRODUCTION_THRESHOLD = 0.70


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class SpatialReviewResult:
    """Full spatial quality review of a placed-asset scene."""

    review_id:         str   = field(default_factory=lambda: f"spatial_{uuid.uuid4().hex[:10]}")
    environment:       str   = ""

    # Dimension scores (0.0 – 1.0)
    collision_score:   float = 0.0
    clearance_score:   float = 0.0
    semantic_score:    float = 0.0
    walkability_score: float = 0.0
    layout_score:      float = 0.0
    overall_score:     float = 0.0

    grade:            str  = "F"
    production_ready: bool = False

    # Raw counts (mirrored into EnvironmentReview when requested)
    collision_count:          int   = 0
    clearance_violations:     int   = 0
    semantic_placement_score: float = 0.0
    walkability_fraction:     float = 0.0
    layout_quality_score:     float = 0.0

    findings:        List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    review_summary:  str  = ""
    generated_at:    float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "review_id":               self.review_id,
            "environment":             self.environment,
            "collision_score":         self.collision_score,
            "clearance_score":         self.clearance_score,
            "semantic_score":          self.semantic_score,
            "walkability_score":       self.walkability_score,
            "layout_score":            self.layout_score,
            "overall_score":           self.overall_score,
            "grade":                   self.grade,
            "production_ready":        self.production_ready,
            "collision_count":         self.collision_count,
            "clearance_violations":    self.clearance_violations,
            "semantic_placement_score": self.semantic_placement_score,
            "walkability_fraction":    self.walkability_fraction,
            "layout_quality_score":    self.layout_quality_score,
            "findings":                list(self.findings),
            "recommendations":         list(self.recommendations),
            "review_summary":          self.review_summary,
            "generated_at":            self.generated_at,
        }


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class SpatialReview:
    """
    Evaluates the spatial quality of a placed-asset scene.
    collision_count > 0 is always a hard block on production_ready.
    """

    def review_placement(
        self,
        environment:      str,
        placements:       List[Tuple[str, Tuple[float, float, float], SpatialMetadata]],
        zone_placements:  Optional[List[Dict[str, Any]]] = None,
        scene_floor_area: float = 200.0,
    ) -> SpatialReviewResult:
        """
        Full spatial review.

        Args:
            environment:      Name of the environment being reviewed.
            placements:       list of (asset_id, position_xyz, SpatialMetadata)
            zone_placements:  optional list of {"asset_id", "zone_name", "placement_type"}
                              for semantic scoring (inferred from metadata if omitted)
            scene_floor_area: total floor area in m² (default 200 m²)

        Returns:
            SpatialReviewResult.  Never raises.
        """
        result = SpatialReviewResult(environment=environment)
        try:
            n = len(placements)

            # ---- Collision -------------------------------------------------
            col_report = get_collision_detector().validate_scene(placements)
            result.collision_count = col_report.collision_count
            result.collision_score = (
                1.0 if col_report.ok
                else max(0.0, 1.0 - col_report.collision_count / max(n, 1))
            )
            for pair in col_report.pairs:
                result.findings.append(
                    f"Collision: '{pair.asset_a}' intersects '{pair.asset_b}' "
                    f"(overlap {pair.overlap_x:.2f} × {pair.overlap_z:.2f} m)."
                )

            # ---- Clearance -------------------------------------------------
            clr_report = get_clearance_validator().validate_scene_clearance(placements)
            result.clearance_violations = clr_report.violation_count
            result.clearance_score = (
                1.0 if clr_report.ok
                else max(0.0, 1.0 - clr_report.violation_count / max(n, 1))
            )
            for v in clr_report.violations[:5]:
                result.findings.append(
                    f"Clearance: '{v.asset_a}' ({v.type_a}) ↔ '{v.asset_b}' ({v.type_b}): "
                    f"{v.actual_clearance:.2f} m actual, {v.required_clearance:.2f} m required."
                )

            # ---- Semantic --------------------------------------------------
            sem_data = zone_placements or [
                {
                    "asset_id":       aid,
                    "zone_name":      "",
                    "placement_type": meta.placement_type,
                }
                for aid, _pos, meta in placements
            ]
            sem_result = get_semantic_placement_rules().evaluate_semantic_compliance(sem_data)
            result.semantic_score           = sem_result["score"]
            result.semantic_placement_score = sem_result["score"]
            for v in sem_result["violations"][:3]:
                result.findings.append(v)

            # ---- Walkability -----------------------------------------------
            occupied = sum(
                meta.footprint_area
                for _id, _pos, meta in placements
                if meta.walkable_obstacle
            )
            walkable = max(0.0, 1.0 - occupied / max(scene_floor_area, 1.0))
            result.walkability_fraction = walkable
            result.walkability_score    = walkable
            if walkable < 0.3:
                result.findings.append(
                    f"Walkability critically low — {walkable:.0%} free floor space. "
                    "Remove large obstacles or reduce asset density."
                )
            elif walkable < 0.5:
                result.findings.append(
                    f"Walkability below recommended threshold — {walkable:.0%} free floor space."
                )

            # ---- Layout (composite) ----------------------------------------
            layout = (
                result.collision_score  * 0.35 +
                result.clearance_score  * 0.25 +
                result.semantic_score   * 0.20 +
                result.walkability_score * 0.20
            )
            result.layout_score       = layout
            result.layout_quality_score = layout
            result.overall_score       = layout

            # ---- Grade & production_ready ----------------------------------
            result.grade = _grade(result.overall_score)
            result.production_ready = (
                result.overall_score >= _PRODUCTION_THRESHOLD
                and result.collision_count == 0   # hard block
            )

            result.recommendations = _build_recommendations(result)
            result.review_summary  = _build_summary(result)

        except Exception as exc:
            result.findings.append(f"Spatial review engine error: {exc}")
            result.review_summary = f"Spatial review failed: {exc}"

        return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _grade(score: float) -> str:
    if score >= 0.90: return "A"
    if score >= 0.80: return "B"
    if score >= 0.70: return "C"
    if score >= 0.55: return "D"
    return "F"


def _build_recommendations(r: SpatialReviewResult) -> List[str]:
    recs: List[str] = []
    if r.collision_count > 0:
        recs.append(
            f"Resolve {r.collision_count} collision(s) before finalizing layout. "
            "Use hou_mcp_layout_optimizer to reposition affected assets."
        )
    if r.clearance_violations > 0:
        recs.append(
            f"Address {r.clearance_violations} clearance violation(s). "
            "Increase separation between machines, vehicles, and walls."
        )
    if r.semantic_score < 0.6:
        recs.append(
            "Improve semantic placement — move assets to preferred zones "
            "(chairs near tables, buckets near walls, machines in hero_zone)."
        )
    if r.walkability_fraction < 0.5:
        recs.append(
            "Preserve walkable space — at least 50 % of floor area must be unobstructed."
        )
    if not recs:
        recs.append("Layout passes spatial validation — proceed to realization.")
    return recs


def _build_summary(r: SpatialReviewResult) -> str:
    if r.production_ready:
        return (
            f"Grade {r.grade} — overall {r.overall_score:.2f}. "
            "No collisions. Clearance and walkability within production bounds."
        )
    issues = []
    if r.collision_count > 0:
        issues.append(f"{r.collision_count} collision(s)")
    if r.clearance_violations > 0:
        issues.append(f"{r.clearance_violations} clearance violation(s)")
    if r.walkability_fraction < 0.5:
        issues.append(f"low walkability ({r.walkability_fraction:.0%})")
    summary = ", ".join(issues) if issues else "quality below threshold"
    return (
        f"Grade {r.grade} — overall {r.overall_score:.2f}. "
        f"Blocking issue(s): {summary}."
    )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_INSTANCE: Optional[SpatialReview] = None
_INSTANCE_LOCK = threading.Lock()


def get_spatial_review() -> SpatialReview:
    """Return the module-level singleton SpatialReview."""
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = SpatialReview()
    return _INSTANCE


def reset_spatial_review_for_tests() -> None:
    """Replace the singleton.  For test isolation only."""
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
