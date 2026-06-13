"""
Asset Knowledge Graph (Tier 12.7)
====================================
Manages semantic relationships between catalog assets.

Relationship types:
  commonly_used_with, same_environment, same_style, same_template, successful_pairing

Design rules:
  - No DCC calls, no network calls
  - Thread-safe
  - Deterministic — same inputs always produce same graph
  - build_graph() auto-derives relationships from enriched catalog entries
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

RELATIONSHIP_TYPES: frozenset = frozenset({
    "commonly_used_with",
    "same_environment",
    "same_style",
    "same_template",
    "successful_pairing",
})

# (source_id, relation_type, target_id) → KnowledgeRelationship
_RelKey = Tuple[str, str, str]


@dataclass
class KnowledgeRelationship:
    source_id:  str = ""
    relation:   str = ""
    target_id:  str = ""
    weight:     float = 1.0
    metadata:   Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": str(self.source_id),
            "relation":  str(self.relation),
            "target_id": str(self.target_id),
            "weight":    float(self.weight),
            "metadata":  dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "KnowledgeRelationship":
        d = d if isinstance(d, dict) else {}
        return cls(
            source_id=str(d.get("source_id", "")),
            relation=str(d.get("relation", "")),
            target_id=str(d.get("target_id", "")),
            weight=float(d.get("weight", 1.0)),
            metadata=dict(d.get("metadata") or {}),
        )


class AssetKnowledgeGraph:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._rels: Dict[_RelKey, KnowledgeRelationship] = {}

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add_relationship(
        self,
        source_id: str,
        relation: str,
        target_id: str,
        weight: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> KnowledgeRelationship:
        """Add or update a relationship. Never raises."""
        try:
            source_id = str(source_id).strip()
            target_id = str(target_id).strip()
            relation = str(relation).strip()
            if not (source_id and target_id and relation):
                return KnowledgeRelationship()
            rel = KnowledgeRelationship(
                source_id=source_id,
                relation=relation,
                target_id=target_id,
                weight=float(weight),
                metadata=dict(metadata or {}),
            )
            key: _RelKey = (source_id, relation, target_id)
            with self._lock:
                self._rels[key] = rel
            return rel
        except Exception:
            return KnowledgeRelationship()

    def remove_relationship(
        self,
        source_id: str,
        relation: str,
        target_id: str,
    ) -> bool:
        """Remove a relationship. Returns True if found and removed."""
        try:
            key: _RelKey = (str(source_id), str(relation), str(target_id))
            with self._lock:
                if key in self._rels:
                    del self._rels[key]
                    return True
            return False
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def query_relationships(
        self,
        asset_id: str,
        relation_type: Optional[str] = None,
    ) -> List[KnowledgeRelationship]:
        """Return all relationships for an asset, optionally filtered by type."""
        try:
            asset_id = str(asset_id).strip()
            with self._lock:
                rels = list(self._rels.values())
            result = [
                r for r in rels
                if r.source_id == asset_id or r.target_id == asset_id
            ]
            if relation_type:
                result = [r for r in result if r.relation == str(relation_type)]
            return sorted(result, key=lambda r: (r.source_id, r.relation, r.target_id))
        except Exception:
            return []

    def get_neighbors(
        self,
        asset_id: str,
        relation_type: Optional[str] = None,
        direction: str = "both",
    ) -> List[str]:
        """Return IDs of assets connected to asset_id.

        direction: "outgoing" (source=asset_id), "incoming" (target=asset_id), "both"
        """
        try:
            asset_id = str(asset_id).strip()
            with self._lock:
                rels = list(self._rels.values())
            neighbors = set()
            for r in rels:
                if relation_type and r.relation != str(relation_type):
                    continue
                if direction in ("outgoing", "both") and r.source_id == asset_id:
                    neighbors.add(r.target_id)
                if direction in ("incoming", "both") and r.target_id == asset_id:
                    neighbors.add(r.source_id)
            return sorted(neighbors)
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Auto-build from catalog entries
    # ------------------------------------------------------------------

    def build_graph(self, enriched_assets: List[Dict[str, Any]]) -> int:
        """Auto-derive relationships from a list of enriched asset dicts.

        Returns the number of new relationships added. Never raises.
        """
        try:
            return self._do_build(enriched_assets)
        except Exception:
            return 0

    def _do_build(self, assets: List[Dict[str, Any]]) -> int:
        added = 0
        # Group by primary_env and primary_lookdev
        env_groups: Dict[str, List[str]] = {}
        style_groups: Dict[str, List[str]] = {}

        for asset in assets:
            if not isinstance(asset, dict):
                continue
            aid = str(asset.get("asset_id", "")).strip()
            if not aid:
                continue
            env = str(asset.get("primary_env", "")).strip()
            if env:
                env_groups.setdefault(env, []).append(aid)
            lookdev = str(asset.get("primary_lookdev", "")).strip()
            if lookdev:
                style_groups.setdefault(lookdev, []).append(aid)

        for env, ids in env_groups.items():
            for i, a in enumerate(ids):
                for b in ids[i + 1:]:
                    existing = self.add_relationship(
                        a, "same_environment", b,
                        weight=0.8,
                        metadata={"environment": env},
                    )
                    if existing.source_id:
                        added += 1

        for style, ids in style_groups.items():
            for i, a in enumerate(ids):
                for b in ids[i + 1:]:
                    existing = self.add_relationship(
                        a, "same_style", b,
                        weight=0.7,
                        metadata={"style": style},
                    )
                    if existing.source_id:
                        added += 1

        return added

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._rels)
            by_type: Dict[str, int] = {}
            for r in self._rels.values():
                by_type[r.relation] = by_type.get(r.relation, 0) + 1
            return {"total_relationships": total, "by_type": by_type}

    def clear(self) -> None:
        with self._lock:
            self._rels.clear()


_INSTANCE: Optional[AssetKnowledgeGraph] = None
_INSTANCE_LOCK = threading.Lock()


def get_asset_knowledge_graph() -> AssetKnowledgeGraph:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = AssetKnowledgeGraph()
    return _INSTANCE


def reset_asset_knowledge_graph_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
