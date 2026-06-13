"""
affordance_engine.py — §46 Semantic Furniture Layout Engine
===========================================================
Determines what each asset type can hold, support, or attract.

An "affordance" is a capability an asset offers:
  provides_surface  → has a horizontal surface that can hold smaller items
  provides_around   → attracts seating/orbiting assets
  is_anchor         → is a major focal point (table, machine, fireplace)
  is_wall_attachable → can mount flush on a wall
  is_ceiling_hangable → can hang from a ceiling
  is_against_wall   → naturally rests against a wall
  is_corner_placed  → naturally placed in a room corner

Public API:
    AffordanceProfile
    AffordanceEngine
    get_affordance_engine()
    reset_affordance_engine_for_tests()
    ANCHOR_TYPES
    PLACEMENT_MODES
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional


# ---------------------------------------------------------------------------
# Surface support table — what each host type can hold on its surface
# ---------------------------------------------------------------------------
_SURFACE_SUPPORTS: Dict[str, List[str]] = {
    "table":        ["bottle", "cup", "book", "plate", "lantern", "glass", "mug",
                     "candle", "bowl", "vase", "tool", "container", "small_prop",
                     "whiskey_bottle", "knife", "fork",
                     "teapot", "kettle", "pitcher", "jar", "pot", "figurine",
                     "candlestick", "inkwell", "scroll", "prop"],
    "desk":         ["book", "cup", "tool", "lamp", "container", "small_prop", "paper",
                     "monitor", "keyboard"],
    "workbench":    ["tool", "container", "machine_part", "wrench", "hammer", "small_prop",
                     "blueprint", "vice"],
    "bar_counter":  ["bottle", "cup", "glass", "mug", "bowl", "container", "small_prop",
                     "whiskey_bottle", "beer_mug"],
    "shelf":        ["book", "bottle", "tool", "container", "vase", "small_prop",
                     "trophy", "figurine"],
    "counter":      ["bottle", "cup", "bowl", "container", "small_prop"],
    "crate":        ["small_prop", "container", "tool"],
    "pallet":       ["crate", "barrel", "container"],
    "cabinet":      ["small_prop", "container", "vase"],
    "mantle":       ["candle", "vase", "small_prop", "lantern", "clock"],
    "console":      ["monitor", "electronic", "small_prop", "container"],
}

# ---------------------------------------------------------------------------
# Around-support table — what orbits each anchor type
# ---------------------------------------------------------------------------
_AROUND_SUPPORTS: Dict[str, List[str]] = {
    "table":        ["chair", "stool"],
    "bar_counter":  ["stool", "chair"],
    "fireplace":    ["chair", "bench"],
    "campfire":     ["chair", "bench", "barrel", "stool"],
    "throne":       ["chair"],
    "altar":        ["chair", "stool"],
}

# ---------------------------------------------------------------------------
# Wall-attachable types
# ---------------------------------------------------------------------------
_WALL_ATTACHED: List[str] = [
    "poster", "painting", "sign", "clock", "shelf",
    "lantern", "torch", "sconce", "banner", "mirror",
    "wanted_poster", "notice", "certificate", "trophy_mount",
    "mounted_head", "rack", "hook", "coat_hook",
]

# ---------------------------------------------------------------------------
# Ceiling-hangable types
# ---------------------------------------------------------------------------
_CEILING_HUNG: List[str] = [
    "lantern", "chandelier", "pendant_light", "hanging_light",
    "rope", "chain", "fan",
]

# ---------------------------------------------------------------------------
# Against-wall types
# ---------------------------------------------------------------------------
_AGAINST_WALL: List[str] = [
    "bench", "cabinet", "shelf", "server_rack", "locker",
    "wardrobe", "bookcase", "piano", "fireplace",
]

# ---------------------------------------------------------------------------
# Corner-placed types
# ---------------------------------------------------------------------------
_CORNER_PLACED: List[str] = [
    "barrel", "bucket", "crate", "plant", "trash_can",
    "container", "hay_bale", "oil_drum",
]

# ---------------------------------------------------------------------------
# Anchor types
# ---------------------------------------------------------------------------
ANCHOR_TYPES: FrozenSet[str] = frozenset({
    "table", "desk", "workbench", "bar_counter", "fireplace",
    "campfire", "machine", "large_machine", "reactor", "console",
    "altar", "throne", "bed", "sofa", "piano",
})

# ---------------------------------------------------------------------------
# Placement modes
# ---------------------------------------------------------------------------
PLACEMENT_MODES: Dict[str, str] = {
    "chair":          "around_anchor",
    "stool":          "around_anchor",
    "bottle":         "on_surface",
    "whiskey_bottle": "on_surface",
    "cup":            "on_surface",
    "glass":          "on_surface",
    "mug":            "on_surface",
    "book":           "on_surface",
    "plate":          "on_surface",
    "bowl":           "on_surface",
    "tool":           "on_surface",
    "candle":         "on_surface",
    "vase":           "on_surface",
    "monitor":        "on_surface",
    "teapot":         "on_surface",
    "kettle":         "on_surface",
    "pitcher":        "on_surface",
    "jar":            "on_surface",
    "pot":            "on_surface",
    "figurine":       "on_surface",
    "candlestick":    "on_surface",
    "inkwell":        "on_surface",
    "scroll":         "on_surface",
    "lantern":        "wall_or_ceiling",
    "torch":          "wall_only",
    "sconce":         "wall_only",
    "poster":         "wall_only",
    "painting":       "wall_only",
    "wanted_poster":  "wall_only",
    "sign":           "wall_only",
    "clock":          "wall_only",
    "banner":         "wall_only",
    "mirror":         "wall_only",
    "bench":          "against_wall",
    "cabinet":        "against_wall",
    "shelf":          "against_wall",
    "barrel":         "corner",
    "bucket":         "corner",
    "crate":          "corner",
    "oil_drum":       "corner",
    "hay_bale":       "corner",
    "plant":          "corner",
    "table":          "hero_center",
    "desk":           "hero_center",
    "workbench":      "near_wall",
    "machine":        "hero_center",
    "large_machine":  "hero_center",
    "console":        "hero_center",
    "fireplace":      "against_wall",
    "campfire":       "hero_center",
    "bed":            "hero_center",
    "sofa":           "hero_center",
}

_DEFAULT_MODE = "scattered"

# ---------------------------------------------------------------------------
# Multi-word alias table — maps common Megascans / Fab name fragments to
# canonical placement types. Checked BEFORE keyword scan so specific phrases
# beat short substrings (e.g. "bar stool" ≠ "bar_counter").
# ---------------------------------------------------------------------------
_TYPE_ALIASES: Dict[str, str] = {
    # Bar / counter variants
    "bar counter":   "bar_counter",
    "bar unit":      "bar_counter",
    "saloon bar":    "bar_counter",
    "counter bar":   "bar_counter",
    "bar top":       "bar_counter",
    # Table variants
    "dining table":  "table",
    "coffee table":  "table",
    "side table":    "table",
    "end table":     "table",
    "kitchen table": "table",
    "dinner table":  "table",
    "picnic table":  "table",
    # Workbench variants
    "work bench":    "workbench",
    "work table":    "workbench",
    # Desk / nightstand
    "night stand":   "desk",
    "nightstand":    "desk",
    # Seating
    "arm chair":     "chair",
    "armchair":      "chair",
    "rocking chair": "chair",
    "bar stool":     "stool",
    "bar chair":     "stool",
    # Bottle variants
    "whiskey bottle": "bottle",
    "wine bottle":    "bottle",
    "beer bottle":    "bottle",
    "glass bottle":   "bottle",
    # Teapot / kettle variants
    "tea pot":        "teapot",
    "tea kettle":     "kettle",
    "ceramic teapot": "teapot",
    "clay teapot":    "teapot",
    "cast iron kettle": "kettle",
    # Jar / pot variants
    "clay pot":       "pot",
    "clay jar":       "jar",
    "ceramic jar":    "jar",
    "ceramic pot":    "pot",
    "wooden bowl":    "bowl",
}


@dataclass
class AffordanceProfile:
    asset_type: str
    provides_surface: bool = False
    surface_children: List[str] = field(default_factory=list)
    provides_around: bool = False
    around_children: List[str] = field(default_factory=list)
    is_anchor: bool = False
    is_wall_attachable: bool = False
    is_ceiling_hangable: bool = False
    is_against_wall: bool = False
    is_corner_placed: bool = False
    placement_mode: str = "scattered"

    def to_dict(self) -> dict:
        return {
            "asset_type":        self.asset_type,
            "provides_surface":  self.provides_surface,
            "surface_children":  list(self.surface_children),
            "provides_around":   self.provides_around,
            "around_children":   list(self.around_children),
            "is_anchor":         self.is_anchor,
            "is_wall_attachable": self.is_wall_attachable,
            "is_ceiling_hangable": self.is_ceiling_hangable,
            "is_against_wall":   self.is_against_wall,
            "is_corner_placed":  self.is_corner_placed,
            "placement_mode":    self.placement_mode,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AffordanceProfile":
        return cls(
            asset_type=d.get("asset_type", ""),
            provides_surface=bool(d.get("provides_surface", False)),
            surface_children=list(d.get("surface_children", [])),
            provides_around=bool(d.get("provides_around", False)),
            around_children=list(d.get("around_children", [])),
            is_anchor=bool(d.get("is_anchor", False)),
            is_wall_attachable=bool(d.get("is_wall_attachable", False)),
            is_ceiling_hangable=bool(d.get("is_ceiling_hangable", False)),
            is_against_wall=bool(d.get("is_against_wall", False)),
            is_corner_placed=bool(d.get("is_corner_placed", False)),
            placement_mode=d.get("placement_mode", "scattered"),
        )


class AffordanceEngine:
    """Determines placement affordances for asset types. Never raises."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def get_affordances(self, asset_type: str) -> AffordanceProfile:
        """Return the full AffordanceProfile for an asset type."""
        try:
            t = asset_type.lower().strip()
            return AffordanceProfile(
                asset_type=t,
                provides_surface=(t in _SURFACE_SUPPORTS),
                surface_children=list(_SURFACE_SUPPORTS.get(t, [])),
                provides_around=(t in _AROUND_SUPPORTS),
                around_children=list(_AROUND_SUPPORTS.get(t, [])),
                is_anchor=(t in ANCHOR_TYPES),
                is_wall_attachable=(t in _WALL_ATTACHED),
                is_ceiling_hangable=(t in _CEILING_HUNG),
                is_against_wall=(t in _AGAINST_WALL),
                is_corner_placed=(t in _CORNER_PLACED),
                placement_mode=PLACEMENT_MODES.get(t, _DEFAULT_MODE),
            )
        except Exception:
            return AffordanceProfile(asset_type=asset_type)

    def can_support(self, host_type: str, child_type: str) -> bool:
        """True if host_type has a surface that can hold child_type (exact match only)."""
        try:
            h = host_type.lower().strip()
            c = child_type.lower().strip()
            return c in _SURFACE_SUPPORTS.get(h, [])
        except Exception:
            return False

    def can_surround(self, host_type: str, child_type: str) -> bool:
        """True if child_type naturally orbits host_type."""
        try:
            h = host_type.lower().strip()
            c = child_type.lower().strip()
            return c in _AROUND_SUPPORTS.get(h, [])
        except Exception:
            return False

    def get_placement_mode(self, asset_type: str) -> str:
        """Return the canonical placement mode for an asset type."""
        try:
            return PLACEMENT_MODES.get(asset_type.lower().strip(), _DEFAULT_MODE)
        except Exception:
            return _DEFAULT_MODE

    def get_surface_children(self, host_type: str) -> List[str]:
        """Return types that can be placed on host_type's surface."""
        try:
            return list(_SURFACE_SUPPORTS.get(host_type.lower().strip(), []))
        except Exception:
            return []

    def get_around_children(self, host_type: str) -> List[str]:
        """Return types that orbit host_type."""
        try:
            return list(_AROUND_SUPPORTS.get(host_type.lower().strip(), []))
        except Exception:
            return []

    def infer_type(self, asset: dict) -> str:
        """Infer asset type from dict fields. Never raises."""
        try:
            t = (
                asset.get("placement_type")
                or asset.get("type")
                or asset.get("asset_type")
                or ""
            ).lower().strip()
            if t:
                return t
            name = (asset.get("name") or "").lower()
            # Normalize spaces/hyphens → underscores so "Bar Counter" matches "bar_counter"
            name_us = name.replace(" ", "_").replace("-", "_")
            # Alias table: multi-word Megascans names → canonical type
            for alias, resolved in _TYPE_ALIASES.items():
                if alias in name:
                    return resolved
            # Keyword scan — longest match wins; check both forms
            for keyword in sorted(
                list(PLACEMENT_MODES.keys()) + list(ANCHOR_TYPES),
                key=len, reverse=True,
            ):
                if keyword in name or keyword in name_us:
                    return keyword
            return "prop"
        except Exception:
            return "prop"


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[AffordanceEngine] = None
_lock = threading.Lock()


def get_affordance_engine() -> AffordanceEngine:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = AffordanceEngine()
    return _instance


def reset_affordance_engine_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
