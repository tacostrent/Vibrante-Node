"""
Material Assignment Engine (Tier 14)
======================================
Generates semantic material assignment plans as transaction operation dicts.
Never mutates Houdini state directly — all output is advisory planning data.

Deterministic, thread-safe, no Houdini dependency.
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .material_recommendation import get_material_recommendation_engine
from .renderer_profiles import SUPPORTED_RENDERERS


def _normalize_renderer(renderer: str) -> str:
    r = str(renderer or "usd_preview_surface").lower().strip()
    return r if r in SUPPORTED_RENDERERS else "usd_preview_surface"


@dataclass
class AssignmentEntry:
    entry_id: str = field(default_factory=lambda: f"asgn_{uuid.uuid4().hex[:8]}")
    asset_id: str = ""
    asset_name: str = ""
    material_name: str = ""
    material_id: str = ""
    renderer: str = "usd_preview_surface"
    confidence: float = 0.5
    assignment_ops: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id":       str(self.entry_id),
            "asset_id":       str(self.asset_id),
            "asset_name":     str(self.asset_name),
            "material_name":  str(self.material_name),
            "material_id":    str(self.material_id),
            "renderer":       str(self.renderer),
            "confidence":     float(self.confidence),
            "assignment_ops": list(self.assignment_ops),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AssignmentEntry":
        d = d if isinstance(d, dict) else {}
        return cls(
            entry_id=str(d.get("entry_id") or f"asgn_{uuid.uuid4().hex[:8]}"),
            asset_id=str(d.get("asset_id", "")),
            asset_name=str(d.get("asset_name", "")),
            material_name=str(d.get("material_name", "")),
            material_id=str(d.get("material_id", "")),
            renderer=str(d.get("renderer", "usd_preview_surface")),
            confidence=float(d.get("confidence") or 0.5),
            assignment_ops=list(d.get("assignment_ops") or []),
        )


@dataclass
class AssignmentPlan:
    plan_id: str = field(default_factory=lambda: f"plan_{uuid.uuid4().hex[:8]}")
    assignments: List[AssignmentEntry] = field(default_factory=list)
    total_assets: int = 0
    total_assigned: int = 0
    renderer: str = "usd_preview_surface"
    ok: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id":        str(self.plan_id),
            "assignments":    [a.to_dict() for a in self.assignments],
            "total_assets":   int(self.total_assets),
            "total_assigned": int(self.total_assigned),
            "renderer":       str(self.renderer),
            "ok":             bool(self.ok),
            "errors":         list(self.errors),
            "warnings":       list(self.warnings),
            "created_at":     float(self.created_at),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AssignmentPlan":
        d = d if isinstance(d, dict) else {}
        assignments = [
            AssignmentEntry.from_dict(a)
            for a in (d.get("assignments") or [])
            if isinstance(a, dict)
        ]
        return cls(
            plan_id=str(d.get("plan_id") or f"plan_{uuid.uuid4().hex[:8]}"),
            assignments=assignments,
            total_assets=int(d.get("total_assets") or 0),
            total_assigned=int(d.get("total_assigned") or 0),
            renderer=str(d.get("renderer", "usd_preview_surface")),
            ok=bool(d.get("ok", True)),
            errors=list(d.get("errors") or []),
            warnings=list(d.get("warnings") or []),
            created_at=float(d.get("created_at") or time.time()),
        )


class MaterialAssignmentEngine:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._assign_count = 0

    def assign_materials(
        self,
        asset_dict: Dict[str, Any],
        renderer: str = "usd_preview_surface",
    ) -> AssignmentEntry:
        """Recommend and build an assignment op for a single asset."""
        try:
            return self._do_assign(asset_dict, renderer)
        except Exception as exc:
            safe = asset_dict if isinstance(asset_dict, dict) else {}
            return AssignmentEntry(
                asset_id=str(safe.get("asset_id", "")),
                asset_name=str(safe.get("name", "")),
                renderer=_normalize_renderer(renderer),
                assignment_ops=[{"op": "assign_material_failed", "error": str(exc)}],
            )

    def _do_assign(
        self,
        asset_dict: Dict[str, Any],
        renderer: str,
    ) -> AssignmentEntry:
        asset_dict = asset_dict if isinstance(asset_dict, dict) else {}
        renderer = _normalize_renderer(renderer)
        asset_id   = str(asset_dict.get("asset_id", ""))
        asset_name = str(asset_dict.get("name", asset_dict.get("asset_name", "")))

        result = get_material_recommendation_engine().recommend_material(asset_dict, renderer)
        if result.recommendations:
            rec = result.recommendations[0]
            mat_name = rec.material_name
            confidence = rec.confidence
        else:
            mat_name = "industrial_metal"
            confidence = 0.5

        mat_id = f"builtin_{mat_name}"
        op = {
            "op":          "assign_material",
            "asset_id":    asset_id,
            "asset_name":  asset_name,
            "material":    mat_name,
            "material_id": mat_id,
            "renderer":    renderer,
            "confidence":  confidence,
        }

        with self._lock:
            self._assign_count += 1

        return AssignmentEntry(
            asset_id=asset_id,
            asset_name=asset_name,
            material_name=mat_name,
            material_id=mat_id,
            renderer=renderer,
            confidence=confidence,
            assignment_ops=[op],
        )

    def assign_environment_materials(
        self,
        environment: str,
        assets: List[Dict[str, Any]],
        renderer: str = "usd_preview_surface",
    ) -> AssignmentPlan:
        """Assign materials to a list of assets within a named environment."""
        try:
            renderer = _normalize_renderer(renderer)
            assets = assets if isinstance(assets, list) else []
            assignments: List[AssignmentEntry] = []
            errors: List[str] = []
            warnings: List[str] = []

            # Get the environment material set
            env_result = get_material_recommendation_engine().recommend_environment_materials(
                environment, renderer
            )
            env_materials = [r.material_name for r in env_result.recommendations]

            for i, asset in enumerate(assets):
                asset = asset if isinstance(asset, dict) else {}
                # Inject environment into asset for context
                enriched = dict(asset)
                enriched.setdefault("environment", environment)
                entry = self._do_assign(enriched, renderer)
                # Prefer env materials if available
                if env_materials and entry.material_name not in env_materials:
                    mat_name = env_materials[i % len(env_materials)]
                    mat_id = f"builtin_{mat_name}"
                    entry.material_name = mat_name
                    entry.material_id = mat_id
                    if entry.assignment_ops:
                        entry.assignment_ops[0]["material"] = mat_name
                        entry.assignment_ops[0]["material_id"] = mat_id
                assignments.append(entry)

            with self._lock:
                self._assign_count += 1

            return AssignmentPlan(
                assignments=assignments,
                total_assets=len(assets),
                total_assigned=len(assignments),
                renderer=renderer,
                ok=True,
                errors=errors,
                warnings=warnings,
            )
        except Exception as exc:
            return AssignmentPlan(
                renderer=_normalize_renderer(renderer),
                ok=False,
                errors=[f"assign_environment_materials failed: {exc}"],
            )

    def assign_asset_materials(
        self,
        asset_list: List[Dict[str, Any]],
        renderer: str = "usd_preview_surface",
    ) -> AssignmentPlan:
        try:
            renderer = _normalize_renderer(renderer)
            asset_list = asset_list if isinstance(asset_list, list) else []
            assignments: List[AssignmentEntry] = []
            for asset in asset_list:
                entry = self.assign_materials(asset, renderer)
                assignments.append(entry)
            with self._lock:
                self._assign_count += 1
            return AssignmentPlan(
                assignments=assignments,
                total_assets=len(asset_list),
                total_assigned=len(assignments),
                renderer=renderer,
                ok=True,
            )
        except Exception as exc:
            return AssignmentPlan(
                renderer=_normalize_renderer(renderer),
                ok=False,
                errors=[f"assign_asset_materials failed: {exc}"],
            )

    def validate_assignments(self, plan_dict: Dict[str, Any]) -> Dict[str, Any]:
        try:
            plan_dict = plan_dict if isinstance(plan_dict, dict) else {}
            errors: List[str] = []
            warnings: List[str] = []

            assignments = plan_dict.get("assignments") or []
            if not isinstance(assignments, list):
                errors.append("'assignments' field must be a list.")
            else:
                for i, a in enumerate(assignments):
                    if not isinstance(a, dict):
                        errors.append(f"Assignment {i}: not a dict.")
                        continue
                    if not a.get("asset_id") and not a.get("asset_name"):
                        warnings.append(f"Assignment {i}: missing asset_id and asset_name.")
                    if not a.get("material_name"):
                        errors.append(f"Assignment {i}: missing material_name.")
                    if not a.get("renderer"):
                        warnings.append(f"Assignment {i}: missing renderer.")

            renderer = str(plan_dict.get("renderer", ""))
            if renderer and renderer not in SUPPORTED_RENDERERS:
                warnings.append(f"Renderer '{renderer}' is not in SUPPORTED_RENDERERS.")

            return {
                "ok":           len(errors) == 0,
                "errors":       errors,
                "warnings":     warnings,
                "validated_at": time.time(),
            }
        except Exception as exc:
            return {"ok": False, "errors": [f"validate_assignments failed: {exc}"], "warnings": [], "validated_at": time.time()}

    def generate_assignment_plan(
        self,
        asset_list: List[Dict[str, Any]],
        renderer: str = "usd_preview_surface",
    ) -> AssignmentPlan:
        """Full plan generation: assign + validate."""
        try:
            plan = self.assign_asset_materials(asset_list, renderer)
            validation = self.validate_assignments(plan.to_dict())
            plan.errors.extend(validation.get("errors") or [])
            plan.warnings.extend(validation.get("warnings") or [])
            if validation.get("errors"):
                plan.ok = False
            return plan
        except Exception as exc:
            return AssignmentPlan(
                renderer=_normalize_renderer(renderer),
                ok=False,
                errors=[f"generate_assignment_plan failed: {exc}"],
            )


_INSTANCE: Optional[MaterialAssignmentEngine] = None
_INSTANCE_LOCK = threading.Lock()


def get_material_assignment_engine() -> MaterialAssignmentEngine:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = MaterialAssignmentEngine()
    return _INSTANCE


def reset_material_assignment_engine_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
