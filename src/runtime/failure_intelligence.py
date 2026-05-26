"""
Failure Intelligence
====================
Detects recurring rollback patterns, dangerous workflow structures, unstable
orchestration patterns, and dependency failure hotspots from historical
execution data.

All analysis is:
  • heuristic-based — no opaque ML
  • advisory — findings never block or modify execution
  • deterministic — same inputs, same outputs

Output shape (from analyze):
  {
    "failure_patterns": [{"pattern", "count", "severity", "description"}, ...],
    "risk_clusters":    [{"cluster", "ops", "frequency"}, ...],
    "recommendations":  [str, ...],
    "health_score":     float (0.0=bad, 1.0=healthy),
  }

This module NEVER:
  • executes operations or calls the bridge
  • modifies plans
  • calls TransactionManager

Public API:
    get_failure_intelligence() -> FailureIntelligence   (singleton)
    reset_failure_intelligence_for_tests()               (test isolation only)

    fi.analyze(execution_records) -> dict
    fi.detect_recurring_patterns(execution_records) -> dict
    fi.detect_risky_structures(operations) -> dict
    fi.get_hotspot_report(execution_records) -> dict
    fi.stats() -> dict
"""

from __future__ import annotations

import threading
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional


class FailureIntelligence:
    """Heuristic failure pattern detector."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._analysis_count = 0

    # ------------------------------------------------------------------
    # Primary analysis
    # ------------------------------------------------------------------

    def analyze(self, execution_records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze execution history for failure patterns.

        Each record: {"intent", "status", "error_count", "rollback_performed",
                      "op_count", "template_id", "timestamp"}

        Returns:
            {
                "failure_patterns": [...],
                "risk_clusters":    [...],
                "recommendations":  [...],
                "health_score":     float,
            }
        """
        with self._lock:
            self._analysis_count += 1

        if not execution_records:
            return {
                "failure_patterns": [],
                "risk_clusters":    [],
                "recommendations":  ["No execution history to analyze."],
                "health_score":     1.0,
            }

        patterns_result = self.detect_recurring_patterns(execution_records)
        hotspot_result  = self.get_hotspot_report(execution_records)

        # Aggregate recommendations
        recommendations: List[str] = []
        recommendations.extend(patterns_result.get("recommendations", []))
        recommendations.extend(hotspot_result.get("recommendations", []))

        # Health score: fraction of successful executions
        total = len(execution_records)
        success = sum(1 for r in execution_records if r.get("status") == "committed")
        health_score = round(success / total, 3)

        if health_score < 0.5:
            recommendations.append(
                f"Overall health score {health_score:.2f} is critically low — "
                "investigate failure root causes before running new transactions."
            )
        elif health_score < 0.8:
            recommendations.append(
                f"Health score {health_score:.2f} — review top failure intents and consider "
                "adding dry_run validation gates."
            )

        return {
            "failure_patterns": patterns_result["patterns"],
            "risk_clusters":    hotspot_result["clusters"],
            "recommendations":  list(dict.fromkeys(recommendations)),   # deduplicate, preserve order
            "health_score":     health_score,
        }

    # ------------------------------------------------------------------
    # Recurring pattern detection
    # ------------------------------------------------------------------

    def detect_recurring_patterns(
        self, execution_records: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Detect recurring failure patterns.

        Returns:
            {
                "patterns":       [{"pattern", "count", "severity", "description"}, ...],
                "recommendations": [str, ...],
            }
        """
        patterns: List[Dict[str, Any]] = []
        recommendations: List[str] = []

        failures = [r for r in execution_records if r.get("status") in ("failed", "rolled_back")]
        if not failures:
            return {"patterns": [], "recommendations": []}

        # Pattern: repeated failure on same intent
        intent_failures: Counter = Counter()
        for r in failures:
            if r.get("intent"):
                intent_failures[r["intent"]] += 1

        for intent, count in intent_failures.most_common(5):
            if count >= 2:
                severity = "high" if count >= 5 else "medium"
                patterns.append({
                    "pattern":     "repeated_intent_failure",
                    "intent":      intent,
                    "count":       count,
                    "severity":    severity,
                    "description": f"Intent '{intent}' has failed {count} times.",
                })
                recommendations.append(
                    f"Intent '{intent}' fails repeatedly — review validation rules or add pre-conditions."
                )

        # Pattern: high rollback rate
        rollbacks = [r for r in execution_records if r.get("rollback_performed")]
        rollback_rate = len(rollbacks) / len(execution_records) if execution_records else 0.0
        if rollback_rate >= 0.3:
            patterns.append({
                "pattern":     "high_rollback_rate",
                "count":       len(rollbacks),
                "severity":    "high" if rollback_rate >= 0.5 else "medium",
                "description": f"Rollback rate is {rollback_rate:.0%} — too many transactions failing mid-execution.",
            })
            recommendations.append("High rollback rate — consider adding dry_run validation before transactions.")

        # Pattern: large batch failures
        large_failures = [r for r in failures if r.get("op_count", 0) > 15]
        if len(large_failures) >= 2:
            patterns.append({
                "pattern":     "large_batch_failures",
                "count":       len(large_failures),
                "severity":    "medium",
                "description": f"{len(large_failures)} failures on large batches (>15 ops).",
            })
            recommendations.append("Split large batches (>15 ops) into smaller transactions.")

        return {"patterns": patterns, "recommendations": recommendations}

    # ------------------------------------------------------------------
    # Risky structure detection
    # ------------------------------------------------------------------

    def detect_risky_structures(
        self, operations: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Detect dangerous structural patterns in an operation batch.

        Returns:
            {
                "risks":    [{"type", "severity", "explanation"}, ...],
                "safe":     bool,
            }
        """
        risks: List[Dict[str, Any]] = []

        if not operations:
            return {"risks": [], "safe": True}

        op_types = [op.get("op", "") for op in operations if isinstance(op, dict)]

        # Risk: delete before create of same parent
        created_parents: set = set()
        for op in operations:
            if not isinstance(op, dict):
                continue
            if op.get("op") == "create_node":
                created_parents.add(op.get("parent", ""))
            elif op.get("op") == "delete_node":
                path = op.get("path", "")
                parent = "/".join(path.rstrip("/").split("/")[:-1]) if "/" in path else ""
                if parent in created_parents:
                    risks.append({
                        "type":        "create_then_delete_parent_child",
                        "severity":    "high",
                        "explanation": f"Deleting '{path}' after creating nodes under the same parent.",
                    })

        # Risk: no create before connect
        has_create = "create_node" in op_types or "build_node_chain" in op_types
        has_connect = "connect_nodes" in op_types
        if has_connect and not has_create:
            risks.append({
                "type":        "connect_without_create",
                "severity":    "medium",
                "explanation": "connect_nodes ops present but no create_node — relies entirely on pre-existing nodes.",
            })

        # Risk: cook with no prior create or set_parms
        has_cook = "cook_node" in op_types
        has_parms = "set_parms" in op_types
        if has_cook and not has_create and not has_parms:
            risks.append({
                "type":        "cook_empty_setup",
                "severity":    "low",
                "explanation": "cook_node with no create_node or set_parms — cooking default state.",
            })

        # Risk: interleaved creates and deletes
        create_indices = [i for i, t in enumerate(op_types) if t == "create_node"]
        delete_indices  = [i for i, t in enumerate(op_types) if t == "delete_node"]
        if create_indices and delete_indices:
            if max(create_indices) > min(delete_indices):
                risks.append({
                    "type":        "interleaved_create_delete",
                    "severity":    "medium",
                    "explanation": "Creates and deletes are interleaved — deletion before all creates may break references.",
                })

        return {"risks": risks, "safe": len(risks) == 0}

    # ------------------------------------------------------------------
    # Hotspot report
    # ------------------------------------------------------------------

    def get_hotspot_report(
        self, execution_records: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Identify hotspot intents and templates with high failure rates.

        Returns:
            {
                "clusters":        [{"cluster", "intent_or_template", "failure_rate", "count"}, ...],
                "recommendations": [str, ...],
            }
        """
        clusters: List[Dict[str, Any]] = []
        recommendations: List[str] = []

        # Group by intent
        intent_records: Dict[str, List] = defaultdict(list)
        for r in execution_records:
            intent = r.get("intent", "")
            if intent:
                intent_records[intent].append(r)

        for intent, records in intent_records.items():
            failures = [r for r in records if r.get("status") in ("failed", "rolled_back")]
            rate = len(failures) / len(records) if records else 0.0
            if rate >= 0.5 and len(records) >= 2:
                clusters.append({
                    "cluster":            "intent_hotspot",
                    "intent_or_template": intent,
                    "failure_rate":       round(rate, 3),
                    "count":              len(records),
                })
                recommendations.append(
                    f"Intent '{intent}' has {rate:.0%} failure rate ({len(failures)}/{len(records)}) "
                    "— investigate pre-conditions and validation rules."
                )

        # Group by template
        template_records: Dict[str, List] = defaultdict(list)
        for r in execution_records:
            tid = r.get("template_id", "")
            if tid:
                template_records[tid].append(r)

        for tid, records in template_records.items():
            failures = [r for r in records if r.get("status") in ("failed", "rolled_back")]
            rate = len(failures) / len(records) if records else 0.0
            if rate >= 0.5 and len(records) >= 2:
                clusters.append({
                    "cluster":            "template_hotspot",
                    "intent_or_template": tid,
                    "failure_rate":       round(rate, 3),
                    "count":              len(records),
                })
                recommendations.append(
                    f"Template '{tid}' has {rate:.0%} failure rate — review template parameters."
                )

        return {"clusters": clusters, "recommendations": recommendations}

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {"analysis_count": self._analysis_count}


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[FailureIntelligence] = None
_INSTANCE_LOCK = threading.Lock()


def get_failure_intelligence() -> FailureIntelligence:
    global _INSTANCE
    with _INSTANCE_LOCK:
        if _INSTANCE is None:
            _INSTANCE = FailureIntelligence()
        return _INSTANCE


def reset_failure_intelligence_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
