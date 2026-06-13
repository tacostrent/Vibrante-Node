"""
src/runtime/assets/suitability — §45 Semantic Asset Suitability Ranking
========================================================================
Converts asset retrieval from semantic similarity to semantic suitability.
Every candidate asset receives a suitability score based on 7 weighted
affinity factors instead of a single vector-similarity score.

Weights:
    environment_affinity  0.25
    role_affinity         0.20
    style_affinity        0.15
    material_affinity     0.10
    scale_affinity        0.10
    placement_affinity    0.10
    story_affinity        0.10

Design rules:
  - No bridge calls, no Houdini imports
  - Deterministic: same input → same output
  - Never raises in public methods
  - Singleton pattern with reset_…_for_tests()
  - Thread-safe throughout
"""

from src.runtime.assets.suitability.environment_affinity import (
    EnvironmentAffinity,
    get_environment_affinity,
    reset_environment_affinity_for_tests,
)
from src.runtime.assets.suitability.role_affinity import (
    RoleAffinity,
    get_role_affinity,
    reset_role_affinity_for_tests,
)
from src.runtime.assets.suitability.style_affinity import (
    StyleAffinity,
    get_style_affinity,
    reset_style_affinity_for_tests,
)
from src.runtime.assets.suitability.material_affinity import (
    MaterialAffinity,
    get_material_affinity,
    reset_material_affinity_for_tests,
)
from src.runtime.assets.suitability.scale_affinity import (
    ScaleAffinity,
    get_scale_affinity,
    reset_scale_affinity_for_tests,
)
from src.runtime.assets.suitability.placement_affinity import (
    PlacementAffinity,
    get_placement_affinity,
    reset_placement_affinity_for_tests,
)
from src.runtime.assets.suitability.story_affinity import (
    StoryAffinity,
    get_story_affinity,
    reset_story_affinity_for_tests,
)
from src.runtime.assets.suitability.asset_suitability_engine import (
    SuitabilityRequest,
    AssetSuitabilityScore,
    SuitabilityResult,
    AssetSuitabilityEngine,
    get_asset_suitability_engine,
    reset_asset_suitability_engine_for_tests,
    WEIGHTS,
)
from src.runtime.assets.suitability.asset_suitability_review import (
    SuitabilityReviewResult,
    AssetSuitabilityReview,
    get_asset_suitability_review,
    reset_asset_suitability_review_for_tests,
)
from src.runtime.assets.suitability.asset_suitability_statistics import (
    SuitabilityStatRecord,
    AssetSuitabilityStatistics,
    get_asset_suitability_statistics,
    reset_asset_suitability_statistics_for_tests,
)
from src.runtime.assets.suitability.asset_suitability_serializer import (
    AssetSuitabilitySerializer,
    get_asset_suitability_serializer,
    reset_asset_suitability_serializer_for_tests,
)

__all__ = [
    # Environment affinity
    "EnvironmentAffinity", "get_environment_affinity", "reset_environment_affinity_for_tests",
    # Role affinity
    "RoleAffinity", "get_role_affinity", "reset_role_affinity_for_tests",
    # Style affinity
    "StyleAffinity", "get_style_affinity", "reset_style_affinity_for_tests",
    # Material affinity
    "MaterialAffinity", "get_material_affinity", "reset_material_affinity_for_tests",
    # Scale affinity
    "ScaleAffinity", "get_scale_affinity", "reset_scale_affinity_for_tests",
    # Placement affinity
    "PlacementAffinity", "get_placement_affinity", "reset_placement_affinity_for_tests",
    # Story affinity
    "StoryAffinity", "get_story_affinity", "reset_story_affinity_for_tests",
    # Engine
    "SuitabilityRequest", "AssetSuitabilityScore", "SuitabilityResult",
    "AssetSuitabilityEngine", "get_asset_suitability_engine",
    "reset_asset_suitability_engine_for_tests", "WEIGHTS",
    # Review
    "SuitabilityReviewResult", "AssetSuitabilityReview",
    "get_asset_suitability_review", "reset_asset_suitability_review_for_tests",
    # Statistics
    "SuitabilityStatRecord", "AssetSuitabilityStatistics",
    "get_asset_suitability_statistics", "reset_asset_suitability_statistics_for_tests",
    # Serializer
    "AssetSuitabilitySerializer", "get_asset_suitability_serializer",
    "reset_asset_suitability_serializer_for_tests",
]
