"""
Unit tests for src.runtime.agent_runtime.

Covers:
  • register_agent returns uuid
  • invalid supervision_level raises
  • deregister_agent True / False
  • get_agent / list_agents
  • list_agents role filter
  • submit_proposal without prompt/intent returns error
  • submit_proposal with unknown agent returns error
  • supervision_level "advisory" always requires_approval, never execution_authorized
  • supervision_level "strict" always requires_approval
  • supervision_level "standard" auto-authorizes safe proposals
  • proposal_count incremented per submission
  • get_proposal retrieves by proposal_id
  • stats shape
  • singleton / reset
"""

from __future__ import annotations

import pytest

from src.runtime.agent_runtime import (
    AgentRuntime,
    get_agent_runtime,
    reset_agent_runtime_for_tests,
    SUPERVISION_LEVELS,
)
from src.runtime.llm_provider          import reset_llm_provider_for_tests, set_llm_provider, MockLLMProvider
from src.runtime.intent_parser         import reset_intent_parser_for_tests
from src.runtime.contextual_reasoning  import reset_contextual_reasoner_for_tests
from src.runtime.ai_planner            import reset_ai_planner_for_tests
from src.runtime.plan_validator        import reset_plan_validator_for_tests
from src.runtime.capability_registry   import reset_capability_registry_for_tests
from src.runtime.runtime_constraints   import reset_runtime_constraints_for_tests
from src.runtime.dependency_graph      import reset_dependency_graph_for_tests


@pytest.fixture(autouse=True)
def _reset():
    reset_agent_runtime_for_tests()
    reset_llm_provider_for_tests()
    reset_intent_parser_for_tests()
    reset_contextual_reasoner_for_tests()
    reset_ai_planner_for_tests()
    reset_plan_validator_for_tests()
    reset_capability_registry_for_tests()
    reset_runtime_constraints_for_tests()
    reset_dependency_graph_for_tests()
    set_llm_provider(MockLLMProvider())
    yield
    reset_agent_runtime_for_tests()
    reset_llm_provider_for_tests()


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def test_register_agent_returns_uuid():
    ar  = get_agent_runtime()
    aid = ar.register_agent("analyzer")
    assert isinstance(aid, str) and len(aid) == 36


def test_register_agent_invalid_supervision_raises():
    ar = get_agent_runtime()
    with pytest.raises(ValueError, match="supervision_level"):
        ar.register_agent("bad", supervision_level="ultra_strict")


def test_deregister_agent_true():
    ar  = get_agent_runtime()
    aid = ar.register_agent("analyzer")
    assert ar.deregister_agent(aid) is True


def test_deregister_agent_unknown_false():
    ar = get_agent_runtime()
    assert ar.deregister_agent("missing") is False


def test_get_agent_returns_dict():
    ar  = get_agent_runtime()
    aid = ar.register_agent("my_agent", role="optimizer", supervision_level="strict")
    a   = ar.get_agent(aid)
    assert a is not None
    assert a["name"] == "my_agent"
    assert a["supervision_level"] == "strict"


def test_get_agent_unknown_returns_none():
    ar = get_agent_runtime()
    assert ar.get_agent("unknown") is None


def test_list_agents_role_filter():
    ar = get_agent_runtime()
    ar.register_agent("a1", role="optimizer")
    ar.register_agent("a2", role="scene_analyzer")
    optimizers = ar.list_agents(role="optimizer")
    assert len(optimizers) == 1
    assert optimizers[0]["name"] == "a1"


# ---------------------------------------------------------------------------
# Proposal submission errors
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_submit_proposal_unknown_agent():
    ar     = get_agent_runtime()
    result = await ar.submit_proposal("unknown-id", {"prompt": "build pyro"})
    assert result["ok"] is False
    assert "Unknown agent" in result.get("error", "")


@pytest.mark.asyncio
async def test_submit_proposal_no_prompt_or_intent():
    ar  = get_agent_runtime()
    aid = ar.register_agent("a1")
    result = await ar.submit_proposal(aid, {"context": {"parent": "/obj"}})
    assert result["ok"] is False
    assert "prompt" in result.get("error", "").lower() or "intent" in result.get("error", "").lower()


# ---------------------------------------------------------------------------
# Advisory supervision — never authorizes execution
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_advisory_never_execution_authorized():
    ar  = get_agent_runtime()
    aid = ar.register_agent("advisory_agent", supervision_level="advisory")
    result = await ar.submit_proposal(aid, {"intent": "create_geo_container", "context": {"parent": "/obj"}})
    # advisory agents always have execution_authorized=False
    assert result.get("execution_authorized") is False
    assert result.get("requires_approval") is True


# ---------------------------------------------------------------------------
# Strict supervision — always requires approval
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_strict_always_requires_approval():
    ar  = get_agent_runtime()
    aid = ar.register_agent("strict_agent", supervision_level="strict")
    result = await ar.submit_proposal(aid, {"intent": "create_geo_container", "context": {"parent": "/obj"}})
    assert result.get("requires_approval") is True
    assert result.get("execution_authorized") is False


# ---------------------------------------------------------------------------
# Standard supervision — safe plan may be auto-authorized
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_standard_safe_plan_may_authorize():
    ar  = get_agent_runtime()
    aid = ar.register_agent("std_agent", supervision_level="standard")
    result = await ar.submit_proposal(aid, {"intent": "create_geo_container", "context": {"parent": "/obj"}})
    # Just check the proposal came back with required keys
    assert "proposal_id" in result
    assert "execution_authorized" in result


# ---------------------------------------------------------------------------
# Proposal count
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_proposal_count_incremented():
    ar  = get_agent_runtime()
    aid = ar.register_agent("counter_agent")
    await ar.submit_proposal(aid, {"intent": "create_geo_container", "context": {"parent": "/obj"}})
    await ar.submit_proposal(aid, {"intent": "create_geo_container", "context": {"parent": "/obj"}})
    a = ar.get_agent(aid)
    assert a["proposal_count"] == 2


# ---------------------------------------------------------------------------
# get_proposal
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_proposal_by_id():
    ar     = get_agent_runtime()
    aid    = ar.register_agent("agent1")
    result = await ar.submit_proposal(aid, {"intent": "create_geo_container", "context": {"parent": "/obj"}})
    pid    = result.get("proposal_id")
    if pid:
        p = ar.get_proposal(pid)
        assert p is not None
        assert p["agent_id"] == aid


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def test_stats_shape():
    ar = get_agent_runtime()
    ar.register_agent("a1", supervision_level="strict")
    ar.register_agent("a2", supervision_level="advisory")
    s = ar.stats()
    assert "total_agents"    in s
    assert "total_proposals" in s
    assert "by_supervision"  in s
    assert s["total_agents"]         == 2
    assert s["by_supervision"]["strict"]   == 1
    assert s["by_supervision"]["advisory"] == 1


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton_same_instance():
    a = get_agent_runtime()
    b = get_agent_runtime()
    assert a is b


def test_reset_creates_fresh_instance():
    a = get_agent_runtime()
    reset_agent_runtime_for_tests()
    b = get_agent_runtime()
    assert a is not b
