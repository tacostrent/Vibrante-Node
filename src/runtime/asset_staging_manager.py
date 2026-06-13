"""
Asset Staging Manager (Tier 2 — Semantic Scene Assembly)
==========================================================
Builds transaction-safe asset staging plans before any Houdini mutation.

This layer is PLANNING ONLY.
It does NOT execute, import, or mutate scenes.
It produces a validated, ordered staging plan ready for the Transaction system.

Public API:
    get_asset_staging_manager() -> AssetStagingManager  (singleton)
    reset_asset_staging_manager_for_tests()

    AssetStagingManager.build_staging_plan(layout_plan) -> dict
    AssetStagingManager.validate_asset_compatibility(assets) -> dict
    AssetStagingManager.validate_scene_coherence(staging_plan) -> dict
    AssetStagingManager.build_import_queue(layout_plan) -> list[dict]
    AssetStagingManager.estimate_scene_complexity(staging_plan) -> dict
    AssetStagingManager.stats() -> dict
"""

import threading
import time
import uuid
from typing import Any, Dict, List, Optional

# Complexity scoring thresholds
_COMPLEXITY_THRESHOLDS = {
    "low":    10,
    "medium": 25,
    "high":   50,
}

# Maximum assets per zone before a coherence warning fires
_MAX_ZONE_ASSETS = 12

# Stylistic conflicts: (cat_a, cat_b) — cannot coexist in the same plan
_CONFLICTING_PAIRS: List[tuple] = [
    ("vegetation", "tech_panel"),   # organic vs sterile environments
    ("sky",        "ceiling"),      # two competing "top" elements
    ("creature",   "robot"),        # biological vs mechanical (strong style break)
]


def _zone_import_priority(zone: str) -> int:
    """Staging order index — lower means import first (back-to-front)."""
    _PRIORITIES = {
        "background": 1,
        "midground":  2,
        "hero_area":  3,
    }
    return _PRIORITIES.get(zone, 4)


class AssetStagingManager:
    """Builds transaction-safe staging plans for scene assembly.

    All methods are planning-only.  No I/O, no bridge calls, no LLM.
    """

    def __init__(self) -> None:
        self._lock       = threading.Lock()
        self._plan_count = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_staging_plan(
        self,
        layout_plan: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build a transaction-safe staging plan from a layout plan.

        Args:
            layout_plan:  Output of SceneLayoutPlanner.generate_layout_plan().

        Returns:
            {
              "staging_id":           str,
              "scene_theme":          str,
              "import_queue":         list[dict],
              "zone_assignments":     {zone: [asset_name, ...]},
              "compatibility_result": {compatible, conflicts, warnings, asset_count},
              "coherence_result":     {coherent, issues, warnings, zone_summary},
              "complexity_estimate":  {complexity_level, total_assets, ...},
              "layout_rules":         dict,
              "recommended_fx":       list[str],
              "camera_hints":         list[str],
              "ready_for_execution":  bool,
              "generated_at":         float,
            }
        """
        with self._lock:
            self._plan_count += 1

        zones      = layout_plan.get("zones", {})
        all_assets = [a for z_assets in zones.values() for a in z_assets]

        import_queue = self.build_import_queue(layout_plan)
        compat       = self.validate_asset_compatibility(all_assets)

        staging_plan: Dict[str, Any] = {
            "staging_id":   str(uuid.uuid4()),
            "scene_theme":  layout_plan.get("scene_theme", "unknown"),
            "import_queue": import_queue,
            "zone_assignments": {
                z: [a.get("name", "") for a in assets]
                for z, assets in zones.items()
            },
            "compatibility_result": compat,
            "layout_rules":   layout_plan.get("layout_rules",   {}),
            "recommended_fx": list(layout_plan.get("recommended_fx", [])),
            "camera_hints":   list(layout_plan.get("camera_hints",   [])),
            "generated_at":   time.time(),
        }

        coherence  = self.validate_scene_coherence(staging_plan)
        complexity = self.estimate_scene_complexity(staging_plan)

        staging_plan["coherence_result"]  = coherence
        staging_plan["complexity_estimate"] = complexity
        staging_plan["ready_for_execution"] = (
            compat["compatible"] and coherence["coherent"]
        )

        return staging_plan

    def validate_asset_compatibility(
        self,
        assets: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Check whether the asset set is stylistically compatible.

        Returns:
            {
              "compatible":  bool,
              "conflicts":   list[str],
              "warnings":    list[str],
              "asset_count": int,
            }
        """
        conflicts: List[str] = []
        warnings:  List[str] = []

        categories = {a.get("category", "unknown") for a in assets}

        for cat_a, cat_b in _CONFLICTING_PAIRS:
            if cat_a in categories and cat_b in categories:
                conflicts.append(
                    f"Style conflict: '{cat_a}' and '{cat_b}' are incompatible in the same scene."
                )

        # Detect duplicate asset names
        seen: set = set()
        for asset in assets:
            name = asset.get("name", "")
            if name and name in seen:
                warnings.append(
                    f"Duplicate asset name: '{name}' — only the first occurrence will be staged."
                )
            seen.add(name)

        # Warn on assets with no category metadata
        for asset in assets:
            if not asset.get("category"):
                warnings.append(
                    f"Asset '{asset.get('name', 'unnamed')}' has no category — "
                    "placement will be arbitrary."
                )

        return {
            "compatible":  len(conflicts) == 0,
            "conflicts":   conflicts,
            "warnings":    warnings,
            "asset_count": len(assets),
        }

    def validate_scene_coherence(
        self,
        staging_plan: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Validate semantic coherence of the staging plan.

        Returns:
            {
              "coherent":     bool,
              "issues":       list[str],
              "warnings":     list[str],
              "zone_summary": {zone: count},
            }
        """
        issues:   List[str] = []
        warnings: List[str] = []

        zone_assignments = staging_plan.get("zone_assignments", {})
        zone_summary     = {z: len(assets) for z, assets in zone_assignments.items()}
        total            = sum(zone_summary.values())

        if total == 0:
            issues.append("Staging plan contains no assets.")

        for zone, count in zone_summary.items():
            if count > _MAX_ZONE_ASSETS:
                warnings.append(
                    f"Zone '{zone}' has {count} assets (max recommended: {_MAX_ZONE_ASSETS}) — "
                    "consider splitting into sub-zones."
                )

        hero_count = zone_summary.get("hero_area", 0)
        if total > 0 and hero_count == 0:
            warnings.append(
                "No assets assigned to hero_area — scene lacks a clear focal point."
            )

        if not staging_plan.get("layout_rules"):
            warnings.append(
                "No layout rules present — apply environment rules before staging."
            )

        return {
            "coherent":     len(issues) == 0,
            "issues":       issues,
            "warnings":     warnings,
            "zone_summary": zone_summary,
        }

    def build_import_queue(
        self,
        layout_plan: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Build an ordered import queue from a layout plan.

        Import order: background → midground → hero_area → other zones.
        This back-to-front construction order matches how Houdini
        node graphs are typically built (environment first, hero last).

        Returns:
            List of {order, asset_name, asset_category, zone, import_priority,
                     asset_metadata}
        """
        zones      = layout_plan.get("zones", {})
        zone_order = ["background", "midground", "hero_area"]
        extra_zones = sorted(z for z in zones if z not in zone_order)

        queue: List[Dict[str, Any]] = []
        idx = 1

        for zone in zone_order + extra_zones:
            for asset in zones.get(zone, []):
                queue.append({
                    "order":          idx,
                    "asset_name":     asset.get("name", f"asset_{idx}"),
                    "asset_category": asset.get("category", "unknown"),
                    "zone":           zone,
                    "import_priority": _zone_import_priority(zone),
                    "asset_metadata": {
                        k: v for k, v in asset.items()
                        if k not in ("name", "category")
                    },
                })
                idx += 1

        return queue

    def estimate_scene_complexity(
        self,
        staging_plan: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Estimate the complexity of the staged scene.

        Score = total_assets + (zone_count × 2) + (fx_count × 3)

        Returns:
            {
              "complexity_level": "low" | "medium" | "high" | "extreme",
              "total_assets":     int,
              "zone_count":       int,
              "fx_count":         int,
              "complexity_score": int,
              "notes":            list[str],
            }
        """
        queue            = staging_plan.get("import_queue", [])
        total_assets     = len(queue)
        zone_assignments = staging_plan.get("zone_assignments", {})
        zone_count       = sum(1 for v in zone_assignments.values() if v)
        fx_list          = staging_plan.get("recommended_fx", [])
        fx_count         = len(fx_list)

        score = total_assets + (zone_count * 2) + (fx_count * 3)

        if score <= _COMPLEXITY_THRESHOLDS["low"]:
            level = "low"
        elif score <= _COMPLEXITY_THRESHOLDS["medium"]:
            level = "medium"
        elif score <= _COMPLEXITY_THRESHOLDS["high"]:
            level = "high"
        else:
            level = "extreme"

        notes: List[str] = []
        if level in ("high", "extreme"):
            notes.append(
                f"Scene complexity is {level} ({score} pts) — "
                "consider splitting into staged transactions."
            )
        if fx_count >= 3:
            notes.append(
                f"{fx_count} FX layers scheduled — ensure sufficient GPU memory."
            )

        return {
            "complexity_level": level,
            "total_assets":     total_assets,
            "zone_count":       zone_count,
            "fx_count":         fx_count,
            "complexity_score": score,
            "notes":            notes,
        }

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {"plan_count": self._plan_count}


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[AssetStagingManager] = None
_LOCK = threading.Lock()


def get_asset_staging_manager() -> AssetStagingManager:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = AssetStagingManager()
        return _INSTANCE


def reset_asset_staging_manager_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
