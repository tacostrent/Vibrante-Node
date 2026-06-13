"""
Geometry Intelligence (Tier 9.7)
=================================
Authoritative geometry intelligence layer. Produces reliable physical
characteristics for every imported asset before any placement, environment
construction, lookdev, lighting, or cinematic processing occurs.

Replaces dimension estimates with:
  - Real bounding boxes (explicit > format metadata > placement-type defaults)
  - Pivot detection (bottom_center / center / top_center / bottom_left / custom)
  - Ground contact points (legs / base_ring / base_plane / wheel / skid / track)
  - Support surface detection (tabletop / shelves / worktop / rack units)
  - 6-class scale classification (tiny/small/medium/large/structural/hero)
  - Role validation (furniture ↔ structure consistency checks)
  - 5-dimension geometry review

Canonical workflow:
  hou_mcp_geometry_analyze → hou_mcp_geometry_metrics → hou_mcp_support_surfaces
    → hou_mcp_geometry_review

Public surface:
"""

# --- Core data models ---------------------------------------------------
from src.runtime.assets.geometry.asset_metrics import (
    GEOMETRY_SCALE_CLASSES,
    PIVOT_TYPES,
    GEOMETRY_ROLES,
    HERO_PLACEMENT_TYPES,
    STRUCTURAL_PLACEMENT_TYPES,
    STRUCTURAL_CATEGORIES,
    SupportSurface,
    GroundContact,
    AssetMetrics,
    AssetMetricsBuilder,
    classify_geometry_scale,
    infer_role,
    get_asset_metrics_builder,
    reset_asset_metrics_builder_for_tests,
)

# --- Bounding box extraction -------------------------------------------
from src.runtime.assets.geometry.bounding_box_extractor import (
    GeometryBBoxExtractor,
    get_geometry_bbox_extractor,
    reset_geometry_bbox_extractor_for_tests,
)

# --- Pivot detection ---------------------------------------------------
from src.runtime.assets.geometry.pivot_detector import (
    PivotDetector,
    get_pivot_detector,
    reset_pivot_detector_for_tests,
)

# --- Ground contact detection -----------------------------------------
from src.runtime.assets.geometry.ground_contact_detector import (
    GroundContactDetector,
    get_ground_contact_detector,
    reset_ground_contact_detector_for_tests,
)

# --- Support surface detection ----------------------------------------
from src.runtime.assets.geometry.support_surface_detector import (
    SupportSurfaceDetector,
    get_support_surface_detector,
    reset_support_surface_detector_for_tests,
)

# --- Geometry analyzer (main orchestrator) ----------------------------
from src.runtime.assets.geometry.geometry_analyzer import (
    GeometryAnalysisResult,
    GeometryAnalyzer,
    get_geometry_analyzer,
    reset_geometry_analyzer_for_tests,
)

# --- Geometry review --------------------------------------------------
from src.runtime.assets.geometry.geometry_review import (
    GeometryReviewResult,
    GeometryReview,
    get_geometry_review,
    reset_geometry_review_for_tests,
)

# --- Serializer -------------------------------------------------------
from src.runtime.assets.geometry.geometry_serializer import (
    GeometrySerializer,
    get_geometry_serializer,
    reset_geometry_serializer_for_tests,
)

# --- Statistics -------------------------------------------------------
from src.runtime.assets.geometry.geometry_statistics import (
    GeometryStatRecord,
    GeometryStatistics,
    get_geometry_statistics,
    reset_geometry_statistics_for_tests,
)

__all__ = [
    # Constants
    "GEOMETRY_SCALE_CLASSES",
    "PIVOT_TYPES",
    "GEOMETRY_ROLES",
    "HERO_PLACEMENT_TYPES",
    "STRUCTURAL_PLACEMENT_TYPES",
    "STRUCTURAL_CATEGORIES",
    # Data models
    "SupportSurface",
    "GroundContact",
    "AssetMetrics",
    "AssetMetricsBuilder",
    "GeometryAnalysisResult",
    "GeometryReviewResult",
    "GeometryStatRecord",
    # Utilities
    "classify_geometry_scale",
    "infer_role",
    # Engines
    "GeometryBBoxExtractor",
    "PivotDetector",
    "GroundContactDetector",
    "SupportSurfaceDetector",
    "GeometryAnalyzer",
    "GeometryReview",
    "GeometrySerializer",
    "GeometryStatistics",
    # Singleton getters
    "get_asset_metrics_builder",
    "get_geometry_bbox_extractor",
    "get_pivot_detector",
    "get_ground_contact_detector",
    "get_support_surface_detector",
    "get_geometry_analyzer",
    "get_geometry_review",
    "get_geometry_serializer",
    "get_geometry_statistics",
    # Test resets
    "reset_asset_metrics_builder_for_tests",
    "reset_geometry_bbox_extractor_for_tests",
    "reset_pivot_detector_for_tests",
    "reset_ground_contact_detector_for_tests",
    "reset_support_surface_detector_for_tests",
    "reset_geometry_analyzer_for_tests",
    "reset_geometry_review_for_tests",
    "reset_geometry_serializer_for_tests",
    "reset_geometry_statistics_for_tests",
]
