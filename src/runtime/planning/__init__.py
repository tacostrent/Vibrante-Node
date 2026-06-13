"""
Scene Planning Runtime (Tier 7)
================================
Transforms a SceneIntent into a deterministic, structured ScenePlan ready for
downstream asset discovery and scene assembly.

Pipeline:
    SceneIntent → ZonePlanner → CompositionPlanner → CameraPlanner
               → AssetQueryGenerator → ScenePlanner (orchestrator)
               → ScenePlanValidator  → ScenePlanRecommendationEngine
               → ScenePlan (typed JSON)

Design rules:
  - LLM-free: all planning is deterministic keyword/rule-based.
  - No bridge calls: no Houdini interaction at this layer.
  - Structured output only: every field is typed.
  - Provider-agnostic: asset queries reference categories, not provider APIs.
"""

from src.runtime.planning.schema.scene_plan import (
    SCHEMA_VERSION,
    AssetQuery,
    CameraTarget,
    CompositionRule,
    PlacementHint,
    SceneZonePlan,
    ScenePlan,
    PlanningResult,
)
from src.runtime.planning.planners.zone_planner import (
    ZonePlanner,
    get_zone_planner,
    reset_zone_planner_for_tests,
)
from src.runtime.planning.composition.composition_planner import (
    CompositionPlanner,
    get_composition_planner,
    reset_composition_planner_for_tests,
)
from src.runtime.planning.camera.camera_planner import (
    CameraPlanner,
    get_camera_planner,
    reset_camera_planner_for_tests,
)
from src.runtime.planning.planners.asset_query_generator import (
    AssetQueryGenerator,
    get_asset_query_generator,
    reset_asset_query_generator_for_tests,
)
from src.runtime.planning.planners.scene_planner import (
    ScenePlanner,
    get_scene_planner,
    reset_scene_planner_for_tests,
)
from src.runtime.planning.validators.scene_plan_validator import (
    ValidationReport,
    ScenePlanValidator,
    get_scene_plan_validator,
    reset_scene_plan_validator_for_tests,
)
from src.runtime.planning.recommendations.scene_plan_recommendation_engine import (
    ScenePlanRecommendationEngine,
    get_scene_plan_recommendation_engine,
    reset_scene_plan_recommendation_engine_for_tests,
)
from src.runtime.planning.serialization.plan_serializer import (
    PlanSerializationError,
    PlanSerializer,
    get_plan_serializer,
    reset_plan_serializer_for_tests,
)
from src.runtime.planning.logging.planning_logger import (
    PlanLogEntry,
    PlanningLogger,
    get_planning_logger,
    reset_planning_logger_for_tests,
)

__all__ = [
    # Schema
    "SCHEMA_VERSION",
    "AssetQuery", "CameraTarget", "CompositionRule",
    "PlacementHint", "SceneZonePlan", "ScenePlan", "PlanningResult",
    # Planners
    "ZonePlanner",        "get_zone_planner",        "reset_zone_planner_for_tests",
    "CompositionPlanner", "get_composition_planner", "reset_composition_planner_for_tests",
    "CameraPlanner",      "get_camera_planner",      "reset_camera_planner_for_tests",
    "AssetQueryGenerator","get_asset_query_generator","reset_asset_query_generator_for_tests",
    "ScenePlanner",       "get_scene_planner",        "reset_scene_planner_for_tests",
    # Validator
    "ValidationReport", "ScenePlanValidator",
    "get_scene_plan_validator", "reset_scene_plan_validator_for_tests",
    # Recommendations
    "ScenePlanRecommendationEngine",
    "get_scene_plan_recommendation_engine",
    "reset_scene_plan_recommendation_engine_for_tests",
    # Serializer
    "PlanSerializationError", "PlanSerializer",
    "get_plan_serializer", "reset_plan_serializer_for_tests",
    # Logger
    "PlanLogEntry", "PlanningLogger",
    "get_planning_logger", "reset_planning_logger_for_tests",
]
