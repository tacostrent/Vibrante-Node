"""Tests for src/runtime/assets/metadata/asset_semantic_mapper.py"""
import pytest

from src.runtime.assets.metadata.asset_semantic_mapper import (
    AssetSemanticMapper,
    SemanticProfile,
    get_asset_semantic_mapper,
    reset_asset_semantic_mapper_for_tests,
)
from src.runtime.assets.metadata.asset_metadata_enricher import reset_asset_metadata_enricher_for_tests
from src.runtime.assets.schema import AssetDescriptor, ASSET_CATEGORIES, ASSET_STYLES


def _make_asset(
    asset_id="a1", provider="test", name="Test", category="prop",
    tags=None, style="unknown", environments=None,
) -> AssetDescriptor:
    return AssetDescriptor(
        asset_id=asset_id,
        provider=provider,
        name=name,
        category=category,
        tags=tags or [],
        style=style,
        environment_suitability=environments or [],
    )


@pytest.fixture(autouse=True)
def reset():
    reset_asset_semantic_mapper_for_tests()
    reset_asset_metadata_enricher_for_tests()
    yield
    reset_asset_semantic_mapper_for_tests()
    reset_asset_metadata_enricher_for_tests()


class TestSingleton:
    def test_singleton_identity(self):
        m1 = get_asset_semantic_mapper()
        m2 = get_asset_semantic_mapper()
        assert m1 is m2


class TestMapEnvironments:
    def test_includes_existing_environments(self):
        asset = _make_asset(environments=["industrial_hangar"])
        mapper = get_asset_semantic_mapper()
        envs = mapper.map_environments(asset)
        assert "industrial_hangar" in envs

    def test_adds_inferred_environments(self):
        asset = _make_asset(tags=["pipe", "industrial"])
        mapper = get_asset_semantic_mapper()
        envs = mapper.map_environments(asset)
        assert "industrial_hangar" in envs

    def test_no_duplicates(self):
        asset = _make_asset(tags=["pipe"], environments=["industrial_hangar"])
        mapper = get_asset_semantic_mapper()
        envs = mapper.map_environments(asset)
        assert envs.count("industrial_hangar") == 1


class TestMapCategories:
    def test_includes_primary_category(self):
        asset = _make_asset(category="vehicle")
        mapper = get_asset_semantic_mapper()
        cats = mapper.map_categories(asset)
        assert "vehicle" in cats

    def test_all_returned_are_valid(self):
        asset = _make_asset(category="prop", tags=["robot", "machinery"])
        mapper = get_asset_semantic_mapper()
        cats = mapper.map_categories(asset)
        for c in cats:
            assert c in ASSET_CATEGORIES

    def test_sorted_result(self):
        asset = _make_asset(category="robot", tags=["vehicle", "prop"])
        mapper = get_asset_semantic_mapper()
        cats = mapper.map_categories(asset)
        assert cats == sorted(cats)


class TestMapStyles:
    def test_existing_valid_style_included(self):
        asset = _make_asset(style="sci_fi")
        mapper = get_asset_semantic_mapper()
        styles = mapper.map_styles(asset)
        assert "sci_fi" in styles

    def test_unknown_style_not_included(self):
        asset = _make_asset(style="unknown")
        mapper = get_asset_semantic_mapper()
        styles = mapper.map_styles(asset)
        assert "unknown" not in styles

    def test_sorted_result(self):
        asset = _make_asset(style="sci_fi", tags=["rusted"])
        mapper = get_asset_semantic_mapper()
        styles = mapper.map_styles(asset)
        assert styles == sorted(styles)


class TestMapRelationships:
    def test_no_relationships_for_empty_list(self):
        asset = _make_asset()
        mapper = get_asset_semantic_mapper()
        rels = mapper.map_relationships(asset, [])
        assert rels == []

    def test_same_environment_found(self):
        asset1 = _make_asset(asset_id="a1", environments=["industrial_hangar"])
        asset2 = _make_asset(asset_id="a2", environments=["industrial_hangar"])
        mapper = get_asset_semantic_mapper()
        rels = mapper.map_relationships(asset1, [asset2])
        rel_types = [r["rel_type"] for r in rels]
        assert "same_environment" in rel_types

    def test_same_style_found(self):
        asset1 = _make_asset(asset_id="a1", style="sci_fi")
        asset2 = _make_asset(asset_id="a2", style="sci_fi")
        mapper = get_asset_semantic_mapper()
        rels = mapper.map_relationships(asset1, [asset2])
        rel_types = [r["rel_type"] for r in rels]
        assert "same_style" in rel_types

    def test_same_category_found(self):
        asset1 = _make_asset(asset_id="a1", category="robot")
        asset2 = _make_asset(asset_id="a2", category="robot")
        mapper = get_asset_semantic_mapper()
        rels = mapper.map_relationships(asset1, [asset2])
        rel_types = [r["rel_type"] for r in rels]
        assert "same_category" in rel_types

    def test_self_not_related(self):
        asset = _make_asset(asset_id="a1", environments=["industrial_hangar"])
        mapper = get_asset_semantic_mapper()
        rels = mapper.map_relationships(asset, [asset])
        # Should not create self-relationship
        assert all(r["target_id"] != asset.asset_id for r in rels)


class TestBuildSemanticProfile:
    def test_returns_semantic_profile(self):
        asset = _make_asset(tags=["pipe"], environments=["industrial_hangar"])
        mapper = get_asset_semantic_mapper()
        profile = mapper.build_semantic_profile(asset)
        assert isinstance(profile, SemanticProfile)
        assert profile.asset_id == asset.asset_id

    def test_profile_to_dict(self):
        asset = _make_asset()
        mapper = get_asset_semantic_mapper()
        profile = mapper.build_semantic_profile(asset)
        d = profile.to_dict()
        assert "asset_id" in d
        assert "environments" in d
        assert "categories" in d
        assert "styles" in d
        assert "relationships" in d
        assert "usage_hints" in d
        assert "confidence" in d

    def test_confidence_range(self):
        asset = _make_asset(tags=["pipe", "industrial"], environments=["industrial_hangar"], style="photorealistic")
        mapper = get_asset_semantic_mapper()
        profile = mapper.build_semantic_profile(asset)
        assert 0.0 <= profile.confidence <= 1.0

    def test_increments_profile_count(self):
        mapper = get_asset_semantic_mapper()
        initial = mapper.get_statistics()["profile_count"]
        mapper.build_semantic_profile(_make_asset())
        assert mapper.get_statistics()["profile_count"] == initial + 1


class TestBatchMap:
    def test_batch_returns_all_profiles(self):
        assets = [_make_asset(asset_id=f"a{i}") for i in range(5)]
        mapper = get_asset_semantic_mapper()
        profiles = mapper.batch_map(assets)
        assert len(profiles) == 5

    def test_batch_increments_mapped_count(self):
        mapper = get_asset_semantic_mapper()
        initial = mapper.get_statistics()["mapped_count"]
        assets = [_make_asset(asset_id=f"a{i}") for i in range(3)]
        mapper.batch_map(assets)
        assert mapper.get_statistics()["mapped_count"] == initial + 3

    def test_batch_detects_relationships(self):
        assets = [
            _make_asset(asset_id="a1", category="robot", environments=["robotics_lab"]),
            _make_asset(asset_id="a2", category="robot", environments=["robotics_lab"]),
        ]
        mapper = get_asset_semantic_mapper()
        profiles = mapper.batch_map(assets)
        # Both profiles should have relationships
        rel_counts = [len(p.relationships) for p in profiles]
        assert any(c > 0 for c in rel_counts)


class TestStatistics:
    def test_statistics_structure(self):
        mapper = get_asset_semantic_mapper()
        s = mapper.get_statistics()
        assert "mapped_count" in s
        assert "profile_count" in s
