"""
Unit tests for src.runtime.multi_dcc_runtime.

Covers:
  • built-in houdini DCC registered at init
  • register_dcc / deregister_dcc
  • register_dcc empty name raises
  • get_dcc / list_dccs
  • route_operation: by op type in capabilities
  • route_operation: fallback to houdini for standard Houdini ops
  • route_operation: unknown op returns houdini (fallback)
  • route_operation: hint_dcc overrides routing
  • route_operations partitions list correctly
  • execute_for_dcc: unknown dcc returns error dict
  • execute_for_dcc: adapter exception caught and returned
  • execute_cross_dcc: delegates to route_operations + execute_for_dcc
  • stats shape
  • singleton / reset
"""

from __future__ import annotations

import pytest

from src.runtime.multi_dcc_runtime import (
    MultiDccRuntime,
    DccAdapter,
    get_multi_dcc_runtime,
    reset_multi_dcc_runtime_for_tests,
)
from src.runtime.distributed_runtime import reset_distributed_runtime_for_tests
from src.runtime.capability_registry  import reset_capability_registry_for_tests
from src.runtime.runtime_constraints  import reset_runtime_constraints_for_tests
from src.runtime.validation_engine    import reset_validation_engine_for_tests
from src.runtime.dependency_graph     import reset_dependency_graph_for_tests


@pytest.fixture(autouse=True)
def _reset():
    reset_multi_dcc_runtime_for_tests()
    reset_distributed_runtime_for_tests()
    reset_capability_registry_for_tests()
    reset_runtime_constraints_for_tests()
    reset_validation_engine_for_tests()
    reset_dependency_graph_for_tests()
    yield
    reset_multi_dcc_runtime_for_tests()
    reset_distributed_runtime_for_tests()


# ---------------------------------------------------------------------------
# Built-in registration
# ---------------------------------------------------------------------------

def test_houdini_registered_at_init():
    mdr  = get_multi_dcc_runtime()
    dccs = {d["id"] for d in mdr.list_dccs()}
    assert "houdini" in dccs


def test_list_dccs_shape():
    mdr = get_multi_dcc_runtime()
    for d in mdr.list_dccs():
        assert "id"           in d
        assert "name"         in d
        assert "capabilities" in d


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class MockAdapter(DccAdapter):
    def __init__(self, dcc_type="custom"):
        super().__init__(dcc_type)
        self._available = True

    @property
    def is_available(self):
        return self._available

    async def execute_operations(self, ops, dry_run=False):
        return {"ok": True, "status": "mock_ok", "operations_executed": len(ops), "errors": [], "graph_diff": {}}


def test_register_dcc_returns_name():
    mdr = get_multi_dcc_runtime()
    dcc_id = mdr.register_dcc("maya", MockAdapter("maya"), ["animation", "rigging"])
    assert dcc_id == "maya"


def test_register_dcc_empty_name_raises():
    mdr = get_multi_dcc_runtime()
    with pytest.raises(ValueError):
        mdr.register_dcc("", MockAdapter(), [])


def test_deregister_dcc_true():
    mdr = get_multi_dcc_runtime()
    mdr.register_dcc("maya", MockAdapter("maya"), [])
    assert mdr.deregister_dcc("maya") is True
    assert mdr.get_dcc("maya") is None


def test_deregister_dcc_unknown_false():
    mdr = get_multi_dcc_runtime()
    assert mdr.deregister_dcc("nuke_unknown") is False


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------

def test_route_houdini_op_defaults_to_houdini():
    mdr   = get_multi_dcc_runtime()
    target = mdr.route_operation({"op": "create_node", "parent": "/obj", "type": "geo"})
    assert target == "houdini"


def test_route_hint_dcc_overrides():
    mdr = get_multi_dcc_runtime()
    mdr.register_dcc("maya", MockAdapter(), ["animation"])
    target = mdr.route_operation({"op": "create_node"}, hint_dcc="maya")
    assert target == "maya"


def test_route_by_capability():
    mdr = get_multi_dcc_runtime()
    mdr.register_dcc("deadline", MockAdapter(), ["farm_submit"])
    target = mdr.route_operation({"op": "farm_submit"})
    assert target == "deadline"


def test_route_operations_partitions():
    mdr = get_multi_dcc_runtime()
    mdr.register_dcc("maya", MockAdapter("maya"), ["animation"])
    ops = [
        {"op": "create_node", "parent": "/obj", "type": "geo"},
        {"op": "animation"},
        {"op": "create_node", "parent": "/obj", "type": "null"},
    ]
    by_dcc = mdr.route_operations(ops, hint_dcc=None)
    # animation op should go to maya
    assert "maya" in by_dcc
    assert len(by_dcc["maya"]) == 1
    # the two houdini ops should go to houdini
    assert len(by_dcc.get("houdini", [])) == 2


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_for_unknown_dcc():
    mdr    = get_multi_dcc_runtime()
    result = await mdr.execute_for_dcc("nuke", [])
    assert result["ok"] is False
    assert "nuke" in result["error"]


@pytest.mark.asyncio
async def test_execute_for_mock_dcc():
    mdr = get_multi_dcc_runtime()
    mdr.register_dcc("maya", MockAdapter("maya"), [])
    result = await mdr.execute_for_dcc("maya", [{"op": "animation"}])
    assert result["ok"] is True
    assert result["status"] == "mock_ok"


@pytest.mark.asyncio
async def test_execute_cross_dcc():
    mdr = get_multi_dcc_runtime()
    mdr.register_dcc("maya", MockAdapter("maya"), ["animation"])
    ops = [{"op": "animation"}, {"op": "create_node", "parent": "/obj", "type": "geo"}]
    # Patch houdini adapter to avoid live bridge
    mdr.register_dcc("houdini", MockAdapter("houdini"),
                     ["create_node", "set_parms", "connect_nodes", "delete_node",
                      "cook_node", "layout_children", "build_node_chain",
                      "set_display_flag", "set_render_flag", "karma", "mantra"])
    result = await mdr.execute_cross_dcc(ops)
    assert isinstance(result["ok"], bool)
    assert "by_dcc" in result


@pytest.mark.asyncio
async def test_execute_adapter_exception_caught():
    class BrokenAdapter(DccAdapter):
        async def execute_operations(self, ops, dry_run=False):
            raise RuntimeError("bridge down")

    mdr = get_multi_dcc_runtime()
    mdr.register_dcc("broken", BrokenAdapter("custom"), [])
    result = await mdr.execute_for_dcc("broken", [{"op": "create_node"}])
    assert result["ok"] is False
    assert "bridge down" in result.get("error", "")


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def test_stats_shape():
    mdr = get_multi_dcc_runtime()
    s = mdr.stats()
    assert "total_dccs" in s
    assert "dcc_names"  in s
    assert s["total_dccs"] >= 1


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton_same_instance():
    a = get_multi_dcc_runtime()
    b = get_multi_dcc_runtime()
    assert a is b


def test_reset_creates_fresh_instance():
    a = get_multi_dcc_runtime()
    reset_multi_dcc_runtime_for_tests()
    b = get_multi_dcc_runtime()
    assert a is not b
