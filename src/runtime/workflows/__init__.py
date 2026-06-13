"""
Workflow Packs & Production Blueprints (Tier 10)
================================================
Reusable production-grade workflow configurations for Vibrante Runtime.

Each WorkflowPack encapsulates a complete production strategy:
  - environment structure
  - asset selection and population
  - placement templates
  - lighting, camera, and atmosphere
  - review thresholds

Public surface (re-exported for convenience):

    from src.runtime.workflows import (
        WorkflowPack, get_builtin_packs,
        WorkflowBlueprint, get_workflow_blueprint,
        WorkflowRegistry, get_workflow_registry,
        WorkflowValidator, get_workflow_validator,
        WorkflowExecutor, get_workflow_executor,
        WorkflowReview, get_workflow_review,
        WorkflowRecommendationEngine, get_workflow_recommendation_engine,
        WorkflowSerializer, get_workflow_serializer,
        WorkflowStatistics, get_workflow_statistics,
    )
"""

from src.runtime.workflows.workflow_pack import (
    WorkflowPack,
    PACK_SCHEMA_VERSION,
    VALID_ENVIRONMENT_TYPES,
    get_builtin_packs,
    reset_workflow_pack_for_tests,
)
from src.runtime.workflows.workflow_blueprint import (
    BlueprintPhase,
    WorkflowBlueprint,
    PHASE_ORDER,
    get_workflow_blueprint,
    reset_workflow_blueprint_for_tests,
)
from src.runtime.workflows.workflow_registry import (
    WorkflowRegistry,
    get_workflow_registry,
    reset_workflow_registry_for_tests,
)
from src.runtime.workflows.workflow_validator import (
    ValidationReport,
    WorkflowValidator,
    get_workflow_validator,
    reset_workflow_validator_for_tests,
)
from src.runtime.workflows.workflow_executor import (
    ExecutionResult,
    WorkflowExecutor,
    get_workflow_executor,
    reset_workflow_executor_for_tests,
)
from src.runtime.workflows.workflow_review import (
    WorkflowReviewResult,
    WorkflowReview,
    get_workflow_review,
    reset_workflow_review_for_tests,
)
from src.runtime.workflows.workflow_recommendation import (
    WorkflowRecommendation,
    RecommendationResult,
    WorkflowRecommendationEngine,
    get_workflow_recommendation_engine,
    reset_workflow_recommendation_engine_for_tests,
)
from src.runtime.workflows.workflow_serializer import (
    WorkflowSerializer,
    get_workflow_serializer,
    reset_workflow_serializer_for_tests,
)
from src.runtime.workflows.workflow_statistics import (
    WorkflowStatistics,
    get_workflow_statistics,
    reset_workflow_statistics_for_tests,
)

__all__ = [
    # Pack
    "WorkflowPack",
    "PACK_SCHEMA_VERSION",
    "VALID_ENVIRONMENT_TYPES",
    "get_builtin_packs",
    "reset_workflow_pack_for_tests",
    # Blueprint
    "BlueprintPhase",
    "WorkflowBlueprint",
    "PHASE_ORDER",
    "get_workflow_blueprint",
    "reset_workflow_blueprint_for_tests",
    # Registry
    "WorkflowRegistry",
    "get_workflow_registry",
    "reset_workflow_registry_for_tests",
    # Validator
    "ValidationReport",
    "WorkflowValidator",
    "get_workflow_validator",
    "reset_workflow_validator_for_tests",
    # Executor
    "ExecutionResult",
    "WorkflowExecutor",
    "get_workflow_executor",
    "reset_workflow_executor_for_tests",
    # Review
    "WorkflowReviewResult",
    "WorkflowReview",
    "get_workflow_review",
    "reset_workflow_review_for_tests",
    # Recommendation
    "WorkflowRecommendation",
    "RecommendationResult",
    "WorkflowRecommendationEngine",
    "get_workflow_recommendation_engine",
    "reset_workflow_recommendation_engine_for_tests",
    # Serializer
    "WorkflowSerializer",
    "get_workflow_serializer",
    "reset_workflow_serializer_for_tests",
    # Statistics
    "WorkflowStatistics",
    "get_workflow_statistics",
    "reset_workflow_statistics_for_tests",
]
