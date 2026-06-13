"""
Asset Role Classifier (Tier 12.7)
===================================
Classifies assets into production roles using deterministic keyword and
category-affinity rules.

Roles:
  hero, support, foreground, midground, background, set_dressing
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

BUILTIN_ROLES: frozenset = frozenset({
    "hero",
    "support",
    "foreground",
    "midground",
    "background",
    "set_dressing",
})

_ROLE_KEYWORDS: Dict[str, frozenset] = {
    "hero": frozenset({
        "hero", "primary", "main", "focal", "key", "feature", "star",
        "central", "showcase", "highlight", "centerpiece", "landmark",
    }),
    "support": frozenset({
        "support", "secondary", "adjacent", "companion", "surrounding",
        "complementary", "assistant", "helper",
    }),
    "foreground": frozenset({
        "foreground", "close", "near", "front", "intimate", "close-up",
    }),
    "midground": frozenset({
        "midground", "middle", "mid", "center", "median",
    }),
    "background": frozenset({
        "background", "distant", "far", "back", "skyline", "horizon",
        "backdrop", "panorama",
    }),
    "set_dressing": frozenset({
        "dressing", "prop", "detail", "ambient", "filler", "scatter",
        "clutter", "debris", "trim", "accent", "decoration", "fill",
    }),
}

_CATEGORY_ROLE_HINTS: Dict[str, str] = {
    "vehicle":       "hero",
    "character":     "hero",
    "creature":      "hero",
    "weapon":        "hero",
    "machinery":     "support",
    "furniture":     "support",
    "equipment":     "support",
    "electronics":   "support",
    "architecture":  "background",
    "vegetation":    "background",
    "terrain":       "background",
    "sky":           "background",
    "prop":          "set_dressing",
    "material":      "set_dressing",
    "surface":       "set_dressing",
    "tool":          "set_dressing",
}

_ROLE_CONFIDENCE: Dict[str, float] = {
    "hero":         0.85,
    "support":      0.75,
    "foreground":   0.70,
    "midground":    0.65,
    "background":   0.70,
    "set_dressing": 0.80,
}


@dataclass
class RoleClassification:
    asset_id:   str = ""
    primary_role: str = "set_dressing"
    confidence: float = 0.5
    all_roles:  List[Dict[str, float]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id":     str(self.asset_id),
            "primary_role": str(self.primary_role),
            "confidence":   float(self.confidence),
            "all_roles":    list(self.all_roles),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RoleClassification":
        d = d if isinstance(d, dict) else {}
        return cls(
            asset_id=str(d.get("asset_id", "")),
            primary_role=str(d.get("primary_role", "set_dressing")),
            confidence=float(d.get("confidence", 0.5)),
            all_roles=list(d.get("all_roles") or []),
        )


class AssetRoleClassifier:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._classify_count = 0

    def classify_role(self, asset_dict: Dict[str, Any]) -> RoleClassification:
        """Classify production role from asset metadata. Never raises."""
        try:
            return self._do_classify(asset_dict if isinstance(asset_dict, dict) else {})
        except Exception:
            return RoleClassification(
                asset_id=str((asset_dict or {}).get("asset_id", "")),
            )

    def _do_classify(self, asset: Dict[str, Any]) -> RoleClassification:
        asset_id = str(asset.get("asset_id", "")).strip()
        name = str(asset.get("name", "")).lower()
        category = str(asset.get("category", "")).lower()
        tags = [str(t).lower() for t in (asset.get("tags") or [])]
        description = str(asset.get("description", "")).lower()

        all_text = f"{name} {description} {' '.join(tags)}"
        tokens = set(all_text.split())

        role_scores: Dict[str, float] = {}
        for role, keywords in _ROLE_KEYWORDS.items():
            hits = len(tokens & keywords)
            role_scores[role] = hits / max(len(keywords) * 0.2, 1)

        # Category hint — strong signal
        if category in _CATEGORY_ROLE_HINTS:
            hinted = _CATEGORY_ROLE_HINTS[category]
            role_scores[hinted] = role_scores.get(hinted, 0.0) + 0.5

        # Sort by score
        ranked = sorted(role_scores.items(), key=lambda x: x[1], reverse=True)
        primary_role = ranked[0][0] if ranked else "set_dressing"
        raw_confidence = ranked[0][1] if ranked else 0.0

        # Map to calibrated confidence
        base_confidence = _ROLE_CONFIDENCE.get(primary_role, 0.5)
        confidence = round(min(base_confidence + raw_confidence * 0.1, 1.0), 4)

        all_roles = [
            {"role": r, "score": round(s, 4)}
            for r, s in ranked
            if s > 0
        ]

        with self._lock:
            self._classify_count += 1

        return RoleClassification(
            asset_id=asset_id,
            primary_role=primary_role,
            confidence=confidence,
            all_roles=all_roles,
        )

    def rank_role_confidence(self, asset_dict: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Return all roles ranked by confidence score."""
        try:
            cls = self.classify_role(asset_dict)
            return cls.all_roles
        except Exception:
            return []

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            return {"classify_count": self._classify_count}


_INSTANCE: Optional[AssetRoleClassifier] = None
_INSTANCE_LOCK = threading.Lock()


def get_asset_role_classifier() -> AssetRoleClassifier:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = AssetRoleClassifier()
    return _INSTANCE


def reset_asset_role_classifier_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
