"""Aggregated studio knowledge statistics (Tier 11 — §31).

Single entry point that queries all Tier 11 modules and returns
a unified statistics snapshot.  Every module failure is silently
caught — the statistics call never crashes.
"""

import threading
from typing import Any, Dict, List

_module_lock = threading.Lock()
_instance = None


def get_knowledge_statistics() -> "KnowledgeStatistics":
    global _instance
    with _module_lock:
        if _instance is None:
            _instance = KnowledgeStatistics()
    return _instance


def reset_knowledge_statistics_for_tests() -> None:
    global _instance
    with _module_lock:
        _instance = None


def _count_by(records: List[Dict[str, Any]], key: str) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for r in records:
        v = str(r.get(key, "unknown"))
        counts[v] = counts.get(v, 0) + 1
    return counts


class KnowledgeStatistics:
    """Aggregates stats from all Tier 11 studio modules."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._query_count = 0

    def get_statistics(self) -> Dict[str, Any]:
        """Full statistics snapshot across all studio modules."""
        with self._lock:
            self._query_count += 1

        result: Dict[str, Any] = {"query_count": self._query_count}

        _modules = {
            "studio_knowledge":          ("src.runtime.studio.studio_knowledge", "get_studio_knowledge_db", "get_studio_statistics"),
            "project_memory":            ("src.runtime.studio.project_memory", "get_project_memory", "get_project_statistics"),
            "studio_standards":          ("src.runtime.studio.studio_standards", "get_studio_standards", "stats"),
            "studio_metrics":            ("src.runtime.studio.studio_metrics", "get_studio_metrics", "stats"),
            "knowledge_recommendation":  ("src.runtime.studio.knowledge_recommendation", "get_knowledge_recommendation_engine", "stats"),
            "production_benchmark":      ("src.runtime.studio.production_benchmark", "get_production_benchmark", "stats"),
            "cross_project_learning":    ("src.runtime.studio.cross_project_learning", "get_cross_project_learning", "stats"),
            "review_analytics":          ("src.runtime.studio.review_analytics", "get_review_analytics", "stats"),
            "knowledge_serializer":      ("src.runtime.studio.knowledge_serializer", "get_knowledge_serializer", "stats"),
        }

        import importlib
        for key, (mod_path, getter_fn, stats_fn) in _modules.items():
            try:
                mod = importlib.import_module(mod_path)
                obj = getattr(mod, getter_fn)()
                result[key] = getattr(obj, stats_fn)()
            except Exception as exc:
                result[key] = {"error": str(exc)}

        return result

    def get_pattern_statistics(self) -> Dict[str, Any]:
        with self._lock:
            self._query_count += 1
        try:
            from src.runtime.pattern_library import get_pattern_library
            patterns = get_pattern_library().search_patterns()
            return {
                "total_patterns": len(patterns),
                "by_type": _count_by(patterns, "pattern_type"),
            }
        except Exception:
            return {"total_patterns": 0, "by_type": {}}

    def get_workflow_statistics(self) -> Dict[str, Any]:
        with self._lock:
            self._query_count += 1
        try:
            from src.runtime.studio.studio_metrics import get_studio_metrics
            return get_studio_metrics().generate_metrics_report()
        except Exception:
            return {}

    def get_review_statistics(self) -> Dict[str, Any]:
        with self._lock:
            self._query_count += 1
        try:
            from src.runtime.studio.studio_metrics import get_studio_metrics
            return get_studio_metrics().calculate_review_performance()
        except Exception:
            return {}

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {"query_count": self._query_count}
