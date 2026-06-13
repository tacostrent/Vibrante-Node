"""
Scene Plan Validator (Tier 7 — Scene Planning Runtime)
=======================================================
Validates a ScenePlan for structural consistency and completeness.

Checks:
  1. Has at least one zone
  2. Each zone has at least one asset category
  3. Has at least one camera target
  4. Has at least one composition rule
  5. estimated_asset_count > 0 (non-trivial plan)
  6. Zone priorities are in valid range (1–10)
  7. No duplicate zone types (warn, not error)
  8. Asset query priorities are valid values
  9. Camera shot types are valid values
  10. Composition rule types are valid values

Validator mutates plan.validation_errors / plan.validation_warnings and
sets plan.validated = True after running.

DESIGN RULES:
  - No bridge calls. No LLM calls.
  - Non-destructive: only writes to validation_errors, validation_warnings, validated.
  - Returns a ValidationReport with structured findings.

Public API:
    ValidationReport
        .valid, .errors, .warnings, .check_count
    ScenePlanValidator
        .validate(plan) -> ValidationReport
    get_scene_plan_validator() -> ScenePlanValidator   (singleton)
    reset_scene_plan_validator_for_tests()
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, List, Optional

from src.runtime.planning.schema.scene_plan import (
    ASSET_PRIORITIES,
    COMPOSITION_RULE_TYPES,
    SHOT_TYPES,
    ZONE_TYPES,
    ScenePlan,
)

# ---------------------------------------------------------------------------
# ValidationReport
# ---------------------------------------------------------------------------

@dataclass
class ValidationReport:
    """Structured result from ScenePlanValidator.validate().

    Attributes:
        valid:        True when zero blocking errors.
        errors:       Blocking issues.
        warnings:     Advisory issues (do not block downstream use).
        check_count:  Number of checks that ran.
    """

    valid:       bool       = True
    errors:      List[str]  = field(default_factory=list)
    warnings:    List[str]  = field(default_factory=list)
    check_count: int        = 0

    def to_dict(self):
        return {
            "valid":       self.valid,
            "errors":      list(self.errors),
            "warnings":    list(self.warnings),
            "check_count": self.check_count,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
        }


# ---------------------------------------------------------------------------
# ScenePlanValidator
# ---------------------------------------------------------------------------

class ScenePlanValidator:
    """Validates a ScenePlan for structural correctness."""

    def validate(self, plan: ScenePlan) -> ValidationReport:
        """Run all checks against *plan*.

        Mutates ``plan.validation_errors``, ``plan.validation_warnings``,
        and sets ``plan.validated = True``.

        Returns:
            :class:`ValidationReport` with structured findings.
        """
        report = ValidationReport()
        checks = 0

        # 1. Has at least one zone
        checks += 1
        if not plan.zones:
            report.errors.append("Plan has no zones — at least one zone is required.")

        # 2. Each zone has at least one asset category
        checks += 1
        for zone in plan.zones:
            if not getattr(zone, "asset_categories", []):
                report.errors.append(
                    f"Zone {zone.zone_type!r} has no asset categories."
                )

        # 3. Has at least one camera target
        checks += 1
        if not plan.camera_targets:
            report.errors.append("Plan has no camera targets.")

        # 4. Has at least one composition rule
        checks += 1
        if not plan.composition_rules:
            report.errors.append("Plan has no composition rules.")

        # 5. Non-trivial estimated asset count
        checks += 1
        if plan.estimated_asset_count == 0:
            report.warnings.append(
                "estimated_asset_count is 0 — plan may be trivially empty."
            )

        # 6. Zone priorities in valid range
        checks += 1
        for zone in plan.zones:
            p = getattr(zone, "priority", None)
            if p is not None and not (1 <= p <= 10):
                report.errors.append(
                    f"Zone {zone.zone_type!r} has out-of-range priority {p} (must be 1–10)."
                )

        # 7. No duplicate zone types (warning)
        checks += 1
        seen_zone_types: set = set()
        for zone in plan.zones:
            zt = getattr(zone, "zone_type", "")
            if zt in seen_zone_types:
                report.warnings.append(
                    f"Duplicate zone type {zt!r} — consider merging or renaming."
                )
            seen_zone_types.add(zt)

        # 8. Asset query priorities are valid
        checks += 1
        for q in plan.asset_queries:
            p = getattr(q, "priority", "")
            if p not in ASSET_PRIORITIES:
                report.warnings.append(
                    f"AssetQuery category={q.category!r} has unknown priority {p!r}."
                )

        # 9. Camera shot types are valid
        checks += 1
        for t in plan.camera_targets:
            st = getattr(t, "shot_type", "")
            if st not in SHOT_TYPES:
                report.warnings.append(
                    f"CameraTarget {t.name!r} has unknown shot_type {st!r}."
                )

        # 10. Composition rule types are valid
        checks += 1
        for r in plan.composition_rules:
            rt = getattr(r, "rule_type", "")
            if rt not in COMPOSITION_RULE_TYPES:
                report.warnings.append(
                    f"CompositionRule has unknown rule_type {rt!r}."
                )

        # Finalize
        report.check_count = checks
        report.valid       = len(report.errors) == 0

        # Mutate plan
        plan.validation_errors   = list(report.errors)
        plan.validation_warnings = list(report.warnings)
        plan.validated           = True

        return report


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[ScenePlanValidator] = None
_INSTANCE_LOCK = threading.Lock()


def get_scene_plan_validator() -> ScenePlanValidator:
    """Return the module-level singleton ScenePlanValidator."""
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = ScenePlanValidator()
    return _INSTANCE


def reset_scene_plan_validator_for_tests() -> None:
    """Replace the singleton. For test isolation only."""
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
