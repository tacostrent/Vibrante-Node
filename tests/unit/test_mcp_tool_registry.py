"""
tests/unit/test_mcp_tool_registry.py
======================================
Unit tests for src.runtime.mcp_tool_registry.

Verifies tool registration, dispatch, handler logic, and that raw Houdini
mutation APIs are NOT exposed.  All runtime calls are mocked.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.runtime.mcp_tool_registry import (
    MCPToolRegistry,
    ToolDefinition,
    get_mcp_tool_registry,
    register_all_tools,
    reset_mcp_tool_registry_for_tests,
)

EXPECTED_TOOLS = {
    "initialize_runtime_context",
    "query_runtime_state",
    "query_scene_context",
    "query_capabilities",
    "query_workflow_templates",
    "query_examples",
    "query_node_parameters",
    "plan_scene",
    "preview_execution",
    "validate_execution_plan",
    "execute_workflow_transaction",
    "review_execution",
}

FORBIDDEN_TOOLS = {
    "create_node", "set_parm", "set_parms", "run_python",
    "run_code", "delete_node", "raw_houdini_execute",
    "connect_nodes", "cook_node",
}


@pytest.fixture(autouse=True)
def reset():
    reset_mcp_tool_registry_for_tests()
    yield
    reset_mcp_tool_registry_for_tests()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton_same_object():
    r1 = get_mcp_tool_registry()
    r2 = get_mcp_tool_registry()
    assert r1 is r2


def test_reset_creates_fresh_instance():
    r1 = get_mcp_tool_registry()
    reset_mcp_tool_registry_for_tests()
    r2 = get_mcp_tool_registry()
    assert r1 is not r2


# ---------------------------------------------------------------------------
# register_all_tools — coverage and safety
# ---------------------------------------------------------------------------

def test_register_all_tools_returns_registry():
    result = register_all_tools()
    assert isinstance(result, MCPToolRegistry)


def test_register_all_tools_count():
    register_all_tools()
    registry = get_mcp_tool_registry()
    assert registry.stats()["tool_count"] == len(EXPECTED_TOOLS)


def test_all_expected_tools_present():
    register_all_tools()
    registry  = get_mcp_tool_registry()
    registered = {t["name"] for t in registry.list_tools()}
    assert EXPECTED_TOOLS <= registered


def test_forbidden_tools_not_present():
    register_all_tools()
    registry  = get_mcp_tool_registry()
    registered = {t["name"] for t in registry.list_tools()}
    assert registered & FORBIDDEN_TOOLS == set()


def test_tools_have_required_fields():
    register_all_tools()
    registry = get_mcp_tool_registry()
    for tool in registry.list_tools():
        assert "name"        in tool
        assert "description" in tool
        assert "inputSchema" in tool
        assert "category"    in tool


def test_tool_categories_are_semantic():
    register_all_tools()
    registry    = get_mcp_tool_registry()
    categories  = {t["category"] for t in registry.list_tools()}
    allowed     = {"runtime", "knowledge", "planning", "execution"}
    assert categories <= allowed


def test_register_all_tools_passes_to_transport():
    mock_transport = MagicMock()
    register_all_tools(transport=mock_transport)
    assert mock_transport.register_tool.call_count == len(EXPECTED_TOOLS)


# ---------------------------------------------------------------------------
# Manual registration
# ---------------------------------------------------------------------------

async def _good_handler(args):
    return {"ok": True, "echo": args}


def test_register_and_get_tool():
    registry = get_mcp_tool_registry()
    defn = ToolDefinition(
        name="my_tool", description="test",
        inputSchema={}, handler=_good_handler, category="test",
    )
    registry.register_tool(defn)
    result = registry.get_tool("my_tool")
    assert result is not None
    assert result.name == "my_tool"


def test_get_unknown_tool_returns_none():
    registry = get_mcp_tool_registry()
    assert registry.get_tool("does_not_exist") is None


def test_list_tools_sorted_by_insertion():
    registry = get_mcp_tool_registry()
    for name in ("tool_c", "tool_a", "tool_b"):
        registry.register_tool(ToolDefinition(
            name=name, description="x", inputSchema={}, handler=_good_handler,
        ))
    names = [t["name"] for t in registry.list_tools()]
    assert set(names) == {"tool_a", "tool_b", "tool_c"}


# ---------------------------------------------------------------------------
# dispatch_tool
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dispatch_known_tool():
    registry = get_mcp_tool_registry()
    registry.register_tool(ToolDefinition(
        name="echo", description="x", inputSchema={}, handler=_good_handler,
    ))
    result = await registry.dispatch_tool("echo", {"x": 1})
    assert result["ok"] is True
    assert result["echo"] == {"x": 1}


@pytest.mark.asyncio
async def test_dispatch_unknown_tool_returns_error():
    registry = get_mcp_tool_registry()
    result   = await registry.dispatch_tool("nonexistent", {})
    assert result["ok"] is False
    assert "Unknown tool" in result["error"]


@pytest.mark.asyncio
async def test_dispatch_handler_exception_returns_error():
    async def bad_handler(args):
        raise ValueError("boom")

    registry = get_mcp_tool_registry()
    registry.register_tool(ToolDefinition(
        name="bad", description="x", inputSchema={}, handler=bad_handler,
    ))
    result = await registry.dispatch_tool("bad", {})
    assert result["ok"] is False
    assert "boom" in result["error"]


@pytest.mark.asyncio
async def test_dispatch_non_dict_result_wrapped():
    async def list_handler(args):
        return [1, 2, 3]  # returns a list, not a dict

    registry = get_mcp_tool_registry()
    registry.register_tool(ToolDefinition(
        name="lister", description="x", inputSchema={}, handler=list_handler,
    ))
    result = await registry.dispatch_tool("lister", {})
    assert "result" in result
    assert result["result"] == [1, 2, 3]


# ---------------------------------------------------------------------------
# Specific handler happy-paths (mocked runtimes)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_initialize_runtime_context_ok():
    register_all_tools()
    registry = get_mcp_tool_registry()

    with patch("src.runtime.runtime_bootstrap.initialize_runtime",
               return_value={"ok": True, "modules": ["a"]}), \
         patch("src.runtime.runtime_bootstrap.get_bootstrap_data",
               return_value={"runtime_name": "Vibrante Runtime", "mcp_tools": []}):
        result = await registry.dispatch_tool("initialize_runtime_context", {})

    assert result["ok"] is True
    assert "bootstrap" in result
    assert "status"    in result


@pytest.mark.asyncio
async def test_query_capabilities_ok():
    register_all_tools()
    registry = get_mcp_tool_registry()

    mock_caps = [{"cap_type": "houdini_op", "cap_id": "create_node"}]
    with patch("src.runtime.capability_registry.get_capability_registry") as mock_reg:
        mock_reg.return_value.query_capabilities.return_value = mock_caps
        result = await registry.dispatch_tool("query_capabilities", {})

    assert result["ok"] is True
    assert result["count"] == 1


@pytest.mark.asyncio
async def test_query_workflow_templates_ok():
    register_all_tools()
    registry = get_mcp_tool_registry()

    mock_templates = [{"template_id": "pyro_source", "description": "Pyro source"}]
    with patch("src.runtime.workflow_templates.get_workflow_templates") as mock_wt:
        mock_wt.return_value.list_templates.return_value = mock_templates
        result = await registry.dispatch_tool("query_workflow_templates", {})

    assert result["ok"] is True
    assert result["count"] == 1


@pytest.mark.asyncio
async def test_plan_scene_missing_prompt():
    register_all_tools()
    registry = get_mcp_tool_registry()
    result   = await registry.dispatch_tool("plan_scene", {})
    assert result["ok"] is False
    assert "prompt" in result["error"]


@pytest.mark.asyncio
async def test_preview_execution_missing_ops():
    register_all_tools()
    registry = get_mcp_tool_registry()
    result   = await registry.dispatch_tool("preview_execution", {})
    assert result["ok"] is False
    assert "operations" in result["error"].lower()


@pytest.mark.asyncio
async def test_validate_execution_plan_invalid_json():
    register_all_tools()
    registry = get_mcp_tool_registry()
    result   = await registry.dispatch_tool(
        "validate_execution_plan", {"operations_json": "not-json"}
    )
    assert result["ok"] is False
    assert "JSON" in result["error"]


@pytest.mark.asyncio
async def test_review_execution_missing_result():
    register_all_tools()
    registry = get_mcp_tool_registry()
    result   = await registry.dispatch_tool("review_execution", {})
    assert result["ok"] is False
    assert "execution_result_json" in result["error"]


@pytest.mark.asyncio
async def test_execute_workflow_transaction_no_ops():
    register_all_tools()
    registry = get_mcp_tool_registry()
    result   = await registry.dispatch_tool("execute_workflow_transaction", {})
    assert result["ok"] is False


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def test_stats_by_category():
    register_all_tools()
    registry = get_mcp_tool_registry()
    stats    = registry.stats()
    assert stats["by_category"]["runtime"]   == 3
    assert stats["by_category"]["knowledge"] == 4
    assert stats["by_category"]["planning"]  == 3
    assert stats["by_category"]["execution"] == 2
