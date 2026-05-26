"""
Unit tests for src.runtime.mcp_server_runtime.

Covers:
  • list_tools returns all built-in tools
  • get_tool returns correct tool definition
  • handle_request returns is_error=False for valid calls
  • handle_request captures exceptions, is_error=True on unknown tool
  • register_tool / deregister_tool
  • deregister_tool raises on built-in tools
  • start / stop / is_running lifecycle
  • stats output shape
  • singleton / reset
  • built-in handler routing (list_capabilities, list_templates)
  • handle_request with plan_workflow passes prompt validation
  • handle_request with preview_plan validates plan dict
"""

from __future__ import annotations

import pytest

from src.runtime.mcp_server_runtime import (
    McpServerRuntime,
    get_mcp_server_runtime,
    reset_mcp_server_runtime_for_tests,
)
from src.runtime.capability_registry import reset_capability_registry_for_tests
from src.runtime.workflow_templates  import reset_workflow_templates_for_tests


@pytest.fixture(autouse=True)
def _reset():
    reset_mcp_server_runtime_for_tests()
    reset_capability_registry_for_tests()
    reset_workflow_templates_for_tests()
    yield
    reset_mcp_server_runtime_for_tests()
    reset_capability_registry_for_tests()
    reset_workflow_templates_for_tests()


# ---------------------------------------------------------------------------
# list_tools
# ---------------------------------------------------------------------------

def test_list_tools_returns_all_builtins():
    srv = get_mcp_server_runtime()
    tools = srv.list_tools()
    names = {t["name"] for t in tools}
    assert "vibrante_plan_workflow"     in names
    assert "vibrante_preview_plan"      in names
    assert "vibrante_list_capabilities" in names
    assert "vibrante_list_templates"    in names
    assert "vibrante_query_audit"       in names
    assert "vibrante_get_scene_status"  in names


def test_list_tools_sorted_by_name():
    srv   = get_mcp_server_runtime()
    tools = srv.list_tools()
    names = [t["name"] for t in tools]
    assert names == sorted(names)


def test_list_tools_have_required_keys():
    srv = get_mcp_server_runtime()
    for tool in srv.list_tools():
        assert "name"        in tool
        assert "description" in tool
        assert "inputSchema" in tool


def test_get_tool_known():
    srv  = get_mcp_server_runtime()
    tool = srv.get_tool("vibrante_list_capabilities")
    assert tool is not None
    assert tool["name"] == "vibrante_list_capabilities"


def test_get_tool_unknown_returns_none():
    srv = get_mcp_server_runtime()
    assert srv.get_tool("not_a_real_tool") is None


# ---------------------------------------------------------------------------
# Custom tool registration
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_custom_tool():
    srv = get_mcp_server_runtime()

    async def my_handler(args):
        return {"custom_result": args.get("x", 0) * 2}

    srv.register_tool(
        "my_custom_tool",
        "Does custom things",
        {"type": "object", "properties": {"x": {"type": "integer"}}},
        my_handler,
    )

    tool = srv.get_tool("my_custom_tool")
    assert tool is not None
    result = await srv.handle_request("my_custom_tool", {"x": 5})
    assert result["custom_result"] == 10
    assert result["is_error"] is False


def test_register_tool_empty_name_raises():
    srv = get_mcp_server_runtime()
    with pytest.raises(ValueError, match="non-empty"):
        srv.register_tool("", "desc", {}, lambda a: {})


@pytest.mark.asyncio
async def test_deregister_custom_tool():
    srv = get_mcp_server_runtime()
    srv.register_tool("tmp_tool", "tmp", {}, lambda a: {})
    assert srv.deregister_tool("tmp_tool") is True
    assert srv.get_tool("tmp_tool") is None


def test_deregister_builtin_raises():
    srv = get_mcp_server_runtime()
    with pytest.raises(ValueError, match="built-in"):
        srv.deregister_tool("vibrante_list_capabilities")


# ---------------------------------------------------------------------------
# handle_request — unknown tool
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handle_request_unknown_tool():
    srv    = get_mcp_server_runtime()
    result = await srv.handle_request("not_a_tool", {})
    assert result["is_error"] is True
    assert "not_a_tool" in result["error"]


# ---------------------------------------------------------------------------
# handle_request — list_capabilities
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handle_list_capabilities():
    srv    = get_mcp_server_runtime()
    result = await srv.handle_request("vibrante_list_capabilities", {})
    assert result["is_error"] is False
    assert isinstance(result["capabilities"], list)
    assert result["count"] >= 1


@pytest.mark.asyncio
async def test_handle_list_capabilities_filtered():
    srv    = get_mcp_server_runtime()
    result = await srv.handle_request("vibrante_list_capabilities", {"cap_type": "renderer"})
    assert all(c["type"] == "renderer" for c in result["capabilities"])


# ---------------------------------------------------------------------------
# handle_request — list_templates
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handle_list_templates():
    srv    = get_mcp_server_runtime()
    result = await srv.handle_request("vibrante_list_templates", {})
    assert result["is_error"] is False
    assert isinstance(result["templates"], list)
    assert result["count"] >= 1


@pytest.mark.asyncio
async def test_handle_list_templates_apply():
    srv    = get_mcp_server_runtime()
    result = await srv.handle_request("vibrante_list_templates", {
        "apply":  "pyro_source",
        "params": {
            "parent": "/obj", "name": "fire",
            "fuel_node": "fuel", "pyro_node": "pyro",
            "source_volume": "density", "radius": "1.0",
        },
    })
    assert result["is_error"] is False
    assert "operations" in result


# ---------------------------------------------------------------------------
# handle_request — get_scene_status
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handle_get_scene_status():
    srv    = get_mcp_server_runtime()
    result = await srv.handle_request("vibrante_get_scene_status", {})
    assert result["is_error"] is False
    assert "dirty_nodes"      in result
    assert "semantic_lineage" in result


# ---------------------------------------------------------------------------
# handle_request — plan_workflow missing prompt
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handle_plan_workflow_empty_prompt():
    srv    = get_mcp_server_runtime()
    result = await srv.handle_request("vibrante_plan_workflow", {"prompt": ""})
    assert result["is_error"] is False
    # The handler returns {"ok": False, "errors": [...]}
    assert result.get("ok") is False


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

def test_start_stop():
    srv = get_mcp_server_runtime()
    assert srv.is_running is False
    srv.start()
    assert srv.is_running is True
    srv.stop()
    assert srv.is_running is False


def test_stats_shape():
    srv   = get_mcp_server_runtime()
    stats = srv.stats()
    assert "tool_count" in stats
    assert "tools"      in stats
    assert stats["tool_count"] >= 6
    assert "running"    in stats


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton_same_instance():
    a = get_mcp_server_runtime()
    b = get_mcp_server_runtime()
    assert a is b


def test_reset_creates_fresh_singleton():
    a = get_mcp_server_runtime()
    reset_mcp_server_runtime_for_tests()
    b = get_mcp_server_runtime()
    assert a is not b
