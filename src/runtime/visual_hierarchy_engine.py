"""
Visual Hierarchy Engine (Tier 4 — Cinematic Orchestration)
============================================================
Evaluates cinematic visual hierarchy — hero focus, depth, balance,
and light distribution.

DESIGN RULE: NO bridge calls. Purely analytical. Deterministic.

Public API:
    VisualHierarchyEngine
        .evaluate_hero_focus(zones, lighting_plan) -> dict
        .evaluate_depth_readability(zones, atmosphere_plan) -> dict
        .evaluate_scene_balance(zones, layout_plan) -> dict
        .evaluate_light_distribution(lighting_plan) -> dict
        .generate_hierarchy_review(zones, lighting_plan, camera_plan) -> dict
        .stats() -> dict

    get_visual_hierarchy_engine() -> VisualHierarchyEngine
    reset_visual_hierarchy_engine_for_tests()
"""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Thresholds and weights
# ---------------------------------------------------------------------------

_MAX_HERO_ASSETS_FOR_FOCUS = 3
_MIN_DEPTH_ZONES = 2
_GOOD_BALANCE_THRESHOLD = 0.4   # max ratio difference for "balanced"

_DEPTH_SCORE_WEIGHTS: Dict[str, float] = {
    "has_hero":       0.35,
    "has_midground":  0.25,
    "has_background": 0.25,
    "has_atmosphere": 0.15,
}


class VisualHierarchyEngine:
    """
    Evaluates cinematic visual hierarchy across hero focus, depth, balance,
    and light distribution. Returns specific critique, never generic status.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._review_count = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate_hero_focus(
        self,
        zones: Dict[str, List[Any]],
        lighting_plan: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate hero zone population and lighting alignment.

        Returns:
            {
                has_hero:               bool,
                hero_asset_count:       int,
                focus_clarity:          float 0.0–1.0,
                lighting_supports_hero: bool,
                issues:                 list[str],
                strengths:              list[str],
            }
        """
        issues: List[str] = []
        strengths: List[str] = []

        hero_assets = zones.get("hero_area", [])
        hero_count = len(hero_assets) if hero_assets else 0
        has_hero = hero_count > 0

        # Focus clarity
        if not has_hero:
            focus_clarity = 0.0
            issues.append("No hero assets placed — scene lacks focal point.")
        elif hero_count > _MAX_HERO_ASSETS_FOR_FOCUS:
            focus_clarity = 0.5
            issues.append("Hero zone overloaded — narrative focus is diluted.")
        elif hero_count == 1:
            focus_clarity = 1.0
        else:
            # 2–3 assets
            focus_clarity = 0.85

        # Lighting alignment
        lighting_supports_hero = False
        if lighting_plan is not None:
            key_strategy = lighting_plan.get("key_strategy")
            if isinstance(key_strategy, dict):
                if key_strategy.get("target_zone") == "hero_area":
                    lighting_supports_hero = True

        if has_hero and lighting_supports_hero:
            strengths.append(
                "Key light targets hero zone — readability reinforced."
            )
        elif has_hero and not lighting_supports_hero:
            issues.append(
                "Key light does not target hero zone — hero may lack emphasis."
            )

        return {
            "has_hero":               has_hero,
            "hero_asset_count":       hero_count,
            "focus_clarity":          round(focus_clarity, 3),
            "lighting_supports_hero": lighting_supports_hero,
            "issues":                 issues,
            "strengths":              strengths,
        }

    def evaluate_depth_readability(
        self,
        zones: Dict[str, List[Any]],
        atmosphere_plan: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate depth layering using zone population and optional atmosphere.

        Returns:
            {
                depth_score:              float 0.0–1.0,
                depth_layers:             list[str],
                depth_readable:           bool,
                atmosphere_enhances_depth: bool,
                issues:                   list[str],
                strengths:                list[str],
            }
        """
        issues: List[str] = []
        strengths: List[str] = []

        hero_assets = zones.get("hero_area", [])
        mid_assets = zones.get("midground", [])
        bg_assets = zones.get("background", [])

        has_hero = bool(hero_assets)
        has_midground = bool(mid_assets)
        has_background = bool(bg_assets)

        # Atmosphere enhances depth
        atmosphere_enhances_depth = False
        if atmosphere_plan is not None:
            if atmosphere_plan.get("recommended_density", 0) > 0:
                atmosphere_enhances_depth = True

        # Weighted score
        score = 0.0
        if has_hero:
            score += _DEPTH_SCORE_WEIGHTS["has_hero"]
        if has_midground:
            score += _DEPTH_SCORE_WEIGHTS["has_midground"]
        if has_background:
            score += _DEPTH_SCORE_WEIGHTS["has_background"]
        if atmosphere_enhances_depth:
            score += _DEPTH_SCORE_WEIGHTS["has_atmosphere"]

        score = max(0.0, min(1.0, score))

        # Collect populated depth layers
        depth_layers: List[str] = []
        if has_hero:
            depth_layers.append("hero_area")
        if has_midground:
            depth_layers.append("midground")
        if has_background:
            depth_layers.append("background")

        # Issues
        if not has_midground:
            issues.append("No midground zone populated — depth transition missing.")
        if not has_background:
            issues.append("Background zone empty — scene appears flat.")
        if score < 0.5:
            issues.append("Insufficient depth layering — readability compromised.")

        # Strengths
        if has_hero and has_midground and has_background:
            strengths.append(
                "Three-layer depth structure — strong cinematic depth."
            )
        if atmosphere_enhances_depth:
            strengths.append(
                "Atmospheric depth fog reinforces zone separation."
            )

        depth_readable = score >= 0.5

        return {
            "depth_score":               round(score, 3),
            "depth_layers":              depth_layers,
            "depth_readable":            depth_readable,
            "atmosphere_enhances_depth": atmosphere_enhances_depth,
            "issues":                    issues,
            "strengths":                 strengths,
        }

    def evaluate_scene_balance(
        self,
        zones: Dict[str, List[Any]],
        layout_plan: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate asset distribution balance across zones.

        Returns:
            {
                balanced:       bool,
                balance_score:  float 0.0–1.0,
                zone_weights:   {zone: asset_count},
                heaviest_zone:  str | None,
                lightest_zone:  str | None,
                issues:         list[str],
            }
        """
        issues: List[str] = []

        zone_weights: Dict[str, int] = {
            zone: len(assets) if assets else 0
            for zone, assets in zones.items()
        }
        total = sum(zone_weights.values())

        if total == 0:
            return {
                "balanced":      False,
                "balance_score": 0.0,
                "zone_weights":  zone_weights,
                "heaviest_zone": None,
                "lightest_zone": None,
                "issues":        ["No assets placed — scene is empty."],
            }

        heaviest_zone = max(zone_weights, key=lambda z: zone_weights[z])
        lightest_zone = min(zone_weights, key=lambda z: zone_weights[z])
        heaviest = zone_weights[heaviest_zone]
        lightest = zone_weights[lightest_zone]

        ratio = (heaviest - lightest) / (heaviest + 1e-9)
        balance_score = round(1.0 - ratio, 3)
        balanced = ratio <= _GOOD_BALANCE_THRESHOLD

        if not balanced:
            issues.append(
                f"Asset distribution is unbalanced — {heaviest_zone} is overloaded."
            )

        return {
            "balanced":      balanced,
            "balance_score": max(0.0, min(1.0, balance_score)),
            "zone_weights":  zone_weights,
            "heaviest_zone": heaviest_zone,
            "lightest_zone": lightest_zone,
            "issues":        issues,
        }

    def evaluate_light_distribution(
        self,
        lighting_plan: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Evaluate whether the lighting plan covers essential cinematic components.

        Returns:
            {
                has_key:            bool,
                has_rim:            bool,
                has_practicals:     bool,
                has_volumetric:     bool,
                distribution_score: float 0.0–1.0,
                issues:             list[str],
                strengths:          list[str],
            }
        """
        issues: List[str] = []
        strengths: List[str] = []

        # Key light
        key_strategy = lighting_plan.get("key_strategy")
        has_key = (
            isinstance(key_strategy, dict)
            and key_strategy.get("intensity", 0) > 0
        )

        # Rim light
        rim_strategy = lighting_plan.get("rim_strategy")
        has_rim = (
            isinstance(rim_strategy, dict)
            and rim_strategy.get("intensity", 0) > 0
        )

        # Practical lighting
        has_practicals = lighting_plan.get("practical_lighting") is not None

        # Volumetric
        volumetric = lighting_plan.get("volumetric", {})
        has_volumetric = (
            isinstance(volumetric, dict)
            and volumetric.get("enabled", False) is True
        )

        distribution_score = sum(
            0.25 for flag in (has_key, has_rim, has_practicals, has_volumetric)
            if flag
        )

        # Issues
        if not has_key:
            issues.append("No key light defined — primary illumination missing.")
        if not has_rim:
            issues.append("No rim light defined — hero/background separation lost.")

        # Strengths
        if has_key and has_rim:
            strengths.append(
                "Key-rim lighting pair maintains depth separation."
            )

        return {
            "has_key":            has_key,
            "has_rim":            has_rim,
            "has_practicals":     has_practicals,
            "has_volumetric":     has_volumetric,
            "distribution_score": round(distribution_score, 3),
            "issues":             issues,
            "strengths":          strengths,
        }

    def generate_hierarchy_review(
        self,
        zones: Dict[str, List[Any]],
        lighting_plan: Dict[str, Any],
        camera_plan: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Run all four evaluations and merge results into a unified review.

        Returns:
            {
                hero_focus:        dict,
                depth_readability: dict,
                scene_balance:     dict,
                light_distribution: dict,
                overall_score:     float 0.0–1.0,
                production_ready:  bool,
                blocking_issues:   list[str],
                strengths:         list[str],
                review_summary:    str,
                generated_at:      float,
            }
        """
        hero_focus = self.evaluate_hero_focus(zones, lighting_plan)
        depth_readability = self.evaluate_depth_readability(zones)
        scene_balance = self.evaluate_scene_balance(zones, None)
        light_distribution = self.evaluate_light_distribution(lighting_plan)

        # Weighted overall score
        hero_score = hero_focus.get("focus_clarity", 0.0)
        depth_score = depth_readability.get("depth_score", 0.0)
        balance_score = scene_balance.get("balance_score", 0.0)
        light_score = light_distribution.get("distribution_score", 0.0)

        overall = (
            hero_score   * 0.35
            + depth_score  * 0.30
            + balance_score * 0.20
            + light_score  * 0.15
        )
        overall = round(max(0.0, min(1.0, overall)), 3)

        # Collect all blocking issues and strengths
        blocking_issues: List[str] = []
        all_strengths: List[str] = []

        for result in (hero_focus, depth_readability, scene_balance, light_distribution):
            blocking_issues.extend(result.get("issues", []))
            all_strengths.extend(result.get("strengths", []))

        production_ready = overall >= 0.6 and len(blocking_issues) == 0

        # Summary
        if overall >= 0.85:
            review_summary = (
                "Visual hierarchy is cinematic — hero focus, depth, "
                "and lighting are all strong."
            )
        elif overall >= 0.65:
            review_summary = (
                "Visual hierarchy is adequate — minor improvements "
                "will enhance cinematic quality."
            )
        else:
            review_summary = (
                "Visual hierarchy needs attention — hero focus or "
                "depth layering is insufficient."
            )

        with self._lock:
            self._review_count += 1

        return {
            "hero_focus":         hero_focus,
            "depth_readability":  depth_readability,
            "scene_balance":      scene_balance,
            "light_distribution": light_distribution,
            "overall_score":      overall,
            "production_ready":   production_ready,
            "blocking_issues":    blocking_issues,
            "strengths":          all_strengths,
            "review_summary":     review_summary,
            "generated_at":       time.time(),
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

_INSTANCE: Optional[VisualHierarchyEngine] = None
_INSTANCE_LOCK = threading.Lock()


def get_visual_hierarchy_engine() -> VisualHierarchyEngine:
    global _INSTANCE
    with _INSTANCE_LOCK:
        if _INSTANCE is None:
            _INSTANCE = VisualHierarchyEngine()
        return _INSTANCE


def reset_visual_hierarchy_engine_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
