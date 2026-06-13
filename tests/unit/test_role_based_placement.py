"""Tests for PlacementRelationships (Tier 9.6)."""

import pytest
from src.runtime.assets.assembly.placement_relationships import (
    ROLES,
    PLACEMENT_MODES,
    STRUCTURAL_KEYWORD_HINTS,
    PlacementRelationship,
    PlacementRelationships,
    get_placement_relationships,
    reset_placement_relationships_for_tests,
)


@pytest.fixture(autouse=True)
def reset():
    reset_placement_relationships_for_tests()
    yield
    reset_placement_relationships_for_tests()


class TestSingleton:
    def test_singleton_same_instance(self):
        assert get_placement_relationships() is get_placement_relationships()

    def test_reset_new_instance(self):
        a = get_placement_relationships()
        reset_placement_relationships_for_tests()
        assert a is not get_placement_relationships()


class TestGetRole:
    def test_chair_is_seating(self):
        r = get_placement_relationships()
        assert r.get_role("chair", "furniture") == "seating"

    def test_stool_is_seating(self):
        r = get_placement_relationships()
        assert r.get_role("stool", "furniture") == "seating"

    def test_table_is_furniture_anchor(self):
        r = get_placement_relationships()
        assert r.get_role("table", "furniture") == "furniture_anchor"

    def test_desk_is_furniture_anchor(self):
        r = get_placement_relationships()
        assert r.get_role("desk", "furniture") == "furniture_anchor"

    def test_bucket_is_decoration(self):
        r = get_placement_relationships()
        assert r.get_role("bucket", "prop") == "decoration"

    def test_lantern_is_decoration(self):
        r = get_placement_relationships()
        assert r.get_role("lantern", "prop") == "decoration"

    def test_beam_is_structure(self):
        r = get_placement_relationships()
        assert r.get_role("beam", "structure") == "structure"

    def test_wall_is_structure(self):
        r = get_placement_relationships()
        assert r.get_role("wall", "structure") == "structure"

    def test_column_is_structure(self):
        r = get_placement_relationships()
        assert r.get_role("column", "structure") == "structure"

    def test_door_is_architectural(self):
        r = get_placement_relationships()
        assert r.get_role("door", "architectural") == "architectural"

    def test_unknown_uses_category_fallback(self):
        r = get_placement_relationships()
        role = r.get_role("made_up_type", "electronic")
        assert role == "electronic"

    def test_totally_unknown_is_prop(self):
        r = get_placement_relationships()
        assert r.get_role("xyz_unknown", "unknown_cat") == "prop"

    def test_name_hint_detects_beam_in_name(self):
        r = get_placement_relationships()
        role = r.get_role("old_wooden_beam", "prop")
        assert role == "structure"


class TestGetPlacementMode:
    def test_chair_around_anchor(self):
        r = get_placement_relationships()
        assert r.get_placement_mode("chair", "furniture") == "around_anchor"

    def test_bucket_corner(self):
        r = get_placement_relationships()
        assert r.get_placement_mode("bucket", "prop") == "corner"

    def test_barrel_corner(self):
        r = get_placement_relationships()
        assert r.get_placement_mode("barrel", "prop") == "corner"

    def test_door_wall_only(self):
        r = get_placement_relationships()
        assert r.get_placement_mode("door", "architectural") == "wall_only"

    def test_beam_route_to_structure(self):
        r = get_placement_relationships()
        assert r.get_placement_mode("beam", "structure") == "route_to_structure"

    def test_wall_route_to_structure(self):
        r = get_placement_relationships()
        assert r.get_placement_mode("wall", "structure") == "route_to_structure"

    def test_poster_wall_only(self):
        r = get_placement_relationships()
        assert r.get_placement_mode("poster", "prop") == "wall_only"

    def test_table_hero_center(self):
        r = get_placement_relationships()
        assert r.get_placement_mode("table", "furniture") == "hero_center"


class TestIsStructural:
    def test_beam_is_structural(self):
        r = get_placement_relationships()
        assert r.is_structural("beam", "structure") is True

    def test_wall_is_structural(self):
        r = get_placement_relationships()
        assert r.is_structural("wall", "structure") is True

    def test_column_is_structural(self):
        r = get_placement_relationships()
        assert r.is_structural("column", "structure") is True

    def test_chair_is_not_structural(self):
        r = get_placement_relationships()
        assert r.is_structural("chair", "furniture") is False

    def test_table_is_not_structural(self):
        r = get_placement_relationships()
        assert r.is_structural("table", "furniture") is False

    def test_name_hint_old_wooden_beam_is_structural(self):
        r = get_placement_relationships()
        assert r.is_structural("", "prop", "Old Wooden Beam") is True

    def test_name_hint_pillar_is_structural(self):
        r = get_placement_relationships()
        assert r.is_structural("", "prop", "stone_pillar") is True


class TestFilterStructural:
    def test_beam_separated_from_chair(self):
        r = get_placement_relationships()
        assets = [
            {"name": "Wooden Chair", "type": "chair", "category": "furniture"},
            {"name": "Old Wooden Beam", "type": "beam", "category": "structure"},
            {"name": "Table", "type": "table", "category": "furniture"},
        ]
        placeable, structural = r.filter_structural(assets)
        assert len(placeable) == 2
        assert len(structural) == 1
        assert structural[0]["name"] == "Old Wooden Beam"

    def test_all_non_structural(self):
        r = get_placement_relationships()
        assets = [
            {"name": "Chair", "type": "chair", "category": "furniture"},
            {"name": "Cup", "type": "cup", "category": "prop"},
        ]
        placeable, structural = r.filter_structural(assets)
        assert len(placeable) == 2
        assert structural == []

    def test_all_structural(self):
        r = get_placement_relationships()
        assets = [
            {"name": "Wall", "type": "wall", "category": "structure"},
            {"name": "Column", "type": "column", "category": "structure"},
        ]
        placeable, structural = r.filter_structural(assets)
        assert placeable == []
        assert len(structural) == 2


class TestGetRelationship:
    def test_chair_has_anchor_type_table(self):
        r = get_placement_relationships()
        rel = r.get_relationship("chair", "furniture")
        assert rel.anchor_type == "table"
        assert rel.facing == "face_anchor"

    def test_bucket_no_anchor(self):
        r = get_placement_relationships()
        rel = r.get_relationship("bucket", "prop")
        assert rel.anchor_type is None

    def test_beam_is_structural_in_relationship(self):
        r = get_placement_relationships()
        rel = r.get_relationship("beam", "structure")
        assert rel.is_structural is True
        assert rel.placement_mode == "route_to_structure"

    def test_door_wall_only_relationship(self):
        r = get_placement_relationships()
        rel = r.get_relationship("door", "architectural")
        assert rel.placement_mode == "wall_only"

    def test_relationship_never_raises(self):
        r = get_placement_relationships()
        rel = r.get_relationship(None, None)  # type: ignore
        assert isinstance(rel, PlacementRelationship)


class TestConstants:
    def test_roles_frozenset(self):
        assert isinstance(ROLES, frozenset)
        assert "seating" in ROLES
        assert "structure" in ROLES
        assert "furniture_anchor" in ROLES

    def test_placement_modes_frozenset(self):
        assert isinstance(PLACEMENT_MODES, frozenset)
        assert "route_to_structure" in PLACEMENT_MODES
        assert "around_anchor" in PLACEMENT_MODES

    def test_structural_keyword_hints_contain_beam(self):
        assert "beam" in STRUCTURAL_KEYWORD_HINTS
        assert "wall" in STRUCTURAL_KEYWORD_HINTS
        assert "column" in STRUCTURAL_KEYWORD_HINTS
