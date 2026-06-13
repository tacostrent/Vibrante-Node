"""
Workflow Validator (Tier 10 — Workflow Packs & Production Blueprints)
=====================================================================
Validates workflow packs and execution plans for structural integrity,
dependency consistency, environment support, and review thresholds.

DESIGN RULES:
  1. No bridge calls.  Stateless.  No Houdini imports.
  2. Validation is advisory — it never blocks execution directly.
  3. validate_pack() is the primary entry point.
  4. All methods return {valid, warnings, errors}.

Public API:
    ValidationReport
    WorkflowValidator
    get_workflow_validator()
    reset_workflow_validator_for_tests()
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.runtime.workflows.workflow_pack import WorkflowPack, VALID_ENVIRONMENT_TYPES
from src.runtime.workflows.workflow_blueprint import PHASE_ORDER

_VALID_LIGHTING_STYLES = frozenset({
    "cinematic_industrial",
    "bladerunner_noir",
    "cold_scifi",
    "atmospheric_lab",
    "warm_control_room",
})

_VALID_CAMERA_MODES = frozenset({
    "cinematic_push_in",
    "orbital_reveal",
    "hero_focus",
    "atmospheric_tracking",
    "handheld_subtle",
})

_VALID_ATMOSPHERE_TYPES = frozenset({
    "industrial_fog",
    "volumetric_scifi",
    "dusty_hangar",
    "cold_atmosphere",
    "cinematic_depth_fog",
})

_VALID_FOG_DENSITIES = frozenset({"none", "light", "medium", "heavy"})


@dataclass
class ValidationReport:
    """Output of any WorkflowValidator check."""
    valid:    bool
    warnings: List[str] = field(default_factory=list)
    errors:   List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid":    self.valid,
            "warnings": self.warnings,
            "errors":   self.errors,
        }


class WorkflowValidator:
    """Validates workflow packs and derived artefacts."""

    def __init__(self) -> None:
        self._validation_count = 0
        self._lock = threading.Lock()

    # -----------------------------------------------------------------
    def validate_pack(self, pack: WorkflowPack) -> ValidationReport:
        """Full structural validation of a WorkflowPack."""
        with self._lock:
            self._validation_count += 1

        errors:   List[str] = []
        warnings: List[str] = []

        # Delegate to pack's own validator first
        pack_errors = pack.validate()
        errors.extend(pack_errors)

        # Extended strategy checks
        env_report  = self.validate_environment(pack.environment_type)
        errors.extend(env_report.errors)
        warnings.extend(env_report.warnings)

        lighting = pack.lighting_strategy.get("style", "")
        if lighting and lighting not in _VALID_LIGHTING_STYLES:
            warnings.append(
                f"lighting_strategy.style {lighting!r} is not a known preset; "
                f"known: {sorted(_VALID_LIGHTING_STYLES)}"
            )

        camera = pack.camera_strategy.get("mode", "")
        if camera and camera not in _VALID_CAMERA_MODES:
            warnings.append(
                f"camera_strategy.mode {camera!r} is not a known mode; "
                f"known: {sorted(_VALID_CAMERA_MODES)}"
            )

        fog = pack.atmosphere_strategy.get("fog_density", "medium")
        if fog not in _VALID_FOG_DENSITIES:
            warnings.append(
                f"atmosphere_strategy.fog_density {fog!r} is not a known value; "
                f"known: {sorted(_VALID_FOG_DENSITIES)}"
            )

        threshold_report = self.validate_review_thresholds(pack.review_strategy)
        errors.extend(threshold_report.errors)
        warnings.extend(threshold_report.warnings)

        return ValidationReport(valid=len(errors) == 0, warnings=warnings, errors=errors)

    # -----------------------------------------------------------------
    def validate_dependencies(
        self, dependencies: Dict[str, List[str]]
    ) -> ValidationReport:
        """Check that all phase deps exist and there are no cycles."""
        errors:   List[str] = []
        warnings: List[str] = []

        known = set(dependencies.keys())
        for phase, deps in dependencies.items():
            for dep in deps:
                if dep not in known:
                    errors.append(
                        f"Phase '{phase}' depends on unknown phase '{dep}'"
                    )
            if phase in deps:
                errors.append(f"Phase '{phase}' depends on itself (self-cycle)")

        # Cycle detection (simple DFS)
        visited: set = set()
        path:    set = set()

        def _has_cycle(node: str) -> bool:
            if node in path:
                return True
            if node in visited:
                return False
            path.add(node)
            for dep in dependencies.get(node, []):
                if _has_cycle(dep):
                    return True
            path.discard(node)
            visited.add(node)
            return False

        for phase in dependencies:
            if _has_cycle(phase):
                errors.append(
                    f"Dependency cycle detected involving phase '{phase}'"
                )
                break

        return ValidationReport(valid=len(errors) == 0, warnings=warnings, errors=errors)

    # -----------------------------------------------------------------
    def validate_execution_plan(self, plan: Dict[str, Any]) -> ValidationReport:
        """Validate a generated execution plan dict."""
        errors:   List[str] = []
        warnings: List[str] = []

        if not plan.get("ok", False):
            errors.extend(plan.get("errors", ["plan is not ok"]))
            return ValidationReport(valid=False, errors=errors)

        ops = plan.get("operations", [])
        for i, op in enumerate(ops):
            if not isinstance(op, dict):
                errors.append(f"operation[{i}] is not a dict")
                continue
            if "op" not in op:
                errors.append(f"operation[{i}] missing required 'op' key")

        phase_order = plan.get("phase_order", [])
        for pname in PHASE_ORDER:
            if pname != "review" and pname not in phase_order:
                warnings.append(f"phase '{pname}' absent from execution plan")

        return ValidationReport(valid=len(errors) == 0, warnings=warnings, errors=errors)

    # -----------------------------------------------------------------
    def validate_environment(self, environment_type: str) -> ValidationReport:
        """Check that the environment type is supported."""
        errors:   List[str] = []
        warnings: List[str] = []
        if not environment_type:
            errors.append("environment_type is empty")
        elif environment_type not in VALID_ENVIRONMENT_TYPES:
            errors.append(
                f"environment_type {environment_type!r} is not supported; "
                f"supported: {sorted(VALID_ENVIRONMENT_TYPES)}"
            )
        return ValidationReport(valid=len(errors) == 0, warnings=warnings, errors=errors)

    # -----------------------------------------------------------------
    def validate_review_thresholds(
        self, review_strategy: Dict[str, Any]
    ) -> ValidationReport:
        """Check that review threshold values are in valid ranges."""
        errors:   List[str] = []
        warnings: List[str] = []

        threshold = review_strategy.get("production_threshold")
        if threshold is not None:
            try:
                t = float(threshold)
                if not (0.0 <= t <= 1.0):
                    errors.append(
                        f"production_threshold {t} out of range [0, 1]"
                    )
                elif t < 0.50:
                    warnings.append(
                        f"production_threshold {t} is very low — scenes may "
                        "not meet production quality standards"
                    )
            except (TypeError, ValueError):
                errors.append(
                    f"production_threshold must be numeric; got {threshold!r}"
                )

        min_read = review_strategy.get("min_readability")
        if min_read is not None:
            try:
                r = float(min_read)
                if not (0.0 <= r <= 1.0):
                    errors.append(
                        f"min_readability {r} out of range [0, 1]"
                    )
            except (TypeError, ValueError):
                errors.append(
                    f"min_readability must be numeric; got {min_read!r}"
                )

        return ValidationReport(valid=len(errors) == 0, warnings=warnings, errors=errors)

    # -----------------------------------------------------------------
    def stats(self) -> Dict[str, Any]:
        return {"validation_count": self._validation_count}


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[WorkflowValidator] = None
_lock = threading.Lock()


def get_workflow_validator() -> WorkflowValidator:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = WorkflowValidator()
    return _instance


def reset_workflow_validator_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
