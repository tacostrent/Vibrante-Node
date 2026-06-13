"""
validation_review.py — §53 Scene Reality Validation (Tier 14.3)
================================================================
Final quality review of a SceneValidationResult.

Five review dimensions:
    support_accuracy    (0.25) — support violations == 0
    occupancy_accuracy  (0.25) — occupancy violations == 0
    relationship_health (0.20) — relationship_failures count
    plausibility_health (0.20) — plausibility_score
    orphan_health       (0.10) — orphan_objects count

Grade mapping:
    >= 0.95 → A  production_ready=True
    >= 0.80 → B  production_ready=True
    >= 0.65 → C  production_ready=False
    >= 0.50 → D  production_ready=False
    <  0.50 → F  production_ready=False

production_ready additionally requires all three composite verdicts to be True.

Public API:
    ValidationReviewResult
    ValidationReview
    get_validation_review()
    reset_validation_review_for_tests()
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_WEIGHTS = {
    "support_accuracy":    0.25,
    "occupancy_accuracy":  0.25,
    "relationship_health": 0.20,
    "plausibility_health": 0.20,
    "orphan_health":       0.10,
}

_GRADE_MAP = [
    (0.95, "A"),
    (0.80, "B"),
    (0.65, "C"),
    (0.50, "D"),
]


@dataclass
class ValidationReviewResult:
    overall_score:        float = 0.0
    grade:                str   = "F"
    production_ready:     bool  = False

    support_accuracy:     float = 0.0
    occupancy_accuracy:   float = 0.0
    relationship_health:  float = 0.0
    plausibility_health:  float = 0.0
    orphan_health:        float = 0.0

    # Composite verdict pass-through
    geometry_valid:       bool  = False
    semantic_valid:       bool  = False
    plausibility_valid:   bool  = False

    findings: List[str] = field(default_factory=list)
    blocking: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_score":       round(self.overall_score, 4),
            "grade":               self.grade,
            "production_ready":    self.production_ready,
            "support_accuracy":    round(self.support_accuracy, 4),
            "occupancy_accuracy":  round(self.occupancy_accuracy, 4),
            "relationship_health": round(self.relationship_health, 4),
            "plausibility_health": round(self.plausibility_health, 4),
            "orphan_health":       round(self.orphan_health, 4),
            "geometry_valid":      self.geometry_valid,
            "semantic_valid":      self.semantic_valid,
            "plausibility_valid":  self.plausibility_valid,
            "findings":            list(self.findings),
            "blocking":            list(self.blocking),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ValidationReviewResult":
        return cls(
            overall_score=float(d.get("overall_score", 0.0)),
            grade=d.get("grade", "F"),
            production_ready=bool(d.get("production_ready", False)),
            support_accuracy=float(d.get("support_accuracy", 0.0)),
            occupancy_accuracy=float(d.get("occupancy_accuracy", 0.0)),
            relationship_health=float(d.get("relationship_health", 0.0)),
            plausibility_health=float(d.get("plausibility_health", 0.0)),
            orphan_health=float(d.get("orphan_health", 0.0)),
            geometry_valid=bool(d.get("geometry_valid", False)),
            semantic_valid=bool(d.get("semantic_valid", False)),
            plausibility_valid=bool(d.get("plausibility_valid", False)),
            findings=list(d.get("findings", [])),
            blocking=list(d.get("blocking", [])),
        )


class ValidationReview:
    """Scores a SceneValidationResult across five dimensions."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def review(self, validation_result: Dict[str, Any]) -> ValidationReviewResult:
        """Score a SceneValidationResult.to_dict(). Never raises."""
        try:
            return self._review(validation_result)
        except Exception as exc:
            return ValidationReviewResult(findings=[f"review error: {exc}"])

    def _review(self, vr: Dict[str, Any]) -> ValidationReviewResult:
        result = ValidationReviewResult()

        # 1. Support accuracy
        n_sv = len(vr.get("support_violations") or [])
        result.support_accuracy = max(0.0, 1.0 - n_sv * 0.25)
        if n_sv:
            result.blocking.append(f"{n_sv} INVALID_SUPPORT_RELATION violation(s)")

        # 2. Occupancy accuracy
        n_ov = len(vr.get("occupancy_violations") or [])
        result.occupancy_accuracy = max(0.0, 1.0 - n_ov * 0.25)
        if n_ov:
            result.blocking.append(f"{n_ov} OCCUPANCY_VIOLATION(s)")

        # 3. Relationship health
        n_rf = len(vr.get("relationship_failures") or [])
        result.relationship_health = max(0.0, 1.0 - n_rf * 0.10)
        if n_rf:
            result.findings.append(f"{n_rf} RELATIONSHIP_FAILURE(s)")

        # 4. Plausibility health (direct from plausibility_score)
        p_score = float(vr.get("plausibility_score", 0.0))
        result.plausibility_health = p_score
        if p_score < 0.90:
            result.findings.append(
                f"plausibility_score={p_score:.2f} below 0.90 threshold"
            )

        # 5. Orphan health
        n_orphans = len(vr.get("orphan_objects") or [])
        result.orphan_health = max(0.0, 1.0 - n_orphans * 0.15)
        if n_orphans:
            result.findings.append(f"{n_orphans} ORPHAN_OBJECT(s) detected")

        # Weighted score
        result.overall_score = (
            result.support_accuracy    * _WEIGHTS["support_accuracy"]
            + result.occupancy_accuracy  * _WEIGHTS["occupancy_accuracy"]
            + result.relationship_health * _WEIGHTS["relationship_health"]
            + result.plausibility_health * _WEIGHTS["plausibility_health"]
            + result.orphan_health       * _WEIGHTS["orphan_health"]
        )

        # Grade
        result.grade = "F"
        for threshold, grade in _GRADE_MAP:
            if result.overall_score >= threshold:
                result.grade = grade
                break

        # Composite verdicts (pass-through)
        result.geometry_valid     = bool(vr.get("geometry_valid", False))
        result.semantic_valid     = bool(vr.get("semantic_valid", False))
        result.plausibility_valid = bool(vr.get("plausibility_valid", False))

        result.production_ready = (
            result.geometry_valid
            and result.semantic_valid
            and result.plausibility_valid
            and result.overall_score >= 0.80
            and not result.blocking
        )

        return result


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[ValidationReview] = None
_lock = threading.Lock()


def get_validation_review() -> ValidationReview:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = ValidationReview()
    return _instance


def reset_validation_review_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
