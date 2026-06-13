"""
Environment Template Library (§44 — Structural Environment Assembly)
====================================================================
Provides 20 production-ready EnvironmentBlueprint templates. Each template
defines the structural requirements, anchor types, atmosphere profile, and
recommended asset types for a specific environment.

Unknown environment names return a generic fallback blueprint.

DESIGN RULES:
  1. No bridge calls. No Houdini imports. Advisory only.
  2. All 20 templates are hard-coded — no file I/O.
  3. Singleton pattern — get_environment_template_library() / reset_…_for_tests().
  4. Thread-safe.
  5. Never raises.

Public API:
    EnvironmentTemplateLibrary
    get_environment_template_library()
    reset_environment_template_library_for_tests()
"""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional

from src.runtime.environment.environment_blueprint import EnvironmentBlueprint


# ---------------------------------------------------------------------------
# Built-in template definitions
# ---------------------------------------------------------------------------

_DEFAULT_CONSTRUCTION_ORDER = ["structure", "zones", "anchors", "support", "decoration", "atmosphere"]


def _make(
    name: str,
    category: str,
    required_structure: List[str],
    optional_structure: List[str],
    required_zones: List[str],
    required_anchors: List[str],
    recommended_assets: List[str],
    atmosphere_profile: str,
    description: str,
) -> EnvironmentBlueprint:
    return EnvironmentBlueprint(
        environment_name    = name,
        environment_category = category,
        required_structure  = required_structure,
        optional_structure  = optional_structure,
        required_zones      = required_zones,
        required_anchors    = required_anchors,
        recommended_assets  = recommended_assets,
        atmosphere_profile  = atmosphere_profile,
        construction_order  = list(_DEFAULT_CONSTRUCTION_ORDER),
        description         = description,
    )


_BUILTIN_TEMPLATES: List[EnvironmentBlueprint] = [
    # -----------------------------------------------------------------------
    # Interior environments
    # -----------------------------------------------------------------------
    _make(
        name="western_room",
        category="interior",
        required_structure=["floor", "wall", "ceiling", "door"],
        optional_structure=["window", "support_beam"],
        required_zones=["hero_zone", "entrance_zone", "decoration_zone", "atmosphere_zone"],
        required_anchors=["main_table", "fireplace", "large_cabinet"],
        recommended_assets=["chair", "bottle", "cup", "lantern", "barrel", "wanted_poster", "saddle_bag"],
        atmosphere_profile="western_dust",
        description="Rustic western interior with a central table, fireplace, and warm lantern lighting.",
    ),
    _make(
        name="saloon",
        category="interior",
        required_structure=["floor", "wall", "bar_counter", "swing_door"],
        optional_structure=["window", "support_column"],
        required_zones=["hero_zone", "entrance_zone", "support_zone", "decoration_zone", "atmosphere_zone"],
        required_anchors=["bar_counter", "main_table", "stage_area"],
        recommended_assets=["stool", "bottle", "glass", "barrel", "piano", "playing_card", "lantern"],
        atmosphere_profile="western_dust",
        description="Classic saloon interior with bar, tables, and a stage area.",
    ),
    _make(
        name="living_room",
        category="interior",
        required_structure=["floor", "wall", "ceiling", "door"],
        optional_structure=["window", "fireplace"],
        required_zones=["hero_zone", "entrance_zone", "decoration_zone", "atmosphere_zone"],
        required_anchors=["sofa", "coffee_table", "bookshelf"],
        recommended_assets=["cushion", "plant", "lamp", "book", "mug", "rug"],
        atmosphere_profile="warm_interior",
        description="Comfortable residential living room with soft seating and warm lighting.",
    ),
    _make(
        name="office",
        category="interior",
        required_structure=["floor", "wall", "ceiling", "door"],
        optional_structure=["window", "partition_wall"],
        required_zones=["hero_zone", "entrance_zone", "support_zone", "decoration_zone", "atmosphere_zone"],
        required_anchors=["main_desk", "whiteboard", "shelving_unit"],
        recommended_assets=["chair", "monitor", "document", "mug", "plant", "filing_box", "pen_holder"],
        atmosphere_profile="cold_interior",
        description="Corporate office with desk clusters, whiteboards, and shelving.",
    ),
    _make(
        name="hotel_lobby",
        category="interior",
        required_structure=["marble_floor", "wall", "high_ceiling", "main_entrance_door"],
        optional_structure=["large_window", "decorative_column"],
        required_zones=["hero_zone", "entrance_zone", "support_zone", "decoration_zone", "atmosphere_zone"],
        required_anchors=["reception_desk", "seating_cluster", "decorative_column"],
        recommended_assets=["sofa", "plant", "chandelier", "luggage_cart", "signage", "clock"],
        atmosphere_profile="warm_interior",
        description="Grand hotel lobby with marble floor, reception desk, and decorative columns.",
    ),
    _make(
        name="restaurant",
        category="interior",
        required_structure=["floor", "wall", "ceiling", "door"],
        optional_structure=["window", "bar_counter"],
        required_zones=["hero_zone", "entrance_zone", "support_zone", "decoration_zone", "atmosphere_zone"],
        required_anchors=["main_table_cluster", "bar_counter", "service_station"],
        recommended_assets=["chair", "table", "wine_glass", "candle", "menu", "napkin_holder"],
        atmosphere_profile="warm_interior",
        description="Restaurant interior with dining tables, a bar, and warm ambient lighting.",
    ),
    _make(
        name="library",
        category="interior",
        required_structure=["floor", "wall", "high_ceiling", "door"],
        optional_structure=["window", "mezzanine_railing"],
        required_zones=["hero_zone", "entrance_zone", "support_zone", "decoration_zone", "atmosphere_zone"],
        required_anchors=["bookshelf_row", "reading_table", "catalogue_desk"],
        recommended_assets=["book", "lamp", "globe", "chair", "bookend", "ladder"],
        atmosphere_profile="cold_interior",
        description="Academic library with tall bookshelves, reading tables, and muted lighting.",
    ),
    # -----------------------------------------------------------------------
    # Industrial environments
    # -----------------------------------------------------------------------
    _make(
        name="warehouse",
        category="industrial",
        required_structure=["concrete_floor", "large_wall", "ceiling", "loading_door"],
        optional_structure=["skylight", "mezzanine_platform"],
        required_zones=["hero_zone", "entrance_zone", "support_zone", "background_zone", "decoration_zone", "atmosphere_zone"],
        required_anchors=["pallet_stack", "storage_shelf", "loading_area"],
        recommended_assets=["forklift", "pallet", "crate", "barrel", "safety_cone", "trolley"],
        atmosphere_profile="industrial_haze",
        description="Large warehouse with loading dock, pallet stacks, and industrial shelving.",
    ),
    _make(
        name="industrial_hangar",
        category="industrial",
        required_structure=["concrete_floor", "steel_column", "roof_structure", "hangar_wall", "large_entry_opening"],
        optional_structure=["catwalk", "crane_rail"],
        required_zones=["hero_zone", "entrance_zone", "support_zone", "background_zone", "decoration_zone", "atmosphere_zone"],
        required_anchors=["hero_machine", "crane", "industrial_furnace"],
        recommended_assets=["oil_drum", "toolbox", "safety_sign", "chain_hook", "work_lamp", "pipe"],
        atmosphere_profile="industrial_haze",
        description="Large industrial hangar with crane, heavy machinery, and steel structure.",
    ),
    _make(
        name="abandoned_factory",
        category="industrial",
        required_structure=["cracked_concrete_floor", "damaged_wall", "partial_roof", "broken_door"],
        optional_structure=["rubble_pile", "broken_window"],
        required_zones=["hero_zone", "entrance_zone", "support_zone", "decoration_zone", "atmosphere_zone"],
        required_anchors=["rusted_machine", "debris_pile", "old_conveyor"],
        recommended_assets=["debris", "rust_pipe", "broken_barrel", "dust_pile", "graffiti_tag"],
        atmosphere_profile="factory_smoke",
        description="Derelict factory with damaged structure, rusted machinery, and decay.",
    ),
    # -----------------------------------------------------------------------
    # Scientific environments
    # -----------------------------------------------------------------------
    _make(
        name="robotics_lab",
        category="scientific",
        required_structure=["lab_floor", "wall", "ceiling", "security_door"],
        optional_structure=["glass_partition", "cable_tray"],
        required_zones=["hero_zone", "entrance_zone", "support_zone", "decoration_zone", "atmosphere_zone"],
        required_anchors=["main_robot_station", "workbench", "equipment_rack"],
        recommended_assets=["robot_arm", "cable_bundle", "electronic_component", "monitor", "tool_kit"],
        atmosphere_profile="cold_interior",
        description="High-tech robotics laboratory with robotic arms, workbenches, and equipment racks.",
    ),
    _make(
        name="control_room",
        category="scientific",
        required_structure=["raised_floor", "wall", "ceiling", "security_door"],
        optional_structure=["display_wall", "cable_tray"],
        required_zones=["hero_zone", "entrance_zone", "support_zone", "decoration_zone", "atmosphere_zone"],
        required_anchors=["master_console", "operations_desk", "display_wall"],
        recommended_assets=["monitor", "keyboard", "mug", "document", "status_light", "headset"],
        atmosphere_profile="cold_interior",
        description="Mission control room with operator consoles and large display walls.",
    ),
    _make(
        name="medical_lab",
        category="scientific",
        required_structure=["sterile_floor", "clean_wall", "ceiling", "security_door"],
        optional_structure=["internal_window", "storage_cabinet"],
        required_zones=["hero_zone", "entrance_zone", "support_zone", "decoration_zone", "atmosphere_zone"],
        required_anchors=["examination_table", "medical_equipment", "specimen_storage"],
        recommended_assets=["syringe", "medical_tool", "flask", "microscope", "specimen_jar"],
        atmosphere_profile="cold_interior",
        description="Sterile medical laboratory with examination tables and specimen storage.",
    ),
    _make(
        name="research_lab",
        category="scientific",
        required_structure=["lab_floor", "wall", "ceiling", "security_door"],
        optional_structure=["glass_partition", "fume_hood"],
        required_zones=["hero_zone", "entrance_zone", "support_zone", "decoration_zone", "atmosphere_zone"],
        required_anchors=["central_workbench", "analysis_station", "chemical_storage"],
        recommended_assets=["flask", "notebook", "microscope", "chemical_jar", "safety_goggles"],
        atmosphere_profile="cold_interior",
        description="Scientific research laboratory with benches, analysis stations, and chemical storage.",
    ),
    # -----------------------------------------------------------------------
    # Sci-fi environments
    # -----------------------------------------------------------------------
    _make(
        name="sci_fi_corridor",
        category="sci-fi",
        required_structure=["deck_plating", "corridor_wall_panel", "ceiling_panel", "sliding_door"],
        optional_structure=["viewport", "cable_conduit"],
        required_zones=["hero_zone", "entrance_zone", "support_zone", "decoration_zone", "atmosphere_zone"],
        required_anchors=["control_panel", "equipment_bay", "airlock_door"],
        recommended_assets=["cable_bundle", "status_light", "fire_extinguisher", "data_pad"],
        atmosphere_profile="cold_interior",
        description="Sleek sci-fi corridor with wall panels, sliding doors, and equipment bays.",
    ),
    # -----------------------------------------------------------------------
    # Outdoor environments
    # -----------------------------------------------------------------------
    _make(
        name="city_street",
        category="outdoor",
        required_structure=["pavement", "building_facade", "sidewalk_kerb"],
        optional_structure=["road_surface", "traffic_light"],
        required_zones=["hero_zone", "entrance_zone", "support_zone", "background_zone", "decoration_zone", "atmosphere_zone"],
        required_anchors=["street_lamp_cluster", "shop_front", "bus_stop"],
        recommended_assets=["bench", "trash_can", "bicycle", "newspaper_stand", "planter"],
        atmosphere_profile="sunlit",
        description="Urban street scene with building facades, pavements, and street furniture.",
    ),
    _make(
        name="forest",
        category="outdoor",
        required_structure=["forest_floor", "large_tree", "canopy_layer"],
        optional_structure=["rock_formation", "stream_bed"],
        required_zones=["hero_zone", "entrance_zone", "support_zone", "background_zone", "decoration_zone", "atmosphere_zone"],
        required_anchors=["ancient_tree", "fallen_log", "rocky_outcrop"],
        recommended_assets=["mushroom", "fern", "small_rock", "root_cluster", "ivy"],
        atmosphere_profile="volumetric_light",
        description="Dense forest with ancient trees, fallen logs, and dappled volumetric light.",
    ),
    _make(
        name="desert",
        category="outdoor",
        required_structure=["sand_ground", "dune_formation", "sky_dome"],
        optional_structure=["rock_formation", "dead_tree"],
        required_zones=["hero_zone", "entrance_zone", "support_zone", "background_zone", "decoration_zone", "atmosphere_zone"],
        required_anchors=["rock_formation", "ruined_structure", "dead_tree"],
        recommended_assets=["cactus", "small_rock", "bleached_bone", "sand_drift", "tumbleweed"],
        atmosphere_profile="sunlit",
        description="Arid desert landscape with dunes, rock formations, and harsh sunlight.",
    ),
    # -----------------------------------------------------------------------
    # Fantasy environments
    # -----------------------------------------------------------------------
    _make(
        name="castle_hall",
        category="fantasy",
        required_structure=["stone_floor", "stone_wall", "vaulted_ceiling", "great_wooden_door"],
        optional_structure=["arched_window", "torch_bracket"],
        required_zones=["hero_zone", "entrance_zone", "support_zone", "decoration_zone", "atmosphere_zone"],
        required_anchors=["throne", "long_table", "fireplace"],
        recommended_assets=["banner", "candle_holder", "torch", "shield", "tapestry", "goblet"],
        atmosphere_profile="warm_interior",
        description="Medieval castle great hall with throne, banqueting table, and heraldic banners.",
    ),
    _make(
        name="survival_camp",
        category="fantasy",
        required_structure=["dirt_ground", "shelter_tarp", "perimeter_fence", "fire_pit_ring"],
        optional_structure=["watch_tower", "supply_depot"],
        required_zones=["hero_zone", "entrance_zone", "support_zone", "decoration_zone", "atmosphere_zone"],
        required_anchors=["camp_fire", "supply_crate_stack", "sleeping_area"],
        recommended_assets=["bedroll", "lantern_camp", "ration_pack", "rope_coil", "water_canteen"],
        atmosphere_profile="western_dust",
        description="Post-apocalyptic survivor camp with fire pit, supply crates, and improvised shelter.",
    ),
]

# Build lookup dict
_TEMPLATE_BY_NAME: Dict[str, EnvironmentBlueprint] = {t.environment_name: t for t in _BUILTIN_TEMPLATES}

# Generic fallback blueprint
_GENERIC_FALLBACK = EnvironmentBlueprint(
    environment_name    = "generic",
    environment_category = "interior",
    required_structure  = ["floor", "wall"],
    optional_structure  = ["ceiling", "door"],
    required_zones      = ["hero_zone", "entrance_zone", "decoration_zone", "atmosphere_zone"],
    required_anchors    = ["main_prop"],
    recommended_assets  = [],
    atmosphere_profile  = "warm_interior",
    construction_order  = list(_DEFAULT_CONSTRUCTION_ORDER),
    description         = "Generic fallback environment — use a specific template for best results.",
)


# ---------------------------------------------------------------------------
# Library class
# ---------------------------------------------------------------------------

class EnvironmentTemplateLibrary:
    """Repository of 20 built-in environment blueprint templates.

    Thread-safe. Never raises. Unknown names return a generic fallback.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def get_template(self, name: str) -> EnvironmentBlueprint:
        """Return the blueprint for ``name``, or the generic fallback."""
        key = (name or "").strip().lower()
        with self._lock:
            return _TEMPLATE_BY_NAME.get(key, _GENERIC_FALLBACK)

    def list_templates(self) -> List[str]:
        """Return all built-in template names (sorted)."""
        with self._lock:
            return sorted(_TEMPLATE_BY_NAME.keys())

    def get_by_category(self, category: str) -> List[EnvironmentBlueprint]:
        """Return all blueprints whose ``environment_category`` matches."""
        cat = (category or "").strip().lower()
        with self._lock:
            return [t for t in _BUILTIN_TEMPLATES if t.environment_category == cat]

    def search(self, query: str) -> List[EnvironmentBlueprint]:
        """Return blueprints whose name or description contains ``query`` (case-insensitive)."""
        q = (query or "").strip().lower()
        if not q:
            return list(_BUILTIN_TEMPLATES)
        with self._lock:
            results = []
            for t in _BUILTIN_TEMPLATES:
                if (q in t.environment_name
                        or q in t.description.lower()
                        or q in t.environment_category
                        or any(q in a for a in t.recommended_assets)
                        or any(q in s for s in t.required_structure)):
                    results.append(t)
            return results


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[EnvironmentTemplateLibrary] = None
_LOCK = threading.Lock()


def get_environment_template_library() -> EnvironmentTemplateLibrary:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = EnvironmentTemplateLibrary()
        return _INSTANCE


def reset_environment_template_library_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
