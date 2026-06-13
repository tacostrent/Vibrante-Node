"""Tests for ProjectMemory (Tier 11 — §31)."""
import os
import tempfile
import pytest
from src.runtime.studio.project_memory import (
    ProjectMemory,
    get_project_memory,
    reset_project_memory_for_tests,
)


@pytest.fixture(autouse=True)
def reset():
    reset_project_memory_for_tests()
    yield
    reset_project_memory_for_tests()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton():
    assert get_project_memory() is get_project_memory()


def test_fresh_instance_in_memory():
    mem = ProjectMemory()
    assert mem.stats()["total_records"] == 0


# ---------------------------------------------------------------------------
# register_project
# ---------------------------------------------------------------------------

def test_register_project_returns_id():
    mem = ProjectMemory()
    pid = mem.register_project("proj_001", "Test Project", environment="industrial_hangar")
    assert pid == "proj_001"


def test_register_project_listed():
    mem = ProjectMemory()
    mem.register_project("proj_a", "A")
    mem.register_project("proj_b", "B")
    assert "proj_a" in mem.list_projects()
    assert "proj_b" in mem.list_projects()
    assert mem.list_projects() == sorted(mem.list_projects())


# ---------------------------------------------------------------------------
# record_project_execution
# ---------------------------------------------------------------------------

def test_record_execution_returns_id():
    mem = ProjectMemory()
    rid = mem.record_project_execution("p1", "industrial_hangar_pack", "committed", score=0.85)
    assert len(rid) == 36  # UUID4


def test_record_execution_queryable():
    mem = ProjectMemory()
    mem.record_project_execution("p1", "pack_a", "committed", score=0.9)
    history = mem.get_project_history("p1", record_type="project_execution")
    assert len(history) == 1
    assert history[0]["workflow"] == "pack_a"
    assert history[0]["score"] == 0.9


# ---------------------------------------------------------------------------
# record_project_review
# ---------------------------------------------------------------------------

def test_record_review():
    mem = ProjectMemory()
    rid = mem.record_project_review("p1", "A", 0.91, findings=["great depth"])
    assert rid is not None
    history = mem.get_project_history("p1", record_type="project_review")
    assert history[0]["grade"] == "A"
    assert history[0]["score"] == 0.91
    assert "great depth" in history[0]["findings"]


# ---------------------------------------------------------------------------
# record_project_workflow
# ---------------------------------------------------------------------------

def test_record_workflow():
    mem = ProjectMemory()
    mem.record_project_workflow("p1", "cinematic_push_in", pack_name="industrial_hangar_pack", outcome="success")
    history = mem.get_project_history("p1", record_type="project_workflow")
    assert history[0]["pack_name"] == "industrial_hangar_pack"
    assert history[0]["outcome"] == "success"


# ---------------------------------------------------------------------------
# record_project_metrics
# ---------------------------------------------------------------------------

def test_record_metrics():
    mem = ProjectMemory()
    rid = mem.record_project_metrics("p1", {"render_time": 120.5, "node_count": 42})
    assert rid is not None
    history = mem.get_project_history("p1", record_type="project_metrics")
    assert history[0]["metrics"]["render_time"] == 120.5


# ---------------------------------------------------------------------------
# get_project_history
# ---------------------------------------------------------------------------

def test_history_filter_by_type():
    mem = ProjectMemory()
    mem.record_project_execution("p1", "wf", "committed")
    mem.record_project_review("p1", "B", 0.8)
    exec_hist = mem.get_project_history("p1", record_type="project_execution")
    review_hist = mem.get_project_history("p1", record_type="project_review")
    assert len(exec_hist) == 1
    assert len(review_hist) == 1


def test_history_limit():
    mem = ProjectMemory()
    for i in range(15):
        mem.record_project_execution("p1", f"wf_{i}", "committed")
    history = mem.get_project_history("p1", limit=5)
    assert len(history) == 5


def test_history_newest_first():
    mem = ProjectMemory()
    mem.record_project_execution("p1", "first", "committed", score=0.7)
    mem.record_project_execution("p1", "second", "committed", score=0.9)
    history = mem.get_project_history("p1", record_type="project_execution")
    assert history[0]["workflow"] == "second"  # newest first


# ---------------------------------------------------------------------------
# get_project_statistics
# ---------------------------------------------------------------------------

def test_statistics_empty():
    mem = ProjectMemory()
    stats = mem.get_project_statistics("nonexistent")
    assert stats["total_records"] == 0
    assert stats["success_rate"] == 0.0


def test_statistics_with_data():
    mem = ProjectMemory()
    mem.record_project_execution("p1", "wf", "committed", score=0.85)
    mem.record_project_execution("p1", "wf", "committed", score=0.90)
    mem.record_project_execution("p1", "wf", "rolled_back")
    mem.record_project_review("p1", "B", 0.87)
    stats = mem.get_project_statistics("p1")
    assert stats["total_executions"] == 3
    assert stats["total_reviews"] == 1
    assert abs(stats["success_rate"] - 2 / 3) < 1e-3


def test_global_statistics():
    mem = ProjectMemory()
    mem.record_project_execution("p1", "wf1", "committed")
    mem.record_project_execution("p2", "wf2", "committed")
    stats = mem.get_project_statistics()  # no project_id → all
    assert stats["total_executions"] == 2


# ---------------------------------------------------------------------------
# stats()
# ---------------------------------------------------------------------------

def test_stats_keys():
    mem = ProjectMemory()
    s = mem.stats()
    assert "total_records" in s
    assert "registered_projects" in s
    assert "write_count" in s


# ---------------------------------------------------------------------------
# Persistence (JSONL round-trip)
# ---------------------------------------------------------------------------

def test_persistence_round_trip():
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as tf:
        path = tf.name
    try:
        mem1 = ProjectMemory(path=path)
        mem1.register_project("p1", "Project One", environment="robotics_lab")
        mem1.record_project_execution("p1", "robotics_lab_pack", "committed", score=0.88)

        mem2 = ProjectMemory(path=path)
        assert "p1" in mem2.list_projects()
        hist = mem2.get_project_history("p1", record_type="project_execution")
        assert len(hist) == 1
        assert hist[0]["score"] == 0.88
    finally:
        os.unlink(path)


def test_corrupt_lines_skipped():
    with tempfile.NamedTemporaryFile(suffix=".jsonl", mode="w", delete=False, encoding="utf-8") as tf:
        tf.write('{"record_type":"project_execution","project_id":"p1","workflow":"wf","status":"committed","score":0.9,"duration":1.0,"metadata":{},"timestamp":1000.0}\n')
        tf.write("NOT_VALID_JSON\n")
        tf.write('{"record_type":"project_registration","project_id":"p1","name":"P1","environment":"","metadata":{},"registered_at":999.0}\n')
        path = tf.name
    try:
        mem = ProjectMemory(path=path)
        assert mem.stats()["total_records"] == 2  # 2 valid lines
    finally:
        os.unlink(path)
