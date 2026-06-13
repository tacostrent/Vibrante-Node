"""
Asset Lookdev Mapper (Tier 12.7)
==================================
Infers lookdev tags for material-intelligence-aware asset handling.

Tags: clean, weathered, aged, industrial, sci_fi, rusted, polished, worn, damaged, pristine
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

LOOKDEV_TAGS: frozenset = frozenset({
    "clean",
    "weathered",
    "aged",
    "industrial",
    "sci_fi",
    "rusted",
    "polished",
    "worn",
    "damaged",
    "pristine",
})

_LOOKDEV_KEYWORDS: Dict[str, frozenset] = {
    "weathered": frozenset({
        "weathered", "worn", "scratched", "scuffed", "faded", "eroded",
        "battered", "patina", "stained", "discolored",
    }),
    "aged": frozenset({
        "aged", "old", "antique", "vintage", "ancient", "deteriorated",
        "timeworn", "historical", "obsolete", "classic",
    }),
    "industrial": frozenset({
        "industrial", "metal", "steel", "iron", "machinery", "factory", "pipe",
        "welded", "riveted", "bolted", "grated", "galvanized", "oxidized",
    }),
    "sci_fi": frozenset({
        "sci_fi", "scifi", "futuristic", "tech", "digital", "electronic",
        "neon", "holographic", "cyberpunk", "advanced", "alien", "space",
    }),
    "rusted": frozenset({
        "rust", "rusted", "corroded", "oxidized", "degraded", "corroding",
        "flaking", "pitted",
    }),
    "clean": frozenset({
        "clean", "new", "pristine", "fresh", "modern", "unused", "mint",
    }),
    "polished": frozenset({
        "polished", "shiny", "glossy", "reflective", "chrome", "mirror",
        "lacquered", "varnished",
    }),
    "worn": frozenset({
        "worn", "used", "tired", "beat", "dinged", "scratched", "marked",
    }),
    "damaged": frozenset({
        "damaged", "broken", "cracked", "dented", "smashed", "fractured",
        "deformed", "destroyed", "wrecked",
    }),
    "pristine": frozenset({
        "pristine", "perfect", "immaculate", "flawless", "unblemished",
    }),
}

_CATEGORY_LOOKDEV_HINTS: Dict[str, List[str]] = {
    "machinery":     ["industrial", "weathered"],
    "vehicle":       ["weathered", "worn"],
    "architecture":  ["aged", "weathered"],
    "electronics":   ["sci_fi", "clean"],
    "robot":         ["sci_fi", "industrial"],
    "weapon":        ["industrial", "worn"],
    "prop":          ["weathered", "aged"],
    "surface":       ["industrial"],
    "material":      ["industrial"],
    "furniture":     ["aged", "worn"],
}


@dataclass
class LookdevMapping:
    asset_id:     str = ""
    lookdev_tags: List[str] = field(default_factory=list)
    scores:       Dict[str, float] = field(default_factory=dict)
    primary:      str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id":     str(self.asset_id),
            "lookdev_tags": list(self.lookdev_tags),
            "scores":       dict(self.scores),
            "primary":      str(self.primary),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "LookdevMapping":
        d = d if isinstance(d, dict) else {}
        return cls(
            asset_id=str(d.get("asset_id", "")),
            lookdev_tags=list(d.get("lookdev_tags") or []),
            scores=dict(d.get("scores") or {}),
            primary=str(d.get("primary", "")),
        )


class AssetLookdevMapper:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._map_count = 0

    def infer_lookdev_tags(self, asset_dict: Dict[str, Any]) -> LookdevMapping:
        """Infer lookdev tags from asset metadata. Never raises."""
        try:
            return self._do_infer(asset_dict if isinstance(asset_dict, dict) else {})
        except Exception:
            return LookdevMapping(
                asset_id=str((asset_dict or {}).get("asset_id", "")),
            )

    def _do_infer(self, asset: Dict[str, Any]) -> LookdevMapping:
        asset_id = str(asset.get("asset_id", "")).strip()
        name = str(asset.get("name", "")).lower()
        category = str(asset.get("category", "")).lower()
        tags = [str(t).lower() for t in (asset.get("tags") or [])]
        description = str(asset.get("description", "")).lower()
        existing_tags = set(tags)

        all_text = f"{name} {description} {' '.join(tags)}"
        tokens = set(all_text.split())

        scores: Dict[str, float] = {}
        for tag, keywords in _LOOKDEV_KEYWORDS.items():
            hits = len(tokens & keywords)
            scores[tag] = hits / max(len(keywords) * 0.2, 1)
            # Boost if already explicitly tagged
            if tag in existing_tags:
                scores[tag] += 0.5

        # Category hints
        if category in _CATEGORY_LOOKDEV_HINTS:
            for hinted in _CATEGORY_LOOKDEV_HINTS[category]:
                scores[hinted] = scores.get(hinted, 0.0) + 0.25

        qualified = {t: s for t, s in scores.items() if s > 0.1}
        ranked = sorted(qualified.keys(), key=lambda t: scores[t], reverse=True)
        primary = ranked[0] if ranked else ""

        with self._lock:
            self._map_count += 1

        return LookdevMapping(
            asset_id=asset_id,
            lookdev_tags=ranked,
            scores={t: round(scores[t], 4) for t in ranked},
            primary=primary,
        )

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            return {"map_count": self._map_count}


_INSTANCE: Optional[AssetLookdevMapper] = None
_INSTANCE_LOCK = threading.Lock()


def get_asset_lookdev_mapper() -> AssetLookdevMapper:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = AssetLookdevMapper()
    return _INSTANCE


def reset_asset_lookdev_mapper_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
