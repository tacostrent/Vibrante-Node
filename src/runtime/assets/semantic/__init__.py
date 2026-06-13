"""
Semantic Asset Catalog & Megascans Knowledge Layer (Tier 12.7)
===============================================================
Transforms raw asset metadata into production knowledge.

Vibrante IS:
  - semantic orchestration
  - production-aware asset intelligence
  - environment-driven asset selection
  - storytelling-aware scene construction
  - workflow-aware asset reasoning

Tier 12.7 builds knowledge (not scenes, not shaders, not files):
  - Semantic catalog with environment / role / lookdev / cinematic metadata
  - Megascans metadata client (official API, offline fallback)
  - Local manifest reader (asset.json / manifest.json / metadata.json)
  - Knowledge graph of asset relationships
  - Query engine for production-intent-driven asset retrieval
  - Catalog review for semantic quality validation

Environment variables:
  VIBRANTE_MEGASCANS_TOKEN  — Megascans/Fab API token (optional)
  VIBRANTE_ASSET_STORAGE    — directory for catalog JSON persistence

Design rules:
  - No network calls when token not set
  - No DCC calls anywhere in this package
  - Deterministic — same input → same output
  - Thread-safe throughout
  - Never raises in public methods
"""
from __future__ import annotations

# --- Mappers ------------------------------------------------------------------
from .asset_environment_mapper import (
    BUILTIN_ENVIRONMENTS,
    EnvironmentMapping,
    AssetEnvironmentMapper,
    get_asset_environment_mapper,
    reset_asset_environment_mapper_for_tests,
)
from .asset_role_classifier import (
    BUILTIN_ROLES,
    RoleClassification,
    AssetRoleClassifier,
    get_asset_role_classifier,
    reset_asset_role_classifier_for_tests,
)
from .asset_storytelling_mapper import (
    STORYTELLING_ROLES,
    StorytellingMapping,
    AssetStorytellingMapper,
    get_asset_storytelling_mapper,
    reset_asset_storytelling_mapper_for_tests,
)
from .asset_lookdev_mapper import (
    LOOKDEV_TAGS,
    LookdevMapping,
    AssetLookdevMapper,
    get_asset_lookdev_mapper,
    reset_asset_lookdev_mapper_for_tests,
)
from .asset_cinematic_mapper import (
    CINEMATIC_USAGES,
    CinematicMapping,
    AssetCinematicMapper,
    get_asset_cinematic_mapper,
    reset_asset_cinematic_mapper_for_tests,
)

# --- Core infrastructure -----------------------------------------------------
from .asset_catalog_statistics import (
    StatRecord,
    CatalogStatistics,
    get_catalog_statistics,
    reset_catalog_statistics_for_tests,
)
from .asset_catalog_serializer import (
    AssetCatalogSerializer,
    get_asset_catalog_serializer,
    reset_asset_catalog_serializer_for_tests,
)
from .asset_manifest_reader import (
    ManifestRecord,
    AssetManifestReader,
    get_asset_manifest_reader,
    reset_asset_manifest_reader_for_tests,
)
from .megascans_metadata_client import (
    ENV_MEGASCANS_TOKEN,
    MegascansAssetMetadata,
    MegascansSearchResult,
    MegascansMetadataClient,
    get_megascans_metadata_client,
    reset_megascans_metadata_client_for_tests,
)
from .asset_metadata_extractor import (
    ExtractedMetadata,
    AssetMetadataExtractor,
    get_asset_metadata_extractor,
    reset_asset_metadata_extractor_for_tests,
)

# --- Enrichment & graph -------------------------------------------------------
from .semantic_asset_enricher import (
    EnrichedAsset,
    SemanticAssetEnricher,
    get_semantic_asset_enricher,
    reset_semantic_asset_enricher_for_tests,
)
from .asset_knowledge_graph import (
    RELATIONSHIP_TYPES,
    KnowledgeRelationship,
    AssetKnowledgeGraph,
    get_asset_knowledge_graph,
    reset_asset_knowledge_graph_for_tests,
)

# --- Catalog, provider, sync, query, review -----------------------------------
from .asset_catalog import (
    ENV_ASSET_STORAGE,
    CatalogEntry,
    AssetCatalog,
    get_asset_catalog,
    reset_asset_catalog_for_tests,
)
from .asset_metadata_provider import (
    MetadataRecord,
    AssetMetadataProvider,
    get_asset_metadata_provider,
    reset_asset_metadata_provider_for_tests,
)
from .asset_catalog_sync import (
    SyncReport,
    AssetCatalogSync,
    get_asset_catalog_sync,
    reset_asset_catalog_sync_for_tests,
)
from .asset_query_engine import (
    QueryResult,
    AssetQueryEngine,
    get_asset_query_engine,
    reset_asset_query_engine_for_tests,
)
from .asset_catalog_review import (
    CatalogReviewResult,
    AssetCatalogReview,
    get_asset_catalog_review,
    reset_asset_catalog_review_for_tests,
)

__all__ = [
    # Constants
    "BUILTIN_ENVIRONMENTS",
    "BUILTIN_ROLES",
    "STORYTELLING_ROLES",
    "LOOKDEV_TAGS",
    "CINEMATIC_USAGES",
    "RELATIONSHIP_TYPES",
    "ENV_MEGASCANS_TOKEN",
    "ENV_ASSET_STORAGE",
    # Mappers
    "EnvironmentMapping",
    "AssetEnvironmentMapper",
    "get_asset_environment_mapper",
    "reset_asset_environment_mapper_for_tests",
    "RoleClassification",
    "AssetRoleClassifier",
    "get_asset_role_classifier",
    "reset_asset_role_classifier_for_tests",
    "StorytellingMapping",
    "AssetStorytellingMapper",
    "get_asset_storytelling_mapper",
    "reset_asset_storytelling_mapper_for_tests",
    "LookdevMapping",
    "AssetLookdevMapper",
    "get_asset_lookdev_mapper",
    "reset_asset_lookdev_mapper_for_tests",
    "CinematicMapping",
    "AssetCinematicMapper",
    "get_asset_cinematic_mapper",
    "reset_asset_cinematic_mapper_for_tests",
    # Infrastructure
    "StatRecord",
    "CatalogStatistics",
    "get_catalog_statistics",
    "reset_catalog_statistics_for_tests",
    "AssetCatalogSerializer",
    "get_asset_catalog_serializer",
    "reset_asset_catalog_serializer_for_tests",
    "ManifestRecord",
    "AssetManifestReader",
    "get_asset_manifest_reader",
    "reset_asset_manifest_reader_for_tests",
    "MegascansAssetMetadata",
    "MegascansSearchResult",
    "MegascansMetadataClient",
    "get_megascans_metadata_client",
    "reset_megascans_metadata_client_for_tests",
    "ExtractedMetadata",
    "AssetMetadataExtractor",
    "get_asset_metadata_extractor",
    "reset_asset_metadata_extractor_for_tests",
    # Enrichment
    "EnrichedAsset",
    "SemanticAssetEnricher",
    "get_semantic_asset_enricher",
    "reset_semantic_asset_enricher_for_tests",
    "KnowledgeRelationship",
    "AssetKnowledgeGraph",
    "get_asset_knowledge_graph",
    "reset_asset_knowledge_graph_for_tests",
    # Catalog + query
    "CatalogEntry",
    "AssetCatalog",
    "get_asset_catalog",
    "reset_asset_catalog_for_tests",
    "MetadataRecord",
    "AssetMetadataProvider",
    "get_asset_metadata_provider",
    "reset_asset_metadata_provider_for_tests",
    "SyncReport",
    "AssetCatalogSync",
    "get_asset_catalog_sync",
    "reset_asset_catalog_sync_for_tests",
    "QueryResult",
    "AssetQueryEngine",
    "get_asset_query_engine",
    "reset_asset_query_engine_for_tests",
    "CatalogReviewResult",
    "AssetCatalogReview",
    "get_asset_catalog_review",
    "reset_asset_catalog_review_for_tests",
]
