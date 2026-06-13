"""
Zone Planner (Tier 7 — Scene Planning Runtime)
===============================================
Deterministically derives spatial zones (foreground / midground / background /
overhead / ground) from a SceneIntent.

Each zone carries:
  - zone_type:         spatial layer
  - description:       human-readable role
  - asset_categories:  what kinds of assets belong here
  - population:        density level
  - priority:          build priority 1–10 (10 = highest)
  - placement_hints:   per-category spatial guidance

DESIGN RULES:
  - No bridge calls.
  - No LLM calls.
  - Deterministic: same SceneIntent → same zones every time.
  - Explainable: every zone has a description.

Public API:
    ZonePlanner
        .plan_zones(intent) -> List[SceneZonePlan]
    get_zone_planner() -> ZonePlanner   (singleton)
    reset_zone_planner_for_tests()
"""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional, Tuple

from src.runtime.planning.schema.scene_plan import PlacementHint, SceneZonePlan

# ---------------------------------------------------------------------------
# Zone templates per environment
# Zone template = (zone_type, description, asset_categories, population, priority)
# ---------------------------------------------------------------------------

_ZT = Tuple[str, str, List[str], str, int]

_ENV_ZONE_TEMPLATES: Dict[str, List[_ZT]] = {
    "urban": [
        ("foreground", "Street-level debris, abandoned vehicles, and urban props",
         ["debris", "vehicle", "prop", "trash", "street_element"], "moderate", 10),
        ("midground",  "Building facades, storefronts, and urban infrastructure",
         ["building", "structure", "facade", "signage", "infrastructure"], "dense", 7),
        ("background", "City skyline, distant towers, and atmospheric silhouettes",
         ["skyline", "tower", "background_building", "billboard"], "sparse", 4),
    ],
    "industrial": [
        ("foreground", "Industrial equipment, pipes, cable runs, and floor props",
         ["machinery", "pipe", "cable", "equipment", "container"], "moderate", 10),
        ("midground",  "Processing structures, storage tanks, and facility buildings",
         ["structure", "tank", "platform", "scaffold", "facility_building"], "moderate", 7),
        ("background", "Industrial skyline, chimneys, silos, and distant facilities",
         ["silo", "chimney", "cooling_tower", "industrial_background"], "sparse", 4),
    ],
    "desert": [
        ("foreground", "Rocks, sand dunes, cacti, and wind-scattered debris",
         ["rock", "sand_dune", "vegetation_desert", "debris"], "sparse", 10),
        ("midground",  "Mesa formations, cliff walls, and sparse structures",
         ["mesa", "cliff", "sandstone_formation", "structure_ruins"], "moderate", 7),
        ("background", "Desert horizon, distant mountains, and heat haze",
         ["mountain_distant", "desert_horizon", "atmospheric_layer"], "sparse", 4),
    ],
    "forest": [
        ("foreground", "Ground cover, fallen logs, undergrowth, and forest floor props",
         ["ground_cover", "log", "bush", "mushroom", "fern"], "dense", 10),
        ("midground",  "Tree trunks, mid-height canopy, and natural structures",
         ["tree", "tree_trunk", "fallen_tree", "forest_structure"], "dense", 7),
        ("background", "Forest canopy, light shafts, and atmospheric depth",
         ["canopy", "forest_background", "atmospheric_fog_layer"], "moderate", 4),
    ],
    "ocean": [
        ("foreground", "Shoreline rocks, sea foam, debris, and coastal props",
         ["rock_coastal", "sea_foam", "debris_coastal", "drift_wood"], "moderate", 10),
        ("midground",  "Water surface, waves, and mid-distance obstacles",
         ["wave", "water_surface", "reef", "shipwreck"], "moderate", 7),
        ("background", "Ocean horizon, distant islands, and sky-water interface",
         ["ocean_horizon", "island_distant", "atmospheric_horizon"], "sparse", 4),
    ],
    "mountain": [
        ("foreground", "Rocky terrain, boulders, mountain flora, and trail elements",
         ["boulder", "rock_formation", "mountain_flora", "trail_element"], "moderate", 10),
        ("midground",  "Mountain slopes, cliff faces, and alpine structures",
         ["cliff_face", "mountain_slope", "alpine_structure", "glacier"], "moderate", 7),
        ("background", "Mountain peaks, snow caps, and sky-mountain silhouette",
         ["mountain_peak", "snow_cap", "atmospheric_mountain"], "sparse", 4),
    ],
    "arctic": [
        ("foreground", "Ice formations, snow drifts, frozen debris, and icy props",
         ["ice_formation", "snow_drift", "frozen_debris", "icicle"], "sparse", 10),
        ("midground",  "Ice shelf, frozen structures, and mid-distance glaciers",
         ["ice_shelf", "frozen_structure", "glacier_mid"], "moderate", 7),
        ("background", "Arctic horizon, aurora, and distant ice sheets",
         ["arctic_horizon", "aurora", "ice_sheet_distant"], "sparse", 4),
    ],
    "space": [
        ("foreground", "Space station modules, debris fields, and near-camera structures",
         ["space_station_module", "debris_field", "asteroid_small", "satellite"], "sparse", 10),
        ("midground",  "Large structures, ships, and orbital elements",
         ["spacecraft", "space_station_large", "orbital_platform", "asteroid_mid"], "moderate", 7),
        ("background", "Nebula, stars, distant planets, and deep space elements",
         ["nebula", "planet_distant", "star_field", "galaxy_background"], "dense", 4),
    ],
    "underground": [
        ("foreground", "Cave floor details, stalagmites, rubble, and close-range elements",
         ["stalactite_small", "cave_floor_detail", "rubble", "mineral_deposit"], "moderate", 10),
        ("midground",  "Cave walls, tunnel structures, and mid-range formations",
         ["cave_wall", "stalactite_large", "tunnel_structure", "underground_pool"], "moderate", 7),
        ("background", "Cavern depth, distant light sources, and atmospheric haze",
         ["cavern_depth", "bioluminescent_element", "cave_background"], "sparse", 4),
    ],
    "interior": [
        ("foreground", "Floor-level props, furniture details, and interactive elements",
         ["furniture_prop", "floor_detail", "scattered_item", "tech_prop"], "moderate", 10),
        ("midground",  "Main furniture, room features, and mid-space elements",
         ["furniture_main", "room_feature", "console", "workstation"], "moderate", 7),
        ("background", "Walls, windows, and architectural background elements",
         ["wall_element", "window", "door", "architectural_detail"], "sparse", 4),
    ],
    "abstract": [
        ("foreground", "Primary abstract shapes and close-range compositional elements",
         ["abstract_shape_fg", "particle_cluster", "light_artifact"], "moderate", 10),
        ("midground",  "Secondary structures and mid-space elements",
         ["abstract_structure", "geometric_form", "light_beam"], "moderate", 7),
        ("background", "Background planes, gradients, and atmospheric depth",
         ["abstract_background", "color_field", "depth_element"], "sparse", 4),
    ],
}

# Fallback template for unknown environments
_DEFAULT_TEMPLATE: List[_ZT] = [
    ("foreground", "Foreground props and close-range compositional elements",
     ["prop", "detail_element", "surface_detail"], "moderate", 10),
    ("midground",  "Main structural and environmental features",
     ["structure", "main_element", "environmental_feature"], "moderate", 7),
    ("background", "Background elements and atmospheric depth",
     ["background_element", "atmospheric_layer"], "sparse", 4),
]

# ---------------------------------------------------------------------------
# Population modifier by mood / destruction
# ---------------------------------------------------------------------------

_MOOD_POPULATION_MODS: Dict[str, str] = {
    "peaceful":    "sparse",
    "melancholic": "sparse",
    "dramatic":    "moderate",
    "tense":       "moderate",
    "chaotic":     "dense",
    "triumphant":  "moderate",
    "ominous":     "moderate",
    "neutral":     "moderate",
}

_DESTRUCTION_EXTRA_CATEGORIES: Dict[str, List[str]] = {
    "moderate":     ["wreckage", "cracked_surface"],
    "heavy":        ["ruin", "collapsed_section", "burned_structure"],
    "catastrophic": ["catastrophic_ruin", "obliterated_section", "debris_field"],
}

# ---------------------------------------------------------------------------
# Placement hints per zone_type
# ---------------------------------------------------------------------------

def _make_placement_hints(zone_type: str, categories: List[str]) -> List[PlacementHint]:
    """Create placement hints for asset categories based on zone type."""
    hints: List[PlacementHint] = []
    depth_map = {"foreground": "front", "midground": "mid", "background": "rear"}
    depth = depth_map.get(zone_type, "mid")

    for cat in categories[:3]:  # limit hints to avoid excessive data
        if zone_type == "foreground":
            position = "distributed"
            spacing  = "medium"
        elif zone_type == "midground":
            position = "distributed"
            spacing  = "medium"
        else:
            position = "distributed"
            spacing  = "loose"
        hints.append(PlacementHint(
            asset_category=cat,
            zone=zone_type,
            position=position,
            depth_hint=depth,
            spacing=spacing,
        ))
    return hints


# ---------------------------------------------------------------------------
# ZonePlanner
# ---------------------------------------------------------------------------

class ZonePlanner:
    """Derives SceneZonePlan list from a SceneIntent.

    All planning is deterministic — no LLM, no bridge calls.
    """

    def plan_zones(self, intent: Any) -> List[SceneZonePlan]:
        """Return ordered zones for the given intent.

        Args:
            intent: A ``SceneIntent`` (or any object with .environment, .mood,
                    .destruction_level, .keywords attributes).

        Returns:
            List of :class:`SceneZonePlan`, ordered foreground→background.
        """
        env  = (getattr(intent, "environment", None) or "").lower()
        mood = (getattr(intent, "mood", None) or "").lower()
        dest = (getattr(intent, "destruction_level", None) or "none").lower()

        template = _ENV_ZONE_TEMPLATES.get(env) or _DEFAULT_TEMPLATE

        zones: List[SceneZonePlan] = []
        for zone_type, description, base_cats, base_pop, priority in template:
            # Apply mood-based population modifier
            population = _MOOD_POPULATION_MODS.get(mood, base_pop) if mood else base_pop
            if zone_type == "background":
                population = "sparse"  # background stays sparse regardless of mood

            # Add destruction-based extra categories to foreground/midground
            cats = list(base_cats)
            if dest in _DESTRUCTION_EXTRA_CATEGORIES and zone_type in ("foreground", "midground"):
                for extra in _DESTRUCTION_EXTRA_CATEGORIES[dest]:
                    if extra not in cats:
                        cats.append(extra)

            placement_hints = _make_placement_hints(zone_type, cats)

            zones.append(SceneZonePlan(
                zone_type=zone_type,
                description=description,
                asset_categories=cats,
                population=population,
                priority=priority,
                placement_hints=placement_hints,
                metadata={"environment": env, "mood": mood, "destruction": dest},
            ))

        return zones


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[ZonePlanner] = None
_INSTANCE_LOCK = threading.Lock()


def get_zone_planner() -> ZonePlanner:
    """Return the module-level singleton ZonePlanner."""
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = ZonePlanner()
    return _INSTANCE


def reset_zone_planner_for_tests() -> None:
    """Replace the singleton. For test isolation only."""
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
