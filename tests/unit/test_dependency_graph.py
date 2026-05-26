"""
Unit tests for src.runtime.dependency_graph.

Covers:
  • register / remove dependency edges
  • remove_node wipes all incident edges
  • get_upstream / get_downstream type filtering
  • get_affected_nodes BFS (including multi-hop)
  • get_cook_chain aggregates connection + cook_dependency edges
  • duplicate / self-dependency edge cases
  • invalid dep_type raises ValueError
  • clear() wipes graph
  • stats() and all_edges() return correct shapes
  • get_dependency_graph() singleton
  • reset_dependency_graph_for_tests()
"""

from __future__ import annotations

import pytest

from src.runtime.dependency_graph import (
    DependencyGraph,
    DEPENDENCY_TYPES,
    get_dependency_graph,
    reset_dependency_graph_for_tests,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset():
    reset_dependency_graph_for_tests()
    yield
    reset_dependency_graph_for_tests()


# ---------------------------------------------------------------------------
# Basic edge operations
# ---------------------------------------------------------------------------

def test_register_creates_upstream_and_downstream():
    g = DependencyGraph()
    g.register_dependency("/obj/a", "/obj/b")
    up = g.get_upstream("/obj/b")
    down = g.get_downstream("/obj/a")
    assert len(up) == 1
    assert up[0] == {"source": "/obj/a", "target": "/obj/b", "type": "connection"}
    assert len(down) == 1
    assert down[0] == {"source": "/obj/a", "target": "/obj/b", "type": "connection"}


def test_register_with_explicit_dep_type():
    g = DependencyGraph()
    g.register_dependency("/obj/x", "/obj/y", dep_type="cook_dependency")
    assert g.get_upstream("/obj/y")[0]["type"] == "cook_dependency"


def test_register_is_idempotent():
    g = DependencyGraph()
    g.register_dependency("/obj/a", "/obj/b")
    g.register_dependency("/obj/a", "/obj/b")
    assert len(g.get_upstream("/obj/b")) == 1


def test_register_updates_type_on_same_pair():
    g = DependencyGraph()
    g.register_dependency("/obj/a", "/obj/b", "connection")
    g.register_dependency("/obj/a", "/obj/b", "cook_dependency")
    assert g.get_upstream("/obj/b")[0]["type"] == "cook_dependency"


def test_self_dependency_is_ignored():
    g = DependencyGraph()
    g.register_dependency("/obj/a", "/obj/a")
    assert g.get_upstream("/obj/a") == []
    assert g.get_downstream("/obj/a") == []


def test_empty_path_is_ignored():
    g = DependencyGraph()
    g.register_dependency("", "/obj/b")
    g.register_dependency("/obj/a", "")
    assert g.get_upstream("/obj/b") == []
    assert g.get_downstream("/obj/a") == []


def test_invalid_dep_type_raises():
    g = DependencyGraph()
    with pytest.raises(ValueError, match="unknown dependency type"):
        g.register_dependency("/obj/a", "/obj/b", dep_type="bad_type")


def test_remove_dependency():
    g = DependencyGraph()
    g.register_dependency("/obj/a", "/obj/b")
    g.remove_dependency("/obj/a", "/obj/b")
    assert g.get_upstream("/obj/b") == []
    assert g.get_downstream("/obj/a") == []


def test_remove_dependency_noop_if_absent():
    g = DependencyGraph()
    g.remove_dependency("/obj/a", "/obj/b")   # no crash


def test_remove_node_wipes_all_edges():
    g = DependencyGraph()
    g.register_dependency("/obj/a", "/obj/b")
    g.register_dependency("/obj/b", "/obj/c")
    g.remove_node("/obj/b")
    assert g.get_upstream("/obj/b") == []
    assert g.get_downstream("/obj/b") == []
    assert g.get_downstream("/obj/a") == []
    assert g.get_upstream("/obj/c") == []


# ---------------------------------------------------------------------------
# Filtering by dep_type
# ---------------------------------------------------------------------------

def test_get_upstream_type_filter():
    g = DependencyGraph()
    g.register_dependency("/obj/a", "/obj/c", "connection")
    g.register_dependency("/obj/b", "/obj/c", "cook_dependency")
    conn_only = g.get_upstream("/obj/c", dep_type="connection")
    cook_only = g.get_upstream("/obj/c", dep_type="cook_dependency")
    assert len(conn_only) == 1 and conn_only[0]["source"] == "/obj/a"
    assert len(cook_only) == 1 and cook_only[0]["source"] == "/obj/b"


def test_get_downstream_type_filter():
    g = DependencyGraph()
    g.register_dependency("/obj/src", "/obj/a", "connection")
    g.register_dependency("/obj/src", "/obj/b", "cook_dependency")
    conn_only = g.get_downstream("/obj/src", dep_type="connection")
    assert len(conn_only) == 1 and conn_only[0]["target"] == "/obj/a"


def test_get_upstream_no_filter_returns_all():
    g = DependencyGraph()
    g.register_dependency("/obj/a", "/obj/c", "connection")
    g.register_dependency("/obj/b", "/obj/c", "render_dependency")
    all_up = g.get_upstream("/obj/c")
    assert len(all_up) == 2


# ---------------------------------------------------------------------------
# get_affected_nodes BFS
# ---------------------------------------------------------------------------

def test_affected_nodes_direct():
    g = DependencyGraph()
    g.register_dependency("/obj/a", "/obj/b")
    affected = g.get_affected_nodes(["/obj/a"])
    assert affected == ["/obj/b"]


def test_affected_nodes_multi_hop():
    g = DependencyGraph()
    g.register_dependency("/obj/a", "/obj/b")
    g.register_dependency("/obj/b", "/obj/c")
    g.register_dependency("/obj/c", "/obj/d")
    affected = g.get_affected_nodes(["/obj/a"])
    assert "/obj/b" in affected
    assert "/obj/c" in affected
    assert "/obj/d" in affected
    assert "/obj/a" not in affected


def test_affected_nodes_type_filter():
    g = DependencyGraph()
    g.register_dependency("/obj/a", "/obj/b", "connection")
    g.register_dependency("/obj/a", "/obj/c", "cook_dependency")
    conn_only = g.get_affected_nodes(["/obj/a"], dep_type="connection")
    assert "/obj/b" in conn_only
    assert "/obj/c" not in conn_only


def test_affected_nodes_deduplication():
    g = DependencyGraph()
    # Diamond: a → b, a → c, b → d, c → d
    g.register_dependency("/obj/a", "/obj/b")
    g.register_dependency("/obj/a", "/obj/c")
    g.register_dependency("/obj/b", "/obj/d")
    g.register_dependency("/obj/c", "/obj/d")
    affected = g.get_affected_nodes(["/obj/a"])
    assert affected.count("/obj/d") == 1


def test_affected_nodes_empty_input():
    g = DependencyGraph()
    g.register_dependency("/obj/a", "/obj/b")
    assert g.get_affected_nodes([]) == []


def test_affected_nodes_no_edges():
    g = DependencyGraph()
    assert g.get_affected_nodes(["/obj/orphan"]) == []


# ---------------------------------------------------------------------------
# get_cook_chain
# ---------------------------------------------------------------------------

def test_cook_chain_aggregates_both_types():
    g = DependencyGraph()
    g.register_dependency("/obj/src", "/obj/a", "connection")
    g.register_dependency("/obj/src", "/obj/b", "cook_dependency")
    chain = g.get_cook_chain("/obj/src")
    assert "/obj/a" in chain
    assert "/obj/b" in chain


def test_cook_chain_empty_when_no_edges():
    g = DependencyGraph()
    assert g.get_cook_chain("/obj/solo") == []


# ---------------------------------------------------------------------------
# clear / stats / all_edges
# ---------------------------------------------------------------------------

def test_clear_wipes_graph():
    g = DependencyGraph()
    g.register_dependency("/obj/a", "/obj/b")
    g.clear()
    assert g.stats()["total_edges"] == 0
    assert g.get_upstream("/obj/b") == []


def test_stats_counts_correct():
    g = DependencyGraph()
    g.register_dependency("/obj/a", "/obj/b")
    g.register_dependency("/obj/a", "/obj/c")
    s = g.stats()
    assert s["total_edges"] == 2
    assert s["nodes_with_upstream"] == 2
    assert s["nodes_with_downstream"] == 1


def test_all_edges_complete():
    g = DependencyGraph()
    g.register_dependency("/obj/a", "/obj/b", "connection")
    g.register_dependency("/obj/b", "/obj/c", "cook_dependency")
    edges = g.all_edges()
    assert len(edges) == 2
    types = {e["type"] for e in edges}
    assert "connection" in types
    assert "cook_dependency" in types


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton_returns_same_instance():
    a = get_dependency_graph()
    b = get_dependency_graph()
    assert a is b


def test_reset_creates_fresh_singleton():
    a = get_dependency_graph()
    a.register_dependency("/obj/x", "/obj/y")
    reset_dependency_graph_for_tests()
    b = get_dependency_graph()
    assert a is not b
    assert b.stats()["total_edges"] == 0


# ---------------------------------------------------------------------------
# All dependency types are valid
# ---------------------------------------------------------------------------

def test_all_declared_dep_types_are_valid():
    g = DependencyGraph()
    for dep_type in DEPENDENCY_TYPES:
        g.register_dependency("/obj/a", "/obj/b", dep_type)
    # No exception raised
