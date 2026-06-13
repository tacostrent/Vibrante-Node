"""
Anchor Asset Builder (§44 — Structural Environment Assembly)
============================================================
Determines the major focal anchor assets for an environment and assigns them
to zones. Anchors define the scene's identity — the elements a viewer
immediately associates with the environment type.

DESIGN RULES:
  1. No bridge calls. No Houdini imports. Planning only.
  2. Deterministic — same environment always yields the same anchor plan.
  3. Semantic child relationships encoded per anchor type.
  4. Never raises — errors captured in AnchorPlan.errors.
  5. Singleton pattern.
  6. Thread-safe.

Public API:
    PlacedAnchor
    AnchorPlan
    AnchorAssetBuilder
    get_anchor_asset_builder()
    reset_anchor_asset_builder_for_tests()
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.runtime.environment.environment_blueprint import EnvironmentBlueprint
from src.runtime.environment.environment_template_library import get_environment_template_library


# ---------------------------------------------------------------------------
# Child type table (what props belong on/near each anchor)
# ---------------------------------------------------------------------------

_ANCHOR_CHILDREN: Dict[str, List[str]] = {
    "main_table":         ["chair", "cup", "bottle", "lantern", "candle"],
    "long_table":         ["chair", "cup", "bottle", "lantern", "candle", "goblet"],
    "main_table_cluster": ["chair", "wine_glass", "candle", "menu", "napkin_holder"],
    "fireplace":          ["log_pile", "iron_poker", "iron_pot"],
    "large_cabinet":      ["bottle", "book", "lantern"],
    "bar_counter":        ["stool", "bottle", "glass", "barrel"],
    "stage_area":         ["microphone_stand", "spotlight"],
    "sofa":               ["coffee_table", "cushion", "side_lamp"],
    "coffee_table":       ["book", "mug", "remote_control"],
    "bookshelf":          ["book", "bookend", "study_lamp"],
    "bookshelf_row":      ["book", "bookend", "study_lamp"],
    "main_desk":          ["monitor", "document", "mug", "pen_holder"],
    "whiteboard":         ["marker", "eraser"],
    "shelving_unit":      ["filing_box", "document", "binder"],
    "reception_desk":     ["computer", "bell", "plant", "signage"],
    "seating_cluster":    ["sofa", "plant", "lamp"],
    "decorative_column":  ["plant", "signage"],
    "service_station":    ["tray", "condiment", "napkin_holder"],
    "catalogue_desk":     ["computer", "document", "mug"],
    "reading_table":      ["book", "lamp", "glasses"],
    "pallet_stack":       ["pallet", "crate", "barrel"],
    "storage_shelf":      ["crate", "box", "barrel"],
    "loading_area":       ["forklift", "trolley", "pallet"],
    "hero_machine":       ["pipe", "control_panel", "bucket", "oil_drum"],
    "crane":              ["hook", "cable_bundle", "safety_sign"],
    "industrial_furnace": ["coal_pile", "pipe", "valve"],
    "rusted_machine":     ["debris", "rust_pipe", "bucket"],
    "debris_pile":        ["broken_barrel", "dust_pile"],
    "old_conveyor":       ["debris", "rust_pipe"],
    "main_robot_station": ["cable_bundle", "electronic_component", "monitor"],
    "workbench":          ["tool", "clamp", "parts_container", "lamp"],
    "equipment_rack":     ["cable_bundle", "status_light", "electronic_component"],
    "master_console":     ["monitor", "keyboard", "mug"],
    "operations_desk":    ["monitor", "document", "headset"],
    "display_wall":       ["monitor", "status_light"],
    "examination_table":  ["syringe", "medical_tool", "specimen_jar"],
    "medical_equipment":  ["flask", "medical_tool", "data_pad"],
    "specimen_storage":   ["specimen_jar", "label", "glove"],
    "central_workbench":  ["flask", "notebook", "chemical_jar"],
    "analysis_station":   ["microscope", "data_pad", "flask"],
    "chemical_storage":   ["chemical_jar", "safety_goggles", "label"],
    "control_panel":      ["data_pad", "status_light", "cable_bundle"],
    "equipment_bay":      ["cable_bundle", "electronic_component", "fire_extinguisher"],
    "airlock_door":       ["status_light", "data_pad"],
    "street_lamp_cluster":["bench", "trash_can"],
    "shop_front":         ["sign", "display_item", "planter"],
    "bus_stop":           ["bench", "timetable_sign", "trash_can"],
    "ancient_tree":       ["mushroom", "ivy", "small_rock"],
    "fallen_log":         ["mushroom", "fern", "small_rock"],
    "rocky_outcrop":      ["small_rock", "moss", "fern"],
    "rock_formation":     ["cactus", "sand_drift", "small_rock"],
    "ruined_structure":   ["debris", "small_rock", "sand_drift"],
    "dead_tree":          ["tumbleweed", "bleached_bone"],
    "throne":             ["banner", "candle_holder", "footstool"],
    "fireplace_castle":   ["iron_poker", "log_pile", "torch"],
    "camp_fire":          ["log", "bedroll", "cooking_pot", "lantern"],
    "supply_crate_stack": ["ration_pack", "rope_coil", "bedroll"],
    "sleeping_area":      ["bedroll", "lantern_camp", "water_canteen"],
}


# ---------------------------------------------------------------------------
# Per-environment anchor definitions
# ---------------------------------------------------------------------------

_ANCHOR_DEFS: Dict[str, List[Dict[str, Any]]] = {
    "western_room":     [
        {"anchor_type": "main_table",    "zone_type": "hero_zone",    "position_hint": "center",        "priority": 1, "display_name": "Main Dining Table"},
        {"anchor_type": "fireplace",     "zone_type": "wall_zone",    "position_hint": "wall_adjacent",  "priority": 2, "display_name": "Stone Fireplace"},
        {"anchor_type": "large_cabinet", "zone_type": "wall_zone",    "position_hint": "wall_adjacent",  "priority": 3, "display_name": "Large Cabinet"},
    ],
    "saloon":           [
        {"anchor_type": "bar_counter",   "zone_type": "service_zone", "position_hint": "background",    "priority": 1, "display_name": "Bar Counter"},
        {"anchor_type": "main_table",    "zone_type": "hero_zone",    "position_hint": "center",        "priority": 2, "display_name": "Main Table"},
        {"anchor_type": "stage_area",    "zone_type": "support_zone", "position_hint": "side",          "priority": 3, "display_name": "Stage Area"},
    ],
    "living_room":      [
        {"anchor_type": "sofa",          "zone_type": "hero_zone",    "position_hint": "center",        "priority": 1, "display_name": "Main Sofa"},
        {"anchor_type": "coffee_table",  "zone_type": "hero_zone",    "position_hint": "center",        "priority": 2, "display_name": "Coffee Table"},
        {"anchor_type": "bookshelf",     "zone_type": "wall_zone",    "position_hint": "wall_adjacent",  "priority": 3, "display_name": "Bookshelf"},
    ],
    "office":           [
        {"anchor_type": "main_desk",     "zone_type": "hero_zone",    "position_hint": "center",        "priority": 1, "display_name": "Main Desk"},
        {"anchor_type": "whiteboard",    "zone_type": "support_zone", "position_hint": "wall_adjacent",  "priority": 2, "display_name": "Whiteboard"},
        {"anchor_type": "shelving_unit", "zone_type": "wall_zone",    "position_hint": "perimeter",     "priority": 3, "display_name": "Shelving Unit"},
    ],
    "hotel_lobby":      [
        {"anchor_type": "reception_desk",      "zone_type": "hero_zone",    "position_hint": "center",    "priority": 1, "display_name": "Reception Desk"},
        {"anchor_type": "seating_cluster",     "zone_type": "seating_zone", "position_hint": "midground", "priority": 2, "display_name": "Seating Cluster"},
        {"anchor_type": "decorative_column",   "zone_type": "decoration_zone", "position_hint": "perimeter", "priority": 3, "display_name": "Decorative Column"},
    ],
    "restaurant":       [
        {"anchor_type": "main_table_cluster",  "zone_type": "hero_zone",    "position_hint": "center",    "priority": 1, "display_name": "Main Table Cluster"},
        {"anchor_type": "bar_counter",         "zone_type": "service_zone", "position_hint": "background","priority": 2, "display_name": "Bar Counter"},
        {"anchor_type": "service_station",     "zone_type": "support_zone", "position_hint": "side",      "priority": 3, "display_name": "Service Station"},
    ],
    "library":          [
        {"anchor_type": "bookshelf_row",  "zone_type": "hero_zone",    "position_hint": "perimeter",    "priority": 1, "display_name": "Bookshelf Row"},
        {"anchor_type": "reading_table",  "zone_type": "seating_zone", "position_hint": "center",       "priority": 2, "display_name": "Reading Table"},
        {"anchor_type": "catalogue_desk", "zone_type": "service_zone", "position_hint": "entrance",     "priority": 3, "display_name": "Catalogue Desk"},
    ],
    "warehouse":        [
        {"anchor_type": "pallet_stack",  "zone_type": "hero_zone",    "position_hint": "center",        "priority": 1, "display_name": "Pallet Stack"},
        {"anchor_type": "storage_shelf", "zone_type": "support_zone", "position_hint": "perimeter",     "priority": 2, "display_name": "Storage Shelf"},
        {"anchor_type": "loading_area",  "zone_type": "entrance_zone", "position_hint": "foreground",   "priority": 3, "display_name": "Loading Area"},
    ],
    "industrial_hangar":[
        {"anchor_type": "hero_machine",      "zone_type": "hero_zone",    "position_hint": "center",    "priority": 1, "display_name": "Hero Machine"},
        {"anchor_type": "crane",             "zone_type": "hero_zone",    "position_hint": "overhead",  "priority": 2, "display_name": "Overhead Crane"},
        {"anchor_type": "industrial_furnace","zone_type": "support_zone", "position_hint": "background","priority": 3, "display_name": "Industrial Furnace"},
    ],
    "abandoned_factory":[
        {"anchor_type": "rusted_machine", "zone_type": "hero_zone",    "position_hint": "center",       "priority": 1, "display_name": "Rusted Machine"},
        {"anchor_type": "debris_pile",    "zone_type": "support_zone", "position_hint": "scattered",    "priority": 2, "display_name": "Debris Pile"},
        {"anchor_type": "old_conveyor",   "zone_type": "background_zone", "position_hint": "background","priority": 3, "display_name": "Old Conveyor Belt"},
    ],
    "robotics_lab":     [
        {"anchor_type": "main_robot_station", "zone_type": "hero_zone",    "position_hint": "center",   "priority": 1, "display_name": "Robot Station"},
        {"anchor_type": "workbench",          "zone_type": "support_zone", "position_hint": "perimeter","priority": 2, "display_name": "Workbench"},
        {"anchor_type": "equipment_rack",     "zone_type": "wall_zone",    "position_hint": "perimeter","priority": 3, "display_name": "Equipment Rack"},
    ],
    "control_room":     [
        {"anchor_type": "master_console",  "zone_type": "hero_zone",    "position_hint": "center",      "priority": 1, "display_name": "Master Console"},
        {"anchor_type": "operations_desk", "zone_type": "support_zone", "position_hint": "midground",   "priority": 2, "display_name": "Operations Desk"},
        {"anchor_type": "display_wall",    "zone_type": "background_zone", "position_hint": "background","priority": 3, "display_name": "Display Wall"},
    ],
    "medical_lab":      [
        {"anchor_type": "examination_table", "zone_type": "hero_zone",    "position_hint": "center",    "priority": 1, "display_name": "Examination Table"},
        {"anchor_type": "medical_equipment", "zone_type": "support_zone", "position_hint": "perimeter", "priority": 2, "display_name": "Medical Equipment"},
        {"anchor_type": "specimen_storage",  "zone_type": "wall_zone",    "position_hint": "perimeter", "priority": 3, "display_name": "Specimen Storage"},
    ],
    "research_lab":     [
        {"anchor_type": "central_workbench", "zone_type": "hero_zone",    "position_hint": "center",    "priority": 1, "display_name": "Central Workbench"},
        {"anchor_type": "analysis_station",  "zone_type": "support_zone", "position_hint": "midground", "priority": 2, "display_name": "Analysis Station"},
        {"anchor_type": "chemical_storage",  "zone_type": "wall_zone",    "position_hint": "perimeter", "priority": 3, "display_name": "Chemical Storage"},
    ],
    "sci_fi_corridor":  [
        {"anchor_type": "control_panel",  "zone_type": "hero_zone",    "position_hint": "wall_adjacent","priority": 1, "display_name": "Control Panel"},
        {"anchor_type": "equipment_bay",  "zone_type": "support_zone", "position_hint": "perimeter",   "priority": 2, "display_name": "Equipment Bay"},
        {"anchor_type": "airlock_door",   "zone_type": "entrance_zone","position_hint": "foreground",  "priority": 3, "display_name": "Airlock Door"},
    ],
    "city_street":      [
        {"anchor_type": "street_lamp_cluster", "zone_type": "hero_zone",    "position_hint": "center",   "priority": 1, "display_name": "Street Lamps"},
        {"anchor_type": "shop_front",          "zone_type": "background_zone", "position_hint": "background", "priority": 2, "display_name": "Shop Front"},
        {"anchor_type": "bus_stop",            "zone_type": "support_zone", "position_hint": "midground","priority": 3, "display_name": "Bus Stop"},
    ],
    "forest":           [
        {"anchor_type": "ancient_tree",  "zone_type": "hero_zone",    "position_hint": "center",        "priority": 1, "display_name": "Ancient Tree"},
        {"anchor_type": "fallen_log",    "zone_type": "support_zone", "position_hint": "midground",     "priority": 2, "display_name": "Fallen Log"},
        {"anchor_type": "rocky_outcrop", "zone_type": "background_zone", "position_hint": "background", "priority": 3, "display_name": "Rocky Outcrop"},
    ],
    "desert":           [
        {"anchor_type": "rock_formation",  "zone_type": "hero_zone",      "position_hint": "center",    "priority": 1, "display_name": "Rock Formation"},
        {"anchor_type": "ruined_structure","zone_type": "background_zone", "position_hint": "background","priority": 2, "display_name": "Ruined Structure"},
        {"anchor_type": "dead_tree",       "zone_type": "support_zone",   "position_hint": "midground", "priority": 3, "display_name": "Dead Tree"},
    ],
    "castle_hall":      [
        {"anchor_type": "throne",      "zone_type": "hero_zone",    "position_hint": "center",          "priority": 1, "display_name": "Throne"},
        {"anchor_type": "long_table",  "zone_type": "seating_zone", "position_hint": "center",          "priority": 2, "display_name": "Long Banqueting Table"},
        {"anchor_type": "fireplace",   "zone_type": "wall_zone",    "position_hint": "wall_adjacent",   "priority": 3, "display_name": "Great Fireplace"},
    ],
    "survival_camp":    [
        {"anchor_type": "camp_fire",         "zone_type": "hero_zone",    "position_hint": "center",    "priority": 1, "display_name": "Camp Fire"},
        {"anchor_type": "supply_crate_stack","zone_type": "support_zone", "position_hint": "perimeter", "priority": 2, "display_name": "Supply Crates"},
        {"anchor_type": "sleeping_area",     "zone_type": "decoration_zone", "position_hint": "perimeter", "priority": 3, "display_name": "Sleeping Area"},
    ],
}

_GENERIC_ANCHORS = [
    {"anchor_type": "main_prop", "zone_type": "hero_zone", "position_hint": "center", "priority": 1, "display_name": "Main Prop"},
]


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class PlacedAnchor:
    """A single anchor asset placed in an environment zone."""

    anchor_id: str = field(default_factory=lambda: f"anch_{uuid.uuid4().hex[:8]}")
    anchor_type: str = ""
    zone_type: str = ""
    position_hint: str = "center"
    display_name: str = ""
    priority: int = 1
    child_types: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "anchor_id":    self.anchor_id,
            "anchor_type":  self.anchor_type,
            "zone_type":    self.zone_type,
            "position_hint": self.position_hint,
            "display_name": self.display_name,
            "priority":     self.priority,
            "child_types":  list(self.child_types),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PlacedAnchor":
        return cls(
            anchor_id    = str(d.get("anchor_id", f"anch_{uuid.uuid4().hex[:8]}")),
            anchor_type  = str(d.get("anchor_type", "")),
            zone_type    = str(d.get("zone_type", "")),
            position_hint = str(d.get("position_hint", "center")),
            display_name = str(d.get("display_name", "")),
            priority     = int(d.get("priority", 1)),
            child_types  = list(d.get("child_types", [])),
        )


@dataclass
class AnchorPlan:
    """The full anchor layout for an environment."""

    environment_name: str = ""
    anchors: List[PlacedAnchor] = field(default_factory=list)
    primary_anchor: Optional[str] = None   # anchor_type of the priority-1 anchor
    anchor_count: int = 0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "environment_name": self.environment_name,
            "anchors":          [a.to_dict() for a in self.anchors],
            "primary_anchor":   self.primary_anchor,
            "anchor_count":     self.anchor_count,
            "errors":           list(self.errors),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AnchorPlan":
        return cls(
            environment_name = str(d.get("environment_name", "")),
            anchors          = [PlacedAnchor.from_dict(a) for a in d.get("anchors", [])],
            primary_anchor   = d.get("primary_anchor"),
            anchor_count     = int(d.get("anchor_count", 0)),
            errors           = list(d.get("errors", [])),
        )


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

class AnchorAssetBuilder:
    """Determine anchor assets and assign them to zones."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def build_anchors(
        self,
        environment_name: str,
        blueprint: Optional[EnvironmentBlueprint] = None,
    ) -> AnchorPlan:
        """Build the anchor plan for the environment.

        If ``blueprint`` is provided, any required_anchors not already covered
        by the built-in definitions are added with generic configuration.
        """
        with self._lock:
            try:
                return self._build(environment_name, blueprint)
            except Exception as exc:
                return AnchorPlan(
                    environment_name = environment_name,
                    errors           = [f"Anchor build error: {exc}"],
                )

    def _build(
        self,
        environment_name: str,
        blueprint: Optional[EnvironmentBlueprint],
    ) -> AnchorPlan:
        key = (environment_name or "").strip().lower()
        defs = list(_ANCHOR_DEFS.get(key, _GENERIC_ANCHORS))

        # Supplement from blueprint required_anchors
        if blueprint and blueprint.required_anchors:
            covered = {d["anchor_type"] for d in defs}
            for req in blueprint.required_anchors:
                if req not in covered:
                    defs.append({
                        "anchor_type": req,
                        "zone_type":   "hero_zone",
                        "position_hint": "center",
                        "priority":    len(defs) + 1,
                        "display_name": req.replace("_", " ").title(),
                    })

        anchors: List[PlacedAnchor] = []
        for d in defs:
            atype = d["anchor_type"]
            children = list(_ANCHOR_CHILDREN.get(atype, []))
            anchors.append(PlacedAnchor(
                anchor_type  = atype,
                zone_type    = d.get("zone_type", "hero_zone"),
                position_hint = d.get("position_hint", "center"),
                display_name = d.get("display_name", atype.replace("_", " ").title()),
                priority     = int(d.get("priority", 1)),
                child_types  = children,
            ))

        # Sort by priority
        anchors.sort(key=lambda a: a.priority)
        primary = anchors[0].anchor_type if anchors else None

        return AnchorPlan(
            environment_name = environment_name,
            anchors          = anchors,
            primary_anchor   = primary,
            anchor_count     = len(anchors),
            errors           = [],
        )

    def get_children_for_anchor(self, anchor_type: str) -> List[str]:
        """Return the list of child asset types for the given anchor."""
        return list(_ANCHOR_CHILDREN.get(anchor_type, []))

    def get_primary_anchor(self, anchor_plan: AnchorPlan) -> Optional[PlacedAnchor]:
        """Return the priority-1 (primary) anchor, or None."""
        for a in anchor_plan.anchors:
            if a.priority == 1:
                return a
        return anchor_plan.anchors[0] if anchor_plan.anchors else None


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[AnchorAssetBuilder] = None
_LOCK = threading.Lock()


def get_anchor_asset_builder() -> AnchorAssetBuilder:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = AnchorAssetBuilder()
        return _INSTANCE


def reset_anchor_asset_builder_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
