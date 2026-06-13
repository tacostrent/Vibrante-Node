"""
relationship_graph.py — §46 Semantic Furniture Layout Engine
============================================================
AssetRelationshipGraph: tracks semantic relationships between placed assets.

Supported relationship types:
  supports       — host surface holds child object (bottle ON table)
  contains       — host container holds child (shelf contains books)
  attached_to    — child is physically attached to host (poster attached_to wall)
  around         — child orbits host (chairs around table)
  near           — child is near but unattached
  against        — child sits flush against host (bench against wall)
  inside         — child is spatially inside host
  hanging_from   — child hangs from host (lantern hanging_from ceiling)
  mounted_on     — child is mounted flat on host surface (sign mounted_on wall)
  facing         — child is oriented toward host (chair facing table)

Public API:
    AssetRelationship
    AssetRelationshipGraph
    get_relationship_graph()
    reset_relationship_graph_for_tests()
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

RELATIONSHIP_TYPES = frozenset({
    "supports",
    "contains",
    "attached_to",
    "around",
    "near",
    "against",
    "inside",
    "hanging_from",
    "mounted_on",
    "facing",
})


@dataclass
class AssetRelationship:
    from_asset_id: str
    to_asset_id: str
    relationship_type: str        # one of RELATIONSHIP_TYPES
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "from_asset_id":    self.from_asset_id,
            "to_asset_id":      self.to_asset_id,
            "relationship_type": self.relationship_type,
            "metadata":         dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AssetRelationship":
        return cls(
            from_asset_id=d.get("from_asset_id", ""),
            to_asset_id=d.get("to_asset_id", ""),
            relationship_type=d.get("relationship_type", "near"),
            metadata=dict(d.get("metadata", {})),
        )


class AssetRelationshipGraph:
    """
    Directed relationship graph for placed assets.

    Edges are directed: from_asset_id → to_asset_id.
    Example: bottle "supports" → table_surface means bottle is ON table.
             chair "around" → table means chair orbits table.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._edges: Dict[str, List[AssetRelationship]] = {}
        self._reverse: Dict[str, List[str]] = {}

    def add_relationship(self, rel: AssetRelationship) -> None:
        """Add a directed relationship edge. Normalises unknown relationship types to 'near'."""
        if rel.relationship_type not in RELATIONSHIP_TYPES:
            rel = AssetRelationship(
                from_asset_id=rel.from_asset_id,
                to_asset_id=rel.to_asset_id,
                relationship_type="near",
                metadata=rel.metadata,
            )
        with self._lock:
            self._edges.setdefault(rel.from_asset_id, []).append(rel)
            self._reverse.setdefault(rel.to_asset_id, []).append(rel.from_asset_id)

    def get_relationships(self, asset_id: str) -> List[AssetRelationship]:
        """Return all outgoing relationships for asset_id."""
        with self._lock:
            return list(self._edges.get(asset_id, []))

    def get_parents(self, asset_id: str) -> List[str]:
        """Return to_asset_ids that asset_id points at."""
        with self._lock:
            return [r.to_asset_id for r in self._edges.get(asset_id, [])]

    def get_dependents(self, asset_id: str) -> List[str]:
        """Return asset_ids that have a relationship pointing TO asset_id."""
        with self._lock:
            return list(self._reverse.get(asset_id, []))

    def get_by_type(self, relationship_type: str) -> List[AssetRelationship]:
        """Return all relationships of a given type."""
        with self._lock:
            result: List[AssetRelationship] = []
            for rels in self._edges.values():
                result.extend(r for r in rels if r.relationship_type == relationship_type)
            return result

    def all_relationships(self) -> List[AssetRelationship]:
        """Return every relationship in the graph."""
        with self._lock:
            result: List[AssetRelationship] = []
            for rels in self._edges.values():
                result.extend(rels)
            return result

    def clear(self) -> None:
        with self._lock:
            self._edges.clear()
            self._reverse.clear()

    def to_dict(self) -> dict:
        return {
            "relationships": [r.to_dict() for r in self.all_relationships()],
            "asset_count":   len(self._edges),
        }

    @property
    def total_relationships(self) -> int:
        with self._lock:
            return sum(len(v) for v in self._edges.values())


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[AssetRelationshipGraph] = None
_lock = threading.Lock()


def get_relationship_graph() -> AssetRelationshipGraph:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = AssetRelationshipGraph()
    return _instance


def reset_relationship_graph_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
