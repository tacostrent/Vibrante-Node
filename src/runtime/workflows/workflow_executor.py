"""
Workflow Executor (Tier 10 — Workflow Packs & Production Blueprints)
====================================================================
Orchestrates safe execution of a WorkflowBlueprint through the
transaction system.  This module NEVER mutates Houdini directly —
it builds transaction operation lists and delegates to the
transaction manager.

DESIGN RULES:
  1. MUST NOT call get_bridge() or mutate Houdini state.
  2. MUST NOT bypass ValidationEngine or RuntimeConstraints.
  3. MUST NOT bypass TransactionManager.
  4. All execution produces operations, previews, and rollback support.
  5. Never raises — errors captured in ExecutionResult.

Public API:
    ExecutionResult
    WorkflowExecutor
    get_workflow_executor()
    reset_workflow_executor_for_tests()
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.runtime.workflows.workflow_pack import WorkflowPack
from src.runtime.workflows.workflow_blueprint import (
    WorkflowBlueprint,
    get_workflow_blueprint,
)
from src.runtime.workflows.workflow_validator import (
    WorkflowValidator,
    get_workflow_validator,
)


@dataclass
class ExecutionResult:
    """Result of a workflow execution or preview."""
    ok:             bool
    workflow:       str
    environment:    str
    phase_results:  List[Dict[str, Any]] = field(default_factory=list)
    operations:     List[Dict[str, Any]] = field(default_factory=list)
    dry_run:        bool = False
    transaction_id: str  = ""
    status:         str  = "pending"   # pending | committed | rolled_back | failed | previewed
    errors:         List[str] = field(default_factory=list)
    warnings:       List[str] = field(default_factory=list)
    graph_diff:     Dict[str, Any] = field(default_factory=dict)
    report_json:    str  = ""
    executed_at:    float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok":             self.ok,
            "workflow":       self.workflow,
            "environment":    self.environment,
            "phase_results":  self.phase_results,
            "operations":     self.operations,
            "dry_run":        self.dry_run,
            "transaction_id": self.transaction_id,
            "status":         self.status,
            "errors":         self.errors,
            "warnings":       self.warnings,
            "graph_diff":     self.graph_diff,
            "report_json":    self.report_json,
            "executed_at":    self.executed_at,
        }


class WorkflowExecutor:
    """Orchestrates workflow blueprint execution through the transaction system."""

    def __init__(self) -> None:
        self._execution_count = 0
        self._lock = threading.Lock()

    # -----------------------------------------------------------------
    def preview_execution(self, pack: WorkflowPack) -> Dict[str, Any]:
        """
        Dry-run: build blueprint + execution plan without mutating anything.
        Returns the plan with phase details and complexity estimate.
        """
        builder = get_workflow_blueprint()
        blueprint = builder.build_blueprint(pack)
        if not blueprint.get("ok"):
            return {
                "ok":      False,
                "errors":  blueprint.get("errors", []),
                "workflow": pack.name,
            }

        plan = builder.generate_execution_plan(blueprint)

        validator = get_workflow_validator()
        pack_report = validator.validate_pack(pack)
        plan_report = validator.validate_execution_plan(plan)

        return {
            "ok":                    True,
            "workflow":              pack.name,
            "environment":           pack.environment_type,
            "phases":                blueprint.get("phases", []),
            "phase_details":         blueprint.get("phase_details", []),
            "operations":            plan.get("operations", []),
            "op_count":              plan.get("op_count", 0),
            "estimated_complexity":  blueprint.get("estimated_complexity", "moderate"),
            "validation":            pack_report.to_dict(),
            "plan_validation":       plan_report.to_dict(),
            "blueprint_id":          blueprint.get("blueprint_id", ""),
        }

    # -----------------------------------------------------------------
    def generate_transaction_plan(self, pack: WorkflowPack) -> Dict[str, Any]:
        """
        Generate a transaction-ready plan dict from a pack.
        This is the data structure that TransactionManager.begin_transaction
        + execute_operation would consume.
        """
        builder = get_workflow_blueprint()
        blueprint = builder.build_blueprint(pack)
        if not blueprint.get("ok"):
            return {"ok": False, "errors": blueprint.get("errors", [])}
        return builder.generate_execution_plan(blueprint)

    # -----------------------------------------------------------------
    def execute_pack(
        self,
        pack:               WorkflowPack,
        dry_run:            bool = False,
        rollback_on_error:  bool = True,
        auto_commit:        bool = True,
    ) -> ExecutionResult:
        """
        Execute a WorkflowPack safely.

        All execution routes through:
          1. Pack + plan validation
          2. TransactionManager.begin_transaction
          3. houdini_runtime.execute_operation per op
          4. Commit or rollback

        Returns ExecutionResult with full audit trail.
        """
        with self._lock:
            self._execution_count += 1

        txn_id = str(uuid.uuid4())

        # Step 1: Build plan
        plan = self.generate_transaction_plan(pack)
        if not plan.get("ok"):
            return ExecutionResult(
                ok=False, workflow=pack.name, environment=pack.environment_type,
                status="failed", errors=plan.get("errors", []),
                transaction_id=txn_id, dry_run=dry_run,
            )

        # Step 2: Validate
        validator = get_workflow_validator()
        pack_report = validator.validate_pack(pack)
        plan_report = validator.validate_execution_plan(plan)
        all_errors = pack_report.errors + plan_report.errors
        all_warnings = pack_report.warnings + plan_report.warnings

        if all_errors:
            return ExecutionResult(
                ok=False, workflow=pack.name, environment=pack.environment_type,
                status="failed", errors=all_errors, warnings=all_warnings,
                operations=plan.get("operations", []),
                transaction_id=txn_id, dry_run=dry_run,
            )

        # Step 3: Dry-run path
        if dry_run:
            return ExecutionResult(
                ok=True, workflow=pack.name, environment=pack.environment_type,
                operations=plan.get("operations", []),
                status="previewed", dry_run=True,
                transaction_id=txn_id, warnings=all_warnings,
                report_json=self._build_report(pack, plan, "previewed", [], []),
            )

        # Step 4: Live execution through TransactionManager
        ops = plan.get("operations", [])
        phase_results: List[Dict[str, Any]] = []
        executed_ops: List[Dict[str, Any]] = []
        exec_errors: List[str] = []

        try:
            from src.runtime import transaction_manager as tm_mod
            from src.runtime import houdini_runtime as hr_mod

            txn_name = f"workflow_{pack.name}_{txn_id[:8]}"
            tm       = tm_mod.get_transaction_manager()

            # Clear dirty state so graph_diff reflects this workflow only
            from src.runtime.scene_cache import get_scene_cache
            get_scene_cache().clear_dirty_state()

            actual_txn_id = tm.begin_transaction(
                txn_name,
                metadata={"pack": pack.name, "env": pack.environment_type},
            )

            for op in ops:
                try:
                    op_result = hr_mod.execute_operation(op)
                    tm.record_operation(actual_txn_id, op_result)
                    executed_ops.append(op_result)
                    phase_results.append({
                        "op":     op.get("op"),
                        "status": op_result.get("status", "ok"),
                    })
                    if op_result.get("status") == "failed":
                        exec_errors.append(op_result.get("error", "op failed"))
                        if rollback_on_error:
                            break
                except Exception as exc:
                    exec_errors.append(str(exc))
                    if rollback_on_error:
                        break

            if exec_errors and rollback_on_error:
                tm.rollback_transaction(actual_txn_id)
                status = "rolled_back"
            elif exec_errors:
                tm.mark_failed(actual_txn_id, exec_errors[0])
                status = "failed"
            elif auto_commit:
                tm.commit_transaction(actual_txn_id)
                status = "committed"
            else:
                status = "pending"

            graph_diff = get_scene_cache().get_dirty_nodes()

        except ImportError:
            # Houdini runtime not available — return plan-only result
            status = "failed"
            exec_errors = ["houdini_runtime not available — bridge required for execution"]
            graph_diff = {}

        ok = (status in ("committed", "pending")) and not exec_errors
        return ExecutionResult(
            ok=ok, workflow=pack.name, environment=pack.environment_type,
            phase_results=phase_results, operations=executed_ops,
            status=status, errors=exec_errors, warnings=all_warnings,
            transaction_id=txn_id, dry_run=False, graph_diff=graph_diff,
            report_json=self._build_report(pack, plan, status, exec_errors, all_warnings),
        )

    # -----------------------------------------------------------------
    def execute_phase(
        self, pack: WorkflowPack, phase_name: str
    ) -> Dict[str, Any]:
        """Execute a single phase of the workflow."""
        builder   = get_workflow_blueprint()
        blueprint = builder.build_blueprint(pack)
        if not blueprint.get("ok"):
            return {"ok": False, "errors": blueprint.get("errors", [])}

        phase_map = {p["phase_name"]: p for p in blueprint.get("phase_details", [])}
        phase     = phase_map.get(phase_name)
        if not phase:
            return {"ok": False, "errors": [f"phase '{phase_name}' not in blueprint"]}

        return {
            "ok":        True,
            "phase":     phase_name,
            "operations": phase.get("operations", []),
            "op_count":  len(phase.get("operations", [])),
        }

    # -----------------------------------------------------------------
    def estimate_runtime_cost(self, pack: WorkflowPack) -> Dict[str, Any]:
        """Estimate the cost of running the pack (no bridge calls)."""
        preview = self.preview_execution(pack)
        op_count    = preview.get("op_count", 0)
        complexity  = preview.get("estimated_complexity", "moderate")

        # Heuristic seconds per op by complexity
        secs_per_op = {"simple": 0.5, "moderate": 1.0, "complex": 2.0, "epic": 3.0}
        estimated   = op_count * secs_per_op.get(complexity, 1.0)

        return {
            "op_count":           op_count,
            "complexity":         complexity,
            "estimated_secs":     estimated,
            "memory_impact":      "medium" if complexity in ("complex", "epic") else "low",
            "rollback_supported": True,
        }

    # -----------------------------------------------------------------
    def _build_report(
        self,
        pack:     WorkflowPack,
        plan:     Dict[str, Any],
        status:   str,
        errors:   List[str],
        warnings: List[str],
    ) -> str:
        import json
        return json.dumps({
            "workflow":      pack.name,
            "environment":   pack.environment_type,
            "status":        status,
            "op_count":      plan.get("op_count", 0),
            "complexity":    plan.get("complexity", "moderate"),
            "errors":        errors,
            "warnings":      warnings,
        }, sort_keys=True)

    def stats(self) -> Dict[str, Any]:
        return {"execution_count": self._execution_count}


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[WorkflowExecutor] = None
_lock = threading.Lock()


def get_workflow_executor() -> WorkflowExecutor:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = WorkflowExecutor()
    return _instance


def reset_workflow_executor_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
