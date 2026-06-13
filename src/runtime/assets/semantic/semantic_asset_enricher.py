"""
Semantic Asset Enricher (Tier 12.7)
======================================
Converts raw asset metadata into full production semantics by running all
semantic mappers in sequence and combining the results.

Input:  raw asset dict (from any provider or manifest)
Output: EnrichedAsset with environments, roles, lookdev, storytelling, cinematic, importance

Design rules:
  - No network calls, no DCC calls
  - Deterministic — same input always produces the same output
  - Never raises in public methods
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .asset_environment_mapper import get_asset_environment_mapper
from .asset_role_classifier import get_asset_role_classifier
from .asset_storytelling_mapper import get_asset_storytelling_mapper
from .asset_lookdev_mapper import get_asset_lookdev_mapper
from .asset_cinematic_mapper import get_asset_cinematic_mapper

_IMPORTANCE_LEVELS = ("primary", "secondary", "tertiary", "ambient")

# Importance thresholds based on role
_ROLE_IMPORTANCE: Dict[str, str] = {
    "hero":         "primary",
    "foreground":   "primary",
    "support":      "secondary",
    "midground":    "secondary",
    "background":   "tertiary",
    "set_dressing": "ambient",
}


@dataclass
class EnrichedAsset:
    asset_id:        str = ""
    name:            str = ""
    provider:        str = ""
    category:        str = ""
    tags:            List[str] = field(default_factory=list)
    environments:    List[str] = field(default_factory=list)
    primary_env:     str = ""
    roles:           List[str] = field(default_factory=list)
    primary_role:    str = ""
    lookdev_tags:    List[str] = field(default_factory=list)
    primary_lookdev: str = ""
    story_role:      str = ""
    cinematic_usage: List[str] = field(default_factory=list)
    primary_cinematic: str = ""
    importance:      str = "ambient"
    semantic_tags:   List[str] = field(default_factory=list)
    enriched_at:     float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id":         str(self.asset_id),
            "name":             str(self.name),
            "provider":         str(self.provider),
            "category":         str(self.category),
            "tags":             list(self.tags),
            "environments":     list(self.environments),
            "primary_env":      str(self.primary_env),
            "roles":            list(self.roles),
            "primary_role":     str(self.primary_role),
            "lookdev_tags":     list(self.lookdev_tags),
            "primary_lookdev":  str(self.primary_lookdev),
            "story_role":       str(self.story_role),
            "cinematic_usage":  list(self.cinematic_usage),
            "primary_cinematic": str(self.primary_cinematic),
            "importance":       str(self.importance),
            "semantic_tags":    list(self.semantic_tags),
            "enriched_at":      float(self.enriched_at),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "EnrichedAsset":
        d = d if isinstance(d, dict) else {}
        return cls(
            asset_id=str(d.get("asset_id", "")),
            name=str(d.get("name", "")),
            provider=str(d.get("provider", "")),
            category=str(d.get("category", "")),
            tags=list(d.get("tags") or []),
            environments=list(d.get("environments") or []),
            primary_env=str(d.get("primary_env", "")),
            roles=list(d.get("roles") or []),
            primary_role=str(d.get("primary_role", "")),
            lookdev_tags=list(d.get("lookdev_tags") or []),
            primary_lookdev=str(d.get("primary_lookdev", "")),
            story_role=str(d.get("story_role", "")),
            cinematic_usage=list(d.get("cinematic_usage") or []),
            primary_cinematic=str(d.get("primary_cinematic", "")),
            importance=str(d.get("importance", "ambient")),
            semantic_tags=list(d.get("semantic_tags") or []),
            enriched_at=float(d.get("enriched_at") or time.time()),
        )


class SemanticAssetEnricher:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._enrich_count = 0

    def enrich_asset(self, asset_dict: Dict[str, Any]) -> EnrichedAsset:
        """Run all semantic mappers and produce an EnrichedAsset. Never raises."""
        try:
            return self._do_enrich(asset_dict if isinstance(asset_dict, dict) else {})
        except Exception:
            return EnrichedAsset(
                asset_id=str((asset_dict or {}).get("asset_id", "")),
            )

    def _do_enrich(self, asset: Dict[str, Any]) -> EnrichedAsset:
        asset_id = str(asset.get("asset_id", "")).strip()
        name = str(asset.get("name", "")).strip()
        provider = str(asset.get("provider", "")).strip()
        category = str(asset.get("category", "")).lower().strip()
        tags = [str(t).lower().strip() for t in (asset.get("tags") or [])]

        env_mapping = get_asset_environment_mapper().map_environments(asset)
        role_cls = get_asset_role_classifier().classify_role(asset)
        story_mapping = get_asset_storytelling_mapper().map_story_role(asset)
        lookdev_mapping = get_asset_lookdev_mapper().infer_lookdev_tags(asset)
        cinematic_mapping = get_asset_cinematic_mapper().infer_cinematic_usage(asset)

        roles = [r["role"] for r in role_cls.all_roles if r.get("score", 0) > 0]
        if not roles and role_cls.primary_role:
            roles = [role_cls.primary_role]

        importance = _ROLE_IMPORTANCE.get(role_cls.primary_role, "ambient")

        # Assemble semantic_tags from all inferences
        semantic_tags = list(dict.fromkeys([
            *env_mapping.environments,
            *roles,
            *lookdev_mapping.lookdev_tags,
            *cinematic_mapping.cinematic_usage,
            story_mapping.story_role,
        ]))

        with self._lock:
            self._enrich_count += 1

        return EnrichedAsset(
            asset_id=asset_id,
            name=name,
            provider=provider,
            category=category,
            tags=tags,
            environments=env_mapping.environments,
            primary_env=env_mapping.primary,
            roles=roles,
            primary_role=role_cls.primary_role,
            lookdev_tags=lookdev_mapping.lookdev_tags,
            primary_lookdev=lookdev_mapping.primary,
            story_role=story_mapping.story_role,
            cinematic_usage=cinematic_mapping.cinematic_usage,
            primary_cinematic=cinematic_mapping.primary,
            importance=importance,
            semantic_tags=semantic_tags,
        )

    # ------------------------------------------------------------------
    # Convenience: individual inference methods
    # ------------------------------------------------------------------

    def infer_environments(self, asset_dict: Dict[str, Any]) -> List[str]:
        """Infer environments for an asset. Never raises."""
        try:
            return get_asset_environment_mapper().map_environments(asset_dict).environments
        except Exception:
            return []

    def infer_story_roles(self, asset_dict: Dict[str, Any]) -> List[str]:
        """Infer storytelling roles. Never raises."""
        try:
            mapping = get_asset_storytelling_mapper().map_story_role(asset_dict)
            return [r["role"] for r in mapping.all_roles if r.get("score", 0) > 0]
        except Exception:
            return []

    def infer_lookdev(self, asset_dict: Dict[str, Any]) -> List[str]:
        """Infer lookdev tags. Never raises."""
        try:
            return get_asset_lookdev_mapper().infer_lookdev_tags(asset_dict).lookdev_tags
        except Exception:
            return []

    def infer_cinematic_usage(self, asset_dict: Dict[str, Any]) -> List[str]:
        """Infer cinematic usages. Never raises."""
        try:
            return get_asset_cinematic_mapper().infer_cinematic_usage(asset_dict).cinematic_usage
        except Exception:
            return []

    def infer_asset_importance(self, asset_dict: Dict[str, Any]) -> str:
        """Infer production importance level. Never raises."""
        try:
            role = get_asset_role_classifier().classify_role(asset_dict).primary_role
            return _ROLE_IMPORTANCE.get(role, "ambient")
        except Exception:
            return "ambient"

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            return {"enrich_count": self._enrich_count}


_INSTANCE: Optional[SemanticAssetEnricher] = None
_INSTANCE_LOCK = threading.Lock()


def get_semantic_asset_enricher() -> SemanticAssetEnricher:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = SemanticAssetEnricher()
    return _INSTANCE


def reset_semantic_asset_enricher_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
