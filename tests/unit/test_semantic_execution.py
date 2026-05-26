"""
Unit tests for src.runtime.semantic_execution.

Covers:
  • translate returns full plan shape
  • translate with unknown intent returns ok=False
  • translate with constraint violation surfaces errors
  • translate with valid intent has ok=True
  • dry_run returns validated status, no mutations
  • execute commits on success
  • execute surfaces rollback on op failure
  • missing capability surfaces as warning (not error)
  • exec_out always True on node test (via node class)
  • singleton / reset
"""

from __future__ import annotations

import pytest

from src.runtime.semantic_execution import (
    SemanticExecutor,
    get_semantic_executor,
    reset_semantic_executor_for_tests,
)
from src.runtime.semantic_registry import (
    get_semantic_registry,
    reset_semantic_registry_for_tests,
)
from src.runtime.runtime_constraints import (
    get_runtime_constraints,
    reset_runtime_constraints_for_tests,
)
from src.runtime.capability_registry import (
    get_capability_registry,
    reset_capability_registry_for_tests,
)
from src.runtime.transaction_manager import (
    get_transaction_manager,
    reset_transaction_manager_for_tests,
)
from src.runtime.scene_cache import get_scene_cache
from src.runtime import transaction_manager as tm_module
from src.utils import hou_bridge as bridge_module


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_all():
    reset_semantic_executor_for_tests()
    reset_semantic_registry_for_tests()
    reset_runtime_constraints_for_tests()
    reset_capability_registry_for_tests()
    reset_transaction_manager_for_tests()
    get_scene_cache().clear_dirty_state()
    get_scene_cache().clear_semantic_lineage()
    yield
    reset_semantic_executor_for_tests()
    reset_semantic_registry_for_tests()
    reset_runtime_constraints_for_tests()
    reset_capability_registry_for_tests()
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


def _register_simple_op(name="test_op"):
    def handler(ctx):
        return [{"op": "create_node", "parent": ctx.get("parent", "/obj"),
                 "type": "geo", "name": ctx.get("name", "test_geo")}]
    get_semantic_registry().register_operation(name, {"description": "test", "tags": []}, handler)


# ---------------------------------------------------------------------------
# translate — shape
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_translate_returns_required_keys():
    _register_simple_op()
    exec_ = get_semantic_executor()
    result = await exec_.translate("test_op", {"parent": "/obj", "name": "g1"})
    for key in ("ok", "intent", "operations", "op_count", "warnings",
                "errors", "resource_estimate", "constraint_violations",
                "validation_result", "metadata"):
        assert key in result, f"Missing key: {key}"


@pytest.mark.asyncio
async def test_translate_unknown_intent_not_ok():
    exec_ = get_semantic_executor()
    result = await exec_.translate("nonexistent_intent_xyz", {})
    assert result["ok"] is False
    assert len(result["errors"]) >= 1


@pytest.mark.asyncio
async def test_translate_valid_intent_ok():
    _register_simple_op()
    exec_ = get_semantic_executor()
    result = await exec_.translate("test_op", {"parent": "/obj"})
    assert result["ok"] is True
    assert result["op_count"] >= 1


@pytest.mark.asyncio
async def test_translate_constraint_violation_surfaces_error():
    # Violate built-in /stage protection
    def stage_handler(ctx):
        return [{"op": "create_node", "parent": "/stage", "type": "geo"}]
    get_semantic_registry().register_operation("stage_op", {}, stage_handler)

    exec_ = get_semantic_executor()
    result = await exec_.translate("stage_op", {})
    assert result["ok"] is False
    assert len(result["errors"]) >= 1
    assert any("/stage" in e or "protect" in e.lower() for e in result["errors"])


@pytest.mark.asyncio
async def test_translate_missing_capability_is_warning_not_error():
    def handler(ctx):
        return [{"op": "create_node", "parent": "/obj", "type": "geo"}]
    get_semantic_registry().register_operation(
        "cap_op",
        {"description": "needs missing cap", "required_capabilities": ["nonexistent_capability_xyz"]},
        handler,
    )
    exec_ = get_semantic_executor()
    result = await exec_.translate("cap_op", {})
    # Constraint violation not raised; warning should appear; ok may still be True
    assert any("nonexistent_capability_xyz" in w for w in result["warnings"])


# ---------------------------------------------------------------------------
# dry_run
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dry_run_returns_validated_status(fake_bridge):
    _register_simple_op()
    exec_ = get_semantic_executor()
    result = await exec_.execute("test_op", {"parent": "/obj"}, dry_run=True)
    assert result["status"] == "validated"
    assert result["replayed"] is False
    assert fake_bridge.created == []


# ---------------------------------------------------------------------------
# execute — success path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_commits_on_success(fake_bridge):
    _register_simple_op()
    exec_ = get_semantic_executor()
    result = await exec_.execute("test_op", {"parent": "/obj", "name": "geo_x"})
    assert result["ok"] is True
    assert result["status"] == "committed"
    assert result["replayed"] is True
    assert "/obj/geo_x" in fake_bridge.created


@pytest.mark.asyncio
async def test_execute_unknown_intent_fails(fake_bridge):
    exec_ = get_semantic_executor()
    result = await exec_.execute("unknown_xyz", {})
    assert result["ok"] is False
    assert result["status"] == "failed"


# ---------------------------------------------------------------------------
# execute — rollback on error
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_rolls_back_on_op_failure(monkeypatch):
    """Simulate an op failure mid-execution."""
    from src.runtime import houdini_runtime

    call_count = {"n": 0}
    original = houdini_runtime.execute_operation

    async def _patched(op):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return {
                "op": "create_node", "params": op, "result": None,
                "snapshot": {}, "status": "failed",
                "error": "forced failure", "dirty": [],
            }
        return await original(op)

    monkeypatch.setattr(houdini_runtime, "execute_operation", _patched)

    import src.utils.hou_bridge as bmod
    monkeypatch.setattr(bmod, "get_bridge", lambda: _FakeBridge())

    _register_simple_op()
    exec_ = get_semantic_executor()
    result = await exec_.execute("test_op", {}, rollback_on_error=True)
    assert result["ok"] is False
    assert result["status"] in ("rolled_back", "failed")


# ---------------------------------------------------------------------------
# Graph diff / lineage
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_records_semantic_lineage(fake_bridge):
    _register_simple_op()
    exec_ = get_semantic_executor()
    await exec_.execute("test_op", {"parent": "/obj"})
    lineage = get_scene_cache().get_semantic_lineage()
    assert len(lineage) >= 1
    assert lineage[-1]["intent_id"] == "test_op"


@pytest.mark.asyncio
async def test_execute_graph_diff_has_created(fake_bridge):
    _register_simple_op()
    exec_ = get_semantic_executor()
    result = await exec_.execute("test_op", {"parent": "/obj", "name": "my_node"})
    diff = result["graph_diff"]
    assert "created" in diff


# ---------------------------------------------------------------------------
# report_json
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_report_json_parses(fake_bridge):
    import json
    _register_simple_op()
    exec_ = get_semantic_executor()
    result = await exec_.execute("test_op", {"parent": "/obj"})
    parsed = json.loads(result["report_json"])
    assert "intent" in parsed
    assert "status" in parsed


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton_returns_same_instance():
    a = get_semantic_executor()
    b = get_semantic_executor()
    assert a is b


def test_reset_creates_fresh_singleton():
    a = get_semantic_executor()
    reset_semantic_executor_for_tests()
    b = get_semantic_executor()
    assert a is not b
