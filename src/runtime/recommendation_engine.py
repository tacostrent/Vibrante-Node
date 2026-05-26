"""
Recommendation Engine
=====================
Recommends semantic workflows, execution templates, orchestration strategies,
optimization paths, and dependency resolutions based on:
  • scene context
  • execution history (via RuntimeAnalytics)
  • semantic memory (via SemanticMemory)
  • capability registry
  • workflow templates

All recommendations are:
  • advisory — never auto-executed
  • inspectable — every recommendation includes reasoning
  • explainable — sources are named

This module NEVER:
  • executes operations or calls the bridge
  • modifies plans
  • calls TransactionManager or ExecutionScheduler

Public API:
    get_recommendation_engine() -> RecommendationEngine   (singleton)
    reset_recommendation_engine_for_tests()                (test isolation only)

    engine.recommend_workflow(intent, context=None) -> dict
    engine.recommend_template(intent, context=None) -> dict
    engine.recommend_strategy(operations, context=None) -> dict
    engine.recommend_dependency_resolution(conflicts) -> dict
    engine.stats() -> dict
"""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Built-in intent → template mappings
# ---------------------------------------------------------------------------

_INTENT_TEMPLATES: Dict[str, List[str]] = {
    "build_pyro_source":         ["pyro_source"],
    "setup_karma_renderer":      ["karma_render"],
    "export_to_usd":             ["usd_export"],
    "cache_geometry":            ["geometry_cache"],
    "asset_publish_scaffold":    ["asset_publish"],
    "solaris_lighting_setup":    ["solaris_lighting_setup"],
    "create_geo_container":      ["vfx_container"],
}

# Built-in strategy descriptions
_STRATEGIES: Dict[str, str] = {
    "dry_run_first":    "Validate without executing — zero side-effects.",
    "split_batch":      "Break large op batches into smaller transactions.",
    "use_template":     "Use a parameterised workflow template for known intent.",
    "wrap_transaction": "Wrap ops in a transaction with rollback_on_error.",
    "preview_plan":     "Use hou_mcp_execution_preview before committing.",
}


class RecommendationEngine:
    """Advisory recommendation engine for orchestration decisions."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._recommendation_count = 0

    # ------------------------------------------------------------------
    # Workflow recommendation
    # ------------------------------------------------------------------

    def recommend_workflow(
        self,
        intent: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Recommend a semantic workflow for the given intent.

        Returns:
            {
                "intent":            str,
                "recommended_op":    str | None,   # semantic operation id
                "confidence":        float,
                "reasoning":         [str, ...],
                "fallback_ops":      [str, ...],   # alternatives if primary unavailable
            }
        """
        with self._lock:
            self._recommendation_count += 1

        context = context or {}
        reasoning: List[str] = []
        confidence = 0.0
        recommended_op: Optional[str] = None
        fallback_ops: List[str] = []

        # Direct intent match
        try:
            from src.runtime.semantic_registry import get_semantic_registry
            reg = get_semantic_registry()
            all_ops = {op["operation_id"] for op in reg.list_operations()}
        except Exception:
            all_ops = set()

        if intent in all_ops:
            recommended_op = intent
            confidence = 0.9
            reasoning.append(f"Direct semantic operation match: '{intent}'.")
        else:
            # Partial keyword match
            for op_id in all_ops:
                if any(kw in op_id for kw in intent.lower().split("_")):
                    fallback_ops.append(op_id)
            if fallback_ops:
                recommended_op = fallback_ops[0]
                confidence = 0.6
                reasoning.append(f"Partial keyword match to '{recommended_op}'.")
                reasoning.append("Verify this is the correct semantic operation before executing.")
            else:
                confidence = 0.0
                reasoning.append(f"No semantic operation found for intent '{intent}'.")
                reasoning.append("Register a custom operation via get_semantic_registry().register_operation().")

        # Context hints
        caps = context.get("available_capabilities", [])
        if "karma" in intent.lower() and "karma" not in caps:
            reasoning.append("WARNING: 'karma' capability not in available_capabilities.")
            confidence *= 0.7

        return {
            "intent":         intent,
            "recommended_op": recommended_op,
            "confidence":     round(confidence, 3),
            "reasoning":      reasoning,
            "fallback_ops":   fallback_ops[1:],
        }

    # ------------------------------------------------------------------
    # Template recommendation
    # ------------------------------------------------------------------

    def recommend_template(
        self,
        intent: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Recommend the best workflow template for an intent.

        Returns:
            {
                "intent":             str,
                "recommended_template": str | None,
                "all_candidates":     [str, ...],
                "confidence":         float,
                "reasoning":          [str, ...],
            }
        """
        with self._lock:
            self._recommendation_count += 1

        context = context or {}
        reasoning: List[str] = []

        # Try semantic memory for historical best
        best_historical: Optional[str] = None
        try:
            from src.runtime.semantic_memory import get_semantic_memory
            mem = get_semantic_memory()
            patterns = mem.get_best_patterns(intent)
            for p in patterns:
                if p.get("pattern_type") == "execution_pattern":
                    meta = p.get("metadata", {})
                    t = meta.get("template_id", "")
                    if t:
                        best_historical = t
                        break
        except Exception:
            pass

        # Built-in mapping
        candidates = list(_INTENT_TEMPLATES.get(intent, []))

        # Also try available templates
        try:
            from src.runtime.workflow_templates import get_workflow_templates
            wt = get_workflow_templates()
            all_templates = {t["id"] for t in wt.list_templates()}
        except Exception:
            all_templates = set()

        intent_lower = intent.lower()
        for tid in all_templates:
            if tid not in candidates and intent_lower in tid.lower():
                candidates.append(tid)

        if best_historical and best_historical in all_templates:
            recommended = best_historical
            confidence = 0.85
            reasoning.append(f"Historically successful template: '{best_historical}'.")
        elif candidates:
            recommended = candidates[0]
            confidence = 0.75
            reasoning.append(f"Built-in template mapping for intent '{intent}'.")
        else:
            recommended = None
            confidence = 0.0
            reasoning.append(f"No template candidates for intent '{intent}'.")

        return {
            "intent":               intent,
            "recommended_template": recommended,
            "all_candidates":       candidates,
            "confidence":           round(confidence, 3),
            "reasoning":            reasoning,
        }

    # ------------------------------------------------------------------
    # Strategy recommendation
    # ------------------------------------------------------------------

    def recommend_strategy(
        self,
        operations: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Recommend an execution strategy for a batch of operations.

        Returns:
            {
                "strategies":   [{"id", "description", "priority"}, ...],
                "primary":      str,   # strategy id to apply first
                "reasoning":    [str, ...],
            }
        """
        with self._lock:
            self._recommendation_count += 1

        strategies: List[Dict[str, Any]] = []
        reasoning: List[str] = []
        context = context or {}

        op_count = len(operations)
        delete_count = sum(1 for op in operations
                           if isinstance(op, dict) and op.get("op") == "delete_node")
        risk_level = context.get("risk_level", "low")

        # Always recommend dry_run as baseline
        strategies.append({"id": "dry_run_first", "description": _STRATEGIES["dry_run_first"], "priority": 1})
        reasoning.append("dry_run_first is always the safest first step.")

        if delete_count > 0:
            strategies.append({"id": "wrap_transaction", "description": _STRATEGIES["wrap_transaction"], "priority": 2})
            reasoning.append(f"{delete_count} delete_node op(s) — transaction boundary required for safe rollback.")

        if op_count > 10:
            strategies.append({"id": "split_batch", "description": _STRATEGIES["split_batch"], "priority": 3})
            reasoning.append(f"Large batch ({op_count} ops) — split for lower rollback cost.")

        if risk_level == "high":
            strategies.append({"id": "preview_plan", "description": _STRATEGIES["preview_plan"], "priority": 2})
            reasoning.append("High-risk operations require preview before commit.")

        primary = strategies[0]["id"] if strategies else "dry_run_first"
        return {
            "strategies": strategies,
            "primary":    primary,
            "reasoning":  reasoning,
        }

    # ------------------------------------------------------------------
    # Dependency resolution recommendation
    # ------------------------------------------------------------------

    def recommend_dependency_resolution(
        self, conflicts: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Recommend resolutions for dependency conflicts.

        Each conflict: {"type", "op_index", "explanation"}

        Returns:
            {
                "resolutions": [{"conflict_index", "resolution", "notes"}, ...],
                "all_resolvable": bool,
            }
        """
        with self._lock:
            self._recommendation_count += 1

        resolutions: List[Dict[str, Any]] = []
        all_resolvable = True

        for i, conflict in enumerate(conflicts):
            ctype = conflict.get("type", "")
            explanation = conflict.get("explanation", "")

            if ctype == "self_connection":
                resolutions.append({
                    "conflict_index": i,
                    "resolution":     "Remove the self-connection op — it will fail validation.",
                    "notes":          "A node cannot be connected to itself.",
                })
            elif ctype == "missing_source_node":
                resolutions.append({
                    "conflict_index": i,
                    "resolution":     "Add a create_node op for the missing source before the connect_nodes op.",
                    "notes":          explanation,
                })
            elif ctype == "cycle":
                resolutions.append({
                    "conflict_index": i,
                    "resolution":     "Break the dependency cycle by removing one of the circular connections.",
                    "notes":          "Cyclic dependencies are not supported in the execution graph.",
                })
                all_resolvable = False
            else:
                resolutions.append({
                    "conflict_index": i,
                    "resolution":     "Review the conflict manually — no automatic resolution available.",
                    "notes":          explanation,
                })
                all_resolvable = False

        return {
            "resolutions":   resolutions,
            "all_resolvable": all_resolvable,
        }

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {"recommendation_count": self._recommendation_count}


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[RecommendationEngine] = None
_INSTANCE_LOCK = threading.Lock()


def get_recommendation_engine() -> RecommendationEngine:
    global _INSTANCE
    with _INSTANCE_LOCK:
        if _INSTANCE is None:
            _INSTANCE = RecommendationEngine()
        return _INSTANCE


def reset_recommendation_engine_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
