"""Tests for Tier 14.4.4 — RelationshipMetadataWriter."""

import pytest

from src.runtime.layout_realization.transform_resolver import ResolvedTransform
from src.runtime.layout_realization.relationship_metadata_writer import (
    METADATA_KEYS,
    AssetRelationshipMetadata,
    RelationshipMetadataWriter,
    build_userdata_from_transform,
    get_relationship_metadata_writer,
    reset_relationship_metadata_writer_for_tests,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_all():
    reset_relationship_metadata_writer_for_tests()
    yield
    reset_relationship_metadata_writer_for_tests()


def _xf(
    asset_id: str,
    asset_name: str = "",
    relationship: str = "",
    parent_id: str = "",
    cluster_id: str = "",
    notes: str = "",
) -> ResolvedTransform:
    rt = ResolvedTransform(
        asset_id=asset_id,
        asset_name=asset_name or asset_id,
        tx=0.0, ty=0.0, tz=0.0,
    )
    rt.relationship = relationship
    rt.parent_id    = parent_id
    rt.cluster_id   = cluster_id
    rt.notes        = notes
    return rt


# ---------------------------------------------------------------------------
# METADATA_KEYS
# ---------------------------------------------------------------------------

def test_metadata_keys_count():
    assert len(METADATA_KEYS) == 9


def test_metadata_keys_all_vibrante_prefixed():
    for k in METADATA_KEYS:
        assert k.startswith("vibrante_"), f"{k!r} missing vibrante_ prefix"


# ---------------------------------------------------------------------------
# build_userdata_from_transform — role inference
# ---------------------------------------------------------------------------

def test_role_anchor():
    xf = _xf("table_01", relationship="anchor")
    ud = build_userdata_from_transform(xf)
    assert ud["vibrante_asset_role"] == "anchor"


def test_role_around_cluster_member():
    xf = _xf("chair_01", relationship="around", parent_id="table_01")
    ud = build_userdata_from_transform(xf)
    assert ud["vibrante_asset_role"] == "cluster_member"


def test_role_supports_surface_child():
    xf = _xf("bottle_01", relationship="supports", parent_id="table_01",
              notes="on table h=0.75m")
    ud = build_userdata_from_transform(xf)
    assert ud["vibrante_asset_role"] == "surface_child"


def test_role_attached_to_wall_mount():
    xf = _xf("poster_01", relationship="attached_to", parent_id="wall_north")
    ud = build_userdata_from_transform(xf)
    assert ud["vibrante_asset_role"] == "wall_mount"


def test_role_against_wall_adjacent():
    xf = _xf("bench_01", relationship="against", parent_id="wall_south")
    ud = build_userdata_from_transform(xf)
    assert ud["vibrante_asset_role"] == "wall_adjacent"


def test_role_hanging_from_ceiling_mount():
    xf = _xf("lantern_01", relationship="hanging_from", parent_id="ceiling")
    ud = build_userdata_from_transform(xf)
    assert ud["vibrante_asset_role"] == "ceiling_mount"


def test_role_scattered_decoration():
    xf = _xf("barrel_01", relationship="scattered")
    ud = build_userdata_from_transform(xf)
    assert ud["vibrante_asset_role"] == "decoration"


def test_role_unknown_defaults_prop():
    xf = _xf("thing_01", relationship="")
    ud = build_userdata_from_transform(xf)
    assert ud["vibrante_asset_role"] == "prop"


# ---------------------------------------------------------------------------
# build_userdata_from_transform — relationship_type
# ---------------------------------------------------------------------------

def test_relationship_type_preserved():
    xf = _xf("chair_01", relationship="around")
    ud = build_userdata_from_transform(xf)
    assert ud["vibrante_relationship_type"] == "around"


def test_relationship_type_empty_when_none():
    xf = _xf("thing_01", relationship="")
    ud = build_userdata_from_transform(xf)
    assert ud["vibrante_relationship_type"] == ""


# ---------------------------------------------------------------------------
# build_userdata_from_transform — expected/actual parent
# ---------------------------------------------------------------------------

def test_expected_parent_set():
    xf = _xf("chair_01", relationship="around", parent_id="table_01")
    ud = build_userdata_from_transform(xf)
    assert ud["vibrante_expected_parent"] == "table_01"
    assert ud["vibrante_actual_parent"]   == "table_01"


def test_expected_parent_empty_for_anchor():
    xf = _xf("table_01", relationship="anchor", parent_id="")
    ud = build_userdata_from_transform(xf)
    assert ud["vibrante_expected_parent"] == ""


# ---------------------------------------------------------------------------
# build_userdata_from_transform — support surface extraction
# ---------------------------------------------------------------------------

def test_surface_extracted_from_notes_table():
    xf = _xf("cup_01", relationship="supports", parent_id="table_01",
              notes="on table h=0.75m")
    ud = build_userdata_from_transform(xf)
    assert ud["vibrante_support_surface"] == "table"


def test_surface_extracted_bar_counter():
    xf = _xf("glass_01", relationship="supports", parent_id="bar_01",
              notes="on bar_counter h=1.05m")
    ud = build_userdata_from_transform(xf)
    assert ud["vibrante_support_surface"] == "bar_counter"


def test_surface_extracted_surface_word_stripped():
    xf = _xf("cup_01", relationship="supports",
              notes="on table surface h=0.75m")
    ud = build_userdata_from_transform(xf)
    assert ud["vibrante_support_surface"] == "table"


def test_surface_empty_for_wall_attachment():
    xf = _xf("poster_01", relationship="attached_to", parent_id="wall_north",
              notes="wall=wall_north h=1.60m")
    ud = build_userdata_from_transform(xf)
    assert ud["vibrante_support_surface"] == ""


# ---------------------------------------------------------------------------
# build_userdata_from_transform — anchor_id and anchor_type
# ---------------------------------------------------------------------------

def test_anchor_id_set_for_around():
    xf = _xf("chair_01", relationship="around", parent_id="table_01")
    ud = build_userdata_from_transform(xf)
    assert ud["vibrante_anchor_id"] == "table_01"


def test_anchor_id_empty_for_wall_attachment():
    xf = _xf("poster_01", relationship="attached_to", parent_id="wall_north")
    ud = build_userdata_from_transform(xf)
    assert ud["vibrante_anchor_id"] == ""


def test_anchor_type_inferred_from_id():
    xf = _xf("chair_01", relationship="around", parent_id="my_table_hero")
    ud = build_userdata_from_transform(xf)
    assert ud["vibrante_anchor_type"] == "table"


def test_anchor_type_from_explicit_map():
    xf = _xf("chair_01", relationship="around", parent_id="anchor_42")
    ud = build_userdata_from_transform(xf, anchor_type_map={"anchor_42": "bar_counter"})
    assert ud["vibrante_anchor_type"] == "bar_counter"


def test_anchor_type_empty_when_no_anchor():
    xf = _xf("barrel_01", relationship="near", parent_id="corner_sw")
    ud = build_userdata_from_transform(xf)
    # "corner_sw" contains no known anchor type hint → empty
    assert ud["vibrante_anchor_type"] == ""


# ---------------------------------------------------------------------------
# build_userdata_from_transform — placement engine
# ---------------------------------------------------------------------------

def test_engine_anchor_layout():
    xf = _xf("table_01", relationship="anchor")
    ud = build_userdata_from_transform(xf)
    assert ud["vibrante_placement_engine"] == "AnchorLayoutEngine"


def test_engine_furniture_cluster():
    xf = _xf("chair_01", relationship="around")
    ud = build_userdata_from_transform(xf)
    assert ud["vibrante_placement_engine"] == "FurnitureClusterBuilder"


def test_engine_surface_placement():
    xf = _xf("bottle_01", relationship="supports")
    ud = build_userdata_from_transform(xf)
    assert ud["vibrante_placement_engine"] == "SurfacePlacementEngine"


def test_engine_wall_attachment():
    xf = _xf("poster_01", relationship="attached_to")
    ud = build_userdata_from_transform(xf)
    assert ud["vibrante_placement_engine"] == "WallAttachmentEngine"


def test_engine_decoration_layout():
    xf = _xf("barrel_01", relationship="near")
    ud = build_userdata_from_transform(xf)
    assert ud["vibrante_placement_engine"] == "DecorationLayoutEngine"


def test_engine_unknown_defaults_semantic():
    xf = _xf("thing_01", relationship="")
    ud = build_userdata_from_transform(xf)
    assert ud["vibrante_placement_engine"] == "SemanticLayoutEngine"


# ---------------------------------------------------------------------------
# build_userdata_from_transform — cluster_id
# ---------------------------------------------------------------------------

def test_cluster_id_preserved():
    xf = _xf("chair_01", relationship="around", cluster_id="saloon_table_cluster")
    ud = build_userdata_from_transform(xf)
    assert ud["vibrante_layout_cluster_id"] == "saloon_table_cluster"


def test_cluster_id_empty_for_non_cluster():
    xf = _xf("barrel_01", relationship="near")
    ud = build_userdata_from_transform(xf)
    assert ud["vibrante_layout_cluster_id"] == ""


# ---------------------------------------------------------------------------
# build_userdata_from_transform — all 9 keys present
# ---------------------------------------------------------------------------

def test_all_9_keys_present():
    xf = _xf("chair_01", relationship="around", parent_id="table_01",
              cluster_id="saloon_table_cluster", notes="on table h=0.75m")
    ud = build_userdata_from_transform(xf)
    for k in METADATA_KEYS:
        assert k in ud, f"Missing key: {k}"


def test_all_values_are_strings():
    xf = _xf("chair_01", relationship="around", parent_id="table_01")
    ud = build_userdata_from_transform(xf)
    for k, v in ud.items():
        assert isinstance(v, str), f"Key {k!r} has non-string value {v!r}"


# ---------------------------------------------------------------------------
# RelationshipMetadataWriter.build_metadata_records
# ---------------------------------------------------------------------------

def test_writer_builds_one_record_per_transform():
    writer = get_relationship_metadata_writer()
    transforms = [
        _xf("table_01", relationship="anchor"),
        _xf("chair_01", relationship="around", parent_id="table_01"),
        _xf("bottle_01", relationship="supports", parent_id="table_01",
            notes="on table h=0.75m"),
    ]
    records = writer.build_metadata_records(transforms, {
        "table_01":  "/obj/scene/table_01",
        "chair_01":  "/obj/scene/chair_01",
        "bottle_01": "/obj/scene/bottle_01",
    })
    assert len(records) == 3


def test_writer_node_path_from_map():
    writer = get_relationship_metadata_writer()
    xf = _xf("table_01", relationship="anchor")
    records = writer.build_metadata_records([xf], {"table_01": "/obj/scene/table_01"})
    assert records[0].node_path == "/obj/scene/table_01"


def test_writer_node_path_empty_when_missing_from_map():
    writer = get_relationship_metadata_writer()
    xf = _xf("table_01", relationship="anchor")
    records = writer.build_metadata_records([xf], {})
    assert records[0].node_path == ""


def test_writer_anchor_type_from_explicit_map():
    writer = get_relationship_metadata_writer()
    xf = _xf("chair_01", relationship="around", parent_id="anchor_99")
    records = writer.build_metadata_records(
        [xf], {},
        anchor_type_map={"anchor_99": "bar_counter"},
    )
    assert records[0].anchor_type == "bar_counter"


def test_writer_never_raises_on_empty_input():
    writer = get_relationship_metadata_writer()
    records = writer.build_metadata_records([], {})
    assert records == []


# ---------------------------------------------------------------------------
# AssetRelationshipMetadata.to_houdini_userdata
# ---------------------------------------------------------------------------

def test_to_houdini_userdata_keys():
    meta = AssetRelationshipMetadata(
        asset_id="chair_01", asset_name="chair_01", node_path="/obj/c",
        asset_role="cluster_member", relationship_type="around",
        expected_parent="table_01", actual_parent="table_01",
        support_surface="", anchor_id="table_01", anchor_type="table",
        placement_engine="FurnitureClusterBuilder", layout_cluster_id="cluster_A",
    )
    ud = meta.to_houdini_userdata()
    assert set(ud.keys()) == set(METADATA_KEYS)


def test_to_houdini_userdata_values_match():
    meta = AssetRelationshipMetadata(
        asset_id="chair_01", asset_name="chair_01", node_path="/obj/c",
        asset_role="cluster_member", relationship_type="around",
        expected_parent="table_01", actual_parent="table_01",
        support_surface="", anchor_id="table_01", anchor_type="table",
        placement_engine="FurnitureClusterBuilder", layout_cluster_id="cluster_A",
    )
    ud = meta.to_houdini_userdata()
    assert ud["vibrante_asset_role"]        == "cluster_member"
    assert ud["vibrante_relationship_type"] == "around"
    assert ud["vibrante_expected_parent"]   == "table_01"
    assert ud["vibrante_anchor_type"]       == "table"
    assert ud["vibrante_placement_engine"]  == "FurnitureClusterBuilder"
    assert ud["vibrante_layout_cluster_id"] == "cluster_A"


# ---------------------------------------------------------------------------
# Singleton behaviour
# ---------------------------------------------------------------------------

def test_singleton_returns_same_instance():
    a = get_relationship_metadata_writer()
    b = get_relationship_metadata_writer()
    assert a is b


def test_reset_creates_new_instance():
    a = get_relationship_metadata_writer()
    reset_relationship_metadata_writer_for_tests()
    b = get_relationship_metadata_writer()
    assert a is not b
