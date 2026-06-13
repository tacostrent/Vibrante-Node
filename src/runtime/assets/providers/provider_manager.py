"""
Provider Manager (Tier 12 — Asset Ecosystem Expansion)
========================================================
Unified provider interface that sits above ProviderRegistry,
adding higher-level orchestration: querying multiple providers,
merging results, and deduplicating assets.

Public API:
    ProviderManager              — class
    get_provider_manager()       — singleton
    reset_provider_manager_for_tests()
"""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, List, Optional

from src.runtime.assets.schema import AssetDescriptor, AssetProviderResult
from src.runtime.assets.providers.base import get_provider_registry


class ProviderManager:
    """
    Unified manager over registered asset providers.

    Wraps ProviderRegistry to provide higher-level operations:
    - Multi-provider parallel queries (sequential for determinism)
    - Result merging and deduplication
    - Statistics tracking
    """

    def __init__(self) -> None:
        self._lock:         threading.Lock = threading.Lock()
        self._query_count:  int = 0
        self._merge_count:  int = 0

    # ------------------------------------------------------------------
    # Provider delegation
    # ------------------------------------------------------------------

    def register_provider(self, provider: Any) -> None:
        """Register a provider via ProviderRegistry."""
        get_provider_registry().register(provider)

    def unregister_provider(self, name: str) -> bool:
        """Unregister a provider by name. Returns True if found."""
        return get_provider_registry().deregister(name)

    def list_providers(self) -> List[Dict[str, Any]]:
        """Return summary dicts for all registered providers."""
        providers = get_provider_registry().all_providers()
        result = []
        for p in sorted(providers, key=lambda x: x.provider_name):
            result.append({
                "name":                p.provider_name,
                "available":           p.is_available,
                "supported_categories": list(p.supported_categories),
            })
        return result

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def query_providers(
        self,
        category: str,
        tags: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None,
        style_hints: Optional[List[str]] = None,
        limit: int = 20,
    ) -> List[AssetDescriptor]:
        """
        Query all available providers and return merged, deduplicated results.

        Args:
            category:    Asset category to search for.
            tags:        Optional tag filter list.
            keywords:    Optional keyword filter list.
            style_hints: Optional style preference hints.
            limit:       Maximum results per provider.

        Returns:
            List of AssetDescriptor, deduplicated by (provider, asset_id),
            sorted deterministically by (provider, name).
        """
        with self._lock:
            self._query_count += 1

        providers = get_provider_registry().available_providers()
        all_results: List[AssetProviderResult] = []
        for provider in providers:
            try:
                result = provider.search(
                    category=category,
                    tags=tags or [],
                    keywords=keywords or [],
                    style_hints=style_hints or [],
                    limit=limit,
                )
                all_results.append(result)
            except Exception:
                pass  # Graceful degradation — skip unavailable provider

        return self.merge_results(all_results)

    def query_provider(
        self,
        provider_name: str,
        category: str,
        tags: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None,
        limit: int = 20,
    ) -> AssetProviderResult:
        """
        Query a single named provider.

        Returns empty AssetProviderResult if the provider is not found.
        """
        provider = get_provider_registry().get(provider_name)
        if provider is None or not provider.is_available:
            return AssetProviderResult(
                provider=provider_name,
                success=False,
                errors=[f"Provider '{provider_name}' not found or unavailable."],
            )
        try:
            return provider.search(
                category=category,
                tags=tags or [],
                keywords=keywords or [],
                limit=limit,
            )
        except Exception as exc:
            return AssetProviderResult(
                provider=provider_name,
                success=False,
                errors=[str(exc)],
            )

    # ------------------------------------------------------------------
    # Merge / dedup
    # ------------------------------------------------------------------

    def merge_results(
        self,
        provider_results: List[AssetProviderResult],
    ) -> List[AssetDescriptor]:
        """
        Merge multiple AssetProviderResult objects into one deduplicated list.

        Deduplication key: (provider, asset_id).
        Output sorted by (provider, name) for determinism.
        """
        with self._lock:
            self._merge_count += 1

        seen: set = set()
        merged: List[AssetDescriptor] = []
        for pres in provider_results:
            for asset in pres.normalized_assets:
                key = (asset.provider, asset.asset_id)
                if key not in seen:
                    seen.add(key)
                    merged.append(asset)

        return sorted(merged, key=lambda a: (a.provider, a.name.lower()))

    def deduplicate_results(
        self,
        assets: List[AssetDescriptor],
    ) -> List[AssetDescriptor]:
        """
        Remove duplicate assets from a list.

        Deduplication key: (provider, asset_id).
        Preserves first occurrence order.
        """
        seen: set = set()
        result: List[AssetDescriptor] = []
        for asset in assets:
            key = (asset.provider, asset.asset_id)
            if key not in seen:
                seen.add(key)
                result.append(asset)
        return result

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_statistics(self) -> Dict[str, Any]:
        """Return usage statistics."""
        reg = get_provider_registry()
        providers = reg.all_providers()
        with self._lock:
            return {
                "total_providers":     len(providers),
                "available_providers": sum(1 for p in providers if p.is_available),
                "query_count":         self._query_count,
                "merge_count":         self._merge_count,
            }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_MANAGER: Optional[ProviderManager] = None
_MANAGER_LOCK = threading.Lock()


def get_provider_manager() -> ProviderManager:
    """Return the module-level singleton ProviderManager."""
    global _MANAGER
    if _MANAGER is None:
        with _MANAGER_LOCK:
            if _MANAGER is None:
                _MANAGER = ProviderManager()
    return _MANAGER


def reset_provider_manager_for_tests() -> None:
    """Replace the singleton.  For test isolation only."""
    global _MANAGER
    with _MANAGER_LOCK:
        _MANAGER = None
