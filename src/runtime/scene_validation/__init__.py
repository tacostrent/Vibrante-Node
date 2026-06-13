"""
src/runtime/scene_validation — §53 Scene Reality Validation (Tier 14.3)
=======================================================================
Validates that a ResolvedSceneLayout is correct in real-world terms, not
just internally consistent in engine terms.

Execution success ≠ scene correctness. This layer runs AFTER all layout
stages (classify → layout → realization → collision → constraint) and
produces four independent verdicts:

    geometry_valid      — no props inside furniture volumes (Rule 2)
                          and no floor-level surface props (Rule 1)
    semantic_valid      — all relationships intact, no orphans (Rules 3+5)
    plausibility_valid  — human-usage simulation passes (Rule 4)
    production_ready    — all three verdicts true

§53 acceptance criteria:
    ✓ No props inside chair volumes
    ✓ No props beneath furniture
    ✓ All small props on valid support surfaces
    ✓ All chairs attached to a valid furniture anchor
    ✓ plausibility_score >= 0.90
    ✓ semantic_validation_score >= 0.95
"""

from src.runtime.scene_validation.support_surface_validator import (
    SupportViolation,
    SupportSurfaceValidator,
    get_support_surface_validator,
    reset_support_surface_validator_for_tests,
)
from src.runtime.scene_validation.occupancy_validator import (
    OccupancyViolation,
    OccupancyValidator,
    get_occupancy_validator,
    reset_occupancy_validator_for_tests,
)
from src.runtime.scene_validation.relationship_validator import (
    RelationshipFailure,
    RelationshipValidator,
    get_relationship_validator,
    reset_relationship_validator_for_tests,
)
from src.runtime.scene_validation.plausibility_engine import (
    PlausibilityResult,
    PlausibilityEngine,
    get_plausibility_engine,
    reset_plausibility_engine_for_tests,
)
from src.runtime.scene_validation.orphan_detector import (
    OrphanRecord,
    OrphanDetector,
    get_orphan_detector,
    reset_orphan_detector_for_tests,
)
from src.runtime.scene_validation.scene_reality_validator import (
    SceneValidationResult,
    SceneRealityValidator,
    get_scene_reality_validator,
    reset_scene_reality_validator_for_tests,
)
from src.runtime.scene_validation.validation_review import (
    ValidationReviewResult,
    ValidationReview,
    get_validation_review,
    reset_validation_review_for_tests,
)
from src.runtime.scene_validation.validation_statistics import (
    ValidationRecord,
    ValidationStatistics,
    get_validation_statistics,
    reset_validation_statistics_for_tests,
)
from src.runtime.scene_validation.validation_serializer import (
    ValidationSerializer,
    get_validation_serializer,
    reset_validation_serializer_for_tests,
)
from src.runtime.scene_validation.routing_audit import (
    RoutingRecord,
    RoutingAuditResult,
    PlacementRoutingAuditor,
    get_placement_routing_auditor,
    reset_placement_routing_auditor_for_tests,
)

__all__ = [
    # Rule 1 — Support surface
    "SupportViolation", "SupportSurfaceValidator",
    "get_support_surface_validator", "reset_support_surface_validator_for_tests",
    # Rule 2 — Occupancy
    "OccupancyViolation", "OccupancyValidator",
    "get_occupancy_validator", "reset_occupancy_validator_for_tests",
    # Rule 3 — Relationship
    "RelationshipFailure", "RelationshipValidator",
    "get_relationship_validator", "reset_relationship_validator_for_tests",
    # Rule 4 — Plausibility
    "PlausibilityResult", "PlausibilityEngine",
    "get_plausibility_engine", "reset_plausibility_engine_for_tests",
    # Rule 5 — Orphan
    "OrphanRecord", "OrphanDetector",
    "get_orphan_detector", "reset_orphan_detector_for_tests",
    # Main orchestrator
    "SceneValidationResult", "SceneRealityValidator",
    "get_scene_reality_validator", "reset_scene_reality_validator_for_tests",
    # Review
    "ValidationReviewResult", "ValidationReview",
    "get_validation_review", "reset_validation_review_for_tests",
    # Statistics
    "ValidationRecord", "ValidationStatistics",
    "get_validation_statistics", "reset_validation_statistics_for_tests",
    # Serializer
    "ValidationSerializer",
    "get_validation_serializer", "reset_validation_serializer_for_tests",
    # Routing audit (§53.1 / Tier 14.3.1)
    "RoutingRecord", "RoutingAuditResult", "PlacementRoutingAuditor",
    "get_placement_routing_auditor", "reset_placement_routing_auditor_for_tests",
]
