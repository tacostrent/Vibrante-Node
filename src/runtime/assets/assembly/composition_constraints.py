"""
Composition Constraints (Tier 9 — Semantic Asset Assembly)
==========================================================
Validates cinematic readability of an assembled environment.

Checks:
  - Readability  — viewer can identify the hero without confusion
  - Negative space — hero zone has breathing room
  - Depth        — at least two depth layers populated
  - Balance      — no single zone visually overwhelms the scene
  - Focus        — hero assets receive primary visual weight

DESIGN RULES:
  1. No bridge calls.  No Houdini imports.  Advisory only.
  2. All checks are deterministic — same input → same result.
  3. Errors are blocking; warnings are advisory.
  4. Never raises.

Public API:
    ConstraintResult
    CompositionReport
    CompositionConstraints
    get_composition_constraints()
    reset_composition_constraints_for_tests()
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.runtime.assets.assembly.environment_builder import EnvironmentPlan

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

_MAX_HERO_ASSETS        = 3    # more than this dilutes focus
_MIN_DEPTH_LAYERS       = 2    # need midground + background for depth
_MAX_ZONE_FILL_RATIO    = 0.85 # single zone should not exceed this fraction of all assets
_MIN_NEG_SPACE_RATIO    = 0.2  # hero zone must have at least 20% free capacity


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ConstraintResult:
    """Result of one composition constraint check."""

    check_name:   str
    passed:       bool
    score:        float        # 0.0–1.0 contribution to overall
    issues:       List[str] = field(default_factory=list)
    details:      str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "check_name": self.check_name,
            "passed":     self.passed,
            "score":      self.score,
            "issues":     list(self.issues),
            "details":    self.details,
        }


@dataclass
class CompositionReport:
    """Full composition validation report for an environment."""

    report_id:   str = field(default_factory=lambda: f"comp_{uuid.uuid4().hex[:10]}")
    environment: str = ""
    checks:      List[ConstraintResult] = field(default_factory=list)
    overall_score: float = 0.0       # weighted average of check scores
    readable:    bool = False
    issues:      List[str] = field(default_factory=list)
    warnings:    List[str] = field(default_factory=list)
    generated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id":     self.report_id,
            "environment":   self.environment,
            "checks":        [c.to_dict() for c in self.checks],
            "overall_score": self.overall_score,
            "readable":      self.readable,
            "issues":        list(self.issues),
            "warnings":      list(self.warnings),
            "generated_at":  self.generated_at,
        }


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class CompositionConstraints:
    """
    Validates cinematic readability of an EnvironmentPlan.
    All checks are deterministic and advisory.
    """

    def validate_readability(self, env_plan: EnvironmentPlan) -> ConstraintResult:
        """Hero zone is populated and not overloaded."""
        hero = env_plan.zones.get("hero_zone")
        issues: List[str] = []

        if hero is None:
            issues.append("No hero_zone defined — scene has no primary focal point.")
            return ConstraintResult("readability", False, 0.0, issues,
                                    "Hero zone absent.")
        if not hero.assigned_assets:
            issues.append("hero_zone is empty — nothing draws the viewer's attention.")
            return ConstraintResult("readability", False, 0.2, issues,
                                    "Hero zone empty.")
        if len(hero.assigned_assets) > _MAX_HERO_ASSETS:
            issues.append(
                f"hero_zone has {len(hero.assigned_assets)} assets "
                f"(max {_MAX_HERO_ASSETS}) — focus is diluted."
            )
            return ConstraintResult("readability", False, 0.6, issues,
                                    "Hero zone overloaded.")

        score = 1.0
        details = (
            f"Hero zone has {len(hero.assigned_assets)} asset(s) — "
            "readability within acceptable range."
        )
        return ConstraintResult("readability", True, score, issues, details)

    def validate_negative_space(self, env_plan: EnvironmentPlan) -> ConstraintResult:
        """Hero zone must have breathing room (free capacity ≥ 20%)."""
        hero = env_plan.zones.get("hero_zone")
        issues: List[str] = []

        if hero is None:
            return ConstraintResult("negative_space", False, 0.0,
                                    ["No hero_zone to check."], "")

        capacity  = max(1, hero.max_assets)
        occupied  = len(hero.assigned_assets)
        free_ratio = max(0.0, 1.0 - occupied / capacity)

        if free_ratio < _MIN_NEG_SPACE_RATIO:
            issues.append(
                f"Hero zone is {occupied}/{capacity} slots full — "
                f"negative space below {_MIN_NEG_SPACE_RATIO:.0%} minimum."
            )
            score = free_ratio / _MIN_NEG_SPACE_RATIO * 0.6
            return ConstraintResult("negative_space", False, score, issues,
                                    f"Free: {free_ratio:.0%}")

        details = f"Hero zone has {free_ratio:.0%} free capacity — negative space adequate."
        return ConstraintResult("negative_space", True, 1.0, issues, details)

    def validate_depth(self, env_plan: EnvironmentPlan) -> ConstraintResult:
        """At least two depth layers (midground + background) must be populated."""
        issues: List[str] = []
        populated_depth_zones: List[str] = []

        depth_zone_names = {"midground", "background", "rubble_field",
                            "workstation_row", "console_arc"}
        for name, zone in env_plan.zones.items():
            if (name in depth_zone_names or zone.depth < -5.0) and zone.assigned_assets:
                populated_depth_zones.append(name)

        if len(populated_depth_zones) < _MIN_DEPTH_LAYERS:
            issues.append(
                f"Only {len(populated_depth_zones)} depth layer(s) populated — "
                f"need at least {_MIN_DEPTH_LAYERS} for cinematic depth."
            )
            score = len(populated_depth_zones) / _MIN_DEPTH_LAYERS * 0.7
            return ConstraintResult("depth", False, score, issues,
                                    f"Depth layers: {populated_depth_zones}")

        details = f"Depth layers populated: {populated_depth_zones}"
        return ConstraintResult("depth", True, 1.0, issues, details)

    def validate_balance(self, env_plan: EnvironmentPlan) -> ConstraintResult:
        """No single zone should contain more than 85% of all assets."""
        issues: List[str] = []
        total  = sum(len(z.assigned_assets) for z in env_plan.zones.values())

        if total == 0:
            return ConstraintResult("balance", False, 0.0,
                                    ["No assets assigned to any zone."], "Empty scene.")

        for name, zone in env_plan.zones.items():
            ratio = len(zone.assigned_assets) / total
            if ratio > _MAX_ZONE_FILL_RATIO:
                issues.append(
                    f"Zone {name!r} contains {ratio:.0%} of all assets — "
                    "scene is visually unbalanced."
                )
                return ConstraintResult("balance", False,
                                        1.0 - (ratio - _MAX_ZONE_FILL_RATIO),
                                        issues,
                                        f"Dominant zone: {name} ({ratio:.0%})")

        details = "No single zone dominates — scene is balanced."
        return ConstraintResult("balance", True, 1.0, issues, details)

    def validate_focus(self, env_plan: EnvironmentPlan) -> ConstraintResult:
        """Primary (hero) zone receives proportionally more assets than support zones."""
        issues: List[str] = []
        hero  = env_plan.zones.get("hero_zone")
        total = sum(len(z.assigned_assets) for z in env_plan.zones.values())

        if total == 0 or hero is None:
            return ConstraintResult("focus", False, 0.0,
                                    ["No hero zone or no assets."], "")

        hero_count  = len(hero.assigned_assets)
        hero_ratio  = hero_count / total

        # Primary zone should hold at least 15% of assets
        if hero_ratio < 0.15 and hero_count == 0:
            issues.append("Hero zone is empty — focus criterion fails.")
            return ConstraintResult("focus", False, 0.0, issues, "Hero empty.")

        # Warn if hero_ratio is below 15% but non-zero
        if hero_ratio < 0.15:
            issues.append(
                f"Hero zone holds only {hero_ratio:.0%} of assets — "
                "viewer focus may be diffused."
            )
            score = hero_ratio / 0.15
            return ConstraintResult("focus", False, score, issues,
                                    f"Hero ratio: {hero_ratio:.0%}")

        details = f"Hero zone holds {hero_ratio:.0%} of assets — focus adequate."
        return ConstraintResult("focus", True, 1.0, issues, details)

    def validate_all(self, env_plan: EnvironmentPlan) -> CompositionReport:
        """
        Run all 5 checks and return a CompositionReport.
        readable = overall_score >= 0.6 and no blocking errors.
        """
        report = CompositionReport(environment=env_plan.environment)

        checks = [
            self.validate_readability(env_plan),
            self.validate_negative_space(env_plan),
            self.validate_depth(env_plan),
            self.validate_balance(env_plan),
            self.validate_focus(env_plan),
        ]
        report.checks = checks

        # Collect issues / warnings
        for c in checks:
            if not c.passed:
                report.issues.extend(c.issues)
            else:
                if c.issues:
                    report.warnings.extend(c.issues)

        # Score: equal weight per check
        report.overall_score = sum(c.score for c in checks) / len(checks)
        report.readable      = report.overall_score >= 0.6 and not report.issues
        report.generated_at  = time.time()
        return report


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[CompositionConstraints] = None
_INSTANCE_LOCK = threading.Lock()


def get_composition_constraints() -> CompositionConstraints:
    """Return the module-level singleton CompositionConstraints."""
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = CompositionConstraints()
    return _INSTANCE


def reset_composition_constraints_for_tests() -> None:
    """Replace the singleton.  For test isolation only."""
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
