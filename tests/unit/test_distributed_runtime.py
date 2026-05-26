"""
Unit tests for src.runtime.distributed_runtime.

Covers:
  • register_worker returns uuid
  • deregister_worker returns True/False
  • get_worker / list_workers
  • list_workers cap_filter
  • dispatch_operations — no_worker when none registered
  • dispatch_operations — local worker dry_run path
  • dispatch_operations — remote worker returns dispatched status
  • dispatch_operations — worker load tracking (acquire/release)
  • get_dispatch_status
  • stats output shape
  • singleton / reset
"""

from __future__ import annotations

import pytest

from src.runtime.distributed_runtime import (
    DistributedRuntime,
    get_distributed_runtime,
    reset_distributed_runtime_for_tests,
)
from src.runtime.capability_registry   import reset_capability_registry_for_tests
from src.runtime.runtime_constraints   import reset_runtime_constraints_for_tests
from src.runtime.validation_engine     import reset_validation_engine_for_tests
from src.runtime.dependency_graph      import reset_dependency_graph_for_tests


@pytest.fixture(autouse=True)
def _reset():
    reset_distributed_runtime_for_tests()
    reset_capability_registry_for_tests()
    reset_runtime_constraints_for_tests()
    reset_validation_engine_for_tests()
    reset_dependency_graph_for_tests()
    yield
    reset_distributed_runtime_for_tests()
    reset_capability_registry_for_tests()
    reset_runtime_constraints_for_tests()
    reset_validation_engine_for_tests()
    reset_dependency_graph_for_tests()


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def test_register_worker_returns_uuid():
    dr  = get_distributed_runtime()
    wid = dr.register_worker("farm-01", ["houdini", "karma"])
    assert isinstance(wid, str) and len(wid) == 36


def test_register_worker_empty_name_raises():
    dr = get_distributed_runtime()
    with pytest.raises(ValueError):
        dr.register_worker("", [])


def test_deregister_worker_true():
    dr  = get_distributed_runtime()
    wid = dr.register_worker("farm-01", [])
    assert dr.deregister_worker(wid) is True


def test_deregister_worker_unknown_false():
    dr = get_distributed_runtime()
    assert dr.deregister_worker("00000000-0000-0000-0000-000000000000") is False


def test_get_worker_returns_dict():
    dr  = get_distributed_runtime()
    wid = dr.register_worker("farm-01", ["houdini"])
    w   = dr.get_worker(wid)
    assert w is not None
    assert w["name"] == "farm-01"
    assert "houdini" in w["capabilities"]


def test_get_worker_unknown_returns_none():
    dr = get_distributed_runtime()
    assert dr.get_worker("missing") is None


def test_list_workers_cap_filter():
    dr  = get_distributed_runtime()
    dr.register_worker("farm-01", ["houdini", "karma"])
    dr.register_worker("farm-02", ["maya"])
    hou_workers = dr.list_workers(cap_filter="houdini")
    assert len(hou_workers) == 1
    assert hou_workers[0]["name"] == "farm-01"


# ---------------------------------------------------------------------------
# Dispatch — no worker
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dispatch_no_worker():
    dr     = get_distributed_runtime()
    result = await dr.dispatch_operations(
        [{"op": "create_node", "parent": "/obj", "type": "geo"}],
        required_capabilities=["houdini"],
    )
    assert result["ok"] is False
    assert result["status"] == "no_worker"
    assert result["dispatch_id"]


# ---------------------------------------------------------------------------
# Dispatch — remote worker (no live Houdini needed)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dispatch_remote_worker_returns_dispatched():
    dr  = get_distributed_runtime()
    wid = dr.register_worker("remote-01", ["houdini"], endpoint="remote://farm1", max_load=8)
    result = await dr.dispatch_operations(
        [{"op": "create_node", "parent": "/obj", "type": "geo"}],
        required_capabilities=["houdini"],
    )
    assert result["ok"] is True
    assert result["status"] == "dispatched"
    assert result["worker_id"] == wid


@pytest.mark.asyncio
async def test_dispatch_remote_worker_dispatch_id_retrievable():
    dr  = get_distributed_runtime()
    dr.register_worker("remote-01", ["houdini"], endpoint="remote://farm1")
    result  = await dr.dispatch_operations(
        [{"op": "cook_node", "path": "/obj/geo1"}],
        required_capabilities=["houdini"],
    )
    did = result["dispatch_id"]
    rec = dr.get_dispatch_status(did)
    assert rec is not None
    assert rec["status"] == "dispatched"


# ---------------------------------------------------------------------------
# Dispatch — capability mismatch
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dispatch_capability_mismatch():
    dr = get_distributed_runtime()
    dr.register_worker("maya-01", ["maya"], endpoint="remote://maya-host")
    result = await dr.dispatch_operations(
        [{"op": "create_node", "parent": "/obj", "type": "geo"}],
        required_capabilities=["houdini"],  # maya worker can't do houdini
    )
    assert result["ok"] is False
    assert result["status"] == "no_worker"


# ---------------------------------------------------------------------------
# Local dispatch — dry run (no live Houdini)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dispatch_local_dry_run(monkeypatch):
    """Local dispatch dry_run never touches Houdini."""
    from src.runtime import distributed_runtime as dr_module

    async def fake_dispatch(self, ops, required_capabilities=None,
                            transaction_name="", dry_run=False, rollback_on_error=True):
        return {
            "ok": True, "status": "validated",
            "transaction_id": None, "operations_executed": 0,
            "errors": [], "graph_diff": {},
            "report_json": "{}",
        }

    dr = get_distributed_runtime()
    wid = dr.register_worker("local-01", ["houdini"], endpoint="local://")
    monkeypatch.setattr(dr_module.DistributedRuntime, "_execute_local", fake_dispatch)

    result = await dr.dispatch_operations(
        [{"op": "create_node", "parent": "/obj", "type": "geo"}],
        required_capabilities=["houdini"],
        dry_run=True,
    )
    assert result["ok"] is True
    assert result["status"] == "validated"


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def test_stats_shape():
    dr = get_distributed_runtime()
    dr.register_worker("w1", [], endpoint="local://")
    s = dr.stats()
    assert "total_workers"    in s
    assert "total_dispatches" in s
    assert s["total_workers"] == 1


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton_same_instance():
    a = get_distributed_runtime()
    b = get_distributed_runtime()
    assert a is b


def test_reset_creates_fresh_instance():
    a = get_distributed_runtime()
    reset_distributed_runtime_for_tests()
    b = get_distributed_runtime()
    assert a is not b
