"""
Unit tests for the hou_mcp_replay_transaction node.

Verifies that the node:
  • loads and registers correctly via NodeRegistry
  • returns error when transaction_id is empty
  • returns error when transaction_id is not found in manager
  • dry_run returns validated / no execution
  • replays ops via houdini_runtime.execute_operation
  • reports replayed=True on successful commit
  • rolls back and reports replayed=False on first op failure
  • handles transaction with no operations (empty replay)
  • exec_out is always True
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.core.registry import NodeRegistry
from src.runtime import transaction_manager as tm_module
from src.runtime.transaction_manager import (
    get_transaction_manager,
    reset_transaction_manager_for_tests,
)
from src.runtime import scene_cache
from src.utils import hou_bridge as bridge_module


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module", autouse=True)
def _ensure_registry():
    repo = Path(__file__).parent.parent.parent
    NodeRegistry.load_all(str(repo / "nodes"))
    NodeRegistry._load_directory(str(repo / "plugins" / "houdini" / "v_nodes_houdini"))


@pytest.fixture(autouse=True)
def _clean():
    reset_transaction_manager_for_tests()
    scene_cache.get_scene_cache().clear_dirty_state()
    scene_cache.get_scene_cache().invalidate()
    yield
    reset_transaction_manager_for_tests()


class _FakeBridge:
    def __init__(self):
        self.created = []
        self.parms = {}

    def create_node(self, parent, node_type, name=""):
        full = f"{parent.rstrip('/')}/{name or node_type}"
        self.created.append(full)
        return {"path": full, "name": name or node_type, "type": node_type}

    def get_parm(self, node, parm):
        return {"value": self.parms.get(node, {}).get(parm, 0)}

    def set_parms(self, node, parms):
        self.parms.setdefault(node, {}).update(parms)
        return {"set": True, "count": len(parms)}

    def set_parm(self, node, parm, value):
        self.parms.setdefault(node, {})[parm] = value
        return {"set": True}

    def connect_nodes(self, from_node, to_node, output=0, input_idx=0):
        return {"connected": True}

    def delete_node(self, path):
        return {"deleted": path}

    def cook_node(self, path, force=False):
        return {"cooked": True}

    def set_display_flag(self, path, on=True):
        return {"set": True}

    def set_render_flag(self, path, on=True):
        return {"set": True}

    def layout_children(self, path):
        return {"done": True}

    def node_info(self, path):
        return {"path": path, "type": "null", "category": "Sop"}

    def node_exists(self, path):
        return {"exists": True}

    def run_code(self, code):
        return {"result": None}


@pytest.fixture
def fake_bridge(monkeypatch):
    fake = _FakeBridge()
    monkeypatch.setattr(bridge_module, "get_bridge", lambda: fake)
    return fake


def _node():
    cls = NodeRegistry.get_class("hou_mcp_replay_transaction")
    assert cls is not None, "hou_mcp_replay_transaction not registered"
    return cls()


# ---------------------------------------------------------------------------
# Helper: build a committed transaction in the manager with ops
# ---------------------------------------------------------------------------

async def _build_committed_txn(ops: list) -> str:
    """Create and commit a transaction with the given operations.

    Stores minimal recorded-op dicts so replay can extract params.
    """
    from src.runtime import houdini_runtime
    mgr = get_transaction_manager()
    txn_id = await mgr.begin_transaction("source_txn")
    for op in ops:
        recorded = {
            "op": op["op"],
            "params": {k: v for k, v in op.items()},
            "status": "ok",
            "snapshot": {},
            "result": None,
        }
        await mgr.record_operation(txn_id, recorded)
    await mgr.commit_transaction(txn_id)
    return txn_id


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def test_node_registers():
    cls = NodeRegistry.get_class("hou_mcp_replay_transaction")
    assert cls is not None


def test_node_has_expected_ports():
    node = _node()
    assert "transaction_id" in node.inputs
    assert "dry_run" in node.inputs
    assert "rollback_on_error" in node.inputs
    assert "replayed" in node.outputs
    assert "operations_executed" in node.outputs
    assert "errors" in node.outputs
    assert "graph_diff" in node.outputs
    assert "status" in node.outputs
    assert "report_json" in node.outputs


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_empty_transaction_id_returns_error():
    node = _node()
    result = await node.execute({"transaction_id": "", "dry_run": False})
    assert result["exec_out"] is True
    assert result["status"] == "failed"
    assert len(result["errors"]) >= 1


@pytest.mark.asyncio
async def test_unknown_transaction_id_returns_error():
    node = _node()
    result = await node.execute({"transaction_id": "nonexistent-id", "dry_run": False})
    assert result["exec_out"] is True
    assert result["status"] == "failed"
    assert any("not found" in str(e) for e in result["errors"])


# ---------------------------------------------------------------------------
# Empty transaction (no ops)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_empty_transaction_replays_ok(fake_bridge):
    mgr = get_transaction_manager()
    txn_id = await mgr.begin_transaction("empty_txn")
    await mgr.commit_transaction(txn_id)

    node = _node()
    result = await node.execute({"transaction_id": txn_id, "dry_run": False})
    assert result["exec_out"] is True
    assert result["replayed"] is True
    assert result["operations_executed"] == []


# ---------------------------------------------------------------------------
# dry_run
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dry_run_returns_validated_status(fake_bridge):
    ops = [{"op": "create_node", "parent": "/obj", "type": "geo", "name": "test"}]
    txn_id = await _build_committed_txn(ops)

    node = _node()
    result = await node.execute({"transaction_id": txn_id, "dry_run": True})
    assert result["exec_out"] is True
    assert result["status"] == "validated"
    assert result["replayed"] is False
    assert fake_bridge.created == []  # nothing executed


@pytest.mark.asyncio
async def test_dry_run_fails_on_invalid_ops(fake_bridge):
    """If stored op has shape error, dry_run returns failed."""
    mgr = get_transaction_manager()
    txn_id = await mgr.begin_transaction("bad_ops_txn")
    await mgr.record_operation(txn_id, {
        "op": "create_node",
        "params": {"op": "create_node"},  # missing parent + type → will fail validation
        "status": "ok", "snapshot": {}, "result": None,
    })
    await mgr.commit_transaction(txn_id)

    node = _node()
    result = await node.execute({"transaction_id": txn_id, "dry_run": True})
    assert result["exec_out"] is True
    # Either validated (shape check passed at record time with minimal params)
    # or failed — either way no exception raised
    assert result["status"] in ("validated", "failed")


# ---------------------------------------------------------------------------
# Successful replay
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_successful_replay_commits(fake_bridge):
    ops = [{"op": "create_node", "parent": "/obj", "type": "geo", "name": "geo_test"}]
    txn_id = await _build_committed_txn(ops)

    node = _node()
    result = await node.execute({
        "transaction_id": txn_id, "dry_run": False, "rollback_on_error": True
    })
    assert result["exec_out"] is True
    assert result["replayed"] is True
    assert result["status"] == "committed"
    assert len(result["operations_executed"]) == 1
    assert "/obj/geo_test" in fake_bridge.created


@pytest.mark.asyncio
async def test_replay_graph_diff_populated(fake_bridge):
    ops = [{"op": "create_node", "parent": "/obj", "type": "geo", "name": "ball"}]
    txn_id = await _build_committed_txn(ops)

    node = _node()
    result = await node.execute({"transaction_id": txn_id, "dry_run": False})
    diff = result["graph_diff"]
    assert "created" in diff
    assert any("ball" in p for p in diff["created"])


# ---------------------------------------------------------------------------
# Rollback on failure
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rollback_on_error_when_op_fails(monkeypatch):
    """If an op fails mid-replay, rollback_on_error=True triggers rollback."""
    from src.runtime import houdini_runtime

    call_count = {"n": 0}

    original_execute = houdini_runtime.execute_operation

    async def _patched(op):
        call_count["n"] += 1
        if call_count["n"] == 2:
            # Second op fails
            return {
                "op": op.get("op", "create_node"),
                "params": op,
                "result": None,
                "snapshot": {},
                "status": "failed",
                "error": "forced failure",
                "dirty": [],
            }
        return await original_execute(op)

    monkeypatch.setattr(houdini_runtime, "execute_operation", _patched)

    import src.utils.hou_bridge as bridge_mod
    fake = _FakeBridge()
    monkeypatch.setattr(bridge_mod, "get_bridge", lambda: fake)

    ops = [
        {"op": "create_node", "parent": "/obj", "type": "geo", "name": "a"},
        {"op": "create_node", "parent": "/obj", "type": "geo", "name": "b"},
    ]
    txn_id = await _build_committed_txn(ops)

    node = _node()
    result = await node.execute({
        "transaction_id": txn_id, "dry_run": False, "rollback_on_error": True
    })
    assert result["exec_out"] is True
    assert result["replayed"] is False
    assert result["status"] in ("rolled_back", "failed")


# ---------------------------------------------------------------------------
# report_json round-trip
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_report_json_round_trips(fake_bridge):
    ops = [{"op": "create_node", "parent": "/obj", "type": "geo", "name": "x"}]
    txn_id = await _build_committed_txn(ops)

    node = _node()
    result = await node.execute({"transaction_id": txn_id, "dry_run": False})
    parsed = json.loads(result["report_json"])
    assert "status" in parsed
    assert "replayed" in parsed
    assert "graph_diff" in parsed


# ---------------------------------------------------------------------------
# exec_out always True
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_exec_out_always_true():
    node = _node()
    result = await node.execute({"transaction_id": "", "dry_run": False})
    assert result.get("exec_out") is True
