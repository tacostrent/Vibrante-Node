"""
Workflow Federation (Tier 4)
=============================
Allows workflows to span multiple runtimes, DCCs, and workers.  A federated
workflow is a directed acyclic graph of segments, each targeting a specific
DCC or runtime, with explicit dependency ordering between segments.

Execution:
  1. Topological sort of segments by declared dependencies.
  2. Each segment is dispatched to its target DCC via MultiDccRuntime
     or to a remote worker via DistributedRuntime.
  3. Segment results are collected; the overall workflow succeeds only
     when all segments commit.

SAFETY RULE: Each segment still goes through the full validation /
constraint / transaction pipeline for its target DCC.  The federation
layer is purely routing and ordering — it adds no execution authority.

Public API:
    get_workflow_federation() -> WorkflowFederation   (singleton)
    reset_workflow_federation_for_tests()

    WorkflowFederation.create_federated_workflow(name, segments, metadata) -> str
    WorkflowFederation.get_workflow(workflow_id) -> dict | None
    WorkflowFederation.execute_federated(workflow_id, dry_run) -> dict   (async)
    WorkflowFederation.get_status(workflow_id) -> dict | None
    WorkflowFederation.list_workflows(status) -> list[dict]
    WorkflowFederation.stats() -> dict
"""

import json
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

WORKFLOW_STATUSES = frozenset({"pending", "running", "completed", "failed", "partial"})
SEGMENT_STATUSES  = frozenset({"pending", "running", "completed", "failed", "skipped"})


def _topological_sort(segments: List[Dict[str, Any]]) -> List[str]:
    """Return segment ids in topological execution order.

    Raises ValueError if a cycle is detected.
    """
    seg_ids = {s["id"] for s in segments}
    deps    = {s["id"]: list(s.get("dependencies", [])) for s in segments}

    # Kahn's algorithm
    in_degree: Dict[str, int] = {sid: 0 for sid in seg_ids}
    for sid, dep_list in deps.items():
        for dep in dep_list:
            if dep in in_degree:
                in_degree[sid] = in_degree.get(sid, 0) + 1

    queue = [sid for sid, deg in in_degree.items() if deg == 0]
    order: List[str] = []

    while queue:
        node = queue.pop(0)
        order.append(node)
        for sid, dep_list in deps.items():
            if node in dep_list:
                in_degree[sid] -= 1
                if in_degree[sid] == 0:
                    queue.append(sid)

    if len(order) != len(seg_ids):
        raise ValueError("Cycle detected in federated workflow segment dependencies")
    return order


class WorkflowFederation:
    """Cross-runtime workflow orchestration with segment dependency ordering."""

    def __init__(self) -> None:
        self._lock      = threading.Lock()
        self._workflows: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Workflow creation
    # ------------------------------------------------------------------

    def create_federated_workflow(
        self,
        name:     str,
        segments: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create a federated workflow and return its workflow_id.

        Each segment dict must contain:
            id           — unique segment identifier
            name         — human label
            operations   — list of structured op dicts
            target_dcc   — DCC name hint (e.g. "houdini", "maya") or None
            dependencies — list of segment ids that must complete first

        Raises:
            ValueError: If segment ids are non-unique, or a dependency cycle
                        is detected.
        """
        if not name:
            raise ValueError("Workflow name must be non-empty")

        seg_ids = [s.get("id") for s in segments]
        if len(seg_ids) != len(set(seg_ids)):
            raise ValueError("Segment ids must be unique")
        if not seg_ids:
            raise ValueError("Workflow must have at least one segment")

        # Validate topological order (raises on cycle)
        _topological_sort(segments)

        workflow_id = str(uuid.uuid4())
        # Deep-copy segments and normalise
        norm_segments = []
        for s in segments:
            norm_segments.append({
                "id":           str(s["id"]),
                "name":         str(s.get("name", s["id"])),
                "operations":   list(s.get("operations", [])),
                "target_dcc":   s.get("target_dcc") or "houdini",
                "dependencies": list(s.get("dependencies", [])),
                "status":       "pending",
                "result":       None,
            })

        with self._lock:
            self._workflows[workflow_id] = {
                "id":         workflow_id,
                "name":       name,
                "segments":   norm_segments,
                "metadata":   dict(metadata or {}),
                "status":     "pending",
                "created_at": time.time(),
                "started_at": None,
                "ended_at":   None,
                "result":     None,
            }
        return workflow_id

    def get_workflow(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            w = self._workflows.get(workflow_id)
            return _deep_copy_workflow(w) if w else None

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def execute_federated(
        self,
        workflow_id: str,
        dry_run:     bool = False,
    ) -> Dict[str, Any]:
        """Execute a federated workflow in segment dependency order.

        Returns a result dict with per-segment outcomes.
        """
        from src.runtime.multi_dcc_runtime import get_multi_dcc_runtime

        with self._lock:
            wf = self._workflows.get(workflow_id)
        if wf is None:
            return {"ok": False, "error": f"Unknown workflow: {workflow_id!r}"}

        # Topological execution order
        try:
            order = _topological_sort(wf["segments"])
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}

        seg_by_id = {s["id"]: s for s in wf["segments"]}

        with self._lock:
            wf["status"]     = "running"
            wf["started_at"] = time.time()

        mdr = get_multi_dcc_runtime()
        segment_results: Dict[str, Any] = {}
        all_ok = True

        for seg_id in order:
            seg = seg_by_id[seg_id]
            with self._lock:
                seg["status"] = "running"

            ops        = seg.get("operations", [])
            target_dcc = seg.get("target_dcc", "houdini")

            try:
                result = await mdr.execute_for_dcc(target_dcc, ops, dry_run=dry_run)
            except Exception as exc:
                result = {
                    "ok": False, "status": "error",
                    "error": str(exc), "dcc": target_dcc,
                }

            seg_ok = result.get("ok", False)
            with self._lock:
                seg["status"] = "completed" if seg_ok else "failed"
                seg["result"] = result

            segment_results[seg_id] = result
            if not seg_ok:
                all_ok = False
                # Mark remaining segments as skipped
                remaining = order[order.index(seg_id) + 1:]
                with self._lock:
                    for rem_id in remaining:
                        seg_by_id[rem_id]["status"] = "skipped"
                break

        final_status = "completed" if all_ok else "failed"
        report = {
            "workflow_id":    workflow_id,
            "workflow_name":  wf["name"],
            "status":         final_status,
            "segment_count":  len(order),
            "segment_results": segment_results,
            "dry_run":        dry_run,
        }

        with self._lock:
            wf["status"]  = final_status
            wf["ended_at"] = time.time()
            wf["result"]  = report

        return {
            "ok":             all_ok,
            "workflow_id":    workflow_id,
            "status":         final_status,
            "segment_count":  len(order),
            "segments_ok":    sum(1 for r in segment_results.values() if r.get("ok")),
            "errors":         [r.get("error", "") for r in segment_results.values() if not r.get("ok")],
            "segment_results": segment_results,
            "report_json":    json.dumps(report, default=str),
        }

    # ------------------------------------------------------------------
    # Status query
    # ------------------------------------------------------------------

    def get_status(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        wf = self.get_workflow(workflow_id)
        if wf is None:
            return None
        return {
            "workflow_id":   workflow_id,
            "name":          wf["name"],
            "status":        wf["status"],
            "segment_count": len(wf["segments"]),
            "segments":      [
                {"id": s["id"], "name": s["name"], "status": s["status"]}
                for s in wf["segments"]
            ],
            "created_at": wf.get("created_at"),
            "started_at": wf.get("started_at"),
            "ended_at":   wf.get("ended_at"),
        }

    def list_workflows(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._lock:
            wfs = list(self._workflows.values())
        if status:
            wfs = [w for w in wfs if w["status"] == status]
        return [
            {
                "id":     w["id"],
                "name":   w["name"],
                "status": w["status"],
                "segment_count": len(w["segments"]),
                "created_at": w.get("created_at"),
            }
            for w in sorted(wfs, key=lambda w: w.get("created_at", 0))
        ]

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            by_status: Dict[str, int] = {}
            for w in self._workflows.values():
                s = w["status"]
                by_status[s] = by_status.get(s, 0) + 1
            return {
                "total_workflows": len(self._workflows),
                "by_status":       by_status,
            }


def _deep_copy_workflow(w: Dict[str, Any]) -> Dict[str, Any]:
    """Return a deep copy of a workflow dict."""
    import copy
    return copy.deepcopy(w)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[WorkflowFederation] = None
_LOCK = threading.Lock()


def get_workflow_federation() -> WorkflowFederation:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = WorkflowFederation()
        return _INSTANCE


def reset_workflow_federation_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
