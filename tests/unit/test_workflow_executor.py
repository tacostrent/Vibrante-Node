"""Tests for WorkflowExecutor (Tier 10 — §30)."""
import pytest
from src.runtime.workflows.workflow_executor import (
    ExecutionResult,
    WorkflowExecutor,
    get_workflow_executor,
    reset_workflow_executor_for_tests,
)
from src.runtime.workflows.workflow_pack import (
    WorkflowPack,
    get_builtin_packs,
    reset_workflow_pack_for_tests,
)
from src.runtime.workflows.workflow_blueprint import reset_workflow_blueprint_for_tests
from src.runtime.workflows.workflow_validator import reset_workflow_validator_for_tests


@pytest.fixture(autouse=True)
def reset():
    reset_workflow_executor_for_tests()
    reset_workflow_pack_for_tests()
    reset_workflow_blueprint_for_tests()
    reset_workflow_validator_for_tests()
    yield
    reset_workflow_executor_for_tests()
    reset_workflow_pack_for_tests()
    reset_workflow_blueprint_for_tests()
    reset_workflow_validator_for_tests()


def _hangar_pack():
    return next(p for p in get_builtin_packs() if p.name == "industrial_hangar_pack")


def _bad_pack():
    return WorkflowPack(
        name="", version="", environment_type="",
        asset_strategy={}, population_strategy={}, placement_strategy={},
        lighting_strategy={}, camera_strategy={}, atmosphere_strategy={},
        review_strategy={},
    )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton():
    assert get_workflow_executor() is get_workflow_executor()


# ---------------------------------------------------------------------------
# preview_execution
# ---------------------------------------------------------------------------

def test_preview_ok():
    preview = get_workflow_executor().preview_execution(_hangar_pack())
    assert preview["ok"] is True


def test_preview_has_phases():
    preview = get_workflow_executor().preview_execution(_hangar_pack())
    assert len(preview["phases"]) == 7


def test_preview_has_op_count():
    preview = get_workflow_executor().preview_execution(_hangar_pack())
    assert preview["op_count"] >= 0


def test_preview_has_complexity():
    preview = get_workflow_executor().preview_execution(_hangar_pack())
    assert preview["estimated_complexity"] in ("simple", "moderate", "complex", "epic")


def test_preview_has_validation():
    preview = get_workflow_executor().preview_execution(_hangar_pack())
    assert "validation" in preview


def test_preview_bad_pack_not_ok():
    preview = get_workflow_executor().preview_execution(_bad_pack())
    assert preview["ok"] is False


# ---------------------------------------------------------------------------
# generate_transaction_plan
# ---------------------------------------------------------------------------

def test_transaction_plan_ok():
    plan = get_workflow_executor().generate_transaction_plan(_hangar_pack())
    assert plan["ok"] is True
    assert isinstance(plan["operations"], list)


def test_transaction_plan_bad_pack():
    plan = get_workflow_executor().generate_transaction_plan(_bad_pack())
    assert plan["ok"] is False


# ---------------------------------------------------------------------------
# execute_pack (dry_run=True — no bridge needed)
# ---------------------------------------------------------------------------

def test_execute_pack_dry_run():
    result = get_workflow_executor().execute_pack(_hangar_pack(), dry_run=True)
    assert result.ok            is True
    assert result.status        == "previewed"
    assert result.dry_run       is True
    assert result.transaction_id != ""


def test_execute_pack_dry_run_bad_pack():
    result = get_workflow_executor().execute_pack(_bad_pack(), dry_run=True)
    assert result.ok     is False
    assert result.errors


def test_execute_pack_dry_run_has_report_json():
    result = get_workflow_executor().execute_pack(_hangar_pack(), dry_run=True)
    assert result.report_json != ""


# ---------------------------------------------------------------------------
# execute_phase
# ---------------------------------------------------------------------------

def test_execute_phase_environment():
    res = get_workflow_executor().execute_phase(_hangar_pack(), "environment")
    assert res["ok"]    is True
    assert res["phase"] == "environment"
    assert isinstance(res["operations"], list)


def test_execute_phase_unknown_fails():
    res = get_workflow_executor().execute_phase(_hangar_pack(), "nonexistent_phase")
    assert res["ok"] is False


# ---------------------------------------------------------------------------
# estimate_runtime_cost
# ---------------------------------------------------------------------------

def test_estimate_runtime_cost_keys():
    cost = get_workflow_executor().estimate_runtime_cost(_hangar_pack())
    for key in ("op_count", "complexity", "estimated_secs",
                "memory_impact", "rollback_supported"):
        assert key in cost


def test_estimate_runtime_cost_positive():
    cost = get_workflow_executor().estimate_runtime_cost(_hangar_pack())
    assert cost["estimated_secs"] >= 0


def test_estimate_rollback_always_supported():
    cost = get_workflow_executor().estimate_runtime_cost(_hangar_pack())
    assert cost["rollback_supported"] is True


# ---------------------------------------------------------------------------
# ExecutionResult
# ---------------------------------------------------------------------------

def test_execution_result_to_dict():
    r = ExecutionResult(
        ok=True, workflow="test", environment="industrial_hangar",
        status="previewed",
    )
    d = r.to_dict()
    for key in ("ok", "workflow", "status", "transaction_id", "dry_run"):
        assert key in d


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

def test_stats_increments():
    ex = get_workflow_executor()
    ex.execute_pack(_hangar_pack(), dry_run=True)
    assert ex.stats()["execution_count"] >= 1
