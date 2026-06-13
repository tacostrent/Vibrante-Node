"""
Environment Registry (§39 — Environment Expansion Pack)
=========================================================
Central registry for all 55 built-in production environments spanning
Industrial, Scientific, Military, Sci-Fi, Urban, Interior, Nature,
Fantasy, and Post-Apocalyptic categories.

Deterministic, thread-safe, no Houdini dependency.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Category constants
# ---------------------------------------------------------------------------

ENV_CATEGORY_INDUSTRIAL      = "industrial"
ENV_CATEGORY_SCIENTIFIC      = "scientific"
ENV_CATEGORY_MILITARY        = "military"
ENV_CATEGORY_SCI_FI          = "sci_fi"
ENV_CATEGORY_URBAN           = "urban"
ENV_CATEGORY_INTERIOR        = "interior"
ENV_CATEGORY_NATURE          = "nature"
ENV_CATEGORY_FANTASY         = "fantasy"
ENV_CATEGORY_POST_APOCALYPTIC = "post_apocalyptic"

ALL_CATEGORIES: frozenset = frozenset({
    ENV_CATEGORY_INDUSTRIAL,
    ENV_CATEGORY_SCIENTIFIC,
    ENV_CATEGORY_MILITARY,
    ENV_CATEGORY_SCI_FI,
    ENV_CATEGORY_URBAN,
    ENV_CATEGORY_INTERIOR,
    ENV_CATEGORY_NATURE,
    ENV_CATEGORY_FANTASY,
    ENV_CATEGORY_POST_APOCALYPTIC,
})

# ---------------------------------------------------------------------------
# Canonical environment name list (55 total)
# ---------------------------------------------------------------------------

BUILTIN_ENVIRONMENT_NAMES: frozenset = frozenset({
    # Industrial (8)
    "industrial_hangar", "abandoned_factory", "warehouse", "shipyard",
    "oil_refinery", "power_station", "mining_facility", "construction_site",
    # Scientific (6) — includes legacy control_room
    "robotics_lab", "research_lab", "medical_lab", "clean_room",
    "biohazard_facility", "control_room",
    # Military (5)
    "military_base", "command_center", "military_hangar", "checkpoint", "bunker",
    # Sci-Fi (6)
    "sci_fi_corridor", "space_station", "spaceship_bridge",
    "engineering_bay", "alien_facility", "cyberpunk_city",
    # Urban (6)
    "city_street", "alleyway", "subway_station",
    "parking_garage", "rooftop", "shopping_mall",
    # Interior (8)
    "western_room", "saloon", "living_room", "office",
    "hotel_lobby", "restaurant", "workshop", "library",
    # Nature (7)
    "forest", "jungle", "desert", "canyon", "mountain", "coastline", "swamp",
    # Fantasy (5)
    "castle_hall", "dungeon", "wizard_tower", "ancient_ruins", "temple",
    # Post-Apocalyptic (4)
    "abandoned_city", "destroyed_highway", "ruined_industrial_site", "survival_camp",
})


# ---------------------------------------------------------------------------
# EnvironmentDefinition
# ---------------------------------------------------------------------------

@dataclass
class EnvironmentDefinition:
    name:               str
    category:           str
    description:        str
    keywords:           List[str] = field(default_factory=list)
    asset_categories:   List[str] = field(default_factory=list)
    hero_asset_types:   List[str] = field(default_factory=list)
    support_asset_types: List[str] = field(default_factory=list)
    storytelling_tags:  List[str] = field(default_factory=list)
    lookdev_tags:       List[str] = field(default_factory=list)
    lighting_tags:      List[str] = field(default_factory=list)
    camera_tags:        List[str] = field(default_factory=list)
    atmosphere_tags:    List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name":               self.name,
            "category":           self.category,
            "description":        self.description,
            "keywords":           list(self.keywords),
            "asset_categories":   list(self.asset_categories),
            "hero_asset_types":   list(self.hero_asset_types),
            "support_asset_types": list(self.support_asset_types),
            "storytelling_tags":  list(self.storytelling_tags),
            "lookdev_tags":       list(self.lookdev_tags),
            "lighting_tags":      list(self.lighting_tags),
            "camera_tags":        list(self.camera_tags),
            "atmosphere_tags":    list(self.atmosphere_tags),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "EnvironmentDefinition":
        d = d if isinstance(d, dict) else {}
        return cls(
            name=str(d.get("name", "")),
            category=str(d.get("category", "")),
            description=str(d.get("description", "")),
            keywords=list(d.get("keywords") or []),
            asset_categories=list(d.get("asset_categories") or []),
            hero_asset_types=list(d.get("hero_asset_types") or []),
            support_asset_types=list(d.get("support_asset_types") or []),
            storytelling_tags=list(d.get("storytelling_tags") or []),
            lookdev_tags=list(d.get("lookdev_tags") or []),
            lighting_tags=list(d.get("lighting_tags") or []),
            camera_tags=list(d.get("camera_tags") or []),
            atmosphere_tags=list(d.get("atmosphere_tags") or []),
        )


# ---------------------------------------------------------------------------
# Built-in environment definitions
# ---------------------------------------------------------------------------

_BUILTIN: List[Dict[str, Any]] = [
    # -----------------------------------------------------------------------
    # INDUSTRIAL
    # -----------------------------------------------------------------------
    {
        "name": "industrial_hangar",
        "category": ENV_CATEGORY_INDUSTRIAL,
        "description": "Large industrial facility with high-bay ceilings, heavy machinery, and active operations.",
        "keywords": ["hangar", "industrial", "factory", "crane", "girder", "beam", "assembly", "machinery",
                     "turbine", "boiler", "conveyor", "valve", "scaffold", "silo", "duct", "pump",
                     "compressor", "welding", "pipe", "barrel", "tank", "gear"],
        "asset_categories": ["machinery", "structure", "prop", "vehicle", "equipment"],
        "hero_asset_types": ["machinery", "crane", "turbine", "vehicle"],
        "support_asset_types": ["pipe", "barrel", "scaffold", "equipment"],
        "storytelling_tags": ["industrial_power", "human_scale", "active_operation"],
        "lookdev_tags": ["industrial", "gritty", "worn", "aged"],
        "lighting_tags": ["overhead_fixtures", "volumetric_haze", "high_contrast"],
        "camera_tags": ["wide_establishing", "low_angle_machinery", "dutch_tilt"],
        "atmosphere_tags": ["dust_haze", "steam", "volumetric_depth"],
    },
    {
        "name": "abandoned_factory",
        "category": ENV_CATEGORY_INDUSTRIAL,
        "description": "Derelict industrial plant reclaimed by decay, overgrowth, and time.",
        "keywords": ["abandoned", "factory", "rust", "decay", "broken", "derelict", "old", "worn",
                     "graffiti", "debris", "rubble", "wreck", "deteriorated", "moss", "vegetation",
                     "collapsed", "ruin", "overgrown", "crumbled", "weathered"],
        "asset_categories": ["machinery", "structure", "prop", "vegetation", "terrain"],
        "hero_asset_types": ["rusted_machinery", "collapsed_structure", "overgrown_equipment"],
        "support_asset_types": ["debris", "rubble", "vegetation", "broken_glass"],
        "storytelling_tags": ["decay", "forgotten_history", "nature_reclaiming"],
        "lookdev_tags": ["rusted", "weathered", "aged", "damaged"],
        "lighting_tags": ["shaft_light", "heavy_volumetric", "deep_shadows"],
        "camera_tags": ["wide_decay", "environmental_storytelling", "low_angle"],
        "atmosphere_tags": ["dust_motes", "heavy_fog", "decay_atmosphere"],
    },
    {
        "name": "warehouse",
        "category": ENV_CATEGORY_INDUSTRIAL,
        "description": "Large storage facility with high shelving, forklifts, and organized logistics.",
        "keywords": ["warehouse", "shelf", "shelving", "forklift", "pallet", "crate", "storage",
                     "rack", "aisle", "loading", "dock", "inventory", "box", "container", "bay"],
        "asset_categories": ["prop", "vehicle", "structure", "equipment", "furniture"],
        "hero_asset_types": ["forklift", "pallet_rack", "storage_container"],
        "support_asset_types": ["crate", "box", "pallet", "shelf"],
        "storytelling_tags": ["logistics_operation", "human_scale", "commerce"],
        "lookdev_tags": ["industrial", "clean", "worn"],
        "lighting_tags": ["fluorescent_overhead", "aisle_lighting", "loading_dock_light"],
        "camera_tags": ["aisle_perspective", "wide_establishing", "overhead_view"],
        "atmosphere_tags": ["dust_particles", "loading_haze", "cool_industrial"],
    },
    {
        "name": "shipyard",
        "category": ENV_CATEGORY_INDUSTRIAL,
        "description": "Maritime industrial facility with dry docks, cranes, and vessels under construction.",
        "keywords": ["shipyard", "dock", "ship", "vessel", "hull", "crane", "drydock", "maritime",
                     "anchor", "chain", "weld", "scaffolding", "keel", "bow", "stern", "mast"],
        "asset_categories": ["machinery", "vehicle", "structure", "prop", "equipment"],
        "hero_asset_types": ["ship_hull", "gantry_crane", "drydock"],
        "support_asset_types": ["scaffold", "chain", "anchor", "welding_equipment"],
        "storytelling_tags": ["maritime_industry", "monumental_scale", "construction_progress"],
        "lookdev_tags": ["industrial", "rusted", "weathered", "worn"],
        "lighting_tags": ["overcast_exterior", "crane_shadow", "water_reflection"],
        "camera_tags": ["wide_dock_view", "hull_scale_shot", "overhead_dock"],
        "atmosphere_tags": ["sea_mist", "salt_air", "overcast_sky"],
    },
    {
        "name": "oil_refinery",
        "category": ENV_CATEGORY_INDUSTRIAL,
        "description": "Petroleum processing complex with distillation towers, pipes, and flare stacks.",
        "keywords": ["refinery", "oil", "petroleum", "tower", "distillation", "pipe", "flare",
                     "valve", "tank", "pump", "chemical", "industrial", "processing", "cracker",
                     "column", "heat_exchanger", "vessel", "pressure"],
        "asset_categories": ["machinery", "structure", "prop", "equipment"],
        "hero_asset_types": ["distillation_tower", "processing_vessel", "flare_stack"],
        "support_asset_types": ["pipe", "valve", "pump", "tank"],
        "storytelling_tags": ["industrial_complexity", "chemical_process", "energy_production"],
        "lookdev_tags": ["industrial", "gritty", "worn", "aged"],
        "lighting_tags": ["flare_light", "industrial_overhead", "night_flicker"],
        "camera_tags": ["tower_scale", "pipe_perspective", "night_refinery"],
        "atmosphere_tags": ["chemical_haze", "flare_smoke", "industrial_glow"],
    },
    {
        "name": "power_station",
        "category": ENV_CATEGORY_INDUSTRIAL,
        "description": "Electrical power generation facility with turbines, generators, and control infrastructure.",
        "keywords": ["power", "station", "turbine", "generator", "electrical", "transformer",
                     "switchgear", "cable", "pylon", "cooling_tower", "reactor", "energy",
                     "substation", "dynamo", "alternator", "grid"],
        "asset_categories": ["machinery", "structure", "equipment", "electronics"],
        "hero_asset_types": ["turbine", "generator", "cooling_tower"],
        "support_asset_types": ["transformer", "cable", "switchgear", "panel"],
        "storytelling_tags": ["energy_generation", "technological_scale", "critical_infrastructure"],
        "lookdev_tags": ["industrial", "clean", "technical"],
        "lighting_tags": ["high_bay_industrial", "warning_lights", "control_glow"],
        "camera_tags": ["turbine_hall_wide", "scale_establishing", "control_perspective"],
        "atmosphere_tags": ["steam_cooling", "electrical_hum", "industrial_scale"],
    },
    {
        "name": "mining_facility",
        "category": ENV_CATEGORY_INDUSTRIAL,
        "description": "Underground or surface mining operation with excavation equipment and processing infrastructure.",
        "keywords": ["mine", "mining", "excavation", "drill", "shaft", "tunnel", "ore", "rock",
                     "crusher", "conveyor", "loader", "dump_truck", "pit", "quarry", "coal",
                     "mineral", "shovel", "blasting"],
        "asset_categories": ["machinery", "vehicle", "structure", "terrain", "equipment"],
        "hero_asset_types": ["mining_excavator", "drill_rig", "ore_crusher"],
        "support_asset_types": ["conveyor", "ore_cart", "support_beam", "ventilation"],
        "storytelling_tags": ["extraction_industry", "underground_scale", "raw_material"],
        "lookdev_tags": ["industrial", "gritty", "dusty", "worn"],
        "lighting_tags": ["helmet_lamp", "shaft_lighting", "dust_filtered"],
        "camera_tags": ["tunnel_depth", "pit_scale", "equipment_close"],
        "atmosphere_tags": ["rock_dust", "underground_damp", "heavy_particles"],
    },
    {
        "name": "construction_site",
        "category": ENV_CATEGORY_INDUSTRIAL,
        "description": "Active building construction zone with cranes, scaffolding, and raw materials.",
        "keywords": ["construction", "site", "crane", "scaffold", "concrete", "steel", "rebar",
                     "foundation", "excavator", "cement", "beam", "girder", "workers", "harness",
                     "blueprint", "bulldozer", "framework", "building"],
        "asset_categories": ["machinery", "vehicle", "structure", "prop", "equipment"],
        "hero_asset_types": ["tower_crane", "excavator", "concrete_structure"],
        "support_asset_types": ["scaffold", "rebar", "cement_mixer", "barrier"],
        "storytelling_tags": ["creation_in_progress", "human_endeavor", "structural_ambition"],
        "lookdev_tags": ["industrial", "dusty", "raw", "unfinished"],
        "lighting_tags": ["daylight_exterior", "dust_diffusion", "shadow_scaffolding"],
        "camera_tags": ["upward_steel", "wide_site_view", "crane_perspective"],
        "atmosphere_tags": ["construction_dust", "cement_haze", "outdoor_wind"],
    },
    # -----------------------------------------------------------------------
    # SCIENTIFIC
    # -----------------------------------------------------------------------
    {
        "name": "robotics_lab",
        "category": ENV_CATEGORY_SCIENTIFIC,
        "description": "Precision robotics research and testing laboratory with automation equipment.",
        "keywords": ["robot", "robotic", "arm", "sensor", "panel", "circuit", "lab", "laboratory",
                     "tech", "scanner", "servo", "actuator", "computer", "monitor", "display",
                     "drone", "automation", "mechanical", "controller", "encoder", "camera", "lidar"],
        "asset_categories": ["robot", "electronics", "furniture", "prop", "equipment"],
        "hero_asset_types": ["robot_arm", "autonomous_robot", "test_rig"],
        "support_asset_types": ["workstation", "sensor_array", "computer", "monitor"],
        "storytelling_tags": ["technological_precision", "research_progress", "automation"],
        "lookdev_tags": ["clean", "technical", "polished", "sci_fi"],
        "lighting_tags": ["clean_fluorescent", "screen_practical", "precise_rim"],
        "camera_tags": ["robot_focus", "technical_detail", "lab_wide"],
        "atmosphere_tags": ["clinical_air", "clean_environment", "blue_cool"],
    },
    {
        "name": "control_room",
        "category": ENV_CATEGORY_SCIENTIFIC,
        "description": "Operations monitoring center with multi-screen displays and command consoles.",
        "keywords": ["console", "screen", "monitor", "terminal", "switch", "button", "panel",
                     "control", "desk", "chair", "keyboard", "radar", "dial", "gauge",
                     "interface", "hud", "hologram", "station", "workstation"],
        "asset_categories": ["electronics", "furniture", "prop", "equipment"],
        "hero_asset_types": ["command_console", "display_bank", "radar_screen"],
        "support_asset_types": ["workstation", "keyboard", "dial", "chair"],
        "storytelling_tags": ["command_authority", "information_flow", "decision_nexus"],
        "lookdev_tags": ["technical", "clean", "sci_fi"],
        "lighting_tags": ["screen_motivated", "cool_atmospheric", "neon_accent"],
        "camera_tags": ["screen_array", "operator_perspective", "convergent_lines"],
        "atmosphere_tags": ["screen_glow", "cool_blue", "tense_atmosphere"],
    },
    {
        "name": "research_lab",
        "category": ENV_CATEGORY_SCIENTIFIC,
        "description": "Scientific research laboratory with experimental apparatus and analytical equipment.",
        "keywords": ["research", "lab", "laboratory", "experiment", "apparatus", "flask", "beaker",
                     "microscope", "centrifuge", "spectroscope", "chemical", "sample", "test",
                     "analysis", "bench", "scientist", "data", "sensor"],
        "asset_categories": ["equipment", "furniture", "prop", "electronics"],
        "hero_asset_types": ["lab_bench", "analytical_instrument", "experiment_apparatus"],
        "support_asset_types": ["flask", "microscope", "computer", "storage_cabinet"],
        "storytelling_tags": ["scientific_discovery", "methodical_inquiry", "knowledge_building"],
        "lookdev_tags": ["clean", "clinical", "technical", "pristine"],
        "lighting_tags": ["cool_fluorescent", "task_lighting", "instrument_glow"],
        "camera_tags": ["bench_level", "instrument_detail", "wide_lab"],
        "atmosphere_tags": ["clean_air", "clinical_cool", "sterile_environment"],
    },
    {
        "name": "medical_lab",
        "category": ENV_CATEGORY_SCIENTIFIC,
        "description": "Medical research and diagnostic laboratory with hospital-grade equipment.",
        "keywords": ["medical", "hospital", "lab", "surgery", "operating", "sterilize", "syringe",
                     "iv", "scanner", "mri", "xray", "patient", "doctor", "nurse", "sterile",
                     "examination", "diagnostic", "pharmaceutical", "clinical"],
        "asset_categories": ["equipment", "furniture", "prop", "electronics"],
        "hero_asset_types": ["operating_table", "mri_scanner", "medical_equipment"],
        "support_asset_types": ["iv_stand", "monitor", "cabinet", "light_rig"],
        "storytelling_tags": ["healing", "life_death", "medical_precision"],
        "lookdev_tags": ["pristine", "clean", "clinical", "white"],
        "lighting_tags": ["surgical_light", "clean_overhead", "monitor_glow"],
        "camera_tags": ["overhead_surgical", "patient_pov", "equipment_detail"],
        "atmosphere_tags": ["sterile_white", "clinical_cold", "hospital_smell"],
    },
    {
        "name": "clean_room",
        "category": ENV_CATEGORY_SCIENTIFIC,
        "description": "Controlled contamination-free environment for microelectronics or pharmaceutical production.",
        "keywords": ["clean_room", "cleanroom", "semiconductor", "wafer", "microchip", "sterile",
                     "hazmat", "suit", "airlock", "filter", "hvac", "contamination", "particle",
                     "fabrication", "silicon", "photolithography", "controlled"],
        "asset_categories": ["equipment", "structure", "electronics", "prop"],
        "hero_asset_types": ["fabrication_machine", "wafer_stepper", "clean_equipment"],
        "support_asset_types": ["filter_system", "workbench", "containment", "suit_rack"],
        "storytelling_tags": ["technological_purity", "contamination_control", "precision_fabrication"],
        "lookdev_tags": ["pristine", "white", "clean", "polished"],
        "lighting_tags": ["yellow_cleanroom", "shadowless_diffuse", "overhead_white"],
        "camera_tags": ["suit_perspective", "equipment_detail", "wide_cleanroom"],
        "atmosphere_tags": ["filtered_air", "static_free", "controlled_environment"],
    },
    {
        "name": "biohazard_facility",
        "category": ENV_CATEGORY_SCIENTIFIC,
        "description": "High-security biological research facility with containment protocols and hazard zones.",
        "keywords": ["biohazard", "containment", "bsl4", "biosafety", "hazmat", "pathogen",
                     "specimen", "culture", "airlock", "decontamination", "hood", "biosafety_cabinet",
                     "glove_box", "pressurized", "laboratory", "virus", "bacteria"],
        "asset_categories": ["equipment", "structure", "prop", "electronics"],
        "hero_asset_types": ["containment_chamber", "biosafety_cabinet", "decon_area"],
        "support_asset_types": ["hazmat_suit", "airlock_door", "warning_sign", "specimen"],
        "storytelling_tags": ["danger_containment", "scientific_risk", "hidden_threat"],
        "lookdev_tags": ["clinical", "worn", "warning_colors", "aged"],
        "lighting_tags": ["warning_red", "clinical_overhead", "emergency_glow"],
        "camera_tags": ["containment_pov", "hazard_close", "warning_sign"],
        "atmosphere_tags": ["pressurized_tension", "sterile_danger", "containment_hum"],
    },
    # -----------------------------------------------------------------------
    # MILITARY
    # -----------------------------------------------------------------------
    {
        "name": "military_base",
        "category": ENV_CATEGORY_MILITARY,
        "description": "Active military installation with barracks, vehicles, and tactical infrastructure.",
        "keywords": ["military", "base", "barracks", "soldier", "weapon", "vehicle", "tank",
                     "humvee", "helicopter", "watchtower", "perimeter", "fence", "checkpoint",
                     "drill", "parade", "armory", "tactical", "operations"],
        "asset_categories": ["vehicle", "structure", "prop", "equipment", "weapon"],
        "hero_asset_types": ["military_vehicle", "watchtower", "armored_transport"],
        "support_asset_types": ["barrier", "sandbag", "weapon_rack", "antenna"],
        "storytelling_tags": ["military_order", "tactical_readiness", "disciplined_force"],
        "lookdev_tags": ["industrial", "worn", "weathered", "camouflage"],
        "lighting_tags": ["harsh_exterior", "floodlight_night", "desert_noon"],
        "camera_tags": ["patrol_perspective", "vehicle_scale", "base_establishing"],
        "atmosphere_tags": ["dust_desert", "military_haze", "tension_atmosphere"],
    },
    {
        "name": "command_center",
        "category": ENV_CATEGORY_MILITARY,
        "description": "Military tactical command hub with communications arrays and strategic displays.",
        "keywords": ["command", "center", "tactical", "map", "briefing", "general", "strategy",
                     "radio", "satellite", "communication", "display", "situation_room",
                     "operations", "intel", "mission", "briefing_table"],
        "asset_categories": ["electronics", "furniture", "prop", "equipment"],
        "hero_asset_types": ["tactical_table", "situation_display", "communication_array"],
        "support_asset_types": ["map", "radio", "chair", "monitor"],
        "storytelling_tags": ["command_authority", "strategic_decision", "military_intelligence"],
        "lookdev_tags": ["industrial", "technical", "clean", "worn"],
        "lighting_tags": ["low_key_dramatic", "screen_glow", "map_light"],
        "camera_tags": ["table_overview", "commander_perspective", "strategic_wide"],
        "atmosphere_tags": ["tension_atmosphere", "cool_blue", "command_gravity"],
    },
    {
        "name": "military_hangar",
        "category": ENV_CATEGORY_MILITARY,
        "description": "Military aircraft hangar with fighter jets, maintenance equipment, and flight crew.",
        "keywords": ["military", "hangar", "aircraft", "fighter", "jet", "helicopter", "maintenance",
                     "runway", "tarmac", "pilot", "wing", "engine", "fuel", "armament",
                     "airforce", "bomber", "carrier"],
        "asset_categories": ["vehicle", "structure", "prop", "equipment"],
        "hero_asset_types": ["fighter_jet", "military_helicopter", "aircraft_carrier"],
        "support_asset_types": ["maintenance_rig", "fuel_cart", "tool_cabinet", "ladder"],
        "storytelling_tags": ["military_power", "aerial_readiness", "technological_force"],
        "lookdev_tags": ["industrial", "worn", "technical", "camouflage"],
        "lighting_tags": ["hangar_overhead", "aircraft_silhouette", "night_tarmac"],
        "camera_tags": ["aircraft_scale", "hangar_wide", "maintenance_detail"],
        "atmosphere_tags": ["jet_exhaust", "hangar_echo", "military_precision"],
    },
    {
        "name": "checkpoint",
        "category": ENV_CATEGORY_MILITARY,
        "description": "Military or border checkpoint with barriers, inspection equipment, and guard posts.",
        "keywords": ["checkpoint", "barrier", "guard", "patrol", "gate", "security", "inspection",
                     "booth", "bollard", "fence", "wire", "identification", "border", "military",
                     "stop", "crossing"],
        "asset_categories": ["structure", "prop", "vehicle", "equipment"],
        "hero_asset_types": ["guard_booth", "barrier_gate", "security_post"],
        "support_asset_types": ["bollard", "wire_fence", "patrol_vehicle", "light"],
        "storytelling_tags": ["controlled_access", "authority_boundary", "tension_crossing"],
        "lookdev_tags": ["industrial", "weathered", "worn", "gritty"],
        "lighting_tags": ["searchlight", "warning_amber", "night_flood"],
        "camera_tags": ["barrier_approach", "guard_pov", "tension_close"],
        "atmosphere_tags": ["tension_haze", "searchlight_beam", "night_dust"],
    },
    {
        "name": "bunker",
        "category": ENV_CATEGORY_MILITARY,
        "description": "Underground military fortification with reinforced walls and emergency provisions.",
        "keywords": ["bunker", "underground", "concrete", "reinforced", "blast_door", "shelter",
                     "emergency", "generator", "supplies", "command", "war_room", "fortification",
                     "military", "vault", "tunnel", "corridor", "defense"],
        "asset_categories": ["structure", "prop", "electronics", "equipment", "furniture"],
        "hero_asset_types": ["blast_door", "command_table", "bunker_entrance"],
        "support_asset_types": ["supply_crate", "generator", "bunk_bed", "communication_equipment"],
        "storytelling_tags": ["survival_shelter", "last_resort", "underground_fortress"],
        "lookdev_tags": ["industrial", "aged", "worn", "gritty"],
        "lighting_tags": ["emergency_red", "bare_bulb", "generator_flicker"],
        "camera_tags": ["claustrophobic_tight", "tunnel_depth", "bunker_establishing"],
        "atmosphere_tags": ["underground_damp", "emergency_tension", "concrete_echo"],
    },
    # -----------------------------------------------------------------------
    # SCI-FI
    # -----------------------------------------------------------------------
    {
        "name": "sci_fi_corridor",
        "category": ENV_CATEGORY_SCI_FI,
        "description": "Futuristic spacecraft or station corridor with neon lighting and modular panels.",
        "keywords": ["corridor", "door", "airlock", "hatch", "vent", "grate", "bulkhead", "module",
                     "pod", "terminal", "conduit", "cable", "lamp", "hallway", "passage",
                     "tunnel", "shaft", "floor", "wall", "ceiling"],
        "asset_categories": ["structure", "electronics", "prop", "equipment"],
        "hero_asset_types": ["corridor_section", "bulkhead_door", "airlock"],
        "support_asset_types": ["wall_panel", "conduit", "terminal", "vent"],
        "storytelling_tags": ["journey_through", "technological_world", "spatial_rhythm"],
        "lookdev_tags": ["sci_fi", "clean", "technical", "polished"],
        "lighting_tags": ["neon_strip", "volumetric_corridor", "strong_rim"],
        "camera_tags": ["forced_perspective", "corridor_depth", "dutch_tilt"],
        "atmosphere_tags": ["neon_glow", "thin_haze", "deep_space_cold"],
    },
    {
        "name": "space_station",
        "category": ENV_CATEGORY_SCI_FI,
        "description": "Orbital space station with pressurized modules, airlocks, and Earth views.",
        "keywords": ["space", "station", "orbital", "module", "airlock", "panel", "terminal",
                     "satellite", "astronaut", "zero_gravity", "earth", "solar_panel",
                     "docking", "habitat", "science", "microgravity"],
        "asset_categories": ["structure", "electronics", "prop", "equipment"],
        "hero_asset_types": ["station_module", "docking_port", "observation_window"],
        "support_asset_types": ["solar_panel", "equipment_rack", "terminal", "cable"],
        "storytelling_tags": ["isolation", "humanity_in_space", "orbital_perspective"],
        "lookdev_tags": ["clean", "sci_fi", "technical", "polished"],
        "lighting_tags": ["earth_bounce", "panel_practical", "cool_space"],
        "camera_tags": ["earth_backdrop", "module_interior", "zero_g_perspective"],
        "atmosphere_tags": ["space_silence", "orbital_light", "isolation_cool"],
    },
    {
        "name": "spaceship_bridge",
        "category": ENV_CATEGORY_SCI_FI,
        "description": "Starship command bridge with navigation consoles, viewscreens, and captain's chair.",
        "keywords": ["bridge", "spaceship", "captain", "helm", "navigation", "viewscreen", "console",
                     "star", "warp", "galaxy", "crew", "tactical", "scanner", "command",
                     "flight_deck", "pilot", "star_field"],
        "asset_categories": ["electronics", "furniture", "structure", "prop"],
        "hero_asset_types": ["captain_chair", "navigation_console", "viewscreen"],
        "support_asset_types": ["crew_station", "holographic_display", "control_panel"],
        "storytelling_tags": ["command_at_frontier", "exploration_leadership", "crew_unity"],
        "lookdev_tags": ["sci_fi", "clean", "technical", "polished"],
        "lighting_tags": ["star_field_glow", "console_practical", "cool_blue"],
        "camera_tags": ["captain_profile", "screen_pov", "bridge_establishing"],
        "atmosphere_tags": ["star_field", "deep_space", "command_glow"],
    },
    {
        "name": "engineering_bay",
        "category": ENV_CATEGORY_SCI_FI,
        "description": "Spacecraft engineering section with power cores, conduits, and maintenance platforms.",
        "keywords": ["engineering", "bay", "engine", "power_core", "reactor", "conduit", "plasma",
                     "coolant", "turbine", "maintenance", "tech", "power", "fuel", "core",
                     "warp_core", "thruster", "mechanical"],
        "asset_categories": ["machinery", "structure", "prop", "electronics", "equipment"],
        "hero_asset_types": ["power_core", "engine_assembly", "reactor"],
        "support_asset_types": ["conduit", "maintenance_platform", "gauge", "coolant_pipe"],
        "storytelling_tags": ["technological_heart", "power_source", "engineering_tension"],
        "lookdev_tags": ["industrial", "sci_fi", "worn", "gritty"],
        "lighting_tags": ["core_glow", "emergency_amber", "volumetric_plasma"],
        "camera_tags": ["core_reveal", "engineering_scale", "maintenance_pov"],
        "atmosphere_tags": ["heat_shimmer", "plasma_glow", "engine_rumble"],
    },
    {
        "name": "alien_facility",
        "category": ENV_CATEGORY_SCI_FI,
        "description": "Extraterrestrial structure with non-human architecture, bioluminescent elements, and alien materials.",
        "keywords": ["alien", "extraterrestrial", "organic", "bioluminescent", "xenomorph", "hive",
                     "colony", "biomechanical", "crystalline", "otherworldly", "tentacle",
                     "spore", "resin", "carapace", "strange", "unknown"],
        "asset_categories": ["structure", "prop", "vegetation", "creature"],
        "hero_asset_types": ["alien_structure", "bioluminescent_growth", "alien_artifact"],
        "support_asset_types": ["organic_wall", "crystal_growth", "alien_pod", "resin"],
        "storytelling_tags": ["first_contact", "unknown_horror", "alien_beauty"],
        "lookdev_tags": ["sci_fi", "aged", "damaged", "weathered"],
        "lighting_tags": ["bioluminescent", "eerie_cool", "alien_glow"],
        "camera_tags": ["alien_scale", "horror_reveal", "explorer_pov"],
        "atmosphere_tags": ["bioluminescent_mist", "alien_atmosphere", "eerie_silence"],
    },
    {
        "name": "cyberpunk_city",
        "category": ENV_CATEGORY_SCI_FI,
        "description": "Dense futuristic urban environment with neon signs, rain-slicked streets, and corporate megastructures.",
        "keywords": ["cyberpunk", "neon", "city", "urban", "rain", "hologram", "corporate",
                     "megastructure", "advertisement", "street", "night", "hacker", "drone",
                     "implant", "dystopia", "overcrowded", "market"],
        "asset_categories": ["architecture", "electronics", "vehicle", "prop", "structure"],
        "hero_asset_types": ["megastructure", "neon_signage", "flying_vehicle"],
        "support_asset_types": ["street_vendor", "hologram_ad", "rain_slick_road", "wires"],
        "storytelling_tags": ["dystopian_society", "corporate_oppression", "neon_survival"],
        "lookdev_tags": ["sci_fi", "worn", "gritty", "industrial"],
        "lighting_tags": ["neon_rain", "city_glow", "flying_vehicle_light"],
        "camera_tags": ["street_level", "rain_reflection", "neon_bokeh"],
        "atmosphere_tags": ["neon_rain", "city_haze", "night_crowd"],
    },
    # -----------------------------------------------------------------------
    # URBAN
    # -----------------------------------------------------------------------
    {
        "name": "city_street",
        "category": ENV_CATEGORY_URBAN,
        "description": "Modern urban street with traffic, pedestrians, storefronts, and city infrastructure.",
        "keywords": ["city", "street", "urban", "traffic", "pedestrian", "sidewalk", "road",
                     "building", "store", "car", "bus", "traffic_light", "sign", "pavement",
                     "crosswalk", "downtown", "avenue"],
        "asset_categories": ["vehicle", "architecture", "prop", "character", "street_furniture"],
        "hero_asset_types": ["street_scene", "vehicle", "building_facade"],
        "support_asset_types": ["street_sign", "bench", "trash_can", "fire_hydrant"],
        "storytelling_tags": ["urban_life", "city_rhythm", "public_space"],
        "lookdev_tags": ["worn", "weathered", "industrial", "aged"],
        "lighting_tags": ["street_lamp", "golden_hour", "overcast_city"],
        "camera_tags": ["street_level", "traffic_pov", "wide_urban"],
        "atmosphere_tags": ["city_smog", "street_rain", "urban_haze"],
    },
    {
        "name": "alleyway",
        "category": ENV_CATEGORY_URBAN,
        "description": "Narrow urban alley with dumpsters, fire escapes, and ambient street character.",
        "keywords": ["alley", "alleyway", "narrow", "dumpster", "garbage", "fire_escape", "graffiti",
                     "brick", "shadows", "urban", "back_street", "pipe", "drain", "puddle",
                     "neon_spill", "back_door"],
        "asset_categories": ["structure", "prop", "architecture"],
        "hero_asset_types": ["dumpster", "fire_escape", "alley_entrance"],
        "support_asset_types": ["trash_bag", "brick_wall", "drainpipe", "graffiti"],
        "storytelling_tags": ["hidden_world", "urban_underbelly", "secret_meeting"],
        "lookdev_tags": ["worn", "gritty", "weathered", "aged"],
        "lighting_tags": ["spill_light", "shadow_alley", "neon_bounce"],
        "camera_tags": ["tight_alley", "escape_route", "shadow_reveal"],
        "atmosphere_tags": ["rain_puddle", "city_smell", "shadow_depth"],
    },
    {
        "name": "subway_station",
        "category": ENV_CATEGORY_URBAN,
        "description": "Underground transit station with platforms, tunnels, and commuter infrastructure.",
        "keywords": ["subway", "metro", "station", "platform", "train", "tunnel", "track", "commuter",
                     "escalator", "turnstile", "poster", "tile", "pillar", "rail", "departure",
                     "underground", "transit"],
        "asset_categories": ["structure", "electronics", "prop", "vehicle", "furniture"],
        "hero_asset_types": ["subway_train", "platform_edge", "tunnel_entrance"],
        "support_asset_types": ["signage", "pillar", "bench", "turnstile"],
        "storytelling_tags": ["urban_transit", "commuter_life", "underground_world"],
        "lookdev_tags": ["worn", "aged", "industrial", "gritty"],
        "lighting_tags": ["fluorescent_flicker", "platform_flood", "tunnel_dark"],
        "camera_tags": ["platform_length", "train_arrival", "tunnel_depth"],
        "atmosphere_tags": ["subway_wind", "brake_smell", "underground_echo"],
    },
    {
        "name": "parking_garage",
        "category": ENV_CATEGORY_URBAN,
        "description": "Multi-level vehicle parking structure with low ceilings and minimal lighting.",
        "keywords": ["parking", "garage", "concrete", "column", "car", "vehicle", "ramp", "low_ceiling",
                     "fluorescent", "painted_line", "level", "floor", "exit", "sign",
                     "surveillance", "stairwell"],
        "asset_categories": ["vehicle", "structure", "prop"],
        "hero_asset_types": ["parked_vehicle", "column_row", "ramp_entry"],
        "support_asset_types": ["painted_marking", "sign", "column", "barrier"],
        "storytelling_tags": ["isolation", "hidden_meeting", "urban_underbelly"],
        "lookdev_tags": ["industrial", "worn", "gritty", "aged"],
        "lighting_tags": ["harsh_fluorescent", "headlight_practical", "deep_shadow"],
        "camera_tags": ["parking_level", "car_hide", "column_depth"],
        "atmosphere_tags": ["concrete_echo", "oil_smell", "isolation_haze"],
    },
    {
        "name": "rooftop",
        "category": ENV_CATEGORY_URBAN,
        "description": "Urban rooftop with skyline views, HVAC equipment, and open sky.",
        "keywords": ["rooftop", "roof", "skyline", "hvac", "vent", "antenna", "water_tower",
                     "city", "urban", "open_air", "parapet", "satellite_dish", "evening",
                     "ledge", "view", "chimney"],
        "asset_categories": ["structure", "equipment", "prop", "architecture"],
        "hero_asset_types": ["city_skyline", "water_tower", "rooftop_equipment"],
        "support_asset_types": ["hvac_unit", "antenna", "vent", "parapet"],
        "storytelling_tags": ["perspective_above", "urban_escape", "sky_meeting"],
        "lookdev_tags": ["weathered", "industrial", "worn"],
        "lighting_tags": ["golden_hour_sky", "city_glow_night", "moonlit_rooftop"],
        "camera_tags": ["skyline_wide", "edge_drama", "city_reflections"],
        "atmosphere_tags": ["sky_atmosphere", "city_smog_horizon", "wind_open"],
    },
    {
        "name": "shopping_mall",
        "category": ENV_CATEGORY_URBAN,
        "description": "Large commercial retail complex with storefronts, food courts, and atrium architecture.",
        "keywords": ["mall", "shopping", "retail", "store", "escalator", "atrium", "skylight",
                     "food_court", "brand", "consumer", "crowd", "advertisement", "shop",
                     "window", "sale", "commercial"],
        "asset_categories": ["furniture", "electronics", "prop", "architecture", "character"],
        "hero_asset_types": ["atrium", "store_display", "escalator"],
        "support_asset_types": ["bench", "signage", "trash_bin", "plant"],
        "storytelling_tags": ["consumer_culture", "public_gathering", "commercial_world"],
        "lookdev_tags": ["clean", "polished", "commercial"],
        "lighting_tags": ["skylight_natural", "retail_warm", "atrium_flood"],
        "camera_tags": ["atrium_wide", "escalator_perspective", "store_level"],
        "atmosphere_tags": ["crowd_buzz", "retail_air", "commercial_glow"],
    },
    # -----------------------------------------------------------------------
    # INTERIOR
    # -----------------------------------------------------------------------
    {
        "name": "western_room",
        "category": ENV_CATEGORY_INTERIOR,
        "description": "19th-century American West interior with wooden furniture, lanterns, and period-authentic props.",
        "keywords": ["wood", "barrel", "crate", "lantern", "whiskey", "saloon", "wagon", "rope",
                     "cowboy", "rustic", "leather", "western", "frontier", "old_west",
                     "floorboard", "plank", "oil_lamp", "hat"],
        "asset_categories": ["furniture", "prop", "vehicle"],
        "hero_asset_types": ["wooden_table", "bar_counter", "fireplace"],
        "support_asset_types": ["barrel", "lantern", "crate", "chair"],
        "storytelling_tags": ["frontier_life", "western_drama", "period_authenticity"],
        "lookdev_tags": ["worn", "weathered", "aged", "rustic"],
        "lighting_tags": ["warm_lantern", "firelight", "window_shaft"],
        "camera_tags": ["saloon_wide", "character_profile", "bar_level"],
        "atmosphere_tags": ["warm_amber", "wood_smoke", "dusty_frontier"],
    },
    {
        "name": "saloon",
        "category": ENV_CATEGORY_INTERIOR,
        "description": "Western frontier drinking establishment with bar, piano, gaming tables, and swinging doors.",
        "keywords": ["saloon", "bar", "piano", "whiskey", "bottle", "glass", "western", "cowboy",
                     "poker", "card", "table", "swinging_door", "staircase", "balcony",
                     "bartender", "dusty", "frontier"],
        "asset_categories": ["furniture", "prop", "equipment"],
        "hero_asset_types": ["bar_counter", "piano", "poker_table"],
        "support_asset_types": ["whiskey_bottle", "glass", "chair", "swinging_door"],
        "storytelling_tags": ["frontier_gathering", "confrontation_stage", "social_hub"],
        "lookdev_tags": ["worn", "weathered", "aged", "rustic"],
        "lighting_tags": ["kerosene_warm", "practical_lanterns", "window_daylight"],
        "camera_tags": ["swinging_door_reveal", "bar_profile", "wide_saloon"],
        "atmosphere_tags": ["warm_amber", "sawdust", "whiskey_haze"],
    },
    {
        "name": "living_room",
        "category": ENV_CATEGORY_INTERIOR,
        "description": "Domestic residential living space with seating, entertainment, and personal decor.",
        "keywords": ["living_room", "sofa", "couch", "tv", "coffee_table", "lamp", "rug", "bookshelf",
                     "cushion", "fireplace", "window", "curtain", "plant", "home", "domestic",
                     "comfortable", "family"],
        "asset_categories": ["furniture", "electronics", "prop", "decoration"],
        "hero_asset_types": ["sofa", "television", "fireplace"],
        "support_asset_types": ["coffee_table", "lamp", "bookshelf", "cushion"],
        "storytelling_tags": ["domestic_life", "family_connection", "personal_space"],
        "lookdev_tags": ["clean", "worn", "comfortable"],
        "lighting_tags": ["warm_ambient", "practical_lamp", "window_natural"],
        "camera_tags": ["living_wide", "fireplace_glow", "family_pov"],
        "atmosphere_tags": ["warm_home", "cozy_light", "domestic_quiet"],
    },
    {
        "name": "office",
        "category": ENV_CATEGORY_INTERIOR,
        "description": "Corporate or professional workspace with desks, computers, and business infrastructure.",
        "keywords": ["office", "desk", "computer", "monitor", "chair", "cubicle", "conference",
                     "meeting_room", "whiteboard", "printer", "phone", "document",
                     "corporate", "professional", "workspace", "employee"],
        "asset_categories": ["furniture", "electronics", "prop"],
        "hero_asset_types": ["executive_desk", "conference_table", "workstation"],
        "support_asset_types": ["monitor", "chair", "printer", "whiteboard"],
        "storytelling_tags": ["corporate_world", "professional_pursuit", "workplace_tension"],
        "lookdev_tags": ["clean", "clinical", "polished"],
        "lighting_tags": ["fluorescent_corporate", "window_natural", "desk_practical"],
        "camera_tags": ["corporate_wide", "desk_level", "window_view"],
        "atmosphere_tags": ["air_conditioning", "corporate_neutral", "fluorescent_cool"],
    },
    {
        "name": "hotel_lobby",
        "category": ENV_CATEGORY_INTERIOR,
        "description": "Upscale hotel entrance with reception, lounge seating, and grand architecture.",
        "keywords": ["hotel", "lobby", "reception", "concierge", "lounge", "chandelier", "marble",
                     "elevator", "luggage", "check_in", "fountain", "luxury", "grand",
                     "guest", "bellhop", "entrance"],
        "asset_categories": ["furniture", "architecture", "decoration", "prop"],
        "hero_asset_types": ["reception_desk", "grand_chandelier", "lobby_seating"],
        "support_asset_types": ["luggage_cart", "plant", "marble_floor", "elevator"],
        "storytelling_tags": ["luxury_arrival", "transient_gathering", "first_impression"],
        "lookdev_tags": ["polished", "clean", "pristine"],
        "lighting_tags": ["chandelier_warm", "lobby_ambient", "grand_presence"],
        "camera_tags": ["grand_entrance", "lobby_wide", "reception_level"],
        "atmosphere_tags": ["luxury_warm", "fresh_flowers", "grand_echo"],
    },
    {
        "name": "restaurant",
        "category": ENV_CATEGORY_INTERIOR,
        "description": "Dining establishment ranging from casual to fine dining with tables, kitchen, and ambiance.",
        "keywords": ["restaurant", "dining", "table", "chair", "kitchen", "menu", "wine", "candle",
                     "waiter", "food", "plate", "glass", "tablecloth", "reservation",
                     "ambiance", "bar", "open_kitchen"],
        "asset_categories": ["furniture", "prop", "decoration", "equipment"],
        "hero_asset_types": ["dining_table", "open_kitchen", "bar_seating"],
        "support_asset_types": ["candle", "wine_bottle", "chair", "tablecloth"],
        "storytelling_tags": ["social_dining", "romantic_setting", "culinary_world"],
        "lookdev_tags": ["polished", "warm", "clean"],
        "lighting_tags": ["candle_practical", "pendant_warm", "ambient_dining"],
        "camera_tags": ["table_level", "kitchen_window", "dining_wide"],
        "atmosphere_tags": ["warm_dining", "food_aroma", "social_hum"],
    },
    {
        "name": "workshop",
        "category": ENV_CATEGORY_INTERIOR,
        "description": "Artisan or mechanical workshop with tools, workbenches, and active craft or repair work.",
        "keywords": ["workshop", "tool", "bench", "workbench", "hammer", "wrench", "drill", "lathe",
                     "vice", "saw", "grinder", "blueprint", "repair", "craft", "wood",
                     "metal", "fabrication", "maker"],
        "asset_categories": ["equipment", "tool", "prop", "furniture"],
        "hero_asset_types": ["workbench", "power_tool", "lathe"],
        "support_asset_types": ["tool_rack", "vice", "blueprint", "material_stock"],
        "storytelling_tags": ["craft_mastery", "making_world", "skilled_hands"],
        "lookdev_tags": ["worn", "industrial", "aged", "gritty"],
        "lighting_tags": ["task_lamp", "warm_workshop", "window_natural"],
        "camera_tags": ["workbench_level", "tool_detail", "workshop_wide"],
        "atmosphere_tags": ["sawdust", "oil_smell", "craft_warmth"],
    },
    {
        "name": "library",
        "category": ENV_CATEGORY_INTERIOR,
        "description": "Repository of books with shelving systems, reading areas, and quiet scholarly atmosphere.",
        "keywords": ["library", "book", "shelf", "bookcase", "reading", "table", "lamp", "study",
                     "knowledge", "archive", "scroll", "tome", "quiet", "scholar", "document",
                     "catalog", "staircase"],
        "asset_categories": ["furniture", "prop", "decoration", "architecture"],
        "hero_asset_types": ["bookshelf_wall", "reading_table", "rare_book"],
        "support_asset_types": ["lamp", "chair", "catalog_cabinet", "ladder"],
        "storytelling_tags": ["accumulated_knowledge", "scholarly_pursuit", "quiet_discovery"],
        "lookdev_tags": ["aged", "worn", "warm", "pristine"],
        "lighting_tags": ["reading_lamp", "window_daylight", "warm_scholarly"],
        "camera_tags": ["shelf_depth", "reading_level", "library_wide"],
        "atmosphere_tags": ["old_paper", "quiet_dust", "knowledge_warmth"],
    },
    # -----------------------------------------------------------------------
    # NATURE
    # -----------------------------------------------------------------------
    {
        "name": "forest",
        "category": ENV_CATEGORY_NATURE,
        "description": "Temperate woodland with tall trees, undergrowth, and filtered sunlight.",
        "keywords": ["tree", "foliage", "nature", "leaf", "moss", "woodland", "branch", "vegetation",
                     "forest", "trunk", "bark", "root", "undergrowth", "fern", "mushroom",
                     "dappled_light", "canopy", "trail"],
        "asset_categories": ["vegetation", "terrain", "prop", "creature"],
        "hero_asset_types": ["ancient_tree", "forest_canopy", "tree_root"],
        "support_asset_types": ["fern", "mushroom", "log", "moss_covered_rock"],
        "storytelling_tags": ["nature_immersion", "wilderness_journey", "ancient_life"],
        "lookdev_tags": ["weathered", "aged", "pristine"],
        "lighting_tags": ["dappled_sunlight", "forest_shade", "volumetric_shafts"],
        "camera_tags": ["canopy_upward", "forest_depth", "trail_perspective"],
        "atmosphere_tags": ["forest_mist", "pollen_drift", "dappled_light"],
    },
    {
        "name": "jungle",
        "category": ENV_CATEGORY_NATURE,
        "description": "Dense tropical rainforest with lush vegetation, vines, and high humidity.",
        "keywords": ["jungle", "tropical", "rainforest", "vine", "palm", "exotic", "dense",
                     "humidity", "canopy", "liana", "banana", "orchid", "river", "waterfall",
                     "creature", "insect", "growth"],
        "asset_categories": ["vegetation", "terrain", "creature", "prop"],
        "hero_asset_types": ["jungle_canopy", "waterfall", "giant_tree"],
        "support_asset_types": ["vine", "fern", "exotic_flower", "fallen_log"],
        "storytelling_tags": ["primal_nature", "survival_exploration", "ancient_wildness"],
        "lookdev_tags": ["pristine", "weathered", "aged"],
        "lighting_tags": ["tropical_diffuse", "canopy_filter", "waterfall_spray"],
        "camera_tags": ["canopy_break", "jungle_depth", "discovery_pov"],
        "atmosphere_tags": ["tropical_humidity", "jungle_mist", "dense_green"],
    },
    {
        "name": "desert",
        "category": ENV_CATEGORY_NATURE,
        "description": "Arid desert landscape with sand dunes, rock formations, and extreme exposure.",
        "keywords": ["desert", "sand", "dune", "arid", "sun", "heat", "rock", "cactus",
                     "mirrage", "dry", "wind", "dust", "oasis", "canyon", "mesa",
                     "horizon", "bleached"],
        "asset_categories": ["terrain", "vegetation", "prop"],
        "hero_asset_types": ["dune_formation", "rock_arch", "desert_mesa"],
        "support_asset_types": ["cactus", "tumble_weed", "sand_ripple", "rock"],
        "storytelling_tags": ["isolation", "survival", "elemental_harshness"],
        "lookdev_tags": ["weathered", "bleached", "worn", "aged"],
        "lighting_tags": ["harsh_noon_sun", "golden_dusk", "moonlit_desert"],
        "camera_tags": ["dune_scale", "horizon_line", "heat_shimmer"],
        "atmosphere_tags": ["heat_haze", "dust_wind", "bleached_atmosphere"],
    },
    {
        "name": "canyon",
        "category": ENV_CATEGORY_NATURE,
        "description": "Deep geological canyon with layered rock walls, river, and dramatic scale.",
        "keywords": ["canyon", "rock", "cliff", "geological", "layer", "river", "gorge", "erosion",
                     "mesa", "red_rock", "trail", "scale", "depth", "sandstone",
                     "outcrop", "overhang"],
        "asset_categories": ["terrain", "vegetation", "prop"],
        "hero_asset_types": ["canyon_wall", "rock_formation", "river_below"],
        "support_asset_types": ["rock_layer", "sparse_vegetation", "river_stone"],
        "storytelling_tags": ["geological_time", "epic_scale", "nature_carved"],
        "lookdev_tags": ["weathered", "aged", "bleached", "worn"],
        "lighting_tags": ["canyon_shadow", "red_rock_sunset", "shaft_through_gap"],
        "camera_tags": ["scale_from_base", "rim_overview", "canyon_depth"],
        "atmosphere_tags": ["red_dust", "canyon_wind", "geological_haze"],
    },
    {
        "name": "mountain",
        "category": ENV_CATEGORY_NATURE,
        "description": "Alpine or high-altitude environment with rocky peaks, snow, and vast vistas.",
        "keywords": ["mountain", "alpine", "peak", "summit", "snow", "rock", "glacier", "cliff",
                     "altitude", "summit", "ridge", "valley", "cloud", "vista",
                     "boulder", "trail", "winter"],
        "asset_categories": ["terrain", "vegetation", "prop"],
        "hero_asset_types": ["mountain_peak", "rock_face", "glacier"],
        "support_asset_types": ["boulder", "alpine_plant", "snow_drift", "cloud"],
        "storytelling_tags": ["triumph_over_nature", "epic_journey", "alpine_solitude"],
        "lookdev_tags": ["pristine", "weathered", "bleached"],
        "lighting_tags": ["alpine_sun", "cloud_shadow", "sunset_mountain"],
        "camera_tags": ["peak_reveal", "valley_panorama", "climber_pov"],
        "atmosphere_tags": ["thin_air", "cloud_wrap", "alpine_crisp"],
    },
    {
        "name": "coastline",
        "category": ENV_CATEGORY_NATURE,
        "description": "Ocean shoreline with waves, cliffs, tidal pools, and maritime atmosphere.",
        "keywords": ["coast", "beach", "ocean", "wave", "cliff", "shore", "sea", "sand",
                     "rock_pool", "lighthouse", "pier", "fishing", "sea_grass",
                     "foam", "tide", "spray", "horizon"],
        "asset_categories": ["terrain", "prop", "vegetation", "structure"],
        "hero_asset_types": ["sea_cliff", "lighthouse", "wave_formation"],
        "support_asset_types": ["rock_pool", "sea_grass", "pier_post", "boat"],
        "storytelling_tags": ["boundary_of_worlds", "maritime_solitude", "elemental_meeting"],
        "lookdev_tags": ["weathered", "worn", "pristine"],
        "lighting_tags": ["sea_light_bounce", "golden_coastal", "overcast_grey"],
        "camera_tags": ["shore_level", "cliff_overview", "ocean_horizon"],
        "atmosphere_tags": ["sea_spray", "ocean_mist", "coastal_wind"],
    },
    {
        "name": "swamp",
        "category": ENV_CATEGORY_NATURE,
        "description": "Wetland environment with standing water, cypress trees, Spanish moss, and murky atmosphere.",
        "keywords": ["swamp", "bayou", "marsh", "wetland", "cypress", "moss", "murky", "water",
                     "fog", "reed", "mangrove", "alligator", "decay", "rotting",
                     "reflection", "dark_water", "mosquito"],
        "asset_categories": ["vegetation", "terrain", "creature", "prop"],
        "hero_asset_types": ["cypress_tree", "murky_water", "swamp_habitat"],
        "support_asset_types": ["spanish_moss", "reed", "mangrove_root", "log"],
        "storytelling_tags": ["dark_mystery", "primal_danger", "hidden_world"],
        "lookdev_tags": ["aged", "weathered", "damaged", "worn"],
        "lighting_tags": ["swamp_diffuse", "fog_filtered", "murky_green"],
        "camera_tags": ["water_level", "fog_depth", "swamp_atmosphere"],
        "atmosphere_tags": ["swamp_fog", "murky_green", "decay_smell"],
    },
    # -----------------------------------------------------------------------
    # FANTASY
    # -----------------------------------------------------------------------
    {
        "name": "castle_hall",
        "category": ENV_CATEGORY_FANTASY,
        "description": "Grand medieval castle interior with stone walls, tapestries, and throne room grandeur.",
        "keywords": ["castle", "hall", "throne", "stone", "medieval", "tapestry", "banner",
                     "column", "stained_glass", "torch", "arched", "knight", "royal",
                     "heraldry", "dungeon_stair", "great_hall"],
        "asset_categories": ["furniture", "architecture", "prop", "decoration"],
        "hero_asset_types": ["throne", "great_fireplace", "stone_arch"],
        "support_asset_types": ["tapestry", "banner", "torch", "column"],
        "storytelling_tags": ["royal_power", "medieval_grandeur", "historic_majesty"],
        "lookdev_tags": ["aged", "weathered", "worn", "pristine"],
        "lighting_tags": ["torch_flicker", "stained_glass_color", "grand_candle"],
        "camera_tags": ["throne_reveal", "hall_perspective", "column_depth"],
        "atmosphere_tags": ["stone_cold", "torch_smoke", "medieval_echo"],
    },
    {
        "name": "dungeon",
        "category": ENV_CATEGORY_FANTASY,
        "description": "Dark underground prison or monster lair with cells, chains, and oppressive stone architecture.",
        "keywords": ["dungeon", "prison", "cell", "chain", "torch", "dark", "damp", "stone",
                     "medieval", "torture", "skeleton", "rat", "door", "lock",
                     "corridor", "underground", "monster"],
        "asset_categories": ["structure", "prop", "architecture"],
        "hero_asset_types": ["prison_cell", "torture_device", "dungeon_corridor"],
        "support_asset_types": ["chain", "torch", "skeleton", "iron_door"],
        "storytelling_tags": ["captivity", "dark_consequences", "underground_horror"],
        "lookdev_tags": ["aged", "worn", "damaged", "gritty"],
        "lighting_tags": ["torch_single", "deep_shadow", "horror_side_light"],
        "camera_tags": ["cell_bars_pov", "corridor_depth", "claustrophobic_tight"],
        "atmosphere_tags": ["dungeon_damp", "torch_flicker", "stone_darkness"],
    },
    {
        "name": "wizard_tower",
        "category": ENV_CATEGORY_FANTASY,
        "description": "Arcane mage tower filled with spell books, alchemical apparatus, floating artifacts, and magical light.",
        "keywords": ["wizard", "mage", "tower", "spell", "potion", "alchemy", "arcane", "magic",
                     "book", "tome", "crystal", "orb", "staff", "scroll", "rune",
                     "floating", "mystical", "laboratory"],
        "asset_categories": ["prop", "decoration", "furniture", "architecture"],
        "hero_asset_types": ["magical_apparatus", "spell_book", "crystal_orb"],
        "support_asset_types": ["potion_bottle", "scroll", "candle", "rune_stone"],
        "storytelling_tags": ["arcane_knowledge", "magical_discovery", "mystical_study"],
        "lookdev_tags": ["aged", "pristine", "worn"],
        "lighting_tags": ["magical_glow", "candle_warm", "arcane_blue"],
        "camera_tags": ["spiral_staircase", "artifact_detail", "magical_wide"],
        "atmosphere_tags": ["magical_mist", "arcane_glow", "mystical_particles"],
    },
    {
        "name": "ancient_ruins",
        "category": ENV_CATEGORY_FANTASY,
        "description": "Crumbling civilization remnants with overgrown stone, broken columns, and lost grandeur.",
        "keywords": ["ruin", "ancient", "stone", "column", "broken", "overgrown", "moss", "vine",
                     "civilization", "lost", "temple", "archaeological", "inscription",
                     "statue", "collapsed", "weathered", "forgotten"],
        "asset_categories": ["architecture", "terrain", "vegetation", "prop"],
        "hero_asset_types": ["broken_column", "ancient_statue", "crumbled_arch"],
        "support_asset_types": ["overgrown_stone", "vine", "inscription", "moss_block"],
        "storytelling_tags": ["lost_civilization", "archaeological_discovery", "time_passage"],
        "lookdev_tags": ["aged", "weathered", "damaged", "worn"],
        "lighting_tags": ["jungle_shaft", "archaeological_discovery", "golden_ruin"],
        "camera_tags": ["ruin_scale", "archaeological_detail", "overgrown_reveal"],
        "atmosphere_tags": ["ruin_mist", "jungle_atmosphere", "ancient_silence"],
    },
    {
        "name": "temple",
        "category": ENV_CATEGORY_FANTASY,
        "description": "Sacred religious or ceremonial space with altar, statuary, and spiritual architecture.",
        "keywords": ["temple", "shrine", "altar", "statue", "sacred", "holy", "incense", "candle",
                     "pillar", "offering", "prayer", "spiritual", "religious", "ceremonial",
                     "deity", "column", "portal"],
        "asset_categories": ["architecture", "decoration", "prop", "furniture"],
        "hero_asset_types": ["altar", "deity_statue", "sacred_flame"],
        "support_asset_types": ["incense", "candle", "offering_bowl", "pillar"],
        "storytelling_tags": ["spiritual_devotion", "sacred_space", "divine_presence"],
        "lookdev_tags": ["aged", "worn", "pristine"],
        "lighting_tags": ["candle_flicker", "shaft_divine", "sacred_glow"],
        "camera_tags": ["altar_reveal", "spiritual_wide", "devotion_close"],
        "atmosphere_tags": ["incense_smoke", "sacred_dust", "spiritual_light"],
    },
    # -----------------------------------------------------------------------
    # POST-APOCALYPTIC
    # -----------------------------------------------------------------------
    {
        "name": "abandoned_city",
        "category": ENV_CATEGORY_POST_APOCALYPTIC,
        "description": "Desolate former metropolis overtaken by nature, decay, and the remnants of civilization.",
        "keywords": ["abandoned", "city", "ruin", "collapse", "overgrown", "decay", "apocalyptic",
                     "desolate", "survivors", "empty", "street", "building", "weed",
                     "moss", "broken_window", "post_apocalyptic"],
        "asset_categories": ["architecture", "vehicle", "vegetation", "prop", "terrain"],
        "hero_asset_types": ["collapsed_building", "overgrown_street", "derelict_skyscraper"],
        "support_asset_types": ["abandoned_car", "broken_glass", "overgrowth", "debris"],
        "storytelling_tags": ["civilization_collapse", "nature_returns", "survivor_world"],
        "lookdev_tags": ["damaged", "weathered", "aged", "rusted"],
        "lighting_tags": ["overcast_apocalyptic", "shaft_through_ruin", "fire_distant"],
        "camera_tags": ["empty_street", "ruin_scale", "survivor_pov"],
        "atmosphere_tags": ["ash_haze", "decay_smell", "post_apocalyptic_grey"],
    },
    {
        "name": "destroyed_highway",
        "category": ENV_CATEGORY_POST_APOCALYPTIC,
        "description": "Cracked, overgrown highway littered with wrecked vehicles and survivor detritus.",
        "keywords": ["highway", "road", "abandoned", "car", "wreck", "cracked", "overgrown",
                     "desolate", "apocalyptic", "survivor", "debris", "pavement", "overpass",
                     "crash", "vehicle", "rusted", "broken_down"],
        "asset_categories": ["vehicle", "terrain", "prop", "architecture"],
        "hero_asset_types": ["wrecked_vehicle_pile", "cracked_overpass", "roadblock"],
        "support_asset_types": ["abandoned_car", "debris", "weed_growth", "sign"],
        "storytelling_tags": ["civilization_remnant", "last_road", "survivor_trail"],
        "lookdev_tags": ["rusted", "damaged", "weathered", "worn"],
        "lighting_tags": ["overcast_grey", "distant_fire_glow", "dust_filtered"],
        "camera_tags": ["road_length", "vehicle_wreck_close", "overpass_scale"],
        "atmosphere_tags": ["ash_drift", "dust_haze", "desolation"],
    },
    {
        "name": "ruined_industrial_site",
        "category": ENV_CATEGORY_POST_APOCALYPTIC,
        "description": "Post-collapse industrial facility with structural failure, chemical contamination signs, and decay.",
        "keywords": ["ruined", "industrial", "collapse", "contamination", "hazard", "toxic",
                     "warning", "decay", "abandoned", "structural_failure", "rust",
                     "chemical", "leak", "post_apocalyptic", "fallout"],
        "asset_categories": ["machinery", "structure", "prop", "terrain"],
        "hero_asset_types": ["collapsed_structure", "rusted_machinery", "contaminated_zone"],
        "support_asset_types": ["warning_sign", "debris", "chemical_drum", "collapsed_roof"],
        "storytelling_tags": ["industrial_apocalypse", "toxic_history", "structural_failure"],
        "lookdev_tags": ["rusted", "damaged", "weathered", "aged"],
        "lighting_tags": ["toxic_green_glow", "shaft_through_collapse", "overcast_toxic"],
        "camera_tags": ["collapse_scale", "contamination_detail", "ruin_depth"],
        "atmosphere_tags": ["toxic_haze", "chemical_fog", "industrial_ruin"],
    },
    {
        "name": "survival_camp",
        "category": ENV_CATEGORY_POST_APOCALYPTIC,
        "description": "Makeshift survivor settlement with improvised shelter, scavenged resources, and community defense.",
        "keywords": ["camp", "survival", "shelter", "makeshift", "scavenged", "fire", "tent",
                     "barricade", "supply", "community", "post_apocalyptic", "fence",
                     "watchtower", "trade", "settlement", "improvised"],
        "asset_categories": ["structure", "prop", "vehicle", "furniture", "equipment"],
        "hero_asset_types": ["campfire", "barricade_wall", "watchtower"],
        "support_asset_types": ["tent", "scavenged_supply", "improvised_shelter", "fence"],
        "storytelling_tags": ["human_resilience", "community_survival", "hope_in_ruin"],
        "lookdev_tags": ["worn", "damaged", "weathered", "gritty"],
        "lighting_tags": ["campfire_warm", "torch_practical", "overcast_grey"],
        "camera_tags": ["campfire_gather", "settlement_wide", "survivor_portrait"],
        "atmosphere_tags": ["campfire_smoke", "survival_warmth", "ash_haze"],
    },
]


# ---------------------------------------------------------------------------
# EnvironmentRegistry
# ---------------------------------------------------------------------------

class EnvironmentRegistry:
    """Central registry for all production environment definitions."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._environments: Dict[str, EnvironmentDefinition] = {}
        self._register_builtins()

    def _register_builtins(self) -> None:
        for d in _BUILTIN:
            env = EnvironmentDefinition.from_dict(d)
            self._environments[env.name] = env

    def register_environment(self, definition: EnvironmentDefinition) -> None:
        """Register or replace an environment definition. Never raises."""
        try:
            if not definition.name:
                return
            with self._lock:
                self._environments[definition.name] = definition
        except Exception:
            pass

    def get_environment(self, name: str) -> Optional[EnvironmentDefinition]:
        """Return the environment definition by name, or None if not found."""
        with self._lock:
            return self._environments.get(str(name or "").strip())

    def list_environments(self, category: str = "") -> List[str]:
        """Return sorted list of environment names, optionally filtered by category."""
        with self._lock:
            envs = list(self._environments.values())
        cat = str(category or "").strip().lower()
        if cat:
            envs = [e for e in envs if e.category == cat]
        return sorted(e.name for e in envs)

    def search_environments(self, query: str = "", category: str = "") -> List[EnvironmentDefinition]:
        """Search environments by name, keywords, or description. Never raises."""
        try:
            with self._lock:
                envs = list(self._environments.values())
            q = str(query or "").lower().strip()
            cat = str(category or "").lower().strip()
            if cat:
                envs = [e for e in envs if e.category == cat]
            if q:
                envs = [
                    e for e in envs
                    if q in e.name
                    or q in e.description.lower()
                    or any(q in kw for kw in e.keywords)
                    or q in e.category
                ]
            return sorted(envs, key=lambda e: e.name)
        except Exception:
            return []

    def get_by_category(self, category: str) -> List[EnvironmentDefinition]:
        """Return all environments for a given category."""
        with self._lock:
            return sorted(
                [e for e in self._environments.values() if e.category == str(category or "")],
                key=lambda e: e.name,
            )

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._environments)
            by_cat: Dict[str, int] = {}
            for e in self._environments.values():
                by_cat[e.category] = by_cat.get(e.category, 0) + 1
        return {"total": total, "by_category": by_cat}


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[EnvironmentRegistry] = None
_INSTANCE_LOCK = threading.Lock()


def get_environment_registry() -> EnvironmentRegistry:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = EnvironmentRegistry()
    return _INSTANCE


def reset_environment_registry_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
