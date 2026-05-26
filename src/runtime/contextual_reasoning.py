"""
Contextual Reasoning Layer (Tier 3)
=====================================
Analyze the current runtime context BEFORE planning to avoid duplicating
existing work, identify conflicts, and surface optimization opportunities.

This module reads:
  - scene_cache (existing dirty state, semantic lineage, visualization data)
  - dependency_graph (inter-node relationships)
  - transaction_manager history (recent transactions)
  - capability_registry (available capabilities)

It does NOT:
  - make bridge calls
  - execute operations
  - mutate any state

Output is a structured analysis dict that the AI planner uses to adapt its
decisions (e.g., extend an existing pyro setup instead of creating a duplicate).

Public API:
    get_contextual_reasoner() -> ContextualReasoner
    reset_contextual_reasoner_for_tests()

    ContextualReasoner.analyze(intent, parameters, scene_context=None) -> dict
"""

import threading
from typing import Any, Dict, List, Optional

# Known workflow patterns: intent_id → node types that indicate the workflow exists
_WORKFLOW_INDICATORS: Dict[str, List[str]] = {
    "build_pyro_source":        ["pyro_source", "pyro", "smoke"],
    "setup_karma_renderer":     ["karma"],
    "export_to_usd":            ["usd", "usdrender"],
    "cache_geometry":           ["filecache", "alembic"],
    "asset_publish_scaffold":   ["INPUT", "OUTPUT"],
    "solaris_lighting_setup":   ["distantlight", "domelight"],
    "create_geo_container":     ["geo"],
}

# High-risk op combinations that should be flagged
_HIGH_RISK_OPS = frozenset({"delete_node", "cook_node"})


def _find_existing_workflows(
    intent:        str,
    dirty_state:   Dict[str, Any],
    lineage:       List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Return a list of detected existing workflows matching the intent."""
    existing: List[Dict[str, Any]] = []

    # Check semantic lineage for prior executions of this intent
    for record in lineage:
        if record.get("intent_id") == intent:
            existing.append({
                "type":        intent,
                "source":      "lineage",
                "txn_id":      record.get("txn_id", ""),
                "op_count":    record.get("op_count", 0),
                "description": f"Previously executed via transaction {record.get('txn_id', '')[:8]}",
            })

    # Check dirty state: if nodes with matching types were created in this session
    created_paths = dirty_state.get("created", [])
    indicators = _WORKFLOW_INDICATORS.get(intent, [])
    for path in created_paths:
        if any(ind.lower() in path.lower() for ind in indicators):
            existing.append({
                "type":        intent,
                "source":      "dirty_state",
                "path":        path,
                "description": f"Node {path} created in this session matches {intent} pattern",
            })

    return existing


def _detect_conflicts(
    intent:     str,
    parameters: Dict[str, Any],
    dep_graph:  Any,
) -> List[Dict[str, str]]:
    """Identify potential conflicts with the proposed plan."""
    conflicts: List[Dict[str, str]] = []

    # Check if target parent path has many downstream dependents
    parent = parameters.get("parent", "/obj")
    if dep_graph is not None:
        try:
            downstream = dep_graph.get_downstream(parent)
            if len(downstream) > 5:
                conflicts.append({
                    "type":    "dependency_chain",
                    "message": f"Parent {parent!r} has {len(downstream)} downstream dependents — "
                               "adding nodes here may trigger costly re-cooks",
                })
        except Exception:
            pass

    return conflicts


def _build_optimization_suggestions(
    existing:   List[Dict[str, Any]],
    intent:     str,
    parameters: Dict[str, Any],
) -> List[str]:
    """Return advisory suggestions for the planner."""
    suggestions: List[str] = []

    if existing:
        for e in existing[:2]:
            path = e.get("path", "")
            if path:
                suggestions.append(
                    f"Consider extending existing node at {path} "
                    f"instead of creating a new {intent} setup."
                )
            else:
                suggestions.append(
                    f"A {intent} workflow was previously executed in this session "
                    f"(txn: {e.get('txn_id', '')[:8]}). Verify it is not a duplicate."
                )

    return suggestions


def _classify_scene_complexity(
    dirty_state: Dict[str, Any],
    dep_graph:   Any,
) -> str:
    """Return 'low' | 'medium' | 'high' based on scene activity."""
    created  = len(dirty_state.get("created", []))
    modified = len(dirty_state.get("modified", []))
    deleted  = len(dirty_state.get("deleted", []))
    total_mutations = created + modified + deleted

    edge_count = 0
    if dep_graph is not None:
        try:
            edge_count = len(dep_graph.all_edges())
        except Exception:
            pass

    score = total_mutations + edge_count * 0.5
    if score >= 20:
        return "high"
    if score >= 5:
        return "medium"
    return "low"


class ContextualReasoner:
    """Analyze runtime context before planning. Stateless."""

    def analyze(
        self,
        intent:        str,
        parameters:    Optional[Dict[str, Any]] = None,
        scene_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Return a structured context analysis for the given intent.

        Args:
            intent:        The semantic operation id being planned.
            parameters:    Proposed parameters from the intent parser.
            scene_context: Optional explicit scene context dict.

        Returns:
            {
                "existing_workflows":        list[dict],
                "recommended_actions":       list[str],
                "conflicts":                 list[dict],
                "optimization_suggestions":  list[str],
                "scene_complexity":          "low" | "medium" | "high",
                "active_transactions":       int,
                "scene_summary":             str,
                "capabilities_available":    list[str],
            }
        """
        parameters = dict(parameters or {})

        # --- Gather data from runtime systems (no bridge calls) ---
        dirty_state  = {}
        lineage:     List[Dict[str, Any]] = []
        dep_graph    = None
        txn_history: List[Dict[str, Any]] = []
        active_txns  = 0
        cap_ids:     List[str] = []

        try:
            from src.runtime.scene_cache import get_scene_cache
            cache       = get_scene_cache()
            dirty_state = cache.get_dirty_nodes()
            lineage     = cache.get_semantic_lineage()
        except Exception:
            pass

        try:
            from src.runtime.dependency_graph import get_dependency_graph
            dep_graph = get_dependency_graph()
        except Exception:
            pass

        try:
            from src.runtime.transaction_manager import get_transaction_manager
            mgr         = get_transaction_manager()
            txn_history = mgr.get_history(limit=10)
            # Count pending
            active_txns = sum(1 for t in txn_history if t.get("status") == "pending")
        except Exception:
            pass

        try:
            from src.runtime.capability_registry import get_capability_registry
            caps    = get_capability_registry()
            cap_ids = [c["id"] for c in caps.query_capabilities()]
        except Exception:
            pass

        # --- Analyze ---
        existing_workflows = _find_existing_workflows(intent, dirty_state, lineage)
        conflicts          = _detect_conflicts(intent, parameters, dep_graph)
        suggestions        = _build_optimization_suggestions(existing_workflows, intent, parameters)
        scene_complexity   = _classify_scene_complexity(dirty_state, dep_graph)

        # Recommended actions
        recommended: List[str] = []
        if existing_workflows:
            recommended.append("extend_existing")
        else:
            recommended.append("create_new")
        if conflicts:
            recommended.append("review_dependencies")

        # Scene summary
        created  = len(dirty_state.get("created", []))
        modified = len(dirty_state.get("modified", []))
        deleted  = len(dirty_state.get("deleted", []))
        summary_parts = [f"Scene complexity: {scene_complexity}."]
        if created:
            summary_parts.append(f"{created} node(s) created this session.")
        if modified:
            summary_parts.append(f"{modified} node(s) modified.")
        if deleted:
            summary_parts.append(f"{deleted} node(s) deleted.")
        if existing_workflows:
            summary_parts.append(f"{len(existing_workflows)} existing {intent} workflow(s) detected.")
        if active_txns:
            summary_parts.append(f"{active_txns} pending transaction(s).")
        scene_summary = " ".join(summary_parts)

        return {
            "existing_workflows":       existing_workflows,
            "recommended_actions":      recommended,
            "conflicts":                conflicts,
            "optimization_suggestions": suggestions,
            "scene_complexity":         scene_complexity,
            "active_transactions":      active_txns,
            "scene_summary":            scene_summary,
            "capabilities_available":   cap_ids,
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_REASONER: Optional[ContextualReasoner] = None
_LOCK = threading.Lock()


def get_contextual_reasoner() -> ContextualReasoner:
    global _REASONER
    with _LOCK:
        if _REASONER is None:
            _REASONER = ContextualReasoner()
        return _REASONER


def reset_contextual_reasoner_for_tests() -> None:
    global _REASONER
    with _LOCK:
        _REASONER = None
