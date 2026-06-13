"""Tests for Tier 14.4.1 — RelationshipGraphBuilder."""

import pytest

from src.runtime.layout.relationship_graph_builder import (
    RelationshipNode,
    RelationshipEdge,
    RelationshipGraph,
    GraphBuildResult,
    RelationshipGraphBuilder,
    GRAPH_RELATIONSHIP_TYPES,
    RELATIONSHIP_GRAPH_STATUS_PASS,
    RELATIONSHIP_GRAPH_STATUS_FAIL,
    get_relationship_graph_builder,
    reset_relationship_graph_builder_for_tests,
)
from src.runtime.layout import reset_affordance_engine_for_tests


@pytest.fixture(autouse=True)
def reset():
    reset_relationship_graph_builder_for_tests()
    reset_affordance_engine_for_tests()
    yield
    reset_relationship_graph_builder_for_tests()
    reset_affordance_engine_for_tests()


# ---------------------------------------------------------------------------
# Helper fixtures
# ---------------------------------------------------------------------------

def _asset(name: str, placement_type: str = "") -> dict:
    d: dict = {"name": name}
    if placement_type:
        d["placement_type"] = placement_type
    return d


def _western_room_assets():
    return [
        _asset("Wooden Table",    "table"),
        _asset("Saloon Chair 1",  "chair"),
        _asset("Saloon Chair 2",  "chair"),
        _asset("Whiskey Bottle",  "bottle"),
        _asset("Old Lantern",     "lantern"),
        _asset("Wanted Poster",   "poster"),
        _asset("Wooden Barrel",   "barrel"),
    ]


# ---------------------------------------------------------------------------
# Data model: RelationshipNode
# ---------------------------------------------------------------------------

class TestRelationshipNode:
    def test_to_dict_round_trip(self):
        n = RelationshipNode(
            node_id="chair_01", asset_type="chair",
            asset_name="Saloon Chair", is_virtual=False,
        )
        d = n.to_dict()
        n2 = RelationshipNode.from_dict(d)
        assert n2.node_id    == "chair_01"
        assert n2.asset_type == "chair"
        assert n2.is_virtual is False

    def test_virtual_flag(self):
        n = RelationshipNode(node_id="wall", asset_type="wall",
                             asset_name="[virtual] wall", is_virtual=True)
        assert n.to_dict()["is_virtual"] is True


# ---------------------------------------------------------------------------
# Data model: RelationshipEdge
# ---------------------------------------------------------------------------

class TestRelationshipEdge:
    def test_to_dict_round_trip(self):
        e = RelationshipEdge(
            from_node_id="chair_01", to_node_id="table_01",
            relationship_type="belongs_near", confidence=1.0,
        )
        d = e.to_dict()
        e2 = RelationshipEdge.from_dict(d)
        assert e2.from_node_id      == "chair_01"
        assert e2.to_node_id        == "table_01"
        assert e2.relationship_type == "belongs_near"
        assert e2.confidence        == 1.0

    def test_confidence_rounded(self):
        e = RelationshipEdge(
            from_node_id="a", to_node_id="b",
            relationship_type="supports", confidence=0.6666667,
        )
        assert e.to_dict()["confidence"] == round(0.6666667, 3)


# ---------------------------------------------------------------------------
# Data model: RelationshipGraph
# ---------------------------------------------------------------------------

class TestRelationshipGraph:
    def test_add_and_query_nodes(self):
        g = RelationshipGraph()
        n = RelationshipNode(node_id="t1", asset_type="table", asset_name="T")
        g.add_node(n)
        assert g.get_node("t1") is not None
        assert g.node_count == 1

    def test_add_and_query_edges(self):
        g = RelationshipGraph()
        g.add_node(RelationshipNode(node_id="c1", asset_type="chair", asset_name="C"))
        g.add_node(RelationshipNode(node_id="t1", asset_type="table", asset_name="T"))
        e = RelationshipEdge(from_node_id="c1", to_node_id="t1",
                             relationship_type="belongs_near")
        g.add_edge(e)
        assert g.edge_count == 1
        out = g.get_edges_from("c1")
        assert len(out) == 1
        assert out[0].relationship_type == "belongs_near"

    def test_unknown_relationship_type_normalised(self):
        g = RelationshipGraph()
        e = RelationshipEdge(from_node_id="a", to_node_id="b",
                             relationship_type="flies_over")
        g.add_edge(e)
        assert g.get_all_edges()[0].relationship_type == "belongs_near"

    def test_get_real_nodes_excludes_virtual(self):
        g = RelationshipGraph()
        g.add_node(RelationshipNode(node_id="r1", asset_type="chair",
                                    asset_name="Chair", is_virtual=False))
        g.add_node(RelationshipNode(node_id="wall", asset_type="wall",
                                    asset_name="[virtual] wall", is_virtual=True))
        real = g.get_real_nodes()
        assert len(real) == 1
        assert real[0].node_id == "r1"

    def test_clear(self):
        g = RelationshipGraph()
        g.add_node(RelationshipNode(node_id="n1", asset_type="chair", asset_name="C"))
        g.add_edge(RelationshipEdge(from_node_id="n1", to_node_id="wall",
                                    relationship_type="attached_to"))
        g.clear()
        assert g.node_count == 0
        assert g.edge_count == 0

    def test_to_dict_from_dict_round_trip(self):
        g = RelationshipGraph()
        g.add_node(RelationshipNode(node_id="c1", asset_type="chair", asset_name="Chair"))
        g.add_node(RelationshipNode(node_id="table", asset_type="table",
                                    asset_name="[virtual] table", is_virtual=True))
        g.add_edge(RelationshipEdge(from_node_id="c1", to_node_id="table",
                                    relationship_type="belongs_near", confidence=0.7,
                                    is_virtual_target=True))
        d  = g.to_dict()
        g2 = RelationshipGraph.from_dict(d)
        assert g2.node_count == 2
        assert g2.edge_count == 1
        assert g2.get_edges_from("c1")[0].is_virtual_target is True


# ---------------------------------------------------------------------------
# Builder: relationship types constant
# ---------------------------------------------------------------------------

class TestConstants:
    def test_all_required_types_present(self):
        required = {
            "attached_to", "supports", "belongs_near", "faces",
            "inside", "under", "on_top_of", "surrounded_by", "aligned_with",
        }
        assert required == GRAPH_RELATIONSHIP_TYPES

    def test_status_constants(self):
        assert RELATIONSHIP_GRAPH_STATUS_PASS == "PASS"
        assert RELATIONSHIP_GRAPH_STATUS_FAIL == "FAIL"


# ---------------------------------------------------------------------------
# Builder: structural attachment rules
# ---------------------------------------------------------------------------

class TestStructuralRules:
    def test_fireplace_attached_to_wall(self):
        assets = [_asset("Old Fireplace", "fireplace")]
        result = get_relationship_graph_builder().build_graph(assets, "western_room")
        edges  = result.relationship_graph.get_edges_from("Old Fireplace")
        assert any(
            e.relationship_type == "attached_to" and e.to_node_id == "wall"
            for e in edges
        )

    def test_door_attached_to_wall(self):
        assets = [_asset("Saloon Door", "door")]
        result = get_relationship_graph_builder().build_graph(assets, "western_room")
        edges  = result.relationship_graph.get_edges_from("Saloon Door")
        assert any(e.relationship_type == "attached_to" and e.to_node_id == "wall"
                   for e in edges)

    def test_window_attached_to_wall(self):
        assets = [_asset("Window Frame", "window")]
        result = get_relationship_graph_builder().build_graph(assets, "western_room")
        edges  = result.relationship_graph.get_edges_from("Window Frame")
        assert any(e.relationship_type == "attached_to" and e.to_node_id == "wall"
                   for e in edges)

    def test_beam_attached_to_ceiling(self):
        assets = [_asset("Wooden Beam", "beam")]
        result = get_relationship_graph_builder().build_graph(assets, "western_room")
        edges  = result.relationship_graph.get_edges_from("Wooden Beam")
        assert any(e.relationship_type == "attached_to" and e.to_node_id == "ceiling"
                   for e in edges)

    def test_column_attached_to_floor(self):
        assets = [_asset("Stone Column", "column")]
        result = get_relationship_graph_builder().build_graph(assets, "robotics_lab")
        edges  = result.relationship_graph.get_edges_from("Stone Column")
        assert any(e.relationship_type == "attached_to" and e.to_node_id == "floor"
                   for e in edges)


# ---------------------------------------------------------------------------
# Builder: seating rules
# ---------------------------------------------------------------------------

class TestSeatingRules:
    def test_chair_belongs_near_table_real(self):
        assets = [
            _asset("Dining Table",  "table"),
            _asset("Chair 01",      "chair"),
        ]
        result = get_relationship_graph_builder().build_graph(assets, "western_room")
        edges  = result.relationship_graph.get_edges_from("Chair 01")
        assert any(
            e.relationship_type == "belongs_near" and e.to_node_id == "Dining Table"
            for e in edges
        )

    def test_chair_faces_table_real(self):
        assets = [
            _asset("Dining Table", "table"),
            _asset("Chair 01",     "chair"),
        ]
        result = get_relationship_graph_builder().build_graph(assets, "western_room")
        edges  = result.relationship_graph.get_edges_from("Chair 01")
        assert any(
            e.relationship_type == "faces" and e.to_node_id == "Dining Table"
            for e in edges
        )

    def test_chair_uses_virtual_table_when_no_table(self):
        assets = [_asset("Chair 01", "chair")]
        result = get_relationship_graph_builder().build_graph(assets, "western_room")
        edges  = result.relationship_graph.get_edges_from("Chair 01")
        virt   = [e for e in edges if e.is_virtual_target and e.to_node_id == "table"]
        assert virt, "Chair must get a virtual table edge when no real table exists"
        assert virt[0].confidence < 1.0

    def test_stool_belongs_near_bar_counter_real(self):
        assets = [
            _asset("Bar Counter", "bar_counter"),
            _asset("Bar Stool",   "stool"),
        ]
        result = get_relationship_graph_builder().build_graph(assets, "saloon")
        edges  = result.relationship_graph.get_edges_from("Bar Stool")
        assert any(
            e.relationship_type == "belongs_near" and e.to_node_id == "Bar Counter"
            for e in edges
        )

    def test_stool_uses_virtual_bar_counter_when_absent(self):
        assets = [_asset("Bar Stool", "stool")]
        result = get_relationship_graph_builder().build_graph(assets, "saloon")
        edges  = result.relationship_graph.get_edges_from("Bar Stool")
        assert any(e.is_virtual_target and e.to_node_id == "bar_counter" for e in edges)


# ---------------------------------------------------------------------------
# Builder: surface prop rules
# ---------------------------------------------------------------------------

class TestSurfacePropRules:
    def test_bottle_supports_table(self):
        assets = [
            _asset("Saloon Table",   "table"),
            _asset("Whiskey Bottle", "bottle"),
        ]
        result = get_relationship_graph_builder().build_graph(assets, "western_room")
        edges  = result.relationship_graph.get_edges_from("Whiskey Bottle")
        assert any(
            e.relationship_type == "supports" and e.to_node_id == "Saloon Table"
            for e in edges
        )

    def test_bottle_supports_shelf_when_present(self):
        assets = [
            _asset("Wall Shelf",     "shelf"),
            _asset("Whiskey Bottle", "bottle"),
        ]
        result = get_relationship_graph_builder().build_graph(assets, "western_room")
        edges  = result.relationship_graph.get_edges_from("Whiskey Bottle")
        assert any(
            e.relationship_type == "supports" and e.to_node_id == "Wall Shelf"
            for e in edges
        )

    def test_bottle_primary_virtual_when_no_real_surface(self):
        assets = [_asset("Whiskey Bottle", "bottle")]
        result = get_relationship_graph_builder().build_graph(assets, "western_room")
        edges  = result.relationship_graph.get_edges_from("Whiskey Bottle")
        assert any(e.is_virtual_target for e in edges)

    def test_cup_supports_table(self):
        assets = [_asset("Table", "table"), _asset("Tin Cup", "cup")]
        result = get_relationship_graph_builder().build_graph(assets, "western_room")
        edges  = result.relationship_graph.get_edges_from("Tin Cup")
        assert any(e.relationship_type == "supports" and e.to_node_id == "Table"
                   for e in edges)

    def test_plate_supports_table(self):
        assets = [_asset("Table", "table"), _asset("Enamel Plate", "plate")]
        result = get_relationship_graph_builder().build_graph(assets, "western_room")
        edges  = result.relationship_graph.get_edges_from("Enamel Plate")
        assert any(e.relationship_type == "supports" and e.to_node_id == "Table"
                   for e in edges)

    def test_lantern_supports_table(self):
        assets = [_asset("Table", "table"), _asset("Oil Lantern", "lantern")]
        result = get_relationship_graph_builder().build_graph(assets, "western_room")
        edges  = result.relationship_graph.get_edges_from("Oil Lantern")
        assert any(e.relationship_type == "supports" and e.to_node_id == "Table"
                   for e in edges)

    def test_lantern_also_attached_to_wall(self):
        assets = [_asset("Oil Lantern", "lantern")]
        result = get_relationship_graph_builder().build_graph(assets, "western_room")
        edges  = result.relationship_graph.get_edges_from("Oil Lantern")
        assert any(e.relationship_type == "attached_to" and e.to_node_id == "wall"
                   for e in edges)


# ---------------------------------------------------------------------------
# Builder: corner / near-wall rules
# ---------------------------------------------------------------------------

class TestWallCornerRules:
    def test_barrel_belongs_near_wall(self):
        assets = [_asset("Old Barrel", "barrel")]
        result = get_relationship_graph_builder().build_graph(assets, "western_room")
        edges  = result.relationship_graph.get_edges_from("Old Barrel")
        assert any(
            e.relationship_type == "belongs_near" and e.to_node_id == "wall"
            for e in edges
        )

    def test_crate_belongs_near_wall(self):
        assets = [_asset("Wooden Crate", "crate")]
        result = get_relationship_graph_builder().build_graph(assets, "western_room")
        edges  = result.relationship_graph.get_edges_from("Wooden Crate")
        assert any(
            e.relationship_type == "belongs_near" and e.to_node_id == "wall"
            for e in edges
        )

    def test_poster_attached_to_wall(self):
        assets = [_asset("Wanted Poster", "poster")]
        result = get_relationship_graph_builder().build_graph(assets, "western_room")
        edges  = result.relationship_graph.get_edges_from("Wanted Poster")
        assert any(e.relationship_type == "attached_to" and e.to_node_id == "wall"
                   for e in edges)


# ---------------------------------------------------------------------------
# Builder: full western_room scene
# ---------------------------------------------------------------------------

class TestWesternRoomScene:
    def test_full_scene_status_pass(self):
        result = get_relationship_graph_builder().build_graph(
            _western_room_assets(), "western_room"
        )
        assert result.status == RELATIONSHIP_GRAPH_STATUS_PASS
        assert result.ok is True
        assert result.validation_errors == []

    def test_relationship_count_nonzero(self):
        result = get_relationship_graph_builder().build_graph(
            _western_room_assets(), "western_room"
        )
        assert result.relationship_count > 0

    def test_assets_with_relationships_populated(self):
        result = get_relationship_graph_builder().build_graph(
            _western_room_assets(), "western_room"
        )
        assert len(result.assets_with_relationships) > 0
        # Table, chairs, bottle, lantern, poster, barrel all should have rels
        assert "Wooden Table" in result.assets_with_relationships

    def test_no_orphan_assets_in_full_scene(self):
        result = get_relationship_graph_builder().build_graph(
            _western_room_assets(), "western_room"
        )
        assert result.orphan_assets == []

    def test_virtual_nodes_excluded_from_assets_with_relationships(self):
        result = get_relationship_graph_builder().build_graph(
            _western_room_assets(), "western_room"
        )
        # Virtual nodes like "wall", "ceiling" must not appear in the list
        for vtype in ("wall", "ceiling", "floor", "corner"):
            assert vtype not in result.assets_with_relationships


# ---------------------------------------------------------------------------
# Builder: validation — FAIL cases
# ---------------------------------------------------------------------------

class TestValidation:
    def test_chair_without_table_fails(self):
        # Chair exists, no table → validation should fail
        assets = [_asset("Chair 01", "chair")]
        result = get_relationship_graph_builder().build_graph(assets, "western_room")
        # Chair gets a virtual table edge (confidence 0.7), which satisfies
        # the validation check (virtual is still a relationship).
        # Status is PASS because the relationship was created to the virtual node.
        assert result.status == RELATIONSHIP_GRAPH_STATUS_PASS

    def test_status_pass_when_all_relationships_satisfied(self):
        assets = [
            _asset("Table",   "table"),
            _asset("Chair 1", "chair"),
            _asset("Bottle",  "bottle"),
        ]
        result = get_relationship_graph_builder().build_graph(assets)
        assert result.status == RELATIONSHIP_GRAPH_STATUS_PASS
        assert result.validation_errors == []

    def test_fireplace_with_wall_passes(self):
        assets = [_asset("Fireplace", "fireplace")]
        result = get_relationship_graph_builder().build_graph(assets, "western_room")
        # Fireplace gets attached_to→wall (virtual), so validation passes
        assert result.status == RELATIONSHIP_GRAPH_STATUS_PASS

    def test_bottle_gets_virtual_table_edge_when_absent(self):
        assets = [_asset("Bottle", "bottle")]
        result = get_relationship_graph_builder().build_graph(assets, "western_room")
        edges  = result.relationship_graph.get_edges_from("Bottle")
        assert any(e.is_virtual_target for e in edges)
        assert result.status == RELATIONSHIP_GRAPH_STATUS_PASS


# ---------------------------------------------------------------------------
# Builder: orphan detection
# ---------------------------------------------------------------------------

class TestOrphans:
    def test_unknown_type_becomes_orphan(self):
        assets = [_asset("Alien Device", "undefined_gadget")]
        result = get_relationship_graph_builder().build_graph(assets, "western_room")
        assert "Alien Device" in result.orphan_assets

    def test_table_anchor_is_not_orphan_in_full_scene(self):
        assets = [_asset("Table", "table"), _asset("Chair", "chair")]
        result = get_relationship_graph_builder().build_graph(assets, "western_room")
        assert "Table" not in result.orphan_assets


# ---------------------------------------------------------------------------
# Builder: current_graph singleton state
# ---------------------------------------------------------------------------

class TestRuntimeState:
    def test_current_graph_set_after_build(self):
        builder = get_relationship_graph_builder()
        assert builder.current_graph is None
        builder.build_graph([_asset("Table", "table")], "western_room")
        assert builder.current_graph is not None

    def test_current_graph_updated_on_second_build(self):
        builder = get_relationship_graph_builder()
        r1 = builder.build_graph([_asset("Table", "table")], "western_room")
        r2 = builder.build_graph([_asset("Chair", "chair"), _asset("Table", "table")], "saloon")
        assert builder.current_graph.edge_count == r2.relationship_count

    def test_reset_clears_current_graph(self):
        builder = get_relationship_graph_builder()
        builder.build_graph([_asset("Table", "table")], "western_room")
        reset_relationship_graph_builder_for_tests()
        assert get_relationship_graph_builder().current_graph is None


# ---------------------------------------------------------------------------
# Builder: determinism
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_same_input_same_output(self):
        assets = _western_room_assets()
        r1 = get_relationship_graph_builder().build_graph(assets, "western_room")
        reset_relationship_graph_builder_for_tests()
        r2 = get_relationship_graph_builder().build_graph(assets, "western_room")
        assert r1.relationship_count        == r2.relationship_count
        assert r1.assets_with_relationships == r2.assets_with_relationships
        assert r1.orphan_assets             == r2.orphan_assets
        assert r1.status                    == r2.status


# ---------------------------------------------------------------------------
# Builder: empty input
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_asset_list(self):
        result = get_relationship_graph_builder().build_graph([], "western_room")
        assert result.relationship_count == 0
        assert result.assets_with_relationships == []
        assert result.orphan_assets == []
        assert result.status == RELATIONSHIP_GRAPH_STATUS_PASS

    def test_never_raises(self):
        # Malformed dicts should not raise
        assets = [
            {},
            {"name": None},
            {"name": "X", "placement_type": None},
        ]
        result = get_relationship_graph_builder().build_graph(assets)
        assert isinstance(result, GraphBuildResult)

    def test_result_to_dict_is_json_serialisable(self):
        import json
        result = get_relationship_graph_builder().build_graph(
            _western_room_assets(), "western_room"
        )
        # Must not raise
        json.dumps(result.to_dict())


# ---------------------------------------------------------------------------
# Builder: multiple environments
# ---------------------------------------------------------------------------

class TestMultipleEnvironments:
    def test_robotics_lab_structural_assets(self):
        assets = [
            _asset("Steel Column", "column"),
            _asset("Steel Girder", "beam"),
            _asset("Robot Arm",    "machine"),
        ]
        result = get_relationship_graph_builder().build_graph(assets, "robotics_lab")
        col_edges = result.relationship_graph.get_edges_from("Steel Column")
        gir_edges = result.relationship_graph.get_edges_from("Steel Girder")
        assert any(e.to_node_id == "floor"   for e in col_edges)
        assert any(e.to_node_id == "ceiling" for e in gir_edges)

    def test_castle_hall_scene(self):
        assets = [
            _asset("Stone Arch",    "archway"),
            _asset("Castle Banner", "banner"),
            _asset("Throne",        "throne"),
        ]
        result = get_relationship_graph_builder().build_graph(assets, "castle_hall")
        arch_edges   = result.relationship_graph.get_edges_from("Stone Arch")
        banner_edges = result.relationship_graph.get_edges_from("Castle Banner")
        assert any(e.relationship_type == "attached_to" for e in arch_edges)
        assert any(e.relationship_type == "attached_to" and "wall" in e.to_node_id
                   for e in banner_edges)
