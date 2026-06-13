"""
story_affinity.py — §45 Semantic Asset Suitability Ranking
===========================================================
Scores how well a candidate asset matches the storytelling narrative of the
target environment. Narrative props carry higher suitability than generic ones.

Public API:
    get_story_affinity() -> StoryAffinity
    reset_story_affinity_for_tests()

    StoryAffinity.score(asset, environment) -> float  0.0–1.0
    StoryAffinity.get_story_assets(environment) -> list[str]
"""

import re
import threading
from typing import Dict, List

# Canonical narrative props per environment (strongest storytelling signal)
_ENV_STORY_ASSETS: Dict[str, List[str]] = {
    "western_room": [
        "wanted poster", "whiskey bottle", "oil lantern", "wooden barrel",
        "saloon chair", "poker chips", "revolver", "sheriff badge", "spur",
        "rope", "saddle", "hat rack", "spittoon", "kerosene lamp",
    ],
    "saloon": [
        "whiskey bottle", "beer mug", "wanted poster", "poker table",
        "bar counter", "mirror", "oil lamp", "piano", "playing cards",
        "saloon chair", "tin cup",
    ],
    "living_room": [
        "picture frame", "fireplace", "sofa", "coffee table", "bookshelf",
        "rug", "lamp", "vase", "television", "cushion",
    ],
    "office": [
        "filing cabinet", "computer", "desk lamp", "stapler",
        "document stack", "coffee mug", "pen holder", "whiteboard",
        "monitor", "keyboard",
    ],
    "hotel_lobby": [
        "reception desk", "chandelier", "armchair", "luggage",
        "flower arrangement", "clock", "painting", "welcome sign",
    ],
    "restaurant": [
        "menu", "tablecloth", "wine glass", "candle holder",
        "place setting", "serving tray", "napkin", "cutlery",
    ],
    "library": [
        "book stack", "reading lamp", "globe", "filing system",
        "card catalog", "magnifying glass", "quill", "inkwell",
        "bookshelf", "scroll",
    ],
    "warehouse": [
        "pallet", "forklift", "crate stack", "barrel row",
        "loading dock", "chain hoist", "inventory label", "hand truck",
    ],
    "industrial_hangar": [
        "engine block", "welding equipment", "chain hoist",
        "tool cabinet", "oil drum", "pressure gauge", "industrial fan",
        "pipe network", "wrench",
    ],
    "abandoned_factory": [
        "rusted machine", "broken conveyor", "debris pile",
        "shattered window", "collapsed shelf", "old barrel",
        "graffiti", "oil stain",
    ],
    "robotics_lab": [
        "robot arm", "circuit board", "sensor array", "computer terminal",
        "cable bundle", "measurement tool", "servo motor", "battery",
    ],
    "control_room": [
        "main console", "status display", "warning light",
        "communication device", "data terminal", "wall screen",
        "emergency button",
    ],
    "medical_lab": [
        "specimen jar", "microscope", "test tube", "surgical tray",
        "medical monitor", "iv stand", "syringe", "petri dish",
    ],
    "research_lab": [
        "test tube", "beaker", "lab notebook", "microscope",
        "fume hood", "safety equipment", "bunsen burner", "flask",
    ],
    "sci_fi_corridor": [
        "holo panel", "energy conduit", "sci-fi door", "status terminal",
        "alien device", "glowing orb", "force field emitter",
        "holographic sign",
    ],
    "city_street": [
        "fire hydrant", "mailbox", "street lamp", "newspaper stand",
        "trash can", "bench", "phone booth", "bus stop",
    ],
    "forest": [
        "fallen log", "mushroom", "flower", "mossy rock", "bird nest",
        "stream stone", "fern", "vine",
    ],
    "desert": [
        "cactus", "tumbleweed", "bleached bones", "sand dune",
        "abandoned vehicle", "weathered post", "skull", "dry bush",
    ],
    "castle_hall": [
        "throne", "banner", "candelabra", "tapestry",
        "suit of armor", "fireplace", "weapon rack", "coat of arms",
    ],
    "survival_camp": [
        "campfire", "bedroll", "survival kit", "food can",
        "rope coil", "makeshift shelter", "water container", "axe",
    ],
    "dungeon": [
        "torch bracket", "chains", "skull", "iron door",
        "manacle", "prison bars", "rat", "torch",
    ],
}

# Strongly rejected narrative props (wrong story entirely)
_ENV_STORY_REJECTED: Dict[str, List[str]] = {
    "western_room": [
        "server rack", "robot arm", "industrial scanner", "holo panel",
        "circuit board",
    ],
    "saloon": [
        "server rack", "robot arm", "holo panel", "circuit board",
        "medical equipment",
    ],
    "living_room": [
        "industrial equipment", "weapon rack", "prison bars", "chains",
    ],
    "office": [
        "weapon rack", "prison bars", "chains", "dungeon equipment",
    ],
    "robotics_lab": [
        "wanted poster", "whiskey bottle", "saloon chair", "medieval banner",
    ],
    "control_room": [
        "wanted poster", "whiskey bottle", "saloon chair", "medieval banner",
    ],
    "sci_fi_corridor": [
        "wanted poster", "whiskey bottle", "wooden barrel", "medieval banner",
        "tapestry",
    ],
    "medical_lab": [
        "wanted poster", "weapon rack", "prison bars", "dungeon equipment",
    ],
    "castle_hall": [
        "server rack", "robot arm", "circuit board", "holo panel",
        "industrial scanner",
    ],
    "dungeon": [
        "server rack", "robot arm", "circuit board", "holo panel",
    ],
}


def _extract_story_text(asset: dict) -> str:
    parts: List[str] = []
    for field in ("name", "category", "type", "asset_type", "description"):
        v = asset.get(field, "")
        if isinstance(v, str):
            parts.append(re.sub(r"[\-_]+", " ", v.lower()))
    for field in ("tags", "style_tags", "environment_tags"):
        v = asset.get(field, [])
        if isinstance(v, list):
            for t in v:
                parts.append(re.sub(r"[\-_]+", " ", str(t).lower()))
    return " ".join(parts)


def _story_hits(text: str, assets: List[str]) -> int:
    count = 0
    for asset_kw in assets:
        kw_norm = re.sub(r"[\-_]+", " ", asset_kw.lower())
        if kw_norm in text:
            count += 1
        else:
            words = [w for w in kw_norm.split() if len(w) > 2]
            if words and any(w in text for w in words):
                count += 1
    return count


class StoryAffinity:
    """Scores asset narrative fit for an environment."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def score(self, asset: dict, environment: str) -> float:
        """Return 0.0–1.0 storytelling fit score."""
        try:
            story_assets = _ENV_STORY_ASSETS.get(environment, [])
            rejected = _ENV_STORY_REJECTED.get(environment, [])
            text = _extract_story_text(asset)

            rej_hits = _story_hits(text, rejected)
            if rej_hits > 0:
                return max(0.0, 0.2 - rej_hits * 0.1)

            hits = _story_hits(text, story_assets)
            if hits == 0:
                return 0.4  # generic — not a story asset for this env
            return min(1.0, 0.5 + hits * 0.15)
        except Exception:
            return 0.5

    def get_story_assets(self, environment: str) -> List[str]:
        return list(_ENV_STORY_ASSETS.get(environment, []))

    def get_rejected_story_assets(self, environment: str) -> List[str]:
        return list(_ENV_STORY_REJECTED.get(environment, []))

    def known_environments(self) -> List[str]:
        return sorted(_ENV_STORY_ASSETS.keys())


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: StoryAffinity | None = None
_instance_lock = threading.Lock()


def get_story_affinity() -> StoryAffinity:
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = StoryAffinity()
    return _instance


def reset_story_affinity_for_tests() -> None:
    global _instance
    with _instance_lock:
        _instance = None
