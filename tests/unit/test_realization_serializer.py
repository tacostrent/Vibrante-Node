"""Tests for RealizationSerializer -- §47 Layout Realization."""
import json
import pytest
from src.runtime.layout_realization import (
    get_realization_serializer,
    reset_realization_serializer_for_tests,
)


@pytest.fixture(autouse=True)
def reset():
    reset_realization_serializer_for_tests()
    yield
    reset_realization_serializer_for_tests()


def test_serialize_adds_schema_version():
    s = get_realization_serializer()
    text = s.serialize({"environment": "western_room"})
    d = json.loads(text)
    assert d.get("_schema_version") == "1.0.0"


def test_serialize_sorted_keys():
    s = get_realization_serializer()
    text = s.serialize({"z_key": 1, "a_key": 2})
    keys = [k for k in json.loads(text).keys() if k != "_schema_version"]
    assert keys == sorted(keys)


def test_deserialize_valid():
    d = get_realization_serializer().deserialize('{"environment": "western_room"}')
    assert d["environment"] == "western_room"


def test_deserialize_invalid_returns_empty():
    d = get_realization_serializer().deserialize("not json{{{")
    assert d == {}


def test_serialize_transforms():
    text = get_realization_serializer().serialize_transforms([{"asset_id": "t", "tx": 1.0}])
    d = json.loads(text)
    assert len(d) == 1


def test_schema_version_property():
    assert get_realization_serializer().schema_version == "1.0.0"
