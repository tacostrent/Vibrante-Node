"""
Lookdev & Material Intelligence (Tier 14)
==========================================
Full re-export of the public surface for the lookdev package.

Modules:
  material_library          — Material definitions, categories, properties
  material_knowledge        — Semantic material inference from asset metadata
  lookdev_patterns          — Reusable environment-matched lookdev recipes
  renderer_profiles         — Renderer-aware material class mappings
  material_recommendation   — Priority-chain material recommendation engine
  material_assignment_engine — Semantic assignment plan generation
  lookdev_review            — 4-dimension lookdev quality review
  lookdev_statistics        — In-memory usage statistics (capped at 2000)
  lookdev_serializer        — Deterministic JSON persistence
  lookdev_validation        — Structural validation for lookdev objects
"""
from __future__ import annotations

from .material_library import (
    BUILTIN_MATERIAL_CATEGORIES,
    MaterialEntry,
    MaterialLibrary,
    get_material_library,
    reset_material_library_for_tests,
)
from .material_knowledge import (
    MaterialInference,
    MaterialKnowledge,
    get_material_knowledge,
    reset_material_knowledge_for_tests,
)
from .lookdev_patterns import (
    LookdevPattern,
    LookdevPatterns,
    get_lookdev_patterns,
    reset_lookdev_patterns_for_tests,
)
from .renderer_profiles import (
    SUPPORTED_RENDERERS,
    RendererProfile,
    RendererProfiles,
    get_renderer_profiles,
    reset_renderer_profiles_for_tests,
)
from .material_recommendation import (
    MaterialRecommendation,
    MaterialRecommendationResult,
    MaterialRecommendationEngine,
    get_material_recommendation_engine,
    reset_material_recommendation_engine_for_tests,
)
from .material_assignment_engine import (
    AssignmentEntry,
    AssignmentPlan,
    MaterialAssignmentEngine,
    get_material_assignment_engine,
    reset_material_assignment_engine_for_tests,
)
from .lookdev_review import (
    LookdevReviewResult,
    LookdevReview,
    get_lookdev_review,
    reset_lookdev_review_for_tests,
)
from .lookdev_statistics import (
    LookdevStatistics,
    get_lookdev_statistics,
    reset_lookdev_statistics_for_tests,
)
from .lookdev_serializer import (
    _SCHEMA_VERSION as LOOKDEV_SCHEMA_VERSION,
    LookdevSerializer,
    get_lookdev_serializer,
    reset_lookdev_serializer_for_tests,
)
from .lookdev_validation import (
    LookdevValidation,
    get_lookdev_validation,
    reset_lookdev_validation_for_tests,
)

__all__ = [
    # Constants
    "BUILTIN_MATERIAL_CATEGORIES",
    "SUPPORTED_RENDERERS",
    "LOOKDEV_SCHEMA_VERSION",
    # Material Library
    "MaterialEntry",
    "MaterialLibrary",
    "get_material_library",
    "reset_material_library_for_tests",
    # Material Knowledge
    "MaterialInference",
    "MaterialKnowledge",
    "get_material_knowledge",
    "reset_material_knowledge_for_tests",
    # Lookdev Patterns
    "LookdevPattern",
    "LookdevPatterns",
    "get_lookdev_patterns",
    "reset_lookdev_patterns_for_tests",
    # Renderer Profiles
    "RendererProfile",
    "RendererProfiles",
    "get_renderer_profiles",
    "reset_renderer_profiles_for_tests",
    # Material Recommendation
    "MaterialRecommendation",
    "MaterialRecommendationResult",
    "MaterialRecommendationEngine",
    "get_material_recommendation_engine",
    "reset_material_recommendation_engine_for_tests",
    # Material Assignment
    "AssignmentEntry",
    "AssignmentPlan",
    "MaterialAssignmentEngine",
    "get_material_assignment_engine",
    "reset_material_assignment_engine_for_tests",
    # Lookdev Review
    "LookdevReviewResult",
    "LookdevReview",
    "get_lookdev_review",
    "reset_lookdev_review_for_tests",
    # Lookdev Statistics
    "LookdevStatistics",
    "get_lookdev_statistics",
    "reset_lookdev_statistics_for_tests",
    # Lookdev Serializer
    "LookdevSerializer",
    "get_lookdev_serializer",
    "reset_lookdev_serializer_for_tests",
    # Lookdev Validation
    "LookdevValidation",
    "get_lookdev_validation",
    "reset_lookdev_validation_for_tests",
]
