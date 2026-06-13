"""
Tests for src.runtime.production_memory
No bridge, no LLM. Pure unit tests.
"""
import json
import os
import tempfile
import pytest
from src.runtime.production_memory import (
    ProductionMemory,
    get_production_memory,
    reset_production_memory_for_tests,
)


@pytest.fixture(autouse=True)
def reset():
    reset_production_memory_for_tests()
    yield
    reset_production_memory_for_tests()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton():
    a = get_production_memory()
    b = get_production_memory()
    assert a is b


def test_reset_creates_new():
    a = get_production_memory()
    reset_production_memory_for_tests()
    b = get_production_memory()
    assert a is not b


# ---------------------------------------------------------------------------
# record_scene
# ---------------------------------------------------------------------------

def test_record_scene_returns_string_id():
    mem = ProductionMemory()
    sid = mem.record_scene({"scene_type": "industrial_hangar", "status": "success", "score": 0.9})
    assert isinstance(sid, str)
    assert sid.startswith("scene_")


def test_record_scene_stores_record():
    mem = ProductionMemory()
    mem.record_scene({
        "scene_type":     "industrial_hangar",
        "lighting_style": "cold_scifi",
        "camera_style":   "hero_focus",
        "atmosphere_type": "industrial_fog",
        "score":          0.88,
        "status":         "success",
    })
    history = mem.get_scene_history()
    assert len(history) == 1
    assert history[0]["scene_type"] == "industrial_hangar"
    assert history[0]["lighting_style"] == "cold_scifi"
    assert history[0]["status"] == "success"


def test_record_scene_invalid_status_normalised():
    mem = ProductionMemory()
    mem.record_scene({"scene_type": "lab", "status": "bad_value", "score": 0.5})
    h = mem.get_scene_history()
    assert h[0]["status"] == "unknown"


def test_record_scene_score_is_float():
    mem = ProductionMemory()
    mem.record_scene({"scene_type": "lab", "status": "success", "score": 1})
    h = mem.get_scene_history()
    assert isinstance(h[0]["score"], float)


def test_record_scene_has_timestamp():
    mem = ProductionMemory()
    mem.record_scene({"scene_type": "lab", "status": "success", "score": 0.8})
    h = mem.get_scene_history()
    assert isinstance(h[0]["timestamp"], float)
    assert h[0]["timestamp"] > 0


# ---------------------------------------------------------------------------
# record_review
# ---------------------------------------------------------------------------

def test_record_review_returns_id():
    mem = ProductionMemory()
    sid = mem.record_scene({"scene_type": "lab", "status": "success", "score": 0.9})
    rid = mem.record_review(sid, {"overall_score": 0.88, "grade": "B", "production_ready": True})
    assert isinstance(rid, str)
    assert rid.startswith("rev_")


def test_record_review_stores_grade():
    mem = ProductionMemory()
    mem.record_review("s1", {"overall_score": 0.75, "grade": "C", "production_ready": False,
                              "findings": ["issue1", "issue2"], "recommendations": ["fix1"]})
    stats = mem.get_statistics()
    assert stats["total_reviews"] == 1


# ---------------------------------------------------------------------------
# record_pattern_usage
# ---------------------------------------------------------------------------

def test_record_pattern_usage_success():
    mem = ProductionMemory()
    rid = mem.record_pattern_usage("industrial_hangar_v1", "industrial_hangar", "success")
    assert isinstance(rid, str)
    assert rid.startswith("pu_")


def test_record_pattern_usage_invalid_outcome_normalised():
    mem = ProductionMemory()
    mem.record_pattern_usage("pat1", "lab", "bad")
    patterns = mem.get_successful_patterns()
    # should not appear as successful since outcome was normalised to unknown
    assert len(patterns) == 0


def test_get_successful_patterns_filter():
    mem = ProductionMemory()
    mem.record_pattern_usage("pat1", "industrial_hangar", "success")
    mem.record_pattern_usage("pat2", "robotics_lab", "success")
    mem.record_pattern_usage("pat3", "industrial_hangar", "failure")
    results = mem.get_successful_patterns(scene_type="industrial_hangar")
    assert len(results) == 1
    assert results[0]["pattern_id"] == "pat1"


# ---------------------------------------------------------------------------
# record_failure
# ---------------------------------------------------------------------------

def test_record_failure_returns_id():
    mem = ProductionMemory()
    fid = mem.record_failure({
        "scene_type":   "industrial_hangar",
        "failure_type": "fog_density_high",
        "description":  "Fog was too dense",
    })
    assert isinstance(fid, str)
    assert fid.startswith("fail_")


def test_record_failure_stored():
    mem = ProductionMemory()
    mem.record_failure({"scene_type": "lab", "failure_type": "hero_absent", "description": "no hero"})
    failures = mem.get_failure_patterns()
    assert len(failures) == 1
    assert failures[0]["failure_type"] == "hero_absent"


def test_get_failure_patterns_filter_by_scene_type():
    mem = ProductionMemory()
    mem.record_failure({"scene_type": "lab", "failure_type": "t1", "description": ""})
    mem.record_failure({"scene_type": "hangar", "failure_type": "t2", "description": ""})
    assert len(mem.get_failure_patterns(scene_type="lab")) == 1
    assert len(mem.get_failure_patterns(scene_type="hangar")) == 1


# ---------------------------------------------------------------------------
# get_scene_history
# ---------------------------------------------------------------------------

def test_get_scene_history_newest_first():
    mem = ProductionMemory()
    for i in range(3):
        mem.record_scene({"scene_type": "lab", "status": "success", "score": float(i) / 10})
    history = mem.get_scene_history()
    timestamps = [r["timestamp"] for r in history]
    assert timestamps == sorted(timestamps, reverse=True)


def test_get_scene_history_filter_by_status():
    mem = ProductionMemory()
    mem.record_scene({"scene_type": "lab", "status": "success", "score": 0.9})
    mem.record_scene({"scene_type": "lab", "status": "failure", "score": 0.2})
    successes = mem.get_scene_history(status="success")
    assert len(successes) == 1
    assert successes[0]["status"] == "success"


def test_get_scene_history_limit():
    mem = ProductionMemory()
    for _ in range(10):
        mem.record_scene({"scene_type": "lab", "status": "success", "score": 0.8})
    assert len(mem.get_scene_history(limit=3)) == 3


def test_get_scene_history_filter_by_type():
    mem = ProductionMemory()
    mem.record_scene({"scene_type": "hangar", "status": "success", "score": 0.9})
    mem.record_scene({"scene_type": "lab", "status": "success", "score": 0.9})
    hangar = mem.get_scene_history(scene_type="hangar")
    assert all(r["scene_type"] == "hangar" for r in hangar)


# ---------------------------------------------------------------------------
# get_statistics
# ---------------------------------------------------------------------------

def test_get_statistics_empty():
    mem = ProductionMemory()
    stats = mem.get_statistics()
    assert stats["total_scenes"] == 0
    assert stats["success_rate"] == 0.0


def test_get_statistics_success_rate():
    mem = ProductionMemory()
    mem.record_scene({"scene_type": "lab", "status": "success", "score": 0.9})
    mem.record_scene({"scene_type": "lab", "status": "failure", "score": 0.3})
    stats = mem.get_statistics()
    assert stats["total_scenes"] == 2
    assert stats["success_rate"] == pytest.approx(0.5)


def test_get_statistics_scenes_by_type():
    mem = ProductionMemory()
    mem.record_scene({"scene_type": "hangar", "status": "success", "score": 0.9})
    mem.record_scene({"scene_type": "hangar", "status": "partial", "score": 0.6})
    mem.record_scene({"scene_type": "lab", "status": "success", "score": 0.8})
    stats = mem.get_statistics()
    assert stats["scenes_by_type"]["hangar"] == 2
    assert stats["scenes_by_type"]["lab"] == 1


def test_get_statistics_has_required_keys():
    mem = ProductionMemory()
    stats = mem.get_statistics()
    for key in ("total_scenes", "successful_scenes", "success_rate", "avg_score",
                "total_reviews", "total_pattern_usages", "pattern_success_rate",
                "total_failures", "scenes_by_type", "total_records"):
        assert key in stats, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# stats (lightweight)
# ---------------------------------------------------------------------------

def test_stats_has_record_count():
    mem = ProductionMemory()
    assert "record_count" in mem.stats()
    assert "write_count" in mem.stats()


def test_stats_increments():
    mem = ProductionMemory()
    mem.record_scene({"scene_type": "lab", "status": "success", "score": 0.8})
    assert mem.stats()["write_count"] == 1


# ---------------------------------------------------------------------------
# Persistence (JSONL)
# ---------------------------------------------------------------------------

def test_persistence_round_trip():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        path = f.name
    try:
        mem1 = ProductionMemory(path=path)
        sid = mem1.record_scene({"scene_type": "hangar", "status": "success", "score": 0.9})
        mem1.record_failure({"scene_type": "hangar", "failure_type": "fog_high", "description": ""})

        mem2 = ProductionMemory(path=path)
        history = mem2.get_scene_history()
        assert len(history) == 1
        assert history[0]["scene_id"] == sid

        failures = mem2.get_failure_patterns()
        assert len(failures) == 1
    finally:
        os.unlink(path)


def test_corrupt_jsonl_lines_skipped():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        f.write('{"record_type": "scene", "scene_type": "lab", "status": "success", "score": 0.8, "timestamp": 1.0}\n')
        f.write("NOT_JSON{{{\n")
        f.write('{"record_type": "failure", "failure_type": "hero_absent", "scene_type": "lab", "description": "", "timestamp": 2.0}\n')
        path = f.name
    try:
        mem = ProductionMemory(path=path)
        stats = mem.get_statistics()
        assert stats["total_scenes"] == 1
        assert stats["total_failures"] == 1
    finally:
        os.unlink(path)


def test_missing_file_starts_empty():
    mem = ProductionMemory(path="/nonexistent/path/production.jsonl")
    assert mem.get_statistics()["total_records"] == 0
