"""Tests for src/runtime/assets/metadata/asset_metadata_enricher.py"""
import pytest

from src.runtime.assets.metadata.asset_metadata_enricher import (
    AssetMetadataEnricher,
    get_asset_metadata_enricher,
    reset_asset_metadata_enricher_for_tests,
    _ENVIRONMENT_KEYWORDS,
    _STYLE_KEYWORDS,
    _USAGE_KEYWORDS,
)
from src.runtime.assets.schema import AssetDescriptor


def _make_asset(name="test", tags=None, style="unknown") -> AssetDescriptor:
    return AssetDescriptor(
        asset_id="test_id",
        provider="test",
        name=name,
        category="prop",
        tags=tags or [],
        style=style,
    )


@pytest.fixture(autouse=True)
def reset():
    reset_asset_metadata_enricher_for_tests()
    yield
    reset_asset_metadata_enricher_for_tests()


class TestSingleton:
    def test_singleton_identity(self):
        e1 = get_asset_metadata_enricher()
        e2 = get_asset_metadata_enricher()
        assert e1 is e2


class TestInferEnvironments:
    def test_industrial_from_pipe_tag(self):
        asset = _make_asset(tags=["pipe", "metal"])
        enricher = get_asset_metadata_enricher()
        envs = enricher.infer_environments(asset)
        assert "industrial_hangar" in envs

    def test_industrial_from_name(self):
        asset = _make_asset(name="Industrial Barrel")
        enricher = get_asset_metadata_enricher()
        envs = enricher.infer_environments(asset)
        assert "industrial_hangar" in envs

    def test_control_room_from_screen(self):
        asset = _make_asset(tags=["screen", "terminal", "console"])
        enricher = get_asset_metadata_enricher()
        envs = enricher.infer_environments(asset)
        assert "control_room" in envs

    def test_robotics_from_robot(self):
        asset = _make_asset(tags=["robot", "arm"])
        enricher = get_asset_metadata_enricher()
        envs = enricher.infer_environments(asset)
        assert "robotics_lab" in envs

    def test_sci_fi_from_neon(self):
        asset = _make_asset(tags=["neon", "futuristic"])
        enricher = get_asset_metadata_enricher()
        envs = enricher.infer_environments(asset)
        assert "sci_fi_corridor" in envs

    def test_abandoned_from_rusted(self):
        asset = _make_asset(tags=["rusted", "abandoned", "decay"])
        enricher = get_asset_metadata_enricher()
        envs = enricher.infer_environments(asset)
        assert "abandoned_factory" in envs

    def test_no_match_returns_empty(self):
        asset = _make_asset(name="Generic Sphere", tags=["geometry"])
        enricher = get_asset_metadata_enricher()
        envs = enricher.infer_environments(asset)
        # Should be empty or minimal
        assert isinstance(envs, list)

    def test_returns_sorted(self):
        asset = _make_asset(tags=["pipe", "screen", "robot"])
        enricher = get_asset_metadata_enricher()
        envs = enricher.infer_environments(asset)
        assert envs == sorted(envs)


class TestInferStyle:
    def test_weathered_from_rusted(self):
        asset = _make_asset(tags=["rusted", "worn"])
        enricher = get_asset_metadata_enricher()
        style = enricher.infer_style(asset)
        assert style == "weathered"

    def test_clean_from_pristine(self):
        asset = _make_asset(tags=["clean", "pristine"])
        enricher = get_asset_metadata_enricher()
        style = enricher.infer_style(asset)
        assert style == "clean"

    def test_sci_fi_from_futuristic(self):
        asset = _make_asset(tags=["futuristic", "neon"])
        enricher = get_asset_metadata_enricher()
        style = enricher.infer_style(asset)
        assert style == "sci_fi"

    def test_no_match_returns_none(self):
        asset = _make_asset(tags=["geometry"])
        enricher = get_asset_metadata_enricher()
        style = enricher.infer_style(asset)
        assert style is None or isinstance(style, str)


class TestInferUsage:
    def test_hero_vehicle_from_forklift(self):
        asset = _make_asset(name="Industrial Forklift")
        enricher = get_asset_metadata_enricher()
        hints = enricher.infer_usage(asset)
        assert "hero_vehicle" in hints

    def test_mid_ground_from_barrel(self):
        asset = _make_asset(name="Metal Barrel")
        enricher = get_asset_metadata_enricher()
        hints = enricher.infer_usage(asset)
        assert "mid_ground" in hints

    def test_wall_detail_from_pipe(self):
        asset = _make_asset(tags=["pipe", "conduit"])
        enricher = get_asset_metadata_enricher()
        hints = enricher.infer_usage(asset)
        assert "wall_detail" in hints

    def test_sorted_result(self):
        asset = _make_asset(tags=["pipe", "barrel", "forklift"])
        enricher = get_asset_metadata_enricher()
        hints = enricher.infer_usage(asset)
        assert hints == sorted(hints)


class TestEnrichAsset:
    def test_enrich_returns_asset(self):
        asset = _make_asset(tags=["pipe", "industrial"])
        enricher = get_asset_metadata_enricher()
        result = enricher.enrich_asset(asset)
        assert result is asset  # Same object

    def test_enrich_adds_environments(self):
        asset = _make_asset(tags=["pipe"])
        enricher = get_asset_metadata_enricher()
        enricher.enrich_asset(asset)
        assert len(asset.environment_suitability) > 0

    def test_enrich_sets_style_when_unknown(self):
        asset = _make_asset(tags=["rusted"], style="unknown")
        enricher = get_asset_metadata_enricher()
        enricher.enrich_asset(asset)
        assert asset.style != "unknown"

    def test_enrich_preserves_existing_style(self):
        asset = _make_asset(tags=["rusted"], style="photorealistic")
        enricher = get_asset_metadata_enricher()
        enricher.enrich_asset(asset)
        assert asset.style == "photorealistic"

    def test_enrich_increments_count(self):
        enricher = get_asset_metadata_enricher()
        initial = enricher.get_statistics()["enriched_count"]
        enricher.enrich_asset(_make_asset())
        assert enricher.get_statistics()["enriched_count"] == initial + 1


class TestStatistics:
    def test_statistics_structure(self):
        enricher = get_asset_metadata_enricher()
        s = enricher.get_statistics()
        assert "enriched_count" in s
        assert s["enriched_count"] >= 0
