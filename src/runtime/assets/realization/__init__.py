"""
Asset Realization & DCC Integration (Tier 13)
=============================================
Transforms AssetDescriptors from Tier 8/12 into production-ready
scene assets: imported, converted, normalized, dependency-resolved,
material-mapped, USD-built, instanced, and realized as transaction ops.

Pipeline:
    AssetDescriptor
        → AssetImporter      (import + provenance tracking)
        → AssetConverter     (format conversion to USD-friendly)
        → AssetNormalizer    (scale, orientation, units, pivots)
        → AssetDependencyResolver (textures, materials, references)
        → AssetMaterialMapper (renderer-specific material profiles)
        → UsdBuilder         (USD hierarchy + metadata)
        → AssetInstancer     (instance plans with transforms)
        → SceneAssetRealizer (transaction operation generation)
        → AssetValidationPipeline (full pipeline validation)
        → AssetRealizationReview  (production quality review)

DESIGN RULES:
  1. No bridge calls. All modules are planning/advisory only.
  2. No randomness. Same input always produces the same output.
  3. All mutations generate transaction operation dicts only.
  4. Review must be specific — never return "Execution successful".
  5. Never raises in public methods — capture errors in result dicts.
  6. Singleton pattern — every module has get_X() and reset_X_for_tests().
"""

from .asset_importer import (
    ImportResult,
    AssetImporter,
    get_asset_importer,
    reset_asset_importer_for_tests,
    SUPPORTED_FORMATS,
)

from .asset_converter import (
    ConversionResult,
    AssetConverter,
    get_asset_converter,
    reset_asset_converter_for_tests,
    CONVERSION_MATRIX,
)

from .asset_normalizer import (
    NormalizationResult,
    AssetNormalizer,
    get_asset_normalizer,
    reset_asset_normalizer_for_tests,
)

from .asset_dependency_resolver import (
    DependencyResult,
    AssetDependencyResolver,
    get_asset_dependency_resolver,
    reset_asset_dependency_resolver_for_tests,
)

from .asset_material_mapper import (
    MaterialProfile,
    MaterialMappingResult,
    AssetMaterialMapper,
    get_asset_material_mapper,
    reset_asset_material_mapper_for_tests,
    SUPPORTED_RENDERERS,
)

from .usd_builder import (
    UsdAsset,
    UsdBuildResult,
    UsdBuilder,
    get_usd_builder,
    reset_usd_builder_for_tests,
    USD_SCHEMA_VERSION,
)

from .asset_instancer import (
    AssetInstance,
    InstancePlan,
    AssetInstancer,
    get_asset_instancer,
    reset_asset_instancer_for_tests,
)

from .scene_asset_realizer import (
    RealizationSpec,
    RealizationPlan,
    RealizedAsset,
    SceneAssetRealizer,
    get_scene_asset_realizer,
    reset_scene_asset_realizer_for_tests,
)

from .asset_validation_pipeline import (
    PipelineValidationResult,
    AssetValidationPipeline,
    get_asset_validation_pipeline,
    reset_asset_validation_pipeline_for_tests,
)

from .asset_realization_review import (
    RealizationReviewResult,
    AssetRealizationReview,
    get_asset_realization_review,
    reset_asset_realization_review_for_tests,
)

from .realization_serializer import (
    RealizationSerializer,
    get_realization_serializer,
    reset_realization_serializer_for_tests,
)

from .realization_statistics import (
    RealizationStatistics,
    get_realization_statistics,
    reset_realization_statistics_for_tests,
)

__all__ = [
    # Importer
    "ImportResult", "AssetImporter",
    "get_asset_importer", "reset_asset_importer_for_tests",
    "SUPPORTED_FORMATS",
    # Converter
    "ConversionResult", "AssetConverter",
    "get_asset_converter", "reset_asset_converter_for_tests",
    "CONVERSION_MATRIX",
    # Normalizer
    "NormalizationResult", "AssetNormalizer",
    "get_asset_normalizer", "reset_asset_normalizer_for_tests",
    # Dependency resolver
    "DependencyResult", "AssetDependencyResolver",
    "get_asset_dependency_resolver", "reset_asset_dependency_resolver_for_tests",
    # Material mapper
    "MaterialProfile", "MaterialMappingResult", "AssetMaterialMapper",
    "get_asset_material_mapper", "reset_asset_material_mapper_for_tests",
    "SUPPORTED_RENDERERS",
    # USD builder
    "UsdAsset", "UsdBuildResult", "UsdBuilder",
    "get_usd_builder", "reset_usd_builder_for_tests",
    "USD_SCHEMA_VERSION",
    # Instancer
    "AssetInstance", "InstancePlan", "AssetInstancer",
    "get_asset_instancer", "reset_asset_instancer_for_tests",
    # Scene asset realizer
    "RealizationSpec", "RealizationPlan", "RealizedAsset", "SceneAssetRealizer",
    "get_scene_asset_realizer", "reset_scene_asset_realizer_for_tests",
    # Validation pipeline
    "PipelineValidationResult", "AssetValidationPipeline",
    "get_asset_validation_pipeline", "reset_asset_validation_pipeline_for_tests",
    # Review
    "RealizationReviewResult", "AssetRealizationReview",
    "get_asset_realization_review", "reset_asset_realization_review_for_tests",
    # Serializer
    "RealizationSerializer",
    "get_realization_serializer", "reset_realization_serializer_for_tests",
    # Statistics
    "RealizationStatistics",
    "get_realization_statistics", "reset_realization_statistics_for_tests",
]
