"""Tests for src/runtime/assets/acquisition_online/download_serializer.py"""
import json
import os
import tempfile
import pytest
from src.runtime.assets.acquisition_online import (
    get_download_serializer,
    reset_download_serializer_for_tests,
)


@pytest.fixture(autouse=True)
def reset_all():
    reset_download_serializer_for_tests()
    yield
    reset_download_serializer_for_tests()


def test_singleton():
    a = get_download_serializer()
    b = get_download_serializer()
    assert a is b


def test_schema_version():
    s = get_download_serializer()
    assert s.schema_version == "1.0.0"


def test_serialize_deserialize_roundtrip():
    s = get_download_serializer()
    data = {"asset_id": "abc", "provider": "megascans", "ok": True}
    serialized = s.serialize(data)
    result = s.deserialize(serialized)
    assert result["asset_id"] == "abc"
    assert result["ok"] is True
    assert "__download_schema_version__" not in result


def test_serialize_sorted_keys():
    s = get_download_serializer()
    data = {"z_key": 1, "a_key": 2}
    serialized = s.serialize(data)
    parsed = json.loads(serialized)
    keys = list(parsed.keys())
    assert keys == sorted(keys)


def test_serialize_list_roundtrip():
    s = get_download_serializer()
    items = [{"id": "a"}, {"id": "b"}]
    serialized = s.serialize_list(items)
    result = s.deserialize_list(serialized)
    assert len(result) == 2
    assert result[0]["id"] == "a"


def test_deserialize_invalid_json():
    s = get_download_serializer()
    result = s.deserialize("not valid json{{{")
    assert result == {}


def test_deserialize_list_invalid():
    s = get_download_serializer()
    result = s.deserialize_list("[]")
    assert result == []


def test_write_read_jsonl(tmp_path):
    s = get_download_serializer()
    path = str(tmp_path / "test.jsonl")
    ok = s.write_jsonl(path, {"asset_id": "x", "ok": True})
    assert ok is True
    records = s.read_jsonl(path)
    assert len(records) == 1
    assert records[0]["asset_id"] == "x"


def test_read_jsonl_missing_file(tmp_path):
    s = get_download_serializer()
    records = s.read_jsonl(str(tmp_path / "nonexistent.jsonl"))
    assert records == []


def test_normalize_nested():
    s = get_download_serializer()
    data = {"list": [1, 2, {"key": "val"}], "nested": {"a": 1}}
    out = s.serialize(data)
    result = s.deserialize(out)
    assert result["list"] == [1, 2, {"key": "val"}]
    assert result["nested"]["a"] == 1
