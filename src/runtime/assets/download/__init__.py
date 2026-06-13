"""
Asset Download Package (Tier 12 — Asset Ecosystem Expansion)
=============================================================
Manages asset acquisition (simulated — no real HTTP in this implementation).

Public API:
    AssetDownloadManager            — class
    get_asset_download_manager()    — singleton
    reset_asset_download_manager_for_tests()
"""

from .asset_download_manager import (
    DownloadTask,
    AssetDownloadManager,
    get_asset_download_manager,
    reset_asset_download_manager_for_tests,
)

__all__ = [
    "DownloadTask",
    "AssetDownloadManager",
    "get_asset_download_manager",
    "reset_asset_download_manager_for_tests",
]
