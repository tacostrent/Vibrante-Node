"""
src/runtime/layout_realization — §47 Layout Realization & Scene Constraint Solver
==================================================================================
Converts a Tier 9.8 LayoutPlan into concrete world-space transforms ready for
Houdini scene application.

Pipeline:
  Cluster Realization → Surface Realization → Wall Realization →
  Decoration Realization → Collision Solving → Constraint Solving →
  Scene Assembly → Review

Design rules:
  - No bridge calls except layout_application_engine (isolated adapter).
  - Deterministic — same LayoutPlan always produces the same ResolvedSceneLayout.
  - Never raises in public methods.
  - Singleton pattern with reset_…_for_tests() on every module.
  - Thread-safe throughout.
"""

from src.runtime.layout_realization.transform_resolver import (
    ResolvedTransform,
    TransformResolver,
    get_transform_resolver,
    reset_transform_resolver_for_tests,
)
from src.runtime.layout_realization.relationship_realizer import (
    RelationshipRealization,
    RelationshipRealizationResult,
    RelationshipRealizer,
    get_relationship_realizer,
    reset_relationship_realizer_for_tests,
)
from src.runtime.layout_realization.surface_realizer import (
    SurfaceRealizationResult,
    SurfaceRealizer,
    get_surface_realizer,
    reset_surface_realizer_for_tests,
)
from src.runtime.layout_realization.wall_attachment_realizer import (
    WallRealizationResult,
    WallAttachmentRealizer,
    get_wall_attachment_realizer,
    reset_wall_attachment_realizer_for_tests,
)
from src.runtime.layout_realization.cluster_realizer import (
    ClusterRealizationResult,
    ClusterRealizer,
    get_cluster_realizer,
    reset_cluster_realizer_for_tests,
)
from src.runtime.layout_realization.collision_solver import (
    CollisionRecord,
    CollisionResult,
    CollisionSolver,
    get_collision_solver,
    reset_collision_solver_for_tests,
)
from src.runtime.layout_realization.scene_constraint_solver import (
    ConstraintViolation,
    ConstraintSolveResult,
    SceneConstraintSolver,
    get_scene_constraint_solver,
    reset_scene_constraint_solver_for_tests,
)
from src.runtime.layout_realization.layout_realization_engine import (
    ResolvedSceneLayout,
    LayoutRealizationEngine,
    get_layout_realization_engine,
    reset_layout_realization_engine_for_tests,
)
from src.runtime.layout_realization.layout_application_engine import (
    ApplicationRecord,
    ApplicationResult,
    LayoutApplicationEngine,
    get_layout_application_engine,
    reset_layout_application_engine_for_tests,
)
from src.runtime.layout_realization.realization_review import (
    RealizationReviewResult,
    RealizationReview,
    get_realization_review,
    reset_realization_review_for_tests,
)
from src.runtime.layout_realization.realization_statistics import (
    RealizationRecord,
    RealizationStatistics,
    get_realization_statistics,
    reset_realization_statistics_for_tests,
)
from src.runtime.layout_realization.realization_serializer import (
    RealizationSerializer,
    get_realization_serializer,
    reset_realization_serializer_for_tests,
)
from src.runtime.layout_realization.relationship_metadata_writer import (
    METADATA_KEYS,
    AssetRelationshipMetadata,
    RelationshipMetadataWriter,
    build_userdata_from_transform,
    get_relationship_metadata_writer,
    reset_relationship_metadata_writer_for_tests,
)
from src.runtime.layout_realization.metadata_application_engine import (
    MetadataWriteRecord,
    MetadataWriteResult,
    MetadataApplicationEngine,
    get_metadata_application_engine,
    reset_metadata_application_engine_for_tests,
)
from src.runtime.layout_realization.relationship_persistence_auditor import (
    PERSISTENCE_AUDIT_PASS,
    PERSISTENCE_AUDIT_FAIL,
    REQUIRED_METADATA_KEYS,
    AssetMetadataRecord,
    RelationshipPersistenceAuditResult,
    RelationshipPersistenceAuditor,
    HoudiniMetadataFetcher,
    get_relationship_persistence_auditor,
    reset_relationship_persistence_auditor_for_tests,
)
from src.runtime.layout_realization.identity_metadata_writer import (
    IDENTITY_KEYS,
    AssetIdentityMetadata,
    IdentityMetadataWriter,
    build_identity_userdata,
    get_identity_metadata_writer,
    reset_identity_metadata_writer_for_tests,
)

__all__ = [
    # Transform resolver
    "ResolvedTransform", "TransformResolver",
    "get_transform_resolver", "reset_transform_resolver_for_tests",
    # Relationship realizer
    "RelationshipRealization", "RelationshipRealizationResult", "RelationshipRealizer",
    "get_relationship_realizer", "reset_relationship_realizer_for_tests",
    # Surface realizer
    "SurfaceRealizationResult", "SurfaceRealizer",
    "get_surface_realizer", "reset_surface_realizer_for_tests",
    # Wall attachment realizer
    "WallRealizationResult", "WallAttachmentRealizer",
    "get_wall_attachment_realizer", "reset_wall_attachment_realizer_for_tests",
    # Cluster realizer
    "ClusterRealizationResult", "ClusterRealizer",
    "get_cluster_realizer", "reset_cluster_realizer_for_tests",
    # Collision solver
    "CollisionRecord", "CollisionResult", "CollisionSolver",
    "get_collision_solver", "reset_collision_solver_for_tests",
    # Constraint solver
    "ConstraintViolation", "ConstraintSolveResult", "SceneConstraintSolver",
    "get_scene_constraint_solver", "reset_scene_constraint_solver_for_tests",
    # Layout realization engine (main orchestrator)
    "ResolvedSceneLayout", "LayoutRealizationEngine",
    "get_layout_realization_engine", "reset_layout_realization_engine_for_tests",
    # Application engine (Houdini bridge adapter)
    "ApplicationRecord", "ApplicationResult", "LayoutApplicationEngine",
    "get_layout_application_engine", "reset_layout_application_engine_for_tests",
    # Review
    "RealizationReviewResult", "RealizationReview",
    "get_realization_review", "reset_realization_review_for_tests",
    # Statistics
    "RealizationRecord", "RealizationStatistics",
    "get_realization_statistics", "reset_realization_statistics_for_tests",
    # Serializer
    "RealizationSerializer",
    "get_realization_serializer", "reset_realization_serializer_for_tests",
    # Relationship metadata writer (Tier 14.4.4)
    "METADATA_KEYS", "AssetRelationshipMetadata", "RelationshipMetadataWriter",
    "build_userdata_from_transform",
    "get_relationship_metadata_writer", "reset_relationship_metadata_writer_for_tests",
    # Metadata application engine (Tier 14.4.4 bridge adapter)
    "MetadataWriteRecord", "MetadataWriteResult", "MetadataApplicationEngine",
    "get_metadata_application_engine", "reset_metadata_application_engine_for_tests",
    # Relationship persistence auditor (Tier 14.4.4)
    "PERSISTENCE_AUDIT_PASS", "PERSISTENCE_AUDIT_FAIL", "REQUIRED_METADATA_KEYS",
    "AssetMetadataRecord", "RelationshipPersistenceAuditResult",
    "RelationshipPersistenceAuditor", "HoudiniMetadataFetcher",
    "get_relationship_persistence_auditor", "reset_relationship_persistence_auditor_for_tests",
    # Identity metadata writer (Tier 14.4.5)
    "IDENTITY_KEYS", "AssetIdentityMetadata", "IdentityMetadataWriter",
    "build_identity_userdata",
    "get_identity_metadata_writer", "reset_identity_metadata_writer_for_tests",
]
