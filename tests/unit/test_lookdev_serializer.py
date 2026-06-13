import json
import os
import tempfile
import pytest
from src.runtime.lookdev import (
    LOOKDEV_SCHEMA_VERSION,
    LookdevSerializer,
    get_lookdev_serializer,
    reset_lookdev_serializer_for_tests,
)


@pytest.fixture(autouse=True)
def reset_singleton():
    reset_lookdev_serializer_for_tests()
    yield
    reset_lookdev_serializer_for_tests()


def test_singleton_identity():
    assert get_lookdev_serializer() is get_lookdev_serializer()


def test_schema_version_defined():
    assert isinstance(LOOKDEV_SCHEMA_VERSION, str)
    assert LOOKDEV_SCHEMA_VERSION == "1.0.0"


def test_export_returns_string():
    s = get_lookdev_serializer().export({"key": "value"})
    assert isinstance(s, str)


def test_export_injects_schema_version():
    s = get_lookdev_serializer().export({"x": 1})
    d = json.loads(s)
    assert "_schema_version" in d
    assert d["_schema_version"] == LOOKDEV_SCHEMA_VERSION


def test_export_sorted_keys():
    s = get_lookdev_serializer().export({"z": 1, "a": 2, "m": 3})
    keys = list(json.loads(s).keys())
    assert keys == sorted(keys)


def test_import_parses_json():
    s = '{"materials": ["metal", "concrete"], "score": 0.85}'
    result = get_lookdev_serializer().import_(s)
    assert result["materials"] == ["metal", "concrete"]
    assert result["score"] == 0.85


def test_import_bad_json_returns_empty():
    result = get_lookdev_serializer().import_("not valid json {{{")
    assert result == {}


def test_import_non_dict_returns_empty():
    result = get_lookdev_serializer().import_("[1, 2, 3]")
    assert result == {}


def test_export_import_round_trip():
    data = {"materials": ["metal", "concrete"], "score": 0.85, "renderer": "arnold"}
    s = get_lookdev_serializer().export(data)
    restored = get_lookdev_serializer().import_(s)
    assert restored["materials"] == ["metal", "concrete"]
    assert restored["score"] == 0.85
    assert restored["renderer"] == "arnold"


def test_export_empty_dict():
    s = get_lookdev_serializer().export({})
    d = json.loads(s)
    assert "_schema_version" in d


def test_save_and_load(tmp_path):
    path = str(tmp_path / "lookdev_test.json")
    data = {"environment": "industrial_hangar", "score": 0.9}
    ok = get_lookdev_serializer().save(data, path)
    assert ok is True
    assert os.path.exists(path)
    loaded = get_lookdev_serializer().load(path)
    assert loaded["environment"] == "industrial_hangar"
    assert loaded["score"] == 0.9
    assert "_schema_version" in loaded


def test_load_nonexistent_returns_empty():
    result = get_lookdev_serializer().load("/no/such/file/xyz.json")
    assert result == {}


def test_save_bad_path_returns_false():
    ok = get_lookdev_serializer().save({"x": 1}, "/no/such/directory/file.json")
    assert ok is False


def test_import_none_returns_empty():
    result = get_lookdev_serializer().import_(None)  # type: ignore
    assert result == {}


def test_stateless_multiple_instances():
    s1 = LookdevSerializer()
    s2 = LookdevSerializer()
    assert s1.export({"a": 1}) == s2.export({"a": 1})
