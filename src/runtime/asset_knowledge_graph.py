"""
Asset Knowledge Graph (Tier 5 — Production Knowledge System)
=============================================================
In-memory semantic graph of asset relationships, backed internally by
``networkx.MultiDiGraph`` and optionally persisted to SQLite.

Internal engine: networkx.MultiDiGraph
  - Nodes carry asset metadata as attributes (asset_type, metadata,
    usage_count, scene_types).
  - Edges carry rel_type and weight as attributes.
  - Bidirectional relationships are stored as two directed edges
    (A→B and B→A) so that out_edges queries work naturally.

Persistence (when db_path is provided):
  - ``asset_nodes``         — one row per asset node
  - ``asset_relationships`` — one row per directed edge (both directions stored)
  - Graph is rebuilt from SQLite on construction.
  - Seed data is written to SQLite on first use (empty DB).
  - Graph objects are NEVER pickled — all data is stored as SQL columns or JSON.

Relationship types:
    commonly_used_with   — assets frequently appear together
    same_environment     — both belong to the same environment type
    same_style           — matching aesthetic/visual style
    same_template        — used together in the same scene template
    successful_pairing   — historically successful combination

Public API:
    AssetKnowledgeGraph(db_path=None)
        .add_asset(asset_id, asset_type, metadata=None) -> None
        .remove_asset(asset_id) -> None
        .add_relationship(asset1_id, asset2_id, rel_type, weight=1.0) -> None
        .remove_relationship(asset1_id, asset2_id, rel_type) -> None
        .find_related_assets(asset_id, rel_type=None, limit=10) -> list
        .find_scene_assets(scene_type) -> list
        .get_asset_usage(asset_id) -> dict
        .record_asset_usage(asset_id) -> None
        .graph_statistics() -> dict
        .stats() -> dict

    get_asset_knowledge_graph() -> AssetKnowledgeGraph   (singleton)
    reset_asset_knowledge_graph_for_tests()
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from typing import Any, Dict, List, Optional

import networkx as nx

# ---------------------------------------------------------------------------
# Module-level constants (exported; tests import them)
# ---------------------------------------------------------------------------

_VALID_REL_TYPES = frozenset({
    "commonly_used_with",
    "same_environment",
    "same_style",
    "same_template",
    "successful_pairing",
})

_SEED_SCENE_ASSETS: Dict[str, List[str]] = {
    "industrial_hangar":      ["industrial_pipe", "maintenance_robot", "storage_crate", "metal_platform"],
    "robotics_lab":           ["maintenance_robot", "workbench", "tool_rack", "circuit_panel"],
    "sci_fi_corridor":        ["corridor_panel", "neon_sign", "tech_console", "wire_conduit"],
    "cinematic_control_room": ["control_console", "monitor_bank", "operator_chair", "alert_panel"],
    "abandoned_factory":      ["rusted_beam", "debris_pile", "broken_conveyor", "dust_particle"],
}

# ---------------------------------------------------------------------------
# SQLite DDL
# ---------------------------------------------------------------------------

_DDL = """
CREATE TABLE IF NOT EXISTS asset_nodes (
    asset_id    TEXT    PRIMARY KEY,
    asset_type  TEXT    NOT NULL DEFAULT 'unknown',
    metadata    TEXT    NOT NULL DEFAULT '{}',
    usage_count INTEGER NOT NULL DEFAULT 0,
    scene_types TEXT    NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS asset_relationships (
    asset1_id TEXT NOT NULL,
    asset2_id TEXT NOT NULL,
    rel_type  TEXT NOT NULL,
    weight    REAL NOT NULL DEFAULT 1.0,
    PRIMARY KEY (asset1_id, asset2_id, rel_type)
);

CREATE INDEX IF NOT EXISTS idx_arel_src ON asset_relationships (asset1_id);
CREATE INDEX IF NOT EXISTS idx_arel_dst ON asset_relationships (asset2_id);
"""


class AssetKnowledgeGraph:
    """Semantic asset relationship graph backed by networkx.MultiDiGraph.

    Optionally persisted to SQLite when *db_path* is provided.
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        self._lock    = threading.Lock()
        self._graph   = nx.MultiDiGraph()
        self._db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None

        if db_path is not None:
            self._db_open()
            self._load_from_db()

        if self._graph.number_of_nodes() == 0:
            # First startup (empty DB or no-persistence mode): seed built-ins
            self._seed_built_ins()
            if db_path is not None:
                self._db_persist_all()

    # ------------------------------------------------------------------
    # SQLite lifecycle
    # ------------------------------------------------------------------

    def _db_open(self) -> None:
        """Open (or create) the SQLite database and initialise the schema."""
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.executescript(_DDL)
        conn.commit()
        self._conn = conn

    def _load_from_db(self) -> None:
        """Rebuild the in-memory graph from SQLite rows. Called during __init__."""
        if not self._conn:
            return
        for row in self._conn.execute(
            "SELECT asset_id, asset_type, metadata, usage_count, scene_types "
            "FROM asset_nodes"
        ):
            asset_id, asset_type, meta_json, usage_count, scenes_json = row
            self._graph.add_node(
                asset_id,
                asset_type  = asset_type,
                metadata    = json.loads(meta_json)    if meta_json    else {},
                usage_count = usage_count,
                scene_types = json.loads(scenes_json)  if scenes_json  else [],
            )
        for row in self._conn.execute(
            "SELECT asset1_id, asset2_id, rel_type, weight FROM asset_relationships"
        ):
            a1, a2, rel_type, weight = row
            self._nx_upsert_edge(a1, a2, rel_type, weight)

    def _db_persist_all(self) -> None:
        """Batch-write the entire in-memory graph to SQLite (used after seeding)."""
        if not self._conn:
            return
        conn = self._conn
        conn.execute("DELETE FROM asset_nodes")
        conn.execute("DELETE FROM asset_relationships")
        for asset_id, data in self._graph.nodes(data=True):
            conn.execute(
                "INSERT OR REPLACE INTO asset_nodes "
                "(asset_id, asset_type, metadata, usage_count, scene_types) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    asset_id,
                    data.get("asset_type", "unknown"),
                    json.dumps(data.get("metadata", {})),
                    data.get("usage_count", 0),
                    json.dumps(data.get("scene_types", [])),
                ),
            )
        for a1, a2, attrs in self._graph.edges(data=True):
            conn.execute(
                "INSERT OR IGNORE INTO asset_relationships "
                "(asset1_id, asset2_id, rel_type, weight) VALUES (?, ?, ?, ?)",
                (a1, a2, attrs.get("rel_type", ""), attrs.get("weight", 1.0)),
            )
        conn.commit()

    def _db_upsert_node(self, asset_id: str) -> None:
        """Write (or update) one node's attributes to the DB. Must be called under lock."""
        if not self._conn:
            return
        data = self._graph.nodes[asset_id]
        self._conn.execute(
            "INSERT OR REPLACE INTO asset_nodes "
            "(asset_id, asset_type, metadata, usage_count, scene_types) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                asset_id,
                data.get("asset_type", "unknown"),
                json.dumps(data.get("metadata", {})),
                data.get("usage_count", 0),
                json.dumps(data.get("scene_types", [])),
            ),
        )
        self._conn.commit()

    def _db_upsert_edge(self, a1: str, a2: str, rel_type: str, weight: float) -> None:
        """Write (or update) one directed edge to the DB. Must be called under lock."""
        if not self._conn:
            return
        self._conn.execute(
            "INSERT OR REPLACE INTO asset_relationships "
            "(asset1_id, asset2_id, rel_type, weight) VALUES (?, ?, ?, ?)",
            (a1, a2, rel_type, weight),
        )
        self._conn.commit()

    def _db_delete_node(self, asset_id: str) -> None:
        """Delete a node and all its incident edge rows. Must be called under lock."""
        if not self._conn:
            return
        self._conn.execute(
            "DELETE FROM asset_relationships WHERE asset1_id=? OR asset2_id=?",
            (asset_id, asset_id),
        )
        self._conn.execute("DELETE FROM asset_nodes WHERE asset_id=?", (asset_id,))
        self._conn.commit()

    def _db_delete_relationship(self, a1: str, a2: str, rel_type: str) -> None:
        """Delete both directions of a typed relationship. Must be called under lock."""
        if not self._conn:
            return
        self._conn.execute(
            "DELETE FROM asset_relationships WHERE "
            "(asset1_id=? AND asset2_id=? AND rel_type=?) OR "
            "(asset1_id=? AND asset2_id=? AND rel_type=?)",
            (a1, a2, rel_type, a2, a1, rel_type),
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # NetworkX helpers (in-memory graph only)
    # ------------------------------------------------------------------

    def _nx_find_edge_key(self, a1: str, a2: str, rel_type: str) -> Optional[int]:
        """Return the MultiDiGraph edge key for an existing edge, or None."""
        if not self._graph.has_edge(a1, a2):
            return None
        for key, attrs in self._graph[a1][a2].items():
            if attrs.get("rel_type") == rel_type:
                return key
        return None

    def _nx_upsert_edge(self, a1: str, a2: str, rel_type: str, weight: float) -> None:
        """Add or update a directed edge in the in-memory graph."""
        key = self._nx_find_edge_key(a1, a2, rel_type)
        if key is not None:
            self._graph[a1][a2][key]["weight"] = weight
        else:
            self._graph.add_edge(a1, a2, rel_type=rel_type, weight=weight)

    def _nx_remove_directed_edges(self, a1: str, a2: str, rel_type: str) -> None:
        """Remove all directed edges a1→a2 with the given rel_type."""
        if not self._graph.has_edge(a1, a2):
            return
        to_remove = [
            key for key, attrs in self._graph[a1][a2].items()
            if attrs.get("rel_type") == rel_type
        ]
        for key in to_remove:
            self._graph.remove_edge(a1, a2, key)

    # ------------------------------------------------------------------
    # Seed data
    # ------------------------------------------------------------------

    def _seed_built_ins(self) -> None:
        """Pre-populate with environment-based relationships."""
        for scene_type, assets in _SEED_SCENE_ASSETS.items():
            for asset_id in assets:
                if not self._graph.has_node(asset_id):
                    self._graph.add_node(
                        asset_id,
                        asset_type  = "prop",
                        metadata    = {"source": "builtin"},
                        usage_count = 0,
                        scene_types = [scene_type],
                    )
                else:
                    existing = self._graph.nodes[asset_id].get("scene_types", [])
                    if scene_type not in existing:
                        self._graph.nodes[asset_id]["scene_types"] = existing + [scene_type]

            # Bidirectional same_environment edges among all assets in the scene
            for i, a1 in enumerate(assets):
                for a2 in assets[i + 1:]:
                    self._nx_upsert_edge(a1, a2, "same_environment", 1.0)
                    self._nx_upsert_edge(a2, a1, "same_environment", 1.0)

    # ------------------------------------------------------------------
    # Mutation — public API
    # ------------------------------------------------------------------

    def add_asset(
        self,
        asset_id: str,
        asset_type: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Register an asset. If already present, updates type and metadata."""
        with self._lock:
            if self._graph.has_node(asset_id):
                self._graph.nodes[asset_id]["asset_type"] = asset_type
                if metadata:
                    self._graph.nodes[asset_id]["metadata"].update(metadata)
            else:
                self._graph.add_node(
                    asset_id,
                    asset_type  = asset_type,
                    metadata    = dict(metadata or {}),
                    usage_count = 0,
                    scene_types = [],
                )
            self._db_upsert_node(asset_id)

    def add_relationship(
        self,
        asset1_id: str,
        asset2_id: str,
        rel_type: str,
        weight: float = 1.0,
    ) -> None:
        """Add a bidirectional relationship between two assets.

        Auto-creates asset stubs for unknown ids.

        Raises:
            ValueError: If asset1_id == asset2_id.
            ValueError: If rel_type is not in _VALID_REL_TYPES.
        """
        if asset1_id == asset2_id:
            raise ValueError(f"Self-relationship not allowed: {asset1_id!r}")
        if rel_type not in _VALID_REL_TYPES:
            raise ValueError(
                f"Invalid relationship type {rel_type!r}. "
                f"Must be one of: {sorted(_VALID_REL_TYPES)}"
            )
        w = float(weight)
        with self._lock:
            for aid in (asset1_id, asset2_id):
                if not self._graph.has_node(aid):
                    self._graph.add_node(
                        aid,
                        asset_type  = "unknown",
                        metadata    = {},
                        usage_count = 0,
                        scene_types = [],
                    )
                    self._db_upsert_node(aid)
            self._nx_upsert_edge(asset1_id, asset2_id, rel_type, w)
            self._nx_upsert_edge(asset2_id, asset1_id, rel_type, w)
            self._db_upsert_edge(asset1_id, asset2_id, rel_type, w)
            self._db_upsert_edge(asset2_id, asset1_id, rel_type, w)

    def remove_asset(self, asset_id: str) -> None:
        """Remove an asset and all its incident edges (cascade)."""
        with self._lock:
            if self._graph.has_node(asset_id):
                self._graph.remove_node(asset_id)  # NetworkX cascades edges
            self._db_delete_node(asset_id)

    def remove_relationship(
        self,
        asset1_id: str,
        asset2_id: str,
        rel_type: str,
    ) -> None:
        """Remove a specific relationship between two assets (both directions).

        No-op if the relationship does not exist.
        """
        with self._lock:
            self._nx_remove_directed_edges(asset1_id, asset2_id, rel_type)
            self._nx_remove_directed_edges(asset2_id, asset1_id, rel_type)
            self._db_delete_relationship(asset1_id, asset2_id, rel_type)

    def record_asset_usage(self, asset_id: str) -> None:
        """Increment usage counter for an asset."""
        with self._lock:
            if self._graph.has_node(asset_id):
                self._graph.nodes[asset_id]["usage_count"] = (
                    self._graph.nodes[asset_id].get("usage_count", 0) + 1
                )
                self._db_upsert_node(asset_id)

    # ------------------------------------------------------------------
    # Queries — public API
    # ------------------------------------------------------------------

    def find_related_assets(
        self,
        asset_id: str,
        rel_type: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Return assets related to asset_id, sorted by weight descending."""
        with self._lock:
            if not self._graph.has_node(asset_id):
                return []
            results = []
            for _, target, attrs in self._graph.out_edges(asset_id, data=True):
                rt = attrs.get("rel_type", "")
                if rel_type is not None and rt != rel_type:
                    continue
                target_data = self._graph.nodes.get(target, {})
                results.append({
                    "asset_id":   target,
                    "rel_type":   rt,
                    "weight":     attrs.get("weight", 1.0),
                    "asset_type": target_data.get("asset_type", "unknown"),
                })
        results.sort(key=lambda r: r["weight"], reverse=True)
        return results[:limit]

    def find_scene_assets(self, scene_type: str) -> List[str]:
        """Return asset ids that belong to the given scene type."""
        with self._lock:
            return [
                node for node, data in self._graph.nodes(data=True)
                if scene_type in data.get("scene_types", [])
            ]

    def get_asset_usage(self, asset_id: str) -> Dict[str, Any]:
        """Return usage statistics for an asset."""
        with self._lock:
            if not self._graph.has_node(asset_id):
                return {"found": False}
            data      = self._graph.nodes[asset_id]
            out_edges = list(self._graph.out_edges(asset_id, data=True))
            rel_types = list({attrs.get("rel_type", "") for _, _, attrs in out_edges})
            scenes    = list(data.get("scene_types", []))
        return {
            "found":              True,
            "asset_id":           asset_id,
            "asset_type":         data.get("asset_type", "unknown"),
            "usage_count":        data.get("usage_count", 0),
            "relationship_count": len(out_edges),
            "rel_types":          rel_types,
            "scene_types":        scenes,
        }

    def graph_statistics(self) -> Dict[str, Any]:
        """Return aggregate graph statistics."""
        with self._lock:
            node_count = self._graph.number_of_nodes()
            # Edges are stored bidirectionally — divide by 2 for unique pairs
            edge_count = self._graph.number_of_edges() // 2

            by_type: Dict[str, int] = {}
            for _, data in self._graph.nodes(data=True):
                t = data.get("asset_type", "unknown")
                by_type[t] = by_type.get(t, 0) + 1

            rel_type_counts: Dict[str, int] = {}
            for _, _, attrs in self._graph.edges(data=True):
                rt = attrs.get("rel_type", "unknown")
                rel_type_counts[rt] = rel_type_counts.get(rt, 0) + 1
            rel_type_counts = {k: v // 2 for k, v in rel_type_counts.items()}

            all_scene_types: set = set()
            for _, data in self._graph.nodes(data=True):
                all_scene_types.update(data.get("scene_types", []))

        return {
            "node_count":          node_count,
            "edge_count":          edge_count,
            "assets_by_type":      by_type,
            "edges_by_rel_type":   rel_type_counts,
            "scene_types_indexed": len(all_scene_types),
        }

    def stats(self) -> Dict[str, Any]:
        return self.graph_statistics()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[AssetKnowledgeGraph] = None
_INSTANCE_LOCK = threading.Lock()


def get_asset_knowledge_graph() -> AssetKnowledgeGraph:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                db_path = os.environ.get("VIBRANTE_ASSET_GRAPH_PATH")
                _INSTANCE = AssetKnowledgeGraph(db_path=db_path)
    return _INSTANCE


def reset_asset_knowledge_graph_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
