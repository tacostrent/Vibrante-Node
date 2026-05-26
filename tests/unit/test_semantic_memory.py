"""
Unit tests for src.runtime.semantic_memory.

Covers:
  • record_pattern returns uuid
  • record_pattern unknown type raises
  • record_pattern unknown outcome raises
  • get_pattern by id
  • get_pattern unknown returns None
  • query_patterns intent filter
  • query_patterns outcome filter
  • query_patterns pattern_type filter
  • query_patterns limit
  • get_best_patterns ordering: success before partial before unknown before failure
  • record_workflow_lineage delegates to record_pattern
  • stats shape
  • clear
  • disk persistence round-trip
  • singleton / reset
"""

from __future__ import annotations

import json
import os
import tempfile

import pytest

from src.runtime.semantic_memory import (
    SemanticMemory,
    get_semantic_memory,
    reset_semantic_memory_for_tests,
    PATTERN_TYPES,
    OUTCOME_VALUES,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_semantic_memory_for_tests()
    yield
    reset_semantic_memory_for_tests()


# ---------------------------------------------------------------------------
# record_pattern
# ---------------------------------------------------------------------------

def test_record_pattern_returns_uuid():
    sm = get_semantic_memory()
    pid = sm.record_pattern("execution_pattern", "build_pyro_source")
    assert isinstance(pid, str) and len(pid) == 36


def test_record_pattern_unknown_type_raises():
    sm = get_semantic_memory()
    with pytest.raises(ValueError, match="Unknown pattern_type"):
        sm.record_pattern("invented_type", "my_intent")


def test_record_pattern_unknown_outcome_raises():
    sm = get_semantic_memory()
    with pytest.raises(ValueError, match="Unknown outcome"):
        sm.record_pattern("execution_pattern", "my_intent", outcome="incredible")


def test_record_pattern_data_stored():
    sm = get_semantic_memory()
    pid = sm.record_pattern(
        "planning_pattern", "build_pyro_source",
        data={"param_a": 1, "param_b": "v"},
        outcome="success",
        metadata={"source": "test"},
    )
    p = sm.get_pattern(pid)
    assert p is not None
    assert p["pattern_type"] == "planning_pattern"
    assert p["intent"]        == "build_pyro_source"
    assert p["outcome"]       == "success"
    assert p["data"]["param_a"] == 1
    assert p["metadata"]["source"] == "test"


# ---------------------------------------------------------------------------
# get_pattern
# ---------------------------------------------------------------------------

def test_get_pattern_unknown_returns_none():
    sm = get_semantic_memory()
    assert sm.get_pattern("00000000-0000-0000-0000-000000000000") is None


# ---------------------------------------------------------------------------
# query_patterns
# ---------------------------------------------------------------------------

def test_query_patterns_intent_filter():
    sm = get_semantic_memory()
    sm.record_pattern("execution_pattern", "intent_a")
    sm.record_pattern("execution_pattern", "intent_b")
    sm.record_pattern("execution_pattern", "intent_a")
    results = sm.query_patterns(intent="intent_a")
    assert all(p["intent"] == "intent_a" for p in results)
    assert len(results) == 2


def test_query_patterns_outcome_filter():
    sm = get_semantic_memory()
    sm.record_pattern("execution_pattern", "i1", outcome="success")
    sm.record_pattern("execution_pattern", "i1", outcome="failure")
    results = sm.query_patterns(outcome="success")
    assert all(p["outcome"] == "success" for p in results)


def test_query_patterns_type_filter():
    sm = get_semantic_memory()
    sm.record_pattern("execution_pattern", "i1")
    sm.record_pattern("planning_pattern",  "i1")
    results = sm.query_patterns(pattern_type="planning_pattern")
    assert all(p["pattern_type"] == "planning_pattern" for p in results)


def test_query_patterns_limit():
    sm = get_semantic_memory()
    for _ in range(10):
        sm.record_pattern("execution_pattern", "intent_x")
    results = sm.query_patterns(intent="intent_x", limit=3)
    assert len(results) == 3


def test_query_patterns_newest_first():
    sm = get_semantic_memory()
    sm.record_pattern("execution_pattern", "ix", outcome="failure")
    sm.record_pattern("execution_pattern", "ix", outcome="success")
    results = sm.query_patterns(intent="ix")
    assert results[0]["outcome"] == "success"   # most recent first


# ---------------------------------------------------------------------------
# get_best_patterns ordering
# ---------------------------------------------------------------------------

def test_get_best_patterns_success_first():
    sm = get_semantic_memory()
    sm.record_pattern("execution_pattern", "test_intent", outcome="failure")
    sm.record_pattern("execution_pattern", "test_intent", outcome="unknown")
    sm.record_pattern("execution_pattern", "test_intent", outcome="partial")
    sm.record_pattern("execution_pattern", "test_intent", outcome="success")
    best = sm.get_best_patterns("test_intent")
    assert best[0]["outcome"] == "success"
    assert best[-1]["outcome"] == "failure"


def test_get_best_patterns_limit():
    sm = get_semantic_memory()
    for _ in range(10):
        sm.record_pattern("execution_pattern", "intent_z", outcome="success")
    best = sm.get_best_patterns("intent_z", limit=3)
    assert len(best) == 3


def test_get_best_patterns_empty_intent():
    sm = get_semantic_memory()
    best = sm.get_best_patterns("nonexistent_intent")
    assert best == []


# ---------------------------------------------------------------------------
# record_workflow_lineage
# ---------------------------------------------------------------------------

def test_record_workflow_lineage_returns_uuid():
    sm = get_semantic_memory()
    pid = sm.record_workflow_lineage(
        "my_workflow",
        [{"op": "create_node"}, {"op": "set_parms"}],
        outcome="success",
    )
    assert isinstance(pid, str) and len(pid) == 36


def test_record_workflow_lineage_stored_correctly():
    sm = get_semantic_memory()
    pid = sm.record_workflow_lineage(
        "hero_asset_workflow",
        [{"op": "create_node"}, {"op": "cook_node"}],
        outcome="partial",
        metadata={"user": "kamal"},
    )
    p = sm.get_pattern(pid)
    assert p is not None
    assert p["pattern_type"] == "workflow_lineage"
    assert p["intent"]       == "hero_asset_workflow"
    assert p["outcome"]      == "partial"
    assert p["data"]["op_count"] == 2
    assert "create_node" in p["data"]["op_types"]


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def test_stats_shape():
    sm = get_semantic_memory()
    sm.record_pattern("execution_pattern", "i1", outcome="success")
    sm.record_pattern("planning_pattern",  "i2", outcome="failure")
    s = sm.stats()
    assert "total_patterns" in s
    assert "write_count"    in s
    assert "by_type"        in s
    assert "by_outcome"     in s
    assert "max_records"    in s
    assert s["total_patterns"] == 2
    assert s["write_count"]    == 2
    assert s["by_outcome"].get("success", 0) == 1
    assert s["by_outcome"].get("failure", 0) == 1


# ---------------------------------------------------------------------------
# Clear
# ---------------------------------------------------------------------------

def test_clear():
    sm = get_semantic_memory()
    sm.record_pattern("execution_pattern", "i1")
    sm.record_pattern("execution_pattern", "i2")
    sm.clear()
    assert sm.stats()["total_patterns"] == 0
    assert sm.query_patterns() == []


# ---------------------------------------------------------------------------
# Disk persistence
# ---------------------------------------------------------------------------

def test_disk_round_trip():
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        path = f.name
    try:
        sm = SemanticMemory(path=path)
        sm.record_pattern("execution_pattern", "fire_sim", outcome="success",
                          data={"param": "x"})
        sm.record_pattern("planning_pattern",  "usd_export", outcome="partial")

        # Read the file back
        with open(path, "r", encoding="utf-8") as f:
            lines = [json.loads(l) for l in f if l.strip()]

        assert len(lines) == 2
        intents = {l["intent"] for l in lines}
        assert "fire_sim" in intents
        assert "usd_export" in intents
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def test_disk_load():
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, mode="w") as f:
        path = f.name
        record = {
            "id": "test-uuid",
            "pattern_type": "execution_pattern",
            "intent": "loaded_intent",
            "data": {},
            "outcome": "success",
            "metadata": {},
            "timestamp": 1700000000.0,
        }
        f.write(json.dumps(record) + "\n")
    try:
        sm = SemanticMemory(path=path)
        sm._load_from_disk()
        results = sm.query_patterns(intent="loaded_intent")
        assert len(results) == 1
        assert results[0]["id"] == "test-uuid"
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton_same_instance():
    a = get_semantic_memory()
    b = get_semantic_memory()
    assert a is b


def test_reset_creates_fresh_instance():
    a = get_semantic_memory()
    reset_semantic_memory_for_tests()
    b = get_semantic_memory()
    assert a is not b
