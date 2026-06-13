"""
Asset Cinematic Mapper (Tier 12.7)
====================================
Maps assets to cinematic usage roles for cinematography-aware scene planning.

Usages:
  hero_focus, silhouette, foreground_interest, depth_layer, visual_balance
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

CINEMATIC_USAGES: frozenset = frozenset({
    "hero_focus",
    "silhouette",
    "foreground_interest",
    "depth_layer",
    "visual_balance",
})

_CINEMATIC_KEYWORDS: Dict[str, frozenset] = {
    "hero_focus": frozenset({
        "hero", "primary", "main", "focal", "feature", "centerpiece",
        "spotlight", "highlight", "focus", "central",
    }),
    "silhouette": frozenset({
        "silhouette", "outline", "shadow", "backlit", "profile", "dark",
        "rim", "contour", "edge",
    }),
    "foreground_interest": frozenset({
        "foreground", "close", "near", "intimate", "detail", "close-up",
        "proximity", "front",
    }),
    "depth_layer": frozenset({
        "depth", "layer", "background", "distant", "atmospheric", "haze",
        "parallax", "recede", "atmosphere", "far",
    }),
    "visual_balance": frozenset({
        "balance", "symmetry", "composition", "arrangement", "layout",
        "weight", "counterweight", "equilibrium",
    }),
}

_CATEGORY_CINEMATIC_HINTS: Dict[str, str] = {
    "vehicle":       "hero_focus",
    "character":     "hero_focus",
    "creature":      "hero_focus",
    "weapon":        "hero_focus",
    "prop":          "foreground_interest",
    "machinery":     "visual_balance",
    "architecture":  "depth_layer",
    "vegetation":    "depth_layer",
    "terrain":       "depth_layer",
    "particle":      "depth_layer",
    "effect":        "silhouette",
    "surface":       "visual_balance",
}


@dataclass
class CinematicMapping:
    asset_id:        str = ""
    cinematic_usage: List[str] = field(default_factory=list)
    scores:          Dict[str, float] = field(default_factory=dict)
    primary:         str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id":        str(self.asset_id),
            "cinematic_usage": list(self.cinematic_usage),
            "scores":          dict(self.scores),
            "primary":         str(self.primary),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CinematicMapping":
        d = d if isinstance(d, dict) else {}
        return cls(
            asset_id=str(d.get("asset_id", "")),
            cinematic_usage=list(d.get("cinematic_usage") or []),
            scores=dict(d.get("scores") or {}),
            primary=str(d.get("primary", "")),
        )


class AssetCinematicMapper:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._map_count = 0

    def infer_cinematic_usage(self, asset_dict: Dict[str, Any]) -> CinematicMapping:
        """Infer cinematic usage from asset metadata. Never raises."""
        try:
            return self._do_infer(asset_dict if isinstance(asset_dict, dict) else {})
        except Exception:
            return CinematicMapping(
                asset_id=str((asset_dict or {}).get("asset_id", "")),
            )

    def _do_infer(self, asset: Dict[str, Any]) -> CinematicMapping:
        asset_id = str(asset.get("asset_id", "")).strip()
        name = str(asset.get("name", "")).lower()
        category = str(asset.get("category", "")).lower()
        tags = [str(t).lower() for t in (asset.get("tags") or [])]
        description = str(asset.get("description", "")).lower()

        all_text = f"{name} {description} {' '.join(tags)}"
        tokens = set(all_text.split())

        scores: Dict[str, float] = {}
        for usage, keywords in _CINEMATIC_KEYWORDS.items():
            hits = len(tokens & keywords)
            scores[usage] = hits / max(len(keywords) * 0.2, 1)

        if category in _CATEGORY_CINEMATIC_HINTS:
            hinted = _CATEGORY_CINEMATIC_HINTS[category]
            scores[hinted] = scores.get(hinted, 0.0) + 0.4

        qualified = {u: s for u, s in scores.items() if s > 0.1}
        ranked = sorted(qualified.keys(), key=lambda u: scores[u], reverse=True)
        primary = ranked[0] if ranked else ""

        with self._lock:
            self._map_count += 1

        return CinematicMapping(
            asset_id=asset_id,
            cinematic_usage=ranked,
            scores={u: round(scores[u], 4) for u in ranked},
            primary=primary,
        )

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            return {"map_count": self._map_count}


_INSTANCE: Optional[AssetCinematicMapper] = None
_INSTANCE_LOCK = threading.Lock()


def get_asset_cinematic_mapper() -> AssetCinematicMapper:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = AssetCinematicMapper()
    return _INSTANCE


def reset_asset_cinematic_mapper_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
