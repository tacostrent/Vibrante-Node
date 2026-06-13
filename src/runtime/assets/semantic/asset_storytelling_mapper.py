"""
Asset Storytelling Mapper (Tier 12.7)
======================================
Maps assets to storytelling roles for narrative-aware scene construction.

Roles:
  hero_object, context_builder, scale_reference, visual_anchor, atmosphere_builder
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

STORYTELLING_ROLES: frozenset = frozenset({
    "hero_object",
    "context_builder",
    "scale_reference",
    "visual_anchor",
    "atmosphere_builder",
})

_STORY_KEYWORDS: Dict[str, frozenset] = {
    "hero_object": frozenset({
        "hero", "primary", "main", "focal", "key", "feature", "star", "centerpiece",
        "landmark", "unique", "iconic", "signature", "showpiece",
    }),
    "context_builder": frozenset({
        "context", "environment", "setting", "background", "world", "scene",
        "location", "place", "surround", "ambient", "atmosphere",
    }),
    "scale_reference": frozenset({
        "scale", "reference", "human", "person", "door", "stairs", "car",
        "height", "size", "proportion", "measure",
    }),
    "visual_anchor": frozenset({
        "anchor", "focal", "guide", "lead", "center", "compass", "orientation",
        "landmark", "waypoint", "marker",
    }),
    "atmosphere_builder": frozenset({
        "atmosphere", "mood", "fog", "haze", "particle", "smoke", "dust",
        "volumetric", "ambient", "light", "glow", "effect",
    }),
}

_CATEGORY_STORY_HINTS: Dict[str, str] = {
    "vehicle":       "hero_object",
    "character":     "hero_object",
    "creature":      "hero_object",
    "weapon":        "hero_object",
    "architecture":  "context_builder",
    "terrain":       "context_builder",
    "door":          "scale_reference",
    "furniture":     "scale_reference",
    "machinery":     "visual_anchor",
    "vegetation":    "atmosphere_builder",
    "particle":      "atmosphere_builder",
    "effect":        "atmosphere_builder",
}


@dataclass
class StorytellingMapping:
    asset_id:   str = ""
    story_role: str = "context_builder"
    confidence: float = 0.5
    all_roles:  List[Dict[str, float]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id":   str(self.asset_id),
            "story_role": str(self.story_role),
            "confidence": float(self.confidence),
            "all_roles":  list(self.all_roles),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "StorytellingMapping":
        d = d if isinstance(d, dict) else {}
        return cls(
            asset_id=str(d.get("asset_id", "")),
            story_role=str(d.get("story_role", "context_builder")),
            confidence=float(d.get("confidence", 0.5)),
            all_roles=list(d.get("all_roles") or []),
        )


class AssetStorytellingMapper:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._map_count = 0

    def map_story_role(self, asset_dict: Dict[str, Any]) -> StorytellingMapping:
        """Infer storytelling role from asset metadata. Never raises."""
        try:
            return self._do_map(asset_dict if isinstance(asset_dict, dict) else {})
        except Exception:
            return StorytellingMapping(
                asset_id=str((asset_dict or {}).get("asset_id", "")),
            )

    def _do_map(self, asset: Dict[str, Any]) -> StorytellingMapping:
        asset_id = str(asset.get("asset_id", "")).strip()
        name = str(asset.get("name", "")).lower()
        category = str(asset.get("category", "")).lower()
        tags = [str(t).lower() for t in (asset.get("tags") or [])]
        description = str(asset.get("description", "")).lower()

        all_text = f"{name} {description} {' '.join(tags)}"
        tokens = set(all_text.split())

        role_scores: Dict[str, float] = {}
        for role, keywords in _STORY_KEYWORDS.items():
            hits = len(tokens & keywords)
            role_scores[role] = hits / max(len(keywords) * 0.2, 1)

        if category in _CATEGORY_STORY_HINTS:
            hinted = _CATEGORY_STORY_HINTS[category]
            role_scores[hinted] = role_scores.get(hinted, 0.0) + 0.5

        ranked = sorted(role_scores.items(), key=lambda x: x[1], reverse=True)
        story_role = ranked[0][0] if ranked else "context_builder"
        raw_score = ranked[0][1] if ranked else 0.0
        confidence = round(min(0.5 + raw_score * 0.15, 1.0), 4)

        all_roles = [
            {"role": r, "score": round(s, 4)}
            for r, s in ranked
            if s > 0
        ]

        with self._lock:
            self._map_count += 1

        return StorytellingMapping(
            asset_id=asset_id,
            story_role=story_role,
            confidence=confidence,
            all_roles=all_roles,
        )

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            return {"map_count": self._map_count}


_INSTANCE: Optional[AssetStorytellingMapper] = None
_INSTANCE_LOCK = threading.Lock()


def get_asset_storytelling_mapper() -> AssetStorytellingMapper:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = AssetStorytellingMapper()
    return _INSTANCE


def reset_asset_storytelling_mapper_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
