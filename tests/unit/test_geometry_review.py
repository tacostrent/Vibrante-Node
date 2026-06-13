"""Tests for GeometryReview (Tier 9.7)."""
import pytest
from src.runtime.assets.geometry import (
    AssetMetrics,
    SupportSurface,
    GroundContact,
    get_geometry_review,
    reset_geometry_review_for_tests,
    GeometryReviewResult,
)


@pytest.fixture(autouse=True)
def reset():
    reset_geometry_review_for_tests()
    yield
    reset_geometry_review_for_tests()


def _table_metrics(source="explicit") -> AssetMetrics:
    return AssetMetrics(
        asset_id    = "tbl1",
        width_m     = 1.2,
        height_m    = 0.75,
        depth_m     = 0.8,
        volume_m3   = 0.72,
        footprint_m2 = 0.96,
        placement_radius = 0.6,
        bbox_min    = [0.0, 0.0, 0.0],
        bbox_max    = [1.2, 0.75, 0.8],
        pivot_type  = "bottom_center",
        scale_class = "large",
        role        = "furniture",
        placement_type = "table",
        is_structural  = False,
        is_hero        = False,
        source         = source,
        support_surfaces = [SupportSurface(surface_type="tabletop", height_m=0.75, area_m2=0.816)],
        ground_contacts  = [GroundContact(contact_type="leg", count=4,
                                          positions=[[-0.5,0,-0.35],[0.5,0,-0.35],
                                                     [-0.5,0,0.35],[0.5,0,0.35]])],
    )


def _beam_metrics() -> AssetMetrics:
    return AssetMetrics(
        asset_id    = "beam1",
        width_m     = 4.0,
        height_m    = 0.3,
        depth_m     = 0.3,
        volume_m3   = 0.36,
        footprint_m2 = 1.2,
        placement_radius = 2.0,
        bbox_min    = [0.0, 0.0, 0.0],
        bbox_max    = [4.0, 0.3, 0.3],
        pivot_type  = "bottom_left",
        scale_class = "structural",
        role        = "structure",
        placement_type = "beam",
        is_structural  = True,
        is_hero        = False,
        source         = "explicit",
        support_surfaces = [],
        ground_contacts  = [GroundContact(contact_type="base_plane", count=1,
                                          positions=[[0.0, 0.0, 0.0]])],
    )


class TestGradeMapping:
    def test_grade_a_table(self):
        result = get_geometry_review().review(_table_metrics())
        # Well-specified table should score well
        assert result.grade in ("A", "B")
        assert result.production_ready is True

    def test_grade_b_estimated_source(self):
        m = _table_metrics(source="estimated")
        result = get_geometry_review().review(m)
        # Estimated source reduces bbox score by 25%
        assert result.overall_score > 0.0

    def test_grade_f_zero_dimensions(self):
        m = AssetMetrics(
            asset_id    = "bad1",
            width_m     = 0.0,
            height_m    = 0.0,
            depth_m     = 0.0,
            placement_type = "table",
        )
        result = get_geometry_review().review(m)
        assert result.production_ready is False
        assert any("zero dimensions" in f for f in result.findings)


class TestBboxValidity:
    def test_explicit_source_high_score(self):
        result = get_geometry_review().review(_table_metrics(source="explicit"))
        assert result.bbox_validity >= 0.9

    def test_estimated_source_lower_score(self):
        result = get_geometry_review().review(_table_metrics(source="estimated"))
        assert result.bbox_validity < 0.9

    def test_zero_dims_blocks(self):
        m = AssetMetrics(width_m=0.0, height_m=0.0, depth_m=0.0, placement_type="chair")
        result = get_geometry_review().review(m)
        assert result.bbox_validity == 0.0
        assert result.production_ready is False


class TestPivotValidity:
    def test_correct_pivot_table(self):
        m = _table_metrics()
        m.pivot_type = "bottom_center"
        result = get_geometry_review().review(m)
        assert result.pivot_validity >= 0.9

    def test_hanging_light_top_center(self):
        m = AssetMetrics(
            asset_id    = "hl1",
            width_m     = 0.3, height_m=0.5, depth_m=0.3,
            placement_type = "hanging_light",
            pivot_type  = "top_center",
            scale_class = "small",
            role        = "prop",
            source      = "explicit",
        )
        result = get_geometry_review().review(m)
        assert result.pivot_validity >= 0.9

    def test_wrong_pivot_for_hanging_light(self):
        m = AssetMetrics(
            asset_id = "hl2",
            width_m=0.3, height_m=0.5, depth_m=0.3,
            placement_type="hanging_light",
            pivot_type="bottom_center",
            scale_class="small", role="prop", source="explicit",
        )
        result = get_geometry_review().review(m)
        assert result.pivot_validity < 0.9


class TestSurfaceDetection:
    def test_table_with_surfaces_scores_full(self):
        result = get_geometry_review().review(_table_metrics())
        assert result.surface_detection == 1.0

    def test_table_without_surfaces_blocks(self):
        m = _table_metrics()
        m.support_surfaces = []
        result = get_geometry_review().review(m)
        assert result.surface_detection == 0.0
        assert result.production_ready is False
        assert any("no support surfaces" in f for f in result.findings)

    def test_chair_without_surfaces_scores_full(self):
        m = AssetMetrics(
            asset_id="ch1", width_m=0.55, height_m=0.9, depth_m=0.55,
            placement_type="chair", scale_class="medium", role="furniture",
            source="explicit",
            support_surfaces=[],
            ground_contacts=[GroundContact("leg", 4, [], "")],
        )
        result = get_geometry_review().review(m)
        assert result.surface_detection == 1.0   # chair is not a surface-provider


class TestGroundContactDetection:
    def test_four_leg_contacts_score_high(self):
        result = get_geometry_review().review(_table_metrics())
        assert result.ground_contact_detection >= 0.9

    def test_hanging_light_no_contacts_scores_full(self):
        m = AssetMetrics(
            asset_id="hl3", width_m=0.3, height_m=0.5, depth_m=0.3,
            placement_type="hanging_light", scale_class="small", role="prop",
            source="explicit", support_surfaces=[], ground_contacts=[],
        )
        result = get_geometry_review().review(m)
        assert result.ground_contact_detection == 1.0


class TestScaleAccuracy:
    def test_valid_beam_structural_role(self):
        result = get_geometry_review().review(_beam_metrics())
        assert result.scale_accuracy >= 0.9

    def test_beam_with_furniture_role_blocks(self):
        m = _beam_metrics()
        m.role = "furniture"
        result = get_geometry_review().review(m)
        assert result.scale_accuracy == 0.0
        assert result.production_ready is False
        assert any("invalid role" in f for f in result.findings)

    def test_chair_with_structure_role_blocks(self):
        m = AssetMetrics(
            asset_id="ch_bad", width_m=0.55, height_m=0.9, depth_m=0.55,
            placement_type="chair", scale_class="medium", role="structure",
            source="explicit",
            support_surfaces=[],
            ground_contacts=[GroundContact("leg", 4, [], "")],
        )
        result = get_geometry_review().review(m)
        assert result.scale_accuracy == 0.0
        assert any("invalid role" in f for f in result.findings)

    def test_valid_furniture_type_and_role(self):
        result = get_geometry_review().review(_table_metrics())
        assert result.scale_accuracy == 1.0


class TestReturnType:
    def test_returns_geometry_review_result(self):
        result = get_geometry_review().review(_table_metrics())
        assert isinstance(result, GeometryReviewResult)

    def test_to_dict_serializable(self):
        result = get_geometry_review().review(_table_metrics())
        d = result.to_dict()
        assert "overall_score"     in d
        assert "grade"             in d
        assert "production_ready"  in d
        assert "bbox_validity"     in d
        assert "pivot_validity"    in d
        assert "surface_detection" in d
        assert "ground_contact_detection" in d
        assert "scale_accuracy"    in d

    def test_recommendations_present(self):
        result = get_geometry_review().review(_table_metrics())
        assert isinstance(result.recommendations, list)
        assert len(result.recommendations) >= 1

    def test_review_summary_present(self):
        result = get_geometry_review().review(_table_metrics())
        assert isinstance(result.review_summary, str)
        assert len(result.review_summary) > 0

    def test_no_raise_on_empty_metrics(self):
        m = AssetMetrics()
        result = get_geometry_review().review(m)
        assert isinstance(result, GeometryReviewResult)
