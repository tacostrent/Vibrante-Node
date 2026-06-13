"""
Catalog Vector Index Builder (Tier 12.8)
==========================================
Builds and maintains the vector index from the semantic catalog.

Workflow:
  AssetCatalog → AssetEmbeddingBuilder → AssetVectorStore

Methods:
  build_full_index()    — embed all catalog assets and store
  update_asset_index()  — update embedding for one asset
  rebuild_index()       — clear store and rebuild from scratch
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .asset_embedding_builder import get_asset_embedding_builder
from .asset_vector_store import get_asset_vector_store


@dataclass
class IndexBuildResult:
    ok:          bool = True
    indexed:     int = 0
    skipped:     int = 0
    errors:      List[str] = field(default_factory=list)
    duration_ms: float = 0.0
    strategy:    str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok":          bool(self.ok),
            "indexed":     int(self.indexed),
            "skipped":     int(self.skipped),
            "errors":      list(self.errors),
            "duration_ms": round(float(self.duration_ms), 2),
            "strategy":    str(self.strategy),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "IndexBuildResult":
        d = d if isinstance(d, dict) else {}
        return cls(
            ok=bool(d.get("ok", True)),
            indexed=int(d.get("indexed", 0)),
            skipped=int(d.get("skipped", 0)),
            errors=list(d.get("errors") or []),
            duration_ms=float(d.get("duration_ms", 0.0)),
            strategy=str(d.get("strategy", "")),
        )


class CatalogVectorIndexBuilder:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._build_count = 0
        self._last_built: float = 0.0

    def build_full_index(self, limit: int = 10000) -> IndexBuildResult:
        """Build embeddings for all assets in catalog. Never raises."""
        try:
            return self._do_build(force_rebuild=False, limit=int(limit))
        except Exception as exc:
            return IndexBuildResult(ok=False, errors=[f"build_full_index failed: {exc}"])

    def rebuild_index(self) -> IndexBuildResult:
        """Clear the vector store and rebuild all embeddings from scratch. Never raises."""
        try:
            get_asset_vector_store().clear()
            return self._do_build(force_rebuild=True, limit=100_000)
        except Exception as exc:
            return IndexBuildResult(ok=False, errors=[f"rebuild_index failed: {exc}"])

    def _do_build(self, force_rebuild: bool, limit: int) -> IndexBuildResult:
        from src.runtime.assets.semantic import get_asset_catalog
        t0 = time.perf_counter()
        catalog = get_asset_catalog()
        store   = get_asset_vector_store()
        builder = get_asset_embedding_builder()

        result = IndexBuildResult(
            strategy="rebuild" if force_rebuild else "incremental",
        )
        count = 0

        for entry in catalog.iter_all():
            if count >= limit:
                break
            if not force_rebuild and store.contains(entry.asset_id):
                result.skipped += 1
                continue
            embedded = builder.build_embedding(entry.to_dict())
            if embedded.vector:
                ok = store.add_vector(embedded.asset_id, embedded.vector)
                if ok:
                    result.indexed += 1
                else:
                    result.errors.append(f"Failed to store vector for {entry.asset_id}")
            else:
                result.skipped += 1
            count += 1

        result.duration_ms = round((time.perf_counter() - t0) * 1000, 2)

        with self._lock:
            self._build_count += 1
            self._last_built = time.time()

        return result

    def update_asset_index(self, asset_id: str) -> bool:
        """Update embedding for a single asset. Returns True on success. Never raises."""
        try:
            from src.runtime.assets.semantic import get_asset_catalog
            catalog = get_asset_catalog()
            entry = catalog.get_asset(asset_id)
            if not entry:
                return False
            embedded = get_asset_embedding_builder().build_embedding(entry.to_dict())
            if not embedded.vector:
                return False
            return get_asset_vector_store().update_vector(embedded.asset_id, embedded.vector)
        except Exception:
            return False

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "build_count": self._build_count,
                "last_built":  self._last_built,
                "store_size":  get_asset_vector_store().size(),
            }


_INSTANCE: Optional[CatalogVectorIndexBuilder] = None
_INSTANCE_LOCK = threading.Lock()


def get_catalog_vector_index_builder() -> CatalogVectorIndexBuilder:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = CatalogVectorIndexBuilder()
    return _INSTANCE


def reset_catalog_vector_index_builder_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
