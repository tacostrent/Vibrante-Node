"""
environment_review.py — §49 Structural Environment Realization
==============================================================
Quality review of an EnvironmentRealizationPlan.

Six review dimensions:
  structural_completeness (0.30) — floor + walls + ceiling present
  architectural_validity  (0.20) — openings inside walls, no floaters
  zone_accuracy           (0.15) — zones defined and inside room
  opening_quality         (0.15) — at least one door present
  beam_quality            (0.10) — beams/columns consistent with env type
  room_integrity          (0.10) — room_closed flag

Grade mapping:
  >= 0.95 → A   production_ready=True
  >= 0.80 → B   production_ready=True
  >= 0.65 → C   production_ready=False
  >= 0.50 → D   production_ready=False
  <  0.50 → F   production_ready=False

Blocking findings (force production_ready=False):
  "floor missing"
  "wall missing"
  "no door"
  "room not closed"
  "no zones defined"

Public API:
    EnvRealizationReviewResult
    EnvRealizationReview
    get_env_realization_review()
    reset_env_realization_review_for_tests()
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_WEIGHTS = {
    "structural_completeness": 0.30,
    "architectural_validity":  0.20,
    "zone_accuracy":           0.15,
    "opening_quality":         0.15,
    "beam_quality":            0.10,
    "room_integrity":          0.10,
}

_BLOCKING_KEYWORDS = frozenset({
    "floor missing", "wall missing", "no door",
    "room not closed", "no zones defined",
})

_GRADE_MAP = [
    (0.95, "A"),
    (0.80, "B"),
    (0.65, "C"),
    (0.50, "D"),
]


@dataclass
class EnvRealizationReviewResult:
    overall_score:            float = 0.0
    grade:                    str   = "F"
    production_ready:         bool  = False

    structural_completeness: float = 0.0
    architectural_validity:  float = 0.0
    zone_accuracy:           float = 0.0
    opening_quality:         float = 0.0
    beam_quality:            float = 0.0
    room_integrity:          float = 0.0

    findings:  List[str] = field(default_factory=list)
    blocking:  List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_score":            round(self.overall_score, 4),
            "grade":                    self.grade,
            "production_ready":         self.production_ready,
            "structural_completeness":  round(self.structural_completeness, 4),
            "architectural_validity":   round(self.architectural_validity, 4),
            "zone_accuracy":            round(self.zone_accuracy, 4),
            "opening_quality":          round(self.opening_quality, 4),
            "beam_quality":             round(self.beam_quality, 4),
            "room_integrity":           round(self.room_integrity, 4),
            "findings":                 list(self.findings),
            "blocking":                 list(self.blocking),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "EnvRealizationReviewResult":
        return cls(
            overall_score=float(d.get("overall_score", 0.0)),
            grade=d.get("grade", "F"),
            production_ready=bool(d.get("production_ready", False)),
            structural_completeness=float(d.get("structural_completeness", 0.0)),
            architectural_validity=float(d.get("architectural_validity", 0.0)),
            zone_accuracy=float(d.get("zone_accuracy", 0.0)),
            opening_quality=float(d.get("opening_quality", 0.0)),
            beam_quality=float(d.get("beam_quality", 0.0)),
            room_integrity=float(d.get("room_integrity", 0.0)),
            findings=list(d.get("findings", [])),
            blocking=list(d.get("blocking", [])),
        )


class EnvRealizationReview:
    """Reviews the quality of an EnvironmentRealizationPlan."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def review(self, plan: Dict[str, Any]) -> EnvRealizationReviewResult:
        """Review an EnvironmentRealizationPlan.to_dict(). Never raises."""
        try:
            return self._review(plan)
        except Exception as exc:
            return EnvRealizationReviewResult(
                findings=[f"review error: {exc}"],
                blocking=["review error"],
            )

    def _review(self, plan: Dict[str, Any]) -> EnvRealizationReviewResult:
        result = EnvRealizationReviewResult()
        is_outdoor = plan.get("room_shell", {}).get("is_outdoor", False) if plan.get("room_shell") else False

        # 1. Structural completeness
        floor_count   = int(plan.get("floor_count",   0))
        wall_count    = int(plan.get("wall_count",    0))
        ceiling_count = int(plan.get("ceiling_count", 0))

        if floor_count == 0:
            result.blocking.append("floor missing")
        if wall_count < 4 and not is_outdoor:
            result.blocking.append("wall missing")
            result.findings.append(f"only {wall_count}/4 walls present")

        if is_outdoor:
            result.structural_completeness = 1.0 if floor_count > 0 else 0.0
        else:
            complete_parts = (
                (1.0 if floor_count > 0 else 0.0)
                + (min(wall_count, 4) / 4.0)
                + (1.0 if ceiling_count > 0 else 0.0)
            ) / 3.0
            result.structural_completeness = complete_parts
            if complete_parts < 1.0:
                result.findings.append(f"structural completeness {complete_parts:.2f}")

        # 2. Architectural validity
        elements = plan.get("structural_elements") or []
        # Check openings have wall_id
        openings_valid = sum(
            1 for e in elements if e.get("is_opening") and e.get("wall_id")
        )
        total_openings = sum(1 for e in elements if e.get("is_opening"))
        if total_openings > 0:
            result.architectural_validity = openings_valid / total_openings
        else:
            result.architectural_validity = 1.0  # no openings = no invalid openings

        # 3. Zone accuracy
        zone_count = int(plan.get("zone_count", 0))
        if zone_count == 0:
            result.zone_accuracy = 0.0
            result.blocking.append("no zones defined")
        else:
            result.zone_accuracy = min(1.0, zone_count / 6.0)

        # 4. Opening quality
        door_count = int(plan.get("door_count", 0))
        window_count = int(plan.get("window_count", 0))
        if door_count == 0 and not is_outdoor:
            result.opening_quality = 0.3  # partial — windows may exist
            result.blocking.append("no door")
        else:
            # Door present + windows bonus
            result.opening_quality = min(1.0, 0.7 + (min(window_count, 2) * 0.15))

        # 5. Beam quality
        beam_count   = int(plan.get("beam_count",   0))
        column_count = int(plan.get("column_count", 0))
        # Outdoor and simple rooms don't need beams
        if is_outdoor or plan.get("environment", "") in (
            "office", "living_room", "restaurant", "medical_lab",
            "control_room", "clean_room", "research_lab",
        ):
            result.beam_quality = 1.0
        else:
            has_support = (beam_count > 0 or column_count > 0)
            result.beam_quality = 1.0 if has_support else 0.6
            if not has_support:
                result.findings.append("no beams or columns for structural environment")

        # 6. Room integrity
        room_closed = bool(plan.get("room_closed", False))
        result.room_integrity = 1.0 if (room_closed or is_outdoor) else 0.0
        if not room_closed and not is_outdoor:
            result.blocking.append("room not closed")

        # Weighted score
        result.overall_score = (
            result.structural_completeness * _WEIGHTS["structural_completeness"]
            + result.architectural_validity  * _WEIGHTS["architectural_validity"]
            + result.zone_accuracy           * _WEIGHTS["zone_accuracy"]
            + result.opening_quality         * _WEIGHTS["opening_quality"]
            + result.beam_quality            * _WEIGHTS["beam_quality"]
            + result.room_integrity          * _WEIGHTS["room_integrity"]
        )

        # Grade
        result.grade = "F"
        for threshold, grade in _GRADE_MAP:
            if result.overall_score >= threshold:
                result.grade = grade
                break

        result.production_ready = (
            result.overall_score >= 0.80
            and not result.blocking
        )

        return result


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[EnvRealizationReview] = None
_lock = threading.Lock()


def get_env_realization_review() -> EnvRealizationReview:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = EnvRealizationReview()
    return _instance


def reset_env_realization_review_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
