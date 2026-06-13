"""Tests for §46 AssetRelationshipGraph."""

import pytest
from src.runtime.layout import (
    AssetRelationship,
    AssetRelationshipGraph,
    RELATIONSHIP_TYPES,
    get_relationship_graph,
    reset_relationship_graph_for_tests,
)


@pytest.fixture(autouse=True)
def reset():
    reset_relationship_graph_for_tests()
    yield
    reset_relationship_graph_for_tests()


def test_all_relationship_types_accepted():
    graph = get_relationship_graph()
    for rt in RELATIONSHIP_TYPES:
        graph.add_relationship(AssetRelationship("a", "b", rt))
    assert graph.total_relationships == len(RELATIONSHIP_TYPES)


def test_unknown_type_normalised_to_near():
    graph = get_relationship_graph()
    graph.add_relationship(AssetRelationship("x", "y", "floats"))
    rels = graph.all_relationships()
    assert rels[0].relationship_type == "near"


def test_get_relationships_returns_outgoing():
    graph = get_relationship_graph()
    graph.add_relationship(AssetRelationship("bottle", "table", "supports"))
    graph.add_relationship(AssetRelationship("chair", "table", "around"))
    rels = graph.get_relationships("bottle")
    assert len(rels) == 1
    assert rels[0].relationship_type == "supports"


def test_get_parents():
    graph = get_relationship_graph()
    graph.add_relationship(AssetRelationship("bottle", "table", "supports"))
    assert "table" in graph.get_parents("bottle")


def test_get_dependents():
    graph = get_relationship_graph()
    graph.add_relationship(AssetRelationship("bottle", "table", "supports"))
    graph.add_relationship(AssetRelationship("chair", "table", "around"))
    deps = graph.get_dependents("table")
    assert "bottle" in deps
    assert "chair" in deps


def test_get_by_type():
    graph = get_relationship_graph()
    graph.add_relationship(AssetRelationship("a", "b", "supports"))
    graph.add_relationship(AssetRelationship("c", "d", "around"))
    graph.add_relationship(AssetRelationship("e", "f", "supports"))
    supports = graph.get_by_type("supports")
    assert len(supports) == 2
    arounds = graph.get_by_type("around")
    assert len(arounds) == 1


def test_clear():
    graph = get_relationship_graph()
    graph.add_relationship(AssetRelationship("a", "b", "near"))
    graph.clear()
    assert graph.total_relationships == 0


def test_to_dict():
    graph = get_relationship_graph()
    graph.add_relationship(AssetRelationship("poster", "wall", "attached_to"))
    d = graph.to_dict()
    assert "relationships" in d
    assert d["asset_count"] == 1


def test_from_dict_roundtrip():
    rel = AssetRelationship("lantern", "ceiling", "hanging_from", {"height": 2.5})
    d = rel.to_dict()
    rel2 = AssetRelationship.from_dict(d)
    assert rel2.from_asset_id == "lantern"
    assert rel2.to_asset_id == "ceiling"
    assert rel2.relationship_type == "hanging_from"
    assert rel2.metadata["height"] == 2.5


def test_singleton_reset():
    g1 = get_relationship_graph()
    g1.add_relationship(AssetRelationship("a", "b", "near"))
    reset_relationship_graph_for_tests()
    g2 = get_relationship_graph()
    assert g2.total_relationships == 0
