"""
src/runtime/environment_realization — §49 Structural Environment Realization
=============================================================================
Converts environment blueprints into complete architectural structures:
floor, walls, ceiling, openings (doors/windows), beams, columns, and zones.

Design rules:
  - No bridge calls. All modules are planning/advisory only.
  - Deterministic — same environment always produces the same RoomShell.
  - Never raises in public methods.
  - Singleton pattern with reset_…_for_tests() on every module.
  - Thread-safe throughout.

Pipeline:
  EnvironmentRealizationEngine
    → StructuralBuilder
        → RoomShellBuilder
            → FloorBuilder
            → CeilingBuilder
            → WallBuilder
            → OpeningBuilder
            → BeamBuilder
        → ArchitecturalConstraintSolver
    → EnvRealizationReview
    → EnvRealizationStatistics
"""

from src.runtime.environment_realization.structural_elements import (
    StructuralElement,
    RoomShell,
    EnvironmentRealizationPlan,
    ELEMENT_TYPES,
    MATERIAL_TYPES,
    OPENING_TYPES,
)
from src.runtime.environment_realization.floor_builder import (
    FloorBuilder,
    get_floor_builder,
    reset_floor_builder_for_tests,
)
from src.runtime.environment_realization.ceiling_builder import (
    CeilingBuilder,
    get_ceiling_builder,
    reset_ceiling_builder_for_tests,
)
from src.runtime.environment_realization.wall_builder import (
    WallBuilder,
    get_wall_builder,
    reset_wall_builder_for_tests,
)
from src.runtime.environment_realization.opening_builder import (
    OpeningBuilder,
    get_opening_builder,
    reset_opening_builder_for_tests,
)
from src.runtime.environment_realization.beam_builder import (
    BeamBuilder,
    get_beam_builder,
    reset_beam_builder_for_tests,
)
from src.runtime.environment_realization.room_shell_builder import (
    RoomShellBuilder,
    get_room_shell_builder,
    reset_room_shell_builder_for_tests,
)
from src.runtime.environment_realization.architectural_constraint_solver import (
    ArchConstraintViolation,
    ArchConstraintResult,
    ArchitecturalConstraintSolver,
    get_architectural_constraint_solver,
    reset_architectural_constraint_solver_for_tests,
)
from src.runtime.environment_realization.structural_builder import (
    StructuralBuilder,
    get_structural_builder,
    reset_structural_builder_for_tests,
)
from src.runtime.environment_realization.environment_realization_engine import (
    EnvironmentRealizationEngine,
    get_environment_realization_engine,
    reset_environment_realization_engine_for_tests,
)
from src.runtime.environment_realization.environment_review import (
    EnvRealizationReviewResult,
    EnvRealizationReview,
    get_env_realization_review,
    reset_env_realization_review_for_tests,
)
from src.runtime.environment_realization.environment_statistics import (
    EnvRealizationRecord,
    EnvRealizationStatistics,
    get_env_realization_statistics,
    reset_env_realization_statistics_for_tests,
)
from src.runtime.environment_realization.environment_serializer import (
    EnvRealizationSerializer,
    get_env_realization_serializer,
    reset_env_realization_serializer_for_tests,
)

from src.runtime.environment_realization.structural_routing_engine import (
    PLACEMENT_ROUTING_MISMATCH,
    RoutingRecord,
    RoutingAudit,
    RoutingResult,
    StructuralRoutingEngine,
    STRUCTURAL_BUILDERS,
    get_structural_routing_engine,
    reset_structural_routing_engine_for_tests,
)
from src.runtime.environment_realization.room_shell_completeness_validator import (
    ShellRequirements,
    CompletenessValidationResult,
    RoomShellCompletenessValidator,
    get_room_shell_completeness_validator,
    reset_room_shell_completeness_validator_for_tests,
)
from src.runtime.environment_realization.structural_attachment_enforcer import (
    AttachmentRecord,
    AttachmentResult,
    StructuralAttachmentEnforcer,
    get_structural_attachment_enforcer,
    reset_structural_attachment_enforcer_for_tests,
)

__all__ = [
    # Data types
    "StructuralElement", "RoomShell", "EnvironmentRealizationPlan",
    "ELEMENT_TYPES", "MATERIAL_TYPES", "OPENING_TYPES",
    # Floor
    "FloorBuilder", "get_floor_builder", "reset_floor_builder_for_tests",
    # Ceiling
    "CeilingBuilder", "get_ceiling_builder", "reset_ceiling_builder_for_tests",
    # Walls
    "WallBuilder", "get_wall_builder", "reset_wall_builder_for_tests",
    # Openings
    "OpeningBuilder", "get_opening_builder", "reset_opening_builder_for_tests",
    # Beams
    "BeamBuilder", "get_beam_builder", "reset_beam_builder_for_tests",
    # Room shell
    "RoomShellBuilder", "get_room_shell_builder", "reset_room_shell_builder_for_tests",
    # Constraint solver
    "ArchConstraintViolation", "ArchConstraintResult",
    "ArchitecturalConstraintSolver",
    "get_architectural_constraint_solver",
    "reset_architectural_constraint_solver_for_tests",
    # Structural builder
    "StructuralBuilder", "get_structural_builder", "reset_structural_builder_for_tests",
    # Main engine
    "EnvironmentRealizationEngine",
    "get_environment_realization_engine",
    "reset_environment_realization_engine_for_tests",
    # Review
    "EnvRealizationReviewResult", "EnvRealizationReview",
    "get_env_realization_review", "reset_env_realization_review_for_tests",
    # Statistics
    "EnvRealizationRecord", "EnvRealizationStatistics",
    "get_env_realization_statistics", "reset_env_realization_statistics_for_tests",
    # Serializer
    "EnvRealizationSerializer",
    "get_env_realization_serializer", "reset_env_realization_serializer_for_tests",
    # Structural routing (Tier 10.3.5)
    "PLACEMENT_ROUTING_MISMATCH", "STRUCTURAL_BUILDERS",
    "RoutingRecord", "RoutingAudit", "RoutingResult",
    "StructuralRoutingEngine",
    "get_structural_routing_engine", "reset_structural_routing_engine_for_tests",
    # Room shell completeness
    "ShellRequirements", "CompletenessValidationResult",
    "RoomShellCompletenessValidator",
    "get_room_shell_completeness_validator",
    "reset_room_shell_completeness_validator_for_tests",
    # Structural attachment enforcer
    "AttachmentRecord", "AttachmentResult",
    "StructuralAttachmentEnforcer",
    "get_structural_attachment_enforcer",
    "reset_structural_attachment_enforcer_for_tests",
]
