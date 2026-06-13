"""
Asset Provider ABC (Tier 8 — Asset Intelligence Runtime)
=========================================================
Protocol contract that every provider must satisfy.

DESIGN RULES:
  1. Providers are interchangeable — runtime code never imports a concrete class.
  2. search() returns AssetProviderResult; normalisation is the provider's job.
  3. No downloads in search() or normalize() — metadata only.
  4. No authentication workflows — deferred to Tier 9.
  5. Thread-safe: providers may be called from multiple coroutines.

Public API:
    AssetProvider           — abstract base class
    ProviderRegistry        — registry of live provider instances
    get_provider_registry() — singleton
    reset_provider_registry_for_tests()
"""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from src.runtime.assets.schema import AssetDescriptor, AssetProviderResult


class AssetProvider(ABC):
    """Abstract base class for all asset providers."""

    # ------------------------------------------------------------------
    # Identity (override in concrete classes)
    # ------------------------------------------------------------------

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Unique string key: "sketchfab", "polyhaven", "local", ..."""

    @property
    @abstractmethod
    def supported_categories(self) -> List[str]:
        """List of ASSET_CATEGORIES this provider covers."""

    @property
    def is_available(self) -> bool:
        """Return True when the provider can serve requests.

        Default implementation always returns True.
        Override for providers that need authentication or network access.
        """
        return True

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    @abstractmethod
    def search(
        self,
        category: str,
        tags: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None,
        style_hints: Optional[List[str]] = None,
        limit: int = 20,
        **kwargs: Any,
    ) -> AssetProviderResult:
        """
        Search for assets matching the given criteria.

        Args:
            category:    Normalized category string (from ASSET_CATEGORIES).
            tags:        Optional tag filter list.
            keywords:    Optional keyword filter list.
            style_hints: Optional style preference hints.
            limit:       Maximum number of results to return.
            **kwargs:    Provider-specific extra parameters.

        Returns:
            AssetProviderResult with normalized_assets populated.
            Never raises — errors captured in result.errors.
        """

    @abstractmethod
    def normalize(self, raw: Dict[str, Any]) -> AssetDescriptor:
        """
        Convert a single raw provider record to an AssetDescriptor.

        Args:
            raw: Provider-specific dict from the search API.

        Returns:
            AssetDescriptor with all standard fields populated.
        """

    def validate_asset(self, asset: AssetDescriptor) -> Dict[str, Any]:
        """
        Provider-level validation (e.g. format availability, licence check).

        Default implementation performs basic field checks.
        Override for provider-specific constraints.

        Returns:
            {"valid": bool, "errors": [...], "warnings": [...]}
        """
        errors: List[str] = []
        warnings: List[str] = []
        if not asset.name:
            errors.append("Asset name is empty.")
        if not asset.category:
            warnings.append("Asset category is not set.")
        if not asset.formats:
            warnings.append("No formats declared.")
        if asset.rating < 0.0 or asset.rating > 5.0:
            errors.append(f"Rating {asset.rating} out of range [0, 5].")
        return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _matches_category(self, asset_category: str, query_category: str) -> bool:
        """Return True when categories overlap (exact or parent match)."""
        if not query_category:
            return True
        return asset_category.lower() == query_category.lower()

    def _tag_overlap(self, asset_tags: List[str], query_tags: List[str]) -> int:
        """Count how many query tags appear in the asset tag list."""
        if not query_tags:
            return 0
        asset_set = {t.lower() for t in asset_tags}
        return sum(1 for t in query_tags if t.lower() in asset_set)


# ---------------------------------------------------------------------------
# Provider Registry
# ---------------------------------------------------------------------------

class ProviderRegistry:
    """
    Registry of live AssetProvider instances.

    Thread-safe.  Providers are registered once and remain available
    for the lifetime of the process.
    """

    def __init__(self) -> None:
        self._lock:      threading.Lock = threading.Lock()
        self._providers: Dict[str, AssetProvider] = {}

    def register(self, provider: AssetProvider) -> None:
        """Register a provider.  Replaces any existing entry for the same name."""
        with self._lock:
            self._providers[provider.provider_name] = provider

    def deregister(self, name: str) -> bool:
        """Remove a provider by name.  Returns True if found."""
        with self._lock:
            if name in self._providers:
                del self._providers[name]
                return True
            return False

    def get(self, name: str) -> Optional[AssetProvider]:
        """Return a provider by name, or None."""
        with self._lock:
            return self._providers.get(name)

    def all_providers(self) -> List[AssetProvider]:
        """Return all registered providers."""
        with self._lock:
            return list(self._providers.values())

    def available_providers(self) -> List[AssetProvider]:
        """Return only providers whose is_available is True."""
        return [p for p in self.all_providers() if p.is_available]

    def providers_for_category(self, category: str) -> List[AssetProvider]:
        """Return providers that declare support for *category*."""
        return [
            p for p in self.available_providers()
            if category in p.supported_categories
        ]

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            names = list(self._providers.keys())
        return {
            "registered_count": len(names),
            "provider_names":   sorted(names),
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_REGISTRY: Optional[ProviderRegistry] = None
_REGISTRY_LOCK = threading.Lock()


def get_provider_registry() -> ProviderRegistry:
    """Return the module-level singleton ProviderRegistry."""
    global _REGISTRY
    if _REGISTRY is None:
        with _REGISTRY_LOCK:
            if _REGISTRY is None:
                _REGISTRY = ProviderRegistry()
    return _REGISTRY


def reset_provider_registry_for_tests() -> None:
    """Replace the singleton.  For test isolation only."""
    global _REGISTRY
    with _REGISTRY_LOCK:
        _REGISTRY = None
