"""Tests for StudioKnowledgeDB (Tier 11 — §31).

Distinct from test_studio_knowledge.py (Tier 5 §24 src/runtime/studio_knowledge.py).
This module tests src/runtime/studio/studio_knowledge.py.
"""
import os
import tempfile
import pytest
from src.runtime.studio.studio_knowledge import (
    StudioKnowledgeDB,
    get_studio_knowledge_db,
    reset_studio_knowledge_db_for_tests,
)


@pytest.fixture(autouse=True)
def reset():
    reset_studio_knowledge_db_for_tests()
    yield
    reset_studio_knowledge_db_for_tests()


def test_singleton():
    assert get_studio_knowledge_db() is get_studio_knowledge_db()


# ---------------------------------------------------------------------------
# record_success
# ---------------------------------------------------------------------------

def test_record_success_returns_id():
    sk = StudioKnowledgeDB()
    rid = sk.record_success("industrial_hangar_pack", "industrial_hangar", score=0.88)
    assert len(rid) == 36


def test_record_success_queryable():
    sk = StudioKnowledgeDB()
    sk.record_success("pack_a", "industrial_hangar", score=0.91)
    results = sk.get_studio_successes(environment="industrial_hangar")
    assert len(results) == 1
    assert results[0]["workflow"] == "pack_a"


def test_record_success_min_score_filter():
    sk = StudioKnowledgeDB()
    sk.record_success("pack_a", "industrial_hangar", score=0.5)
    sk.record_success("pack_b", "industrial_hangar", score=0.9)
    high = sk.get_studio_successes(min_score=0.8)
    assert len(high) == 1
    assert high[0]["workflow"] == "pack_b"


def test_record_success_sorted_by_score():
    sk = StudioKnowledgeDB()
    sk.record_success("low_pack", "industrial_hangar", score=0.6)
    sk.record_success("high_pack", "industrial_hangar", score=0.95)
    results = sk.get_studio_successes()
    assert results[0]["workflow"] == "high_pack"


# ---------------------------------------------------------------------------
# record_failure
# ---------------------------------------------------------------------------

def test_record_failure():
    sk = StudioKnowledgeDB()
    sk.record_failure("bad_pack", "robotics_lab", failure_type="fog_density_high")
    failures = sk.get_studio_failures()
    assert len(failures) == 1
    assert failures[0]["failure_type"] == "fog_density_high"


def test_failures_env_filter():
    sk = StudioKnowledgeDB()
    sk.record_failure("pack_a", "industrial_hangar")
    sk.record_failure("pack_b", "robotics_lab")
    results = sk.get_studio_failures(environment="robotics_lab")
    assert len(results) == 1
    assert results[0]["workflow"] == "pack_b"


# ---------------------------------------------------------------------------
# record_pattern
# ---------------------------------------------------------------------------

def test_record_pattern_valid():
    sk = StudioKnowledgeDB()
    rid = sk.record_pattern("my_pattern", "scene_pattern", "industrial_hangar", "success")
    assert rid is not None
    patterns = sk.get_studio_patterns(outcome="success")
    assert len(patterns) == 1


def test_record_pattern_invalid_outcome():
    sk = StudioKnowledgeDB()
    with pytest.raises(ValueError, match="Invalid outcome"):
        sk.record_pattern("p", "scene_pattern", "industrial_hangar", "invalid_outcome")


def test_record_pattern_all_valid_outcomes():
    sk = StudioKnowledgeDB()
    for outcome in ("success", "partial", "failure", "unknown"):
        sk.record_pattern(f"p_{outcome}", "scene_pattern", "env", outcome)
    patterns = sk.get_studio_patterns()
    assert len(patterns) == 4


# ---------------------------------------------------------------------------
# record_review
# ---------------------------------------------------------------------------

def test_record_review():
    sk = StudioKnowledgeDB()
    rid = sk.record_review("pack_a", "industrial_hangar", "A", 0.91, findings=["good depth"])
    assert rid is not None
    with sk._lock:
        reviews = [r for r in sk._records if r.get("record_type") == "review"]
    assert len(reviews) == 1
    assert reviews[0]["grade"] == "A"
    assert "good depth" in reviews[0]["findings"]


# ---------------------------------------------------------------------------
# get_studio_statistics
# ---------------------------------------------------------------------------

def test_statistics_empty():
    sk = StudioKnowledgeDB()
    stats = sk.get_studio_statistics()
    assert stats["total_successes"] == 0
    assert stats["total_failures"] == 0
    assert stats["success_rate"] == 0.0
    assert stats["average_score"] == 0.0


def test_statistics_with_data():
    sk = StudioKnowledgeDB()
    sk.record_success("pack_a", "industrial_hangar", score=0.85)
    sk.record_success("pack_a", "industrial_hangar", score=0.90)
    sk.record_failure("pack_b", "robotics_lab")
    stats = sk.get_studio_statistics()
    assert stats["total_successes"] == 2
    assert stats["total_failures"] == 1
    total = stats["total_successes"] + stats["total_failures"]
    assert abs(stats["success_rate"] - 2 / total) < 1e-3
    assert stats["average_score"] > 0


def test_statistics_top_workflows():
    sk = StudioKnowledgeDB()
    for _ in range(3):
        sk.record_success("best_pack", "industrial_hangar", score=0.9)
    sk.record_success("other_pack", "industrial_hangar", score=0.8)
    stats = sk.get_studio_statistics()
    assert stats["top_workflows"][0]["workflow"] == "best_pack"


def test_statistics_required_keys():
    sk = StudioKnowledgeDB()
    stats = sk.get_studio_statistics()
    for key in ("total_records", "total_successes", "total_failures",
                "total_patterns", "total_reviews", "success_rate",
                "average_score", "top_workflows", "write_count"):
        assert key in stats, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# stats()
# ---------------------------------------------------------------------------

def test_stats_keys():
    sk = StudioKnowledgeDB()
    s = sk.stats()
    assert "total_records" in s
    assert "write_count" in s


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def test_persistence_round_trip():
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as tf:
        path = tf.name
    try:
        sk1 = StudioKnowledgeDB(path=path)
        sk1.record_success("pack_a", "industrial_hangar", score=0.92, lighting_style="cinematic_industrial")
        sk1.record_failure("bad_pack", "robotics_lab", failure_type="overlit")

        sk2 = StudioKnowledgeDB(path=path)
        stats = sk2.get_studio_statistics()
        assert stats["total_successes"] == 1
        assert stats["total_failures"] == 1
    finally:
        os.unlink(path)


def test_corrupt_lines_skipped():
    with tempfile.NamedTemporaryFile(suffix=".jsonl", mode="w", delete=False, encoding="utf-8") as tf:
        tf.write('{"record_type":"success","workflow":"w","environment":"e","score":0.9,'
                 '"lighting_style":"","camera_mode":"","atmosphere_type":"",'
                 '"project_id":"","metadata":{},"timestamp":1.0,"record_id":"abc"}\n')
        tf.write("CORRUPT\n")
        path = tf.name
    try:
        sk = StudioKnowledgeDB(path=path)
        assert sk.stats()["total_records"] == 1
    finally:
        os.unlink(path)
