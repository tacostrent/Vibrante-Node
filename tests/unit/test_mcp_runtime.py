"""
Unit tests for src.runtime.mcp_runtime.

We do not spin up a real MCP server. Instead we substitute a fake
_ManagedSession that mirrors the public-facing attributes (`session`,
`server_info`, `capabilities`) and a fake session object that returns
canned tool catalogs / call results. This proves the registry + result
shaping behaviour without requiring the MCP SDK transports.
"""

from __future__ import annotations

import asyncio
import json
import pytest

from src.runtime import mcp_runtime


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class _FakeTool:
    def __init__(self, name: str, description: str, schema: dict):
        self.name = name
        self.description = description
        self.inputSchema = schema


class _FakeListResult:
    def __init__(self, tools):
        self.tools = tools


class _FakeTextBlock:
    def __init__(self, text: str):
        self.type = "text"
        self.text = text


class _FakeCallResult:
    def __init__(self, blocks, is_error=False):
        self.content = blocks
        self.isError = is_error


class _FakeSession:
    def __init__(self, tools=(), call_result=None, call_error=False):
        self._tools = list(tools)
        self._call_result = call_result
        self._call_error = call_error
        self.calls: list[tuple[str, dict]] = []

    async def list_tools(self):
        return _FakeListResult(list(self._tools))

    async def call_tool(self, name, arguments):
        self.calls.append((name, dict(arguments)))
        blocks = self._call_result if self._call_result is not None else [_FakeTextBlock("ok")]
        return _FakeCallResult(blocks, self._call_error)


class _FakeManagedSession:
    """Stand-in for _ManagedSession that skips the transport handshake."""

    def __init__(self, name, transport, config, session=None,
                 server_info=None, capabilities=None):
        self.name = name
        self.transport = transport
        self.config = config
        self.session = session or _FakeSession()
        self.server_info = server_info or {"name": "fake", "version": "0.0.0"}
        self.capabilities = capabilities or {"tools": {}}
        self.closed = False

    async def open(self):
        return None

    async def close(self):
        self.closed = True
        self.session = None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clean_registry():
    mcp_runtime._SESSIONS.clear()
    yield
    mcp_runtime._SESSIONS.clear()


@pytest.fixture
def patch_session(monkeypatch):
    """Patch _ManagedSession to skip real transport handshake."""

    factories: list[_FakeManagedSession] = []

    def _factory(name, transport, config, **session_kwargs):
        managed = _FakeManagedSession(name, transport, config, **session_kwargs)
        factories.append(managed)
        return managed

    def _install(session=None, server_info=None, capabilities=None):
        def _ctor(name, transport, config):
            return _factory(name, transport, config,
                            session=session, server_info=server_info,
                            capabilities=capabilities)
        monkeypatch.setattr(mcp_runtime, "_ManagedSession", _ctor)
        return factories

    return _install


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_default_timeout_reads_env_var(monkeypatch):
    monkeypatch.setenv("VIBRANTE_MCP_TIMEOUT", "12.5")
    assert mcp_runtime._default_timeout() == 12.5


def test_default_timeout_falls_back_on_garbage(monkeypatch):
    monkeypatch.setenv("VIBRANTE_MCP_TIMEOUT", "not-a-number")
    assert mcp_runtime._default_timeout() == 30.0


@pytest.mark.asyncio
async def test_register_server_rejects_unknown_transport(patch_session):
    patch_session()
    with pytest.raises(ValueError, match="unsupported transport"):
        await mcp_runtime.register_server("s1", "tcp", {})


@pytest.mark.asyncio
async def test_register_server_requires_name(patch_session):
    patch_session()
    with pytest.raises(ValueError, match="server name is required"):
        await mcp_runtime.register_server("", "stdio", {"command": "x"})


@pytest.mark.asyncio
async def test_register_server_stores_session(patch_session):
    factories = patch_session()
    result = await mcp_runtime.register_server("s1", "stdio", {"command": "x"})
    assert result["connected"] is True
    assert result["server_info"] == {"name": "fake", "version": "0.0.0"}
    assert result["reused"] is False
    assert "s1" in mcp_runtime._SESSIONS
    assert factories[0].name == "s1"


@pytest.mark.asyncio
async def test_register_server_idempotent_on_same_name(patch_session):
    factories = patch_session()
    await mcp_runtime.register_server("s1", "stdio", {"command": "x"})
    second = await mcp_runtime.register_server("s1", "stdio", {"command": "x"})
    assert second["reused"] is True
    assert len(factories) == 1  # second call did NOT create a new managed session


@pytest.mark.asyncio
async def test_register_server_replaces_stale_session(patch_session):
    factories = patch_session()
    await mcp_runtime.register_server("s1", "stdio", {"command": "x"})
    # Simulate stale: session went away (e.g. transport died)
    factories[0].session = None
    second = await mcp_runtime.register_server("s1", "stdio", {"command": "x"})
    assert second["reused"] is False
    assert len(factories) == 2
    assert factories[0].closed is True


@pytest.mark.asyncio
async def test_list_tools_returns_normalised_dicts(patch_session):
    tools = [
        _FakeTool("echo", "Echo input", {"type": "object"}),
        _FakeTool("add", "", None),
    ]
    patch_session(session=_FakeSession(tools=tools))
    await mcp_runtime.register_server("s1", "stdio", {"command": "x"})
    result = await mcp_runtime.list_tools("s1")
    assert result == [
        {"name": "echo", "description": "Echo input", "inputSchema": {"type": "object"}},
        {"name": "add", "description": "", "inputSchema": {}},
    ]


@pytest.mark.asyncio
async def test_list_tools_errors_when_server_not_registered():
    with pytest.raises(ConnectionError, match="is not registered"):
        await mcp_runtime.list_tools("missing")


@pytest.mark.asyncio
async def test_call_tool_shapes_text_block(patch_session):
    blocks = [_FakeTextBlock("hello")]
    fake_session = _FakeSession(call_result=blocks)
    patch_session(session=fake_session)
    await mcp_runtime.register_server("s1", "stdio", {"command": "x"})

    result = await mcp_runtime.call_tool("s1", "echo", {"foo": "bar"})

    assert result["is_error"] is False
    assert result["result"] == {"type": "text", "text": "hello"}
    parsed_back = json.loads(result["result_json"])
    assert parsed_back == result["result"]
    assert fake_session.calls == [("echo", {"foo": "bar"})]


@pytest.mark.asyncio
async def test_call_tool_propagates_is_error_flag(patch_session):
    fake_session = _FakeSession(
        call_result=[_FakeTextBlock("boom")], call_error=True
    )
    patch_session(session=fake_session)
    await mcp_runtime.register_server("s1", "stdio", {"command": "x"})

    result = await mcp_runtime.call_tool("s1", "boom", {})
    assert result["is_error"] is True


@pytest.mark.asyncio
async def test_call_tool_strips_internal_timeout(patch_session):
    fake_session = _FakeSession()
    patch_session(session=fake_session)
    await mcp_runtime.register_server("s1", "stdio", {"command": "x"})

    await mcp_runtime.call_tool("s1", "echo", {"foo": "bar", "_timeout_sec": 5})

    # _timeout_sec must not be forwarded to the MCP tool
    assert fake_session.calls == [("echo", {"foo": "bar"})]


@pytest.mark.asyncio
async def test_shutdown_server_clears_registry(patch_session):
    factories = patch_session()
    await mcp_runtime.register_server("s1", "stdio", {"command": "x"})
    await mcp_runtime.shutdown_server("s1")
    assert "s1" not in mcp_runtime._SESSIONS
    assert factories[0].closed is True


@pytest.mark.asyncio
async def test_shutdown_all_closes_every_session(patch_session):
    factories = patch_session()
    await mcp_runtime.register_server("s1", "stdio", {"command": "x"})
    await mcp_runtime.register_server("s2", "stdio", {"command": "y"})
    assert len(mcp_runtime._SESSIONS) == 2

    await mcp_runtime.shutdown_all()

    assert mcp_runtime._SESSIONS == {}
    assert all(f.closed for f in factories)


def test_shutdown_all_sync_is_noop_when_empty():
    # Should not raise, should not require a running event loop
    mcp_runtime.shutdown_all_sync()
    assert mcp_runtime._SESSIONS == {}


def test_list_registered_servers_returns_names(patch_session):
    factories = patch_session()
    asyncio.run(mcp_runtime.register_server("alpha", "stdio", {"command": "x"}))
    asyncio.run(mcp_runtime.register_server("beta", "stdio", {"command": "y"}))
    names = sorted(mcp_runtime.list_registered_servers())
    assert names == ["alpha", "beta"]
    assert len(factories) == 2
