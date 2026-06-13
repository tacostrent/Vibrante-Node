"""Tests for src/runtime/assets/metadata/provider_normalizer.py"""
import pytest

from src.runtime.assets.metadata.provider_normalizer import (
    ProviderNormalizer,
    get_provider_normalizer,
    reset_provider_normalizer_for_tests,
    _SKETCHFAB_CATEGORY_MAP,
    _QUIXEL_CATEGORY_MAP,
)
from src.runtime.assets.schema import AssetDescriptor, AssetMetadata, AssetPreview, ASSET_CATEGORIES


@pytest.fixture(autouse=True)
def reset():
    reset_provider_normalizer_for_tests()
    yield
    reset_provider_normalizer_for_tests()


class TestSingleton:
    def test_singleton_identity(self):
        n1 = get_provider_normalizer()
        n2 = get_provider_normalizer()
        assert n1 is n2


class TestNormalizeAsset:
    def test_sketchfab_raw(self):
        raw = {
            "uid": "robot_mk7",
            "name": "Maintenance Robot",
            "categories": ["robot"],
            "tags": ["robot", "industrial"],
            "license": {"slug": "by"},
            "formats": ["fbx", "gltf"],
            "stats": {"viewCount": 5000, "likeCount": 300},
            "faceCount": 28000,
            "isAnimated": True,
        }
        norm = get_provider_normalizer()
        asset = norm.normalize_asset(raw, "sketchfab")
        assert isinstance(asset, AssetDescriptor)
        assert asset.provider == "sketchfab"
        assert asset.name == "Maintenance Robot"
        assert "robot" in asset.tags
        assert asset.metadata.face_count == 28000
        assert asset.metadata.is_animated is True

    def test_quixel_raw(self):
        raw = {
            "id": "surf_rock",
            "name": "Rock Surface",
            "category": "surfaces",
            "tags": ["rock", "stone"],
            "formats": ["uasset"],
        }
        norm = get_provider_normalizer()
        asset = norm.normalize_asset(raw, "quixel")
        assert asset.provider == "quixel"
        assert asset.category == "material"

    def test_polyhaven_raw(self):
        raw = {
            "uid": "pine_tree",
            "name": "Pine Tree",
            "category": "models",
            "tags": ["tree", "pine", "vegetation"],
            "license": {"slug": "cc0"},
            "formats": ["fbx", "blend"],
        }
        norm = get_provider_normalizer()
        asset = norm.normalize_asset(raw, "polyhaven")
        assert asset.provider == "polyhaven"
        assert asset.license == "cc0"
        assert asset.category == "prop"  # "models" -> "prop"

    def test_missing_fields_get_defaults(self):
        raw = {"uid": "empty_asset"}
        norm = get_provider_normalizer()
        asset = norm.normalize_asset(raw, "test_provider")
        assert asset.name != ""
        # fallback category — "other" or "prop" depending on mapping
        assert asset.category in ("prop", "other")
        assert isinstance(asset.tags, list)

    def test_increments_count(self):
        norm = get_provider_normalizer()
        initial = norm.get_statistics()["normalized_count"]
        norm.normalize_asset({"uid": "x"}, "test")
        assert norm.get_statistics()["normalized_count"] == initial + 1


class TestNormalizeMetadata:
    def test_extracts_face_count(self):
        raw = {"faceCount": 5000, "vertexCount": 3000}
        norm = get_provider_normalizer()
        meta = norm.normalize_metadata(raw, "sketchfab")
        assert meta.face_count == 5000
        assert meta.vertex_count == 3000

    def test_extracts_animated(self):
        raw = {"isAnimated": True}
        norm = get_provider_normalizer()
        meta = norm.normalize_metadata(raw, "sketchfab")
        assert meta.is_animated is True

    def test_defaults(self):
        norm = get_provider_normalizer()
        meta = norm.normalize_metadata({}, "test")
        assert isinstance(meta, AssetMetadata)
        assert meta.face_count == 0


class TestNormalizePreview:
    def test_no_preview_returns_none(self):
        norm = get_provider_normalizer()
        assert norm.normalize_preview({}, "test") is None

    def test_from_preview_images(self):
        raw = {
            "uid": "my_asset",
            "preview": {"images": [{"url": "https://example.com/thumb.jpg"}]},
        }
        norm = get_provider_normalizer()
        preview = norm.normalize_preview(raw, "sketchfab")
        assert preview is not None
        assert isinstance(preview, AssetPreview)
        assert "example.com" in preview.url

    def test_from_preview_url_field(self):
        raw = {"uid": "x", "preview_url": "https://example.com/img.jpg"}
        norm = get_provider_normalizer()
        preview = norm.normalize_preview(raw, "test")
        assert preview is not None
        assert preview.url == "https://example.com/img.jpg"


class TestNormalizeTags:
    def test_lowercase_and_strip(self):
        norm = get_provider_normalizer()
        result = norm.normalize_tags(["Robot", "  Industrial  "], "sketchfab")
        assert "robot" in result
        assert "industrial" in result

    def test_deduplicate(self):
        norm = get_provider_normalizer()
        result = norm.normalize_tags(["robot", "Robot", "ROBOT"], "test")
        assert result.count("robot") == 1

    def test_remove_empty(self):
        norm = get_provider_normalizer()
        result = norm.normalize_tags(["robot", "", "  "], "test")
        assert "" not in result
        assert "  " not in result

    def test_non_string_values(self):
        norm = get_provider_normalizer()
        result = norm.normalize_tags([123, "tag"], "test")
        assert "123" in result
        assert "tag" in result


class TestNormalizeCategory:
    def test_sketchfab_vehicles(self):
        norm = get_provider_normalizer()
        assert norm.normalize_category("vehicles", "sketchfab") == "vehicle"

    def test_sketchfab_characters(self):
        norm = get_provider_normalizer()
        assert norm.normalize_category("characters", "sketchfab") == "character"

    def test_quixel_surfaces(self):
        norm = get_provider_normalizer()
        assert norm.normalize_category("surfaces", "quixel") == "material"

    def test_direct_match(self):
        norm = get_provider_normalizer()
        assert norm.normalize_category("vehicle", "unknown_provider") == "vehicle"

    def test_fallback_to_prop(self):
        norm = get_provider_normalizer()
        result = norm.normalize_category("something_completely_unknown", "test")
        assert result == "prop"

    def test_case_insensitive(self):
        norm = get_provider_normalizer()
        assert norm.normalize_category("VEHICLES", "sketchfab") == "vehicle"


class TestStatistics:
    def test_statistics_structure(self):
        norm = get_provider_normalizer()
        s = norm.get_statistics()
        assert "normalized_count" in s
