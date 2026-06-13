"""
Production Scoring (Tier 5 — Production Knowledge System)
==========================================================
Evaluates production quality from structured scene data.
All scoring is deterministic and explainable — no AI, no randomness.

Scores are composites of several measurable properties:
  readability  — hero clarity + depth layers + midground presence
  composition  — zone balance + visual weight distribution
  lighting     — balance score from lighting plan
  camera       — readability score from camera plan
  atmosphere   — density appropriateness + depth support
  overall      — weighted combination of all dimensions

DESIGN RULE: NO bridge calls. No LLM. Deterministic.

Public API:
    ProductionScoring
        .score_readability(zones) -> dict
        .score_composition(zones) -> dict
        .score_lighting(lighting_plan) -> dict
        .score_camera(camera_plan) -> dict
        .score_atmosphere(atmosphere_plan) -> dict
        .score_scene(scene_data) -> dict
        .stats() -> dict

    get_production_scoring() -> ProductionScoring   (singleton)
    reset_production_scoring_for_tests()
"""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional

# Weights for the overall scene score
_SCENE_SCORE_WEIGHTS: Dict[str, float] = {
    "readability": 0.30,
    "composition": 0.25,
    "lighting":    0.20,
    "camera":      0.15,
    "atmosphere":  0.10,
}

# Density range considered optimal for cinematic depth
_DENSITY_OPTIMAL_MIN = 0.01
_DENSITY_OPTIMAL_MAX = 0.06


def _grade(score: float) -> str:
    if score >= 0.9:
        return "A"
    if score >= 0.8:
        return "B"
    if score >= 0.7:
        return "C"
    if score >= 0.6:
        return "D"
    return "F"


class ProductionScoring:
    """Deterministic production quality evaluator."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._eval_count = 0

    # ------------------------------------------------------------------
    # Individual dimension scorers
    # ------------------------------------------------------------------

    def score_readability(self, zones: Dict[str, Any]) -> Dict[str, Any]:
        """Score hero clarity + depth layers.

        Args:
            zones: dict mapping zone names to asset lists.

        Returns:
            {readability_score, hero_count, depth_layers, has_midground,
             has_background, issues, grade}
        """
        hero_assets = zones.get("hero_area") or []
        mid_assets  = zones.get("midground") or []
        bg_assets   = zones.get("background") or []

        hero_count = len(hero_assets)
        has_midground  = len(mid_assets) > 0
        has_background = len(bg_assets) > 0

        issues: List[str] = []
        score = 0.0

        # Hero clarity
        if hero_count == 0:
            issues.append("No hero assets — scene lacks focal point.")
        elif hero_count == 1:
            score += 0.40
        elif hero_count <= 3:
            score += 0.30
        else:
            score += 0.15
            issues.append(f"{hero_count} hero assets — focus is diluted.")

        # Depth layers
        if has_midground:
            score += 0.35
        else:
            issues.append("Midground zone is empty — depth is flat.")

        if has_background:
            score += 0.25
        else:
            issues.append("Background zone is empty — no depth anchor.")

        populated_zones = sum(1 for z in [hero_assets, mid_assets, bg_assets] if z)
        depth_layers = [
            z for z, a in [("hero_area", hero_assets), ("midground", mid_assets),
                           ("background", bg_assets)] if a
        ]

        return {
            "readability_score": round(min(score, 1.0), 4),
            "hero_count":        hero_count,
            "depth_layers":      depth_layers,
            "populated_zones":   populated_zones,
            "has_midground":     has_midground,
            "has_background":    has_background,
            "issues":            issues,
            "grade":             _grade(min(score, 1.0)),
        }

    def score_composition(self, zones: Dict[str, Any]) -> Dict[str, Any]:
        """Score visual weight distribution across zones.

        Returns:
            {composition_score, zone_weights, balance_ratio,
             heaviest_zone, issues, grade}
        """
        zone_counts: Dict[str, int] = {}
        for zone, assets in zones.items():
            if assets:
                zone_counts[zone] = len(assets)

        issues: List[str] = []

        if not zone_counts:
            return {
                "composition_score": 0.0,
                "zone_weights":      {},
                "balance_ratio":     0.0,
                "heaviest_zone":     None,
                "issues":            ["Scene is empty — no composition possible."],
                "grade":             "F",
            }

        total = sum(zone_counts.values())
        zone_weights = {z: c / total for z, c in zone_counts.items()}
        heaviest = max(zone_counts, key=zone_counts.get)
        lightest = min(zone_counts, key=zone_counts.get)
        heaviest_count = zone_counts[heaviest]
        lightest_count = zone_counts[lightest]

        # balance_ratio: 0 = perfect, 1 = extreme imbalance
        balance_ratio = (heaviest_count - lightest_count) / (heaviest_count + 1e-9)

        score = 1.0 - (balance_ratio * 0.5)  # penalty for imbalance
        if balance_ratio > 0.6:
            issues.append(f"Zone '{heaviest}' is heavily overloaded — visual balance broken.")
        if len(zone_counts) == 1:
            score *= 0.5
            issues.append("Only one populated zone — no visual distribution.")

        return {
            "composition_score": round(max(0.0, min(score, 1.0)), 4),
            "zone_weights":      {z: round(w, 4) for z, w in zone_weights.items()},
            "balance_ratio":     round(balance_ratio, 4),
            "heaviest_zone":     heaviest,
            "issues":            issues,
            "grade":             _grade(max(0.0, min(score, 1.0))),
        }

    def score_lighting(self, lighting_plan: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Score lighting plan quality from balance data.

        Returns:
            {lighting_score, has_key, has_rim, balanced, issues, grade}
        """
        if not lighting_plan:
            return {
                "lighting_score": 0.0,
                "has_key":        False,
                "has_rim":        False,
                "balanced":       False,
                "issues":         ["No lighting plan provided."],
                "grade":          "F",
            }

        issues: List[str] = []
        score = 0.0

        key   = lighting_plan.get("key_strategy") or {}
        rim   = lighting_plan.get("rim_strategy") or {}
        balance = lighting_plan.get("balance") or {}

        has_key = isinstance(key, dict) and key.get("intensity", 0) > 0
        has_rim = isinstance(rim, dict) and rim.get("intensity", 0) > 0
        balanced = bool(balance.get("balanced", False)) if isinstance(balance, dict) else False

        if has_key:
            score += 0.40
        else:
            issues.append("Key light absent — primary illumination undefined.")

        if has_rim:
            score += 0.30
        else:
            issues.append("Rim light absent — hero separation undefined.")

        if balanced:
            score += 0.30
        else:
            if isinstance(balance, dict) and balance.get("issues"):
                issues.extend(balance["issues"][:2])
            else:
                issues.append("Light balance could not be evaluated.")

        return {
            "lighting_score": round(min(score, 1.0), 4),
            "has_key":        has_key,
            "has_rim":        has_rim,
            "balanced":       balanced,
            "issues":         issues,
            "grade":          _grade(min(score, 1.0)),
        }

    def score_camera(self, camera_plan: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Score camera plan from readability data.

        Returns:
            {camera_score, readable, has_establishing, mode, issues, grade}
        """
        if not camera_plan:
            return {
                "camera_score":    0.0,
                "readable":        False,
                "has_establishing": False,
                "mode":            "",
                "issues":          ["No camera plan provided."],
                "grade":           "F",
            }

        issues: List[str] = []
        readability = camera_plan.get("readability") or {}
        if isinstance(readability, dict):
            raw_score = float(readability.get("readability_score", 0.0))
            readable = bool(readability.get("readable", raw_score >= 0.5))
            if isinstance(readability.get("issues"), list):
                issues.extend(readability["issues"][:2])
        else:
            raw_score = 0.0
            readable = False
            issues.append("Camera readability data unavailable.")

        targets = camera_plan.get("targets") or []
        shot_types = [t.get("shot_type", "") for t in targets if isinstance(t, dict)]
        has_establishing = "wide_establishing" in shot_types

        if not has_establishing:
            issues.append("No establishing shot — scene context is undefined.")

        score = raw_score
        if not has_establishing:
            score = max(0.0, score - 0.1)

        return {
            "camera_score":     round(min(score, 1.0), 4),
            "readable":         readable,
            "has_establishing": has_establishing,
            "mode":             str(camera_plan.get("camera_mode", "")),
            "issues":           issues,
            "grade":            _grade(min(score, 1.0)),
        }

    def score_atmosphere(self, atmosphere_plan: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Score atmospheric depth plan.

        Returns:
            {atmosphere_score, density_ok, supports_depth, density, issues, grade}
        """
        if not atmosphere_plan:
            return {
                "atmosphere_score": 0.5,  # neutral — absent atmosphere is OK
                "density_ok":       False,
                "supports_depth":   False,
                "density":          0.0,
                "issues":           ["No atmosphere plan — depth relies on geometry alone."],
                "grade":            "C",
            }

        issues: List[str] = []
        density = float(atmosphere_plan.get("recommended_density", 0.0))
        depth_support = str(
            atmosphere_plan.get("depth_atmosphere", {}).get("depth_support", "")
            if isinstance(atmosphere_plan.get("depth_atmosphere"), dict)
            else atmosphere_plan.get("depth_support", "")
        )

        density_ok = _DENSITY_OPTIMAL_MIN <= density <= _DENSITY_OPTIMAL_MAX
        supports_depth = depth_support in ("strong", "moderate")

        score = 0.0
        if density > 0:
            score += 0.40
        else:
            issues.append("Zero atmosphere density — no depth fog contribution.")

        if density_ok:
            score += 0.40
        elif density > _DENSITY_OPTIMAL_MAX:
            score += 0.10
            issues.append(f"Density {density:.3f} exceeds maximum {_DENSITY_OPTIMAL_MAX} — assets will be obscured.")

        if supports_depth:
            score += 0.20

        return {
            "atmosphere_score": round(min(score, 1.0), 4),
            "density_ok":       density_ok,
            "supports_depth":   supports_depth,
            "density":          density,
            "issues":           issues,
            "grade":            _grade(min(score, 1.0)),
        }

    def score_scene(self, scene_data: Dict[str, Any]) -> Dict[str, Any]:
        """Composite scene score across all dimensions.

        scene_data may contain:
            zones (dict), lighting_plan (dict), camera_plan (dict),
            atmosphere_plan (dict)

        Returns:
            {overall, grade, readability, composition, lighting, camera,
             atmosphere, dimension_scores, production_ready, issues}
        """
        zones          = scene_data.get("zones") or {}
        lighting_plan  = scene_data.get("lighting_plan")
        camera_plan    = scene_data.get("camera_plan")
        atmosphere_plan = scene_data.get("atmosphere_plan")

        r = self.score_readability(zones)
        c = self.score_composition(zones)
        l = self.score_lighting(lighting_plan)
        k = self.score_camera(camera_plan)
        a = self.score_atmosphere(atmosphere_plan)

        dim_scores = {
            "readability": r["readability_score"],
            "composition": c["composition_score"],
            "lighting":    l["lighting_score"],
            "camera":      k["camera_score"],
            "atmosphere":  a["atmosphere_score"],
        }

        overall = sum(
            dim_scores[d] * _SCENE_SCORE_WEIGHTS[d]
            for d in _SCENE_SCORE_WEIGHTS
        )
        overall = round(min(overall, 1.0), 4)

        all_issues = (
            r["issues"] + c["issues"] + l["issues"] +
            k["issues"] + a["issues"]
        )
        production_ready = overall >= 0.7 and not any(
            "absent" in i.lower() or "empty" in i.lower() or "no hero" in i.lower()
            for i in all_issues
        )

        with self._lock:
            self._eval_count += 1

        return {
            "overall":          overall,
            "grade":            _grade(overall),
            "readability":      r["readability_score"],
            "composition":      c["composition_score"],
            "lighting":         l["lighting_score"],
            "camera":           k["camera_score"],
            "atmosphere":       a["atmosphere_score"],
            "dimension_scores": dim_scores,
            "production_ready": production_ready,
            "issues":           all_issues,
        }

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {"eval_count": self._eval_count}


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[ProductionScoring] = None
_INSTANCE_LOCK = threading.Lock()


def get_production_scoring() -> ProductionScoring:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = ProductionScoring()
    return _INSTANCE


def reset_production_scoring_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
