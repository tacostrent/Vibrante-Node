"""
Unit tests for src.runtime.transaction_manager.

Covers:
  • Transaction lifecycle (begin → record → commit / rollback)
  • Rollback dispatch via the registered handler table
  • Rollback tolerance — a failing handler must NEVER raise
  • Bounded execution history
  • Inspection helpers (get_transaction, list_transactions, clear_finished)
  • The Houdini executor + handlers via a mocked bridge (no live Houdini)

The transaction manager itself is DCC-agnostic; we still verify that
`houdini_runtime` registers handlers for every supported op type when imported.
"""

from __future__ import annotations

import asyncio
import pytest

from src.runtime import transaction_manager, houdini_runtime, scene_cache
from src.utils import hou_bridge as bridge_module


# ---------------------------------------------------------------------------
# Fakes & fixtures
# ---------------------------------------------------------------------------

class FakeBridge:
    def __init__(self):
        self.parms: dict[str, dict] = {}
        self.created: list[str] = []
        self.deleted: list[str] = []
        self.set_parms_calls: list[tuple[str, dict]] = []
        self.connections: list[tuple[str, str, int, int]] = []
        self.flags: dict[str, dict] = {}
        self.cooked: list[str] = []
        self.layout_calls: list[str] = []
        self.run_code_calls: list[str] = []
        self.fail_create_node = False
        self.fail_set_parms = False
        self.fail_delete_node = False
        # input_sources: target_path → list of source paths per input slot
        self.input_sources: dict[str, list[str | None]] = {}

    # node lifecycle
    def create_node(self, parent, node_type, name=""):
        if self.fail_create_node:
            raise RuntimeError("create_node forced failure")
        full = f"{parent.rstrip('/')}/{name or node_type}"
        self.created.append(full)
        return {"path": full, "name": name or node_type, "type": node_type}

    def delete_node(self, path):
        if self.fail_delete_node:
            raise RuntimeError("delete_node forced failure")
        self.deleted.append(path)
        return {"deleted": path}

    # parms
    def get_parm(self, node, parm):
        return {"value": self.parms.get(node, {}).get(parm, 0)}

    def set_parm(self, node, parm, value):
        self.parms.setdefault(node, {})[parm] = value
        return {"set": True}

    def set_parms(self, node, parms):
        if self.fail_set_parms:
            raise RuntimeError("set_parms forced failure")
        self.set_parms_calls.append((node, dict(parms)))
        bucket = self.parms.setdefault(node, {})
        for k, v in parms.items():
            bucket[k] = v
        return {"set": True, "count": len(parms)}

    # connections
    def connect_nodes(self, from_node, to_node, output=0, input_idx=0):
        self.connections.append((from_node, to_node, output, input_idx))
        return {"connected": True}

    # flags
    def set_display_flag(self, path, on=True):
        self.flags.setdefault(path, {})["display"] = bool(on)
        return {"set": True}

    def set_render_flag(self, path, on=True):
        self.flags.setdefault(path, {})["render"] = bool(on)
        return {"set": True}

    # other
    def cook_node(self, path, force=False):
        self.cooked.append(path)
        return {"cooked": True}

    def layout_children(self, path):
        self.layout_calls.append(path)
        return {"done": True}

    def node_info(self, path):
        return {"path": path, "type": "null", "category": "Sop"}

    def node_exists(self, path):
        return {"exists": True}

    # run_code is used internally by houdini_runtime for prev-state capture
    # (flag reads, input-source reads). Return predictable stubs.
    def run_code(self, code):
        self.run_code_calls.append(code)
        if "isDisplayFlagSet" in code:
            return {"result": False}
        if "isRenderFlagSet" in code:
            return {"result": False}
        if "_n.inputs()" in code:
            return {"result": None}  # no prior connection
        return {"result": None}


@pytest.fixture
def fake_bridge(monkeypatch):
    fake = FakeBridge()
    monkeypatch.setattr(bridge_module, "get_bridge", lambda: fake)
    scene_cache.get_scene_cache().clear_dirty_state()
    scene_cache.get_scene_cache().invalidate()
    return fake


@pytest.fixture
def fresh_manager():
    transaction_manager.reset_transaction_manager_for_tests()
    mgr = transaction_manager.get_transaction_manager()
    yield mgr
    transaction_manager.reset_transaction_manager_for_tests()


# ---------------------------------------------------------------------------
# Handler registration (sanity)
# ---------------------------------------------------------------------------

def test_all_houdini_ops_have_rollback_handlers():
    handlers = set(transaction_manager.list_rollback_handlers())
    missing = set(houdini_runtime.SUPPORTED_OPS) - handlers
    assert not missing, f"ops without rollback handlers: {sorted(missing)}"


def test_register_rollback_handler_rejects_bad_inputs():
    with pytest.raises(ValueError):
        transaction_manager.register_rollback_handler("", lambda x: x)
    with pytest.raises(TypeError):
        transaction_manager.register_rollback_handler("op", "not callable")


# ---------------------------------------------------------------------------
# Transaction lifecycle
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_begin_transaction_returns_uuid(fresh_manager):
    txn_id = await fresh_manager.begin_transaction("my_txn")
    assert isinstance(txn_id, str)
    assert len(txn_id) >= 32
    view = await fresh_manager.get_transaction(txn_id)
    assert view["status"] == "pending"
    assert view["name"] == "my_txn"
    assert view["operations"] == []


@pytest.mark.asyncio
async def test_begin_transaction_requires_name(fresh_manager):
    with pytest.raises(ValueError):
        await fresh_manager.begin_transaction("")


@pytest.mark.asyncio
async def test_record_operation_appends(fresh_manager):
    txn_id = await fresh_manager.begin_transaction("t")
    await fresh_manager.record_operation(txn_id, {
        "op": "create_node",
        "params": {"parent": "/obj", "type": "geo"},
        "result": {"path": "/obj/geo1"},
        "snapshot": {"created_path": "/obj/geo1"},
        "status": "ok",
        "dirty": ["/obj/geo1"],
    })
    view = await fresh_manager.get_transaction(txn_id)
    assert len(view["operations"]) == 1
    assert view["operations"][0]["op"] == "create_node"
    assert view["dirty_nodes"] == ["/obj/geo1"]


@pytest.mark.asyncio
async def test_record_operation_rejects_unknown_transaction(fresh_manager):
    with pytest.raises(KeyError):
        await fresh_manager.record_operation("does-not-exist", {"op": "noop"})


@pytest.mark.asyncio
async def test_record_operation_rejects_after_commit(fresh_manager):
    txn_id = await fresh_manager.begin_transaction("t")
    await fresh_manager.commit_transaction(txn_id)
    with pytest.raises(RuntimeError):
        await fresh_manager.record_operation(txn_id, {"op": "create_node"})


@pytest.mark.asyncio
async def test_record_operation_requires_op_field(fresh_manager):
    txn_id = await fresh_manager.begin_transaction("t")
    with pytest.raises(ValueError):
        await fresh_manager.record_operation(txn_id, {"params": {}})


@pytest.mark.asyncio
async def test_record_failed_op_captures_error(fresh_manager):
    txn_id = await fresh_manager.begin_transaction("t")
    await fresh_manager.record_operation(txn_id, {
        "op": "create_node",
        "status": "failed",
        "error": "boom",
    })
    view = await fresh_manager.get_transaction(txn_id)
    assert view["errors"] == [{"op": "create_node", "error": "boom"}]


@pytest.mark.asyncio
async def test_commit_transitions_to_committed(fresh_manager):
    txn_id = await fresh_manager.begin_transaction("t")
    view = await fresh_manager.commit_transaction(txn_id)
    assert view["status"] == "committed"
    assert view["committed_at"] is not None


@pytest.mark.asyncio
async def test_cannot_commit_twice(fresh_manager):
    txn_id = await fresh_manager.begin_transaction("t")
    await fresh_manager.commit_transaction(txn_id)
    with pytest.raises(RuntimeError):
        await fresh_manager.commit_transaction(txn_id)


@pytest.mark.asyncio
async def test_cannot_rollback_committed(fresh_manager):
    txn_id = await fresh_manager.begin_transaction("t")
    await fresh_manager.commit_transaction(txn_id)
    with pytest.raises(RuntimeError):
        await fresh_manager.rollback_transaction(txn_id)


@pytest.mark.asyncio
async def test_clear_finished_only_drops_completed(fresh_manager):
    a = await fresh_manager.begin_transaction("a")
    b = await fresh_manager.begin_transaction("b")
    await fresh_manager.commit_transaction(a)
    removed = await fresh_manager.clear_finished_transactions()
    assert removed == 1
    assert await fresh_manager.get_transaction(a) is None
    assert (await fresh_manager.get_transaction(b))["status"] == "pending"


@pytest.mark.asyncio
async def test_list_transactions_returns_all(fresh_manager):
    await fresh_manager.begin_transaction("a")
    await fresh_manager.begin_transaction("b")
    listed = await fresh_manager.list_transactions()
    assert {t["name"] for t in listed} == {"a", "b"}


# ---------------------------------------------------------------------------
# Rollback dispatch
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rollback_walks_operations_in_reverse(fresh_manager):
    """A handler is called once per recorded operation, in reverse order."""
    call_order: list[str] = []

    async def handler(recorded):
        call_order.append(recorded["params"]["tag"])
        return {"ok": True}

    transaction_manager.register_rollback_handler("noop_test", handler)
    txn_id = await fresh_manager.begin_transaction("t")
    for tag in ("a", "b", "c"):
        await fresh_manager.record_operation(txn_id, {
            "op": "noop_test", "params": {"tag": tag}, "snapshot": {}, "status": "ok",
        })

    result = await fresh_manager.rollback_transaction(txn_id)
    assert call_order == ["c", "b", "a"]
    assert result["status"] == "rolled_back"
    assert result["rollback_errors"] == []


@pytest.mark.asyncio
async def test_rollback_handler_raising_does_not_crash(fresh_manager):
    """A handler that raises must be captured into rollback_errors, not propagated."""

    async def boom(recorded):
        raise RuntimeError("rollback exploded")

    transaction_manager.register_rollback_handler("boom_test", boom)
    txn_id = await fresh_manager.begin_transaction("t")
    await fresh_manager.record_operation(txn_id, {
        "op": "boom_test", "params": {}, "snapshot": {}, "status": "ok",
    })
    result = await fresh_manager.rollback_transaction(txn_id)
    assert result["status"] == "rolled_back"
    assert len(result["rollback_errors"]) == 1
    assert "RuntimeError: rollback exploded" in result["rollback_errors"][0]["error"]


@pytest.mark.asyncio
async def test_rollback_reports_missing_handler(fresh_manager):
    """Unknown op types yield an explicit rollback error, not a crash."""
    txn_id = await fresh_manager.begin_transaction("t")
    await fresh_manager.record_operation(txn_id, {
        "op": "unknown_op_xyz", "params": {}, "snapshot": {}, "status": "ok",
    })
    result = await fresh_manager.rollback_transaction(txn_id)
    assert any("no rollback handler" in e["error"] for e in result["rollback_errors"])


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_history_records_lifecycle_events(fresh_manager):
    txn_id = await fresh_manager.begin_transaction("h")
    await fresh_manager.record_operation(txn_id, {"op": "create_node", "snapshot": {}})
    await fresh_manager.commit_transaction(txn_id)
    history = fresh_manager.get_history(limit=10)
    actions = [h["action"] for h in history if h["transaction_id"] == txn_id]
    assert actions == ["begin", "record", "commit"]


def test_history_is_bounded(fresh_manager):
    fresh_manager.HISTORY_CAP = 5
    for i in range(20):
        fresh_manager._append_history(f"t{i}", "begin", "ok", {})
    assert len(fresh_manager.get_history(limit=100)) == 5


# ---------------------------------------------------------------------------
# End-to-end via houdini_runtime executors (mocked bridge)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_e2e_create_node_executes_and_rolls_back(fresh_manager, fake_bridge):
    txn_id = await fresh_manager.begin_transaction("e2e")
    rec = await houdini_runtime.execute_operation({
        "op": "create_node", "parent": "/obj", "type": "geo", "name": "myGeo",
    })
    await fresh_manager.record_operation(txn_id, rec)
    assert rec["status"] == "ok"
    assert "/obj/myGeo" in fake_bridge.created

    # dirty tracking populated
    dirty = scene_cache.get_scene_cache().get_dirty_nodes()
    assert "/obj/myGeo" in dirty["created"]

    # Roll back → the created node gets deleted
    result = await fresh_manager.rollback_transaction(txn_id)
    assert result["status"] == "rolled_back"
    assert result["rollback_errors"] == []
    assert "/obj/myGeo" in fake_bridge.deleted


@pytest.mark.asyncio
async def test_e2e_set_parms_restores_previous_values(fresh_manager, fake_bridge):
    fake_bridge.parms["/obj/box1"] = {"sizex": 1.0, "sizey": 2.0}
    txn_id = await fresh_manager.begin_transaction("p")
    rec = await houdini_runtime.execute_operation({
        "op": "set_parms",
        "node": "/obj/box1",
        "parms": {"sizex": 10.0, "sizey": 20.0},
    })
    await fresh_manager.record_operation(txn_id, rec)
    assert fake_bridge.parms["/obj/box1"]["sizex"] == 10.0

    result = await fresh_manager.rollback_transaction(txn_id)
    assert result["status"] == "rolled_back"
    assert result["rollback_errors"] == []
    assert fake_bridge.parms["/obj/box1"]["sizex"] == 1.0
    assert fake_bridge.parms["/obj/box1"]["sizey"] == 2.0


@pytest.mark.asyncio
async def test_e2e_delete_node_rollback_reports_limitation(fresh_manager, fake_bridge):
    """Tier 2: deleting a node is irreversible — rollback must report the failure cleanly."""
    txn_id = await fresh_manager.begin_transaction("d")
    rec = await houdini_runtime.execute_operation({
        "op": "delete_node", "path": "/obj/old",
    })
    await fresh_manager.record_operation(txn_id, rec)

    result = await fresh_manager.rollback_transaction(txn_id)
    assert result["status"] == "rolled_back"
    assert len(result["rollback_errors"]) == 1
    assert "cannot restore deleted node" in result["rollback_errors"][0]["error"]


@pytest.mark.asyncio
async def test_e2e_failed_create_returns_failed_status(fresh_manager, fake_bridge):
    fake_bridge.fail_create_node = True
    rec = await houdini_runtime.execute_operation({
        "op": "create_node", "parent": "/obj", "type": "geo", "name": "willFail",
    })
    assert rec["status"] == "failed"
    assert "RuntimeError" in rec["error"]


@pytest.mark.asyncio
async def test_validate_operation_catches_bad_shape():
    err = houdini_runtime._validate_operation({"op": "create_node"})  # missing parent
    assert err and "parent" in err

    err = houdini_runtime._validate_operation({"op": "unknown"})
    assert err and "unsupported" in err

    err = houdini_runtime._validate_operation({"op": "set_parms", "node": "/obj/a", "parms": "not a dict"})
    assert err and "parms" in err

    # Well-formed → None
    assert houdini_runtime._validate_operation({"op": "cook_node", "path": "/obj/a"}) is None
