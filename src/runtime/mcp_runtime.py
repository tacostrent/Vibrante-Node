"""
MCP Runtime Manager
===================
Long-lived registry of MCP (Model Context Protocol) client sessions used by
graph nodes. Treats MCP strictly as transport + capability discovery — never
as an intelligence layer.

Supports two transports:
    stdio  — config: {"command": str, "args": list[str], "env": dict | None}
    sse    — config: {"url": str, "headers": dict | None}

Public async API:
    await register_server(name, transport, config)  -> {"connected", "server_info", "capabilities"}
    await list_tools(server_name)                   -> [{"name", "description", "inputSchema"}, ...]
    await call_tool(server_name, tool, arguments)   -> {"result", "result_json", "is_error"}
    await shutdown_server(server_name)
    await shutdown_all()

The runtime never mutates `os.environ`. Per-call timeout defaults to 30 s
(override with the env var VIBRANTE_MCP_TIMEOUT or by passing `_timeout_sec`
in the `arguments` dict on call_tool).
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Dict, Optional

# mcp SDK symbols — populated lazily on first _require_mcp() call so that
# importing this module at startup does NOT pay the ~0.7 s mcp import cost.
_MCP_AVAILABLE: Optional[bool] = None   # None = not yet attempted
_MCP_IMPORT_ERROR: Optional[str] = None
ClientSession = None        # type: ignore
StdioServerParameters = None  # type: ignore
stdio_client = None         # type: ignore
sse_client = None           # type: ignore


def _default_timeout() -> float:
    raw = os.environ.get("VIBRANTE_MCP_TIMEOUT", "30")
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 30.0


def _require_mcp() -> None:
    global _MCP_AVAILABLE, _MCP_IMPORT_ERROR
    global ClientSession, StdioServerParameters, stdio_client, sse_client

    if _MCP_AVAILABLE is True:
        return
    if _MCP_AVAILABLE is False:
        raise RuntimeError(
            "The 'mcp' Python package is not installed. "
            "Run: pip install 'mcp>=1.0.0'. "
            f"Underlying import error: {_MCP_IMPORT_ERROR}"
        )

    # First call — attempt the import now (deferred from module load time).
    try:
        from mcp import ClientSession as _CS, StdioServerParameters as _SSP
        from mcp.client.stdio import stdio_client as _SC
        from mcp.client.sse import sse_client as _SEC
        ClientSession = _CS
        StdioServerParameters = _SSP
        stdio_client = _SC
        sse_client = _SEC
        _MCP_AVAILABLE = True
        _MCP_IMPORT_ERROR = None
    except ImportError as e:
        _MCP_AVAILABLE = False
        _MCP_IMPORT_ERROR = str(e)
        raise RuntimeError(
            "The 'mcp' Python package is not installed. "
            "Run: pip install 'mcp>=1.0.0'. "
            f"Underlying import error: {_MCP_IMPORT_ERROR}"
        ) from e


class _ManagedSession:
    """Owns the lifecycle of one MCP connection.

    The MCP SDK exposes transports as async context managers that yield
    (read_stream, write_stream). To keep the session alive across many
    graph executions we hold those streams open inside a long-lived
    background task and gate all I/O through `session`.
    """

    def __init__(self, name: str, transport: str, config: dict):
        self.name = name
        self.transport = transport
        self.config = config
        self.session: Optional["ClientSession"] = None
        self.server_info: dict = {}
        self.capabilities: dict = {}
        self._task: Optional[asyncio.Task] = None
        self._ready: asyncio.Event = asyncio.Event()
        self._shutdown: asyncio.Event = asyncio.Event()
        self._error: Optional[BaseException] = None

    async def open(self) -> None:
        _require_mcp()
        self._task = asyncio.create_task(self._run(), name=f"mcp-session-{self.name}")
        try:
            await asyncio.wait_for(self._ready.wait(), timeout=_default_timeout())
        except asyncio.TimeoutError:
            self._shutdown.set()
            if self._task is not None:
                self._task.cancel()
            raise ConnectionError(
                f"MCP server '{self.name}' did not finish handshake within "
                f"{_default_timeout()} s"
            )
        if self._error is not None:
            raise ConnectionError(
                f"MCP server '{self.name}' failed to open: {self._error}"
            )

    async def _run(self) -> None:
        try:
            if self.transport == "stdio":
                command = self.config.get("command", "")
                if not command:
                    raise ValueError("stdio transport requires 'command'")
                args = self.config.get("args") or []
                env = self.config.get("env")
                params = StdioServerParameters(command=command, args=list(args), env=env)
                async with stdio_client(params) as (read_stream, write_stream):
                    await self._serve(read_stream, write_stream)
            elif self.transport == "sse":
                url = self.config.get("url", "")
                if not url:
                    raise ValueError("sse transport requires 'url'")
                headers = self.config.get("headers") or {}
                async with sse_client(url, headers=headers) as (read_stream, write_stream):
                    await self._serve(read_stream, write_stream)
            else:
                raise ValueError(f"Unsupported transport: {self.transport}")
        except BaseException as exc:  # noqa: BLE001 — surface anything to opener
            self._error = exc
            self._ready.set()

    async def _serve(self, read_stream, write_stream) -> None:
        async with ClientSession(read_stream, write_stream) as session:
            init_result = await session.initialize()
            self.session = session
            self.server_info = self._extract_server_info(init_result)
            self.capabilities = self._extract_capabilities(init_result)
            self._ready.set()
            await self._shutdown.wait()
            self.session = None

    @staticmethod
    def _extract_server_info(init_result: Any) -> dict:
        info = getattr(init_result, "serverInfo", None)
        if info is None:
            return {}
        return {
            "name": getattr(info, "name", ""),
            "version": getattr(info, "version", ""),
        }

    @staticmethod
    def _extract_capabilities(init_result: Any) -> dict:
        caps = getattr(init_result, "capabilities", None)
        if caps is None:
            return {}
        try:
            return caps.model_dump(exclude_none=True)
        except AttributeError:
            return {}

    async def close(self) -> None:
        self._shutdown.set()
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except asyncio.TimeoutError:
                self._task.cancel()
            except asyncio.CancelledError:
                pass


_SESSIONS: Dict[str, _ManagedSession] = {}
_REGISTRY_LOCK = asyncio.Lock()


async def register_server(name: str, transport: str, config: dict) -> dict:
    """Register an MCP server connection. Idempotent on `name`."""
    _require_mcp()
    if not name:
        raise ValueError("server name is required")
    if transport not in ("stdio", "sse"):
        raise ValueError(f"unsupported transport: {transport!r}")

    async with _REGISTRY_LOCK:
        existing = _SESSIONS.get(name)
        if existing is not None and existing.session is not None:
            return {
                "connected": True,
                "server_info": dict(existing.server_info),
                "capabilities": dict(existing.capabilities),
                "reused": True,
            }
        if existing is not None:
            # Stale handle — close and replace.
            await existing.close()
            _SESSIONS.pop(name, None)

        managed = _ManagedSession(name, transport, dict(config or {}))
        await managed.open()
        _SESSIONS[name] = managed
        return {
            "connected": True,
            "server_info": dict(managed.server_info),
            "capabilities": dict(managed.capabilities),
            "reused": False,
        }


def _get_session(server_name: str) -> _ManagedSession:
    managed = _SESSIONS.get(server_name)
    if managed is None or managed.session is None:
        raise ConnectionError(
            f"MCP server '{server_name}' is not registered. "
            "Call register_server() first (or wire an mcp_server_init node "
            "upstream)."
        )
    return managed


async def list_tools(server_name: str) -> list[dict]:
    managed = _get_session(server_name)
    assert managed.session is not None
    result = await asyncio.wait_for(managed.session.list_tools(), timeout=_default_timeout())
    out: list[dict] = []
    for tool in getattr(result, "tools", []) or []:
        out.append({
            "name": getattr(tool, "name", ""),
            "description": getattr(tool, "description", "") or "",
            "inputSchema": getattr(tool, "inputSchema", {}) or {},
        })
    return out


async def call_tool(server_name: str, tool_name: str, arguments: dict) -> dict:
    managed = _get_session(server_name)
    assert managed.session is not None

    args = dict(arguments or {})
    timeout = args.pop("_timeout_sec", _default_timeout())

    try:
        result = await asyncio.wait_for(
            managed.session.call_tool(tool_name, args), timeout=timeout
        )
    except asyncio.TimeoutError:
        return {
            "result": None,
            "result_json": "",
            "is_error": True,
            "error": f"tool '{tool_name}' timed out after {timeout} s",
        }

    is_error = bool(getattr(result, "isError", False))
    content = getattr(result, "content", [])
    payload = _content_to_payload(content)
    return {
        "result": payload,
        "result_json": json.dumps(payload, default=str),
        "is_error": is_error,
    }


def _content_to_payload(content_list: Any) -> Any:
    """Convert MCP content blocks to plain JSON-serialisable Python."""
    if not content_list:
        return None
    pieces = []
    for block in content_list:
        block_type = getattr(block, "type", None)
        if block_type == "text":
            pieces.append({"type": "text", "text": getattr(block, "text", "")})
        elif block_type == "image":
            pieces.append({
                "type": "image",
                "data": getattr(block, "data", ""),
                "mimeType": getattr(block, "mimeType", ""),
            })
        elif block_type == "resource":
            resource = getattr(block, "resource", None)
            pieces.append({
                "type": "resource",
                "uri": getattr(resource, "uri", "") if resource else "",
            })
        else:
            try:
                pieces.append(block.model_dump())
            except AttributeError:
                pieces.append(str(block))
    if len(pieces) == 1:
        return pieces[0]
    return pieces


async def shutdown_server(server_name: str) -> None:
    async with _REGISTRY_LOCK:
        managed = _SESSIONS.pop(server_name, None)
    if managed is not None:
        await managed.close()


async def shutdown_all() -> None:
    async with _REGISTRY_LOCK:
        managed_list = list(_SESSIONS.values())
        _SESSIONS.clear()
    for managed in managed_list:
        try:
            await managed.close()
        except Exception:
            pass


def shutdown_all_sync() -> None:
    """Synchronous shutdown for use from non-async callers (e.g. closeEvent).

    Runs `shutdown_all()` on a fresh event loop if no loop is running,
    otherwise schedules it as a fire-and-forget task. Safe to call multiple
    times; idempotent when no sessions exist.
    """
    if not _SESSIONS:
        return
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = None

    if loop is not None and loop.is_running():
        loop.create_task(shutdown_all())
        return

    try:
        asyncio.run(shutdown_all())
    except RuntimeError:
        # Fallback: brand-new loop
        new_loop = asyncio.new_event_loop()
        try:
            new_loop.run_until_complete(shutdown_all())
        finally:
            new_loop.close()


def list_registered_servers() -> list[str]:
    return list(_SESSIONS.keys())
