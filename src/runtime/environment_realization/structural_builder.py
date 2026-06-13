"""
structural_builder.py — §49 Structural Environment Realization
==============================================================
Orchestrates the full structural generation pipeline and converts
the RoomShell into a flat list of StructuralElements plus
transaction operation dicts (Houdini-ready, no bridge calls).

Transaction op format (matches layout_application_engine convention):
  {
    "type":      "create_structural_node",
    "element_id": "floor_western_room",
    "element_type": "floor",
    "environment": "western_room",
    "parms": {"tx": 0.0, "ty": 0.0, "tz": 0.0, "width": 10.0, ...},
    "material": "wood",
    "parent_path": "/obj/env_western_room",
  }

Public API:
    StructuralBuilder
    get_structural_builder()
    reset_structural_builder_for_tests()
"""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional, Tuple

from src.runtime.environment_realization.structural_elements import (
    StructuralElement, RoomShell, EnvironmentRealizationPlan,
)
from src.runtime.environment_realization.room_shell_builder import get_room_shell_builder
from src.runtime.environment_realization.architectural_constraint_solver import (
    get_architectural_constraint_solver,
)


def _element_box_size(elem: StructuralElement):
    """Return (sizex, sizey, sizez) for the box SOP that represents this element."""
    dims = elem.dimensions
    et   = elem.element_type
    if et == "floor":
        return (
            dims.get("width",     10.0),
            dims.get("thickness",  0.10),
            dims.get("depth",     12.0),
        )
    if et == "ceiling":
        return (
            dims.get("width",     10.0),
            dims.get("thickness",  0.15),
            dims.get("depth",     12.0),
        )
    if et == "wall":
        return (
            dims.get("width",     10.0),
            dims.get("height",     4.0),
            dims.get("thickness",  0.20),
        )
    if et == "beam":
        return (
            dims.get("length",    10.0),
            dims.get("height",     0.30),
            dims.get("width",      0.20),
        )
    if et == "column":
        cw = dims.get("width", 0.30)
        return (cw, dims.get("height", 4.0), cw)
    # Openings (door, window, skylight, …): width × height × depth
    return (
        dims.get("width",   0.90),
        dims.get("height",  2.10),
        dims.get("depth", dims.get("thickness", 0.30)),
    )


class StructuralBuilder:
    """
    Builds a complete EnvironmentRealizationPlan from an environment name.

    Usage:
        plan = get_structural_builder().build("western_room")
        # plan.structural_elements → list of all architectural elements
        # plan.transaction_ops     → Houdini-ready op dicts
        # plan.room_closed         → True for complete indoor environments
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def build(
        self,
        environment: str,
        override_dims: Optional[Tuple[float, float, float]] = None,
    ) -> EnvironmentRealizationPlan:
        """
        Build the full structural realization plan.

        Args:
            environment:   name (e.g. "western_room")
            override_dims: optional (width, height, depth) in meters

        Returns: EnvironmentRealizationPlan. Never raises.
        """
        try:
            return self._build(environment, override_dims)
        except Exception as exc:
            return EnvironmentRealizationPlan(
                environment=environment,
                ok=False,
                errors=[f"StructuralBuilder.build failed: {exc}"],
            )

    def _build(
        self,
        environment: str,
        override_dims: Optional[Tuple[float, float, float]],
    ) -> EnvironmentRealizationPlan:
        plan = EnvironmentRealizationPlan(environment=environment)

        # Step 1: Build room shell
        shell = get_room_shell_builder().build(environment, override_dims)

        # Step 2: Validate architectural constraints
        constraint_result = get_architectural_constraint_solver().solve(shell)
        shell = constraint_result.shell

        plan.room_shell = shell

        # Step 3: Flatten all elements
        plan.structural_elements = shell.all_elements()

        # Step 4: Count elements
        plan.wall_count    = len(shell.walls)
        plan.floor_count   = 1 if shell.floor else 0
        plan.ceiling_count = 1 if shell.ceiling else 0
        plan.door_count    = sum(
            1 for e in shell.openings
            if e.element_type in ("door", "swing_door", "sliding_door", "loading_door",
                                   "archway", "hangar_opening")
        )
        plan.window_count  = sum(
            1 for e in shell.openings
            if e.element_type in ("window", "skylight", "porthole", "arrow_slit", "vent")
        )
        plan.beam_count    = len(shell.beams)
        plan.column_count  = len(shell.columns)
        plan.room_closed   = shell.room_closed

        # Step 5: Build zone regions
        plan.zone_regions = self._build_zones(shell)
        plan.zone_count   = len(plan.zone_regions)

        # Step 6: Build transaction ops (bridge-compatible format)
        env_safe    = environment.replace(" ", "_").replace("-", "_")
        container   = f"/obj/env_{env_safe}"
        plan.transaction_ops = self._build_ops(plan.structural_elements, container, env_safe)

        # Step 7: Production ready
        plan.production_ready = (
            plan.room_closed
            and plan.floor_count > 0
            and (plan.wall_count == 4 or shell.is_outdoor)
            and plan.ok
        )

        return plan

    @staticmethod
    def _build_zones(shell: RoomShell) -> List[Dict[str, Any]]:
        """Generate zone region descriptors from room dimensions."""
        if shell.is_outdoor:
            return [
                {"zone": "hero_zone",       "centre": [0.0, 0.0,  0.0], "radius": 5.0},
                {"zone": "support_zone",    "centre": [0.0, 0.0,  5.0], "radius": 4.0},
                {"zone": "background_zone", "centre": [0.0, 0.0, 12.0], "radius": 6.0},
            ]
        w2 = shell.width / 2.0
        d2 = shell.depth / 2.0
        return [
            {"zone": "hero_zone",       "centre": [0.0, 0.0,  0.0],  "radius": min(w2, d2) * 0.35},
            {"zone": "support_zone",    "centre": [w2 * 0.5, 0.0, 0.0], "radius": min(w2, d2) * 0.30},
            {"zone": "entrance_zone",   "centre": [0.0, 0.0, d2 * 0.8], "radius": min(w2, d2) * 0.20},
            {"zone": "background_zone", "centre": [0.0, 0.0, -d2 * 0.7], "radius": min(w2, d2) * 0.25},
            {"zone": "decoration_zone", "centre": [-w2 * 0.6, 0.0, 0.0], "radius": min(w2, d2) * 0.20},
            {"zone": "atmosphere_zone", "centre": [0.0, shell.height * 0.7, 0.0], "radius": min(w2, d2) * 0.50},
        ]

    @staticmethod
    def _build_ops(
        elements: List[StructuralElement],
        container_path: str,
        env_safe: str,
    ) -> List[Dict[str, Any]]:
        """
        Build bridge-compatible operation dicts for all structural elements.

        Op sequence per environment:
          1. create_node  — subnet container at /obj/env_<name>
          2. Per element:
             a. create_node  — geo node inside the subnet
             b. set_parms    — tx/ty/tz/rx/ry/rz (object-level transforms)
             c. create_node  — box SOP inside the geo node
             d. set_parms    — sizex/sizey/sizez on the box SOP
             e. set_display_flag — make box SOP the displayed node
             f. set_display_flag — make geo node visible
          3. layout_children — auto-layout the subnet
        """
        ops: List[Dict[str, Any]] = []

        # --- 1. Create environment subnet container ---
        ops.append({
            "op":    "create_node",
            "parent": "/obj",
            "type":  "subnet",
            "name":  f"env_{env_safe}",
        })

        # --- 2. Create one geo node per structural element with a box SOP inside ---
        for elem in elements:
            node_path = f"{container_path}/{elem.element_id}"
            box_path  = f"{node_path}/box1"

            # Object-level transform parms
            parms: Dict[str, Any] = {
                "tx": round(elem.position[0], 4) if elem.position else 0.0,
                "ty": round(elem.position[1], 4) if len(elem.position) > 1 else 0.0,
                "tz": round(elem.position[2], 4) if len(elem.position) > 2 else 0.0,
                "rx": round(elem.rotation[0], 4) if elem.rotation else 0.0,
                "ry": round(elem.rotation[1], 4) if len(elem.rotation) > 1 else 0.0,
                "rz": round(elem.rotation[2], 4) if len(elem.rotation) > 2 else 0.0,
            }

            sx, sy, sz = _element_box_size(elem)

            # a) Create geo node inside subnet
            ops.append({
                "op":    "create_node",
                "parent": container_path,
                "type":  "geo",
                "name":  elem.element_id,
            })

            # b) Set object-level transforms
            ops.append({
                "op":    "set_parms",
                "node":  node_path,
                "parms": parms,
            })

            # c) Create box SOP inside the geo node
            ops.append({
                "op":    "create_node",
                "parent": node_path,
                "type":  "box",
                "name":  "box1",
            })

            # d) Set box SOP dimensions (box centred at local origin)
            ops.append({
                "op":    "set_parms",
                "node":  box_path,
                "parms": {
                    "sizex": round(sx, 4),
                    "sizey": round(sy, 4),
                    "sizez": round(sz, 4),
                },
            })

            # e) Display flag on the box SOP
            ops.append({
                "op":   "set_display_flag",
                "path": box_path,
                "on":   True,
            })

            # f) Display flag on geo node
            ops.append({
                "op":   "set_display_flag",
                "path": node_path,
                "on":   True,
            })

        # --- 3. Auto-layout the container ---
        ops.append({
            "op":   "layout_children",
            "path": container_path,
        })

        return ops


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[StructuralBuilder] = None
_lock = threading.Lock()


def get_structural_builder() -> StructuralBuilder:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = StructuralBuilder()
    return _instance


def reset_structural_builder_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
