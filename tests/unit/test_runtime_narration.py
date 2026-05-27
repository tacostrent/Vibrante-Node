"""
Tests for src.runtime.runtime_narration
No Houdini, no bridge, no external APIs. Pure unit tests.
"""

import pytest
from src.runtime.runtime_narration import (
    RuntimeNarration,
    NarrationEntry,
    NARRATION_BLOCKS,
    get_runtime_narration,
    reset_runtime_narration_for_tests,
)


@pytest.fixture(autouse=True)
def reset():
    reset_runtime_narration_for_tests()
    yield
    reset_runtime_narration_for_tests()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton_returns_same_instance():
    a = get_runtime_narration()
    b = get_runtime_narration()
    assert a is b


def test_reset_creates_new_instance():
    a = get_runtime_narration()
    reset_runtime_narration_for_tests()
    b = get_runtime_narration()
    assert a is not b


# ---------------------------------------------------------------------------
# NARRATION_BLOCKS
# ---------------------------------------------------------------------------

def test_narration_blocks_contains_expected():
    expected = {"Runtime", "Planning", "Validation", "Preview", "Execution", "Review"}
    assert expected == NARRATION_BLOCKS


# ---------------------------------------------------------------------------
# NarrationEntry
# ---------------------------------------------------------------------------

def test_narration_entry_formatted():
    entry = NarrationEntry("Planning", "Goal decomposed.")
    assert entry.formatted == "[Planning] Goal decomposed."
    assert str(entry) == "[Planning] Goal decomposed."


def test_narration_entry_to_dict():
    entry = NarrationEntry("Execution", "Stage running.", {"stage": "fireball_core"})
    d = entry.to_dict()
    assert d["block"] == "Execution"
    assert d["message"] == "Stage running."
    assert d["context"]["stage"] == "fireball_core"
    assert "timestamp" in d
    assert "formatted" in d


def test_narration_entry_timestamp_monotonic():
    a = NarrationEntry("Runtime", "first")
    b = NarrationEntry("Runtime", "second")
    assert b.timestamp >= a.timestamp


# ---------------------------------------------------------------------------
# narrate — basics
# ---------------------------------------------------------------------------

def test_narrate_returns_entry():
    rn = RuntimeNarration()
    entry = rn.narrate("Planning", "Test message.")
    assert isinstance(entry, NarrationEntry)
    assert entry.block == "Planning"
    assert entry.message == "Test message."


def test_narrate_all_valid_blocks():
    rn = RuntimeNarration()
    for block in NARRATION_BLOCKS:
        entry = rn.narrate(block, f"Message for {block}.")
        assert entry.block == block


def test_narrate_invalid_block_falls_back_to_runtime():
    rn = RuntimeNarration()
    entry = rn.narrate("INVALID_BLOCK", "Some message.")
    assert entry.block == "Runtime"


def test_narrate_logged():
    rn = RuntimeNarration()
    rn.narrate("Planning", "Message 1.")
    rn.narrate("Execution", "Message 2.")
    log = rn.get_session_log()
    assert len(log) == 2


def test_narrate_with_context():
    rn = RuntimeNarration()
    entry = rn.narrate("Preview", "Risk assessed.", {"risk_level": "high"})
    assert entry.context["risk_level"] == "high"


# ---------------------------------------------------------------------------
# narrate_decomposition
# ---------------------------------------------------------------------------

def test_narrate_decomposition_no_match():
    rn = RuntimeNarration()
    result = {"matched_workflows": [], "stages": [], "notes": [], "confidence": 0.0}
    text = rn.narrate_decomposition("unknown goal", result)
    assert "[Planning]" in text
    assert "unknown goal" in text
    # Should mention no match or specific terminology
    assert isinstance(text, str)


def test_narrate_decomposition_composite():
    rn = RuntimeNarration()
    result = {
        "matched_workflows": ["cinematic_explosion", "dust_wave"],
        "stages": ["terrain_prep", "pyro_source", "smoke_evolution", "dust_source"],
        "notes": ["Composite goal matched: 'cinematic explosion scene' → 2 workflows"],
        "confidence": 0.95,
    }
    text = rn.narrate_decomposition("cinematic explosion scene", result)
    assert "[Planning]" in text
    assert "cinematic explosion scene" in text
    assert "2 workflow" in text or "workflows" in text


def test_narrate_decomposition_keyword():
    rn = RuntimeNarration()
    result = {
        "matched_workflows": ["smoke_column"],
        "stages": ["burn_source", "initial_column"],
        "notes": ["Matched 1 workflow(s): smoke_column"],
        "confidence": 0.85,
    }
    text = rn.narrate_decomposition("add rising smoke", result)
    assert "[Planning]" in text
    assert "smoke" in text.lower() or "workflow" in text.lower()


def test_narrate_decomposition_logs_entry():
    rn = RuntimeNarration()
    result = {"matched_workflows": [], "stages": [], "notes": [], "confidence": 0.0}
    rn.narrate_decomposition("test goal", result)
    log = rn.get_session_log()
    assert len(log) >= 1
    assert log[-1].block == "Planning"


# ---------------------------------------------------------------------------
# narrate_execution_start
# ---------------------------------------------------------------------------

def test_narrate_execution_start():
    rn = RuntimeNarration()
    stages = ["terrain_prep", "pyro_source", "fireball_core"]
    text = rn.narrate_execution_start("cinematic_explosion", stages)
    assert "[Execution]" in text
    assert "cinematic_explosion" in text
    assert "3" in text or "terrain_prep" in text


def test_narrate_execution_start_truncates_long_stage_list():
    rn = RuntimeNarration()
    stages = [f"stage_{i}" for i in range(20)]
    text = rn.narrate_execution_start("big_workflow", stages)
    assert "+14 more" in text or "+13 more" in text or "more" in text


# ---------------------------------------------------------------------------
# narrate_stage_start
# ---------------------------------------------------------------------------

def test_narrate_stage_start():
    rn = RuntimeNarration()
    text = rn.narrate_stage_start("cinematic_explosion", "fireball_core", "Building temperature field.")
    assert "[Execution]" in text
    assert "fireball_core" in text
    assert "Building temperature field." in text


def test_narrate_stage_start_no_description():
    rn = RuntimeNarration()
    text = rn.narrate_stage_start("cinematic_explosion", "fireball_core")
    assert "[Execution]" in text
    assert "fireball_core" in text


# ---------------------------------------------------------------------------
# narrate_stage_complete
# ---------------------------------------------------------------------------

def test_narrate_stage_complete_passed():
    rn = RuntimeNarration()
    text = rn.narrate_stage_complete("cinematic_explosion", "fireball_core", True)
    assert "[Execution]" in text
    assert "fireball_core" in text
    assert "✓" in text


def test_narrate_stage_complete_failed_with_critique():
    rn = RuntimeNarration()
    text = rn.narrate_stage_complete(
        "cinematic_explosion", "smoke_evolution", False,
        "Smoke breakup lacks variation."
    )
    assert "[Review]" in text
    assert "smoke_evolution" in text
    assert "Smoke breakup lacks variation." in text
    assert "✗" in text


def test_narrate_stage_complete_failed_no_critique():
    rn = RuntimeNarration()
    text = rn.narrate_stage_complete("cinematic_explosion", "pressure_wave", False)
    assert "[Review]" in text
    assert "pressure_wave" in text


# ---------------------------------------------------------------------------
# narrate_review
# ---------------------------------------------------------------------------

def test_narrate_review_production_ready():
    rn = RuntimeNarration()
    review = {
        "production_ready": True,
        "stage_count": 9,
        "failed_stages": 0,
        "critical_issues": [],
        "advisory_notes": [],
    }
    text = rn.narrate_review("cinematic_explosion", review)
    assert "[Review]" in text
    assert "cinematic_explosion" in text
    assert "production-ready" in text.lower() or "Production-ready" in text


def test_narrate_review_with_critical_issues():
    rn = RuntimeNarration()
    review = {
        "production_ready": False,
        "stage_count": 5,
        "failed_stages": 2,
        "critical_issues": ["Smoke breakup lacks variation."],
        "advisory_notes": [],
    }
    text = rn.narrate_review("cinematic_explosion", review)
    assert "[Review]" in text
    assert "3/5" in text or "stages" in text.lower()
    assert "Smoke breakup lacks variation." in text


def test_narrate_review_advisory_only():
    rn = RuntimeNarration()
    review = {
        "production_ready": False,
        "stage_count": 7,
        "failed_stages": 0,
        "critical_issues": [],
        "advisory_notes": ["Volumetric depth could be improved."],
    }
    text = rn.narrate_review("arnold_cinematic_lighting", review)
    assert "[Review]" in text
    assert "Volumetric depth could be improved." in text


def test_narrate_review_logs_review_block():
    rn = RuntimeNarration()
    review = {"production_ready": True, "stage_count": 3, "failed_stages": 0,
              "critical_issues": [], "advisory_notes": []}
    rn.narrate_review("some_workflow", review)
    log = rn.get_session_log()
    assert any(e.block == "Review" for e in log)


# ---------------------------------------------------------------------------
# narrate_validation
# ---------------------------------------------------------------------------

def test_narrate_validation_passed():
    rn = RuntimeNarration()
    result = {"valid": True, "risk_level": "low", "errors": [], "warnings": [], "op_count": 5}
    text = rn.narrate_validation(result)
    assert "[Validation]" in text
    assert "low" in text


def test_narrate_validation_failed():
    rn = RuntimeNarration()
    result = {
        "valid": False,
        "risk_level": "high",
        "errors": [{"message": "Missing parent node"}],
        "warnings": [],
        "op_count": 3,
    }
    text = rn.narrate_validation(result)
    assert "[Validation]" in text
    assert "Missing parent node" in text


def test_narrate_validation_with_warnings():
    rn = RuntimeNarration()
    result = {
        "valid": True,
        "risk_level": "medium",
        "errors": [],
        "warnings": [{"message": "Downstream dependents may break"}],
        "op_count": 8,
    }
    text = rn.narrate_validation(result)
    assert "[Validation]" in text
    assert "1 warning" in text or "warning" in text.lower()


# ---------------------------------------------------------------------------
# narrate_preview
# ---------------------------------------------------------------------------

def test_narrate_preview_low_risk():
    rn = RuntimeNarration()
    data = {"risk_level": "low", "op_count": 5}
    text = rn.narrate_preview(data)
    assert "[Preview]" in text
    assert "low" in text.lower() or "safe" in text.lower()


def test_narrate_preview_high_risk():
    rn = RuntimeNarration()
    data = {"risk_level": "high", "op_count": 12, "nodes_to_delete": ["a", "b", "c"]}
    text = rn.narrate_preview(data)
    assert "[Preview]" in text
    assert "HIGH" in text or "high" in text.lower()
    assert "3" in text  # delete count


def test_narrate_preview_dry_run():
    rn = RuntimeNarration()
    data = {"risk_level": "low", "op_count": 5, "status": "validated"}
    text = rn.narrate_preview(data)
    assert "[Preview]" in text
    assert "dry-run" in text.lower() or "dry_run" in text.lower() or "validated" in text.lower()


# ---------------------------------------------------------------------------
# narrate_runtime_event
# ---------------------------------------------------------------------------

def test_narrate_runtime_init():
    rn = RuntimeNarration()
    text = rn.narrate_runtime_event("init")
    assert "[Runtime]" in text
    assert "Runtime" in text


def test_narrate_runtime_bridge_unavailable():
    rn = RuntimeNarration()
    text = rn.narrate_runtime_event("bridge_unavailable", {"port": 18811})
    assert "[Runtime]" in text
    assert "18811" in text


def test_narrate_runtime_unknown_event():
    rn = RuntimeNarration()
    text = rn.narrate_runtime_event("unknown_event_xyz")
    assert "[Runtime]" in text
    assert "unknown_event_xyz" in text


# ---------------------------------------------------------------------------
# Log management
# ---------------------------------------------------------------------------

def test_get_session_log_limit():
    rn = RuntimeNarration()
    for i in range(20):
        rn.narrate("Runtime", f"Message {i}")
    log = rn.get_session_log(limit=5)
    assert len(log) == 5


def test_get_formatted_log():
    rn = RuntimeNarration()
    rn.narrate("Planning", "Test 1.")
    rn.narrate("Execution", "Test 2.")
    fmt = rn.get_formatted_log()
    assert all(isinstance(s, str) for s in fmt)
    assert any("[Planning]" in s for s in fmt)
    assert any("[Execution]" in s for s in fmt)


def test_clear_log():
    rn = RuntimeNarration()
    rn.narrate("Runtime", "Entry 1")
    rn.narrate("Runtime", "Entry 2")
    rn.clear_log()
    assert rn.get_session_log() == []


def test_log_max_size_trim():
    rn = RuntimeNarration(max_log_size=10)
    for i in range(20):
        rn.narrate("Runtime", f"Message {i}")
    log = rn.get_session_log(limit=100)
    assert len(log) <= 10


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

def test_stats_shape():
    rn = RuntimeNarration()
    s = rn.stats()
    assert "narrate_count" in s
    assert "log_size" in s
    assert "max_log_size" in s


def test_stats_count_increments():
    rn = RuntimeNarration()
    rn.narrate("Runtime", "A")
    rn.narrate("Planning", "B")
    rn.narrate("Execution", "C")
    assert rn.stats()["narrate_count"] == 3
