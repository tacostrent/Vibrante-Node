"""Tests for KnowledgeSerializer (Tier 11 — §31)."""
import json
import os
import tempfile
import pytest
from src.runtime.studio.knowledge_serializer import (
    KnowledgeSerializer,
    get_knowledge_serializer,
    reset_knowledge_serializer_for_tests,
    KNOWLEDGE_SCHEMA_VERSION,
)


@pytest.fixture(autouse=True)
def reset():
    reset_knowledge_serializer_for_tests()
    yield
    reset_knowledge_serializer_for_tests()


def test_singleton():
    assert get_knowledge_serializer() is get_knowledge_serializer()


# ---------------------------------------------------------------------------
# to_json
# ---------------------------------------------------------------------------

def test_to_json_returns_string():
    ks = KnowledgeSerializer()
    s = ks.to_json({"foo": "bar"})
    assert isinstance(s, str)


def test_to_json_valid_json():
    ks = KnowledgeSerializer()
    s = ks.to_json({"x": 1})
    parsed = json.loads(s)
    assert parsed is not None


def test_to_json_sorted_keys():
    ks = KnowledgeSerializer()
    s = ks.to_json({"z": 1, "a": 2, "m": 3})
    lines = s.split("\n")
    key_lines = [l for l in lines if ": " in l and '"' in l]
    keys = [l.strip().split('"')[1] for l in key_lines if l.strip().startswith('"')]
    assert keys == sorted(keys)


def test_to_json_embeds_schema_version():
    ks = KnowledgeSerializer()
    s = ks.to_json({"test": True})
    parsed = json.loads(s)
    assert parsed.get("_schema_version") == KNOWLEDGE_SCHEMA_VERSION


def test_to_json_wraps_data():
    ks = KnowledgeSerializer()
    s = ks.to_json({"key": "val"})
    parsed = json.loads(s)
    assert parsed["data"]["key"] == "val"


# ---------------------------------------------------------------------------
# from_json
# ---------------------------------------------------------------------------

def test_from_json_round_trip():
    ks = KnowledgeSerializer()
    data = {"env": "industrial_hangar", "score": 0.88}
    s = ks.to_json(data)
    recovered = ks.from_json(s)
    assert recovered == data


def test_from_json_lenient_on_corrupt():
    ks = KnowledgeSerializer()
    result = ks.from_json("NOT_JSON", lenient=True)
    assert result is None


def test_from_json_strict_raises_on_corrupt():
    ks = KnowledgeSerializer()
    with pytest.raises(json.JSONDecodeError):
        ks.from_json("NOT_JSON", lenient=False)


def test_from_json_plain_dict():
    ks = KnowledgeSerializer()
    # JSON without 'data' key — returned as-is
    plain = '{"key": "value"}'
    result = ks.from_json(plain)
    assert result == {"key": "value"}


# ---------------------------------------------------------------------------
# save / load
# ---------------------------------------------------------------------------

def test_save_returns_true():
    ks = KnowledgeSerializer()
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
        path = tf.name
    try:
        ok = ks.save({"workflow": "pack_a"}, path)
        assert ok is True
    finally:
        os.unlink(path)


def test_save_load_round_trip():
    ks = KnowledgeSerializer()
    data = {"environment": "robotics_lab", "score": 0.91}
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
        path = tf.name
    try:
        ks.save(data, path)
        loaded = ks.load(path)
        assert loaded == data
    finally:
        os.unlink(path)


def test_load_missing_file_lenient():
    ks = KnowledgeSerializer()
    result = ks.load("/nonexistent/path/file.json", lenient=True)
    assert result is None


def test_load_missing_file_strict():
    ks = KnowledgeSerializer()
    with pytest.raises(FileNotFoundError):
        ks.load("/nonexistent/path/file.json", lenient=False)


def test_save_increments_write_count():
    ks = KnowledgeSerializer()
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
        path = tf.name
    try:
        ks.save({}, path)
        ks.save({}, path)
        assert ks.stats()["write_count"] == 2
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------

def test_export_returns_dict():
    ks = KnowledgeSerializer()
    result = ks.export()  # no path
    assert isinstance(result, dict)
    assert "_schema_version" in result
    assert "exported_at" in result
    assert "modules" in result


def test_export_to_file():
    ks = KnowledgeSerializer()
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
        path = tf.name
    try:
        result = ks.export(path=path)
        assert os.path.exists(path)
        loaded = json.loads(open(path).read())
        assert loaded["_schema_version"] == KNOWLEDGE_SCHEMA_VERSION
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# import_
# ---------------------------------------------------------------------------

def test_import_round_trip():
    ks = KnowledgeSerializer()
    data = {"key": "value", "score": 0.85}
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
        path = tf.name
    try:
        ks.save(data, path)
        imported = ks.import_(path)
        assert imported == data
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# stats()
# ---------------------------------------------------------------------------

def test_stats_key():
    ks = KnowledgeSerializer()
    assert "write_count" in ks.stats()
    assert ks.stats()["write_count"] == 0
