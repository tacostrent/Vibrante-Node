"""
Lighting Intelligence & Cinematic Illumination (Tier 15)
=========================================================
Full re-export of the public surface for the lighting package.

Modules:
  lighting_knowledge            — Production lighting concepts (14 builtins)
  lighting_language             — Cinematic intent → structured lighting intent
  lighting_patterns             — Reusable environment-matched lighting recipes (8 builtins)
  lighting_environment_mapper   — Environment → lighting requirements mapping
  lighting_mood_engine          — Mood inference and mood profile generation (8 moods)
  lighting_readability_engine   — Visual clarity and readability evaluation
  lighting_hierarchy_engine     — Visual focus hierarchy (hero/support/background/atmosphere)
  lighting_color_engine         — Color palette and temperature strategy
  lighting_exposure_engine      — Exposure strategy and dynamic range
  lighting_strategy_engine      — Holistic lighting strategy generation
  lighting_recommendation_engine — Production-proven lighting recommendations
  lighting_plan_builder         — Renderer-agnostic lighting plan construction
  lighting_review               — 6-dimension lighting quality review
  lighting_statistics           — In-memory usage statistics (capped at 2000)
  lighting_serializer           — Deterministic JSON persistence
  lighting_validation           — Structural validation for lighting objects
"""
from __future__ import annotations

from .lighting_knowledge import (
    BUILTIN_LIGHTING_ROLES,
    LightingConcept,
    LightingKnowledge,
    get_lighting_knowledge,
    reset_lighting_knowledge_for_tests,
)
from .lighting_language import (
    BUILTIN_MOODS,
    BUILTIN_CONTRASTS,
    BUILTIN_STYLES,
    LightingIntent,
    LightingLanguage,
    get_lighting_language,
    reset_lighting_language_for_tests,
)
from .lighting_patterns import (
    LightingPattern,
    LightingPatterns,
    get_lighting_patterns,
    reset_lighting_patterns_for_tests,
)
from .lighting_environment_mapper import (
    EnvironmentLightingMapping,
    LightingEnvironmentMapper,
    get_lighting_environment_mapper,
    reset_lighting_environment_mapper_for_tests,
)
from .lighting_mood_engine import (
    MoodProfile,
    LightingMoodEngine,
    get_lighting_mood_engine,
    reset_lighting_mood_engine_for_tests,
)
from .lighting_readability_engine import (
    ReadabilityResult,
    LightingReadabilityEngine,
    get_lighting_readability_engine,
    reset_lighting_readability_engine_for_tests,
)
from .lighting_hierarchy_engine import (
    HIERARCHY_ROLES,
    HierarchyEntry,
    FocusHierarchy,
    LightingHierarchyEngine,
    get_lighting_hierarchy_engine,
    reset_lighting_hierarchy_engine_for_tests,
)
from .lighting_color_engine import (
    ColorStrategy,
    LightingColorEngine,
    get_lighting_color_engine,
    reset_lighting_color_engine_for_tests,
)
from .lighting_exposure_engine import (
    ExposureStrategy,
    LightingExposureEngine,
    get_lighting_exposure_engine,
    reset_lighting_exposure_engine_for_tests,
)
from .lighting_strategy_engine import (
    LightingStrategy,
    LightingStrategyEngine,
    get_lighting_strategy_engine,
    reset_lighting_strategy_engine_for_tests,
)
from .lighting_recommendation_engine import (
    LightingRecommendation,
    LightingRecommendationEngine,
    get_lighting_recommendation_engine,
    reset_lighting_recommendation_engine_for_tests,
)
from .lighting_plan_builder import (
    LightSpec,
    LightPlan,
    LightingPlanBuilder,
    get_lighting_plan_builder,
    reset_lighting_plan_builder_for_tests,
)
from .lighting_review import (
    LightingReviewResult,
    LightingReview,
    get_lighting_review,
    reset_lighting_review_for_tests,
)
from .lighting_statistics import (
    LightingStatistics,
    get_lighting_statistics,
    reset_lighting_statistics_for_tests,
)
from .lighting_serializer import (
    _SCHEMA_VERSION as LIGHTING_SCHEMA_VERSION,
    LightingSerializer,
    get_lighting_serializer,
    reset_lighting_serializer_for_tests,
)
from .lighting_validation import (
    LightingValidation,
    get_lighting_validation,
    reset_lighting_validation_for_tests,
)

__all__ = [
    # Constants
    "BUILTIN_LIGHTING_ROLES",
    "BUILTIN_MOODS",
    "BUILTIN_CONTRASTS",
    "BUILTIN_STYLES",
    "HIERARCHY_ROLES",
    "LIGHTING_SCHEMA_VERSION",
    # Lighting Knowledge
    "LightingConcept",
    "LightingKnowledge",
    "get_lighting_knowledge",
    "reset_lighting_knowledge_for_tests",
    # Lighting Language
    "LightingIntent",
    "LightingLanguage",
    "get_lighting_language",
    "reset_lighting_language_for_tests",
    # Lighting Patterns
    "LightingPattern",
    "LightingPatterns",
    "get_lighting_patterns",
    "reset_lighting_patterns_for_tests",
    # Environment Mapper
    "EnvironmentLightingMapping",
    "LightingEnvironmentMapper",
    "get_lighting_environment_mapper",
    "reset_lighting_environment_mapper_for_tests",
    # Mood Engine
    "MoodProfile",
    "LightingMoodEngine",
    "get_lighting_mood_engine",
    "reset_lighting_mood_engine_for_tests",
    # Readability Engine
    "ReadabilityResult",
    "LightingReadabilityEngine",
    "get_lighting_readability_engine",
    "reset_lighting_readability_engine_for_tests",
    # Hierarchy Engine
    "HierarchyEntry",
    "FocusHierarchy",
    "LightingHierarchyEngine",
    "get_lighting_hierarchy_engine",
    "reset_lighting_hierarchy_engine_for_tests",
    # Color Engine
    "ColorStrategy",
    "LightingColorEngine",
    "get_lighting_color_engine",
    "reset_lighting_color_engine_for_tests",
    # Exposure Engine
    "ExposureStrategy",
    "LightingExposureEngine",
    "get_lighting_exposure_engine",
    "reset_lighting_exposure_engine_for_tests",
    # Strategy Engine
    "LightingStrategy",
    "LightingStrategyEngine",
    "get_lighting_strategy_engine",
    "reset_lighting_strategy_engine_for_tests",
    # Recommendation Engine
    "LightingRecommendation",
    "LightingRecommendationEngine",
    "get_lighting_recommendation_engine",
    "reset_lighting_recommendation_engine_for_tests",
    # Plan Builder
    "LightSpec",
    "LightPlan",
    "LightingPlanBuilder",
    "get_lighting_plan_builder",
    "reset_lighting_plan_builder_for_tests",
    # Review
    "LightingReviewResult",
    "LightingReview",
    "get_lighting_review",
    "reset_lighting_review_for_tests",
    # Statistics
    "LightingStatistics",
    "get_lighting_statistics",
    "reset_lighting_statistics_for_tests",
    # Serializer
    "LightingSerializer",
    "get_lighting_serializer",
    "reset_lighting_serializer_for_tests",
    # Validation
    "LightingValidation",
    "get_lighting_validation",
    "reset_lighting_validation_for_tests",
]
