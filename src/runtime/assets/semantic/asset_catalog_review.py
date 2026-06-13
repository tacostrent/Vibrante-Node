"""
Asset Catalog Review (Tier 12.7)
===================================
Validates semantic quality of the catalog and individual assets.

Output:
  {
    "score": 0.92,
    "coverage": 0.95,
    "production_ready": true,
    "grade": "A",
    "findings": [...]
  }

production_ready requires score >= 0.7 AND no blocking findings.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .asset_catalog import get_asset_catalog

_GRADE_MAP = [
    (0.85, "A"),
    (0.70, "B"),
    (0.55, "C"),
    (0.40, "D"),
]

_BLOCKING_KEYWORDS = frozenset({
    "empty catalog",
    "no environments",
    "no roles",
})


@dataclass
class CatalogReviewResult:
    ok:               bool = True
    score:            float = 0.0
    coverage:         float = 0.0
    grade:            str = "F"
    production_ready: bool = False
    total_assets:     int = 0
    enriched_assets:  int = 0
    findings:         List[str] = field(default_factory=list)
    recommendations:  List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok":               bool(self.ok),
            "score":            round(float(self.score), 4),
            "coverage":         round(float(self.coverage), 4),
            "grade":            str(self.grade),
            "production_ready": bool(self.production_ready),
            "total_assets":     int(self.total_assets),
            "enriched_assets":  int(self.enriched_assets),
            "findings":         list(self.findings),
            "recommendations":  list(self.recommendations),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CatalogReviewResult":
        d = d if isinstance(d, dict) else {}
        return cls(
            ok=bool(d.get("ok", True)),
            score=float(d.get("score", 0.0)),
            coverage=float(d.get("coverage", 0.0)),
            grade=str(d.get("grade", "F")),
            production_ready=bool(d.get("production_ready", False)),
            total_assets=int(d.get("total_assets", 0)),
            enriched_assets=int(d.get("enriched_assets", 0)),
            findings=list(d.get("findings") or []),
            recommendations=list(d.get("recommendations") or []),
        )


def _grade(score: float) -> str:
    for threshold, grade in _GRADE_MAP:
        if score >= threshold:
            return grade
    return "F"


class AssetCatalogReview:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._review_count = 0

    def review_catalog(self) -> CatalogReviewResult:
        """Review the entire catalog for semantic quality. Never raises."""
        try:
            return self._do_review_catalog()
        except Exception as exc:
            return CatalogReviewResult(ok=False, findings=[f"review_catalog failed: {exc}"])

    def _do_review_catalog(self) -> CatalogReviewResult:
        catalog = get_asset_catalog()
        stats = catalog.get_statistics()
        total = stats.get("total", 0)

        with self._lock:
            self._review_count += 1

        if total == 0:
            return CatalogReviewResult(
                ok=True,
                score=0.0,
                coverage=0.0,
                grade="F",
                production_ready=False,
                total_assets=0,
                findings=["empty catalog — no assets registered."],
                recommendations=["Run catalog sync to populate the semantic catalog."],
            )

        findings: List[str] = []
        recommendations: List[str] = []

        # Coverage: fraction with environments and roles
        entries = list(catalog.iter_all())
        with_env  = sum(1 for e in entries if e.environments)
        with_role = sum(1 for e in entries if e.roles)
        with_lookdev = sum(1 for e in entries if e.lookdev)
        coverage = (with_env + with_role) / (total * 2) if total else 0.0

        # Score dimensions
        env_coverage   = with_env  / total if total else 0.0
        role_coverage  = with_role / total if total else 0.0
        lookdev_cov    = with_lookdev / total if total else 0.0
        enrich_frac    = sum(1 for e in entries if e.semantic_tags) / total if total else 0.0

        score = round(
            env_coverage  * 0.35 +
            role_coverage * 0.30 +
            lookdev_cov   * 0.20 +
            enrich_frac   * 0.15,
            4,
        )

        if env_coverage < 0.5:
            findings.append(f"low environment coverage: {env_coverage:.0%} of assets have environments inferred.")
            recommendations.append("Re-run semantic enrichment on assets without environment tags.")
        if role_coverage < 0.5:
            findings.append(f"low role coverage: {role_coverage:.0%} of assets have roles classified.")
            recommendations.append("Add category metadata to assets to improve role classification.")
        if lookdev_cov < 0.3:
            findings.append(f"low lookdev coverage: {lookdev_cov:.0%} of assets have lookdev tags.")
            recommendations.append("Add descriptive tags (weathered, industrial, sci_fi) to asset manifests.")

        grade = _grade(score)
        blocking = any(
            any(kw in f.lower() for kw in _BLOCKING_KEYWORDS)
            for f in findings
        )
        production_ready = score >= 0.7 and not blocking

        return CatalogReviewResult(
            ok=True,
            score=score,
            coverage=round(coverage, 4),
            grade=grade,
            production_ready=production_ready,
            total_assets=total,
            enriched_assets=sum(1 for e in entries if e.semantic_tags),
            findings=findings,
            recommendations=recommendations,
        )

    def review_asset(self, asset_id: str) -> CatalogReviewResult:
        """Review a single asset for semantic completeness. Never raises."""
        try:
            catalog = get_asset_catalog()
            entry = catalog.get_asset(asset_id)
            if not entry:
                return CatalogReviewResult(
                    ok=False,
                    findings=[f"asset '{asset_id}' not found in catalog."],
                )

            findings: List[str] = []
            recommendations: List[str] = []

            if not entry.environments:
                findings.append("no environments — environment mapping failed.")
                recommendations.append("Add environment keywords to name, tags, or description.")
            if not entry.roles:
                findings.append("no roles — role classification failed.")
                recommendations.append("Add category or role keywords to the asset manifest.")
            if not entry.lookdev:
                findings.append("no lookdev tags — lookdev inference failed.")
                recommendations.append("Add surface descriptors (weathered, clean, rusted) to tags.")
            if not entry.semantic_tags:
                findings.append("no semantic tags — enrichment produced no semantic output.")
                recommendations.append("Re-run enrichment after adding richer metadata.")

            dims = [
                1.0 if entry.environments else 0.0,
                1.0 if entry.roles else 0.0,
                1.0 if entry.lookdev else 0.0,
                1.0 if entry.semantic_tags else 0.0,
            ]
            score = round(sum(dims) / len(dims), 4)
            grade = _grade(score)
            production_ready = score >= 0.7

            with self._lock:
                self._review_count += 1

            return CatalogReviewResult(
                ok=True,
                score=score,
                coverage=score,
                grade=grade,
                production_ready=production_ready,
                total_assets=1,
                enriched_assets=1 if entry.semantic_tags else 0,
                findings=findings,
                recommendations=recommendations,
            )
        except Exception as exc:
            return CatalogReviewResult(ok=False, findings=[f"review_asset failed: {exc}"])

    def review_coverage(self) -> Dict[str, Any]:
        """Return a coverage breakdown by environment, role, lookdev."""
        try:
            catalog = get_asset_catalog()
            entries = list(catalog.iter_all())
            total = len(entries)
            if total == 0:
                return {"total": 0, "env_coverage": 0, "role_coverage": 0, "lookdev_coverage": 0}
            return {
                "total":            total,
                "env_coverage":     round(sum(1 for e in entries if e.environments) / total, 4),
                "role_coverage":    round(sum(1 for e in entries if e.roles) / total, 4),
                "lookdev_coverage": round(sum(1 for e in entries if e.lookdev) / total, 4),
                "story_coverage":   round(sum(1 for e in entries if e.storytelling) / total, 4),
                "cinematic_coverage": round(sum(1 for e in entries if e.cinematic_usage) / total, 4),
            }
        except Exception:
            return {}

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            return {"review_count": self._review_count}


_INSTANCE: Optional[AssetCatalogReview] = None
_INSTANCE_LOCK = threading.Lock()


def get_asset_catalog_review() -> AssetCatalogReview:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = AssetCatalogReview()
    return _INSTANCE


def reset_asset_catalog_review_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
