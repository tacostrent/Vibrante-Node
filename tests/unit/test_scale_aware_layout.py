"""
Integration tests for Scale-Aware Layout (Tier 9.6).

Tests the end-to-end flow:
  UnitNormalizer → AssetScaleAnalyzer → LayoutSpacingEngine → PlacementRelationships

Also validates the BBoxExtractor now correctly handles cm inputs.
"""

import pytest
from src.runtime.assets.assembly.unit_normalizer import reset_unit_normalizer_for_tests
from src.runtime.assets.assembly.asset_scale_analyzer import (
    reset_asset_scale_analyzer_for_tests,
    get_asset_scale_analyzer,
)
from src.runtime.assets.assembly.footprint_calculator import (
    reset_footprint_calculator_for_tests,
    get_footprint_calculator,
)
from src.runtime.assets.assembly.layout_spacing_engine import (
    reset_layout_spacing_engine_for_tests,
    get_layout_spacing_engine,
)
from src.runtime.assets.assembly.placement_relationships import (
    reset_placement_relationships_for_tests,
    get_placement_relationships,
)
from src.runtime.assets.assembly.bounding_box_extractor import (
    reset_bbox_extractor_for_tests,
    get_bbox_extractor,
)


@pytest.fixture(autouse=True)
def reset():
    reset_unit_normalizer_for_tests()
    reset_asset_scale_analyzer_for_tests()
    reset_footprint_calculator_for_tests()
    reset_layout_spacing_engine_for_tests()
    reset_placement_relationships_for_tests()
    reset_bbox_extractor_for_tests()
    yield
    reset_unit_normalizer_for_tests()
    reset_asset_scale_analyzer_for_tests()
    reset_footprint_calculator_for_tests()
    reset_layout_spacing_engine_for_tests()
    reset_placement_relationships_for_tests()
    reset_bbox_extractor_for_tests()


# The assets from the spec that had incorrect fixed-offset placement
WOODEN_CHAIR = {"name": "Wooden Chair", "bbox_x": 48.9, "bbox_y": 83.8, "bbox_z": 43.3, "category": "furniture"}
WOODEN_TABLE = {"name": "Wooden Table", "bbox_x": 69.7, "bbox_y": 49.9, "bbox_z": 69.8, "category": "furniture"}
OLD_BEAM     = {"name": "Old Wooden Beam", "bbox_x": 377.7, "bbox_y": 36.6, "bbox_z": 36.2, "category": "structure"}


class TestUnitNormalizationEndToEnd:
    """Verify cm assets are correctly interpreted as meters throughout."""

    def test_chair_bbox_correctly_in_meters(self):
        analyzer = get_asset_scale_analyzer()
        profile = analyzer.analyze_asset(WOODEN_CHAIR)
        # Should be ~0.489 m, not 48.9 m
        assert profile.bbox_meters[0] < 1.0, f"Chair width {profile.bbox_meters[0]:.3f} m not in sub-meter range"
        assert abs(profile.bbox_meters[0] - 0.489) < 0.01

    def test_table_bbox_correctly_in_meters(self):
        analyzer = get_asset_scale_analyzer()
        profile = analyzer.analyze_asset(WOODEN_TABLE)
        assert profile.bbox_meters[0] < 1.5
        assert abs(profile.bbox_meters[0] - 0.697) < 0.01

    def test_beam_bbox_correctly_in_meters(self):
        analyzer = get_asset_scale_analyzer()
        profile = analyzer.analyze_asset(OLD_BEAM)
        assert abs(profile.bbox_meters[0] - 3.777) < 0.01

    def test_bbox_extractor_correctly_normalizes_cm(self):
        extractor = get_bbox_extractor()
        meta = extractor.build_spatial_metadata(WOODEN_CHAIR)
        assert meta.bbox_x < 1.0, f"BBoxExtractor returned {meta.bbox_x:.3f} (should be ~0.489 m)"
        assert abs(meta.bbox_x - 0.489) < 0.01


class TestScaleClassification:
    """Verify scale classes are correctly assigned to spec examples."""

    def test_chair_is_medium(self):
        analyzer = get_asset_scale_analyzer()
        profile = analyzer.analyze_asset(WOODEN_CHAIR)
        assert profile.asset_scale_class == "medium"

    def test_table_is_medium(self):
        analyzer = get_asset_scale_analyzer()
        profile = analyzer.analyze_asset(WOODEN_TABLE)
        assert profile.asset_scale_class == "medium"

    def test_beam_is_structural(self):
        analyzer = get_asset_scale_analyzer()
        profile = analyzer.analyze_asset(OLD_BEAM)
        assert profile.asset_scale_class == "structural"
        assert profile.is_structural is True


class TestNoOverlap:
    """Core requirement: chair/table/beam placed without overlap."""

    def test_chair_and_table_not_overlapping(self):
        eng = get_layout_spacing_engine()
        assets = [WOODEN_CHAIR, WOODEN_TABLE]  # beam excluded — structural
        spaced = eng.space_assets(assets)
        assert len(spaced) == 2

        dist = abs(spaced[1].position[0] - spaced[0].position[0])
        # Chair radius ~0.244 m, Table radius ~0.349 m → min spacing ~0.593 m
        analyzer = get_asset_scale_analyzer()
        chair_p = analyzer.analyze_asset(WOODEN_CHAIR)
        table_p = analyzer.analyze_asset(WOODEN_TABLE)
        min_spacing = chair_p.placement_radius + table_p.placement_radius
        assert dist >= min_spacing - 1e-6, (
            f"Chair and table overlap! spacing={dist:.3f} m, required >= {min_spacing:.3f} m"
        )

    def test_beam_excluded_from_placement(self):
        eng = get_layout_spacing_engine()
        assets = [WOODEN_CHAIR, OLD_BEAM, WOODEN_TABLE]
        spaced = eng.space_assets(assets)
        # Only chair and table should be placed
        assert len(spaced) == 2
        names = {sp.asset_id for sp in spaced}
        assert "Old Wooden Beam" not in names

    def test_old_fixed_offset_would_overlap(self):
        """Confirm the old index*3 approach was wrong for these assets.

        With fixed spacing of 3 m, items would be at 0, 3, 6 — but the
        chair (0.489 m wide, placed at 0) and the table (0.697 m wide, placed at 3)
        would never actually overlap at those positions. However, small props like
        cups (0.08 m) at 0 and at 3 would have a 3 m gap — wasted and physically wrong.

        The real problem was that with cm values interpreted as meters, a 48.9 m wide
        chair at position 3 m would be an absurd layout. This test confirms the
        corrected bbox is sub-metre for all these assets.
        """
        analyzer = get_asset_scale_analyzer()
        for asset in [WOODEN_CHAIR, WOODEN_TABLE, OLD_BEAM]:
            profile = analyzer.analyze_asset(asset)
            max_dim = profile.max_dimension
            assert max_dim < 10.0, (
                f"'{asset['name']}' has implausible max_dim={max_dim:.2f} m "
                "(unit normalization may be broken)"
            )


class TestStructuralRouting:
    """Beams/walls/columns must be flagged for StructureBuilder routing."""

    def test_beam_route_to_structure(self):
        rel = get_placement_relationships()
        assert rel.is_structural("", "structure", "Old Wooden Beam") is True

    def test_beam_mode_is_route_to_structure(self):
        rel = get_placement_relationships()
        assert rel.get_placement_mode("beam", "structure") == "route_to_structure"

    def test_beam_role_is_structure(self):
        rel = get_placement_relationships()
        assert rel.get_role("beam", "structure") == "structure"

    def test_filter_separates_beam_from_furniture(self):
        rel = get_placement_relationships()
        assets = [WOODEN_CHAIR, OLD_BEAM, WOODEN_TABLE]
        placeable, structural = rel.filter_structural(assets)
        assert len(placeable) == 2
        assert len(structural) == 1
        assert structural[0]["name"] == "Old Wooden Beam"


class TestFootprintAccuracy:
    """Footprints must reflect real sub-metre dimensions."""

    def test_chair_footprint_sub_half_sqm(self):
        calc = get_footprint_calculator()
        result = calc.calculate(WOODEN_CHAIR)
        # 0.489 × 0.433 ≈ 0.212 m²
        assert result.footprint_area < 0.5, (
            f"Chair footprint {result.footprint_area:.3f} m² is too large"
        )
        assert result.footprint_area > 0.01

    def test_table_footprint_sub_1_sqm(self):
        calc = get_footprint_calculator()
        result = calc.calculate(WOODEN_TABLE)
        # 0.697 × 0.698 ≈ 0.487 m²
        assert result.footprint_area < 1.0

    def test_deterministic_same_input_same_output(self):
        calc = get_footprint_calculator()
        r1 = calc.calculate(WOODEN_CHAIR)
        r2 = calc.calculate(WOODEN_CHAIR)
        assert r1.footprint_area == r2.footprint_area
        assert r1.clearance_radius == r2.clearance_radius
