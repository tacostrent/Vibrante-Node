"""
Procedural Scene Assembler (Tier 3)
======================================
Generates the complete ordered transaction operation plan for a semantic
scene assembly. Integrates LayoutTransformEngine, SceneHierarchyBuilder,
and HoudiniAssetRealizer to produce a single executable plan.

IMPORTANT DESIGN RULE: This module ONLY generates operation dicts.
It NEVER calls get_bridge() directly for mutations.

Public API:
    ProceduralSceneAssembler
        .assemble_scene(layout_plan, staging_plan, options) -> dict
        .build_environment_operations(scene_theme, layout_rules) -> list[dict]
        .build_asset_placement_operations(zones, staging_plan) -> list[dict]
        .build_camera_operations(camera_targets, camera_hints) -> list[dict]
        .build_lighting_operations(layout_rules, scene_theme) -> list[dict]

    get_procedural_scene_assembler() -> ProceduralSceneAssembler
    reset_procedural_scene_assembler_for_tests()
"""

from __future__ import annotations

import threading
import time
import uuid
from typing import Any, Dict, List, Optional

from src.runtime.layout_transform_engine import get_layout_transform_engine
from src.runtime.scene_hierarchy_builder import get_scene_hierarchy_builder
from src.runtime.houdini_asset_realizer import get_houdini_asset_realizer

# ---------------------------------------------------------------------------
# Lighting presets (deterministic, no LLM)
# ---------------------------------------------------------------------------

_LIGHTING_PRESETS: Dict[str, List[Dict[str, Any]]] = {
    "practical_industrial": [
        {"name": "key_light",   "type": "envlight", "params": {"env_map": "", "light_intensity": 1.0}},
        {"name": "fill_light",  "type": "hlight",   "params": {"ty": 8.0, "tx": -5.0, "light_intensity": 0.4}},
        {"name": "rim_light",   "type": "hlight",   "params": {"ty": 6.0, "tx": 5.0,  "light_intensity": 0.6}},
    ],
    "neon_accent": [
        {"name": "ambient",     "type": "envlight", "params": {"light_intensity": 0.3}},
        {"name": "neon_key",    "type": "hlight",   "params": {"ty": 4.0, "light_color_r": 0.2, "light_color_b": 1.0, "light_intensity": 1.2}},
    ],
    "clean_white": [
        {"name": "sky_light",   "type": "envlight", "params": {"light_intensity": 1.5}},
        {"name": "fill",        "type": "hlight",   "params": {"ty": 10.0, "light_intensity": 0.5}},
    ],
    "dramatic_screen_glow": [
        {"name": "screen_key",  "type": "hlight",   "params": {"ty": 3.0, "tz": -2.0, "light_color_b": 0.9, "light_intensity": 0.8}},
        {"name": "rim",         "type": "hlight",   "params": {"ty": 6.0, "tx": 4.0, "light_intensity": 0.3}},
    ],
    "natural_decay": [
        {"name": "sky",         "type": "envlight", "params": {"light_intensity": 0.8}},
        {"name": "practical_1", "type": "hlight",   "params": {"ty": 5.0, "light_intensity": 0.6}},
    ],
}

_DEFAULT_LIGHTING = _LIGHTING_PRESETS["practical_industrial"]

# ---------------------------------------------------------------------------
# Blocking geometry specs — one primitive per asset category
# box  params: sizex, sizey, sizez
# tube params: rad1 (bottom radius), rad2 (top radius), height
# ---------------------------------------------------------------------------

_BLOCKER_SPECS: Dict[str, Dict[str, Any]] = {
    "vehicle":         {"type": "box",  "params": {"sizex": 4.5,  "sizey": 1.8, "sizez": 9.0}},
    "character":       {"type": "tube", "params": {"rad1": 0.35,  "rad2": 0.35, "height": 1.8}},
    "robot":           {"type": "tube", "params": {"rad1": 0.4,   "rad2": 0.4,  "height": 2.0}},
    "creature":        {"type": "box",  "params": {"sizex": 1.5,  "sizey": 1.5, "sizez": 2.5}},
    "machinery_hero":  {"type": "box",  "params": {"sizex": 3.0,  "sizey": 3.0, "sizez": 3.0}},
    "hero_prop":       {"type": "box",  "params": {"sizex": 0.8,  "sizey": 1.2, "sizez": 0.8}},
    "weapon":          {"type": "box",  "params": {"sizex": 0.2,  "sizey": 0.8, "sizez": 1.5}},
    "structure":       {"type": "box",  "params": {"sizex": 5.0,  "sizey": 4.0, "sizez": 5.0}},
    "container":       {"type": "box",  "params": {"sizex": 2.0,  "sizey": 2.0, "sizez": 2.0}},
    "tech_panel":      {"type": "box",  "params": {"sizex": 2.0,  "sizey": 2.0, "sizez": 0.1}},
    "terrain":         {"type": "box",  "params": {"sizex": 10.0, "sizey": 0.3, "sizez": 10.0}},
    "sky":             {"type": "box",  "params": {"sizex": 30.0, "sizey": 0.1, "sizez": 30.0}},
    "ceiling":         {"type": "box",  "params": {"sizex": 12.0, "sizey": 0.2, "sizez": 12.0}},
    "floor":           {"type": "box",  "params": {"sizex": 12.0, "sizey": 0.1, "sizez": 12.0}},
    "vegetation":      {"type": "tube", "params": {"rad1": 0.5,   "rad2": 0.1,  "height": 2.5}},
    "pipe":            {"type": "tube", "params": {"rad1": 0.15,  "rad2": 0.15, "height": 4.0}},
    "misc":            {"type": "box",  "params": {"sizex": 1.0,  "sizey": 1.0, "sizez": 1.0}},
}
_DEFAULT_BLOCKER: Dict[str, Any] = {"type": "box", "params": {"sizex": 1.0, "sizey": 1.0, "sizez": 1.0}}


class ProceduralSceneAssembler:
    """
    Orchestrates the full procedural scene assembly into an ordered operation list.

    The assemble_scene() method produces a complete, executable plan:
      Phase 1 — Hierarchy creation (null containers)
      Phase 2 — Environment geo
      Phase 3 — Asset placement (back-to-front, with transforms)
      Phase 4 — Lighting rig
      Phase 5 — Camera setup
      Phase 6 — Layout pass
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._assembly_count = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def assemble_scene(
        self,
        layout_plan: Dict[str, Any],
        staging_plan: Dict[str, Any],
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate the complete ordered operation plan for scene assembly.

        Returns:
            {
                assembly_id:   str (uuid4)
                scene_theme:   str
                operations:    list[dict]  — ordered, ready for TransactionManager
                phase_counts:  {phase_name: op_count}
                total_ops:     int
                generated_at:  float
            }
        """
        options = options or {}
        assembly_id = str(uuid.uuid4())
        scene_theme = layout_plan.get("scene_theme", "unknown")
        layout_rules = layout_plan.get("layout_rules", {})
        zones = layout_plan.get("zones", {})
        camera_hints = layout_plan.get("camera_hints", [])

        all_ops: List[Dict[str, Any]] = []
        phase_counts: Dict[str, int] = {}

        # Phase 1: Hierarchy
        hierarchy = get_scene_hierarchy_builder().build_hierarchy(layout_plan)
        hier_ops = hierarchy.get("network_ops", [])
        all_ops.extend(hier_ops)
        phase_counts["hierarchy"] = len(hier_ops)

        # Phase 2: Environment
        env_ops = self.build_environment_operations(scene_theme, layout_rules)
        all_ops.extend(env_ops)
        phase_counts["environment"] = len(env_ops)

        # Phase 3: Asset placement
        asset_ops = self.build_asset_placement_operations(zones, staging_plan)
        all_ops.extend(asset_ops)
        phase_counts["asset_placement"] = len(asset_ops)

        # Phase 4: Lighting
        lighting_ops = self.build_lighting_operations(layout_rules, scene_theme)
        all_ops.extend(lighting_ops)
        phase_counts["lighting"] = len(lighting_ops)

        # Phase 5: Camera
        transform_engine = get_layout_transform_engine()
        camera_targets = transform_engine.calculate_camera_focus_targets(zones, layout_rules)
        cam_ops = self.build_camera_operations(camera_targets, camera_hints)
        all_ops.extend(cam_ops)
        phase_counts["camera"] = len(cam_ops)

        # Phase 6: Layout pass on each container
        layout_roots = [
            "/obj/environment", "/obj/hero_assets", "/obj/background",
            "/obj/fx", "/obj/lighting", "/obj/camera",
        ]
        for root in layout_roots:
            all_ops.append({"op": "layout_children", "path": root})
        phase_counts["layout"] = len(layout_roots)

        with self._lock:
            self._assembly_count += 1

        return {
            "assembly_id":  assembly_id,
            "scene_theme":  scene_theme,
            "operations":   all_ops,
            "phase_counts": phase_counts,
            "total_ops":    len(all_ops),
            "generated_at": time.time(),
        }

    def build_environment_operations(
        self,
        scene_theme: str,
        layout_rules: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Generate create_node operations for environment-specific elements.

        For each theme, creates a geo node with an appropriate SOP network stub.
        """
        ops: List[Dict[str, Any]] = []

        fog_density = layout_rules.get("fog_density", "none")
        scale = layout_rules.get("scale", "medium")

        # Ground plane
        ops.append({
            "op":     "create_node",
            "parent": "/obj/environment",
            "type":   "geo",
            "name":   "ground_geo",
            "params": {},
        })

        # Add fog volume node if density is non-zero
        if fog_density not in ("none", ""):
            ops.append({
                "op":     "create_node",
                "parent": "/obj/environment",
                "type":   "geo",
                "name":   "fog_volume",
                "params": {},
            })

        return ops

    def build_asset_placement_operations(
        self,
        zones: Dict[str, List[Dict[str, Any]]],
        staging_plan: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Generate the create_node + set_parms operations for all scene assets.

        Assets are processed back-to-front using the import_queue order.
        Transforms are injected from LayoutTransformEngine.
        """
        ops: List[Dict[str, Any]] = []
        transform_engine = get_layout_transform_engine()
        realizer = get_houdini_asset_realizer()
        layout_rules = staging_plan.get("layout_rules", {})

        # Use import_queue for guaranteed back-to-front ordering
        import_queue = staging_plan.get("import_queue", [])

        # Build zone asset lookup
        zone_assets: Dict[str, List[Dict[str, Any]]] = {}
        for zone, assets in zones.items():
            zone_assets[zone] = list(assets)

        # Pre-calculate transforms per zone
        zone_transforms: Dict[str, Dict[str, Any]] = {}
        zone_rotations: Dict[str, Dict[str, Any]] = {}
        for zone, assets in zone_assets.items():
            if assets:
                zone_transforms[zone] = transform_engine.calculate_asset_positions(
                    assets, zone, layout_rules
                )
                zone_rotations[zone] = transform_engine.calculate_asset_rotations(
                    assets, zone
                )

        # Generate ops in import queue order (back-to-front)
        for item in import_queue:
            asset_name = item.get("asset_name", "")
            asset_category = item.get("asset_category", "misc")
            zone = item.get("zone", "background")

            if not asset_name:
                continue

            asset_dict = {"name": asset_name, "category": asset_category}
            semantic_name = realizer.apply_semantic_naming(asset_dict, zone)

            # Determine container
            from src.runtime.scene_hierarchy_builder import _ZONE_PARENTS
            container = _ZONE_PARENTS.get(zone, "/obj/background")

            # Create the asset geo node
            ops.append({
                "op":     "create_node",
                "parent": container,
                "type":   "geo",
                "name":   semantic_name,
                "params": {},
            })

            # Apply transforms if calculated
            transforms = zone_transforms.get(zone, {})
            rotations = zone_rotations.get(zone, {})

            parms: Dict[str, Any] = {}
            if asset_name in transforms:
                tx, ty, tz = transforms[asset_name]
                parms.update({"tx": tx, "ty": ty, "tz": tz})
            if asset_name in rotations:
                rx, ry, rz = rotations[asset_name]
                parms.update({"rx": rx, "ry": ry, "rz": rz})

            if parms:
                ops.append({
                    "op":    "set_parms",
                    "node":  f"{container}/{semantic_name}",
                    "parms": parms,
                })

            # Create blocking primitive inside the geo container so the layout
            # is immediately visible in Houdini before real assets are loaded.
            geo_path = f"{container}/{semantic_name}"
            blocker_spec = _BLOCKER_SPECS.get(asset_category, _DEFAULT_BLOCKER)
            ops.append({
                "op":     "create_node",
                "parent": geo_path,
                "type":   blocker_spec["type"],
                "name":   "blocker",
                "params": dict(blocker_spec["params"]),
            })
            ops.append({
                "op":   "set_display_flag",
                "path": f"{geo_path}/blocker",
                "on":   True,
            })

        return ops

    def build_camera_operations(
        self,
        camera_targets: List[Dict[str, Any]],
        camera_hints: List[str],
    ) -> List[Dict[str, Any]]:
        """
        Generate camera create_node + set_parms operations.

        One camera per target, positioned to frame the target.
        """
        ops: List[Dict[str, Any]] = []

        for target in camera_targets:
            shot_type = target.get("shot_type", "establishing")
            cam_name = f"cam_{shot_type}"
            tx, ty, tz = target.get("position", (0.0, 5.0, 15.0))

            # Camera sits above and in front of scene, pointed at target
            cam_tz = tz + 15.0

            ops.append({
                "op":     "create_node",
                "parent": "/obj/camera",
                "type":   "cam",
                "name":   cam_name,
                "params": {
                    "tx": float(tx),
                    "ty": float(ty) + 2.0,
                    "tz": float(cam_tz),
                    "rx": -10.0,  # Slightly downward angle
                    "focal": 50.0,  # 50mm lens default
                },
            })

        return ops

    def build_lighting_operations(
        self,
        layout_rules: Dict[str, Any],
        scene_theme: str,
    ) -> List[Dict[str, Any]]:
        """
        Generate lighting create_node + set_parms operations.

        Selects preset from lighting_style in layout_rules.
        """
        ops: List[Dict[str, Any]] = []
        lighting_style = layout_rules.get("lighting_style", "practical_industrial")
        preset = _LIGHTING_PRESETS.get(lighting_style, _DEFAULT_LIGHTING)

        for light in preset:
            ops.append({
                "op":     "create_node",
                "parent": "/obj/lighting",
                "type":   light["type"],
                "name":   light["name"],
                "params": dict(light.get("params", {})),
            })

        return ops

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {"assembly_count": self._assembly_count}


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[ProceduralSceneAssembler] = None
_INSTANCE_LOCK = threading.Lock()


def get_procedural_scene_assembler() -> ProceduralSceneAssembler:
    global _INSTANCE
    with _INSTANCE_LOCK:
        if _INSTANCE is None:
            _INSTANCE = ProceduralSceneAssembler()
        return _INSTANCE


def reset_procedural_scene_assembler_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
