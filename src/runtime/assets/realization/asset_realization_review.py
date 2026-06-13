"""
Asset Realization Review (Tier 13)
=====================================
Production quality review for the asset realization pipeline.
All critique is specific — generic "success" messages are disallowed.

DESIGN RULES:
  1. No bridge calls, no Houdini imports.
  2. All critique is specific — never "Execution successful".
  3. production_ready requires overall_score >= 0.7 AND no blocking findings.
  4. Never raises in public methods.
  5. Singleton pattern.

Public API:
    RealizationReviewResult
    AssetRealizationReview
    get_asset_realization_review()
    reset_asset_realization_review_for_tests()
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .asset_importer import get_asset_importer
from .asset_converter import get_asset_converter
from .asset_dependency_resolver import get_asset_dependency_resolver
from .asset_material_mapper import get_asset_material_mapper
from .scene_asset_realizer import get_scene_asset_realizer

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_WEIGHTS = {
    "import":       0.20,
    "conversion":   0.20,
    "dependency":   0.25,
    "material":     0.20,
    "realization":  0.15,
}

_PRODUCTION_THRESHOLD = 0.70

# Specific critique messages
_REALIZATION_CRITIQUES: Dict[str, str] = {
    "import_failed":          "Asset import failed — source path or provider is not accessible.",
    "import_no_id":           "Imported asset has no asset_id — provenance tracking will fail.",
    "import_unsupported_fmt": "Asset format is not in SUPPORTED_FORMATS — conversion will be required.",
    "conversion_failed":      "Format conversion failed — asset cannot be used in the USD pipeline.",
    "conversion_no_target":   "No target format specified — USD-compatible output cannot be generated.",
    "dep_failed":             "Dependency resolution failed — textures or materials cannot be located.",
    "dep_missing":            "Missing dependencies detected — incomplete asset will render incorrectly.",
    "material_failed":        "Material mapping failed — renderer-specific profiles cannot be generated.",
    "material_none":          "No material profiles generated — asset will render with default grey material.",
    "realization_no_ops":     "Realization plan has no transaction ops — scene integration impossible.",
    "realization_failed":     "Realization plan build failed — asset cannot be placed in the scene.",
}

_BLOCKING_KEYWORDS = frozenset({
    "failed",
    "cannot",
    "impossible",
    "not accessible",
})


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class RealizationReviewResult:
    """Full realization quality review."""

    ok:                bool      = True
    asset_id:          str       = ""
    overall_score:     float     = 0.0
    grade:             str       = "F"
    production_ready:  bool      = False
    import_score:      float     = 0.0
    conversion_score:  float     = 0.0
    dependency_score:  float     = 0.0
    material_score:    float     = 0.0
    realization_score: float     = 0.0
    findings:          List[str] = field(default_factory=list)
    recommendations:   List[str] = field(default_factory=list)
    review_summary:    str       = ""
    reviewed_at:       float     = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok":                self.ok,
            "asset_id":          self.asset_id,
            "overall_score":     self.overall_score,
            "grade":             self.grade,
            "production_ready":  self.production_ready,
            "import_score":      self.import_score,
            "conversion_score":  self.conversion_score,
            "dependency_score":  self.dependency_score,
            "material_score":    self.material_score,
            "realization_score": self.realization_score,
            "findings":          list(self.findings),
            "recommendations":   list(self.recommendations),
            "review_summary":    self.review_summary,
            "reviewed_at":       self.reviewed_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RealizationReviewResult":
        return cls(
            ok=bool(d.get("ok", True)),
            asset_id=str(d.get("asset_id", "")),
            overall_score=float(d.get("overall_score", 0.0)),
            grade=str(d.get("grade", "F")),
            production_ready=bool(d.get("production_ready", False)),
            import_score=float(d.get("import_score", 0.0)),
            conversion_score=float(d.get("conversion_score", 0.0)),
            dependency_score=float(d.get("dependency_score", 0.0)),
            material_score=float(d.get("material_score", 0.0)),
            realization_score=float(d.get("realization_score", 0.0)),
            findings=list(d.get("findings") or []),
            recommendations=list(d.get("recommendations") or []),
            review_summary=str(d.get("review_summary", "")),
            reviewed_at=float(d.get("reviewed_at") or time.time()),
        )


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class AssetRealizationReview:
    """
    Evaluates asset realization quality.
    All critique is specific — never generic "success" messages.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._review_count = 0

    # ------------------------------------------------------------------
    # Per-stage reviewers
    # ------------------------------------------------------------------

    def review_import(self, import_result: Any) -> Dict[str, Any]:
        """Review import result. Returns {'score', 'issues'}."""
        if isinstance(import_result, dict):
            r = import_result
        else:
            r = import_result.to_dict() if hasattr(import_result, "to_dict") else {}

        score = 1.0
        issues: List[str] = []
        if not r.get("ok", True):
            issues.append(_REALIZATION_CRITIQUES["import_failed"])
            score -= 0.6
        if not r.get("asset_id"):
            issues.append(_REALIZATION_CRITIQUES["import_no_id"])
            score -= 0.3
        fmt = str(r.get("format", ""))
        if fmt and not _format_is_supported(fmt):
            issues.append(_REALIZATION_CRITIQUES["import_unsupported_fmt"])
            score -= 0.1
        return {"score": max(0.0, score), "issues": issues}

    def review_conversion(self, conversion_result: Any) -> Dict[str, Any]:
        """Review conversion result."""
        if isinstance(conversion_result, dict):
            r = conversion_result
        else:
            r = conversion_result.to_dict() if hasattr(conversion_result, "to_dict") else {}

        score = 1.0
        issues: List[str] = []
        if not r.get("ok", True):
            issues.append(_REALIZATION_CRITIQUES["conversion_failed"])
            score -= 0.6
        if not r.get("target_format"):
            issues.append(_REALIZATION_CRITIQUES["conversion_no_target"])
            score -= 0.3
        return {"score": max(0.0, score), "issues": issues}

    def review_dependencies(self, dependency_result: Any) -> Dict[str, Any]:
        """Review dependency resolution result."""
        if isinstance(dependency_result, dict):
            r = dependency_result
        else:
            r = dependency_result.to_dict() if hasattr(dependency_result, "to_dict") else {}

        score = 1.0
        issues: List[str] = []
        if not r.get("ok", True):
            issues.append(_REALIZATION_CRITIQUES["dep_failed"])
            score -= 0.5
        missing = r.get("missing_deps", [])
        if missing:
            issues.append(_REALIZATION_CRITIQUES["dep_missing"])
            score -= 0.3
        return {"score": max(0.0, score), "issues": issues}

    def review_materials(self, material_result: Any) -> Dict[str, Any]:
        """Review material mapping result."""
        if isinstance(material_result, dict):
            r = material_result
        else:
            r = material_result.to_dict() if hasattr(material_result, "to_dict") else {}

        score = 1.0
        issues: List[str] = []
        if not r.get("ok", True):
            issues.append(_REALIZATION_CRITIQUES["material_failed"])
            score -= 0.5
        profiles = r.get("profiles", [])
        material_count = r.get("material_count", len(profiles) if isinstance(profiles, list) else 0)
        if material_count == 0:
            issues.append(_REALIZATION_CRITIQUES["material_none"])
            score -= 0.3
        return {"score": max(0.0, score), "issues": issues}

    def review_realization(self, realization_plan: Any) -> Dict[str, Any]:
        """Review realization plan."""
        if isinstance(realization_plan, dict):
            r = realization_plan
        else:
            r = realization_plan.to_dict() if hasattr(realization_plan, "to_dict") else {}

        score = 1.0
        issues: List[str] = []
        if r.get("errors"):
            issues.append(_REALIZATION_CRITIQUES["realization_failed"])
            score -= 0.5
        ops = r.get("transaction_ops", [])
        if not ops:
            issues.append(_REALIZATION_CRITIQUES["realization_no_ops"])
            score -= 0.4
        return {"score": max(0.0, score), "issues": issues}

    def generate_review(self, asset_dict: Dict[str, Any]) -> RealizationReviewResult:
        """Run full pipeline and generate review. Never raises."""
        try:
            return self._do_review(asset_dict)
        except Exception as exc:
            safe = asset_dict if isinstance(asset_dict, dict) else {}
            return RealizationReviewResult(
                ok=False,
                asset_id=str(safe.get("asset_id", "")),
                findings=[f"Review engine error: {exc}"],
                review_summary=f"Review failed: {exc}",
            )

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {"review_count": self._review_count}

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _do_review(self, asset_dict: Dict[str, Any]) -> RealizationReviewResult:
        asset_id = str(asset_dict.get("asset_id", ""))
        findings: List[str] = []

        # Run pipeline stages
        import_result    = get_asset_importer().import_asset(asset_dict)
        conv_result      = get_asset_converter().convert_to_usd(asset_dict)
        dep_result       = get_asset_dependency_resolver().resolve(asset_dict)
        material_result  = get_asset_material_mapper().map_materials(asset_dict)
        realization_plan = get_scene_asset_realizer().build_realization_plan([asset_dict])

        import_r   = self.review_import(import_result)
        conv_r     = self.review_conversion(conv_result)
        dep_r      = self.review_dependencies(dep_result)
        mat_r      = self.review_materials(material_result)
        real_r     = self.review_realization(realization_plan)

        for r in (import_r, conv_r, dep_r, mat_r, real_r):
            findings.extend(r["issues"])

        import_score      = import_r["score"]
        conversion_score  = conv_r["score"]
        dependency_score  = dep_r["score"]
        material_score    = mat_r["score"]
        realization_score = real_r["score"]

        overall = (
            import_score      * _WEIGHTS["import"]      +
            conversion_score  * _WEIGHTS["conversion"]  +
            dependency_score  * _WEIGHTS["dependency"]  +
            material_score    * _WEIGHTS["material"]    +
            realization_score * _WEIGHTS["realization"]
        )

        grade = _grade(overall)
        has_blocking = any(
            any(kw in f.lower() for kw in _BLOCKING_KEYWORDS)
            for f in findings
        )
        production_ready = overall >= _PRODUCTION_THRESHOLD and not has_blocking

        recommendations = _build_recommendations(
            import_score, conversion_score, dependency_score,
            material_score, realization_score,
        )
        review_summary = _build_summary(grade, overall, production_ready, findings)

        with self._lock:
            self._review_count += 1

        return RealizationReviewResult(
            ok=True,
            asset_id=asset_id,
            overall_score=overall,
            grade=grade,
            production_ready=production_ready,
            import_score=import_score,
            conversion_score=conversion_score,
            dependency_score=dependency_score,
            material_score=material_score,
            realization_score=realization_score,
            findings=findings,
            recommendations=recommendations,
            review_summary=review_summary,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_is_supported(fmt: str) -> bool:
    from .asset_importer import SUPPORTED_FORMATS
    return fmt.lower() in SUPPORTED_FORMATS


def _grade(score: float) -> str:
    if score >= 0.90:
        return "A"
    if score >= 0.80:
        return "B"
    if score >= 0.70:
        return "C"
    if score >= 0.60:
        return "D"
    return "F"


def _build_recommendations(
    import_score: float,
    conversion_score: float,
    dependency_score: float,
    material_score: float,
    realization_score: float,
) -> List[str]:
    recs: List[str] = []
    if import_score < 0.7:
        recs.append("Verify asset source path and provider availability before reimporting.")
    if conversion_score < 0.7:
        recs.append("Ensure source format is in CONVERSION_MATRIX and target format is specified.")
    if dependency_score < 0.7:
        recs.append("Resolve missing textures and materials before scene realization.")
    if material_score < 0.7:
        recs.append("Map materials to a supported renderer (arnold, usd_preview_surface, karma).")
    if realization_score < 0.7:
        recs.append("Review realization plan for empty or failed transaction ops.")
    if not recs:
        recs.append("Asset meets production standards — proceed to scene integration.")
    return recs


def _build_summary(
    grade: str,
    overall: float,
    production_ready: bool,
    findings: List[str],
) -> str:
    if production_ready:
        return (
            f"Grade {grade} — overall {overall:.2f}. "
            "Asset meets all realization criteria and is production-ready."
        )
    first_finding = findings[0] if findings else "no specific findings logged"
    return (
        f"Grade {grade} — overall {overall:.2f}. "
        f"Not production-ready. Primary issue: {first_finding}"
    )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[AssetRealizationReview] = None
_INSTANCE_LOCK = threading.Lock()


def get_asset_realization_review() -> AssetRealizationReview:
    """Return the module-level singleton AssetRealizationReview."""
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = AssetRealizationReview()
    return _INSTANCE


def reset_asset_realization_review_for_tests() -> None:
    """Replace the singleton. For test isolation only."""
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
