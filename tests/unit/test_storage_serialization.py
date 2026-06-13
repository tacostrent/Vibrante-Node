"""
Tests for src.runtime.storage.serialization
Covers: serialize_record, deserialize_record, all type-specific pairs,
        determinism, migration framework, and JSONLBackend integration.

No bridge, no LLM. Pure unit tests.
"""

from __future__ import annotations

import json
import os
import tempfile
import time

import pytest

from src.runtime.storage.serialization import (
    SCHEMA_VERSION,
    _VERSION_KEY,
    _apply_migrations,
    deserialize_asset,
    deserialize_failure,
    deserialize_pattern,
    deserialize_record,
    deserialize_relationship,
    deserialize_review,
    deserialize_scene,
    register_migrator,
    reset_migrators_for_tests,
    serialize_asset,
    serialize_failure,
    serialize_pattern,
    serialize_record,
    serialize_relationship,
    serialize_review,
    serialize_scene,
)
from src.runtime.storage.memory_backend import JSONLBackend


@pytest.fixture(autouse=True)
def clean_migrators():
    reset_migrators_for_tests()
    yield
    reset_migrators_for_tests()


# ---------------------------------------------------------------------------
# serialize_record — core contract
# ---------------------------------------------------------------------------

class TestSerializeRecord:

    def test_returns_string(self):
        assert isinstance(serialize_record({"a": 1}), str)

    def test_output_is_valid_json(self):
        s = serialize_record({"scene_type": "hangar", "score": 0.9})
        parsed = json.loads(s)
        assert isinstance(parsed, dict)

    def test_embeds_schema_version(self):
        s = serialize_record({"a": 1})
        parsed = json.loads(s)
        assert parsed[_VERSION_KEY] == SCHEMA_VERSION

    def test_does_not_overwrite_existing_schema_version(self):
        """Caller-supplied _schema_version (e.g. during migration) is preserved."""
        s = serialize_record({"a": 1, _VERSION_KEY: 99})
        parsed = json.loads(s)
        assert parsed[_VERSION_KEY] == 99

    def test_does_not_mutate_input(self):
        rec = {"a": 1}
        serialize_record(rec)
        assert _VERSION_KEY not in rec

    def test_keys_are_sorted(self):
        s = serialize_record({"z": 1, "a": 2, "m": 3})
        raw_keys = list(json.loads(s).keys())
        assert raw_keys == sorted(raw_keys)

    def test_non_serializable_coerced_to_string(self):
        import uuid
        uid = uuid.uuid4()
        s = serialize_record({"id": uid})
        parsed = json.loads(s)
        assert parsed["id"] == str(uid)

    def test_nested_dict_keys_sorted(self):
        s = serialize_record({"outer": {"z": 1, "a": 2}})
        inner = json.loads(s)["outer"]
        assert list(inner.keys()) == sorted(inner.keys())

    def test_empty_dict_serializes(self):
        s = serialize_record({})
        parsed = json.loads(s)
        assert parsed[_VERSION_KEY] == SCHEMA_VERSION

    def test_preserves_all_scalar_types(self):
        rec = {"i": 1, "f": 1.5, "b": True, "n": None, "s": "hello"}
        s = serialize_record(rec)
        parsed = json.loads(s)
        assert parsed["i"] == 1
        assert parsed["f"] == pytest.approx(1.5)
        assert parsed["b"] is True
        assert parsed["n"] is None
        assert parsed["s"] == "hello"


# ---------------------------------------------------------------------------
# deserialize_record — core contract
# ---------------------------------------------------------------------------

class TestDeserializeRecord:

    def test_returns_dict(self):
        s = serialize_record({"a": 1})
        result = deserialize_record(s)
        assert isinstance(result, dict)

    def test_strips_schema_version(self):
        s = serialize_record({"a": 1})
        result = deserialize_record(s)
        assert _VERSION_KEY not in result

    def test_preserves_all_other_keys(self):
        rec = {"scene_type": "hangar", "score": 0.9, "status": "success"}
        result = deserialize_record(serialize_record(rec))
        for k, v in rec.items():
            assert result[k] == v

    def test_empty_string_returns_empty_dict(self):
        assert deserialize_record("") == {}

    def test_invalid_json_returns_empty_dict(self):
        assert deserialize_record("NOT_JSON{{{") == {}

    def test_none_returns_empty_dict(self):
        assert deserialize_record(None) == {}  # type: ignore[arg-type]

    def test_json_array_returns_empty_dict(self):
        assert deserialize_record("[1, 2, 3]") == {}

    def test_json_string_returns_empty_dict(self):
        assert deserialize_record('"just a string"') == {}

    def test_no_schema_version_treated_as_v1(self):
        """Records written without _schema_version (pre-versioning) load fine."""
        raw = json.dumps({"record_type": "scene", "scene_type": "x"})
        result = deserialize_record(raw)
        assert result["scene_type"] == "x"
        assert _VERSION_KEY not in result

    def test_current_version_no_migration_applied(self):
        raw = json.dumps({"record_type": "scene", _VERSION_KEY: SCHEMA_VERSION})
        result = deserialize_record(raw)
        # Should come back clean — no _schema_version, no extra keys
        assert _VERSION_KEY not in result


# ---------------------------------------------------------------------------
# Round-trip fidelity
# ---------------------------------------------------------------------------

class TestRoundTrip:

    def _rt(self, record):
        return deserialize_record(serialize_record(record))

    def test_simple_round_trip(self):
        rec = {"record_type": "scene", "scene_type": "hangar", "score": 0.9}
        assert self._rt(rec) == rec

    def test_round_trip_with_nested_dict(self):
        rec = {"record_type": "review", "dimensions": {"a": 1, "b": 2}}
        assert self._rt(rec) == rec

    def test_round_trip_with_list(self):
        rec = {"record_type": "scene", "findings": ["issue1", "issue2"]}
        assert self._rt(rec) == rec

    def test_round_trip_preserves_float_precision(self):
        rec = {"score": 0.123456789}
        result = self._rt(rec)
        assert result["score"] == pytest.approx(0.123456789)

    def test_round_trip_none_value(self):
        rec = {"record_type": "scene", "optional": None}
        assert self._rt(rec) == rec

    def test_round_trip_bool_values(self):
        rec = {"production_ready": True, "has_errors": False}
        result = self._rt(rec)
        assert result["production_ready"] is True
        assert result["has_errors"] is False


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:

    def test_same_input_same_output(self):
        rec = {"z": 3, "a": 1, "m": 2, "record_type": "scene"}
        outputs = {serialize_record(rec) for _ in range(20)}
        assert len(outputs) == 1

    def test_insertion_order_does_not_affect_output(self):
        r1 = {"a": 1, "b": 2, "c": 3}
        r2 = {"c": 3, "b": 2, "a": 1}
        assert serialize_record(r1) == serialize_record(r2)

    def test_different_values_produce_different_output(self):
        r1 = serialize_record({"scene_type": "hangar"})
        r2 = serialize_record({"scene_type": "lab"})
        assert r1 != r2

    def test_extra_key_produces_different_output(self):
        r1 = serialize_record({"a": 1})
        r2 = serialize_record({"a": 1, "b": 2})
        assert r1 != r2

    def test_deterministic_across_types(self):
        rec = {"record_type": "scene", "x": 1}
        assert serialize_scene(rec) == serialize_record(rec)
        assert serialize_review(rec) == serialize_record(rec)
        assert serialize_pattern(rec) == serialize_record(rec)
        assert serialize_failure(rec) == serialize_record(rec)
        assert serialize_asset(rec) == serialize_record(rec)
        assert serialize_relationship(rec) == serialize_record(rec)


# ---------------------------------------------------------------------------
# Type-specific helpers
# ---------------------------------------------------------------------------

class TestTypeSpecificPairs:

    def _rt(self, serialize_fn, deserialize_fn, record):
        return deserialize_fn(serialize_fn(record))

    def test_scene_round_trip(self):
        rec = {"record_type": "scene", "scene_type": "hangar", "score": 0.9}
        assert self._rt(serialize_scene, deserialize_scene, rec) == rec

    def test_review_round_trip(self):
        rec = {"record_type": "review", "grade": "A", "production_ready": True}
        assert self._rt(serialize_review, deserialize_review, rec) == rec

    def test_pattern_round_trip(self):
        rec = {"record_type": "pattern_usage", "outcome": "success", "pattern_id": "p1"}
        assert self._rt(serialize_pattern, deserialize_pattern, rec) == rec

    def test_failure_round_trip(self):
        rec = {"record_type": "failure", "failure_type": "fog_high", "scene_type": "x"}
        assert self._rt(serialize_failure, deserialize_failure, rec) == rec

    def test_asset_round_trip(self):
        rec = {"record_type": "asset", "asset_id": "a1", "category": "vehicle"}
        assert self._rt(serialize_asset, deserialize_asset, rec) == rec

    def test_relationship_round_trip(self):
        rec = {"record_type": "relationship", "source": "a1", "target": "a2"}
        assert self._rt(serialize_relationship, deserialize_relationship, rec) == rec

    def test_type_specific_serialize_returns_string(self):
        for fn in (serialize_scene, serialize_review, serialize_pattern,
                   serialize_failure, serialize_asset, serialize_relationship):
            assert isinstance(fn({"record_type": "x"}), str)

    def test_type_specific_deserialize_strips_version(self):
        for ser, des in (
            (serialize_scene,        deserialize_scene),
            (serialize_review,       deserialize_review),
            (serialize_pattern,      deserialize_pattern),
            (serialize_failure,      deserialize_failure),
            (serialize_asset,        deserialize_asset),
            (serialize_relationship, deserialize_relationship),
        ):
            result = des(ser({"a": 1}))
            assert _VERSION_KEY not in result

    def test_type_specific_deserialize_errors_return_empty_dict(self):
        for des in (deserialize_scene, deserialize_review, deserialize_pattern,
                    deserialize_failure, deserialize_asset, deserialize_relationship):
            assert des("NOT_JSON") == {}


# ---------------------------------------------------------------------------
# Migration framework
# ---------------------------------------------------------------------------

class TestMigrationFramework:

    def test_no_migrators_registered_is_noop(self):
        """With no migrators, records at any version pass through unchanged."""
        rec = {"record_type": "scene", "scene_type": "x"}
        # Write a fake v1 record (no _schema_version in raw, so defaults to v1)
        raw = json.dumps(rec)
        result = deserialize_record(raw)
        assert result == rec

    def test_register_and_apply_generic_migrator(self):
        """A generic migrator (record_type=None) fires for any record type."""
        register_migrator(
            from_version=0,
            record_type=None,
            fn=lambda r: {**r, "migrated": True},
        )
        # Simulate a v0 record
        raw = json.dumps({"record_type": "scene", "x": 1, _VERSION_KEY: 0})
        result = deserialize_record(raw)
        assert result.get("migrated") is True

    def test_register_and_apply_type_specific_migrator(self):
        """A type-specific migrator fires only for matching record_type."""
        register_migrator(
            from_version=0,
            record_type="scene",
            fn=lambda r: {**r, "scene_migrated": True},
        )
        # scene record → migrated
        scene_raw = json.dumps({"record_type": "scene", _VERSION_KEY: 0})
        assert deserialize_record(scene_raw).get("scene_migrated") is True

        # review record → NOT migrated (different type)
        review_raw = json.dumps({"record_type": "review", _VERSION_KEY: 0})
        assert "scene_migrated" not in deserialize_record(review_raw)

    def test_type_specific_beats_generic_for_same_version(self):
        """Type-specific migrator takes priority; generic does NOT also fire."""
        register_migrator(from_version=0, record_type="scene",
                          fn=lambda r: {**r, "source": "specific"})
        register_migrator(from_version=0, record_type=None,
                          fn=lambda r: {**r, "source": "generic"})

        raw = json.dumps({"record_type": "scene", _VERSION_KEY: 0})
        result = deserialize_record(raw)
        assert result["source"] == "specific"

    def test_generic_fires_when_no_type_specific(self):
        """When no type-specific migrator exists, generic fires."""
        register_migrator(from_version=0, record_type="scene",
                          fn=lambda r: {**r, "source": "specific"})
        register_migrator(from_version=0, record_type=None,
                          fn=lambda r: {**r, "source": "generic"})

        raw = json.dumps({"record_type": "review", _VERSION_KEY: 0})
        result = deserialize_record(raw)
        assert result["source"] == "generic"

    def test_current_version_record_skips_migration(self):
        """Records already at SCHEMA_VERSION are never passed to migrators."""
        fired = []
        register_migrator(from_version=SCHEMA_VERSION, record_type=None,
                          fn=lambda r: (fired.append(True), r)[1])
        raw = serialize_record({"record_type": "scene"})
        deserialize_record(raw)
        assert fired == []

    def test_reset_migrators_clears_registry(self):
        register_migrator(from_version=0, record_type=None,
                          fn=lambda r: {**r, "migrated": True})
        reset_migrators_for_tests()
        raw = json.dumps({"record_type": "scene", _VERSION_KEY: 0})
        result = deserialize_record(raw)
        assert "migrated" not in result

    def test_apply_migrations_identity_at_current_version(self):
        """_apply_migrations is a no-op when from_version == SCHEMA_VERSION."""
        rec = {"record_type": "scene", "x": 1}
        assert _apply_migrations(rec, SCHEMA_VERSION) == rec

    def test_apply_migrations_does_not_mutate_input(self):
        register_migrator(from_version=0, record_type=None,
                          fn=lambda r: {**r, "added": True})
        rec = {"record_type": "scene"}
        _apply_migrations(rec, 0)
        assert "added" not in rec

    def test_migrator_can_rename_field(self):
        """Practical example: rename 'old_score' → 'score'."""
        register_migrator(
            from_version=0,
            record_type="scene",
            fn=lambda r: {**{k: v for k, v in r.items() if k != "old_score"},
                          "score": r.get("old_score", 0.0)},
        )
        raw = json.dumps({"record_type": "scene", "old_score": 0.8, _VERSION_KEY: 0})
        result = deserialize_record(raw)
        assert result["score"] == pytest.approx(0.8)
        assert "old_score" not in result

    def test_migrator_can_add_default_field(self):
        """Practical example: add 'atmosphere_type' with a safe default."""
        register_migrator(
            from_version=0,
            record_type=None,
            fn=lambda r: {**r, "atmosphere_type": r.get("atmosphere_type", "none")},
        )
        raw = json.dumps({"record_type": "scene", _VERSION_KEY: 0})
        result = deserialize_record(raw)
        assert result["atmosphere_type"] == "none"


# ---------------------------------------------------------------------------
# JSONLBackend integration — serialization layer used end-to-end
# ---------------------------------------------------------------------------

class TestJSONLBackendIntegration:

    @pytest.fixture()
    def tmp_jsonl(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False
        ) as f:
            path = f.name
        yield path
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass

    def test_written_lines_contain_schema_version(self, tmp_jsonl):
        """insert() now writes through serialize_record — every line has _schema_version."""
        b = JSONLBackend(tmp_jsonl)
        b.insert("scene", {"record_type": "scene", "scene_type": "hangar",
                            "timestamp": time.time()})

        with open(tmp_jsonl, "r", encoding="utf-8") as fh:
            raw = fh.read().strip()

        parsed = json.loads(raw)
        assert _VERSION_KEY in parsed
        assert parsed[_VERSION_KEY] == SCHEMA_VERSION

    def test_query_results_do_not_contain_schema_version(self, tmp_jsonl):
        """Records in memory (and returned by query) never expose _schema_version."""
        b = JSONLBackend(tmp_jsonl)
        b.insert("scene", {"record_type": "scene", "scene_type": "hangar",
                            "timestamp": time.time()})
        result = b.query("scene")[0]
        assert _VERSION_KEY not in result

    def test_old_jsonl_without_schema_version_loads(self, tmp_jsonl):
        """Files written before the serialization layer (no _schema_version) load fine."""
        with open(tmp_jsonl, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "record_type": "scene", "scene_type": "legacy",
                "timestamp": 1.0, "status": "success",
            }) + "\n")

        b = JSONLBackend(tmp_jsonl)
        results = b.query("scene")
        assert len(results) == 1
        assert results[0]["scene_type"] == "legacy"
        assert _VERSION_KEY not in results[0]

    def test_corrupt_line_skipped(self, tmp_jsonl):
        with open(tmp_jsonl, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "record_type": "scene", "scene_type": "x", "timestamp": 1.0,
            }) + "\n")
            fh.write("CORRUPT{{{not json\n")
            fh.write(json.dumps({
                "record_type": "failure", "failure_type": "fog", "scene_type": "x",
                "timestamp": 2.0,
            }) + "\n")

        b = JSONLBackend(tmp_jsonl)
        assert b.count("scene")   == 1
        assert b.count("failure") == 1

    def test_round_trip_preserves_all_fields(self, tmp_jsonl):
        rec = {
            "record_type": "scene",
            "scene_type":  "hangar",
            "score":       0.91,
            "status":      "success",
            "timestamp":   1000.0,
        }
        b1 = JSONLBackend(tmp_jsonl)
        b1.insert("scene", rec)

        b2 = JSONLBackend(tmp_jsonl)
        result = b2.query("scene")[0]
        for k, v in rec.items():
            assert result[k] == v, f"Mismatch for key {k!r}"

    def test_migrated_records_load_without_schema_version(self, tmp_jsonl):
        """Records loaded after a migration do not expose _schema_version."""
        register_migrator(from_version=0, record_type=None,
                          fn=lambda r: {**r, "migrated": True})

        with open(tmp_jsonl, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "record_type": "scene", "scene_type": "x", "timestamp": 1.0,
                _VERSION_KEY: 0,
            }) + "\n")

        b = JSONLBackend(tmp_jsonl)
        result = b.query("scene")[0]
        assert _VERSION_KEY not in result
        assert result.get("migrated") is True

    def test_schema_version_in_output_is_current(self, tmp_jsonl):
        """Every newly written line carries the current SCHEMA_VERSION."""
        b = JSONLBackend(tmp_jsonl)
        for i in range(3):
            b.insert("scene", {"record_type": "scene", "scene_type": "x",
                                "timestamp": float(i)})

        with open(tmp_jsonl, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    assert json.loads(line)[_VERSION_KEY] == SCHEMA_VERSION
