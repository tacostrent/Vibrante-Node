"""
Scene Layout Planner (Tier 2 — Semantic Scene Assembly)
=========================================================
Generates semantically coherent scene layout plans.

Uses environment rules and composition heuristics to organize
semantic asset groups into cinematically valid layout structures.

Does NOT generate world-space coordinates.
Does NOT touch Houdini.
No bridge calls, no LLM, no I/O.

Public API:
    get_scene_layout_planner() -> SceneLayoutPlanner   (singleton)
    reset_scene_layout_planner_for_tests()

    SceneLayoutPlanner.generate_layout_plan(scene_theme, assets) -> dict
    SceneLayoutPlanner.create_zones(scene_theme) -> dict
    SceneLayoutPlanner.assign_hero_assets(assets, zones) -> dict
    SceneLayoutPlanner.assign_background_assets(assets, zones) -> dict
    SceneLayoutPlanner.generate_layout_hierarchy(layout_plan) -> dict
    SceneLayoutPlanner.stats() -> dict
"""

import threading
import time
import uuid
from typing import Any, Dict, List, Optional


def _get_env_rules():
    from src.runtime.environment_rules import get_environment_rules
    return get_environment_rules()


def _get_composition_engine():
    from src.runtime.cinematic_composition import get_cinematic_composition_engine
    return get_cinematic_composition_engine()


# Categories that take priority placement in the hero zone
_HERO_CATEGORIES = frozenset({
    "vehicle", "character", "machinery_hero", "hero_prop",
    "robot", "weapon", "creature",
})

# Categories that prefer background placement
_BACKGROUND_CATEGORIES = frozenset({
    "structure", "terrain", "sky", "backdrop", "distant_props",
})

# Canonical zones always present in every layout plan
_CANONICAL_ZONES = ("hero_area", "midground", "background")


class SceneLayoutPlanner:
    """Generates semantically coherent scene layout plans.

    All methods are deterministic.  No I/O, no bridge calls, no LLM.
    """

    def __init__(self) -> None:
        self._lock       = threading.Lock()
        self._plan_count = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_layout_plan(
        self,
        scene_theme: str,
        assets: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Generate a complete semantic layout plan.

        Args:
            scene_theme:  Environment identifier (e.g. "industrial_hangar").
            assets:       List of asset dicts, each with at least
                          {"name": str, "category": str}.

        Returns:
            {
              "plan_id":             str,
              "scene_theme":         str,
              "zones":               {zone: [assets]},
              "layout_rules":        {hero_focus, fog_density, ...},
              "asset_placements":    {category: zone},
              "recommended_fx":      [fx_type, ...],
              "camera_hints":        [shot_type, ...],
              "depth_layers":        [layer_name, ...],
              "total_assets":        int,
              "hierarchy":           {render_order, zone_priorities, focus_path},
              "composition_analysis":{readable, readability_score, ...},
              "generated_at":        float,
            }
        """
        with self._lock:
            self._plan_count += 1

        env_rules = _get_env_rules()
        rules     = env_rules.get_rules(scene_theme)

        zones = self.create_zones(scene_theme)
        zones = self.assign_hero_assets(assets, zones)
        zones = self.assign_background_assets(assets, zones)

        layout_plan: Dict[str, Any] = {
            "plan_id":          str(uuid.uuid4()),
            "scene_theme":      scene_theme,
            "zones":            zones,
            "layout_rules": {
                "hero_focus":     rules.get("hero_zone",       "center"),
                "fog_density":    rules.get("fog_density",     "none"),
                "lighting_style": rules.get("lighting_style",  "natural"),
                "atmosphere":     rules.get("atmosphere",      "neutral"),
                "scale":          rules.get("scale",           "medium"),
            },
            "asset_placements": rules.get("asset_placements", {}),
            "recommended_fx":   list(rules.get("fx_recommendations", [])),
            "camera_hints":     list(rules.get("camera_hints",       [])),
            "depth_layers":     list(rules.get("depth_layers", list(_CANONICAL_ZONES))),
            "total_assets":     len(assets),
            "generated_at":     time.time(),
        }

        layout_plan["hierarchy"] = self.generate_layout_hierarchy(layout_plan)

        comp = _get_composition_engine()
        layout_plan["composition_analysis"] = comp.evaluate_scene_readability(layout_plan)

        return layout_plan

    def create_zones(self, scene_theme: str) -> Dict[str, List[Any]]:
        """Create an empty zone structure for the given theme.

        Always includes the three canonical zones (hero_area, midground,
        background) plus any theme-specific extra layers.
        """
        env_rules    = _get_env_rules()
        rules        = env_rules.get_rules(scene_theme)
        depth_layers = rules.get("depth_layers", list(_CANONICAL_ZONES))

        zones: Dict[str, List[Any]] = {}
        for canonical in _CANONICAL_ZONES:
            zones[canonical] = []
        for layer in depth_layers:
            if layer not in zones:
                zones[layer] = []

        return zones

    def assign_hero_assets(
        self,
        assets:  List[Dict[str, Any]],
        zones:   Dict[str, List[Any]],
    ) -> Dict[str, List[Any]]:
        """Assign hero-category assets to hero_area zone.

        An asset is considered a hero if:
          - its category is in _HERO_CATEGORIES, OR
          - it has ``is_hero=True``, OR
          - it has ``priority >= 8``.

        Returns a new zones dict (does not mutate the input).
        """
        zones          = {z: list(v) for z, v in zones.items()}
        assigned_names = {a.get("name") for z_list in zones.values() for a in z_list}

        for asset in assets:
            name     = asset.get("name", "")
            category = asset.get("category", "")
            if name in assigned_names:
                continue
            if (
                category in _HERO_CATEGORIES
                or asset.get("is_hero", False)
                or asset.get("priority", 0) >= 8
            ):
                zones["hero_area"].append(asset)
                assigned_names.add(name)

        return zones

    def assign_background_assets(
        self,
        assets: List[Dict[str, Any]],
        zones:  Dict[str, List[Any]],
    ) -> Dict[str, List[Any]]:
        """Assign remaining (non-hero) assets to midground / background.

        Background-category assets always go to background.
        Everything else alternates between midground and background
        to keep zone sizes balanced.

        Returns a new zones dict (does not mutate the input).
        """
        zones          = {z: list(v) for z, v in zones.items()}
        assigned_names = {a.get("name") for z_list in zones.values() for a in z_list}

        for asset in assets:
            name     = asset.get("name", "")
            category = asset.get("category", "")
            if name in assigned_names:
                continue
            if category in _BACKGROUND_CATEGORIES:
                zones["background"].append(asset)
            elif len(zones["midground"]) <= len(zones["background"]):
                zones["midground"].append(asset)
            else:
                zones["background"].append(asset)
            assigned_names.add(name)

        return zones

    def generate_layout_hierarchy(
        self,
        layout_plan: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate the semantic rendering hierarchy for an assembled plan.

        Returns:
            {
              "render_order":    [zone_name, ...],  # back-to-front
              "zone_priorities": {zone: int},        # 1 = most important
              "focus_path":      [zone_name, ...],   # narrative story flow
            }
        """
        zones        = layout_plan.get("zones", {})
        depth_layers = layout_plan.get(
            "depth_layers", ["background", "midground", "hero_area"]
        )

        # Render order: farthest first (painter's algorithm)
        render_order: List[str] = []
        for layer in reversed(depth_layers):
            if layer in zones and layer not in render_order:
                render_order.append(layer)
        for canonical in ("background", "midground", "hero_area"):
            if canonical in zones and canonical not in render_order:
                render_order.append(canonical)

        # Zone priorities: hero_area = 1, midground = 2, background = 3, rest after
        zone_priorities: Dict[str, int] = {}
        priority = 1
        for z in ("hero_area", "midground", "background"):
            if z in zones:
                zone_priorities[z] = priority
                priority += 1
        for z in sorted(zones):
            if z not in zone_priorities:
                zone_priorities[z] = priority
                priority += 1

        # Focus path: narrative journey through the scene
        focus_path = [z for z in ("hero_area", "midground", "background") if z in zones]

        return {
            "render_order":    render_order,
            "zone_priorities": zone_priorities,
            "focus_path":      focus_path,
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

_INSTANCE: Optional[SceneLayoutPlanner] = None
_LOCK = threading.Lock()


def get_scene_layout_planner() -> SceneLayoutPlanner:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = SceneLayoutPlanner()
        return _INSTANCE


def reset_scene_layout_planner_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
