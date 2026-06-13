"""
src/runtime/environment — §44 Structural Environment Assembly
=============================================================
Higher-level environment construction package that builds on the existing
Tier 9.5 assembly layer. Provides template-library-driven environment
blueprints, zone building, anchor placement, support and decorative
population, atmosphere configuration, completeness checking, and review.

All modules follow design rules:
  - No bridge calls / no Houdini imports
  - Deterministic: same input → same output
  - Never raises in public methods
  - Singleton pattern with reset_…_for_tests()
  - Thread-safe throughout
"""

# Environment Blueprint
from src.runtime.environment.environment_blueprint import (
    EnvironmentBlueprint,
)

# Template Library
from src.runtime.environment.environment_template_library import (
    EnvironmentTemplateLibrary,
    get_environment_template_library,
    reset_environment_template_library_for_tests,
)

# Requirements checker
from src.runtime.environment.environment_requirements import (
    RequirementsCheckResult,
    EnvironmentRequirements,
    get_environment_requirements,
    reset_environment_requirements_for_tests,
)

# Zone Builder
from src.runtime.environment.environment_zone_builder import (
    EnvironmentZone,
    ZonePlan,
    EnvironmentZoneBuilder,
    get_environment_zone_builder,
    reset_environment_zone_builder_for_tests,
)

# Structure Builder
from src.runtime.environment.environment_structure_builder import (
    BuiltStructuralElement,
    EnvironmentStructurePlan,
    EnvironmentStructureBuilder,
    get_environment_structure_builder,
    reset_environment_structure_builder_for_tests,
)

# Anchor Asset Builder
from src.runtime.environment.anchor_asset_builder import (
    PlacedAnchor,
    AnchorPlan,
    AnchorAssetBuilder,
    get_anchor_asset_builder,
    reset_anchor_asset_builder_for_tests,
)

# Support Asset Builder
from src.runtime.environment.support_asset_builder import (
    SupportAsset,
    SupportPlan,
    SupportAssetBuilder,
    get_support_asset_builder,
    reset_support_asset_builder_for_tests,
)

# Decorative Population
from src.runtime.environment.decorative_population import (
    DecorativeItem,
    DecorationPlan,
    DecorativePopulation,
    get_decorative_population,
    reset_decorative_population_for_tests,
)

# Atmosphere Builder
from src.runtime.environment.atmosphere_builder import (
    AtmosphereProfile,
    AtmospherePlan,
    AtmosphereBuilder,
    get_atmosphere_builder,
    reset_atmosphere_builder_for_tests,
)

# Completeness
from src.runtime.environment.environment_completeness import (
    CompletenessResult,
    EnvironmentCompleteness,
    get_environment_completeness,
    reset_environment_completeness_for_tests,
)

# Review
from src.runtime.environment.environment_review import (
    EnvironmentReviewResult,
    EnvironmentReview,
    get_environment_review,
    reset_environment_review_for_tests,
)

# Serializer
from src.runtime.environment.environment_serializer import (
    EnvironmentSerializer,
    get_environment_serializer,
    reset_environment_serializer_for_tests,
)

# Statistics
from src.runtime.environment.environment_statistics import (
    EnvironmentStatRecord,
    EnvironmentStatistics,
    get_environment_statistics,
    reset_environment_statistics_for_tests,
)

__all__ = [
    # blueprint
    "EnvironmentBlueprint",
    # template library
    "EnvironmentTemplateLibrary",
    "get_environment_template_library",
    "reset_environment_template_library_for_tests",
    # requirements
    "RequirementsCheckResult",
    "EnvironmentRequirements",
    "get_environment_requirements",
    "reset_environment_requirements_for_tests",
    # zone builder
    "EnvironmentZone",
    "ZonePlan",
    "EnvironmentZoneBuilder",
    "get_environment_zone_builder",
    "reset_environment_zone_builder_for_tests",
    # structure builder
    "BuiltStructuralElement",
    "EnvironmentStructurePlan",
    "EnvironmentStructureBuilder",
    "get_environment_structure_builder",
    "reset_environment_structure_builder_for_tests",
    # anchor
    "PlacedAnchor",
    "AnchorPlan",
    "AnchorAssetBuilder",
    "get_anchor_asset_builder",
    "reset_anchor_asset_builder_for_tests",
    # support
    "SupportAsset",
    "SupportPlan",
    "SupportAssetBuilder",
    "get_support_asset_builder",
    "reset_support_asset_builder_for_tests",
    # decorative
    "DecorativeItem",
    "DecorationPlan",
    "DecorativePopulation",
    "get_decorative_population",
    "reset_decorative_population_for_tests",
    # atmosphere
    "AtmosphereProfile",
    "AtmospherePlan",
    "AtmosphereBuilder",
    "get_atmosphere_builder",
    "reset_atmosphere_builder_for_tests",
    # completeness
    "CompletenessResult",
    "EnvironmentCompleteness",
    "get_environment_completeness",
    "reset_environment_completeness_for_tests",
    # review
    "EnvironmentReviewResult",
    "EnvironmentReview",
    "get_environment_review",
    "reset_environment_review_for_tests",
    # serializer
    "EnvironmentSerializer",
    "get_environment_serializer",
    "reset_environment_serializer_for_tests",
    # statistics
    "EnvironmentStatRecord",
    "EnvironmentStatistics",
    "get_environment_statistics",
    "reset_environment_statistics_for_tests",
]
