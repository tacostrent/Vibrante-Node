"""
Asset Providers (Tier 8 — Asset Intelligence Runtime)
======================================================
Provider abstraction layer.  All concrete providers implement
AssetProvider (the ABC in base.py).

Runtime code must NEVER import a concrete provider class directly —
always use the AssetProvider interface or the provider registry.
"""

from .base import AssetProvider, ProviderRegistry, get_provider_registry, reset_provider_registry_for_tests
from .sketchfab_provider import SketchfabProvider
from .polyhaven_provider import PolyhavenProvider
from .local_library_provider import LocalLibraryProvider
# Tier 12
from .provider_manager import ProviderManager, get_provider_manager, reset_provider_manager_for_tests
from .sketchfab_live_provider import SketchfabLiveProvider
from .quixel_provider import QuixelProvider
from .usd_library_provider import UsdLibraryProvider
from .studio_library_provider import StudioLibraryProvider

__all__ = [
    "AssetProvider",
    "ProviderRegistry",
    "get_provider_registry",
    "reset_provider_registry_for_tests",
    "SketchfabProvider",
    "PolyhavenProvider",
    "LocalLibraryProvider",
    # Tier 12
    "ProviderManager",
    "get_provider_manager",
    "reset_provider_manager_for_tests",
    "SketchfabLiveProvider",
    "QuixelProvider",
    "UsdLibraryProvider",
    "StudioLibraryProvider",
]
