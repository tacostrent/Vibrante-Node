"""
Placement Relationships (Tier 9.6 — Scale-Aware Spatial Placement)
===================================================================
Encodes semantic placement rules and asset role classification.

Key responsibilities:
  1. Role assignment — map asset types/categories to production roles
     (seating, furniture_anchor, decoration, structure, architectural…)
  2. Placement mode — how an asset is positioned
     (around_anchor, near_wall, corner, wall_only, route_to_structure, scattered)
  3. Structural routing — detect assets that must go to EnvironmentStructureBuilder
     instead of the furniture/prop placement pipeline
  4. Anchor relationships — which assets cluster near/around which anchors

Role → Placement mode mapping ensures that:
  - beam/wall/column → route_to_structure (never placed as furniture)
  - chair → around_anchor (groups around tables)
  - bucket → corner (placed at room corners)
  - door → wall_only (attached to walls, not floating)

DESIGN RULES:
  1. No bridge calls. No Houdini imports.
  2. Deterministic — same asset metadata → same role + placement mode.
  3. Never raises — defaults to role="prop", mode="scattered".
  4. Singleton.

Public API:
    ROLES
    PLACEMENT_MODES
    STRUCTURAL_KEYWORD_HINTS
    PlacementRelationship
    PlacementRelationships
    get_placement_relationships()
    reset_placement_relationships_for_tests()
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Controlled vocabularies
# ---------------------------------------------------------------------------

ROLES = frozenset({
    "seating",           # chair, stool, bench
    "furniture_anchor",  # table, desk, workbench, console — assets cluster around these
    "decoration",        # cup, bottle, lantern, bucket, small prop
    "structure",         # beam, wall, column, roof, platform — route to structure builder
    "architectural",     # door, window, archway, partition
    "electronic",        # server rack, terminal, panel
    "machinery",         # robot, crane, machine, furnace
    "vegetation",        # tree, bush, fern, plant
    "terrain",           # ground, rock, dune
    "vehicle",           # forklift, car, truck
    "prop",              # fallback / generic prop
})

PLACEMENT_MODES = frozenset({
    "around_anchor",      # placed radially around another asset (chairs around table)
    "near_wall",          # placed within 0.5–1.5 m of a wall
    "corner",             # placed in room corners
    "wall_only",          # must attach to a wall (door, window)
    "ceiling_mounted",    # placed on ceiling or overhead
    "floor_scattered",    # evenly scattered across floor
    "route_to_structure", # structural — must go to EnvironmentStructureBuilder
    "hero_center",        # placed at zone centre (anchor-class assets)
    "cluster_around",     # clusters near an anchor, but not anchored itself
    "scattered",          # default / no specific placement rule
})

# Keywords in asset name that indicate structural routing
STRUCTURAL_KEYWORD_HINTS: frozenset = frozenset({
    "beam", "wall", "column", "roof", "ceiling", "floor_panel",
    "support", "pillar", "rafter", "truss", "joist", "purlin",
    "strut", "buttress", "arch", "vault", "dome", "foundation",
    "slab", "platform", "catwalk",
})

# ---------------------------------------------------------------------------
# Role / mode lookup tables
# ---------------------------------------------------------------------------

# asset_type (lower) → (role, placement_mode)
_TYPE_RULES: Dict[str, tuple] = {
    # Seating
    "chair":            ("seating",         "around_anchor"),
    "office_chair":     ("seating",         "around_anchor"),
    "stool":            ("seating",         "around_anchor"),
    "bar_stool":        ("seating",         "around_anchor"),
    "bench":            ("seating",         "near_wall"),
    "sofa":             ("seating",         "hero_center"),
    "armchair":         ("seating",         "cluster_around"),
    "dining_chair":     ("seating",         "around_anchor"),

    # Furniture anchors
    "table":            ("furniture_anchor","hero_center"),
    "coffee_table":     ("furniture_anchor","hero_center"),
    "desk":             ("furniture_anchor","hero_center"),
    "workbench":        ("furniture_anchor","hero_center"),
    "bar_counter":      ("furniture_anchor","hero_center"),
    "gambling_table":   ("furniture_anchor","hero_center"),
    "lab_bench":        ("furniture_anchor","hero_center"),
    "operating_table":  ("furniture_anchor","hero_center"),
    "dining_table":     ("furniture_anchor","hero_center"),
    "bookshelf":        ("furniture_anchor","near_wall"),
    "bookshelf_wall":   ("furniture_anchor","near_wall"),
    "shelving_rack":    ("furniture_anchor","near_wall"),
    "filing_cabinet":   ("furniture_anchor","near_wall"),

    # Decoration
    "cup":              ("decoration",      "floor_scattered"),
    "mug":              ("decoration",      "floor_scattered"),
    "bottle":           ("decoration",      "floor_scattered"),
    "glass":            ("decoration",      "floor_scattered"),
    "lantern":          ("decoration",      "floor_scattered"),
    "candle":           ("decoration",      "floor_scattered"),
    "bucket":           ("decoration",      "corner"),
    "barrel":           ("decoration",      "corner"),
    "book":             ("decoration",      "floor_scattered"),
    "vase":             ("decoration",      "floor_scattered"),
    "plant":            ("decoration",      "corner"),
    "poster":           ("decoration",      "wall_only"),
    "wanted_poster":    ("decoration",      "wall_only"),
    "graffiti":         ("decoration",      "wall_only"),
    "torch":            ("decoration",      "wall_only"),
    "skull":            ("decoration",      "corner"),
    "goblet":           ("decoration",      "floor_scattered"),
    "scroll":           ("decoration",      "floor_scattered"),
    "notebook":         ("decoration",      "floor_scattered"),
    "flask":            ("decoration",      "floor_scattered"),

    # Structural — route to EnvironmentStructureBuilder
    "beam":             ("structure",       "route_to_structure"),
    "wooden_beam":      ("structure",       "route_to_structure"),
    "steel_beam":       ("structure",       "route_to_structure"),
    "old_wooden_beam":  ("structure",       "route_to_structure"),
    "wall":             ("structure",       "route_to_structure"),
    "column":           ("structure",       "route_to_structure"),
    "support_column":   ("structure",       "route_to_structure"),
    "pillar":           ("structure",       "route_to_structure"),
    "roof":             ("structure",       "route_to_structure"),
    "platform":         ("structure",       "route_to_structure"),
    "catwalk":          ("structure",       "route_to_structure"),
    "floor":            ("structure",       "route_to_structure"),
    "concrete_floor":   ("structure",       "route_to_structure"),
    "stone_floor":      ("structure",       "route_to_structure"),

    # Architectural (near structure, not furniture)
    "door":             ("architectural",   "wall_only"),
    "window":           ("architectural",   "wall_only"),
    "hangar_door":      ("architectural",   "wall_only"),
    "blast_door":       ("architectural",   "wall_only"),
    "airlock":          ("architectural",   "wall_only"),
    "archway":          ("architectural",   "wall_only"),
    "partition":        ("architectural",   "near_wall"),

    # Electronic
    "server_rack":      ("electronic",      "near_wall"),
    "console":          ("electronic",      "hero_center"),
    "terminal":         ("electronic",      "hero_center"),
    "screen":           ("electronic",      "near_wall"),
    "panel":            ("electronic",      "near_wall"),

    # Machinery
    "crane":            ("machinery",       "hero_center"),
    "machine":          ("machinery",       "hero_center"),
    "robot":            ("machinery",       "hero_center"),
    "furnace":          ("machinery",       "hero_center"),
    "forklift":         ("vehicle",         "floor_scattered"),

    # Vegetation / terrain
    "tree":             ("vegetation",      "floor_scattered"),
    "bush":             ("vegetation",      "floor_scattered"),
    "rock":             ("terrain",         "floor_scattered"),
    "terrain":          ("terrain",         "route_to_structure"),
}

# category → (role, placement_mode)
_CATEGORY_RULES: Dict[str, tuple] = {
    "furniture":     ("furniture_anchor", "hero_center"),
    "prop":          ("prop",             "scattered"),
    "structure":     ("structure",        "route_to_structure"),
    "architectural": ("architectural",    "near_wall"),
    "electronic":    ("electronic",       "near_wall"),
    "machinery":     ("machinery",        "hero_center"),
    "robot":         ("machinery",        "hero_center"),
    "vehicle":       ("vehicle",          "floor_scattered"),
    "terrain":       ("terrain",          "route_to_structure"),
    "vegetation":    ("vegetation",       "floor_scattered"),
    "pipe":          ("prop",             "near_wall"),
    "character":     ("prop",             "floor_scattered"),
    "creature":      ("prop",             "floor_scattered"),
    "weapon":        ("prop",             "scattered"),
    "hdri":          ("prop",             "scattered"),
    "material":      ("prop",             "scattered"),
}

_DEFAULT_RULE = ("prop", "scattered")


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class PlacementRelationship:
    """Semantic placement rules for one asset type."""

    asset_type:      str   = ""
    role:            str   = "prop"
    placement_mode:  str   = "scattered"
    anchor_type:     Optional[str]  = None   # asset type this clusters around
    distance_min:    float = 0.5
    distance_max:    float = 2.0
    facing:          str   = "camera"        # face_anchor / camera / wall / scattered
    is_structural:   bool  = False           # True → route_to_structure
    notes:           str   = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_type":     self.asset_type,
            "role":           self.role,
            "placement_mode": self.placement_mode,
            "anchor_type":    self.anchor_type,
            "distance_min":   self.distance_min,
            "distance_max":   self.distance_max,
            "facing":         self.facing,
            "is_structural":  self.is_structural,
            "notes":          self.notes,
        }


# Extended per-type relationship metadata
_RELATIONSHIP_DETAILS: Dict[str, Dict[str, Any]] = {
    "chair":        {"anchor_type": "table",         "distance_min": 0.8, "distance_max": 1.2, "facing": "face_anchor"},
    "dining_chair": {"anchor_type": "dining_table",  "distance_min": 0.8, "distance_max": 1.2, "facing": "face_anchor"},
    "stool":        {"anchor_type": "bar_counter",   "distance_min": 0.5, "distance_max": 0.9, "facing": "face_anchor"},
    "bench":        {"anchor_type": None,            "distance_min": 0.1, "distance_max": 0.5, "facing": "camera"},
    "bucket":       {"anchor_type": None,            "distance_min": 0.0, "distance_max": 1.0, "facing": "scattered"},
    "barrel":       {"anchor_type": None,            "distance_min": 0.0, "distance_max": 2.0, "facing": "scattered"},
    "door":         {"anchor_type": "wall",          "distance_min": 0.0, "distance_max": 0.1, "facing": "camera"},
    "window":       {"anchor_type": "wall",          "distance_min": 0.0, "distance_max": 0.1, "facing": "camera"},
    "plant":        {"anchor_type": None,            "distance_min": 0.0, "distance_max": 0.5, "facing": "scattered"},
}


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class PlacementRelationships:
    """Provides role, placement mode, and structural routing for any asset.

    Never raises. Returns safe defaults ("prop", "scattered") for unknowns.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def get_role(self, asset_type: str, category: str) -> str:
        """Return the production role for an asset.

        Checks asset_type first, then category. Falls back to "prop".
        """
        t = asset_type.lower().strip().replace(" ", "_")
        if t in _TYPE_RULES:
            return _TYPE_RULES[t][0]
        c = category.lower().strip()
        if c in _CATEGORY_RULES:
            return _CATEGORY_RULES[c][0]
        # Name-based structural hint
        if any(hint in t for hint in STRUCTURAL_KEYWORD_HINTS):
            return "structure"
        return _DEFAULT_RULE[0]

    def get_placement_mode(self, asset_type: str, category: str) -> str:
        """Return the placement mode for an asset."""
        t = asset_type.lower().strip().replace(" ", "_")
        if t in _TYPE_RULES:
            return _TYPE_RULES[t][1]
        c = category.lower().strip()
        if c in _CATEGORY_RULES:
            return _CATEGORY_RULES[c][1]
        if any(hint in t for hint in STRUCTURAL_KEYWORD_HINTS):
            return "route_to_structure"
        return _DEFAULT_RULE[1]

    def get_relationship(self, asset_type: str, category: str) -> PlacementRelationship:
        """Return the full PlacementRelationship for an asset.

        Never raises.
        """
        try:
            t_key = asset_type.lower().strip().replace(" ", "_")
            role  = self.get_role(asset_type, category)
            mode  = self.get_placement_mode(asset_type, category)
            is_structural = (mode == "route_to_structure")

            details = _RELATIONSHIP_DETAILS.get(t_key, {})

            return PlacementRelationship(
                asset_type    = asset_type,
                role          = role,
                placement_mode = mode,
                anchor_type   = details.get("anchor_type"),
                distance_min  = float(details.get("distance_min", 0.5)),
                distance_max  = float(details.get("distance_max", 2.0)),
                facing        = str(details.get("facing", "camera")),
                is_structural = is_structural,
                notes         = f"role={role}, mode={mode}",
            )
        except Exception:
            return PlacementRelationship()

    def is_structural(self, asset_type: str, category: str, asset_name: str = "") -> bool:
        """Return True if this asset should be routed to EnvironmentStructureBuilder."""
        mode = self.get_placement_mode(asset_type, category)
        if mode == "route_to_structure":
            return True
        # Name hint check on actual asset name
        name_lower = asset_name.lower().strip().replace(" ", "_")
        return any(hint in name_lower for hint in STRUCTURAL_KEYWORD_HINTS)

    def filter_structural(
        self, assets: List[Dict[str, Any]]
    ) -> tuple:
        """Partition assets into (placeable, structural) lists.

        Returns (placeable_assets, structural_assets) — structural assets
        should be passed to EnvironmentStructureBuilder, not the furniture
        placement engine.
        """
        placeable: List[Dict[str, Any]] = []
        structural: List[Dict[str, Any]] = []

        for asset in assets:
            a_type = str(asset.get("type") or asset.get("asset_type") or "")
            a_cat  = str(asset.get("category") or "")
            a_name = str(asset.get("name") or asset.get("asset_id") or "")
            if self.is_structural(a_type, a_cat, a_name):
                structural.append(asset)
            else:
                placeable.append(asset)

        return placeable, structural

    def get_role_summary(self, assets: List[Dict[str, Any]]) -> Dict[str, int]:
        """Return a count of assets by role."""
        summary: Dict[str, int] = {}
        for asset in assets:
            a_type = str(asset.get("type") or asset.get("asset_type") or "")
            a_cat  = str(asset.get("category") or "")
            role   = self.get_role(a_type, a_cat)
            summary[role] = summary.get(role, 0) + 1
        return summary


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[PlacementRelationships] = None
_LOCK = threading.Lock()


def get_placement_relationships() -> PlacementRelationships:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = PlacementRelationships()
        return _INSTANCE


def reset_placement_relationships_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
