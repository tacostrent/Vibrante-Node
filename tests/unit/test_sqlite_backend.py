"""
Tests for src.runtime.storage.sqlite_backend
Covers: SQLiteBackend interface, multi-table schema, persistence, thread safety,
        JSONL migration, corruption recovery, and ProductionMemory integration.

No bridge, no LLM. Pure unit tests.
"""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import threading
import time

import pytest

from src.runtime.storage.memory_backend import ProductionMemoryBackend
from src.runtime.storage.sqlite_backend import (
    SQLiteBackend,
    _TABLE_MAP,
    _is_sqlite_db,
    _read_jsonl,
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


@pytest.fixture()
def db_path(tmp_path):
    return str(tmp_path / "test.db")


@pytest.fixture()
def backend(db_path):
    return SQLiteBackend(db_path)


def _rec(record_type: str, **kwargs) -> dict:
    r = {"record_type": record_type, "timestamp": time.time()}
    r.update(kwargs)
    return r


# ---------------------------------------------------------------------------
# Abstract interface compliance
# ---------------------------------------------------------------------------

class TestAbstractInterface:

    def test_is_subclass_of_backend(self):
        assert issubclass(SQLiteBackend, ProductionMemoryBackend)

    def test_instance_is_backend(self, backend):
        assert isinstance(backend, ProductionMemoryBackend)

    def test_has_all_required_methods(self, backend):
        for method in ("insert", "query", "count", "all_records",
                       "clear", "record_count", "write_count"):
            assert callable(getattr(backend, method))


# ---------------------------------------------------------------------------
# Table map
# ---------------------------------------------------------------------------

class TestTableMap:

    def test_all_required_tables_present(self):
        required = {"scene", "review", "pattern_usage", "failure", "recommendation"}
        assert required == set(_TABLE_MAP.keys())

    def test_table_names(self):
        assert _TABLE_MAP["scene"]         == "scenes"
        assert _TABLE_MAP["review"]        == "reviews"
        assert _TABLE_MAP["pattern_usage"] == "patterns"
        assert _TABLE_MAP["failure"]       == "failures"
        assert _TABLE_MAP["recommendation"] == "recommendations"

    def test_unknown_record_type_raises(self, backend):
        with pytest.raises(ValueError, match="Unknown record_type"):
            backend.insert("bogus_type", _rec("bogus_type"))

    def test_unknown_type_in_query_raises(self, backend):
        with pytest.raises(ValueError):
            backend.query("bogus_type")

    def test_unknown_type_in_count_raises(self, backend):
        with pytest.raises(ValueError):
            backend.count("bogus_type")


# ---------------------------------------------------------------------------
# Schema — all five tables are created on first open
# ---------------------------------------------------------------------------

class TestSchema:

    def test_all_tables_exist_after_first_operation(self, backend, db_path):
        backend.insert("scene", _rec("scene", scene_type="x"))
        conn = sqlite3.connect(db_path)
        tables = {
            r[0] for r in
            conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        conn.close()
        expected = {"scenes", "reviews", "patterns", "failures", "recommendations"}
        assert expected.issubset(tables)

    def test_wal_mode_enabled(self, backend, db_path):
        backend.insert("scene", _rec("scene", scene_type="x"))
        conn = sqlite3.connect(db_path)
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        conn.close()
        assert mode == "wal"

    def test_each_table_has_timestamp_index(self, backend, db_path):
        backend.insert("scene", _rec("scene", scene_type="x"))
        conn = sqlite3.connect(db_path)
        indexes = {
            r[0] for r in
            conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()
        }
        conn.close()
        for expected in ("idx_scenes_ts", "idx_reviews_ts", "idx_patterns_ts",
                         "idx_failures_ts", "idx_recommendations_ts"):
            assert expected in indexes


# ---------------------------------------------------------------------------
# Insert and query — all record types
# ---------------------------------------------------------------------------

class TestInsertAndQuery:

    def test_insert_scene(self, backend):
        backend.insert("scene", _rec("scene", scene_type="hangar"))
        results = backend.query("scene")
        assert len(results) == 1
        assert results[0]["scene_type"] == "hangar"

    def test_insert_review(self, backend):
        backend.insert("review", _rec("review", grade="A", record_id="rev_001"))
        results = backend.query("review")
        assert len(results) == 1
        assert results[0]["grade"] == "A"

    def test_insert_pattern_usage(self, backend):
        backend.insert("pattern_usage", _rec("pattern_usage", outcome="success", pattern_id="p1"))
        results = backend.query("pattern_usage")
        assert len(results) == 1
        assert results[0]["outcome"] == "success"

    def test_insert_failure(self, backend):
        backend.insert("failure", _rec("failure", failure_type="fog_high", failure_id="f1"))
        results = backend.query("failure")
        assert len(results) == 1
        assert results[0]["failure_type"] == "fog_high"

    def test_insert_recommendation(self, backend):
        backend.insert("recommendation", _rec("recommendation", intent="build_pyro"))
        results = backend.query("recommendation")
        assert len(results) == 1
        assert results[0]["intent"] == "build_pyro"

    def test_tables_are_isolated(self, backend):
        """Records in one table are not visible when querying another."""
        backend.insert("scene",   _rec("scene",   scene_type="hangar"))
        backend.insert("failure", _rec("failure", failure_type="fog"))
        assert len(backend.query("scene"))   == 1
        assert len(backend.query("failure")) == 1
        assert len(backend.query("review"))  == 0

    def test_query_filter(self, backend):
        backend.insert("scene", _rec("scene", scene_type="hangar", status="success"))
        backend.insert("scene", _rec("scene", scene_type="hangar", status="failure"))
        results = backend.query("scene", filters={"status": "success"})
        assert len(results) == 1
        assert results[0]["status"] == "success"

    def test_query_multiple_filters(self, backend):
        backend.insert("scene", _rec("scene", scene_type="hangar", status="success"))
        backend.insert("scene", _rec("scene", scene_type="lab",    status="success"))
        results = backend.query("scene", filters={"scene_type": "hangar", "status": "success"})
        assert len(results) == 1

    def test_query_order_desc(self, backend):
        for i in range(4):
            backend.insert("scene", _rec("scene", scene_type="x", timestamp=float(i)))
        results = backend.query("scene", order_desc=True)
        ts = [r["timestamp"] for r in results]
        assert ts == sorted(ts, reverse=True)

    def test_query_order_asc(self, backend):
        for i in range(4):
            backend.insert("scene", _rec("scene", scene_type="x", timestamp=float(i)))
        results = backend.query("scene", order_desc=False)
        ts = [r["timestamp"] for r in results]
        assert ts == sorted(ts)

    def test_query_limit(self, backend):
        for _ in range(10):
            backend.insert("scene", _rec("scene", scene_type="x"))
        assert len(backend.query("scene", limit=3)) == 3

    def test_query_returns_copies(self, backend):
        backend.insert("scene", _rec("scene", scene_type="hangar"))
        result = backend.query("scene")[0]
        result["scene_type"] = "MUTATED"
        stored = backend.query("scene")[0]
        assert stored["scene_type"] == "hangar"

    def test_query_preserves_record_type_field(self, backend):
        backend.insert("scene", _rec("scene", scene_type="hangar"))
        result = backend.query("scene")[0]
        assert result["record_type"] == "scene"

    def test_empty_query_returns_empty_list(self, backend):
        assert backend.query("scene") == []


# ---------------------------------------------------------------------------
# Count
# ---------------------------------------------------------------------------

class TestCount:

    def test_count_no_filter(self, backend):
        backend.insert("scene", _rec("scene", scene_type="x"))
        backend.insert("scene", _rec("scene", scene_type="y"))
        assert backend.count("scene") == 2

    def test_count_with_filter(self, backend):
        backend.insert("scene", _rec("scene", scene_type="hangar"))
        backend.insert("scene", _rec("scene", scene_type="lab"))
        assert backend.count("scene", filters={"scene_type": "hangar"}) == 1

    def test_count_empty_table(self, backend):
        assert backend.count("scene") == 0

    def test_count_cross_table_isolation(self, backend):
        backend.insert("scene",   _rec("scene"))
        backend.insert("failure", _rec("failure"))
        assert backend.count("scene")   == 1
        assert backend.count("failure") == 1
        assert backend.count("review")  == 0


# ---------------------------------------------------------------------------
# all_records
# ---------------------------------------------------------------------------

class TestAllRecords:

    def test_all_records_no_limit(self, backend):
        for _ in range(5):
            backend.insert("scene", _rec("scene", scene_type="x"))
        backend.insert("failure", _rec("failure"))
        assert len(backend.all_records("scene"))   == 5
        assert len(backend.all_records("failure")) == 1

    def test_all_records_empty(self, backend):
        assert backend.all_records("scene") == []


# ---------------------------------------------------------------------------
# record_count and write_count
# ---------------------------------------------------------------------------

class TestCounters:

    def test_record_count_sums_all_tables(self, backend):
        backend.insert("scene",   _rec("scene"))
        backend.insert("review",  _rec("review"))
        backend.insert("failure", _rec("failure"))
        assert backend.record_count() == 3

    def test_record_count_zero_initially(self, backend):
        assert backend.record_count() == 0

    def test_write_count_increments(self, backend):
        assert backend.write_count() == 0
        backend.insert("scene", _rec("scene"))
        backend.insert("scene", _rec("scene"))
        assert backend.write_count() == 2

    def test_write_count_reset_by_clear(self, backend):
        backend.insert("scene", _rec("scene"))
        backend.clear()
        assert backend.write_count() == 0

    def test_record_count_reset_by_clear(self, backend):
        backend.insert("scene",   _rec("scene"))
        backend.insert("failure", _rec("failure"))
        backend.clear()
        assert backend.record_count() == 0


# ---------------------------------------------------------------------------
# clear
# ---------------------------------------------------------------------------

class TestClear:

    def test_clear_empties_all_tables(self, backend):
        for rt in ("scene", "review", "pattern_usage", "failure"):
            backend.insert(rt, _rec(rt))
        backend.clear()
        for rt in ("scene", "review", "pattern_usage", "failure"):
            assert backend.count(rt) == 0

    def test_clear_resets_write_count(self, backend):
        backend.insert("scene", _rec("scene"))
        backend.clear()
        assert backend.write_count() == 0


# ---------------------------------------------------------------------------
# Persistence (round-trip)
# ---------------------------------------------------------------------------

class TestPersistence:

    def test_round_trip_scenes(self, db_path):
        b1 = SQLiteBackend(db_path)
        b1.insert("scene", _rec("scene", scene_type="hangar", status="success"))

        b2 = SQLiteBackend(db_path)
        results = b2.query("scene")
        assert len(results) == 1
        assert results[0]["scene_type"] == "hangar"

    def test_round_trip_all_types(self, db_path):
        b1 = SQLiteBackend(db_path)
        b1.insert("scene",         _rec("scene",         scene_type="hangar"))
        b1.insert("review",        _rec("review",        grade="B"))
        b1.insert("pattern_usage", _rec("pattern_usage", outcome="success"))
        b1.insert("failure",       _rec("failure",       failure_type="fog"))

        b2 = SQLiteBackend(db_path)
        assert b2.count("scene")         == 1
        assert b2.count("review")        == 1
        assert b2.count("pattern_usage") == 1
        assert b2.count("failure")       == 1
        assert b2.record_count()         == 4

    def test_second_instance_preserves_order(self, db_path):
        b1 = SQLiteBackend(db_path)
        for i in range(3):
            b1.insert("scene", _rec("scene", scene_type="x", timestamp=float(i)))

        b2 = SQLiteBackend(db_path)
        results = b2.query("scene", order_desc=True)
        ts = [r["timestamp"] for r in results]
        assert ts == sorted(ts, reverse=True)

    def test_data_persists_after_clear_and_reinsert(self, db_path):
        b1 = SQLiteBackend(db_path)
        b1.insert("scene", _rec("scene", scene_type="old"))
        b1.clear()
        b1.insert("scene", _rec("scene", scene_type="new"))

        b2 = SQLiteBackend(db_path)
        results = b2.query("scene")
        assert len(results) == 1
        assert results[0]["scene_type"] == "new"

    def test_write_count_not_persisted(self, db_path):
        """write_count is in-memory per instance — not stored in the DB."""
        b1 = SQLiteBackend(db_path)
        b1.insert("scene", _rec("scene"))
        assert b1.write_count() == 1

        b2 = SQLiteBackend(db_path)
        # New instance starts at 0 even though the record is in the DB
        assert b2.write_count() == 0


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:

    def test_concurrent_inserts_all_land(self, db_path):
        """100 concurrent threads inserting scenes — every record must be present."""
        backend = SQLiteBackend(db_path)
        errors: list = []
        N = 100

        def worker(i: int):
            try:
                backend.insert("scene", _rec("scene", scene_type=f"type_{i}"))
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(N)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Thread errors: {errors}"
        assert backend.record_count() == N

    def test_concurrent_reads_and_writes(self, db_path):
        """Readers and writers coexist without raising."""
        backend = SQLiteBackend(db_path)
        # Pre-populate
        for i in range(20):
            backend.insert("scene", _rec("scene", scene_type=f"t_{i}"))

        errors: list = []

        def writer():
            try:
                for _ in range(10):
                    backend.insert("scene", _rec("scene", scene_type="writer"))
            except Exception as exc:
                errors.append(exc)

        def reader():
            try:
                for _ in range(10):
                    backend.query("scene", limit=5)
            except Exception as exc:
                errors.append(exc)

        threads = (
            [threading.Thread(target=writer) for _ in range(3)]
            + [threading.Thread(target=reader) for _ in range(5)]
        )
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Concurrent errors: {errors}"

    def test_write_count_accurate_after_concurrent_inserts(self, db_path):
        backend = SQLiteBackend(db_path)
        N = 50

        def worker():
            for _ in range(N):
                backend.insert("scene", _rec("scene", scene_type="x"))

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert backend.write_count() == N * 4
        assert backend.record_count() == N * 4


# ---------------------------------------------------------------------------
# JSONL migration
# ---------------------------------------------------------------------------

class TestJsonlMigration:

    def _write_jsonl(self, path: str, records: list) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            for rec in records:
                fh.write(json.dumps(rec) + "\n")

    def test_jsonl_file_is_migrated(self, tmp_path):
        """Pointing SQLiteBackend at a JSONL path migrates records into SQLite."""
        jsonl_path = str(tmp_path / "prod.jsonl")
        self._write_jsonl(jsonl_path, [
            {"record_type": "scene",   "scene_type": "hangar", "timestamp": 1.0,
             "status": "success", "score": 0.9},
            {"record_type": "failure", "failure_type": "fog",  "timestamp": 2.0,
             "scene_type": "hangar", "description": ""},
        ])

        # Open with SQLiteBackend — it detects JSONL and migrates
        b = SQLiteBackend(jsonl_path)
        assert b.count("scene")   == 1
        assert b.count("failure") == 1
        assert b.query("scene")[0]["scene_type"] == "hangar"

    def test_migrated_data_persists_in_sqlite(self, tmp_path):
        """After the first operation the file is a proper SQLite database."""
        jsonl_path = str(tmp_path / "prod.jsonl")
        self._write_jsonl(jsonl_path, [
            {"record_type": "scene", "scene_type": "lab", "timestamp": 1.0,
             "status": "success", "score": 0.8},
        ])

        b = SQLiteBackend(jsonl_path)
        b.record_count()  # trigger lazy open → migration runs

        # File should now be a valid SQLite database
        assert _is_sqlite_db(jsonl_path)

    def test_second_open_after_migration_reads_sqlite(self, tmp_path):
        """A second SQLiteBackend instance opens the migrated DB, not JSONL."""
        jsonl_path = str(tmp_path / "prod.jsonl")
        self._write_jsonl(jsonl_path, [
            {"record_type": "scene", "scene_type": "hangar", "timestamp": 1.0,
             "status": "success", "score": 0.9},
        ])

        b1 = SQLiteBackend(jsonl_path)
        b1.insert("scene", _rec("scene", scene_type="new"))

        b2 = SQLiteBackend(jsonl_path)
        assert b2.count("scene") == 2

    def test_corrupt_jsonl_lines_skipped_during_migration(self, tmp_path):
        jsonl_path = str(tmp_path / "prod.jsonl")
        with open(jsonl_path, "w", encoding="utf-8") as fh:
            fh.write('{"record_type": "scene", "scene_type": "ok", "timestamp": 1.0}\n')
            fh.write("NOT_JSON{{{\n")
            fh.write('{"record_type": "failure", "failure_type": "fog", '
                     '"scene_type": "ok", "description": "", "timestamp": 2.0}\n')

        b = SQLiteBackend(jsonl_path)
        assert b.count("scene")   == 1
        assert b.count("failure") == 1

    def test_unknown_record_type_skipped_during_migration(self, tmp_path):
        jsonl_path = str(tmp_path / "prod.jsonl")
        self._write_jsonl(jsonl_path, [
            {"record_type": "scene",   "scene_type": "x", "timestamp": 1.0},
            {"record_type": "UNKNOWN", "data": "x",       "timestamp": 2.0},
        ])

        b = SQLiteBackend(jsonl_path)
        assert b.count("scene") == 1
        # No crash; unknown type was silently skipped

    def test_migration_write_count_reflects_imported_records(self, tmp_path):
        jsonl_path = str(tmp_path / "prod.jsonl")
        self._write_jsonl(jsonl_path, [
            {"record_type": "scene",   "scene_type": "x", "timestamp": 1.0},
            {"record_type": "failure", "failure_type": "t", "scene_type": "x",
             "description": "", "timestamp": 2.0},
        ])

        b = SQLiteBackend(jsonl_path)
        b.record_count()  # trigger lazy open → migration runs and increments _writes
        assert b.write_count() == 2


# ---------------------------------------------------------------------------
# Corruption recovery
# ---------------------------------------------------------------------------

class TestCorruptionRecovery:

    def test_non_sqlite_file_treated_as_jsonl(self, tmp_path):
        """A non-SQLite binary file is treated as JSONL (gets 0 records), not a crash."""
        bad_path = str(tmp_path / "corrupt.db")
        with open(bad_path, "wb") as fh:
            fh.write(b"\x00\x01\x02\x03garbage data\n")

        b = SQLiteBackend(bad_path)
        # Should open cleanly with 0 records
        assert b.record_count() == 0
        # And should be insertable
        b.insert("scene", _rec("scene", scene_type="x"))
        assert b.record_count() == 1

    def test_empty_file_starts_fresh(self, tmp_path):
        empty_path = str(tmp_path / "empty.db")
        open(empty_path, "wb").close()

        b = SQLiteBackend(empty_path)
        assert b.record_count() == 0

    def test_missing_file_creates_database(self, tmp_path):
        new_path = str(tmp_path / "brand_new.db")
        assert not os.path.exists(new_path)

        b = SQLiteBackend(new_path)
        b.insert("scene", _rec("scene", scene_type="x"))
        assert os.path.exists(new_path)
        assert b.record_count() == 1

    def test_corrupt_sqlite_header_recovered(self, tmp_path):
        """A file with a valid SQLite magic but corrupt body is recovered."""
        bad_path = str(tmp_path / "corrupt_sqlite.db")
        # Write the SQLite magic header followed by garbage
        with open(bad_path, "wb") as fh:
            fh.write(b"SQLite format 3\x00" + b"\x00" * 100)

        b = SQLiteBackend(bad_path)
        # After recovery the backend must be usable
        b.insert("scene", _rec("scene", scene_type="x"))
        assert b.record_count() == 1

    def test_two_backends_share_recovered_database(self, tmp_path):
        bad_path = str(tmp_path / "bad.db")
        with open(bad_path, "wb") as fh:
            fh.write(b"\xDE\xAD\xBE\xEF" * 50)

        b1 = SQLiteBackend(bad_path)
        b1.insert("scene", _rec("scene", scene_type="hangar"))

        b2 = SQLiteBackend(bad_path)
        assert b2.count("scene") == 1


# ---------------------------------------------------------------------------
# ProductionMemory integration
# ---------------------------------------------------------------------------

class TestProductionMemoryIntegration:

    def test_sqlite_backend_injected(self, db_path):
        b   = SQLiteBackend(db_path)
        mem = ProductionMemory(backend=b)
        sid = mem.record_scene({"scene_type": "hangar", "status": "success", "score": 0.9})
        assert sid.startswith("scene_")
        assert len(mem.get_scene_history()) == 1

    def test_all_record_types_via_production_memory(self, db_path):
        b   = SQLiteBackend(db_path)
        mem = ProductionMemory(backend=b)
        sid = mem.record_scene({"scene_type": "hangar", "status": "success", "score": 0.9})
        mem.record_review(sid, {"overall_score": 0.9, "grade": "A", "production_ready": True})
        mem.record_pattern_usage("pat1", "hangar", "success")
        mem.record_failure({"scene_type": "hangar", "failure_type": "fog", "description": ""})
        stats = mem.get_statistics()
        assert stats["total_scenes"]         == 1
        assert stats["total_reviews"]        == 1
        assert stats["total_pattern_usages"] == 1
        assert stats["total_failures"]       == 1
        assert stats["total_records"]        == 4

    def test_persistence_via_production_memory(self, db_path):
        mem1 = ProductionMemory(backend=SQLiteBackend(db_path))
        sid  = mem1.record_scene({"scene_type": "hangar", "status": "success", "score": 0.9})

        mem2 = ProductionMemory(backend=SQLiteBackend(db_path))
        hist = mem2.get_scene_history()
        assert len(hist) == 1
        assert hist[0]["scene_id"] == sid

    def test_path_extension_db_uses_sqlite_backend(self, tmp_path):
        path = str(tmp_path / "prod.db")
        mem  = ProductionMemory(path=path)
        assert isinstance(mem._backend, SQLiteBackend)

    def test_path_extension_sqlite_uses_sqlite_backend(self, tmp_path):
        path = str(tmp_path / "prod.sqlite")
        mem  = ProductionMemory(path=path)
        assert isinstance(mem._backend, SQLiteBackend)

    def test_path_extension_sqlite3_uses_sqlite_backend(self, tmp_path):
        path = str(tmp_path / "prod.sqlite3")
        mem  = ProductionMemory(path=path)
        assert isinstance(mem._backend, SQLiteBackend)

    def test_path_extension_jsonl_uses_jsonl_backend(self, tmp_path):
        from src.runtime.storage.memory_backend import JSONLBackend
        path = str(tmp_path / "prod.jsonl")
        mem  = ProductionMemory(path=path)
        assert isinstance(mem._backend, JSONLBackend)

    def test_end_to_end_statistics_via_sqlite(self, db_path):
        mem = ProductionMemory(backend=SQLiteBackend(db_path))
        mem.record_scene({"scene_type": "hangar", "status": "success", "score": 0.9})
        mem.record_scene({"scene_type": "hangar", "status": "failure", "score": 0.3})
        mem.record_scene({"scene_type": "lab",    "status": "success", "score": 0.8})
        stats = mem.get_statistics()
        assert stats["total_scenes"]          == 3
        assert stats["success_rate"]          == pytest.approx(2 / 3)
        assert stats["scenes_by_type"]["hangar"] == 2
        assert stats["scenes_by_type"]["lab"]    == 1

    def test_sqlite_scene_history_newest_first(self, db_path):
        mem = ProductionMemory(backend=SQLiteBackend(db_path))
        for i in range(3):
            mem.record_scene({"scene_type": "lab", "status": "success", "score": float(i) / 10})
        history = mem.get_scene_history()
        ts = [r["timestamp"] for r in history]
        assert ts == sorted(ts, reverse=True)


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------

class TestHelpers:

    def test_is_sqlite_db_true_for_valid_file(self, db_path):
        b = SQLiteBackend(db_path)
        b.insert("scene", _rec("scene", scene_type="x"))
        assert _is_sqlite_db(db_path) is True

    def test_is_sqlite_db_false_for_jsonl(self, tmp_path):
        jsonl_path = str(tmp_path / "records.jsonl")
        with open(jsonl_path, "w") as fh:
            fh.write('{"record_type": "scene"}\n')
        assert _is_sqlite_db(jsonl_path) is False

    def test_is_sqlite_db_false_for_missing_file(self):
        assert _is_sqlite_db("/nonexistent/path.db") is False

    def test_read_jsonl_returns_valid_dicts(self, tmp_path):
        path = str(tmp_path / "data.jsonl")
        with open(path, "w") as fh:
            fh.write('{"a": 1}\n')
            fh.write('{"b": 2}\n')
        records = _read_jsonl(path)
        assert records == [{"a": 1}, {"b": 2}]

    def test_read_jsonl_skips_corrupt_lines(self, tmp_path):
        path = str(tmp_path / "data.jsonl")
        with open(path, "w") as fh:
            fh.write('{"a": 1}\n')
            fh.write("CORRUPT\n")
            fh.write('{"c": 3}\n')
        records = _read_jsonl(path)
        assert len(records) == 2

    def test_read_jsonl_skips_non_dict_entries(self, tmp_path):
        path = str(tmp_path / "data.jsonl")
        with open(path, "w") as fh:
            fh.write('{"a": 1}\n')
            fh.write('[1, 2, 3]\n')
        records = _read_jsonl(path)
        assert len(records) == 1

    def test_read_jsonl_missing_file_returns_empty(self):
        records = _read_jsonl("/nonexistent/path.jsonl")
        assert records == []
