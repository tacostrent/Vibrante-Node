"""
style_affinity.py — §45 Semantic Asset Suitability Ranking
===========================================================
Scores how well an asset's visual style matches the target environment.

Public API:
    get_style_affinity() -> StyleAffinity
    reset_style_affinity_for_tests()

    StyleAffinity.score(asset, environment) -> float   0.0–1.0
"""

import re
import threading
from typing import Dict, List

_ENV_STYLE_PREFERRED: Dict[str, List[str]] = {
    "western_room": [
        "weathered", "aged", "worn", "dusty", "rustic", "antique",
        "distressed", "vintage", "handmade", "rough", "patina",
    ],
    "saloon": [
        "weathered", "aged", "worn", "rustic", "distressed",
        "vintage", "rough", "handmade",
    ],
    "living_room": [
        "clean", "cozy", "warm", "comfortable", "domestic", "neutral",
        "homely", "soft",
    ],
    "office": [
        "clean", "modern", "minimal", "professional", "organized",
        "sleek", "polished",
    ],
    "hotel_lobby": [
        "polished", "elegant", "luxury", "ornate", "refined",
        "pristine", "grand",
    ],
    "restaurant": [
        "polished", "clean", "elegant", "warm", "inviting", "refined",
    ],
    "library": [
        "aged", "classic", "traditional", "ornate", "scholarly",
        "dusty", "antique",
    ],
    "warehouse": [
        "industrial", "utilitarian", "rough", "heavy", "practical",
        "plain",
    ],
    "industrial_hangar": [
        "industrial", "rusted", "worn", "heavy", "utilitarian",
        "mechanical", "weathered",
    ],
    "abandoned_factory": [
        "rusted", "decayed", "broken", "crumbling", "deteriorated",
        "dilapidated", "neglected",
    ],
    "robotics_lab": [
        "clean", "modern", "technical", "precise", "futuristic",
        "minimalist", "sleek",
    ],
    "control_room": [
        "clean", "technical", "modern", "organized", "precise",
        "functional",
    ],
    "medical_lab": [
        "sterile", "clean", "clinical", "pristine", "hygienic",
        "white",
    ],
    "research_lab": [
        "clean", "scientific", "precise", "organized", "clinical",
        "analytical",
    ],
    "sci_fi_corridor": [
        "futuristic", "sleek", "alien", "high-tech", "advanced",
        "neon", "glowing",
    ],
    "city_street": [
        "weathered", "urban", "worn", "gritty", "modern", "functional",
    ],
    "forest": [
        "organic", "natural", "rough", "aged", "weathered", "earthy",
        "mossy", "textured",
    ],
    "desert": [
        "weathered", "sun-baked", "dry", "bleached", "rough", "arid",
        "sandy",
    ],
    "castle_hall": [
        "aged", "medieval", "ornate", "gothic", "stone", "ancient",
        "majestic",
    ],
    "survival_camp": [
        "makeshift", "rough", "worn", "improvised", "crude",
        "utilitarian", "scavenged",
    ],
    "dungeon": [
        "dark", "rough", "ancient", "damp", "grim", "medieval",
        "crumbling",
    ],
}

_ENV_STYLE_REJECTED: Dict[str, List[str]] = {
    "western_room": [
        "polished", "futuristic", "modern", "sterile", "pristine",
        "chrome", "neon", "minimalist",
    ],
    "saloon": [
        "polished", "futuristic", "modern", "sterile", "chrome",
        "neon",
    ],
    "living_room": [
        "industrial", "heavy", "rusted", "military", "sterile",
        "futuristic",
    ],
    "office": [
        "rustic", "weathered", "medieval", "dungeon", "ancient",
        "crumbling",
    ],
    "hotel_lobby": [
        "industrial", "rustic", "rusted", "damaged", "broken",
        "worn", "rough",
    ],
    "restaurant": [
        "industrial", "rustic", "rusted", "damaged", "broken",
    ],
    "library": [
        "futuristic", "neon", "industrial", "chrome", "modern",
    ],
    "warehouse": [
        "elegant", "ornate", "luxury", "pristine", "polished",
    ],
    "industrial_hangar": [
        "elegant", "ornate", "luxury", "pristine", "futuristic",
    ],
    "abandoned_factory": [
        "clean", "pristine", "polished", "modern", "elegant",
    ],
    "robotics_lab": [
        "rustic", "aged", "weathered", "medieval", "rough",
    ],
    "control_room": [
        "rustic", "aged", "weathered", "medieval", "rough",
    ],
    "medical_lab": [
        "rustic", "weathered", "dirty", "rusted", "ancient",
    ],
    "research_lab": [
        "rustic", "weathered", "dirty", "rusted", "medieval",
    ],
    "sci_fi_corridor": [
        "rustic", "medieval", "aged", "wooden", "weathered", "rough",
    ],
    "city_street": [
        "medieval", "futuristic", "pristine", "fantasy",
    ],
    "forest": [
        "industrial", "modern", "futuristic", "chrome", "sterile",
        "neon",
    ],
    "desert": [
        "industrial", "chrome", "futuristic", "sterile", "forest",
    ],
    "castle_hall": [
        "industrial", "futuristic", "chrome", "modern", "sterile",
        "neon",
    ],
    "survival_camp": [
        "elegant", "polished", "luxury", "modern", "sterile",
    ],
    "dungeon": [
        "clean", "modern", "futuristic", "polished", "luxury",
    ],
}


def _extract_style_text(asset: dict) -> str:
    parts: List[str] = []
    for field in ("name", "category", "type", "description"):
        v = asset.get(field, "")
        if isinstance(v, str):
            parts.append(re.sub(r"[\-_]+", " ", v.lower()))
    for field in ("tags", "style_tags", "lookdev_tags"):
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


class StyleAffinity:
    """Scores asset visual style compatibility with an environment."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def score(self, asset: dict, environment: str) -> float:
        try:
            preferred = _ENV_STYLE_PREFERRED.get(environment, [])
            rejected = _ENV_STYLE_REJECTED.get(environment, [])
            text = _extract_style_text(asset)

            pref = _hits(text, preferred)
            rej = _hits(text, rejected)

            base = 0.5
            base += min(0.5, pref * 0.10)
            base -= min(0.5, rej * 0.15)
            return max(0.0, min(1.0, base))
        except Exception:
            return 0.5

    def get_preferred_styles(self, environment: str) -> List[str]:
        return list(_ENV_STYLE_PREFERRED.get(environment, []))

    def get_rejected_styles(self, environment: str) -> List[str]:
        return list(_ENV_STYLE_REJECTED.get(environment, []))


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: StyleAffinity | None = None
_instance_lock = threading.Lock()


def get_style_affinity() -> StyleAffinity:
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = StyleAffinity()
    return _instance


def reset_style_affinity_for_tests() -> None:
    global _instance
    with _instance_lock:
        _instance = None
