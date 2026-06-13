"""
decoration_layout_engine.py — §46 Semantic Furniture Layout Engine
=================================================================
Assigns contextual placement targets to decorative assets based on the
environment. Per-environment preference tables drive decoration selection
and routing.

Public API:
    DecorativeItem
    DecorationLayoutResult
    DecorationLayoutEngine
    get_decoration_layout_engine()
    reset_decoration_layout_engine_for_tests()
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# Per-environment preferred decoration asset types
_ENV_PREFERENCES: Dict[str, List[str]] = {
    "western_room": [
        "barrel", "lantern", "whiskey_bottle", "wanted_poster", "rope",
        "bucket", "hay_bale", "saddle", "spittoon",
    ],
    "saloon": [
        "barrel", "lantern", "bottle", "wanted_poster", "card_deck",
        "spittoon", "chandelier", "stool",
    ],
    "industrial_hangar": [
        "tool", "container", "pipe", "warning_sign", "machine_part",
        "oil_drum", "chain", "rope",
    ],
    "warehouse": [
        "crate", "barrel", "pallet", "container", "chain", "hook",
        "oil_drum",
    ],
    "robotics_lab": [
        "electronic", "container", "tool", "cable", "monitor",
        "warning_sign", "machine_part",
    ],
    "research_lab": [
        "container", "electronic", "cable", "monitor", "certificate",
        "small_prop",
    ],
    "medical_lab": [
        "container", "monitor", "cable", "equipment", "small_prop",
        "certificate",
    ],
    "control_room": [
        "monitor", "electronic", "cable", "warning_sign", "small_prop",
    ],
    "castle_hall": [
        "banner", "torch", "armor_stand", "tapestry", "candle",
        "shield", "weapon_rack",
    ],
    "dungeon": [
        "torch", "chain", "barrel", "iron_door", "shackles",
    ],
    "city_street": [
        "trash_can", "fire_hydrant", "newspaper", "small_prop", "street_sign",
    ],
    "forest": [
        "mushroom", "rock", "stick", "log", "leaf_pile",
    ],
    "desert": [
        "rock", "cactus", "skull", "small_prop",
    ],
    "office": [
        "paper", "book", "cup", "monitor", "small_prop",
    ],
    "library": [
        "book", "candle", "vase", "small_prop", "painting",
    ],
    "space_station": [
        "electronic", "cable", "container", "monitor", "warning_sign",
    ],
    "sci_fi_corridor": [
        "electronic", "cable", "warning_sign", "small_prop",
    ],
    "cyberpunk_city": [
        "neon_sign", "electronic", "cable", "trash_can",
    ],
    "military_base": [
        "ammo_crate", "barrel", "sandbag", "warning_sign", "rope",
    ],
    "survival_camp": [
        "barrel", "crate", "rope", "lantern", "blanket", "bucket",
    ],
    "hotel_lobby": [
        "vase", "painting", "candle", "small_prop", "clock",
    ],
    "restaurant": [
        "vase", "candle", "bottle", "small_prop",
    ],
    "living_room": [
        "book", "vase", "candle", "small_prop", "painting",
    ],
}

_DEFAULT_PREFERENCES = ["barrel", "crate", "container", "small_prop"]

# Preferred placement target per asset type
_PLACEMENT_TARGET: Dict[str, str] = {
    "barrel":         "corner",
    "hay_bale":       "corner",
    "oil_drum":       "corner",
    "bucket":         "corner",
    "crate":          "corner",
    "trash_can":      "corner",
    "lantern":        "wall_mounted",
    "torch":          "wall_only",
    "sconce":         "wall_only",
    "poster":         "wall_only",
    "wanted_poster":  "wall_only",
    "painting":       "wall_only",
    "banner":         "wall_only",
    "neon_sign":      "wall_only",
    "street_sign":    "wall_only",
    "warning_sign":   "wall_only",
    "certificate":    "wall_only",
    "clock":          "wall_only",
    "bottle":         "on_surface",
    "whiskey_bottle": "on_surface",
    "cup":            "on_surface",
    "glass":          "on_surface",
    "mug":            "on_surface",
    "book":           "on_surface",
    "candle":         "on_surface",
    "vase":           "on_surface",
    "tool":           "near_anchor",
    "rope":           "near_wall",
    "chain":          "near_wall",
    "pipe":           "near_wall",
    "cable":          "near_anchor",
}
_DEFAULT_TARGET = "scattered"

# Canonical scatter positions
_SCATTER_POSITIONS = [
    [-2.50, 0.0, -3.00],
    [ 2.50, 0.0, -3.00],
    [-3.00, 0.0,  0.00],
    [ 3.00, 0.0,  0.00],
    [-2.50, 0.0,  3.00],
    [ 2.50, 0.0,  3.00],
    [-1.00, 0.0, -2.50],
    [ 1.00, 0.0, -2.50],
    [-1.00, 0.0,  2.50],
    [ 1.00, 0.0,  2.50],
]
_CORNER_POSITIONS = [
    [-3.50, 0.0, -3.50],
    [ 3.50, 0.0, -3.50],
    [-3.50, 0.0,  3.50],
    [ 3.50, 0.0,  3.50],
]


@dataclass
class DecorativeItem:
    asset_id: str
    asset_name: str
    asset_type: str
    placement_target: str
    position: List[float]
    contextual: bool = False   # True if asset type is in environment preference list

    def to_dict(self) -> dict:
        return {
            "asset_id":         self.asset_id,
            "asset_name":       self.asset_name,
            "asset_type":       self.asset_type,
            "placement_target": self.placement_target,
            "position":         [round(v, 3) for v in self.position],
            "contextual":       self.contextual,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "DecorativeItem":
        return cls(
            asset_id=d.get("asset_id", ""),
            asset_name=d.get("asset_name", ""),
            asset_type=d.get("asset_type", ""),
            placement_target=d.get("placement_target", "scattered"),
            position=list(d.get("position", [0.0, 0.0, 0.0])),
            contextual=bool(d.get("contextual", False)),
        )


@dataclass
class DecorationLayoutResult:
    environment: str
    items: List[DecorativeItem] = field(default_factory=list)
    preferred_types: List[str] = field(default_factory=list)
    ok: bool = True
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "environment":     self.environment,
            "items":           [i.to_dict() for i in self.items],
            "preferred_types": list(self.preferred_types),
            "ok":              self.ok,
            "errors":          list(self.errors),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "DecorationLayoutResult":
        return cls(
            environment=d.get("environment", ""),
            items=[DecorativeItem.from_dict(i) for i in d.get("items", [])],
            preferred_types=list(d.get("preferred_types", [])),
            ok=bool(d.get("ok", True)),
            errors=list(d.get("errors", [])),
        )


class DecorationLayoutEngine:
    """Assigns contextual placement targets to decorative assets."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def place_decorations(
        self,
        assets: List[Dict[str, Any]],
        environment: str = "",
    ) -> DecorationLayoutResult:
        """Assign placement targets to decorative assets for the given environment. Never raises."""
        try:
            return self._place(assets, environment)
        except Exception as exc:
            return DecorationLayoutResult(
                environment=environment,
                ok=False,
                errors=[f"DecorationLayoutEngine.place_decorations failed: {exc}"],
            )

    def _place(
        self,
        assets: List[Dict[str, Any]],
        environment: str,
    ) -> DecorationLayoutResult:
        env = environment.lower()
        preferred = list(_ENV_PREFERENCES.get(env, _DEFAULT_PREFERENCES))
        items: List[DecorativeItem] = []

        corner_idx = 0
        scatter_idx = 0
        wall_y = 1.60

        for i, asset in enumerate(assets):
            a_type = str(
                asset.get("placement_type")
                or asset.get("type")
                or asset.get("asset_type")
                or "prop"
            ).lower()

            target = _PLACEMENT_TARGET.get(a_type, _DEFAULT_TARGET)
            contextual = a_type in preferred

            if target in ("wall_only", "wall_mounted"):
                pos = [0.0, wall_y, -4.0]
            elif target == "corner":
                pos = list(_CORNER_POSITIONS[corner_idx % len(_CORNER_POSITIONS)])
                corner_idx += 1
            elif target == "on_surface":
                # These items reached decoration without a host — place at floor level.
                # Scene Reality Validator will flag them as INVALID_SUPPORT_RELATION
                # so they are visible and fixable rather than hidden at a fake height.
                pos = [0.0, 0.0, 0.0]
            elif target == "near_wall":
                pos = [0.0, 0.0, -3.5]
            elif target == "near_anchor":
                pos = [1.0, 0.0, 0.5]
            else:
                pos = list(_SCATTER_POSITIONS[scatter_idx % len(_SCATTER_POSITIONS)])
                scatter_idx += 1

            items.append(DecorativeItem(
                asset_id=str(asset.get("asset_id") or asset.get("name") or f"deco_{i}"),
                asset_name=str(asset.get("name") or asset.get("asset_id") or ""),
                asset_type=a_type,
                placement_target=target,
                position=pos,
                contextual=contextual,
            ))

        return DecorationLayoutResult(
            environment=env,
            items=items,
            preferred_types=preferred,
        )

    def get_preferred_types(self, environment: str) -> List[str]:
        """Return the preferred decoration types for an environment."""
        return list(_ENV_PREFERENCES.get(environment.lower(), _DEFAULT_PREFERENCES))


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[DecorationLayoutEngine] = None
_lock = threading.Lock()


def get_decoration_layout_engine() -> DecorationLayoutEngine:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = DecorationLayoutEngine()
    return _instance


def reset_decoration_layout_engine_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
