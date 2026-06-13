"""Tests for LightingSerializer (Tier 15)."""
import json
import os
import tempfile
import pytest
from src.runtime.lighting import (
    get_lighting_serializer,
    reset_lighting_serializer_for_tests,
    LIGHTING_SCHEMA_VERSION,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_lighting_serializer_for_tests()
    yield
    reset_lighting_serializer_for_tests()


class TestLightingSerializer:
    def test_export_includes_schema_version(self):
        s = get_lighting_serializer()
        exported = s.export({"key": "value"})
        d = json.loads(exported)
        assert d["_schema_version"] == LIGHTING_SCHEMA_VERSION

    def test_export_sorted_keys(self):
        s = get_lighting_serializer()
        exported = s.export({"z": 1, "a": 2})
        keys = list(json.loads(exported).keys())
        assert keys == sorted(keys)

    def test_import_parses_json(self):
        s = get_lighting_serializer()
        imported = s.import_('{"key": "value"}')
        assert imported["key"] == "value"

    def test_import_invalid_returns_empty(self):
        s = get_lighting_serializer()
        assert s.import_("not json {{") == {}

    def test_import_non_dict_returns_empty(self):
        s = get_lighting_serializer()
        assert s.import_("[1, 2, 3]") == {}

    def test_save_and_load(self, tmp_path):
        s = get_lighting_serializer()
        path = str(tmp_path / "test.json")
        data = {"plan_id": "p1", "mood": "dramatic"}
        assert s.save(data, path) is True
        loaded = s.load(path)
        assert loaded["plan_id"] == "p1"
        assert loaded["_schema_version"] == LIGHTING_SCHEMA_VERSION

    def test_load_missing_file_returns_empty(self):
        s = get_lighting_serializer()
        assert s.load("/nonexistent/path/file.json") == {}

    def test_save_returns_false_on_bad_path(self):
        s = get_lighting_serializer()
        result = s.save({}, "/nonexistent/deeply/nested/path/file.json")
        assert result is False

    def test_roundtrip_preserves_data(self, tmp_path):
        s = get_lighting_serializer()
        path = str(tmp_path / "round.json")
        data = {"mood": "industrial", "score": 0.85, "list": [1, 2, 3]}
        s.save(data, path)
        loaded = s.load(path)
        assert loaded["mood"] == "industrial"
        assert loaded["score"] == 0.85

    def test_schema_version_constant(self):
        assert LIGHTING_SCHEMA_VERSION == "1.0.0"

    def test_singleton(self):
        assert get_lighting_serializer() is get_lighting_serializer()
