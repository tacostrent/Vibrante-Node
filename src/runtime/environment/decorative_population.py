"""
Decorative Population (§44 — Structural Environment Assembly)
=============================================================
Fills environment zones with contextually appropriate small props and surface
dressing. Runs AFTER structure, zones, and anchors are defined.

DESIGN RULES:
  1. No bridge calls. No Houdini imports. Planning only.
  2. Deterministic — same environment always yields the same decoration plan.
  3. Never raises — errors captured in DecorationPlan.errors.
  4. Singleton pattern.
  5. Thread-safe.

Public API:
    DecorativeItem
    DecorationPlan
    DecorativePopulation
    get_decorative_population()
    reset_decorative_population_for_tests()
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.runtime.environment.anchor_asset_builder import AnchorPlan


# ---------------------------------------------------------------------------
# Per-environment decorative item definitions
# ---------------------------------------------------------------------------

_ENV_DECO: Dict[str, List[Dict[str, Any]]] = {
    "western_room": [
        {"item_type": "cup",          "zone_type": "hero_zone",     "placement_target": "on_table",      "parent_anchor_type": "main_table", "count": 4},
        {"item_type": "bottle",       "zone_type": "hero_zone",     "placement_target": "on_table",      "parent_anchor_type": "main_table", "count": 3},
        {"item_type": "candle",       "zone_type": "hero_zone",     "placement_target": "on_table",      "parent_anchor_type": "main_table", "count": 2},
        {"item_type": "wanted_poster","zone_type": "wall_zone",     "placement_target": "wall_mounted",  "parent_anchor_type": None,          "count": 2},
        {"item_type": "saddle_bag",   "zone_type": "decoration_zone","placement_target": "floor",        "parent_anchor_type": None,          "count": 1},
        {"item_type": "lantern",      "zone_type": "wall_zone",     "placement_target": "on_shelf",      "parent_anchor_type": None,          "count": 2},
    ],
    "saloon": [
        {"item_type": "bottle",       "zone_type": "service_zone",  "placement_target": "on_table",      "parent_anchor_type": "bar_counter", "count": 5},
        {"item_type": "glass",        "zone_type": "service_zone",  "placement_target": "on_table",      "parent_anchor_type": "bar_counter", "count": 6},
        {"item_type": "playing_card", "zone_type": "hero_zone",     "placement_target": "on_table",      "parent_anchor_type": "main_table",  "count": 2},
        {"item_type": "candle",       "zone_type": "hero_zone",     "placement_target": "on_table",      "parent_anchor_type": "main_table",  "count": 3},
        {"item_type": "wanted_poster","zone_type": "wall_zone",     "placement_target": "wall_mounted",  "parent_anchor_type": None,          "count": 3},
        {"item_type": "lantern",      "zone_type": "atmosphere_zone","placement_target": "ceiling",      "parent_anchor_type": None,          "count": 4},
    ],
    "living_room": [
        {"item_type": "book",         "zone_type": "hero_zone",     "placement_target": "on_table",      "parent_anchor_type": "coffee_table", "count": 3},
        {"item_type": "mug",          "zone_type": "hero_zone",     "placement_target": "on_table",      "parent_anchor_type": "coffee_table", "count": 2},
        {"item_type": "cushion",      "zone_type": "seating_zone",  "placement_target": "near_anchor",   "parent_anchor_type": "sofa",         "count": 3},
        {"item_type": "plant",        "zone_type": "decoration_zone","placement_target": "floor",        "parent_anchor_type": None,           "count": 2},
        {"item_type": "wall_clock",   "zone_type": "wall_zone",     "placement_target": "wall_mounted",  "parent_anchor_type": None,           "count": 1},
        {"item_type": "framed_photo", "zone_type": "wall_zone",     "placement_target": "wall_mounted",  "parent_anchor_type": None,           "count": 3},
    ],
    "office": [
        {"item_type": "document_stack","zone_type": "hero_zone",    "placement_target": "on_table",      "parent_anchor_type": "main_desk",    "count": 3},
        {"item_type": "coffee_mug",   "zone_type": "hero_zone",     "placement_target": "on_table",      "parent_anchor_type": "main_desk",    "count": 2},
        {"item_type": "wall_clock",   "zone_type": "wall_zone",     "placement_target": "wall_mounted",  "parent_anchor_type": None,           "count": 1},
        {"item_type": "plant",        "zone_type": "decoration_zone","placement_target": "floor",        "parent_anchor_type": None,           "count": 2},
        {"item_type": "filing_box",   "zone_type": "wall_zone",     "placement_target": "near_wall",     "parent_anchor_type": None,           "count": 4},
    ],
    "hotel_lobby": [
        {"item_type": "plant",        "zone_type": "decoration_zone","placement_target": "floor",        "parent_anchor_type": None,           "count": 4},
        {"item_type": "magazine",     "zone_type": "seating_zone",  "placement_target": "on_table",      "parent_anchor_type": "seating_cluster", "count": 5},
        {"item_type": "clock",        "zone_type": "wall_zone",     "placement_target": "wall_mounted",  "parent_anchor_type": None,           "count": 1},
        {"item_type": "chandelier",   "zone_type": "atmosphere_zone","placement_target": "ceiling",      "parent_anchor_type": None,           "count": 2},
        {"item_type": "signage",      "zone_type": "entrance_zone", "placement_target": "near_anchor",   "parent_anchor_type": "reception_desk","count": 2},
    ],
    "restaurant": [
        {"item_type": "wine_glass",   "zone_type": "hero_zone",     "placement_target": "on_table",      "parent_anchor_type": "main_table_cluster", "count": 8},
        {"item_type": "candle",       "zone_type": "hero_zone",     "placement_target": "on_table",      "parent_anchor_type": "main_table_cluster", "count": 6},
        {"item_type": "menu",         "zone_type": "hero_zone",     "placement_target": "on_table",      "parent_anchor_type": "main_table_cluster", "count": 4},
        {"item_type": "napkin_holder","zone_type": "service_zone",  "placement_target": "on_table",      "parent_anchor_type": "service_station",    "count": 3},
        {"item_type": "wall_art",     "zone_type": "wall_zone",     "placement_target": "wall_mounted",  "parent_anchor_type": None,                 "count": 3},
    ],
    "library": [
        {"item_type": "book",         "zone_type": "hero_zone",     "placement_target": "on_shelf",      "parent_anchor_type": "bookshelf_row", "count": 20},
        {"item_type": "bookend",      "zone_type": "hero_zone",     "placement_target": "on_shelf",      "parent_anchor_type": "bookshelf_row", "count": 4},
        {"item_type": "study_lamp",   "zone_type": "seating_zone",  "placement_target": "on_table",      "parent_anchor_type": "reading_table", "count": 2},
        {"item_type": "globe",        "zone_type": "decoration_zone","placement_target": "on_table",     "parent_anchor_type": None,            "count": 1},
        {"item_type": "plant",        "zone_type": "decoration_zone","placement_target": "floor",        "parent_anchor_type": None,            "count": 2},
    ],
    "warehouse": [
        {"item_type": "safety_cone",  "zone_type": "decoration_zone","placement_target": "floor",        "parent_anchor_type": None, "count": 6},
        {"item_type": "safety_sign",  "zone_type": "wall_zone",     "placement_target": "wall_mounted",  "parent_anchor_type": None, "count": 4},
        {"item_type": "pallet",       "zone_type": "hero_zone",     "placement_target": "near_anchor",   "parent_anchor_type": "pallet_stack", "count": 4},
        {"item_type": "tape_roll",    "zone_type": "decoration_zone","placement_target": "floor",        "parent_anchor_type": None, "count": 2},
    ],
    "industrial_hangar": [
        {"item_type": "oil_drum",     "zone_type": "support_zone",  "placement_target": "corner",        "parent_anchor_type": None, "count": 4},
        {"item_type": "toolbox",      "zone_type": "decoration_zone","placement_target": "near_anchor",  "parent_anchor_type": "hero_machine", "count": 3},
        {"item_type": "safety_sign",  "zone_type": "wall_zone",     "placement_target": "wall_mounted",  "parent_anchor_type": None, "count": 4},
        {"item_type": "chain_hook",   "zone_type": "atmosphere_zone","placement_target": "ceiling",      "parent_anchor_type": None, "count": 2},
        {"item_type": "work_lamp",    "zone_type": "decoration_zone","placement_target": "floor",        "parent_anchor_type": None, "count": 3},
    ],
    "abandoned_factory": [
        {"item_type": "debris",       "zone_type": "decoration_zone","placement_target": "scattered",    "parent_anchor_type": None, "count": 8},
        {"item_type": "rust_pipe",    "zone_type": "wall_zone",     "placement_target": "near_wall",     "parent_anchor_type": None, "count": 4},
        {"item_type": "graffiti_tag", "zone_type": "wall_zone",     "placement_target": "wall_mounted",  "parent_anchor_type": None, "count": 3},
        {"item_type": "broken_glass", "zone_type": "decoration_zone","placement_target": "floor",        "parent_anchor_type": None, "count": 5},
    ],
    "robotics_lab": [
        {"item_type": "electronic_component","zone_type": "support_zone","placement_target": "on_table", "parent_anchor_type": "workbench", "count": 4},
        {"item_type": "cable_bundle", "zone_type": "wall_zone",     "placement_target": "near_wall",     "parent_anchor_type": None, "count": 3},
        {"item_type": "data_pad",     "zone_type": "decoration_zone","placement_target": "on_table",     "parent_anchor_type": None, "count": 2},
        {"item_type": "status_light", "zone_type": "atmosphere_zone","placement_target": "ceiling",      "parent_anchor_type": None, "count": 4},
    ],
    "control_room": [
        {"item_type": "mug",          "zone_type": "hero_zone",     "placement_target": "on_table",      "parent_anchor_type": "operations_desk", "count": 3},
        {"item_type": "document",     "zone_type": "hero_zone",     "placement_target": "on_table",      "parent_anchor_type": "master_console",  "count": 4},
        {"item_type": "status_light", "zone_type": "atmosphere_zone","placement_target": "ceiling",      "parent_anchor_type": None, "count": 6},
        {"item_type": "headset",      "zone_type": "decoration_zone","placement_target": "near_anchor",  "parent_anchor_type": "operations_desk", "count": 2},
    ],
    "medical_lab": [
        {"item_type": "specimen_jar", "zone_type": "support_zone",  "placement_target": "on_shelf",      "parent_anchor_type": "specimen_storage", "count": 5},
        {"item_type": "syringe",      "zone_type": "hero_zone",     "placement_target": "on_table",      "parent_anchor_type": "examination_table","count": 3},
        {"item_type": "glove_box",    "zone_type": "wall_zone",     "placement_target": "wall_mounted",  "parent_anchor_type": None, "count": 2},
        {"item_type": "warning_sign", "zone_type": "wall_zone",     "placement_target": "wall_mounted",  "parent_anchor_type": None, "count": 2},
    ],
    "research_lab": [
        {"item_type": "flask",        "zone_type": "hero_zone",     "placement_target": "on_table",      "parent_anchor_type": "central_workbench", "count": 5},
        {"item_type": "notebook",     "zone_type": "hero_zone",     "placement_target": "on_table",      "parent_anchor_type": "central_workbench", "count": 2},
        {"item_type": "chemical_jar", "zone_type": "support_zone",  "placement_target": "on_shelf",      "parent_anchor_type": "chemical_storage",  "count": 6},
        {"item_type": "safety_goggle","zone_type": "wall_zone",     "placement_target": "wall_mounted",  "parent_anchor_type": None, "count": 2},
    ],
    "sci_fi_corridor": [
        {"item_type": "data_pad",     "zone_type": "wall_zone",     "placement_target": "wall_mounted",  "parent_anchor_type": None, "count": 3},
        {"item_type": "status_light", "zone_type": "atmosphere_zone","placement_target": "ceiling_mounted","parent_anchor_type": None, "count": 6},
        {"item_type": "cable_bundle", "zone_type": "wall_zone",     "placement_target": "wall_mounted",  "parent_anchor_type": None, "count": 4},
        {"item_type": "fire_extinguisher","zone_type": "wall_zone", "placement_target": "wall_mounted",  "parent_anchor_type": None, "count": 2},
    ],
    "city_street": [
        {"item_type": "bench",        "zone_type": "support_zone",  "placement_target": "near_wall",     "parent_anchor_type": None, "count": 3},
        {"item_type": "trash_can",    "zone_type": "decoration_zone","placement_target": "floor",        "parent_anchor_type": None, "count": 4},
        {"item_type": "sign",         "zone_type": "wall_zone",     "placement_target": "wall_mounted",  "parent_anchor_type": None, "count": 3},
        {"item_type": "bicycle",      "zone_type": "decoration_zone","placement_target": "near_wall",    "parent_anchor_type": None, "count": 2},
    ],
    "forest": [
        {"item_type": "mushroom",     "zone_type": "decoration_zone","placement_target": "floor",        "parent_anchor_type": None, "count": 8},
        {"item_type": "fern",         "zone_type": "decoration_zone","placement_target": "scattered",    "parent_anchor_type": None, "count": 10},
        {"item_type": "small_rock",   "zone_type": "decoration_zone","placement_target": "scattered",    "parent_anchor_type": None, "count": 6},
        {"item_type": "ivy",          "zone_type": "wall_zone",     "placement_target": "near_anchor",   "parent_anchor_type": "ancient_tree", "count": 4},
    ],
    "desert": [
        {"item_type": "cactus",       "zone_type": "decoration_zone","placement_target": "scattered",    "parent_anchor_type": None, "count": 5},
        {"item_type": "small_rock",   "zone_type": "decoration_zone","placement_target": "scattered",    "parent_anchor_type": None, "count": 8},
        {"item_type": "bleached_bone","zone_type": "decoration_zone","placement_target": "floor",        "parent_anchor_type": None, "count": 3},
        {"item_type": "tumbleweed",   "zone_type": "decoration_zone","placement_target": "scattered",    "parent_anchor_type": None, "count": 4},
    ],
    "castle_hall": [
        {"item_type": "candle_holder","zone_type": "hero_zone",     "placement_target": "on_table",      "parent_anchor_type": "long_table", "count": 6},
        {"item_type": "goblet",       "zone_type": "hero_zone",     "placement_target": "on_table",      "parent_anchor_type": "long_table", "count": 8},
        {"item_type": "banner",       "zone_type": "wall_zone",     "placement_target": "wall_mounted",  "parent_anchor_type": None,         "count": 4},
        {"item_type": "torch",        "zone_type": "wall_zone",     "placement_target": "wall_mounted",  "parent_anchor_type": None,         "count": 6},
        {"item_type": "shield",       "zone_type": "wall_zone",     "placement_target": "wall_mounted",  "parent_anchor_type": None,         "count": 3},
    ],
    "survival_camp": [
        {"item_type": "bedroll",      "zone_type": "decoration_zone","placement_target": "floor",        "parent_anchor_type": "sleeping_area",    "count": 3},
        {"item_type": "lantern_camp", "zone_type": "hero_zone",     "placement_target": "near_anchor",   "parent_anchor_type": "camp_fire",        "count": 2},
        {"item_type": "ration_pack",  "zone_type": "support_zone",  "placement_target": "near_anchor",   "parent_anchor_type": "supply_crate_stack","count": 4},
        {"item_type": "water_canteen","zone_type": "decoration_zone","placement_target": "floor",        "parent_anchor_type": None,               "count": 3},
        {"item_type": "rope_coil",    "zone_type": "decoration_zone","placement_target": "near_wall",    "parent_anchor_type": None,               "count": 2},
    ],
}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class DecorativeItem:
    """A single decorative prop placement specification."""

    item_id: str = field(default_factory=lambda: f"deco_{uuid.uuid4().hex[:8]}")
    item_type: str = ""
    zone_type: str = ""
    placement_target: str = "scattered"
    parent_anchor_type: Optional[str] = None
    count: int = 1
    display_name: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id":           self.item_id,
            "item_type":         self.item_type,
            "zone_type":         self.zone_type,
            "placement_target":  self.placement_target,
            "parent_anchor_type": self.parent_anchor_type,
            "count":             self.count,
            "display_name":      self.display_name,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DecorativeItem":
        return cls(
            item_id            = str(d.get("item_id", f"deco_{uuid.uuid4().hex[:8]}")),
            item_type          = str(d.get("item_type", "")),
            zone_type          = str(d.get("zone_type", "")),
            placement_target   = str(d.get("placement_target", "scattered")),
            parent_anchor_type = d.get("parent_anchor_type"),
            count              = int(d.get("count", 1)),
            display_name       = str(d.get("display_name", "")),
        )


@dataclass
class DecorationPlan:
    """The full decorative population plan for an environment."""

    environment_name: str = ""
    items: List[DecorativeItem] = field(default_factory=list)
    total_count: int = 0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "environment_name": self.environment_name,
            "items":            [i.to_dict() for i in self.items],
            "total_count":      self.total_count,
            "errors":           list(self.errors),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DecorationPlan":
        return cls(
            environment_name = str(d.get("environment_name", "")),
            items            = [DecorativeItem.from_dict(i) for i in d.get("items", [])],
            total_count      = int(d.get("total_count", 0)),
            errors           = list(d.get("errors", [])),
        )


# ---------------------------------------------------------------------------
# Population engine
# ---------------------------------------------------------------------------

class DecorativePopulation:
    """Populate an environment with decorative items."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def populate(
        self,
        environment_name: str,
        anchor_plan: Optional[AnchorPlan] = None,
    ) -> DecorationPlan:
        """Build the decoration plan for the environment."""
        with self._lock:
            try:
                return self._populate(environment_name, anchor_plan)
            except Exception as exc:
                return DecorationPlan(
                    environment_name = environment_name,
                    errors           = [f"Decoration error: {exc}"],
                )

    def _populate(
        self,
        environment_name: str,
        anchor_plan: Optional[AnchorPlan],
    ) -> DecorationPlan:
        key = (environment_name or "").strip().lower()
        items: List[DecorativeItem] = []

        for d in _ENV_DECO.get(key, []):
            itype = d["item_type"]
            items.append(DecorativeItem(
                item_type          = itype,
                zone_type          = d.get("zone_type", "decoration_zone"),
                placement_target   = d.get("placement_target", "scattered"),
                parent_anchor_type = d.get("parent_anchor_type"),
                count              = int(d.get("count", 1)),
                display_name       = itype.replace("_", " ").title(),
            ))

        total = sum(i.count for i in items)
        return DecorationPlan(
            environment_name = environment_name,
            items            = items,
            total_count      = total,
            errors           = [],
        )

    def get_items_for_zone(
        self,
        plan: DecorationPlan,
        zone_type: str,
    ) -> List[DecorativeItem]:
        """Return all items assigned to the given zone_type."""
        return [i for i in plan.items if i.zone_type == zone_type]


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[DecorativePopulation] = None
_LOCK = threading.Lock()


def get_decorative_population() -> DecorativePopulation:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = DecorativePopulation()
        return _INSTANCE


def reset_decorative_population_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
