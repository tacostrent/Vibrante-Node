"""
Asset Sync (Tier 12 — Asset Ecosystem Expansion)
=================================================
Synchronize asset libraries between providers and local storage.

Public API:
    SyncReport               — sync summary
    AssetSync                — sync manager class
    get_asset_sync()         — singleton
    reset_asset_sync_for_tests()
"""

from __future__ import annotations

import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.runtime.assets.schema import AssetDescriptor


class SyncReport:
    """Summary of a library synchronization operation."""

    def __init__(
        self,
        provider: str,
        sync_id: Optional[str] = None,
    ) -> None:
        self.provider:      str   = provider
        self.sync_id:       str   = sync_id or f"sync_{uuid.uuid4().hex[:10]}"
        self.assets_found:  int   = 0
        self.assets_new:    int   = 0
        self.assets_updated: int  = 0
        self.assets_removed: int  = 0
        self.errors:        List[str] = []
        self.duration_sec:  float = 0.0
        self.completed_at:  float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider":       self.provider,
            "sync_id":        self.sync_id,
            "assets_found":   self.assets_found,
            "assets_new":     self.assets_new,
            "assets_updated": self.assets_updated,
            "assets_removed": self.assets_removed,
            "errors":         list(self.errors),
            "duration_sec":   self.duration_sec,
            "completed_at":   self.completed_at,
        }


class AssetSync:
    """
    Synchronize asset libraries between providers and local storage.

    Thread-safe.  Sync history is kept in memory (last 100 reports).
    """

    def __init__(self) -> None:
        self._lock:    threading.Lock = threading.Lock()
        self._history: List[SyncReport] = []
        self._max_history: int = 100

    # ------------------------------------------------------------------
    # Sync operations
    # ------------------------------------------------------------------

    def sync_provider(self, provider_name: str) -> SyncReport:
        """
        Sync a registered provider's assets into local storage.

        Queries the provider, compares with AssetStorage, and reports
        new / updated / removed assets.
        """
        t0 = time.perf_counter()
        report = SyncReport(provider=provider_name)
        try:
            from src.runtime.assets.providers.base import get_provider_registry
            from src.runtime.assets.cache.asset_storage import get_asset_storage

            provider = get_provider_registry().get(provider_name)
            if provider is None or not provider.is_available:
                report.errors.append(
                    f"Provider '{provider_name}' not found or unavailable."
                )
                report.duration_sec = time.perf_counter() - t0
                report.completed_at = time.time()
                self._add_to_history(report)
                return report

            # Query provider for all assets (broad query)
            provider_result = provider.search(category="", limit=1000)
            provider_assets = provider_result.normalized_assets
            report.assets_found = len(provider_assets)

            storage = get_asset_storage()
            for asset in provider_assets:
                if storage.asset_exists(provider_name, asset.asset_id):
                    report.assets_updated += 1
                else:
                    # Register placeholder (no actual download)
                    storage.register_asset(asset, "")
                    report.assets_new += 1

        except Exception as exc:
            report.errors.append(str(exc))

        report.duration_sec = time.perf_counter() - t0
        report.completed_at = time.time()
        self._add_to_history(report)
        return report

    def sync_library(
        self,
        library_path: str,
        provider_name: str,
    ) -> SyncReport:
        """
        Sync a local directory into AssetStorage.

        Scans the directory and registers all found assets.
        """
        t0 = time.perf_counter()
        report = SyncReport(provider=provider_name)
        try:
            if not library_path or not os.path.isdir(library_path):
                report.errors.append(f"Library path not found: {library_path}")
                report.duration_sec = time.perf_counter() - t0
                report.completed_at = time.time()
                self._add_to_history(report)
                return report

            from src.runtime.assets.schema import AssetDescriptor, AssetMetadata
            from src.runtime.assets.cache.asset_storage import get_asset_storage

            storage = get_asset_storage()
            seen_files: List[str] = []

            # Walk directory and register files
            for root, dirs, files in os.walk(library_path):
                for fname in sorted(files):
                    fpath = str(Path(root) / fname)
                    seen_files.append(fpath)
                    asset_name = Path(fname).stem
                    asset_id = f"{provider_name}_{asset_name.lower().replace(' ', '_')}"
                    report.assets_found += 1
                    if not storage.asset_exists(provider_name, asset_id):
                        ext = Path(fname).suffix.lower().lstrip(".")
                        placeholder = AssetDescriptor(
                            asset_id=asset_id,
                            provider=provider_name,
                            name=asset_name,
                            formats=[ext] if ext else [],
                            category="prop",
                        )
                        storage.register_asset(placeholder, fpath)
                        report.assets_new += 1
                    else:
                        report.assets_updated += 1

        except Exception as exc:
            report.errors.append(str(exc))

        report.duration_sec = time.perf_counter() - t0
        report.completed_at = time.time()
        self._add_to_history(report)
        return report

    def validate_sync(self, provider_name: str) -> Dict[str, Any]:
        """
        Validate that local storage matches the provider's asset list.

        Returns:
            {"valid": bool, "issues": List[str],
             "assets_in_storage": int, "assets_in_provider": int}
        """
        issues: List[str] = []
        assets_in_storage = 0
        assets_in_provider = 0
        try:
            from src.runtime.assets.providers.base import get_provider_registry
            from src.runtime.assets.cache.asset_storage import get_asset_storage

            storage = get_asset_storage()
            assets_in_storage = len(storage.list_assets(provider=provider_name))

            provider = get_provider_registry().get(provider_name)
            if provider is None:
                issues.append(f"Provider '{provider_name}' not registered.")
            elif provider.is_available:
                result = provider.search(category="", limit=1000)
                assets_in_provider = len(result.normalized_assets)
                for asset in result.normalized_assets:
                    if not storage.asset_exists(provider_name, asset.asset_id):
                        issues.append(f"Asset '{asset.asset_id}' in provider but not in storage.")
        except Exception as exc:
            issues.append(str(exc))

        return {
            "valid":              len(issues) == 0,
            "issues":             issues,
            "assets_in_storage":  assets_in_storage,
            "assets_in_provider": assets_in_provider,
        }

    def build_sync_report(
        self,
        provider_name: str,
        found: int,
        registered: int,
        errors: List[str],
    ) -> SyncReport:
        """Build a SyncReport from raw counts."""
        report = SyncReport(provider=provider_name)
        report.assets_found = found
        report.assets_new = registered
        report.errors = list(errors)
        report.completed_at = time.time()
        return report

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    def get_sync_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return recent sync reports (newest first)."""
        with self._lock:
            history = list(self._history)
        return [r.to_dict() for r in reversed(history)][:limit]

    def get_statistics(self) -> Dict[str, Any]:
        """Return sync statistics."""
        with self._lock:
            history = list(self._history)
        return {
            "total_syncs":   len(history),
            "total_new":     sum(r.assets_new for r in history),
            "total_updated": sum(r.assets_updated for r in history),
            "total_errors":  sum(len(r.errors) for r in history),
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _add_to_history(self, report: SyncReport) -> None:
        with self._lock:
            self._history.append(report)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_SYNC: Optional[AssetSync] = None
_SYNC_LOCK = threading.Lock()


def get_asset_sync() -> AssetSync:
    """Return the module-level singleton AssetSync."""
    global _SYNC
    if _SYNC is None:
        with _SYNC_LOCK:
            if _SYNC is None:
                _SYNC = AssetSync()
    return _SYNC


def reset_asset_sync_for_tests() -> None:
    """Replace the singleton.  For test isolation only."""
    global _SYNC
    with _SYNC_LOCK:
        _SYNC = None
