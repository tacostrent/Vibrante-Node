"""
Unit tests for src.runtime.houdini_runtime.

Mocks the hou_bridge module so neither Houdini nor an actual bridge connection
is required. Verifies the scene_context shape contract and the build_node_chain
validation + execution order.
"""

from __future__ import annotations

import pytest

from src.runtime import houdini_runtime, scene_cache
from src.utils import hou_bridge as bridge_module


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class FakeBridge:
    def __init__(self):
        self.calls: list[tuple[str, tuple, dict]] = []
        self.scene = {
            "hip_file": "/tmp/test.hip",
            "hip_name": "test.hip",
            "houdini_version": "20.0.500",
            "fps": 24,
            "frame": 1,
            "frame_range": [1, 240],
        }
        self.selection_paths: list[str] = []
        self.network_summaries: dict[str, list[dict]] = {
            "/obj": [{"name": "geo1", "type": "geo", "path": "/obj/geo1", "category": "Object"}],
            "/mat": [],
            "/out": [],
        }
        self.existing_nodes: set[str] = {"/obj", "/obj/geo1", "/mat", "/out"}
        self.created_nodes: list[tuple[str, str, str]] = []
        self.connected: list[tuple[str, str, int, int]] = []
        self.set_parm_calls: list[tuple[str, dict]] = []
        self.set_keyframe_calls: list[tuple[str, str, float, object]] = []
        self.cooked: list[str] = []
        self.layout_calls: list[str] = []
        self.run_code_result = {"result": {"files": [], "defs": []}}
        self.fail_create_node = False
        self.fail_connect_nodes = False
        self.fail_set_parms = False

    def scene_info(self):
        self.calls.append(("scene_info", (), {}))
        return dict(self.scene)

    def get_selection(self):
        self.calls.append(("get_selection", (), {}))
        return list(self.selection_paths)

    def network_summary(self, path):
        self.calls.append(("network_summary", (path,), {}))
        return list(self.network_summaries.get(path, []))

    def children(self, path):
        self.calls.append(("children", (path,), {}))
        return list(self.network_summaries.get(path, []))

    def node_exists(self, path):
        self.calls.append(("node_exists", (path,), {}))
        return {"exists": path in self.existing_nodes}

    def node_info(self, path):
        self.calls.append(("node_info", (path,), {}))
        return {"path": path, "type": "null", "category": "Sop"}

    def create_node(self, parent, node_type, name=""):
        self.calls.append(("create_node", (parent, node_type, name), {}))
        if self.fail_create_node:
            raise RuntimeError("create_node forced failure")
        full = f"{parent.rstrip('/')}/{name or node_type}"
        self.created_nodes.append((parent, node_type, full))
        self.existing_nodes.add(full)
        return {"path": full, "name": name or node_type, "type": node_type}

    def set_parms(self, node, parms):
        self.calls.append(("set_parms", (node, parms), {}))
        if self.fail_set_parms:
            raise RuntimeError("set_parms forced failure")
        self.set_parm_calls.append((node, dict(parms)))
        return {"set": True, "count": len(parms)}

    def set_parm(self, node, parm, value):
        self.calls.append(("set_parm", (node, parm, value), {}))
        self.set_parm_calls.append((node, {parm: value}))
        return {"set": True}

    def get_parm(self, node, parm):
        self.calls.append(("get_parm", (node, parm), {}))
        return {"value": 0}

    def set_keyframe(self, node, parm, frame, value):
        self.calls.append(("set_keyframe", (node, parm, frame, value), {}))
        self.set_keyframe_calls.append((node, parm, frame, value))
        return {"set": True}

    def connect_nodes(self, from_node, to_node, output=0, input_idx=0):
        self.calls.append(("connect_nodes", (from_node, to_node, output, input_idx), {}))
        if self.fail_connect_nodes:
            raise RuntimeError("connect_nodes forced failure")
        self.connected.append((from_node, to_node, output, input_idx))
        return {"connected": True}

    def layout_children(self, path):
        self.calls.append(("layout_children", (path,), {}))
        self.layout_calls.append(path)
        return {"done": True}

    def cook_node(self, path, force=False):
        self.calls.append(("cook_node", (path, force), {}))
        self.cooked.append(path)
        return {"cooked": True}

    def run_code(self, code):
        self.calls.append(("run_code", (code,), {}))
        return dict(self.run_code_result)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_bridge(monkeypatch):
    fake = FakeBridge()
    monkeypatch.setattr(bridge_module, "get_bridge", lambda: fake)
    # Reset cache to keep tests independent
    scene_cache.get_scene_cache().invalidate()
    return fake


# ---------------------------------------------------------------------------
# scene_context tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scene_context_has_stable_shape(fake_bridge):
    ctx = await houdini_runtime.scene_context()

    assert set(ctx.keys()) == {"scene", "selection", "networks", "assets", "render"}
    assert ctx["scene"]["hip_file"] == "/tmp/test.hip"
    assert ctx["scene"]["frame_range"] == [1, 240]
    assert isinstance(ctx["selection"], list)
    assert "obj" in ctx["networks"]
    assert "mat" in ctx["networks"]
    assert "out" in ctx["networks"]
    assert set(ctx["assets"].keys()) == {"hda_files", "definitions"}
    assert "render_nodes" in ctx["render"]


@pytest.mark.asyncio
async def test_scene_context_skips_sections_when_excluded(fake_bridge):
    ctx = await houdini_runtime.scene_context(
        include_selection=False, include_assets=False, include_render=False,
    )

    assert ctx["selection"] == []
    assert ctx["assets"] == {"hda_files": [], "definitions": []}
    assert ctx["render"] == {"render_nodes": []}

    method_calls = [name for name, _, _ in fake_bridge.calls]
    assert "get_selection" not in method_calls
    assert "run_code" not in method_calls  # assets fetch skipped


@pytest.mark.asyncio
async def test_scene_context_cache_dedupes_repeated_calls(fake_bridge):
    await houdini_runtime.scene_context()
    first_call_count = len(fake_bridge.calls)
    await houdini_runtime.scene_context()
    # Second call hits the cache entirely
    assert len(fake_bridge.calls) == first_call_count


@pytest.mark.asyncio
async def test_scene_context_force_refresh_bypasses_cache(fake_bridge):
    await houdini_runtime.scene_context()
    first_call_count = len(fake_bridge.calls)
    await houdini_runtime.scene_context(force_refresh=True)
    assert len(fake_bridge.calls) > first_call_count


@pytest.mark.asyncio
async def test_scene_context_classifies_render_nodes(fake_bridge):
    fake_bridge.network_summaries["/out"] = [
        {"name": "karma1", "type": "karma", "path": "/out/karma1", "category": "Driver"},
        {"name": "geomerge1", "type": "geometry", "path": "/out/geomerge1", "category": "Driver"},
    ]
    ctx = await houdini_runtime.scene_context()
    render = ctx["render"]["render_nodes"]
    assert {n["path"] for n in render} == {"/out/karma1"}


@pytest.mark.asyncio
async def test_scene_context_returns_selection_with_metadata(fake_bridge):
    fake_bridge.selection_paths = ["/obj/geo1"]
    ctx = await houdini_runtime.scene_context()
    assert ctx["selection"] == [{"path": "/obj/geo1", "type": "null", "category": "Sop"}]


@pytest.mark.asyncio
async def test_scene_context_handles_missing_optional_networks(fake_bridge):
    # No /stage configured — should NOT appear in output
    ctx = await houdini_runtime.scene_context()
    assert "stage" not in ctx["networks"]
    assert "tasks" not in ctx["networks"]


@pytest.mark.asyncio
async def test_scene_context_includes_optional_network_when_present(fake_bridge):
    fake_bridge.existing_nodes.add("/stage")
    fake_bridge.network_summaries["/stage"] = [
        {"name": "lop1", "type": "configurestage", "path": "/stage/lop1", "category": "Lop"},
    ]
    ctx = await houdini_runtime.scene_context()
    assert "stage" in ctx["networks"]
    assert ctx["networks"]["stage"][0]["path"] == "/stage/lop1"


# ---------------------------------------------------------------------------
# build_node_chain tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_build_node_chain_rejects_empty_spec(fake_bridge):
    result = await houdini_runtime.build_node_chain({"nodes": []})
    assert result["ok"] is False
    assert "at least one node" in result["error"]
    assert fake_bridge.created_nodes == []


@pytest.mark.asyncio
async def test_build_node_chain_rejects_unknown_parent(fake_bridge):
    spec = {
        "nodes": [{"id": "n1", "parent": "/does/not/exist", "type": "sphere", "name": "src"}],
    }
    result = await houdini_runtime.build_node_chain(spec)
    assert result["ok"] is False
    assert "parent node does not exist" in result["error"]
    assert fake_bridge.created_nodes == []


@pytest.mark.asyncio
async def test_build_node_chain_rejects_duplicate_ids(fake_bridge):
    spec = {
        "nodes": [
            {"id": "n1", "parent": "/obj/geo1", "type": "sphere"},
            {"id": "n1", "parent": "/obj/geo1", "type": "mountain"},
        ],
    }
    result = await houdini_runtime.build_node_chain(spec)
    assert result["ok"] is False
    assert "duplicate node id" in result["error"]


@pytest.mark.asyncio
async def test_build_node_chain_rejects_connection_to_unknown_id(fake_bridge):
    spec = {
        "nodes": [{"id": "n1", "parent": "/obj/geo1", "type": "sphere"}],
        "connections": [{"from": "n1", "to": "missing"}],
    }
    result = await houdini_runtime.build_node_chain(spec)
    assert result["ok"] is False
    assert "unknown node id 'missing'" in result["error"]


@pytest.mark.asyncio
async def test_build_node_chain_creates_and_connects(fake_bridge):
    spec = {
        "intent": "test_chain",
        "nodes": [
            {"id": "src", "parent": "/obj/geo1", "type": "sphere", "name": "ball", "params": {"radx": 2.0}},
            {"id": "mid", "parent": "/obj/geo1", "type": "mountain", "name": "noise"},
            {"id": "snk", "parent": "/obj/geo1", "type": "null", "name": "OUT"},
        ],
        "connections": [
            {"from": "src", "to": "mid", "out": 0, "in": 0},
            {"from": "mid", "to": "snk", "out": 0, "in": 0},
        ],
        "layout": True,
        "cook": True,
    }
    result = await houdini_runtime.build_node_chain(spec)

    assert result["ok"] is True
    assert result["intent"] == "test_chain"
    assert len(result["created_paths"]) == 3
    assert set(result["id_to_path"].keys()) == {"src", "mid", "snk"}

    # set_parms should have run for the sphere only
    assert fake_bridge.set_parm_calls == [("/obj/geo1/ball", {"radx": 2.0})]
    # Two connections wired
    assert len(fake_bridge.connected) == 2
    # Layout ran exactly once for the single parent involved
    assert fake_bridge.layout_calls == ["/obj/geo1"]
    # Cook ran for the last created node
    assert fake_bridge.cooked == ["/obj/geo1/OUT"]


@pytest.mark.asyncio
async def test_build_node_chain_failure_reports_partial_paths(fake_bridge):
    fake_bridge.fail_connect_nodes = True
    spec = {
        "nodes": [
            {"id": "n1", "parent": "/obj/geo1", "type": "sphere", "name": "ball"},
            {"id": "n2", "parent": "/obj/geo1", "type": "null", "name": "OUT"},
        ],
        "connections": [{"from": "n1", "to": "n2"}],
    }
    result = await houdini_runtime.build_node_chain(spec)

    assert result["ok"] is False
    assert "connect_nodes failed" in result["error"]
    assert result["created_paths"] == ["/obj/geo1/ball", "/obj/geo1/OUT"]
    assert "n1" in result["id_to_path"]
    assert "n2" in result["id_to_path"]


@pytest.mark.asyncio
async def test_build_node_chain_invalidates_scene_cache(fake_bridge):
    # Warm cache
    await houdini_runtime.scene_context()
    cache = scene_cache.get_scene_cache()
    assert cache.get("scene_context::scene") is not None

    await houdini_runtime.build_node_chain({
        "nodes": [{"id": "n1", "parent": "/obj/geo1", "type": "sphere", "name": "ball"}],
    })

    # Cache for scene_context must be invalidated after a mutation
    assert cache.get("scene_context::scene") is None


# ---------------------------------------------------------------------------
# scene_cache integration
# ---------------------------------------------------------------------------

def test_scene_cache_ttl_expiry(monkeypatch):
    # Drive a virtual clock so the test is deterministic and never touches real time
    clock = {"now": 1000.0}
    monkeypatch.setattr(scene_cache.time, "monotonic", lambda: clock["now"])
    cache = scene_cache.SceneCache()
    cache.set("k", "v", ttl_sec=0.1)
    assert cache.get("k") == "v"
    clock["now"] += 1.0  # advance well past the TTL
    assert cache.get("k") is None


def test_scene_cache_invalidate_prefix():
    cache = scene_cache.SceneCache()
    cache.set("a::1", 1)
    cache.set("a::2", 2)
    cache.set("b::1", 3)
    cache.invalidate("a::")
    assert cache.get("a::1") is None
    assert cache.get("a::2") is None
    assert cache.get("b::1") == 3


@pytest.mark.asyncio
async def test_execute_operation_set_keyframe(fake_bridge):
    result = await houdini_runtime.execute_operation({
        "op": "set_keyframe",
        "node": "/obj/cam1",
        "parm": "tx",
        "frame": 48,
        "value": 6.0,
    })

    assert result["status"] == "ok"
    assert fake_bridge.set_keyframe_calls == [("/obj/cam1", "tx", 48.0, 6.0)]
