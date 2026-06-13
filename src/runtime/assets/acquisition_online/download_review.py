"""
Download Review (Tier 12.9)
==============================
Validates acquisition quality across 4 dimensions.

Score weights:
  download_success  0.35
  integrity         0.30
  cache_efficiency  0.20
  provenance_quality 0.15

Grade mapping:
  ≥ 0.85 → A  production_ready=True
  ≥ 0.70 → B  production_ready=True
  ≥ 0.55 → C  production_ready=False
  ≥ 0.40 → D  production_ready=False
  < 0.40 → F  production_ready=False
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_SCORE_WEIGHTS = {
    "download_success":  0.35,
    "integrity":         0.30,
    "cache_efficiency":  0.20,
    "provenance_quality": 0.15,
}

_BLOCKING_KEYWORDS = frozenset({
    "no assets",
    "zero downloads",
    "all failed",
    "no provenance",
})


@dataclass
class DownloadReviewResult:
    ok:               bool  = False
    overall_score:    float = 0.0
    grade:            str   = "F"
    production_ready: bool  = False
    dimensions:       Dict[str, float] = field(default_factory=dict)
    findings:         List[str] = field(default_factory=list)
    advisory:         str   = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok":               bool(self.ok),
            "overall_score":    round(float(self.overall_score), 4),
            "grade":            str(self.grade),
            "production_ready": bool(self.production_ready),
            "dimensions":       {k: round(v, 4) for k, v in self.dimensions.items()},
            "findings":         list(self.findings),
            "advisory":         str(self.advisory),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DownloadReviewResult":
        d = d if isinstance(d, dict) else {}
        return cls(
            ok=bool(d.get("ok", False)),
            overall_score=float(d.get("overall_score", 0.0)),
            grade=str(d.get("grade", "F")),
            production_ready=bool(d.get("production_ready", False)),
            dimensions=dict(d.get("dimensions") or {}),
            findings=list(d.get("findings") or []),
            advisory=str(d.get("advisory", "")),
        )


class DownloadReview:
    def __init__(self) -> None:
        self._lock = threading.Lock()

    def review_download(
        self,
        asset_id:    str,
        provider:    str = "",
        local_path:  str = "",
        checksum:    str = "",
    ) -> DownloadReviewResult:
        """Review a single download result. Never raises."""
        try:
            from .asset_cache_manager import get_asset_cache_manager
            from .asset_provenance_tracker import get_asset_provenance_tracker, compute_file_checksum
            import os

            findings: List[str] = []
            dims: Dict[str, float] = {k: 0.0 for k in _SCORE_WEIGHTS}

            # download_success
            file_exists = bool(local_path) and os.path.isfile(local_path)
            dims["download_success"] = 1.0 if file_exists else 0.0
            if not file_exists:
                findings.append(f"File missing or not downloaded: {local_path}")

            # integrity
            if file_exists and checksum:
                actual = compute_file_checksum(local_path)
                if actual == checksum:
                    dims["integrity"] = 1.0
                else:
                    dims["integrity"] = 0.0
                    findings.append(f"Checksum mismatch for {asset_id}")
            elif file_exists:
                dims["integrity"] = 0.7  # file exists but no checksum to verify
            else:
                dims["integrity"] = 0.0

            # cache_efficiency
            cache = get_asset_cache_manager()
            entry = cache.get_cache_entry(asset_id, provider)
            dims["cache_efficiency"] = 1.0 if (entry is not None) else 0.3

            # provenance_quality
            tracker = get_asset_provenance_tracker()
            prov = tracker.lookup(asset_id, provider)
            dims["provenance_quality"] = 1.0 if (prov and prov.asset_id) else 0.0
            if not prov:
                findings.append(f"No provenance record for {asset_id}")

            score, grade, ready = self._compute_grade(dims, findings)
            return DownloadReviewResult(
                ok=True, overall_score=score, grade=grade, production_ready=ready,
                dimensions=dims, findings=findings,
                advisory=self._build_advisory(grade, findings),
            )
        except Exception as exc:
            return DownloadReviewResult(ok=False, findings=[str(exc)])

    def review_pipeline(
        self,
        pipeline_result: Dict[str, Any],
    ) -> DownloadReviewResult:
        """Review an AcquisitionPipelineResult dict. Never raises."""
        try:
            findings: List[str] = []
            dims: Dict[str, float] = {k: 0.0 for k in _SCORE_WEIGHTS}

            total      = int(pipeline_result.get("total", 0))
            downloaded = int(pipeline_result.get("downloaded", 0))
            cached     = int(pipeline_result.get("cached", 0))
            failed     = int(pipeline_result.get("failed", 0))
            assets     = list(pipeline_result.get("assets") or [])

            if total == 0:
                findings.append("no assets acquired in pipeline")
                score, grade, ready = self._compute_grade(dims, findings)
                return DownloadReviewResult(
                    ok=True, overall_score=score, grade=grade, production_ready=ready,
                    dimensions=dims, findings=findings,
                )

            # download_success
            success_rate = (total - failed) / max(total, 1)
            dims["download_success"] = round(success_rate, 4)
            if failed > 0:
                findings.append(f"{failed}/{total} assets failed to acquire")
            if failed == total:
                findings.append("all failed")

            # integrity — check provenance for each acquired asset
            from .asset_provenance_tracker import get_asset_provenance_tracker
            tracker = get_asset_provenance_tracker()
            verified = 0
            for a in assets:
                if not isinstance(a, dict):
                    continue
                aid = str(a.get("asset_id", ""))
                prv = str(a.get("provider", ""))
                prov = tracker.lookup(aid, prv)
                if prov and prov.asset_id:
                    verified += 1
            dims["integrity"] = round(verified / max(len(assets), 1), 4)

            # cache_efficiency
            dims["cache_efficiency"] = round((cached + downloaded) / max(total, 1), 4)

            # provenance_quality
            prov_rate = round(verified / max(len(assets), 1), 4) if assets else 0.0
            dims["provenance_quality"] = prov_rate
            if prov_rate < 0.5:
                findings.append("no provenance" if prov_rate == 0.0 else
                                "Low provenance coverage")

            score, grade, ready = self._compute_grade(dims, findings)
            return DownloadReviewResult(
                ok=True, overall_score=score, grade=grade, production_ready=ready,
                dimensions=dims, findings=findings,
                advisory=self._build_advisory(grade, findings),
            )
        except Exception as exc:
            return DownloadReviewResult(ok=False, findings=[str(exc)])

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _compute_grade(
        self,
        dims: Dict[str, float],
        findings: List[str],
    ) -> tuple:
        score = sum(dims.get(k, 0.0) * w for k, w in _SCORE_WEIGHTS.items())
        score = round(max(0.0, min(1.0, score)), 4)
        if score >= 0.85:
            grade = "A"
        elif score >= 0.70:
            grade = "B"
        elif score >= 0.55:
            grade = "C"
        elif score >= 0.40:
            grade = "D"
        else:
            grade = "F"
        has_blocking = any(
            any(bk in f.lower() for bk in _BLOCKING_KEYWORDS)
            for f in findings
        )
        ready = (score >= 0.70) and not has_blocking
        return score, grade, ready

    @staticmethod
    def _build_advisory(grade: str, findings: List[str]) -> str:
        if grade in ("A", "B"):
            return "Acquisition quality is production-ready."
        if grade == "C":
            return "Acquisition quality is acceptable but below production threshold."
        issues = "; ".join(findings[:3]) if findings else "unknown issues"
        return f"Acquisition quality is below production threshold. Issues: {issues}"


_INSTANCE: Optional[DownloadReview] = None
_INSTANCE_LOCK = threading.Lock()


def get_download_review() -> DownloadReview:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = DownloadReview()
    return _INSTANCE


def reset_download_review_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
