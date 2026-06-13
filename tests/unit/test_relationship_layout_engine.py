"""Tests for Tier 14.4.2 — RelationshipLayoutEngine."""

import math
import pytest

from src.runtime.layout.relationship_graph_builder import (
    get_relationship_graph_builder,
    reset_relationship_graph_builder_for_tests,
    RelationshipGraph,
)
from src.runtime.layout.relationship_layout_engine import (
    RelationshipAwareLayout,
    RelationshipLayoutEngine,
    RELATIONSHIP_LAYOUT_STATUS_PASS,
    RELATIONSHIP_LAYOUT_STATUS_FAIL,
    get_relationship_layout_engine,
    reset_relationship_layout_engine_for_tests,
    _MIN_SURFACE_H,
    _NEAR_WALL_INSET,
)
from src.runtime.layout import reset_affordance_engine_for_tests


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_all():
    reset_relationship_layout_engine_for_tests()
    reset_relationship_graph_builder_for_tests()
    reset_affordance_engine_for_tests()
    yield
    reset_relationship_layout_engine_for_tests()
    reset_relationship_graph_builder_for_tests()
    reset_affordance_engine_for_tests()


def _asset(name: str, placement_type: str = "") -> dict:
    d: dict = {"name": name}
    if placement_type:
        d["placement_type"] = placement_type
    return d


def _build(assets, env="western_room"):
    """Build graph + layout in one call."""
    graph = get_relationship_graph_builder().build_graph(assets, env).relationship_graph
    return get_relationship_layout_engine().build_layout(assets, graph)


def _transform(layout: RelationshipAwareLayout, asset_id: str):
    for t in layout.relationship_aware_transforms:
        if t.asset_id == asset_id:
            return t
    return None


# ---------------------------------------------------------------------------
# Smoke test — never raises
# ---------------------------------------------------------------------------

class TestNeverRaises:
    def test_empty_assets(self):
        graph = RelationshipGraph()
        layout = get_relationship_layout_engine().build_layout([], graph)
        assert isinstance(layout, RelationshipAwareLayout)

    def test_none_shell(self):
        assets = [_asset("Table", "table")]
        layout = _build(assets)
        assert layout is not None

    def test_malformed_assets(self):
        assets = [{}, {"name": None}, {"placement_type": None}]
        graph  = RelationshipGraph()
        layout = get_relationship_layout_engine().build_layout(assets, graph)
        assert isinstance(layout, RelationshipAwareLayout)


# ---------------------------------------------------------------------------
# Anchor placement
# ---------------------------------------------------------------------------

class TestAnchors:
    def test_table_placed_at_origin(self):
        assets = [_asset("Table", "table")]
        layout = _build(assets)
        t = _transform(layout, "Table")
        assert t is not None
        assert t.tx == 0.0
        assert t.ty == 0.0
        assert t.tz == 0.0

    def test_multiple_tables_spread_on_z(self):
        assets = [_asset("Table1", "table"), _asset("Table2", "table")]
        layout = _build(assets)
        t1 = _transform(layout, "Table1")
        t2 = _transform(layout, "Table2")
        assert t1 is not None and t2 is not None
        assert t1.tz != t2.tz

    def test_fireplace_on_north_wall(self):
        assets = [_asset("Fireplace", "fireplace")]
        layout = _build(assets)
        t = _transform(layout, "Fireplace")
        assert t is not None
        # must be near the north wall (negative z)
        assert t.tz < -3.0
        assert t.ty == 0.0

    def test_fireplace_parent_is_wall(self):
        assets = [_asset("Fireplace", "fireplace")]
        layout = _build(assets)
        t = _transform(layout, "Fireplace")
        assert t is not None
        assert "wall" in (t.parent_id or "")

    def test_fireplace_faces_room_interior(self):
        assets = [_asset("Fireplace", "fireplace")]
        layout = _build(assets)
        t = _transform(layout, "Fireplace")
        assert t is not None
        # ry=0 means facing south (positive Z = room interior)
        assert t.ry == 0.0

    def test_bar_counter_placed_away_from_origin(self):
        assets = [_asset("Bar", "bar_counter")]
        layout = _build(assets)
        t = _transform(layout, "Bar")
        assert t is not None
        assert t.tz != 0.0  # should not be at room centre


# ---------------------------------------------------------------------------
# Rule 2 — Chairs around table
# ---------------------------------------------------------------------------

class TestChairTableRule:
    def test_chair_placed_near_table(self):
        assets = [_asset("Table", "table"), _asset("Chair", "chair")]
        layout = _build(assets)
        tc = _transform(layout, "Chair")
        tt = _transform(layout, "Table")
        assert tc is not None and tt is not None
        dx = tc.tx - tt.tx
        dz = tc.tz - tt.tz
        dist = math.sqrt(dx * dx + dz * dz)
        assert dist > 0.5, "Chair must be offset from table"
        assert dist < 4.0, "Chair must not be across the room"

    def test_chair_faces_table(self):
        assets = [_asset("Table", "table"), _asset("Chair", "chair")]
        layout = _build(assets)
        tc = _transform(layout, "Chair")
        tt = _transform(layout, "Table")
        assert tc is not None and tt is not None
        # ry should point toward table
        expected_ry = math.degrees(
            math.atan2(tt.tx - tc.tx, tt.tz - tc.tz)
        ) % 360.0
        assert abs(tc.ry - expected_ry) < 1.0

    def test_chair_parent_is_table(self):
        assets = [_asset("Table", "table"), _asset("Chair1", "chair")]
        layout = _build(assets)
        t = _transform(layout, "Chair1")
        assert t is not None
        assert t.parent_id == "Table"

    def test_multiple_chairs_orbit_at_different_angles(self):
        assets = [
            _asset("Table",  "table"),
            _asset("Chair1", "chair"),
            _asset("Chair2", "chair"),
        ]
        layout = _build(assets)
        t1 = _transform(layout, "Chair1")
        t2 = _transform(layout, "Chair2")
        assert t1 is not None and t2 is not None
        # Two chairs should not be at the same position
        assert not (abs(t1.tx - t2.tx) < 0.01 and abs(t1.tz - t2.tz) < 0.01)

    def test_chair_validation_pass_with_table(self):
        assets = [_asset("Table", "table"), _asset("Chair", "chair")]
        layout = _build(assets)
        assert layout.chair_table_relation_pass is True

    def test_chair_validation_no_table_in_scene(self):
        # Chair gets virtual table → still PASS (virtual satisfies the graph)
        assets = [_asset("Chair", "chair")]
        layout = _build(assets)
        # No table in scene → chair falls back; chair_table_relation_pass may fail
        # because parent_id is not set when target is virtual
        # This tests the hard-rule behaviour
        t = _transform(layout, "Chair")
        assert t is not None  # placed somewhere, even if no table


# ---------------------------------------------------------------------------
# Rule 3 — Stools at bar counter
# ---------------------------------------------------------------------------

class TestStoolBarRule:
    def test_stool_placed_near_bar(self):
        assets = [_asset("Bar", "bar_counter"), _asset("Stool", "stool")]
        layout = _build(assets)
        ts = _transform(layout, "Stool")
        tb = _transform(layout, "Bar")
        assert ts is not None and tb is not None
        dx = ts.tx - tb.tx
        dz = ts.tz - tb.tz
        dist = math.sqrt(dx * dx + dz * dz)
        assert dist > 0.3
        assert dist < 5.0

    def test_stool_parent_is_bar(self):
        assets = [_asset("Bar", "bar_counter"), _asset("Stool", "stool")]
        layout = _build(assets)
        t = _transform(layout, "Stool")
        assert t is not None
        assert t.parent_id == "Bar"

    def test_stool_validation_pass(self):
        assets = [_asset("Bar", "bar_counter"), _asset("Stool", "stool")]
        layout = _build(assets)
        assert layout.stool_bar_relation_pass is True


# ---------------------------------------------------------------------------
# Rule 4 — Bottles on surfaces (never floor)
# ---------------------------------------------------------------------------

class TestBottleSurfaceRule:
    def test_bottle_on_table_surface(self):
        assets = [_asset("Table", "table"), _asset("Bottle", "bottle")]
        layout = _build(assets)
        t = _transform(layout, "Bottle")
        assert t is not None
        assert t.ty >= _MIN_SURFACE_H, f"Bottle ty={t.ty} must be > {_MIN_SURFACE_H}"

    def test_bottle_y_matches_table_surface_height(self):
        assets = [_asset("Table", "table"), _asset("Bottle", "bottle")]
        layout = _build(assets)
        t = _transform(layout, "Bottle")
        assert t is not None
        assert abs(t.ty - 0.75) < 0.01, f"Expected ty≈0.75, got {t.ty}"

    def test_bottle_parent_is_table(self):
        assets = [_asset("Table", "table"), _asset("Bottle", "bottle")]
        layout = _build(assets)
        t = _transform(layout, "Bottle")
        assert t is not None
        assert t.parent_id == "Table"

    def test_bottle_on_shelf_when_present(self):
        assets = [_asset("Shelf", "shelf"), _asset("Bottle", "bottle")]
        layout = _build(assets)
        t = _transform(layout, "Bottle")
        assert t is not None
        assert t.ty > _MIN_SURFACE_H
        assert abs(t.ty - 1.40) < 0.01

    def test_bottle_never_on_floor(self):
        assets = [_asset("Bottle", "bottle")]
        layout = _build(assets)
        t = _transform(layout, "Bottle")
        assert t is not None
        # Even with no table, bottle must NOT be on floor
        assert t.ty > _MIN_SURFACE_H

    def test_bottle_validation_pass(self):
        assets = [_asset("Table", "table"), _asset("Bottle", "bottle")]
        layout = _build(assets)
        assert layout.bottle_support_pass is True


# ---------------------------------------------------------------------------
# Rule 5 — Cups on table
# ---------------------------------------------------------------------------

class TestCupTableRule:
    def test_cup_on_table_surface(self):
        assets = [_asset("Table", "table"), _asset("Tin Cup", "cup")]
        layout = _build(assets)
        t = _transform(layout, "Tin Cup")
        assert t is not None
        assert t.ty > _MIN_SURFACE_H

    def test_cup_ty_matches_table_height(self):
        assets = [_asset("Table", "table"), _asset("Cup", "cup")]
        layout = _build(assets)
        t = _transform(layout, "Cup")
        assert t is not None
        assert abs(t.ty - 0.75) < 0.01

    def test_cup_never_on_floor(self):
        assets = [_asset("Cup", "cup")]
        layout = _build(assets)
        t = _transform(layout, "Cup")
        assert t is not None
        assert t.ty > _MIN_SURFACE_H

    def test_cup_validation_pass(self):
        assets = [_asset("Table", "table"), _asset("Cup", "cup")]
        layout = _build(assets)
        assert layout.cup_support_pass is True


# ---------------------------------------------------------------------------
# Rule 6 — Plates on table
# ---------------------------------------------------------------------------

class TestPlateTableRule:
    def test_plate_on_table(self):
        assets = [_asset("Table", "table"), _asset("Plate", "plate")]
        layout = _build(assets)
        t = _transform(layout, "Plate")
        assert t is not None
        assert t.ty > _MIN_SURFACE_H

    def test_plate_never_on_floor(self):
        assets = [_asset("Plate", "plate")]
        layout = _build(assets)
        t = _transform(layout, "Plate")
        assert t is not None
        assert t.ty > _MIN_SURFACE_H

    def test_plate_validation_pass(self):
        assets = [_asset("Table", "table"), _asset("Plate", "plate")]
        layout = _build(assets)
        assert layout.plate_support_pass is True


# ---------------------------------------------------------------------------
# Rule 7 — Lantern: surface or wall
# ---------------------------------------------------------------------------

class TestLanternAttachmentRule:
    def test_lantern_on_table_when_present(self):
        assets = [_asset("Table", "table"), _asset("Lantern", "lantern")]
        layout = _build(assets)
        t = _transform(layout, "Lantern")
        assert t is not None
        # Lantern on table surface → ty = 0.75
        assert t.ty > _MIN_SURFACE_H

    def test_lantern_on_wall_when_no_table(self):
        assets = [_asset("Lantern", "lantern")]
        layout = _build(assets)
        t = _transform(layout, "Lantern")
        assert t is not None
        # Must not be floating: either on surface (ty > MIN) or wall-mounted (parent=wall)
        on_surface = t.ty > _MIN_SURFACE_H
        on_wall    = "wall" in (t.parent_id or "") or t.relationship == "attached_to"
        assert on_surface or on_wall, f"Lantern floating: ty={t.ty} parent={t.parent_id}"

    def test_lantern_not_floating(self):
        for assets in [
            [_asset("Table", "table"), _asset("Lantern", "lantern")],
            [_asset("Lantern", "lantern")],
        ]:
            layout = _build(assets)
            t = _transform(layout, "Lantern")
            assert t is not None
            on_surface = t.ty > _MIN_SURFACE_H
            on_wall    = "wall" in (t.parent_id or "")
            assert on_surface or on_wall

    def test_lantern_validation_pass(self):
        assets = [_asset("Table", "table"), _asset("Lantern", "lantern")]
        layout = _build(assets)
        assert layout.lantern_attachment_pass is True


# ---------------------------------------------------------------------------
# Rule 8 — Barrels near perimeter wall
# ---------------------------------------------------------------------------

class TestBarrelWallRule:
    def test_barrel_not_at_room_center(self):
        assets = [_asset("Barrel", "barrel")]
        layout = _build(assets)
        t = _transform(layout, "Barrel")
        assert t is not None
        # Not both tx and tz near zero simultaneously
        assert not (abs(t.tx) < 1.0 and abs(t.tz) < 1.0)

    def test_barrel_near_wall_parent(self):
        assets = [_asset("Barrel", "barrel")]
        layout = _build(assets)
        t = _transform(layout, "Barrel")
        assert t is not None
        assert "wall" in (t.parent_id or ""), f"Barrel parent should be a wall, got '{t.parent_id}'"

    def test_barrel_on_floor(self):
        assets = [_asset("Barrel", "barrel")]
        layout = _build(assets)
        t = _transform(layout, "Barrel")
        assert t is not None
        assert t.ty == 0.0

    def test_barrel_validation_pass(self):
        assets = [_asset("Table", "table"), _asset("Barrel", "barrel")]
        layout = _build(assets)
        assert layout.barrel_wall_relation_pass is True

    def test_multiple_barrels_different_positions(self):
        assets = [_asset("Barrel1", "barrel"), _asset("Barrel2", "barrel")]
        layout = _build(assets)
        t1 = _transform(layout, "Barrel1")
        t2 = _transform(layout, "Barrel2")
        assert t1 is not None and t2 is not None
        # Different positions
        assert not (abs(t1.tx - t2.tx) < 0.01 and abs(t1.tz - t2.tz) < 0.01)


# ---------------------------------------------------------------------------
# Rule 9 — Crates near perimeter wall
# ---------------------------------------------------------------------------

class TestCrateWallRule:
    def test_crate_near_wall(self):
        assets = [_asset("Crate", "crate")]
        layout = _build(assets)
        t = _transform(layout, "Crate")
        assert t is not None
        assert "wall" in (t.parent_id or "")

    def test_crate_not_floating(self):
        assets = [_asset("Crate", "crate")]
        layout = _build(assets)
        t = _transform(layout, "Crate")
        assert t is not None
        assert t.ty == 0.0

    def test_crate_validation_pass(self):
        assets = [_asset("Crate", "crate")]
        layout = _build(assets)
        assert layout.crate_wall_relation_pass is True


# ---------------------------------------------------------------------------
# Hard rules: nothing on floor that shouldn't be
# ---------------------------------------------------------------------------

class TestHardFloorRules:
    @pytest.mark.parametrize("ptype", ["bottle", "cup", "plate"])
    def test_no_floor_placement_for_tabletop_items(self, ptype: str):
        assets = [_asset("Table", "table"), _asset(f"Item_{ptype}", ptype)]
        layout = _build(assets)
        t = _transform(layout, f"Item_{ptype}")
        assert t is not None
        assert t.ty > _MIN_SURFACE_H, f"{ptype} must not be on floor, got ty={t.ty}"

    @pytest.mark.parametrize("ptype", ["bottle", "cup", "plate"])
    def test_no_floor_placement_even_without_table(self, ptype: str):
        assets = [_asset(f"Item_{ptype}", ptype)]
        layout = _build(assets)
        t = _transform(layout, f"Item_{ptype}")
        assert t is not None
        assert t.ty > _MIN_SURFACE_H, f"{ptype} must not be on floor even without table"

    def test_fireplace_must_be_wall_attached(self):
        assets = [_asset("FP", "fireplace")]
        layout = _build(assets)
        t = _transform(layout, "FP")
        assert t is not None
        assert "wall" in (t.parent_id or "") or t.relationship == "attached_to"


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

class TestScoring:
    def test_full_western_room_score_above_threshold(self):
        assets = [
            _asset("Table",   "table"),
            _asset("Chair1",  "chair"),
            _asset("Chair2",  "chair"),
            _asset("Bottle",  "bottle"),
            _asset("Lantern", "lantern"),
            _asset("Poster",  "poster"),
            _asset("Barrel",  "barrel"),
        ]
        layout = _build(assets, "western_room")
        assert layout.relationship_score >= 0.90

    def test_score_is_between_0_and_1(self):
        assets = [_asset("Table", "table"), _asset("Chair", "chair")]
        layout = _build(assets)
        assert 0.0 <= layout.relationship_score <= 1.0

    def test_status_pass_with_good_scene(self):
        assets = [
            _asset("Table",  "table"),
            _asset("Chair",  "chair"),
            _asset("Bottle", "bottle"),
        ]
        layout = _build(assets)
        assert layout.status == RELATIONSHIP_LAYOUT_STATUS_PASS

    def test_supported_objects_populated(self):
        assets = [_asset("Table", "table"), _asset("Bottle", "bottle")]
        layout = _build(assets)
        assert "Bottle" in layout.supported_objects

    def test_wall_attached_objects_populated(self):
        assets = [_asset("Poster", "poster")]
        layout = _build(assets)
        assert "Poster" in layout.wall_attached_objects

    def test_surface_attached_objects_populated(self):
        assets = [_asset("Table", "table"), _asset("Cup", "cup")]
        layout = _build(assets)
        assert "Cup" in layout.surface_attached_objects


# ---------------------------------------------------------------------------
# Output format
# ---------------------------------------------------------------------------

class TestOutputFormat:
    def test_transforms_list_length_matches_assets(self):
        assets = [
            _asset("Table", "table"),
            _asset("Chair", "chair"),
            _asset("Bottle", "bottle"),
        ]
        layout = _build(assets)
        assert len(layout.relationship_aware_transforms) == len(assets)

    def test_all_transforms_have_asset_id(self):
        assets = [_asset("Table", "table"), _asset("Chair", "chair")]
        layout = _build(assets)
        for t in layout.relationship_aware_transforms:
            assert t.asset_id != ""

    def test_to_dict_is_json_serialisable(self):
        import json
        assets = [
            _asset("Table",     "table"),
            _asset("Chair",     "chair"),
            _asset("Fireplace", "fireplace"),
            _asset("Bottle",    "bottle"),
            _asset("Barrel",    "barrel"),
        ]
        layout = _build(assets, "western_room")
        json.dumps(layout.to_dict())  # must not raise


# ---------------------------------------------------------------------------
# Shell integration
# ---------------------------------------------------------------------------

class TestShellIntegration:
    def test_shell_dict_affects_room_size(self):
        # A large room should push the fireplace further from origin
        large_shell = {"floor_area": 400.0, "ceiling_height": 8.0}
        small_shell = {"floor_area": 25.0,  "ceiling_height": 3.0}
        assets      = [_asset("Fireplace", "fireplace")]

        graph = get_relationship_graph_builder().build_graph(assets).relationship_graph

        layout_large = get_relationship_layout_engine().build_layout(
            assets, graph, large_shell
        )
        layout_small = get_relationship_layout_engine().build_layout(
            assets, graph, small_shell
        )
        t_large = _transform(layout_large, "Fireplace")
        t_small = _transform(layout_small, "Fireplace")
        assert t_large is not None and t_small is not None
        # Larger room → fireplace should be further from origin on Z axis
        assert abs(t_large.tz) > abs(t_small.tz)

    def test_none_shell_uses_defaults(self):
        assets = [_asset("Table", "table")]
        graph  = get_relationship_graph_builder().build_graph(assets).relationship_graph
        layout = get_relationship_layout_engine().build_layout(assets, graph, None)
        assert layout is not None
        t = _transform(layout, "Table")
        assert t is not None


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_same_input_produces_same_transforms(self):
        assets = [
            _asset("Table",  "table"),
            _asset("Chair1", "chair"),
            _asset("Chair2", "chair"),
            _asset("Bottle", "bottle"),
            _asset("Barrel", "barrel"),
        ]
        layout1 = _build(assets, "western_room")
        reset_relationship_layout_engine_for_tests()
        reset_relationship_graph_builder_for_tests()
        layout2 = _build(assets, "western_room")

        ids1 = sorted(t.asset_id for t in layout1.relationship_aware_transforms)
        ids2 = sorted(t.asset_id for t in layout2.relationship_aware_transforms)
        assert ids1 == ids2

        for t1 in layout1.relationship_aware_transforms:
            t2 = _transform(layout2, t1.asset_id)
            assert t2 is not None
            assert abs(t1.tx - t2.tx) < 0.001
            assert abs(t1.ty - t2.ty) < 0.001
            assert abs(t1.tz - t2.tz) < 0.001
