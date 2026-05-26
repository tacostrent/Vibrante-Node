"""
Knowledge Graph (Tier 4)
=========================
Runtime-oriented semantic relationship tracking for production assets,
shots, workflows, and DCC sessions.

This is NOT a database replacement.  It is a lightweight in-memory graph
of production entities and their relationships, enabling the orchestration
layer to answer questions like:
  "Which shots depend on this asset?"
  "What workflows produced this render?"
  "Which DCC sessions are involved in this sequence?"

Entity types:   asset, shot, sequence, worker, dcc_session, workflow, render
Relationship types: depends_on, created_by, rendered_in, submitted_to,
                    part_of, executed_by, produces, references

Public API:
    get_knowledge_graph() -> KnowledgeGraph   (singleton)
    reset_knowledge_graph_for_tests()

    KnowledgeGraph.add_entity(entity_type, entity_id, properties) -> str
    KnowledgeGraph.get_entity(entity_id) -> dict | None
    KnowledgeGraph.remove_entity(entity_id) -> bool
    KnowledgeGraph.add_relationship(source_id, target_id, rel_type, properties) -> str
    KnowledgeGraph.remove_relationship(rel_id) -> bool
    KnowledgeGraph.query_related(entity_id, rel_type, direction) -> list[dict]
    KnowledgeGraph.find_path(source_id, target_id, max_depth) -> list[str]
    KnowledgeGraph.all_entities() -> list[dict]
    KnowledgeGraph.all_relationships() -> list[dict]
    KnowledgeGraph.stats() -> dict
    KnowledgeGraph.clear()
"""

import json
import os
import threading
import time
import uuid
from collections import deque
from typing import Any, Dict, List, Optional

ENTITY_TYPES = frozenset({
    "asset", "shot", "sequence", "worker", "dcc_session",
    "workflow", "render", "custom",
})

RELATIONSHIP_TYPES = frozenset({
    "depends_on", "created_by", "rendered_in", "submitted_to",
    "part_of", "executed_by", "produces", "references", "custom",
})


class KnowledgeGraph:
    """In-memory semantic knowledge graph with optional JSONL persistence."""

    def __init__(self, path: Optional[str] = None) -> None:
        self._path        = path
        self._lock        = threading.Lock()
        self._entities:   Dict[str, Dict[str, Any]] = {}
        self._rels:       Dict[str, Dict[str, Any]] = {}
        # Adjacency: entity_id → {rel_id, ...}
        self._outbound:   Dict[str, set] = {}
        self._inbound:    Dict[str, set] = {}

    # ------------------------------------------------------------------
    # Entity management
    # ------------------------------------------------------------------

    def add_entity(
        self,
        entity_type: str,
        entity_id:   str,
        properties:  Optional[Dict[str, Any]] = None,
    ) -> str:
        """Add or update an entity.  Returns entity_id."""
        if not entity_id:
            raise ValueError("entity_id must be non-empty")
        if entity_type not in ENTITY_TYPES:
            raise ValueError(f"Unknown entity_type: {entity_type!r}")
        with self._lock:
            existing = self._entities.get(entity_id)
            self._entities[entity_id] = {
                "id":         entity_id,
                "type":       entity_type,
                "properties": dict(properties or {}),
                "created_at": existing["created_at"] if existing else time.time(),
                "updated_at": time.time(),
            }
            self._outbound.setdefault(entity_id, set())
            self._inbound.setdefault(entity_id, set())
        return entity_id

    def get_entity(self, entity_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            e = self._entities.get(entity_id)
            return dict(e) if e else None

    def remove_entity(self, entity_id: str) -> bool:
        """Remove an entity and all incident relationships."""
        with self._lock:
            if entity_id not in self._entities:
                return False
            # Collect incident rel_ids
            incident = set(self._outbound.get(entity_id, set()))
            incident |= set(self._inbound.get(entity_id, set()))
            for rel_id in incident:
                rel = self._rels.pop(rel_id, None)
                if rel:
                    self._outbound.get(rel["source_id"], set()).discard(rel_id)
                    self._inbound.get(rel["target_id"], set()).discard(rel_id)
            self._outbound.pop(entity_id, None)
            self._inbound.pop(entity_id, None)
            del self._entities[entity_id]
        return True

    # ------------------------------------------------------------------
    # Relationship management
    # ------------------------------------------------------------------

    def add_relationship(
        self,
        source_id:   str,
        target_id:   str,
        rel_type:    str,
        properties:  Optional[Dict[str, Any]] = None,
    ) -> str:
        """Add a directed relationship (source → target).  Returns rel_id."""
        if source_id == target_id:
            raise ValueError("Self-relationships are not allowed")
        if rel_type not in RELATIONSHIP_TYPES:
            raise ValueError(f"Unknown relationship type: {rel_type!r}")
        if not source_id or not target_id:
            raise ValueError("source_id and target_id must be non-empty")
        rel_id = str(uuid.uuid4())
        with self._lock:
            # Auto-create entity stubs if they don't exist
            for eid in (source_id, target_id):
                if eid not in self._entities:
                    self._entities[eid] = {
                        "id": eid, "type": "custom",
                        "properties": {}, "created_at": time.time(), "updated_at": time.time(),
                    }
                    self._outbound[eid] = set()
                    self._inbound[eid]  = set()
            self._rels[rel_id] = {
                "id":         rel_id,
                "source_id":  source_id,
                "target_id":  target_id,
                "type":       rel_type,
                "properties": dict(properties or {}),
                "created_at": time.time(),
            }
            self._outbound[source_id].add(rel_id)
            self._inbound[target_id].add(rel_id)
        return rel_id

    def remove_relationship(self, rel_id: str) -> bool:
        with self._lock:
            rel = self._rels.pop(rel_id, None)
            if rel is None:
                return False
            self._outbound.get(rel["source_id"], set()).discard(rel_id)
            self._inbound.get(rel["target_id"], set()).discard(rel_id)
        return True

    def get_relationship(self, rel_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            r = self._rels.get(rel_id)
            return dict(r) if r else None

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def query_related(
        self,
        entity_id: str,
        rel_type:  Optional[str] = None,
        direction: str = "outbound",
    ) -> List[Dict[str, Any]]:
        """Return entities related to entity_id.

        Args:
            rel_type:  Filter by relationship type, or None for all.
            direction: "outbound" (entity is source), "inbound" (entity is target),
                       "both".
        """
        with self._lock:
            rel_ids: set = set()
            if direction in ("outbound", "both"):
                rel_ids |= set(self._outbound.get(entity_id, set()))
            if direction in ("inbound", "both"):
                rel_ids |= set(self._inbound.get(entity_id, set()))

            results = []
            for rid in rel_ids:
                rel = self._rels.get(rid)
                if rel is None:
                    continue
                if rel_type and rel["type"] != rel_type:
                    continue
                # Identify the "other" end
                other_id = rel["target_id"] if rel["source_id"] == entity_id else rel["source_id"]
                other    = self._entities.get(other_id)
                if other:
                    results.append({
                        "entity":       dict(other),
                        "relationship": dict(rel),
                    })
        return sorted(results, key=lambda r: r["relationship"]["created_at"])

    def find_path(
        self,
        source_id: str,
        target_id: str,
        max_depth: int = 6,
    ) -> List[str]:
        """BFS shortest path between source and target (outbound edges only).

        Returns list of entity_ids from source to target (inclusive),
        or [] if no path found.
        """
        if source_id == target_id:
            return [source_id]
        with self._lock:
            outbound_copy = {k: set(v) for k, v in self._outbound.items()}
            rels_copy     = {k: dict(v) for k, v in self._rels.items()}

        queue:   deque = deque([[source_id]])
        visited: set   = {source_id}

        while queue:
            path = queue.popleft()
            if len(path) - 1 >= max_depth:
                continue
            current = path[-1]
            for rid in outbound_copy.get(current, set()):
                rel     = rels_copy.get(rid)
                if rel is None:
                    continue
                neighbor = rel["target_id"]
                if neighbor in visited:
                    continue
                new_path = path + [neighbor]
                if neighbor == target_id:
                    return new_path
                visited.add(neighbor)
                queue.append(new_path)
        return []

    def all_entities(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [dict(e) for e in self._entities.values()]

    def all_relationships(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [dict(r) for r in self._rels.values()]

    # ------------------------------------------------------------------
    # Stats / clear
    # ------------------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            by_entity: Dict[str, int] = {}
            for e in self._entities.values():
                t = e["type"]
                by_entity[t] = by_entity.get(t, 0) + 1
            by_rel: Dict[str, int] = {}
            for r in self._rels.values():
                t = r["type"]
                by_rel[t] = by_rel.get(t, 0) + 1
            return {
                "entity_count":       len(self._entities),
                "relationship_count": len(self._rels),
                "by_entity_type":     by_entity,
                "by_rel_type":        by_rel,
            }

    def clear(self) -> None:
        with self._lock:
            self._entities.clear()
            self._rels.clear()
            self._outbound.clear()
            self._inbound.clear()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[KnowledgeGraph] = None
_LOCK = threading.Lock()
_PATH_ENV = "VIBRANTE_KNOWLEDGE_GRAPH_PATH"


def get_knowledge_graph() -> KnowledgeGraph:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            path = os.environ.get(_PATH_ENV)
            _INSTANCE = KnowledgeGraph(path=path or None)
        return _INSTANCE


def reset_knowledge_graph_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
