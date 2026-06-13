"""Tests for Tier 14.4.5 — Asset Identity Audit."""

import pytest

from src.runtime.layout_realization.identity_metadata_writer import (
    IDENTITY_KEYS,
    AssetIdentityMetadata,
    IdentityMetadataWriter,
    build_identity_userdata,
    get_identity_metadata_writer,
    reset_identity_metadata_writer_for_tests,
)
from src.runtime.layout_realization.transform_resolver import ResolvedTransform
from src.runtime.asset_identity.opaque_id_detector import (
    OPAQUE_PATTERN,
    VOCABULARY_WORDS,
    OpaqueIdDetector,
    is_opaque_id,
    get_opaque_id_detector,
    reset_opaque_id_detector_for_tests,
)
from src.runtime.asset_identity.role_engine_validator import (
    ROLE_ENGINE_MAP,
    RoleEngineValidator,
    get_role_engine_validator,
    reset_role_engine_validator_for_tests,
)
from src.runtime.asset_identity.role_geometry_validator import (
    ROLE_CATEGORY_MAP,
    RoleGeometryValidator,
    get_role_geometry_validator,
    reset_role_geometry_validator_for_tests,
)
from src.runtime.asset_identity.asset_identity_auditor import (
    IDENTITY_AUDIT_PASS,
    IDENTITY_AUDIT_FAIL,
    IDENTITY_RESOLVED,
    IDENTITY_OPAQUE_NAME,
    IDENTITY_OPAQUE_ID,
    IDENTITY_MISSING_ROLE,
    IDENTITY_MISSING_CATEGORY,
    IDENTITY_MISSING_NAME,
    IDENTITY_ROLE_ENGINE_MISMATCH,
    IDENTITY_ROLE_CATEGORY_MISMATCH,
    IDENTITY_UNCLASSIFIED,
    ALL_IDENTITY_KEYS,
    AssetIdentityRecord,
    IdentityAuditResult,
    AssetIdentityAuditor,
    get_asset_identity_auditor,
    reset_asset_identity_auditor_for_tests,
)
from src.runtime.asset_identity.identity_review import (
    IdentityReviewResult,
    IdentityReview,
    get_identity_review,
    reset_identity_review_for_tests,
)
from src.runtime.asset_identity.identity_statistics import (
    IdentityStatistics,
    get_identity_statistics,
    reset_identity_statistics_for_tests,
)
from src.runtime.asset_identity.identity_serializer import (
    IdentitySerializer,
    get_identity_serializer,
    reset_identity_serializer_for_tests,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_all():
    reset_opaque_id_detector_for_tests()
    reset_role_engine_validator_for_tests()
    reset_role_geometry_validator_for_tests()
    reset_asset_identity_auditor_for_tests()
    reset_identity_review_for_tests()
    reset_identity_statistics_for_tests()
    reset_identity_serializer_for_tests()
    reset_identity_metadata_writer_for_tests()
    yield
    reset_opaque_id_detector_for_tests()
    reset_role_engine_validator_for_tests()
    reset_role_geometry_validator_for_tests()
    reset_asset_identity_auditor_for_tests()
    reset_identity_review_for_tests()
    reset_identity_statistics_for_tests()
    reset_identity_serializer_for_tests()
    reset_identity_metadata_writer_for_tests()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _full_meta(
    asset_id:       str = "chair_01",
    asset_name:     str = "Wooden Saloon Chair",
    asset_category: str = "furniture",
    asset_role:     str = "cluster_member",
    engine:         str = "FurnitureClusterBuilder",
    rel_type:       str = "around",
    expected_parent: str = "table_01",
    actual_parent:  str = "table_01",
    support_surface: str = "",
    anchor_id:      str = "table_01",
    anchor_type:    str = "table",
    cluster_id:     str = "saloon_table_cluster",
) -> dict:
    return {
        "vibrante_asset_id":         asset_id,
        "vibrante_asset_name":       asset_name,
        "vibrante_asset_category":   asset_category,
        "vibrante_asset_role":       asset_role,
        "vibrante_placement_engine": engine,
        "vibrante_relationship_type": rel_type,
        "vibrante_expected_parent":  expected_parent,
        "vibrante_actual_parent":    actual_parent,
        "vibrante_support_surface":  support_surface,
        "vibrante_anchor_id":        anchor_id,
        "vibrante_anchor_type":      anchor_type,
        "vibrante_layout_cluster_id": cluster_id,
    }


def _xf(
    asset_id:   str = "chair_01",
    asset_name: str = "Wooden Saloon Chair",
    relationship: str = "around",
    parent_id:  str = "table_01",
    cluster_id: str = "saloon_table_cluster",
) -> ResolvedTransform:
    rt = ResolvedTransform(
        asset_id=asset_id, asset_name=asset_name,
        tx=0.0, ty=0.0, tz=0.0,
    )
    rt.relationship = relationship
    rt.parent_id    = parent_id
    rt.cluster_id   = cluster_id
    rt.notes        = ""
    return rt


# ===========================================================================
# IDENTITY_KEYS
# ===========================================================================

def test_identity_keys_count():
    assert len(IDENTITY_KEYS) == 3


def test_identity_keys_names():
    assert "vibrante_asset_id"       in IDENTITY_KEYS
    assert "vibrante_asset_name"     in IDENTITY_KEYS
    assert "vibrante_asset_category" in IDENTITY_KEYS


def test_all_identity_keys_count():
    assert len(ALL_IDENTITY_KEYS) == 12   # 3 identity + 9 relationship


def test_all_identity_keys_contains_relationship_keys():
    from src.runtime.layout_realization.relationship_metadata_writer import METADATA_KEYS
    for k in METADATA_KEYS:
        assert k in ALL_IDENTITY_KEYS


# ===========================================================================
# OpaqueIdDetector
# ===========================================================================

class TestOpaqueIdDetector:

    def test_known_opaque_ids(self):
        d = get_opaque_id_detector()
        assert d.is_opaque("xgihfgbqx")
        assert d.is_opaque("wgxobac")
        assert d.is_opaque("ukphdffaw")
        assert d.is_opaque("abcdefghi")
        assert d.is_opaque("zyxwvuts")

    def test_human_readable_not_opaque(self):
        d = get_opaque_id_detector()
        assert not d.is_opaque("wooden_chair")
        assert not d.is_opaque("Wooden Saloon Chair")
        assert not d.is_opaque("table_01")
        assert not d.is_opaque("old_barrel")
        assert not d.is_opaque("WoodenChair_lod0")
        assert not d.is_opaque("megascans_wood_abc123")

    def test_vocabulary_words_not_opaque(self):
        d = get_opaque_id_detector()
        # single vocab words are short but contain a known word
        assert not d.is_opaque("chair")
        assert not d.is_opaque("table")
        assert not d.is_opaque("barrel")
        assert not d.is_opaque("lantern")

    def test_digits_not_opaque(self):
        d = get_opaque_id_detector()
        assert not d.is_opaque("chair01")
        assert not d.is_opaque("table123")

    def test_uppercase_not_opaque(self):
        d = get_opaque_id_detector()
        assert not d.is_opaque("WoodenChair")
        assert not d.is_opaque("OldBarrel")

    def test_underscore_not_opaque(self):
        d = get_opaque_id_detector()
        assert not d.is_opaque("old_chair")
        assert not d.is_opaque("metal_table")

    def test_empty_not_opaque(self):
        d = get_opaque_id_detector()
        assert not d.is_opaque("")
        assert not d.is_opaque("   ")

    def test_too_short_not_opaque(self):
        d = get_opaque_id_detector()
        assert not d.is_opaque("abc")    # 3 chars — below 5
        assert not d.is_opaque("xy")

    def test_too_long_not_opaque(self):
        d = get_opaque_id_detector()
        assert not d.is_opaque("abcdefghijklmnopq")   # 17 chars — above 15

    def test_module_level_helper(self):
        assert is_opaque_id("xgihfgbqx")
        assert not is_opaque_id("wooden_chair")

    def test_singleton_stable(self):
        a = get_opaque_id_detector()
        b = get_opaque_id_detector()
        assert a is b

    def test_vocabulary_words_set_nonempty(self):
        assert len(VOCABULARY_WORDS) > 30


# ===========================================================================
# RoleEngineValidator
# ===========================================================================

class TestRoleEngineValidator:

    def test_anchor_anchor_layout_engine(self):
        v = get_role_engine_validator()
        assert v.is_compatible("anchor", "AnchorLayoutEngine")

    def test_cluster_member_furniture_cluster(self):
        v = get_role_engine_validator()
        assert v.is_compatible("cluster_member", "FurnitureClusterBuilder")

    def test_surface_child_surface_placement(self):
        v = get_role_engine_validator()
        assert v.is_compatible("surface_child", "SurfacePlacementEngine")

    def test_wall_mount_wall_attachment(self):
        v = get_role_engine_validator()
        assert v.is_compatible("wall_mount", "WallAttachmentEngine")

    def test_ceiling_mount_wall_attachment(self):
        v = get_role_engine_validator()
        assert v.is_compatible("ceiling_mount", "WallAttachmentEngine")

    def test_decoration_decoration_layout(self):
        v = get_role_engine_validator()
        assert v.is_compatible("decoration", "DecorationLayoutEngine")

    def test_mismatch_surface_child_wall_attachment(self):
        v = get_role_engine_validator()
        assert not v.is_compatible("surface_child", "WallAttachmentEngine")

    def test_mismatch_anchor_surface_placement(self):
        v = get_role_engine_validator()
        assert not v.is_compatible("anchor", "SurfacePlacementEngine")

    def test_mismatch_cluster_member_wall_attachment(self):
        v = get_role_engine_validator()
        assert not v.is_compatible("cluster_member", "WallAttachmentEngine")

    def test_empty_role_always_compatible(self):
        v = get_role_engine_validator()
        assert v.is_compatible("", "WallAttachmentEngine")

    def test_empty_engine_always_compatible(self):
        v = get_role_engine_validator()
        assert v.is_compatible("anchor", "")

    def test_unknown_role_compatible(self):
        v = get_role_engine_validator()
        assert v.is_compatible("unknown_role", "AnchorLayoutEngine")

    def test_expected_engines_for_wall_mount(self):
        v = get_role_engine_validator()
        assert "WallAttachmentEngine" in v.expected_engines("wall_mount")

    def test_role_engine_map_nonempty(self):
        assert len(ROLE_ENGINE_MAP) >= 10


# ===========================================================================
# RoleGeometryValidator
# ===========================================================================

class TestRoleGeometryValidator:

    def test_anchor_furniture_compatible(self):
        v = get_role_geometry_validator()
        assert v.is_compatible("anchor", "furniture")

    def test_cluster_member_furniture_compatible(self):
        v = get_role_geometry_validator()
        assert v.is_compatible("cluster_member", "furniture")

    def test_surface_child_prop_compatible(self):
        v = get_role_geometry_validator()
        assert v.is_compatible("surface_child", "prop")

    def test_wall_mount_signage_compatible(self):
        v = get_role_geometry_validator()
        assert v.is_compatible("wall_mount", "signage")

    def test_decoration_smallprop_compatible(self):
        v = get_role_geometry_validator()
        assert v.is_compatible("decoration", "smallprop")

    def test_structural_surface_child_mismatch(self):
        v = get_role_geometry_validator()
        assert not v.is_compatible("surface_child", "structural")

    def test_structural_cluster_member_mismatch(self):
        v = get_role_geometry_validator()
        assert not v.is_compatible("cluster_member", "structural")

    def test_structural_ceiling_mount_mismatch(self):
        v = get_role_geometry_validator()
        assert not v.is_compatible("ceiling_mount", "structural")

    def test_empty_role_compatible(self):
        v = get_role_geometry_validator()
        assert v.is_compatible("", "furniture")

    def test_empty_category_compatible(self):
        v = get_role_geometry_validator()
        assert v.is_compatible("anchor", "")

    def test_unknown_category_compatible(self):
        v = get_role_geometry_validator()
        assert v.is_compatible("anchor", "unknown")


# ===========================================================================
# IdentityMetadataWriter
# ===========================================================================

class TestIdentityMetadataWriter:

    def test_build_from_transform_basic(self):
        writer = get_identity_metadata_writer()
        xf = _xf("chair_01", "Wooden Saloon Chair")
        records = writer.build_metadata_records([xf], category_map={"chair_01": "furniture"})
        assert len(records) == 1
        r = records[0]
        assert r.asset_id       == "chair_01"
        assert r.asset_name     == "Wooden Saloon Chair"
        assert r.asset_category == "furniture"

    def test_category_inferred_from_name_chair(self):
        writer = get_identity_metadata_writer()
        xf = _xf("c1", "Old Wooden Chair")
        records = writer.build_metadata_records([xf])
        assert records[0].asset_category == "furniture"

    def test_category_inferred_from_name_table(self):
        writer = get_identity_metadata_writer()
        xf = _xf("t1", "Saloon Table")
        records = writer.build_metadata_records([xf])
        assert records[0].asset_category == "furniture"

    def test_category_inferred_from_name_lantern(self):
        writer = get_identity_metadata_writer()
        xf = _xf("l1", "Oil Lantern")
        records = writer.build_metadata_records([xf])
        assert records[0].asset_category == "prop"

    def test_category_inferred_from_name_beam(self):
        writer = get_identity_metadata_writer()
        xf = _xf("b1", "Old Wooden Beam")
        records = writer.build_metadata_records([xf])
        assert records[0].asset_category == "structural"

    def test_category_explicit_overrides_inference(self):
        writer = get_identity_metadata_writer()
        xf = _xf("c1", "Weird Chair Name That Might Not Infer")
        records = writer.build_metadata_records([xf], category_map={"c1": "custom_cat"})
        assert records[0].asset_category == "custom_cat"

    def test_to_houdini_userdata_keys(self):
        writer = get_identity_metadata_writer()
        xf = _xf("c1", "Wooden Chair")
        records = writer.build_metadata_records([xf], category_map={"c1": "furniture"})
        ud = records[0].to_houdini_userdata()
        assert set(ud.keys()) == set(IDENTITY_KEYS)

    def test_build_identity_userdata_helper(self):
        xf = _xf("c1", "Barrel")
        ud = build_identity_userdata(xf, asset_category="prop")
        assert ud["vibrante_asset_id"]       == "c1"
        assert ud["vibrante_asset_name"]     == "Barrel"
        assert ud["vibrante_asset_category"] == "prop"

    def test_empty_transforms_returns_empty(self):
        writer = get_identity_metadata_writer()
        assert writer.build_metadata_records([]) == []


# ===========================================================================
# AssetIdentityAuditor — PASS scenarios
# ===========================================================================

class TestAssetIdentityAuditorPass:

    def test_pass_single_fully_resolved(self):
        auditor = get_asset_identity_auditor()
        result = auditor.audit(
            node_metadata={"chair_01": _full_meta()},
            node_names={"chair_01": "chair_01"},
            node_paths={"chair_01": "/obj/scene/chair_01"},
        )
        assert result.status == IDENTITY_AUDIT_PASS
        assert result.production_ready is True
        assert result.resolved_assets == 1
        assert result.opaque_assets   == 0
        assert result.unclassified_assets == 0
        assert result.identity_coverage == 1.0

    def test_pass_multiple_assets_all_resolved(self):
        auditor = get_asset_identity_auditor()
        meta = {
            "chair_01": _full_meta(asset_id="chair_01", asset_name="Wooden Saloon Chair"),
            "table_01": _full_meta(
                asset_id="table_01", asset_name="Round Saloon Table",
                asset_category="furniture", asset_role="anchor",
                engine="AnchorLayoutEngine", rel_type="anchor",
                anchor_id="", anchor_type="",
            ),
            "bottle_01": _full_meta(
                asset_id="bottle_01", asset_name="Whiskey Bottle",
                asset_category="prop", asset_role="surface_child",
                engine="SurfacePlacementEngine", rel_type="supports",
            ),
        }
        result = auditor.audit(node_metadata=meta)
        assert result.status == IDENTITY_AUDIT_PASS
        assert result.total_assets == 3
        assert result.resolved_assets == 3
        assert result.identity_coverage == 1.0

    def test_pass_empty_metadata_vacuous(self):
        auditor = get_asset_identity_auditor()
        result = auditor.audit(node_metadata={})
        assert result.status == IDENTITY_AUDIT_PASS
        assert result.production_ready is True
        assert result.total_assets == 0


# ===========================================================================
# AssetIdentityAuditor — opaque name detection
# ===========================================================================

class TestOpaqueNameDetection:

    def test_fail_opaque_name(self):
        auditor = get_asset_identity_auditor()
        meta = {"xgihfgbqx": _full_meta(
            asset_id="xgihfgbqx",
            asset_name="xgihfgbqx",
        )}
        result = auditor.audit(node_metadata=meta)
        assert result.status == IDENTITY_AUDIT_FAIL
        assert result.opaque_assets == 1
        assert result.records[0].identity_status == IDENTITY_OPAQUE_NAME

    def test_fail_opaque_name_wgxobac(self):
        auditor = get_asset_identity_auditor()
        meta = {"wgxobac": _full_meta(asset_id="wgxobac", asset_name="wgxobac")}
        result = auditor.audit(node_metadata=meta)
        assert result.opaque_assets >= 1

    def test_fail_opaque_name_ukphdffaw(self):
        auditor = get_asset_identity_auditor()
        meta = {"ukphdffaw": _full_meta(asset_id="ukphdffaw", asset_name="ukphdffaw")}
        result = auditor.audit(node_metadata=meta)
        assert result.opaque_assets >= 1

    def test_fail_opaque_node_name_fallback(self):
        # asset_name key missing → falls back to node_name
        auditor = get_asset_identity_auditor()
        bad_meta = dict(_full_meta())
        bad_meta["vibrante_asset_name"] = ""   # blank → use node_name
        result = auditor.audit(
            node_metadata={"xgihfgbqx": bad_meta},
            node_names={"xgihfgbqx": "xgihfgbqx"},
        )
        assert result.opaque_assets >= 1

    def test_human_name_not_flagged_opaque(self):
        auditor = get_asset_identity_auditor()
        result = auditor.audit(
            node_metadata={"chair_01": _full_meta(
                asset_id="chair_01",
                asset_name="Wooden Saloon Chair",
            )}
        )
        assert result.opaque_assets == 0
        assert result.records[0].is_opaque_name is False


# ===========================================================================
# AssetIdentityAuditor — missing field detection
# ===========================================================================

class TestMissingFields:

    def test_fail_missing_role(self):
        auditor = get_asset_identity_auditor()
        meta = {"c1": _full_meta(asset_role="")}
        result = auditor.audit(node_metadata=meta)
        assert result.status == IDENTITY_AUDIT_FAIL
        rec = result.records[0]
        assert rec.identity_status in (IDENTITY_MISSING_ROLE, IDENTITY_UNCLASSIFIED)

    def test_fail_missing_category(self):
        auditor = get_asset_identity_auditor()
        meta = {"c1": _full_meta(asset_category="")}
        result = auditor.audit(node_metadata=meta)
        assert result.status == IDENTITY_AUDIT_FAIL
        rec = result.records[0]
        assert rec.identity_status in (IDENTITY_MISSING_CATEGORY, IDENTITY_UNCLASSIFIED)

    def test_fail_missing_name(self):
        auditor = get_asset_identity_auditor()
        bad_meta = dict(_full_meta())
        bad_meta["vibrante_asset_name"] = ""
        result = auditor.audit(
            node_metadata={"c1": bad_meta},
            node_names={"c1": "c1"},  # node_name also empty / non-vocab
        )
        assert result.status == IDENTITY_AUDIT_FAIL

    def test_fail_unclassified_multiple_missing(self):
        auditor = get_asset_identity_auditor()
        bad_meta = dict(_full_meta())
        bad_meta["vibrante_asset_role"]     = ""
        bad_meta["vibrante_asset_category"] = ""
        bad_meta["vibrante_asset_name"]     = ""
        result = auditor.audit(
            node_metadata={"c1": bad_meta},
            node_names={"c1": "c1"},
        )
        assert result.unclassified_assets == 1
        assert result.records[0].identity_status == IDENTITY_UNCLASSIFIED


# ===========================================================================
# AssetIdentityAuditor — mismatch detection
# ===========================================================================

class TestMismatchDetection:

    def test_role_engine_mismatch_surface_child_wall_attachment(self):
        auditor = get_asset_identity_auditor()
        meta = {"c1": _full_meta(
            asset_role="surface_child",
            engine="WallAttachmentEngine",
            asset_name="Whiskey Bottle",
        )}
        result = auditor.audit(node_metadata=meta)
        assert result.status == IDENTITY_AUDIT_FAIL
        rec = result.records[0]
        assert rec.identity_status == IDENTITY_ROLE_ENGINE_MISMATCH
        assert rec.role_engine_ok is False

    def test_role_category_mismatch_structural_surface_child(self):
        auditor = get_asset_identity_auditor()
        meta = {"b1": _full_meta(
            asset_name="Old Wooden Beam",
            asset_category="structural",
            asset_role="surface_child",
            engine="SurfacePlacementEngine",
        )}
        result = auditor.audit(node_metadata=meta)
        assert result.status == IDENTITY_AUDIT_FAIL
        rec = result.records[0]
        assert rec.identity_status == IDENTITY_ROLE_CATEGORY_MISMATCH
        assert rec.role_category_ok is False

    def test_role_category_mismatch_structural_cluster_member(self):
        auditor = get_asset_identity_auditor()
        meta = {"col1": _full_meta(
            asset_name="Stone Column",
            asset_category="structural",
            asset_role="cluster_member",
            engine="FurnitureClusterBuilder",
        )}
        result = auditor.audit(node_metadata=meta)
        assert result.status == IDENTITY_AUDIT_FAIL
        assert result.records[0].role_category_ok is False


# ===========================================================================
# AssetIdentityAuditor — output fields
# ===========================================================================

class TestOutputFields:

    def test_record_output_fields(self):
        auditor = get_asset_identity_auditor()
        result = auditor.audit(
            node_metadata={"chair_01": _full_meta()},
            node_names={"chair_01": "chair_01"},
            node_paths={"chair_01": "/obj/scene/chair_01"},
        )
        r = result.records[0]
        assert r.asset_path       == "/obj/scene/chair_01"
        assert r.asset_name       == "Wooden Saloon Chair"
        assert r.asset_role       == "cluster_member"
        assert r.asset_category   == "furniture"
        assert r.placement_engine == "FurnitureClusterBuilder"
        assert r.identity_status  == IDENTITY_RESOLVED

    def test_to_dict_has_required_keys(self):
        auditor = get_asset_identity_auditor()
        result = auditor.audit(node_metadata={"c1": _full_meta()})
        d = result.records[0].to_dict()
        for key in ("asset_path", "asset_name", "asset_role", "asset_category",
                    "placement_engine", "identity_status"):
            assert key in d

    def test_audit_result_to_dict(self):
        auditor = get_asset_identity_auditor()
        result = auditor.audit(node_metadata={"c1": _full_meta()})
        d = result.to_dict()
        assert "identity_coverage"   in d
        assert "opaque_assets"       in d
        assert "unclassified_assets" in d
        assert "production_ready"    in d
        assert "records"             in d

    def test_identity_keys_present_count(self):
        auditor = get_asset_identity_auditor()
        result = auditor.audit(node_metadata={"c1": _full_meta()})
        assert result.records[0].identity_keys_present == 3

    def test_determinism(self):
        auditor = get_asset_identity_auditor()
        meta = {"c1": _full_meta(), "b1": _full_meta(asset_id="b1", asset_name="Barrel")}
        r1 = auditor.audit(node_metadata=meta)
        r2 = auditor.audit(node_metadata=meta)
        assert r1.status              == r2.status
        assert r1.identity_coverage   == r2.identity_coverage
        assert r1.resolved_assets     == r2.resolved_assets


# ===========================================================================
# IdentityReview
# ===========================================================================

class TestIdentityReview:

    def _pass_result(self) -> IdentityAuditResult:
        auditor = get_asset_identity_auditor()
        meta = {f"a{i}": _full_meta(asset_id=f"a{i}", asset_name=f"Asset {i}") for i in range(5)}
        return auditor.audit(node_metadata=meta)

    def test_review_pass_result_grade_A_or_B(self):
        reviewer = get_identity_review()
        result   = reviewer.review(self._pass_result())
        assert result.grade in ("A", "B")
        assert result.production_ready is True
        assert result.overall_score >= 0.70

    def test_review_empty_audit_vacuous_pass(self):
        reviewer = get_identity_review()
        auditor  = get_asset_identity_auditor()
        empty    = auditor.audit(node_metadata={})
        result   = reviewer.review(empty)
        assert result.production_ready is True
        assert result.overall_score == 1.0

    def test_review_opaque_assets_blocks_production(self):
        auditor  = get_asset_identity_auditor()
        reviewer = get_identity_review()
        meta = {"xgihfgbqx": _full_meta(asset_id="xgihfgbqx", asset_name="xgihfgbqx")}
        audit  = auditor.audit(node_metadata=meta)
        result = reviewer.review(audit)
        assert result.production_ready is False
        assert any("opaque" in b for b in result.blocking)

    def test_review_unclassified_blocks_production(self):
        auditor  = get_asset_identity_auditor()
        reviewer = get_identity_review()
        bad_meta = dict(_full_meta())
        bad_meta["vibrante_asset_role"]     = ""
        bad_meta["vibrante_asset_category"] = ""
        bad_meta["vibrante_asset_name"]     = ""
        audit  = auditor.audit(
            node_metadata={"c1": bad_meta},
            node_names={"c1": "c1"},
        )
        result = reviewer.review(audit)
        assert result.production_ready is False
        assert any("unclassified" in b for b in result.blocking)

    def test_review_to_dict(self):
        reviewer = get_identity_review()
        auditor  = get_asset_identity_auditor()
        audit    = auditor.audit(node_metadata={"c1": _full_meta()})
        result   = reviewer.review(audit)
        d        = result.to_dict()
        for key in ("overall_score", "grade", "production_ready",
                    "identity_completeness", "name_quality",
                    "role_validity", "classification_rate"):
            assert key in d


# ===========================================================================
# IdentityStatistics
# ===========================================================================

class TestIdentityStatistics:

    def test_record_and_count(self):
        stats = get_identity_statistics()
        stats.record(
            total_assets=3, resolved_assets=3, opaque_assets=0,
            unclassified_assets=0, identity_coverage=1.0, production_ready=True,
        )
        assert stats.count() == 1

    def test_pass_rate_all_pass(self):
        stats = get_identity_statistics()
        for _ in range(4):
            stats.record(
                total_assets=2, resolved_assets=2, opaque_assets=0,
                unclassified_assets=0, identity_coverage=1.0, production_ready=True,
            )
        assert stats.pass_rate() == 1.0

    def test_average_coverage(self):
        stats = get_identity_statistics()
        stats.record(2, 2, 0, 0, 1.0, True)
        stats.record(2, 1, 0, 0, 0.5, False)
        assert abs(stats.average_coverage() - 0.75) < 1e-9

    def test_summary_keys(self):
        stats = get_identity_statistics()
        stats.record(3, 3, 0, 0, 1.0, True)
        s = stats.summary()
        assert "total_runs"       in s
        assert "pass_rate"        in s
        assert "average_coverage" in s

    def test_cap_at_2000(self):
        stats = get_identity_statistics()
        for _ in range(2100):
            stats.record(1, 1, 0, 0, 1.0, True)
        assert stats.count() == 2000


# ===========================================================================
# IdentitySerializer
# ===========================================================================

class TestIdentitySerializer:

    def test_serialize_audit_valid_json(self):
        import json
        auditor    = get_asset_identity_auditor()
        serializer = get_identity_serializer()
        result     = auditor.audit(node_metadata={"c1": _full_meta()})
        s          = serializer.serialize_audit(result)
        d          = json.loads(s)
        assert "identity_coverage" in d
        assert "_schema_version"   in d

    def test_serialize_review_valid_json(self):
        import json
        auditor    = get_asset_identity_auditor()
        reviewer   = get_identity_review()
        serializer = get_identity_serializer()
        audit  = auditor.audit(node_metadata={"c1": _full_meta()})
        review = reviewer.review(audit)
        s      = serializer.serialize_review(review)
        d      = json.loads(s)
        assert "grade" in d
        assert "production_ready" in d

    def test_sorted_keys(self):
        import json
        auditor    = get_asset_identity_auditor()
        serializer = get_identity_serializer()
        result     = auditor.audit(node_metadata={"c1": _full_meta()})
        raw        = serializer.serialize_audit(result)
        d          = json.loads(raw)
        keys       = list(d.keys())
        assert keys == sorted(keys)

    def test_deserialize_audit(self):
        auditor    = get_asset_identity_auditor()
        serializer = get_identity_serializer()
        result     = auditor.audit(node_metadata={"c1": _full_meta()})
        s          = serializer.serialize_audit(result)
        d          = serializer.deserialize_audit(s)
        assert isinstance(d, dict)
        assert "identity_coverage" in d
