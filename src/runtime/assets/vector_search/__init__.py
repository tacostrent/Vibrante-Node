"""
Semantic Vector Search & Asset Retrieval (Tier 12.8)
======================================================
Intent-driven semantic asset retrieval using vector embeddings and hybrid ranking.

Vibrante IS:
  - semantic orchestration
  - production-aware asset intelligence
  - intent-driven asset retrieval
  - environment-aware asset reasoning
  - workflow-aware scene construction

Tier 12.8 retrieves knowledge (not scenes, not shaders, not files):
  - Deterministic 128-dim embeddings (no external ML deps required)
  - Optional sentence-transformers upgrade (all-MiniLM-L6-v2, 384 dims)
  - Pure-Python vector store with optional FAISS acceleration
  - Structured intent parsing (environment, role, storytelling, lookdev, cinematic)
  - Hybrid ranking: vector (0.40) + environment (0.20) + storytelling (0.15) + lookdev (0.10) + graph (0.10) + memory (0.05)
  - Full retrieval pipeline: intent → embed → search → rank → assets

Environment variables:
  VIBRANTE_ASSET_STORAGE  — directory for vector store JSON persistence

Design rules:
  - No network calls, no DCC calls
  - Deterministic — same input → same output (with DeterministicEmbeddingProvider)
  - Thread-safe throughout
  - Never raises in public methods
  - Provider-injectable for tests: set_embedding_provider(DeterministicEmbeddingProvider())
"""
from __future__ import annotations

# --- Similarity utilities -----------------------------------------------------
from .semantic_similarity import (
    cosine_similarity,
    rank_similarity,
    score_match,
    normalize_scores,
    l2_normalize,
)

# --- Embedding provider -------------------------------------------------------
from .embedding_provider import (
    EmbeddingVector,
    EmbeddingProvider,
    DeterministicEmbeddingProvider,
    SentenceTransformersProvider,
    get_embedding_provider,
    set_embedding_provider,
    reset_embedding_provider_for_tests,
)

# --- Intent parsing -----------------------------------------------------------
from .intent_parser import (
    ParsedIntent,
    IntentParser,
    get_intent_parser,
    reset_intent_parser_for_tests,
)

# --- Core infrastructure ------------------------------------------------------
from .asset_vector_store import (
    VectorSearchResult,
    AssetVectorStore,
    get_asset_vector_store,
    reset_asset_vector_store_for_tests,
)
from .retrieval_statistics import (
    RetrievalRecord,
    RetrievalStatistics,
    get_retrieval_statistics,
    reset_retrieval_statistics_for_tests,
)
from .retrieval_serializer import (
    RetrievalSerializer,
    get_retrieval_serializer,
    reset_retrieval_serializer_for_tests,
)

# --- Embedding builders -------------------------------------------------------
from .asset_embedding_builder import (
    EmbeddedAsset,
    AssetEmbeddingBuilder,
    get_asset_embedding_builder,
    reset_asset_embedding_builder_for_tests,
)
from .intent_embedding_engine import (
    IntentEmbeddingEngine,
    get_intent_embedding_engine,
    reset_intent_embedding_engine_for_tests,
)

# --- Search and ranking -------------------------------------------------------
from .vector_search_engine import (
    VectorSearchResponse,
    VectorSearchEngine,
    get_vector_search_engine,
    reset_vector_search_engine_for_tests,
)
from .hybrid_ranking_engine import (
    RankedAsset,
    HybridRankingEngine,
    get_hybrid_ranking_engine,
    reset_hybrid_ranking_engine_for_tests,
)

# --- Pipeline and review ------------------------------------------------------
from .retrieval_pipeline import (
    RetrievalResult,
    RetrievalPipeline,
    get_retrieval_pipeline,
    reset_retrieval_pipeline_for_tests,
)
from .retrieval_review import (
    RetrievalReviewResult,
    RetrievalReview,
    get_retrieval_review,
    reset_retrieval_review_for_tests,
)

# --- Index builder ------------------------------------------------------------
from .catalog_vector_index_builder import (
    IndexBuildResult,
    CatalogVectorIndexBuilder,
    get_catalog_vector_index_builder,
    reset_catalog_vector_index_builder_for_tests,
)

__all__ = [
    # Similarity
    "cosine_similarity",
    "rank_similarity",
    "score_match",
    "normalize_scores",
    "l2_normalize",
    # Embedding providers
    "EmbeddingVector",
    "EmbeddingProvider",
    "DeterministicEmbeddingProvider",
    "SentenceTransformersProvider",
    "get_embedding_provider",
    "set_embedding_provider",
    "reset_embedding_provider_for_tests",
    # Intent
    "ParsedIntent",
    "IntentParser",
    "get_intent_parser",
    "reset_intent_parser_for_tests",
    # Vector store
    "VectorSearchResult",
    "AssetVectorStore",
    "get_asset_vector_store",
    "reset_asset_vector_store_for_tests",
    # Stats / serializer
    "RetrievalRecord",
    "RetrievalStatistics",
    "get_retrieval_statistics",
    "reset_retrieval_statistics_for_tests",
    "RetrievalSerializer",
    "get_retrieval_serializer",
    "reset_retrieval_serializer_for_tests",
    # Embedding builders
    "EmbeddedAsset",
    "AssetEmbeddingBuilder",
    "get_asset_embedding_builder",
    "reset_asset_embedding_builder_for_tests",
    "IntentEmbeddingEngine",
    "get_intent_embedding_engine",
    "reset_intent_embedding_engine_for_tests",
    # Search and ranking
    "VectorSearchResponse",
    "VectorSearchEngine",
    "get_vector_search_engine",
    "reset_vector_search_engine_for_tests",
    "RankedAsset",
    "HybridRankingEngine",
    "get_hybrid_ranking_engine",
    "reset_hybrid_ranking_engine_for_tests",
    # Pipeline
    "RetrievalResult",
    "RetrievalPipeline",
    "get_retrieval_pipeline",
    "reset_retrieval_pipeline_for_tests",
    "RetrievalReviewResult",
    "RetrievalReview",
    "get_retrieval_review",
    "reset_retrieval_review_for_tests",
    # Index builder
    "IndexBuildResult",
    "CatalogVectorIndexBuilder",
    "get_catalog_vector_index_builder",
    "reset_catalog_vector_index_builder_for_tests",
]
