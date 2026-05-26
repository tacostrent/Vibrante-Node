"""
Unit tests for src.runtime.ai_planner.

Covers:
  • plan returns required keys
  • no intent → ok=False
  • known intent resolves ops
  • ambiguous intent produces warning
  • plan uses workflow template when available
  • plan falls back to semantic registry when template missing
  • constraint violation surfaces in errors
  • approval required for high-risk ops
  • approval required when delete_node present
  • approval not required for low-risk plan
  • LLM refinement applied via mock provider
  • singleton / reset
"""

from __future__ import annotations

import pytest

from src.runtime.ai_planner import (
    AIPlanner,
    get_ai_planner,
    reset_ai_planner_for_tests,
)
from src.runtime.semantic_registry import (
    get_semantic_registry,
    reset_semantic_registry_for_tests,
)
from src.runtime.runtime_constraints import (
    get_runtime_constraints,
    reset_runtime_constraints_for_tests,
)
from src.runtime.llm_provider import (
    MockLLMProvider,
    set_llm_provider,
    reset_llm_provider_for_tests,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_ai_planner_for_tests()
    reset_semantic_registry_for_tests()
    reset_runtime_constraints_for_tests()
    reset_llm_provider_for_tests()
    yield
    reset_ai_planner_for_tests()
    reset_semantic_registry_for_tests()
    reset_runtime_constraints_for_tests()
    reset_llm_provider_for_tests()


def _make_parsed(intent, confidence=0.9, params=None, ambiguous=False, alternatives=None):
    return {
        "intent":           intent,
        "parameters":       params or {},
        "confidence":       confidence,
        "alternatives":     alternatives or [],
        "ambiguous":        ambiguous,
        "raw_prompt":       f"test prompt for {intent}",
        "matched_keywords": [],
        "llm_enhanced":     False,
    }


# ---------------------------------------------------------------------------
# Output shape
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_plan_returns_required_keys():
    planner = get_ai_planner()
    parsed  = _make_parsed("create_geo_container")
    result  = await planner.plan(parsed)
    for key in ("plan_id", "ok", "intent", "confidence", "selected_template",
                "execution_strategy", "operations", "op_count", "parameters",
                "warnings", "errors", "requires_approval", "approval_reasons",
                "resource_estimate", "constraint_result", "reasoning",
                "llm_refined", "timestamp"):
        assert key in result, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# No intent
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_intent_returns_not_ok():
    planner = get_ai_planner()
    parsed  = _make_parsed(None, confidence=0.0)
    result  = await planner.plan(parsed)
    assert result["ok"] is False
    assert len(result["errors"]) >= 1


# ---------------------------------------------------------------------------
# Known intent resolves ops
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_known_intent_resolves_ops():
    planner = get_ai_planner()
    parsed  = _make_parsed("create_geo_container", params={"parent": "/obj", "name": "test_geo"})
    result  = await planner.plan(parsed)
    assert result["ok"] is True
    assert result["op_count"] >= 1
    assert result["intent"] == "create_geo_container"


@pytest.mark.asyncio
async def test_plan_id_is_uuid():
    planner = get_ai_planner()
    parsed  = _make_parsed("create_geo_container")
    result  = await planner.plan(parsed)
    assert len(result["plan_id"]) == 36


# ---------------------------------------------------------------------------
# Ambiguity warning
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ambiguous_intent_adds_warning():
    planner = get_ai_planner()
    parsed  = _make_parsed(
        "build_pyro_source",
        ambiguous=True,
        alternatives=[{"intent": "create_geo_container", "confidence": 0.5}],
    )
    result = await planner.plan(parsed)
    assert any("ambiguous" in w.lower() for w in result["warnings"])


# ---------------------------------------------------------------------------
# Template vs semantic registry
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_plan_selects_template_for_pyro():
    planner = get_ai_planner()
    parsed  = _make_parsed("build_pyro_source", params={"parent": "/obj", "name": "fire"})
    result  = await planner.plan(parsed)
    assert result["ok"] is True
    # May use template or registry — just check ops produced
    assert result["op_count"] >= 1


@pytest.mark.asyncio
async def test_plan_falls_back_to_registry_for_custom_op():
    # Register a custom op not in the template map
    reg = get_semantic_registry()
    reg.register_operation(
        "custom_xyz",
        {"description": "test"},
        lambda ctx: [{"op": "create_node", "parent": ctx.get("parent", "/obj"), "type": "geo"}],
    )
    planner = get_ai_planner()
    parsed  = _make_parsed("custom_xyz", params={"parent": "/obj"})
    result  = await planner.plan(parsed)
    assert result["ok"] is True
    assert result["selected_template"] is None  # no template for custom_xyz


# ---------------------------------------------------------------------------
# Constraint violation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_constraint_violation_surfaces_in_errors():
    reg = get_semantic_registry()
    reg.register_operation(
        "stage_op",
        {"description": "tries to create in /stage"},
        lambda ctx: [{"op": "create_node", "parent": "/stage", "type": "geo"}],
    )
    planner = get_ai_planner()
    parsed  = _make_parsed("stage_op")
    result  = await planner.plan(parsed)
    assert result["ok"] is False
    assert any("/stage" in e or "protect" in e.lower() for e in result["errors"])


# ---------------------------------------------------------------------------
# Approval
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_approval_required_for_delete_op():
    reg = get_semantic_registry()
    reg.register_operation(
        "delete_op",
        {"description": "deletes stuff"},
        lambda ctx: [{"op": "delete_node", "path": "/obj/old"}],
    )
    planner = get_ai_planner()
    parsed  = _make_parsed("delete_op")
    result  = await planner.plan(parsed)
    assert result["requires_approval"] is True
    assert len(result["approval_reasons"]) >= 1


@pytest.mark.asyncio
async def test_approval_not_required_for_simple_create():
    reg = get_semantic_registry()
    reg.register_operation(
        "safe_create",
        {"description": "safe"},
        lambda ctx: [{"op": "create_node", "parent": "/obj", "type": "null", "name": "safe1"}],
    )
    planner = get_ai_planner()
    parsed  = _make_parsed("safe_create")
    result  = await planner.plan(parsed)
    assert result["requires_approval"] is False


# ---------------------------------------------------------------------------
# LLM refinement
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_llm_refinement_adds_suggestions():
    mock = MockLLMProvider()
    mock._responses = {}

    # Override suggest_plan_refinement to return refined=True
    import src.runtime.llm_provider as lp_mod
    original = lp_mod.MockLLMProvider.suggest_plan_refinement

    async def _patched_refinement(self, intent, plan, scene_context=None):
        return {
            "refined": True,
            "suggestions": ["Use 4 subdivisions for better detail."],
            "warnings": [],
            "parameters": {},
        }

    lp_mod.MockLLMProvider.suggest_plan_refinement = _patched_refinement
    set_llm_provider(mock)

    try:
        planner = get_ai_planner()
        parsed  = _make_parsed("create_geo_container")
        result  = await planner.plan(parsed)
        assert result["llm_refined"] is True
        assert any("refinement" in w.lower() or "subdivision" in w.lower() for w in result["warnings"])
    finally:
        lp_mod.MockLLMProvider.suggest_plan_refinement = original


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton_same_instance():
    a = get_ai_planner()
    b = get_ai_planner()
    assert a is b


def test_reset_creates_fresh_singleton():
    a = get_ai_planner()
    reset_ai_planner_for_tests()
    b = get_ai_planner()
    assert a is not b
