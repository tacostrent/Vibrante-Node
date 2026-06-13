"""
Architectural Templates (Tier 9.5 — Structural Environment Assembly)
=====================================================================
Provides hard-coded EnvironmentBlueprint instances for 21 production
environments. Each blueprint declares the structural elements required,
the major anchor assets, secondary supports, decorative dressing, and
atmospheric layers for that environment type.

Templates for:
  Interior:   western_room, saloon, living_room, office, hotel_lobby,
              restaurant, library
  Industrial: industrial_hangar, warehouse, abandoned_factory
  Scientific: robotics_lab, research_lab, medical_lab, control_room
  Sci-Fi:     sci_fi_corridor, space_station
  Outdoor:    city_street, forest, desert
  Fantasy:    castle_hall, survival_camp, dungeon

DESIGN RULES:
  1. No bridge calls. No Houdini imports. Planning only.
  2. All templates are read-only constants — never mutate them at runtime.
  3. Unknown environments get the _GENERIC_BLUEPRINT fallback.
  4. Never raises.

Public API:
    ArchitecturalTemplates
    get_architectural_templates()
    reset_architectural_templates_for_tests()
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional

from src.runtime.assets.assembly.environment_blueprint import EnvironmentBlueprint


# ---------------------------------------------------------------------------
# Template definitions
# ---------------------------------------------------------------------------

_BUILTIN_TEMPLATES: Dict[str, EnvironmentBlueprint] = {

    # ---- Interior / Domestic ---------------------------------------------------

    "western_room": EnvironmentBlueprint(
        environment_name    = "western_room",
        floor_required      = True,
        wall_required       = True,
        ceiling_required    = False,
        door_required       = True,
        window_required     = True,
        structural_assets   = ["floor", "wall", "door", "window"],
        anchor_assets       = ["table", "bar_counter", "fireplace"],
        support_assets      = ["chair", "stool", "shelf", "bench"],
        decorative_assets   = ["cup", "bottle", "lantern", "poster", "book", "bucket"],
        atmosphere_assets   = ["dust", "warm_volumetric", "window_light"],
        structural_optional = ["wooden_beam", "shelf_unit", "support_column"],
        description         = "Traditional western interior with table, bar, and fireplace as focal elements.",
    ),

    "saloon": EnvironmentBlueprint(
        environment_name    = "saloon",
        floor_required      = True,
        wall_required       = True,
        ceiling_required    = False,
        door_required       = True,
        window_required     = True,
        structural_assets   = ["floor", "wall", "saloon_door", "window"],
        anchor_assets       = ["bar_counter", "gambling_table", "stage"],
        support_assets      = ["chair", "stool", "barrel", "shelf"],
        decorative_assets   = ["bottle", "glass", "lantern", "wanted_poster", "bucket"],
        atmosphere_assets   = ["dust", "warm_amber_light", "piano_ambient"],
        structural_optional = ["mezzanine_railing", "wooden_beam", "mirror_behind_bar"],
        description         = "Western saloon with bar counter as the primary anchor and gambling tables as support.",
    ),

    "living_room": EnvironmentBlueprint(
        environment_name    = "living_room",
        floor_required      = True,
        wall_required       = True,
        ceiling_required    = True,
        door_required       = True,
        window_required     = True,
        structural_assets   = ["floor", "wall", "ceiling", "door", "window"],
        anchor_assets       = ["sofa", "coffee_table", "television"],
        support_assets      = ["armchair", "bookcase", "lamp", "rug"],
        decorative_assets   = ["book", "vase", "cushion", "remote", "plant"],
        atmosphere_assets   = ["window_light", "warm_ambient", "tv_glow"],
        structural_optional = ["fireplace", "curtain", "archway"],
        description         = "Domestic living room with sofa arrangement as the focal anchor.",
    ),

    "office": EnvironmentBlueprint(
        environment_name    = "office",
        floor_required      = True,
        wall_required       = True,
        ceiling_required    = True,
        door_required       = True,
        window_required     = True,
        structural_assets   = ["floor", "wall", "ceiling", "door", "window"],
        anchor_assets       = ["desk", "office_chair", "computer"],
        support_assets      = ["shelf", "filing_cabinet", "whiteboard", "printer"],
        decorative_assets   = ["book", "plant", "mug", "paper_stack", "pen_holder"],
        atmosphere_assets   = ["fluorescent_light", "window_ambient"],
        structural_optional = ["partition_wall", "meeting_table", "projector"],
        description         = "Corporate or home office with desk as primary anchor.",
    ),

    "hotel_lobby": EnvironmentBlueprint(
        environment_name    = "hotel_lobby",
        floor_required      = True,
        wall_required       = True,
        ceiling_required    = True,
        door_required       = True,
        window_required     = False,
        structural_assets   = ["marble_floor", "wall", "ceiling", "main_entrance_door", "pillar"],
        anchor_assets       = ["reception_desk", "seating_group", "concierge_stand"],
        support_assets      = ["sofa", "armchair", "plant", "luggage_rack"],
        decorative_assets   = ["vase", "artwork", "lobby_lamp", "rug", "brochure_stand"],
        atmosphere_assets   = ["chandelier_light", "warm_lobby_ambient"],
        structural_optional = ["elevator_bank", "staircase", "fountain"],
        description         = "Grand hotel lobby with reception desk as the primary anchor and seating areas as support.",
    ),

    "restaurant": EnvironmentBlueprint(
        environment_name    = "restaurant",
        floor_required      = True,
        wall_required       = True,
        ceiling_required    = True,
        door_required       = True,
        window_required     = True,
        structural_assets   = ["floor", "wall", "ceiling", "door", "window"],
        anchor_assets       = ["hero_dining_table", "kitchen_pass", "host_stand"],
        support_assets      = ["dining_chair", "booth", "wine_rack", "service_station"],
        decorative_assets   = ["candle", "flower_arrangement", "tablecloth", "menu_card"],
        atmosphere_assets   = ["warm_dining_ambient", "candle_glow", "pendant_light"],
        structural_optional = ["bar_counter", "private_booth", "wine_cellar_display"],
        description         = "Restaurant dining space with hero table and kitchen presence establishing environment identity.",
    ),

    "library": EnvironmentBlueprint(
        environment_name    = "library",
        floor_required      = True,
        wall_required       = True,
        ceiling_required    = True,
        door_required       = True,
        window_required     = True,
        structural_assets   = ["floor", "wall", "ceiling", "door", "window"],
        anchor_assets       = ["bookshelf_wall", "reading_table", "librarian_desk"],
        support_assets      = ["reading_chair", "reading_lamp", "catalogue_stand", "step_ladder"],
        decorative_assets   = ["book", "globe", "bust", "plant", "magnifying_glass"],
        atmosphere_assets   = ["diffuse_reading_light", "warm_ambient"],
        structural_optional = ["mezzanine", "spiral_staircase", "archway", "skylight"],
        description         = "Library with bookshelf walls as structural anchors and reading table as activity focus.",
    ),

    # ---- Industrial -----------------------------------------------------------

    "industrial_hangar": EnvironmentBlueprint(
        environment_name    = "industrial_hangar",
        floor_required      = True,
        wall_required       = True,
        ceiling_required    = False,
        door_required       = True,
        window_required     = False,
        structural_assets   = ["concrete_floor", "wall", "support_column", "roof_structure", "steel_beam", "hangar_door"],
        anchor_assets       = ["main_machine", "industrial_furnace", "crane"],
        support_assets      = ["pipe_network", "electronic_panel", "catwalk", "service_platform"],
        decorative_assets   = ["barrel", "bucket", "toolbox", "warning_sign", "fuel_drum"],
        atmosphere_assets   = ["industrial_fog", "volumetric_shaft", "overhead_sodium_light"],
        structural_optional = ["catwalk_system", "ventilation_duct", "emergency_exit"],
        description         = "Large industrial space with main machine or crane as the defining anchor.",
    ),

    "warehouse": EnvironmentBlueprint(
        environment_name    = "warehouse",
        floor_required      = True,
        wall_required       = True,
        ceiling_required    = True,
        door_required       = True,
        window_required     = False,
        structural_assets   = ["concrete_floor", "wall", "high_ceiling", "loading_door", "support_column"],
        anchor_assets       = ["shelving_rack", "pallet_stack", "forklift"],
        support_assets      = ["pallet", "industrial_lamp", "shipping_container"],
        decorative_assets   = ["cardboard_box", "barrel", "bucket", "warning_tape", "fire_extinguisher"],
        atmosphere_assets   = ["warehouse_haze", "overhead_industrial_light"],
        structural_optional = ["mezzanine_storage", "loading_dock", "conveyor_belt"],
        description         = "High-ceiling storage warehouse with racking systems and pallets as the dominant elements.",
    ),

    "abandoned_factory": EnvironmentBlueprint(
        environment_name    = "abandoned_factory",
        floor_required      = True,
        wall_required       = True,
        ceiling_required    = False,
        door_required       = False,
        window_required     = False,
        structural_assets   = ["cracked_concrete_floor", "damaged_wall", "exposed_steel_structure", "rubble_pile"],
        anchor_assets       = ["broken_machine", "rusted_crane", "collapsed_conveyor"],
        support_assets      = ["rubble", "rusted_pipe", "broken_catwalk", "exposed_wiring"],
        decorative_assets   = ["debris", "graffiti", "broken_glass", "weeds", "dust"],
        atmosphere_assets   = ["dust_particles", "god_rays_through_holes", "ambient_decay"],
        structural_optional = ["collapsed_roof_section", "overgrown_vegetation", "stagnant_water"],
        description         = "Decayed industrial ruin — broken machinery and collapsed structure define the space.",
    ),

    # ---- Scientific -----------------------------------------------------------

    "robotics_lab": EnvironmentBlueprint(
        environment_name    = "robotics_lab",
        floor_required      = True,
        wall_required       = True,
        ceiling_required    = True,
        door_required       = True,
        window_required     = False,
        structural_assets   = ["lab_floor", "wall", "ceiling", "security_door", "lab_partition"],
        anchor_assets       = ["robot_platform", "research_console", "testing_rig"],
        support_assets      = ["server_rack", "equipment_bay", "workbench", "safety_barrier"],
        decorative_assets   = ["cable_bundle", "electronic_component", "tool_kit", "notebook"],
        atmosphere_assets   = ["cool_white_ambient", "led_strip", "equipment_status_glow"],
        structural_optional = ["glass_observation_partition", "cable_tray", "emergency_stop_station"],
        description         = "Clean robotics research lab with active robot platform as the central anchor.",
    ),

    "research_lab": EnvironmentBlueprint(
        environment_name    = "research_lab",
        floor_required      = True,
        wall_required       = True,
        ceiling_required    = True,
        door_required       = True,
        window_required     = True,
        structural_assets   = ["lab_floor", "wall", "ceiling", "door", "window"],
        anchor_assets       = ["central_lab_bench", "server_cluster", "imaging_equipment"],
        support_assets      = ["fume_hood", "storage_cabinet", "equipment_stand", "waste_bin"],
        decorative_assets   = ["flask", "specimen_jar", "notebook", "plant", "whiteboard"],
        atmosphere_assets   = ["cool_lab_ambient", "task_lighting", "monitor_glow"],
        structural_optional = ["clean_room_barrier", "airlock_chamber", "observation_window"],
        description         = "Research laboratory with central bench and specialist imaging equipment as anchors.",
    ),

    "medical_lab": EnvironmentBlueprint(
        environment_name    = "medical_lab",
        floor_required      = True,
        wall_required       = True,
        ceiling_required    = True,
        door_required       = True,
        window_required     = False,
        structural_assets   = ["sterile_floor", "wall", "ceiling", "door"],
        anchor_assets       = ["operating_table", "medical_scanner", "patient_monitor"],
        support_assets      = ["iv_stand", "medical_cabinet", "emergency_cart", "monitor_arm"],
        decorative_assets   = ["medical_tool", "specimen_container", "biohazard_warning", "surgical_light"],
        atmosphere_assets   = ["clinical_white_ambient", "sterile_overhead_lighting"],
        structural_optional = ["observation_glass_wall", "decontamination_chamber", "scrub_station"],
        description         = "Sterile medical environment with operating table as the definitive focal element.",
    ),

    "control_room": EnvironmentBlueprint(
        environment_name    = "control_room",
        floor_required      = True,
        wall_required       = True,
        ceiling_required    = True,
        door_required       = True,
        window_required     = False,
        structural_assets   = ["raised_floor", "wall", "ceiling", "security_door"],
        anchor_assets       = ["main_console_bank", "large_screen_array", "command_chair"],
        support_assets      = ["operator_workstation", "communication_station", "server_rack"],
        decorative_assets   = ["status_indicator_light", "coffee_mug", "notepad", "cable_management"],
        atmosphere_assets   = ["console_glow", "screen_blue_light", "dim_ambient"],
        structural_optional = ["raised_command_platform", "observation_window_to_ops_floor"],
        description         = "Mission control layout with main console array and large display wall as hero elements.",
    ),

    # ---- Sci-Fi ---------------------------------------------------------------

    "sci_fi_corridor": EnvironmentBlueprint(
        environment_name    = "sci_fi_corridor",
        floor_required      = True,
        wall_required       = True,
        ceiling_required    = True,
        door_required       = True,
        window_required     = False,
        structural_assets   = ["deck_plating", "corridor_wall_panel", "ceiling_panel", "blast_door", "sliding_door"],
        anchor_assets       = ["electronic_terminal", "airlock_control", "security_panel"],
        support_assets      = ["pipe_conduit", "vent_grille", "emergency_light", "cable_tray"],
        decorative_assets   = ["hologram_emitter", "warning_light", "hazard_decal", "hand_scanner"],
        atmosphere_assets   = ["cool_corridor_ambient", "led_strip_lighting", "scan_beam"],
        structural_optional = ["intersection_junction", "observation_port", "maintenance_hatch"],
        description         = "Functional sci-fi corridor defined by blast doors and electronic panels.",
    ),

    "space_station": EnvironmentBlueprint(
        environment_name    = "space_station",
        floor_required      = True,
        wall_required       = True,
        ceiling_required    = True,
        door_required       = True,
        window_required     = True,
        structural_assets   = ["grating_floor", "reinforced_hull_wall", "ceiling_panel", "airlock_door", "viewport"],
        anchor_assets       = ["navigation_console", "command_interface", "life_support_unit"],
        support_assets      = ["storage_locker", "equipment_bay", "communication_array"],
        decorative_assets   = ["tool_kit", "personal_effect", "warning_decal", "emergency_kit"],
        atmosphere_assets   = ["cool_station_ambient", "instrument_glow", "starfield_viewport"],
        structural_optional = ["solar_panel_view", "docking_clamp", "observation_blister"],
        description         = "Compact space station module with navigation console and viewport as defining elements.",
    ),

    # ---- Outdoor / Nature -----------------------------------------------------

    "city_street": EnvironmentBlueprint(
        environment_name    = "city_street",
        floor_required      = True,
        wall_required       = True,
        ceiling_required    = False,
        door_required       = False,
        window_required     = False,
        structural_assets   = ["pavement", "road_surface", "building_facade", "sidewalk_kerb"],
        anchor_assets       = ["hero_building_entrance", "street_lamp_cluster", "bus_stop"],
        support_assets      = ["bench", "trash_bin", "fire_hydrant", "post_box"],
        decorative_assets   = ["newspaper", "puddle_decal", "poster", "graffiti", "cigarette_butt"],
        atmosphere_assets   = ["overcast_sky", "street_lamp_halo", "wet_pavement_reflection"],
        structural_optional = ["traffic_light", "crosswalk_marking", "awning", "parked_vehicle"],
        description         = "Urban street scene with building facades as spatial walls and street furniture as dressing.",
    ),

    "forest": EnvironmentBlueprint(
        environment_name    = "forest",
        floor_required      = True,
        wall_required       = False,
        ceiling_required    = False,
        door_required       = False,
        window_required     = False,
        structural_assets   = ["forest_floor", "large_tree", "canopy_layer"],
        anchor_assets       = ["ancient_tree", "rock_formation", "fallen_log"],
        support_assets      = ["medium_tree", "bush_cluster", "fern_patch"],
        decorative_assets   = ["mushroom", "flower", "moss_patch", "leaf_pile", "twig"],
        atmosphere_assets   = ["forest_volumetric_light", "dappled_ambient", "nature_mist"],
        structural_optional = ["stream", "boulder_cluster", "hollow_log", "tree_stump"],
        description         = "Dense woodland with ancient trees and rock formations as primary spatial anchors.",
    ),

    "desert": EnvironmentBlueprint(
        environment_name    = "desert",
        floor_required      = True,
        wall_required       = False,
        ceiling_required    = False,
        door_required       = False,
        window_required     = False,
        structural_assets   = ["sand_ground", "dune_formation", "sky_dome"],
        anchor_assets       = ["rock_formation", "ancient_ruin", "cactus_cluster"],
        support_assets      = ["small_rock", "dry_shrub", "sand_dune"],
        decorative_assets   = ["bleached_bone", "weathered_artifact", "sand_ripple", "small_cactus"],
        atmosphere_assets   = ["harsh_overhead_sun", "heat_haze_shimmer", "dust_wind"],
        structural_optional = ["oasis_vegetation", "canyon_wall", "abandoned_vehicle", "dry_riverbed"],
        description         = "Arid desert landscape with rock formations and ruins providing the only hard anchors.",
    ),

    # ---- Fantasy / Historical --------------------------------------------------

    "castle_hall": EnvironmentBlueprint(
        environment_name    = "castle_hall",
        floor_required      = True,
        wall_required       = True,
        ceiling_required    = True,
        door_required       = True,
        window_required     = True,
        structural_assets   = ["stone_floor", "stone_wall", "vaulted_ceiling", "great_wooden_door", "arched_window", "pillar"],
        anchor_assets       = ["throne", "main_fireplace", "banner_display"],
        support_assets      = ["long_dining_table", "candle_stand", "suit_of_armor", "tapestry"],
        decorative_assets   = ["torch", "goblet", "scroll", "shield", "heraldic_banner"],
        atmosphere_assets   = ["torch_fire", "smoky_warm_ambient", "shaft_through_window"],
        structural_optional = ["minstrel_gallery", "balcony_overlook", "trophy_display"],
        description         = "Grand medieval hall with throne and main fireplace establishing the ceremonial focal point.",
    ),

    "survival_camp": EnvironmentBlueprint(
        environment_name    = "survival_camp",
        floor_required      = True,
        wall_required       = False,
        ceiling_required    = False,
        door_required       = False,
        window_required     = False,
        structural_assets   = ["dirt_ground", "fire_pit_ring", "shelter_tarp", "perimeter_fence"],
        anchor_assets       = ["fire_pit", "main_shelter", "supply_cache"],
        support_assets      = ["crate_stack", "barrel", "sleeping_bag_roll", "medical_kit"],
        decorative_assets   = ["tin_can", "rope_coil", "survival_map", "lantern", "ration_pack"],
        atmosphere_assets   = ["campfire_glow", "night_ambient_sky", "smoke_wisp"],
        structural_optional = ["watchtower", "radio_antenna", "improvised_fence", "burned_vehicle"],
        description         = "Post-apocalyptic or wilderness survival camp with fire pit as the social and visual centre.",
    ),

    "dungeon": EnvironmentBlueprint(
        environment_name    = "dungeon",
        floor_required      = True,
        wall_required       = True,
        ceiling_required    = True,
        door_required       = True,
        window_required     = False,
        structural_assets   = ["wet_stone_floor", "stone_wall", "low_ceiling", "iron_door", "torch_bracket"],
        anchor_assets       = ["torture_rack", "prison_cell_block", "stone_altar"],
        support_assets      = ["iron_chain", "cage", "barrel", "wooden_bench"],
        decorative_assets   = ["wall_torch", "skull", "bucket", "manacle", "rat"],
        atmosphere_assets   = ["torch_flicker", "oppressive_dark_ambient", "water_drip"],
        structural_optional = ["drainage_channel", "secret_door", "alcove_niche"],
        description         = "Underground dungeon with iron doors and torch light as the environmental markers.",
    ),
}

# Single fallback for completely unknown environment names
_GENERIC_BLUEPRINT = EnvironmentBlueprint(
    environment_name    = "generic",
    floor_required      = True,
    wall_required       = True,
    ceiling_required    = False,
    door_required       = False,
    window_required     = False,
    structural_assets   = ["floor", "wall"],
    anchor_assets       = ["main_prop"],
    support_assets      = ["secondary_prop"],
    decorative_assets   = ["small_prop"],
    atmosphere_assets   = ["ambient_light"],
    structural_optional = [],
    description         = "Generic fallback blueprint — no specific environment type matched.",
)

SUPPORTED_ENVIRONMENTS: frozenset = frozenset(_BUILTIN_TEMPLATES.keys())


# ---------------------------------------------------------------------------
# ArchitecturalTemplates — singleton facade
# ---------------------------------------------------------------------------

class ArchitecturalTemplates:
    """Read-only access to per-environment EnvironmentBlueprint definitions."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def get_template(self, environment_name: str) -> EnvironmentBlueprint:
        """Return the EnvironmentBlueprint for the given environment.

        Falls back to the generic blueprint if the name is not recognised.
        Never raises.
        """
        try:
            return _BUILTIN_TEMPLATES.get(environment_name, _GENERIC_BLUEPRINT)
        except Exception:
            return _GENERIC_BLUEPRINT

    def list_environments(self) -> List[str]:
        """Return all supported environment names, sorted."""
        return sorted(SUPPORTED_ENVIRONMENTS)

    def supports(self, environment_name: str) -> bool:
        """Return True if a specific template exists for this environment."""
        return environment_name in SUPPORTED_ENVIRONMENTS

    def get_anchor_types(self, environment_name: str) -> List[str]:
        """Return the anchor asset types for the given environment."""
        return list(self.get_template(environment_name).anchor_assets)

    def get_structural_requirements(self, environment_name: str) -> dict:
        """Return a dict of structural requirements (floor/wall/ceiling/door/window)."""
        bp = self.get_template(environment_name)
        return {
            "floor_required":   bp.floor_required,
            "wall_required":    bp.wall_required,
            "ceiling_required": bp.ceiling_required,
            "door_required":    bp.door_required,
            "window_required":  bp.window_required,
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[ArchitecturalTemplates] = None
_LOCK = threading.Lock()


def get_architectural_templates() -> ArchitecturalTemplates:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = ArchitecturalTemplates()
        return _INSTANCE


def reset_architectural_templates_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
