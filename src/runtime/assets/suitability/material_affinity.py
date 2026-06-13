"""
material_affinity.py — §45 Semantic Asset Suitability Ranking
=============================================================
Scores how well an asset's material composition matches the target environment.

Public API:
    get_material_affinity() -> MaterialAffinity
    reset_material_affinity_for_tests()

    MaterialAffinity.score(asset, environment) -> float   0.0–1.0
"""

import re
import threading
from typing import Dict, List

_ENV_MATERIAL_PREFERRED: Dict[str, List[str]] = {
    "western_room": [
        "wood", "wooden", "iron", "leather", "fabric", "aged metal",
        "brass", "rope", "felt", "hide",
    ],
    "saloon": [
        "wood", "wooden", "iron", "leather", "brass", "fabric",
        "glass", "tin",
    ],
    "living_room": [
        "fabric", "cotton", "wood", "wooden", "ceramic", "glass",
        "plastic", "foam", "carpet", "linen",
    ],
    "office": [
        "metal", "plastic", "glass", "chrome", "laminate", "fabric",
        "rubber",
    ],
    "hotel_lobby": [
        "marble", "stone", "chrome", "glass", "gold", "brass",
        "velvet", "silk",
    ],
    "restaurant": [
        "wood", "ceramic", "glass", "fabric", "steel", "porcelain",
        "linen",
    ],
    "library": [
        "wood", "wooden", "leather", "paper", "fabric", "brass",
        "parchment",
    ],
    "warehouse": [
        "metal", "concrete", "steel", "plastic", "wood", "rubber",
        "wire",
    ],
    "industrial_hangar": [
        "steel", "iron", "concrete", "metal", "rubber", "wire",
        "cable",
    ],
    "abandoned_factory": [
        "rusted metal", "concrete", "broken glass", "steel", "rust",
        "corroded",
    ],
    "robotics_lab": [
        "metal", "plastic", "carbon fiber", "electronic", "glass",
        "chrome", "pcb",
    ],
    "control_room": [
        "metal", "plastic", "glass", "electronic", "chrome", "rubber",
        "wire",
    ],
    "medical_lab": [
        "steel", "glass", "plastic", "rubber", "chrome", "ceramic",
        "silicone",
    ],
    "research_lab": [
        "glass", "steel", "plastic", "rubber", "ceramic", "silicone",
    ],
    "sci_fi_corridor": [
        "carbon fiber", "glass", "metal", "chrome", "crystal",
        "energy", "alloy",
    ],
    "city_street": [
        "concrete", "metal", "asphalt", "glass", "plastic", "steel",
        "brick",
    ],
    "forest": [
        "wood", "bark", "stone", "organic", "natural", "clay",
        "moss",
    ],
    "desert": [
        "stone", "sand", "clay", "rock", "dry wood", "bone",
        "sandstone",
    ],
    "castle_hall": [
        "stone", "iron", "wood", "fabric", "tapestry", "gold",
        "candle", "marble",
    ],
    "survival_camp": [
        "fabric", "wood", "rope", "canvas", "metal", "rubber",
        "tarp", "wire",
    ],
    "dungeon": [
        "stone", "iron", "chain", "bone", "rust", "wood", "damp",
    ],
}

_ENV_MATERIAL_REJECTED: Dict[str, List[str]] = {
    "western_room": [
        "chrome", "plastic", "carbon fiber", "electronic", "crystal",
        "neon", "alloy",
    ],
    "saloon": [
        "chrome", "plastic", "carbon fiber", "electronic", "neon",
        "alloy",
    ],
    "living_room": [
        "industrial steel", "concrete", "chain", "rusted metal",
    ],
    "office": [
        "rusted metal", "stone", "bone", "organic", "bark",
    ],
    "hotel_lobby": [
        "rusted metal", "concrete", "chain", "bone", "rope",
    ],
    "restaurant": [
        "rusted metal", "concrete", "chain", "bone", "rope",
    ],
    "library": [
        "chrome", "plastic", "carbon fiber", "chain", "concrete",
    ],
    "warehouse": [
        "marble", "gold", "velvet", "crystal", "silk",
    ],
    "industrial_hangar": [
        "marble", "gold", "velvet", "silk", "crystal",
    ],
    "abandoned_factory": [
        "marble", "gold", "velvet", "fresh wood", "pristine",
    ],
    "robotics_lab": [
        "wood", "stone", "bone", "organic", "leather",
    ],
    "control_room": [
        "wood", "stone", "bone", "organic", "leather",
    ],
    "medical_lab": [
        "wood", "stone", "bone", "organic", "rusted",
    ],
    "research_lab": [
        "wood", "stone", "bone", "organic", "rusted",
    ],
    "sci_fi_corridor": [
        "wood", "stone", "leather", "organic", "rust",
    ],
    "city_street": [
        "marble", "gold", "crystal", "silk",
    ],
    "forest": [
        "chrome", "plastic", "carbon fiber", "neon", "electronic",
    ],
    "desert": [
        "chrome", "plastic", "carbon fiber", "neon", "electronic",
    ],
    "castle_hall": [
        "chrome", "plastic", "carbon fiber", "neon",
    ],
    "survival_camp": [
        "marble", "gold", "crystal", "chrome",
    ],
    "dungeon": [
        "chrome", "plastic", "carbon fiber", "marble", "gold",
    ],
}


def _extract_material_text(asset: dict) -> str:
    parts: List[str] = []
    for field in ("name", "category", "type", "description"):
        v = asset.get(field, "")
        if isinstance(v, str):
            parts.append(re.sub(r"[\-_]+", " ", v.lower()))
    for field in ("tags", "material_tags", "lookdev_tags"):
        v = asset.get(field, [])
        if isinstance(v, list):
            for t in v:
                parts.append(re.sub(r"[\-_]+", " ", str(t).lower()))
    return " ".join(parts)


def _hits(text: str, keywords: List[str]) -> int:
    count = 0
    for kw in keywords:
        kw_norm = re.sub(r"[\-_]+", " ", kw.lower())
        if kw_norm in text:
            count += 1
        else:
            words = [w for w in kw_norm.split() if len(w) > 2]
            if words and any(w in text for w in words):
                count += 1
    return count


class MaterialAffinity:
    """Scores asset material composition compatibility with an environment."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def score(self, asset: dict, environment: str) -> float:
        try:
            preferred = _ENV_MATERIAL_PREFERRED.get(environment, [])
            rejected = _ENV_MATERIAL_REJECTED.get(environment, [])
            text = _extract_material_text(asset)

            pref = _hits(text, preferred)
            rej = _hits(text, rejected)

            base = 0.5
            base += min(0.5, pref * 0.10)
            base -= min(0.5, rej * 0.15)
            return max(0.0, min(1.0, base))
        except Exception:
            return 0.5

    def get_preferred_materials(self, environment: str) -> List[str]:
        return list(_ENV_MATERIAL_PREFERRED.get(environment, []))

    def get_rejected_materials(self, environment: str) -> List[str]:
        return list(_ENV_MATERIAL_REJECTED.get(environment, []))


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: MaterialAffinity | None = None
_instance_lock = threading.Lock()


def get_material_affinity() -> MaterialAffinity:
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = MaterialAffinity()
    return _instance


def reset_material_affinity_for_tests() -> None:
    global _instance
    with _instance_lock:
        _instance = None
