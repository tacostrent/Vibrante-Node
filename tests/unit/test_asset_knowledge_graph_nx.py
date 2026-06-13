"""
Tests for the NetworkX + SQLite upgrade of AssetKnowledgeGraph.
Covers: internal engine, SQLite schema, graph reconstruction, persistence,
        remove_relationship, relationship queries, and statistics accuracy.

No bridge, no LLM. Pure unit tests.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading

import networkx as nx
import pytest

from src.runtime.asset_knowledge_graph import (
    AssetKnowledgeGraph,
    _SEED_SCENE_ASSETS,
    _VALID_REL_TYPES,
    get_asset_knowledge_graph,
    reset_asset_knowledge_graph_for_tests,
)


@pytest.fixture(autouse=True)
def reset_singleton():
    reset_asset_knowledge_graph_for_tests()
    yield
    reset_asset_knowledge_graph_for_tests()


@pytest.fixture()
def db_path(tmp_path):
    return str(tmp_path / "graph.db")


@pytest.fixture()
def fresh(db_path):
    """A fresh AssetKnowledgeGraph backed by SQLite."""
    return AssetKnowledgeGraph(db_path=db_path)


@pytest.fixture()
def inmem():
    """A fresh AssetKnowledgeGraph with no SQLite (in-memory only)."""
    return AssetKnowledgeGraph()


# ---------------------------------------------------------------------------
# Internal engine — NetworkX
# ---------------------------------------------------------------------------

class TestNetworkXEngine:

    def test_internal_graph_is_multidi(self, inmem):
        assert isinstance(inmem._graph, nx.MultiDiGraph)

    def test_internal_graph_is_multidi_with_sqlite(self, fresh):
        assert isinstance(fresh._graph, nx.MultiDiGraph)

    def test_nodes_use_graph_attributes(self, inmem):
        inmem.add_asset("robot", "character", {"style": "sci_fi"})
        data = inmem._graph.nodes["robot"]
        assert data["asset_type"] == "character"
        assert data["metadata"]["style"] == "sci_fi"
        assert "usage_count" in data
        assert "scene_types" in data

    def test_edges_carry_rel_type_and_weight(self, inmem):
        inmem.add_asset("a", "prop")
        inmem.add_asset("b", "prop")
        inmem.add_relationship("a", "b", "commonly_used_with", weight=2.5)
        edge_attrs = list(inmem._graph["a"]["b"].values())
        assert any(
            e["rel_type"] == "commonly_used_with" and e["weight"] == pytest.approx(2.5)
            for e in edge_attrs
        )

    def test_bidirectional_stored_as_two_directed_edges(self, inmem):
        inmem.add_relationship("x", "y", "same_style")
        assert inmem._graph.has_edge("x", "y")
        assert inmem._graph.has_edge("y", "x")

    def test_no_pickle_in_db(self, fresh, db_path):
        """SQLite rows must contain readable text, never pickled bytes."""
        fresh.add_asset("check_me", "prop", {"key": "val"})
        conn = sqlite3.connect(db_path)
        rows = conn.execute("SELECT metadata FROM asset_nodes WHERE asset_id='check_me'").fetchall()
        conn.close()
        assert rows
        # Metadata is stored as a plain JSON string
        parsed = json.loads(rows[0][0])
        assert parsed["key"] == "val"

    def test_scene_types_stored_as_json_array(self, fresh, db_path):
        """scene_types column must be a JSON array string, not a pickled object."""
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT scene_types FROM asset_nodes WHERE asset_id='industrial_pipe'"
        ).fetchone()
        conn.close()
        assert row is not None
        parsed = json.loads(row[0])
        assert isinstance(parsed, list)
        assert "industrial_hangar" in parsed


# ---------------------------------------------------------------------------
# SQLite schema
# ---------------------------------------------------------------------------

class TestSQLiteSchema:

    def test_tables_created_on_open(self, db_path):
        AssetKnowledgeGraph(db_path=db_path)
        conn = sqlite3.connect(db_path)
        tables = {
            r[0] for r in
            conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        conn.close()
        assert {"asset_nodes", "asset_relationships"}.issubset(tables)

    def test_indexes_created(self, db_path):
        AssetKnowledgeGraph(db_path=db_path)
        conn = sqlite3.connect(db_path)
        indexes = {
            r[0] for r in
            conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()
        }
        conn.close()
        assert "idx_arel_src" in indexes
        assert "idx_arel_dst" in indexes

    def test_wal_mode_enabled(self, db_path):
        AssetKnowledgeGraph(db_path=db_path)
        conn = sqlite3.connect(db_path)
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        conn.close()
        assert mode == "wal"

    def test_asset_nodes_columns(self, db_path):
        AssetKnowledgeGraph(db_path=db_path)
        conn = sqlite3.connect(db_path)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(asset_nodes)").fetchall()}
        conn.close()
        assert {"asset_id", "asset_type", "metadata", "usage_count", "scene_types"}.issubset(cols)

    def test_asset_relationships_columns(self, db_path):
        AssetKnowledgeGraph(db_path=db_path)
        conn = sqlite3.connect(db_path)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(asset_relationships)").fetchall()}
        conn.close()
        assert {"asset1_id", "asset2_id", "rel_type", "weight"}.issubset(cols)


# ---------------------------------------------------------------------------
# Graph reconstruction
# ---------------------------------------------------------------------------

class TestGraphReconstruction:

    def test_seed_data_written_to_sqlite(self, db_path):
        AssetKnowledgeGraph(db_path=db_path)
        conn = sqlite3.connect(db_path)
        count = conn.execute("SELECT COUNT(*) FROM asset_nodes").fetchone()[0]
        conn.close()
        assert count > 0

    def test_second_instance_loads_seed_from_sqlite(self, db_path):
        AssetKnowledgeGraph(db_path=db_path)          # writes seed
        g2 = AssetKnowledgeGraph(db_path=db_path)     # reads seed
        assert g2.graph_statistics()["node_count"] > 0

    def test_reconstructed_nodes_match_original(self, db_path):
        g1 = AssetKnowledgeGraph(db_path=db_path)
        g1.add_asset("custom_robot", "character", {"studio": "test"})
        g1.add_relationship("custom_robot", "industrial_pipe", "commonly_used_with", weight=3.0)

        g2 = AssetKnowledgeGraph(db_path=db_path)
        usage = g2.get_asset_usage("custom_robot")
        assert usage["found"] is True
        assert usage["asset_type"] == "character"

    def test_reconstructed_edges_match_original(self, db_path):
        g1 = AssetKnowledgeGraph(db_path=db_path)
        g1.add_asset("src", "prop")
        g1.add_asset("dst", "prop")
        g1.add_relationship("src", "dst", "successful_pairing", weight=4.2)

        g2 = AssetKnowledgeGraph(db_path=db_path)
        related = g2.find_related_assets("src", rel_type="successful_pairing")
        assert len(related) == 1
        assert related[0]["asset_id"] == "dst"
        assert related[0]["weight"] == pytest.approx(4.2)

    def test_bidirectional_edges_reconstructed(self, db_path):
        g1 = AssetKnowledgeGraph(db_path=db_path)
        g1.add_asset("p", "prop")
        g1.add_asset("q", "prop")
        g1.add_relationship("p", "q", "same_style")

        g2 = AssetKnowledgeGraph(db_path=db_path)
        assert g2._graph.has_edge("p", "q")
        assert g2._graph.has_edge("q", "p")

    def test_scene_types_reconstructed(self, db_path):
        AssetKnowledgeGraph(db_path=db_path)           # seeds
        g2 = AssetKnowledgeGraph(db_path=db_path)
        assets = g2.find_scene_assets("industrial_hangar")
        assert "industrial_pipe" in assets

    def test_usage_count_reconstructed(self, db_path):
        g1 = AssetKnowledgeGraph(db_path=db_path)
        g1.add_asset("track_me", "prop")
        g1.record_asset_usage("track_me")
        g1.record_asset_usage("track_me")

        g2 = AssetKnowledgeGraph(db_path=db_path)
        assert g2.get_asset_usage("track_me")["usage_count"] == 2

    def test_second_open_does_not_reseed(self, db_path):
        """If DB already has data, seed must not run again on second open."""
        g1 = AssetKnowledgeGraph(db_path=db_path)
        n1 = g1.graph_statistics()["node_count"]

        g2 = AssetKnowledgeGraph(db_path=db_path)
        n2 = g2.graph_statistics()["node_count"]
        assert n2 == n1   # seed did not double the node count

    def test_removed_asset_not_reconstructed(self, db_path):
        g1 = AssetKnowledgeGraph(db_path=db_path)
        g1.add_asset("temp_asset", "prop")
        g1.remove_asset("temp_asset")

        g2 = AssetKnowledgeGraph(db_path=db_path)
        assert g2.get_asset_usage("temp_asset")["found"] is False


# ---------------------------------------------------------------------------
# Persistence — individual operations
# ---------------------------------------------------------------------------

class TestPersistence:

    def test_add_asset_written_to_sqlite(self, db_path):
        g = AssetKnowledgeGraph(db_path=db_path)
        g.add_asset("persist_me", "character", {"x": 1})
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT asset_type, metadata FROM asset_nodes WHERE asset_id='persist_me'"
        ).fetchone()
        conn.close()
        assert row is not None
        assert row[0] == "character"
        assert json.loads(row[1])["x"] == 1

    def test_add_relationship_written_both_directions(self, db_path):
        g = AssetKnowledgeGraph(db_path=db_path)
        g.add_asset("a", "prop")
        g.add_asset("b", "prop")
        g.add_relationship("a", "b", "same_template", weight=2.0)
        conn = sqlite3.connect(db_path)
        rows = conn.execute(
            "SELECT asset1_id, asset2_id, weight FROM asset_relationships "
            "WHERE rel_type='same_template' ORDER BY asset1_id"
        ).fetchall()
        conn.close()
        pairs = {(r[0], r[1]) for r in rows}
        assert ("a", "b") in pairs
        assert ("b", "a") in pairs
        assert all(r[2] == pytest.approx(2.0) for r in rows)

    def test_remove_asset_deletes_from_sqlite(self, db_path):
        g = AssetKnowledgeGraph(db_path=db_path)
        g.add_asset("del_me", "prop")
        g.remove_asset("del_me")
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT 1 FROM asset_nodes WHERE asset_id='del_me'"
        ).fetchone()
        conn.close()
        assert row is None

    def test_remove_asset_deletes_edges_from_sqlite(self, db_path):
        g = AssetKnowledgeGraph(db_path=db_path)
        g.add_asset("hub", "prop")
        g.add_asset("spoke", "prop")
        g.add_relationship("hub", "spoke", "commonly_used_with")
        g.remove_asset("hub")
        conn = sqlite3.connect(db_path)
        rows = conn.execute(
            "SELECT 1 FROM asset_relationships WHERE asset1_id='hub' OR asset2_id='hub'"
        ).fetchall()
        conn.close()
        assert rows == []

    def test_usage_count_written_to_sqlite(self, db_path):
        g = AssetKnowledgeGraph(db_path=db_path)
        g.add_asset("counted", "prop")
        g.record_asset_usage("counted")
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT usage_count FROM asset_nodes WHERE asset_id='counted'"
        ).fetchone()
        conn.close()
        assert row[0] == 1

    def test_weight_update_persisted(self, db_path):
        g = AssetKnowledgeGraph(db_path=db_path)
        g.add_asset("m", "prop")
        g.add_asset("n", "prop")
        g.add_relationship("m", "n", "same_style", weight=1.0)
        g.add_relationship("m", "n", "same_style", weight=5.0)  # update weight
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT weight FROM asset_relationships "
            "WHERE asset1_id='m' AND asset2_id='n' AND rel_type='same_style'"
        ).fetchone()
        conn.close()
        assert row[0] == pytest.approx(5.0)

    def test_no_pickle_bytes_in_metadata_column(self, db_path):
        g = AssetKnowledgeGraph(db_path=db_path)
        g.add_asset("clean", "prop", {"nested": {"a": [1, 2, 3]}})
        conn = sqlite3.connect(db_path)
        raw = conn.execute(
            "SELECT metadata FROM asset_nodes WHERE asset_id='clean'"
        ).fetchone()[0]
        conn.close()
        # Must be a valid UTF-8 JSON string, never pickle bytes
        parsed = json.loads(raw)
        assert parsed["nested"]["a"] == [1, 2, 3]


# ---------------------------------------------------------------------------
# remove_relationship (new method)
# ---------------------------------------------------------------------------

class TestRemoveRelationship:

    def test_removes_both_directions(self, inmem):
        inmem.add_asset("p", "prop")
        inmem.add_asset("q", "prop")
        inmem.add_relationship("p", "q", "commonly_used_with")
        inmem.remove_relationship("p", "q", "commonly_used_with")
        assert "q" not in [r["asset_id"] for r in inmem.find_related_assets("p")]
        assert "p" not in [r["asset_id"] for r in inmem.find_related_assets("q")]

    def test_leaves_other_rel_types_intact(self, inmem):
        inmem.add_asset("a", "prop")
        inmem.add_asset("b", "prop")
        inmem.add_relationship("a", "b", "commonly_used_with")
        inmem.add_relationship("a", "b", "same_style")
        inmem.remove_relationship("a", "b", "commonly_used_with")
        remaining = inmem.find_related_assets("a")
        rel_types = {r["rel_type"] for r in remaining if r["asset_id"] == "b"}
        assert "same_style" in rel_types
        assert "commonly_used_with" not in rel_types

    def test_noop_on_nonexistent_relationship(self, inmem):
        inmem.add_asset("x", "prop")
        inmem.add_asset("y", "prop")
        inmem.remove_relationship("x", "y", "same_style")  # no edge exists — no raise

    def test_assets_still_exist_after_remove_relationship(self, inmem):
        inmem.add_asset("c", "prop")
        inmem.add_asset("d", "prop")
        inmem.add_relationship("c", "d", "same_template")
        inmem.remove_relationship("c", "d", "same_template")
        assert inmem.get_asset_usage("c")["found"] is True
        assert inmem.get_asset_usage("d")["found"] is True

    def test_remove_relationship_persisted_to_sqlite(self, db_path):
        g = AssetKnowledgeGraph(db_path=db_path)
        g.add_asset("s1", "prop")
        g.add_asset("s2", "prop")
        g.add_relationship("s1", "s2", "successful_pairing")
        g.remove_relationship("s1", "s2", "successful_pairing")
        conn = sqlite3.connect(db_path)
        rows = conn.execute(
            "SELECT 1 FROM asset_relationships "
            "WHERE rel_type='successful_pairing' "
            "AND ((asset1_id='s1' AND asset2_id='s2') OR (asset1_id='s2' AND asset2_id='s1'))"
        ).fetchall()
        conn.close()
        assert rows == []

    def test_remove_relationship_survives_reconstruction(self, db_path):
        g1 = AssetKnowledgeGraph(db_path=db_path)
        g1.add_asset("r1", "prop")
        g1.add_asset("r2", "prop")
        g1.add_relationship("r1", "r2", "commonly_used_with")
        g1.remove_relationship("r1", "r2", "commonly_used_with")

        g2 = AssetKnowledgeGraph(db_path=db_path)
        related = g2.find_related_assets("r1", rel_type="commonly_used_with")
        assert not any(r["asset_id"] == "r2" for r in related)

    def test_edge_count_decreases_after_remove_relationship(self, inmem):
        inmem.add_asset("u", "prop")
        inmem.add_asset("v", "prop")
        inmem.add_relationship("u", "v", "same_style")
        before = inmem.graph_statistics()["edge_count"]
        inmem.remove_relationship("u", "v", "same_style")
        after = inmem.graph_statistics()["edge_count"]
        assert after == before - 1


# ---------------------------------------------------------------------------
# Relationship queries (NetworkX-backed)
# ---------------------------------------------------------------------------

class TestRelationshipQueries:

    def test_find_related_returns_correct_rel_type_in_result(self, inmem):
        inmem.add_asset("h", "prop")
        inmem.add_asset("i", "prop")
        inmem.add_relationship("h", "i", "same_environment")
        related = inmem.find_related_assets("h")
        assert any(r["rel_type"] == "same_environment" for r in related)

    def test_find_related_multiple_rel_types_to_same_asset(self, inmem):
        inmem.add_asset("m", "prop")
        inmem.add_asset("n", "prop")
        inmem.add_relationship("m", "n", "commonly_used_with", weight=2.0)
        inmem.add_relationship("m", "n", "same_style",        weight=1.0)
        related = inmem.find_related_assets("m")
        n_entries = [r for r in related if r["asset_id"] == "n"]
        rel_types = {e["rel_type"] for e in n_entries}
        assert "commonly_used_with" in rel_types
        assert "same_style"        in rel_types

    def test_find_related_filter_returns_only_matching_type(self, inmem):
        inmem.add_asset("f1", "prop")
        inmem.add_asset("f2", "prop")
        inmem.add_asset("f3", "prop")
        inmem.add_relationship("f1", "f2", "commonly_used_with")
        inmem.add_relationship("f1", "f3", "same_style")
        results = inmem.find_related_assets("f1", rel_type="commonly_used_with")
        assert all(r["rel_type"] == "commonly_used_with" for r in results)
        assert all(r["asset_id"] != "f3" for r in results)

    def test_find_related_weight_sorted_descending(self, inmem):
        inmem.add_asset("root", "prop")
        for i, w in enumerate([1.0, 5.0, 3.0]):
            inmem.add_asset(f"leaf_{i}", "prop")
            inmem.add_relationship("root", f"leaf_{i}", "commonly_used_with", weight=w)
        related = inmem.find_related_assets("root")
        weights = [r["weight"] for r in related]
        assert weights == sorted(weights, reverse=True)

    def test_find_scene_assets_with_multiple_scene_membership(self, inmem):
        """An asset that belongs to two scenes should appear in both."""
        inmem.add_asset("multi", "prop")
        inmem._graph.nodes["multi"]["scene_types"] = ["hangar", "lab"]
        assert "multi" in inmem.find_scene_assets("hangar")
        assert "multi" in inmem.find_scene_assets("lab")

    def test_get_asset_usage_counts_only_outgoing_edges(self, inmem):
        """relationship_count reflects out-edges only (matching original behavior)."""
        inmem.add_asset("hub", "prop")
        inmem.add_asset("sp1", "prop")
        inmem.add_asset("sp2", "prop")
        inmem.add_relationship("hub", "sp1", "commonly_used_with")
        inmem.add_relationship("hub", "sp2", "commonly_used_with")
        usage = inmem.get_asset_usage("hub")
        assert usage["relationship_count"] == 2

    def test_all_valid_rel_types_queryable(self, inmem):
        for rt in _VALID_REL_TYPES:
            inmem.add_relationship(f"src_{rt}", f"dst_{rt}", rt)
        for rt in _VALID_REL_TYPES:
            related = inmem.find_related_assets(f"src_{rt}", rel_type=rt)
            assert len(related) == 1
            assert related[0]["rel_type"] == rt


# ---------------------------------------------------------------------------
# Statistics accuracy
# ---------------------------------------------------------------------------

class TestStatisticsAccuracy:

    def test_node_count_after_add_and_remove(self, inmem):
        before = inmem.graph_statistics()["node_count"]
        inmem.add_asset("extra", "prop")
        assert inmem.graph_statistics()["node_count"] == before + 1
        inmem.remove_asset("extra")
        assert inmem.graph_statistics()["node_count"] == before

    def test_edge_count_after_add_relationship(self, inmem):
        before = inmem.graph_statistics()["edge_count"]
        inmem.add_asset("p", "prop")
        inmem.add_asset("q", "prop")
        inmem.add_relationship("p", "q", "same_style")
        assert inmem.graph_statistics()["edge_count"] == before + 1

    def test_edge_count_after_remove_asset(self, inmem):
        inmem.add_asset("hub", "prop")
        for i in range(3):
            inmem.add_asset(f"s{i}", "prop")
            inmem.add_relationship("hub", f"s{i}", "commonly_used_with")
        before = inmem.graph_statistics()["edge_count"]
        inmem.remove_asset("hub")
        after = inmem.graph_statistics()["edge_count"]
        assert after == before - 3

    def test_edges_by_rel_type_counts(self, inmem):
        inmem.add_asset("a", "prop")
        inmem.add_asset("b", "prop")
        inmem.add_asset("c", "prop")
        inmem.add_relationship("a", "b", "same_style")
        inmem.add_relationship("a", "c", "same_style")
        stats = inmem.graph_statistics()
        # Seed may have some same_environment; we just check same_style delta is 2
        assert stats["edges_by_rel_type"].get("same_style", 0) >= 2

    def test_scene_types_indexed_covers_seed(self, inmem):
        stats = inmem.graph_statistics()
        assert stats["scene_types_indexed"] >= len(_SEED_SCENE_ASSETS)

    def test_assets_by_type_reflects_all_assets(self, fresh):
        fresh.add_asset("char1", "character")
        fresh.add_asset("char2", "character")
        fresh.add_asset("veh1", "vehicle")
        stats = fresh.graph_statistics()
        assert stats["assets_by_type"].get("character", 0) >= 2
        assert stats["assets_by_type"].get("vehicle", 0) >= 1

    def test_statistics_consistent_after_reconstruction(self, db_path):
        g1 = AssetKnowledgeGraph(db_path=db_path)
        g1.add_asset("extra1", "prop")
        g1.add_asset("extra2", "prop")
        g1.add_relationship("extra1", "extra2", "commonly_used_with")
        s1 = g1.graph_statistics()

        g2 = AssetKnowledgeGraph(db_path=db_path)
        s2 = g2.graph_statistics()

        assert s2["node_count"]  == s1["node_count"]
        assert s2["edge_count"]  == s1["edge_count"]
        assert s2["scene_types_indexed"] == s1["scene_types_indexed"]


# ---------------------------------------------------------------------------
# Thread safety (SQLite + NetworkX under concurrent access)
# ---------------------------------------------------------------------------

class TestThreadSafety:

    def test_concurrent_add_asset_all_land(self, db_path):
        g = AssetKnowledgeGraph(db_path=db_path)
        errors: list = []
        N = 50

        def worker(i):
            try:
                g.add_asset(f"thread_asset_{i}", "prop")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(N)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        stats = g.graph_statistics()
        # All N assets plus the seed data
        assert stats["node_count"] >= N

    def test_concurrent_reads_do_not_raise(self, fresh):
        errors: list = []

        def reader():
            try:
                for _ in range(20):
                    fresh.find_related_assets("industrial_pipe")
                    fresh.graph_statistics()
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=reader) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
