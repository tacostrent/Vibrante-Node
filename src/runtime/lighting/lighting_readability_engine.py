"""
Lighting Readability Engine (Tier 15)
======================================
Evaluates visual clarity and readability of a lighting plan.
Deterministic, thread-safe, no Houdini dependency.
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ReadabilityResult:
    result_id: str = field(default_factory=lambda: f"rr_{uuid.uuid4().hex[:8]}")
    score: float = 0.0
    subject_visibility: float = 0.0
    silhouette_quality: float = 0.0
    foreground_separation: float = 0.0
    background_separation: float = 0.0
    contrast_balance: float = 0.0
    findings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    evaluated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "result_id":             str(self.result_id),
            "score":                 float(self.score),
            "subject_visibility":    float(self.subject_visibility),
            "silhouette_quality":    float(self.silhouette_quality),
            "foreground_separation": float(self.foreground_separation),
            "background_separation": float(self.background_separation),
            "contrast_balance":      float(self.contrast_balance),
            "findings":              list(self.findings),
            "recommendations":       list(self.recommendations),
            "evaluated_at":          float(self.evaluated_at),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ReadabilityResult":
        d = d if isinstance(d, dict) else {}
        return cls(
            result_id=str(d.get("result_id") or f"rr_{uuid.uuid4().hex[:8]}"),
            score=float(d.get("score") or 0.0),
            subject_visibility=float(d.get("subject_visibility") or 0.0),
            silhouette_quality=float(d.get("silhouette_quality") or 0.0),
            foreground_separation=float(d.get("foreground_separation") or 0.0),
            background_separation=float(d.get("background_separation") or 0.0),
            contrast_balance=float(d.get("contrast_balance") or 0.0),
            findings=list(d.get("findings") or []),
            recommendations=list(d.get("recommendations") or []),
            evaluated_at=float(d.get("evaluated_at") or time.time()),
        )


class LightingReadabilityEngine:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._eval_count = 0

    # ------------------------------------------------------------------
    # Sub-evaluators
    # ------------------------------------------------------------------

    def _eval_subject_visibility(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate whether the key light adequately illuminates the subject."""
        findings: List[str] = []
        warnings: List[str] = []
        key = plan.get("key_light") or {}
        if not key:
            findings.append("No key light defined — subject visibility cannot be guaranteed.")
            return {"score": 0.0, "findings": findings, "warnings": warnings}
        intensity = float(key.get("intensity", 0.0))
        if intensity < 0.3:
            warnings.append(
                f"Key light intensity {intensity:.2f} is very low — subject may not be visible."
            )
            return {"score": max(0.0, intensity / 0.3 * 0.6), "findings": findings, "warnings": warnings}
        score = min(1.0, intensity)
        return {"score": round(score, 3), "findings": findings, "warnings": warnings}

    def _eval_silhouette_quality(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate rim/back light for subject silhouette separation."""
        findings: List[str] = []
        warnings: List[str] = []
        rim = plan.get("rim_light") or {}
        if not rim:
            warnings.append("No rim light — silhouette separation from background may be poor.")
            return {"score": 0.5, "findings": findings, "warnings": warnings}
        intensity = float(rim.get("intensity", 0.0))
        if intensity < 0.2:
            warnings.append(
                f"Rim light intensity {intensity:.2f} too low for effective silhouette separation."
            )
            return {"score": max(0.0, intensity / 0.2 * 0.6), "findings": findings, "warnings": warnings}
        score = min(1.0, 0.6 + intensity * 0.4)
        return {"score": round(score, 3), "findings": findings, "warnings": warnings}

    def _eval_foreground_separation(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate foreground/hero separation from midground."""
        findings: List[str] = []
        warnings: List[str] = []
        hierarchy = plan.get("hierarchy_notes") or {}
        hero = hierarchy.get("hero") or []
        if not hero:
            warnings.append("No hero subject defined in hierarchy — foreground separation cannot be verified.")
            return {"score": 0.7, "findings": findings, "warnings": warnings}
        rim = plan.get("rim_light") or {}
        key = plan.get("key_light") or {}
        rim_intensity = float(rim.get("intensity", 0.0))
        key_intensity = float(key.get("intensity", 0.0))
        if key_intensity > 0 and rim_intensity > 0:
            separation_ratio = rim_intensity / key_intensity
            if separation_ratio < 0.3:
                warnings.append(
                    f"Rim/key ratio {separation_ratio:.2f} too low — hero may blend into background."
                )
            score = min(1.0, 0.5 + separation_ratio)
        else:
            score = 0.5
        return {"score": round(score, 3), "findings": findings, "warnings": warnings}

    def _eval_background_separation(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate background relative darkness for depth perception."""
        findings: List[str] = []
        warnings: List[str] = []
        exposure = plan.get("exposure") or {}
        contrast = str(exposure.get("contrast_ratio", "")).lower()
        dynamic_range = float(exposure.get("dynamic_range_stops", 0.0))
        if not contrast and dynamic_range == 0.0:
            warnings.append("No exposure/contrast data — background separation indeterminate.")
            return {"score": 0.7, "findings": findings, "warnings": warnings}
        score = 0.8
        if contrast == "low":
            warnings.append("Low contrast — background may compete with subject.")
            score = 0.5
        elif contrast == "high":
            score = 1.0
        return {"score": round(score, 3), "findings": findings, "warnings": warnings}

    def _eval_contrast_balance(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate overall contrast balance between key and fill."""
        findings: List[str] = []
        warnings: List[str] = []
        key = plan.get("key_light") or {}
        fill = plan.get("fill_light") or {}
        key_i = float(key.get("intensity", 0.0))
        fill_i = float(fill.get("intensity", 0.0))

        if key_i == 0.0:
            findings.append("No key light — contrast balance cannot be determined.")
            return {"score": 0.0, "findings": findings, "warnings": warnings}

        if fill_i == 0.0:
            warnings.append("No fill light — shadows may be completely black; consider bounce fill.")
            score = 0.5
        else:
            ratio = key_i / fill_i
            # Ideal cinematic ratio is between 3:1 and 8:1
            if ratio < 2.0:
                warnings.append(f"Key:fill ratio {ratio:.1f}:1 too low — image may look flat.")
                score = 0.6
            elif ratio > 12.0:
                warnings.append(
                    f"Key:fill ratio {ratio:.1f}:1 very high — consider adding bounce fill to retain detail."
                )
                score = 0.7
            else:
                score = 1.0
        return {"score": round(score, 3), "findings": findings, "warnings": warnings}

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def evaluate_readability(self, plan_dict: Dict[str, Any]) -> ReadabilityResult:
        """Evaluate visual readability of a lighting plan dict."""
        try:
            return self._do_evaluate(plan_dict if isinstance(plan_dict, dict) else {})
        except Exception as exc:
            return ReadabilityResult(
                score=0.0,
                findings=[f"evaluate_readability error: {exc}"],
            )

    def _do_evaluate(self, plan: Dict[str, Any]) -> ReadabilityResult:
        r_vis     = self._eval_subject_visibility(plan)
        r_sil     = self._eval_silhouette_quality(plan)
        r_fg      = self._eval_foreground_separation(plan)
        r_bg      = self._eval_background_separation(plan)
        r_ctrst   = self._eval_contrast_balance(plan)

        vis_s   = float(r_vis.get("score",   0.0))
        sil_s   = float(r_sil.get("score",   0.0))
        fg_s    = float(r_fg.get("score",    0.0))
        bg_s    = float(r_bg.get("score",    0.0))
        ctrst_s = float(r_ctrst.get("score", 0.0))

        overall = round(
            vis_s   * 0.30
            + sil_s   * 0.25
            + fg_s    * 0.20
            + bg_s    * 0.15
            + ctrst_s * 0.10,
            3,
        )

        findings: List[str] = (
            r_vis.get("findings", [])
            + r_sil.get("findings", [])
            + r_fg.get("findings", [])
            + r_bg.get("findings", [])
            + r_ctrst.get("findings", [])
        )
        recommendations: List[str] = (
            r_vis.get("warnings", [])
            + r_sil.get("warnings", [])
            + r_fg.get("warnings", [])
            + r_bg.get("warnings", [])
            + r_ctrst.get("warnings", [])
        )

        with self._lock:
            self._eval_count += 1

        return ReadabilityResult(
            score=overall,
            subject_visibility=vis_s,
            silhouette_quality=sil_s,
            foreground_separation=fg_s,
            background_separation=bg_s,
            contrast_balance=ctrst_s,
            findings=findings,
            recommendations=recommendations,
        )

    def recommend_adjustments(self, plan_dict: Dict[str, Any]) -> List[str]:
        """Return a list of actionable adjustments to improve readability."""
        try:
            result = self.evaluate_readability(plan_dict)
            adjustments: List[str] = list(result.findings) + list(result.recommendations)
            if result.score >= 0.8:
                adjustments.append("Readability is strong — no major adjustments required.")
            return adjustments
        except Exception:
            return []

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            return {"eval_calls": self._eval_count}


_INSTANCE: Optional[LightingReadabilityEngine] = None
_INSTANCE_LOCK = threading.Lock()


def get_lighting_readability_engine() -> LightingReadabilityEngine:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = LightingReadabilityEngine()
    return _INSTANCE


def reset_lighting_readability_engine_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
