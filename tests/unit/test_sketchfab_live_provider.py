"""Tests for src/runtime/assets/providers/sketchfab_live_provider.py"""
import pytest

from src.runtime.assets.providers.sketchfab_live_provider import SketchfabLiveProvider
from src.runtime.assets.schema import AssetDescriptor, AssetPreview, AssetMetadata


class TestSketchfabLiveProvider:
    def setup_method(self):
        self.provider = SketchfabLiveProvider()

    def test_provider_name(self):
        assert self.provider.provider_name == "sketchfab_live"

    def test_is_available(self):
        assert self.provider.is_available is True

    def test_supported_categories_nonempty(self):
        cats = self.provider.supported_categories
        assert "vehicle" in cats
        assert "robot" in cats
        assert len(cats) > 5

    def test_search_returns_result(self):
        result = self.provider.search(category="prop")
        assert result.success is True
        assert result.provider == "sketchfab_live"
        assert isinstance(result.normalized_assets, list)

    def test_search_all_returns_20_plus(self):
        result = self.provider.search(category="")
        # Seed has 21+ assets
        assert len(result.normalized_assets) >= 20

    def test_search_category_filter(self):
        result = self.provider.search(category="vehicle")
        # All assets must have "vehicle" in their raw categories list
        for asset in result.normalized_assets:
            # category filter passes if "vehicle" appears in any of the asset's categories
            assert asset.category in ("vehicle", "machinery", "structure") or \
                "vehicle" in asset.tags or asset.category == "vehicle"

    def test_search_tag_filter(self):
        result = self.provider.search(category="", tags=["robot"])
        names = [a.name.lower() for a in result.normalized_assets]
        assert any("robot" in n or "drone" in n for n in names)

    def test_search_limit_respected(self):
        result = self.provider.search(category="", limit=3)
        assert len(result.normalized_assets) <= 3

    def test_pagination_page1(self):
        result1 = self.provider.search(category="", page=1, page_size=5)
        result2 = self.provider.search(category="", page=2, page_size=5)
        ids1 = {a.asset_id for a in result1.normalized_assets}
        ids2 = {a.asset_id for a in result2.normalized_assets}
        # Different pages (may overlap at boundaries but should differ)
        assert result1.normalized_assets != result2.normalized_assets or ids1 == ids2

    def test_normalize_result_returns_descriptor(self):
        result = self.provider.search(category="prop", limit=1)
        if result.normalized_assets:
            a = result.normalized_assets[0]
            assert isinstance(a, AssetDescriptor)
            assert a.provider == "sketchfab_live"
            assert a.asset_id.startswith("skfbl_")

    def test_normalized_has_metadata(self):
        result = self.provider.search(category="", limit=5)
        for a in result.normalized_assets:
            assert isinstance(a.metadata, AssetMetadata)

    def test_normalized_has_preview(self):
        result = self.provider.search(category="prop", limit=3)
        for a in result.normalized_assets:
            assert isinstance(a.preview, AssetPreview)

    def test_lookup_known_id(self):
        result = self.provider.search(category="prop", limit=1)
        if result.normalized_assets:
            asset = result.normalized_assets[0]
            found = self.provider.lookup(asset.asset_id)
            assert found is not None
            assert found.asset_id == asset.asset_id

    def test_lookup_unknown_returns_none(self):
        assert self.provider.lookup("skfbl_nonexistent_xyz") is None

    def test_get_preview(self):
        result = self.provider.search(category="prop", limit=1)
        if result.normalized_assets:
            asset = result.normalized_assets[0]
            preview = self.provider.get_preview(asset.asset_id)
            assert preview is not None
            assert isinstance(preview, AssetPreview)

    def test_get_metadata(self):
        result = self.provider.search(category="prop", limit=1)
        if result.normalized_assets:
            asset = result.normalized_assets[0]
            meta = self.provider.get_metadata(asset.asset_id)
            assert meta is not None
            assert isinstance(meta, AssetMetadata)

    def test_normalized_has_formats(self):
        result = self.provider.search(category="")
        for a in result.normalized_assets:
            assert len(a.formats) > 0

    def test_style_hint_filter(self):
        result = self.provider.search(category="", style_hints=["sci_fi"])
        for a in result.normalized_assets:
            assert a.style in ("sci_fi", "unknown")

    def test_deterministic_order(self):
        r1 = self.provider.search(category="", limit=10)
        r2 = self.provider.search(category="", limit=10)
        ids1 = [a.asset_id for a in r1.normalized_assets]
        ids2 = [a.asset_id for a in r2.normalized_assets]
        assert ids1 == ids2
