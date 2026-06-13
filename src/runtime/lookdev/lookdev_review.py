"""
Lookdev Review (Tier 14)
========================
Evaluates lookdev quality across 4 dimensions:
  - Material consistency  (30%)
  - Environment coherence (25%)
  - Renderer compatibility (25%)
  - Visual quality        (20%)

production_ready requires overall_score >= 0.70 AND no blocking findings.
Deterministic, thread-safe, no Houdini dependency.
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .material_library import get_material_library
from .lookdev_patterns import get_lookdev_patterns
from .renderer_profiles import get_renderer_profiles, SUPPORTED_RENDERERS

_PRODUCTION_THRESHOLD = 0.70
_GRADE_THRESHOLDS = [
    (0.85, "A"),
    (0.70, "B"),
    (0.55, "C"),
    (0.40, "D"),
]

_BLOCKING_KEYWORDS = frozenset({
    "no materials",
    "zero assignments",
    "invalid renderer",
    "empty plan",
    "no assignment",
})

_OUTDOOR_ENVIRONMENTS = frozenset({
    "outdoor", "exterior", "open_air", "landscape", "terrain",
    "forest", "desert", "field", "plaza",
})


def _has_blocking(findings: List[str]) -> bool:
    joined = " ".join(findings).lower()
    return any(kw in joined for kw in _BLOCKING_KEYWORDS)


def _grade(score: float) -> str:
    for threshold, letter in _GRADE_THRESHOLDS:
        if score >= threshold:
            return letter
    return "F"


@dataclass
class LookdevReviewResult:
    review_id: str = field(default_factory=lambda: f"rev_{uuid.uuid4().hex[:8]}")
    score: float = 0.0
    grade: str = "F"
    production_ready: bool = False
    material_consistency: float = 0.0
    environment_coherence: float = 0.0
    renderer_compatibility: float = 0.0
    visual_quality: float = 0.0
    findings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    reviewed_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "review_id":              str(self.review_id),
            "score":                  float(self.score),
            "grade":                  str(self.grade),
            "production_ready":       bool(self.production_ready),
            "material_consistency":   float(self.material_consistency),
            "environment_coherence":  float(self.environment_coherence),
            "renderer_compatibility": float(self.renderer_compatibility),
            "visual_quality":         float(self.visual_quality),
            "findings":               list(self.findings),
            "recommendations":        list(self.recommendations),
            "reviewed_at":            float(self.reviewed_at),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "LookdevReviewResult":
        d = d if isinstance(d, dict) else {}
        return cls(
            review_id=str(d.get("review_id") or f"rev_{uuid.uuid4().hex[:8]}"),
            score=float(d.get("score") or 0.0),
            grade=str(d.get("grade", "F")),
            production_ready=bool(d.get("production_ready", False)),
            material_consistency=float(d.get("material_consistency") or 0.0),
            environment_coherence=float(d.get("environment_coherence") or 0.0),
            renderer_compatibility=float(d.get("renderer_compatibility") or 0.0),
            visual_quality=float(d.get("visual_quality") or 0.0),
            findings=list(d.get("findings") or []),
            recommendations=list(d.get("recommendations") or []),
            reviewed_at=float(d.get("reviewed_at") or time.time()),
        )


class LookdevReview:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._review_count = 0

    def review_material_consistency(
        self,
        assignments: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        try:
            assignments = assignments if isinstance(assignments, list) else []
            findings: List[str] = []
            warnings: List[str] = []

            if not assignments:
                findings.append("No materials assigned — zero assignments in lookdev plan.")
                return {"score": 0.0, "findings": findings, "warnings": warnings}

            lib = get_material_library()
            known_mats = {m.name for m in lib.list_materials()}
            unknown: List[str] = []
            mat_names = []
            categories: List[str] = []

            for a in assignments:
                if not isinstance(a, dict):
                    continue
                mat = str(a.get("material_name") or a.get("material") or "")
                if mat:
                    mat_names.append(mat)
                    if mat not in known_mats:
                        unknown.append(mat)
                    entry = lib.search_materials(query=mat)
                    if entry:
                        categories.append(entry[0].category)

            if unknown:
                warnings.append(f"Unknown materials (not in MaterialLibrary): {', '.join(sorted(set(unknown)))}.")

            score = 1.0
            # Penalise unknown materials
            if mat_names:
                known_ratio = (len(mat_names) - len(unknown)) / len(mat_names)
                score = max(0.0, score * known_ratio)

            # Consistency: check for duplicate same-category assignments on different assets
            cat_count: Dict[str, int] = {}
            for c in categories:
                cat_count[c] = cat_count.get(c, 0) + 1
            dominant = max(cat_count.values(), default=0)
            if dominant == len(assignments) and len(assignments) > 1:
                warnings.append("All assets share the same material category — consider material diversity.")

            return {"score": round(score, 3), "findings": findings, "warnings": warnings}
        except Exception as exc:
            return {"score": 0.0, "findings": [f"review_material_consistency error: {exc}"], "warnings": []}

    def review_environment_coherence(
        self,
        scene_dict: Dict[str, Any],
    ) -> Dict[str, Any]:
        try:
            scene_dict = scene_dict if isinstance(scene_dict, dict) else {}
            findings: List[str] = []
            warnings: List[str] = []
            score = 1.0

            environment = str(scene_dict.get("environment") or "").strip()
            if not environment:
                findings.append("No environment specified — cannot validate environment coherence.")
                score = 0.4

            materials = scene_dict.get("materials") or []
            if not isinstance(materials, list):
                materials = []

            if materials and environment:
                # Check if materials match a known lookdev pattern
                patterns = get_lookdev_patterns().search_patterns(environment=environment.lower())
                if not patterns:
                    patterns = get_lookdev_patterns().search_patterns(query=environment.lower())
                if patterns:
                    pattern_mats = set(patterns[0].materials)
                    used_mats = set(str(m) for m in materials)
                    overlap = len(used_mats & pattern_mats)
                    if overlap == 0:
                        warnings.append(
                            f"Materials do not match the '{environment}' lookdev pattern "
                            f"(expected: {', '.join(sorted(patterns[0].materials))})."
                        )
                        score = max(0.0, score - 0.3)
                    elif overlap < len(pattern_mats) // 2:
                        warnings.append(f"Partial material match for '{environment}' pattern.")
                        score = max(0.0, score - 0.1)
                else:
                    warnings.append(f"No lookdev pattern found for environment '{environment}'.")
                    score = max(0.0, score - 0.15)

            return {"score": round(score, 3), "findings": findings, "warnings": warnings}
        except Exception as exc:
            return {"score": 0.0, "findings": [f"review_environment_coherence error: {exc}"], "warnings": []}

    def review_renderer_compatibility(
        self,
        plan_dict: Dict[str, Any],
        renderer: str,
    ) -> Dict[str, Any]:
        try:
            plan_dict = plan_dict if isinstance(plan_dict, dict) else {}
            findings: List[str] = []
            warnings: List[str] = []

            renderer = str(renderer or "").lower().strip()
            if not renderer:
                findings.append("Invalid renderer — no renderer specified.")
                return {"score": 0.0, "findings": findings, "warnings": warnings}

            profiles = get_renderer_profiles()
            if not profiles.validate_renderer_support(renderer):
                findings.append(
                    f"Invalid renderer '{renderer}' — not in SUPPORTED_RENDERERS "
                    f"(arnold, karma, usd_preview_surface)."
                )
                return {"score": 0.0, "findings": findings, "warnings": warnings}

            score = 1.0
            assignments = plan_dict.get("assignments") or []
            if isinstance(assignments, list):
                for a in assignments:
                    if isinstance(a, dict):
                        asgn_renderer = str(a.get("renderer", renderer))
                        if asgn_renderer and asgn_renderer != renderer:
                            warnings.append(
                                f"Assignment renderer '{asgn_renderer}' differs from plan renderer '{renderer}'."
                            )
                            score = max(0.0, score - 0.1)
                            break

            return {"score": round(score, 3), "findings": findings, "warnings": warnings}
        except Exception as exc:
            return {"score": 0.0, "findings": [f"review_renderer_compatibility error: {exc}"], "warnings": []}

    def review_visual_quality(
        self,
        scene_dict: Dict[str, Any],
    ) -> Dict[str, Any]:
        try:
            scene_dict = scene_dict if isinstance(scene_dict, dict) else {}
            findings: List[str] = []
            warnings: List[str] = []
            score = 1.0

            materials = scene_dict.get("materials") or []
            if not isinstance(materials, list):
                materials = []
            environment = str(scene_dict.get("environment") or "").lower()

            # Check emissive panels in outdoor environments
            emissive_count = sum(1 for m in materials if "emissive" in str(m).lower())
            if emissive_count > 3:
                warnings.append(
                    f"High emissive material count ({emissive_count}) — "
                    "too many glowing surfaces reduces realism."
                )
                score = max(0.0, score - 0.15)

            is_outdoor = any(kw in environment for kw in _OUTDOOR_ENVIRONMENTS)
            if is_outdoor and emissive_count > 0:
                warnings.append(
                    f"Emissive materials ({emissive_count}) in outdoor environment '{environment}' — "
                    "emissive panels are typically indoor/sci-fi elements."
                )
                score = max(0.0, score - 0.1)

            # Check material roughness coverage via library
            lib = get_material_library()
            undefined_roughness: List[str] = []
            for mat_name in materials:
                entries = lib.search_materials(query=str(mat_name))
                if entries:
                    props = entries[0].properties
                    if "roughness" not in props:
                        undefined_roughness.append(str(mat_name))
            if undefined_roughness:
                warnings.append(
                    f"Materials without defined roughness: {', '.join(undefined_roughness)}."
                )
                score = max(0.0, score - 0.05 * len(undefined_roughness))

            if not materials:
                findings.append("No materials defined — visual quality cannot be assessed.")
                score = 0.3

            return {"score": round(max(0.0, score), 3), "findings": findings, "warnings": warnings}
        except Exception as exc:
            return {"score": 0.0, "findings": [f"review_visual_quality error: {exc}"], "warnings": []}

    def review_lookdev(self, lookdev_dict: Dict[str, Any]) -> LookdevReviewResult:
        try:
            return self._do_review(lookdev_dict)
        except Exception as exc:
            return LookdevReviewResult(
                score=0.0,
                grade="F",
                production_ready=False,
                findings=[f"review_lookdev failed: {exc}"],
            )

    def _do_review(self, lookdev_dict: Dict[str, Any]) -> LookdevReviewResult:
        lookdev_dict = lookdev_dict if isinstance(lookdev_dict, dict) else {}
        renderer    = str(lookdev_dict.get("renderer", "usd_preview_surface"))
        environment = str(lookdev_dict.get("environment", ""))
        assignments = lookdev_dict.get("assignments") or []
        materials   = lookdev_dict.get("materials") or []

        # Build sub-dicts
        scene_dict = {"environment": environment, "materials": materials}

        r_consistency   = self.review_material_consistency(assignments if isinstance(assignments, list) else [])
        r_coherence     = self.review_environment_coherence(scene_dict)
        r_compatibility = self.review_renderer_compatibility(lookdev_dict, renderer)
        r_quality       = self.review_visual_quality(scene_dict)

        mat_score   = float(r_consistency.get("score", 0.0))
        env_score   = float(r_coherence.get("score", 0.0))
        rend_score  = float(r_compatibility.get("score", 0.0))
        vis_score   = float(r_quality.get("score", 0.0))

        overall = round(
            mat_score  * 0.30
            + env_score   * 0.25
            + rend_score  * 0.25
            + vis_score   * 0.20,
            3,
        )

        findings: List[str] = []
        findings += r_consistency.get("findings", [])
        findings += r_coherence.get("findings", [])
        findings += r_compatibility.get("findings", [])
        findings += r_quality.get("findings", [])

        recommendations: List[str] = []
        recommendations += r_consistency.get("warnings", [])
        recommendations += r_coherence.get("warnings", [])
        recommendations += r_compatibility.get("warnings", [])
        recommendations += r_quality.get("warnings", [])

        blocking = _has_blocking(findings)
        production_ready = overall >= _PRODUCTION_THRESHOLD and not blocking

        with self._lock:
            self._review_count += 1

        return LookdevReviewResult(
            score=overall,
            grade=_grade(overall),
            production_ready=production_ready,
            material_consistency=mat_score,
            environment_coherence=env_score,
            renderer_compatibility=rend_score,
            visual_quality=vis_score,
            findings=findings,
            recommendations=recommendations,
        )


_INSTANCE: Optional[LookdevReview] = None
_INSTANCE_LOCK = threading.Lock()


def get_lookdev_review() -> LookdevReview:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = LookdevReview()
    return _INSTANCE


def reset_lookdev_review_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
