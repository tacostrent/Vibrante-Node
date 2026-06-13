"""
Scene Hierarchy Builder (Tier 3)
==================================
Builds the canonical Houdini scene hierarchy from a layout plan and
generates structured operation dicts for the transaction system.

IMPORTANT DESIGN RULE: This module ONLY generates operation dicts. It NEVER
calls get_bridge() directly for mutations.

Public API:
    SceneHierarchyBuilder
        .build_hierarchy(layout_plan) -> dict
        .assign_assets_to_zones(zones, staging_plan) -> dict
        .generate_network_structure(scene_theme) -> list[dict]
        .validate_hierarchy_integrity(hierarchy) -> dict

    get_scene_hierarchy_builder() -> SceneHierarchyBuilder
    reset_scene_hierarchy_builder_for_tests()
"""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Canonical hierarchy
# ---------------------------------------------------------------------------

_CANONICAL_ROOTS: List[Dict[str, Any]] = [
    {"path": "/obj/environment", "type": "null",   "purpose": "Environment geo and terrain"},
    {"path": "/obj/hero_assets", "type": "null",   "purpose": "Primary hero assets"},
    {"path": "/obj/background",  "type": "null",   "purpose": "Background and midground fill"},
    {"path": "/obj/fx",          "type": "null",   "purpose": "FX networks (pyro, RBD, etc.)"},
    {"path": "/obj/lighting",    "type": "null",   "purpose": "Lighting rigs and sky"},
    {"path": "/obj/camera",      "type": "null",   "purpose": "Cameras and camera animation"},
    {"path": "/obj/render",      "type": "null",   "purpose": "Render setup and ROPs"},
]

# Zone → canonical parent path
_ZONE_PARENTS: Dict[str, str] = {
    "hero_area":   "/obj/hero_assets",
    "midground":   "/obj/background",
    "background":  "/obj/background",
    "ceiling":     "/obj/environment",
    "floor":       "/obj/environment",
    "walls":       "/obj/environment",
    "fx":          "/obj/fx",
    "lighting":    "/obj/lighting",
    "camera":      "/obj/camera",
}

_REQUIRED_HIERARCHY_KEYS = frozenset({
    "roots", "zone_map", "asset_assignments", "network_ops",
})


class SceneHierarchyBuilder:
    """
    Builds the canonical production scene hierarchy as operation dicts.

    Outputs are feed-forward: the returned operation list can be passed
    directly to a TransactionManager for controlled execution.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._build_count = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_hierarchy(
        self,
        layout_plan: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Return the full scene hierarchy description including:
            roots:            list of canonical root descriptions
            zone_map:         {zone: parent_path}
            asset_assignments:{asset_name: parent_path}
            network_ops:      list of create_node operation dicts
            scene_theme:      str
        """
        scene_theme = layout_plan.get("scene_theme", "unknown")
        zones = layout_plan.get("zones", {})

        zone_map: Dict[str, str] = {}
        for zone in zones:
            zone_map[zone] = _ZONE_PARENTS.get(zone, "/obj/background")

        asset_assignments: Dict[str, str] = {}
        for zone, assets in zones.items():
            parent = _ZONE_PARENTS.get(zone, "/obj/background")
            for asset in assets:
                name = asset.get("name", "")
                if name:
                    asset_assignments[name] = parent

        network_ops = self.generate_network_structure(scene_theme)

        with self._lock:
            self._build_count += 1

        return {
            "roots":             [dict(r) for r in _CANONICAL_ROOTS],
            "zone_map":          zone_map,
            "asset_assignments": asset_assignments,
            "network_ops":       network_ops,
            "scene_theme":       scene_theme,
        }

    def assign_assets_to_zones(
        self,
        zones: Dict[str, List[Dict[str, Any]]],
        staging_plan: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Map each asset to its canonical parent path using zone assignment.

        Returns {asset_name: {"zone": str, "parent_path": str, "order": int}}
        """
        import_queue = staging_plan.get("import_queue", [])
        order_map: Dict[str, int] = {
            item["asset_name"]: item["order"]
            for item in import_queue
            if "asset_name" in item
        }

        result: Dict[str, Any] = {}
        for zone, assets in zones.items():
            parent = _ZONE_PARENTS.get(zone, "/obj/background")
            for asset in assets:
                name = asset.get("name", "")
                if name:
                    result[name] = {
                        "zone":        zone,
                        "parent_path": parent,
                        "order":       order_map.get(name, 999),
                    }
        return result

    def generate_network_structure(
        self,
        scene_theme: str,
    ) -> List[Dict[str, Any]]:
        """
        Generate ordered create_node operations for the canonical hierarchy.

        Returns a list of operation dicts in the format accepted by
        houdini_runtime.execute_operation().
        """
        ops: List[Dict[str, Any]] = []
        for root in _CANONICAL_ROOTS:
            path = root["path"]
            parent = "/".join(path.split("/")[:-1]) or "/obj"
            node_name = path.split("/")[-1]
            ops.append({
                "op":     "create_node",
                "parent": parent,
                "type":   "null",
                "name":   node_name,
                "params": {
                    "comment": root["purpose"],
                },
            })
        return ops

    def validate_hierarchy_integrity(
        self,
        hierarchy: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Validate a hierarchy dict produced by build_hierarchy().

        Returns {valid: bool, errors: list[str], warnings: list[str]}
        """
        errors: List[str] = []
        warnings: List[str] = []

        # Check required keys
        missing = _REQUIRED_HIERARCHY_KEYS - set(hierarchy.keys())
        if missing:
            errors.append(f"Missing required hierarchy keys: {sorted(missing)}")

        # Validate roots
        roots = hierarchy.get("roots", [])
        if not roots:
            errors.append("Hierarchy has no root nodes defined.")
        else:
            root_paths = {r.get("path") for r in roots}
            canonical_paths = {r["path"] for r in _CANONICAL_ROOTS}
            missing_roots = canonical_paths - root_paths
            if missing_roots:
                warnings.append(
                    f"Missing canonical roots: {sorted(missing_roots)}"
                )

        # Check zone_map has known zones
        zone_map = hierarchy.get("zone_map", {})
        if not zone_map:
            warnings.append("No zones mapped — scene may be empty.")

        # Check asset_assignments
        asset_assignments = hierarchy.get("asset_assignments", {})
        for asset_name, parent_path in asset_assignments.items():
            if not parent_path.startswith("/obj/"):
                errors.append(
                    f"Asset '{asset_name}' assigned to invalid path: '{parent_path}'"
                )

        # Check network_ops are well-formed
        for i, op in enumerate(hierarchy.get("network_ops", [])):
            if op.get("op") != "create_node":
                errors.append(f"network_ops[{i}] is not a create_node op: {op.get('op')}")
            if not op.get("name"):
                errors.append(f"network_ops[{i}] missing 'name' field.")

        return {
            "valid":    len(errors) == 0,
            "errors":   errors,
            "warnings": warnings,
        }

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def get_zone_parent(self, zone: str) -> str:
        """Return the canonical parent path for a zone name."""
        return _ZONE_PARENTS.get(zone, "/obj/background")

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {"build_count": self._build_count}


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[SceneHierarchyBuilder] = None
_INSTANCE_LOCK = threading.Lock()


def get_scene_hierarchy_builder() -> SceneHierarchyBuilder:
    global _INSTANCE
    with _INSTANCE_LOCK:
        if _INSTANCE is None:
            _INSTANCE = SceneHierarchyBuilder()
        return _INSTANCE


def reset_scene_hierarchy_builder_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
