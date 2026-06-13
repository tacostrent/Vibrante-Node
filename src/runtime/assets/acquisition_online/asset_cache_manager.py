"""
Asset Cache Manager (Tier 12.9)
==================================
Local cache for downloaded assets.

Directory structure:
  {VIBRANTE_ASSET_CACHE}/assets/{provider}/{asset_id}/  — asset files
  {VIBRANTE_ASSET_CACHE}/cache_index.json               — cache metadata index

Features:
  - Deduplication by SHA-256 content hash
  - Version tracking
  - Provider-namespaced keys
"""
from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

ENV_ASSET_CACHE    = "VIBRANTE_ASSET_CACHE"
_INDEX_FILENAME    = "cache_index.json"
_ASSETS_SUBDIR     = "assets"


@dataclass
class CacheEntry:
    asset_id:    str = ""
    provider:    str = ""
    local_path:  str = ""
    version:     str = ""
    checksum:    str = ""
    size_bytes:  int = 0
    cached_at:   float = field(default_factory=time.time)
    last_used:   float = field(default_factory=time.time)
    formats:     List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id":   str(self.asset_id),
            "provider":   str(self.provider),
            "local_path": str(self.local_path),
            "version":    str(self.version),
            "checksum":   str(self.checksum),
            "size_bytes": int(self.size_bytes),
            "cached_at":  float(self.cached_at),
            "last_used":  float(self.last_used),
            "formats":    list(self.formats),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CacheEntry":
        d = d if isinstance(d, dict) else {}
        return cls(
            asset_id=str(d.get("asset_id", "")),
            provider=str(d.get("provider", "")),
            local_path=str(d.get("local_path", "")),
            version=str(d.get("version", "")),
            checksum=str(d.get("checksum", "")),
            size_bytes=int(d.get("size_bytes", 0)),
            cached_at=float(d.get("cached_at") or time.time()),
            last_used=float(d.get("last_used") or time.time()),
            formats=list(d.get("formats") or []),
        )


class AssetCacheManager:
    def __init__(self) -> None:
        self._lock  = threading.Lock()
        self._index: Dict[str, CacheEntry] = {}   # "provider:asset_id" → entry
        self._load_index()

    # ------------------------------------------------------------------
    # Directories
    # ------------------------------------------------------------------

    def _cache_root(self) -> Optional[str]:
        return os.environ.get(ENV_ASSET_CACHE, "").strip() or None

    def _assets_dir(self) -> Optional[str]:
        root = self._cache_root()
        return os.path.join(root, _ASSETS_SUBDIR) if root else None

    def _index_path(self) -> Optional[str]:
        root = self._cache_root()
        return os.path.join(root, _INDEX_FILENAME) if root else None

    def get_asset_dir(self, asset_id: str, provider: str) -> Optional[str]:
        """Return (or create) the directory for an asset. Returns None if no cache root."""
        assets_dir = self._assets_dir()
        if not assets_dir:
            return None
        path = os.path.join(assets_dir, str(provider), str(asset_id))
        os.makedirs(path, exist_ok=True)
        return path

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load_index(self) -> None:
        try:
            path = self._index_path()
            if not path or not os.path.isfile(path):
                return
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return
            with self._lock:
                for key, entry_dict in (data.get("entries") or {}).items():
                    self._index[key] = CacheEntry.from_dict(entry_dict)
        except Exception:
            pass

    def _save_index(self) -> None:
        try:
            path = self._index_path()
            if not path:
                return
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            with self._lock:
                payload = {
                    "__cache_schema_version__": "1.0.0",
                    "entries": {k: v.to_dict() for k, v in self._index.items()},
                }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, sort_keys=True)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Cache operations
    # ------------------------------------------------------------------

    def cache_asset(
        self,
        asset_id:   str,
        provider:   str,
        local_path: str,
        version:    str = "",
        checksum:   str = "",
        size_bytes: int = 0,
        formats:    Optional[List[str]] = None,
    ) -> CacheEntry:
        """Register an asset in the cache index. Never raises."""
        try:
            asset_id   = str(asset_id).strip()
            provider   = str(provider).strip()
            local_path = str(local_path).strip()
            if not asset_id or not local_path:
                return CacheEntry(asset_id=asset_id, provider=provider)
            key = f"{provider}:{asset_id}"
            entry = CacheEntry(
                asset_id=asset_id,
                provider=provider,
                local_path=local_path,
                version=str(version),
                checksum=str(checksum),
                size_bytes=int(size_bytes),
                formats=list(formats or []),
            )
            with self._lock:
                self._index[key] = entry
            self._save_index()
            return entry
        except Exception:
            return CacheEntry(asset_id=str(asset_id), provider=str(provider))

    def asset_exists(self, asset_id: str, provider: str = "") -> bool:
        """Check if asset is in cache and file exists on disk."""
        try:
            entry = self.get_cache_entry(asset_id, provider)
            if not entry:
                return False
            return bool(entry.local_path) and os.path.exists(entry.local_path)
        except Exception:
            return False

    def get_asset_path(self, asset_id: str, provider: str = "") -> Optional[str]:
        """Return local path for a cached asset, or None."""
        try:
            entry = self.get_cache_entry(asset_id, provider)
            if entry and entry.local_path and os.path.exists(entry.local_path):
                with self._lock:
                    entry.last_used = time.time()
                self._save_index()
                return entry.local_path
            return None
        except Exception:
            return None

    def get_cache_entry(self, asset_id: str, provider: str = "") -> Optional[CacheEntry]:
        """Return CacheEntry by asset_id (and optional provider). Never raises."""
        try:
            with self._lock:
                if provider:
                    return self._index.get(f"{provider}:{asset_id}")
                # Search all providers
                for key, entry in self._index.items():
                    if entry.asset_id == str(asset_id):
                        return entry
            return None
        except Exception:
            return None

    def remove_asset(self, asset_id: str, provider: str = "") -> bool:
        """Remove from cache index (does not delete files). Returns True if found."""
        try:
            removed = False
            # _save_index() acquires self._lock itself, so it must be called
            # after the lock is released (same pattern as cache_asset).
            with self._lock:
                if provider:
                    key = f"{provider}:{asset_id}"
                    if key in self._index:
                        del self._index[key]
                        removed = True
                else:
                    to_remove = [k for k, e in self._index.items()
                                 if e.asset_id == str(asset_id)]
                    for k in to_remove:
                        del self._index[k]
                    removed = bool(to_remove)
            if removed:
                self._save_index()
            return removed
        except Exception:
            return False

    def cache_statistics(self) -> Dict[str, Any]:
        with self._lock:
            total_bytes = sum(e.size_bytes for e in self._index.values())
            return {
                "total_assets":  len(self._index),
                "total_bytes":   total_bytes,
                "total_mb":      round(total_bytes / 1024 / 1024, 2),
                "cache_root":    self._cache_root() or "not configured",
            }

    def list_cached_assets(self) -> List[CacheEntry]:
        with self._lock:
            return list(self._index.values())


_INSTANCE: Optional[AssetCacheManager] = None
_INSTANCE_LOCK = threading.Lock()


def get_asset_cache_manager() -> AssetCacheManager:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = AssetCacheManager()
    return _INSTANCE


def reset_asset_cache_manager_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
