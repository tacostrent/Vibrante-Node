"""Project-level production history store (Tier 11 — §31).

Append-only, JSONL-backed, thread-safe.  Stores per-project executions,
reviews, workflow usage, and custom metrics.

Persistence path: VIBRANTE_PROJECT_MEMORY_PATH env var (JSONL).
No path → in-memory only (useful for tests).
"""

import json
import os
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

_module_lock = threading.Lock()
_instance: Optional["ProjectMemory"] = None
_MAX_RECORDS = 5000


def get_project_memory() -> "ProjectMemory":
    global _instance
    with _module_lock:
        if _instance is None:
            path = os.environ.get("VIBRANTE_PROJECT_MEMORY_PATH")
            _instance = ProjectMemory(path=path)
    return _instance


def reset_project_memory_for_tests() -> None:
    global _instance
    with _module_lock:
        _instance = None


class ProjectMemory:
    """Project-level production history.  One record per event, newest-first queries."""

    def __init__(self, path: Optional[str] = None):
        self._path = path
        self._lock = threading.Lock()
        self._records: List[Dict[str, Any]] = []
        self._projects: Dict[str, Dict[str, Any]] = {}
        self._write_count = 0
        if path:
            self._load()

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if not self._path or not os.path.exists(self._path):
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        if isinstance(record, dict):
                            self._records.append(record)
                            if record.get("record_type") == "project_registration":
                                pid = record.get("project_id", "")
                                if pid:
                                    self._projects[pid] = record
                    except (json.JSONDecodeError, ValueError):
                        continue  # skip corrupt lines
        except (OSError, IOError):
            pass

    def _append(self, record: Dict[str, Any]) -> None:
        self._records.append(record)
        self._write_count += 1
        if self._path:
            try:
                with open(self._path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(record, sort_keys=True) + "\n")
            except (OSError, IOError):
                pass  # never block execution
        if len(self._records) > _MAX_RECORDS * 2:
            self._records = self._records[-_MAX_RECORDS:]

    # ------------------------------------------------------------------
    # Public write API
    # ------------------------------------------------------------------

    def register_project(
        self,
        project_id: str,
        name: str,
        environment: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        with self._lock:
            record: Dict[str, Any] = {
                "record_type": "project_registration",
                "project_id": project_id,
                "name": name,
                "environment": environment,
                "metadata": metadata or {},
                "registered_at": time.time(),
            }
            self._projects[project_id] = record
            self._append(record)
            return project_id

    def record_project_execution(
        self,
        project_id: str,
        workflow: str,
        status: str,
        score: float = 0.0,
        duration: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        with self._lock:
            rid = str(uuid.uuid4())
            self._append({
                "record_type": "project_execution",
                "record_id": rid,
                "project_id": project_id,
                "workflow": workflow,
                "status": status,
                "score": float(score),
                "duration": float(duration),
                "metadata": metadata or {},
                "timestamp": time.time(),
            })
            return rid

    def record_project_review(
        self,
        project_id: str,
        grade: str,
        score: float,
        findings: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        with self._lock:
            rid = str(uuid.uuid4())
            self._append({
                "record_type": "project_review",
                "record_id": rid,
                "project_id": project_id,
                "grade": grade,
                "score": float(score),
                "findings": findings or [],
                "metadata": metadata or {},
                "timestamp": time.time(),
            })
            return rid

    def record_project_workflow(
        self,
        project_id: str,
        workflow: str,
        pack_name: str = "",
        outcome: str = "success",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        with self._lock:
            rid = str(uuid.uuid4())
            self._append({
                "record_type": "project_workflow",
                "record_id": rid,
                "project_id": project_id,
                "workflow": workflow,
                "pack_name": pack_name,
                "outcome": outcome,
                "metadata": metadata or {},
                "timestamp": time.time(),
            })
            return rid

    def record_project_metrics(
        self,
        project_id: str,
        metrics: Dict[str, Any],
    ) -> str:
        with self._lock:
            rid = str(uuid.uuid4())
            self._append({
                "record_type": "project_metrics",
                "record_id": rid,
                "project_id": project_id,
                "metrics": metrics,
                "timestamp": time.time(),
            })
            return rid

    # ------------------------------------------------------------------
    # Public read API
    # ------------------------------------------------------------------

    def get_project_history(
        self,
        project_id: str,
        record_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        with self._lock:
            results = [
                r for r in self._records
                if r.get("project_id") == project_id
                and (record_type is None or r.get("record_type") == record_type)
            ]
            results.sort(key=lambda r: r.get("timestamp", 0), reverse=True)
            return results[:limit]

    def get_project_statistics(self, project_id: Optional[str] = None) -> Dict[str, Any]:
        with self._lock:
            records = (
                [r for r in self._records if r.get("project_id") == project_id]
                if project_id
                else list(self._records)
            )
            executions = [r for r in records if r.get("record_type") == "project_execution"]
            reviews = [r for r in records if r.get("record_type") == "project_review"]
            committed = [e for e in executions if e.get("status") == "committed"]
            success_rate = len(committed) / len(executions) if executions else 0.0
            scores = [r.get("score", 0.0) for r in reviews if r.get("score", 0.0) > 0]
            avg_score = sum(scores) / len(scores) if scores else 0.0
            return {
                "project_id": project_id,
                "total_records": len(records),
                "total_executions": len(executions),
                "total_reviews": len(reviews),
                "success_rate": round(success_rate, 3),
                "average_score": round(avg_score, 3),
                "registered_projects": len(self._projects),
                "write_count": self._write_count,
            }

    def list_projects(self) -> List[str]:
        with self._lock:
            return sorted(self._projects.keys())

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_records": len(self._records),
                "registered_projects": len(self._projects),
                "write_count": self._write_count,
            }
