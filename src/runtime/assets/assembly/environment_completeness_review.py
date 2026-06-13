"""
Environment Completeness Review (Tier 9.5 — Structural Environment Assembly)
=============================================================================
Evaluates whether a scene constitutes a complete environment versus a random
collection of scattered assets. Reviews six structural dimensions:

  - structure_score:   required structural elements (floor, walls, etc.)
  - zone_score:        required zones populated and valid
  - anchor_score:      major anchor assets defined
  - support_score:     secondary supporting assets defined
  - decoration_score:  decorative dressing defined
  - atmosphere_score:  atmospheric elements defined

BLOCKING FINDINGS (block production_ready regardless of score):
  - "floor missing"             — floor required but absent
  - "wall missing"              — walls required but absent
  - "required structure missing" — at least one other required element absent
  - "anchor asset missing"      — no anchor assets defined in the anchor plan
  - "no zones"                  — no structural zones defined

GRADE MAPPING:
  >= 0.85 → A  (production_ready)
  >= 0.70 → B  (production_ready)
  >= 0.55 → C  (not production_ready)
  >= 0.40 → D  (not production_ready)
  <  0.40 → F  (not production_ready)

SCORE WEIGHTS:
  structure:   0.35
  anchor:      0.25
  zones:       0.15
  support:     0.10
  decoration:  0.10
  atmosphere:  0.05

DESIGN RULES:
  1. No bridge calls. No Houdini imports. Advisory only.
  2. All evaluation is deterministic — same input → same review.
  3. production_ready requires overall_score >= 0.70 AND no blocking findings.
  4. review_summary is always a specific critique string, never generic "success".
  5. Never raises.

Public API:
    EnvironmentCompletenessReview
    EnvironmentCompletenessReviewer
    get_environment_completeness_reviewer()
    reset_environment_completeness_reviewer_for_tests()
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.runtime.assets.assembly.environment_structure_builder import (
    EnvironmentStructure,
    get_environment_structure_builder,
)
from src.runtime.assets.assembly.anchor_asset_engine import (
    AnchorPlan,
    get_anchor_asset_engine,
)
from src.runtime.assets.assembly.decorative_population_engine import (
    DecorationPlan,
    get_decorative_population_engine,
)


# ---------------------------------------------------------------------------
# Score weights
# ---------------------------------------------------------------------------

_WEIGHTS: Dict[str, float] = {
    "structure":   0.35,
    "anchor":      0.25,
    "zones":       0.15,
    "support":     0.10,
    "decoration":  0.10,
    "atmosphere":  0.05,
}

_PRODUCTION_THRESHOLD = 0.70


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class EnvironmentCompletenessReview:
    """Full completeness review for a structured environment."""

    review_id:        str = field(default_factory=lambda: f"ecr_{uuid.uuid4().hex[:10]}")
    environment_name: str = ""

    # Dimension scores (0.0 – 1.0)
    structure_score:   float = 0.0
    zone_score:        float = 0.0
    anchor_score:      float = 0.0
    support_score:     float = 0.0
    decoration_score:  float = 0.0
    atmosphere_score:  float = 0.0

    overall_score:    float = 0.0
    grade:            str   = "F"
    production_ready: bool  = False

    blocking_findings: List[str] = field(default_factory=list)
    findings:          List[str] = field(default_factory=list)
    review_summary:    str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "review_id":        self.review_id,
            "environment_name": self.environment_name,
            "structure_score":  self.structure_score,
            "zone_score":       self.zone_score,
            "anchor_score":     self.anchor_score,
            "support_score":    self.support_score,
            "decoration_score": self.decoration_score,
            "atmosphere_score": self.atmosphere_score,
            "overall_score":    self.overall_score,
            "grade":            self.grade,
            "production_ready": self.production_ready,
            "blocking_findings":list(self.blocking_findings),
            "findings":         list(self.findings),
            "review_summary":   self.review_summary,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "EnvironmentCompletenessReview":
        return cls(
            review_id         = str(d.get("review_id", f"ecr_{uuid.uuid4().hex[:10]}")),
            environment_name  = str(d.get("environment_name", "")),
            structure_score   = float(d.get("structure_score", 0.0)),
            zone_score        = float(d.get("zone_score", 0.0)),
            anchor_score      = float(d.get("anchor_score", 0.0)),
            support_score     = float(d.get("support_score", 0.0)),
            decoration_score  = float(d.get("decoration_score", 0.0)),
            atmosphere_score  = float(d.get("atmosphere_score", 0.0)),
            overall_score     = float(d.get("overall_score", 0.0)),
            grade             = str(d.get("grade", "F")),
            production_ready  = bool(d.get("production_ready", False)),
            blocking_findings = list(d.get("blocking_findings", [])),
            findings          = list(d.get("findings", [])),
            review_summary    = str(d.get("review_summary", "")),
        )


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


# ---------------------------------------------------------------------------
# Reviewer
# ---------------------------------------------------------------------------

class EnvironmentCompletenessReviewer:
    """Evaluates environment completeness across six structural dimensions.

    Usage:
        reviewer = get_environment_completeness_reviewer()
        result = reviewer.review(environment_name)
        # or
        result = reviewer.review_from_components(structure, anchor_plan, decoration_plan)
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------

    def review(self, environment_name: str) -> EnvironmentCompletenessReview:
        """Build and review a complete environment from scratch.

        Automatically constructs structure, anchor plan, and decoration plan
        from the environment name, then reviews the result.

        Never raises.
        """
        try:
            structure = get_environment_structure_builder().build_structure(environment_name)
            anchor_plan = get_anchor_asset_engine().get_anchor_plan(environment_name)
            decoration_plan = get_decorative_population_engine().get_decoration_plan(
                environment_name, anchor_plan
            )
            return self._evaluate(structure, anchor_plan, decoration_plan)
        except Exception as exc:
            return EnvironmentCompletenessReview(
                environment_name = environment_name,
                review_summary   = f"Review failed: {exc}",
                findings         = [f"Review failed: {exc}"],
            )

    def review_from_components(
        self,
        structure: EnvironmentStructure,
        anchor_plan: AnchorPlan,
        decoration_plan: DecorationPlan,
    ) -> EnvironmentCompletenessReview:
        """Review using pre-built components.

        Args:
            structure:        EnvironmentStructure from EnvironmentStructureBuilder.
            anchor_plan:      AnchorPlan from AnchorAssetEngine.
            decoration_plan:  DecorationPlan from DecorativePopulationEngine.

        Returns:
            EnvironmentCompletenessReview with all dimension scores.
        """
        try:
            return self._evaluate(structure, anchor_plan, decoration_plan)
        except Exception as exc:
            env = getattr(structure, "environment_name", "unknown")
            return EnvironmentCompletenessReview(
                environment_name = env,
                review_summary   = f"Review failed: {exc}",
                findings         = [f"Review failed: {exc}"],
            )

    # ------------------------------------------------------------------
    # Internal evaluation pipeline
    # ------------------------------------------------------------------

    def _evaluate(
        self,
        structure: EnvironmentStructure,
        anchor_plan: AnchorPlan,
        decoration_plan: DecorationPlan,
    ) -> EnvironmentCompletenessReview:
        env = structure.environment_name
        blocking: List[str] = []
        findings: List[str] = []

        # ---- 1. Structure score -----------------------------------------
        structure_score, struct_findings, struct_blocking = self._score_structure(structure)
        findings.extend(struct_findings)
        blocking.extend(struct_blocking)

        # ---- 2. Zone score ----------------------------------------------
        zone_score, zone_findings = self._score_zones(structure)
        findings.extend(zone_findings)
        if zone_score == 0.0:
            blocking.append("no zones — scene has no spatial organisation.")

        # ---- 3. Anchor score --------------------------------------------
        anchor_score, anchor_findings, anchor_blocking = self._score_anchors(anchor_plan)
        findings.extend(anchor_findings)
        blocking.extend(anchor_blocking)

        # ---- 4. Support score -------------------------------------------
        support_score, support_findings = self._score_support(structure)
        findings.extend(support_findings)

        # ---- 5. Decoration score ----------------------------------------
        decoration_score, deco_findings = self._score_decoration(decoration_plan)
        findings.extend(deco_findings)

        # ---- 6. Atmosphere score ----------------------------------------
        atmosphere_score, atmo_findings = self._score_atmosphere(structure)
        findings.extend(atmo_findings)

        # ---- Overall score -----------------------------------------------
        overall = (
            structure_score  * _WEIGHTS["structure"] +
            anchor_score     * _WEIGHTS["anchor"] +
            zone_score       * _WEIGHTS["zones"] +
            support_score    * _WEIGHTS["support"] +
            decoration_score * _WEIGHTS["decoration"] +
            atmosphere_score * _WEIGHTS["atmosphere"]
        )
        overall = round(min(1.0, max(0.0, overall)), 4)

        grade = _grade(overall)
        production_ready = (overall >= _PRODUCTION_THRESHOLD) and len(blocking) == 0

        review_summary = self._build_summary(
            env, overall, blocking, findings, production_ready
        )

        return EnvironmentCompletenessReview(
            environment_name  = env,
            structure_score   = round(structure_score, 4),
            zone_score        = round(zone_score, 4),
            anchor_score      = round(anchor_score, 4),
            support_score     = round(support_score, 4),
            decoration_score  = round(decoration_score, 4),
            atmosphere_score  = round(atmosphere_score, 4),
            overall_score     = overall,
            grade             = grade,
            production_ready  = production_ready,
            blocking_findings = blocking,
            findings          = findings,
            review_summary    = review_summary,
        )

    # ------------------------------------------------------------------
    # Dimension scorers
    # ------------------------------------------------------------------

    def _score_structure(
        self, structure: EnvironmentStructure
    ) -> tuple:
        blocking: List[str] = []
        findings: List[str] = []

        if not structure.structural_elements:
            blocking.append("required structure missing — no structural elements defined.")
            return 0.0, findings, blocking

        bp = structure.blueprint
        if bp is None:
            findings.append("No blueprint — structure completeness cannot be fully evaluated.")
            # Be lenient: if elements exist, give partial credit
            score = 0.5 if structure.structural_elements else 0.0
            return score, findings, blocking

        missing = structure.missing_required

        if bp.floor_required and "floor" in missing:
            blocking.append("floor missing — a floor is required for this environment.")
        if bp.wall_required and "wall" in missing:
            blocking.append("wall missing — walls are required for this environment.")
        if bp.ceiling_required and "ceiling" in missing:
            findings.append("Ceiling is required but missing — will affect atmosphere.")
        if bp.door_required and "door" in missing:
            findings.append("Door/entrance is required but missing.")
        if bp.window_required and "window" in missing:
            findings.append("Window/viewport is required but missing.")

        if missing:
            findings.append(f"Missing required elements: {', '.join(missing)}.")

        # Score based on fraction of required elements present
        total_required = sum([bp.floor_required, bp.wall_required, bp.ceiling_required,
                               bp.door_required, bp.window_required])
        if total_required == 0:
            score = 1.0 if structure.structural_elements else 0.5
        else:
            fraction_missing = len(missing) / total_required
            score = max(0.0, 1.0 - fraction_missing)

        # Bonus: optional elements defined
        optional_defined = len(bp.structural_optional)
        if optional_defined > 0:
            score = min(1.0, score + 0.05)

        return score, findings, blocking

    def _score_zones(self, structure: EnvironmentStructure) -> tuple:
        findings: List[str] = []

        if not structure.zones:
            findings.append("No zones defined — environment has no spatial organisation.")
            return 0.0, findings

        total_zones = len(structure.zones)
        required_zones = [z for z in structure.zones if z.required]
        populated_required = len(required_zones)
        total_required = len(required_zones)

        if total_required == 0:
            score = 1.0 if total_zones >= 3 else 0.6
        else:
            score = populated_required / total_required

        if total_zones < 3:
            findings.append(f"Only {total_zones} zone(s) defined — a complete environment typically has 5–6 zones.")

        return min(1.0, score), findings

    def _score_anchors(self, anchor_plan: AnchorPlan) -> tuple:
        blocking: List[str] = []
        findings: List[str] = []

        if not anchor_plan.anchors:
            blocking.append("anchor asset missing — no anchor assets defined; scene lacks identity.")
            return 0.0, findings, blocking

        if anchor_plan.primary_anchor is None:
            findings.append("No primary anchor — scene has no single defining focal element.")
            score = 0.5
        else:
            score = 1.0

        anchor_count = len(anchor_plan.anchors)
        if anchor_count == 1:
            findings.append("Only one anchor defined — consider adding 1–2 secondary anchors for depth.")
            score = min(score, 0.75)

        return score, findings, blocking

    def _score_support(self, structure: EnvironmentStructure) -> tuple:
        findings: List[str] = []
        bp = structure.blueprint

        if bp is None:
            return 0.5, findings

        has_support = len(bp.support_assets) > 0
        if not has_support:
            findings.append("No support asset types defined in blueprint.")
            return 0.4, findings

        # Support score is binary: either the environment has support assets or it doesn't
        return 1.0, findings

    def _score_decoration(self, decoration_plan: DecorationPlan) -> tuple:
        findings: List[str] = []

        if not decoration_plan.items:
            findings.append("No decorative items defined — scene lacks surface detail.")
            return 0.0, findings

        total_qty = decoration_plan.total_items
        if total_qty < 3:
            findings.append(f"Only {total_qty} decorative item(s) — scene needs more surface dressing.")
            return 0.4, findings
        if total_qty < 6:
            return 0.7, findings

        return 1.0, findings

    def _score_atmosphere(self, structure: EnvironmentStructure) -> tuple:
        findings: List[str] = []
        bp = structure.blueprint

        if bp is None:
            return 0.5, findings

        has_atmosphere = len(bp.atmosphere_assets) > 0
        if not has_atmosphere:
            findings.append("No atmosphere assets defined — scene lacks lighting and volumetric depth.")
            return 0.0, findings

        return 1.0, findings

    # ------------------------------------------------------------------
    # Summary builder
    # ------------------------------------------------------------------

    def _build_summary(
        self,
        environment_name: str,
        overall_score: float,
        blocking: List[str],
        findings: List[str],
        production_ready: bool,
    ) -> str:
        if blocking:
            return (
                f"Environment '{environment_name}' is NOT production-ready: "
                f"{blocking[0]}"
            )
        if not production_ready:
            top = findings[0] if findings else "score below production threshold"
            return (
                f"Environment '{environment_name}' scores {overall_score:.2f} "
                f"but is not production-ready: {top}"
            )
        # Still specific even on success
        return (
            f"Environment '{environment_name}' passes completeness review "
            f"with overall score {overall_score:.2f} — structure, zones, anchors, "
            f"and decoration are all defined."
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[EnvironmentCompletenessReviewer] = None
_LOCK = threading.Lock()


def get_environment_completeness_reviewer() -> EnvironmentCompletenessReviewer:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = EnvironmentCompletenessReviewer()
        return _INSTANCE


def reset_environment_completeness_reviewer_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
