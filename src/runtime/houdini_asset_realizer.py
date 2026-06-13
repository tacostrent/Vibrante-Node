"""
Houdini Asset Realizer (Tier 3)
================================
Converts a semantic staging plan into a list of structured transaction
operations that the TransactionManager + houdini_runtime can execute.

IMPORTANT DESIGN RULE: This module ONLY generates operation dicts. It NEVER
calls get_bridge() or mutates Houdini directly. All mutations go through
the transaction system for rollback safety.

Architecture:
    StagingPlan → HoudiniAssetRealizer → list[operation dicts]
    → TransactionManager → houdini_runtime.execute_operation → Houdini

Public API:
    HoudiniAssetRealizer
        .realize_scene(layout_plan, staging_plan) -> dict
        .create_environment_structure(scene_theme) -> list[dict]
        .create_asset_container(zone, environment_root) -> dict
        .apply_semantic_naming(asset, zone) -> str
        .register_realized_assets(operations, asset_map) -> dict
        .build_transaction_operations(layout_plan, staging_plan) -> list[dict]

    get_houdini_asset_realizer() -> HoudiniAssetRealizer
    reset_houdini_asset_realizer_for_tests()
"""

from __future__ import annotations

import threading
import time
import uuid
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Scene root structure
# ---------------------------------------------------------------------------

_SCENE_ROOTS = [
    "/obj/environment",
    "/obj/hero_assets",
    "/obj/background",
    "/obj/fx",
    "/obj/lighting",
    "/obj/camera",
    "/obj/render",
]

# Zone → container path mapping
_ZONE_CONTAINERS: Dict[str, str] = {
    "hero_area":    "/obj/hero_assets",
    "midground":    "/obj/background",
    "background":   "/obj/background",
    "ceiling":      "/obj/environment",
    "floor":        "/obj/environment",
    "walls":        "/obj/environment",
}

# Category → semantic name prefix
_CATEGORY_PREFIXES: Dict[str, str] = {
    "vehicle":         "veh",
    "character":       "chr",
    "machinery_hero":  "mch",
    "hero_prop":       "prop",
    "robot":           "bot",
    "weapon":          "wpn",
    "creature":        "crt",
    "container":       "ctr",
    "structure":       "str",
    "terrain":         "ter",
    "sky":             "sky",
    "ceiling":         "ceil",
    "floor":           "flr",
    "vegetation":      "veg",
    "tech_panel":      "tech",
    "misc":            "misc",
}


class HoudiniAssetRealizer:
    """
    Generates structured transaction operations for cinematic scene realization.

    All operations are in the format accepted by houdini_runtime.execute_operation().
    No bridge calls are made here — this is a pure planning layer.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._realization_count = 0
        self._realized_assets: Dict[str, str] = {}  # asset_name → houdini_path

    # ------------------------------------------------------------------
    # Core public API
    # ------------------------------------------------------------------

    def realize_scene(
        self,
        layout_plan: Dict[str, Any],
        staging_plan: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Convert a layout+staging plan into a complete realization spec.

        Returns a dict with:
            operations:       list of transaction operation dicts
            realization_id:   uuid4 string
            scene_theme:      str
            asset_count:      int
            zone_map:         {asset_name: zone}
            path_map:         {asset_name: expected_houdini_path}
            generated_at:     float timestamp
        """
        realization_id = str(uuid.uuid4())
        scene_theme = layout_plan.get("scene_theme", "unknown")

        ops = self.build_transaction_operations(layout_plan, staging_plan)

        path_map: Dict[str, str] = {}
        zone_map: Dict[str, str] = {}
        zones = layout_plan.get("zones", {})
        for zone, assets in zones.items():
            container = _ZONE_CONTAINERS.get(zone, "/obj/background")
            for asset in assets:
                name = asset.get("name", "")
                category = asset.get("category", "misc")
                if name:
                    semantic_name = self.apply_semantic_naming(asset, zone)
                    path_map[name] = f"{container}/{semantic_name}"
                    zone_map[name] = zone

        with self._lock:
            self._realization_count += 1
            self._realized_assets.update(path_map)

        return {
            "realization_id": realization_id,
            "scene_theme":    scene_theme,
            "operations":     ops,
            "asset_count":    sum(len(a) for a in zones.values()),
            "zone_map":       zone_map,
            "path_map":       path_map,
            "generated_at":   time.time(),
        }

    def create_environment_structure(self, scene_theme: str) -> List[Dict[str, Any]]:
        """
        Generate create_node operations for the canonical /obj/* hierarchy.

        Returns a list of operation dicts — one per scene root container.
        """
        ops: List[Dict[str, Any]] = []
        for root_path in _SCENE_ROOTS:
            parent = "/obj"
            node_name = root_path.split("/")[-1]
            ops.append({
                "op":     "create_node",
                "parent": parent,
                "type":   "null",
                "name":   node_name,
                "params": {},
            })
        return ops

    def create_asset_container(
        self,
        zone: str,
        environment_root: str = "/obj",
    ) -> Dict[str, Any]:
        """
        Generate a create_node operation for a zone container geo node.
        """
        container = _ZONE_CONTAINERS.get(zone, "/obj/background")
        parent = container if container.count("/") > 1 else environment_root
        node_name = f"zone_{zone}"
        return {
            "op":     "create_node",
            "parent": parent,
            "type":   "geo",
            "name":   node_name,
            "params": {},
        }

    def apply_semantic_naming(
        self,
        asset: Dict[str, Any],
        zone: str,
    ) -> str:
        """
        Derive a deterministic Houdini node name from asset + zone.

        Format: <prefix>_<cleaned_asset_name>
        """
        name = asset.get("name", "asset").lower().replace(" ", "_")
        category = asset.get("category", "misc")
        prefix = _CATEGORY_PREFIXES.get(category, "obj")
        # Ensure valid Houdini identifier
        safe_name = "".join(c if c.isalnum() or c == "_" else "_" for c in name)
        return f"{prefix}_{safe_name}"

    def register_realized_assets(
        self,
        operations: List[Dict[str, Any]],
        asset_map: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        Record the expected path mapping for realized assets.

        Returns a summary dict with asset_count and path_map.
        """
        with self._lock:
            self._realized_assets.update(asset_map)
        return {
            "asset_count": len(asset_map),
            "path_map":    dict(asset_map),
        }

    def build_transaction_operations(
        self,
        layout_plan: Dict[str, Any],
        staging_plan: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Build the full ordered list of transaction operations for scene realization.

        Order:
          1. Create scene root structure (/obj/environment, /obj/hero_assets, etc.)
          2. For each zone in back-to-front order (from import_queue):
             a. Create zone container geo
             b. For each asset: create_node + set_parms (transform hints)
          3. layout_children on each container

        Returns a list of operation dicts compatible with execute_operation().
        """
        ops: List[Dict[str, Any]] = []

        scene_theme = layout_plan.get("scene_theme", "unknown")

        # Step 1: Scene root structure
        ops.extend(self.create_environment_structure(scene_theme))

        # Step 2: Assets from import queue (already sorted back-to-front)
        import_queue = staging_plan.get("import_queue", [])
        zone_containers_created: set = set()

        for item in import_queue:
            zone = item.get("zone", "background")
            asset_name = item.get("asset_name", "")
            asset_category = item.get("asset_category", "misc")
            meta = item.get("asset_metadata", {})

            # Ensure zone container exists (create once per zone)
            container = _ZONE_CONTAINERS.get(zone, "/obj/background")
            if zone not in zone_containers_created:
                zone_containers_created.add(zone)
                zone_node_name = f"zone_{zone}"
                # The container path parent is the relevant /obj/* root
                ops.append({
                    "op":     "create_node",
                    "parent": container,
                    "type":   "geo",
                    "name":   zone_node_name,
                    "params": {},
                })

            # Create asset node inside zone container
            asset_dict = {"name": asset_name, "category": asset_category}
            semantic_name = self.apply_semantic_naming(asset_dict, zone)
            asset_container = f"{container}/zone_{zone}"

            params: Dict[str, Any] = {}
            # Carry through any transform hints from metadata
            for key in ("tx", "ty", "tz", "rx", "ry", "rz", "sx", "sy", "sz"):
                if key in meta:
                    params[key] = meta[key]

            ops.append({
                "op":     "create_node",
                "parent": asset_container,
                "type":   "null",
                "name":   semantic_name,
                "params": params,
            })

        # Step 3: Layout children on each container root
        for root_path in _SCENE_ROOTS:
            ops.append({
                "op":   "layout_children",
                "path": root_path,
            })

        return ops

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "realization_count": self._realization_count,
                "registered_assets": len(self._realized_assets),
            }

    def get_realized_path(self, asset_name: str) -> Optional[str]:
        with self._lock:
            return self._realized_assets.get(asset_name)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[HoudiniAssetRealizer] = None
_INSTANCE_LOCK = threading.Lock()


def get_houdini_asset_realizer() -> HoudiniAssetRealizer:
    global _INSTANCE
    with _INSTANCE_LOCK:
        if _INSTANCE is None:
            _INSTANCE = HoudiniAssetRealizer()
        return _INSTANCE


def reset_houdini_asset_realizer_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
