"""
Environment Structure Builder (§44 — Structural Environment Assembly)
=====================================================================
Builds the structural scaffold for an environment: floor, walls, ceiling,
doors, windows, and support elements. This is the §44 package version —
distinct from src.runtime.assets.assembly.environment_structure_builder.

Structure-First Rule: structure must be built before any asset is placed.

DESIGN RULES:
  1. No bridge calls. No Houdini imports. Planning only.
  2. Deterministic — same environment always yields the same structure.
  3. Never raises — errors captured in EnvironmentStructurePlan.errors.
  4. Singleton pattern.
  5. Thread-safe.

Public API:
    BuiltStructuralElement
    EnvironmentStructurePlan
    EnvironmentStructureBuilder
    get_environment_structure_builder()
    reset_environment_structure_builder_for_tests()
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.runtime.environment.environment_blueprint import EnvironmentBlueprint
from src.runtime.environment.environment_template_library import get_environment_template_library


# ---------------------------------------------------------------------------
# Position hint table
# ---------------------------------------------------------------------------

_POSITION_HINTS: Dict[str, str] = {
    # floors
    "floor":                  "entire_floor_plane",
    "concrete_floor":         "entire_floor_plane",
    "cracked_concrete_floor": "entire_floor_plane",
    "large_floor":            "entire_floor_plane",
    "lab_floor":              "entire_floor_plane",
    "sterile_floor":          "entire_floor_plane",
    "clean_floor":            "entire_floor_plane",
    "raised_floor":           "entire_floor_plane",
    "marble_floor":           "entire_floor_plane",
    "stone_floor":            "entire_floor_plane",
    "deck_plating":           "entire_floor_plane",
    "sand_ground":            "entire_floor_plane",
    "forest_floor":           "entire_floor_plane",
    "dirt_ground":            "entire_floor_plane",
    "pavement":               "foreground_to_midground",
    "fire_pit_ring":          "center_floor",
    # walls
    "wall":                   "four_perimeter_walls",
    "large_wall":             "four_perimeter_walls",
    "clean_wall":             "four_perimeter_walls",
    "damaged_wall":           "partial_perimeter_walls",
    "stone_wall":             "four_perimeter_walls",
    "corridor_wall_panel":    "two_side_walls",
    "building_facade":        "background_perimeter",
    "hangar_wall":            "four_perimeter_walls",
    "perimeter_fence":        "outer_perimeter",
    # ceilings
    "ceiling":                "overhead_plane",
    "high_ceiling":           "overhead_plane_high",
    "vaulted_ceiling":        "vaulted_overhead",
    "ceiling_panel":          "overhead_plane",
    "roof_structure":         "overhead_spanning",
    "partial_roof":           "partial_overhead",
    "canopy_layer":           "overhead_organic",
    "sky_dome":               "overhead_infinite",
    "shelter_tarp":           "background_zone",
    # doors
    "door":                   "foreground_wall",
    "main_entrance_door":     "foreground_wall_center",
    "great_wooden_door":      "foreground_wall_center",
    "loading_door":           "foreground_wall_large",
    "sliding_door":           "any_wall",
    "security_door":          "foreground_wall",
    "swing_door":             "foreground_wall_center",
    "broken_door":            "foreground_wall",
    "large_entry_opening":    "foreground_wall_large",
    # windows
    "window":                 "side_walls",
    "arched_window":          "upper_side_walls",
    "large_window":           "side_walls",
    "broken_window":          "side_walls",
    "viewport":               "any_wall",
    "glass_partition":        "interior_divider",
    "internal_window":        "interior_divider",
    # support structure
    "steel_column":           "perimeter_corners",
    "support_column":         "perimeter_corners",
    "decorative_column":      "midground_sides",
    "bar_counter":            "background_wall",
    "mezzanine_platform":     "upper_perimeter",
    "mezzanine_railing":      "upper_perimeter",
    "cable_tray":             "ceiling_perimeter",
    "fume_hood":              "wall_mounted_high",
    "catwalk":                "upper_midground",
    "crane_rail":             "overhead_rails",
    "rubble_pile":            "scattered_floor",
    "debris_pile":            "scattered_floor",
    "dune_formation":         "midground_mound",
    "large_tree":             "midground_vertical",
    "rock_formation":         "midground_cluster",
    "sidewalk_kerb":          "perimeter_edge",
    "road_surface":           "center_road_plane",
    "torch_bracket":          "wall_mounted_mid",
    "traffic_light":          "perimeter_vertical",
    "watch_tower":            "background_vertical",
    "supply_depot":           "background_perimeter",
    "display_wall":           "background_wall",
    "partition_wall":         "interior_divider",
    "cable_conduit":          "wall_mounted_mid",
    "skylight":               "overhead_plane",
}

# Floor, wall, ceiling, door, window keywords for detection
_FLOOR_KW  = ["floor", "ground", "pavement", "plating", "deck", "pavement", "dirt", "sand", "fire_pit"]
_WALL_KW   = ["wall", "facade", "panel", "fence", "barrier"]
_CEIL_KW   = ["ceiling", "roof", "canopy", "dome", "tarp", "overhead"]
_DOOR_KW   = ["door", "airlock", "gate", "opening", "entrance"]
_WIN_KW    = ["window", "viewport", "port", "skylight", "partition"]


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class BuiltStructuralElement:
    """A single structural element in the environment scaffold."""

    element_type: str = ""
    display_name: str = ""
    position_hint: str = ""
    required: bool = True
    present: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "element_type":  self.element_type,
            "display_name":  self.display_name,
            "position_hint": self.position_hint,
            "required":      self.required,
            "present":       self.present,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "BuiltStructuralElement":
        return cls(
            element_type  = str(d.get("element_type", "")),
            display_name  = str(d.get("display_name", "")),
            position_hint = str(d.get("position_hint", "")),
            required      = bool(d.get("required", True)),
            present       = bool(d.get("present", True)),
        )


@dataclass
class EnvironmentStructurePlan:
    """Full structural scaffold produced by EnvironmentStructureBuilder."""

    environment_name: str = ""
    elements: List[BuiltStructuralElement] = field(default_factory=list)

    # Quick-access presence flags
    floor_present:   bool = False
    walls_present:   bool = False
    ceiling_present: bool = False
    doors_present:   bool = False
    windows_present: bool = False

    structure_complete: bool = False
    missing_required: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    build_time: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "environment_name":  self.environment_name,
            "elements":          [e.to_dict() for e in self.elements],
            "floor_present":     self.floor_present,
            "walls_present":     self.walls_present,
            "ceiling_present":   self.ceiling_present,
            "doors_present":     self.doors_present,
            "windows_present":   self.windows_present,
            "structure_complete": self.structure_complete,
            "missing_required":  list(self.missing_required),
            "errors":            list(self.errors),
            "build_time":        self.build_time,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "EnvironmentStructurePlan":
        return cls(
            environment_name  = str(d.get("environment_name", "")),
            elements          = [BuiltStructuralElement.from_dict(e) for e in d.get("elements", [])],
            floor_present     = bool(d.get("floor_present", False)),
            walls_present     = bool(d.get("walls_present", False)),
            ceiling_present   = bool(d.get("ceiling_present", False)),
            doors_present     = bool(d.get("doors_present", False)),
            windows_present   = bool(d.get("windows_present", False)),
            structure_complete = bool(d.get("structure_complete", False)),
            missing_required  = list(d.get("missing_required", [])),
            errors            = list(d.get("errors", [])),
            build_time        = float(d.get("build_time", 0.0)),
        )


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

def _element_from_type(elem_type: str, required: bool) -> BuiltStructuralElement:
    pos = _POSITION_HINTS.get(elem_type, "scene_space")
    display = elem_type.replace("_", " ").title()
    return BuiltStructuralElement(
        element_type  = elem_type,
        display_name  = display,
        position_hint = pos,
        required      = required,
        present       = True,
    )


def _has_kw(elem_types: List[str], keywords: List[str]) -> bool:
    for et in elem_types:
        for kw in keywords:
            if kw in et:
                return True
    return False


class EnvironmentStructureBuilder:
    """Build a full structural plan for an environment.

    This is the §44 package version. It uses EnvironmentTemplateLibrary
    (not ArchitecturalTemplates from src.runtime.assets.assembly).
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def build_environment(self, environment_name: str) -> EnvironmentStructurePlan:
        """Build the full structural plan from the template library.

        This is the primary public method. Pass the environment name; the
        builder fetches the blueprint from the template library automatically.
        """
        lib = get_environment_template_library()
        blueprint = lib.get_template(environment_name)
        plan = self.build_structure(blueprint)
        # Always use the caller-supplied name (blueprint for unknown envs is "generic")
        plan.environment_name = environment_name
        return plan

    def build_structure(self, blueprint: EnvironmentBlueprint) -> EnvironmentStructurePlan:
        """Build structure from an explicit EnvironmentBlueprint."""
        t0 = time.perf_counter()
        with self._lock:
            try:
                return self._build(blueprint, t0)
            except Exception as exc:
                return EnvironmentStructurePlan(
                    environment_name = blueprint.environment_name,
                    structure_complete = False,
                    errors = [f"Build error: {exc}"],
                    build_time = time.perf_counter() - t0,
                )

    def _build(self, blueprint: EnvironmentBlueprint, t0: float) -> EnvironmentStructurePlan:
        elements: List[BuiltStructuralElement] = []
        missing_required: List[str] = []
        errors: List[str] = []

        # Build required structural elements
        for elem_type in blueprint.required_structure:
            elements.append(_element_from_type(elem_type, required=True))

        # Build optional structural elements
        for elem_type in blueprint.optional_structure:
            elements.append(_element_from_type(elem_type, required=False))

        defined_types = [e.element_type for e in elements]

        # Check structural completeness
        floor_pres   = _has_kw(defined_types, _FLOOR_KW)
        walls_pres   = _has_kw(defined_types, _WALL_KW)
        ceiling_pres = _has_kw(defined_types, _CEIL_KW)
        doors_pres   = _has_kw(defined_types, _DOOR_KW)
        windows_pres = _has_kw(defined_types, _WIN_KW)

        req_set = {s.lower() for s in blueprint.required_structure}

        if any(kw in " ".join(req_set) for kw in _FLOOR_KW) and not floor_pres:
            missing_required.append("floor")
            errors.append("floor required but not defined")
        if any(kw in " ".join(req_set) for kw in _WALL_KW) and not walls_pres:
            missing_required.append("wall")
            errors.append("wall required but not defined")
        if any(kw in " ".join(req_set) for kw in _CEIL_KW) and not ceiling_pres:
            missing_required.append("ceiling")
            errors.append("ceiling required but not defined")

        structure_complete = len(missing_required) == 0

        return EnvironmentStructurePlan(
            environment_name  = blueprint.environment_name,
            elements          = elements,
            floor_present     = floor_pres,
            walls_present     = walls_pres,
            ceiling_present   = ceiling_pres,
            doors_present     = doors_pres,
            windows_present   = windows_pres,
            structure_complete = structure_complete,
            missing_required  = missing_required,
            errors            = errors,
            build_time        = time.perf_counter() - t0,
        )

    # Individual sub-builders (each returns elements for that category)

    def build_floor(self, environment_name: str) -> List[BuiltStructuralElement]:
        """Return structural elements classified as floor."""
        plan = self.build_environment(environment_name)
        return [e for e in plan.elements if _has_kw([e.element_type], _FLOOR_KW)]

    def build_walls(self, environment_name: str) -> List[BuiltStructuralElement]:
        """Return structural elements classified as walls."""
        plan = self.build_environment(environment_name)
        return [e for e in plan.elements if _has_kw([e.element_type], _WALL_KW)]

    def build_ceiling(self, environment_name: str) -> List[BuiltStructuralElement]:
        """Return structural elements classified as ceiling."""
        plan = self.build_environment(environment_name)
        return [e for e in plan.elements if _has_kw([e.element_type], _CEIL_KW)]

    def build_doors(self, environment_name: str) -> List[BuiltStructuralElement]:
        """Return structural elements classified as doors."""
        plan = self.build_environment(environment_name)
        return [e for e in plan.elements if _has_kw([e.element_type], _DOOR_KW)]

    def build_windows(self, environment_name: str) -> List[BuiltStructuralElement]:
        """Return structural elements classified as windows."""
        plan = self.build_environment(environment_name)
        return [e for e in plan.elements if _has_kw([e.element_type], _WIN_KW)]

    def build_support_structure(self, environment_name: str) -> List[BuiltStructuralElement]:
        """Return structural elements that are neither floor/wall/ceiling/door/window."""
        plan = self.build_environment(environment_name)
        all_kw = _FLOOR_KW + _WALL_KW + _CEIL_KW + _DOOR_KW + _WIN_KW
        return [e for e in plan.elements if not _has_kw([e.element_type], all_kw)]

    def validate_structure(self, plan: EnvironmentStructurePlan) -> List[str]:
        """Return a list of structural validation errors."""
        errors: List[str] = []
        if not plan.floor_present:
            errors.append("floor missing")
        if not plan.walls_present:
            errors.append("wall missing")
        errors.extend(plan.missing_required)
        return errors


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
