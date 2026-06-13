"""
role_affinity.py — §45 Semantic Asset Suitability Ranking
==========================================================
Scores how well a candidate asset matches a requested role/slot type.

Public API:
    get_role_affinity() -> RoleAffinity
    reset_role_affinity_for_tests()

    RoleAffinity.score(asset, role) -> float   0.0–1.0
    RoleAffinity.get_exact(role) -> list[str]
    RoleAffinity.get_rejected(role) -> list[str]
"""

import re
import threading
from typing import Dict, List

# Exact match → 1.0
_ROLE_EXACT: Dict[str, List[str]] = {
    "chair": ["chair", "seat", "chair seat"],
    "table": ["table", "dining table", "work table"],
    "barrel": ["barrel", "cask", "keg"],
    "bucket": ["bucket", "pail"],
    "lantern": ["lantern", "oil lantern", "wall lantern", "hanging lantern"],
    "lamp": ["lamp", "oil lamp", "table lamp"],
    "poster": ["poster", "wanted poster", "wall poster", "sign"],
    "shelf": ["shelf", "shelving", "bookshelf"],
    "cabinet": ["cabinet", "cupboard", "locker"],
    "bench": ["bench", "pew", "settee"],
    "machine": ["machine", "machinery", "engine"],
    "pipe": ["pipe", "piping", "tube"],
    "crate": ["crate", "chest"],
    "box": ["box", "crate", "container"],
    "door": ["door", "doorway"],
    "window": ["window", "porthole"],
    "console": ["console", "terminal"],
    "bottle": ["bottle", "flask", "jug"],
    "cup": ["cup", "mug"],
    "torch": ["torch", "brazier"],
    "statue": ["statue", "sculpture", "figurine"],
    "plant": ["plant", "fern", "flower"],
    "vehicle": ["vehicle", "car", "truck"],
    "beam": ["beam", "support beam", "roof beam"],
    "column": ["column", "pillar", "post"],
    "wall": ["wall", "partition"],
    "floor": ["floor", "flooring"],
    "stool": ["stool", "barstool"],
    "sofa": ["sofa", "couch", "settee"],
    "desk": ["desk", "writing desk"],
    "workbench": ["workbench", "workshop table"],
    "painting": ["painting", "artwork", "picture"],
    "candle": ["candle", "candlestick"],
    "chandelier": ["chandelier", "pendant light"],
    "drum": ["drum", "oil drum"],
    "toolbox": ["toolbox", "tool chest"],
    "rack": ["rack", "server rack"],
    "tank": ["tank", "storage tank"],
    "anvil": ["anvil"],
    "fireplace": ["fireplace", "hearth"],
    "book": ["book", "tome", "volume"],
}

# Partial/related match → 0.5–0.75
_ROLE_PARTIAL: Dict[str, List[str]] = {
    "chair": ["stool", "seating", "throne", "perch"],
    "table": ["desk", "workbench", "counter", "bar counter", "surface", "altar"],
    "barrel": ["container", "drum", "storage", "cask"],
    "bucket": ["container", "bin", "vessel"],
    "lantern": ["torch", "candle", "light fixture", "chandelier", "sconce", "lamp"],
    "lamp": ["lantern", "torch", "sconce", "light fixture"],
    "poster": ["painting", "picture", "artwork", "wall art", "plaque", "notice"],
    "shelf": ["rack", "bookcase", "display case"],
    "cabinet": ["wardrobe", "dresser", "hutch"],
    "machine": ["device", "equipment", "mechanism", "apparatus"],
    "crate": ["pallet", "box", "chest", "container"],
    "box": ["crate", "chest", "pallet"],
    "console": ["monitor", "panel", "display", "terminal"],
    "bottle": ["container", "vessel", "carafe"],
    "cup": ["bowl", "vessel", "glass"],
    "torch": ["lantern", "flame", "fire"],
    "plant": ["tree", "bush", "vegetation"],
    "vehicle": ["cart", "wagon"],
    "toolbox": ["crate", "cabinet", "storage"],
    "drum": ["barrel", "container"],
    "painting": ["poster", "picture", "artwork"],
    "stool": ["chair", "seat", "bench"],
    "sofa": ["bench", "chair", "seat"],
    "desk": ["table", "workbench", "counter"],
    "book": ["tome", "journal", "manual"],
    "fireplace": ["furnace", "hearth", "brazier"],
}

# Rejected types → 0.0–0.3 (wrong role entirely)
_ROLE_REJECTED: Dict[str, List[str]] = {
    "chair": ["table", "shelf", "cabinet", "beam", "wall", "column", "machine", "vehicle"],
    "table": ["chair", "shelf", "barrel", "column", "beam", "wall", "machine"],
    "barrel": ["chair", "table", "beam", "wall", "column", "machine", "vehicle"],
    "bucket": ["table", "chair", "shelf", "machine", "vehicle", "beam"],
    "lantern": ["table", "chair", "barrel", "shelf", "machine", "vehicle", "door"],
    "lamp": ["table", "chair", "barrel", "machine", "vehicle"],
    "poster": ["table", "chair", "barrel", "machine", "vehicle", "beam", "terrain"],
    "shelf": ["chair", "barrel", "machine", "vehicle", "beam", "terrain"],
    "machine": ["chair", "cup", "bottle", "poster", "plant", "book"],
    "pipe": ["chair", "table", "cup", "bottle", "poster"],
    "crate": ["chair", "lantern", "poster", "machine"],
    "console": ["chair", "barrel", "lantern", "beam"],
    "bottle": ["table", "machine", "vehicle", "beam", "wall"],
    "cup": ["table", "machine", "vehicle", "beam"],
    "plant": ["machine", "vehicle", "beam", "wall"],
    "vehicle": ["chair", "table", "shelf", "cup", "bottle", "book"],
    "beam": ["chair", "cup", "bottle", "lantern", "poster"],
    "column": ["chair", "cup", "bottle", "lantern", "poster"],
    "fireplace": ["vehicle", "machine", "chair", "bottle"],
}


def _extract_role_text(asset: dict) -> str:
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


class RoleAffinity:
    """Scores asset–role slot compatibility."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def score(self, asset: dict, role: str) -> float:
        """Return 0.0–1.0 role fit score."""
        try:
            if not role:
                return 0.5
            role_norm = re.sub(r"[\-_]+", " ", role.lower())
            text = _extract_role_text(asset)

            # Check exact list
            exact = _ROLE_EXACT.get(role_norm, [role_norm])
            for e in exact:
                e_norm = re.sub(r"[\-_]+", " ", e.lower())
                if e_norm in text:
                    return 1.0

            # Check rejected list
            rejected = _ROLE_REJECTED.get(role_norm, [])
            rej_hits = sum(
                1 for r in rejected
                if re.sub(r"[\-_]+", " ", r.lower()) in text
            )
            if rej_hits > 0:
                return max(0.0, 0.3 - rej_hits * 0.1)

            # Check partial list
            partial = _ROLE_PARTIAL.get(role_norm, [])
            part_hits = sum(
                1 for p in partial
                if re.sub(r"[\-_]+", " ", p.lower()) in text
            )
            if part_hits > 0:
                return min(0.75, 0.5 + part_hits * 0.12)

            # No signal — mild negative (unknown type)
            return 0.3
        except Exception:
            return 0.5

    def get_exact(self, role: str) -> List[str]:
        return list(_ROLE_EXACT.get(role, [role]))

    def get_rejected(self, role: str) -> List[str]:
        return list(_ROLE_REJECTED.get(role, []))

    def known_roles(self) -> List[str]:
        return sorted(_ROLE_EXACT.keys())


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: RoleAffinity | None = None
_instance_lock = threading.Lock()


def get_role_affinity() -> RoleAffinity:
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = RoleAffinity()
    return _instance


def reset_role_affinity_for_tests() -> None:
    global _instance
    with _instance_lock:
        _instance = None
