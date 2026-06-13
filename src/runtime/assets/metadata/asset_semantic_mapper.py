"""
Asset Semantic Mapper (Tier 12 — Asset Ecosystem Expansion)
============================================================
Converts provider metadata into semantic concepts (environments, categories,
styles, relationships).

Public API:
    SemanticProfile              — semantic profile model
    AssetSemanticMapper          — mapper class
    get_asset_semantic_mapper()  — singleton
    reset_asset_semantic_mapper_for_tests()
"""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional

from src.runtime.assets.schema import ASSET_CATEGORIES, ASSET_STYLES, AssetDescriptor


class SemanticProfile:
    """Semantic profile for an asset."""

    def __init__(
        self,
        asset_id:     str,
        provider:     str,
        environments: List[str],
        categories:   List[str],
        styles:       List[str],
        relationships: List[Dict[str, Any]],
        usage_hints:  List[str],
        confidence:   float = 0.5,
    ) -> None:
        self.asset_id      = asset_id
        self.provider      = provider
        self.environments  = environments
        self.categories    = categories
        self.styles        = styles
        self.relationships = relationships
        self.usage_hints   = usage_hints
        self.confidence    = confidence

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id":      self.asset_id,
            "provider":      self.provider,
            "environments":  self.environments,
            "categories":    self.categories,
            "styles":        self.styles,
            "relationships": self.relationships,
            "usage_hints":   self.usage_hints,
            "confidence":    self.confidence,
        }


class AssetSemanticMapper:
    """
    Converts provider metadata into semantic concept profiles.

    All mapping is deterministic and keyword/rule-based.
    No LLM.  No ML.  No randomness.
    """

    def __init__(self) -> None:
        self._lock:         threading.Lock = threading.Lock()
        self._mapped_count: int = 0
        self._profile_count: int = 0

    def map_environments(self, asset: AssetDescriptor) -> List[str]:
        """
        Infer suitable environments from asset metadata.
        Delegates to AssetMetadataEnricher, plus adds existing environment_suitability.
        """
        try:
            from src.runtime.assets.metadata.asset_metadata_enricher import get_asset_metadata_enricher
            enricher = get_asset_metadata_enricher()
            inferred = enricher.infer_environments(asset)
        except Exception:
            inferred = []
        # Merge with existing
        combined = list(asset.environment_suitability)
        for env in inferred:
            if env not in combined:
                combined.append(env)
        return sorted(combined)

    def map_categories(self, asset: AssetDescriptor) -> List[str]:
        """
        Map asset to valid ASSET_CATEGORIES.
        Returns list of matching categories.
        """
        cats: List[str] = []
        # Primary category
        if asset.category in ASSET_CATEGORIES:
            cats.append(asset.category)
        # Infer from tags/name
        all_terms = set()
        all_terms.add(asset.name.lower())
        for t in asset.tags + asset.keywords:
            all_terms.add(t.lower())
        for cat in ASSET_CATEGORIES:
            if cat.lower() in all_terms and cat not in cats:
                cats.append(cat)
        return sorted(cats)

    def map_styles(self, asset: AssetDescriptor) -> List[str]:
        """
        Map asset style using ASSET_STYLES vocabulary.
        'unknown' is excluded — it carries no semantic meaning.
        """
        styles: List[str] = []
        if asset.style and asset.style in ASSET_STYLES and asset.style != "unknown":
            styles.append(asset.style)
        # Try inferred style
        try:
            from src.runtime.assets.metadata.asset_metadata_enricher import get_asset_metadata_enricher
            inferred = get_asset_metadata_enricher().infer_style(asset)
        except Exception:
            inferred = None
        if inferred and inferred not in styles:
            styles.append(inferred)
        return sorted(styles)

    def map_relationships(
        self,
        asset: AssetDescriptor,
        known_assets: List[AssetDescriptor],
    ) -> List[Dict[str, Any]]:
        """
        Find semantic relationships between this asset and known_assets.

        Relationship types:
          - "same_environment" — share environment_suitability entries
          - "same_style" — share style
          - "same_category" — share primary category
        """
        relationships: List[Dict[str, Any]] = []
        if not known_assets:
            return relationships

        asset_envs  = set(asset.environment_suitability)
        asset_style = asset.style
        asset_cat   = asset.category

        for other in known_assets:
            if other.asset_id == asset.asset_id and other.provider == asset.provider:
                continue
            shared_envs = asset_envs & set(other.environment_suitability)
            if shared_envs:
                relationships.append({
                    "rel_type":      "same_environment",
                    "target_id":     other.asset_id,
                    "target_provider": other.provider,
                    "shared":        sorted(shared_envs),
                })
            if asset_style and asset_style == other.style:
                relationships.append({
                    "rel_type":      "same_style",
                    "target_id":     other.asset_id,
                    "target_provider": other.provider,
                    "style":         asset_style,
                })
            if asset_cat == other.category:
                relationships.append({
                    "rel_type":      "same_category",
                    "target_id":     other.asset_id,
                    "target_provider": other.provider,
                    "category":      asset_cat,
                })

        return relationships

    def build_semantic_profile(
        self,
        asset: AssetDescriptor,
        known_assets: Optional[List[AssetDescriptor]] = None,
    ) -> SemanticProfile:
        """
        Build a full SemanticProfile for an asset.
        """
        environments = self.map_environments(asset)
        categories   = self.map_categories(asset)
        styles       = self.map_styles(asset)
        relationships = self.map_relationships(asset, known_assets or [])
        try:
            from src.runtime.assets.metadata.asset_metadata_enricher import get_asset_metadata_enricher
            usage_hints = get_asset_metadata_enricher().infer_usage(asset)
        except Exception:
            usage_hints = []

        # Confidence based on data richness
        confidence = 0.5
        if asset.tags:
            confidence += 0.1
        if asset.environment_suitability:
            confidence += 0.1
        if asset.style and asset.style != "unknown":
            confidence += 0.1
        confidence = min(1.0, confidence)

        with self._lock:
            self._profile_count += 1

        return SemanticProfile(
            asset_id=asset.asset_id,
            provider=asset.provider,
            environments=environments,
            categories=categories,
            styles=styles,
            relationships=relationships,
            usage_hints=usage_hints,
            confidence=confidence,
        )

    def batch_map(
        self,
        assets: List[AssetDescriptor],
    ) -> List[SemanticProfile]:
        """
        Build SemanticProfiles for a list of assets.

        Passes all assets as known_assets for relationship detection.
        """
        profiles = []
        for asset in assets:
            profiles.append(
                self.build_semantic_profile(asset, known_assets=assets)
            )
        with self._lock:
            self._mapped_count += len(assets)
        return profiles

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "mapped_count":  self._mapped_count,
                "profile_count": self._profile_count,
            }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_MAPPER: Optional[AssetSemanticMapper] = None
_MAPPER_LOCK = threading.Lock()


def get_asset_semantic_mapper() -> AssetSemanticMapper:
    """Return the module-level singleton AssetSemanticMapper."""
    global _MAPPER
    if _MAPPER is None:
        with _MAPPER_LOCK:
            if _MAPPER is None:
                _MAPPER = AssetSemanticMapper()
    return _MAPPER


def reset_asset_semantic_mapper_for_tests() -> None:
    """Replace the singleton.  For test isolation only."""
    global _MAPPER
    with _MAPPER_LOCK:
        _MAPPER = None
