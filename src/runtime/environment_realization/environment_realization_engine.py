"""
environment_realization_engine.py — §49 Structural Environment Realization
==========================================================================
Main orchestrator. Converts an environment name (+ optional overrides) into
a complete EnvironmentRealizationPlan that includes:
  - RoomShell (floor, walls, ceiling, openings, beams, columns)
  - Structural elements flat list
  - Zone regions (spatial bounds for hero/support/decoration zones)
  - Transaction ops (Houdini-ready, no bridge calls needed here)
  - Quality review

Usage:
    plan = get_environment_realization_engine().realize("western_room")
    # plan.room_closed == True
    # plan.production_ready == True
    # plan.transaction_ops → list of op dicts for hou_mcp_apply_layout

Public API:
    EnvironmentRealizationEngine
    get_environment_realization_engine()
    reset_environment_realization_engine_for_tests()
"""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional, Tuple

from src.runtime.environment_realization.structural_elements import EnvironmentRealizationPlan
from src.runtime.environment_realization.structural_builder import get_structural_builder
from src.runtime.environment_realization.environment_review import get_env_realization_review
from src.runtime.environment_realization.environment_statistics import get_env_realization_statistics


class EnvironmentRealizationEngine:
    """
    Single entry point for environment structural realization.

    Pipeline:
      1. StructuralBuilder    → RoomShell + all elements + transaction ops
      2. RealizationReview    → score, grade, production_ready, findings
      3. RealizationStatistics → record run
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def realize(
        self,
        environment: str,
        override_dims: Optional[Tuple[float, float, float]] = None,
    ) -> EnvironmentRealizationPlan:
        """
        Realize the architectural structure for an environment.

        Args:
            environment:   name string (e.g. "western_room")
            override_dims: optional (width, height, depth) in meters

        Returns: EnvironmentRealizationPlan. Never raises.
        """
        try:
            return self._realize(environment, override_dims)
        except Exception as exc:
            return EnvironmentRealizationPlan(
                environment=environment,
                ok=False,
                errors=[f"EnvironmentRealizationEngine.realize failed: {exc}"],
            )

    def _realize(
        self,
        environment: str,
        override_dims: Optional[Tuple[float, float, float]],
    ) -> EnvironmentRealizationPlan:
        # Build structure
        plan = get_structural_builder().build(environment, override_dims)

        # Review
        review = get_env_realization_review().review(plan.to_dict())
        plan.production_ready = review.production_ready

        # Statistics
        get_env_realization_statistics().record(
            environment=environment,
            wall_count=plan.wall_count,
            floor_count=plan.floor_count,
            ceiling_count=plan.ceiling_count,
            door_count=plan.door_count,
            beam_count=plan.beam_count,
            overall_score=review.overall_score,
            grade=review.grade,
            production_ready=review.production_ready,
        )

        return plan


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[EnvironmentRealizationEngine] = None
_lock = threading.Lock()


def get_environment_realization_engine() -> EnvironmentRealizationEngine:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = EnvironmentRealizationEngine()
    return _instance


def reset_environment_realization_engine_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
