"""
Unit tests for src.runtime.studio_knowledge.

Covers:
  • record_workflow_pattern: returns a string id
  • record_workflow_pattern: invalid outcome raises ValueError
  • record_asset_pattern: returns a string id
  • record_asset_pattern: invalid outcome raises ValueError
  • get_best_recipe: returns best success record (highest op_count)
  • get_best_recipe: returns None when no success records
  • get_best_recipe: dcc filter respected
  • query_patterns: returns all when no filters
  • query_patterns: intent filter
  • query_patterns: dcc filter
  • query_patterns: outcome filter
  • query_patterns: limit respected
  • query_patterns: newest first ordering
  • get_optimization_insights: shape for known intent
  • get_optimization_insights: zero-pattern returns safe defaults
  • get_optimization_insights: success_rate correct
  • get_optimization_insights: best_template detected
  • get_optimization_insights: best_dcc detected
  • stats: shape and by_outcome counts
  • disk round-trip: records survive StudioKnowledge reload
  • disk round-trip: corrupt JSONL lines skipped
  • singleton / reset
"""

from __future__ import annotations

import json
import os
import tempfile

import pytest

from src.runtime.studio_knowledge import (
    StudioKnowledge,
    get_studio_knowledge,
    reset_studio_knowledge_for_tests,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_studio_knowledge_for_tests()
    yield
    reset_studio_knowledge_for_tests()


def _wf(intent="build_pyro_source", outcome="success", op_count=5, dcc="houdini",
         template_id="", duration_sec=2.0):
    return {
        "intent": intent,
        "outcome": outcome,
        "op_count": op_count,
        "dcc": dcc,
        "template_id": template_id,
        "duration_sec": duration_sec,
    }


# ---------------------------------------------------------------------------
# record_workflow_pattern
# ---------------------------------------------------------------------------

def test_record_workflow_pattern_returns_id():
    sk = get_studio_knowledge()
    pid = sk.record_workflow_pattern(_wf())
    assert isinstance(pid, str) and len(pid) > 0


def test_record_workflow_pattern_invalid_outcome_raises():
    sk = get_studio_knowledge()
    with pytest.raises(ValueError, match="Invalid outcome"):
        sk.record_workflow_pattern(_wf(outcome="invalid_outcome"))


# ---------------------------------------------------------------------------
# record_asset_pattern
# ---------------------------------------------------------------------------

def test_record_asset_pattern_returns_id():
    sk = get_studio_knowledge()
    pid = sk.record_asset_pattern({"intent": "asset_publish", "outcome": "success", "dcc": "houdini"})
    assert isinstance(pid, str) and len(pid) > 0


def test_record_asset_pattern_invalid_outcome_raises():
    sk = get_studio_knowledge()
    with pytest.raises(ValueError, match="Invalid outcome"):
        sk.record_asset_pattern({"intent": "x", "outcome": "bad", "dcc": "houdini"})


# ---------------------------------------------------------------------------
# get_best_recipe
# ---------------------------------------------------------------------------

def test_get_best_recipe_returns_best():
    sk = get_studio_knowledge()
    sk.record_workflow_pattern(_wf(op_count=3))
    sk.record_workflow_pattern(_wf(op_count=10))
    result = sk.get_best_recipe("build_pyro_source")
    assert result is not None
    assert result["op_count"] == 10


def test_get_best_recipe_none_when_no_success():
    sk = get_studio_knowledge()
    sk.record_workflow_pattern(_wf(outcome="failure"))
    result = sk.get_best_recipe("build_pyro_source")
    assert result is None


def test_get_best_recipe_dcc_filter():
    sk = get_studio_knowledge()
    sk.record_workflow_pattern(_wf(op_count=10, dcc="houdini"))
    sk.record_workflow_pattern(_wf(op_count=20, dcc="maya"))
    result = sk.get_best_recipe("build_pyro_source", dcc="houdini")
    assert result is not None
    assert result["dcc"] == "houdini"
    assert result["op_count"] == 10


def test_get_best_recipe_none_for_unknown_intent():
    sk = get_studio_knowledge()
    sk.record_workflow_pattern(_wf())
    result = sk.get_best_recipe("unknown_xyz_intent")
    assert result is None


# ---------------------------------------------------------------------------
# query_patterns
# ---------------------------------------------------------------------------

def test_query_patterns_returns_all():
    sk = get_studio_knowledge()
    sk.record_workflow_pattern(_wf(intent="a"))
    sk.record_workflow_pattern(_wf(intent="b"))
    assert len(sk.query_patterns()) == 2


def test_query_patterns_intent_filter():
    sk = get_studio_knowledge()
    sk.record_workflow_pattern(_wf(intent="pyro"))
    sk.record_workflow_pattern(_wf(intent="karma"))
    results = sk.query_patterns(intent="pyro")
    assert len(results) == 1
    assert results[0]["intent"] == "pyro"


def test_query_patterns_dcc_filter():
    sk = get_studio_knowledge()
    sk.record_workflow_pattern(_wf(dcc="houdini"))
    sk.record_workflow_pattern(_wf(dcc="maya"))
    results = sk.query_patterns(dcc="maya")
    assert len(results) == 1
    assert results[0]["dcc"] == "maya"


def test_query_patterns_outcome_filter():
    sk = get_studio_knowledge()
    sk.record_workflow_pattern(_wf(outcome="success"))
    sk.record_workflow_pattern(_wf(outcome="failure"))
    results = sk.query_patterns(outcome="failure")
    assert len(results) == 1
    assert results[0]["outcome"] == "failure"


def test_query_patterns_limit_respected():
    sk = get_studio_knowledge()
    for i in range(10):
        sk.record_workflow_pattern(_wf(intent=f"intent_{i}"))
    results = sk.query_patterns(limit=5)
    assert len(results) == 5


def test_query_patterns_newest_first():
    sk = get_studio_knowledge()
    sk.record_workflow_pattern(_wf(intent="first"))
    sk.record_workflow_pattern(_wf(intent="second"))
    results = sk.query_patterns()
    assert results[0]["intent"] == "second"


# ---------------------------------------------------------------------------
# get_optimization_insights
# ---------------------------------------------------------------------------

def test_get_optimization_insights_shape():
    sk = get_studio_knowledge()
    sk.record_workflow_pattern(_wf())
    result = sk.get_optimization_insights("build_pyro_source")
    assert "intent" in result
    assert "pattern_count" in result
    assert "success_rate" in result
    assert "avg_op_count" in result
    assert "best_template" in result
    assert "best_dcc" in result
    assert "insights" in result


def test_get_optimization_insights_empty():
    sk = get_studio_knowledge()
    result = sk.get_optimization_insights("unknown_xyz")
    assert result["pattern_count"] == 0
    assert result["success_rate"] == 0.0
    assert result["best_template"] is None
    assert result["best_dcc"] is None
    assert len(result["insights"]) >= 1


def test_get_optimization_insights_success_rate():
    sk = get_studio_knowledge()
    sk.record_workflow_pattern(_wf(outcome="success"))
    sk.record_workflow_pattern(_wf(outcome="success"))
    sk.record_workflow_pattern(_wf(outcome="failure"))
    sk.record_workflow_pattern(_wf(outcome="failure"))
    result = sk.get_optimization_insights("build_pyro_source")
    assert abs(result["success_rate"] - 0.5) < 0.01


def test_get_optimization_insights_best_template():
    sk = get_studio_knowledge()
    sk.record_workflow_pattern(_wf(outcome="success", template_id="tmpl_a"))
    sk.record_workflow_pattern(_wf(outcome="success", template_id="tmpl_a"))
    sk.record_workflow_pattern(_wf(outcome="failure", template_id="tmpl_b"))
    result = sk.get_optimization_insights("build_pyro_source")
    assert result["best_template"] == "tmpl_a"


def test_get_optimization_insights_best_dcc():
    sk = get_studio_knowledge()
    sk.record_workflow_pattern(_wf(outcome="success", dcc="houdini"))
    sk.record_workflow_pattern(_wf(outcome="success", dcc="houdini"))
    sk.record_workflow_pattern(_wf(outcome="success", dcc="maya"))
    result = sk.get_optimization_insights("build_pyro_source")
    assert result["best_dcc"] == "houdini"


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

def test_stats_shape():
    sk = get_studio_knowledge()
    sk.record_workflow_pattern(_wf(outcome="success"))
    sk.record_workflow_pattern(_wf(outcome="failure"))
    s = sk.stats()
    assert "total_patterns" in s
    assert "by_outcome" in s
    assert "write_count" in s
    assert s["total_patterns"] == 2
    assert s["by_outcome"].get("success", 0) == 1
    assert s["by_outcome"].get("failure", 0) == 1


def test_stats_write_count():
    sk = get_studio_knowledge()
    sk.record_workflow_pattern(_wf())
    sk.record_asset_pattern({"intent": "x", "outcome": "success", "dcc": "houdini"})
    assert sk.stats()["write_count"] == 2


# ---------------------------------------------------------------------------
# Disk persistence
# ---------------------------------------------------------------------------

def test_disk_round_trip():
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        tmp_path = f.name
    try:
        sk1 = StudioKnowledge(path=tmp_path)
        sk1.record_workflow_pattern(_wf(intent="pyro_disk_test", outcome="success", op_count=7))
        sk1.record_workflow_pattern(_wf(intent="pyro_disk_test", outcome="failure"))

        sk2 = StudioKnowledge(path=tmp_path)
        patterns = sk2.query_patterns(intent="pyro_disk_test")
        assert len(patterns) == 2

        best = sk2.get_best_recipe("pyro_disk_test")
        assert best is not None
        assert best["op_count"] == 7
    finally:
        os.unlink(tmp_path)


def test_disk_corrupt_lines_skipped():
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, mode="w", encoding="utf-8") as f:
        f.write('{"id": "abc", "pattern_type": "workflow_pattern", "intent": "ok", '
                '"outcome": "success", "dcc": "houdini", "op_count": 1, '
                '"template_id": "", "duration_sec": 0.0, "op_fingerprint": [], "timestamp": 1000.0}\n')
        f.write("NOT VALID JSON }{[\n")
        f.write('{"id": "def", "pattern_type": "workflow_pattern", "intent": "ok2", '
                '"outcome": "failure", "dcc": "", "op_count": 0, '
                '"template_id": "", "duration_sec": 0.0, "op_fingerprint": [], "timestamp": 999.0}\n')
        tmp_path = f.name
    try:
        sk = StudioKnowledge(path=tmp_path)
        patterns = sk.query_patterns()
        assert len(patterns) == 2
    finally:
        os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton_same_instance():
    assert get_studio_knowledge() is get_studio_knowledge()


def test_reset_creates_fresh():
    a = get_studio_knowledge()
    reset_studio_knowledge_for_tests()
    b = get_studio_knowledge()
    assert a is not b
