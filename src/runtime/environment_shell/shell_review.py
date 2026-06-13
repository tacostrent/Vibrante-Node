"""
ShellReview — Tier 10.4
=========================
6-dimension quality review of a completed EnvironmentShell.

Score weights:
  floor_integrity    0.25
  wall_integrity     0.25
  ceiling_integrity  0.20
  anchor_coverage    0.15
  enclosure_quality  0.10
  phase_completion   0.05

Grade mapping:
  >= 0.90 → A  production_ready = True
  >= 0.75 → B  production_ready = True
  >= 0.60 → C  production_ready = False
  >= 0.45 → D  production_ready = False
  <  0.45 → F  production_ready = False

Blocking findings (force production_ready = False):
  "floor missing"
  "wall missing"
  "ceiling missing"
  "enclosure invalid"
  "no anchors defined"

Never raises.

Public API:
    ShellReviewResult
    ShellReview
    get_shell_review()
    reset_shell_review_for_tests()
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.runtime.environment_shell.environment_shell_state import EnvironmentShell
from src.runtime.environment_shell.shell_phase_result import ALL_PHASE_STATUSES


_BLOCKING_KEYWORDS = (
    "floor missing",
    "wall missing",
    "ceiling missing",
    "enclosure invalid",
    "no anchors defined",
)

_GRADE_THRESHOLDS = (
    (0.90, "A"),
    (0.75, "B"),
    (0.60, "C"),
    (0.45, "D"),
)


@dataclass
class ShellReviewResult:
    environment:        str   = ""
    overall_score:      float = 0.0
    grade:              str   = "F"
    production_ready:   bool  = False
    floor_score:        float = 0.0
    wall_score:         float = 0.0
    ceiling_score:      float = 0.0
    anchor_score:       float = 0.0
    enclosure_score:    float = 0.0
    phase_score:        float = 0.0
    findings:           List[str] = field(default_factory=list)
    recommendations:    List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "environment":      self.environment,
            "overall_score":    round(self.overall_score, 4),
            "grade":            self.grade,
            "production_ready": self.production_ready,
            "floor_score":      round(self.floor_score, 4),
            "wall_score":       round(self.wall_score, 4),
            "ceiling_score":    round(self.ceiling_score, 4),
            "anchor_score":     round(self.anchor_score, 4),
            "enclosure_score":  round(self.enclosure_score, 4),
            "phase_score":      round(self.phase_score, 4),
            "findings":         list(self.findings),
            "recommendations":  list(self.recommendations),
        }


class ShellReview:

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def review(self, shell: EnvironmentShell) -> ShellReviewResult:
        """Review a completed shell. Never raises."""
        try:
            return self._review(shell)
        except Exception as exc:
            r = ShellReviewResult(environment=getattr(shell, "environment", ""))
            r.findings.append(f"ShellReview internal error: {exc}")
            return r

    def review_dict(self, shell_dict: Dict[str, Any]) -> ShellReviewResult:
        """Convenience: accept a dict. Never raises."""
        try:
            shell = EnvironmentShell.from_dict(shell_dict)
            return self.review(shell)
        except Exception as exc:
            r = ShellReviewResult()
            r.findings.append(f"ShellReview.review_dict error: {exc}")
            return r

    def _review(self, shell: EnvironmentShell) -> ShellReviewResult:
        r = ShellReviewResult(environment=shell.environment)
        findings: List[str] = []
        recs:     List[str] = []

        # 1. Floor (0.25)
        if shell.floor_exists and shell.floor_area > 0:
            r.floor_score = 1.0
        elif shell.floor_exists:
            r.floor_score = 0.5
            findings.append("floor area is zero")
        else:
            r.floor_score = 0.0
            findings.append("floor missing")
            recs.append("Run Phase 1 (ShellFloorBuilder) before placement.")

        # 2. Walls (0.25)
        required = 0 if shell.is_outdoor else 4
        if shell.is_outdoor:
            r.wall_score = 1.0
        elif shell.wall_count >= required and shell.walls_form_enclosure:
            r.wall_score = 1.0
        elif shell.wall_count >= required:
            r.wall_score = 0.7
            findings.append("walls built but enclosure not validated")
        elif shell.wall_count > 0:
            r.wall_score = 0.3
            findings.append(f"wall_count={shell.wall_count} < required {required}")
            recs.append("Run Phase 2 (ShellWallBuilder) to build all perimeter walls.")
        else:
            r.wall_score = 0.0
            findings.append("wall missing")
            recs.append("Run Phase 2 (ShellWallBuilder) before placement.")

        # 3. Ceiling (0.20)
        if shell.is_outdoor:
            r.ceiling_score = 1.0
        elif shell.ceiling_exists and shell.ceiling_height > 0:
            r.ceiling_score = 1.0
        elif shell.ceiling_exists:
            r.ceiling_score = 0.5
            findings.append("ceiling exists but height is zero")
        else:
            r.ceiling_score = 0.0
            findings.append("ceiling missing")
            recs.append("Run Phase 3 (ShellCeilingBuilder) before placement.")

        # 4. Anchor coverage (0.15)
        total_anchors = (
            shell.door_anchor_count
            + shell.window_anchor_count
            + shell.beam_anchor_count
        )
        if total_anchors > 0:
            r.anchor_score = 1.0
        elif shell.is_outdoor:
            r.anchor_score = 0.8
        else:
            r.anchor_score = 0.0
            findings.append("no anchors defined")
            recs.append("Run Phase 4 (StructuralAnchorGenerator) to create attachment points.")

        # 5. Enclosure quality (0.10)
        if shell.is_outdoor or shell.enclosure_valid:
            r.enclosure_score = 1.0
        else:
            r.enclosure_score = 0.0
            findings.append("enclosure invalid")

        # 6. Phase completion (0.05)
        completed = sum(
            1 for s in ALL_PHASE_STATUSES
            if shell.phase_statuses.get(s.replace("_COMPLETE", "").replace("_READY", "").lower(), "") == s
            or s in shell.phase_statuses.values()
        )
        r.phase_score = completed / len(ALL_PHASE_STATUSES) if ALL_PHASE_STATUSES else 0.0

        # Overall
        r.overall_score = (
            r.floor_score    * 0.25
            + r.wall_score   * 0.25
            + r.ceiling_score * 0.20
            + r.anchor_score  * 0.15
            + r.enclosure_score * 0.10
            + r.phase_score   * 0.05
        )

        # Grade
        r.grade = "F"
        for threshold, grade in _GRADE_THRESHOLDS:
            if r.overall_score >= threshold:
                r.grade = grade
                break

        # Blocking findings check
        has_blocking = any(
            kw in f.lower() for f in findings for kw in _BLOCKING_KEYWORDS
        )
        r.production_ready = (r.overall_score >= 0.75) and not has_blocking
        r.findings         = findings
        r.recommendations  = recs
        return r


# ── Singleton ──────────────────────────────────────────────────────────────────

_INSTANCE: Optional[ShellReview] = None
_LOCK = threading.Lock()


def get_shell_review() -> ShellReview:
    global _INSTANCE
    if _INSTANCE is None:
        with _LOCK:
            if _INSTANCE is None:
                _INSTANCE = ShellReview()
    return _INSTANCE


def reset_shell_review_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
