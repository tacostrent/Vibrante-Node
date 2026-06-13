"""
Asset Storage (Tier 12 — Asset Ecosystem Expansion)
====================================================
Manages the local asset cache directory and in-memory registry.

Default root: VIBRANTE_ASSET_STORAGE env var → ~/VibranteAssets

Public API:
    StorageRecord                — descriptor
    AssetStorage                 — manager class
    get_asset_storage()          — singleton
    reset_asset_storage_for_tests()
"""

from __future__ import annotations

import os
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

from src.runtime.assets.schema import AssetDescriptor


class StorageRecord:
    """Represents a registered asset in local storage."""

    def __init__(
        self,
        asset_descriptor: AssetDescriptor,
        local_path: str,
    ) -> None:
        self.storage_id:    str   = f"stor_{uuid.uuid4().hex[:12]}"
        self.asset_id:      str   = asset_descriptor.asset_id
        self.provider:      str   = asset_descriptor.provider
        self.local_path:    str   = local_path
        self.format:        str   = asset_descriptor.formats[0] if asset_descriptor.formats else "unknown"
        self.size_bytes:    int   = self._get_file_size(local_path)
        self.registered_at: float = time.time()
        self.last_accessed: float = time.time()
        # Keep a copy of the name for reference
        self.asset_name:    str   = asset_descriptor.name
        self.category:      str   = asset_descriptor.category

    def _get_file_size(self, path: str) -> int:
        if path and os.path.isfile(path):
            try:
                return os.path.getsize(path)
            except OSError:
                pass
        return 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "storage_id":    self.storage_id,
            "asset_id":      self.asset_id,
            "provider":      self.provider,
            "local_path":    self.local_path,
            "format":        self.format,
            "size_bytes":    self.size_bytes,
            "registered_at": self.registered_at,
            "last_accessed": self.last_accessed,
            "asset_name":    self.asset_name,
            "category":      self.category,
        }


class AssetStorage:
    """
    Manages local asset cache directory and in-memory registry.

    Storage root priority:
        1. VIBRANTE_ASSET_STORAGE environment variable
        2. ~/VibranteAssets

    Thread-safe in-memory registry: (provider, asset_id) → StorageRecord
    """

    def __init__(self, root: Optional[str] = None) -> None:
        self._root = root
        self._lock: threading.Lock = threading.Lock()
        # Key: (provider, asset_id) → StorageRecord
        self._registry: Dict[tuple, StorageRecord] = {}

    @property
    def _resolved_root(self) -> str:
        if self._root:
            return self._root
        env_root = os.environ.get("VIBRANTE_ASSET_STORAGE")
        if env_root:
            return env_root
        return os.path.expanduser("~/VibranteAssets")

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_asset(
        self,
        asset_descriptor: AssetDescriptor,
        local_path: str,
    ) -> str:
        """
        Register an asset in local storage.

        Args:
            asset_descriptor: The asset to register.
            local_path:       Local filesystem path where the asset is stored.

        Returns:
            storage_id (str)
        """
        record = StorageRecord(asset_descriptor, local_path)
        key = (asset_descriptor.provider, asset_descriptor.asset_id)
        with self._lock:
            self._registry[key] = record
        return record.storage_id

    def remove_asset(self, storage_id: str) -> bool:
        """
        Remove an asset registration by storage_id.

        Returns True if found and removed.
        """
        with self._lock:
            key_to_remove = None
            for key, record in self._registry.items():
                if record.storage_id == storage_id:
                    key_to_remove = key
                    break
            if key_to_remove:
                del self._registry[key_to_remove]
                return True
        return False

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_asset(self, storage_id: str) -> Optional[StorageRecord]:
        """Return a StorageRecord by storage_id."""
        with self._lock:
            for record in self._registry.values():
                if record.storage_id == storage_id:
                    record.last_accessed = time.time()
                    return record
        return None

    def find_asset(self, provider: str, asset_id: str) -> Optional[StorageRecord]:
        """Find a StorageRecord by (provider, asset_id)."""
        key = (provider, asset_id)
        with self._lock:
            record = self._registry.get(key)
            if record:
                record.last_accessed = time.time()
                return record
        return None

    def asset_exists(self, provider: str, asset_id: str) -> bool:
        """Return True if the asset is registered."""
        key = (provider, asset_id)
        with self._lock:
            return key in self._registry

    def list_assets(
        self,
        provider: Optional[str] = None,
        category: Optional[str] = None,
    ) -> List[StorageRecord]:
        """
        Return all registered assets, optionally filtered.

        Results are sorted by (provider, asset_id) for determinism.
        """
        with self._lock:
            records = list(self._registry.values())
        if provider:
            records = [r for r in records if r.provider == provider]
        if category:
            records = [r for r in records if r.category == category]
        return sorted(records, key=lambda r: (r.provider, r.asset_id))

    # ------------------------------------------------------------------
    # Storage root
    # ------------------------------------------------------------------

    def get_storage_root(self) -> str:
        """Return the configured storage root path."""
        return self._resolved_root

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_storage_statistics(self) -> Dict[str, Any]:
        """Return storage usage statistics."""
        with self._lock:
            records = list(self._registry.values())
        total_size = sum(r.size_bytes for r in records)
        by_provider: Dict[str, int] = {}
        for r in records:
            by_provider[r.provider] = by_provider.get(r.provider, 0) + 1
        return {
            "total_assets":     len(records),
            "total_size_bytes": total_size,
            "assets_by_provider": by_provider,
            "storage_root":     self._resolved_root,
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_STORAGE: Optional[AssetStorage] = None
_STORAGE_LOCK = threading.Lock()


def get_asset_storage() -> AssetStorage:
    """Return the module-level singleton AssetStorage."""
    global _STORAGE
    if _STORAGE is None:
        with _STORAGE_LOCK:
            if _STORAGE is None:
                _STORAGE = AssetStorage()
    return _STORAGE


def reset_asset_storage_for_tests() -> None:
    """Replace the singleton.  For test isolation only."""
    global _STORAGE
    with _STORAGE_LOCK:
        _STORAGE = None
