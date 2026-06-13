"""
placement_affinity.py — §45 Semantic Asset Suitability Ranking
===============================================================
Scores how well an asset fits a specific placement context (around_table,
wall_mounted, corner, etc.).

Public API:
    get_placement_affinity() -> PlacementAffinity
    reset_placement_affinity_for_tests()

    PlacementAffinity.score(asset, placement_context) -> float  0.0–1.0
"""

import re
import threading
from typing import Dict, List

# Types accepted at each placement context
_PLACEMENT_ACCEPTED: Dict[str, List[str]] = {
    "around_table": ["chair", "stool", "seat", "seating", "throne", "perch"],
    "around_bar_counter": ["stool", "barstool", "chair", "seat"],
    "on_table": [
        "cup", "mug", "bottle", "glass", "plate", "food", "book", "lantern",
        "candle", "bowl", "basket", "toolbox", "lamp",
    ],
    "near_wall": [
        "bench", "shelf", "cabinet", "barrel", "bucket", "poster", "lantern",
        "torch", "painting", "rack", "wardrobe", "sofa",
    ],
    "wall_mounted": [
        "poster", "sign", "painting", "lantern", "torch", "bracket",
        "sconce", "shield", "clock", "frame",
    ],
    "corner": [
        "barrel", "bucket", "plant", "container", "crate", "chest",
        "statue", "armor", "trash", "drum",
    ],
    "hero_center": [
        "table", "desk", "machine", "console", "throne", "altar",
        "workbench", "anvil", "pool",
    ],
    "ceiling_mounted": [
        "light", "lantern", "chandelier", "hanging lamp", "pendant",
        "fan", "sprinkler",
    ],
    "floor_scattered": [
        "bottle", "debris", "rubble", "container", "prop", "rock",
        "bone", "leaf",
    ],
    "stacked": [
        "crate", "box", "barrel", "pallet", "book", "container",
    ],
    "around_anchor": [
        "chair", "stool", "seat", "bench", "table", "shelf",
    ],
    "service_area": [
        "barrel", "bucket", "crate", "toolbox", "drum", "tank",
    ],
}

# Types explicitly rejected at each placement context
_PLACEMENT_REJECTED: Dict[str, List[str]] = {
    "around_table": ["shelf", "cabinet", "wall", "beam", "column", "machine", "vehicle"],
    "around_bar_counter": ["table", "shelf", "cabinet", "beam", "machine", "vehicle"],
    "on_table": ["chair", "table", "beam", "machine", "vehicle", "barrel", "shelf", "column"],
    "near_wall": ["vehicle", "overhead", "machine"],
    "wall_mounted": ["table", "chair", "barrel", "machine", "vehicle", "beam", "column"],
    "corner": ["table", "machine", "vehicle", "poster", "door", "window"],
    "hero_center": ["chair", "barrel", "bucket", "poster", "cup", "bottle"],
    "ceiling_mounted": ["table", "chair", "barrel", "machine", "vehicle", "beam"],
    "floor_scattered": ["table", "machine", "vehicle", "beam", "wall"],
    "stacked": ["chair", "machine", "vehicle", "poster", "lantern"],
    "around_anchor": ["beam", "column", "wall", "machine", "vehicle"],
    "service_area": ["chair", "table", "poster", "machine", "vehicle"],
}


def _extract_placement_text(asset: dict) -> str:
    parts: List[str] = []
    for field in ("type", "asset_type", "placement_type", "name", "category"):
        v = asset.get(field, "")
        if isinstance(v, str):
            parts.append(re.sub(r"[\-_]+", " ", v.lower()))
    tags = asset.get("tags", [])
    if isinstance(tags, list):
        for t in tags:
            parts.append(re.sub(r"[\-_]+", " ", str(t).lower()))
    return " ".join(parts)


class PlacementAffinity:
    """Scores asset suitability for a specific placement context."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def score(self, asset: dict, placement_context: str) -> float:
        """Return 0.0–1.0 placement fit score."""
        try:
            if not placement_context:
                return 0.5
            ctx = placement_context.lower().replace("-", "_").replace(" ", "_")
            accepted = _PLACEMENT_ACCEPTED.get(ctx, [])
            rejected = _PLACEMENT_REJECTED.get(ctx, [])
            text = _extract_placement_text(asset)

            # Accepted hit
            for term in accepted:
                if re.sub(r"[\-_]+", " ", term.lower()) in text:
                    return 1.0

            # Rejected hit
            for term in rejected:
                if re.sub(r"[\-_]+", " ", term.lower()) in text:
                    return 0.1

            return 0.4  # no match — mild negative
        except Exception:
            return 0.5

    def get_accepted(self, placement_context: str) -> List[str]:
        ctx = placement_context.lower().replace("-", "_").replace(" ", "_")
        return list(_PLACEMENT_ACCEPTED.get(ctx, []))

    def get_rejected(self, placement_context: str) -> List[str]:
        ctx = placement_context.lower().replace("-", "_").replace(" ", "_")
        return list(_PLACEMENT_REJECTED.get(ctx, []))

    def known_contexts(self) -> List[str]:
        return sorted(_PLACEMENT_ACCEPTED.keys())


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: PlacementAffinity | None = None
_instance_lock = threading.Lock()


def get_placement_affinity() -> PlacementAffinity:
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = PlacementAffinity()
    return _instance


def reset_placement_affinity_for_tests() -> None:
    global _instance
    with _instance_lock:
        _instance = None
