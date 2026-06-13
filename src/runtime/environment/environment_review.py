"""
Environment Review (§44 — Structural Environment Assembly)
==========================================================
6-dimension quality review of a built environment. Produces a grade, score,
production_ready flag, findings, and recommendations.

Score weights:
  structure   = 0.35
  zones       = 0.15
  anchors     = 0.25
  support     = 0.10
  decoration  = 0.10
  atmosphere  = 0.05

Grade mapping:
  >= 0.85 → A, production_ready = True
  >= 0.70 → B, production_ready = True
  >= 0.55 → C, production_ready = False
  >= 0.40 → D, production_ready = False
  <  0.40 → F, production_ready = False

Blocking findings (override production_ready):
  "floor missing", "wall missing", "anchor asset missing", "no zones defined"

DESIGN RULES:
  1. No bridge calls. No Houdini imports. Advisory only.
  2. Deterministic.
  3. Never raises — errors captured in EnvironmentReviewResult.findings.
  4. Singleton pattern.
  5. Thread-safe.

Public API:
    EnvironmentReviewResult
    EnvironmentReview
    get_environment_review()
    reset_environment_review_for_tests()
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.runtime.environment.environment_structure_builder import EnvironmentStructurePlan
from src.runtime.environment.environment_zone_builder import ZonePlan
from src.runtime.environment.anchor_asset_builder import AnchorPlan
from src.runtime.environment.support_asset_builder import SupportPlan
from src.runtime.environment.decorative_population import DecorationPlan
from src.runtime.environment.atmosphere_builder import AtmospherePlan


# ---------------------------------------------------------------------------
# Score weights
# ---------------------------------------------------------------------------

_WEIGHTS = {
    "structure":  0.35,
    "zones":      0.15,
    "anchors":    0.25,
    "support":    0.10,
    "decoration": 0.10,
    "atmosphere": 0.05,
}

_BLOCKING_KEYWORDS = [
    "floor missing",
    "wall missing",
    "anchor asset missing",
    "no zones defined",
]


def _grade(score: float) -> str:
    if score >= 0.85:
        return "A"
    if score >= 0.70:
        return "B"
    if score >= 0.55:
        return "C"
    if score >= 0.40:
        return "D"
    return "F"


def _is_blocking(finding: str) -> bool:
    fl = finding.lower()
    return any(kw in fl for kw in _BLOCKING_KEYWORDS)


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

@dataclass
class EnvironmentReviewResult:
    """6-dimension quality review of a built environment."""

    environment_name: str = ""
    structure_score: float = 0.0
    zone_score: float = 0.0
    anchor_score: float = 0.0
    support_score: float = 0.0
    decoration_score: float = 0.0
    atmosphere_score: float = 0.0
    overall_score: float = 0.0
    grade: str = "F"
    production_ready: bool = False
    findings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    build_time: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "environment_name":  self.environment_name,
            "structure_score":   round(self.structure_score, 4),
            "zone_score":        round(self.zone_score, 4),
            "anchor_score":      round(self.anchor_score, 4),
            "support_score":     round(self.support_score, 4),
            "decoration_score":  round(self.decoration_score, 4),
            "atmosphere_score":  round(self.atmosphere_score, 4),
            "overall_score":     round(self.overall_score, 4),
            "grade":             self.grade,
            "production_ready":  self.production_ready,
            "findings":          list(self.findings),
            "recommendations":   list(self.recommendations),
            "build_time":        round(self.build_time, 4),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "EnvironmentReviewResult":
        return cls(
            environment_name = str(d.get("environment_name", "")),
            structure_score  = float(d.get("structure_score", 0.0)),
            zone_score       = float(d.get("zone_score", 0.0)),
            anchor_score     = float(d.get("anchor_score", 0.0)),
            support_score    = float(d.get("support_score", 0.0)),
            decoration_score = float(d.get("decoration_score", 0.0)),
            atmosphere_score = float(d.get("atmosphere_score", 0.0)),
            overall_score    = float(d.get("overall_score", 0.0)),
            grade            = str(d.get("grade", "F")),
            production_ready = bool(d.get("production_ready", False)),
            findings         = list(d.get("findings", [])),
            recommendations  = list(d.get("recommendations", [])),
            build_time       = float(d.get("build_time", 0.0)),
        )


# ---------------------------------------------------------------------------
# Review engine
# ---------------------------------------------------------------------------

class EnvironmentReview:
    """Perform a 6-dimension quality review of a built environment."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def review(
        self,
        environment_name: str,
        structure_plan: Optional[EnvironmentStructurePlan] = None,
        zone_plan: Optional[ZonePlan] = None,
        anchor_plan: Optional[AnchorPlan] = None,
        support_plan: Optional[SupportPlan] = None,
        decoration_plan: Optional[DecorationPlan] = None,
        atmosphere_plan: Optional[AtmospherePlan] = None,
    ) -> EnvironmentReviewResult:
        """Run the 6-dimension review.

        All plan arguments are optional. Missing plans contribute 0.0 to their
        respective dimension scores.

        Returns:
            EnvironmentReviewResult — never raises.
        """
        t0 = time.perf_counter()
        with self._lock:
            try:
                return self._review(
                    environment_name, structure_plan, zone_plan, anchor_plan,
                    support_plan, decoration_plan, atmosphere_plan, t0,
                )
            except Exception as exc:
                return EnvironmentReviewResult(
                    environment_name = environment_name,
                    findings         = [f"Review error: {exc}"],
                    build_time       = time.perf_counter() - t0,
                )

    def _review(
        self,
        env_name: str,
        structure_plan: Optional[EnvironmentStructurePlan],
        zone_plan: Optional[ZonePlan],
        anchor_plan: Optional[AnchorPlan],
        support_plan: Optional[SupportPlan],
        decoration_plan: Optional[DecorationPlan],
        atmosphere_plan: Optional[AtmospherePlan],
        t0: float,
    ) -> EnvironmentReviewResult:
        findings: List[str] = []
        recommendations: List[str] = []

        # ---- Structure dimension -------------------------------------------
        if structure_plan is None:
            struct_score = 0.0
            findings.append("floor missing")
            findings.append("wall missing")
            recommendations.append("Run hou_mcp_environment_structure to build the structural scaffold.")
        else:
            missing_count = len(structure_plan.missing_required)
            struct_score = max(0.0, 1.0 - 0.2 * missing_count)
            if not structure_plan.floor_present:
                findings.append("floor missing")
                recommendations.append("Add a floor element to the structural plan.")
            if not structure_plan.walls_present:
                findings.append("wall missing")
                recommendations.append("Add wall elements to the structural plan.")
            if not structure_plan.structure_complete:
                findings.append(f"incomplete structure: {', '.join(structure_plan.missing_required)}")

        # ---- Zone dimension ------------------------------------------------
        if zone_plan is None or zone_plan.zone_count == 0:
            zone_score = 0.0
            findings.append("no zones defined")
            recommendations.append("Run hou_mcp_environment_zones to define environment zones.")
        elif zone_plan.zone_count >= 4:
            zone_score = 1.0
        elif zone_plan.zone_count >= 2:
            zone_score = 0.5
        else:
            zone_score = 0.25

        # ---- Anchor dimension ----------------------------------------------
        if anchor_plan is None or anchor_plan.anchor_count == 0:
            anchor_score = 0.0
            findings.append("anchor asset missing")
            recommendations.append("Run anchor builder to place major focal elements.")
        else:
            anchor_score = 1.0

        # ---- Support dimension ---------------------------------------------
        if support_plan is None or support_plan.total_count == 0:
            support_score = 0.5
            recommendations.append("Add support assets for richer scene context.")
        else:
            support_score = 1.0

        # ---- Decoration dimension ------------------------------------------
        if decoration_plan is None or decoration_plan.total_count == 0:
            deco_score = 0.0
            recommendations.append("Add decorative props to enhance scene detail.")
        elif decoration_plan.total_count < 3:
            deco_score = 0.5
        else:
            deco_score = 1.0

        # ---- Atmosphere dimension ------------------------------------------
        if atmosphere_plan is None or atmosphere_plan.errors:
            atm_score = 0.5
            recommendations.append("Configure atmosphere effects for the environment.")
        else:
            atm_score = 1.0

        # ---- Overall score -------------------------------------------------
        overall = (
            struct_score * _WEIGHTS["structure"]
            + zone_score  * _WEIGHTS["zones"]
            + anchor_score * _WEIGHTS["anchors"]
            + support_score * _WEIGHTS["support"]
            + deco_score  * _WEIGHTS["decoration"]
            + atm_score   * _WEIGHTS["atmosphere"]
        )

        g = _grade(overall)
        base_ready = overall >= 0.70 and g in ("A", "B")

        # Apply blocking findings
        has_blocker = any(_is_blocking(f) for f in findings)
        production_ready = base_ready and not has_blocker

        return EnvironmentReviewResult(
            environment_name = env_name,
            structure_score  = struct_score,
            zone_score       = zone_score,
            anchor_score     = anchor_score,
            support_score    = support_score,
            decoration_score = deco_score,
            atmosphere_score = atm_score,
            overall_score    = overall,
            grade            = g,
            production_ready = production_ready,
            findings         = findings,
            recommendations  = recommendations,
            build_time       = time.perf_counter() - t0,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[EnvironmentReview] = None
_LOCK = threading.Lock()


def get_environment_review() -> EnvironmentReview:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = EnvironmentReview()
        return _INSTANCE


def reset_environment_review_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
