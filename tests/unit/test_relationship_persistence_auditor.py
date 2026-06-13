"""Tests for Tier 14.4.4 — RelationshipPersistenceAuditor."""

import pytest

from src.runtime.layout_realization.transform_resolver import ResolvedTransform
from src.runtime.layout_realization.relationship_metadata_writer import METADATA_KEYS
from src.runtime.layout_realization.relationship_persistence_auditor import (
    PERSISTENCE_AUDIT_PASS,
    PERSISTENCE_AUDIT_FAIL,
    REQUIRED_METADATA_KEYS,
    AssetMetadataRecord,
    RelationshipPersistenceAuditResult,
    RelationshipPersistenceAuditor,
    get_relationship_persistence_auditor,
    reset_relationship_persistence_auditor_for_tests,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_all():
    reset_relationship_persistence_auditor_for_tests()
    yield
    reset_relationship_persistence_auditor_for_tests()


def _full_meta(
    role: str = "cluster_member",
    relationship_type: str = "around",
    expected_parent: str = "table_01",
    actual_parent: str = "table_01",
    support_surface: str = "",
    anchor_id: str = "table_01",
    anchor_type: str = "table",
    placement_engine: str = "FurnitureClusterBuilder",
    layout_cluster_id: str = "cluster_A",
) -> dict:
    return {
        "vibrante_asset_role":         role,
        "vibrante_relationship_type":  relationship_type,
        "vibrante_expected_parent":    expected_parent,
        "vibrante_actual_parent":      actual_parent,
        "vibrante_support_surface":    support_surface,
        "vibrante_anchor_id":          anchor_id,
        "vibrante_anchor_type":        anchor_type,
        "vibrante_placement_engine":   placement_engine,
        "vibrante_layout_cluster_id":  layout_cluster_id,
    }


def _xf(asset_id: str, relationship: str = "", parent_id: str = "") -> ResolvedTransform:
    rt = ResolvedTransform(asset_id=asset_id, asset_name=asset_id, tx=0.0, ty=0.0, tz=0.0)
    rt.relationship = relationship
    rt.parent_id    = parent_id
    return rt


# ---------------------------------------------------------------------------
# REQUIRED_METADATA_KEYS
# ---------------------------------------------------------------------------

def test_required_metadata_keys_match_metadata_keys():
    assert set(REQUIRED_METADATA_KEYS) == set(METADATA_KEYS)


def test_required_metadata_keys_count():
    assert len(REQUIRED_METADATA_KEYS) == 9


# ---------------------------------------------------------------------------
# PASS: all assets have complete metadata
# ---------------------------------------------------------------------------

def test_pass_when_all_metadata_complete():
    auditor = get_relationship_persistence_auditor()
    meta = {
        "chair_01":  _full_meta(),
        "bottle_01": _full_meta(role="surface_child", relationship_type="supports",
                                anchor_type="table", placement_engine="SurfacePlacementEngine"),
    }
    result = auditor.audit(meta)
    assert result.status           == PERSISTENCE_AUDIT_PASS
    assert result.production_ready is True
    assert result.metadata_coverage == 1.0
    assert result.missing_metadata  == 0
    assert result.ok               is True


def test_pass_vacuous_empty_node_map():
    auditor = get_relationship_persistence_auditor()
    result = auditor.audit({})
    assert result.status           == PERSISTENCE_AUDIT_PASS
    assert result.production_ready is True
    assert result.metadata_coverage == 1.0
    assert result.total_assets      == 0


# ---------------------------------------------------------------------------
# FAIL: missing metadata
# ---------------------------------------------------------------------------

def test_fail_when_one_asset_missing_all_keys():
    auditor = get_relationship_persistence_auditor()
    meta = {
        "chair_01":  _full_meta(),
        "barrel_01": {},           # no keys at all
    }
    result = auditor.audit(meta)
    assert result.status            == PERSISTENCE_AUDIT_FAIL
    assert result.production_ready  is False
    assert result.missing_metadata  == 1
    assert result.metadata_coverage < 1.0


def test_fail_when_one_asset_missing_some_keys():
    auditor = get_relationship_persistence_auditor()
    partial = {k: "value" for k in REQUIRED_METADATA_KEYS[:5]}   # 5 of 9
    meta = {
        "chair_01":  _full_meta(),
        "barrel_01": partial,
    }
    result = auditor.audit(meta)
    assert result.status           == PERSISTENCE_AUDIT_FAIL
    assert result.missing_metadata == 1


def test_fail_all_missing():
    auditor = get_relationship_persistence_auditor()
    meta = {
        "a": {},
        "b": {},
        "c": {},
    }
    result = auditor.audit(meta)
    assert result.total_assets         == 3
    assert result.assets_complete      == 0
    assert result.missing_metadata     == 3
    assert result.metadata_coverage    == 0.0
    assert result.production_ready     is False


# ---------------------------------------------------------------------------
# Coverage calculation
# ---------------------------------------------------------------------------

def test_coverage_partial():
    auditor = get_relationship_persistence_auditor()
    meta = {
        "a": _full_meta(),      # complete
        "b": _full_meta(),      # complete
        "c": {},                # missing
        "d": {},                # missing
    }
    result = auditor.audit(meta)
    assert result.assets_complete  == 2
    assert result.missing_metadata == 2
    assert result.metadata_coverage == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Per-asset record fields
# ---------------------------------------------------------------------------

def test_record_metadata_exists_true():
    auditor = get_relationship_persistence_auditor()
    meta = {"chair_01": _full_meta()}
    result = auditor.audit(meta)
    rec = result.records[0]
    assert rec.metadata_exists   is True
    assert rec.metadata_complete is True


def test_record_metadata_exists_false_when_empty():
    auditor = get_relationship_persistence_auditor()
    meta = {"barrel_01": {}}
    result = auditor.audit(meta)
    rec = result.records[0]
    assert rec.metadata_exists   is False
    assert rec.metadata_complete is False


def test_record_missing_keys_reported():
    auditor = get_relationship_persistence_auditor()
    partial = {k: "v" for k in REQUIRED_METADATA_KEYS[:4]}
    meta = {"x": partial}
    result = auditor.audit(meta)
    rec = result.records[0]
    assert len(rec.missing_keys) == 5
    for k in rec.missing_keys:
        assert k not in partial


def test_record_values_read_from_metadata():
    auditor = get_relationship_persistence_auditor()
    meta = {
        "chair_01": _full_meta(
            role="cluster_member", relationship_type="around",
            expected_parent="table_01", actual_parent="table_01",
            support_surface="", anchor_id="table_01", anchor_type="table",
            placement_engine="FurnitureClusterBuilder",
        )
    }
    result = auditor.audit(meta)
    rec = result.records[0]
    assert rec.asset_role        == "cluster_member"
    assert rec.relationship_type == "around"
    assert rec.expected_parent   == "table_01"
    assert rec.actual_parent     == "table_01"
    assert rec.support_surface   == ""
    assert rec.anchor_type       == "table"
    assert rec.placement_engine  == "FurnitureClusterBuilder"


def test_record_node_name_from_node_names_dict():
    auditor = get_relationship_persistence_auditor()
    meta = {"chair_01": _full_meta()}
    result = auditor.audit(meta, node_names={"chair_01": "Wooden Chair"})
    assert result.records[0].asset_name == "Wooden Chair"


def test_record_node_path_from_node_paths_dict():
    auditor = get_relationship_persistence_auditor()
    meta = {"chair_01": _full_meta()}
    result = auditor.audit(meta, node_paths={"chair_01": "/obj/scene/chair_01"})
    assert result.records[0].node_path == "/obj/scene/chair_01"


# ---------------------------------------------------------------------------
# metadata_matches_layout with planned transforms
# ---------------------------------------------------------------------------

def test_metadata_matches_layout_true_when_consistent():
    auditor = get_relationship_persistence_auditor()
    xf = _xf("chair_01", relationship="around", parent_id="table_01")
    meta = {
        "chair_01": _full_meta(
            relationship_type="around",
            expected_parent="table_01",
        )
    }
    result = auditor.audit(meta, planned_transforms=[xf])
    assert result.records[0].metadata_matches_layout is True
    assert result.assets_matching_layout == 1


def test_metadata_matches_layout_false_when_relationship_differs():
    auditor = get_relationship_persistence_auditor()
    xf = _xf("chair_01", relationship="supports", parent_id="table_01")
    meta = {
        "chair_01": _full_meta(
            relationship_type="around",   # wrong — was planned as supports
            expected_parent="table_01",
        )
    }
    result = auditor.audit(meta, planned_transforms=[xf])
    assert result.records[0].metadata_matches_layout is False


def test_metadata_matches_layout_false_when_parent_differs():
    auditor = get_relationship_persistence_auditor()
    xf = _xf("chair_01", relationship="around", parent_id="table_02")
    meta = {
        "chair_01": _full_meta(
            relationship_type="around",
            expected_parent="table_01",  # wrong parent
        )
    }
    result = auditor.audit(meta, planned_transforms=[xf])
    assert result.records[0].metadata_matches_layout is False


def test_metadata_matches_layout_true_when_no_plan_supplied():
    auditor = get_relationship_persistence_auditor()
    meta = {"chair_01": _full_meta()}
    result = auditor.audit(meta, planned_transforms=[])
    # No plan to compare → treat as matching (no contradiction)
    assert result.records[0].metadata_matches_layout is True


def test_metadata_matches_layout_false_when_incomplete():
    auditor = get_relationship_persistence_auditor()
    xf = _xf("chair_01", relationship="around", parent_id="table_01")
    meta = {
        "chair_01": {k: "v" for k in REQUIRED_METADATA_KEYS[:3]}   # incomplete
    }
    result = auditor.audit(meta, planned_transforms=[xf])
    # incomplete → matches_layout must be False
    assert result.records[0].metadata_matches_layout is False


# ---------------------------------------------------------------------------
# to_dict output contract
# ---------------------------------------------------------------------------

def test_to_dict_has_required_top_level_fields():
    auditor = get_relationship_persistence_auditor()
    result = auditor.audit({"chair_01": _full_meta()})
    d = result.to_dict()
    for key in ("records", "total_assets", "assets_with_metadata", "assets_complete",
                "assets_matching_layout", "missing_metadata", "metadata_coverage",
                "status", "production_ready", "audit_table", "ok", "errors"):
        assert key in d, f"Missing key: {key}"


def test_to_dict_record_has_required_output_fields():
    auditor = get_relationship_persistence_auditor()
    result = auditor.audit({"chair_01": _full_meta()})
    rec_d = result.records[0].to_dict()
    for key in ("asset_name", "role", "relationship_type", "expected_parent",
                "actual_parent", "support_surface", "placement_engine",
                "metadata_exists", "metadata_complete", "metadata_matches_layout",
                "missing_keys"):
        assert key in rec_d, f"Record missing key: {key}"


# ---------------------------------------------------------------------------
# Audit table formatting
# ---------------------------------------------------------------------------

def test_audit_table_contains_pass_when_complete():
    auditor = get_relationship_persistence_auditor()
    result = auditor.audit({"chair_01": _full_meta()})
    assert "PASS" in result.audit_table
    assert "COMPLETE" in result.audit_table


def test_audit_table_contains_fail_when_missing():
    auditor = get_relationship_persistence_auditor()
    result = auditor.audit({"barrel_01": {}})
    assert "FAIL"    in result.audit_table
    assert "MISSING" in result.audit_table


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

def test_never_raises_on_bad_input():
    auditor = get_relationship_persistence_auditor()
    # Ensure no exception on None-ish values in metadata
    result = auditor.audit({"x": {"vibrante_asset_role": None}})
    assert result is not None


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton():
    a = get_relationship_persistence_auditor()
    b = get_relationship_persistence_auditor()
    assert a is b


def test_reset():
    a = get_relationship_persistence_auditor()
    reset_relationship_persistence_auditor_for_tests()
    b = get_relationship_persistence_auditor()
    assert a is not b
