"""
asset_suitability_review.py — §45 Semantic Asset Suitability Ranking
=====================================================================
Reviews the quality of a suitability ranking result.

Public API:
    get_asset_suitability_review() -> AssetSuitabilityReview
    reset_asset_suitability_review_for_tests()

    AssetSuitabilityReview.review(result) -> SuitabilityReviewResult
"""

import threading
from dataclasses import dataclass, field
from typing import List

from src.runtime.assets.suitability.asset_suitability_engine import SuitabilityResult

_GRADE_THRESHOLDS = (
    (0.85, "A"),
    (0.70, "B"),
    (0.55, "C"),
    (0.40, "D"),
)
_BLOCKING_KEYWORDS = (
    "no candidates",
    "best score below threshold",
    "all candidates rejected",
)


@dataclass
class SuitabilityReviewResult:
    best_score: float          # highest candidate final_score
    mean_score: float          # average final_score across candidates
    rejection_rate: float      # fraction with final_score < 0.30
    coverage_score: float      # did we have any suitable candidates ≥ 0.50?
    overall_score: float       # weighted composite
    grade: str                 # A / B / C / D / F
    production_ready: bool
    findings: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "best_score": round(self.best_score, 4),
            "mean_score": round(self.mean_score, 4),
            "rejection_rate": round(self.rejection_rate, 4),
            "coverage_score": round(self.coverage_score, 4),
            "overall_score": round(self.overall_score, 4),
            "grade": self.grade,
            "production_ready": self.production_ready,
            "findings": list(self.findings),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SuitabilityReviewResult":
        return cls(
            best_score=float(d.get("best_score", 0.0)),
            mean_score=float(d.get("mean_score", 0.0)),
            rejection_rate=float(d.get("rejection_rate", 1.0)),
            coverage_score=float(d.get("coverage_score", 0.0)),
            overall_score=float(d.get("overall_score", 0.0)),
            grade=d.get("grade", "F"),
            production_ready=bool(d.get("production_ready", False)),
            findings=list(d.get("findings", [])),
        )


class AssetSuitabilityReview:
    """Evaluates the quality of a SuitabilityResult."""

    # Weights for overall_score
    _W_BEST      = 0.40
    _W_MEAN      = 0.30
    _W_COVERAGE  = 0.20
    _W_REJECTION = 0.10   # inverted: low rejection → high score

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def review(self, result: SuitabilityResult) -> SuitabilityReviewResult:
        """Review a SuitabilityResult and return a graded assessment."""
        try:
            findings: List[str] = []

            if result.total_candidates == 0:
                findings.append("no candidates provided for suitability ranking")
                return SuitabilityReviewResult(
                    best_score=0.0,
                    mean_score=0.0,
                    rejection_rate=1.0,
                    coverage_score=0.0,
                    overall_score=0.0,
                    grade="F",
                    production_ready=False,
                    findings=findings,
                )

            scores = [s.final_score for s in result.scores]
            best_score = max(scores)
            mean_score = sum(scores) / len(scores)
            rejection_rate = result.rejected_count / max(1, result.total_candidates)
            coverage_count = sum(1 for s in scores if s >= 0.50)
            coverage_score = min(1.0, coverage_count / max(1, result.total_candidates))

            # Dimension scores (0.0–1.0 each)
            dim_best = best_score
            dim_mean = mean_score
            dim_coverage = coverage_score
            dim_rejection_ok = 1.0 - rejection_rate  # low rejection → good

            overall = (
                self._W_BEST     * dim_best
                + self._W_MEAN   * dim_mean
                + self._W_COVERAGE * dim_coverage
                + self._W_REJECTION * dim_rejection_ok
            )
            overall = max(0.0, min(1.0, overall))

            # Findings
            if best_score < 0.50:
                findings.append(
                    f"best score below threshold: {best_score:.2f} (need ≥ 0.50)"
                )
            if rejection_rate > 0.5:
                findings.append(
                    f"all candidates rejected: {result.rejected_count}/{result.total_candidates} "
                    f"scored below 0.30"
                )
            if coverage_count == 0:
                findings.append("no suitable candidates found with score ≥ 0.50")

            # Grade
            grade = "F"
            for threshold, letter in _GRADE_THRESHOLDS:
                if overall >= threshold:
                    grade = letter
                    break

            # Blocking check
            has_blocking = any(
                any(kw in f for kw in _BLOCKING_KEYWORDS) for f in findings
            )
            production_ready = (
                overall >= 0.70
                and best_score >= 0.50
                and not has_blocking
            )

            return SuitabilityReviewResult(
                best_score=best_score,
                mean_score=mean_score,
                rejection_rate=rejection_rate,
                coverage_score=coverage_score,
                overall_score=overall,
                grade=grade,
                production_ready=production_ready,
                findings=findings,
            )
        except Exception as exc:
            return SuitabilityReviewResult(
                best_score=0.0,
                mean_score=0.0,
                rejection_rate=1.0,
                coverage_score=0.0,
                overall_score=0.0,
                grade="F",
                production_ready=False,
                findings=[f"review error: {exc}"],
            )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: AssetSuitabilityReview | None = None
_instance_lock = threading.Lock()


def get_asset_suitability_review() -> AssetSuitabilityReview:
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = AssetSuitabilityReview()
    return _instance


def reset_asset_suitability_review_for_tests() -> None:
    global _instance
    with _instance_lock:
        _instance = None
