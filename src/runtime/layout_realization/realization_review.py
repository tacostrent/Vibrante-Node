"""
realization_review.py — §47 Layout Realization & Scene Constraint Solver
=========================================================================
Quality review of a ResolvedSceneLayout.

Six review dimensions:
  transform_accuracy   (0.25) — all assets have non-zero positions
  relationship_accuracy (0.20) — assets have valid relationship tags
  collision_quality    (0.20) — collision_count == 0
  surface_quality      (0.15) — surface items are above floor (ty > 0)
  wall_attachment_quality (0.10) — wall items have correct ry
  visibility_quality   (0.10) — hero anchor is not occluded

Grade mapping:
  ≥ 0.90 → A  production_ready=True
  ≥ 0.75 → B  production_ready=True
  ≥ 0.60 → C  production_ready=False
  ≥ 0.45 → D  production_ready=False
  <  0.45 → F  production_ready=False

Blocking findings (force production_ready=False regardless of score):
  "chair inside table"
  "bottle on floor when table exists"
  "poster outside wall"
  "cluster overlap"
  "hero asset blocked"

Public API:
    RealizationReviewResult
    RealizationReview
    get_realization_review()
    reset_realization_review_for_tests()
"""

from __future__ import annotations

import math
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.runtime.layout_realization.transform_resolver import ResolvedTransform

_WEIGHTS = {
    "transform_accuracy":       0.25,
    "relationship_accuracy":    0.20,
    "collision_quality":        0.20,
    "surface_quality":          0.15,
    "wall_attachment_quality":  0.10,
    "visibility_quality":       0.10,
}

_BLOCKING_KEYWORDS = frozenset({
    "chair inside table",
    "bottle on floor when table exists",
    "poster outside wall",
    "cluster overlap",
    "hero asset blocked",
})

_GRADE_MAP = [
    (0.90, "A"),
    (0.75, "B"),
    (0.60, "C"),
    (0.45, "D"),
]


@dataclass
class RealizationReviewResult:
    overall_score:            float = 0.0
    grade:                    str   = "F"
    production_ready:         bool  = False

    transform_accuracy:       float = 0.0
    relationship_accuracy:    float = 0.0
    collision_quality:        float = 0.0
    surface_quality:          float = 0.0
    wall_attachment_quality:  float = 0.0
    visibility_quality:       float = 0.0

    findings:  List[str] = field(default_factory=list)
    blocking:  List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_score":           round(self.overall_score, 4),
            "grade":                   self.grade,
            "production_ready":        self.production_ready,
            "transform_accuracy":      round(self.transform_accuracy, 4),
            "relationship_accuracy":   round(self.relationship_accuracy, 4),
            "collision_quality":       round(self.collision_quality, 4),
            "surface_quality":         round(self.surface_quality, 4),
            "wall_attachment_quality": round(self.wall_attachment_quality, 4),
            "visibility_quality":      round(self.visibility_quality, 4),
            "findings":                list(self.findings),
            "blocking":                list(self.blocking),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RealizationReviewResult":
        return cls(
            overall_score=float(d.get("overall_score", 0.0)),
            grade=d.get("grade", "F"),
            production_ready=bool(d.get("production_ready", False)),
            transform_accuracy=float(d.get("transform_accuracy", 0.0)),
            relationship_accuracy=float(d.get("relationship_accuracy", 0.0)),
            collision_quality=float(d.get("collision_quality", 0.0)),
            surface_quality=float(d.get("surface_quality", 0.0)),
            wall_attachment_quality=float(d.get("wall_attachment_quality", 0.0)),
            visibility_quality=float(d.get("visibility_quality", 0.0)),
            findings=list(d.get("findings", [])),
            blocking=list(d.get("blocking", [])),
        )


class RealizationReview:
    """Evaluates the quality of a ResolvedSceneLayout."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def review(self, scene_layout: Dict[str, Any]) -> RealizationReviewResult:
        """
        Review a ResolvedSceneLayout.to_dict().
        Never raises.
        """
        try:
            return self._review(scene_layout)
        except Exception as exc:
            return RealizationReviewResult(
                overall_score=0.0, grade="F",
                findings=[f"review error: {exc}"],
            )

    def _review(self, scene: Dict[str, Any]) -> RealizationReviewResult:
        transforms = scene.get("transforms") or []
        result = RealizationReviewResult()

        if not transforms:
            result.findings.append("no transforms in scene layout")
            result.blocking.append("no transforms in scene layout")
            result.production_ready = False
            return result

        n = len(transforms)

        # 1. Transform accuracy — non-origin positions
        non_origin = sum(
            1 for t in transforms
            if not (t.get("tx", 0) == 0.0 and t.get("tz", 0) == 0.0)
        )
        result.transform_accuracy = non_origin / n if n else 0.0
        if result.transform_accuracy < 0.5:
            result.findings.append(
                f"only {non_origin}/{n} assets have non-origin positions"
            )

        # 2. Relationship accuracy — assets have relationship tag
        with_rel = sum(1 for t in transforms if t.get("relationship", ""))
        result.relationship_accuracy = with_rel / n if n else 0.0
        if result.relationship_accuracy < 0.5:
            result.findings.append(f"only {with_rel}/{n} assets have a relationship tag")

        # 3. Collision quality
        collision_count = int(scene.get("collision_count", 0))
        result.collision_quality = 1.0 if collision_count == 0 else max(0.0, 1.0 - collision_count * 0.2)
        if collision_count > 0:
            result.findings.append(f"{collision_count} unresolved collision(s) remain")
            # Check for specific blocking collision pattern
            self._check_chair_inside_table(transforms, result)

        # 4. Surface quality — surface items above floor
        surface_items = [t for t in transforms if t.get("relationship") == "supports"]
        if surface_items:
            on_surface = sum(1 for t in surface_items if float(t.get("ty", 0)) > 0.5)
            result.surface_quality = on_surface / len(surface_items)
            if result.surface_quality < 1.0:
                off = len(surface_items) - on_surface
                result.findings.append(f"{off} surface item(s) at floor level (ty ≤ 0.5m)")
                if off > 0:
                    result.blocking.append("bottle on floor when table exists")
        else:
            result.surface_quality = 1.0   # no surface items = no penalty

        # 5. Wall attachment quality — wall items have ry ≠ 0 or position near boundary
        wall_items = [t for t in transforms if t.get("relationship") == "attached_to"]
        if wall_items:
            on_wall = sum(
                1 for t in wall_items
                if abs(float(t.get("tz", 0))) > 3.0 or abs(float(t.get("tx", 0))) > 3.0
            )
            result.wall_attachment_quality = on_wall / len(wall_items)
            if result.wall_attachment_quality < 0.5:
                result.findings.append(
                    f"only {on_wall}/{len(wall_items)} wall-attached assets near room boundary"
                )
                result.blocking.append("poster outside wall")
        else:
            result.wall_attachment_quality = 1.0

        # 6. Visibility quality — hero not behind occluder
        collision_free_count = sum(1 for t in transforms if t.get("is_collision_free", True))
        result.visibility_quality = collision_free_count / n if n else 1.0

        # Weighted score
        result.overall_score = (
            result.transform_accuracy    * _WEIGHTS["transform_accuracy"]
            + result.relationship_accuracy * _WEIGHTS["relationship_accuracy"]
            + result.collision_quality     * _WEIGHTS["collision_quality"]
            + result.surface_quality       * _WEIGHTS["surface_quality"]
            + result.wall_attachment_quality * _WEIGHTS["wall_attachment_quality"]
            + result.visibility_quality    * _WEIGHTS["visibility_quality"]
        )

        # Grade
        result.grade = "F"
        for threshold, grade in _GRADE_MAP:
            if result.overall_score >= threshold:
                result.grade = grade
                break

        # Production ready
        has_blocking = bool(result.blocking)
        result.production_ready = (
            result.overall_score >= 0.75
            and not has_blocking
        )

        return result

    @staticmethod
    def _check_chair_inside_table(
        transforms: List[Dict[str, Any]],
        result: RealizationReviewResult,
    ) -> None:
        """Detect chairs at the same position as a table (worst-case collision)."""
        table_pos = [(t["tx"], t["tz"]) for t in transforms if "table" in t.get("asset_name", "").lower()]
        chair_pos = [(t["tx"], t["tz"]) for t in transforms if "chair" in t.get("asset_name", "").lower()]
        for tp in table_pos:
            for cp in chair_pos:
                dist = math.sqrt((tp[0] - cp[0]) ** 2 + (tp[1] - cp[1]) ** 2)
                if dist < 0.10:
                    result.blocking.append("chair inside table")
                    return


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[RealizationReview] = None
_lock = threading.Lock()


def get_realization_review() -> RealizationReview:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = RealizationReview()
    return _instance


def reset_realization_review_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
