"""
Decorative Population Engine (Tier 9.5 — Structural Environment Assembly)
==========================================================================
Fills environment zones with contextually appropriate small props and
surface dressing. Decorative items are placed AFTER the structure is built
and anchor assets are determined.

Population is driven by:
  1. The environment blueprint's decorative_assets list.
  2. Semantic relationships — items that "belong on" or "belong near" anchors.
  3. Zone capacity limits — decoration_zone has the highest budget.

DESIGN RULES:
  1. No bridge calls. No Houdini imports. Planning only.
  2. Deterministic — same environment + anchor plan → same decoration plan.
  3. Never raises — errors captured in DecorationPlan.errors.
  4. Decoration does not steal focus — hero and support zones get minimal dressing.

Public API:
    DecorativeItem
    DecorationPlan
    DecorativePopulationEngine
    get_decorative_population_engine()
    reset_decorative_population_engine_for_tests()
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.runtime.assets.assembly.architectural_templates import get_architectural_templates
from src.runtime.assets.assembly.anchor_asset_engine import (
    AnchorPlan,
    get_anchor_asset_engine,
    SEMANTIC_RELATIONSHIPS,
)


# ---------------------------------------------------------------------------
# Per-zone decoration budget (max items per zone type)
# ---------------------------------------------------------------------------

_ZONE_BUDGETS: Dict[str, int] = {
    "entrance_zone":   3,
    "hero_zone":       4,   # only anchor-dependent items
    "support_zone":    5,
    "decoration_zone": 12,
    "atmosphere_zone": 3,
    "background_zone": 5,
}

# Placement target verbs
PLACEMENT_TARGETS = frozenset({
    "on_table", "near_wall", "corner", "ceiling", "floor", "on_shelf",
    "near_anchor", "scattered", "wall_mounted", "ceiling_mounted",
})


# ---------------------------------------------------------------------------
# Per-environment decoration recipes
# ---------------------------------------------------------------------------

_DECORATION_RECIPES: Dict[str, List[Dict[str, Any]]] = {
    # Each entry: {category, asset_type, placement_target, parent_anchor, zone, quantity}

    "western_room": [
        {"category": "prop", "asset_type": "cup",        "placement_target": "on_table",   "parent_anchor": "table",       "zone": "hero_zone",       "quantity": 4},
        {"category": "prop", "asset_type": "bottle",     "placement_target": "on_table",   "parent_anchor": "table",       "zone": "hero_zone",       "quantity": 3},
        {"category": "prop", "asset_type": "lantern",    "placement_target": "on_table",   "parent_anchor": "table",       "zone": "hero_zone",       "quantity": 2},
        {"category": "prop", "asset_type": "bottle",     "placement_target": "on_table",   "parent_anchor": "bar_counter", "zone": "support_zone",    "quantity": 5},
        {"category": "prop", "asset_type": "bucket",     "placement_target": "near_wall",  "parent_anchor": None,          "zone": "decoration_zone", "quantity": 2},
        {"category": "prop", "asset_type": "lantern",    "placement_target": "wall_mounted","parent_anchor": None,          "zone": "background_zone", "quantity": 3},
        {"category": "prop", "asset_type": "poster",     "placement_target": "wall_mounted","parent_anchor": None,          "zone": "background_zone", "quantity": 2},
        {"category": "prop", "asset_type": "book",       "placement_target": "on_shelf",   "parent_anchor": None,          "zone": "decoration_zone", "quantity": 4},
    ],
    "saloon": [
        {"category": "prop", "asset_type": "bottle",     "placement_target": "on_table",   "parent_anchor": "bar_counter", "zone": "hero_zone",       "quantity": 6},
        {"category": "prop", "asset_type": "glass",      "placement_target": "on_table",   "parent_anchor": "bar_counter", "zone": "hero_zone",       "quantity": 4},
        {"category": "prop", "asset_type": "cup",        "placement_target": "on_table",   "parent_anchor": "gambling_table","zone": "support_zone",  "quantity": 4},
        {"category": "prop", "asset_type": "barrel",     "placement_target": "near_wall",  "parent_anchor": None,          "zone": "decoration_zone", "quantity": 3},
        {"category": "prop", "asset_type": "lantern",    "placement_target": "wall_mounted","parent_anchor": None,          "zone": "background_zone", "quantity": 4},
        {"category": "prop", "asset_type": "wanted_poster","placement_target": "wall_mounted","parent_anchor": None,        "zone": "background_zone", "quantity": 3},
        {"category": "prop", "asset_type": "bucket",     "placement_target": "corner",     "parent_anchor": None,          "zone": "decoration_zone", "quantity": 2},
    ],
    "living_room": [
        {"category": "prop", "asset_type": "book",       "placement_target": "on_table",   "parent_anchor": "coffee_table","zone": "hero_zone",       "quantity": 3},
        {"category": "prop", "asset_type": "remote",     "placement_target": "on_table",   "parent_anchor": "coffee_table","zone": "hero_zone",       "quantity": 1},
        {"category": "prop", "asset_type": "vase",       "placement_target": "on_table",   "parent_anchor": "coffee_table","zone": "hero_zone",       "quantity": 1},
        {"category": "prop", "asset_type": "cushion",    "placement_target": "near_anchor","parent_anchor": "sofa",        "zone": "hero_zone",       "quantity": 3},
        {"category": "prop", "asset_type": "book",       "placement_target": "on_shelf",   "parent_anchor": "bookcase",    "zone": "support_zone",    "quantity": 8},
        {"category": "prop", "asset_type": "plant",      "placement_target": "corner",     "parent_anchor": None,          "zone": "decoration_zone", "quantity": 2},
    ],
    "office": [
        {"category": "prop", "asset_type": "book",        "placement_target": "on_table",  "parent_anchor": "desk",         "zone": "hero_zone",       "quantity": 3},
        {"category": "prop", "asset_type": "mug",         "placement_target": "on_table",  "parent_anchor": "desk",         "zone": "hero_zone",       "quantity": 1},
        {"category": "prop", "asset_type": "notebook",    "placement_target": "on_table",  "parent_anchor": "desk",         "zone": "hero_zone",       "quantity": 2},
        {"category": "prop", "asset_type": "pen_holder",  "placement_target": "on_table",  "parent_anchor": "desk",         "zone": "hero_zone",       "quantity": 1},
        {"category": "prop", "asset_type": "book",        "placement_target": "on_shelf",  "parent_anchor": "bookcase",     "zone": "support_zone",    "quantity": 10},
        {"category": "prop", "asset_type": "plant",       "placement_target": "corner",    "parent_anchor": None,           "zone": "decoration_zone", "quantity": 2},
        {"category": "prop", "asset_type": "paper_stack", "placement_target": "on_table",  "parent_anchor": "desk",         "zone": "hero_zone",       "quantity": 2},
    ],
    "hotel_lobby": [
        {"category": "prop", "asset_type": "vase",        "placement_target": "on_table",  "parent_anchor": "reception_desk","zone": "hero_zone",      "quantity": 2},
        {"category": "prop", "asset_type": "brochure_stand","placement_target": "near_anchor","parent_anchor": "reception_desk","zone": "hero_zone",    "quantity": 1},
        {"category": "prop", "asset_type": "lobby_lamp",  "placement_target": "near_anchor","parent_anchor": "seating_group","zone": "hero_zone",       "quantity": 2},
        {"category": "prop", "asset_type": "rug",         "placement_target": "floor",     "parent_anchor": None,           "zone": "decoration_zone", "quantity": 2},
        {"category": "prop", "asset_type": "artwork",     "placement_target": "wall_mounted","parent_anchor": None,          "zone": "background_zone", "quantity": 3},
        {"category": "prop", "asset_type": "plant",       "placement_target": "corner",    "parent_anchor": None,           "zone": "decoration_zone", "quantity": 3},
    ],
    "restaurant": [
        {"category": "prop", "asset_type": "candle",      "placement_target": "on_table",  "parent_anchor": "hero_dining_table","zone": "hero_zone",   "quantity": 2},
        {"category": "prop", "asset_type": "flower_arrangement","placement_target": "on_table","parent_anchor": "hero_dining_table","zone": "hero_zone","quantity": 1},
        {"category": "prop", "asset_type": "tablecloth",  "placement_target": "on_table",  "parent_anchor": "hero_dining_table","zone": "hero_zone",   "quantity": 1},
        {"category": "prop", "asset_type": "menu_card",   "placement_target": "on_table",  "parent_anchor": None,           "zone": "decoration_zone", "quantity": 6},
        {"category": "prop", "asset_type": "candle",      "placement_target": "on_table",  "parent_anchor": None,           "zone": "support_zone",    "quantity": 6},
        {"category": "prop", "asset_type": "artwork",     "placement_target": "wall_mounted","parent_anchor": None,          "zone": "background_zone", "quantity": 3},
    ],
    "library": [
        {"category": "prop", "asset_type": "book",        "placement_target": "on_shelf",  "parent_anchor": "bookshelf_wall","zone": "support_zone",   "quantity": 20},
        {"category": "prop", "asset_type": "book",        "placement_target": "on_table",  "parent_anchor": "reading_table", "zone": "hero_zone",       "quantity": 4},
        {"category": "prop", "asset_type": "globe",       "placement_target": "on_table",  "parent_anchor": "reading_table", "zone": "hero_zone",       "quantity": 1},
        {"category": "prop", "asset_type": "magnifying_glass","placement_target": "on_table","parent_anchor": "reading_table","zone": "hero_zone",      "quantity": 1},
        {"category": "prop", "asset_type": "plant",       "placement_target": "corner",    "parent_anchor": None,           "zone": "decoration_zone", "quantity": 2},
        {"category": "prop", "asset_type": "bust",        "placement_target": "on_shelf",  "parent_anchor": None,           "zone": "decoration_zone", "quantity": 2},
    ],
    "industrial_hangar": [
        {"category": "prop", "asset_type": "toolbox",     "placement_target": "near_anchor","parent_anchor": "main_machine", "zone": "hero_zone",       "quantity": 2},
        {"category": "prop", "asset_type": "barrel",      "placement_target": "near_wall",  "parent_anchor": None,           "zone": "decoration_zone", "quantity": 4},
        {"category": "prop", "asset_type": "bucket",      "placement_target": "near_wall",  "parent_anchor": None,           "zone": "decoration_zone", "quantity": 3},
        {"category": "prop", "asset_type": "fuel_drum",   "placement_target": "corner",     "parent_anchor": None,           "zone": "decoration_zone", "quantity": 3},
        {"category": "prop", "asset_type": "warning_sign","placement_target": "wall_mounted","parent_anchor": None,           "zone": "background_zone", "quantity": 4},
        {"category": "pipe", "asset_type": "pipe",        "placement_target": "near_wall",  "parent_anchor": None,           "zone": "support_zone",    "quantity": 6},
    ],
    "warehouse": [
        {"category": "prop", "asset_type": "cardboard_box","placement_target": "on_table",  "parent_anchor": "shelving_rack","zone": "hero_zone",       "quantity": 8},
        {"category": "prop", "asset_type": "barrel",      "placement_target": "near_wall",  "parent_anchor": None,           "zone": "decoration_zone", "quantity": 4},
        {"category": "prop", "asset_type": "bucket",      "placement_target": "corner",     "parent_anchor": None,           "zone": "decoration_zone", "quantity": 2},
        {"category": "prop", "asset_type": "warning_tape","placement_target": "floor",      "parent_anchor": None,           "zone": "decoration_zone", "quantity": 3},
        {"category": "prop", "asset_type": "fire_extinguisher","placement_target": "near_wall","parent_anchor": None,         "zone": "background_zone", "quantity": 2},
    ],
    "abandoned_factory": [
        {"category": "prop", "asset_type": "rubble",      "placement_target": "scattered",  "parent_anchor": None,           "zone": "decoration_zone", "quantity": 8},
        {"category": "prop", "asset_type": "debris",      "placement_target": "scattered",  "parent_anchor": None,           "zone": "decoration_zone", "quantity": 6},
        {"category": "prop", "asset_type": "broken_glass","placement_target": "floor",      "parent_anchor": None,           "zone": "decoration_zone", "quantity": 4},
        {"category": "prop", "asset_type": "graffiti",    "placement_target": "wall_mounted","parent_anchor": None,           "zone": "background_zone", "quantity": 5},
        {"category": "prop", "asset_type": "weeds",       "placement_target": "corner",     "parent_anchor": None,           "zone": "decoration_zone", "quantity": 4},
        {"category": "pipe", "asset_type": "rusted_pipe", "placement_target": "near_wall",  "parent_anchor": None,           "zone": "support_zone",    "quantity": 4},
    ],
    "robotics_lab": [
        {"category": "prop", "asset_type": "cable_bundle","placement_target": "near_anchor","parent_anchor": "robot_platform","zone": "hero_zone",       "quantity": 3},
        {"category": "prop", "asset_type": "electronic_component","placement_target": "on_table","parent_anchor": None,        "zone": "decoration_zone", "quantity": 4},
        {"category": "prop", "asset_type": "tool_kit",    "placement_target": "near_anchor","parent_anchor": "research_console","zone": "hero_zone",     "quantity": 1},
        {"category": "prop", "asset_type": "notebook",    "placement_target": "on_table",   "parent_anchor": "research_console","zone": "hero_zone",     "quantity": 2},
        {"category": "prop", "asset_type": "cable_bundle","placement_target": "near_anchor","parent_anchor": None,            "zone": "support_zone",    "quantity": 4},
    ],
    "research_lab": [
        {"category": "prop", "asset_type": "flask",       "placement_target": "on_table",  "parent_anchor": "central_lab_bench","zone": "hero_zone",    "quantity": 4},
        {"category": "prop", "asset_type": "notebook",    "placement_target": "on_table",  "parent_anchor": "central_lab_bench","zone": "hero_zone",    "quantity": 2},
        {"category": "prop", "asset_type": "specimen_jar","placement_target": "on_table",  "parent_anchor": "central_lab_bench","zone": "hero_zone",    "quantity": 3},
        {"category": "prop", "asset_type": "plant",       "placement_target": "corner",    "parent_anchor": None,           "zone": "decoration_zone", "quantity": 1},
        {"category": "prop", "asset_type": "cable_bundle","placement_target": "near_anchor","parent_anchor": "server_cluster","zone": "support_zone",   "quantity": 3},
    ],
    "medical_lab": [
        {"category": "prop", "asset_type": "medical_tool","placement_target": "near_anchor","parent_anchor": "operating_table","zone": "hero_zone",     "quantity": 4},
        {"category": "prop", "asset_type": "specimen_container","placement_target": "on_table","parent_anchor": None,           "zone": "decoration_zone","quantity": 3},
        {"category": "prop", "asset_type": "biohazard_warning","placement_target": "wall_mounted","parent_anchor": None,        "zone": "background_zone","quantity": 2},
        {"category": "prop", "asset_type": "surgical_light","placement_target": "ceiling_mounted","parent_anchor": "operating_table","zone": "hero_zone","quantity": 1},
    ],
    "control_room": [
        {"category": "prop", "asset_type": "status_indicator_light","placement_target": "on_table","parent_anchor": "main_console_bank","zone": "hero_zone","quantity": 6},
        {"category": "prop", "asset_type": "mug",         "placement_target": "on_table",  "parent_anchor": "main_console_bank","zone": "hero_zone",     "quantity": 2},
        {"category": "prop", "asset_type": "notepad",     "placement_target": "on_table",  "parent_anchor": "main_console_bank","zone": "hero_zone",     "quantity": 2},
        {"category": "prop", "asset_type": "cable_management","placement_target": "near_wall","parent_anchor": None,            "zone": "support_zone",  "quantity": 4},
    ],
    "sci_fi_corridor": [
        {"category": "prop", "asset_type": "hologram_emitter","placement_target": "wall_mounted","parent_anchor": None,        "zone": "support_zone",    "quantity": 3},
        {"category": "prop", "asset_type": "warning_light","placement_target": "ceiling_mounted","parent_anchor": None,        "zone": "decoration_zone", "quantity": 4},
        {"category": "prop", "asset_type": "hazard_decal","placement_target": "wall_mounted","parent_anchor": None,            "zone": "decoration_zone", "quantity": 5},
        {"category": "prop", "asset_type": "hand_scanner","placement_target": "near_anchor","parent_anchor": "airlock_control","zone": "entrance_zone",   "quantity": 1},
    ],
    "space_station": [
        {"category": "prop", "asset_type": "tool_kit",    "placement_target": "on_table",  "parent_anchor": "navigation_console","zone": "hero_zone",    "quantity": 2},
        {"category": "prop", "asset_type": "personal_effect","placement_target": "near_anchor","parent_anchor": None,           "zone": "decoration_zone","quantity": 3},
        {"category": "prop", "asset_type": "warning_decal","placement_target": "wall_mounted","parent_anchor": None,            "zone": "support_zone",   "quantity": 4},
        {"category": "prop", "asset_type": "emergency_kit","placement_target": "near_wall", "parent_anchor": None,             "zone": "background_zone", "quantity": 2},
    ],
    "city_street": [
        {"category": "prop", "asset_type": "newspaper",   "placement_target": "floor",     "parent_anchor": None,           "zone": "decoration_zone", "quantity": 3},
        {"category": "prop", "asset_type": "poster",      "placement_target": "wall_mounted","parent_anchor": None,          "zone": "background_zone", "quantity": 4},
        {"category": "prop", "asset_type": "graffiti",    "placement_target": "wall_mounted","parent_anchor": None,          "zone": "background_zone", "quantity": 3},
        {"category": "terrain", "asset_type": "puddle_decal","placement_target": "floor",   "parent_anchor": None,           "zone": "decoration_zone", "quantity": 4},
    ],
    "forest": [
        {"category": "prop", "asset_type": "mushroom",    "placement_target": "near_anchor","parent_anchor": "fallen_log",  "zone": "support_zone",    "quantity": 5},
        {"category": "prop", "asset_type": "moss_patch",  "placement_target": "near_anchor","parent_anchor": "ancient_tree","zone": "hero_zone",       "quantity": 4},
        {"category": "terrain","asset_type": "leaf_pile", "placement_target": "floor",      "parent_anchor": None,          "zone": "decoration_zone", "quantity": 6},
        {"category": "prop", "asset_type": "flower",      "placement_target": "floor",      "parent_anchor": None,          "zone": "decoration_zone", "quantity": 6},
        {"category": "prop", "asset_type": "twig",        "placement_target": "floor",      "parent_anchor": None,          "zone": "decoration_zone", "quantity": 8},
    ],
    "desert": [
        {"category": "prop", "asset_type": "bleached_bone","placement_target": "floor",     "parent_anchor": None,          "zone": "decoration_zone", "quantity": 3},
        {"category": "prop", "asset_type": "weathered_artifact","placement_target": "near_anchor","parent_anchor": "ancient_ruin","zone": "hero_zone",  "quantity": 2},
        {"category": "terrain","asset_type": "sand_ripple","placement_target": "floor",     "parent_anchor": None,          "zone": "decoration_zone", "quantity": 8},
        {"category": "prop", "asset_type": "small_cactus","placement_target": "scattered",  "parent_anchor": None,          "zone": "support_zone",    "quantity": 4},
    ],
    "castle_hall": [
        {"category": "prop", "asset_type": "goblet",      "placement_target": "on_table",  "parent_anchor": "throne",       "zone": "hero_zone",       "quantity": 2},
        {"category": "prop", "asset_type": "torch",       "placement_target": "wall_mounted","parent_anchor": None,          "zone": "background_zone", "quantity": 8},
        {"category": "prop", "asset_type": "tapestry",    "placement_target": "wall_mounted","parent_anchor": None,          "zone": "background_zone", "quantity": 4},
        {"category": "prop", "asset_type": "shield",      "placement_target": "wall_mounted","parent_anchor": None,          "zone": "decoration_zone", "quantity": 3},
        {"category": "prop", "asset_type": "goblet",      "placement_target": "on_table",  "parent_anchor": "long_dining_table","zone": "support_zone","quantity": 6},
        {"category": "prop", "asset_type": "scroll",      "placement_target": "on_table",  "parent_anchor": None,           "zone": "decoration_zone", "quantity": 3},
    ],
    "survival_camp": [
        {"category": "prop", "asset_type": "tin_can",     "placement_target": "near_anchor","parent_anchor": "fire_pit",    "zone": "hero_zone",       "quantity": 3},
        {"category": "prop", "asset_type": "rope_coil",   "placement_target": "near_anchor","parent_anchor": "main_shelter","zone": "support_zone",    "quantity": 2},
        {"category": "prop", "asset_type": "lantern",     "placement_target": "near_anchor","parent_anchor": "fire_pit",    "zone": "hero_zone",       "quantity": 2},
        {"category": "prop", "asset_type": "ration_pack", "placement_target": "on_table",  "parent_anchor": "supply_cache","zone": "support_zone",    "quantity": 4},
        {"category": "prop", "asset_type": "survival_map","placement_target": "on_table",  "parent_anchor": None,          "zone": "decoration_zone", "quantity": 1},
    ],
    "dungeon": [
        {"category": "prop", "asset_type": "torch",       "placement_target": "wall_mounted","parent_anchor": None,          "zone": "background_zone", "quantity": 6},
        {"category": "prop", "asset_type": "skull",       "placement_target": "near_wall",  "parent_anchor": None,          "zone": "decoration_zone", "quantity": 4},
        {"category": "prop", "asset_type": "bucket",      "placement_target": "corner",     "parent_anchor": None,          "zone": "decoration_zone", "quantity": 2},
        {"category": "prop", "asset_type": "manacle",     "placement_target": "wall_mounted","parent_anchor": "prison_cell_block","zone": "hero_zone",  "quantity": 4},
        {"category": "prop", "asset_type": "chain",       "placement_target": "near_anchor","parent_anchor": "torture_rack","zone": "support_zone",    "quantity": 3},
    ],
}

_GENERIC_DECORATION: List[Dict[str, Any]] = [
    {"category": "prop", "asset_type": "small_prop", "placement_target": "scattered", "parent_anchor": None, "zone": "decoration_zone", "quantity": 4},
]


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class DecorativeItem:
    """A single decorative item to be placed in the environment."""

    item_id:          str = field(default_factory=lambda: f"dec_{uuid.uuid4().hex[:8]}")
    category:         str = ""
    asset_type:       str = ""
    placement_target: str = "scattered"  # one of PLACEMENT_TARGETS
    parent_anchor:    Optional[str] = None
    zone:             str = "decoration_zone"
    quantity:         int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id":          self.item_id,
            "category":         self.category,
            "asset_type":       self.asset_type,
            "placement_target": self.placement_target,
            "parent_anchor":    self.parent_anchor,
            "zone":             self.zone,
            "quantity":         self.quantity,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DecorativeItem":
        return cls(
            item_id          = str(d.get("item_id", f"dec_{uuid.uuid4().hex[:8]}")),
            category         = str(d.get("category", "")),
            asset_type       = str(d.get("asset_type", "")),
            placement_target = str(d.get("placement_target", "scattered")),
            parent_anchor    = d.get("parent_anchor"),
            zone             = str(d.get("zone", "decoration_zone")),
            quantity         = int(d.get("quantity", 1)),
        )


@dataclass
class DecorationPlan:
    """Complete decorative population plan for an environment."""

    plan_id:          str = field(default_factory=lambda: f"decp_{uuid.uuid4().hex[:10]}")
    environment_name: str = ""
    items:            List[DecorativeItem] = field(default_factory=list)
    total_items:      int = 0
    errors:           List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id":          self.plan_id,
            "environment_name": self.environment_name,
            "items":            [i.to_dict() for i in self.items],
            "total_items":      self.total_items,
            "errors":           list(self.errors),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DecorationPlan":
        return cls(
            plan_id          = str(d.get("plan_id", f"decp_{uuid.uuid4().hex[:10]}")),
            environment_name = str(d.get("environment_name", "")),
            items            = [DecorativeItem.from_dict(i) for i in d.get("items", [])],
            total_items      = int(d.get("total_items", 0)),
            errors           = list(d.get("errors", [])),
        )


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class DecorativePopulationEngine:
    """Populates environment zones with contextually appropriate small props.

    Population follows the structure-first rule: decoration only makes sense
    once anchors are established, which only makes sense once structure exists.

    Never raises — errors captured in DecorationPlan.errors.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def get_decoration_plan(
        self,
        environment_name: str,
        anchor_plan: Optional[AnchorPlan] = None,
    ) -> DecorationPlan:
        """Build the decoration plan for the given environment.

        Args:
            environment_name: canonical environment name.
            anchor_plan:      optional AnchorPlan to use for context;
                              if None, a plan is fetched automatically.

        Returns:
            DecorationPlan with all items, zones, and placement targets.
        """
        try:
            return self._build_plan(environment_name, anchor_plan)
        except Exception as exc:
            return DecorationPlan(
                environment_name = environment_name,
                errors = [f"Decoration plan build failed: {exc}"],
            )

    def _build_plan(
        self,
        environment_name: str,
        anchor_plan: Optional[AnchorPlan],
    ) -> DecorationPlan:
        if anchor_plan is None:
            anchor_plan = get_anchor_asset_engine().get_anchor_plan(environment_name)

        raw = _DECORATION_RECIPES.get(environment_name, _GENERIC_DECORATION)
        items: List[DecorativeItem] = []
        errors: List[str] = []

        # Track zone budgets
        zone_counts: Dict[str, int] = {}

        for entry in raw:
            zone = str(entry.get("zone", "decoration_zone"))
            quantity = int(entry.get("quantity", 1))
            budget = _ZONE_BUDGETS.get(zone, 8)
            current = zone_counts.get(zone, 0)
            allowed = max(0, budget - current)
            if allowed <= 0:
                continue
            actual_qty = min(quantity, allowed)
            zone_counts[zone] = current + actual_qty

            items.append(DecorativeItem(
                category         = str(entry.get("category", "prop")),
                asset_type       = str(entry.get("asset_type", "")),
                placement_target = str(entry.get("placement_target", "scattered")),
                parent_anchor    = entry.get("parent_anchor"),
                zone             = zone,
                quantity         = actual_qty,
            ))

        total = sum(i.quantity for i in items)

        return DecorationPlan(
            environment_name = environment_name,
            items            = items,
            total_items      = total,
            errors           = errors,
        )

    def get_items_for_zone(self, plan: DecorationPlan, zone: str) -> List[DecorativeItem]:
        """Return all decorative items assigned to a specific zone."""
        return [i for i in plan.items if i.zone == zone]

    def get_items_for_anchor(self, plan: DecorationPlan, anchor_type: str) -> List[DecorativeItem]:
        """Return all decorative items that belong on/near a specific anchor."""
        return [i for i in plan.items if i.parent_anchor == anchor_type]


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[DecorativePopulationEngine] = None
_LOCK = threading.Lock()


def get_decorative_population_engine() -> DecorativePopulationEngine:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = DecorativePopulationEngine()
        return _INSTANCE


def reset_decorative_population_engine_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
