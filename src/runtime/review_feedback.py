"""
Review Feedback Engine (Tier 5 — Production Knowledge System)
==============================================================
Converts production reviews into structured, actionable knowledge.
Extracts failure categories, strength categories, and improvement
actions. Optionally persists feedback to ProductionMemory.

DESIGN RULE: NO bridge calls. Deterministic extraction from review dicts.

Public API:
    ReviewFeedbackEngine
        .extract_feedback(review) -> dict
        .extract_failures(review) -> list[str]
        .extract_strengths(review) -> list[str]
        .build_improvement_actions(feedback) -> list[dict]
        .update_production_memory(review, scene_id=None) -> dict
        .stats() -> dict

    get_review_feedback_engine() -> ReviewFeedbackEngine   (singleton)
    reset_review_feedback_engine_for_tests()
"""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Keyword → failure category mapping
# ---------------------------------------------------------------------------

_FAILURE_KEYWORD_MAP: Dict[str, str] = {
    "fog too dense":         "fog_density_high",
    "density too high":      "fog_density_high",
    "density exceeds":       "fog_density_high",
    "obscured":              "fog_density_high",
    "hero readability":      "hero_focus_low",
    "no hero":               "hero_absent",
    "focal point":           "hero_focus_low",
    "flat":                  "depth_flat",
    "depth is flat":         "depth_flat",
    "depth layering is absent": "depth_flat",
    "no depth":              "depth_flat",
    "midground":             "midground_empty",
    "background zone is empty": "background_empty",
    "key light absent":      "key_light_missing",
    "key light":             "key_light_missing",
    "rim light absent":      "rim_light_missing",
    "rim light":             "rim_light_missing",
    "light balance":         "light_balance_poor",
    "fill light":            "fill_light_excessive",
    "camera shake":          "camera_shake_high",
    "shake intensity":       "camera_shake_high",
    "establishing shot":     "establishing_shot_missing",
    "no camera":             "camera_absent",
    "framing is undefined":  "camera_absent",
    "render":                "render_issue",
    "production_ready":      "production_not_ready",
    "aa samples":            "sampling_low",
    "motion blur":           "motion_blur_off",
    "exr":                   "output_format_wrong",
    "emission":              "aov_missing",
    "cryptomatte":           "aov_missing",
}

_STRENGTH_KEYWORD_MAP: Dict[str, str] = {
    "hero":                  "hero_focus_strong",
    "depth separation":      "depth_strong",
    "zone layering":         "depth_strong",
    "balanced":              "light_balance_good",
    "practical lighting":    "practicals_good",
    "cinematic":             "cinematic_quality",
    "push-in":               "camera_motion_cinematic",
    "orbital":               "camera_motion_cinematic",
    "hero_focus":            "camera_hero_focus",
    "establishing":          "establishing_shot_present",
    "production-ready":      "production_ready",
    "atmosphere":            "atmosphere_supports_depth",
}

# Improvement action templates keyed by failure category
_IMPROVEMENT_ACTIONS: Dict[str, Dict[str, Any]] = {
    "fog_density_high":       {"action": "reduce_fog_density",      "target": "atmosphere_plan",    "priority": "high"},
    "hero_absent":            {"action": "add_hero_asset",           "target": "zones.hero_area",   "priority": "critical"},
    "hero_focus_low":         {"action": "reduce_hero_count",        "target": "zones.hero_area",   "priority": "high"},
    "depth_flat":             {"action": "add_depth_layers",         "target": "scene_layout",      "priority": "high"},
    "midground_empty":        {"action": "populate_midground",       "target": "zones.midground",   "priority": "medium"},
    "background_empty":       {"action": "populate_background",      "target": "zones.background",  "priority": "medium"},
    "key_light_missing":      {"action": "add_key_light",            "target": "lighting_plan",     "priority": "critical"},
    "rim_light_missing":      {"action": "add_rim_light",            "target": "lighting_plan",     "priority": "high"},
    "light_balance_poor":     {"action": "rebalance_lights",         "target": "lighting_plan",     "priority": "medium"},
    "fill_light_excessive":   {"action": "reduce_fill_intensity",    "target": "lighting_plan",     "priority": "medium"},
    "camera_shake_high":      {"action": "reduce_shake_intensity",   "target": "camera_plan",       "priority": "medium"},
    "camera_absent":          {"action": "add_camera_plan",          "target": "camera_plan",       "priority": "critical"},
    "establishing_shot_missing": {"action": "add_establishing_shot", "target": "camera_plan",       "priority": "high"},
    "render_issue":           {"action": "review_render_settings",   "target": "render_plan",       "priority": "medium"},
    "sampling_low":           {"action": "increase_aa_samples",      "target": "render_plan",       "priority": "medium"},
    "motion_blur_off":        {"action": "enable_motion_blur",       "target": "render_plan",       "priority": "medium"},
    "output_format_wrong":    {"action": "set_exr_output",           "target": "render_plan",       "priority": "high"},
    "aov_missing":            {"action": "add_required_aovs",        "target": "render_plan",       "priority": "medium"},
}


class ReviewFeedbackEngine:
    """Converts reviews into structured production feedback."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._extraction_count = 0

    def extract_feedback(self, review: Dict[str, Any]) -> Dict[str, Any]:
        """Extract structured feedback from a review dict.

        Works with any review format: cinematic_scene_review,
        scene_realization_review, or custom review dicts.

        Returns:
            {failures, strengths, issues, recommendations,
             overall_score, production_ready, grade}
        """
        failures  = self.extract_failures(review)
        strengths = self.extract_strengths(review)

        overall_score = float(review.get("overall_score", 0.0))
        production_ready = bool(review.get("production_ready", False))
        grade = str(review.get("grade", _grade(overall_score)))

        # Collect raw issue text
        raw_issues: List[str] = []
        for key in ("findings", "issues", "critical_findings", "blocking_issues"):
            val = review.get(key)
            if isinstance(val, list):
                raw_issues.extend(str(x) for x in val)

        raw_recs: List[str] = []
        for key in ("recommendations",):
            val = review.get(key)
            if isinstance(val, list):
                raw_recs.extend(str(x) for x in val)

        with self._lock:
            self._extraction_count += 1

        return {
            "failures":         failures,
            "strengths":        strengths,
            "issues":           raw_issues,
            "recommendations":  raw_recs,
            "overall_score":    overall_score,
            "production_ready": production_ready,
            "grade":            grade,
        }

    def extract_failures(self, review: Dict[str, Any]) -> List[str]:
        """Extract structured failure category names from a review.

        Returns list of failure category strings (e.g. "fog_density_high").
        """
        raw_text: List[str] = []
        for key in ("findings", "issues", "critical_findings", "blocking_issues"):
            val = review.get(key)
            if isinstance(val, list):
                raw_text.extend(str(x).lower() for x in val)
        if isinstance(review.get("review_summary"), str):
            raw_text.append(review["review_summary"].lower())

        seen: set = set()
        failures: List[str] = []
        for text in raw_text:
            for kw, category in _FAILURE_KEYWORD_MAP.items():
                if kw.lower() in text and category not in seen:
                    seen.add(category)
                    failures.append(category)
        return failures

    def extract_strengths(self, review: Dict[str, Any]) -> List[str]:
        """Extract structured strength category names from a review."""
        raw_text: List[str] = []
        for key in ("strengths", "findings"):
            val = review.get(key)
            if isinstance(val, list):
                raw_text.extend(str(x).lower() for x in val)
        if isinstance(review.get("review_summary"), str):
            raw_text.append(review["review_summary"].lower())

        seen: set = set()
        strengths: List[str] = []
        for text in raw_text:
            for kw, category in _STRENGTH_KEYWORD_MAP.items():
                if kw.lower() in text and category not in seen:
                    seen.add(category)
                    strengths.append(category)
        return strengths

    def build_improvement_actions(
        self, feedback: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Convert failure categories into actionable improvement steps.

        Args:
            feedback: Return value of extract_feedback().

        Returns:
            List of action dicts sorted by priority (critical first).
        """
        _priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        actions: List[Dict[str, Any]] = []
        seen: set = set()

        for failure in feedback.get("failures", []):
            if failure in _IMPROVEMENT_ACTIONS and failure not in seen:
                seen.add(failure)
                action = dict(_IMPROVEMENT_ACTIONS[failure])
                action["failure_category"] = failure
                actions.append(action)

        actions.sort(key=lambda a: _priority_order.get(a.get("priority", "low"), 3))
        return actions

    def update_production_memory(
        self,
        review: Dict[str, Any],
        scene_id: Optional[str] = None,
        scene_type: Optional[str] = None,
        lighting_style: Optional[str] = None,
        camera_style: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Extract feedback and record it to ProductionMemory.

        Does NOT raise if ProductionMemory is unavailable — returns error key
        instead so callers can handle gracefully.

        Returns:
            {feedback, actions, memory_updated, scene_record_id, review_record_id}
        """
        feedback = self.extract_feedback(review)
        actions  = self.build_improvement_actions(feedback)

        result: Dict[str, Any] = {
            "feedback":        feedback,
            "actions":         actions,
            "memory_updated":  False,
            "scene_record_id": None,
            "review_record_id": None,
        }

        try:
            from src.runtime.production_memory import get_production_memory
            mem = get_production_memory()

            # Record the scene if we have enough info
            if scene_type or scene_id:
                score = feedback["overall_score"]
                status = (
                    "success" if feedback["production_ready"]
                    else "partial" if score >= 0.5
                    else "failure"
                )
                sid = mem.record_scene({
                    "scene_type":     scene_type or "unknown",
                    "lighting_style": lighting_style or "",
                    "camera_style":   camera_style or "",
                    "score":          score,
                    "status":         status,
                })
                result["scene_record_id"] = sid

                # Record failure patterns for each failure category
                for failure in feedback["failures"]:
                    mem.record_failure({
                        "scene_type":    scene_type or "unknown",
                        "failure_type":  failure,
                        "description":   failure,
                        "lighting_style": lighting_style or "",
                        "camera_style":  camera_style or "",
                    })

            # Record the review
            rev_id = mem.record_review(scene_id or result.get("scene_record_id") or "", review)
            result["review_record_id"] = rev_id
            result["memory_updated"] = True

        except Exception as exc:
            result["error"] = str(exc)

        return result

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {"extraction_count": self._extraction_count}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _grade(score: float) -> str:
    if score >= 0.9: return "A"
    if score >= 0.8: return "B"
    if score >= 0.7: return "C"
    if score >= 0.6: return "D"
    return "F"


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[ReviewFeedbackEngine] = None
_INSTANCE_LOCK = threading.Lock()


def get_review_feedback_engine() -> ReviewFeedbackEngine:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = ReviewFeedbackEngine()
    return _INSTANCE


def reset_review_feedback_engine_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
