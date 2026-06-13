"""
Library Index (Tier 12.5)
==========================
Builds and maintains a searchable in-memory index of all locally acquired
assets from Fab and Megascans libraries. The index can also be persisted
to disk as a deterministic JSON snapshot.

Designed for fast lookups by name, category, tags, and provider.
Updated incrementally when new assets are discovered.

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

_INDEX_FILENAME = "library_index.json"
_SCHEMA_VERSION = "1.0.0"
_MAX_INDEX_ENTRIES = 50000


def _index_path() -> str:
    root = os.environ.get("VIBRANTE_ASSET_STORAGE", "").strip()
    if not root:
        return ""
    return os.path.join(root, _INDEX_FILENAME)


@dataclass
class IndexEntry:
    index_id:      str = field(default_factory=lambda: f"idx_{uuid.uuid4().hex[:10]}")
    asset_id:      str = ""
    provider:      str = ""
    name:          str = ""
    category:      str = ""
    subcategory:   str = ""
    tags:          List[str] = field(default_factory=list)
    semantic_tags: List[str] = field(default_factory=list)
    formats:       List[str] = field(default_factory=list)
    local_path:    str = ""
    provenance:    str = ""   # e.g. "fab_local_library", "megascans_local_library"
    indexed_at:    float = field(default_factory=time.time)
    extra:         Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index_id":      str(self.index_id),
            "asset_id":      str(self.asset_id),
            "provider":      str(self.provider),
            "name":          str(self.name),
            "category":      str(self.category),
            "subcategory":   str(self.subcategory),
            "tags":          list(self.tags),
            "semantic_tags": list(self.semantic_tags),
            "formats":       list(self.formats),
            "local_path":    str(self.local_path),
            "provenance":    str(self.provenance),
            "indexed_at":    float(self.indexed_at),
            "extra":         dict(self.extra),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "IndexEntry":
        d = d if isinstance(d, dict) else {}
        return cls(
            index_id=str(d.get("index_id") or f"idx_{uuid.uuid4().hex[:10]}"),
            asset_id=str(d.get("asset_id", "")),
            provider=str(d.get("provider", "")),
            name=str(d.get("name", "")),
            category=str(d.get("category", "")),
            subcategory=str(d.get("subcategory", "")),
            tags=list(d.get("tags") or []),
            semantic_tags=list(d.get("semantic_tags") or []),
            formats=list(d.get("formats") or []),
            local_path=str(d.get("local_path", "")),
            provenance=str(d.get("provenance", "")),
            indexed_at=float(d.get("indexed_at") or time.time()),
            extra=dict(d.get("extra") or {}),
        )


@dataclass
class IndexSearchResult:
    ok:           bool = True
    query:        str = ""
    entries:      List[IndexEntry] = field(default_factory=list)
    total_hits:   int = 0
    search_time:  float = 0.0
    errors:       List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok":          bool(self.ok),
            "query":       str(self.query),
            "entries":     [e.to_dict() for e in self.entries],
            "total_hits":  int(self.total_hits),
            "search_time": float(self.search_time),
            "errors":      list(self.errors),
        }


class LibraryIndex:
    def __init__(self) -> None:
        self._lock       = threading.Lock()
        # (provider, asset_id) → index_id
        self._key_map:   Dict[str, str] = {}
        # index_id → IndexEntry
        self._entries:   Dict[str, IndexEntry] = {}
        self._dirty:     bool = False
        self._add_count: int = 0
        self._hit_count: int = 0
        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        path = _index_path()
        if not path or not os.path.isfile(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for entry_dict in (data.get("entries") or []):
                entry = IndexEntry.from_dict(entry_dict)
                self._entries[entry.index_id] = entry
                key = self._make_key(entry.provider, entry.asset_id)
                self._key_map[key] = entry.index_id
        except Exception:
            pass

    def save(self) -> bool:
        """Persist the index to disk. Returns True on success."""
        path = _index_path()
        if not path:
            return False
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with self._lock:
                payload = {
                    "_schema_version": _SCHEMA_VERSION,
                    "saved_at":        time.time(),
                    "total":           len(self._entries),
                    "entries":         [e.to_dict() for e in self._entries.values()],
                }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, sort_keys=True, indent=2, default=str)
            with self._lock:
                self._dirty = False
            return True
        except Exception:
            return False

    @staticmethod
    def _make_key(provider: str, asset_id: str) -> str:
        return f"{provider.lower()}::{asset_id}"

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def add_entry(
        self,
        asset_id:      str,
        provider:      str,
        name:          str,
        category:      str = "",
        subcategory:   str = "",
        tags:          Optional[List[str]] = None,
        semantic_tags: Optional[List[str]] = None,
        formats:       Optional[List[str]] = None,
        local_path:    str = "",
        provenance:    str = "",
        extra:         Optional[Dict[str, Any]] = None,
    ) -> IndexEntry:
        """Add or update an index entry. Thread-safe."""
        key = self._make_key(str(provider), str(asset_id))
        with self._lock:
            if key in self._key_map:
                entry = self._entries[self._key_map[key]]
                entry.name          = str(name) or entry.name
                entry.category      = str(category) or entry.category
                entry.subcategory   = str(subcategory) or entry.subcategory
                entry.tags          = sorted(set(list(tags or []) + entry.tags))
                entry.semantic_tags = sorted(set(list(semantic_tags or []) + entry.semantic_tags))
                entry.formats       = sorted(set(list(formats or []) + entry.formats))
                entry.local_path    = str(local_path) or entry.local_path
                entry.provenance    = str(provenance) or entry.provenance
                if extra:
                    entry.extra.update(extra)
                entry.indexed_at = time.time()
            else:
                if len(self._entries) >= _MAX_INDEX_ENTRIES:
                    oldest = sorted(self._entries.values(), key=lambda e: e.indexed_at)
                    for old in oldest[:max(1, len(self._entries) - _MAX_INDEX_ENTRIES + 1)]:
                        self._entries.pop(old.index_id, None)
                        self._key_map.pop(self._make_key(old.provider, old.asset_id), None)

                entry = IndexEntry(
                    asset_id=str(asset_id),
                    provider=str(provider),
                    name=str(name),
                    category=str(category),
                    subcategory=str(subcategory),
                    tags=sorted(set(tags or [])),
                    semantic_tags=sorted(set(semantic_tags or [])),
                    formats=sorted(set(formats or [])),
                    local_path=str(local_path),
                    provenance=str(provenance),
                    extra=dict(extra or {}),
                )
                self._entries[entry.index_id] = entry
                self._key_map[key] = entry.index_id
                self._add_count += 1
            self._dirty = True
        return entry

    def add_from_descriptor(self, asset_dict: Dict[str, Any], provenance: str = "") -> Optional[IndexEntry]:
        """Add an entry from an AssetDescriptor-compatible dict."""
        try:
            asset_dict = asset_dict if isinstance(asset_dict, dict) else {}
            asset_id = str(asset_dict.get("asset_id", "")).strip()
            provider = str(asset_dict.get("provider", "")).strip()
            if not asset_id or not provider:
                return None
            meta   = asset_dict.get("metadata") or {}
            extra  = dict(meta.get("extra") or {}) if isinstance(meta, dict) else {}
            return self.add_entry(
                asset_id=asset_id,
                provider=provider,
                name=str(asset_dict.get("name", "")),
                category=str(asset_dict.get("category", "")),
                tags=list(asset_dict.get("tags") or []),
                semantic_tags=list(asset_dict.get("environment_suitability") or []),
                formats=list(asset_dict.get("formats") or []),
                local_path=str(extra.get("local_path", "")),
                provenance=provenance or str(extra.get("source", "")),
                extra=extra,
            )
        except Exception:
            return None

    def remove(self, provider: str, asset_id: str) -> bool:
        key = self._make_key(str(provider), str(asset_id))
        with self._lock:
            index_id = self._key_map.pop(key, None)
            if index_id:
                self._entries.pop(index_id, None)
                self._dirty = True
                return True
            return False

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        query:     str = "",
        category:  str = "",
        provider:  str = "",
        tags:      Optional[List[str]] = None,
        limit:     int = 50,
    ) -> IndexSearchResult:
        """Full-text search across name, tags, and category. Deterministic."""
        try:
            t0 = time.perf_counter()
            with self._lock:
                entries = list(self._entries.values())

            q   = str(query   or "").lower().strip()
            cat = str(category or "").lower().strip()
            prov = str(provider or "").lower().strip()
            tag_filters = [t.lower() for t in (tags or [])]

            results: List[tuple[float, IndexEntry]] = []
            for e in entries:
                # Provider filter
                if prov and e.provider.lower() != prov:
                    continue
                # Category filter
                if cat and e.category.lower() != cat:
                    continue
                # Tag filter
                e_tags = set(t.lower() for t in e.tags + e.semantic_tags)
                if tag_filters and not all(tf in e_tags for tf in tag_filters):
                    continue
                # Relevance score
                score = 0.0
                if q:
                    if q in e.name.lower():
                        score += 1.0
                    for tag in e.tags:
                        if q in tag.lower():
                            score += 0.3
                    if q in e.category.lower():
                        score += 0.2
                    if q in e.provider.lower():
                        score += 0.1
                    if score == 0.0:
                        continue  # no match
                else:
                    score = 1.0
                results.append((score, e))

            results.sort(key=lambda x: (-x[0], x[1].name))
            limited = [e for _, e in results[:limit]]
            elapsed = time.perf_counter() - t0

            with self._lock:
                self._hit_count += 1

            return IndexSearchResult(
                ok=True,
                query=query,
                entries=limited,
                total_hits=len(results),
                search_time=round(elapsed, 4),
            )
        except Exception as exc:
            return IndexSearchResult(ok=False, query=query, errors=[f"search failed: {exc}"])

    def get_entry(self, provider: str, asset_id: str) -> Optional[IndexEntry]:
        key = self._make_key(str(provider), str(asset_id))
        with self._lock:
            index_id = self._key_map.get(key)
            return self._entries.get(index_id) if index_id else None

    def list_providers(self) -> List[str]:
        with self._lock:
            return sorted({e.provider for e in self._entries.values()})

    def list_categories(self) -> List[str]:
        with self._lock:
            return sorted({e.category for e in self._entries.values() if e.category})

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._entries)
            by_provider: Dict[str, int] = {}
            by_category: Dict[str, int] = {}
            for e in self._entries.values():
                by_provider[e.provider] = by_provider.get(e.provider, 0) + 1
                by_category[e.category] = by_category.get(e.category, 0) + 1
        return {
            "total_entries": total,
            "by_provider":   dict(sorted(by_provider.items())),
            "by_category":   dict(sorted(by_category.items())),
            "add_count":     self._add_count,
            "hit_count":     self._hit_count,
            "is_dirty":      self._dirty,
            "index_path":    _index_path(),
        }


_INSTANCE: Optional[LibraryIndex] = None
_INSTANCE_LOCK = threading.Lock()


def get_library_index() -> LibraryIndex:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = LibraryIndex()
    return _INSTANCE


def reset_library_index_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
