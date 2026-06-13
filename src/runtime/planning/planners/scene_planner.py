"""
Scene Planner (Tier 7 — Scene Planning Runtime)
================================================
Orchestrates the full planning pipeline: SceneIntent → ScenePlan.

Steps:
  1. ZonePlanner        → List[SceneZonePlan]
  2. CompositionPlanner → List[CompositionRule]
  3. CameraPlanner      → List[CameraTarget]
  4. AssetQueryGenerator → List[AssetQuery]
  5. Collect PlacementHints from zones
  6. Estimate complexity and asset count
  7. Assemble ScenePlan

DESIGN RULES:
  - No bridge calls. No LLM calls.
  - Deterministic: same SceneIntent → same ScenePlan.
  - Never raises — failures are captured in PlanningResult.errors.
  - planning_notes record which phases ran and their outputs.

Public API:
    ScenePlanner
        .plan(intent)       -> PlanningResult     [sync]
    get_scene_planner() -> ScenePlanner   (singleton)
    reset_scene_planner_for_tests()
"""

from __future__ import annotations

import threading
import time
from typing import Any, List, Optional

from src.runtime.planning.schema.scene_plan import (
    PlanningResult,
    ScenePlan,
    PlacementHint,
)
from src.runtime.planning.planners.zone_planner import get_zone_planner
from src.runtime.planning.composition.composition_planner import get_composition_planner
from src.runtime.planning.camera.camera_planner import get_camera_planner
from src.runtime.planning.planners.asset_query_generator import get_asset_query_generator

# ---------------------------------------------------------------------------
# Complexity estimation
# ---------------------------------------------------------------------------

def _estimate_complexity(n_zones: int, n_queries: int) -> str:
    if n_zones <= 2 and n_queries < 10:
        return "simple"
    if n_zones <= 3 and n_queries < 25:
        return "moderate"
    if n_zones <= 4 and n_queries < 50:
        return "complex"
    return "epic"


def _collect_placement_hints(zones: List[Any]) -> List[PlacementHint]:
    hints: List[PlacementHint] = []
    for zone in zones:
        hints.extend(getattr(zone, "placement_hints", []))
    return hints


# ---------------------------------------------------------------------------
# ScenePlanner
# ---------------------------------------------------------------------------

class ScenePlanner:
    """Orchestrates SceneIntent → ScenePlan.

    Uses ZonePlanner, CompositionPlanner, CameraPlanner, and
    AssetQueryGenerator internally.  All sub-planners are resolved via
    their singletons so they can be replaced in tests.
    """

    def plan(self, intent: Any) -> PlanningResult:
        """Run the full planning pipeline against *intent*.

        Args:
            intent: A :class:`~src.runtime.semantic.schema.scene_intent_schema.SceneIntent`
                    or any duck-typed object with .environment, .style, .mood,
                    .destruction_level, .intent_id fields.

        Returns:
            :class:`PlanningResult` with ``ok=True`` on success.
            Never raises — errors are captured in the result.
        """
        t0     = time.perf_counter()
        result = PlanningResult()

        try:
            intent_id = getattr(intent, "intent_id", "") or ""
            env       = getattr(intent, "environment", None)
            style     = getattr(intent, "style", None)
            mood      = getattr(intent, "mood", None)

            plan = ScenePlan(
                scene_intent_id=intent_id,
                environment=env,
                style=style,
                mood=mood,
            )

            # --- Phase 1: Zones ---
            try:
                zones = get_zone_planner().plan_zones(intent)
                plan.zones = zones
                result.pipeline_stages.append("zones")
                plan.planning_notes.append(
                    f"Zone planner: created {len(zones)} zones for {env or 'unknown'!r} environment."
                )
            except Exception as exc:
                result.warnings.append(f"Zone planner failed: {exc}")
                zones = []

            # --- Phase 2: Composition ---
            try:
                rules = get_composition_planner().plan_composition(intent, zones)
                plan.composition_rules = rules
                result.pipeline_stages.append("composition")
                plan.planning_notes.append(
                    f"Composition planner: generated {len(rules)} rules "
                    f"for style={style!r}, mood={mood!r}."
                )
            except Exception as exc:
                result.warnings.append(f"Composition planner failed: {exc}")

            # --- Phase 3: Cameras ---
            try:
                targets = get_camera_planner().plan_cameras(intent, zones)
                plan.camera_targets = targets
                result.pipeline_stages.append("cameras")
                plan.planning_notes.append(
                    f"Camera planner: generated {len(targets)} targets."
                )
            except Exception as exc:
                result.warnings.append(f"Camera planner failed: {exc}")

            # --- Phase 4: Asset Queries ---
            try:
                queries = get_asset_query_generator().generate_queries(intent, zones)
                plan.asset_queries = queries
                result.pipeline_stages.append("asset_queries")
                plan.planning_notes.append(
                    f"Asset query generator: produced {len(queries)} queries."
                )
            except Exception as exc:
                result.warnings.append(f"Asset query generator failed: {exc}")
                queries = []

            # --- Phase 5: Placement Hints ---
            plan.placement_hints = _collect_placement_hints(zones)
            result.pipeline_stages.append("placement_hints")

            # --- Phase 6: Estimates ---
            plan.estimated_complexity  = _estimate_complexity(len(zones), len(queries))
            plan.estimated_asset_count = sum(
                getattr(q, "quantity", 1) for q in queries
            )
            result.pipeline_stages.append("estimates")
            plan.planning_notes.append(
                f"Complexity: {plan.estimated_complexity!r}, "
                f"estimated {plan.estimated_asset_count} assets."
            )

            result.ok   = True
            result.plan = plan

        except Exception as exc:
            result.errors.append(f"Planning failed: {exc}")

        result.planning_time = time.perf_counter() - t0
        return result


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[ScenePlanner] = None
_INSTANCE_LOCK = threading.Lock()


def get_scene_planner() -> ScenePlanner:
    """Return the module-level singleton ScenePlanner."""
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = ScenePlanner()
    return _INSTANCE


def reset_scene_planner_for_tests() -> None:
    """Replace the singleton. For test isolation only."""
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
