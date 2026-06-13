"""
Asset Catalog (Tier 12.7)
===========================
Persistent semantic database for enriched asset records.

Storage:
  In-memory dict for all operations (fast).
  Optional JSON persistence when VIBRANTE_ASSET_STORAGE env var is set.

The catalog stores the full EnrichedAsset data plus search indices for
environment, role, lookdev, storytelling, and cinematic usage queries.

Environment variable:
  VIBRANTE_ASSET_STORAGE  — directory for catalog JSON persistence
"""
from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional

from .asset_catalog_serializer import get_asset_catalog_serializer
from .asset_catalog_statistics import get_catalog_statistics

ENV_ASSET_STORAGE = "VIBRANTE_ASSET_STORAGE"
_CATALOG_FILENAME = "semantic_catalog.json"


@dataclass
class CatalogEntry:
    asset_id:        str = ""
    name:            str = ""
    provider:        str = ""
    category:        str = ""
    tags:            List[str] = field(default_factory=list)
    semantic_tags:   List[str] = field(default_factory=list)
    environments:    List[str] = field(default_factory=list)
    roles:           List[str] = field(default_factory=list)
    lookdev:         List[str] = field(default_factory=list)
    storytelling:    str = ""
    cinematic_usage: List[str] = field(default_factory=list)
    download_url:    str = ""
    preview_url:     str = ""
    downloaded:      bool = False
    local_path:      str = ""
    metadata_source: str = ""
    last_synced:     float = field(default_factory=time.time)
    # Denormalized for fast filtering
    primary_env:     str = ""
    primary_role:    str = ""
    primary_lookdev: str = ""
    importance:      str = "ambient"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id":        str(self.asset_id),
            "name":            str(self.name),
            "provider":        str(self.provider),
            "category":        str(self.category),
            "tags":            list(self.tags),
            "semantic_tags":   list(self.semantic_tags),
            "environments":    list(self.environments),
            "roles":           list(self.roles),
            "lookdev":         list(self.lookdev),
            "storytelling":    str(self.storytelling),
            "cinematic_usage": list(self.cinematic_usage),
            "download_url":    str(self.download_url),
            "preview_url":     str(self.preview_url),
            "downloaded":      bool(self.downloaded),
            "local_path":      str(self.local_path),
            "metadata_source": str(self.metadata_source),
            "last_synced":     float(self.last_synced),
            "primary_env":     str(self.primary_env),
            "primary_role":    str(self.primary_role),
            "primary_lookdev": str(self.primary_lookdev),
            "importance":      str(self.importance),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CatalogEntry":
        d = d if isinstance(d, dict) else {}
        return cls(
            asset_id=str(d.get("asset_id", "")),
            name=str(d.get("name", "")),
            provider=str(d.get("provider", "")),
            category=str(d.get("category", "")),
            tags=list(d.get("tags") or []),
            semantic_tags=list(d.get("semantic_tags") or []),
            environments=list(d.get("environments") or []),
            roles=list(d.get("roles") or []),
            lookdev=list(d.get("lookdev") or []),
            storytelling=str(d.get("storytelling", "")),
            cinematic_usage=list(d.get("cinematic_usage") or []),
            download_url=str(d.get("download_url", "")),
            preview_url=str(d.get("preview_url", "")),
            downloaded=bool(d.get("downloaded", False)),
            local_path=str(d.get("local_path", "")),
            metadata_source=str(d.get("metadata_source", "")),
            last_synced=float(d.get("last_synced") or time.time()),
            primary_env=str(d.get("primary_env", "")),
            primary_role=str(d.get("primary_role", "")),
            primary_lookdev=str(d.get("primary_lookdev", "")),
            importance=str(d.get("importance", "ambient")),
        )

    @classmethod
    def from_enriched(cls, enriched: Dict[str, Any], extra: Optional[Dict[str, Any]] = None) -> "CatalogEntry":
        """Build a CatalogEntry from an EnrichedAsset dict."""
        extra = extra or {}
        return cls(
            asset_id=str(enriched.get("asset_id", "")),
            name=str(enriched.get("name", "")),
            provider=str(enriched.get("provider", "")),
            category=str(enriched.get("category", "")),
            tags=list(enriched.get("tags") or []),
            semantic_tags=list(enriched.get("semantic_tags") or []),
            environments=list(enriched.get("environments") or []),
            roles=list(enriched.get("roles") or []),
            lookdev=list(enriched.get("lookdev_tags") or []),
            storytelling=str(enriched.get("story_role", "")),
            cinematic_usage=list(enriched.get("cinematic_usage") or []),
            download_url=str(extra.get("download_url", "")),
            preview_url=str(enriched.get("preview_url") or extra.get("preview_url", "")),
            downloaded=bool(extra.get("downloaded", False)),
            local_path=str(extra.get("local_path", "")),
            metadata_source=str(extra.get("metadata_source", "enriched")),
            primary_env=str(enriched.get("primary_env", "")),
            primary_role=str(enriched.get("primary_role", "")),
            primary_lookdev=str(enriched.get("primary_lookdev", "")),
            importance=str(enriched.get("importance", "ambient")),
        )


class AssetCatalog:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._entries: Dict[str, CatalogEntry] = {}
        self._loaded = False
        self._load_from_disk()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _catalog_path(self) -> Optional[str]:
        storage = os.environ.get(ENV_ASSET_STORAGE, "").strip()
        if not storage:
            return None
        return os.path.join(storage, _CATALOG_FILENAME)

    def _load_from_disk(self) -> None:
        try:
            path = self._catalog_path()
            if not path or not os.path.isfile(path):
                return
            with open(path, "r", encoding="utf-8") as f:
                raw = f.read()
            entries = get_asset_catalog_serializer().deserialize_catalog(raw)
            with self._lock:
                for e in entries:
                    entry = CatalogEntry.from_dict(e)
                    if entry.asset_id:
                        self._entries[entry.asset_id] = entry
            self._loaded = True
        except Exception:
            pass

    def save_to_disk(self) -> bool:
        """Persist catalog to disk. Returns True on success."""
        try:
            path = self._catalog_path()
            if not path:
                return False
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with self._lock:
                entries = [e.to_dict() for e in self._entries.values()]
            data = get_asset_catalog_serializer().serialize_catalog(entries)
            with open(path, "w", encoding="utf-8") as f:
                f.write(data)
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def register_asset(
        self,
        asset_id: str,
        enriched_dict: Dict[str, Any],
        extra: Optional[Dict[str, Any]] = None,
    ) -> CatalogEntry:
        """Register a new asset or overwrite an existing one. Never raises."""
        try:
            asset_id = str(asset_id).strip()
            if not asset_id:
                raise ValueError("asset_id is required")
            entry = CatalogEntry.from_enriched(enriched_dict, extra)
            entry.asset_id = asset_id
            with self._lock:
                self._entries[asset_id] = entry
            get_catalog_statistics().record("register", asset_id=asset_id)
            return entry
        except Exception as exc:
            get_catalog_statistics().record("register", asset_id=str(asset_id), ok=False)
            return CatalogEntry(asset_id=str(asset_id))

    def update_asset(self, asset_id: str, updates: Dict[str, Any]) -> bool:
        """Partially update a catalog entry. Returns True if found and updated."""
        try:
            asset_id = str(asset_id).strip()
            with self._lock:
                entry = self._entries.get(asset_id)
                if not entry:
                    return False
                d = entry.to_dict()
                d.update({k: v for k, v in updates.items() if k in d})
                self._entries[asset_id] = CatalogEntry.from_dict(d)
            return True
        except Exception:
            return False

    def remove_asset(self, asset_id: str) -> bool:
        """Remove an asset from the catalog. Returns True if found and removed."""
        try:
            with self._lock:
                if asset_id in self._entries:
                    del self._entries[asset_id]
                    return True
            return False
        except Exception:
            return False

    def get_asset(self, asset_id: str) -> Optional[CatalogEntry]:
        """Return a CatalogEntry by ID, or None."""
        try:
            with self._lock:
                return self._entries.get(str(asset_id).strip())
        except Exception:
            return None

    def asset_exists(self, asset_id: str) -> bool:
        with self._lock:
            return str(asset_id).strip() in self._entries

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search_assets(
        self,
        query: str = "",
        environment: str = "",
        role: str = "",
        lookdev: str = "",
        storytelling: str = "",
        cinematic: str = "",
        provider: str = "",
        category: str = "",
        downloaded_only: bool = False,
        limit: int = 50,
    ) -> List[CatalogEntry]:
        """Multi-facet semantic search. Never raises."""
        try:
            return self._do_search(
                query=query.lower().strip(),
                environment=environment.lower().strip(),
                role=role.lower().strip(),
                lookdev=lookdev.lower().strip(),
                storytelling=storytelling.lower().strip(),
                cinematic=cinematic.lower().strip(),
                provider=provider.lower().strip(),
                category=category.lower().strip(),
                downloaded_only=downloaded_only,
                limit=int(limit),
            )
        except Exception:
            return []

    def _do_search(
        self, query, environment, role, lookdev,
        storytelling, cinematic, provider, category,
        downloaded_only, limit,
    ) -> List[CatalogEntry]:
        get_catalog_statistics().record("query")
        with self._lock:
            candidates = list(self._entries.values())

        results = []
        for entry in candidates:
            if downloaded_only and not entry.downloaded:
                continue
            if provider and entry.provider.lower() != provider:
                continue
            if category and entry.category.lower() != category:
                continue
            if environment and environment not in entry.environments:
                continue
            if role and role not in entry.roles:
                continue
            if lookdev and lookdev not in entry.lookdev:
                continue
            if storytelling and entry.storytelling.lower() != storytelling:
                continue
            if cinematic and cinematic not in entry.cinematic_usage:
                continue
            if query:
                text = f"{entry.name} {entry.category} {' '.join(entry.tags)} {' '.join(entry.semantic_tags)}"
                if query not in text.lower():
                    continue
            results.append(entry)

        # Sort: importance order, then name
        _importance_order = {"primary": 0, "secondary": 1, "tertiary": 2, "ambient": 3}
        results.sort(key=lambda e: (_importance_order.get(e.importance, 4), e.name.lower()))
        return results[:limit]

    def iter_all(self) -> Iterator[CatalogEntry]:
        with self._lock:
            entries = list(self._entries.values())
        yield from entries

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._entries)
            by_env: Dict[str, int] = {}
            by_role: Dict[str, int] = {}
            downloaded = 0
            for e in self._entries.values():
                for env in e.environments:
                    by_env[env] = by_env.get(env, 0) + 1
                for r in e.roles:
                    by_role[r] = by_role.get(r, 0) + 1
                if e.downloaded:
                    downloaded += 1
            return {
                "total":      total,
                "downloaded": downloaded,
                "by_env":     by_env,
                "by_role":    by_role,
            }


_INSTANCE: Optional[AssetCatalog] = None
_INSTANCE_LOCK = threading.Lock()


def get_asset_catalog() -> AssetCatalog:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = AssetCatalog()
    return _INSTANCE


def reset_asset_catalog_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
