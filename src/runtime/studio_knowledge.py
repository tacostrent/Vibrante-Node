"""
Studio Knowledge
================
Tracks project/shot workflow patterns, asset orchestration history, successful
execution recipes, pipeline optimization patterns, and cross-DCC workflow
strategies.

Stores ONLY:
  • structured orchestration metadata (intents, templates, op counts, outcomes)
  • pipeline pattern fingerprints (op-type sequences, not full op data)
  • anonymized timing data

Does NOT store:
  • raw artist conversations or chat logs
  • private production data (file paths, asset names)
  • arbitrary free-text or user input

Persistence: optional JSONL file (VIBRANTE_STUDIO_KNOWLEDGE_PATH env var or
constructor path= argument). In-memory only if path=None.

Public API:
    get_studio_knowledge() -> StudioKnowledge   (singleton)
    reset_studio_knowledge_for_tests()           (test isolation only)

    sk.record_workflow_pattern(data) -> str
    sk.record_asset_pattern(data) -> str
    sk.get_best_recipe(intent, dcc=None) -> dict | None
    sk.query_patterns(intent=None, dcc=None, outcome=None, limit=20) -> list[dict]
    sk.get_optimization_insights(intent) -> dict
    sk.stats() -> dict
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

_VALID_OUTCOMES = frozenset({"success", "partial", "failure", "unknown"})
_VALID_PATTERN_TYPES = frozenset({
    "workflow_pattern", "asset_pattern", "cross_dcc_pattern",
    "pipeline_recipe", "optimization_hint",
})


class StudioKnowledge:
    """Structured studio orchestration knowledge store."""

    def __init__(self, path: Optional[str] = None) -> None:
        self._lock = threading.Lock()
        self._patterns: List[Dict[str, Any]] = []
        self._max_records = 1000
        self._write_count = 0

        if path is None:
            path = os.environ.get("VIBRANTE_STUDIO_KNOWLEDGE_PATH")
        self._path = path
        self._loaded = False

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record_workflow_pattern(self, data: Dict[str, Any]) -> str:
        """Record a workflow pattern from a completed execution.

        Required data keys:
          intent (str), outcome (str), op_count (int), dcc (str)
        Optional:
          template_id, duration_sec, op_fingerprint (list[str] of op types)
        Returns pattern id.
        """
        return self._record("workflow_pattern", data)

    def record_asset_pattern(self, data: Dict[str, Any]) -> str:
        """Record an asset orchestration pattern.

        Required data keys:
          intent (str), outcome (str), dcc (str)
        Optional:
          asset_type (str), op_count, template_id
        Returns pattern id.
        """
        return self._record("asset_pattern", data)

    def _record(self, pattern_type: str, data: Dict[str, Any]) -> str:
        self._ensure_loaded()

        intent  = str(data.get("intent", ""))
        outcome = str(data.get("outcome", "unknown"))
        dcc     = str(data.get("dcc", ""))

        if outcome not in _VALID_OUTCOMES:
            raise ValueError(f"Invalid outcome '{outcome}'. Valid: {sorted(_VALID_OUTCOMES)}")

        pattern_id = str(uuid.uuid4())
        record: Dict[str, Any] = {
            "id":           pattern_id,
            "pattern_type": pattern_type,
            "intent":       intent,
            "outcome":      outcome,
            "dcc":          dcc,
            "op_count":     int(data.get("op_count", 0)),
            "template_id":  str(data.get("template_id", "")),
            "duration_sec": float(data.get("duration_sec", 0.0)),
            "op_fingerprint": list(data.get("op_fingerprint", [])),
            "timestamp":    time.time(),
        }

        with self._lock:
            self._patterns.append(record)
            self._write_count += 1
            if len(self._patterns) > self._max_records * 2:
                self._patterns = self._patterns[-self._max_records:]
            if self._path:
                self._append_to_disk(record)

        return pattern_id

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    def get_best_recipe(
        self, intent: str, dcc: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Return the most successful workflow pattern for an intent.

        Returns the pattern dict or None if no successful patterns exist.
        """
        self._ensure_loaded()
        with self._lock:
            candidates = [
                p for p in self._patterns
                if p["intent"] == intent
                and p["outcome"] == "success"
                and (dcc is None or p["dcc"] == dcc)
            ]

        if not candidates:
            return None

        # Prefer patterns with more ops (more complete), then newest
        candidates.sort(key=lambda p: (-p["op_count"], -p["timestamp"]))
        return dict(candidates[0])

    def query_patterns(
        self,
        intent: Optional[str] = None,
        dcc: Optional[str] = None,
        outcome: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Query stored patterns with optional filters.

        Returns list of pattern dicts, newest first.
        """
        self._ensure_loaded()
        with self._lock:
            results = list(self._patterns)

        if intent:
            results = [p for p in results if p["intent"] == intent]
        if dcc:
            results = [p for p in results if p["dcc"] == dcc]
        if outcome:
            results = [p for p in results if p["outcome"] == outcome]

        results.sort(key=lambda p: p["timestamp"], reverse=True)
        return results[:limit]

    def get_optimization_insights(self, intent: str) -> Dict[str, Any]:
        """Return optimization insights for a given intent from historical patterns.

        Returns:
            {
                "intent":        str,
                "pattern_count": int,
                "success_rate":  float,
                "avg_op_count":  float,
                "best_template": str | None,
                "best_dcc":      str | None,
                "insights":      [str, ...],
            }
        """
        self._ensure_loaded()
        with self._lock:
            patterns = [p for p in self._patterns if p["intent"] == intent]

        if not patterns:
            return {
                "intent":        intent,
                "pattern_count": 0,
                "success_rate":  0.0,
                "avg_op_count":  0.0,
                "best_template": None,
                "best_dcc":      None,
                "insights":      [f"No historical data for intent '{intent}'."],
            }

        successes = [p for p in patterns if p["outcome"] == "success"]
        success_rate = round(len(successes) / len(patterns), 3)
        avg_ops = round(sum(p["op_count"] for p in patterns) / len(patterns), 1)

        # Best template by success rate
        from collections import Counter
        template_success: Dict[str, int] = {}
        template_count: Dict[str, int] = {}
        for p in patterns:
            tid = p["template_id"]
            if tid:
                template_count[tid] = template_count.get(tid, 0) + 1
                if p["outcome"] == "success":
                    template_success[tid] = template_success.get(tid, 0) + 1
        best_template: Optional[str] = None
        best_rate = 0.0
        for tid, cnt in template_count.items():
            rate = template_success.get(tid, 0) / cnt
            if rate > best_rate:
                best_rate = rate
                best_template = tid

        # Best DCC
        dcc_counts = Counter(p["dcc"] for p in successes if p["dcc"])
        best_dcc = dcc_counts.most_common(1)[0][0] if dcc_counts else None

        insights: List[str] = []
        if success_rate >= 0.8:
            insights.append(f"Intent '{intent}' has a strong success rate ({success_rate:.0%}).")
        elif success_rate >= 0.5:
            insights.append(f"Intent '{intent}' succeeds {success_rate:.0%} of the time — review failure cases.")
        else:
            insights.append(f"Intent '{intent}' fails more than half the time — investigate pre-conditions.")

        if best_template:
            insights.append(f"Template '{best_template}' has the highest success rate for this intent.")
        if best_dcc:
            insights.append(f"DCC '{best_dcc}' is the most successful execution target.")

        return {
            "intent":        intent,
            "pattern_count": len(patterns),
            "success_rate":  success_rate,
            "avg_op_count":  avg_ops,
            "best_template": best_template,
            "best_dcc":      best_dcc,
            "insights":      insights,
        }

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        self._ensure_loaded()
        with self._lock:
            total = len(self._patterns)
            outcomes: Dict[str, int] = {}
            for p in self._patterns:
                outcomes[p["outcome"]] = outcomes.get(p["outcome"], 0) + 1
            return {
                "total_patterns": total,
                "by_outcome":     outcomes,
                "write_count":    self._write_count,
                "path":           self._path,
            }

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _ensure_loaded(self) -> None:
        with self._lock:
            if self._loaded:
                return
            self._loaded = True
            if self._path and os.path.isfile(self._path):
                self._load_from_disk()

    def _load_from_disk(self) -> None:
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        if isinstance(record, dict) and "id" in record:
                            self._patterns.append(record)
                    except json.JSONDecodeError:
                        pass
        except OSError:
            pass

    def _append_to_disk(self, record: Dict[str, Any]) -> None:
        try:
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[StudioKnowledge] = None
_INSTANCE_LOCK = threading.Lock()


def get_studio_knowledge() -> StudioKnowledge:
    global _INSTANCE
    with _INSTANCE_LOCK:
        if _INSTANCE is None:
            _INSTANCE = StudioKnowledge()
        return _INSTANCE


def reset_studio_knowledge_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
