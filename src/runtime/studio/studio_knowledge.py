"""Cross-project studio knowledge aggregator (Tier 11 — §31).

Aggregates success/failure/pattern/review records across all projects.
This is distinct from src/runtime/studio_knowledge.py (Tier 5 §24), which
tracks pattern usage scores.  This module tracks studio-wide outcomes.

Persistence path: VIBRANTE_STUDIO_KNOWLEDGE_DB_PATH env var (JSONL).
No path → in-memory only.
"""

import json
import os
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

_module_lock = threading.Lock()
_instance: Optional["StudioKnowledgeDB"] = None
_MAX_RECORDS = 10000
_VALID_OUTCOMES = frozenset({"success", "partial", "failure", "unknown"})


def get_studio_knowledge_db() -> "StudioKnowledgeDB":
    global _instance
    with _module_lock:
        if _instance is None:
            path = os.environ.get("VIBRANTE_STUDIO_KNOWLEDGE_DB_PATH")
            _instance = StudioKnowledgeDB(path=path)
    return _instance


def reset_studio_knowledge_db_for_tests() -> None:
    global _instance
    with _module_lock:
        _instance = None


class StudioKnowledgeDB:
    """Cross-project studio knowledge store.  Append-only, sorted queries."""

    def __init__(self, path: Optional[str] = None):
        self._path = path
        self._lock = threading.Lock()
        self._records: List[Dict[str, Any]] = []
        self._write_count = 0
        if path:
            self._load()

    # ------------------------------------------------------------------
    # Persistence
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
                        r = json.loads(line)
                        if isinstance(r, dict):
                            self._records.append(r)
                    except (json.JSONDecodeError, ValueError):
                        continue
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
                pass
        if len(self._records) > _MAX_RECORDS * 2:
            self._records = self._records[-_MAX_RECORDS:]

    # ------------------------------------------------------------------
    # Write API
    # ------------------------------------------------------------------

    def record_success(
        self,
        workflow: str,
        environment: str,
        score: float = 0.0,
        project_id: str = "",
        lighting_style: str = "",
        camera_mode: str = "",
        atmosphere_type: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        with self._lock:
            rid = str(uuid.uuid4())
            self._append({
                "record_type": "success",
                "record_id": rid,
                "workflow": workflow,
                "environment": environment,
                "score": float(score),
                "project_id": project_id,
                "lighting_style": lighting_style,
                "camera_mode": camera_mode,
                "atmosphere_type": atmosphere_type,
                "metadata": metadata or {},
                "timestamp": time.time(),
            })
            return rid

    def record_failure(
        self,
        workflow: str,
        environment: str,
        failure_type: str = "",
        project_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        with self._lock:
            rid = str(uuid.uuid4())
            self._append({
                "record_type": "failure",
                "record_id": rid,
                "workflow": workflow,
                "environment": environment,
                "failure_type": failure_type,
                "project_id": project_id,
                "metadata": metadata or {},
                "timestamp": time.time(),
            })
            return rid

    def record_pattern(
        self,
        pattern_id: str,
        pattern_type: str,
        environment: str,
        outcome: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        if outcome not in _VALID_OUTCOMES:
            raise ValueError(f"Invalid outcome {outcome!r}. Must be one of {sorted(_VALID_OUTCOMES)}")
        with self._lock:
            rid = str(uuid.uuid4())
            self._append({
                "record_type": "pattern",
                "record_id": rid,
                "pattern_id": pattern_id,
                "pattern_type": pattern_type,
                "environment": environment,
                "outcome": outcome,
                "metadata": metadata or {},
                "timestamp": time.time(),
            })
            return rid

    def record_review(
        self,
        workflow: str,
        environment: str,
        grade: str,
        score: float,
        findings: Optional[List[str]] = None,
        project_id: str = "",
    ) -> str:
        with self._lock:
            rid = str(uuid.uuid4())
            self._append({
                "record_type": "review",
                "record_id": rid,
                "workflow": workflow,
                "environment": environment,
                "grade": grade,
                "score": float(score),
                "findings": findings or [],
                "project_id": project_id,
                "timestamp": time.time(),
            })
            return rid

    # ------------------------------------------------------------------
    # Read API
    # ------------------------------------------------------------------

    def get_studio_patterns(
        self,
        environment: Optional[str] = None,
        outcome: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        with self._lock:
            results = [
                r for r in self._records
                if r.get("record_type") == "pattern"
                and (environment is None or r.get("environment") == environment)
                and (outcome is None or r.get("outcome") == outcome)
            ]
            results.sort(key=lambda r: r.get("timestamp", 0), reverse=True)
            return results[:limit]

    def get_studio_failures(
        self,
        environment: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        with self._lock:
            results = [
                r for r in self._records
                if r.get("record_type") == "failure"
                and (environment is None or r.get("environment") == environment)
            ]
            results.sort(key=lambda r: r.get("timestamp", 0), reverse=True)
            return results[:limit]

    def get_studio_successes(
        self,
        environment: Optional[str] = None,
        min_score: float = 0.0,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        with self._lock:
            results = [
                r for r in self._records
                if r.get("record_type") == "success"
                and (environment is None or r.get("environment") == environment)
                and r.get("score", 0.0) >= min_score
            ]
            results.sort(key=lambda r: r.get("score", 0.0), reverse=True)
            return results[:limit]

    def get_studio_statistics(self) -> Dict[str, Any]:
        with self._lock:
            successes = [r for r in self._records if r.get("record_type") == "success"]
            failures = [r for r in self._records if r.get("record_type") == "failure"]
            patterns = [r for r in self._records if r.get("record_type") == "pattern"]
            reviews = [r for r in self._records if r.get("record_type") == "review"]

            total = len(successes) + len(failures)
            success_rate = len(successes) / total if total > 0 else 0.0
            scores = [r.get("score", 0.0) for r in successes if r.get("score", 0.0) > 0]
            avg_score = sum(scores) / len(scores) if scores else 0.0

            # workflow breakdown
            wf_counts: Dict[str, Dict[str, int]] = {}
            for r in successes + failures:
                wf = r.get("workflow", "unknown") or "unknown"
                if wf not in wf_counts:
                    wf_counts[wf] = {"successes": 0, "failures": 0}
                key = "successes" if r.get("record_type") == "success" else "failures"
                wf_counts[wf][key] += 1

            top_workflows = sorted(
                [{"workflow": k, **v} for k, v in wf_counts.items()],
                key=lambda x: x["successes"],
                reverse=True,
            )[:5]

            return {
                "total_records": len(self._records),
                "total_successes": len(successes),
                "total_failures": len(failures),
                "total_patterns": len(patterns),
                "total_reviews": len(reviews),
                "success_rate": round(success_rate, 3),
                "average_score": round(avg_score, 3),
                "top_workflows": top_workflows,
                "write_count": self._write_count,
            }

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_records": len(self._records),
                "write_count": self._write_count,
            }
