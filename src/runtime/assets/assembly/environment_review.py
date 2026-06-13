"""
Environment Review (Tier 9 — Semantic Asset Assembly)
=====================================================
Evaluates assembled environment quality across four dimensions:
  - Layout      — zone structure and depth hierarchy
  - Population  — asset group balance and density
  - Readability — viewer's ability to identify the narrative focus
  - Storytelling — narrative coherence and visual flow

All critique is specific — generic "success" messages are explicitly
disallowed. Every finding names the failing criterion.

DESIGN RULES:
  1. No bridge calls.  No Houdini imports.  Advisory only.
  2. All evaluation is deterministic — same input → same review.
  3. production_ready requires overall_score >= 0.6 AND no blocking findings.
  4. review_summary is always a specific critique string, never "success".
  5. Never raises.

Public API:
    EnvironmentReviewResult
    EnvironmentReview
    get_environment_review()
    reset_environment_review_for_tests()
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.runtime.assets.assembly.environment_builder import EnvironmentPlan
from src.runtime.assets.assembly.scene_population_engine import PopulationPlan
from src.runtime.assets.assembly.storytelling_layout_engine import StoryLayout
from src.runtime.assets.assembly.composition_constraints import (
    CompositionReport,
    get_composition_constraints,
)

# ---------------------------------------------------------------------------
# Score weights per dimension
# ---------------------------------------------------------------------------

_WEIGHTS = {
    "layout":       0.30,
    "population":   0.25,
    "readability":  0.30,
    "storytelling": 0.15,
}

# Minimum score threshold for production-ready
_PRODUCTION_THRESHOLD = 0.60

# Specific critique messages — never generic
_CRITIQUES: Dict[str, str] = {
    "no_hero_zone":          "No hero zone defined — the scene has no primary focal point.",
    "hero_empty":            "Hero zone is empty — place at least one primary asset to anchor the scene.",
    "hero_overloaded":       "Hero zone exceeds maximum assets — reduce to 1–3 to preserve focus.",
    "no_depth":              "No depth layers populated — add midground or background assets for spatial depth.",
    "no_support":            "Support zone is empty — hero assets lack contextual surroundings.",
    "no_hero_assets_group":  "Hero assets group is empty — population lacks a narrative anchor.",
    "overloaded_detail":     "Detail assets dominate the scene — reduce props and dressing for visual clarity.",
    "no_story_beats":        "No story beats generated — scene lacks narrative structure.",
    "hero_beat_missing":     "No hero beat in story layout — the central narrative moment is undefined.",
    "viewer_path_empty":     "Viewer path is undefined — there is no visual journey through the scene.",
    "readability_low":       "Composition readability score is below threshold — review hero focus and depth layers.",
    "balance_failure":       "One zone dominates the scene distribution — redistribute assets for visual balance.",
}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class EnvironmentReviewResult:
    """Full environment quality review."""

    review_id:        str = field(default_factory=lambda: f"rev_{uuid.uuid4().hex[:10]}")
    environment:      str = ""

    # Semantic dimension scores
    layout_score:      float = 0.0
    population_score:  float = 0.0
    readability_score: float = 0.0
    storytelling_score: float = 0.0
    overall_score:     float = 0.0

    # Spatial metrics (populated when a PlacementPlan is provided)
    collision_count:          int   = 0
    clearance_violations:     int   = 0
    semantic_placement_score: float = 0.0
    walkability_score:        float = 1.0
    layout_quality_score:     float = 0.0

    grade:             str = "F"          # A/B/C/D/F
    production_ready:  bool = False
    strengths:         List[str] = field(default_factory=list)
    findings:          List[str] = field(default_factory=list)
    recommendations:   List[str] = field(default_factory=list)
    review_summary:    str = ""
    generated_at:      float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "review_id":               self.review_id,
            "environment":             self.environment,
            "layout_score":            self.layout_score,
            "population_score":        self.population_score,
            "readability_score":       self.readability_score,
            "storytelling_score":      self.storytelling_score,
            "overall_score":           self.overall_score,
            "collision_count":         self.collision_count,
            "clearance_violations":    self.clearance_violations,
            "semantic_placement_score": self.semantic_placement_score,
            "walkability_score":       self.walkability_score,
            "layout_quality_score":    self.layout_quality_score,
            "grade":                   self.grade,
            "production_ready":        self.production_ready,
            "strengths":               list(self.strengths),
            "findings":                list(self.findings),
            "recommendations":         list(self.recommendations),
            "review_summary":          self.review_summary,
            "generated_at":            self.generated_at,
        }


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class EnvironmentReview:
    """
    Evaluates assembled environment quality.
    All critique is specific — never "execution successful".
    """

    def evaluate_layout(self, env_plan: EnvironmentPlan) -> Dict[str, Any]:
        """Evaluate zone structure and depth hierarchy."""
        score    = 1.0
        issues:  List[str] = []
        strengths: List[str] = []

        # Hero zone present
        if "hero_zone" not in env_plan.zones:
            issues.append(_CRITIQUES["no_hero_zone"])
            score -= 0.4
        else:
            hero = env_plan.zones["hero_zone"]
            if not hero.assigned_assets:
                issues.append(_CRITIQUES["hero_empty"])
                score -= 0.3
            elif len(hero.assigned_assets) > 3:
                issues.append(_CRITIQUES["hero_overloaded"])
                score -= 0.15
            else:
                strengths.append(f"Hero zone populated with {len(hero.assigned_assets)} asset(s).")

        # Depth layers
        depth_zones = [
            n for n, z in env_plan.zones.items()
            if z.depth < -5.0 and z.assigned_assets
        ]
        if len(depth_zones) < 2:
            issues.append(_CRITIQUES["no_depth"])
            score -= 0.25
        else:
            strengths.append(f"Depth supported by {len(depth_zones)} background zone(s).")

        # Support present
        support_zones = [
            n for n, z in env_plan.zones.items()
            if z.role == "support" and z.assigned_assets
        ]
        if not support_zones:
            issues.append(_CRITIQUES["no_support"])
            score -= 0.1
        else:
            strengths.append(f"{len(support_zones)} support zone(s) provide context.")

        return {
            "score":     max(0.0, score),
            "issues":    issues,
            "strengths": strengths,
        }

    def evaluate_population(self, pop_plan: PopulationPlan) -> Dict[str, Any]:
        """Evaluate population group balance."""
        score    = 1.0
        issues:  List[str] = []
        strengths: List[str] = []

        hero_group = pop_plan.groups.get("hero_assets")
        if not hero_group or hero_group.asset_count == 0:
            issues.append(_CRITIQUES["no_hero_assets_group"])
            score -= 0.4
        else:
            strengths.append(
                f"Hero group populated: {hero_group.asset_count} asset(s)."
            )

        detail_group = pop_plan.groups.get("detail_assets")
        total = sum(g.asset_count for g in pop_plan.groups.values())
        if total > 0 and detail_group:
            detail_ratio = detail_group.asset_count / total
            if detail_ratio > 0.6:
                issues.append(_CRITIQUES["overloaded_detail"])
                score -= 0.2

        # Population balance score from the plan itself
        if pop_plan.balance_score < 0.6:
            issues.append(
                f"Population balance score is {pop_plan.balance_score:.2f} — "
                "hero, support, and detail groups are unbalanced."
            )
            score -= 0.2

        return {
            "score":     max(0.0, score),
            "issues":    issues,
            "strengths": strengths,
        }

    def evaluate_readability(self, comp_report: CompositionReport) -> Dict[str, Any]:
        """Evaluate cinematic readability from a CompositionReport."""
        score      = comp_report.overall_score
        issues:    List[str] = list(comp_report.issues)
        strengths: List[str] = []

        if comp_report.readable:
            strengths.append(
                f"Scene readability passed with score {comp_report.overall_score:.2f}."
            )
        else:
            if score < 0.4:
                issues.append(_CRITIQUES["readability_low"])
            for check in comp_report.checks:
                if not check.passed and check.check_name == "balance":
                    issues.append(_CRITIQUES["balance_failure"])
                    break

        return {
            "score":     score,
            "issues":    issues,
            "strengths": strengths,
        }

    def evaluate_storytelling(self, story_layout: StoryLayout) -> Dict[str, Any]:
        """Evaluate narrative coherence and visual flow."""
        score    = 1.0
        issues:  List[str] = []
        strengths: List[str] = []

        if not story_layout.beats:
            issues.append(_CRITIQUES["no_story_beats"])
            score -= 0.4
        else:
            hero_beats = [b for b in story_layout.beats if b.beat_type == "hero"]
            if not hero_beats:
                issues.append(_CRITIQUES["hero_beat_missing"])
                score -= 0.3
            else:
                strengths.append(
                    f"Hero beat defined: {hero_beats[0].description[:60]}"
                )

        if not story_layout.viewer_path:
            issues.append(_CRITIQUES["viewer_path_empty"])
            score -= 0.2
        else:
            strengths.append(
                f"Viewer path: {' → '.join(story_layout.viewer_path)}"
            )

        if story_layout.visual_flow:
            strengths.append(f"Visual flow: {story_layout.visual_flow}")

        return {
            "score":     max(0.0, score),
            "issues":    issues,
            "strengths": strengths,
        }

    def evaluate_environment(
        self,
        env_plan:     EnvironmentPlan,
        pop_plan:     Optional[PopulationPlan] = None,
        story_layout: Optional[StoryLayout] = None,
        placement_plan: Optional[Any] = None,   # PlacementPlan — import avoided for circularity
    ) -> EnvironmentReviewResult:
        """
        Full environment quality review.
        Accepts an optional PlacementPlan to surface spatial metrics
        (collision_count, clearance_violations).
        Never raises. Always returns specific critique.
        """
        result = EnvironmentReviewResult(environment=env_plan.environment)

        try:
            # Layout
            layout_eval = self.evaluate_layout(env_plan)
            result.layout_score = layout_eval["score"]
            result.findings.extend(layout_eval["issues"])
            result.strengths.extend(layout_eval["strengths"])

            # Population
            if pop_plan is not None:
                pop_eval = self.evaluate_population(pop_plan)
            else:
                pop_eval = {"score": 0.5, "issues": [], "strengths": []}
            result.population_score = pop_eval["score"]
            result.findings.extend(pop_eval["issues"])
            result.strengths.extend(pop_eval["strengths"])

            # Readability — run composition constraints inline
            comp_report = get_composition_constraints().validate_all(env_plan)
            read_eval   = self.evaluate_readability(comp_report)
            result.readability_score = read_eval["score"]
            result.findings.extend(read_eval["issues"])
            result.strengths.extend(read_eval["strengths"])

            # Storytelling
            if story_layout is not None:
                story_eval = self.evaluate_storytelling(story_layout)
            else:
                story_eval = {"score": 0.5, "issues": [], "strengths": []}
            result.storytelling_score = story_eval["score"]
            result.findings.extend(story_eval["issues"])
            result.strengths.extend(story_eval["strengths"])

            # Spatial metrics from PlacementPlan (when provided)
            if placement_plan is not None:
                result.collision_count      = getattr(placement_plan, "collision_count", 0)
                result.clearance_violations = getattr(placement_plan, "clearance_violations", 0)
                if result.collision_count > 0:
                    result.findings.append(
                        f"{result.collision_count} asset collision(s) detected in placement plan. "
                        "Run hou_mcp_layout_optimizer to resolve before realization."
                    )
                if result.clearance_violations > 0:
                    result.findings.append(
                        f"{result.clearance_violations} clearance violation(s) detected. "
                        "Increase spacing between machines, vehicles, and walls."
                    )

            # Weighted overall
            result.overall_score = (
                result.layout_score       * _WEIGHTS["layout"]      +
                result.population_score   * _WEIGHTS["population"]  +
                result.readability_score  * _WEIGHTS["readability"] +
                result.storytelling_score * _WEIGHTS["storytelling"]
            )

            result.grade = _grade(result.overall_score)
            # collision_count > 0 is a hard block on production_ready
            spatial_ok = result.collision_count == 0
            result.production_ready = (
                result.overall_score >= _PRODUCTION_THRESHOLD
                and not result.findings
                and spatial_ok
            )

            result.recommendations = _build_recommendations(result)
            result.review_summary  = _build_summary(result)

        except Exception as exc:
            result.findings.append(f"Review engine error: {exc}")
            result.review_summary = f"Review failed: {exc}"

        return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _grade(score: float) -> str:
    if score >= 0.90:
        return "A"
    if score >= 0.80:
        return "B"
    if score >= 0.70:
        return "C"
    if score >= 0.60:
        return "D"
    return "F"


def _build_recommendations(result: EnvironmentReviewResult) -> List[str]:
    recs: List[str] = []
    if result.layout_score < 0.6:
        recs.append("Add depth layers: populate midground and background zones.")
    if result.population_score < 0.6:
        recs.append("Rebalance population: ensure hero_assets group has primary assets.")
    if result.readability_score < 0.6:
        recs.append("Improve readability: reduce hero_zone asset count to 1–3.")
    if result.storytelling_score < 0.6:
        recs.append("Strengthen narrative: define hero beat and viewer path.")
    if not recs:
        recs.append("Environment meets production standards — proceed to realization.")
    return recs


def _build_summary(result: EnvironmentReviewResult) -> str:
    if result.production_ready:
        return (
            f"Grade {result.grade} — "
            f"overall {result.overall_score:.2f}. "
            f"Environment meets production readability and storytelling criteria."
        )
    worst_dim = min(
        [
            ("layout",      result.layout_score),
            ("population",  result.population_score),
            ("readability", result.readability_score),
            ("storytelling", result.storytelling_score),
        ],
        key=lambda x: x[1],
    )
    first_finding = result.findings[0] if result.findings else "no specific findings"
    return (
        f"Grade {result.grade} — "
        f"overall {result.overall_score:.2f}. "
        f"Weakest dimension: {worst_dim[0]} ({worst_dim[1]:.2f}). "
        f"Primary issue: {first_finding}"
    )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[EnvironmentReview] = None
_INSTANCE_LOCK = threading.Lock()


def get_environment_review() -> EnvironmentReview:
    """Return the module-level singleton EnvironmentReview."""
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = EnvironmentReview()
    return _INSTANCE


def reset_environment_review_for_tests() -> None:
    """Replace the singleton.  For test isolation only."""
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
