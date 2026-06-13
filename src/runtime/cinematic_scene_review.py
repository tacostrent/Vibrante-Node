"""
Cinematic Scene Review (Tier 4 — Cinematic Orchestration)
==========================================================
Evaluates cinematic quality of a fully orchestrated scene.
Integrates findings from lighting, camera, atmosphere, and hierarchy.

DESIGN RULE: NO bridge calls. Advisory only. Deterministic.
IMPORTANT: "Execution successful" is NEVER an acceptable review finding.
           Every review must return SPECIFIC cinematic criteria.

Public API:
    CinematicSceneReview
        .evaluate_cinematic_quality(scene_data) -> dict
        .evaluate_visual_storytelling(zones, lighting_plan, camera_plan) -> dict
        .evaluate_depth_readability(zones, atmosphere_plan) -> dict
        .evaluate_atmosphere_balance(atmosphere_plan, lighting_plan) -> dict
        .generate_cinematic_review(scene_data) -> dict
    get_cinematic_scene_review() -> CinematicSceneReview
    reset_cinematic_scene_review_for_tests()
"""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Scoring weights
# ---------------------------------------------------------------------------

_CINEMATIC_SCORE_WEIGHTS: Dict[str, float] = {
    "storytelling": 0.30,
    "depth":        0.25,
    "atmosphere":   0.20,
    "lighting":     0.15,
    "camera":       0.10,
}

# ---------------------------------------------------------------------------
# Specific critique messages — NEVER generic
# ---------------------------------------------------------------------------

_CINEMATIC_CRITIQUES: Dict[str, str] = {
    "no_hero":            "No hero asset present — scene has no narrative focal point.",
    "no_depth":           "Depth layering is absent — scene reads as flat.",
    "no_atmosphere":      "No atmospheric elements — depth separation relies on geometry alone.",
    "fog_too_dense":      "Atmosphere density too high — mid-ground assets are obscured.",
    "no_key_light":       "Key light absent — primary illumination undefined.",
    "rim_missing":        "Rim light absent — hero and background merge without edge separation.",
    "no_camera":          "No camera plan provided — framing is undefined.",
    "low_readability":    "Scene readability is below cinematic threshold.",
    "light_flat":         "Lighting balance is flat — fill light dominates, removing depth.",
    "camera_shake_high":  "Camera shake intensity exceeds readability threshold.",
    "no_practicals":      "No practical lights — scene environment lacks internal light sources.",
    "storytelling_weak":  "Visual storytelling is weak — hero, lighting, and camera are misaligned.",
    "depth_strong":       "Cinematic depth separation is strong — zone layering reads clearly.",
    "hero_excellent":     "Hero asset readability is excellent — focal point is clear and lit.",
    "atmosphere_correct": "Atmosphere density supports lighting correctly — depth is enhanced.",
    "practical_good":     "Practical lighting improves scene environment storytelling.",
    "camera_cinematic":   "Camera pacing feels cinematic and readable.",
    "depth_fog_correct":  "Depth fog density is appropriate — silhouettes remain readable.",
}

# ---------------------------------------------------------------------------
# Grade thresholds
# ---------------------------------------------------------------------------

_CINEMATIC_GRADE_THRESHOLDS: Dict[str, float] = {
    "A": 0.9,
    "B": 0.8,
    "C": 0.7,
    "D": 0.6,
}

# Critical finding substrings used by production_ready check
_CRITICAL_KEYWORDS = ("absent", "no hero", "flat", "undefined")


def _grade(score: float) -> str:
    """Return letter grade for a 0.0–1.0 score."""
    for letter, threshold in _CINEMATIC_GRADE_THRESHOLDS.items():
        if score >= threshold:
            return letter
    return "F"


class CinematicSceneReview:
    """
    Evaluates cinematic quality of a fully orchestrated scene.
    Advisory only — no bridge calls, no mutations.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._review_count = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate_cinematic_quality(self, scene_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate all cinematic dimensions and produce a weighted overall score.

        scene_data keys:
            zones (dict), lighting_plan (dict|None), camera_plan (dict|None),
            atmosphere_plan (dict|None), assembly_result (dict|None)

        Returns:
            {
                overall_score: float,
                grade: str,
                dimensions: {storytelling, depth, atmosphere, lighting, camera},
                findings: list[str],
                recommendations: list[str],
                generated_at: float,
            }
        """
        zones = scene_data.get("zones") or {}
        lighting_plan = scene_data.get("lighting_plan")
        camera_plan = scene_data.get("camera_plan")
        atmosphere_plan = scene_data.get("atmosphere_plan")

        storytelling = self.evaluate_visual_storytelling(zones, lighting_plan, camera_plan)
        depth = self.evaluate_depth_readability(zones, atmosphere_plan)
        atmosphere = self.evaluate_atmosphere_balance(atmosphere_plan, lighting_plan)

        # Lighting sub-score
        if not lighting_plan:
            lighting_score = 0.0
        else:
            balance = lighting_plan.get("balance", {})
            if isinstance(balance, dict) and "balance_score" in balance:
                lighting_score = float(balance["balance_score"])
            else:
                lighting_score = 0.5

        # Camera sub-score
        if not camera_plan:
            camera_score = 0.0
        else:
            readability = camera_plan.get("readability", {})
            if isinstance(readability, dict) and "readability_score" in readability:
                camera_score = float(readability["readability_score"])
            else:
                camera_score = 0.5

        dimensions: Dict[str, float] = {
            "storytelling": round(storytelling["score"], 3),
            "depth":        round(depth["score"], 3),
            "atmosphere":   round(atmosphere["score"], 3),
            "lighting":     round(lighting_score, 3),
            "camera":       round(camera_score, 3),
        }

        overall = sum(
            dimensions[dim] * weight
            for dim, weight in _CINEMATIC_SCORE_WEIGHTS.items()
        )
        overall = round(max(0.0, min(1.0, overall)), 3)

        # Collect all findings from sub-evaluations
        findings: List[str] = []
        findings.extend(storytelling.get("findings", []))
        findings.extend(depth.get("findings", []))
        findings.extend(atmosphere.get("findings", []))

        if lighting_score < 0.3 and lighting_plan is not None:
            findings.append(_CINEMATIC_CRITIQUES["light_flat"])
        if not lighting_plan:
            findings.append(_CINEMATIC_CRITIQUES["no_key_light"])
        if not camera_plan:
            findings.append(_CINEMATIC_CRITIQUES["no_camera"])
        if overall < 0.5:
            findings.append(_CINEMATIC_CRITIQUES["low_readability"])

        # Deduplicate while preserving order
        seen = set()
        unique_findings: List[str] = []
        for f in findings:
            if f not in seen:
                seen.add(f)
                unique_findings.append(f)

        recommendations: List[str] = []
        if dimensions["storytelling"] < 0.5:
            recommendations.append("Improve hero placement and ensure it is lit by a key light.")
        if dimensions["depth"] < 0.5:
            recommendations.append("Add midground and background assets to build depth layers.")
        if dimensions["atmosphere"] < 0.4:
            recommendations.append("Introduce subtle atmospheric fog to separate depth layers.")
        if dimensions["lighting"] < 0.5:
            recommendations.append("Add a rim or back light to separate the hero from the background.")
        if dimensions["camera"] < 0.5:
            recommendations.append("Define at least one establishing and one hero-focus camera shot.")

        return {
            "overall_score":    overall,
            "grade":            _grade(overall),
            "dimensions":       dimensions,
            "findings":         unique_findings,
            "recommendations":  recommendations,
            "generated_at":     time.time(),
        }

    def evaluate_visual_storytelling(
        self,
        zones: Dict[str, Any],
        lighting_plan: Optional[Dict[str, Any]] = None,
        camera_plan: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate whether the scene communicates a clear visual story.

        Returns:
            {
                score: float,
                has_hero: bool,
                hero_lit: bool,
                has_camera: bool,
                findings: list[str],
                strengths: list[str],
            }
        """
        findings: List[str] = []
        strengths: List[str] = []
        score = 0.0

        # Hero presence
        hero_zone = zones.get("hero_area") or []
        has_hero = len(hero_zone) > 0
        if has_hero:
            score += 0.4
        else:
            findings.append(_CINEMATIC_CRITIQUES["no_hero"])

        # Hero lit check
        hero_lit = False
        if lighting_plan and has_hero:
            key_strategy = lighting_plan.get("key_strategy", {})
            if isinstance(key_strategy, dict):
                hero_lit = key_strategy.get("target_zone") == "hero_area"
        if has_hero and hero_lit:
            score += 0.3
            strengths.append(_CINEMATIC_CRITIQUES["hero_excellent"])
        elif has_hero and not hero_lit:
            findings.append(_CINEMATIC_CRITIQUES["no_key_light"])

        # Camera presence
        has_camera = camera_plan is not None
        if has_camera:
            score += 0.2
            strengths.append(_CINEMATIC_CRITIQUES["camera_cinematic"])
        else:
            findings.append(_CINEMATIC_CRITIQUES["no_camera"])

        # Camera has hero_focus shot
        if has_camera:
            targets = camera_plan.get("targets") or camera_plan.get("camera_targets", [])
            has_hero_focus = any(
                t.get("shot_type") == "hero_focus"
                for t in targets
                if isinstance(t, dict)
            )
            if has_hero_focus:
                score += 0.1

        score = round(max(0.0, min(1.0, score)), 3)

        return {
            "score":      score,
            "has_hero":   has_hero,
            "hero_lit":   hero_lit,
            "has_camera": has_camera,
            "findings":   findings,
            "strengths":  strengths,
        }

    def evaluate_depth_readability(
        self,
        zones: Dict[str, Any],
        atmosphere_plan: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate whether the scene has readable depth.

        Returns:
            {
                score: float,
                zone_count: int,
                has_atmosphere: bool,
                findings: list[str],
                strengths: list[str],
            }
        """
        findings: List[str] = []
        strengths: List[str] = []

        # Count non-empty zones
        non_empty_zones = [z for z, assets in zones.items() if assets]
        zone_count = len(non_empty_zones)

        score = min(zone_count * 0.25, 0.75)

        if zone_count < 2:
            findings.append(_CINEMATIC_CRITIQUES["no_depth"])
        elif zone_count >= 3:
            strengths.append(_CINEMATIC_CRITIQUES["depth_strong"])

        # Atmosphere contribution
        density = 0.0
        has_atmosphere = False
        if atmosphere_plan:
            density = atmosphere_plan.get("recommended_density", 0.0)
            if not isinstance(density, (int, float)):
                density = 0.0
            has_atmosphere = density > 0

        if has_atmosphere:
            score += 0.25
            if density <= 0.06:
                strengths.append(_CINEMATIC_CRITIQUES["depth_fog_correct"])
            else:
                findings.append(_CINEMATIC_CRITIQUES["fog_too_dense"])
        else:
            findings.append(_CINEMATIC_CRITIQUES["no_atmosphere"])

        score = round(max(0.0, min(1.0, score)), 3)

        return {
            "score":          score,
            "zone_count":     zone_count,
            "has_atmosphere": has_atmosphere,
            "findings":       findings,
            "strengths":      strengths,
        }

    def evaluate_atmosphere_balance(
        self,
        atmosphere_plan: Optional[Dict[str, Any]] = None,
        lighting_plan: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate whether atmosphere and lighting are balanced cinematically.

        Returns:
            {
                score: float,
                atmosphere_present: bool,
                lighting_volumetric: bool,
                density_appropriate: bool,
                findings: list[str],
                strengths: list[str],
            }
        """
        findings: List[str] = []
        strengths: List[str] = []

        # Parse density
        density = 0.0
        atmosphere_present = False
        if atmosphere_plan:
            density = atmosphere_plan.get("recommended_density", 0.0)
            if not isinstance(density, (int, float)):
                density = 0.0
            atmosphere_present = density > 0

        # Base score
        if not atmosphere_plan:
            # No atmosphere is acceptable — neutral score
            score = 0.5
        elif atmosphere_present:
            score = 0.6
        else:
            score = 0.5

        # Volumetric lighting
        lighting_volumetric = False
        if lighting_plan:
            volumetric = lighting_plan.get("volumetric", {})
            if isinstance(volumetric, dict):
                lighting_volumetric = bool(volumetric.get("enabled", False))

        if lighting_volumetric:
            score += 0.2
            strengths.append(_CINEMATIC_CRITIQUES["practical_good"])

        # Density appropriateness
        density_appropriate = atmosphere_present and 0.0 < density <= 0.06
        if density_appropriate:
            score += 0.2
            strengths.append(_CINEMATIC_CRITIQUES["atmosphere_correct"])

        if atmosphere_present and density > 0.06:
            score -= 0.3
            findings.append(_CINEMATIC_CRITIQUES["fog_too_dense"])

        score = round(max(0.0, min(1.0, score)), 3)

        return {
            "score":               score,
            "atmosphere_present":  atmosphere_present,
            "lighting_volumetric": lighting_volumetric,
            "density_appropriate": density_appropriate,
            "findings":            findings,
            "strengths":           strengths,
        }

    def generate_cinematic_review(self, scene_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Top-level cinematic review — orchestrates all evaluations.

        scene_data: same structure as evaluate_cinematic_quality.

        Returns production_ready, overall_score, grade, all sub-review dicts,
        merged findings and strengths, recommendations, review_summary, generated_at.
        """
        zones = scene_data.get("zones") or {}
        lighting_plan = scene_data.get("lighting_plan")
        camera_plan = scene_data.get("camera_plan")
        atmosphere_plan = scene_data.get("atmosphere_plan")

        cinematic_quality = self.evaluate_cinematic_quality(scene_data)
        storytelling = self.evaluate_visual_storytelling(zones, lighting_plan, camera_plan)
        depth = self.evaluate_depth_readability(zones, atmosphere_plan)
        atmosphere = self.evaluate_atmosphere_balance(atmosphere_plan, lighting_plan)

        overall_score = cinematic_quality["overall_score"]
        grade = cinematic_quality["grade"]

        # Merge all findings (deduplicated)
        seen: set = set()
        all_findings: List[str] = []
        for f in (
            cinematic_quality.get("findings", [])
            + storytelling.get("findings", [])
            + depth.get("findings", [])
            + atmosphere.get("findings", [])
        ):
            if f not in seen:
                seen.add(f)
                all_findings.append(f)

        # Merge all strengths (deduplicated)
        seen_s: set = set()
        all_strengths: List[str] = []
        for s in (
            storytelling.get("strengths", [])
            + depth.get("strengths", [])
            + atmosphere.get("strengths", [])
        ):
            if s not in seen_s:
                seen_s.add(s)
                all_strengths.append(s)

        # production_ready: score >= 0.7 and no critical findings
        critical_findings = [
            f for f in all_findings
            if any(kw in f.lower() for kw in _CRITICAL_KEYWORDS)
        ]
        production_ready = overall_score >= 0.7 and len(critical_findings) == 0

        # Specific, grade-based summary — never "Execution successful"
        if grade == "A":
            review_summary = (
                "Cinematic realization is production-ready — "
                "depth separation is strong, hero focus is excellent."
            )
        elif grade == "B":
            review_summary = (
                "Scene achieves good cinematic quality — "
                "minor refinements to atmosphere or camera will elevate it."
            )
        elif grade == "C":
            review_summary = (
                "Scene is cinematically acceptable — "
                "hero lighting or depth layering needs attention."
            )
        elif grade == "D":
            review_summary = (
                "Cinematic quality is below threshold — "
                "hero focus, depth, or lighting requires significant improvement."
            )
        else:
            review_summary = (
                "Scene is not cinematically viable — "
                "fundamental readability and composition issues must be resolved."
            )

        recommendations = cinematic_quality.get("recommendations", [])

        with self._lock:
            self._review_count += 1

        return {
            "production_ready": production_ready,
            "overall_score":    overall_score,
            "grade":            grade,
            "cinematic_quality": cinematic_quality,
            "storytelling":     storytelling,
            "depth":            depth,
            "atmosphere":       atmosphere,
            "findings":         all_findings,
            "strengths":        all_strengths,
            "recommendations":  recommendations,
            "review_summary":   review_summary,
            "generated_at":     time.time(),
        }

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {"review_count": self._review_count}


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[CinematicSceneReview] = None
_INSTANCE_LOCK = threading.Lock()


def get_cinematic_scene_review() -> CinematicSceneReview:
    global _INSTANCE
    with _INSTANCE_LOCK:
        if _INSTANCE is None:
            _INSTANCE = CinematicSceneReview()
        return _INSTANCE


def reset_cinematic_scene_review_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
