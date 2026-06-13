"""
Tests for src.runtime.storage.memory_backend
Covers: ProductionMemoryBackend (interface), InMemoryBackend, JSONLBackend,
        MemoryBackend alias, and backend injection into ProductionMemory.

No bridge, no LLM. Pure unit tests.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
import pytest

from src.runtime.storage.memory_backend import (
    InMemoryBackend,
    JSONLBackend,
    MemoryBackend,
    ProductionMemoryBackend,
)
from src.runtime.production_memory import (
    ProductionMemory,
    reset_production_memory_for_tests,
)


@pytest.fixture(autouse=True)
def reset_singleton():
    reset_production_memory_for_tests()
    yield
    reset_production_memory_for_tests()


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------

def test_abstract_backend_cannot_be_instantiated():
    """ProductionMemoryBackend is abstract — direct instantiation must fail."""
    with pytest.raises(TypeError):
        ProductionMemoryBackend()  # type: ignore[abstract]


def test_abstract_backend_is_base_of_in_memory():
    assert issubclass(InMemoryBackend, ProductionMemoryBackend)


def test_abstract_backend_is_base_of_jsonl():
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        path = f.name
    try:
        assert issubclass(JSONLBackend, ProductionMemoryBackend)
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# MemoryBackend alias
# ---------------------------------------------------------------------------

def test_memory_backend_alias_is_in_memory_backend():
    assert MemoryBackend is InMemoryBackend


def test_memory_backend_alias_instantiates():
    b = MemoryBackend()
    assert isinstance(b, ProductionMemoryBackend)


# ---------------------------------------------------------------------------
# InMemoryBackend — basic operations
# ---------------------------------------------------------------------------

def _make_record(record_type: str, **kwargs) -> dict:
    r = {"record_type": record_type, "timestamp": time.time()}
    r.update(kwargs)
    return r


class TestInMemoryBackend:

    def test_insert_and_query(self):
        b = InMemoryBackend()
        rec = _make_record("scene", scene_type="hangar", status="success")
        b.insert("scene", rec)
        results = b.query("scene")
        assert len(results) == 1
        assert results[0]["scene_type"] == "hangar"

    def test_query_only_matching_type(self):
        b = InMemoryBackend()
        b.insert("scene",   _make_record("scene",   scene_type="hangar"))
        b.insert("failure", _make_record("failure", scene_type="hangar"))
        assert len(b.query("scene"))   == 1
        assert len(b.query("failure")) == 1

    def test_query_filter(self):
        b = InMemoryBackend()
        b.insert("scene", _make_record("scene", scene_type="hangar", status="success"))
        b.insert("scene", _make_record("scene", scene_type="hangar", status="failure"))
        results = b.query("scene", filters={"status": "success"})
        assert len(results) == 1
        assert results[0]["status"] == "success"

    def test_query_multiple_filters(self):
        b = InMemoryBackend()
        b.insert("scene", _make_record("scene", scene_type="hangar", status="success"))
        b.insert("scene", _make_record("scene", scene_type="lab",    status="success"))
        results = b.query("scene", filters={"scene_type": "hangar", "status": "success"})
        assert len(results) == 1
        assert results[0]["scene_type"] == "hangar"

    def test_query_order_desc(self):
        b = InMemoryBackend()
        for i in range(3):
            b.insert("scene", _make_record("scene", scene_type="x", timestamp=float(i)))
        results = b.query("scene", order_desc=True)
        timestamps = [r["timestamp"] for r in results]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_query_order_asc(self):
        b = InMemoryBackend()
        for i in range(3):
            b.insert("scene", _make_record("scene", scene_type="x", timestamp=float(i)))
        results = b.query("scene", order_desc=False)
        timestamps = [r["timestamp"] for r in results]
        assert timestamps == sorted(timestamps)

    def test_query_limit(self):
        b = InMemoryBackend()
        for _ in range(10):
            b.insert("scene", _make_record("scene", scene_type="x"))
        assert len(b.query("scene", limit=3)) == 3

    def test_count_no_filter(self):
        b = InMemoryBackend()
        b.insert("scene", _make_record("scene", scene_type="x"))
        b.insert("scene", _make_record("scene", scene_type="y"))
        assert b.count("scene") == 2

    def test_count_with_filter(self):
        b = InMemoryBackend()
        b.insert("scene", _make_record("scene", scene_type="hangar"))
        b.insert("scene", _make_record("scene", scene_type="lab"))
        assert b.count("scene", filters={"scene_type": "hangar"}) == 1

    def test_all_records(self):
        b = InMemoryBackend()
        for _ in range(5):
            b.insert("scene", _make_record("scene", scene_type="x"))
        b.insert("failure", _make_record("failure", scene_type="x"))
        records = b.all_records("scene")
        assert len(records) == 5
        assert all(r["record_type"] == "scene" for r in records)

    def test_clear(self):
        b = InMemoryBackend()
        b.insert("scene", _make_record("scene", scene_type="x"))
        b.clear()
        assert b.record_count() == 0
        assert b.write_count()  == 0

    def test_record_count(self):
        b = InMemoryBackend()
        assert b.record_count() == 0
        b.insert("scene",   _make_record("scene",   scene_type="x"))
        b.insert("failure", _make_record("failure", scene_type="x"))
        assert b.record_count() == 2

    def test_write_count(self):
        b = InMemoryBackend()
        assert b.write_count() == 0
        b.insert("scene", _make_record("scene", scene_type="x"))
        b.insert("scene", _make_record("scene", scene_type="y"))
        assert b.write_count() == 2

    def test_write_count_reset_by_clear(self):
        b = InMemoryBackend()
        b.insert("scene", _make_record("scene", scene_type="x"))
        b.clear()
        assert b.write_count() == 0

    def test_insert_stores_copy(self):
        """Mutating the original dict after insert must not affect stored data."""
        b = InMemoryBackend()
        rec = _make_record("scene", scene_type="hangar")
        b.insert("scene", rec)
        rec["scene_type"] = "MUTATED"
        result = b.query("scene")[0]
        assert result["scene_type"] == "hangar"

    def test_query_returns_copies(self):
        """Mutating a query result must not affect stored data."""
        b = InMemoryBackend()
        b.insert("scene", _make_record("scene", scene_type="hangar"))
        result = b.query("scene")[0]
        result["scene_type"] = "MUTATED"
        stored = b.query("scene")[0]
        assert stored["scene_type"] == "hangar"

    def test_empty_query_returns_empty_list(self):
        b = InMemoryBackend()
        assert b.query("scene") == []

    def test_empty_all_records_returns_empty_list(self):
        b = InMemoryBackend()
        assert b.all_records("scene") == []


# ---------------------------------------------------------------------------
# JSONLBackend — basic operations (mirrors InMemoryBackend tests)
# ---------------------------------------------------------------------------

class TestJSONLBackend:

    @pytest.fixture()
    def tmp_path_str(self):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            path = f.name
        yield path
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass

    def test_insert_and_query(self, tmp_path_str):
        b = JSONLBackend(tmp_path_str)
        b.insert("scene", _make_record("scene", scene_type="hangar", status="success"))
        results = b.query("scene")
        assert len(results) == 1
        assert results[0]["scene_type"] == "hangar"

    def test_query_filter(self, tmp_path_str):
        b = JSONLBackend(tmp_path_str)
        b.insert("scene", _make_record("scene", scene_type="hangar", status="success"))
        b.insert("scene", _make_record("scene", scene_type="hangar", status="failure"))
        results = b.query("scene", filters={"status": "success"})
        assert len(results) == 1

    def test_query_order_desc(self, tmp_path_str):
        b = JSONLBackend(tmp_path_str)
        for i in range(3):
            b.insert("scene", _make_record("scene", scene_type="x", timestamp=float(i)))
        results = b.query("scene", order_desc=True)
        timestamps = [r["timestamp"] for r in results]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_query_limit(self, tmp_path_str):
        b = JSONLBackend(tmp_path_str)
        for _ in range(10):
            b.insert("scene", _make_record("scene", scene_type="x"))
        assert len(b.query("scene", limit=4)) == 4

    def test_count(self, tmp_path_str):
        b = JSONLBackend(tmp_path_str)
        b.insert("scene", _make_record("scene", scene_type="hangar"))
        b.insert("scene", _make_record("scene", scene_type="lab"))
        assert b.count("scene") == 2

    def test_count_with_filter(self, tmp_path_str):
        b = JSONLBackend(tmp_path_str)
        b.insert("scene", _make_record("scene", scene_type="hangar"))
        b.insert("scene", _make_record("scene", scene_type="lab"))
        assert b.count("scene", filters={"scene_type": "hangar"}) == 1

    def test_all_records(self, tmp_path_str):
        b = JSONLBackend(tmp_path_str)
        for _ in range(4):
            b.insert("scene", _make_record("scene", scene_type="x"))
        b.insert("failure", _make_record("failure", scene_type="x"))
        assert len(b.all_records("scene")) == 4

    def test_record_count(self, tmp_path_str):
        b = JSONLBackend(tmp_path_str)
        b.insert("scene",   _make_record("scene",   scene_type="x"))
        b.insert("failure", _make_record("failure", scene_type="x"))
        assert b.record_count() == 2

    def test_write_count(self, tmp_path_str):
        b = JSONLBackend(tmp_path_str)
        b.insert("scene", _make_record("scene", scene_type="x"))
        b.insert("scene", _make_record("scene", scene_type="y"))
        assert b.write_count() == 2

    def test_persistence_round_trip(self, tmp_path_str):
        """Records written by one instance are readable by a second instance."""
        b1 = JSONLBackend(tmp_path_str)
        b1.insert("scene",   _make_record("scene",   scene_type="hangar", status="success"))
        b1.insert("failure", _make_record("failure", scene_type="hangar", failure_type="t1"))

        b2 = JSONLBackend(tmp_path_str)
        assert len(b2.query("scene"))   == 1
        assert len(b2.query("failure")) == 1

    def test_corrupt_jsonl_lines_skipped(self, tmp_path_str):
        """Corrupt lines in the JSONL file are silently skipped on load."""
        with open(tmp_path_str, "w", encoding="utf-8") as fh:
            fh.write('{"record_type": "scene", "scene_type": "x", "timestamp": 1.0}\n')
            fh.write("NOT_JSON{{{\n")
            fh.write('{"record_type": "failure", "failure_type": "t", "scene_type": "x", "timestamp": 2.0}\n')

        b = JSONLBackend(tmp_path_str)
        assert b.count("scene")   == 1
        assert b.count("failure") == 1

    def test_missing_file_starts_empty(self):
        b = JSONLBackend("/nonexistent/path/prod.jsonl")
        assert b.record_count() == 0

    def test_write_failure_does_not_raise(self):
        """A write failure (bad path) must never propagate to the caller."""
        b = JSONLBackend("/nonexistent_dir/prod.jsonl")
        # Should not raise even though the directory doesn't exist
        b.insert("scene", _make_record("scene", scene_type="x"))
        assert b.write_count() == 1  # in-memory count still increments

    def test_clear_truncates_file(self, tmp_path_str):
        b = JSONLBackend(tmp_path_str)
        b.insert("scene", _make_record("scene", scene_type="x"))
        b.clear()
        assert b.record_count() == 0
        # File should be empty
        assert os.path.getsize(tmp_path_str) == 0

    def test_query_returns_copies(self, tmp_path_str):
        b = JSONLBackend(tmp_path_str)
        b.insert("scene", _make_record("scene", scene_type="hangar"))
        result = b.query("scene")[0]
        result["scene_type"] = "MUTATED"
        stored = b.query("scene")[0]
        assert stored["scene_type"] == "hangar"


# ---------------------------------------------------------------------------
# backend= injection into ProductionMemory
# ---------------------------------------------------------------------------

class TestProductionMemoryBackendInjection:

    def test_accepts_in_memory_backend(self):
        b = InMemoryBackend()
        mem = ProductionMemory(backend=b)
        sid = mem.record_scene({"scene_type": "hangar", "status": "success", "score": 0.9})
        assert sid.startswith("scene_")
        assert len(mem.get_scene_history()) == 1

    def test_backend_receives_all_record_types(self):
        b = InMemoryBackend()
        mem = ProductionMemory(backend=b)
        sid = mem.record_scene({"scene_type": "hangar", "status": "success", "score": 0.9})
        mem.record_review(sid, {"overall_score": 0.9, "grade": "A", "production_ready": True})
        mem.record_pattern_usage("pat1", "hangar", "success")
        mem.record_failure({"scene_type": "hangar", "failure_type": "t", "description": ""})
        assert b.count("scene")         == 1
        assert b.count("review")        == 1
        assert b.count("pattern_usage") == 1
        assert b.count("failure")       == 1
        assert b.record_count()         == 4

    def test_stats_delegate_to_backend(self):
        b = InMemoryBackend()
        mem = ProductionMemory(backend=b)
        mem.record_scene({"scene_type": "hangar", "status": "success", "score": 0.9})
        s = mem.stats()
        assert s["write_count"]  == 1
        assert s["record_count"] == 1

    def test_get_statistics_via_injected_backend(self):
        b = InMemoryBackend()
        mem = ProductionMemory(backend=b)
        mem.record_scene({"scene_type": "hangar", "status": "success", "score": 0.9})
        mem.record_scene({"scene_type": "hangar", "status": "failure", "score": 0.3})
        stats = mem.get_statistics()
        assert stats["total_scenes"]  == 2
        assert stats["success_rate"]  == pytest.approx(0.5)
        assert stats["total_records"] == 2

    def test_backend_parameter_takes_precedence_over_path(self, tmp_path):
        """When backend= is supplied, path= is ignored."""
        b = InMemoryBackend()
        path = str(tmp_path / "unused.jsonl")
        mem = ProductionMemory(path=path, backend=b)
        mem.record_scene({"scene_type": "lab", "status": "success", "score": 0.8})
        # The file must NOT have been created
        assert not os.path.exists(path)
        # But the record must be in the injected backend
        assert b.count("scene") == 1

    def test_path_none_uses_in_memory_backend(self):
        mem = ProductionMemory(path=None)
        assert isinstance(mem._backend, InMemoryBackend)

    def test_path_set_uses_jsonl_backend(self, tmp_path):
        path = str(tmp_path / "prod.jsonl")
        mem = ProductionMemory(path=path)
        assert isinstance(mem._backend, JSONLBackend)

    def test_jsonl_backend_persistence_via_production_memory(self, tmp_path):
        path = str(tmp_path / "prod.jsonl")
        mem1 = ProductionMemory(path=path)
        sid = mem1.record_scene({"scene_type": "hangar", "status": "success", "score": 0.9})

        mem2 = ProductionMemory(path=path)
        history = mem2.get_scene_history()
        assert len(history) == 1
        assert history[0]["scene_id"] == sid

    def test_shared_backend_visible_across_two_instances(self):
        """Two ProductionMemory instances sharing a backend see each other's writes."""
        b = InMemoryBackend()
        m1 = ProductionMemory(backend=b)
        m2 = ProductionMemory(backend=b)
        m1.record_scene({"scene_type": "hangar", "status": "success", "score": 0.9})
        assert len(m2.get_scene_history()) == 1


# ---------------------------------------------------------------------------
# _matches static helper
# ---------------------------------------------------------------------------

def test_matches_all_filters():
    b = InMemoryBackend()
    rec = {"record_type": "scene", "a": 1, "b": 2}
    assert b._matches(rec, {"a": 1, "b": 2}) is True


def test_matches_partial_filter():
    b = InMemoryBackend()
    rec = {"record_type": "scene", "a": 1, "b": 2}
    assert b._matches(rec, {"a": 1}) is True


def test_matches_fails_on_wrong_value():
    b = InMemoryBackend()
    rec = {"record_type": "scene", "a": 1}
    assert b._matches(rec, {"a": 99}) is False


def test_matches_empty_filter_always_true():
    b = InMemoryBackend()
    rec = {"record_type": "scene", "x": "y"}
    assert b._matches(rec, {}) is True


def test_matches_missing_key_fails():
    b = InMemoryBackend()
    rec = {"record_type": "scene"}
    assert b._matches(rec, {"nonexistent": "value"}) is False
