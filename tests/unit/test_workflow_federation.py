"""
Unit tests for src.runtime.workflow_federation.

Covers:
  • create_federated_workflow returns uuid
  • create_federated_workflow empty name raises
  • create_federated_workflow empty segments raises
  • create_federated_workflow duplicate segment ids raises
  • create_federated_workflow cycle detection raises
  • get_workflow returns dict / None for unknown
  • list_workflows / list_workflows status filter
  • get_status shape
  • execute_federated all-success path (via MockAdapter)
  • execute_federated partial failure marks remaining segments skipped
  • execute_federated unknown workflow returns error
  • execute_federated dry_run passed to execute_for_dcc
  • topological ordering respected
  • stats shape
  • singleton / reset
"""

from __future__ import annotations

import pytest

from src.runtime.workflow_federation import (
    WorkflowFederation,
    get_workflow_federation,
    reset_workflow_federation_for_tests,
)
from src.runtime.multi_dcc_runtime import (
    get_multi_dcc_runtime,
    reset_multi_dcc_runtime_for_tests,
    DccAdapter,
)
from src.runtime.distributed_runtime  import reset_distributed_runtime_for_tests
from src.runtime.capability_registry  import reset_capability_registry_for_tests
from src.runtime.runtime_constraints  import reset_runtime_constraints_for_tests
from src.runtime.validation_engine    import reset_validation_engine_for_tests
from src.runtime.dependency_graph     import reset_dependency_graph_for_tests


class MockAdapter(DccAdapter):
    """Adapter that always returns success."""
    def __init__(self, dcc_type="custom"):
        super().__init__(dcc_type)
        self._available = True

    @property
    def is_available(self):
        return self._available

    async def execute_operations(self, ops, dry_run=False):
        return {
            "ok": True, "status": "mock_ok",
            "operations_executed": len(ops),
            "errors": [], "graph_diff": {},
        }


class FailAdapter(DccAdapter):
    """Adapter that always returns failure."""
    def __init__(self, dcc_type="fail"):
        super().__init__(dcc_type)
        self._available = True

    @property
    def is_available(self):
        return self._available

    async def execute_operations(self, ops, dry_run=False):
        return {
            "ok": False, "status": "mock_fail",
            "error": "injected failure",
            "operations_executed": 0,
            "errors": ["injected failure"], "graph_diff": {},
        }


@pytest.fixture(autouse=True)
def _reset():
    reset_workflow_federation_for_tests()
    reset_multi_dcc_runtime_for_tests()
    reset_distributed_runtime_for_tests()
    reset_capability_registry_for_tests()
    reset_runtime_constraints_for_tests()
    reset_validation_engine_for_tests()
    reset_dependency_graph_for_tests()
    yield
    reset_workflow_federation_for_tests()
    reset_multi_dcc_runtime_for_tests()
    reset_distributed_runtime_for_tests()


def _register_mock_houdini():
    """Replace the built-in Houdini adapter with a safe mock."""
    mdr = get_multi_dcc_runtime()
    mdr.register_dcc("houdini", MockAdapter("houdini"),
                     ["create_node", "set_parms", "connect_nodes", "delete_node",
                      "cook_node", "layout_children", "build_node_chain",
                      "set_display_flag", "set_render_flag", "karma", "mantra"])
    return mdr


def _make_simple_segments(n=2, target_dcc="houdini"):
    """Return n independent segments."""
    return [
        {
            "id": f"seg_{i}", "name": f"Segment {i}",
            "operations": [{"op": "create_node", "parent": "/obj", "type": "geo"}],
            "target_dcc": target_dcc,
            "dependencies": [],
        }
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# Creation
# ---------------------------------------------------------------------------

def test_create_federated_workflow_returns_uuid():
    wf  = get_workflow_federation()
    wid = wf.create_federated_workflow("test_wf", _make_simple_segments(1))
    assert isinstance(wid, str) and len(wid) == 36


def test_create_empty_name_raises():
    wf = get_workflow_federation()
    with pytest.raises(ValueError, match="non-empty"):
        wf.create_federated_workflow("", _make_simple_segments(1))


def test_create_empty_segments_raises():
    wf = get_workflow_federation()
    with pytest.raises(ValueError):
        wf.create_federated_workflow("empty_wf", [])


def test_create_duplicate_segment_ids_raises():
    wf = get_workflow_federation()
    segs = [
        {"id": "dup", "name": "A", "operations": [], "target_dcc": "houdini", "dependencies": []},
        {"id": "dup", "name": "B", "operations": [], "target_dcc": "houdini", "dependencies": []},
    ]
    with pytest.raises(ValueError, match="unique"):
        wf.create_federated_workflow("dup_wf", segs)


def test_create_cycle_raises():
    wf = get_workflow_federation()
    segs = [
        {"id": "a", "name": "A", "operations": [], "target_dcc": "houdini", "dependencies": ["b"]},
        {"id": "b", "name": "B", "operations": [], "target_dcc": "houdini", "dependencies": ["a"]},
    ]
    with pytest.raises(ValueError, match="[Cc]ycle"):
        wf.create_federated_workflow("cycle_wf", segs)


# ---------------------------------------------------------------------------
# get_workflow / list_workflows / get_status
# ---------------------------------------------------------------------------

def test_get_workflow_returns_dict():
    wf  = get_workflow_federation()
    wid = wf.create_federated_workflow("wf1", _make_simple_segments(2))
    w   = wf.get_workflow(wid)
    assert w is not None
    assert w["name"]           == "wf1"
    assert len(w["segments"]) == 2
    assert w["status"]         == "pending"


def test_get_workflow_unknown_returns_none():
    wf = get_workflow_federation()
    assert wf.get_workflow("00000000-0000-0000-0000-000000000000") is None


def test_list_workflows():
    wf = get_workflow_federation()
    wf.create_federated_workflow("wf_a", _make_simple_segments(1))
    wf.create_federated_workflow("wf_b", _make_simple_segments(1))
    workflows = wf.list_workflows()
    names = {w["name"] for w in workflows}
    assert "wf_a" in names and "wf_b" in names


def test_list_workflows_status_filter():
    wf  = get_workflow_federation()
    wid = wf.create_federated_workflow("pending_wf", _make_simple_segments(1))
    pending = wf.list_workflows(status="pending")
    assert any(w["id"] == wid for w in pending)
    completed = wf.list_workflows(status="completed")
    assert not any(w["id"] == wid for w in completed)


def test_get_status_shape():
    wf  = get_workflow_federation()
    wid = wf.create_federated_workflow("status_wf", _make_simple_segments(2))
    s   = wf.get_status(wid)
    assert s is not None
    assert "workflow_id"   in s
    assert "status"        in s
    assert "segment_count" in s
    assert "segments"      in s
    assert s["segment_count"] == 2


def test_get_status_unknown_returns_none():
    wf = get_workflow_federation()
    assert wf.get_status("missing") is None


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_all_success():
    _register_mock_houdini()
    wf  = get_workflow_federation()
    wid = wf.create_federated_workflow("success_wf", _make_simple_segments(2))
    result = await wf.execute_federated(wid)
    assert result["ok"] is True
    assert result["status"] == "completed"
    assert result["segments_ok"] == 2


@pytest.mark.asyncio
async def test_execute_unknown_workflow_error():
    wf = get_workflow_federation()
    result = await wf.execute_federated("nonexistent-id")
    assert result["ok"] is False
    assert "Unknown workflow" in result["error"]


@pytest.mark.asyncio
async def test_execute_failure_marks_remaining_skipped():
    mdr = get_multi_dcc_runtime()
    mdr.register_dcc("houdini",     MockAdapter("houdini"),  ["any_cap"])
    mdr.register_dcc("fail_target", FailAdapter("fail_target"), ["fail_cap"])

    wf = get_workflow_federation()
    segs = [
        {
            "id": "first", "name": "First", "operations": [{"op": "create_node"}],
            "target_dcc": "fail_target", "dependencies": [],
        },
        {
            "id": "second", "name": "Second", "operations": [{"op": "create_node"}],
            "target_dcc": "houdini", "dependencies": ["first"],
        },
    ]
    wid = wf.create_federated_workflow("fail_wf", segs)
    result = await wf.execute_federated(wid)
    assert result["ok"] is False
    assert result["status"] == "failed"
    # Second segment should be skipped
    w = wf.get_workflow(wid)
    seg_statuses = {s["id"]: s["status"] for s in w["segments"]}
    assert seg_statuses["first"]  == "failed"
    assert seg_statuses["second"] == "skipped"


@pytest.mark.asyncio
async def test_execute_dry_run_passed_through():
    """dry_run flag should be forwarded to execute_for_dcc; mock always succeeds."""
    import json
    _register_mock_houdini()
    wf  = get_workflow_federation()
    wid = wf.create_federated_workflow("dry_wf", _make_simple_segments(1))
    result = await wf.execute_federated(wid, dry_run=True)
    assert result["ok"] is True
    # dry_run flag is stored in report_json
    report = json.loads(result["report_json"])
    assert report["dry_run"] is True


@pytest.mark.asyncio
async def test_execute_topological_order():
    """Segments with dependencies execute in correct order."""
    execution_order = []

    class OrderTrackingAdapter(DccAdapter):
        def __init__(self, tag):
            super().__init__(tag)
            self._tag = tag

        @property
        def is_available(self):
            return True

        async def execute_operations(self, ops, dry_run=False):
            execution_order.append(self._tag)
            return {"ok": True, "status": "ok", "operations_executed": 0,
                    "errors": [], "graph_diff": {}}

    mdr = get_multi_dcc_runtime()
    mdr.register_dcc("dcc_a", OrderTrackingAdapter("a"), ["cap_a"])
    mdr.register_dcc("dcc_b", OrderTrackingAdapter("b"), ["cap_b"])
    mdr.register_dcc("dcc_c", OrderTrackingAdapter("c"), ["cap_c"])

    wf = get_workflow_federation()
    segs = [
        {"id": "c", "name": "C", "operations": [], "target_dcc": "dcc_c", "dependencies": ["b"]},
        {"id": "b", "name": "B", "operations": [], "target_dcc": "dcc_b", "dependencies": ["a"]},
        {"id": "a", "name": "A", "operations": [], "target_dcc": "dcc_a", "dependencies": []},
    ]
    wid = wf.create_federated_workflow("ordered_wf", segs)
    await wf.execute_federated(wid)
    assert execution_order == ["a", "b", "c"]


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def test_stats_shape():
    wf = get_workflow_federation()
    wf.create_federated_workflow("wf1", _make_simple_segments(1))
    wf.create_federated_workflow("wf2", _make_simple_segments(1))
    s = wf.stats()
    assert "total_workflows" in s
    assert "by_status"       in s
    assert s["total_workflows"] == 2
    assert s["by_status"].get("pending", 0) == 2


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton_same_instance():
    a = get_workflow_federation()
    b = get_workflow_federation()
    assert a is b


def test_reset_creates_fresh_instance():
    a = get_workflow_federation()
    reset_workflow_federation_for_tests()
    b = get_workflow_federation()
    assert a is not b
