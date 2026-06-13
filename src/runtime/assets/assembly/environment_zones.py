"""
Environment Zones (Tier 9.5 — Structural Environment Assembly)
===============================================================
Defines the semantic zone types used in structured environment assembly.
Zones are spatial containers that organize assets by narrative and structural
role. They are always created after the structural scaffold is built.

Zone execution order (enforced by EnvironmentStructureBuilder):
  1. entrance_zone  — viewer entry point / camera approach
  2. hero_zone      — primary focal point, major anchor assets
  3. support_zone   — secondary assets that contextualise the hero
  4. decoration_zone — small props, surface dressing
  5. atmosphere_zone — lighting, volumetrics, atmospheric effects
  6. background_zone — distant perimeter / set dressing

DESIGN RULES:
  1. No bridge calls. No Houdini imports. Planning only.
  2. Zone definitions are deterministic.
  3. Never raises.

Public API:
    ZONE_TYPES
    StructuralZone
    BUILTIN_ZONE_DEFINITIONS
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


ZONE_TYPES = frozenset({
    "entrance_zone",
    "hero_zone",
    "support_zone",
    "decoration_zone",
    "atmosphere_zone",
    "background_zone",
})

# Role descriptions for each zone type
ZONE_ROLE_DESCRIPTIONS: Dict[str, str] = {
    "entrance_zone":   "Viewer entry or camera approach — establishes the first impression.",
    "hero_zone":       "Primary focal point — holds the major anchor assets that define the scene.",
    "support_zone":    "Secondary zone — contextualises and supports the hero without stealing focus.",
    "decoration_zone": "Surface dressing — small props, details, and narrative texture.",
    "atmosphere_zone": "Atmospheric layer — lighting, volumetrics, particles, HDRI.",
    "background_zone": "Distant perimeter — architectural set dressing and depth fills.",
}


@dataclass
class StructuralZone:
    """A named spatial container within an environment structure."""

    zone_id:   str = ""   # unique ID within the environment (e.g. "hero_zone")
    zone_type: str = ""   # one of ZONE_TYPES

    label:       str = ""
    description: str = ""

    # Spatial hint for the placement engine
    position_hint: str = "center"   # center / perimeter / corners / ceiling / foreground / midground / background

    # Asset budget
    max_assets: int  = 8
    min_assets: int  = 0

    required:           bool       = False
    allowed_categories: List[str]  = field(default_factory=list)

    # Preferred facing direction for assets placed in this zone
    facing: str = "camera"  # camera / inward / outward / scattered

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id":            self.zone_id,
            "zone_type":          self.zone_type,
            "label":              self.label,
            "description":        self.description,
            "position_hint":      self.position_hint,
            "max_assets":         self.max_assets,
            "min_assets":         self.min_assets,
            "required":           self.required,
            "allowed_categories": list(self.allowed_categories),
            "facing":             self.facing,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "StructuralZone":
        return cls(
            zone_id            = str(d.get("zone_id", "")),
            zone_type          = str(d.get("zone_type", "")),
            label              = str(d.get("label", "")),
            description        = str(d.get("description", "")),
            position_hint      = str(d.get("position_hint", "center")),
            max_assets         = int(d.get("max_assets", 8)),
            min_assets         = int(d.get("min_assets", 0)),
            required           = bool(d.get("required", False)),
            allowed_categories = list(d.get("allowed_categories", [])),
            facing             = str(d.get("facing", "camera")),
        )


# ---------------------------------------------------------------------------
# Pre-built canonical zone sets for each environment
# The structure builder selects the appropriate set from this dict.
# ---------------------------------------------------------------------------

BUILTIN_ZONE_DEFINITIONS: Dict[str, List[Dict[str, Any]]] = {

    # ---- Interior ----

    "western_room": [
        {"zone_id": "entrance_zone",   "zone_type": "entrance_zone",   "label": "Entrance / Swing Door",  "position_hint": "foreground", "max_assets": 3,  "min_assets": 1, "required": True,  "allowed_categories": ["architectural", "prop"], "facing": "camera"},
        {"zone_id": "hero_zone",       "zone_type": "hero_zone",       "label": "Main Table Area",        "position_hint": "center",     "max_assets": 5,  "min_assets": 1, "required": True,  "allowed_categories": ["furniture", "prop"],     "facing": "camera"},
        {"zone_id": "support_zone",    "zone_type": "support_zone",    "label": "Bar Counter / Fireplace","position_hint": "background",  "max_assets": 6,  "min_assets": 1, "required": True,  "allowed_categories": ["furniture", "prop"],     "facing": "inward"},
        {"zone_id": "decoration_zone", "zone_type": "decoration_zone", "label": "Surface Props",          "position_hint": "center",     "max_assets": 12, "min_assets": 2, "required": False, "allowed_categories": ["prop"],                  "facing": "scattered"},
        {"zone_id": "atmosphere_zone", "zone_type": "atmosphere_zone", "label": "Atmosphere",             "position_hint": "ceiling",    "max_assets": 4,  "min_assets": 0, "required": False, "allowed_categories": ["material", "hdri"],      "facing": "outward"},
        {"zone_id": "background_zone", "zone_type": "background_zone", "label": "Wall Dressing",          "position_hint": "perimeter",  "max_assets": 6,  "min_assets": 1, "required": True,  "allowed_categories": ["architectural", "prop"], "facing": "inward"},
    ],

    "saloon": [
        {"zone_id": "entrance_zone",   "zone_type": "entrance_zone",   "label": "Saloon Doors",           "position_hint": "foreground", "max_assets": 2,  "min_assets": 1, "required": True,  "allowed_categories": ["architectural", "prop"], "facing": "camera"},
        {"zone_id": "hero_zone",       "zone_type": "hero_zone",       "label": "Bar Counter",            "position_hint": "background", "max_assets": 4,  "min_assets": 1, "required": True,  "allowed_categories": ["furniture", "prop"],     "facing": "camera"},
        {"zone_id": "support_zone",    "zone_type": "support_zone",    "label": "Gambling Tables",        "position_hint": "center",     "max_assets": 8,  "min_assets": 2, "required": True,  "allowed_categories": ["furniture", "prop"],     "facing": "inward"},
        {"zone_id": "decoration_zone", "zone_type": "decoration_zone", "label": "Surface Props",          "position_hint": "center",     "max_assets": 10, "min_assets": 2, "required": False, "allowed_categories": ["prop"],                  "facing": "scattered"},
        {"zone_id": "atmosphere_zone", "zone_type": "atmosphere_zone", "label": "Warm Haze",              "position_hint": "ceiling",    "max_assets": 4,  "min_assets": 0, "required": False, "allowed_categories": ["material", "hdri"],      "facing": "outward"},
        {"zone_id": "background_zone", "zone_type": "background_zone", "label": "Back Wall / Stage",      "position_hint": "perimeter",  "max_assets": 5,  "min_assets": 1, "required": True,  "allowed_categories": ["architectural", "prop"], "facing": "inward"},
    ],

    "living_room": [
        {"zone_id": "entrance_zone",   "zone_type": "entrance_zone",   "label": "Doorway",                "position_hint": "foreground", "max_assets": 2,  "min_assets": 0, "required": False, "allowed_categories": ["architectural"],          "facing": "camera"},
        {"zone_id": "hero_zone",       "zone_type": "hero_zone",       "label": "Sofa & Coffee Table",    "position_hint": "center",     "max_assets": 4,  "min_assets": 1, "required": True,  "allowed_categories": ["furniture"],              "facing": "camera"},
        {"zone_id": "support_zone",    "zone_type": "support_zone",    "label": "TV / Bookcase Area",     "position_hint": "background", "max_assets": 5,  "min_assets": 1, "required": True,  "allowed_categories": ["furniture", "electronic"],"facing": "inward"},
        {"zone_id": "decoration_zone", "zone_type": "decoration_zone", "label": "Surface Dressing",       "position_hint": "center",     "max_assets": 10, "min_assets": 2, "required": False, "allowed_categories": ["prop"],                  "facing": "scattered"},
        {"zone_id": "atmosphere_zone", "zone_type": "atmosphere_zone", "label": "Window Light",           "position_hint": "perimeter",  "max_assets": 3,  "min_assets": 0, "required": False, "allowed_categories": ["material", "hdri"],      "facing": "inward"},
        {"zone_id": "background_zone", "zone_type": "background_zone", "label": "Far Wall / Shelves",     "position_hint": "perimeter",  "max_assets": 4,  "min_assets": 1, "required": False, "allowed_categories": ["furniture", "prop"],     "facing": "inward"},
    ],

    "office": [
        {"zone_id": "entrance_zone",   "zone_type": "entrance_zone",   "label": "Reception Area",         "position_hint": "foreground", "max_assets": 3,  "min_assets": 0, "required": False, "allowed_categories": ["furniture", "prop"],     "facing": "camera"},
        {"zone_id": "hero_zone",       "zone_type": "hero_zone",       "label": "Main Desk",              "position_hint": "center",     "max_assets": 4,  "min_assets": 1, "required": True,  "allowed_categories": ["furniture", "electronic"],"facing": "camera"},
        {"zone_id": "support_zone",    "zone_type": "support_zone",    "label": "Workstations / Filing",  "position_hint": "perimeter",  "max_assets": 8,  "min_assets": 2, "required": True,  "allowed_categories": ["furniture", "electronic"],"facing": "inward"},
        {"zone_id": "decoration_zone", "zone_type": "decoration_zone", "label": "Desk Props",             "position_hint": "center",     "max_assets": 8,  "min_assets": 1, "required": False, "allowed_categories": ["prop"],                  "facing": "scattered"},
        {"zone_id": "atmosphere_zone", "zone_type": "atmosphere_zone", "label": "Fluorescent Ambient",    "position_hint": "ceiling",    "max_assets": 3,  "min_assets": 0, "required": False, "allowed_categories": ["material", "hdri"],      "facing": "outward"},
        {"zone_id": "background_zone", "zone_type": "background_zone", "label": "Window Wall",            "position_hint": "perimeter",  "max_assets": 4,  "min_assets": 0, "required": False, "allowed_categories": ["architectural", "prop"], "facing": "inward"},
    ],

    "hotel_lobby": [
        {"zone_id": "entrance_zone",   "zone_type": "entrance_zone",   "label": "Main Entrance Doors",    "position_hint": "foreground", "max_assets": 3,  "min_assets": 1, "required": True,  "allowed_categories": ["architectural"],          "facing": "camera"},
        {"zone_id": "hero_zone",       "zone_type": "hero_zone",       "label": "Reception & Seating",    "position_hint": "center",     "max_assets": 6,  "min_assets": 2, "required": True,  "allowed_categories": ["furniture", "prop"],     "facing": "camera"},
        {"zone_id": "support_zone",    "zone_type": "support_zone",    "label": "Lounge / Pillars",       "position_hint": "midground",  "max_assets": 8,  "min_assets": 2, "required": True,  "allowed_categories": ["furniture", "architectural"],"facing": "inward"},
        {"zone_id": "decoration_zone", "zone_type": "decoration_zone", "label": "Ornamental Props",       "position_hint": "center",     "max_assets": 8,  "min_assets": 2, "required": False, "allowed_categories": ["prop"],                  "facing": "scattered"},
        {"zone_id": "atmosphere_zone", "zone_type": "atmosphere_zone", "label": "Warm Chandelier Light",  "position_hint": "ceiling",    "max_assets": 3,  "min_assets": 0, "required": False, "allowed_categories": ["material", "hdri"],      "facing": "outward"},
        {"zone_id": "background_zone", "zone_type": "background_zone", "label": "Grand Staircase / Lifts","position_hint": "background", "max_assets": 4,  "min_assets": 1, "required": True,  "allowed_categories": ["architectural"],          "facing": "inward"},
    ],

    "restaurant": [
        {"zone_id": "entrance_zone",   "zone_type": "entrance_zone",   "label": "Host Stand / Entrance",  "position_hint": "foreground", "max_assets": 2,  "min_assets": 1, "required": True,  "allowed_categories": ["furniture", "prop"],     "facing": "camera"},
        {"zone_id": "hero_zone",       "zone_type": "hero_zone",       "label": "Feature Dining Table",   "position_hint": "center",     "max_assets": 5,  "min_assets": 2, "required": True,  "allowed_categories": ["furniture"],              "facing": "camera"},
        {"zone_id": "support_zone",    "zone_type": "support_zone",    "label": "Dining Area / Bar",      "position_hint": "midground",  "max_assets": 10, "min_assets": 3, "required": True,  "allowed_categories": ["furniture", "prop"],     "facing": "inward"},
        {"zone_id": "decoration_zone", "zone_type": "decoration_zone", "label": "Table Settings",         "position_hint": "center",     "max_assets": 10, "min_assets": 2, "required": False, "allowed_categories": ["prop"],                  "facing": "scattered"},
        {"zone_id": "atmosphere_zone", "zone_type": "atmosphere_zone", "label": "Warm Ambient / Candles", "position_hint": "ceiling",    "max_assets": 4,  "min_assets": 0, "required": False, "allowed_categories": ["material", "hdri"],      "facing": "outward"},
        {"zone_id": "background_zone", "zone_type": "background_zone", "label": "Kitchen Pass / Bar Wall","position_hint": "background", "max_assets": 5,  "min_assets": 1, "required": True,  "allowed_categories": ["architectural", "prop"], "facing": "inward"},
    ],

    "library": [
        {"zone_id": "entrance_zone",   "zone_type": "entrance_zone",   "label": "Library Entrance",       "position_hint": "foreground", "max_assets": 2,  "min_assets": 0, "required": False, "allowed_categories": ["architectural", "prop"], "facing": "camera"},
        {"zone_id": "hero_zone",       "zone_type": "hero_zone",       "label": "Reading Table / Desk",   "position_hint": "center",     "max_assets": 4,  "min_assets": 1, "required": True,  "allowed_categories": ["furniture"],              "facing": "camera"},
        {"zone_id": "support_zone",    "zone_type": "support_zone",    "label": "Bookshelf Walls",        "position_hint": "perimeter",  "max_assets": 8,  "min_assets": 3, "required": True,  "allowed_categories": ["furniture", "prop"],     "facing": "inward"},
        {"zone_id": "decoration_zone", "zone_type": "decoration_zone", "label": "Reading Props / Globes", "position_hint": "center",     "max_assets": 8,  "min_assets": 2, "required": False, "allowed_categories": ["prop"],                  "facing": "scattered"},
        {"zone_id": "atmosphere_zone", "zone_type": "atmosphere_zone", "label": "Diffuse Reading Light",  "position_hint": "ceiling",    "max_assets": 3,  "min_assets": 0, "required": False, "allowed_categories": ["material", "hdri"],      "facing": "outward"},
        {"zone_id": "background_zone", "zone_type": "background_zone", "label": "Archive / Mezzanine",    "position_hint": "background", "max_assets": 4,  "min_assets": 0, "required": False, "allowed_categories": ["architectural", "furniture"],"facing": "inward"},
    ],

    # ---- Industrial ----

    "industrial_hangar": [
        {"zone_id": "entrance_zone",   "zone_type": "entrance_zone",   "label": "Hangar Entrance",        "position_hint": "foreground", "max_assets": 4,  "min_assets": 1, "required": True,  "allowed_categories": ["architectural"],          "facing": "camera"},
        {"zone_id": "hero_zone",       "zone_type": "hero_zone",       "label": "Main Machine / Vehicle", "position_hint": "center",     "max_assets": 3,  "min_assets": 1, "required": True,  "allowed_categories": ["machinery", "vehicle", "robot"],"facing": "camera"},
        {"zone_id": "support_zone",    "zone_type": "support_zone",    "label": "Crane / Catwalks",       "position_hint": "midground",  "max_assets": 6,  "min_assets": 1, "required": True,  "allowed_categories": ["structure", "electronic", "machinery"],"facing": "inward"},
        {"zone_id": "decoration_zone", "zone_type": "decoration_zone", "label": "Industrial Props",       "position_hint": "perimeter",  "max_assets": 10, "min_assets": 2, "required": False, "allowed_categories": ["prop", "pipe"],           "facing": "scattered"},
        {"zone_id": "atmosphere_zone", "zone_type": "atmosphere_zone", "label": "Industrial Haze / Shafts","position_hint": "ceiling",   "max_assets": 4,  "min_assets": 0, "required": False, "allowed_categories": ["material", "hdri"],      "facing": "outward"},
        {"zone_id": "background_zone", "zone_type": "background_zone", "label": "Columns / Back Wall",    "position_hint": "background", "max_assets": 8,  "min_assets": 2, "required": True,  "allowed_categories": ["structure", "architectural"],"facing": "inward"},
    ],

    "warehouse": [
        {"zone_id": "entrance_zone",   "zone_type": "entrance_zone",   "label": "Loading Dock",           "position_hint": "foreground", "max_assets": 3,  "min_assets": 1, "required": True,  "allowed_categories": ["architectural", "prop"], "facing": "camera"},
        {"zone_id": "hero_zone",       "zone_type": "hero_zone",       "label": "Main Storage Rack",      "position_hint": "center",     "max_assets": 4,  "min_assets": 1, "required": True,  "allowed_categories": ["structure", "prop"],     "facing": "camera"},
        {"zone_id": "support_zone",    "zone_type": "support_zone",    "label": "Pallet Stacks / Forklift","position_hint": "midground", "max_assets": 8,  "min_assets": 2, "required": True,  "allowed_categories": ["prop", "vehicle"],       "facing": "inward"},
        {"zone_id": "decoration_zone", "zone_type": "decoration_zone", "label": "Crates & Barrels",       "position_hint": "perimeter",  "max_assets": 12, "min_assets": 3, "required": False, "allowed_categories": ["prop"],                  "facing": "scattered"},
        {"zone_id": "atmosphere_zone", "zone_type": "atmosphere_zone", "label": "Warehouse Haze",         "position_hint": "ceiling",    "max_assets": 3,  "min_assets": 0, "required": False, "allowed_categories": ["material", "hdri"],      "facing": "outward"},
        {"zone_id": "background_zone", "zone_type": "background_zone", "label": "Far Racks / Wall",       "position_hint": "background", "max_assets": 6,  "min_assets": 1, "required": True,  "allowed_categories": ["structure", "architectural"],"facing": "inward"},
    ],

    "abandoned_factory": [
        {"zone_id": "entrance_zone",   "zone_type": "entrance_zone",   "label": "Broken Entry",           "position_hint": "foreground", "max_assets": 3,  "min_assets": 0, "required": False, "allowed_categories": ["architectural", "prop"], "facing": "camera"},
        {"zone_id": "hero_zone",       "zone_type": "hero_zone",       "label": "Collapsed Machinery",    "position_hint": "center",     "max_assets": 3,  "min_assets": 1, "required": True,  "allowed_categories": ["machinery", "structure"], "facing": "camera"},
        {"zone_id": "support_zone",    "zone_type": "support_zone",    "label": "Ruined Structure",       "position_hint": "midground",  "max_assets": 6,  "min_assets": 2, "required": True,  "allowed_categories": ["structure", "prop"],     "facing": "scattered"},
        {"zone_id": "decoration_zone", "zone_type": "decoration_zone", "label": "Debris & Decay",         "position_hint": "perimeter",  "max_assets": 12, "min_assets": 3, "required": False, "allowed_categories": ["prop", "terrain"],       "facing": "scattered"},
        {"zone_id": "atmosphere_zone", "zone_type": "atmosphere_zone", "label": "Dust / Light Shafts",    "position_hint": "ceiling",    "max_assets": 4,  "min_assets": 0, "required": False, "allowed_categories": ["material", "hdri"],      "facing": "outward"},
        {"zone_id": "background_zone", "zone_type": "background_zone", "label": "Crumbling Walls",        "position_hint": "background", "max_assets": 6,  "min_assets": 1, "required": True,  "allowed_categories": ["architectural", "structure"],"facing": "inward"},
    ],

    # ---- Scientific ----

    "robotics_lab": [
        {"zone_id": "entrance_zone",   "zone_type": "entrance_zone",   "label": "Security Airlock",       "position_hint": "foreground", "max_assets": 2,  "min_assets": 0, "required": False, "allowed_categories": ["architectural"],          "facing": "camera"},
        {"zone_id": "hero_zone",       "zone_type": "hero_zone",       "label": "Robot Platform",         "position_hint": "center",     "max_assets": 3,  "min_assets": 1, "required": True,  "allowed_categories": ["robot", "machinery", "electronic"],"facing": "camera"},
        {"zone_id": "support_zone",    "zone_type": "support_zone",    "label": "Server Racks / Consoles","position_hint": "perimeter",  "max_assets": 8,  "min_assets": 2, "required": True,  "allowed_categories": ["electronic", "furniture"], "facing": "inward"},
        {"zone_id": "decoration_zone", "zone_type": "decoration_zone", "label": "Lab Equipment / Cables", "position_hint": "center",     "max_assets": 8,  "min_assets": 1, "required": False, "allowed_categories": ["prop", "electronic"],    "facing": "scattered"},
        {"zone_id": "atmosphere_zone", "zone_type": "atmosphere_zone", "label": "LED / Equipment Glow",   "position_hint": "ceiling",    "max_assets": 3,  "min_assets": 0, "required": False, "allowed_categories": ["material", "hdri"],      "facing": "outward"},
        {"zone_id": "background_zone", "zone_type": "background_zone", "label": "Glass Partitions / Wall","position_hint": "background", "max_assets": 4,  "min_assets": 1, "required": False, "allowed_categories": ["architectural", "electronic"],"facing": "inward"},
    ],

    "research_lab": [
        {"zone_id": "entrance_zone",   "zone_type": "entrance_zone",   "label": "Lab Entry",              "position_hint": "foreground", "max_assets": 2,  "min_assets": 0, "required": False, "allowed_categories": ["architectural"],          "facing": "camera"},
        {"zone_id": "hero_zone",       "zone_type": "hero_zone",       "label": "Central Lab Bench",      "position_hint": "center",     "max_assets": 4,  "min_assets": 1, "required": True,  "allowed_categories": ["furniture", "electronic"],"facing": "camera"},
        {"zone_id": "support_zone",    "zone_type": "support_zone",    "label": "Fume Hoods / Storage",   "position_hint": "perimeter",  "max_assets": 8,  "min_assets": 2, "required": True,  "allowed_categories": ["furniture", "electronic"],"facing": "inward"},
        {"zone_id": "decoration_zone", "zone_type": "decoration_zone", "label": "Specimens / Tools",      "position_hint": "center",     "max_assets": 10, "min_assets": 2, "required": False, "allowed_categories": ["prop"],                  "facing": "scattered"},
        {"zone_id": "atmosphere_zone", "zone_type": "atmosphere_zone", "label": "Cool Lab Light",         "position_hint": "ceiling",    "max_assets": 3,  "min_assets": 0, "required": False, "allowed_categories": ["material", "hdri"],      "facing": "outward"},
        {"zone_id": "background_zone", "zone_type": "background_zone", "label": "Server Cluster / Window","position_hint": "background", "max_assets": 4,  "min_assets": 1, "required": False, "allowed_categories": ["electronic", "architectural"],"facing": "inward"},
    ],

    "medical_lab": [
        {"zone_id": "entrance_zone",   "zone_type": "entrance_zone",   "label": "Decontamination Entry",  "position_hint": "foreground", "max_assets": 2,  "min_assets": 0, "required": False, "allowed_categories": ["architectural"],          "facing": "camera"},
        {"zone_id": "hero_zone",       "zone_type": "hero_zone",       "label": "Operating Table / Scanner","position_hint": "center",   "max_assets": 3,  "min_assets": 1, "required": True,  "allowed_categories": ["furniture", "electronic"],"facing": "camera"},
        {"zone_id": "support_zone",    "zone_type": "support_zone",    "label": "Medical Equipment",      "position_hint": "perimeter",  "max_assets": 8,  "min_assets": 2, "required": True,  "allowed_categories": ["electronic", "furniture"],"facing": "inward"},
        {"zone_id": "decoration_zone", "zone_type": "decoration_zone", "label": "Medical Props",          "position_hint": "center",     "max_assets": 8,  "min_assets": 1, "required": False, "allowed_categories": ["prop"],                  "facing": "scattered"},
        {"zone_id": "atmosphere_zone", "zone_type": "atmosphere_zone", "label": "Sterile White Ambient",  "position_hint": "ceiling",    "max_assets": 3,  "min_assets": 0, "required": False, "allowed_categories": ["material", "hdri"],      "facing": "outward"},
        {"zone_id": "background_zone", "zone_type": "background_zone", "label": "Observation Window",     "position_hint": "background", "max_assets": 3,  "min_assets": 0, "required": False, "allowed_categories": ["architectural"],          "facing": "inward"},
    ],

    "control_room": [
        {"zone_id": "entrance_zone",   "zone_type": "entrance_zone",   "label": "Entry / Airlock",        "position_hint": "foreground", "max_assets": 2,  "min_assets": 0, "required": False, "allowed_categories": ["architectural"],          "facing": "camera"},
        {"zone_id": "hero_zone",       "zone_type": "hero_zone",       "label": "Command Console Array",  "position_hint": "center",     "max_assets": 4,  "min_assets": 2, "required": True,  "allowed_categories": ["electronic", "furniture"],"facing": "camera"},
        {"zone_id": "support_zone",    "zone_type": "support_zone",    "label": "Workstations",           "position_hint": "midground",  "max_assets": 8,  "min_assets": 2, "required": True,  "allowed_categories": ["electronic", "furniture"],"facing": "inward"},
        {"zone_id": "decoration_zone", "zone_type": "decoration_zone", "label": "Status Lights / Props",  "position_hint": "perimeter",  "max_assets": 8,  "min_assets": 1, "required": False, "allowed_categories": ["prop", "electronic"],    "facing": "scattered"},
        {"zone_id": "atmosphere_zone", "zone_type": "atmosphere_zone", "label": "Console Glow / Screen",  "position_hint": "ceiling",    "max_assets": 3,  "min_assets": 0, "required": False, "allowed_categories": ["material", "hdri"],      "facing": "outward"},
        {"zone_id": "background_zone", "zone_type": "background_zone", "label": "Main Screen / Back Wall","position_hint": "background", "max_assets": 4,  "min_assets": 1, "required": True,  "allowed_categories": ["electronic", "architectural"],"facing": "inward"},
    ],

    # ---- Sci-Fi ----

    "sci_fi_corridor": [
        {"zone_id": "entrance_zone",   "zone_type": "entrance_zone",   "label": "Blast Door / Airlock",   "position_hint": "foreground", "max_assets": 2,  "min_assets": 1, "required": True,  "allowed_categories": ["architectural"],          "facing": "camera"},
        {"zone_id": "hero_zone",       "zone_type": "hero_zone",       "label": "Central Corridor",       "position_hint": "center",     "max_assets": 3,  "min_assets": 1, "required": True,  "allowed_categories": ["electronic", "prop"],    "facing": "camera"},
        {"zone_id": "support_zone",    "zone_type": "support_zone",    "label": "Side Panels / Vents",    "position_hint": "perimeter",  "max_assets": 8,  "min_assets": 2, "required": True,  "allowed_categories": ["electronic", "pipe"],    "facing": "inward"},
        {"zone_id": "decoration_zone", "zone_type": "decoration_zone", "label": "Holo Emitters / Decals", "position_hint": "perimeter",  "max_assets": 8,  "min_assets": 1, "required": False, "allowed_categories": ["prop", "electronic"],    "facing": "scattered"},
        {"zone_id": "atmosphere_zone", "zone_type": "atmosphere_zone", "label": "LED / Scan Light",       "position_hint": "ceiling",    "max_assets": 3,  "min_assets": 0, "required": False, "allowed_categories": ["material", "hdri"],      "facing": "outward"},
        {"zone_id": "background_zone", "zone_type": "background_zone", "label": "Far Blast Door",         "position_hint": "background", "max_assets": 3,  "min_assets": 1, "required": True,  "allowed_categories": ["architectural"],          "facing": "inward"},
    ],

    "space_station": [
        {"zone_id": "entrance_zone",   "zone_type": "entrance_zone",   "label": "Docking Airlock",        "position_hint": "foreground", "max_assets": 2,  "min_assets": 1, "required": True,  "allowed_categories": ["architectural"],          "facing": "camera"},
        {"zone_id": "hero_zone",       "zone_type": "hero_zone",       "label": "Navigation / Command",   "position_hint": "center",     "max_assets": 4,  "min_assets": 2, "required": True,  "allowed_categories": ["electronic", "furniture"],"facing": "camera"},
        {"zone_id": "support_zone",    "zone_type": "support_zone",    "label": "Equipment Bays",         "position_hint": "perimeter",  "max_assets": 8,  "min_assets": 2, "required": True,  "allowed_categories": ["electronic", "structure"],"facing": "inward"},
        {"zone_id": "decoration_zone", "zone_type": "decoration_zone", "label": "Personal / Tool Props",  "position_hint": "perimeter",  "max_assets": 8,  "min_assets": 1, "required": False, "allowed_categories": ["prop"],                  "facing": "scattered"},
        {"zone_id": "atmosphere_zone", "zone_type": "atmosphere_zone", "label": "Starfield Viewport",     "position_hint": "perimeter",  "max_assets": 3,  "min_assets": 0, "required": False, "allowed_categories": ["material", "hdri"],      "facing": "outward"},
        {"zone_id": "background_zone", "zone_type": "background_zone", "label": "Hull / Viewport Wall",   "position_hint": "background", "max_assets": 4,  "min_assets": 1, "required": True,  "allowed_categories": ["architectural", "electronic"],"facing": "inward"},
    ],

    # ---- Outdoor ----

    "city_street": [
        {"zone_id": "entrance_zone",   "zone_type": "entrance_zone",   "label": "Foreground Sidewalk",    "position_hint": "foreground", "max_assets": 4,  "min_assets": 1, "required": True,  "allowed_categories": ["prop", "architectural"], "facing": "camera"},
        {"zone_id": "hero_zone",       "zone_type": "hero_zone",       "label": "Main Building Entrance", "position_hint": "center",     "max_assets": 3,  "min_assets": 1, "required": True,  "allowed_categories": ["architectural", "prop"], "facing": "camera"},
        {"zone_id": "support_zone",    "zone_type": "support_zone",    "label": "Street Furniture",       "position_hint": "midground",  "max_assets": 8,  "min_assets": 2, "required": True,  "allowed_categories": ["prop", "architectural"], "facing": "inward"},
        {"zone_id": "decoration_zone", "zone_type": "decoration_zone", "label": "Ground Dressing",        "position_hint": "center",     "max_assets": 10, "min_assets": 2, "required": False, "allowed_categories": ["prop", "terrain"],       "facing": "scattered"},
        {"zone_id": "atmosphere_zone", "zone_type": "atmosphere_zone", "label": "Sky / Street Lighting",  "position_hint": "ceiling",    "max_assets": 3,  "min_assets": 0, "required": False, "allowed_categories": ["material", "hdri"],      "facing": "outward"},
        {"zone_id": "background_zone", "zone_type": "background_zone", "label": "Building Facades / Sky", "position_hint": "background", "max_assets": 6,  "min_assets": 2, "required": True,  "allowed_categories": ["architectural", "terrain"],"facing": "inward"},
    ],

    "forest": [
        {"zone_id": "entrance_zone",   "zone_type": "entrance_zone",   "label": "Forest Edge / Path",     "position_hint": "foreground", "max_assets": 3,  "min_assets": 1, "required": True,  "allowed_categories": ["terrain", "vegetation"],"facing": "camera"},
        {"zone_id": "hero_zone",       "zone_type": "hero_zone",       "label": "Ancient Tree / Clearing","position_hint": "center",     "max_assets": 3,  "min_assets": 1, "required": True,  "allowed_categories": ["terrain", "vegetation"],"facing": "camera"},
        {"zone_id": "support_zone",    "zone_type": "support_zone",    "label": "Mid-Forest Canopy",      "position_hint": "midground",  "max_assets": 8,  "min_assets": 3, "required": True,  "allowed_categories": ["terrain", "vegetation"],"facing": "scattered"},
        {"zone_id": "decoration_zone", "zone_type": "decoration_zone", "label": "Ground Cover / Roots",   "position_hint": "center",     "max_assets": 12, "min_assets": 3, "required": False, "allowed_categories": ["prop", "terrain"],       "facing": "scattered"},
        {"zone_id": "atmosphere_zone", "zone_type": "atmosphere_zone", "label": "Forest Light / Mist",    "position_hint": "ceiling",    "max_assets": 4,  "min_assets": 0, "required": False, "allowed_categories": ["material", "hdri"],      "facing": "outward"},
        {"zone_id": "background_zone", "zone_type": "background_zone", "label": "Deep Forest / Canopy",   "position_hint": "background", "max_assets": 8,  "min_assets": 2, "required": True,  "allowed_categories": ["terrain", "vegetation"],"facing": "inward"},
    ],

    "desert": [
        {"zone_id": "entrance_zone",   "zone_type": "entrance_zone",   "label": "Dune Foreground",        "position_hint": "foreground", "max_assets": 2,  "min_assets": 0, "required": False, "allowed_categories": ["terrain"],                "facing": "camera"},
        {"zone_id": "hero_zone",       "zone_type": "hero_zone",       "label": "Rock Formation / Ruins", "position_hint": "center",     "max_assets": 3,  "min_assets": 1, "required": True,  "allowed_categories": ["terrain", "architectural"],"facing": "camera"},
        {"zone_id": "support_zone",    "zone_type": "support_zone",    "label": "Dune / Cactus Field",    "position_hint": "midground",  "max_assets": 6,  "min_assets": 1, "required": True,  "allowed_categories": ["terrain", "vegetation"],"facing": "scattered"},
        {"zone_id": "decoration_zone", "zone_type": "decoration_zone", "label": "Sand / Small Rocks",     "position_hint": "center",     "max_assets": 10, "min_assets": 2, "required": False, "allowed_categories": ["prop", "terrain"],       "facing": "scattered"},
        {"zone_id": "atmosphere_zone", "zone_type": "atmosphere_zone", "label": "Harsh Sun / Heat Haze",  "position_hint": "ceiling",    "max_assets": 3,  "min_assets": 0, "required": False, "allowed_categories": ["material", "hdri"],      "facing": "outward"},
        {"zone_id": "background_zone", "zone_type": "background_zone", "label": "Horizon / Canyon Wall",  "position_hint": "background", "max_assets": 4,  "min_assets": 1, "required": False, "allowed_categories": ["terrain"],                "facing": "inward"},
    ],

    # ---- Fantasy / Historical ----

    "castle_hall": [
        {"zone_id": "entrance_zone",   "zone_type": "entrance_zone",   "label": "Great Hall Entrance",    "position_hint": "foreground", "max_assets": 3,  "min_assets": 1, "required": True,  "allowed_categories": ["architectural", "prop"], "facing": "camera"},
        {"zone_id": "hero_zone",       "zone_type": "hero_zone",       "label": "Throne / Dais",          "position_hint": "background", "max_assets": 4,  "min_assets": 1, "required": True,  "allowed_categories": ["furniture", "prop"],     "facing": "camera"},
        {"zone_id": "support_zone",    "zone_type": "support_zone",    "label": "Pillars / Long Table",   "position_hint": "midground",  "max_assets": 8,  "min_assets": 2, "required": True,  "allowed_categories": ["architectural", "furniture"],"facing": "inward"},
        {"zone_id": "decoration_zone", "zone_type": "decoration_zone", "label": "Torches / Tapestry",     "position_hint": "perimeter",  "max_assets": 10, "min_assets": 3, "required": False, "allowed_categories": ["prop"],                  "facing": "inward"},
        {"zone_id": "atmosphere_zone", "zone_type": "atmosphere_zone", "label": "Torch Fire / Smoke",     "position_hint": "ceiling",    "max_assets": 4,  "min_assets": 0, "required": False, "allowed_categories": ["material", "hdri"],      "facing": "outward"},
        {"zone_id": "background_zone", "zone_type": "background_zone", "label": "Vaulted Arch / Banner",  "position_hint": "background", "max_assets": 5,  "min_assets": 1, "required": True,  "allowed_categories": ["architectural", "prop"], "facing": "inward"},
    ],

    "survival_camp": [
        {"zone_id": "entrance_zone",   "zone_type": "entrance_zone",   "label": "Camp Perimeter Entry",   "position_hint": "foreground", "max_assets": 2,  "min_assets": 0, "required": False, "allowed_categories": ["prop", "architectural"], "facing": "camera"},
        {"zone_id": "hero_zone",       "zone_type": "hero_zone",       "label": "Fire Pit",               "position_hint": "center",     "max_assets": 3,  "min_assets": 1, "required": True,  "allowed_categories": ["prop", "structure"],     "facing": "camera"},
        {"zone_id": "support_zone",    "zone_type": "support_zone",    "label": "Shelter / Supply Cache", "position_hint": "perimeter",  "max_assets": 6,  "min_assets": 1, "required": True,  "allowed_categories": ["structure", "prop"],     "facing": "inward"},
        {"zone_id": "decoration_zone", "zone_type": "decoration_zone", "label": "Survival Props",         "position_hint": "center",     "max_assets": 10, "min_assets": 2, "required": False, "allowed_categories": ["prop"],                  "facing": "scattered"},
        {"zone_id": "atmosphere_zone", "zone_type": "atmosphere_zone", "label": "Campfire Glow / Night",  "position_hint": "ceiling",    "max_assets": 3,  "min_assets": 0, "required": False, "allowed_categories": ["material", "hdri"],      "facing": "outward"},
        {"zone_id": "background_zone", "zone_type": "background_zone", "label": "Perimeter Fence / Trees","position_hint": "background", "max_assets": 6,  "min_assets": 1, "required": False, "allowed_categories": ["structure", "terrain"],  "facing": "inward"},
    ],
}

# Fallback used for all unknown environments
_GENERIC_ZONES: List[Dict[str, Any]] = [
    {"zone_id": "entrance_zone",   "zone_type": "entrance_zone",   "label": "Entry Point",   "position_hint": "foreground", "max_assets": 3,  "min_assets": 0, "required": False, "allowed_categories": ["architectural", "prop"], "facing": "camera"},
    {"zone_id": "hero_zone",       "zone_type": "hero_zone",       "label": "Hero Focus",    "position_hint": "center",     "max_assets": 4,  "min_assets": 1, "required": True,  "allowed_categories": ["machinery", "furniture", "robot", "vehicle"], "facing": "camera"},
    {"zone_id": "support_zone",    "zone_type": "support_zone",    "label": "Support Area",  "position_hint": "midground",  "max_assets": 8,  "min_assets": 1, "required": True,  "allowed_categories": ["electronic", "structure", "prop"], "facing": "inward"},
    {"zone_id": "decoration_zone", "zone_type": "decoration_zone", "label": "Props",         "position_hint": "perimeter",  "max_assets": 10, "min_assets": 0, "required": False, "allowed_categories": ["prop", "pipe"], "facing": "scattered"},
    {"zone_id": "atmosphere_zone", "zone_type": "atmosphere_zone", "label": "Atmosphere",    "position_hint": "ceiling",    "max_assets": 3,  "min_assets": 0, "required": False, "allowed_categories": ["material", "hdri"], "facing": "outward"},
    {"zone_id": "background_zone", "zone_type": "background_zone", "label": "Background",    "position_hint": "background", "max_assets": 6,  "min_assets": 0, "required": False, "allowed_categories": ["architectural", "terrain", "structure"], "facing": "inward"},
]


def get_zone_definitions(environment_name: str) -> List[StructuralZone]:
    """Return the canonical StructuralZone list for the given environment.

    Falls back to the generic zone set for unknown environments.
    """
    raw = BUILTIN_ZONE_DEFINITIONS.get(environment_name, _GENERIC_ZONES)
    return [StructuralZone.from_dict(z) for z in raw]
