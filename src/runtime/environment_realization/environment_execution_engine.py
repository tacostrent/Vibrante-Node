"""
environment_execution_engine.py — §49 Structural Environment Realization
========================================================================
Houdini bridge adapter: executes an EnvironmentRealizationPlan by running
all transaction_ops through houdini_runtime.execute_operation().

This is the ONLY module in the environment_realization package that calls
the Houdini bridge. All other modules are pure planning/advisory.

Execution sequence per environment:
  1. create_node  "/obj" → subnet "env_<name>"         (container)
  2. For each element:
     create_node  container → geo "element_id"
     set_parms    node_path ← {tx, ty, tz, rx, ry, rz}
     set_display_flag       ← True
  3. layout_children  container

Public API:
    ExecutionRecord
    ExecutionResult
    EnvironmentExecutionEngine
    get_environment_execution_engine()
    reset_environment_execution_engine_for_tests()
"""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ExecutionRecord:
    op_index:  int
    op_type:   str
    node_path: str
    ok:        bool
    error:     str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "op_index":  self.op_index,
            "op_type":   self.op_type,
            "node_path": self.node_path,
            "ok":        self.ok,
            "error":     self.error,
        }


@dataclass
class ExecutionResult:
    environment:       str
    container_path:    str
    ops_total:         int = 0
    ops_committed:     int = 0
    ops_failed:        int = 0
    nodes_created:     int = 0
    nodes_displayed:   int = 0
    records:           List[ExecutionRecord] = field(default_factory=list)
    created_paths:     List[str] = field(default_factory=list)
    ok:     bool = True
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "environment":     self.environment,
            "container_path":  self.container_path,
            "ops_total":       self.ops_total,
            "ops_committed":   self.ops_committed,
            "ops_failed":      self.ops_failed,
            "nodes_created":   self.nodes_created,
            "nodes_displayed": self.nodes_displayed,
            "created_paths":   list(self.created_paths),
            "ok":              self.ok,
            "errors":          list(self.errors),
        }


class EnvironmentExecutionEngine:
    """
    Executes an EnvironmentRealizationPlan's transaction_ops against Houdini.

    Usage (async, from within a node execute() method):
        plan    = get_environment_realization_engine().realize("western_room")
        result  = await get_environment_execution_engine().execute(plan.to_dict())
        # result.nodes_created >= 13 for western_room
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    async def execute(
        self,
        plan: Dict[str, Any],
    ) -> ExecutionResult:
        """
        Execute all transaction_ops from an EnvironmentRealizationPlan.

        Args:
            plan: EnvironmentRealizationPlan.to_dict()

        Returns: ExecutionResult. Never raises.
        """
        try:
            return await self._execute(plan)
        except Exception as exc:
            env = plan.get("environment", "") if isinstance(plan, dict) else ""
            return ExecutionResult(
                environment=env,
                container_path=f"/obj/env_{env}",
                ok=False,
                errors=[f"EnvironmentExecutionEngine.execute failed: {exc}"],
            )

    async def _execute(self, plan: Dict[str, Any]) -> ExecutionResult:
        from src.runtime import houdini_runtime  # lazy — no bridge in planning path

        env = plan.get("environment", "unknown")
        env_safe = env.replace(" ", "_").replace("-", "_")
        container = f"/obj/env_{env_safe}"
        ops = plan.get("transaction_ops") or []

        result = ExecutionResult(
            environment=env,
            container_path=container,
            ops_total=len(ops),
        )

        for i, op in enumerate(ops):
            op_type = op.get("op", "")
            try:
                op_result = await houdini_runtime.execute_operation(op)
                status    = op_result.get("status", "failed")

                if status == "failed":
                    err = op_result.get("error", "unknown error")
                    result.ops_failed += 1
                    result.records.append(ExecutionRecord(
                        op_index=i, op_type=op_type,
                        node_path=self._op_path(op), ok=False, error=err,
                    ))
                    result.errors.append(f"op[{i}] {op_type}: {err}")
                else:
                    result.ops_committed += 1
                    path = (op_result.get("result") or {}).get("path", "")
                    if not path:
                        path = self._op_path(op)

                    record = ExecutionRecord(
                        op_index=i, op_type=op_type,
                        node_path=path, ok=True,
                    )
                    result.records.append(record)

                    if op_type == "create_node" and path:
                        result.nodes_created += 1
                        result.created_paths.append(path)
                    elif op_type == "set_display_flag":
                        result.nodes_displayed += 1

            except Exception as exc:
                result.ops_failed += 1
                result.errors.append(f"op[{i}] {op_type}: {exc}")
                result.records.append(ExecutionRecord(
                    op_index=i, op_type=op_type,
                    node_path=self._op_path(op),
                    ok=False, error=str(exc),
                ))

        result.ok = result.ops_failed == 0
        return result

    @staticmethod
    def _op_path(op: Dict[str, Any]) -> str:
        """Extract the most relevant path from an op dict for logging."""
        return (
            op.get("node") or op.get("path") or
            f"{op.get('parent','')}/{op.get('name','')}"
        )

    def execute_sync(
        self,
        plan: Dict[str, Any],
    ) -> ExecutionResult:
        """
        Synchronous wrapper — use inside non-async contexts.
        Runs the coroutine on a new event loop.
        Never raises.
        """
        try:
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(self.execute(plan))
            finally:
                loop.close()
        except Exception as exc:
            env = plan.get("environment", "") if isinstance(plan, dict) else ""
            return ExecutionResult(
                environment=env,
                container_path=f"/obj/env_{env}",
                ok=False,
                errors=[f"execute_sync failed: {exc}"],
            )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[EnvironmentExecutionEngine] = None
_lock = threading.Lock()


def get_environment_execution_engine() -> EnvironmentExecutionEngine:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = EnvironmentExecutionEngine()
    return _instance


def reset_environment_execution_engine_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
