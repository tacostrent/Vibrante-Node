"""
Asset Query Generator (Tier 7 — Scene Planning Runtime)
========================================================
Generates structured AssetQuery objects from a SceneIntent and its zone list.

Queries specify WHAT to search for — not where to download from. Provider
integrations (Sketchfab, Polyhaven, Quixel) consume these queries in a later tier.

DESIGN RULES:
  - No bridge calls. No API calls. No LLM calls.
  - Deterministic: same intent + zones → same queries.
  - Queries carry: category, tags (style + mood + environment), quantity, priority.
  - Tags are composed from zone context + environment style + mood modifiers.

Public API:
    AssetQueryGenerator
        .generate_queries(intent, zones) -> List[AssetQuery]
    get_asset_query_generator() -> AssetQueryGenerator   (singleton)
    reset_asset_query_generator_for_tests()
"""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional

from src.runtime.planning.schema.scene_plan import AssetQuery

# ---------------------------------------------------------------------------
# Per-category quantity and size hints
# ---------------------------------------------------------------------------

_CATEGORY_QUANTITY: Dict[str, int] = {
    "debris":           5,
    "rubble":           4,
    "vehicle":          2,
    "prop":             3,
    "street_element":   3,
    "trash":            4,
    "building":         6,
    "structure":        4,
    "facade":           3,
    "signage":          3,
    "infrastructure":   2,
    "skyline":          1,
    "tower":            3,
    "background_building": 5,
    "billboard":        2,
    "machinery":        2,
    "pipe":             4,
    "cable":            3,
    "equipment":        3,
    "container":        3,
    "tank":             2,
    "platform":         2,
    "scaffold":         2,
    "facility_building":2,
    "silo":             2,
    "chimney":          2,
    "cooling_tower":    1,
    "rock":             4,
    "sand_dune":        3,
    "vegetation_desert":2,
    "mesa":             2,
    "cliff":            2,
    "ground_cover":     6,
    "log":              3,
    "bush":             4,
    "tree":             5,
    "tree_trunk":       4,
    "wave":             1,
    "water_surface":    1,
    "boulder":          3,
    "rock_formation":   3,
    "ice_formation":    3,
    "space_station_module": 2,
    "debris_field":     1,
    "asteroid_small":   3,
    "spacecraft":       1,
    "furniture_prop":   4,
    "floor_detail":     3,
    "furniture_main":   3,
    "room_feature":     2,
    "wall_element":     3,
}

_DEFAULT_QUANTITY = 2

_CATEGORY_SIZE: Dict[str, str] = {
    "debris":       "small",
    "rubble":       "small",
    "prop":         "small",
    "trash":        "small",
    "vehicle":      "medium",
    "building":     "large",
    "structure":    "large",
    "tower":        "massive",
    "skyline":      "massive",
    "machinery":    "medium",
    "tree":         "large",
    "rock":         "medium",
    "spacecraft":   "massive",
}

_DEFAULT_SIZE = "medium"

# ---------------------------------------------------------------------------
# Style → tag modifiers
# ---------------------------------------------------------------------------

_STYLE_TAGS: Dict[str, List[str]] = {
    "photorealistic": ["photorealistic", "detailed", "high-resolution"],
    "cinematic":      ["cinematic", "hero-quality", "detailed"],
    "stylized":       ["stylized", "artistic"],
    "noir":           ["dark", "weathered", "moody"],
    "sci_fi":         ["sci-fi", "futuristic", "metallic", "high-tech"],
    "fantasy":        ["fantasy", "magical", "mystical"],
    "documentary":    ["realistic", "contemporary", "unpolished"],
    "abstract":       ["abstract", "geometric"],
}

# ---------------------------------------------------------------------------
# Mood → tag modifiers
# ---------------------------------------------------------------------------

_MOOD_TAGS: Dict[str, List[str]] = {
    "dramatic":    ["dramatic", "impactful"],
    "tense":       ["tense", "threatening"],
    "peaceful":    ["peaceful", "pristine", "clean"],
    "chaotic":     ["chaotic", "scattered", "damaged"],
    "melancholic": ["weathered", "aged", "decaying"],
    "triumphant":  ["grand", "imposing"],
    "ominous":     ["ominous", "dark", "looming"],
    "neutral":     [],
}

# ---------------------------------------------------------------------------
# Destruction level → tag modifiers
# ---------------------------------------------------------------------------

_DESTRUCTION_TAGS: Dict[str, List[str]] = {
    "none":         ["pristine", "clean"],
    "light":        ["worn", "weathered"],
    "moderate":     ["damaged", "cracked"],
    "heavy":        ["ruined", "destroyed", "collapsed"],
    "catastrophic": ["obliterated", "rubble", "burned"],
}

# ---------------------------------------------------------------------------
# Environment → base tags
# ---------------------------------------------------------------------------

_ENV_TAGS: Dict[str, List[str]] = {
    "urban":       ["urban", "city", "street"],
    "industrial":  ["industrial", "factory"],
    "desert":      ["desert", "arid", "sandy"],
    "forest":      ["forest", "woodland", "natural"],
    "ocean":       ["ocean", "coastal", "marine"],
    "mountain":    ["mountain", "alpine", "rocky"],
    "arctic":      ["arctic", "frozen", "icy", "cold"],
    "space":       ["space", "sci-fi", "orbital"],
    "underground": ["cave", "underground", "rocky"],
    "interior":    ["interior", "indoor"],
    "abstract":    ["abstract"],
}

# ---------------------------------------------------------------------------
# Priority by zone
# ---------------------------------------------------------------------------

_ZONE_PRIORITY: Dict[str, str] = {
    "foreground": "required",
    "midground":  "required",
    "background": "recommended",
    "overhead":   "optional",
    "ground":     "recommended",
    "ceiling":    "optional",
    "interior_wall": "recommended",
}


class AssetQueryGenerator:
    """Generates AssetQuery objects from a SceneIntent and its zone list."""

    def generate_queries(self, intent: Any, zones: List[Any]) -> List[AssetQuery]:
        """Return structured asset search requests for all zones.

        Args:
            intent: A SceneIntent (or duck-typed object with .environment, .style,
                    .mood, .destruction_level).
            zones:  List of SceneZonePlan objects.

        Returns:
            List of :class:`AssetQuery` covering every zone's asset categories.
        """
        env   = (getattr(intent, "environment", None)       or "").lower()
        style = (getattr(intent, "style", None)             or "").lower()
        mood  = (getattr(intent, "mood", None)              or "").lower()
        dest  = (getattr(intent, "destruction_level", None) or "none").lower()

        # Build tag pools from context
        style_tags = _STYLE_TAGS.get(style, [])
        mood_tags  = _MOOD_TAGS.get(mood, [])
        dest_tags  = _DESTRUCTION_TAGS.get(dest, [])
        env_tags   = _ENV_TAGS.get(env, [])

        queries: List[AssetQuery] = []
        seen_keys: set = set()  # deduplicate by (category, zone)

        for zone in zones:
            zone_type = getattr(zone, "zone_type", "")
            cats      = list(getattr(zone, "asset_categories", []))
            priority  = _ZONE_PRIORITY.get(zone_type, "recommended")

            for cat in cats:
                key = (cat, zone_type)
                if key in seen_keys:
                    continue
                seen_keys.add(key)

                # Compose tags: env + style + mood + destruction (dedup)
                all_tags = list(dict.fromkeys(
                    env_tags + style_tags + mood_tags + dest_tags
                ))

                quantity  = _CATEGORY_QUANTITY.get(cat, _DEFAULT_QUANTITY)
                size_hint = _CATEGORY_SIZE.get(cat, _DEFAULT_SIZE)

                queries.append(AssetQuery(
                    category=cat,
                    tags=all_tags,
                    zone=zone_type,
                    quantity=quantity,
                    priority=priority,
                    style_hints=style_tags,
                    size_hint=size_hint,
                    metadata={"environment": env, "mood": mood, "destruction": dest},
                ))

        return queries


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[AssetQueryGenerator] = None
_INSTANCE_LOCK = threading.Lock()


def get_asset_query_generator() -> AssetQueryGenerator:
    """Return the module-level singleton AssetQueryGenerator."""
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = AssetQueryGenerator()
    return _INSTANCE


def reset_asset_query_generator_for_tests() -> None:
    """Replace the singleton. For test isolation only."""
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
