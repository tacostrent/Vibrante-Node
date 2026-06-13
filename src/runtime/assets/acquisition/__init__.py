"""
Asset Acquisition Service (Tier 12.5)
=======================================
Full re-export of the public surface for the acquisition package.

Responsibilities:
  - Discover Fab and Megascans assets acquired through official workflows
  - Track downloads and asset provenance in a persistent registry
  - Index local libraries for fast search
  - Detect newly appeared assets by directory comparison
  - Make locally acquired assets available to the Vibrante Runtime

Environment variables:
  VIBRANTE_FAB_LIBRARY          — path to local Fab library
  VIBRANTE_MEGASCANS_LIBRARY    — path to local Megascans library
  VIBRANTE_ASSET_STORAGE        — root for registry + index persistence

Design rules:
  - No network calls
  - No Epic/Fab authentication
  - No hardcoded credentials
  - Only reads officially acquired, locally stored assets
"""
from __future__ import annotations

from .fab_library_scanner import (
    ENV_FAB_LIBRARY,
    FabAssetRecord,
    FabScanResult,
    FabLibraryScanner,
    get_fab_library_scanner,
    reset_fab_library_scanner_for_tests,
)
from .megascans_scanner import (
    ENV_MEGASCANS_LIBRARY,
    MegascansAssetRecord,
    MegascansScanResult,
    MegascansScanner,
    get_megascans_scanner,
    reset_megascans_scanner_for_tests,
)
from .download_registry import (
    RegistryEntry,
    DownloadRegistry,
    get_download_registry,
    reset_download_registry_for_tests,
)
from .library_index import (
    IndexEntry,
    IndexSearchResult,
    LibraryIndex,
    get_library_index,
    reset_library_index_for_tests,
)
from .library_watcher import (
    WatchEntry,
    NewAssetEvent,
    LibraryWatcher,
    get_library_watcher,
    reset_library_watcher_for_tests,
)
from .acquisition_manager import (
    AcquisitionRequest,
    AcquisitionResult,
    AcquisitionManager,
    get_acquisition_manager,
    reset_acquisition_manager_for_tests,
)

__all__ = [
    # Constants
    "ENV_FAB_LIBRARY",
    "ENV_MEGASCANS_LIBRARY",
    # Fab Library Scanner
    "FabAssetRecord",
    "FabScanResult",
    "FabLibraryScanner",
    "get_fab_library_scanner",
    "reset_fab_library_scanner_for_tests",
    # Megascans Scanner
    "MegascansAssetRecord",
    "MegascansScanResult",
    "MegascansScanner",
    "get_megascans_scanner",
    "reset_megascans_scanner_for_tests",
    # Download Registry
    "RegistryEntry",
    "DownloadRegistry",
    "get_download_registry",
    "reset_download_registry_for_tests",
    # Library Index
    "IndexEntry",
    "IndexSearchResult",
    "LibraryIndex",
    "get_library_index",
    "reset_library_index_for_tests",
    # Library Watcher
    "WatchEntry",
    "NewAssetEvent",
    "LibraryWatcher",
    "get_library_watcher",
    "reset_library_watcher_for_tests",
    # Acquisition Manager
    "AcquisitionRequest",
    "AcquisitionResult",
    "AcquisitionManager",
    "get_acquisition_manager",
    "reset_acquisition_manager_for_tests",
]
