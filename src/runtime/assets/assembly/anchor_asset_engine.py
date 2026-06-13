"""
Anchor Asset Engine (Tier 9.5 — Structural Environment Assembly)
================================================================
Determines the major focal elements (anchors) for an environment and assigns
them to zones. Anchor assets define the scene's identity — they are the
elements a viewer immediately associates with the environment type.

Anchor hierarchy:
  - primary_anchor : single most important element (e.g. throne in castle_hall)
  - secondary_anchors: 1–3 additional focal elements
  - Each anchor has a zone assignment, position hint, and a list of supported
    child asset types that should be placed near or on the anchor.

DESIGN RULES:
  1. No bridge calls. No Houdini imports. Planning only.
  2. Anchor selection is deterministic — same environment always yields the
     same anchor plan regardless of available assets.
  3. Semantic relationships (chair belongs_near table) are encoded here
     so the decorative population engine can reference them.
  4. Never raises — errors captured in AnchorPlan.errors.

Public API:
    AnchorAsset
    AnchorPlan
    AnchorAssetEngine
    get_anchor_asset_engine()
    reset_anchor_asset_engine_for_tests()
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.runtime.assets.assembly.architectural_templates import get_architectural_templates
from src.runtime.assets.assembly.environment_zones import get_zone_definitions


# ---------------------------------------------------------------------------
# Semantic "belongs near / belongs on" relationships
# ---------------------------------------------------------------------------

SEMANTIC_RELATIONSHIPS: Dict[str, Dict[str, Any]] = {
    # asset_type → {"belongs_near": [...], "belongs_on": [...], "min_dist": float, "max_dist": float}
    "chair":          {"belongs_near": ["table", "bar_counter", "gambling_table", "dining_table", "desk"], "belongs_on": [],             "min_dist": 0.3, "max_dist": 1.2},
    "stool":          {"belongs_near": ["bar_counter", "table"],                                            "belongs_on": [],             "min_dist": 0.3, "max_dist": 0.8},
    "cup":            {"belongs_near": [],                                                                   "belongs_on": ["table", "bar_counter", "desk", "workbench"], "min_dist": 0.0, "max_dist": 0.0},
    "bottle":         {"belongs_near": [],                                                                   "belongs_on": ["table", "bar_counter", "shelf"],             "min_dist": 0.0, "max_dist": 0.0},
    "lantern":        {"belongs_near": [],                                                                   "belongs_on": ["table", "wall", "ceiling", "bar_counter"],   "min_dist": 0.0, "max_dist": 0.0},
    "bucket":         {"belongs_near": ["wall", "corner"],                                                  "belongs_on": [],             "min_dist": 0.1, "max_dist": 2.0},
    "barrel":         {"belongs_near": ["wall", "corner"],                                                  "belongs_on": [],             "min_dist": 0.1, "max_dist": 2.0},
    "book":           {"belongs_near": [],                                                                   "belongs_on": ["shelf", "table", "desk"],                    "min_dist": 0.0, "max_dist": 0.0},
    "flask":          {"belongs_near": [],                                                                   "belongs_on": ["lab_bench", "workbench", "table"],           "min_dist": 0.0, "max_dist": 0.0},
    "notebook":       {"belongs_near": [],                                                                   "belongs_on": ["desk", "workbench", "table"],                "min_dist": 0.0, "max_dist": 0.0},
    "electronic_component": {"belongs_near": [], "belongs_on": ["workbench", "server_rack", "equipment_bay"], "min_dist": 0.0, "max_dist": 0.0},
    "mug":            {"belongs_near": [],                                                                   "belongs_on": ["desk", "table", "bar_counter"],              "min_dist": 0.0, "max_dist": 0.0},
    "candle":         {"belongs_near": [],                                                                   "belongs_on": ["table", "candle_stand", "shelf"],            "min_dist": 0.0, "max_dist": 0.0},
    "torch":          {"belongs_near": [],                                                                   "belongs_on": ["wall", "torch_bracket", "pillar"],           "min_dist": 0.0, "max_dist": 0.0},
    "skull":          {"belongs_near": ["wall", "corner"],                                                  "belongs_on": ["shelf", "altar"],                            "min_dist": 0.0, "max_dist": 1.0},
    "plant":          {"belongs_near": ["wall", "corner"],                                                  "belongs_on": [],                                            "min_dist": 0.1, "max_dist": 1.5},
    "tool_kit":       {"belongs_near": [],                                                                   "belongs_on": ["workbench", "table", "equipment_bay"],       "min_dist": 0.0, "max_dist": 0.0},
    "pipe":           {"belongs_near": ["wall"],                                                             "belongs_on": [],                                            "min_dist": 0.1, "max_dist": 3.0},
    "cable_bundle":   {"belongs_near": ["server_rack", "console", "workbench"],                             "belongs_on": [],                                            "min_dist": 0.1, "max_dist": 2.0},
    "fire_extinguisher": {"belongs_near": ["wall"],                                                          "belongs_on": [],                                            "min_dist": 0.1, "max_dist": 1.0},
    "medical_tool":   {"belongs_near": [],                                                                   "belongs_on": ["medical_cabinet", "operating_table"],        "min_dist": 0.0, "max_dist": 0.0},
    "ration_pack":    {"belongs_near": [],                                                                   "belongs_on": ["crate_stack", "supply_cache"],               "min_dist": 0.0, "max_dist": 0.0},
    "lantern_camp":   {"belongs_near": ["fire_pit", "shelter"],                                              "belongs_on": [],                                            "min_dist": 0.3, "max_dist": 3.0},
    "mushroom":       {"belongs_near": ["tree", "fallen_log", "rock"],                                       "belongs_on": [],                                            "min_dist": 0.1, "max_dist": 2.0},
    "debris":         {"belongs_near": ["wall", "column", "rubble_pile"],                                    "belongs_on": [],                                            "min_dist": 0.0, "max_dist": 5.0},
}


# ---------------------------------------------------------------------------
# Per-environment anchor definitions
# ---------------------------------------------------------------------------

_ANCHOR_DEFS: Dict[str, List[Dict[str, Any]]] = {
    # Each entry: {asset_type, zone, position_hint, is_primary, supports_types, description}

    "western_room": [
        {"asset_type": "table",       "zone": "hero_zone",    "position_hint": "center",     "is_primary": True,  "supports_types": ["chair", "cup", "bottle", "lantern"],         "description": "Main dining table — chairs gather around it"},
        {"asset_type": "bar_counter", "zone": "support_zone", "position_hint": "background", "is_primary": False, "supports_types": ["stool", "bottle", "cup", "barrel"],           "description": "Bar counter along back wall"},
        {"asset_type": "fireplace",   "zone": "support_zone", "position_hint": "side_wall",  "is_primary": False, "supports_types": ["lantern", "bucket"],                          "description": "Fireplace provides warmth and ambient light"},
    ],
    "saloon": [
        {"asset_type": "bar_counter",    "zone": "hero_zone",    "position_hint": "background", "is_primary": True,  "supports_types": ["stool", "bottle", "glass", "lantern"],       "description": "Bar counter — the social anchor of the saloon"},
        {"asset_type": "gambling_table", "zone": "support_zone", "position_hint": "center",     "is_primary": False, "supports_types": ["chair", "cup", "bottle"],                    "description": "Gambling table with chairs"},
        {"asset_type": "stage",          "zone": "background_zone","position_hint": "far_wall", "is_primary": False, "supports_types": ["lantern"],                                   "description": "Performance stage at the back"},
    ],
    "living_room": [
        {"asset_type": "sofa",         "zone": "hero_zone",    "position_hint": "center",     "is_primary": True,  "supports_types": ["cushion", "remote"],                          "description": "Main sofa facing the television"},
        {"asset_type": "coffee_table", "zone": "hero_zone",    "position_hint": "center_low", "is_primary": False, "supports_types": ["book", "vase", "mug", "remote"],             "description": "Coffee table in front of sofa"},
        {"asset_type": "television",   "zone": "support_zone", "position_hint": "background", "is_primary": False, "supports_types": [],                                            "description": "Television / entertainment unit"},
    ],
    "office": [
        {"asset_type": "desk",         "zone": "hero_zone",    "position_hint": "center",     "is_primary": True,  "supports_types": ["computer", "book", "mug", "notebook", "pen_holder"], "description": "Primary work desk"},
        {"asset_type": "office_chair", "zone": "hero_zone",    "position_hint": "behind_desk","is_primary": False, "supports_types": [],                                            "description": "Desk chair"},
        {"asset_type": "bookcase",     "zone": "support_zone", "position_hint": "side_wall",  "is_primary": False, "supports_types": ["book", "plant"],                             "description": "Bookcase along wall"},
    ],
    "hotel_lobby": [
        {"asset_type": "reception_desk", "zone": "hero_zone",    "position_hint": "center_back","is_primary": True, "supports_types": ["computer", "vase", "brochure_stand"],         "description": "Main reception desk — first point of contact"},
        {"asset_type": "seating_group",  "zone": "hero_zone",    "position_hint": "center",     "is_primary": False,"supports_types": ["sofa", "armchair", "lamp"],                   "description": "Lobby seating arrangement"},
        {"asset_type": "staircase",      "zone": "background_zone","position_hint": "background","is_primary": False,"supports_types": [],                                            "description": "Grand staircase as architectural focal point"},
    ],
    "restaurant": [
        {"asset_type": "hero_dining_table","zone": "hero_zone", "position_hint": "center",     "is_primary": True,  "supports_types": ["dining_chair", "candle", "flower_arrangement", "tablecloth"], "description": "Feature dining table at scene centre"},
        {"asset_type": "kitchen_pass",    "zone": "support_zone","position_hint": "background","is_primary": False, "supports_types": ["plate_stack"],                               "description": "Kitchen pass window"},
        {"asset_type": "host_stand",      "zone": "entrance_zone","position_hint": "foreground","is_primary": False,"supports_types": ["menu_card"],                                 "description": "Host stand at entrance"},
    ],
    "library": [
        {"asset_type": "bookshelf_wall",  "zone": "support_zone","position_hint": "perimeter", "is_primary": True,  "supports_types": ["book", "step_ladder"],                       "description": "Wall-to-wall bookshelves — the defining element"},
        {"asset_type": "reading_table",   "zone": "hero_zone",   "position_hint": "center",    "is_primary": False, "supports_types": ["book", "reading_lamp", "globe"],             "description": "Reading table at room centre"},
        {"asset_type": "librarian_desk",  "zone": "entrance_zone","position_hint": "near_entry","is_primary": False,"supports_types": ["book", "catalogue"],                         "description": "Librarian's desk near entry"},
    ],
    "industrial_hangar": [
        {"asset_type": "main_machine",       "zone": "hero_zone",   "position_hint": "center",    "is_primary": True,  "supports_types": ["pipe", "toolbox", "barrel"],               "description": "Primary industrial machine — the scene's identity"},
        {"asset_type": "crane",              "zone": "hero_zone",   "position_hint": "overhead",  "is_primary": False, "supports_types": ["chain", "hook"],                           "description": "Overhead crane spanning the hangar"},
        {"asset_type": "industrial_furnace", "zone": "support_zone","position_hint": "background","is_primary": False, "supports_types": ["pipe", "barrel"],                          "description": "Industrial furnace or smelter"},
    ],
    "warehouse": [
        {"asset_type": "shelving_rack",   "zone": "hero_zone",    "position_hint": "center",    "is_primary": True,  "supports_types": ["cardboard_box", "barrel"],                  "description": "Primary shelving rack — defines the warehouse"},
        {"asset_type": "pallet_stack",    "zone": "support_zone", "position_hint": "midground", "is_primary": False, "supports_types": ["cardboard_box", "barrel"],                  "description": "Pallet stacks around the floor"},
        {"asset_type": "forklift",        "zone": "support_zone", "position_hint": "aisle",     "is_primary": False, "supports_types": [],                                           "description": "Forklift parked in aisle"},
    ],
    "abandoned_factory": [
        {"asset_type": "broken_machine",    "zone": "hero_zone",   "position_hint": "center",   "is_primary": True,  "supports_types": ["rubble", "pipe"],                           "description": "Collapsed or rusted main machine"},
        {"asset_type": "rusted_crane",      "zone": "hero_zone",   "position_hint": "overhead", "is_primary": False, "supports_types": ["chain"],                                    "description": "Rusted overhead crane"},
        {"asset_type": "collapsed_conveyor","zone": "support_zone","position_hint": "midground","is_primary": False,  "supports_types": ["debris", "rubble"],                         "description": "Collapsed conveyor belt"},
    ],
    "robotics_lab": [
        {"asset_type": "robot_platform",   "zone": "hero_zone",   "position_hint": "center",   "is_primary": True,  "supports_types": ["cable_bundle", "electronic_component"],      "description": "Central robot testing platform"},
        {"asset_type": "research_console", "zone": "hero_zone",   "position_hint": "foreground","is_primary": False, "supports_types": ["notebook", "mug"],                           "description": "Operator research console"},
        {"asset_type": "testing_rig",      "zone": "support_zone","position_hint": "background","is_primary": False, "supports_types": ["cable_bundle"],                             "description": "Secondary testing rig"},
    ],
    "research_lab": [
        {"asset_type": "central_lab_bench", "zone": "hero_zone",  "position_hint": "center",   "is_primary": True,  "supports_types": ["flask", "notebook", "specimen_jar"],         "description": "Central research bench — primary work surface"},
        {"asset_type": "server_cluster",    "zone": "support_zone","position_hint": "background","is_primary": False,"supports_types": ["cable_bundle"],                              "description": "Server cluster for data processing"},
        {"asset_type": "imaging_equipment", "zone": "support_zone","position_hint": "side",    "is_primary": False, "supports_types": ["cable_bundle"],                              "description": "Scientific imaging equipment"},
    ],
    "medical_lab": [
        {"asset_type": "operating_table",  "zone": "hero_zone",   "position_hint": "center",   "is_primary": True,  "supports_types": ["medical_tool", "iv_stand", "surgical_light"],"description": "Operating table — the medical focal point"},
        {"asset_type": "medical_scanner",  "zone": "support_zone","position_hint": "side",     "is_primary": False, "supports_types": ["cable_bundle"],                              "description": "Imaging scanner beside operating table"},
        {"asset_type": "patient_monitor",  "zone": "hero_zone",   "position_hint": "near_table","is_primary": False,"supports_types": [],                                             "description": "Patient monitoring equipment"},
    ],
    "control_room": [
        {"asset_type": "main_console_bank", "zone": "hero_zone",  "position_hint": "center",   "is_primary": True,  "supports_types": ["status_indicator_light", "mug", "notepad"], "description": "Main operator console bank"},
        {"asset_type": "large_screen_array","zone": "background_zone","position_hint": "back_wall","is_primary": False,"supports_types": [],                                          "description": "Large display wall"},
        {"asset_type": "command_chair",     "zone": "hero_zone",  "position_hint": "center_back","is_primary": False,"supports_types": [],                                            "description": "Command chair in front of main console"},
    ],
    "sci_fi_corridor": [
        {"asset_type": "electronic_terminal","zone": "hero_zone", "position_hint": "center",   "is_primary": True,  "supports_types": ["cable_bundle", "hologram_emitter"],          "description": "Primary electronic terminal in corridor"},
        {"asset_type": "airlock_control",    "zone": "entrance_zone","position_hint": "near_door","is_primary": False,"supports_types": ["warning_light"],                            "description": "Airlock control panel"},
        {"asset_type": "security_panel",     "zone": "support_zone","position_hint": "side_wall","is_primary": False,"supports_types": ["warning_light"],                            "description": "Security identification panel"},
    ],
    "space_station": [
        {"asset_type": "navigation_console", "zone": "hero_zone", "position_hint": "center",   "is_primary": True,  "supports_types": ["status_indicator_light", "tool_kit"],        "description": "Navigation and command console"},
        {"asset_type": "command_interface",  "zone": "hero_zone", "position_hint": "foreground","is_primary": False, "supports_types": [],                                            "description": "Primary command interface"},
        {"asset_type": "life_support_unit",  "zone": "support_zone","position_hint": "perimeter","is_primary": False,"supports_types": ["cable_bundle"],                             "description": "Life support systems unit"},
    ],
    "city_street": [
        {"asset_type": "hero_building_entrance","zone": "hero_zone","position_hint": "center",  "is_primary": True,  "supports_types": ["prop"],                                      "description": "Main building entrance — camera target"},
        {"asset_type": "street_lamp_cluster",   "zone": "support_zone","position_hint": "midground","is_primary": False,"supports_types": [],                                         "description": "Street lamp cluster"},
        {"asset_type": "bus_stop",              "zone": "support_zone","position_hint": "foreground_side","is_primary": False,"supports_types": ["bench"],                            "description": "Bus stop with bench"},
    ],
    "forest": [
        {"asset_type": "ancient_tree",    "zone": "hero_zone",   "position_hint": "center",   "is_primary": True,  "supports_types": ["mushroom", "moss_patch"],                     "description": "Ancient tree — the defining spatial anchor"},
        {"asset_type": "rock_formation",  "zone": "hero_zone",   "position_hint": "foreground","is_primary": False, "supports_types": ["moss_patch", "fern"],                        "description": "Rock formation at focal area"},
        {"asset_type": "fallen_log",      "zone": "support_zone","position_hint": "midground", "is_primary": False, "supports_types": ["mushroom", "moss_patch"],                    "description": "Fallen log across scene midground"},
    ],
    "desert": [
        {"asset_type": "rock_formation",  "zone": "hero_zone",   "position_hint": "center",   "is_primary": True,  "supports_types": ["small_rock", "bleached_bone"],                "description": "Rock formation — only hard anchor in desert"},
        {"asset_type": "ancient_ruin",    "zone": "hero_zone",   "position_hint": "background","is_primary": False, "supports_types": ["weathered_artifact"],                        "description": "Ancient ruins providing history"},
        {"asset_type": "cactus_cluster",  "zone": "support_zone","position_hint": "midground", "is_primary": False, "supports_types": [],                                            "description": "Cactus cluster for scale reference"},
    ],
    "castle_hall": [
        {"asset_type": "throne",         "zone": "hero_zone",   "position_hint": "dais_center","is_primary": True,  "supports_types": ["goblet", "scroll"],                         "description": "Throne on raised dais — ceremonial focal point"},
        {"asset_type": "main_fireplace", "zone": "support_zone","position_hint": "side_wall",  "is_primary": False, "supports_types": ["torch", "lantern"],                         "description": "Grand fireplace providing warmth and drama"},
        {"asset_type": "banner_display", "zone": "background_zone","position_hint": "back_wall","is_primary": False,"supports_types": [],                                            "description": "Heraldic banners on the walls"},
    ],
    "survival_camp": [
        {"asset_type": "fire_pit",      "zone": "hero_zone",   "position_hint": "center",   "is_primary": True,  "supports_types": ["lantern_camp", "tin_can", "ration_pack"],     "description": "Central fire pit — camp social anchor"},
        {"asset_type": "main_shelter",  "zone": "support_zone","position_hint": "background","is_primary": False, "supports_types": ["sleeping_bag_roll"],                         "description": "Main sleeping shelter"},
        {"asset_type": "supply_cache",  "zone": "support_zone","position_hint": "perimeter", "is_primary": False, "supports_types": ["crate_stack", "ration_pack"],                "description": "Stockpile of supplies"},
    ],
    "dungeon": [
        {"asset_type": "prison_cell_block","zone": "hero_zone",  "position_hint": "background","is_primary": True,  "supports_types": ["manacle", "skull", "bucket"],              "description": "Prison cells — the environment's defining purpose"},
        {"asset_type": "torture_rack",    "zone": "support_zone","position_hint": "center",   "is_primary": False, "supports_types": ["chain"],                                    "description": "Torture device at scene centre"},
        {"asset_type": "stone_altar",     "zone": "support_zone","position_hint": "side",     "is_primary": False, "supports_types": ["skull", "torch"],                           "description": "Stone altar for dark ritual suggestion"},
    ],
}

# Fallback for unknown environments
_GENERIC_ANCHORS: List[Dict[str, Any]] = [
    {"asset_type": "main_prop",  "zone": "hero_zone", "position_hint": "center",    "is_primary": True,  "supports_types": [],        "description": "Primary scene prop"},
    {"asset_type": "secondary",  "zone": "support_zone","position_hint": "midground","is_primary": False, "supports_types": [],        "description": "Secondary supporting element"},
]


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class AnchorAsset:
    """A major focal element within an environment zone."""

    anchor_id:    str = field(default_factory=lambda: f"anc_{uuid.uuid4().hex[:8]}")
    asset_type:   str = ""
    zone:         str = ""
    position_hint: str = ""
    is_primary:   bool = False
    supports_types: List[str] = field(default_factory=list)
    description:  str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "anchor_id":      self.anchor_id,
            "asset_type":     self.asset_type,
            "zone":           self.zone,
            "position_hint":  self.position_hint,
            "is_primary":     self.is_primary,
            "supports_types": list(self.supports_types),
            "description":    self.description,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AnchorAsset":
        return cls(
            anchor_id      = str(d.get("anchor_id", f"anc_{uuid.uuid4().hex[:8]}")),
            asset_type     = str(d.get("asset_type", "")),
            zone           = str(d.get("zone", "")),
            position_hint  = str(d.get("position_hint", "")),
            is_primary     = bool(d.get("is_primary", False)),
            supports_types = list(d.get("supports_types", [])),
            description    = str(d.get("description", "")),
        )


@dataclass
class AnchorPlan:
    """The complete anchor asset plan for an environment."""

    plan_id:         str = field(default_factory=lambda: f"ancp_{uuid.uuid4().hex[:10]}")
    environment_name: str = ""
    anchors:         List[AnchorAsset] = field(default_factory=list)
    primary_anchor:  Optional[AnchorAsset] = None
    errors:          List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id":          self.plan_id,
            "environment_name": self.environment_name,
            "anchors":          [a.to_dict() for a in self.anchors],
            "primary_anchor":   self.primary_anchor.to_dict() if self.primary_anchor else None,
            "errors":           list(self.errors),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AnchorPlan":
        anchors = [AnchorAsset.from_dict(a) for a in d.get("anchors", [])]
        pa_raw = d.get("primary_anchor")
        primary = AnchorAsset.from_dict(pa_raw) if pa_raw else None
        return cls(
            plan_id          = str(d.get("plan_id", f"ancp_{uuid.uuid4().hex[:10]}")),
            environment_name = str(d.get("environment_name", "")),
            anchors          = anchors,
            primary_anchor   = primary,
            errors           = list(d.get("errors", [])),
        )


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class AnchorAssetEngine:
    """Determines anchor asset plans for environment types.

    Never raises. Falls back to generic anchors for unknown environments.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def get_anchor_plan(self, environment_name: str) -> AnchorPlan:
        """Return the AnchorPlan for the given environment.

        Args:
            environment_name: canonical environment name.

        Returns:
            AnchorPlan with anchors, primary_anchor, and zone assignments.
        """
        try:
            return self._build_plan(environment_name)
        except Exception as exc:
            return AnchorPlan(
                environment_name = environment_name,
                errors = [f"Anchor plan build failed: {exc}"],
            )

    def _build_plan(self, environment_name: str) -> AnchorPlan:
        raw_defs = _ANCHOR_DEFS.get(environment_name, _GENERIC_ANCHORS)

        anchors: List[AnchorAsset] = []
        primary: Optional[AnchorAsset] = None
        errors: List[str] = []

        for d in raw_defs:
            anchor = AnchorAsset(
                asset_type    = str(d.get("asset_type", "")),
                zone          = str(d.get("zone", "hero_zone")),
                position_hint = str(d.get("position_hint", "center")),
                is_primary    = bool(d.get("is_primary", False)),
                supports_types = list(d.get("supports_types", [])),
                description   = str(d.get("description", "")),
            )
            anchors.append(anchor)
            if anchor.is_primary and primary is None:
                primary = anchor

        if not anchors:
            errors.append(f"No anchor definitions found for environment '{environment_name}'.")

        if anchors and primary is None:
            # Promote the first anchor to primary if none was flagged
            anchors[0] = AnchorAsset(
                anchor_id     = anchors[0].anchor_id,
                asset_type    = anchors[0].asset_type,
                zone          = anchors[0].zone,
                position_hint = anchors[0].position_hint,
                is_primary    = True,
                supports_types = anchors[0].supports_types,
                description   = anchors[0].description,
            )
            primary = anchors[0]

        return AnchorPlan(
            environment_name = environment_name,
            anchors          = anchors,
            primary_anchor   = primary,
            errors           = errors,
        )

    def get_semantic_relationship(self, asset_type: str) -> Dict[str, Any]:
        """Return the semantic placement relationship for a given asset type.

        Returns a dict with keys: belongs_near, belongs_on, min_dist, max_dist.
        Returns empty lists / 0.0 if no relationship is defined.
        """
        default: Dict[str, Any] = {
            "belongs_near": [], "belongs_on": [],
            "min_dist": 0.3,    "max_dist": 2.0,
        }
        return dict(SEMANTIC_RELATIONSHIPS.get(asset_type, default))

    def get_children_for_anchor(self, environment_name: str, anchor_type: str) -> List[str]:
        """Return the list of asset types that should be placed near/on the given anchor."""
        plan = self.get_anchor_plan(environment_name)
        for anchor in plan.anchors:
            if anchor.asset_type == anchor_type:
                return list(anchor.supports_types)
        return []


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[AnchorAssetEngine] = None
_LOCK = threading.Lock()


def get_anchor_asset_engine() -> AnchorAssetEngine:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = AnchorAssetEngine()
        return _INSTANCE


def reset_anchor_asset_engine_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
