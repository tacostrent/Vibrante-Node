"""
Lighting Review (Tier 15)
==========================
Evaluates lighting plan quality across 6 dimensions:
  - Readability          (20%)
  - Mood accuracy        (20%)
  - Story support        (20%)
  - Visual hierarchy     (15%)
  - Color harmony        (15%)
  - Exposure quality     (10%)

production_ready requires score >= 0.70 AND no blocking findings.
Deterministic, thread-safe, no Houdini dependency.
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .lighting_readability_engine import get_lighting_readability_engine
from .lighting_mood_engine import get_lighting_mood_engine
from .lighting_color_engine import get_lighting_color_engine
from .lighting_exposure_engine import get_lighting_exposure_engine

_PRODUCTION_THRESHOLD = 0.70
_GRADE_THRESHOLDS = [
    (0.85, "A"),
    (0.70, "B"),
    (0.55, "C"),
    (0.40, "D"),
]

_BLOCKING_KEYWORDS = frozenset({
    "no key light",
    "no lighting defined",
    "empty plan",
    "no light sources",
    "zero lights",
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
class LightingReviewResult:
    review_id: str = field(default_factory=lambda: f"lrev_{uuid.uuid4().hex[:8]}")
    score: float = 0.0
    grade: str = "F"
    production_ready: bool = False
    readability: float = 0.0
    mood_accuracy: float = 0.0
    story_support: float = 0.0
    visual_hierarchy: float = 0.0
    color_harmony: float = 0.0
    exposure_quality: float = 0.0
    findings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    reviewed_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "review_id":        str(self.review_id),
            "score":            float(self.score),
            "grade":            str(self.grade),
            "production_ready": bool(self.production_ready),
            "readability":      float(self.readability),
            "mood_accuracy":    float(self.mood_accuracy),
            "story_support":    float(self.story_support),
            "visual_hierarchy": float(self.visual_hierarchy),
            "color_harmony":    float(self.color_harmony),
            "exposure_quality": float(self.exposure_quality),
            "findings":         list(self.findings),
            "recommendations":  list(self.recommendations),
            "reviewed_at":      float(self.reviewed_at),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "LightingReviewResult":
        d = d if isinstance(d, dict) else {}
        return cls(
            review_id=str(d.get("review_id") or f"lrev_{uuid.uuid4().hex[:8]}"),
            score=float(d.get("score") or 0.0),
            grade=str(d.get("grade", "F")),
            production_ready=bool(d.get("production_ready", False)),
            readability=float(d.get("readability") or 0.0),
            mood_accuracy=float(d.get("mood_accuracy") or 0.0),
            story_support=float(d.get("story_support") or 0.0),
            visual_hierarchy=float(d.get("visual_hierarchy") or 0.0),
            color_harmony=float(d.get("color_harmony") or 0.0),
            exposure_quality=float(d.get("exposure_quality") or 0.0),
            findings=list(d.get("findings") or []),
            recommendations=list(d.get("recommendations") or []),
            reviewed_at=float(d.get("reviewed_at") or time.time()),
        )


class LightingReview:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._review_count = 0

    # ------------------------------------------------------------------
    # Sub-reviewers
    # ------------------------------------------------------------------

    def review_readability(self, plan_dict: Dict[str, Any]) -> Dict[str, Any]:
        try:
            result = get_lighting_readability_engine().evaluate_readability(plan_dict)
            return {
                "score":    result.score,
                "findings": result.findings,
                "warnings": result.recommendations,
            }
        except Exception as exc:
            return {"score": 0.0, "findings": [f"review_readability error: {exc}"], "warnings": []}

    def review_mood_accuracy(self, plan_dict: Dict[str, Any]) -> Dict[str, Any]:
        try:
            plan_dict = plan_dict if isinstance(plan_dict, dict) else {}
            findings: List[str] = []
            warnings: List[str] = []

            mood = str(plan_dict.get("mood", "")).lower().strip()
            intent = str(plan_dict.get("intent", "")).lower()

            if not mood:
                warnings.append("No mood specified in plan — mood accuracy cannot be evaluated.")
                return {"score": 0.7, "findings": findings, "warnings": warnings}

            known_moods = get_lighting_mood_engine().list_moods()
            if mood not in known_moods:
                warnings.append(f"Mood '{mood}' is not a known builtin mood.")
                return {"score": 0.6, "findings": findings, "warnings": warnings}

            # Verify mood is consistent with intent text
            inferred = get_lighting_mood_engine().infer_mood(intent) if intent else ""
            score = 1.0
            if inferred and inferred != mood:
                warnings.append(
                    f"Plan mood '{mood}' doesn't match inferred mood '{inferred}' from intent text."
                )
                score = 0.7

            return {"score": round(score, 3), "findings": findings, "warnings": warnings}
        except Exception as exc:
            return {"score": 0.0, "findings": [f"review_mood_accuracy error: {exc}"], "warnings": []}

    def review_story_support(self, plan_dict: Dict[str, Any]) -> Dict[str, Any]:
        try:
            plan_dict = plan_dict if isinstance(plan_dict, dict) else {}
            findings: List[str] = []
            warnings: List[str] = []

            key = plan_dict.get("key_light") or {}
            rim = plan_dict.get("rim_light") or {}
            hierarchy = plan_dict.get("hierarchy_notes") or {}

            if not key:
                findings.append("No key light defined — story cannot be supported without a primary light.")
                return {"score": 0.0, "findings": findings, "warnings": warnings}

            score = 0.8
            hero_subjects = hierarchy.get("hero", [])
            if not hero_subjects:
                warnings.append("No hero subject in hierarchy — story focus may be unclear.")
                score = 0.6

            if not rim:
                warnings.append("No rim light — hero subject may lack definition and story presence.")
                score = max(0.0, score - 0.1)

            intent = str(plan_dict.get("intent", ""))
            mood = str(plan_dict.get("mood", ""))
            if not intent and not mood:
                warnings.append("No intent or mood defined — story direction is missing.")
                score = max(0.0, score - 0.1)

            return {"score": round(score, 3), "findings": findings, "warnings": warnings}
        except Exception as exc:
            return {"score": 0.0, "findings": [f"review_story_support error: {exc}"], "warnings": []}

    def review_visual_hierarchy(self, plan_dict: Dict[str, Any]) -> Dict[str, Any]:
        try:
            plan_dict = plan_dict if isinstance(plan_dict, dict) else {}
            findings: List[str] = []
            warnings: List[str] = []
            score = 1.0

            hierarchy = plan_dict.get("hierarchy_notes") or {}
            hero = hierarchy.get("hero", [])
            background = hierarchy.get("background", [])

            if not hero and not background:
                warnings.append("No visual hierarchy defined — all subjects may compete equally.")
                score = 0.6

            key = plan_dict.get("key_light") or {}
            rim = plan_dict.get("rim_light") or {}
            key_i = float(key.get("intensity", 0.0))
            rim_i = float(rim.get("intensity", 0.0))

            if key_i > 0 and rim_i > 0:
                if rim_i / key_i > 1.5:
                    warnings.append(
                        f"Rim intensity ({rim_i:.2f}) exceeds key ({key_i:.2f}) — subject silhouette may overpower scene."
                    )
                    score = max(0.0, score - 0.1)

            return {"score": round(score, 3), "findings": findings, "warnings": warnings}
        except Exception as exc:
            return {"score": 0.0, "findings": [f"review_visual_hierarchy error: {exc}"], "warnings": []}

    def review_color_harmony(self, plan_dict: Dict[str, Any]) -> Dict[str, Any]:
        try:
            plan_dict = plan_dict if isinstance(plan_dict, dict) else {}
            findings: List[str] = []
            warnings: List[str] = []

            color_strategy = plan_dict.get("color_strategy") or {}
            if not color_strategy:
                warnings.append("No color strategy in plan — color harmony cannot be evaluated.")
                return {"score": 0.7, "findings": findings, "warnings": warnings}

            primary = color_strategy.get("primary_color", [1.0, 1.0, 1.0])
            accent  = color_strategy.get("accent_color",  [0.5, 0.5, 0.5])
            harmony = get_lighting_color_engine().evaluate_harmony(primary, accent)

            score = 1.0 if harmony.get("harmony_ok", True) else 0.6
            for finding in harmony.get("findings", []):
                warnings.append(finding)

            return {"score": round(score, 3), "findings": findings, "warnings": warnings}
        except Exception as exc:
            return {"score": 0.0, "findings": [f"review_color_harmony error: {exc}"], "warnings": []}

    def review_exposure_quality(self, plan_dict: Dict[str, Any]) -> Dict[str, Any]:
        try:
            plan_dict = plan_dict if isinstance(plan_dict, dict) else {}
            findings: List[str] = []
            warnings: List[str] = []

            exposure = plan_dict.get("exposure") or {}
            if not exposure:
                warnings.append("No exposure data in plan.")
                return {"score": 0.7, "findings": findings, "warnings": warnings}

            mood = str(plan_dict.get("mood", ""))
            recommended = get_lighting_exposure_engine().recommend_exposure(mood=mood)
            plan_ev = float(exposure.get("ev_target", 0.0))
            rec_ev  = recommended.ev_target
            ev_diff = abs(plan_ev - rec_ev)

            score = 1.0
            if ev_diff > 1.5:
                warnings.append(
                    f"Plan EV {plan_ev:.1f} differs from recommended EV {rec_ev:.1f} by {ev_diff:.1f} stops."
                )
                score = max(0.0, 1.0 - ev_diff * 0.15)

            return {"score": round(score, 3), "findings": findings, "warnings": warnings}
        except Exception as exc:
            return {"score": 0.0, "findings": [f"review_exposure_quality error: {exc}"], "warnings": []}

    # ------------------------------------------------------------------
    # Main review
    # ------------------------------------------------------------------

    def review_plan(self, plan_dict: Dict[str, Any]) -> LightingReviewResult:
        """Review a lighting plan dict across 6 quality dimensions."""
        try:
            return self._do_review(plan_dict if isinstance(plan_dict, dict) else {})
        except Exception as exc:
            return LightingReviewResult(
                score=0.0, grade="F", production_ready=False,
                findings=[f"review_plan failed: {exc}"],
            )

    def _do_review(self, plan: Dict[str, Any]) -> LightingReviewResult:
        r_read    = self.review_readability(plan)
        r_mood    = self.review_mood_accuracy(plan)
        r_story   = self.review_story_support(plan)
        r_hier    = self.review_visual_hierarchy(plan)
        r_color   = self.review_color_harmony(plan)
        r_expo    = self.review_exposure_quality(plan)

        read_s  = float(r_read.get("score",  0.0))
        mood_s  = float(r_mood.get("score",  0.0))
        story_s = float(r_story.get("score", 0.0))
        hier_s  = float(r_hier.get("score",  0.0))
        color_s = float(r_color.get("score", 0.0))
        expo_s  = float(r_expo.get("score",  0.0))

        overall = round(
            read_s  * 0.20
            + mood_s  * 0.20
            + story_s * 0.20
            + hier_s  * 0.15
            + color_s * 0.15
            + expo_s  * 0.10,
            3,
        )

        findings: List[str] = (
            r_read.get("findings",  [])
            + r_mood.get("findings",  [])
            + r_story.get("findings", [])
            + r_hier.get("findings",  [])
            + r_color.get("findings", [])
            + r_expo.get("findings",  [])
        )
        recommendations: List[str] = (
            r_read.get("warnings",  [])
            + r_mood.get("warnings",  [])
            + r_story.get("warnings", [])
            + r_hier.get("warnings",  [])
            + r_color.get("warnings", [])
            + r_expo.get("warnings",  [])
        )

        blocking = _has_blocking(findings)
        production_ready = overall >= _PRODUCTION_THRESHOLD and not blocking

        with self._lock:
            self._review_count += 1

        return LightingReviewResult(
            score=overall,
            grade=_grade(overall),
            production_ready=production_ready,
            readability=read_s,
            mood_accuracy=mood_s,
            story_support=story_s,
            visual_hierarchy=hier_s,
            color_harmony=color_s,
            exposure_quality=expo_s,
            findings=findings,
            recommendations=recommendations,
        )


_INSTANCE: Optional[LightingReview] = None
_INSTANCE_LOCK = threading.Lock()


def get_lighting_review() -> LightingReview:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = LightingReview()
    return _INSTANCE


def reset_lighting_review_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
