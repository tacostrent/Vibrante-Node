"""
Semantic Memory (Tier 4)
=========================
Persistent structured memory for orchestration patterns.  Stores successful
workflow patterns, planning heuristics, and execution lineage so future
planning sessions can learn from past successes without exposing raw LLM
conversations or prompts.

STORED (structured orchestration metadata):
  - execution_pattern   — a successful intent + parameter set + outcome
  - planning_pattern    — a planning strategy that produced a good plan
  - optimization_hint   — advisory hint derived from repeated patterns
  - workflow_lineage    — record of a named workflow's full execution history

NOT STORED:
  - raw LLM prompts or chat logs
  - personal user data
  - unparsed free-text

Public API:
    get_semantic_memory() -> SemanticMemory   (singleton)
    reset_semantic_memory_for_tests()

    SemanticMemory.record_pattern(pattern_type, intent, data, outcome) -> str
    SemanticMemory.record_workflow_lineage(name, operations, outcome, metadata) -> str
    SemanticMemory.query_patterns(intent, outcome, pattern_type, limit) -> list[dict]
    SemanticMemory.get_best_patterns(intent, limit) -> list[dict]
    SemanticMemory.get_pattern(pattern_id) -> dict | None
    SemanticMemory.stats() -> dict
    SemanticMemory.clear()
"""

import json
import os
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

PATTERN_TYPES = frozenset({
    "execution_pattern",
    "planning_pattern",
    "optimization_hint",
    "workflow_lineage",
})

OUTCOME_VALUES = frozenset({"success", "partial", "failure", "unknown"})

_DEFAULT_MAX_RECORDS = 1000
_PATH_ENV            = "VIBRANTE_SEMANTIC_MEMORY_PATH"


class SemanticMemory:
    """Persistent structured semantic memory for orchestration patterns."""

    def __init__(
        self,
        path:        Optional[str] = None,
        max_records: int = _DEFAULT_MAX_RECORDS,
    ) -> None:
        self._path        = path
        self._max_records = max_records
        self._lock        = threading.Lock()
        self._patterns:   List[Dict[str, Any]] = []
        self._write_count = 0

    # ------------------------------------------------------------------
    # Record
    # ------------------------------------------------------------------

    def record_pattern(
        self,
        pattern_type: str,
        intent:       str,
        data:         Optional[Dict[str, Any]] = None,
        outcome:      str = "unknown",
        metadata:     Optional[Dict[str, Any]] = None,
    ) -> str:
        """Record a structured orchestration pattern.

        Args:
            pattern_type: One of PATTERN_TYPES.
            intent:       Semantic intent id (e.g. "build_pyro_source").
            data:         Structured pattern data (no raw prompts).
            outcome:      One of OUTCOME_VALUES.
            metadata:     Optional extra metadata.

        Returns:
            pattern_id (uuid4 string)
        """
        if pattern_type not in PATTERN_TYPES:
            raise ValueError(f"Unknown pattern_type: {pattern_type!r}")
        if outcome not in OUTCOME_VALUES:
            raise ValueError(f"Unknown outcome: {outcome!r}")

        pattern_id = str(uuid.uuid4())
        record = {
            "id":           pattern_id,
            "pattern_type": pattern_type,
            "intent":       intent,
            "data":         dict(data or {}),
            "outcome":      outcome,
            "metadata":     dict(metadata or {}),
            "timestamp":    time.time(),
        }

        with self._lock:
            self._patterns.append(record)
            if len(self._patterns) > self._max_records * 2:
                self._patterns = self._patterns[-self._max_records:]
            self._write_count += 1

        if self._path:
            try:
                with open(self._path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(record, default=str) + "\n")
            except Exception:
                pass

        return pattern_id

    def record_workflow_lineage(
        self,
        workflow_name: str,
        operations:    List[Dict[str, Any]],
        outcome:       str = "unknown",
        metadata:      Optional[Dict[str, Any]] = None,
    ) -> str:
        """Record a workflow execution as a lineage entry."""
        return self.record_pattern(
            pattern_type="workflow_lineage",
            intent=workflow_name,
            data={
                "workflow_name":  workflow_name,
                "op_count":       len(operations),
                "op_types":       sorted({op.get("op", "unknown") for op in operations}),
            },
            outcome=outcome,
            metadata=metadata,
        )

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_pattern(self, pattern_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            for p in reversed(self._patterns):
                if p["id"] == pattern_id:
                    return dict(p)
        return None

    def query_patterns(
        self,
        intent:       Optional[str] = None,
        outcome:      Optional[str] = None,
        pattern_type: Optional[str] = None,
        limit:        int = 50,
    ) -> List[Dict[str, Any]]:
        """Return patterns matching filters, newest first."""
        with self._lock:
            patterns = list(reversed(self._patterns))

        if intent:
            patterns = [p for p in patterns if p.get("intent") == intent]
        if outcome:
            patterns = [p for p in patterns if p.get("outcome") == outcome]
        if pattern_type:
            patterns = [p for p in patterns if p.get("pattern_type") == pattern_type]

        return [dict(p) for p in patterns[:limit]]

    def get_best_patterns(
        self,
        intent: str,
        limit:  int = 5,
    ) -> List[Dict[str, Any]]:
        """Return the most successful patterns for a given intent.

        Patterns are sorted: success first, then partial, then unknown, then failure.
        """
        _order = {"success": 0, "partial": 1, "unknown": 2, "failure": 3}
        patterns = self.query_patterns(intent=intent, limit=1000)
        patterns.sort(key=lambda p: (_order.get(p.get("outcome", "unknown"), 3), -p.get("timestamp", 0)))
        return patterns[:limit]

    # ------------------------------------------------------------------
    # Stats / clear
    # ------------------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            by_type: Dict[str, int] = {}
            by_outcome: Dict[str, int] = {}
            for p in self._patterns:
                pt = p.get("pattern_type", "unknown")
                po = p.get("outcome", "unknown")
                by_type[pt]    = by_type.get(pt, 0) + 1
                by_outcome[po] = by_outcome.get(po, 0) + 1
            return {
                "total_patterns": len(self._patterns),
                "write_count":    self._write_count,
                "by_type":        by_type,
                "by_outcome":     by_outcome,
                "max_records":    self._max_records,
                "path":           self._path,
            }

    def clear(self) -> None:
        with self._lock:
            self._patterns.clear()

    # ------------------------------------------------------------------
    # Disk load
    # ------------------------------------------------------------------

    def _load_from_disk(self) -> None:
        if not self._path or not os.path.exists(self._path):
            return
        records: List[Dict[str, Any]] = []
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        records.append(json.loads(line))
                    except (json.JSONDecodeError, ValueError):
                        pass
        except OSError:
            pass
        with self._lock:
            self._patterns = records[-self._max_records:]


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[SemanticMemory] = None
_LOCK = threading.Lock()


def get_semantic_memory() -> SemanticMemory:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            path = os.environ.get(_PATH_ENV)
            _INSTANCE = SemanticMemory(path=path or None)
        return _INSTANCE


def reset_semantic_memory_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
