"""
src/runtime/layout — §46 Semantic Furniture Layout Engine
=========================================================
Transforms environment population from zone-based asset scattering
into relationship-based, affordance-driven placement.

Pipeline:
  Anchor Placement → Relationship Graph → Furniture Clustering →
  Surface Placement → Wall Attachment → Decoration Layout → Layout Review

Design rules:
  - No bridge calls. All modules are planning/advisory only.
  - Deterministic — same input always produces the same output.
  - Never raises in public methods.
  - Singleton pattern with reset_…_for_tests() on every module.
  - Thread-safe throughout.
"""

from src.runtime.layout.relationship_graph import (
    AssetRelationship,
    AssetRelationshipGraph,
    RELATIONSHIP_TYPES,
    get_relationship_graph,
    reset_relationship_graph_for_tests,
)
from src.runtime.layout.affordance_engine import (
    AffordanceProfile,
    AffordanceEngine,
    ANCHOR_TYPES,
    PLACEMENT_MODES,
    get_affordance_engine,
    reset_affordance_engine_for_tests,
)
from src.runtime.layout.surface_placement_engine import (
    SurfacePlacement,
    SurfacePlacementResult,
    SurfacePlacementEngine,
    get_surface_placement_engine,
    reset_surface_placement_engine_for_tests,
)
from src.runtime.layout.furniture_cluster_builder import (
    ClusterMember,
    FurnitureCluster,
    ClusterBuildResult,
    FurnitureClusterBuilder,
    get_furniture_cluster_builder,
    reset_furniture_cluster_builder_for_tests,
)
from src.runtime.layout.anchor_layout_engine import (
    AnchorPlacement,
    AnchorLayoutResult,
    AnchorLayoutEngine,
    get_anchor_layout_engine,
    reset_anchor_layout_engine_for_tests,
)
from src.runtime.layout.wall_attachment_engine import (
    WallAttachment,
    WallAttachmentResult,
    WallAttachmentEngine,
    get_wall_attachment_engine,
    reset_wall_attachment_engine_for_tests,
)
from src.runtime.layout.decoration_layout_engine import (
    DecorativeItem,
    DecorationLayoutResult,
    DecorationLayoutEngine,
    get_decoration_layout_engine,
    reset_decoration_layout_engine_for_tests,
)
from src.runtime.layout.layout_review import (
    LayoutReviewResult,
    LayoutReview,
    get_layout_review,
    reset_layout_review_for_tests,
)
from src.runtime.layout.layout_serializer import (
    LayoutSerializer,
    get_layout_serializer,
    reset_layout_serializer_for_tests,
)
from src.runtime.layout.layout_statistics import (
    LayoutStatRecord,
    LayoutStatistics,
    get_layout_statistics,
    reset_layout_statistics_for_tests,
)
from src.runtime.layout.semantic_layout_engine import (
    LayoutPlan,
    SemanticLayoutEngine,
    get_semantic_layout_engine,
    reset_semantic_layout_engine_for_tests,
)
from src.runtime.layout.relationship_realization_auditor import (
    REALIZATION_AUDIT_PASS,
    REALIZATION_AUDIT_FAIL,
    AssetAuditRecord,
    RealizationAuditResult,
    RelationshipRealizationAuditor,
    HoudiniTransformFetcher,
    get_relationship_realization_auditor,
    reset_relationship_realization_auditor_for_tests,
)
from src.runtime.layout.relationship_layout_engine import (
    RELATIONSHIP_LAYOUT_STATUS_PASS,
    RELATIONSHIP_LAYOUT_STATUS_FAIL,
    RelationshipAwareLayout,
    RelationshipLayoutEngine,
    get_relationship_layout_engine,
    reset_relationship_layout_engine_for_tests,
)
from src.runtime.layout.relationship_graph_builder import (
    RelationshipNode,
    RelationshipEdge,
    RelationshipGraph,
    GraphBuildResult,
    RelationshipGraphBuilder,
    GRAPH_RELATIONSHIP_TYPES,
    RELATIONSHIP_GRAPH_STATUS_PASS,
    RELATIONSHIP_GRAPH_STATUS_FAIL,
    get_relationship_graph_builder,
    reset_relationship_graph_builder_for_tests,
)

__all__ = [
    # Relationship graph
    "AssetRelationship", "AssetRelationshipGraph", "RELATIONSHIP_TYPES",
    "get_relationship_graph", "reset_relationship_graph_for_tests",
    # Affordance engine
    "AffordanceProfile", "AffordanceEngine", "ANCHOR_TYPES", "PLACEMENT_MODES",
    "get_affordance_engine", "reset_affordance_engine_for_tests",
    # Surface placement
    "SurfacePlacement", "SurfacePlacementResult", "SurfacePlacementEngine",
    "get_surface_placement_engine", "reset_surface_placement_engine_for_tests",
    # Furniture clusters
    "ClusterMember", "FurnitureCluster", "ClusterBuildResult", "FurnitureClusterBuilder",
    "get_furniture_cluster_builder", "reset_furniture_cluster_builder_for_tests",
    # Anchor layout
    "AnchorPlacement", "AnchorLayoutResult", "AnchorLayoutEngine",
    "get_anchor_layout_engine", "reset_anchor_layout_engine_for_tests",
    # Wall attachment
    "WallAttachment", "WallAttachmentResult", "WallAttachmentEngine",
    "get_wall_attachment_engine", "reset_wall_attachment_engine_for_tests",
    # Decoration layout
    "DecorativeItem", "DecorationLayoutResult", "DecorationLayoutEngine",
    "get_decoration_layout_engine", "reset_decoration_layout_engine_for_tests",
    # Review
    "LayoutReviewResult", "LayoutReview",
    "get_layout_review", "reset_layout_review_for_tests",
    # Serializer
    "LayoutSerializer", "get_layout_serializer", "reset_layout_serializer_for_tests",
    # Statistics
    "LayoutStatRecord", "LayoutStatistics",
    "get_layout_statistics", "reset_layout_statistics_for_tests",
    # Main engine
    "LayoutPlan", "SemanticLayoutEngine",
    "get_semantic_layout_engine", "reset_semantic_layout_engine_for_tests",
    # Tier 14.4.3 — Relationship Realization Audit
    "REALIZATION_AUDIT_PASS", "REALIZATION_AUDIT_FAIL",
    "AssetAuditRecord", "RealizationAuditResult",
    "RelationshipRealizationAuditor", "HoudiniTransformFetcher",
    "get_relationship_realization_auditor", "reset_relationship_realization_auditor_for_tests",
    # Tier 14.4.2 — Relationship-Aware Layout
    "RELATIONSHIP_LAYOUT_STATUS_PASS", "RELATIONSHIP_LAYOUT_STATUS_FAIL",
    "RelationshipAwareLayout", "RelationshipLayoutEngine",
    "get_relationship_layout_engine", "reset_relationship_layout_engine_for_tests",
    # Tier 14.4.1 — Relationship Graph Builder
    "RelationshipNode", "RelationshipEdge", "RelationshipGraph",
    "GraphBuildResult", "RelationshipGraphBuilder",
    "GRAPH_RELATIONSHIP_TYPES",
    "RELATIONSHIP_GRAPH_STATUS_PASS", "RELATIONSHIP_GRAPH_STATUS_FAIL",
    "get_relationship_graph_builder", "reset_relationship_graph_builder_for_tests",
]
