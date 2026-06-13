"""Production benchmarking against historical performance (Tier 11 — §31).

Compares a project's scores against the studio-wide average derived from
StudioKnowledgeDB and StudioMetrics.  No bridge calls.  Advisory only.
"""

import threading
from typing import Any, Dict, List, Optional

_module_lock = threading.Lock()
_instance: Optional["ProductionBenchmark"] = None

_STUDIO_AVERAGE_FALLBACK = 0.75  # used when no historical data is available


def get_production_benchmark() -> "ProductionBenchmark":
    global _instance
    with _module_lock:
        if _instance is None:
            _instance = ProductionBenchmark()
    return _instance


def reset_production_benchmark_for_tests() -> None:
    global _instance
    with _module_lock:
        _instance = None


class ProductionBenchmark:
    """Compares project scores against historical studio performance."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._benchmark_count = 0

    # ------------------------------------------------------------------
    # Studio average helper
    # ------------------------------------------------------------------

    def _get_studio_average(self) -> float:
        scores: List[float] = []
        try:
            from src.runtime.studio.studio_knowledge import get_studio_knowledge_db
            stats = get_studio_knowledge_db().get_studio_statistics()
            avg = stats.get("average_score", 0.0)
            if avg > 0:
                scores.append(avg)
        except Exception:
            pass
        try:
            from src.runtime.studio.studio_metrics import get_studio_metrics
            avg = get_studio_metrics().calculate_quality_average()
            if avg > 0:
                scores.append(avg)
        except Exception:
            pass
        return round(sum(scores) / len(scores), 3) if scores else _STUDIO_AVERAGE_FALLBACK

    def _get_env_average(self, environment: str) -> float:
        try:
            from src.runtime.studio.studio_knowledge import get_studio_knowledge_db
            successes = get_studio_knowledge_db().get_studio_successes(
                environment=environment, limit=50
            )
            scores = [r.get("score", 0.0) for r in successes if r.get("score", 0.0) > 0]
            if scores:
                return round(sum(scores) / len(scores), 3)
        except Exception:
            pass
        return _STUDIO_AVERAGE_FALLBACK

    def _get_workflow_scores(self, workflow: str) -> List[float]:
        try:
            from src.runtime.studio.studio_knowledge import get_studio_knowledge_db
            successes = get_studio_knowledge_db().get_studio_successes(limit=100)
            return [
                r.get("score", 0.0)
                for r in successes
                if r.get("workflow") == workflow and r.get("score", 0.0) > 0
            ]
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Public benchmark API
    # ------------------------------------------------------------------

    def benchmark_project(
        self,
        project_id: str,
        project_score: float,
        project_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        with self._lock:
            self._benchmark_count += 1
        studio_avg = self._get_studio_average()
        diff = project_score - studio_avg
        performance = (
            "above_average" if diff > 0.05
            else "below_average" if diff < -0.05
            else "average"
        )
        return {
            "project_id": project_id,
            "project_score": round(project_score, 3),
            "studio_average": studio_avg,
            "difference": round(diff, 3),
            "performance": performance,
            "percentile": self._estimate_percentile(diff),
            "recommendations": self._get_recommendations(performance, diff),
        }

    def benchmark_workflow(self, workflow: str, workflow_score: float) -> Dict[str, Any]:
        with self._lock:
            self._benchmark_count += 1
        historical = self._get_workflow_scores(workflow)
        avg = sum(historical) / len(historical) if historical else _STUDIO_AVERAGE_FALLBACK
        diff = workflow_score - avg
        performance = (
            "above_average" if diff > 0.05
            else "below_average" if diff < -0.05
            else "average"
        )
        return {
            "workflow": workflow,
            "workflow_score": round(workflow_score, 3),
            "historical_average": round(avg, 3),
            "difference": round(diff, 3),
            "performance": performance,
            "sample_count": len(historical),
        }

    def benchmark_review(self, grade: str, score: float) -> Dict[str, Any]:
        with self._lock:
            self._benchmark_count += 1
        studio_avg = self._get_studio_average()
        diff = score - studio_avg
        performance = (
            "above_average" if diff > 0.05
            else "below_average" if diff < -0.05
            else "average"
        )
        return {
            "grade": grade,
            "score": round(score, 3),
            "studio_review_average": studio_avg,
            "difference": round(diff, 3),
            "performance": performance,
        }

    def benchmark_environment(self, environment: str, score: float) -> Dict[str, Any]:
        with self._lock:
            self._benchmark_count += 1
        env_avg = self._get_env_average(environment)
        diff = score - env_avg
        performance = (
            "above_average" if diff > 0.05
            else "below_average" if diff < -0.05
            else "average"
        )
        return {
            "environment": environment,
            "score": round(score, 3),
            "environment_average": env_avg,
            "difference": round(diff, 3),
            "performance": performance,
        }

    def generate_benchmark_report(
        self,
        project_id: str,
        project_score: float,
        workflow: str = "",
        environment: str = "",
        reviews: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        studio_avg = self._get_studio_average()
        project_bench = self.benchmark_project(project_id, project_score)

        report: Dict[str, Any] = {
            "project_id": project_id,
            "project_score": round(project_score, 3),
            "studio_average": studio_avg,
            "project_benchmark": project_bench,
        }
        if workflow:
            report["workflow_benchmark"] = self.benchmark_workflow(workflow, project_score)
        if environment:
            report["environment_benchmark"] = self.benchmark_environment(environment, project_score)
        if reviews:
            rev_scores = [r.get("score", 0.0) for r in reviews]
            avg_rev = sum(rev_scores) / len(rev_scores) if rev_scores else 0.0
            report["review_benchmark"] = self.benchmark_review("", avg_rev)

        perf = project_bench["performance"]
        report["summary"] = (
            f"Project {project_id}: score {project_score:.2f} vs studio average "
            f"{studio_avg:.2f} — {perf}."
        )
        return report

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _estimate_percentile(self, diff: float) -> int:
        if diff >= 0.15:
            return 90
        if diff >= 0.10:
            return 80
        if diff >= 0.05:
            return 65
        if diff >= 0.0:
            return 55
        if diff >= -0.05:
            return 40
        if diff >= -0.10:
            return 25
        return 10

    def _get_recommendations(self, performance: str, diff: float) -> List[str]:
        recs: List[str] = []
        if performance == "above_average":
            recs.append("Excellent performance — capture this approach as a studio pattern.")
        elif performance == "below_average":
            recs.append(
                "Score is below studio average — review production settings and workflow choice."
            )
            if diff < -0.15:
                recs.append(
                    "Significant underperformance — consider switching to a proven workflow pack."
                )
        else:
            recs.append("Performance meets studio standards.")
        return recs

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {"benchmark_count": self._benchmark_count}
