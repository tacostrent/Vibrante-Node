"""
src/runtime/reality — §54 Reality Intelligence (Tier 15.0+)
============================================================
Not a placement engine: a Senior Environment Artist, Layout TD, Level
Designer, Set Dresser and Houdini Pipeline TD in one package.

Core rule: never ask "Can I place this asset?" — always ask "Would a human
intentionally place this asset here?"

Reality First: the viewport is the source of truth. When geometry
contradicts metadata, GEOMETRY WINS.

Only geometry_inspector and correction_applier touch the Houdini bridge;
every other module is pure, deterministic planning.
"""

from src.runtime.reality.reality_scene_model import (
    FLOAT_TOLERANCE,
    WALL_PROXIMITY,
    STRUCTURAL_TYPES,
    SceneAsset,
    SceneSnapshot,
    infer_asset_type,
    parse_scene,
    raycast_down,
    distance_to_nearest_wall,
    is_against_wall,
    is_wall_mounted,
    is_ceiling_mounted,
    xz_overlap,
    horizontal_distance,
    facing_ry_towards,
)
from src.runtime.reality.human_reasoning_engine import (
    AssetJustification,
    HumanReasoningResult,
    HumanReasoningEngine,
    get_human_reasoning_engine,
    reset_human_reasoning_engine_for_tests,
)
from src.runtime.reality.functional_zone_builder import (
    ZONE_DEFINITIONS,
    FunctionalZone,
    FunctionalZonePlan,
    FunctionalZoneBuilder,
    get_functional_zone_builder,
    reset_functional_zone_builder_for_tests,
)
from src.runtime.reality.support_rule_engine import (
    SUPPORT_REQUIREMENTS,
    SupportCheck,
    SupportRuleResult,
    SupportRuleEngine,
    get_support_rule_engine,
    reset_support_rule_engine_for_tests,
)
from src.runtime.reality.floating_object_detector import (
    FloatingViolation,
    FloatingObjectResult,
    FloatingObjectDetector,
    get_floating_object_detector,
    reset_floating_object_detector_for_tests,
)
from src.runtime.reality.beam_connection_validator import (
    ENDPOINT_TOLERANCE,
    BeamConnection,
    BeamConnectionResult,
    BeamConnectionValidator,
    get_beam_connection_validator,
    reset_beam_connection_validator_for_tests,
)
from src.runtime.reality.architectural_integrity_validator import (
    IntegrityViolation,
    ArchitecturalIntegrityResult,
    ArchitecturalIntegrityValidator,
    get_architectural_integrity_validator,
    reset_architectural_integrity_validator_for_tests,
)
from src.runtime.reality.density_engine import (
    DensityResult,
    EnvironmentDensityEngine,
    get_environment_density_engine,
    reset_environment_density_engine_for_tests,
)
from src.runtime.reality.composition_engine import (
    MIN_NEGATIVE_SPACE,
    FocalPoint,
    CompositionResult,
    CompositionEngine,
    get_composition_engine,
    reset_composition_engine_for_tests,
)
from src.runtime.reality.correction_pass_engine import (
    CorrectionOp,
    CorrectionPlan,
    RealityCorrectionPass,
    get_reality_correction_pass,
    reset_reality_correction_pass_for_tests,
)
from src.runtime.reality.geometry_inspector import (
    ObservedAsset,
    ObservedScene,
    GeometryInspector,
    get_geometry_inspector,
    reset_geometry_inspector_for_tests,
)
from src.runtime.reality.correction_applier import (
    AppliedCorrection,
    CorrectionApplyResult,
    CorrectionApplier,
    get_correction_applier,
    reset_correction_applier_for_tests,
)
from src.runtime.reality.visual_review_engine import (
    VisualReviewResult,
    VisualReviewEngine,
    get_visual_review_engine,
    reset_visual_review_engine_for_tests,
)
from src.runtime.reality.reality_intelligence_engine import (
    RealityIntelligenceResult,
    RealityIntelligenceEngine,
    get_reality_intelligence_engine,
    reset_reality_intelligence_engine_for_tests,
)
from src.runtime.reality.reality_statistics import (
    RealityStatRecord,
    RealityStatistics,
    get_reality_statistics,
    reset_reality_statistics_for_tests,
)
from src.runtime.reality.reality_serializer import (
    REALITY_SCHEMA_VERSION,
    RealitySerializer,
    get_reality_serializer,
    reset_reality_serializer_for_tests,
)

__all__ = [
    # Scene model
    "FLOAT_TOLERANCE", "WALL_PROXIMITY", "STRUCTURAL_TYPES",
    "SceneAsset", "SceneSnapshot",
    "infer_asset_type", "parse_scene", "raycast_down",
    "distance_to_nearest_wall", "is_against_wall", "is_wall_mounted",
    "is_ceiling_mounted", "xz_overlap", "horizontal_distance",
    "facing_ry_towards",
    # Human reasoning
    "AssetJustification", "HumanReasoningResult", "HumanReasoningEngine",
    "get_human_reasoning_engine", "reset_human_reasoning_engine_for_tests",
    # Functional zones
    "ZONE_DEFINITIONS", "FunctionalZone", "FunctionalZonePlan",
    "FunctionalZoneBuilder",
    "get_functional_zone_builder", "reset_functional_zone_builder_for_tests",
    # Support rules
    "SUPPORT_REQUIREMENTS", "SupportCheck", "SupportRuleResult",
    "SupportRuleEngine",
    "get_support_rule_engine", "reset_support_rule_engine_for_tests",
    # Floating objects
    "FloatingViolation", "FloatingObjectResult", "FloatingObjectDetector",
    "get_floating_object_detector", "reset_floating_object_detector_for_tests",
    # Beam connections
    "ENDPOINT_TOLERANCE", "BeamConnection", "BeamConnectionResult",
    "BeamConnectionValidator",
    "get_beam_connection_validator", "reset_beam_connection_validator_for_tests",
    # Architectural integrity
    "IntegrityViolation", "ArchitecturalIntegrityResult",
    "ArchitecturalIntegrityValidator",
    "get_architectural_integrity_validator",
    "reset_architectural_integrity_validator_for_tests",
    # Density
    "DensityResult", "EnvironmentDensityEngine",
    "get_environment_density_engine", "reset_environment_density_engine_for_tests",
    # Composition
    "MIN_NEGATIVE_SPACE", "FocalPoint", "CompositionResult", "CompositionEngine",
    "get_composition_engine", "reset_composition_engine_for_tests",
    # Correction pass
    "CorrectionOp", "CorrectionPlan", "RealityCorrectionPass",
    "get_reality_correction_pass", "reset_reality_correction_pass_for_tests",
    # Geometry inspector (bridge)
    "ObservedAsset", "ObservedScene", "GeometryInspector",
    "get_geometry_inspector", "reset_geometry_inspector_for_tests",
    # Correction applier (bridge)
    "AppliedCorrection", "CorrectionApplyResult", "CorrectionApplier",
    "get_correction_applier", "reset_correction_applier_for_tests",
    # Visual review
    "VisualReviewResult", "VisualReviewEngine",
    "get_visual_review_engine", "reset_visual_review_engine_for_tests",
    # Orchestrator
    "RealityIntelligenceResult", "RealityIntelligenceEngine",
    "get_reality_intelligence_engine", "reset_reality_intelligence_engine_for_tests",
    # Statistics
    "RealityStatRecord", "RealityStatistics",
    "get_reality_statistics", "reset_reality_statistics_for_tests",
    # Serializer
    "REALITY_SCHEMA_VERSION", "RealitySerializer",
    "get_reality_serializer", "reset_reality_serializer_for_tests",
]
