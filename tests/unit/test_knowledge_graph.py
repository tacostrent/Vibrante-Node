"""
Unit tests for src.runtime.knowledge_graph.

Covers:
  • add_entity / get_entity / remove_entity
  • add_entity unknown type raises
  • add_entity empty id raises
  • add_entity idempotent update (created_at preserved)
  • add_relationship / remove_relationship / get_relationship
  • add_relationship self-relationship raises
  • add_relationship unknown rel_type raises
  • add_relationship auto-creates entity stubs
  • remove_entity cascades to incident relationships
  • query_related outbound / inbound / both
  • query_related rel_type filter
  • find_path BFS direct / multi-hop / no path / self / cycle-safe
  • all_entities / all_relationships
  • stats shape
  • clear
  • singleton / reset
"""

from __future__ import annotations

import pytest

from src.runtime.knowledge_graph import (
    KnowledgeGraph,
    get_knowledge_graph,
    reset_knowledge_graph_for_tests,
    ENTITY_TYPES,
    RELATIONSHIP_TYPES,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_knowledge_graph_for_tests()
    yield
    reset_knowledge_graph_for_tests()


# ---------------------------------------------------------------------------
# Entity management
# ---------------------------------------------------------------------------

def test_add_entity_returns_id():
    kg = get_knowledge_graph()
    eid = kg.add_entity("asset", "asset_01")
    assert eid == "asset_01"


def test_add_entity_get_entity():
    kg = get_knowledge_graph()
    kg.add_entity("asset", "asset_01", {"project": "hero"})
    e = kg.get_entity("asset_01")
    assert e is not None
    assert e["id"] == "asset_01"
    assert e["type"] == "asset"
    assert e["properties"]["project"] == "hero"


def test_add_entity_unknown_type_raises():
    kg = get_knowledge_graph()
    with pytest.raises(ValueError, match="Unknown entity_type"):
        kg.add_entity("planet", "p1")


def test_add_entity_empty_id_raises():
    kg = get_knowledge_graph()
    with pytest.raises(ValueError):
        kg.add_entity("asset", "")


def test_add_entity_update_preserves_created_at():
    kg = get_knowledge_graph()
    kg.add_entity("asset", "a1", {"v": 1})
    original = kg.get_entity("a1")["created_at"]
    kg.add_entity("asset", "a1", {"v": 2})
    updated = kg.get_entity("a1")
    assert updated["created_at"] == original
    assert updated["properties"]["v"] == 2


def test_get_entity_unknown_returns_none():
    kg = get_knowledge_graph()
    assert kg.get_entity("missing") is None


def test_remove_entity_true():
    kg = get_knowledge_graph()
    kg.add_entity("asset", "a1")
    assert kg.remove_entity("a1") is True
    assert kg.get_entity("a1") is None


def test_remove_entity_unknown_false():
    kg = get_knowledge_graph()
    assert kg.remove_entity("not_there") is False


def test_remove_entity_cascades_relationships():
    kg = get_knowledge_graph()
    kg.add_entity("asset", "a1")
    kg.add_entity("shot", "s1")
    rid = kg.add_relationship("a1", "s1", "depends_on")
    kg.remove_entity("a1")
    assert kg.get_relationship(rid) is None
    # s1 should still exist
    assert kg.get_entity("s1") is not None


# ---------------------------------------------------------------------------
# Relationship management
# ---------------------------------------------------------------------------

def test_add_relationship_returns_uuid():
    kg = get_knowledge_graph()
    kg.add_entity("asset", "a1")
    kg.add_entity("shot", "s1")
    rid = kg.add_relationship("a1", "s1", "depends_on")
    assert isinstance(rid, str) and len(rid) == 36


def test_add_relationship_get_relationship():
    kg = get_knowledge_graph()
    kg.add_entity("asset", "a1")
    kg.add_entity("shot", "s1")
    rid = kg.add_relationship("a1", "s1", "references", {"weight": 1})
    r = kg.get_relationship(rid)
    assert r is not None
    assert r["source_id"] == "a1"
    assert r["target_id"] == "s1"
    assert r["type"] == "references"
    assert r["properties"]["weight"] == 1


def test_add_relationship_self_raises():
    kg = get_knowledge_graph()
    kg.add_entity("asset", "a1")
    with pytest.raises(ValueError, match="Self-relationship"):
        kg.add_relationship("a1", "a1", "depends_on")


def test_add_relationship_unknown_type_raises():
    kg = get_knowledge_graph()
    kg.add_entity("asset", "a1")
    kg.add_entity("shot", "s1")
    with pytest.raises(ValueError, match="Unknown relationship type"):
        kg.add_relationship("a1", "s1", "invented_type")


def test_add_relationship_auto_creates_stubs():
    kg = get_knowledge_graph()
    # Neither entity pre-registered
    rid = kg.add_relationship("x1", "x2", "custom")
    assert kg.get_entity("x1") is not None
    assert kg.get_entity("x2") is not None
    assert kg.get_relationship(rid) is not None


def test_remove_relationship_true():
    kg = get_knowledge_graph()
    kg.add_entity("asset", "a1")
    kg.add_entity("shot",  "s1")
    rid = kg.add_relationship("a1", "s1", "depends_on")
    assert kg.remove_relationship(rid) is True
    assert kg.get_relationship(rid) is None


def test_remove_relationship_unknown_false():
    kg = get_knowledge_graph()
    assert kg.remove_relationship("00000000-0000-0000-0000-000000000000") is False


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------

def test_query_related_outbound():
    kg = get_knowledge_graph()
    kg.add_entity("asset", "a1")
    kg.add_entity("shot",  "s1")
    kg.add_entity("shot",  "s2")
    kg.add_relationship("a1", "s1", "depends_on")
    kg.add_relationship("a1", "s2", "depends_on")
    results = kg.query_related("a1", direction="outbound")
    ids = {r["entity"]["id"] for r in results}
    assert "s1" in ids and "s2" in ids


def test_query_related_inbound():
    kg = get_knowledge_graph()
    kg.add_entity("asset",   "a1")
    kg.add_entity("asset",   "a2")
    kg.add_entity("shot",    "s1")
    kg.add_relationship("a1", "s1", "depends_on")
    kg.add_relationship("a2", "s1", "depends_on")
    results = kg.query_related("s1", direction="inbound")
    ids = {r["entity"]["id"] for r in results}
    assert "a1" in ids and "a2" in ids


def test_query_related_both():
    kg = get_knowledge_graph()
    kg.add_entity("asset", "a1")
    kg.add_entity("shot",  "s1")
    kg.add_entity("render","r1")
    kg.add_relationship("a1", "s1", "depends_on")
    kg.add_relationship("s1", "r1", "rendered_in")
    results = kg.query_related("s1", direction="both")
    ids = {r["entity"]["id"] for r in results}
    assert "a1" in ids and "r1" in ids


def test_query_related_rel_type_filter():
    kg = get_knowledge_graph()
    kg.add_entity("asset", "a1")
    kg.add_entity("shot",  "s1")
    kg.add_entity("render","r1")
    kg.add_relationship("a1", "s1", "depends_on")
    kg.add_relationship("a1", "r1", "produces")
    results = kg.query_related("a1", rel_type="depends_on")
    assert len(results) == 1
    assert results[0]["entity"]["id"] == "s1"


def test_query_related_empty_entity():
    kg = get_knowledge_graph()
    kg.add_entity("asset", "lonely")
    results = kg.query_related("lonely")
    assert results == []


# ---------------------------------------------------------------------------
# find_path
# ---------------------------------------------------------------------------

def test_find_path_self():
    kg = get_knowledge_graph()
    kg.add_entity("asset", "a1")
    path = kg.find_path("a1", "a1")
    assert path == ["a1"]


def test_find_path_direct():
    kg = get_knowledge_graph()
    kg.add_entity("asset", "a1")
    kg.add_entity("shot",  "s1")
    kg.add_relationship("a1", "s1", "depends_on")
    path = kg.find_path("a1", "s1")
    assert path == ["a1", "s1"]


def test_find_path_multi_hop():
    kg = get_knowledge_graph()
    for eid in ["a", "b", "c", "d"]:
        kg.add_entity("custom", eid)
    kg.add_relationship("a", "b", "custom")
    kg.add_relationship("b", "c", "custom")
    kg.add_relationship("c", "d", "custom")
    path = kg.find_path("a", "d")
    assert path == ["a", "b", "c", "d"]


def test_find_path_no_path():
    kg = get_knowledge_graph()
    kg.add_entity("asset", "a1")
    kg.add_entity("shot",  "s1")
    # No relationship
    assert kg.find_path("a1", "s1") == []


def test_find_path_max_depth():
    kg = get_knowledge_graph()
    # Chain of length 10
    for i in range(10):
        kg.add_entity("custom", str(i))
    for i in range(9):
        kg.add_relationship(str(i), str(i + 1), "custom")
    # max_depth=3 should not find path of length 9
    path = kg.find_path("0", "9", max_depth=3)
    assert path == []


# ---------------------------------------------------------------------------
# All entities / relationships
# ---------------------------------------------------------------------------

def test_all_entities():
    kg = get_knowledge_graph()
    kg.add_entity("asset", "a1")
    kg.add_entity("shot",  "s1")
    entities = kg.all_entities()
    ids = {e["id"] for e in entities}
    assert "a1" in ids and "s1" in ids


def test_all_relationships():
    kg = get_knowledge_graph()
    kg.add_entity("asset", "a1")
    kg.add_entity("shot",  "s1")
    rid = kg.add_relationship("a1", "s1", "depends_on")
    rels = kg.all_relationships()
    assert any(r["id"] == rid for r in rels)


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def test_stats_shape():
    kg = get_knowledge_graph()
    kg.add_entity("asset", "a1")
    kg.add_entity("shot",  "s1")
    kg.add_relationship("a1", "s1", "depends_on")
    s = kg.stats()
    assert "entity_count"       in s
    assert "relationship_count" in s
    assert "by_entity_type"     in s
    assert "by_rel_type"        in s
    assert s["entity_count"]       >= 2
    assert s["relationship_count"] >= 1


def test_stats_by_type():
    kg = get_knowledge_graph()
    kg.add_entity("asset", "a1")
    kg.add_entity("asset", "a2")
    kg.add_entity("shot",  "s1")
    s = kg.stats()
    assert s["by_entity_type"].get("asset", 0) == 2
    assert s["by_entity_type"].get("shot", 0)  == 1


# ---------------------------------------------------------------------------
# Clear
# ---------------------------------------------------------------------------

def test_clear():
    kg = get_knowledge_graph()
    kg.add_entity("asset", "a1")
    kg.add_entity("shot",  "s1")
    kg.add_relationship("a1", "s1", "depends_on")
    kg.clear()
    assert kg.stats()["entity_count"]       == 0
    assert kg.stats()["relationship_count"] == 0
    assert kg.all_entities()               == []


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton_same_instance():
    a = get_knowledge_graph()
    b = get_knowledge_graph()
    assert a is b


def test_reset_creates_fresh_instance():
    a = get_knowledge_graph()
    reset_knowledge_graph_for_tests()
    b = get_knowledge_graph()
    assert a is not b
