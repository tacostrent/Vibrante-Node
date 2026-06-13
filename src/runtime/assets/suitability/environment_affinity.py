"""
environment_affinity.py — §45 Semantic Asset Suitability Ranking
================================================================
Scores how well a candidate asset matches a target environment.
Keyword tables encode preferred and rejected signals per environment.

Public API:
    get_environment_affinity() -> EnvironmentAffinity
    reset_environment_affinity_for_tests()

    EnvironmentAffinity.score(asset, environment) -> float   0.0–1.0
    EnvironmentAffinity.get_preferred(environment) -> list[str]
    EnvironmentAffinity.get_rejected(environment) -> list[str]
"""

import re
import threading
from typing import Dict, List

# ---------------------------------------------------------------------------
# Keyword tables
# ---------------------------------------------------------------------------

_ENV_PREFERRED: Dict[str, List[str]] = {
    "western_room": [
        "western", "saloon", "rustic", "aged", "wood", "wooden", "historical",
        "cowboy", "frontier", "antique", "old_west", "weathered", "pioneer",
        "whiskey", "saddle", "lantern", "barrel", "wanted",
    ],
    "saloon": [
        "saloon", "western", "bar", "rustic", "aged", "wood", "wooden",
        "frontier", "cowboy", "barroom", "tavern", "vintage", "whiskey",
        "piano", "mirror",
    ],
    "living_room": [
        "domestic", "home", "cozy", "comfortable", "residential", "furniture",
        "living", "sofa", "carpet", "curtain", "cushion", "warm",
    ],
    "office": [
        "office", "corporate", "desk", "professional", "business",
        "workstation", "ergonomic", "modern", "computer", "filing",
    ],
    "hotel_lobby": [
        "hotel", "lobby", "elegant", "marble", "luxurious", "chandelier",
        "reception", "concierge", "grand", "plush", "velvet",
    ],
    "restaurant": [
        "restaurant", "dining", "bistro", "culinary", "food", "kitchen",
        "cafe", "table", "serving", "cuisine",
    ],
    "library": [
        "library", "books", "shelf", "academic", "wooden", "study",
        "scholarly", "reading", "archival", "tome", "parchment",
    ],
    "warehouse": [
        "warehouse", "storage", "industrial", "boxes", "crate", "pallet",
        "forklift", "loading", "cargo", "bulk", "shelving",
    ],
    "industrial_hangar": [
        "industrial", "hangar", "machinery", "metal", "factory", "steel",
        "pipes", "mechanical", "heavy", "engineering", "workshop", "tool",
    ],
    "abandoned_factory": [
        "abandoned", "ruined", "derelict", "factory", "rusted", "decay",
        "industrial", "broken", "crumbling", "neglected", "dilapidated",
    ],
    "robotics_lab": [
        "robot", "robotic", "lab", "technology", "electronic", "sensor",
        "circuit", "mechanical", "automation", "ai", "cable", "servo",
    ],
    "control_room": [
        "control", "console", "screen", "monitor", "panel", "operations",
        "technical", "switches", "displays", "readout", "button",
    ],
    "medical_lab": [
        "medical", "clinical", "sterile", "hospital", "pharmaceutical",
        "health", "lab", "surgical", "diagnostic", "specimen",
    ],
    "research_lab": [
        "research", "scientific", "lab", "experiment", "glass", "chemistry",
        "analytical", "apparatus", "beaker", "flask", "specimen",
    ],
    "sci_fi_corridor": [
        "sci-fi", "scifi", "futuristic", "space", "corridor", "technology",
        "alien", "high-tech", "holo", "neon", "portal", "energy",
    ],
    "city_street": [
        "urban", "city", "street", "outdoor", "concrete", "asphalt",
        "municipal", "road", "sidewalk", "traffic", "signage",
    ],
    "forest": [
        "nature", "forest", "tree", "plant", "organic", "natural", "wood",
        "foliage", "bark", "leaf", "moss", "branch",
    ],
    "desert": [
        "desert", "arid", "sand", "dry", "rocky", "sandstone", "dune",
        "cactus", "sparse", "bleached", "wasteland",
    ],
    "castle_hall": [
        "castle", "medieval", "stone", "gothic", "throne", "knight",
        "royal", "hall", "banner", "tapestry", "fortress",
    ],
    "survival_camp": [
        "survival", "camp", "makeshift", "rough", "improvised", "outdoor",
        "primitive", "campfire", "scavenged", "tarp", "canvas",
    ],
    "dungeon": [
        "dungeon", "dark", "stone", "chains", "medieval", "prison",
        "underground", "damp", "torch", "iron", "cell",
    ],
}

_ENV_REJECTED: Dict[str, List[str]] = {
    "western_room": [
        "robotic", "industrial", "laboratory", "futuristic", "chrome",
        "plastic", "electronic", "neon", "sci-fi", "modern_office",
    ],
    "saloon": [
        "robotic", "industrial", "laboratory", "futuristic", "chrome",
        "plastic", "electronic", "neon", "sci-fi",
    ],
    "living_room": [
        "industrial", "military", "laboratory", "sci-fi", "futuristic",
        "heavy_machinery", "rusted", "abandoned",
    ],
    "office": [
        "industrial", "rustic", "western", "medieval", "fantasy",
        "forest", "rusted", "abandoned",
    ],
    "hotel_lobby": [
        "industrial", "rusted", "broken", "abandoned", "factory",
        "dungeon", "military",
    ],
    "restaurant": [
        "industrial", "laboratory", "military", "sci-fi", "rusted",
        "broken", "dungeon", "abandoned",
    ],
    "library": [
        "industrial", "sci-fi", "military", "rusted", "heavy_machinery",
        "dungeon", "survival",
    ],
    "warehouse": [
        "western", "castle", "library", "medical", "elegant", "medieval",
    ],
    "industrial_hangar": [
        "western", "castle", "library", "nature", "forest", "elegant",
        "domestic", "medieval",
    ],
    "abandoned_factory": [
        "clean", "pristine", "western", "castle", "library", "nature",
        "medical",
    ],
    "robotics_lab": [
        "western", "medieval", "rustic", "aged", "castle", "nature",
        "forest", "dungeon",
    ],
    "control_room": [
        "western", "medieval", "rustic", "nature", "forest", "castle",
        "dungeon",
    ],
    "medical_lab": [
        "rusted", "weathered", "western", "medieval", "dirty", "dungeon",
        "survival",
    ],
    "research_lab": [
        "rusted", "weathered", "western", "medieval", "dirty", "dungeon",
    ],
    "sci_fi_corridor": [
        "wooden", "rustic", "medieval", "western", "aged", "antique",
        "forest", "nature",
    ],
    "city_street": [
        "medieval", "fantasy", "forest", "sci-fi", "laboratory", "dungeon",
    ],
    "forest": [
        "industrial", "electronic", "chrome", "modern_office",
        "laboratory", "futuristic",
    ],
    "desert": [
        "industrial", "electronic", "chrome", "forest", "tropical",
        "water", "laboratory",
    ],
    "castle_hall": [
        "industrial", "electronic", "futuristic", "modern", "plastic",
        "chrome", "laboratory",
    ],
    "survival_camp": [
        "elegant", "polished", "luxury", "chrome", "laboratory",
        "modern_office",
    ],
    "dungeon": [
        "modern", "futuristic", "electronic", "chrome", "luxury",
        "clean", "sterile",
    ],
}

# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------

def _extract_text(asset: dict) -> str:
    parts: List[str] = []
    for field in ("name", "category", "type", "asset_type", "placement_type", "description"):
        v = asset.get(field, "")
        if isinstance(v, str):
            parts.append(re.sub(r"[\-_]+", " ", v.lower()))
    for field in ("tags", "style_tags", "material_tags", "lookdev_tags", "environment_tags"):
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
            # fallback: any single word from keyword appears in text
            words = [w for w in kw_norm.split() if len(w) > 2]
            if words and any(w in text for w in words):
                count += 1
    return count


# ---------------------------------------------------------------------------
# EnvironmentAffinity
# ---------------------------------------------------------------------------

class EnvironmentAffinity:
    """Scores asset–environment keyword compatibility."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def score(self, asset: dict, environment: str) -> float:
        """Return 0.0–1.0 environment fit score."""
        try:
            preferred = _ENV_PREFERRED.get(environment, [])
            rejected = _ENV_REJECTED.get(environment, [])

            env_tags = asset.get("environment_tags", [])
            if isinstance(env_tags, list) and environment in env_tags:
                return 1.0

            text = _extract_text(asset)
            pref = _hits(text, preferred)
            rej = _hits(text, rejected)

            base = 0.5
            base += min(0.5, pref * 0.10)
            base -= min(0.5, rej * 0.15)
            return max(0.0, min(1.0, base))
        except Exception:
            return 0.5

    def get_preferred(self, environment: str) -> List[str]:
        return list(_ENV_PREFERRED.get(environment, []))

    def get_rejected(self, environment: str) -> List[str]:
        return list(_ENV_REJECTED.get(environment, []))

    def known_environments(self) -> List[str]:
        return sorted(_ENV_PREFERRED.keys())


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: EnvironmentAffinity | None = None
_instance_lock = threading.Lock()


def get_environment_affinity() -> EnvironmentAffinity:
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = EnvironmentAffinity()
    return _instance


def reset_environment_affinity_for_tests() -> None:
    global _instance
    with _instance_lock:
        _instance = None
