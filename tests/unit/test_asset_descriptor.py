"""
Tests for src/runtime/assets/schema/asset_descriptor.py
"""

import json
import pytest

from src.runtime.assets.schema import (
    SCHEMA_VERSION, ASSET_CATEGORIES, ASSET_FORMATS, LICENSE_TYPES,
    SCALE_TYPES, ASSET_STYLES,
    AssetMetadata, AssetPreview, AssetDescriptor,
    AssetProviderResult, AssetQueryResult, AssetRecommendation,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class TestConstants:
    def test_schema_version_string(self):
        assert isinstance(SCHEMA_VERSION, str)
        parts = SCHEMA_VERSION.split(".")
        assert len(parts) == 3

    def test_asset_categories_is_frozenset(self):
        assert isinstance(ASSET_CATEGORIES, frozenset)
        assert "vehicle" in ASSET_CATEGORIES
        assert "character" in ASSET_CATEGORIES
        assert "prop" in ASSET_CATEGORIES
        assert "other" in ASSET_CATEGORIES

    def test_asset_formats_includes_standard(self):
        for fmt in ("fbx", "obj", "gltf", "usd", "vdb"):
            assert fmt in ASSET_FORMATS

    def test_license_types_includes_cc0(self):
        assert "cc0" in LICENSE_TYPES
        assert "commercial" in LICENSE_TYPES


# ---------------------------------------------------------------------------
# AssetMetadata
# ---------------------------------------------------------------------------

class TestAssetMetadata:
    def test_defaults(self):
        m = AssetMetadata()
        assert m.face_count == 0
        assert m.is_animated is False
        assert m.author == ""

    def test_round_trip(self):
        m = AssetMetadata(face_count=12000, vertex_count=8000, is_animated=True, author="Studio")
        d = m.to_dict()
        m2 = AssetMetadata.from_dict(d)
        assert m2.face_count == 12000
        assert m2.vertex_count == 8000
        assert m2.is_animated is True
        assert m2.author == "Studio"

    def test_json_round_trip(self):
        m = AssetMetadata(face_count=500, author="test")
        s = m.to_json()
        m2 = AssetMetadata.from_json(s)
        assert m2.face_count == 500
        assert m2.author == "test"

    def test_to_json_sorted_keys(self):
        m = AssetMetadata(face_count=1, vertex_count=2)
        s = m.to_json()
        keys = list(json.loads(s).keys())
        assert keys == sorted(keys)


# ---------------------------------------------------------------------------
# AssetPreview
# ---------------------------------------------------------------------------

class TestAssetPreview:
    def test_defaults(self):
        p = AssetPreview()
        assert p.url == ""
        assert p.format == "jpg"

    def test_round_trip(self):
        p = AssetPreview(asset_id="a1", provider="sketchfab",
                         url="https://example.com/img.jpg", width=512, height=512)
        p2 = AssetPreview.from_dict(p.to_dict())
        assert p2.asset_id == "a1"
        assert p2.url == "https://example.com/img.jpg"
        assert p2.width == 512


# ---------------------------------------------------------------------------
# AssetDescriptor
# ---------------------------------------------------------------------------

class TestAssetDescriptor:
    def _make(self, **kwargs):
        defaults = dict(
            asset_id="test_001",
            provider="sketchfab",
            name="Test Asset",
            category="prop",
            tags=["industrial", "metal"],
            license="cc-by",
            formats=["fbx", "obj"],
            rating=3.5,
            popularity=1200,
        )
        defaults.update(kwargs)
        return AssetDescriptor(**defaults)

    def test_unique_ids(self):
        a1, a2 = AssetDescriptor(), AssetDescriptor()
        assert a1.asset_id != a2.asset_id

    def test_round_trip(self):
        a = self._make()
        d = a.to_dict()
        a2 = AssetDescriptor.from_dict(d)
        assert a2.asset_id == "test_001"
        assert a2.name == "Test Asset"
        assert a2.category == "prop"
        assert a2.tags == ["industrial", "metal"]
        assert a2.rating == pytest.approx(3.5)

    def test_json_round_trip(self):
        a = self._make()
        s = a.to_json()
        a2 = AssetDescriptor.from_json(s)
        assert a2.asset_id == a.asset_id

    def test_json_sorted_keys(self):
        a = self._make()
        s = a.to_json()
        keys = list(json.loads(s).keys())
        assert keys == sorted(keys)

    def test_is_cc0_property(self):
        a = self._make(license="cc0")
        assert a.is_cc0 is True
        a2 = self._make(license="cc-by")
        assert a2.is_cc0 is False

    def test_has_usd_property(self):
        a = self._make(formats=["usd", "fbx"])
        assert a.has_usd is True
        a2 = self._make(formats=["fbx", "obj"])
        assert a2.has_usd is False

    def test_has_vdb_property(self):
        a = self._make(formats=["vdb", "bgeo"])
        assert a.has_vdb is True

    def test_tag_set_property(self):
        a = self._make(tags=["Metal", "INDUSTRIAL"])
        ts = a.tag_set
        assert "metal" in ts
        assert "industrial" in ts

    def test_with_preview(self):
        preview = AssetPreview(asset_id="x", url="http://img.jpg")
        a = self._make(preview=preview)
        d = a.to_dict()
        a2 = AssetDescriptor.from_dict(d)
        assert a2.preview is not None
        assert a2.preview.url == "http://img.jpg"

    def test_with_metadata(self):
        meta = AssetMetadata(face_count=9000, is_animated=True)
        a = self._make(metadata=meta)
        d = a.to_dict()
        a2 = AssetDescriptor.from_dict(d)
        assert a2.metadata.face_count == 9000
        assert a2.metadata.is_animated is True


# ---------------------------------------------------------------------------
# AssetProviderResult
# ---------------------------------------------------------------------------

class TestAssetProviderResult:
    def test_defaults(self):
        r = AssetProviderResult()
        assert r.success is True
        assert r.errors == []
        assert r.normalized_assets == []

    def test_round_trip(self):
        asset = AssetDescriptor(asset_id="a1", provider="test", name="Foo")
        r = AssetProviderResult(
            provider="test",
            normalized_assets=[asset],
            success=True,
            query_time=0.05,
        )
        d = r.to_dict()
        r2 = AssetProviderResult.from_dict(d)
        assert r2.provider == "test"
        assert len(r2.normalized_assets) == 1
        assert r2.normalized_assets[0].asset_id == "a1"
        assert r2.query_time == pytest.approx(0.05)


# ---------------------------------------------------------------------------
# AssetQueryResult
# ---------------------------------------------------------------------------

class TestAssetQueryResult:
    def test_defaults(self):
        r = AssetQueryResult()
        assert r.total_found == 0
        assert r.assets == []

    def test_round_trip(self):
        assets = [AssetDescriptor(asset_id=f"a{i}", name=f"Asset {i}") for i in range(3)]
        r = AssetQueryResult(
            query_id="q1", category="prop", zone="foreground",
            assets=assets, total_found=3,
        )
        d = r.to_dict()
        r2 = AssetQueryResult.from_dict(d)
        assert r2.query_id == "q1"
        assert r2.total_found == 3
        assert len(r2.assets) == 3

    def test_unique_ids(self):
        r1, r2 = AssetQueryResult(), AssetQueryResult()
        assert r1.result_id != r2.result_id


# ---------------------------------------------------------------------------
# AssetRecommendation
# ---------------------------------------------------------------------------

class TestAssetRecommendation:
    def test_defaults(self):
        r = AssetRecommendation()
        assert r.score == 0.0
        assert r.rank == 0
        assert r.source == "provider"

    def test_round_trip(self):
        asset = AssetDescriptor(asset_id="a1", name="Bot")
        rec = AssetRecommendation(
            asset=asset, score=0.87, rank=1, zone="foreground",
            category="robot", source="memory", confidence=0.95,
            boost_reasons=["Used in 3 successful scenes"],
        )
        d = rec.to_dict()
        rec2 = AssetRecommendation.from_dict(d)
        assert rec2.score == pytest.approx(0.87)
        assert rec2.rank == 1
        assert rec2.zone == "foreground"
        assert rec2.source == "memory"
        assert rec2.asset is not None
        assert rec2.asset.name == "Bot"
        assert len(rec2.boost_reasons) == 1

    def test_unique_ids(self):
        r1, r2 = AssetRecommendation(), AssetRecommendation()
        assert r1.recommendation_id != r2.recommendation_id
