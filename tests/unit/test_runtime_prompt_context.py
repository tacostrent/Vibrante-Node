"""
tests/unit/test_runtime_prompt_context.py
==========================================
Unit tests for src.runtime.runtime_prompt_context.
"""

import pytest

from src.runtime.runtime_prompt_context import (
    get_contextual_prompt,
    get_execution_rules_block,
    get_recommended_flow_block,
    get_scene_context_block,
    get_system_prompt,
    get_tool_guide,
)
from src.runtime.runtime_identity import (
    EXECUTION_RULES,
    MCP_TOOL_NAMES,
    RECOMMENDED_EXECUTION_FLOW,
    RUNTIME_NAME,
    RUNTIME_TYPE,
)


# ---------------------------------------------------------------------------
# get_execution_rules_block
# ---------------------------------------------------------------------------

def test_execution_rules_block_is_string():
    assert isinstance(get_execution_rules_block(), str)


def test_execution_rules_block_contains_header():
    block = get_execution_rules_block()
    assert "Execution Rules" in block


def test_execution_rules_block_contains_all_rules():
    block = get_execution_rules_block()
    for rule in EXECUTION_RULES:
        # Each rule is bullet-prefixed; check the core text
        assert rule[:30] in block


def test_execution_rules_count_in_block():
    block  = get_execution_rules_block()
    bullets = [line for line in block.splitlines() if line.strip().startswith("-")]
    assert len(bullets) == len(EXECUTION_RULES)


# ---------------------------------------------------------------------------
# get_recommended_flow_block
# ---------------------------------------------------------------------------

def test_recommended_flow_block_is_string():
    assert isinstance(get_recommended_flow_block(), str)


def test_recommended_flow_block_contains_header():
    block = get_recommended_flow_block()
    assert "Preferred Execution Flow" in block


def test_recommended_flow_block_has_8_steps():
    block = get_recommended_flow_block()
    steps = [line for line in block.splitlines() if line.strip().startswith(("1.", "2.", "3.", "4.", "5.", "6.", "7.", "8."))]
    assert len(steps) == len(RECOMMENDED_EXECUTION_FLOW)


# ---------------------------------------------------------------------------
# get_tool_guide
# ---------------------------------------------------------------------------

def test_tool_guide_is_string():
    assert isinstance(get_tool_guide(), str)


def test_tool_guide_contains_all_mcp_tools():
    guide = get_tool_guide()
    for tool_name in MCP_TOOL_NAMES:
        assert tool_name in guide


def test_tool_guide_has_category_headers():
    guide = get_tool_guide()
    for header in ("RUNTIME:", "KNOWLEDGE:", "PLANNING:", "EXECUTION:"):
        assert header in guide


# ---------------------------------------------------------------------------
# get_system_prompt
# ---------------------------------------------------------------------------

def test_system_prompt_is_string():
    assert isinstance(get_system_prompt(), str)


def test_system_prompt_contains_runtime_name():
    prompt = get_system_prompt()
    assert RUNTIME_NAME in prompt


def test_system_prompt_contains_runtime_type():
    prompt = get_system_prompt()
    assert RUNTIME_TYPE in prompt


def test_system_prompt_contains_execution_rules():
    prompt = get_system_prompt()
    assert "Execution Rules" in prompt


def test_system_prompt_contains_flow():
    prompt = get_system_prompt()
    assert "Preferred Execution Flow" in prompt


def test_system_prompt_contains_tool_guide():
    prompt = get_system_prompt()
    assert "Available MCP Tools" in prompt


def test_system_prompt_mentions_initialize_first():
    prompt = get_system_prompt()
    assert "initialize_runtime_context" in prompt


def test_system_prompt_mentions_preview_before_execute():
    prompt = get_system_prompt()
    assert "preview_execution" in prompt
    assert "execute_workflow_transaction" in prompt
    # preview should appear before execute in the prompt
    assert prompt.index("preview_execution") < prompt.index("execute_workflow_transaction")


def test_system_prompt_no_direct_houdini():
    prompt = get_system_prompt()
    assert "raw Houdini API" in prompt or "direct Houdini" in prompt


def test_system_prompt_idempotent():
    p1 = get_system_prompt()
    p2 = get_system_prompt()
    assert p1 == p2


# ---------------------------------------------------------------------------
# get_scene_context_block
# ---------------------------------------------------------------------------

def test_scene_context_block_none_input():
    result = get_scene_context_block(None)
    assert "not available" in result.lower()


def test_scene_context_block_empty_dict():
    result = get_scene_context_block({})
    assert "not available" in result.lower()


def test_scene_context_block_with_scene():
    ctx = {
        "scene": {
            "hip_file": "/home/user/test.hip",
            "houdini_version": "20.5",
            "frame": 24,
            "frame_range": [1, 240],
        }
    }
    result = get_scene_context_block(ctx)
    assert "test.hip" in result
    assert "20.5"     in result
    assert "24"       in result


def test_scene_context_block_with_networks():
    ctx = {
        "networks": {
            "obj": [
                {"name": "geo1"},
                {"name": "geo2"},
            ]
        }
    }
    result = get_scene_context_block(ctx)
    assert "obj" in result
    assert "geo1" in result


def test_scene_context_block_truncates_long_networks():
    ctx = {
        "networks": {
            "obj": [{"name": f"geo{i}"} for i in range(10)]
        }
    }
    result = get_scene_context_block(ctx)
    assert "+5 more" in result


def test_scene_context_block_with_selection():
    ctx = {
        "selection": [
            {"path": "/obj/my_geo", "type": "geo"}
        ]
    }
    result = get_scene_context_block(ctx)
    assert "/obj/my_geo" in result
    assert "selection" in result


def test_scene_context_block_with_hdas():
    ctx = {
        "assets": {
            "hda_files": ["/path/to/a.hda", "/path/to/b.hda"]
        }
    }
    result = get_scene_context_block(ctx)
    assert "hda_files" in result
    assert "2 loaded" in result


# ---------------------------------------------------------------------------
# get_contextual_prompt
# ---------------------------------------------------------------------------

def test_contextual_prompt_no_scene():
    result = get_contextual_prompt()
    assert "Execution Rules" in result


def test_contextual_prompt_with_scene():
    ctx    = {"scene": {"hip_file": "/my/file.hip", "houdini_version": "20.5", "frame": 1, "frame_range": [1, 240]}}
    result = get_contextual_prompt(scene_context=ctx)
    assert "Execution Rules"  in result
    assert "file.hip"         in result


def test_contextual_prompt_shorter_than_system_prompt():
    p_sys = get_system_prompt()
    p_ctx = get_contextual_prompt()
    assert len(p_ctx) < len(p_sys)
