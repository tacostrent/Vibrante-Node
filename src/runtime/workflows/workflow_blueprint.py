"""
Workflow Blueprint (Tier 10 — Workflow Packs & Production Blueprints)
=====================================================================
Translates a WorkflowPack into an ordered, executable workflow definition.

A WorkflowBlueprint resolves the pack's strategies into concrete phases,
estimates complexity, and produces a transaction-ready execution plan that
downstream systems can validate and execute safely.

DESIGN RULES:
  1. No bridge calls.  No Houdini mutations.  Planning only.
  2. All phases are deterministic — same pack → same blueprint.
  3. Never raises — errors captured in build result.
  4. generate_execution_plan() returns transaction-compatible op dicts.

Public API:
    BlueprintPhase
    WorkflowBlueprint
    get_workflow_blueprint()
    reset_workflow_blueprint_for_tests()
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.runtime.workflows.workflow_pack import WorkflowPack

# ---------------------------------------------------------------------------
# Phase order (canonical)
# ---------------------------------------------------------------------------

PHASE_ORDER = [
    "environment",
    "population",
    "placement",
    "lighting",
    "camera",
    "atmosphere",
    "review",
]

# Complexity thresholds based on total op count
_COMPLEXITY_THRESHOLDS = {
    "simple":   10,
    "moderate": 30,
    "complex":  60,
    # > 60 → "epic"
}


# ---------------------------------------------------------------------------
# BlueprintPhase
# ---------------------------------------------------------------------------

@dataclass
class BlueprintPhase:
    """One phase in the workflow execution plan."""
    phase_name:    str
    description:   str
    operations:    List[Dict[str, Any]] = field(default_factory=list)
    dependencies:  List[str] = field(default_factory=list)
    optional:      bool = False
    metadata:      Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phase_name":   self.phase_name,
            "description":  self.description,
            "operations":   self.operations,
            "dependencies": self.dependencies,
            "optional":     self.optional,
            "metadata":     self.metadata,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "BlueprintPhase":
        return cls(
            phase_name   = d.get("phase_name", ""),
            description  = d.get("description", ""),
            operations   = d.get("operations", []),
            dependencies = d.get("dependencies", []),
            optional     = d.get("optional", False),
            metadata     = d.get("metadata", {}),
        )


# ---------------------------------------------------------------------------
# WorkflowBlueprint
# ---------------------------------------------------------------------------

class WorkflowBlueprint:
    """Executable workflow definition derived from a WorkflowPack."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._build_count = 0

    # -----------------------------------------------------------------
    def build_blueprint(self, pack: WorkflowPack) -> Dict[str, Any]:
        """
        Build the complete blueprint dict from a WorkflowPack.

        Returns:
            {
              "ok": bool,
              "workflow": str,      # pack name
              "environment": str,
              "phases": [str, ...],
              "phase_details": [...],
              "dependencies": {phase: [deps]},
              "estimated_complexity": str,
              "total_ops": int,
              "blueprint_id": str,
              "generated_at": float,
              "errors": [...]
            }
        """
        with self._lock:
            self._build_count += 1

        errors = pack.validate()
        if errors:
            return {
                "ok":     False,
                "errors": errors,
                "workflow": pack.name,
                "phases":   [],
            }

        phases = self._build_phases(pack)
        deps   = self._resolve_dependencies(phases)
        total_ops = sum(len(p.operations) for p in phases)
        complexity = self._estimate_complexity(total_ops)

        return {
            "ok":                    True,
            "workflow":              pack.name,
            "environment":           pack.environment_type,
            "phases":                [p.phase_name for p in phases],
            "phase_details":         [p.to_dict() for p in phases],
            "dependencies":          deps,
            "estimated_complexity":  complexity,
            "total_ops":             total_ops,
            "blueprint_id":          str(uuid.uuid4()),
            "generated_at":          time.time(),
            "errors":                [],
        }

    # -----------------------------------------------------------------
    def _build_phases(self, pack: WorkflowPack) -> List[BlueprintPhase]:
        builders = {
            "environment": self._phase_environment,
            "population":  self._phase_population,
            "placement":   self._phase_placement,
            "lighting":    self._phase_lighting,
            "camera":      self._phase_camera,
            "atmosphere":  self._phase_atmosphere,
            "review":      self._phase_review,
        }
        return [builders[name](pack) for name in PHASE_ORDER]

    # -----------------------------------------------------------------
    def _phase_environment(self, pack: WorkflowPack) -> BlueprintPhase:
        env = pack.environment_type
        ops = [
            {"op": "create_node", "parent": "/obj/environment", "type": "geo",  "name": "ground_geo"},
            {"op": "create_node", "parent": "/obj/hero_assets",  "type": "null", "name": "hero_root"},
            {"op": "create_node", "parent": "/obj/background",   "type": "null", "name": "bg_root"},
        ]
        fog = pack.atmosphere_strategy.get("fog_density", "medium")
        if fog not in ("none", ""):
            ops.append({"op": "create_node", "parent": "/obj/environment",
                         "type": "pyro", "name": "fog_volume"})
        return BlueprintPhase(
            phase_name   = "environment",
            description  = f"Build canonical /obj hierarchy for {env}",
            operations   = ops,
            dependencies = [],
        )

    def _phase_population(self, pack: WorkflowPack) -> BlueprintPhase:
        pop = pack.population_strategy
        ops = [
            {"op": "set_parms", "node": "/obj/hero_assets/hero_root",
             "parms": {"max_assets": pop.get("hero_max", 3)}},
            {"op": "set_parms", "node": "/obj/background/bg_root",
             "parms": {"detail_cap": pop.get("detail_cap", 0.60)}},
        ]
        return BlueprintPhase(
            phase_name   = "population",
            description  = "Assign asset groups and population limits",
            operations   = ops,
            dependencies = ["environment"],
        )

    def _phase_placement(self, pack: WorkflowPack) -> BlueprintPhase:
        tmpl = pack.placement_strategy.get("template", pack.environment_type)
        ops = [
            {"op": "layout_children", "path": "/obj/hero_assets"},
            {"op": "layout_children", "path": "/obj/background"},
            {"op": "layout_children", "path": "/obj/environment"},
        ]
        return BlueprintPhase(
            phase_name   = "placement",
            description  = f"Apply deterministic placement template: {tmpl}",
            operations   = ops,
            dependencies = ["population"],
            metadata     = {"template": tmpl},
        )

    def _phase_lighting(self, pack: WorkflowPack) -> BlueprintPhase:
        style  = pack.lighting_strategy.get("style", "cinematic_industrial")
        target = pack.lighting_strategy.get("key_target", "hero_zone")
        ops = [
            {"op": "create_node", "parent": "/obj/lighting", "type": "envlight",
             "name": f"key_{style}"},
            {"op": "create_node", "parent": "/obj/lighting", "type": "envlight",
             "name": "rim_light"},
        ]
        if pack.lighting_strategy.get("volumetric", True):
            ops.append({"op": "create_node", "parent": "/obj/lighting",
                         "type": "envlight", "name": "vol_light"})
        return BlueprintPhase(
            phase_name   = "lighting",
            description  = f"Apply lighting preset: {style} targeting {target}",
            operations   = ops,
            dependencies = ["environment"],
            metadata     = {"style": style, "key_target": target},
        )

    def _phase_camera(self, pack: WorkflowPack) -> BlueprintPhase:
        mode = pack.camera_strategy.get("mode", "cinematic_push_in")
        ops  = [
            {"op": "create_node", "parent": "/obj/camera", "type": "cam",
             "name": "wide_establishing"},
        ]
        if pack.camera_strategy.get("hero_shot", True):
            ops.append({"op": "create_node", "parent": "/obj/camera",
                         "type": "cam", "name": "hero_cam"})
        return BlueprintPhase(
            phase_name   = "camera",
            description  = f"Set up camera targets using mode: {mode}",
            operations   = ops,
            dependencies = ["environment"],
            metadata     = {"mode": mode},
        )

    def _phase_atmosphere(self, pack: WorkflowPack) -> BlueprintPhase:
        atm  = pack.atmosphere_strategy.get("atmosphere_type", "industrial_fog")
        fog  = pack.atmosphere_strategy.get("fog_density", "medium")
        ops  = []
        if fog not in ("none", ""):
            ops.append({"op": "set_parms", "node": "/obj/environment/fog_volume",
                         "parms": {"density": fog}})
        if pack.atmosphere_strategy.get("particles", True):
            ops.append({"op": "create_node", "parent": "/obj/fx",
                         "type": "pyro", "name": "particle_layer"})
        return BlueprintPhase(
            phase_name   = "atmosphere",
            description  = f"Configure atmospheric depth: {atm} (density={fog})",
            operations   = ops,
            dependencies = ["environment", "lighting"],
            optional     = fog in ("none", ""),
            metadata     = {"atmosphere_type": atm, "fog_density": fog},
        )

    def _phase_review(self, pack: WorkflowPack) -> BlueprintPhase:
        threshold = pack.review_strategy.get("production_threshold", 0.70)
        ops: List[Dict[str, Any]] = []   # review is advisory — no mutation ops
        return BlueprintPhase(
            phase_name   = "review",
            description  = (
                f"Evaluate production quality (threshold={threshold:.2f}); "
                "requires specific per-dimension findings"
            ),
            operations   = ops,
            dependencies = ["lighting", "camera", "atmosphere"],
            metadata     = {"threshold": threshold},
        )

    # -----------------------------------------------------------------
    def _resolve_dependencies(
        self, phases: List[BlueprintPhase]
    ) -> Dict[str, List[str]]:
        return {p.phase_name: p.dependencies for p in phases}

    def _estimate_complexity(self, total_ops: int) -> str:
        if total_ops <= _COMPLEXITY_THRESHOLDS["simple"]:
            return "simple"
        if total_ops <= _COMPLEXITY_THRESHOLDS["moderate"]:
            return "moderate"
        if total_ops <= _COMPLEXITY_THRESHOLDS["complex"]:
            return "complex"
        return "epic"

    # -----------------------------------------------------------------
    def resolve_dependencies(self, blueprint: Dict[str, Any]) -> List[str]:
        """Return topologically-sorted phase execution order."""
        deps   = blueprint.get("dependencies", {})
        phases = blueprint.get("phases", [])
        order: List[str] = []
        remaining = list(phases)
        while remaining:
            added = False
            for p in list(remaining):
                if all(d in order for d in deps.get(p, [])):
                    order.append(p)
                    remaining.remove(p)
                    added = True
            if not added:
                # cycle or missing dep — append remainder as-is
                order.extend(remaining)
                break
        return order

    def generate_execution_plan(self, blueprint: Dict[str, Any]) -> Dict[str, Any]:
        """
        Flatten all phase operations into an ordered transaction-compatible plan.
        """
        if not blueprint.get("ok", False):
            return {"ok": False, "operations": [], "errors": blueprint.get("errors", [])}

        ordered_phases = self.resolve_dependencies(blueprint)
        phase_map = {p["phase_name"]: p for p in blueprint.get("phase_details", [])}

        ops: List[Dict[str, Any]] = []
        for pname in ordered_phases:
            phase = phase_map.get(pname)
            if phase:
                ops.extend(phase.get("operations", []))

        return {
            "ok":            True,
            "workflow":      blueprint.get("workflow", ""),
            "environment":   blueprint.get("environment", ""),
            "operations":    ops,
            "op_count":      len(ops),
            "phase_order":   ordered_phases,
            "complexity":    blueprint.get("estimated_complexity", "moderate"),
            "blueprint_id":  blueprint.get("blueprint_id", ""),
        }

    def validate_blueprint(self, blueprint: Dict[str, Any]) -> Dict[str, Any]:
        """Check a blueprint for structural integrity."""
        errors: List[str] = []
        warnings: List[str] = []
        if not blueprint.get("workflow"):
            errors.append("blueprint missing 'workflow' (pack name)")
        phases = blueprint.get("phases", [])
        if not phases:
            errors.append("blueprint has no phases")
        for pname in PHASE_ORDER:
            if pname not in phases:
                warnings.append(f"phase '{pname}' is absent from blueprint")
        return {
            "valid":    len(errors) == 0,
            "errors":   errors,
            "warnings": warnings,
        }

    def estimate_complexity(self, blueprint: Dict[str, Any]) -> str:
        total = blueprint.get("total_ops", 0)
        return self._estimate_complexity(total)

    def stats(self) -> Dict[str, Any]:
        return {"build_count": self._build_count}


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[WorkflowBlueprint] = None
_lock = threading.Lock()


def get_workflow_blueprint() -> WorkflowBlueprint:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = WorkflowBlueprint()
    return _instance


def reset_workflow_blueprint_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
