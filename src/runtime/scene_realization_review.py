"""
Scene Realization Review (Tier 3)
====================================
Evaluates the quality of a completed scene realization. Provides specific
artistic and technical critique — never generic success messages.

DESIGN RULE: This module is purely advisory. It reads data structures and
returns critique. It never calls get_bridge() or mutates anything.

Public API:
    SceneRealizationReview
        .evaluate_scene_readability(realization_result) -> dict
        .evaluate_layout_balance(zones, positions) -> dict
        .evaluate_asset_distribution(zones) -> dict
        .evaluate_scene_complexity(staging_plan) -> dict
        .generate_realization_review(assembly_result, layout_plan) -> dict

    get_scene_realization_review() -> SceneRealizationReview
    reset_scene_realization_review_for_tests()
"""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Review thresholds
# ---------------------------------------------------------------------------

_MAX_HERO_ASSETS = 3
_MIN_DEPTH_ZONES = 2  # need at least midground + background for depth
_BALANCE_THRESHOLD = 0.3  # max acceptable ratio of heaviest vs lightest zone
_COMPLEXITY_THRESHOLDS = {
    "low":    10,
    "medium": 25,
    "high":   50,
}

# Specific critique messages keyed by issue type
_CRITIQUE_MESSAGES: Dict[str, str] = {
    "no_hero_assets":         "No hero assets placed — scene lacks focal point.",
    "too_many_heroes":        f"Hero zone overloaded (>{_MAX_HERO_ASSETS} assets) — narrative clarity diluted.",
    "no_depth":               "Scene has no depth — background and midground are both empty.",
    "no_background":          "Background zone is empty — scene will appear flat.",
    "no_midground":           "Midground zone is empty — depth transition missing.",
    "empty_scene":            "Scene has no assets — realization produced no output.",
    "unbalanced_distribution": "Asset distribution is unbalanced — one zone is heavily overloaded.",
    "hero_not_centred":       "Hero asset is not near scene centre — off-axis placement reduces impact.",
    "no_lighting":            "No lighting operations generated — scene will render black.",
    "no_camera":              "No camera operations generated — no framing defined.",
    "high_complexity":        "Scene complexity is high — consider splitting into multiple transactions.",
    "extreme_complexity":     "Scene complexity is extreme — performance impact likely.",
    "style_conflicts_present":"Style conflicts were detected in the asset set — incompatible categories coexist.",
    "low_readability":        "Scene readability score is below 0.5 — hero focus and depth layers need review.",
}


class SceneRealizationReview:
    """
    Evaluates scene realization quality and produces specific artistic critique.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._review_count = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate_scene_readability(
        self,
        realization_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Evaluate whether the realized scene is cinematically readable.

        Returns:
            {
                readable:          bool,
                readability_score: float 0.0–1.0,
                issues:            list[str],
                strengths:         list[str],
                criteria_checked:  list[str],
            }
        """
        issues: List[str] = []
        strengths: List[str] = []
        criteria: List[str] = []
        score = 1.0

        zone_map = realization_result.get("zone_map", {})
        path_map = realization_result.get("path_map", {})

        # Count assets per zone
        zone_counts: Dict[str, int] = {}
        for name, zone in zone_map.items():
            zone_counts[zone] = zone_counts.get(zone, 0) + 1

        hero_count = zone_counts.get("hero_area", 0)
        mid_count = zone_counts.get("midground", 0)
        bg_count = zone_counts.get("background", 0)
        total = len(path_map)

        # Check: has hero
        criteria.append("hero_presence")
        if hero_count == 0:
            issues.append(_CRITIQUE_MESSAGES["no_hero_assets"])
            score -= 0.3
        elif hero_count > _MAX_HERO_ASSETS:
            issues.append(_CRITIQUE_MESSAGES["too_many_heroes"])
            score -= 0.2
        else:
            strengths.append(f"Hero zone has {hero_count} focal asset(s).")

        # Check: depth
        criteria.append("depth_layers")
        if mid_count == 0 and bg_count == 0:
            issues.append(_CRITIQUE_MESSAGES["no_depth"])
            score -= 0.3
        elif bg_count == 0:
            issues.append(_CRITIQUE_MESSAGES["no_background"])
            score -= 0.15
        elif mid_count == 0:
            issues.append(_CRITIQUE_MESSAGES["no_midground"])
            score -= 0.1
        else:
            strengths.append("Scene has three-layer depth (hero/mid/background).")

        # Check: empty scene
        criteria.append("asset_presence")
        if total == 0:
            issues.append(_CRITIQUE_MESSAGES["empty_scene"])
            score -= 0.5
        else:
            strengths.append(f"Scene contains {total} placed assets.")

        score = max(0.0, min(1.0, score))
        readable = score >= 0.5 and len(issues) == 0

        return {
            "readable":          readable,
            "readability_score": round(score, 3),
            "issues":            issues,
            "strengths":         strengths,
            "criteria_checked":  criteria,
        }

    def evaluate_layout_balance(
        self,
        zones: Dict[str, List[Any]],
        positions: Optional[Dict[str, Tuple[float, float, float]]] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate whether assets are balanced across the scene.

        Returns:
            {
                balanced:      bool,
                balance_score: float 0.0–1.0,
                zone_weights:  {zone: count},
                issues:        list[str],
            }
        """
        issues: List[str] = []
        zone_weights: Dict[str, int] = {
            zone: len(assets) for zone, assets in zones.items()
        }

        total = sum(zone_weights.values())
        if total == 0:
            return {
                "balanced":      False,
                "balance_score": 0.0,
                "zone_weights":  zone_weights,
                "issues":        [_CRITIQUE_MESSAGES["empty_scene"]],
            }

        populated_zones = [z for z, c in zone_weights.items() if c > 0]
        if len(populated_zones) < 2:
            score = 0.4
            issues.append("Only one zone has assets — no spatial distribution.")
        else:
            max_count = max(zone_weights.values())
            min_count = min(c for c in zone_weights.values() if c > 0)
            ratio = (max_count - min_count) / max(total, 1)
            score = max(0.0, 1.0 - ratio)
            if ratio > _BALANCE_THRESHOLD:
                issues.append(_CRITIQUE_MESSAGES["unbalanced_distribution"])

        # Check hero positioning if positions provided
        if positions:
            hero_assets = zones.get("hero_area", [])
            for asset in hero_assets:
                name = asset.get("name", "") if isinstance(asset, dict) else str(asset)
                pos = positions.get(name)
                if pos is not None:
                    tx = pos[0]
                    # Hero should be within 5 units of centre
                    if abs(tx) > 5.0:
                        issues.append(_CRITIQUE_MESSAGES["hero_not_centred"])
                    break

        return {
            "balanced":      len(issues) == 0 and score >= 0.6,
            "balance_score": round(score, 3),
            "zone_weights":  zone_weights,
            "issues":        issues,
        }

    def evaluate_asset_distribution(
        self,
        zones: Dict[str, List[Any]],
    ) -> Dict[str, Any]:
        """
        Evaluate whether assets are well-distributed across semantic zones.

        Returns:
            {
                well_distributed: bool,
                distribution:     {zone: count},
                coverage:         float (0–1, fraction of zones populated),
                issues:           list[str],
                recommendations:  list[str],
            }
        """
        issues: List[str] = []
        recommendations: List[str] = []

        distribution: Dict[str, int] = {
            zone: len(assets) for zone, assets in zones.items()
        }
        total_zones = len(distribution)
        populated = sum(1 for c in distribution.values() if c > 0)
        coverage = populated / total_zones if total_zones > 0 else 0.0

        # Check depth coverage
        has_hero = distribution.get("hero_area", 0) > 0
        has_mid = distribution.get("midground", 0) > 0
        has_bg = distribution.get("background", 0) > 0

        if not has_hero:
            issues.append("No assets in hero zone — scene lacks visual focus.")
            recommendations.append("Place 1–3 primary assets in hero_area.")
        if not has_mid:
            recommendations.append("Add at least one midground asset for depth.")
        if not has_bg:
            recommendations.append("Add background elements to prevent flat appearance.")

        # Check for single-zone overloading
        for zone, count in distribution.items():
            if count > 10:
                issues.append(
                    f"Zone '{zone}' has {count} assets — consider splitting into sub-zones."
                )

        well_distributed = len(issues) == 0 and coverage >= 0.5 and has_hero

        return {
            "well_distributed": well_distributed,
            "distribution":     distribution,
            "coverage":         round(coverage, 3),
            "issues":           issues,
            "recommendations":  recommendations,
        }

    def evaluate_scene_complexity(
        self,
        staging_plan: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Evaluate scene complexity and flag performance concerns.

        Returns:
            {
                complexity_level:  "low"|"medium"|"high"|"extreme",
                complexity_score:  float,
                issues:            list[str],
                notes:             list[str],
            }
        """
        issues: List[str] = []
        notes: List[str] = []

        import_queue = staging_plan.get("import_queue", [])
        zone_assignments = staging_plan.get("zone_assignments", {})
        recommended_fx = staging_plan.get("recommended_fx", [])

        total_assets = len(import_queue)
        zone_count = len([z for z, assets in zone_assignments.items() if assets])
        fx_count = len(recommended_fx)

        score = total_assets + (zone_count * 2) + (fx_count * 3)

        if score <= _COMPLEXITY_THRESHOLDS["low"]:
            level = "low"
        elif score <= _COMPLEXITY_THRESHOLDS["medium"]:
            level = "medium"
        elif score <= _COMPLEXITY_THRESHOLDS["high"]:
            level = "high"
            issues.append(_CRITIQUE_MESSAGES["high_complexity"])
        else:
            level = "extreme"
            issues.append(_CRITIQUE_MESSAGES["extreme_complexity"])

        if fx_count >= 3:
            notes.append(f"{fx_count} FX layers recommended — verify GPU memory budget.")
        if total_assets > 30:
            notes.append(f"{total_assets} assets — consider LOD management.")

        return {
            "complexity_level": level,
            "complexity_score": score,
            "issues":           issues,
            "notes":            notes,
        }

    def generate_realization_review(
        self,
        assembly_result: Dict[str, Any],
        layout_plan: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Generate the full post-realization review.

        Returns:
            {
                production_ready:    bool,
                overall_score:       float 0.0–1.0,
                readability:         dict,
                balance:             dict,
                distribution:        dict,
                complexity:          dict,
                findings:            list[str],
                recommendations:     list[str],
                review_summary:      str,
                generated_at:        float,
            }
        """
        zones = layout_plan.get("zones", {})
        staging_plan = assembly_result.get("staging_plan", {})
        zone_map = assembly_result.get("zone_map", {})
        path_map = assembly_result.get("path_map", {})

        # Synthesise a realization_result for readability eval
        realization_result = {
            "zone_map": zone_map,
            "path_map": path_map,
        }

        readability = self.evaluate_scene_readability(realization_result)
        balance = self.evaluate_layout_balance(zones)
        distribution = self.evaluate_asset_distribution(zones)
        complexity = self.evaluate_scene_complexity(staging_plan or {})

        # Phase counts
        phase_counts = assembly_result.get("phase_counts", {})
        lighting_ops = phase_counts.get("lighting", 0)
        camera_ops = phase_counts.get("camera", 0)

        all_findings: List[str] = []
        all_recommendations: List[str] = []

        all_findings.extend(readability.get("issues", []))
        all_findings.extend(balance.get("issues", []))
        all_findings.extend(distribution.get("issues", []))
        all_findings.extend(complexity.get("issues", []))

        if lighting_ops == 0:
            all_findings.append(_CRITIQUE_MESSAGES["no_lighting"])
        if camera_ops == 0:
            all_findings.append(_CRITIQUE_MESSAGES["no_camera"])

        all_recommendations.extend(distribution.get("recommendations", []))
        all_recommendations.extend(complexity.get("notes", []))

        # Overall score
        r_score = readability.get("readability_score", 0.5)
        b_score = balance.get("balance_score", 0.5)
        d_cov = distribution.get("coverage", 0.5)
        c_penalty = 0.2 if complexity.get("complexity_level") in ("high", "extreme") else 0.0

        overall = ((r_score * 0.4) + (b_score * 0.3) + (d_cov * 0.3)) - c_penalty
        overall = max(0.0, min(1.0, overall))

        production_ready = (
            len(all_findings) == 0
            and overall >= 0.6
            and readability.get("readable", False)
        )

        if production_ready:
            summary = (
                f"Scene realization is production-ready. "
                f"Score: {overall:.2f}. "
                f"{len(path_map)} assets placed across "
                f"{len([z for z, a in zones.items() if a])} zones."
            )
        else:
            n_issues = len(all_findings)
            summary = (
                f"Scene realization has {n_issues} issue(s) requiring attention. "
                f"Score: {overall:.2f}. Review findings before executing."
            )

        with self._lock:
            self._review_count += 1

        return {
            "production_ready":  production_ready,
            "overall_score":     round(overall, 3),
            "readability":       readability,
            "balance":           balance,
            "distribution":      distribution,
            "complexity":        complexity,
            "findings":          all_findings,
            "recommendations":   all_recommendations,
            "review_summary":    summary,
            "generated_at":      time.time(),
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

_INSTANCE: Optional[SceneRealizationReview] = None
_INSTANCE_LOCK = threading.Lock()


def get_scene_realization_review() -> SceneRealizationReview:
    global _INSTANCE
    with _INSTANCE_LOCK:
        if _INSTANCE is None:
            _INSTANCE = SceneRealizationReview()
        return _INSTANCE


def reset_scene_realization_review_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
