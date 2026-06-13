"""Review outcome analytics (Tier 11 — §31).

Analyzes review records to find common failures, common successes,
quality trends, and per-workflow pass rates.

No persistence — reads record lists passed by the caller.
"""

import threading
from collections import Counter
from typing import Any, Dict, List, Optional

_module_lock = threading.Lock()
_instance: Optional["ReviewAnalytics"] = None


def get_review_analytics() -> "ReviewAnalytics":
    global _instance
    with _module_lock:
        if _instance is None:
            _instance = ReviewAnalytics()
    return _instance


def reset_review_analytics_for_tests() -> None:
    global _instance
    with _module_lock:
        _instance = None


class ReviewAnalytics:
    """Deterministic review outcome analyzer."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._analysis_count = 0

    def analyze_reviews(self, reviews: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate metrics from a list of review records."""
        with self._lock:
            self._analysis_count += 1

        if not reviews:
            return {
                "total_reviews": 0,
                "average_score": 0.0,
                "grade_distribution": {},
                "pass_rate": 0.0,
                "common_failures": [],
                "common_successes": [],
                "trend": "insufficient_data",
            }

        scores = [r.get("score", 0.0) for r in reviews]
        avg_score = sum(scores) / len(scores)
        grade_dist = dict(Counter(r.get("grade", "F") for r in reviews))
        passing = [r for r in reviews if r.get("score", 0.0) >= 0.7]
        pass_rate = len(passing) / len(reviews)

        return {
            "total_reviews": len(reviews),
            "average_score": round(avg_score, 3),
            "grade_distribution": grade_dist,
            "pass_rate": round(pass_rate, 3),
            "common_failures": self.find_common_failures(reviews),
            "common_successes": self.find_common_successes(reviews),
            "trend": self._trend_direction(reviews),
        }

    def find_common_failures(
        self, reviews: List[Dict[str, Any]], top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Count how often each finding string appears across reviews."""
        counts: Counter = Counter()
        for r in reviews:
            findings = r.get("findings", [])
            if isinstance(findings, list):
                for f in findings:
                    if isinstance(f, str) and f:
                        counts[f] += 1
        return [{"finding": f, "count": c} for f, c in counts.most_common(top_k)]

    def find_common_successes(
        self, reviews: List[Dict[str, Any]], top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Count which workflows appear most often in passing reviews."""
        counts: Counter = Counter()
        for r in reviews:
            if r.get("score", 0.0) >= 0.7:
                wf = r.get("workflow", "")
                if wf:
                    counts[wf] += 1
        return [{"workflow": w, "count": c} for w, c in counts.most_common(top_k)]

    def analyze_trends(
        self, reviews: List[Dict[str, Any]], window_size: int = 5
    ) -> Dict[str, Any]:
        """Compare recent vs older window average scores."""
        if len(reviews) < 2:
            return {
                "trend_direction": "insufficient_data",
                "trend_score": 0.0,
                "windows": [],
            }
        sorted_reviews = sorted(reviews, key=lambda r: r.get("timestamp", 0))
        diff = 0.0
        if len(sorted_reviews) >= window_size * 2:
            recent = sorted_reviews[-window_size:]
            older = sorted_reviews[-window_size * 2: -window_size]
            recent_avg = sum(r.get("score", 0.0) for r in recent) / len(recent)
            older_avg = sum(r.get("score", 0.0) for r in older) / len(older)
            diff = recent_avg - older_avg

        direction = (
            "improving" if diff > 0.05 else "declining" if diff < -0.05 else "stable"
        )
        return {
            "trend_direction": direction,
            "trend_score": round(diff, 3),
            "windows": [{"type": "all", "count": len(reviews)}],
        }

    def generate_review_report(self, reviews: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Full report: analysis + trends + recommendations."""
        analysis = self.analyze_reviews(reviews)
        trends = self.analyze_trends(reviews)
        failures = self.find_common_failures(reviews)
        successes = self.find_common_successes(reviews)

        most_common_failure = failures[0]["finding"] if failures else None
        most_common_success = successes[0]["workflow"] if successes else None

        recommendations: List[str] = []
        if most_common_failure:
            recommendations.append(f"Address recurring issue: '{most_common_failure}'")
        if analysis["pass_rate"] < 0.5:
            recommendations.append(
                "Pass rate below 50% — review studio production standards."
            )
        if trends.get("trend_direction") == "declining":
            recommendations.append(
                "Review quality is declining — investigate recent workflow changes."
            )
        if analysis["average_score"] >= 0.85:
            recommendations.append(
                "Studio performance is above standard — maintain current practices."
            )

        return {
            "most_common_failure": most_common_failure,
            "most_common_success": most_common_success,
            "analysis": analysis,
            "trends": trends,
            "recommendations": recommendations,
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _trend_direction(self, reviews: List[Dict[str, Any]]) -> str:
        return self.analyze_trends(reviews).get("trend_direction", "stable")

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {"analysis_count": self._analysis_count}
