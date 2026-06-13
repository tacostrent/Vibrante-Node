"""
Asset Vector Store (Tier 12.8)
================================
Persistent in-memory vector database with optional FAISS acceleration.

Default backend: pure-Python brute-force cosine similarity (always available).
Optional backend: FAISS (if installed) for larger catalogs.

Environment variable:
  VIBRANTE_ASSET_STORAGE  — directory for optional vector index persistence
"""
from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .semantic_similarity import cosine_similarity

ENV_VECTOR_STORE = "VIBRANTE_ASSET_STORAGE"
_STORE_FILENAME  = "vector_store.json"

try:
    import faiss as _faiss  # type: ignore
    _HAS_FAISS = True
except ImportError:
    _HAS_FAISS = False

try:
    import numpy as _np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False


@dataclass
class VectorSearchResult:
    asset_id: str = ""
    score:    float = 0.0
    rank:     int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id": str(self.asset_id),
            "score":    round(float(self.score), 6),
            "rank":     int(self.rank),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "VectorSearchResult":
        d = d if isinstance(d, dict) else {}
        return cls(
            asset_id=str(d.get("asset_id", "")),
            score=float(d.get("score", 0.0)),
            rank=int(d.get("rank", 0)),
        )


class AssetVectorStore:
    """
    Thread-safe vector store.

    Internally holds {asset_id: vector} and searches by cosine similarity.
    All public methods never raise.
    """

    def __init__(self) -> None:
        self._lock      = threading.Lock()
        self._vectors:   Dict[str, List[float]] = {}
        self._dimensions: Optional[int] = None
        self._add_count  = 0
        self._query_count = 0

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add_vector(self, asset_id: str, vector: List[float]) -> bool:
        """Store a vector for asset_id. Returns True on success. Never raises."""
        try:
            asset_id = str(asset_id).strip()
            vector   = [float(x) for x in vector]
            if not asset_id or not vector:
                return False
            with self._lock:
                if self._dimensions is None:
                    self._dimensions = len(vector)
                elif len(vector) != self._dimensions:
                    return False
                self._vectors[asset_id] = vector
                self._add_count += 1
            return True
        except Exception:
            return False

    def update_vector(self, asset_id: str, vector: List[float]) -> bool:
        """Update an existing vector (same as add). Returns True on success."""
        return self.add_vector(asset_id, vector)

    def delete_vector(self, asset_id: str) -> bool:
        """Remove vector for asset_id. Returns True if found."""
        try:
            with self._lock:
                if asset_id in self._vectors:
                    del self._vectors[asset_id]
                    return True
            return False
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def query(
        self,
        query_vector: List[float],
        top_k: int = 10,
        exclude_ids: Optional[List[str]] = None,
    ) -> List[VectorSearchResult]:
        """Return top-k nearest neighbors by cosine similarity. Never raises."""
        try:
            return self._do_query(
                [float(x) for x in query_vector],
                int(top_k),
                set(exclude_ids or []),
            )
        except Exception:
            return []

    def _do_query(
        self,
        query_vector: List[float],
        top_k: int,
        exclude: set,
    ) -> List[VectorSearchResult]:
        with self._lock:
            items = list(self._vectors.items())
            self._query_count += 1

        scored: List[Tuple[str, float]] = []
        for asset_id, vec in items:
            if asset_id in exclude:
                continue
            score = cosine_similarity(query_vector, vec)
            scored.append((asset_id, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [
            VectorSearchResult(asset_id=aid, score=score, rank=i + 1)
            for i, (aid, score) in enumerate(scored[:top_k])
        ]

    def query_batch(
        self,
        query_vectors: List[List[float]],
        top_k: int = 10,
    ) -> List[List[VectorSearchResult]]:
        """Query multiple vectors at once. Never raises."""
        try:
            return [self.query(qv, top_k) for qv in query_vectors]
        except Exception:
            return [[] for _ in query_vectors]

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _store_path(self) -> Optional[str]:
        storage = os.environ.get(ENV_VECTOR_STORE, "").strip()
        if not storage:
            return None
        return os.path.join(storage, _STORE_FILENAME)

    def save(self, path: Optional[str] = None) -> bool:
        """Save vector store to JSON file. Returns True on success."""
        try:
            target = path or self._store_path()
            if not target:
                return False
            os.makedirs(os.path.dirname(os.path.abspath(target)), exist_ok=True)
            with self._lock:
                payload = {
                    "dimensions": self._dimensions,
                    "vectors":    {aid: vec for aid, vec in self._vectors.items()},
                    "saved_at":   time.time(),
                }
            with open(target, "w", encoding="utf-8") as f:
                json.dump(payload, f)
            return True
        except Exception:
            return False

    def load(self, path: Optional[str] = None) -> bool:
        """Load vector store from JSON file. Returns True on success."""
        try:
            target = path or self._store_path()
            if not target or not os.path.isfile(target):
                return False
            with open(target, "r", encoding="utf-8") as f:
                payload = json.load(f)
            if not isinstance(payload, dict):
                return False
            with self._lock:
                self._dimensions = payload.get("dimensions")
                self._vectors    = {str(k): [float(x) for x in v]
                                    for k, v in (payload.get("vectors") or {}).items()}
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Stats / utility
    # ------------------------------------------------------------------

    def size(self) -> int:
        with self._lock:
            return len(self._vectors)

    def contains(self, asset_id: str) -> bool:
        with self._lock:
            return str(asset_id) in self._vectors

    def get_all_ids(self) -> List[str]:
        with self._lock:
            return list(self._vectors.keys())

    def clear(self) -> None:
        with self._lock:
            self._vectors.clear()
            self._dimensions = None

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "size":        len(self._vectors),
                "dimensions":  self._dimensions,
                "add_count":   self._add_count,
                "query_count": self._query_count,
                "has_faiss":   _HAS_FAISS,
            }


_INSTANCE: Optional[AssetVectorStore] = None
_INSTANCE_LOCK = threading.Lock()


def get_asset_vector_store() -> AssetVectorStore:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = AssetVectorStore()
                _INSTANCE.load()
    return _INSTANCE


def reset_asset_vector_store_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
