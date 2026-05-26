"""
tests/unit/test_mcp_transport.py
=================================
Unit tests for src.runtime.mcp_transport.

All tests use mocks — no live MCP connection, no live Houdini.
"""

import asyncio
import json
import threading
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.runtime.mcp_transport import (
    MCPTransport,
    _require_mcp_server,
    get_mcp_transport,
    reset_mcp_transport_for_tests,
)
from src.runtime.mcp_tool_registry import (
    ToolDefinition,
    reset_mcp_tool_registry_for_tests,
)


@pytest.fixture(autouse=True)
def reset():
    reset_mcp_transport_for_tests()
    reset_mcp_tool_registry_for_tests()
    yield
    reset_mcp_transport_for_tests()
    reset_mcp_tool_registry_for_tests()


# ---------------------------------------------------------------------------
# Construction and singleton
# ---------------------------------------------------------------------------

def test_get_mcp_transport_returns_instance():
    t = get_mcp_transport()
    assert isinstance(t, MCPTransport)


def test_singleton_same_object():
    t1 = get_mcp_transport()
    t2 = get_mcp_transport()
    assert t1 is t2


def test_reset_creates_new_instance():
    t1 = get_mcp_transport()
    reset_mcp_transport_for_tests()
    t2 = get_mcp_transport()
    assert t1 is not t2


def test_not_running_on_creation():
    t = MCPTransport()
    assert t.is_running is False


# ---------------------------------------------------------------------------
# Tool registration delegates to registry
# ---------------------------------------------------------------------------

async def _noop_handler(args):
    return {"ok": True}


def test_register_tool_appears_in_registry():
    t    = MCPTransport()
    defn = ToolDefinition(
        name="test_tool",
        description="A test tool",
        inputSchema={"type": "object", "properties": {}},
        handler=_noop_handler,
        category="test",
    )
    t.register_tool(defn)
    tools = t._registry.list_tools()
    names = [t["name"] for t in tools]
    assert "test_tool" in names


def test_register_multiple_tools():
    t = MCPTransport()
    for i in range(3):
        defn = ToolDefinition(
            name=f"tool_{i}",
            description=f"Tool {i}",
            inputSchema={},
            handler=_noop_handler,
        )
        t.register_tool(defn)
    assert len(t._registry.list_tools()) == 3


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def test_stats_structure():
    t = MCPTransport()
    s = t.stats()
    assert "is_running"  in s
    assert "tool_count"  in s
    assert "tools"       in s
    assert isinstance(s["tools"], list)


def test_stats_reflects_registered_tools():
    t    = MCPTransport()
    defn = ToolDefinition(
        name="my_tool", description="x",
        inputSchema={}, handler=_noop_handler,
    )
    t.register_tool(defn)
    s = t.stats()
    assert s["tool_count"] == 1
    assert "my_tool" in s["tools"]


# ---------------------------------------------------------------------------
# Shutdown
# ---------------------------------------------------------------------------

def test_shutdown_sets_not_running():
    t = MCPTransport()
    t.shutdown()
    assert t.is_running is False


# ---------------------------------------------------------------------------
# _require_mcp_server — failure path
# ---------------------------------------------------------------------------

def test_require_mcp_server_raises_when_unavailable():
    import src.runtime.mcp_transport as mod
    original_server = mod._Server
    try:
        mod._Server = None
        with patch("builtins.__import__", side_effect=ImportError("no mcp")):
            with pytest.raises(RuntimeError, match="mcp"):
                _require_mcp_server()
    finally:
        mod._Server = original_server


# ---------------------------------------------------------------------------
# _run_async — mocked mcp SDK
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_async_with_mocked_sdk():
    """_run_async should call app.run with the streams from stdio_server."""
    transport = MCPTransport()

    # Register one tool so list_tools returns something
    transport.register_tool(ToolDefinition(
        name="ping", description="ping",
        inputSchema={}, handler=_noop_handler,
    ))

    # Build mock types module
    mock_types = MagicMock()
    mock_types.Tool.side_effect = lambda **kw: kw
    mock_types.TextContent.side_effect = lambda **kw: kw

    # Build mock server
    mock_app = MagicMock()
    mock_app.create_initialization_options.return_value = {}
    mock_app.run = AsyncMock()
    # list_tools / call_tool decorators return the fn unchanged
    mock_app.list_tools.return_value  = lambda fn: fn
    mock_app.call_tool.return_value   = lambda fn: fn

    # Fake stdio_server context manager returns (read, write)
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def fake_stdio():
        yield (MagicMock(), MagicMock())

    import src.runtime.mcp_transport as mod
    orig_server   = mod._Server
    orig_stdio    = mod._stdio_server
    orig_types    = mod._mcp_types

    mod._Server       = lambda name: mock_app
    mod._stdio_server = fake_stdio
    mod._mcp_types    = mock_types

    try:
        await transport._run_async()
    finally:
        mod._Server       = orig_server
        mod._stdio_server = orig_stdio
        mod._mcp_types    = orig_types

    mock_app.run.assert_called_once()


@pytest.mark.asyncio
async def test_run_async_sets_and_clears_running_flag():
    transport = MCPTransport()

    mock_types = MagicMock()
    mock_types.Tool.side_effect       = lambda **kw: kw
    mock_types.TextContent.side_effect = lambda **kw: kw
    mock_app = MagicMock()
    mock_app.create_initialization_options.return_value = {}
    mock_app.run = AsyncMock()
    mock_app.list_tools.return_value = lambda fn: fn
    mock_app.call_tool.return_value  = lambda fn: fn

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def fake_stdio():
        yield (MagicMock(), MagicMock())

    import src.runtime.mcp_transport as mod
    orig_server, orig_stdio, orig_types = mod._Server, mod._stdio_server, mod._mcp_types
    mod._Server       = lambda name: mock_app
    mod._stdio_server = fake_stdio
    mod._mcp_types    = mock_types

    try:
        await transport._run_async()
    finally:
        mod._Server       = orig_server
        mod._stdio_server = orig_stdio
        mod._mcp_types    = orig_types

    assert transport.is_running is False  # cleared in finally


# ---------------------------------------------------------------------------
# run_stdio uses asyncio.run
# ---------------------------------------------------------------------------

def test_run_stdio_calls_asyncio_run():
    transport = MCPTransport()
    with patch("asyncio.run") as mock_run:
        transport.run_stdio()
        mock_run.assert_called_once()


# ---------------------------------------------------------------------------
# Thread safety — parallel registrations
# ---------------------------------------------------------------------------

def test_concurrent_register_tool_thread_safe():
    t = MCPTransport()
    errors = []

    def register(i):
        try:
            t.register_tool(ToolDefinition(
                name=f"concurrent_tool_{i}", description="x",
                inputSchema={}, handler=_noop_handler,
            ))
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=register, args=(i,)) for i in range(20)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()

    assert errors == []
    assert len(t._registry.list_tools()) == 20
