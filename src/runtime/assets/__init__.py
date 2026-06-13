"""
Asset Intelligence Runtime (Tier 8)
=====================================
Transforms structured AssetQuery lists into ranked, validated,
provider-agnostic AssetRecommendations.

Pipeline:
    ScenePlan (asset_queries)
        → AssetDiscoveryEngine   (query all providers, merge, dedup)
        → AssetValidationEngine  (category / format / scale / conflict checks)
        → AssetRankingEngine     (6-factor deterministic scoring)
        → AssetRecommendationEngine (full pipeline orchestration)
        → AssetRecommendationResult (ranked, scored, explainable)

Providers (interchangeable, no downloads):
    SketchfabProvider   — industrial / sci-fi seed data
    PolyhavenProvider   — CC0 materials / HDRIs / models
    LocalLibraryProvider — local filesystem scan

Knowledge integrations (Tier 5, graceful degradation):
    ProductionMemory    — history boost (confidence 0.95)
    PatternLibrary      — pattern boost (confidence 0.80)
    AssetKnowledgeGraph — graph relationship boost (confidence 0.65)
    Provider quality    — base scoring (confidence 0.50)

DESIGN RULES:
  1. No Houdini imports.  No bridge calls.  Pure intelligence layer.
  2. No downloads.  No authentication.  Metadata only.
  3. All ranking is deterministic — same input → same ranking.
  4. Provider-agnostic — runtime never imports a concrete provider class.
  5. Tier 5 integrations wrapped in try/except — graceful degradation.

Usage:
    from src.runtime.assets import (
        get_asset_recommendation_engine,
        get_asset_discovery_engine,
        get_asset_validation_engine,
        get_asset_ranking_engine,
        get_provider_registry,
        SketchfabProvider,
        PolyhavenProvider,
    )
    from src.runtime.assets.schema import AssetDescriptor, AssetRecommendation
"""

# Schema
from .schema import (
    SCHEMA_VERSION,
    ASSET_CATEGORIES,
    ASSET_FORMATS,
    LICENSE_TYPES,
    SCALE_TYPES,
    ASSET_STYLES,
    AssetMetadata,
    AssetPreview,
    AssetDescriptor,
    AssetProviderResult,
    AssetQueryResult,
    AssetRecommendation,
)

# Providers
from .providers import (
    AssetProvider,
    ProviderRegistry,
    get_provider_registry,
    reset_provider_registry_for_tests,
    SketchfabProvider,
    PolyhavenProvider,
    LocalLibraryProvider,
)

# Discovery
from .discovery import (
    DiscoveryResult,
    AssetDiscoveryEngine,
    get_asset_discovery_engine,
    reset_asset_discovery_engine_for_tests,
)

# Validation
from .validation import (
    ValidationReport,
    AssetValidationEngine,
    get_asset_validation_engine,
    reset_asset_validation_engine_for_tests,
)

# Cache
from .cache import (
    AssetCache,
    get_asset_cache,
    reset_asset_cache_for_tests,
)

# Ranking
from .ranking import (
    RankingResult,
    AssetRankingEngine,
    get_asset_ranking_engine,
    reset_asset_ranking_engine_for_tests,
)

# Recommendations
from .recommendations import (
    AssetRecommendationResult,
    AssetRecommendationEngine,
    get_asset_recommendation_engine,
    reset_asset_recommendation_engine_for_tests,
)

# Serialization
from .serialization import (
    AssetSerializer,
    get_asset_serializer,
    reset_asset_serializer_for_tests,
)

# Logging
from .logging import (
    AssetLogEntry,
    AssetLogger,
    get_asset_logger,
    reset_asset_logger_for_tests,
)

# Tier 12 — Provider extensions
from .providers import (
    ProviderManager,
    get_provider_manager,
    reset_provider_manager_for_tests,
    SketchfabLiveProvider,
    QuixelProvider,
    UsdLibraryProvider,
    StudioLibraryProvider,
)

# Tier 12 — Download
from .download import (
    DownloadTask,
    AssetDownloadManager,
    get_asset_download_manager,
    reset_asset_download_manager_for_tests,
)

# Tier 12 — Storage (imported via cache package)
from .cache import (
    StorageRecord,
    AssetStorage,
    get_asset_storage,
    reset_asset_storage_for_tests,
    SyncReport,
    AssetSync,
    get_asset_sync,
    reset_asset_sync_for_tests,
)

# Tier 12 — Metadata
from .metadata import (
    AssetMetadataEnricher,
    get_asset_metadata_enricher,
    reset_asset_metadata_enricher_for_tests,
    SemanticProfile,
    AssetSemanticMapper,
    get_asset_semantic_mapper,
    reset_asset_semantic_mapper_for_tests,
    ProviderNormalizer,
    get_provider_normalizer,
    reset_provider_normalizer_for_tests,
    ProvenanceRecord,
    AssetProvenance,
    get_asset_provenance,
    reset_asset_provenance_for_tests,
)

# Assembly (Tier 9 — §29)
from .assembly import (
    EnvironmentBuilder,
    EnvironmentPlan,
    EnvironmentZone,
    get_environment_builder,
    reset_environment_builder_for_tests,
    PlacementTemplates,
    get_placement_templates,
    reset_placement_templates_for_tests,
    AssetPlacement,
    PlacementPlan,
    AssetPlacementEngine,
    get_asset_placement_engine,
    reset_asset_placement_engine_for_tests,
    AssetCluster,
    ClusterPlan,
    AssetClusteringEngine,
    get_asset_clustering_engine,
    reset_asset_clustering_engine_for_tests,
    StoryBeat,
    StoryLayout,
    StorytellingLayoutEngine,
    get_storytelling_layout_engine,
    reset_storytelling_layout_engine_for_tests,
    PopulationGroup,
    PopulationPlan,
    ScenePopulationEngine,
    get_scene_population_engine,
    reset_scene_population_engine_for_tests,
    ConstraintResult,
    CompositionReport,
    CompositionConstraints,
    get_composition_constraints,
    reset_composition_constraints_for_tests,
    EnvironmentReviewResult,
    EnvironmentReview,
    get_environment_review,
    reset_environment_review_for_tests,
)

__all__ = [
    # Schema constants
    "SCHEMA_VERSION",
    "ASSET_CATEGORIES",
    "ASSET_FORMATS",
    "LICENSE_TYPES",
    "SCALE_TYPES",
    "ASSET_STYLES",
    # Schema models
    "AssetMetadata",
    "AssetPreview",
    "AssetDescriptor",
    "AssetProviderResult",
    "AssetQueryResult",
    "AssetRecommendation",
    # Providers
    "AssetProvider",
    "ProviderRegistry",
    "get_provider_registry",
    "reset_provider_registry_for_tests",
    "SketchfabProvider",
    "PolyhavenProvider",
    "LocalLibraryProvider",
    # Discovery
    "DiscoveryResult",
    "AssetDiscoveryEngine",
    "get_asset_discovery_engine",
    "reset_asset_discovery_engine_for_tests",
    # Validation
    "ValidationReport",
    "AssetValidationEngine",
    "get_asset_validation_engine",
    "reset_asset_validation_engine_for_tests",
    # Cache
    "AssetCache",
    "get_asset_cache",
    "reset_asset_cache_for_tests",
    # Ranking
    "RankingResult",
    "AssetRankingEngine",
    "get_asset_ranking_engine",
    "reset_asset_ranking_engine_for_tests",
    # Recommendations
    "AssetRecommendationResult",
    "AssetRecommendationEngine",
    "get_asset_recommendation_engine",
    "reset_asset_recommendation_engine_for_tests",
    # Serialization
    "AssetSerializer",
    "get_asset_serializer",
    "reset_asset_serializer_for_tests",
    # Logging
    "AssetLogEntry",
    "AssetLogger",
    "get_asset_logger",
    "reset_asset_logger_for_tests",
    # Tier 12 — Providers
    "ProviderManager", "get_provider_manager", "reset_provider_manager_for_tests",
    "SketchfabLiveProvider", "QuixelProvider", "UsdLibraryProvider", "StudioLibraryProvider",
    # Tier 12 — Download
    "DownloadTask", "AssetDownloadManager",
    "get_asset_download_manager", "reset_asset_download_manager_for_tests",
    # Tier 12 — Storage
    "StorageRecord", "AssetStorage",
    "get_asset_storage", "reset_asset_storage_for_tests",
    "SyncReport", "AssetSync",
    "get_asset_sync", "reset_asset_sync_for_tests",
    # Tier 12 — Metadata
    "AssetMetadataEnricher",
    "get_asset_metadata_enricher", "reset_asset_metadata_enricher_for_tests",
    "SemanticProfile", "AssetSemanticMapper",
    "get_asset_semantic_mapper", "reset_asset_semantic_mapper_for_tests",
    "ProviderNormalizer",
    "get_provider_normalizer", "reset_provider_normalizer_for_tests",
    "ProvenanceRecord", "AssetProvenance",
    "get_asset_provenance", "reset_asset_provenance_for_tests",
    # Assembly (Tier 9 — §29)
    "EnvironmentBuilder", "EnvironmentPlan", "EnvironmentZone",
    "get_environment_builder", "reset_environment_builder_for_tests",
    "PlacementTemplates",
    "get_placement_templates", "reset_placement_templates_for_tests",
    "AssetPlacement", "PlacementPlan", "AssetPlacementEngine",
    "get_asset_placement_engine", "reset_asset_placement_engine_for_tests",
    "AssetCluster", "ClusterPlan", "AssetClusteringEngine",
    "get_asset_clustering_engine", "reset_asset_clustering_engine_for_tests",
    "StoryBeat", "StoryLayout", "StorytellingLayoutEngine",
    "get_storytelling_layout_engine", "reset_storytelling_layout_engine_for_tests",
    "PopulationGroup", "PopulationPlan", "ScenePopulationEngine",
    "get_scene_population_engine", "reset_scene_population_engine_for_tests",
    "ConstraintResult", "CompositionReport", "CompositionConstraints",
    "get_composition_constraints", "reset_composition_constraints_for_tests",
    "EnvironmentReviewResult", "EnvironmentReview",
    "get_environment_review", "reset_environment_review_for_tests",
]
