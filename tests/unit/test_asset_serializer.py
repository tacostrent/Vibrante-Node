"""
Tests for src/runtime/assets/serialization/asset_serializer.py
"""

import json
import pytest
import tempfile
import os

from src.runtime.assets.serialization import (
    AssetSerializer,
    get_asset_serializer,
    reset_asset_serializer_for_tests,
)
from src.runtime.assets.schema import (
    AssetDescriptor, AssetQueryResult, AssetRecommendation,
)


@pytest.fixture(autouse=True)
def reset():
    reset_asset_serializer_for_tests()
    yield
    reset_asset_serializer_for_tests()


def make_descriptor(**kwargs) -> AssetDescriptor:
    defaults = dict(
        asset_id="ser_001", provider="sketchfab", name="Serialized Asset",
        category="prop", tags=["test"], formats=["fbx"],
    )
    defaults.update(kwargs)
    return AssetDescriptor(**defaults)


class TestAssetSerializer:
    def test_singleton_identity(self):
        s1 = get_asset_serializer()
        s2 = get_asset_serializer()
        assert s1 is s2

    # ------------------------------------------------------------------
    # AssetDescriptor
    # ------------------------------------------------------------------

    def test_descriptor_to_json_is_string(self):
        s = get_asset_serializer().descriptor_to_json(make_descriptor())
        assert isinstance(s, str)

    def test_descriptor_round_trip(self):
        a = make_descriptor()
        s = get_asset_serializer().descriptor_to_json(a)
        a2 = get_asset_serializer().descriptor_from_json(s)
        assert a2 is not None
        assert a2.asset_id == "ser_001"
        assert a2.name == "Serialized Asset"

    def test_descriptor_json_sorted_keys(self):
        a = make_descriptor()
        s = get_asset_serializer().descriptor_to_json(a)
        # Outer record (may have _schema_version or record_type prepended)
        data = json.loads(s)
        keys = [k for k in data.keys() if not k.startswith("_")]
        assert keys == sorted(keys)

    def test_descriptor_from_json_lenient_on_bad_input(self):
        result = get_asset_serializer().descriptor_from_json("{invalid", lenient=True)
        assert result is None

    def test_descriptor_list_round_trip(self):
        assets = [make_descriptor(asset_id=f"a{i}") for i in range(3)]
        s = get_asset_serializer().descriptor_list_to_json(assets)
        back = get_asset_serializer().descriptor_list_from_json(s)
        assert len(back) == 3
        ids = [a.asset_id for a in back]
        assert "a0" in ids and "a1" in ids and "a2" in ids

    def test_descriptor_list_empty(self):
        s = get_asset_serializer().descriptor_list_to_json([])
        back = get_asset_serializer().descriptor_list_from_json(s)
        assert back == []

    def test_descriptor_list_bad_json_returns_empty(self):
        back = get_asset_serializer().descriptor_list_from_json("not json")
        assert back == []

    # ------------------------------------------------------------------
    # AssetQueryResult
    # ------------------------------------------------------------------

    def test_query_result_round_trip(self):
        qr = AssetQueryResult(
            query_id="q1", category="prop", zone="foreground",
            assets=[make_descriptor()], total_found=1,
        )
        s = get_asset_serializer().query_result_to_json(qr)
        qr2 = get_asset_serializer().query_result_from_json(s)
        assert qr2 is not None
        assert qr2.query_id == "q1"
        assert len(qr2.assets) == 1

    def test_query_result_from_json_lenient(self):
        result = get_asset_serializer().query_result_from_json("{bad}", lenient=True)
        assert result is None

    # ------------------------------------------------------------------
    # AssetRecommendation
    # ------------------------------------------------------------------

    def test_recommendation_round_trip(self):
        rec = AssetRecommendation(
            asset=make_descriptor(), score=0.82, rank=1,
            zone="foreground", category="prop", source="memory",
        )
        s = get_asset_serializer().recommendation_to_json(rec)
        rec2 = get_asset_serializer().recommendation_from_json(s)
        assert rec2 is not None
        assert rec2.score == pytest.approx(0.82)
        assert rec2.rank == 1
        assert rec2.source == "memory"

    def test_recommendation_list_round_trip(self):
        recs = [
            AssetRecommendation(asset=make_descriptor(asset_id=f"r{i}"), score=float(i) * 0.1, rank=i + 1)
            for i in range(3)
        ]
        s = get_asset_serializer().recommendation_list_to_json(recs)
        back = get_asset_serializer().recommendation_list_from_json(s)
        assert len(back) == 3

    # ------------------------------------------------------------------
    # File I/O
    # ------------------------------------------------------------------

    def test_save_and_load_descriptor(self):
        a = make_descriptor(asset_id="file_test")
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            get_asset_serializer().save(a, path)
            a2 = get_asset_serializer().load_descriptor(path)
            assert a2 is not None
            assert a2.asset_id == "file_test"
        finally:
            os.unlink(path)

    def test_load_missing_file_lenient(self):
        result = get_asset_serializer().load_descriptor("/nonexistent/path.json", lenient=True)
        assert result is None

    def test_load_missing_file_strict_raises(self):
        with pytest.raises(FileNotFoundError):
            get_asset_serializer().load_descriptor("/nonexistent/path.json", lenient=False)
