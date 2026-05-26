"""
AI Planning Engine (Tier 3)
============================
Generate semantic execution plans from a parsed intent + contextual analysis.

The planner is DETERMINISTIC by default:
  - Uses SemanticRegistry, WorkflowTemplates, RuntimeConstraints, ResourceEstimator
  - An optional LLM provider (llm_provider.py) can suggest plan refinements
  - LLM suggestions are advisory only; they never bypass constraint/validation
  - The planner NEVER executes operations or mutates Houdini state

Input:
  - parsed intent dict (from intent_parser.py)
  - context analysis dict (from contextual_reasoning.py)
  - optional scene_context (from houdini_runtime.scene_context)

Output: a plan dict ready for SemanticExecutor.execute() or dry-run preview

Public API:
    get_ai_planner() -> AIPlanner
    reset_ai_planner_for_tests()

    AIPlanner.plan(parsed_intent, context_analysis, scene_context=None) -> dict
"""

import threading
import uuid
import time
from typing import Any, Dict, List, Optional

from src.runtime.semantic_registry  import get_semantic_registry
from src.runtime.workflow_templates  import get_workflow_templates
from src.runtime.runtime_constraints import get_runtime_constraints
from src.runtime.resource_estimator  import get_resource_estimator
from src.runtime.llm_provider        import get_llm_provider

# Risk thresholds that automatically flag a plan for approval
_APPROVAL_RISK_THRESHOLD   = "high"
_APPROVAL_COST_THRESHOLD   = 0.8   # estimated_cook_cost above this → requires_approval
_APPROVAL_OP_COUNT         = 20    # plan with > N ops → requires_approval
_DESTRUCTIVE_OPS           = frozenset({"delete_node"})


def _select_strategy(
    intent:           str,
    context_analysis: Dict[str, Any],
    parameters:       Dict[str, Any],
) -> Dict[str, Any]:
    """Decide the best execution strategy: extend existing vs create new."""
    existing = context_analysis.get("existing_workflows", [])
    recommended = context_analysis.get("recommended_actions", [])

    if "extend_existing" in recommended and existing:
        best = existing[0]
        return {
            "strategy":    "extend_existing",
            "target_path": best.get("path", ""),
            "source":      best.get("source", ""),
            "rationale":   f"Existing {intent} workflow detected; extending it is safer than duplication.",
        }

    return {
        "strategy":  "create_new",
        "target_path": parameters.get("parent", "/obj"),
        "source":      "none",
        "rationale":   "No existing workflow detected; creating new.",
    }


def _build_template_params(
    intent:           str,
    parameters:       Dict[str, Any],
    strategy:         Dict[str, Any],
) -> Dict[str, str]:
    """Merge intent parameters into template variable format (all strings)."""
    params: Dict[str, str] = {}

    # Intent-level parameters
    for k, v in parameters.items():
        params[k] = str(v)

    # Defaults from strategy
    if "parent" not in params:
        params["parent"] = strategy.get("target_path", "/obj")

    # Intent-specific defaults
    defaults: Dict[str, Dict[str, str]] = {
        "build_pyro_source": {
            "name":   "pyro_src",
            "style":  "fire",
        },
        "create_geo_container": {
            "name": "geo1",
        },
        "setup_karma_renderer": {
            "name":       "karma1",
            "stage_path": "/stage",
        },
        "export_to_usd": {
            "name":        "usd_export",
            "output_path": "$HIP/export/scene.usd",
        },
        "cache_geometry": {
            "name":        "filecache1",
            "output_path": "$HIP/cache/$OS.$F4.bgeo.sc",
        },
        "asset_publish_scaffold": {
            "name": "asset_root",
        },
        "solaris_lighting_setup": {
            "name":       "lighting_rig",
            "stage_path": "/stage",
        },
    }
    for key, val in defaults.get(intent, {}).items():
        params.setdefault(key, val)

    return params


def _assess_approval(
    ops:              List[Dict[str, Any]],
    resource_estimate: Dict[str, Any],
    constraint_result: Dict[str, Any],
    context_analysis:  Dict[str, Any],
) -> Dict[str, Any]:
    """Return approval assessment: requires_approval + reasons."""
    reasons: List[str] = []

    risk = resource_estimate.get("risk_level", "low")
    if risk == _APPROVAL_RISK_THRESHOLD:
        reasons.append(f"Risk level is '{risk}'.")

    cook_cost = resource_estimate.get("estimated_cook_cost", 0.0)
    if cook_cost > _APPROVAL_COST_THRESHOLD:
        reasons.append(f"Estimated cook cost {cook_cost:.2f} exceeds threshold {_APPROVAL_COST_THRESHOLD}.")

    if len(ops) > _APPROVAL_OP_COUNT:
        reasons.append(f"Plan contains {len(ops)} operations (threshold {_APPROVAL_OP_COUNT}).")

    destructive = [op for op in ops if op.get("op") in _DESTRUCTIVE_OPS]
    if destructive:
        reasons.append(f"{len(destructive)} destructive operation(s) detected (delete_node).")

    violations = constraint_result.get("violations", [])
    if violations:
        reasons.append(f"{len(violations)} constraint violation(s) detected.")

    conflicts = context_analysis.get("conflicts", [])
    if conflicts:
        reasons.append(f"{len(conflicts)} dependency conflict(s) in scene.")

    requires_approval = len(reasons) > 0
    return {
        "requires_approval": requires_approval,
        "approval_reasons":  reasons,
    }


class AIPlanner:
    """Generate validated execution plans from parsed intents.

    Never executes operations. Never mutates state. Returns plans that can
    be submitted to SemanticExecutor.execute() or inspected/approved first.
    """

    async def plan(
        self,
        parsed_intent:    Dict[str, Any],
        context_analysis: Optional[Dict[str, Any]] = None,
        scene_context:    Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate an execution plan for the given parsed intent.

        Args:
            parsed_intent:    Output of IntentParser.parse().
            context_analysis: Output of ContextualReasoner.analyze().
            scene_context:    Optional scene snapshot (from houdini_runtime).

        Returns:
            {
                "plan_id":              str,
                "ok":                   bool,
                "intent":               str | None,
                "confidence":           float,
                "selected_template":    str | None,
                "execution_strategy":   dict,
                "operations":           list[dict],
                "op_count":             int,
                "parameters":           dict,
                "warnings":             list[str],
                "errors":               list[str],
                "requires_approval":    bool,
                "approval_reasons":     list[str],
                "resource_estimate":    dict,
                "constraint_result":    dict,
                "reasoning":            list[str],
                "llm_refined":          bool,
                "timestamp":            float,
            }
        """
        plan_id  = str(uuid.uuid4())
        ts       = time.time()
        warnings: List[str] = []
        errors:   List[str] = []
        reasoning: List[str] = []

        context_analysis = dict(context_analysis or {})
        parsed_intent    = dict(parsed_intent)

        intent     = parsed_intent.get("intent")
        parameters = dict(parsed_intent.get("parameters", {}))
        confidence = float(parsed_intent.get("confidence", 0.0))

        # --- No intent found ---
        if not intent:
            return {
                "plan_id":            plan_id,
                "ok":                 False,
                "intent":             None,
                "confidence":         confidence,
                "selected_template":  None,
                "execution_strategy": {},
                "operations":         [],
                "op_count":           0,
                "parameters":         parameters,
                "warnings":           warnings,
                "errors":             ["No semantic intent could be resolved from the prompt."],
                "requires_approval":  False,
                "approval_reasons":   [],
                "resource_estimate":  {},
                "constraint_result":  {},
                "reasoning":          ["Intent parser returned no intent."],
                "llm_refined":        False,
                "timestamp":          ts,
            }

        # --- Ambiguity warning ---
        if parsed_intent.get("ambiguous"):
            alts = parsed_intent.get("alternatives", [])
            alt_labels = ", ".join(a.get("intent", "") for a in alts[:2])
            warnings.append(
                f"Intent '{intent}' is ambiguous with: {alt_labels}. "
                "Proceeding with best match — verify the plan before executing."
            )
        reasoning.append(f"Resolved intent: '{intent}' (confidence={confidence:.2f})")

        # --- Select strategy ---
        strategy = _select_strategy(intent, context_analysis, parameters)
        reasoning.append(f"Execution strategy: {strategy['strategy']} — {strategy['rationale']}")

        # --- Optimization suggestions from context ---
        for sug in context_analysis.get("optimization_suggestions", []):
            warnings.append(f"Optimization hint: {sug}")

        # --- Resolve template parameters ---
        template_params = _build_template_params(intent, parameters, strategy)

        # --- Resolve ops: try workflow template first, then semantic registry ---
        wt    = get_workflow_templates()
        ops: List[Dict[str, Any]] = []
        selected_template: Optional[str] = None

        # Map intent id to template id (they share names by convention)
        template_map: Dict[str, str] = {
            "build_pyro_source":       "pyro_source",
            "setup_karma_renderer":    "karma_render",
            "export_to_usd":           "usd_export",
            "cache_geometry":          "geometry_cache",
            "asset_publish_scaffold":  "asset_publish",
            "solaris_lighting_setup":  "solaris_lighting_setup",
            "create_geo_container":    "vfx_container",
        }

        template_id = template_map.get(intent)
        if template_id and wt.get_template(template_id):
            try:
                ops = wt.apply_template(template_id, template_params)
                selected_template = template_id
                reasoning.append(f"Resolved via workflow template '{template_id}': {len(ops)} op(s).")
            except Exception as exc:
                warnings.append(f"Workflow template '{template_id}' failed: {exc}. Falling back to semantic registry.")

        if not ops:
            reg  = get_semantic_registry()
            plan_data = reg.resolve_to_execution_plan(intent, template_params)
            if plan_data["ok"]:
                ops = plan_data["operations"]
                reasoning.append(f"Resolved via semantic registry: {len(ops)} op(s).")
            else:
                errors.append(f"Could not resolve intent '{intent}': {plan_data.get('error', 'unknown error')}")

        # --- Constraint check ---
        constraint_result = get_runtime_constraints().validate_transaction(ops) if ops else {"valid": True, "violations": []}
        for violation in constraint_result.get("violations", []):
            errors.append(f"Constraint '{violation.get('policy_id', '?')}': {violation.get('message', '')}")

        # --- Resource estimate ---
        resource_estimate = get_resource_estimator().estimate_transaction(ops) if ops else {}

        # --- Approval assessment ---
        approval = _assess_approval(ops, resource_estimate, constraint_result, context_analysis)

        # --- Optional LLM refinement ---
        llm_refined = False
        provider = get_llm_provider()
        if ops and provider.is_available and provider.provider_name != "noop":
            try:
                refinement = await provider.suggest_plan_refinement(
                    intent,
                    {
                        "operations": ops,
                        "parameters": template_params,
                        "strategy":   strategy,
                    },
                    scene_context,
                )
                if refinement.get("refined"):
                    for sug in refinement.get("suggestions", []):
                        warnings.append(f"LLM refinement: {sug}")
                    for warn in refinement.get("warnings", []):
                        warnings.append(f"LLM warning: {warn}")
                    llm_refined = True
                    reasoning.append(f"LLM ({provider.provider_name}) provided refinement suggestions.")
            except Exception as exc:
                warnings.append(f"LLM plan refinement failed (non-fatal): {exc}")

        ok = len(errors) == 0

        return {
            "plan_id":            plan_id,
            "ok":                 ok,
            "intent":             intent,
            "confidence":         confidence,
            "selected_template":  selected_template,
            "execution_strategy": strategy,
            "operations":         ops,
            "op_count":           len(ops),
            "parameters":         template_params,
            "warnings":           warnings,
            "errors":             errors,
            "requires_approval":  approval["requires_approval"],
            "approval_reasons":   approval["approval_reasons"],
            "resource_estimate":  resource_estimate,
            "constraint_result":  constraint_result,
            "reasoning":          reasoning,
            "llm_refined":        llm_refined,
            "timestamp":          ts,
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_PLANNER: Optional[AIPlanner] = None
_LOCK = threading.Lock()


def get_ai_planner() -> AIPlanner:
    global _PLANNER
    with _LOCK:
        if _PLANNER is None:
            _PLANNER = AIPlanner()
        return _PLANNER


def reset_ai_planner_for_tests() -> None:
    global _PLANNER
    with _LOCK:
        _PLANNER = None
