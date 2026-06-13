"""
Asset Environment Mapper (Tier 12.7 + §39 Environment Expansion Pack)
=======================================================================
Maps assets to production environments using keyword-based semantic inference.
Deterministic — same asset metadata always produces the same environment mapping.

55 built-in environments across 9 categories:
  Industrial: industrial_hangar, abandoned_factory, warehouse, shipyard,
              oil_refinery, power_station, mining_facility, construction_site
  Scientific: robotics_lab, research_lab, medical_lab, clean_room,
              biohazard_facility, control_room
  Military:   military_base, command_center, military_hangar, checkpoint, bunker
  Sci-Fi:     sci_fi_corridor, space_station, spaceship_bridge, engineering_bay,
              alien_facility, cyberpunk_city
  Urban:      city_street, alleyway, subway_station, parking_garage, rooftop,
              shopping_mall
  Interior:   western_room, saloon, living_room, office, hotel_lobby,
              restaurant, workshop, library
  Nature:     forest, jungle, desert, canyon, mountain, coastline, swamp
  Fantasy:    castle_hall, dungeon, wizard_tower, ancient_ruins, temple
  Post-Apoc:  abandoned_city, destroyed_highway, ruined_industrial_site,
              survival_camp
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

BUILTIN_ENVIRONMENTS: frozenset = frozenset({
    # Industrial
    "industrial_hangar", "abandoned_factory", "warehouse", "shipyard",
    "oil_refinery", "power_station", "mining_facility", "construction_site",
    # Scientific
    "robotics_lab", "research_lab", "medical_lab", "clean_room",
    "biohazard_facility", "control_room",
    # Military
    "military_base", "command_center", "military_hangar", "checkpoint", "bunker",
    # Sci-Fi
    "sci_fi_corridor", "space_station", "spaceship_bridge",
    "engineering_bay", "alien_facility", "cyberpunk_city",
    # Urban
    "city_street", "alleyway", "subway_station", "parking_garage",
    "rooftop", "shopping_mall",
    # Interior
    "western_room", "saloon", "living_room", "office",
    "hotel_lobby", "restaurant", "workshop", "library",
    # Nature
    "forest", "jungle", "desert", "canyon", "mountain", "coastline", "swamp",
    # Fantasy
    "castle_hall", "dungeon", "wizard_tower", "ancient_ruins", "temple",
    # Post-Apocalyptic
    "abandoned_city", "destroyed_highway", "ruined_industrial_site", "survival_camp",
})

_ENV_KEYWORDS: Dict[str, frozenset] = {
    # -----------------------------------------------------------------------
    # Industrial
    # -----------------------------------------------------------------------
    "industrial_hangar": frozenset({
        "pipe", "crane", "girder", "beam", "hangar", "factory", "industrial",
        "assembly", "tank", "barrel", "machinery", "gear", "turbine", "boiler",
        "furnace", "conveyor", "valve", "flange", "scaffold", "platform",
        "silo", "duct", "storage", "pump", "compressor", "welding",
    }),
    "abandoned_factory": frozenset({
        "rust", "decay", "broken", "abandoned", "derelict", "old", "worn",
        "graffiti", "debris", "rubble", "wreck", "deteriorated", "moss",
        "vegetation", "collapsed", "ruin", "overgrown", "crumbled", "weathered",
    }),
    "warehouse": frozenset({
        "warehouse", "shelf", "shelving", "forklift", "pallet", "crate",
        "storage", "rack", "aisle", "loading", "dock", "inventory", "box",
        "container", "logistics",
    }),
    "shipyard": frozenset({
        "ship", "vessel", "hull", "drydock", "maritime", "anchor", "chain",
        "keel", "bow", "stern", "mast", "shipyard", "dock", "maritime",
    }),
    "oil_refinery": frozenset({
        "refinery", "oil", "petroleum", "distillation", "flare", "cracker",
        "chemical", "processing", "heat_exchanger", "pressure", "reactor",
    }),
    "power_station": frozenset({
        "power", "generator", "electrical", "transformer", "switchgear",
        "cooling_tower", "energy", "substation", "dynamo", "alternator", "grid",
    }),
    "mining_facility": frozenset({
        "mine", "mining", "excavation", "drill", "ore", "quarry", "coal",
        "mineral", "shovel", "crusher", "shaft_tunnel",
    }),
    "construction_site": frozenset({
        "construction", "concrete", "rebar", "foundation", "cement", "builder",
        "framework", "building_site", "scaffold_construction",
    }),
    # -----------------------------------------------------------------------
    # Scientific
    # -----------------------------------------------------------------------
    "robotics_lab": frozenset({
        "robot", "robotic", "arm", "sensor", "panel", "circuit", "lab",
        "laboratory", "tech", "scanner", "servo", "actuator", "computer",
        "monitor", "display", "drone", "automation", "mechanical",
        "controller", "encoder", "camera", "lidar", "component",
    }),
    "research_lab": frozenset({
        "research", "experiment", "apparatus", "flask", "beaker",
        "microscope", "centrifuge", "spectroscope", "sample", "analysis",
        "bench", "scientist", "data", "analytical",
    }),
    "medical_lab": frozenset({
        "medical", "hospital", "surgery", "operating", "sterilize", "syringe",
        "mri", "xray", "patient", "doctor", "sterile", "diagnostic",
        "pharmaceutical", "clinical_medical",
    }),
    "clean_room": frozenset({
        "cleanroom", "semiconductor", "wafer", "microchip", "sterile_room",
        "contamination", "particle_free", "fabrication", "silicon",
        "photolithography", "controlled_environment",
    }),
    "biohazard_facility": frozenset({
        "biohazard", "containment", "biosafety", "hazmat", "pathogen",
        "specimen", "decontamination", "biosafety_cabinet", "pressurized",
        "virus", "bacteria",
    }),
    "control_room": frozenset({
        "console", "screen", "monitor", "terminal", "switch", "button",
        "panel", "control", "desk", "chair", "keyboard", "radar", "dial",
        "gauge", "interface", "hud", "hologram", "station", "workstation",
    }),
    # -----------------------------------------------------------------------
    # Military
    # -----------------------------------------------------------------------
    "military_base": frozenset({
        "military", "barracks", "soldier", "weapon", "tank", "humvee",
        "helicopter_military", "watchtower", "perimeter", "armory",
        "tactical", "parade",
    }),
    "command_center": frozenset({
        "tactical", "briefing", "general", "strategy", "radio",
        "situation_room", "operations", "intel", "mission", "briefing_table",
        "command",
    }),
    "military_hangar": frozenset({
        "fighter", "jet", "bomber", "carrier", "armament", "airforce",
        "pilot", "aircraft_military", "tarmac", "runway",
    }),
    "checkpoint": frozenset({
        "checkpoint", "barrier", "guard", "patrol", "gate", "security",
        "inspection", "booth", "bollard", "border", "crossing",
    }),
    "bunker": frozenset({
        "bunker", "underground", "concrete_bunker", "blast_door", "shelter",
        "emergency", "fortification", "vault", "war_room", "defense",
    }),
    # -----------------------------------------------------------------------
    # Sci-Fi
    # -----------------------------------------------------------------------
    "sci_fi_corridor": frozenset({
        "corridor", "door", "airlock", "hatch", "vent", "grate", "bulkhead",
        "module", "pod", "terminal", "conduit", "cable", "lamp",
        "hallway", "passage", "tunnel", "shaft", "floor", "wall", "ceiling",
    }),
    "space_station": frozenset({
        "space", "station", "orbital", "module_space", "satellite",
        "astronaut", "zero_gravity", "earth_orbit", "solar_panel",
        "docking", "habitat", "microgravity",
    }),
    "spaceship_bridge": frozenset({
        "bridge", "spaceship", "captain", "helm", "navigation", "viewscreen",
        "star", "warp", "galaxy", "crew", "tactical_space", "flight_deck",
    }),
    "engineering_bay": frozenset({
        "engineering", "engine", "power_core", "reactor", "conduit", "plasma",
        "coolant", "warp_core", "thruster", "mechanical_space",
    }),
    "alien_facility": frozenset({
        "alien", "extraterrestrial", "organic", "bioluminescent", "xenomorph",
        "hive", "biomechanical", "crystalline", "otherworldly", "resin",
        "carapace",
    }),
    "cyberpunk_city": frozenset({
        "cyberpunk", "neon", "hologram", "corporate", "megastructure",
        "hacker", "drone_cyber", "implant", "dystopia", "overcrowded",
    }),
    # -----------------------------------------------------------------------
    # Urban
    # -----------------------------------------------------------------------
    "city_street": frozenset({
        "city", "street", "urban", "traffic", "pedestrian", "sidewalk",
        "road", "building", "store", "car", "bus", "traffic_light",
        "crosswalk", "downtown",
    }),
    "alleyway": frozenset({
        "alley", "narrow", "dumpster", "garbage", "fire_escape", "graffiti",
        "brick", "back_street", "drain", "puddle", "back_door",
    }),
    "subway_station": frozenset({
        "subway", "metro", "platform", "train", "track", "commuter",
        "escalator", "turnstile", "rail", "underground_transit",
    }),
    "parking_garage": frozenset({
        "parking", "garage", "concrete_parking", "column_parking", "ramp",
        "parked", "fluorescent_parking", "stairwell",
    }),
    "rooftop": frozenset({
        "rooftop", "roof", "skyline", "hvac", "water_tower",
        "antenna", "parapet", "satellite_dish", "ledge", "chimney",
    }),
    "shopping_mall": frozenset({
        "mall", "shopping", "retail", "store", "escalator", "atrium",
        "skylight", "food_court", "brand", "advertisement", "shop",
        "consumer", "commercial",
    }),
    # -----------------------------------------------------------------------
    # Interior
    # -----------------------------------------------------------------------
    "western_room": frozenset({
        "wood", "barrel_western", "crate_western", "lantern", "whiskey",
        "wagon", "rope", "cowboy", "rustic", "leather", "western",
        "frontier", "old_west", "floorboard", "oil_lamp",
    }),
    "saloon": frozenset({
        "saloon", "bar_counter", "piano", "poker", "card_table",
        "swinging_door", "bartender", "whiskey_glass", "frontier_bar",
    }),
    "living_room": frozenset({
        "sofa", "couch", "tv", "coffee_table", "cushion", "curtain",
        "home", "domestic", "comfortable", "family_room",
    }),
    "office": frozenset({
        "desk", "cubicle", "conference", "meeting_room", "whiteboard",
        "printer", "corporate", "professional", "workspace", "employee",
    }),
    "hotel_lobby": frozenset({
        "hotel", "lobby", "reception", "concierge", "lounge_hotel",
        "chandelier", "marble", "elevator", "luggage", "check_in",
        "fountain", "luxury", "grand",
    }),
    "restaurant": frozenset({
        "dining", "waiter", "menu", "tablecloth", "reservation",
        "ambiance", "open_kitchen", "candle_dining", "wine_dining",
    }),
    "workshop": frozenset({
        "workbench", "hammer", "wrench", "drill_tool", "lathe", "vice",
        "saw", "grinder", "blueprint_workshop", "craft",
    }),
    "library": frozenset({
        "book", "bookcase", "reading", "study", "knowledge", "archive",
        "scroll", "tome", "quiet", "scholar", "catalog_library",
    }),
    # -----------------------------------------------------------------------
    # Nature
    # -----------------------------------------------------------------------
    "forest": frozenset({
        "tree", "foliage", "leaf", "moss", "woodland", "branch",
        "trunk", "bark", "root", "undergrowth", "fern", "mushroom",
        "dappled", "canopy", "trail_forest",
    }),
    "jungle": frozenset({
        "jungle", "tropical", "vine", "palm", "liana", "banana",
        "orchid", "humidity", "rainforest", "exotic",
    }),
    "desert": frozenset({
        "desert", "sand", "dune", "arid", "cactus", "mirrage",
        "tumbleweed", "mesa", "horizon_desert", "bleached",
    }),
    "canyon": frozenset({
        "canyon", "cliff", "gorge", "geological", "sandstone",
        "outcrop", "overhang", "red_rock",
    }),
    "mountain": frozenset({
        "mountain", "alpine", "peak", "summit", "snow", "glacier",
        "ridge", "valley_mountain", "altitude",
    }),
    "coastline": frozenset({
        "coast", "beach", "ocean", "wave", "shore", "sea", "rock_pool",
        "lighthouse", "pier", "fishing", "sea_grass", "foam", "tide",
    }),
    "swamp": frozenset({
        "swamp", "bayou", "marsh", "wetland", "cypress", "murky",
        "reed", "mangrove", "alligator", "dark_water",
    }),
    # -----------------------------------------------------------------------
    # Fantasy
    # -----------------------------------------------------------------------
    "castle_hall": frozenset({
        "castle", "throne", "tapestry", "banner", "stained_glass",
        "torch_medieval", "knight", "heraldry", "great_hall", "arched",
    }),
    "dungeon": frozenset({
        "dungeon", "prison_cell", "chain", "dark_underground", "torture",
        "skeleton", "iron_door", "medieval_dark",
    }),
    "wizard_tower": frozenset({
        "wizard", "mage", "spell", "potion", "alchemy", "arcane",
        "magic", "tome", "crystal", "orb", "staff", "scroll", "rune",
        "mystical",
    }),
    "ancient_ruins": frozenset({
        "ruin", "ancient", "collapsed_column", "overgrown_stone",
        "archaeological", "inscription", "lost_civilization", "forgotten",
    }),
    "temple": frozenset({
        "shrine", "altar", "sacred", "holy", "incense", "candle_temple",
        "offering", "prayer", "spiritual", "religious", "ceremonial", "deity",
    }),
    # -----------------------------------------------------------------------
    # Post-Apocalyptic
    # -----------------------------------------------------------------------
    "abandoned_city": frozenset({
        "apocalyptic", "desolate", "survivors", "empty_city",
        "overgrown_city", "broken_window", "post_apocalyptic",
    }),
    "destroyed_highway": frozenset({
        "highway", "road_wreck", "cracked_road", "overpass", "roadblock",
        "wrecked_vehicle",
    }),
    "ruined_industrial_site": frozenset({
        "contamination", "hazard", "toxic", "structural_failure", "fallout",
        "chemical_leak", "ruined_factory",
    }),
    "survival_camp": frozenset({
        "camp", "survival", "makeshift", "barricade", "scavenged",
        "campfire", "watchtower_survival", "settlement", "improvised",
    }),
}

_CATEGORY_ENV_AFFINITY: Dict[str, List[str]] = {
    "machinery":     ["industrial_hangar", "robotics_lab", "power_station", "mining_facility"],
    "robot":         ["robotics_lab", "industrial_hangar", "engineering_bay"],
    "prop":          ["industrial_hangar", "sci_fi_corridor", "western_room", "workshop"],
    "architecture":  ["abandoned_factory", "sci_fi_corridor", "castle_hall", "abandoned_city"],
    "electronics":   ["control_room", "robotics_lab", "command_center", "spaceship_bridge"],
    "furniture":     ["control_room", "office", "living_room", "hotel_lobby", "library"],
    "vehicle":       ["industrial_hangar", "abandoned_factory", "military_base", "city_street"],
    "vegetation":    ["abandoned_factory", "forest", "jungle", "swamp", "ancient_ruins"],
    "surface":       ["industrial_hangar", "abandoned_factory", "desert", "canyon"],
    "material":      ["industrial_hangar", "abandoned_factory", "desert", "canyon"],
    "equipment":     ["industrial_hangar", "robotics_lab", "medical_lab", "workshop"],
    "tool":          ["industrial_hangar", "workshop", "construction_site"],
    "weapon":        ["military_base", "military_hangar", "bunker", "dungeon"],
    "creature":      ["forest", "jungle", "swamp", "alien_facility"],
    "terrain":       ["desert", "canyon", "mountain", "forest", "swamp", "coastline"],
    "character":     ["city_street", "sci_fi_corridor", "spaceship_bridge"],
    "decoration":    ["living_room", "hotel_lobby", "castle_hall", "library", "temple"],
}


@dataclass
class EnvironmentMapping:
    asset_id:     str = ""
    environments: List[str] = field(default_factory=list)
    scores:       Dict[str, float] = field(default_factory=dict)
    primary:      str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id":     str(self.asset_id),
            "environments": list(self.environments),
            "scores":       dict(self.scores),
            "primary":      str(self.primary),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "EnvironmentMapping":
        d = d if isinstance(d, dict) else {}
        return cls(
            asset_id=str(d.get("asset_id", "")),
            environments=list(d.get("environments") or []),
            scores=dict(d.get("scores") or {}),
            primary=str(d.get("primary", "")),
        )


class AssetEnvironmentMapper:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._map_count = 0

    def map_environments(self, asset_dict: Dict[str, Any]) -> EnvironmentMapping:
        """Infer applicable environments from asset metadata. Never raises."""
        try:
            return self._do_map(asset_dict if isinstance(asset_dict, dict) else {})
        except Exception:
            return EnvironmentMapping(
                asset_id=str((asset_dict or {}).get("asset_id", "")),
            )

    def _do_map(self, asset: Dict[str, Any]) -> EnvironmentMapping:
        asset_id = str(asset.get("asset_id", "")).strip()
        name = str(asset.get("name", "")).lower()
        category = str(asset.get("category", "")).lower()
        tags = [str(t).lower() for t in (asset.get("tags") or [])]
        semantic_tags = [str(t).lower() for t in (asset.get("semantic_tags") or [])]
        description = str(asset.get("description", "")).lower()

        all_text = f"{name} {description} {' '.join(tags)} {' '.join(semantic_tags)} {category}"
        tokens = set(all_text.split())

        scores: Dict[str, float] = {}
        for env, keywords in _ENV_KEYWORDS.items():
            keyword_hits = len(tokens & keywords)
            score = keyword_hits / max(len(keywords) * 0.15, 1)
            if category in _CATEGORY_ENV_AFFINITY and env in _CATEGORY_ENV_AFFINITY[category]:
                score += 0.3
            scores[env] = round(min(score, 1.0), 4)

        qualified = {e: s for e, s in scores.items() if s > 0.05}
        ranked = sorted(qualified.keys(), key=lambda e: scores[e], reverse=True)
        primary = ranked[0] if ranked else ""

        with self._lock:
            self._map_count += 1

        return EnvironmentMapping(
            asset_id=asset_id,
            environments=ranked,
            scores={e: scores[e] for e in ranked},
            primary=primary,
        )

    def rank_environment_fit(
        self,
        asset_dict: Dict[str, Any],
        environments: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Rank environments by fit score for a given asset."""
        try:
            mapping = self.map_environments(asset_dict)
            envs = environments if environments else sorted(BUILTIN_ENVIRONMENTS)
            result = []
            for env in envs:
                result.append({"environment": env, "score": mapping.scores.get(env, 0.0)})
            return sorted(result, key=lambda x: x["score"], reverse=True)
        except Exception:
            return []

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            return {"map_count": self._map_count}


_INSTANCE: Optional[AssetEnvironmentMapper] = None
_INSTANCE_LOCK = threading.Lock()


def get_asset_environment_mapper() -> AssetEnvironmentMapper:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = AssetEnvironmentMapper()
    return _INSTANCE


def reset_asset_environment_mapper_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
