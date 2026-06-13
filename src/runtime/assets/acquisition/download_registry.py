"""
Download Registry (Tier 12.5)
==============================
Persistent JSON registry of all locally acquired assets.

Unlike the in-memory AssetDownloadManager (which tracks download tasks
initiated by Vibrante), the DownloadRegistry records assets that were
acquired externally through official Fab / Bridge workflows and then
discovered on disk.

Persisted to: VIBRANTE_ASSET_STORAGE/acquisition_registry.json
Falls back to in-memory-only mode when storage is not configured.

Deterministic, thread-safe, no Houdini dependency, no network calls.
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_REGISTRY_FILENAME = "acquisition_registry.json"
_SCHEMA_VERSION = "1.0.0"
_MAX_ENTRIES = 10000


def _registry_path() -> str:
    root = os.environ.get("VIBRANTE_ASSET_STORAGE", "").strip()
    if not root:
        return ""
    return os.path.join(root, _REGISTRY_FILENAME)


@dataclass
class RegistryEntry:
    entry_id:      str = field(default_factory=lambda: f"reg_{uuid.uuid4().hex[:10]}")
    asset_id:      str = ""
    provider:      str = ""
    name:          str = ""
    category:      str = ""
    local_path:    str = ""
    formats:       List[str] = field(default_factory=list)
    tags:          List[str] = field(default_factory=list)
    semantic_tags: List[str] = field(default_factory=list)
    provenance:    Dict[str, Any] = field(default_factory=dict)
    status:        str = "available"  # "available" | "missing" | "corrupted"
    registered_at: float = field(default_factory=time.time)
    last_verified: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id":      str(self.entry_id),
            "asset_id":      str(self.asset_id),
            "provider":      str(self.provider),
            "name":          str(self.name),
            "category":      str(self.category),
            "local_path":    str(self.local_path),
            "formats":       list(self.formats),
            "tags":          list(self.tags),
            "semantic_tags": list(self.semantic_tags),
            "provenance":    dict(self.provenance),
            "status":        str(self.status),
            "registered_at": float(self.registered_at),
            "last_verified": float(self.last_verified),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RegistryEntry":
        d = d if isinstance(d, dict) else {}
        return cls(
            entry_id=str(d.get("entry_id") or f"reg_{uuid.uuid4().hex[:10]}"),
            asset_id=str(d.get("asset_id", "")),
            provider=str(d.get("provider", "")),
            name=str(d.get("name", "")),
            category=str(d.get("category", "")),
            local_path=str(d.get("local_path", "")),
            formats=list(d.get("formats") or []),
            tags=list(d.get("tags") or []),
            semantic_tags=list(d.get("semantic_tags") or []),
            provenance=dict(d.get("provenance") or {}),
            status=str(d.get("status", "available")),
            registered_at=float(d.get("registered_at") or time.time()),
            last_verified=float(d.get("last_verified") or time.time()),
        )


class DownloadRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        # Primary key: (provider, asset_id) → entry_id
        self._by_key:     Dict[str, str] = {}
        # entry_id → RegistryEntry
        self._entries:    Dict[str, RegistryEntry] = {}
        self._dirty:      bool = False
        self._load_count: int = 0
        self._save_count: int = 0
        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        path = _registry_path()
        if not path or not os.path.isfile(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return
            for entry_dict in (data.get("entries") or []):
                entry = RegistryEntry.from_dict(entry_dict)
                self._entries[entry.entry_id] = entry
                key = self._make_key(entry.provider, entry.asset_id)
                self._by_key[key] = entry.entry_id
            self._load_count += 1
        except Exception:
            pass

    def _save(self) -> bool:
        path = _registry_path()
        if not path:
            return False
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            payload = {
                "_schema_version": _SCHEMA_VERSION,
                "saved_at":        time.time(),
                "entries":         [e.to_dict() for e in self._entries.values()],
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, sort_keys=True, indent=2, default=str)
            self._save_count += 1
            self._dirty = False
            return True
        except Exception:
            return False

    @staticmethod
    def _make_key(provider: str, asset_id: str) -> str:
        return f"{provider.lower()}::{asset_id}"

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def register(
        self,
        asset_id: str,
        provider: str,
        local_path: str,
        name: str = "",
        category: str = "",
        formats: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        semantic_tags: Optional[List[str]] = None,
        provenance: Optional[Dict[str, Any]] = None,
    ) -> RegistryEntry:
        """Register or update an acquired asset. Thread-safe."""
        key = self._make_key(str(provider), str(asset_id))
        with self._lock:
            if key in self._by_key:
                # Update existing
                entry = self._entries[self._by_key[key]]
                entry.local_path  = str(local_path)
                entry.name        = str(name) or entry.name
                entry.category    = str(category) or entry.category
                entry.formats     = list(formats or entry.formats)
                entry.tags        = list(tags or entry.tags)
                entry.semantic_tags = list(semantic_tags or entry.semantic_tags)
                entry.provenance  = dict(provenance or entry.provenance)
                entry.status      = "available"
                entry.last_verified = time.time()
            else:
                # Cap registry
                if len(self._entries) >= _MAX_ENTRIES:
                    oldest = sorted(self._entries.values(), key=lambda e: e.registered_at)
                    for old in oldest[:len(self._entries) - _MAX_ENTRIES + 1]:
                        self._entries.pop(old.entry_id, None)
                        old_key = self._make_key(old.provider, old.asset_id)
                        self._by_key.pop(old_key, None)

                entry = RegistryEntry(
                    asset_id=str(asset_id),
                    provider=str(provider),
                    name=str(name),
                    category=str(category),
                    local_path=str(local_path),
                    formats=list(formats or []),
                    tags=list(tags or []),
                    semantic_tags=list(semantic_tags or []),
                    provenance=dict(provenance or {"source": "local_acquisition"}),
                )
                self._entries[entry.entry_id] = entry
                self._by_key[key] = entry.entry_id
            self._dirty = True
        return entry

    def get(self, entry_id: str) -> Optional[RegistryEntry]:
        with self._lock:
            e = self._entries.get(entry_id)
            return e

    def find(self, provider: str, asset_id: str) -> Optional[RegistryEntry]:
        key = self._make_key(str(provider), str(asset_id))
        with self._lock:
            eid = self._by_key.get(key)
            return self._entries.get(eid) if eid else None

    def exists(self, provider: str, asset_id: str) -> bool:
        return self.find(provider, asset_id) is not None

    def remove(self, entry_id: str) -> bool:
        with self._lock:
            entry = self._entries.pop(entry_id, None)
            if entry:
                key = self._make_key(entry.provider, entry.asset_id)
                self._by_key.pop(key, None)
                self._dirty = True
                return True
            return False

    def list_entries(
        self,
        provider: str = "",
        category: str = "",
        status: str = "",
    ) -> List[RegistryEntry]:
        with self._lock:
            entries = list(self._entries.values())
        if provider:
            entries = [e for e in entries if e.provider.lower() == provider.lower()]
        if category:
            entries = [e for e in entries if e.category.lower() == category.lower()]
        if status:
            entries = [e for e in entries if e.status == status]
        return sorted(entries, key=lambda e: (e.provider, e.name))

    def mark_missing(self, entry_id: str) -> bool:
        with self._lock:
            entry = self._entries.get(entry_id)
            if entry:
                entry.status = "missing"
                entry.last_verified = time.time()
                self._dirty = True
                return True
            return False

    def verify_paths(self) -> Dict[str, Any]:
        """Check which registered entries still exist on disk."""
        with self._lock:
            entries = list(self._entries.values())
        missing: List[str] = []
        found:   List[str] = []
        for entry in entries:
            if entry.local_path and os.path.exists(entry.local_path):
                found.append(entry.entry_id)
                with self._lock:
                    if entry.entry_id in self._entries:
                        self._entries[entry.entry_id].status = "available"
                        self._entries[entry.entry_id].last_verified = time.time()
            else:
                missing.append(entry.entry_id)
                with self._lock:
                    if entry.entry_id in self._entries:
                        self._entries[entry.entry_id].status = "missing"
                        self._entries[entry.entry_id].last_verified = time.time()
        if missing:
            with self._lock:
                self._dirty = True
        return {
            "total":   len(entries),
            "found":   len(found),
            "missing": len(missing),
            "missing_ids": missing,
        }

    def flush(self) -> bool:
        """Persist to disk if dirty. Returns True if saved or not dirty."""
        with self._lock:
            if not self._dirty:
                return True
        return self._save()

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._entries)
            by_provider: Dict[str, int] = {}
            by_status:   Dict[str, int] = {}
            for e in self._entries.values():
                by_provider[e.provider] = by_provider.get(e.provider, 0) + 1
                by_status[e.status]     = by_status.get(e.status, 0) + 1
        return {
            "total_entries":  total,
            "by_provider":    dict(sorted(by_provider.items())),
            "by_status":      dict(sorted(by_status.items())),
            "load_count":     self._load_count,
            "save_count":     self._save_count,
            "registry_path":  _registry_path(),
        }


_INSTANCE: Optional[DownloadRegistry] = None
_INSTANCE_LOCK = threading.Lock()


def get_download_registry() -> DownloadRegistry:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = DownloadRegistry()
    return _INSTANCE


def reset_download_registry_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
