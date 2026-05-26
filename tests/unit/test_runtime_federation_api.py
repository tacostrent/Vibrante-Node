"""
Unit tests for src.runtime.runtime_federation_api.

Covers:
  • local runtime auto-registered at init
  • register_runtime returns uuid
  • register_runtime empty name raises
  • register_runtime invalid type raises
  • deregister_runtime True / False
  • deregister_runtime "local" raises ValueError
  • get_runtime_status / list_runtimes
  • list_runtimes runtime_type filter
  • discover_capabilities local — queries live registry
  • discover_capabilities remote — returns registered list
  • discover_capabilities unknown — returns []
  • exchange_capabilities updates peer + returns sent/received
  • update_runtime_heartbeat True / False
  • request_execution local — delegates to DistributedRuntime
  • request_execution remote — returns federated_dispatch
  • request_execution unknown runtime — returns error
  • stats shape
  • singleton / reset
"""

from __future__ import annotations

import pytest

from src.runtime.runtime_federation_api import (
    RuntimeFederationApi,
    get_runtime_federation_api,
    reset_runtime_federation_api_for_tests,
)
from src.runtime.capability_registry  import reset_capability_registry_for_tests
from src.runtime.runtime_constraints  import reset_runtime_constraints_for_tests
from src.runtime.validation_engine    import reset_validation_engine_for_tests
from src.runtime.dependency_graph     import reset_dependency_graph_for_tests
from src.runtime.distributed_runtime import (
    reset_distributed_runtime_for_tests,
    get_distributed_runtime,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_runtime_federation_api_for_tests()
    reset_distributed_runtime_for_tests()
    reset_capability_registry_for_tests()
    reset_runtime_constraints_for_tests()
    reset_validation_engine_for_tests()
    reset_dependency_graph_for_tests()
    yield
    reset_runtime_federation_api_for_tests()
    reset_distributed_runtime_for_tests()
    reset_capability_registry_for_tests()


# ---------------------------------------------------------------------------
# Auto-registration of local runtime
# ---------------------------------------------------------------------------

def test_local_runtime_registered_at_init():
    api = get_runtime_federation_api()
    rt  = api.get_runtime_status("local")
    assert rt is not None
    assert rt["id"]           == "local"
    assert rt["runtime_type"] == "local"
    assert rt["endpoint"]     == "local://"


def test_local_runtime_in_list():
    api      = get_runtime_federation_api()
    runtimes = {r["id"] for r in api.list_runtimes()}
    assert "local" in runtimes


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def test_register_runtime_returns_uuid():
    api = get_runtime_federation_api()
    rid = api.register_runtime("farm-node-01", "remote://farm1", ["houdini"], "farm")
    assert isinstance(rid, str) and len(rid) == 36


def test_register_runtime_empty_name_raises():
    api = get_runtime_federation_api()
    with pytest.raises(ValueError):
        api.register_runtime("", "remote://x", [], "remote")


def test_register_runtime_invalid_type_raises():
    api = get_runtime_federation_api()
    with pytest.raises(ValueError, match="runtime_type"):
        api.register_runtime("bad", "remote://x", [], "invented_type")


def test_deregister_runtime_true():
    api = get_runtime_federation_api()
    rid = api.register_runtime("peer-01", "remote://peer1", [], "remote")
    assert api.deregister_runtime(rid) is True
    assert api.get_runtime_status(rid) is None


def test_deregister_runtime_unknown_false():
    api = get_runtime_federation_api()
    assert api.deregister_runtime("00000000-0000-0000-0000-000000000000") is False


def test_deregister_local_raises():
    api = get_runtime_federation_api()
    with pytest.raises(ValueError, match="local"):
        api.deregister_runtime("local")


# ---------------------------------------------------------------------------
# Get status / list
# ---------------------------------------------------------------------------

def test_get_runtime_status_returns_dict():
    api = get_runtime_federation_api()
    rid = api.register_runtime("peer-01", "remote://peer1", ["karma"], "remote")
    rt  = api.get_runtime_status(rid)
    assert rt is not None
    assert rt["name"]         == "peer-01"
    assert rt["runtime_type"] == "remote"
    assert "karma" in rt["capabilities"]


def test_get_runtime_status_unknown_returns_none():
    api = get_runtime_federation_api()
    assert api.get_runtime_status("missing") is None


def test_list_runtimes_type_filter():
    api = get_runtime_federation_api()
    api.register_runtime("farm-01", "remote://farm", [], "farm")
    api.register_runtime("cloud-01", "remote://cloud", [], "cloud")
    farm_rts = api.list_runtimes(runtime_type="farm")
    assert all(r["runtime_type"] == "farm" for r in farm_rts)
    assert len(farm_rts) == 1


# ---------------------------------------------------------------------------
# Capability discovery / exchange
# ---------------------------------------------------------------------------

def test_discover_capabilities_local_returns_list():
    api  = get_runtime_federation_api()
    caps = api.discover_capabilities("local")
    assert isinstance(caps, list)
    # Local runtime queries live CapabilityRegistry — should have built-in caps
    assert len(caps) >= 1


def test_discover_capabilities_remote_returns_registered():
    api = get_runtime_federation_api()
    rid = api.register_runtime("peer", "remote://peer", ["karma", "mantra"], "remote")
    caps = api.discover_capabilities(rid)
    ids  = {c["id"] if isinstance(c, dict) else c for c in caps}
    assert "karma" in ids and "mantra" in ids


def test_discover_capabilities_unknown_returns_empty():
    api = get_runtime_federation_api()
    assert api.discover_capabilities("nonexistent-id") == []


def test_exchange_capabilities_returns_sent_received():
    api = get_runtime_federation_api()
    rid = api.register_runtime("peer", "remote://peer", ["karma"], "remote")
    result = api.exchange_capabilities(rid, our_capabilities=["houdini", "mantra"])
    assert result["ok"] is True
    assert isinstance(result["received"], list)
    assert isinstance(result["sent"], list)
    assert "houdini" in result["sent"]


# ---------------------------------------------------------------------------
# Heartbeat
# ---------------------------------------------------------------------------

def test_update_runtime_heartbeat_true():
    api = get_runtime_federation_api()
    rid = api.register_runtime("peer", "remote://p", [], "remote")
    assert api.update_runtime_heartbeat(rid) is True


def test_update_runtime_heartbeat_unknown_false():
    api = get_runtime_federation_api()
    assert api.update_runtime_heartbeat("missing") is False


def test_update_heartbeat_sets_online():
    api = get_runtime_federation_api()
    rid = api.register_runtime("peer", "remote://p", [], "remote")
    # Force offline
    with api._lock:
        api._runtimes[rid]["status"] = "offline"
    api.update_runtime_heartbeat(rid)
    assert api.get_runtime_status(rid)["status"] == "online"


# ---------------------------------------------------------------------------
# request_execution
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_request_execution_unknown_runtime_error():
    api    = get_runtime_federation_api()
    result = await api.request_execution("nonexistent", [{"op": "create_node"}])
    assert result["ok"] is False
    assert "Unknown runtime" in result["error"]


@pytest.mark.asyncio
async def test_request_execution_remote_returns_federated_dispatch():
    api = get_runtime_federation_api()
    rid = api.register_runtime("remote-peer", "remote://farm1", ["houdini"], "remote")
    result = await api.request_execution(rid, [{"op": "create_node"}])
    assert result["ok"]     is True
    assert result["status"] == "federated_dispatch"
    assert "dispatch_id"    in result
    assert result["runtime_id"] == rid


@pytest.mark.asyncio
async def test_request_execution_local_delegates_to_distributed():
    """Local runtime goes through DistributedRuntime; no workers → no_worker status."""
    api    = get_runtime_federation_api()
    result = await api.request_execution(
        "local",
        [{"op": "create_node", "parent": "/obj", "type": "geo"}],
    )
    # No workers registered → should get no_worker (still a dict from DistributedRuntime)
    assert "ok" in result
    # no_worker is ok=False since no worker found
    assert result.get("status") in ("no_worker", "validated", "dispatched", "completed")


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def test_stats_shape():
    api = get_runtime_federation_api()
    api.register_runtime("farm", "remote://f", [], "farm")
    s = api.stats()
    assert "total_runtimes"  in s
    assert "by_type"         in s
    assert "by_status"       in s
    assert "total_exchanges" in s
    assert s["total_runtimes"] >= 2   # local + farm


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton_same_instance():
    a = get_runtime_federation_api()
    b = get_runtime_federation_api()
    assert a is b


def test_reset_creates_fresh_instance():
    a = get_runtime_federation_api()
    reset_runtime_federation_api_for_tests()
    b = get_runtime_federation_api()
    assert a is not b
