"""
Scene Asset Realizer (Tier 13)
================================
Generates transaction operation dicts for scene asset realization.
No real Houdini mutations — produces structured op lists.

DESIGN RULES:
  1. No bridge calls, no Houdini imports.
  2. No randomness — same input → same output.
  3. All mutations produce transaction op dicts only.
  4. Never raises in public methods.
  5. Singleton pattern.

Public API:
    RealizationSpec
    RealizationPlan
    RealizedAsset
    SceneAssetRealizer
    get_scene_asset_realizer()
    reset_scene_asset_realizer_for_tests()
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ZONE_PARENTS: Dict[str, str] = {
    "hero_zone":    "/obj/hero_assets",
    "hero_area":    "/obj/hero_assets",
    "midground":    "/obj/background",
    "background":   "/obj/background",
    "service_area": "/obj/background",
    "ceiling":      "/obj/background",
}

_DEFAULT_PARENT = "/obj/background"

_COMPLEXITY_THRESHOLDS = {
    "simple":   10,
    "moderate": 30,
    "complex":  60,
}

_CATEGORY_PREFIXES: Dict[str, str] = {
    "vehicle":      "veh_",
    "character":    "chr_",
    "robot":        "bot_",
    "machinery":    "mch_",
    "structure":    "str_",
    "electronic":   "elc_",
    "prop":         "prp_",
    "terrain":      "ter_",
    "vegetation":   "veg_",
    "material":     "mat_",
    "hdri":         "hdri_",
    "environment":  "env_",
}


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class RealizationSpec:
    """Spec for realizing a single asset in the scene."""

    asset_id:         str              = ""
    asset_name:       str              = ""
    zone:             str              = "hero_zone"
    transform:        Dict[str, float] = field(default_factory=dict)
    parent_path:      str              = "/obj/hero_assets"
    material_profile: Dict[str, Any]   = field(default_factory=dict)
    instance_count:   int              = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id":         self.asset_id,
            "asset_name":       self.asset_name,
            "zone":             self.zone,
            "transform":        dict(self.transform),
            "parent_path":      self.parent_path,
            "material_profile": dict(self.material_profile),
            "instance_count":   self.instance_count,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RealizationSpec":
        return cls(
            asset_id=str(d.get("asset_id", "")),
            asset_name=str(d.get("asset_name", "")),
            zone=str(d.get("zone", "hero_zone")),
            transform=dict(d.get("transform") or {}),
            parent_path=str(d.get("parent_path", "/obj/hero_assets")),
            material_profile=dict(d.get("material_profile") or {}),
            instance_count=int(d.get("instance_count", 1)),
        )


@dataclass
class RealizationPlan:
    """Plan for realizing a set of assets in the scene."""

    plan_id:              str                   = field(default_factory=lambda: f"rplan_{uuid.uuid4().hex[:10]}")
    specs:                List[RealizationSpec] = field(default_factory=list)
    transaction_ops:      List[Dict[str, Any]]  = field(default_factory=list)
    asset_count:          int                   = 0
    estimated_complexity: str                   = "simple"
    errors:               List[str]             = field(default_factory=list)
    warnings:             List[str]             = field(default_factory=list)
    created_at:           float                 = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id":              self.plan_id,
            "specs":                [s.to_dict() for s in self.specs],
            "transaction_ops":      list(self.transaction_ops),
            "asset_count":          self.asset_count,
            "estimated_complexity": self.estimated_complexity,
            "errors":               list(self.errors),
            "warnings":             list(self.warnings),
            "created_at":           self.created_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RealizationPlan":
        specs = [
            RealizationSpec.from_dict(s) if isinstance(s, dict) else s
            for s in (d.get("specs") or [])
        ]
        return cls(
            plan_id=str(d.get("plan_id", f"rplan_{uuid.uuid4().hex[:10]}")),
            specs=specs,
            transaction_ops=list(d.get("transaction_ops") or []),
            asset_count=int(d.get("asset_count", len(specs))),
            estimated_complexity=str(d.get("estimated_complexity", "simple")),
            errors=list(d.get("errors") or []),
            warnings=list(d.get("warnings") or []),
            created_at=float(d.get("created_at") or time.time()),
        )


@dataclass
class RealizedAsset:
    """A single asset that has been realized into a transaction op."""

    asset_id:       str            = ""
    asset_name:     str            = ""
    zone:           str            = "hero_zone"
    node_path:      str            = ""
    transaction_op: Dict[str, Any] = field(default_factory=dict)
    status:         str            = "planned"
    realized_at:    float          = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id":       self.asset_id,
            "asset_name":     self.asset_name,
            "zone":           self.zone,
            "node_path":      self.node_path,
            "transaction_op": dict(self.transaction_op),
            "status":         self.status,
            "realized_at":    self.realized_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RealizedAsset":
        return cls(
            asset_id=str(d.get("asset_id", "")),
            asset_name=str(d.get("asset_name", "")),
            zone=str(d.get("zone", "hero_zone")),
            node_path=str(d.get("node_path", "")),
            transaction_op=dict(d.get("transaction_op") or {}),
            status=str(d.get("status", "planned")),
            realized_at=float(d.get("realized_at") or time.time()),
        )


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class SceneAssetRealizer:
    """
    Generates transaction ops for scene asset realization.
    No bridge calls — produces structured op dicts.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._realize_count = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def realize_asset(
        self,
        asset_dict: Dict[str, Any],
        zone: str = "hero_zone",
        parent_path: str = "/obj/hero_assets",
        transform: Optional[Dict[str, float]] = None,
    ) -> RealizedAsset:
        """Generate a RealizedAsset with its transaction op. Never raises."""
        try:
            return self._do_realize(asset_dict, zone, parent_path, transform or {})
        except Exception as exc:
            safe = asset_dict if isinstance(asset_dict, dict) else {}
            return RealizedAsset(
                asset_id=str(safe.get("asset_id", "")),
                asset_name=str(safe.get("name", "")),
                zone=zone,
                status="failed",
                transaction_op={"error": str(exc)},
            )

    def realize_assets(
        self,
        assets: List[Dict[str, Any]],
        zone_map: Optional[Dict[str, str]] = None,
    ) -> List[RealizedAsset]:
        """Realize a list of assets. Never raises."""
        zone_map = zone_map or {}
        results: List[RealizedAsset] = []
        for a in assets:
            asset_id = str(a.get("asset_id", ""))
            zone     = zone_map.get(asset_id, a.get("zone", "hero_zone"))
            parent   = _ZONE_PARENTS.get(zone, _DEFAULT_PARENT)
            results.append(self.realize_asset(a, zone, parent))
        return results

    def build_realization_plan(
        self,
        assets: List[Dict[str, Any]],
        layout_plan: Optional[Dict[str, Any]] = None,
    ) -> RealizationPlan:
        """Build a full RealizationPlan. Never raises."""
        try:
            return self._do_build_plan(assets, layout_plan)
        except Exception as exc:
            return RealizationPlan(
                errors=[f"Failed to build realization plan: {exc}"],
            )

    def generate_transaction_operations(
        self,
        plan: RealizationPlan,
    ) -> List[Dict[str, Any]]:
        """Extract transaction ops from a RealizationPlan."""
        return [dict(op) for op in plan.transaction_ops]

    def preview_realization(
        self,
        assets: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Preview realization without building a full plan."""
        try:
            plan = self.build_realization_plan(assets)
            zones: Dict[str, int] = {}
            for spec in plan.specs:
                zones[spec.zone] = zones.get(spec.zone, 0) + 1
            return {
                "op_count":   len(plan.transaction_ops),
                "zones":      zones,
                "complexity": plan.estimated_complexity,
                "asset_count": plan.asset_count,
            }
        except Exception as exc:
            return {
                "op_count":   0,
                "zones":      {},
                "complexity": "unknown",
                "error":      str(exc),
            }

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {"realize_count": self._realize_count}

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _do_realize(
        self,
        asset_dict: Dict[str, Any],
        zone: str,
        parent_path: str,
        transform: Dict[str, float],
    ) -> RealizedAsset:
        asset_id   = str(asset_dict.get("asset_id", "") or str(uuid.uuid4()))
        asset_name = str(asset_dict.get("name", asset_id))
        category   = str(asset_dict.get("category", ""))
        prefix     = _CATEGORY_PREFIXES.get(category, "")
        safe_name  = (asset_name.replace(" ", "_").replace("-", "_"))[:32]
        node_name  = f"{prefix}{safe_name}"
        node_path  = f"{parent_path}/{node_name}"

        # Build create_node op
        op: Dict[str, Any] = {
            "op":     "create_node",
            "parent": parent_path,
            "type":   "geo",
            "name":   node_name,
        }

        # Add transform params if non-zero
        tx = float(transform.get("tx", 0.0))
        ty = float(transform.get("ty", 0.0))
        tz = float(transform.get("tz", 0.0))
        if abs(tx) > 1e-6 or abs(ty) > 1e-6 or abs(tz) > 1e-6:
            op["params"] = {"tx": tx, "ty": ty, "tz": tz}

        with self._lock:
            self._realize_count += 1

        return RealizedAsset(
            asset_id=asset_id,
            asset_name=asset_name,
            zone=zone,
            node_path=node_path,
            transaction_op=op,
            status="planned",
        )

    def _do_build_plan(
        self,
        assets: List[Dict[str, Any]],
        layout_plan: Optional[Dict[str, Any]],
    ) -> RealizationPlan:
        specs:   List[RealizationSpec]  = []
        ops:     List[Dict[str, Any]]   = []
        zones_used: Dict[str, int] = {}

        for asset in assets:
            asset_id = str(asset.get("asset_id", ""))
            zone     = str(asset.get("zone", "hero_zone"))
            parent   = _ZONE_PARENTS.get(zone, _DEFAULT_PARENT)

            realized = self._do_realize(asset, zone, parent, {})
            spec = RealizationSpec(
                asset_id=asset_id,
                asset_name=str(asset.get("name", asset_id)),
                zone=zone,
                parent_path=parent,
                instance_count=1,
            )
            specs.append(spec)
            ops.append(realized.transaction_op)
            zones_used[zone] = zones_used.get(zone, 0) + 1

        # Layout ops for containers
        for parent in set(_ZONE_PARENTS.values()):
            ops.append({"op": "layout_children", "path": parent})

        # Complexity
        n = len(ops)
        if n <= _COMPLEXITY_THRESHOLDS["simple"]:
            complexity = "simple"
        elif n <= _COMPLEXITY_THRESHOLDS["moderate"]:
            complexity = "moderate"
        elif n <= _COMPLEXITY_THRESHOLDS["complex"]:
            complexity = "complex"
        else:
            complexity = "epic"

        return RealizationPlan(
            specs=specs,
            transaction_ops=ops,
            asset_count=len(assets),
            estimated_complexity=complexity,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[SceneAssetRealizer] = None
_INSTANCE_LOCK = threading.Lock()


def get_scene_asset_realizer() -> SceneAssetRealizer:
    """Return the module-level singleton SceneAssetRealizer."""
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = SceneAssetRealizer()
    return _INSTANCE


def reset_scene_asset_realizer_for_tests() -> None:
    """Replace the singleton. For test isolation only."""
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
