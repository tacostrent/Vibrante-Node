"""
Structural Asset Classification (Tier 10.3)
===========================================
Automatically identifies architectural and structural assets before layout
generation and environment realization.

Distinguishes furniture, props, decorations, and architectural elements using
real geometry, asset metadata, semantic tags, and environment context.

Public surface:
    StructuralClassificationResult  — classification output
    StructuralAssetClassifier       — main entry point
    get_structural_asset_classifier()
    reset_structural_asset_classifier_for_tests()

    GeometryRoleDetector            — geometry-signal classifier
    get_geometry_role_detector()
    reset_geometry_role_detector_for_tests()

    MetadataRoleClassifier          — keyword/category classifier
    get_metadata_role_classifier()
    reset_metadata_role_classifier_for_tests()

    EnvironmentStructuralAffinity   — context-aware confidence adjustment
    get_environment_structural_affinity()
    reset_environment_structural_affinity_for_tests()

    PlacementIntent                 — routing / attachment instructions
    StructuralPlacementRules        — placement rule engine
    STRUCTURAL_ROLES                — frozenset of all structural role names
    get_structural_placement_rules()
    reset_structural_placement_rules_for_tests()

    StructuralReviewResult          — review output
    StructuralReview                — review engine
    get_structural_review()
    reset_structural_review_for_tests()

    StructuralStatRecord
    StructuralStatistics
    get_structural_statistics()
    reset_structural_statistics_for_tests()

    StructuralSerializer
    get_structural_serializer()
    reset_structural_serializer_for_tests()
"""

from src.runtime.structure.structural_asset_classifier import (
    ALL_STRUCTURAL_ROLES,
    StructuralClassificationResult,
    StructuralAssetClassifier,
    get_structural_asset_classifier,
    reset_structural_asset_classifier_for_tests,
)
from src.runtime.structure.geometry_role_detector import (
    GeometryRoleDetector,
    get_geometry_role_detector,
    reset_geometry_role_detector_for_tests,
)
from src.runtime.structure.metadata_role_classifier import (
    MetadataRoleClassifier,
    get_metadata_role_classifier,
    reset_metadata_role_classifier_for_tests,
)
from src.runtime.structure.environment_structural_affinity import (
    EnvironmentStructuralAffinity,
    get_environment_structural_affinity,
    reset_environment_structural_affinity_for_tests,
)
from src.runtime.structure.structural_placement_rules import (
    PlacementIntent,
    STRUCTURAL_ROLES,
    StructuralPlacementRules,
    get_structural_placement_rules,
    reset_structural_placement_rules_for_tests,
)
from src.runtime.structure.structural_review import (
    StructuralReviewResult,
    StructuralReview,
    get_structural_review,
    reset_structural_review_for_tests,
)
from src.runtime.structure.structural_statistics import (
    StructuralStatRecord,
    StructuralStatistics,
    get_structural_statistics,
    reset_structural_statistics_for_tests,
)
from src.runtime.structure.structural_serializer import (
    StructuralSerializer,
    get_structural_serializer,
    reset_structural_serializer_for_tests,
)

__all__ = [
    # Classifier
    "ALL_STRUCTURAL_ROLES",
    "StructuralClassificationResult",
    "StructuralAssetClassifier",
    "get_structural_asset_classifier",
    "reset_structural_asset_classifier_for_tests",
    # Geometry
    "GeometryRoleDetector",
    "get_geometry_role_detector",
    "reset_geometry_role_detector_for_tests",
    # Metadata
    "MetadataRoleClassifier",
    "get_metadata_role_classifier",
    "reset_metadata_role_classifier_for_tests",
    # Environment affinity
    "EnvironmentStructuralAffinity",
    "get_environment_structural_affinity",
    "reset_environment_structural_affinity_for_tests",
    # Placement rules
    "PlacementIntent",
    "STRUCTURAL_ROLES",
    "StructuralPlacementRules",
    "get_structural_placement_rules",
    "reset_structural_placement_rules_for_tests",
    # Review
    "StructuralReviewResult",
    "StructuralReview",
    "get_structural_review",
    "reset_structural_review_for_tests",
    # Statistics
    "StructuralStatRecord",
    "StructuralStatistics",
    "get_structural_statistics",
    "reset_structural_statistics_for_tests",
    # Serializer
    "StructuralSerializer",
    "get_structural_serializer",
    "reset_structural_serializer_for_tests",
]
