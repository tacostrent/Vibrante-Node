"""
Unit tests for the dirty-scene-tracking layer + the hou_mcp_graph_diff node.

The diff node has no live bridge dependency — it reads scene_cache state. We
exercise it by:
  • driving the SceneCache mark_* API directly to populate dirty state
  • running houdini_runtime executors against a FakeBridge to verify they
    correctly populate the same dirty state
  • running the node's class via the registry to confirm the JSON wiring
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.core.registry import NodeRegistry
from src.runtime import houdini_runtime, scene_cache
from src.utils import hou_bridge as bridge_module


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clean_cache():
    cache = scene_cache.get_scene_cache()
    cache.clear_dirty_state()
    cache.invalidate()
    yield
    cache.clear_dirty_state()
    cache.invalidate()


@pytest.fixture(scope="module", autouse=True)
def _ensure_registry():
    repo = Path(__file__).parent.parent.parent
    NodeRegistry.load_all(str(repo / "nodes"))
    NodeRegistry._load_directory(str(repo / "plugins" / "houdini" / "v_nodes_houdini"))


class FakeBridge:
    def __init__(self):
        self.created: list[str] = []
        self.parms: dict[str, dict] = {}

    def create_node(self, parent, node_type, name=""):
        full = f"{parent.rstrip('/')}/{name or node_type}"
        self.created.append(full)
        return {"path": full, "name": name or node_type, "type": node_type}

    def get_parm(self, node, parm):
        return {"value": self.parms.get(node, {}).get(parm, 0)}

    def set_parm(self, node, parm, value):
        self.parms.setdefault(node, {})[parm] = value
        return {"set": True}

    def set_parms(self, node, parms):
        self.parms.setdefault(node, {}).update(parms)
        return {"set": True, "count": len(parms)}

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
        if "isDisplayFlagSet" in code or "isRenderFlagSet" in code:
            return {"result": True}
        if "_n.inputs()" in code:
            return {"result": None}
        return {"result": None}


@pytest.fixture
def fake_bridge(monkeypatch):
    fake = FakeBridge()
    monkeypatch.setattr(bridge_module, "get_bridge", lambda: fake)
    return fake


# ---------------------------------------------------------------------------
# SceneCache dirty tracking primitives
# ---------------------------------------------------------------------------

def test_dirty_state_starts_empty():
    cache = scene_cache.SceneCache()
    d = cache.get_dirty_nodes()
    assert d == {
        "modified": [], "created": [], "deleted": [], "cooked": [],
        "connections_changed": [], "flags_changed": [],
    }


def test_mark_methods_categorise_correctly():
    cache = scene_cache.SceneCache()
    cache.mark_node_dirty("/obj/a")
    cache.mark_node_created("/obj/b")
    cache.mark_node_deleted("/obj/c")
    cache.mark_node_cooked("/obj/d")
    cache.mark_connection_changed("/obj/a", "/obj/b", 0)
    cache.mark_flag_changed("/obj/e")
    d = cache.get_dirty_nodes()
    assert d["modified"] == ["/obj/a"]
    assert d["created"] == ["/obj/b"]
    assert d["deleted"] == ["/obj/c"]
    assert d["cooked"] == ["/obj/d"]
    assert d["connections_changed"] == [{"from": "/obj/a", "to": "/obj/b", "in": 0}]
    assert d["flags_changed"] == ["/obj/e"]


def test_delete_clears_other_categories():
    """Deleting a node supersedes any prior dirty marks on the same path."""
    cache = scene_cache.SceneCache()
    cache.mark_node_dirty("/obj/x")
    cache.mark_node_cooked("/obj/x")
    cache.mark_node_created("/obj/x")
    cache.mark_node_deleted("/obj/x")
    d = cache.get_dirty_nodes()
    assert d["deleted"] == ["/obj/x"]
    assert "/obj/x" not in d["modified"]
    assert "/obj/x" not in d["cooked"]
    assert "/obj/x" not in d["created"]


def test_create_after_delete_clears_deleted_flag():
    cache = scene_cache.SceneCache()
    cache.mark_node_deleted("/obj/y")
    cache.mark_node_created("/obj/y")
    d = cache.get_dirty_nodes()
    assert d["created"] == ["/obj/y"]
    assert "/obj/y" not in d["deleted"]


def test_mark_ignores_empty_paths():
    cache = scene_cache.SceneCache()
    cache.mark_node_dirty("")
    cache.mark_node_created(None)  # type: ignore[arg-type]
    cache.mark_connection_changed("", "/obj/a", 0)
    d = cache.get_dirty_nodes()
    assert all(len(v) == 0 for v in d.values())


def test_clear_dirty_state_drains_all_categories():
    cache = scene_cache.SceneCache()
    cache.mark_node_dirty("/obj/a")
    cache.mark_node_created("/obj/b")
    cache.clear_dirty_state()
    d = cache.get_dirty_nodes()
    assert all(len(v) == 0 for v in d.values())


def test_dirty_output_is_sorted():
    """JSON output ordering must be deterministic for LLM prompts."""
    cache = scene_cache.SceneCache()
    for path in ("/obj/z", "/obj/a", "/obj/m"):
        cache.mark_node_dirty(path)
    d = cache.get_dirty_nodes()
    assert d["modified"] == ["/obj/a", "/obj/m", "/obj/z"]


def test_stats_includes_dirty_counts():
    cache = scene_cache.SceneCache()
    cache.mark_node_created("/obj/a")
    cache.mark_node_dirty("/obj/b")
    stats = cache.stats()
    assert stats["dirty"]["created"] == 1
    assert stats["dirty"]["modified"] == 1


# ---------------------------------------------------------------------------
# houdini_runtime executors populate dirty state correctly
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_create_node_marks_created(fake_bridge):
    await houdini_runtime.execute_operation({
        "op": "create_node", "parent": "/obj", "type": "geo", "name": "ball",
    })
    d = scene_cache.get_scene_cache().get_dirty_nodes()
    assert d["created"] == ["/obj/ball"]


@pytest.mark.asyncio
async def test_execute_set_parms_marks_modified(fake_bridge):
    await houdini_runtime.execute_operation({
        "op": "set_parms", "node": "/obj/box", "parms": {"sizex": 5.0},
    })
    d = scene_cache.get_scene_cache().get_dirty_nodes()
    assert d["modified"] == ["/obj/box"]


@pytest.mark.asyncio
async def test_execute_connect_marks_connection_changed(fake_bridge):
    await houdini_runtime.execute_operation({
        "op": "connect_nodes", "from": "/obj/a", "to": "/obj/b", "out": 0, "in": 0,
    })
    d = scene_cache.get_scene_cache().get_dirty_nodes()
    assert d["connections_changed"] == [{"from": "/obj/a", "to": "/obj/b", "in": 0}]


@pytest.mark.asyncio
async def test_execute_delete_marks_deleted(fake_bridge):
    await houdini_runtime.execute_operation({
        "op": "delete_node", "path": "/obj/old",
    })
    d = scene_cache.get_scene_cache().get_dirty_nodes()
    assert d["deleted"] == ["/obj/old"]


@pytest.mark.asyncio
async def test_execute_cook_marks_cooked(fake_bridge):
    await houdini_runtime.execute_operation({
        "op": "cook_node", "path": "/obj/geo1", "force": False,
    })
    d = scene_cache.get_scene_cache().get_dirty_nodes()
    assert d["cooked"] == ["/obj/geo1"]


@pytest.mark.asyncio
async def test_execute_set_display_flag_marks_flags_changed(fake_bridge):
    await houdini_runtime.execute_operation({
        "op": "set_display_flag", "path": "/obj/geo1/box", "on": True,
    })
    d = scene_cache.get_scene_cache().get_dirty_nodes()
    assert d["flags_changed"] == ["/obj/geo1/box"]


# ---------------------------------------------------------------------------
# hou_mcp_graph_diff node (via the registry)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_graph_diff_node_returns_structured_payload():
    cache = scene_cache.get_scene_cache()
    cache.mark_node_created("/obj/n1")
    cache.mark_node_dirty("/obj/n2")
    cache.mark_node_cooked("/obj/n3")
    cache.mark_connection_changed("/obj/n1", "/obj/n2", 0)
    cache.mark_flag_changed("/obj/n3")

    cls = NodeRegistry.get_class("hou_mcp_graph_diff")
    node = cls()
    result = await node.execute({"clear_after_read": False})

    assert result["created"] == ["/obj/n1"]
    assert result["modified"] == ["/obj/n2"]
    assert result["cooked"] == ["/obj/n3"]
    assert result["connections_changed"] == [{"from": "/obj/n1", "to": "/obj/n2", "in": 0}]
    assert result["flags_changed"] == ["/obj/n3"]
    assert result["total_changes"] == 5
    # JSON output is round-trip-safe
    assert json.loads(result["diff_json"])["created"] == ["/obj/n1"]


@pytest.mark.asyncio
async def test_graph_diff_node_clear_after_read_drains_state():
    cache = scene_cache.get_scene_cache()
    cache.mark_node_created("/obj/x")

    cls = NodeRegistry.get_class("hou_mcp_graph_diff")
    node = cls()
    first = await node.execute({"clear_after_read": True})
    second = await node.execute({"clear_after_read": True})

    assert first["created"] == ["/obj/x"]
    assert second["created"] == []
    assert second["total_changes"] == 0


@pytest.mark.asyncio
async def test_graph_diff_node_does_not_clear_when_disabled():
    cache = scene_cache.get_scene_cache()
    cache.mark_node_created("/obj/persistent")

    cls = NodeRegistry.get_class("hou_mcp_graph_diff")
    node = cls()
    first = await node.execute({"clear_after_read": False})
    second = await node.execute({"clear_after_read": False})

    assert first["created"] == ["/obj/persistent"]
    assert second["created"] == ["/obj/persistent"]


@pytest.mark.asyncio
async def test_graph_diff_includes_exec_out():
    cls = NodeRegistry.get_class("hou_mcp_graph_diff")
    node = cls()
    result = await node.execute({"clear_after_read": True})
    assert result.get("exec_out") is True
