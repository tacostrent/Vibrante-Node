"""
MCP Transport Runtime
=====================
Implements the actual MCP stdio transport for the Vibrante Runtime.

The transport:
  - accepts stdio connections from Claude Desktop, Codex CLI, Cursor, and
    any other MCP-compatible client
  - delegates tool listing and dispatch to MCPToolRegistry
  - runs entirely in asyncio (compatible with the mcp SDK >= 1.0.0)
  - defers mcp SDK imports until run_stdio() is called (startup-safe)

Public API:
    MCPTransport.register_tool(tool_definition)  — forward to registry
    MCPTransport.run_stdio()                     — block and serve stdio
    MCPTransport.shutdown()                      — request stop

    get_mcp_transport() -> MCPTransport   (singleton)
    reset_mcp_transport_for_tests()
"""

from __future__ import annotations

import asyncio
import json
import threading
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.runtime.mcp_tool_registry import ToolDefinition

# ---------------------------------------------------------------------------
# Deferred mcp SDK server imports
# ---------------------------------------------------------------------------

_Server       = None  # mcp.server.Server
_stdio_server = None  # mcp.server.stdio.stdio_server
_mcp_types    = None  # mcp.types module


def _require_mcp_server() -> None:
    """Import mcp SDK server-side symbols on first call.

    Deferred so that importing mcp_transport at startup does NOT pay the
    mcp package load cost until a real transport session begins.
    """
    global _Server, _stdio_server, _mcp_types

    if _Server is not None:
        return

    try:
        from mcp.server       import Server        as _S
        from mcp.server.stdio import stdio_server  as _ss
        import mcp.types as _mt
        _Server       = _S
        _stdio_server = _ss
        _mcp_types    = _mt
    except ImportError as exc:
        raise RuntimeError(
            "The 'mcp' package server-side APIs are not available. "
            "Run: pip install 'mcp>=1.0.0'. "
            f"Underlying error: {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# MCPTransport
# ---------------------------------------------------------------------------

class MCPTransport:
    """Vibrante Runtime stdio MCP server.

    Lifecycle:
        transport = MCPTransport()
        register_all_tools(transport)   # or transport.register_tool(defn) calls
        transport.run_stdio()           # blocks until client disconnects

    The transport shares the MCPToolRegistry singleton so tools registered
    before or after construction are both visible.
    """

    def __init__(self) -> None:
        from src.runtime.mcp_tool_registry import get_mcp_tool_registry
        self._registry = get_mcp_tool_registry()
        self._running  = False
        self._lock     = threading.Lock()

    # ------------------------------------------------------------------
    # Tool registration (delegates to the shared registry)
    # ------------------------------------------------------------------

    def register_tool(self, tool_definition: "ToolDefinition") -> None:
        """Register a tool via the shared MCPToolRegistry."""
        self._registry.register_tool(tool_definition)

    # ------------------------------------------------------------------
    # Stdio transport
    # ------------------------------------------------------------------

    def run_stdio(self) -> None:
        """Block and serve MCP over stdio until the client disconnects.

        Creates a fresh event loop via asyncio.run() — safe because this
        method is only called from scripts/run_vibrante_mcp.py as the main
        entry point, never from inside the Qt application loop.
        """
        asyncio.run(self._run_async())

    async def _run_async(self) -> None:
        """Async inner loop — creates the mcp Server and runs stdio transport."""
        _require_mcp_server()

        app      = _Server("vibrante-node")
        registry = self._registry

        # ── list_tools handler ──────────────────────────────────────────
        @app.list_tools()
        async def handle_list_tools():
            return [
                _mcp_types.Tool(
                    name        = t["name"],
                    description = t["description"],
                    inputSchema = t.get("inputSchema", {"type": "object", "properties": {}}),
                )
                for t in registry.list_tools()
            ]

        # ── call_tool handler ───────────────────────────────────────────
        @app.call_tool()
        async def handle_call_tool(name: str, arguments):
            result = await registry.dispatch_tool(name, arguments or {})
            return [
                _mcp_types.TextContent(
                    type = "text",
                    text = json.dumps(result, default=str, indent=2),
                )
            ]

        # ── run ─────────────────────────────────────────────────────────
        with self._lock:
            self._running = True
        try:
            async with _stdio_server() as (read_stream, write_stream):
                init_opts = app.create_initialization_options()
                await app.run(read_stream, write_stream, init_opts)
        finally:
            with self._lock:
                self._running = False

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    def shutdown(self) -> None:
        """Signal the transport to stop (best-effort; stdio session ends naturally)."""
        with self._lock:
            self._running = False

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._running

    def stats(self) -> dict:
        return {
            "is_running":  self.is_running,
            "tool_count":  len(self._registry.list_tools()),
            "tools":       sorted(t["name"] for t in self._registry.list_tools()),
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[MCPTransport] = None
_LOCK = threading.Lock()


def get_mcp_transport() -> MCPTransport:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = MCPTransport()
        return _INSTANCE


def reset_mcp_transport_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
