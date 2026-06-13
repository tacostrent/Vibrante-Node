"""
Asset Embedding Builder (Tier 12.8)
======================================
Converts semantic catalog records into embedding vectors for vector search.

Embedding input fields (from EnrichedAsset / CatalogEntry):
  name, category, tags, semantic_tags, environments, roles,
  lookdev, storytelling, cinematic_usage
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .embedding_provider import EmbeddingVector, get_embedding_provider, _asset_to_text


@dataclass
class EmbeddedAsset:
    asset_id:  str = ""
    vector:    List[float] = field(default_factory=list)
    provider:  str = ""
    text_repr: str = ""
    dimensions: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id":   str(self.asset_id),
            "vector":     list(self.vector),
            "provider":   str(self.provider),
            "text_repr":  str(self.text_repr),
            "dimensions": int(self.dimensions),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "EmbeddedAsset":
        d = d if isinstance(d, dict) else {}
        return cls(
            asset_id=str(d.get("asset_id", "")),
            vector=list(d.get("vector") or []),
            provider=str(d.get("provider", "")),
            text_repr=str(d.get("text_repr", "")),
            dimensions=int(d.get("dimensions", 0)),
        )


class AssetEmbeddingBuilder:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._build_count = 0

    def build_embedding(self, asset_dict: Dict[str, Any]) -> EmbeddedAsset:
        """Build embedding for a single asset dict. Never raises."""
        try:
            return self._do_build(asset_dict if isinstance(asset_dict, dict) else {})
        except Exception:
            return EmbeddedAsset(asset_id=str((asset_dict or {}).get("asset_id", "")))

    def _do_build(self, asset: Dict[str, Any]) -> EmbeddedAsset:
        asset_id  = str(asset.get("asset_id", "")).strip()
        text_repr = _asset_to_text(asset)
        provider  = get_embedding_provider()
        ev:        EmbeddingVector = provider.embed_asset(asset)

        with self._lock:
            self._build_count += 1

        return EmbeddedAsset(
            asset_id=asset_id,
            vector=ev.as_list(),
            provider=ev.provider,
            text_repr=text_repr,
            dimensions=ev.dimensions,
        )

    def build_catalog_embeddings(
        self,
        assets: List[Dict[str, Any]],
    ) -> List[EmbeddedAsset]:
        """Build embeddings for a list of asset dicts. Never raises."""
        try:
            return [self.build_embedding(a) for a in assets if isinstance(a, dict)]
        except Exception:
            return []

    def update_embedding(self, asset_dict: Dict[str, Any]) -> EmbeddedAsset:
        """Alias for build_embedding (re-builds if already exists)."""
        return self.build_embedding(asset_dict)

    def rebuild_index(self, assets: List[Dict[str, Any]]) -> int:
        """Rebuild embeddings for all assets. Returns count. Never raises."""
        try:
            embeddings = self.build_catalog_embeddings(assets)
            return len(embeddings)
        except Exception:
            return 0

    def build_query_embedding(self, query_text: str) -> EmbeddingVector:
        """Build an embedding for a raw query string. Never raises."""
        try:
            return get_embedding_provider().embed_text(str(query_text))
        except Exception:
            from .embedding_provider import EmbeddingVector as EV
            return EV(vector=[], dimensions=0, provider="error")

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "build_count": self._build_count,
                "provider":    get_embedding_provider().provider_name,
                "dimensions":  get_embedding_provider().dimensions,
            }


_INSTANCE: Optional[AssetEmbeddingBuilder] = None
_INSTANCE_LOCK = threading.Lock()


def get_asset_embedding_builder() -> AssetEmbeddingBuilder:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = AssetEmbeddingBuilder()
    return _INSTANCE


def reset_asset_embedding_builder_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
