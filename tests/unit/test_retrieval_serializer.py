"""Tests for retrieval_serializer.py (Tier 12.8)."""
from __future__ import annotations
import json
import pytest
from src.runtime.assets.vector_search import (
    RetrievalSerializer, get_retrieval_serializer, reset_retrieval_serializer_for_tests,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_retrieval_serializer_for_tests()
    yield
    reset_retrieval_serializer_for_tests()


class TestRetrievalSerializer:
    def test_schema_version(self):
        assert get_retrieval_serializer().schema_version == "1.0.0"

    def test_serialize_dict(self):
        data = {"score": 0.9, "grade": "A", "results": [{"asset_id": "a1"}]}
        out = get_retrieval_serializer().serialize(data)
        parsed = json.loads(out)
        assert parsed["score"] == 0.9
        assert parsed["grade"] == "A"

    def test_serialize_sorted_keys(self):
        data = {"z": 1, "a": 2, "m": 3}
        out = get_retrieval_serializer().serialize(data)
        parsed_keys = list(json.loads(out).keys())
        non_schema = [k for k in parsed_keys if not k.startswith("__")]
        assert non_schema == sorted(non_schema)

    def test_deserialize(self):
        data = {"score": 0.85, "findings": ["ok"]}
        serialized = get_retrieval_serializer().serialize(data)
        restored = get_retrieval_serializer().deserialize(serialized)
        assert restored["score"] == 0.85
        assert restored["findings"] == ["ok"]

    def test_deserialize_invalid_json(self):
        result = get_retrieval_serializer().deserialize("not valid json !!!")
        assert result == {}

    def test_serialize_list(self):
        items = [{"id": "a1", "score": 0.9}, {"id": "a2", "score": 0.7}]
        out = get_retrieval_serializer().serialize_list(items)
        restored = get_retrieval_serializer().deserialize_list(out)
        assert len(restored) == 2
        assert restored[0]["id"] == "a1"

    def test_deserialize_list_invalid(self):
        result = get_retrieval_serializer().deserialize_list("bad json")
        assert result == []

    def test_handles_nested_dicts(self):
        data = {"outer": {"inner": {"deep": 42}}}
        out = get_retrieval_serializer().serialize(data)
        restored = get_retrieval_serializer().deserialize(out)
        assert restored["outer"]["inner"]["deep"] == 42

    def test_handles_lists_in_values(self):
        data = {"items": [1, 2, 3]}
        out = get_retrieval_serializer().serialize(data)
        restored = get_retrieval_serializer().deserialize(out)
        assert restored["items"] == [1, 2, 3]
