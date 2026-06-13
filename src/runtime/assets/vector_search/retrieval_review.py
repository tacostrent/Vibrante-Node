"""
Retrieval Review (Tier 12.8)
==============================
Evaluates semantic retrieval quality.

Metrics: precision, semantic_relevance, environment_accuracy, role_accuracy

Output:
  {
    "score": 0.93,
    "grade": "A",
    "production_ready": true,
    "findings": [...]
  }

production_ready requires score >= 0.7 AND no blocking findings.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .retrieval_statistics import get_retrieval_statistics

_GRADE_MAP = [(0.85, "A"), (0.70, "B"), (0.55, "C"), (0.40, "D")]
_BLOCKING_KEYWORDS = frozenset({"empty store", "no results", "zero assets"})

_SCORE_WEIGHTS = {
    "result_count":          0.25,
    "semantic_relevance":    0.30,
    "environment_accuracy":  0.25,
    "role_accuracy":         0.20,
}


def _grade(score: float) -> str:
    for threshold, g in _GRADE_MAP:
        if score >= threshold:
            return g
    return "F"


@dataclass
class RetrievalReviewResult:
    ok:               bool = True
    score:            float = 0.0
    grade:            str = "F"
    production_ready: bool = False
    precision:        float = 0.0
    semantic_relevance: float = 0.0
    environment_accuracy: float = 0.0
    role_accuracy:    float = 0.0
    findings:         List[str] = field(default_factory=list)
    recommendations:  List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok":                   bool(self.ok),
            "score":                round(float(self.score), 4),
            "grade":                str(self.grade),
            "production_ready":     bool(self.production_ready),
            "precision":            round(float(self.precision), 4),
            "semantic_relevance":   round(float(self.semantic_relevance), 4),
            "environment_accuracy": round(float(self.environment_accuracy), 4),
            "role_accuracy":        round(float(self.role_accuracy), 4),
            "findings":             list(self.findings),
            "recommendations":      list(self.recommendations),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RetrievalReviewResult":
        d = d if isinstance(d, dict) else {}
        return cls(
            ok=bool(d.get("ok", True)),
            score=float(d.get("score", 0.0)),
            grade=str(d.get("grade", "F")),
            production_ready=bool(d.get("production_ready", False)),
            precision=float(d.get("precision", 0.0)),
            semantic_relevance=float(d.get("semantic_relevance", 0.0)),
            environment_accuracy=float(d.get("environment_accuracy", 0.0)),
            role_accuracy=float(d.get("role_accuracy", 0.0)),
            findings=list(d.get("findings") or []),
            recommendations=list(d.get("recommendations") or []),
        )


class RetrievalReview:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._review_count = 0

    def review_results(
        self,
        query_context: Dict[str, Any],
        results: List[Dict[str, Any]],
    ) -> RetrievalReviewResult:
        """Review the quality of a retrieval result set. Never raises."""
        try:
            return self._do_review_results(
                dict(query_context) if isinstance(query_context, dict) else {},
                list(results) if isinstance(results, list) else [],
            )
        except Exception as exc:
            return RetrievalReviewResult(
                ok=False,
                findings=[f"review_results failed: {exc}"],
            )

    def _do_review_results(
        self,
        ctx: Dict[str, Any],
        results: List[Dict[str, Any]],
    ) -> RetrievalReviewResult:
        findings: List[str] = []
        recommendations: List[str] = []

        n = len(results)
        if n == 0:
            return RetrievalReviewResult(
                ok=True,
                score=0.0,
                grade="F",
                production_ready=False,
                findings=["no results — vector store may be empty or query too specific."],
                recommendations=[
                    "Run hou_mcp_vector_index to build the vector index first.",
                    "Broaden the query intent.",
                ],
            )

        req_env  = str(ctx.get("environment", "")).strip()
        req_role = str(ctx.get("role", "")).strip()

        # Result count score (more is better, up to 10)
        result_count_score = min(n / 10, 1.0)

        # Semantic relevance: avg top score from ranked results
        scores = [float(r.get("total_score", r.get("score", 0.0))) for r in results]
        avg_score = sum(scores) / len(scores) if scores else 0.0
        semantic_relevance = min(avg_score * 2, 1.0)  # scale: avg 0.5 → 1.0

        # Environment accuracy
        if req_env:
            env_matches = sum(
                1 for r in results
                if req_env in (r.get("environments") or []) or r.get("primary_env") == req_env
            )
            env_accuracy = env_matches / n
            if env_accuracy < 0.5:
                findings.append(f"low environment accuracy ({env_accuracy:.0%}) for '{req_env}'.")
                recommendations.append("Re-index catalog with richer environment metadata.")
        else:
            env_accuracy = 0.7  # neutral when no env requested

        # Role accuracy
        if req_role:
            role_matches = sum(
                1 for r in results
                if req_role in (r.get("roles") or [])
            )
            role_accuracy = role_matches / n
            if role_accuracy < 0.5:
                findings.append(f"low role accuracy ({role_accuracy:.0%}) for '{req_role}'.")
                recommendations.append("Enrich catalog role metadata for better role matching.")
        else:
            role_accuracy = 0.7

        score = round(
            result_count_score  * _SCORE_WEIGHTS["result_count"] +
            semantic_relevance  * _SCORE_WEIGHTS["semantic_relevance"] +
            env_accuracy        * _SCORE_WEIGHTS["environment_accuracy"] +
            role_accuracy       * _SCORE_WEIGHTS["role_accuracy"],
            4,
        )

        grade = _grade(score)
        blocking = any(
            any(kw in f.lower() for kw in _BLOCKING_KEYWORDS)
            for f in findings
        )
        production_ready = score >= 0.7 and not blocking

        with self._lock:
            self._review_count += 1

        return RetrievalReviewResult(
            ok=True,
            score=score,
            grade=grade,
            production_ready=production_ready,
            precision=round(result_count_score, 4),
            semantic_relevance=round(semantic_relevance, 4),
            environment_accuracy=round(env_accuracy, 4),
            role_accuracy=round(role_accuracy, 4),
            findings=findings,
            recommendations=recommendations,
        )

    def review_query(self, intent_text: str, top_k: int = 10) -> RetrievalReviewResult:
        """Run a retrieval and review the results. Never raises."""
        try:
            from .retrieval_pipeline import get_retrieval_pipeline
            from .intent_parser import get_intent_parser
            result = get_retrieval_pipeline().retrieve(intent_text, top_k=top_k)
            ctx = result.parsed_intent or {}
            return self.review_results(ctx, result.assets)
        except Exception as exc:
            return RetrievalReviewResult(
                ok=False,
                findings=[f"review_query failed: {exc}"],
            )

    def review_pipeline(self) -> RetrievalReviewResult:
        """Review overall pipeline health using recent statistics. Never raises."""
        try:
            stats = get_retrieval_statistics().get_summary()
            total = stats.get("total_queries", 0)
            avg   = stats.get("avg_score", 0.0)

            findings: List[str] = []
            recommendations: List[str] = []

            if total == 0:
                return RetrievalReviewResult(
                    ok=True,
                    score=0.0,
                    grade="F",
                    production_ready=False,
                    findings=["no queries executed yet."],
                    recommendations=["Run at least one semantic retrieval to evaluate pipeline health."],
                )

            if avg < 0.3:
                findings.append(f"low average retrieval score ({avg:.3f}) — results may not be semantically relevant.")
                recommendations.append("Rebuild the vector index with current catalog entries.")

            score = min(avg * 1.5, 1.0)
            grade = _grade(score)
            production_ready = score >= 0.7

            with self._lock:
                self._review_count += 1

            return RetrievalReviewResult(
                ok=True,
                score=round(score, 4),
                grade=grade,
                production_ready=production_ready,
                semantic_relevance=round(avg, 4),
                findings=findings,
                recommendations=recommendations,
            )
        except Exception as exc:
            return RetrievalReviewResult(
                ok=False,
                findings=[f"review_pipeline failed: {exc}"],
            )

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            return {"review_count": self._review_count}


_INSTANCE: Optional[RetrievalReview] = None
_INSTANCE_LOCK = threading.Lock()


def get_retrieval_review() -> RetrievalReview:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = RetrievalReview()
    return _INSTANCE


def reset_retrieval_review_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
