"""
Environment Structure Builder (Tier 9.5 — Structural Environment Assembly)
===========================================================================
Constructs the structural scaffold for an environment before any assets
are placed. Enforces the Structure-First Rule:

  1. Build environment structure
  2. Validate environment completeness
  3. Create zones
  4. Place anchor assets          (AnchorAssetEngine)
  5. Place support assets         (ScenePopulationEngine)
  6. Place decorative assets      (DecorativePopulationEngine)
  7. Add atmosphere               (downstream via placement / lighting)

No assets may be placed before the structure exists. The EnvironmentStructure
produced here is consumed by AnchorAssetEngine and DecorativePopulationEngine
to ensure all downstream placement is relative to walls, zones, and anchors
rather than the world origin.

DESIGN RULES:
  1. No bridge calls. No Houdini imports. Planning only.
  2. Deterministic — same inputs produce the same structure.
  3. Never raises — errors captured in EnvironmentStructure.errors.
  4. Missing required elements are recorded in missing_required.
  5. structure_complete = True only when all required elements are defined.

Public API:
    StructuralElement
    EnvironmentStructure
    EnvironmentStructureBuilder
    get_environment_structure_builder()
    reset_environment_structure_builder_for_tests()
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.runtime.assets.assembly.environment_blueprint import EnvironmentBlueprint
from src.runtime.assets.assembly.architectural_templates import get_architectural_templates
from src.runtime.assets.assembly.environment_zones import StructuralZone, get_zone_definitions


# ---------------------------------------------------------------------------
# Position hints for structural elements
# ---------------------------------------------------------------------------

_ELEMENT_POSITIONS: Dict[str, str] = {
    "floor":                       "entire_floor_plane",
    "cracked_concrete_floor":      "entire_floor_plane",
    "concrete_floor":              "entire_floor_plane",
    "lab_floor":                   "entire_floor_plane",
    "sterile_floor":               "entire_floor_plane",
    "wet_stone_floor":             "entire_floor_plane",
    "stone_floor":                 "entire_floor_plane",
    "marble_floor":                "entire_floor_plane",
    "raised_floor":                "entire_floor_plane",
    "grating_floor":               "entire_floor_plane",
    "deck_plating":                "entire_floor_plane",
    "sand_ground":                 "entire_floor_plane",
    "forest_floor":                "entire_floor_plane",
    "dirt_ground":                 "entire_floor_plane",
    "pavement":                    "foreground_to_midground",
    "road_surface":                "center_road_plane",
    "sidewalk_kerb":               "perimeter_edge",
    "wall":                        "four_perimeter_walls",
    "stone_wall":                  "four_perimeter_walls",
    "damaged_wall":                "partial_perimeter_walls",
    "corridor_wall_panel":         "two_side_walls",
    "reinforced_hull_wall":        "four_perimeter_walls",
    "building_facade":             "background_perimeter",
    "ceiling":                     "overhead_plane",
    "high_ceiling":                "overhead_plane_high",
    "low_ceiling":                 "overhead_plane_low",
    "vaulted_ceiling":             "vaulted_overhead",
    "ceiling_panel":               "overhead_plane",
    "door":                        "foreground_wall",
    "main_entrance_door":          "foreground_wall_center",
    "hangar_door":                 "foreground_wall_large",
    "blast_door":                  "foreground_wall",
    "sliding_door":                "any_wall",
    "airlock_door":                "foreground_wall",
    "iron_door":                   "foreground_wall",
    "great_wooden_door":           "foreground_wall_center",
    "security_door":               "foreground_wall",
    "loading_door":                "foreground_wall_large",
    "saloon_door":                 "foreground_wall_center",
    "window":                      "side_walls",
    "arched_window":               "upper_side_walls",
    "viewport":                    "any_wall",
    "support_column":              "perimeter_corners",
    "pillar":                      "midground_sides",
    "roof_structure":              "overhead_spanning",
    "steel_beam":                  "overhead_structural",
    "exposed_steel_structure":     "partial_overhead",
    "lab_partition":               "interior_divider",
    "rubble_pile":                 "scattered_floor",
    "canopy_layer":                "overhead_organic",
    "large_tree":                  "midground_vertical",
    "fire_pit_ring":               "center_floor",
    "shelter_tarp":                "background_zone",
    "perimeter_fence":             "outer_perimeter",
    "dune_formation":              "midground_mound",
    "sky_dome":                    "overhead_infinite",
    "torch_bracket":               "wall_mounted_mid",
}


@dataclass
class StructuralElement:
    """A single structural component within an environment."""

    element_id:    str = field(default_factory=lambda: f"el_{uuid.uuid4().hex[:8]}")
    element_type:  str = ""   # "floor", "wall", "ceiling", "door", etc.
    position_hint: str = ""   # descriptive position in world space
    required:      bool = True
    present:       bool = True  # always True — structure builder defines all elements it knows about

    def to_dict(self) -> Dict[str, Any]:
        return {
            "element_id":    self.element_id,
            "element_type":  self.element_type,
            "position_hint": self.position_hint,
            "required":      self.required,
            "present":       self.present,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "StructuralElement":
        return cls(
            element_id    = str(d.get("element_id", f"el_{uuid.uuid4().hex[:8]}")),
            element_type  = str(d.get("element_type", "")),
            position_hint = str(d.get("position_hint", "")),
            required      = bool(d.get("required", True)),
            present       = bool(d.get("present", True)),
        )


@dataclass
class EnvironmentStructure:
    """Full structural scaffold for a scene environment.

    Produced by EnvironmentStructureBuilder. Consumed by AnchorAssetEngine
    and DecorativePopulationEngine to ensure all placement is relative to
    structural elements rather than the world origin.
    """

    structure_id:       str = field(default_factory=lambda: f"struct_{uuid.uuid4().hex[:10]}")
    environment_name:   str = ""
    blueprint:          Optional[EnvironmentBlueprint] = None

    structural_elements: List[StructuralElement] = field(default_factory=list)
    zones:               List[StructuralZone]    = field(default_factory=list)

    structure_complete: bool       = False
    missing_required:   List[str]  = field(default_factory=list)
    errors:             List[str]  = field(default_factory=list)
    build_time:         float      = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "structure_id":       self.structure_id,
            "environment_name":   self.environment_name,
            "blueprint":          self.blueprint.to_dict() if self.blueprint else {},
            "structural_elements": [e.to_dict() for e in self.structural_elements],
            "zones":              [z.to_dict() for z in self.zones],
            "structure_complete": self.structure_complete,
            "missing_required":   list(self.missing_required),
            "errors":             list(self.errors),
            "build_time":         self.build_time,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "EnvironmentStructure":
        bp_raw = d.get("blueprint", {})
        bp = EnvironmentBlueprint.from_dict(bp_raw) if bp_raw else None
        return cls(
            structure_id        = str(d.get("structure_id", f"struct_{uuid.uuid4().hex[:10]}")),
            environment_name    = str(d.get("environment_name", "")),
            blueprint           = bp,
            structural_elements = [StructuralElement.from_dict(e) for e in d.get("structural_elements", [])],
            zones               = [StructuralZone.from_dict(z) for z in d.get("zones", [])],
            structure_complete  = bool(d.get("structure_complete", False)),
            missing_required    = list(d.get("missing_required", [])),
            errors              = list(d.get("errors", [])),
            build_time          = float(d.get("build_time", 0.0)),
        )


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

class EnvironmentStructureBuilder:
    """Builds a structural scaffold from an environment name.

    The pipeline is:
      1. Fetch the EnvironmentBlueprint from ArchitecturalTemplates.
      2. Create a StructuralElement for each item in blueprint.structural_assets.
      3. Check required elements (floor/wall/ceiling/door/window) against blueprint flags.
      4. Load the canonical zone set for this environment.
      5. Check for structural completeness.
      6. Return EnvironmentStructure.

    Never raises — errors are captured in EnvironmentStructure.errors.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def build_structure(self, environment_name: str) -> EnvironmentStructure:
        """Build and return the structural scaffold for the given environment.

        Args:
            environment_name: One of the canonical environment names or any
                              custom name (falls back to generic blueprint).

        Returns:
            EnvironmentStructure with all structural elements and zones defined.
        """
        t0 = time.perf_counter()
        try:
            return self._build(environment_name, t0)
        except Exception as exc:
            return EnvironmentStructure(
                environment_name = environment_name,
                structure_complete = False,
                errors = [f"Unexpected build error: {exc}"],
                build_time = time.perf_counter() - t0,
            )

    def _build(self, environment_name: str, t0: float) -> EnvironmentStructure:
        templates = get_architectural_templates()
        blueprint = templates.get_template(environment_name)

        structural_elements: List[StructuralElement] = []
        missing_required: List[str] = []
        errors: List[str] = []

        # -- Step 1: materialise structural assets from blueprint ----------
        for asset_type in blueprint.structural_assets:
            position = _ELEMENT_POSITIONS.get(asset_type, "scene_space")
            structural_elements.append(StructuralElement(
                element_type  = asset_type,
                position_hint = position,
                required      = True,
                present       = True,
            ))

        # -- Step 2: check required boolean flags against what we have -----
        defined_types = {e.element_type for e in structural_elements}

        if blueprint.floor_required:
            floor_types = {t for t in defined_types if "floor" in t or "ground" in t or "pavement" in t or "plating" in t}
            if not floor_types:
                missing_required.append("floor")
                errors.append("Floor is required but not defined in structural assets.")

        if blueprint.wall_required:
            wall_types = {t for t in defined_types if "wall" in t or "facade" in t}
            if not wall_types:
                missing_required.append("wall")
                errors.append("Wall is required but not defined in structural assets.")

        if blueprint.ceiling_required:
            ceiling_types = {t for t in defined_types if "ceiling" in t or "overhead" in t}
            if not ceiling_types:
                missing_required.append("ceiling")
                errors.append("Ceiling is required but not defined in structural assets.")

        if blueprint.door_required:
            door_types = {t for t in defined_types if "door" in t or "airlock" in t}
            if not door_types:
                missing_required.append("door")
                errors.append("Door is required but not defined in structural assets.")

        if blueprint.window_required:
            window_types = {t for t in defined_types if "window" in t or "viewport" in t or "port" in t}
            if not window_types:
                missing_required.append("window")
                errors.append("Window/viewport is required but not defined in structural assets.")

        # -- Step 3: load zone definitions ---------------------------------
        zones = get_zone_definitions(environment_name)

        # -- Step 4: determine completeness --------------------------------
        structure_complete = len(missing_required) == 0

        return EnvironmentStructure(
            environment_name    = environment_name,
            blueprint           = blueprint,
            structural_elements = structural_elements,
            zones               = zones,
            structure_complete  = structure_complete,
            missing_required    = missing_required,
            errors              = errors,
            build_time          = time.perf_counter() - t0,
        )

    def get_required_element_types(self, environment_name: str) -> List[str]:
        """Return the list of required structural element type names for an environment."""
        bp = get_architectural_templates().get_template(environment_name)
        required = []
        if bp.floor_required:
            required.append("floor")
        if bp.wall_required:
            required.append("wall")
        if bp.ceiling_required:
            required.append("ceiling")
        if bp.door_required:
            required.append("door")
        if bp.window_required:
            required.append("window")
        return required

    def element_types_present(self, structure: EnvironmentStructure) -> List[str]:
        """Return list of element types defined in the given structure."""
        return [e.element_type for e in structure.structural_elements]


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[EnvironmentStructureBuilder] = None
_LOCK = threading.Lock()


def get_environment_structure_builder() -> EnvironmentStructureBuilder:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = EnvironmentStructureBuilder()
        return _INSTANCE


def reset_environment_structure_builder_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
