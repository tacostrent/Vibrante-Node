"""
Asset Metadata Package (Tier 12 — Asset Ecosystem Expansion)
=============================================================
Enrichment, semantic mapping, normalization, and provenance tracking.

Public API:
    AssetMetadataEnricher          — class
    get_asset_metadata_enricher()  — singleton
    reset_asset_metadata_enricher_for_tests()

    AssetSemanticMapper            — class
    get_asset_semantic_mapper()    — singleton
    reset_asset_semantic_mapper_for_tests()

    ProviderNormalizer             — class
    get_provider_normalizer()      — singleton
    reset_provider_normalizer_for_tests()

    AssetProvenance                — class
    get_asset_provenance()         — singleton
    reset_asset_provenance_for_tests()
"""

from .asset_metadata_enricher import (
    AssetMetadataEnricher,
    get_asset_metadata_enricher,
    reset_asset_metadata_enricher_for_tests,
)

from .asset_semantic_mapper import (
    SemanticProfile,
    AssetSemanticMapper,
    get_asset_semantic_mapper,
    reset_asset_semantic_mapper_for_tests,
)

from .provider_normalizer import (
    ProviderNormalizer,
    get_provider_normalizer,
    reset_provider_normalizer_for_tests,
)

from .asset_provenance import (
    ProvenanceRecord,
    AssetProvenance,
    get_asset_provenance,
    reset_asset_provenance_for_tests,
)

__all__ = [
    "AssetMetadataEnricher",
    "get_asset_metadata_enricher",
    "reset_asset_metadata_enricher_for_tests",
    "SemanticProfile",
    "AssetSemanticMapper",
    "get_asset_semantic_mapper",
    "reset_asset_semantic_mapper_for_tests",
    "ProviderNormalizer",
    "get_provider_normalizer",
    "reset_provider_normalizer_for_tests",
    "ProvenanceRecord",
    "AssetProvenance",
    "get_asset_provenance",
    "reset_asset_provenance_for_tests",
]
