"""Tests for EnvRealizationSerializer -- §49 Structural Environment Realization."""
import json
import pytest
from src.runtime.environment_realization import (
    get_env_realization_serializer,
    reset_env_realization_serializer_for_tests,
)


@pytest.fixture(autouse=True)
def reset():
    reset_env_realization_serializer_for_tests()
    yield
    reset_env_realization_serializer_for_tests()


def test_serialize_adds_schema_version():
    text = get_env_realization_serializer().serialize({"environment": "western_room"})
    d = json.loads(text)
    assert d.get("_schema_version") == "1.0.0"


def test_serialize_sorted_keys():
    text = get_env_realization_serializer().serialize({"z": 1, "a": 2})
    keys = [k for k in json.loads(text).keys() if k != "_schema_version"]
    assert keys == sorted(keys)


def test_deserialize_valid():
    d = get_env_realization_serializer().deserialize('{"environment": "western_room"}')
    assert d["environment"] == "western_room"


def test_deserialize_invalid_returns_empty():
    d = get_env_realization_serializer().deserialize("not json{{{")
    assert d == {}


def test_serialize_elements():
    elems = [{"element_id": "floor", "element_type": "floor", "material": "wood"}]
    text = get_env_realization_serializer().serialize_elements(elems)
    d = json.loads(text)
    assert d[0]["element_id"] == "floor"


def test_schema_version_property():
    assert get_env_realization_serializer().schema_version == "1.0.0"
