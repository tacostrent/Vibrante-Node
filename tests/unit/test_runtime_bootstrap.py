"""
tests/unit/test_runtime_bootstrap.py
======================================
Unit tests for src.runtime.runtime_bootstrap.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.runtime.runtime_bootstrap import (
    get_available_operations,
    get_available_templates,
    get_bootstrap_data,
    get_runtime_capabilities,
    initialize_runtime,
)
from src.runtime.runtime_identity import (
    EXECUTION_RULES,
    MCP_TOOL_NAMES,
    RECOMMENDED_EXECUTION_FLOW,
    RUNTIME_IDENTITY,
    RUNTIME_NAME,
)


# ---------------------------------------------------------------------------
# initialize_runtime
# ---------------------------------------------------------------------------

def test_initialize_runtime_returns_dict():
    result = initialize_runtime()
    assert isinstance(result, dict)


def test_initialize_runtime_has_ok():
    result = initialize_runtime()
    assert result["ok"] is True


def test_initialize_runtime_has_initialized_at():
    result = initialize_runtime()
    assert "initialized_at" in result
    assert isinstance(result["initialized_at"], float)


def test_initialize_runtime_has_modules_list():
    result = initialize_runtime()
    assert "modules" in result
    assert isinstance(result["modules"], list)


def test_initialize_runtime_loads_at_least_some_modules():
    result = initialize_runtime()
    # At minimum, the stdlib modules (no heavy deps) should load
    assert len(result["modules"]) > 0


def test_initialize_runtime_ok_even_with_missing_modules():
    # Even if a module raises on import, ok stays True
    with patch(
        "src.runtime.runtime_bootstrap._warm",
        side_effect=lambda s, name, _: s.update({f"{name}_error": "forced"}),
    ):
        result = initialize_runtime()
    assert result["ok"] is True


# ---------------------------------------------------------------------------
# get_runtime_capabilities
# ---------------------------------------------------------------------------

def test_get_runtime_capabilities_returns_list():
    result = get_runtime_capabilities()
    assert isinstance(result, list)


def test_get_runtime_capabilities_graceful_on_error():
    with patch(
        "src.runtime.capability_registry.get_capability_registry",
        side_effect=RuntimeError("no registry"),
    ):
        result = get_runtime_capabilities()
    assert result == []


# ---------------------------------------------------------------------------
# get_available_templates
# ---------------------------------------------------------------------------

def test_get_available_templates_returns_list():
    result = get_available_templates()
    assert isinstance(result, list)


def test_get_available_templates_returns_strings():
    result = get_available_templates()
    for item in result:
        assert isinstance(item, str)


def test_get_available_templates_graceful_on_error():
    with patch(
        "src.runtime.workflow_templates.get_workflow_templates",
        side_effect=RuntimeError("boom"),
    ):
        result = get_available_templates()
    assert result == []


# ---------------------------------------------------------------------------
# get_available_operations
# ---------------------------------------------------------------------------

def test_get_available_operations_returns_list():
    result = get_available_operations()
    assert isinstance(result, list)


def test_get_available_operations_includes_builtins():
    result = get_available_operations()
    # The semantic registry ships with at least one built-in operation
    assert len(result) > 0


def test_get_available_operations_graceful_on_error():
    with patch(
        "src.runtime.semantic_registry.get_semantic_registry",
        side_effect=RuntimeError("boom"),
    ):
        result = get_available_operations()
    assert result == []


# ---------------------------------------------------------------------------
# get_bootstrap_data
# ---------------------------------------------------------------------------

def test_bootstrap_data_is_dict():
    data = get_bootstrap_data()
    assert isinstance(data, dict)


def test_bootstrap_has_runtime_name():
    data = get_bootstrap_data()
    assert data["runtime_name"] == RUNTIME_NAME


def test_bootstrap_has_execution_model():
    data = get_bootstrap_data()
    assert data["execution_model"] == RUNTIME_IDENTITY["execution_model"]


def test_bootstrap_has_runtime_rules():
    data = get_bootstrap_data()
    assert "runtime_rules" in data
    assert isinstance(data["runtime_rules"], list)
    assert len(data["runtime_rules"]) == len(EXECUTION_RULES)


def test_bootstrap_rules_match_identity():
    data = get_bootstrap_data()
    assert data["runtime_rules"] == EXECUTION_RULES


def test_bootstrap_has_recommended_flow():
    data = get_bootstrap_data()
    assert "recommended_execution_flow" in data
    assert isinstance(data["recommended_execution_flow"], list)


def test_bootstrap_flow_matches_identity():
    data = get_bootstrap_data()
    assert data["recommended_execution_flow"] == RECOMMENDED_EXECUTION_FLOW


def test_bootstrap_has_mcp_tools():
    data = get_bootstrap_data()
    assert "mcp_tools" in data
    assert isinstance(data["mcp_tools"], list)
    assert set(MCP_TOOL_NAMES) <= set(data["mcp_tools"])


def test_bootstrap_has_workflow_templates():
    data = get_bootstrap_data()
    assert "workflow_templates" in data
    assert isinstance(data["workflow_templates"], list)


def test_bootstrap_has_available_capabilities():
    data = get_bootstrap_data()
    assert "available_capabilities" in data
    assert isinstance(data["available_capabilities"], list)


def test_bootstrap_has_available_operations():
    data = get_bootstrap_data()
    assert "available_operations" in data
    assert isinstance(data["available_operations"], list)


def test_bootstrap_data_is_json_serialisable():
    import json
    data = get_bootstrap_data()
    dumped = json.dumps(data, default=str)
    assert isinstance(dumped, str)
