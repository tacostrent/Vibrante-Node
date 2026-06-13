"""
Semantic Asset Assembly (Tier 9 / Tier 9.4 / Tier 9.5)
========================================================
Converts recommended assets into production-aware environment plans using
deterministic semantic assembly rules, real-asset spatial intelligence, and
structural environment scaffolding.

Pipeline:
    Tier 9.5 — Structure-First Assembly (NEW):
        EnvironmentStructureBuilder  (floor / walls / structural scaffold)
          ├── ArchitecturalTemplates (hard-coded blueprints for 21 environments)
          ├── EnvironmentZones       (zone types + canonical zone sets)
          └── EnvironmentBlueprint  (required elements + asset layer lists)
        AnchorAssetEngine           (major focal element assignments)
        DecorativePopulationEngine  (small props + semantic placement)
        EnvironmentCompletenessReviewer (6-dimension completeness check)

    Tier 9 / 9.4 — Asset Placement:
        EnvironmentBuilder          (zone-structured environment plan)
        PlacementTemplates          (deterministic slot positions)
        AssetPlacementEngine        (world-space positions + spatial optimizer)
          ├── BBoxExtractor         (real asset dimensions from metadata)
          ├── PlacementOptimizer    (collision-free position search)
          ├── CollisionDetector     (AABB collision detection)
          └── ClearanceValidator    (minimum separation enforcement)
        AssetClusteringEngine       (production-style asset groupings)
        StorytellingLayoutEngine    (visual flow + narrative structure)
        ScenePopulationEngine       (population groups + balance)
        CompositionConstraints      (readability + depth validation)
        EnvironmentReview           (environment quality evaluation)
        SpatialReview               (collision / clearance / walkability)

DESIGN RULES:
  1. No Houdini imports.  No bridge calls.  Planning only.
  2. No randomness.  All placement is deterministic.
  3. Structure-first: structure must exist before assets are placed.
  4. All mutations go through the transaction system downstream.
  5. Review is advisory — never blocks execution authority.
  6. collision_count > 0 → production_ready = False (hard rule, Tier 9.4).
"""

from .unit_normalizer import (
    UNIT_FACTORS,
    UnitNormalizer,
    get_unit_normalizer,
    reset_unit_normalizer_for_tests,
)
from .asset_scale_analyzer import (
    SCALE_CLASSES,
    STRUCTURAL_PLACEMENT_TYPES,
    STRUCTURAL_CATEGORIES,
    AssetScaleProfile,
    AssetScaleAnalyzer,
    get_asset_scale_analyzer,
    reset_asset_scale_analyzer_for_tests,
)
from .footprint_calculator import (
    FootprintResult,
    FootprintCalculator,
    get_footprint_calculator,
    reset_footprint_calculator_for_tests,
)
from .layout_spacing_engine import (
    SpacedPosition,
    LayoutSpacingEngine,
    get_layout_spacing_engine,
    reset_layout_spacing_engine_for_tests,
)
from .placement_relationships import (
    ROLES,
    PLACEMENT_MODES,
    STRUCTURAL_KEYWORD_HINTS,
    PlacementRelationship,
    PlacementRelationships,
    get_placement_relationships,
    reset_placement_relationships_for_tests,
)
from .environment_blueprint import (
    EnvironmentBlueprint,
)
from .environment_zones import (
    ZONE_TYPES,
    StructuralZone,
    BUILTIN_ZONE_DEFINITIONS,
    get_zone_definitions,
)
from .architectural_templates import (
    ArchitecturalTemplates,
    SUPPORTED_ENVIRONMENTS,
    get_architectural_templates,
    reset_architectural_templates_for_tests,
)
from .environment_structure_builder import (
    StructuralElement,
    EnvironmentStructure,
    EnvironmentStructureBuilder,
    get_environment_structure_builder,
    reset_environment_structure_builder_for_tests,
)
from .anchor_asset_engine import (
    AnchorAsset,
    AnchorPlan,
    AnchorAssetEngine,
    SEMANTIC_RELATIONSHIPS,
    get_anchor_asset_engine,
    reset_anchor_asset_engine_for_tests,
)
from .decorative_population_engine import (
    DecorativeItem,
    DecorationPlan,
    DecorativePopulationEngine,
    get_decorative_population_engine,
    reset_decorative_population_engine_for_tests,
)
from .environment_completeness_review import (
    EnvironmentCompletenessReview,
    EnvironmentCompletenessReviewer,
    get_environment_completeness_reviewer,
    reset_environment_completeness_reviewer_for_tests,
)
from .spatial_metadata import (
    SpatialMetadata,
    PLACEMENT_TYPES,
    UNIT_SYSTEMS,
)
from .bounding_box_extractor import (
    BBoxExtractor,
    get_bbox_extractor,
    reset_bbox_extractor_for_tests,
)
from .collision_detector import (
    CollisionPair,
    CollisionReport,
    CollisionDetector,
    get_collision_detector,
    reset_collision_detector_for_tests,
)
from .clearance_validator import (
    ClearanceViolation,
    ClearanceReport,
    ClearanceValidator,
    get_clearance_validator,
    reset_clearance_validator_for_tests,
)
from .semantic_placement_rules import (
    PlacementRule,
    SemanticPlacementRules,
    get_semantic_placement_rules,
    reset_semantic_placement_rules_for_tests,
)
from .placement_optimizer import (
    OptimizedPlacement,
    OptimizationPlan,
    PlacementOptimizer,
    get_placement_optimizer,
    reset_placement_optimizer_for_tests,
)
from .spatial_review import (
    SpatialReviewResult,
    SpatialReview,
    get_spatial_review,
    reset_spatial_review_for_tests,
)
from .environment_builder import (
    EnvironmentBuilder,
    EnvironmentPlan,
    EnvironmentZone,
    get_environment_builder,
    reset_environment_builder_for_tests,
)
from .placement_templates import (
    PlacementTemplates,
    get_placement_templates,
    reset_placement_templates_for_tests,
)
from .asset_placement_engine import (
    AssetPlacement,
    PlacementPlan,
    AssetPlacementEngine,
    get_asset_placement_engine,
    reset_asset_placement_engine_for_tests,
)
from .asset_clustering_engine import (
    AssetCluster,
    ClusterPlan,
    AssetClusteringEngine,
    get_asset_clustering_engine,
    reset_asset_clustering_engine_for_tests,
)
from .storytelling_layout_engine import (
    StoryBeat,
    StoryLayout,
    StorytellingLayoutEngine,
    get_storytelling_layout_engine,
    reset_storytelling_layout_engine_for_tests,
)
from .scene_population_engine import (
    PopulationGroup,
    PopulationPlan,
    ScenePopulationEngine,
    get_scene_population_engine,
    reset_scene_population_engine_for_tests,
)
from .composition_constraints import (
    ConstraintResult,
    CompositionReport,
    CompositionConstraints,
    get_composition_constraints,
    reset_composition_constraints_for_tests,
)
from .environment_review import (
    EnvironmentReviewResult,
    EnvironmentReview,
    get_environment_review,
    reset_environment_review_for_tests,
)

__all__ = [
    # Tier 9.6 — Scale-Aware Spatial Placement
    "UNIT_FACTORS", "UnitNormalizer",
    "get_unit_normalizer", "reset_unit_normalizer_for_tests",
    "SCALE_CLASSES", "STRUCTURAL_PLACEMENT_TYPES", "STRUCTURAL_CATEGORIES",
    "AssetScaleProfile", "AssetScaleAnalyzer",
    "get_asset_scale_analyzer", "reset_asset_scale_analyzer_for_tests",
    "FootprintResult", "FootprintCalculator",
    "get_footprint_calculator", "reset_footprint_calculator_for_tests",
    "SpacedPosition", "LayoutSpacingEngine",
    "get_layout_spacing_engine", "reset_layout_spacing_engine_for_tests",
    "ROLES", "PLACEMENT_MODES", "STRUCTURAL_KEYWORD_HINTS",
    "PlacementRelationship", "PlacementRelationships",
    "get_placement_relationships", "reset_placement_relationships_for_tests",
    # Tier 9.5 — Structural Environment Assembly
    "EnvironmentBlueprint",
    "ZONE_TYPES", "StructuralZone", "BUILTIN_ZONE_DEFINITIONS", "get_zone_definitions",
    "ArchitecturalTemplates", "SUPPORTED_ENVIRONMENTS",
    "get_architectural_templates", "reset_architectural_templates_for_tests",
    "StructuralElement", "EnvironmentStructure", "EnvironmentStructureBuilder",
    "get_environment_structure_builder", "reset_environment_structure_builder_for_tests",
    "AnchorAsset", "AnchorPlan", "AnchorAssetEngine", "SEMANTIC_RELATIONSHIPS",
    "get_anchor_asset_engine", "reset_anchor_asset_engine_for_tests",
    "DecorativeItem", "DecorationPlan", "DecorativePopulationEngine",
    "get_decorative_population_engine", "reset_decorative_population_engine_for_tests",
    "EnvironmentCompletenessReview", "EnvironmentCompletenessReviewer",
    "get_environment_completeness_reviewer", "reset_environment_completeness_reviewer_for_tests",
    # Spatial Metadata & Bounding Box
    "SpatialMetadata", "PLACEMENT_TYPES", "UNIT_SYSTEMS",
    "BBoxExtractor",
    "get_bbox_extractor", "reset_bbox_extractor_for_tests",
    # Collision Detection
    "CollisionPair", "CollisionReport", "CollisionDetector",
    "get_collision_detector", "reset_collision_detector_for_tests",
    # Clearance Validation
    "ClearanceViolation", "ClearanceReport", "ClearanceValidator",
    "get_clearance_validator", "reset_clearance_validator_for_tests",
    # Semantic Placement Rules
    "PlacementRule", "SemanticPlacementRules",
    "get_semantic_placement_rules", "reset_semantic_placement_rules_for_tests",
    # Placement Optimizer
    "OptimizedPlacement", "OptimizationPlan", "PlacementOptimizer",
    "get_placement_optimizer", "reset_placement_optimizer_for_tests",
    # Spatial Review
    "SpatialReviewResult", "SpatialReview",
    "get_spatial_review", "reset_spatial_review_for_tests",
    # Environment Builder
    "EnvironmentBuilder", "EnvironmentPlan", "EnvironmentZone",
    "get_environment_builder", "reset_environment_builder_for_tests",
    # Placement Templates
    "PlacementTemplates",
    "get_placement_templates", "reset_placement_templates_for_tests",
    # Asset Placement
    "AssetPlacement", "PlacementPlan", "AssetPlacementEngine",
    "get_asset_placement_engine", "reset_asset_placement_engine_for_tests",
    # Clustering
    "AssetCluster", "ClusterPlan", "AssetClusteringEngine",
    "get_asset_clustering_engine", "reset_asset_clustering_engine_for_tests",
    # Storytelling
    "StoryBeat", "StoryLayout", "StorytellingLayoutEngine",
    "get_storytelling_layout_engine", "reset_storytelling_layout_engine_for_tests",
    # Population
    "PopulationGroup", "PopulationPlan", "ScenePopulationEngine",
    "get_scene_population_engine", "reset_scene_population_engine_for_tests",
    # Composition
    "ConstraintResult", "CompositionReport", "CompositionConstraints",
    "get_composition_constraints", "reset_composition_constraints_for_tests",
    # Review
    "EnvironmentReviewResult", "EnvironmentReview",
    "get_environment_review", "reset_environment_review_for_tests",
]
