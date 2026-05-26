"""
Semantic Execution (Tier 2.75)
================================
DETERMINISTIC translation from a named semantic intent to a validated,
constrained, costed execution plan — and optional execution via the
transaction system.

Architecture:
    Intent (name + context)
        → SemanticRegistry.resolve_to_execution_plan()
        → CapabilityRegistry (required-capability check)
        → RuntimeConstraints.validate_transaction()
        → ValidationEngine.validate_operations()
        → ResourceEstimator.estimate_transaction()
        → Execution Plan (operations, metadata, warnings, cost)
        → [optional] TransactionManager (execute via houdini_runtime)
        → AuditStore (record)

This module contains ZERO LLM calls. Every step is a deterministic Python
function or registry lookup. The caller supplies the intent name; the
SemanticRegistry maps it to an op list; the remaining pipeline validates
and potentially executes it.

Public API:
    get_semantic_executor() -> SemanticExecutor   (singleton)
    reset_semantic_executor_for_tests()

    SemanticExecutor.translate(intent, context) -> dict
    SemanticExecutor.execute(intent, context, dry_run, auto_commit, rollback_on_error) -> dict
"""

import asyncio
import json
import threading
import time
from typing import Any, Dict, List, Optional

from src.runtime.semantic_registry  import get_semantic_registry
from src.runtime.capability_registry import get_capability_registry
from src.runtime.runtime_constraints import get_runtime_constraints
from src.runtime.resource_estimator  import get_resource_estimator
from src.runtime.scene_cache         import get_scene_cache


def _get_validation_engine():
    from src.runtime.validation_engine import get_validation_engine
    return get_validation_engine()


def _get_transaction_manager():
    from src.runtime import transaction_manager as tm_module
    return tm_module.get_transaction_manager()


def _get_houdini_runtime():
    from src.runtime import houdini_runtime
    return houdini_runtime


def _get_audit_store():
    from src.runtime.audit_store import get_audit_store
    return get_audit_store()


class SemanticExecutor:
    """Deterministic semantic intent translator + executor."""

    # ------------------------------------------------------------------
    # translate — plan without executing
    # ------------------------------------------------------------------

    async def translate(
        self,
        intent:  str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Translate a semantic intent to an execution plan.

        No mutations are performed. Returns a complete plan dict that can
        be inspected, modified, then passed to `execute`.

        Returns:
            {
                "ok":               bool,
                "intent":           str,
                "operations":       list[dict],
                "op_count":         int,
                "warnings":         list[str],
                "errors":           list[str],
                "resource_estimate": dict,
                "constraint_violations": list[dict],
                "validation_result": dict,
                "metadata":         dict,
            }
        """
        context = dict(context or {})
        warnings: List[str] = []
        errors:   List[str] = []

        # 1. Resolve intent to op list
        registry = get_semantic_registry()
        plan     = registry.resolve_to_execution_plan(intent, context)

        if not plan["ok"]:
            return {
                "ok":                    False,
                "intent":                intent,
                "operations":            [],
                "op_count":              0,
                "warnings":              warnings,
                "errors":                [plan["error"]],
                "resource_estimate":     {},
                "constraint_violations": [],
                "validation_result":     {},
                "metadata":              plan["metadata"],
            }

        ops      = plan["operations"]
        metadata = plan["metadata"]

        # 2. Required-capability check
        caps = get_capability_registry()
        for cap_id in metadata.get("required_capabilities", []):
            if not caps.supports(cap_id):
                warnings.append(
                    f"Semantic operation '{intent}' requires capability '{cap_id}' "
                    f"which is not currently registered."
                )

        # 3. Constraint validation
        constraint_result = get_runtime_constraints().validate_transaction(ops)
        constraint_violations = constraint_result.get("violations", [])
        if constraint_violations:
            errors.extend(
                f"Constraint '{v['policy_id']}': {v['message']}"
                for v in constraint_violations
            )

        # 4. Structural op validation
        validation_result = await _get_validation_engine().validate_operations(ops)
        for err in validation_result.get("errors", []):
            errors.append(f"Op[{err.get('index', '?')}] {err.get('op', '')}: {err.get('message', '')}")
        for warn in validation_result.get("warnings", []):
            warnings.append(f"Op[{warn.get('index', '?')}] {warn.get('op', '')}: {warn.get('message', '')}")

        # 5. Resource estimate
        resource_estimate = get_resource_estimator().estimate_transaction(ops)

        ok = len(errors) == 0

        return {
            "ok":                    ok,
            "intent":                intent,
            "operations":            ops,
            "op_count":              len(ops),
            "warnings":              warnings,
            "errors":                errors,
            "resource_estimate":     resource_estimate,
            "constraint_violations": constraint_violations,
            "validation_result":     validation_result,
            "metadata":              metadata,
        }

    # ------------------------------------------------------------------
    # execute — translate then run via transaction system
    # ------------------------------------------------------------------

    async def execute(
        self,
        intent:              str,
        context:             Optional[Dict[str, Any]] = None,
        dry_run:             bool = False,
        auto_commit:         bool = True,
        rollback_on_error:   bool = True,
        transaction_name:    Optional[str] = None,
    ) -> Dict[str, Any]:
        """Translate intent and execute via the transaction system.

        If `dry_run=True`, validates and estimates but performs no mutations.

        Returns:
            {
                "ok":                bool,
                "intent":            str,
                "transaction_id":    str | None,
                "status":            "validated" | "committed" | "rolled_back" | "failed",
                "replayed":          bool,
                "operations_executed": list[dict],
                "errors":            list[str],
                "warnings":          list[str],
                "graph_diff":        dict,
                "resource_estimate": dict,
                "report_json":       str,
            }
        """
        context = dict(context or {})

        # Translate
        plan = await self.translate(intent, context)

        if not plan["ok"]:
            return {
                "ok":                   False,
                "intent":               intent,
                "transaction_id":       None,
                "status":               "failed",
                "replayed":             False,
                "operations_executed":  [],
                "errors":               plan["errors"],
                "warnings":             plan["warnings"],
                "graph_diff":           {},
                "resource_estimate":    plan["resource_estimate"],
                "report_json":          json.dumps({
                    "intent": intent, "status": "failed",
                    "errors": plan["errors"], "warnings": plan["warnings"],
                }),
            }

        ops              = plan["operations"]
        resource_estimate = plan["resource_estimate"]
        warnings         = list(plan["warnings"])
        errors:   List[str] = []

        if dry_run:
            return {
                "ok":                   True,
                "intent":               intent,
                "transaction_id":       None,
                "status":               "validated",
                "replayed":             False,
                "operations_executed":  [],
                "errors":               [],
                "warnings":             warnings,
                "graph_diff":           {},
                "resource_estimate":    resource_estimate,
                "report_json":          json.dumps({
                    "intent": intent, "status": "validated",
                    "op_count": len(ops), "warnings": warnings,
                    "resource_estimate": resource_estimate,
                }),
            }

        # Execute via transaction system
        cache   = get_scene_cache()
        cache.clear_dirty_state()

        mgr    = _get_transaction_manager()
        hou_rt = _get_houdini_runtime()
        txn_name = transaction_name or f"semantic:{intent}"

        txn_id = await mgr.begin_transaction(txn_name, metadata={"intent": intent, "context": context})

        ops_executed: List[Dict[str, Any]] = []
        status       = "pending"
        final_err    = ""

        for op in ops:
            recorded = await hou_rt.execute_operation(op)
            await mgr.record_operation(txn_id, recorded)
            ops_executed.append(recorded)
            if recorded.get("status") == "failed":
                errors.append(recorded.get("error") or "op failed")
                if rollback_on_error:
                    await mgr.rollback_transaction(txn_id)
                    status    = "rolled_back"
                    final_err = errors[-1]
                    break
                else:
                    await mgr.mark_failed(txn_id, errors[-1])
                    status = "failed"
                    break

        if status == "pending":
            if auto_commit:
                await mgr.commit_transaction(txn_id)
                status = "committed"
            else:
                status = "committed"

        graph_diff = cache.get_dirty_nodes()
        replayed   = status == "committed"

        # Record semantic lineage in cache
        cache.record_semantic_execution(intent, txn_id, len(ops_executed))

        # Audit log (fire-and-forget, non-blocking)
        try:
            audit = _get_audit_store()
            await audit.log_transaction({
                "transaction_id":   txn_id,
                "intent":           intent,
                "context":          context,
                "status":           status,
                "op_count":         len(ops_executed),
                "graph_diff":       graph_diff,
                "resource_estimate": resource_estimate,
                "semantic_execution": True,
            })
        except Exception:
            pass

        report = {
            "intent":           intent,
            "transaction_id":   txn_id,
            "status":           status,
            "replayed":         replayed,
            "op_count":         len(ops_executed),
            "errors":           errors,
            "warnings":         warnings,
            "graph_diff":       graph_diff,
            "resource_estimate": resource_estimate,
        }

        return {
            "ok":                   replayed,
            "intent":               intent,
            "transaction_id":       txn_id,
            "status":               status,
            "replayed":             replayed,
            "operations_executed":  ops_executed,
            "errors":               errors,
            "warnings":             warnings,
            "graph_diff":           graph_diff,
            "resource_estimate":    resource_estimate,
            "report_json":          json.dumps(report),
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_EXECUTOR: Optional[SemanticExecutor] = None
_LOCK = threading.Lock()


def get_semantic_executor() -> SemanticExecutor:
    global _EXECUTOR
    with _LOCK:
        if _EXECUTOR is None:
            _EXECUTOR = SemanticExecutor()
        return _EXECUTOR


def reset_semantic_executor_for_tests() -> None:
    global _EXECUTOR
    with _LOCK:
        _EXECUTOR = None
