"""Cross-project pattern extraction (Tier 11 — §31).

Reads accumulated records from StudioKnowledgeDB and ProjectMemory,
then extracts reusable intelligence: best workflows, best lighting/camera/
atmosphere settings, and recurring failure patterns.

No persistence — reads from other modules.  Deterministic: same input
always produces the same output.
"""

import threading
from typing import Any, Dict, List, Optional

_module_lock = threading.Lock()
_instance: Optional["CrossProjectLearning"] = None


def get_cross_project_learning() -> "CrossProjectLearning":
    global _instance
    with _module_lock:
        if _instance is None:
            _instance = CrossProjectLearning()
    return _instance


def reset_cross_project_learning_for_tests() -> None:
    global _instance
    with _module_lock:
        _instance = None


class CrossProjectLearning:
    """Extracts reusable intelligence from cross-project records."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._analysis_count = 0

    # ------------------------------------------------------------------
    # Pattern analysis
    # ------------------------------------------------------------------

    def identify_successful_patterns(
        self, records: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Return workflow patterns that appear ≥2× with avg score ≥0.7."""
        workflow_stats: Dict[str, Dict[str, Any]] = {}
        for r in records:
            if r.get("record_type") in ("failure",):
                continue
            wf = r.get("workflow", "")
            if not wf:
                continue
            if wf not in workflow_stats:
                workflow_stats[wf] = {
                    "count": 0,
                    "total_score": 0.0,
                    "environment": r.get("environment", ""),
                }
            workflow_stats[wf]["count"] += 1
            workflow_stats[wf]["total_score"] += r.get("score", 0.0)

        patterns = []
        for wf, s in workflow_stats.items():
            count = s["count"]
            avg = s["total_score"] / count if count > 0 else 0.0
            if count >= 2 and avg >= 0.7:
                patterns.append({
                    "pattern_type": "successful_workflow",
                    "workflow": wf,
                    "occurrence_count": count,
                    "average_score": round(avg, 3),
                    "environment": s["environment"],
                    "confidence": min(0.5 + count * 0.1, 0.95),
                })
        return sorted(patterns, key=lambda p: p["average_score"], reverse=True)

    def identify_failed_patterns(
        self, records: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Return failure patterns that appear ≥2×."""
        failure_counts: Dict[str, int] = {}
        failure_env: Dict[str, str] = {}
        for r in records:
            if r.get("record_type") != "failure":
                continue
            ft = r.get("failure_type", "") or r.get("workflow", "unknown_failure")
            if not ft:
                continue
            failure_counts[ft] = failure_counts.get(ft, 0) + 1
            failure_env.setdefault(ft, r.get("environment", ""))

        patterns = []
        for ft, count in failure_counts.items():
            if count >= 2:
                patterns.append({
                    "pattern_type": "recurring_failure",
                    "failure_type": ft,
                    "occurrence_count": count,
                    "environment": failure_env.get(ft, ""),
                    "risk_level": "high" if count >= 5 else "medium" if count >= 3 else "low",
                })
        return sorted(patterns, key=lambda p: p["occurrence_count"], reverse=True)

    def extract_best_workflows(
        self, records: List[Dict[str, Any]], top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Rank workflows by average success score."""
        workflow_data: Dict[str, Dict[str, Any]] = {}
        for r in records:
            if r.get("record_type") == "failure":
                continue
            wf = r.get("workflow", "")
            if not wf:
                continue
            if wf not in workflow_data:
                workflow_data[wf] = {"scores": [], "count": 0, "env": r.get("environment", "")}
            score = r.get("score", 0.0)
            if score > 0:
                workflow_data[wf]["scores"].append(score)
            workflow_data[wf]["count"] += 1

        results = []
        for wf, data in workflow_data.items():
            scores = data["scores"]
            avg = sum(scores) / len(scores) if scores else 0.0
            results.append({
                "workflow": wf,
                "average_score": round(avg, 3),
                "usage_count": data["count"],
                "environment": data["env"],
                "recommended": avg >= 0.8,
            })
        return sorted(results, key=lambda x: x["average_score"], reverse=True)[:top_k]

    def extract_best_lighting(self, records: List[Dict[str, Any]]) -> Optional[str]:
        """Find the lighting style with the highest average score."""
        lighting_scores: Dict[str, List[float]] = {}
        for r in records:
            style = r.get("lighting_style", "") or (r.get("metadata") or {}).get("lighting_style", "")
            if not style:
                continue
            score = r.get("score", 0.0)
            if style not in lighting_scores:
                lighting_scores[style] = []
            if score > 0:
                lighting_scores[style].append(score)
        if not lighting_scores:
            return None
        return max(
            lighting_scores,
            key=lambda s: sum(lighting_scores[s]) / max(len(lighting_scores[s]), 1),
        )

    def extract_best_camera(self, records: List[Dict[str, Any]]) -> Optional[str]:
        """Find the camera mode with the highest average score."""
        camera_scores: Dict[str, List[float]] = {}
        for r in records:
            mode = r.get("camera_mode", "") or (r.get("metadata") or {}).get("camera_mode", "")
            if not mode:
                continue
            score = r.get("score", 0.0)
            if mode not in camera_scores:
                camera_scores[mode] = []
            if score > 0:
                camera_scores[mode].append(score)
        if not camera_scores:
            return None
        return max(
            camera_scores,
            key=lambda m: sum(camera_scores[m]) / max(len(camera_scores[m]), 1),
        )

    def extract_best_atmosphere(self, records: List[Dict[str, Any]]) -> Optional[str]:
        """Find the atmosphere type with the highest average score."""
        atm_scores: Dict[str, List[float]] = {}
        for r in records:
            atm = r.get("atmosphere_type", "") or (r.get("metadata") or {}).get("atmosphere_type", "")
            if not atm:
                continue
            score = r.get("score", 0.0)
            if atm not in atm_scores:
                atm_scores[atm] = []
            if score > 0:
                atm_scores[atm].append(score)
        if not atm_scores:
            return None
        return max(
            atm_scores,
            key=lambda a: sum(atm_scores[a]) / max(len(atm_scores[a]), 1),
        )

    def build_learning_report(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate a full cross-project learning report from a record list."""
        with self._lock:
            self._analysis_count += 1

        successful = self.identify_successful_patterns(records)
        failed = self.identify_failed_patterns(records)
        best_workflows = self.extract_best_workflows(records)
        best_lighting = self.extract_best_lighting(records)
        best_camera = self.extract_best_camera(records)
        best_atmosphere = self.extract_best_atmosphere(records)

        return {
            "record_count": len(records),
            "best_workflow": best_workflows[0]["workflow"] if best_workflows else None,
            "best_lighting": best_lighting,
            "best_camera": best_camera,
            "best_atmosphere": best_atmosphere,
            "successful_patterns": successful,
            "failed_patterns": failed,
            "top_workflows": best_workflows,
            "recommendations": self._build_recommendations(successful, failed),
        }

    # ------------------------------------------------------------------
    # Convenience: read from live singletons
    # ------------------------------------------------------------------

    def build_learning_report_from_studio(self) -> Dict[str, Any]:
        """Build report from all records in the live StudioKnowledgeDB."""
        records: List[Dict[str, Any]] = []
        try:
            from src.runtime.studio.studio_knowledge import get_studio_knowledge_db
            db = get_studio_knowledge_db()
            records += db.get_studio_successes(limit=500)
            records += db.get_studio_failures(limit=500)
            records += db.get_studio_patterns(limit=500)
        except Exception:
            pass
        try:
            from src.runtime.studio.project_memory import get_project_memory
            mem = get_project_memory()
            for pid in mem.list_projects():
                records += mem.get_project_history(project_id=pid, limit=100)
        except Exception:
            pass
        return self.build_learning_report(records)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build_recommendations(
        self,
        successful: List[Dict[str, Any]],
        failed: List[Dict[str, Any]],
    ) -> List[str]:
        recs: List[str] = []
        if successful:
            recs.append(f"Prefer '{successful[0]['workflow']}' — proven success rate across projects.")
        if failed:
            recs.append(f"Avoid '{failed[0]['failure_type']}' — recurring failure pattern detected.")
        if len(successful) >= 3:
            recs.append("Multiple successful workflows identified — consider A/B testing on new projects.")
        if not successful and not failed:
            recs.append("Insufficient cross-project data — record more executions to enable learning.")
        return recs

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {"analysis_count": self._analysis_count}
