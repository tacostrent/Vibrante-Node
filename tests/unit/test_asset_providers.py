"""
Tests for src/runtime/assets/providers/
"""

import pytest

from src.runtime.assets.providers import (
    AssetProvider,
    ProviderRegistry,
    get_provider_registry,
    reset_provider_registry_for_tests,
    SketchfabProvider,
    PolyhavenProvider,
    LocalLibraryProvider,
)
from src.runtime.assets.schema import AssetDescriptor


@pytest.fixture(autouse=True)
def reset_registry():
    reset_provider_registry_for_tests()
    yield
    reset_provider_registry_for_tests()


# ---------------------------------------------------------------------------
# ProviderRegistry
# ---------------------------------------------------------------------------

class TestProviderRegistry:
    def test_singleton_identity(self):
        r1 = get_provider_registry()
        r2 = get_provider_registry()
        assert r1 is r2

    def test_register_and_get(self):
        reg = get_provider_registry()
        p = SketchfabProvider()
        reg.register(p)
        assert reg.get("sketchfab") is p

    def test_register_replaces(self):
        reg = get_provider_registry()
        p1 = SketchfabProvider()
        p2 = SketchfabProvider()
        reg.register(p1)
        reg.register(p2)
        assert reg.get("sketchfab") is p2

    def test_deregister(self):
        reg = get_provider_registry()
        reg.register(SketchfabProvider())
        assert reg.deregister("sketchfab") is True
        assert reg.get("sketchfab") is None

    def test_deregister_unknown(self):
        reg = get_provider_registry()
        assert reg.deregister("nonexistent") is False

    def test_all_providers(self):
        reg = get_provider_registry()
        reg.register(SketchfabProvider())
        reg.register(PolyhavenProvider())
        names = {p.provider_name for p in reg.all_providers()}
        assert "sketchfab" in names
        assert "polyhaven" in names

    def test_available_providers(self):
        reg = get_provider_registry()
        reg.register(SketchfabProvider())
        available = reg.available_providers()
        assert len(available) == 1

    def test_providers_for_category(self):
        reg = get_provider_registry()
        reg.register(SketchfabProvider())
        reg.register(PolyhavenProvider())
        providers = reg.providers_for_category("vehicle")
        # Only Sketchfab supports vehicle
        names = {p.provider_name for p in providers}
        assert "sketchfab" in names
        assert "polyhaven" not in names

    def test_stats(self):
        reg = get_provider_registry()
        reg.register(SketchfabProvider())
        s = reg.stats()
        assert s["registered_count"] == 1
        assert "sketchfab" in s["provider_names"]


# ---------------------------------------------------------------------------
# SketchfabProvider
# ---------------------------------------------------------------------------

class TestSketchfabProvider:
    def test_provider_name(self):
        assert SketchfabProvider().provider_name == "sketchfab"

    def test_supported_categories_nonempty(self):
        cats = SketchfabProvider().supported_categories
        assert "vehicle" in cats
        assert "character" in cats

    def test_is_available(self):
        assert SketchfabProvider().is_available is True

    def test_search_returns_result(self):
        result = SketchfabProvider().search(category="prop")
        assert result.success is True
        assert result.provider == "sketchfab"
        assert isinstance(result.normalized_assets, list)

    def test_search_category_filter(self):
        result = SketchfabProvider().search(category="vehicle")
        for asset in result.normalized_assets:
            assert asset.category == "vehicle"

    def test_search_tag_filter(self):
        result = SketchfabProvider().search(category="", tags=["robot"])
        names = [a.name.lower() for a in result.normalized_assets]
        assert any("robot" in n for n in names)

    def test_search_empty_category_returns_all(self):
        result = SketchfabProvider().search(category="")
        assert len(result.normalized_assets) > 0

    def test_normalize_returns_descriptor(self):
        p = SketchfabProvider()
        result = p.search(category="prop", limit=1)
        if result.normalized_assets:
            a = result.normalized_assets[0]
            assert isinstance(a, AssetDescriptor)
            assert a.provider == "sketchfab"
            assert a.asset_id.startswith("skfb_")

    def test_normalized_asset_has_formats(self):
        result = SketchfabProvider().search(category="prop")
        for asset in result.normalized_assets:
            assert len(asset.formats) > 0

    def test_normalized_asset_has_tags(self):
        result = SketchfabProvider().search(category="", limit=20)
        for asset in result.normalized_assets:
            assert isinstance(asset.tags, list)

    def test_limit_respected(self):
        result = SketchfabProvider().search(category="", limit=2)
        assert len(result.normalized_assets) <= 2

    def test_validate_asset_valid(self):
        result = SketchfabProvider().search(category="prop", limit=1)
        if result.normalized_assets:
            v = SketchfabProvider().validate_asset(result.normalized_assets[0])
            assert "valid" in v
            assert "errors" in v

    def test_query_time_recorded(self):
        result = SketchfabProvider().search(category="prop")
        assert result.query_time >= 0.0


# ---------------------------------------------------------------------------
# PolyhavenProvider
# ---------------------------------------------------------------------------

class TestPolyhavenProvider:
    def test_provider_name(self):
        assert PolyhavenProvider().provider_name == "polyhaven"

    def test_all_assets_cc0(self):
        result = PolyhavenProvider().search(category="")
        for asset in result.normalized_assets:
            assert asset.license == "cc0"

    def test_search_hdri_category(self):
        result = PolyhavenProvider().search(category="hdri")
        for asset in result.normalized_assets:
            assert asset.category == "hdri"

    def test_normalized_asset_has_preview(self):
        result = PolyhavenProvider().search(category="material", limit=1)
        if result.normalized_assets:
            a = result.normalized_assets[0]
            assert a.asset_id.startswith("ph_")
            assert a.preview_url != ""

    def test_search_returns_result(self):
        result = PolyhavenProvider().search(category="material")
        assert result.success is True


# ---------------------------------------------------------------------------
# LocalLibraryProvider
# ---------------------------------------------------------------------------

class TestLocalLibraryProvider:
    def test_unavailable_when_no_path(self):
        p = LocalLibraryProvider(library_path=None)
        assert p.is_available is False

    def test_search_returns_empty_when_unavailable(self):
        p = LocalLibraryProvider(library_path=None)
        result = p.search(category="vehicle")
        assert result.success is True
        assert result.normalized_assets == []

    def test_provider_name(self):
        assert LocalLibraryProvider().provider_name == "local"

    def test_supported_categories_comprehensive(self):
        cats = LocalLibraryProvider().supported_categories
        assert "vehicle" in cats
        assert "material" in cats
        assert len(cats) > 10
