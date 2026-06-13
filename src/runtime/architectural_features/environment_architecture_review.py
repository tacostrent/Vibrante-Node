"""
environment_architecture_review.py — Tier 10.5 Structural Openings & Architectural Features
=============================================================================================
Validates an ArchitecturalPlan against the shell's declared anchor counts and
geometric rules, then produces a scored ARCHITECTURE_STATUS report.

Validation rules:
  1. Every door_anchor in the shell must have a matching ArchitecturalOpening.
  2. Every window_anchor in the shell must have a matching ArchitecturalOpening.
  3. Every fireplace: back_face_distance ≤ 0.05m, forward_axis correct.
  4. Every beam: gap_to_ceiling ≤ 0.05m, NOT intersects_wall, is_below_ceiling.
  5. Every shelf: NOT is_floating.

Score weights:
  door_openings:    0.30
  window_openings:  0.25
  fireplace:        0.20
  beams:            0.15
  shelves:          0.10

PASS criterion:
  architecture_score ≥ 0.80
  AND no missing door openings
  AND no missing window openings

Hard rule:
  production_ready = False if ANY anchor lacks its corresponding opening.

Public API:
  ARCHITECTURE_STATUS_PASS
  ARCHITECTURE_STATUS_FAIL
  ArchitectureReviewResult
  EnvironmentArchitectureReview
  get_environment_architecture_review()
  reset_environment_architecture_review_for_tests()
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.runtime.architectural_features.architectural_plan import (
    ArchitecturalPlan,
    FireplacePlacement,
    BeamPlacement,
    WallShelfPlacement,
    _INTERIOR_VECTORS,
)

# ── Status constants ───────────────────────────────────────────────────────────

ARCHITECTURE_STATUS_PASS = "PASS"
ARCHITECTURE_STATUS_FAIL = "FAIL"

# ── Thresholds ─────────────────────────────────────────────────────────────────

_FP_WALL_MAX_DIST:   float = 0.05   # fireplace back_face ≤ this
_BEAM_CEIL_MAX_GAP:  float = 0.05   # beam gap_to_ceiling ≤ this
_PASS_SCORE:         float = 0.80   # overall architecture_score ≥ this

# Score weights (sum to 1.0)
_WEIGHTS = {
    "door_openings":   0.30,
    "window_openings": 0.25,
    "fireplace":       0.20,
    "beams":           0.15,
    "shelves":         0.10,
}

# ── Result model ───────────────────────────────────────────────────────────────

@dataclass
class ArchitectureReviewResult:
    """Full output of EnvironmentArchitectureReview.review()."""

    # Per-feature validation
    door_openings_valid:   bool
    window_openings_valid: bool
    fireplace_valid:       bool
    beams_valid:           bool
    shelves_valid:         bool

    # Detailed failure lists
    missing_door_openings:   List[str]   = field(default_factory=list)
    missing_window_openings: List[str]   = field(default_factory=list)
    floating_assets:         List[str]   = field(default_factory=list)
    wall_intersections:      List[str]   = field(default_factory=list)
    fireplace_failures:      List[str]   = field(default_factory=list)
    beam_failures:           List[str]   = field(default_factory=list)

    # Scores
    architecture_score:    float = 0.0
    door_score:            float = 0.0
    window_score:          float = 0.0
    fireplace_score:       float = 0.0
    beam_score:            float = 0.0
    shelf_score:           float = 0.0

    # Overall
    status:           str  = ARCHITECTURE_STATUS_PASS
    production_ready: bool = True
    architecture_report: str = ""

    ok:     bool       = True
    errors: List[str]  = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "door_openings_valid":   self.door_openings_valid,
            "window_openings_valid": self.window_openings_valid,
            "fireplace_valid":       self.fireplace_valid,
            "beams_valid":           self.beams_valid,
            "shelves_valid":         self.shelves_valid,
            "missing_door_openings":   list(self.missing_door_openings),
            "missing_window_openings": list(self.missing_window_openings),
            "floating_assets":         list(self.floating_assets),
            "wall_intersections":      list(self.wall_intersections),
            "fireplace_failures":      list(self.fireplace_failures),
            "beam_failures":           list(self.beam_failures),
            "architecture_score":  round(self.architecture_score, 4),
            "door_score":          round(self.door_score,     4),
            "window_score":        round(self.window_score,   4),
            "fireplace_score":     round(self.fireplace_score,4),
            "beam_score":          round(self.beam_score,     4),
            "shelf_score":         round(self.shelf_score,    4),
            "status":              self.status,
            "production_ready":    self.production_ready,
            "architecture_report": self.architecture_report,
            "ok":                  self.ok,
            "errors":              list(self.errors),
        }


# ── Review engine ──────────────────────────────────────────────────────────────

class EnvironmentArchitectureReview:
    """
    Validates an ArchitecturalPlan and produces an ArchitectureReviewResult.

    Usage:
        result = get_environment_architecture_review().review(plan, shell_dict)
        assert result.status == ARCHITECTURE_STATUS_PASS
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def review(
        self,
        plan:       ArchitecturalPlan,
        shell_dict: Dict[str, Any] = None,
    ) -> ArchitectureReviewResult:
        """Run the full architecture review. Never raises."""
        try:
            return self._review(plan, shell_dict or {})
        except Exception as exc:
            return ArchitectureReviewResult(
                door_openings_valid=False, window_openings_valid=False,
                fireplace_valid=False, beams_valid=False, shelves_valid=False,
                status=ARCHITECTURE_STATUS_FAIL, production_ready=False,
                ok=False, errors=[f"EnvironmentArchitectureReview.review failed: {exc}"],
            )

    # ─────────────────────────────────────────────────────────────────────────

    def _review(
        self,
        plan:  ArchitecturalPlan,
        shell: Dict[str, Any],
    ) -> ArchitectureReviewResult:

        anchors: List[Dict[str, Any]] = list(shell.get("anchors", []))

        # ── Door openings ─────────────────────────────────────────────────────
        door_anchor_ids    = {a["anchor_id"] for a in anchors
                               if a.get("anchor_type") == "door_anchor"}
        opening_door_ids   = {o.anchor_id for o in plan.door_openings}
        missing_doors      = sorted(door_anchor_ids - opening_door_ids)
        door_score         = _coverage_score(len(door_anchor_ids) - len(missing_doors),
                                              len(door_anchor_ids))
        door_valid         = len(missing_doors) == 0

        # ── Window openings ───────────────────────────────────────────────────
        win_anchor_ids     = {a["anchor_id"] for a in anchors
                               if a.get("anchor_type") == "window_anchor"}
        opening_win_ids    = {o.anchor_id for o in plan.window_openings}
        missing_windows    = sorted(win_anchor_ids - opening_win_ids)
        window_score       = _coverage_score(len(win_anchor_ids) - len(missing_windows),
                                              len(win_anchor_ids))
        window_valid       = len(missing_windows) == 0

        # ── Fireplace ────────────────────────────────────────────────────────
        fp_failures: List[str] = []
        for fp in plan.fireplace_placements:
            ok, reason = _validate_fireplace(fp)
            if not ok:
                fp_failures.append(f"{fp.feature_id}: {reason}")
        fp_total   = len(plan.fireplace_placements)
        fp_passed  = fp_total - len(fp_failures)
        fp_score   = _coverage_score(fp_passed, fp_total)
        fp_valid   = len(fp_failures) == 0

        # ── Beams ────────────────────────────────────────────────────────────
        beam_failures:   List[str] = []
        wall_intersects: List[str] = []
        for b in plan.beam_placements:
            ok, reason = _validate_beam(b)
            if not ok:
                beam_failures.append(f"{b.feature_id}: {reason}")
            if b.intersects_wall:
                wall_intersects.append(b.feature_id)
        beam_total  = len(plan.beam_placements)
        beam_passed = beam_total - len(beam_failures)
        beam_score  = _coverage_score(beam_passed, beam_total)
        beam_valid  = len(beam_failures) == 0

        # ── Shelves ──────────────────────────────────────────────────────────
        floating: List[str] = []
        for s in plan.shelf_placements:
            if s.is_floating:
                floating.append(s.feature_id)
        shelf_total  = len(plan.shelf_placements)
        shelf_passed = shelf_total - len(floating)
        shelf_score  = _coverage_score(shelf_passed, shelf_total)
        shelf_valid  = len(floating) == 0

        # ── Overall score ────────────────────────────────────────────────────
        arch_score = (
            door_score   * _WEIGHTS["door_openings"]
            + window_score * _WEIGHTS["window_openings"]
            + fp_score     * _WEIGHTS["fireplace"]
            + beam_score   * _WEIGHTS["beams"]
            + shelf_score  * _WEIGHTS["shelves"]
        )

        # Hard rule: any missing opening blocks production_ready
        missing_any_opening = bool(missing_doors or missing_windows)
        prod_ready = (arch_score >= _PASS_SCORE) and not missing_any_opening

        status = (
            ARCHITECTURE_STATUS_PASS
            if arch_score >= _PASS_SCORE and not missing_any_opening
            else ARCHITECTURE_STATUS_FAIL
        )

        report = _format_report(
            plan.environment, arch_score, status,
            door_valid, window_valid, fp_valid, beam_valid, shelf_valid,
            len(plan.door_openings), len(door_anchor_ids),
            len(plan.window_openings), len(win_anchor_ids),
            len(plan.fireplace_placements), len(fp_failures),
            len(plan.beam_placements), len(beam_failures),
            len(plan.shelf_placements), len(floating),
            missing_doors, missing_windows,
            fp_failures, beam_failures, floating,
        )

        return ArchitectureReviewResult(
            door_openings_valid   = door_valid,
            window_openings_valid = window_valid,
            fireplace_valid       = fp_valid,
            beams_valid           = beam_valid,
            shelves_valid         = shelf_valid,
            missing_door_openings   = missing_doors,
            missing_window_openings = missing_windows,
            floating_assets         = floating,
            wall_intersections      = wall_intersects,
            fireplace_failures      = fp_failures,
            beam_failures           = beam_failures,
            architecture_score  = round(arch_score, 4),
            door_score          = round(door_score,   4),
            window_score        = round(window_score, 4),
            fireplace_score     = round(fp_score,     4),
            beam_score          = round(beam_score,   4),
            shelf_score         = round(shelf_score,  4),
            status              = status,
            production_ready    = prod_ready,
            architecture_report = report,
            ok                  = prod_ready,
        )


# ── Validation helpers ─────────────────────────────────────────────────────────

def _validate_fireplace(fp: FireplacePlacement) -> Tuple[bool, str]:
    """Return (passed, failure_reason)."""
    if fp.back_face_distance > _FP_WALL_MAX_DIST:
        return False, (
            f"back_face_distance={fp.back_face_distance:.3f}m "
            f"> {_FP_WALL_MAX_DIST}m (wall_face={fp.wall_face})"
        )
    expected = _INTERIOR_VECTORS.get(fp.wall_face, [0.0, 0.0, 1.0])
    if fp.forward_axis != expected:
        # Allow small float deviations
        close = all(abs(fp.forward_axis[i] - expected[i]) < 0.01
                    for i in range(len(expected)))
        if not close:
            return False, (
                f"forward_axis={fp.forward_axis} does not point to room interior "
                f"(expected {expected} for wall_face={fp.wall_face})"
            )
    return True, ""


def _validate_beam(b: BeamPlacement) -> Tuple[bool, str]:
    """Return (passed, failure_reason)."""
    if b.gap_to_ceiling > _BEAM_CEIL_MAX_GAP:
        return False, (
            f"gap_to_ceiling={b.gap_to_ceiling:.3f}m > {_BEAM_CEIL_MAX_GAP}m"
        )
    if b.intersects_wall:
        return False, "beam intersects perimeter wall"
    if not b.is_below_ceiling:
        return False, "beam extends above ceiling"
    return True, ""


def _coverage_score(n_valid: int, n_total: int) -> float:
    """Return 1.0 for empty totals (vacuously valid)."""
    if n_total == 0:
        return 1.0
    return max(0.0, min(1.0, n_valid / n_total))


# ── Report formatter ──────────────────────────────────────────────────────────

def _format_report(
    env: str, score: float, status: str,
    door_v: bool, win_v: bool, fp_v: bool, beam_v: bool, shelf_v: bool,
    n_doors: int,  n_door_anchors: int,
    n_wins:  int,  n_win_anchors:  int,
    n_fps:   int,  n_fp_fail:  int,
    n_beams: int,  n_beam_fail: int,
    n_shelves: int, n_shelf_fail: int,
    missing_doors:  List[str],
    missing_wins:   List[str],
    fp_fails:       List[str],
    beam_fails:     List[str],
    float_shelves:  List[str],
) -> str:
    sep = "=" * 62
    thin = "-" * 62

    def _flag(v: bool) -> str:
        return "PASS" if v else "FAIL"

    lines = [
        "",
        f"ARCHITECTURE REVIEW - {env}",
        sep,
        f"Door Openings    ({n_doors}/{n_door_anchors}):      {_flag(door_v)}",
        f"Window Openings  ({n_wins}/{n_win_anchors}):      {_flag(win_v)}",
        f"Fireplace        ({n_fps - n_fp_fail}/{n_fps}):      {_flag(fp_v)}",
        f"Beams            ({n_beams - n_beam_fail}/{n_beams}):      {_flag(beam_v)}",
        f"Wall Shelves     ({n_shelves - n_shelf_fail}/{n_shelves}):      {_flag(shelf_v)}",
        thin,
        f"Architecture Score:   {score:.3f}",
        f"Status:               {status}",
        f"Production Ready:     {'YES' if status == ARCHITECTURE_STATUS_PASS else 'NO'}",
        sep,
    ]

    if missing_doors:
        lines += ["", "Missing door openings:"] + [f"  - {a}" for a in missing_doors]
    if missing_wins:
        lines += ["", "Missing window openings:"] + [f"  - {a}" for a in missing_wins]
    if fp_fails:
        lines += ["", "Fireplace failures:"] + [f"  - {f}" for f in fp_fails]
    if beam_fails:
        lines += ["", "Beam failures:"] + [f"  - {f}" for f in beam_fails]
    if float_shelves:
        lines += ["", "Floating shelves:"] + [f"  - {s}" for s in float_shelves]

    lines.append("")
    return "\n".join(lines)


# ── Singleton ──────────────────────────────────────────────────────────────────

_instance: Optional[EnvironmentArchitectureReview] = None
_lock = threading.Lock()


def get_environment_architecture_review() -> EnvironmentArchitectureReview:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = EnvironmentArchitectureReview()
    return _instance


def reset_environment_architecture_review_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
