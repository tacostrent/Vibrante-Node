"""
src/runtime/environment_shell — Tier 10.4 Environment Shell Construction
=========================================================================
Environment-first architecture: build the complete room shell (floor, walls,
ceiling, structural anchors) BEFORE placing any asset.

Design rules:
  - No bridge calls. All modules are planning/advisory only.
  - Deterministic — same environment always produces the same EnvironmentShell.
  - Never raises in public methods.
  - Singleton pattern with reset_…_for_tests() on every module.
  - Thread-safe throughout.

Pipeline (EnvironmentShellBuilder):
  1. EnvironmentShellBlueprintFactory → EnvironmentShellBlueprint
  2. ShellFloorBuilder     → Phase 1  FLOOR_CONSTRUCTION_COMPLETE
  3. ShellWallBuilder      → Phase 2  WALL_CONSTRUCTION_COMPLETE
  4. ShellCeilingBuilder   → Phase 3  CEILING_CONSTRUCTION_COMPLETE
  5. StructuralAnchorGenerator → Phase 4  STRUCTURAL_ANCHORS_READY
  6. StructuralElementPlacer   → Phase 5  STRUCTURAL_PLACEMENT_COMPLETE
  7. ShellValidator        → Phase 6  ENVIRONMENT_VALIDATION_COMPLETE
  8. EnvironmentReadinessGate  → ENVIRONMENT_READY / ENVIRONMENT_NOT_READY
  9. EnvironmentShellAuditor   → ShellAudit
 10. ShellReview           → ShellReviewResult
 11. ShellStatistics       → record
"""

from src.runtime.environment_shell.shell_phase_result import (
    ShellPhaseResult,
    FLOOR_CONSTRUCTION_COMPLETE,
    WALL_CONSTRUCTION_COMPLETE,
    CEILING_CONSTRUCTION_COMPLETE,
    STRUCTURAL_ANCHORS_READY,
    STRUCTURAL_PLACEMENT_COMPLETE,
    ENVIRONMENT_VALIDATION_COMPLETE,
    ENVIRONMENT_NOT_READY,
    ENVIRONMENT_READY,
    ALL_PHASE_STATUSES,
)
from src.runtime.environment_shell.environment_shell_blueprint import (
    EnvironmentShellBlueprint,
    EnvironmentShellBlueprintFactory,
    get_blueprint_factory,
    reset_blueprint_factory_for_tests,
)
from src.runtime.environment_shell.shell_floor_builder import (
    ShellFloorBuilder,
    get_shell_floor_builder,
    reset_shell_floor_builder_for_tests,
)
from src.runtime.environment_shell.shell_wall_builder import (
    ShellWallBuilder,
    get_shell_wall_builder,
    reset_shell_wall_builder_for_tests,
)
from src.runtime.environment_shell.shell_ceiling_builder import (
    ShellCeilingBuilder,
    get_shell_ceiling_builder,
    reset_shell_ceiling_builder_for_tests,
)
from src.runtime.environment_shell.structural_anchor_generator import (
    StructuralAnchorGenerator,
    get_structural_anchor_generator,
    reset_structural_anchor_generator_for_tests,
)
from src.runtime.environment_shell.structural_element_placer import (
    StructuralElementPlacer,
    get_structural_element_placer,
    reset_structural_element_placer_for_tests,
)
from src.runtime.environment_shell.shell_validator import (
    ShellValidator,
    get_shell_validator,
    reset_shell_validator_for_tests,
)
from src.runtime.environment_shell.environment_shell_state import EnvironmentShell
from src.runtime.environment_shell.environment_readiness_gate import (
    BLOCKED_SYSTEMS,
    GateResult,
    EnvironmentReadinessGate,
    get_environment_readiness_gate,
    reset_environment_readiness_gate_for_tests,
)
from src.runtime.environment_shell.environment_shell_audit import (
    ShellAudit,
    EnvironmentShellAuditor,
    get_environment_shell_auditor,
    reset_environment_shell_auditor_for_tests,
)
from src.runtime.environment_shell.shell_review import (
    ShellReviewResult,
    ShellReview,
    get_shell_review,
    reset_shell_review_for_tests,
)
from src.runtime.environment_shell.shell_statistics import (
    ShellStatRecord,
    ShellStatistics,
    get_shell_statistics,
    reset_shell_statistics_for_tests,
)
from src.runtime.environment_shell.shell_serializer import (
    ShellSerializer,
    get_shell_serializer,
    reset_shell_serializer_for_tests,
)
from src.runtime.environment_shell.environment_shell_builder import (
    EnvironmentShellBuildResult,
    EnvironmentShellBuilder,
    get_environment_shell_builder,
    reset_environment_shell_builder_for_tests,
)

__all__ = [
    # Phase status constants
    "ShellPhaseResult",
    "FLOOR_CONSTRUCTION_COMPLETE",
    "WALL_CONSTRUCTION_COMPLETE",
    "CEILING_CONSTRUCTION_COMPLETE",
    "STRUCTURAL_ANCHORS_READY",
    "STRUCTURAL_PLACEMENT_COMPLETE",
    "ENVIRONMENT_VALIDATION_COMPLETE",
    "ENVIRONMENT_NOT_READY",
    "ENVIRONMENT_READY",
    "ALL_PHASE_STATUSES",
    # Blueprint
    "EnvironmentShellBlueprint",
    "EnvironmentShellBlueprintFactory",
    "get_blueprint_factory",
    "reset_blueprint_factory_for_tests",
    # Phase 1 — Floor
    "ShellFloorBuilder",
    "get_shell_floor_builder",
    "reset_shell_floor_builder_for_tests",
    # Phase 2 — Walls
    "ShellWallBuilder",
    "get_shell_wall_builder",
    "reset_shell_wall_builder_for_tests",
    # Phase 3 — Ceiling
    "ShellCeilingBuilder",
    "get_shell_ceiling_builder",
    "reset_shell_ceiling_builder_for_tests",
    # Phase 4 — Anchors
    "StructuralAnchorGenerator",
    "get_structural_anchor_generator",
    "reset_structural_anchor_generator_for_tests",
    # Phase 5 — Placement
    "StructuralElementPlacer",
    "get_structural_element_placer",
    "reset_structural_element_placer_for_tests",
    # Phase 6 — Validation
    "ShellValidator",
    "get_shell_validator",
    "reset_shell_validator_for_tests",
    # Shell state
    "EnvironmentShell",
    # Gate
    "BLOCKED_SYSTEMS",
    "GateResult",
    "EnvironmentReadinessGate",
    "get_environment_readiness_gate",
    "reset_environment_readiness_gate_for_tests",
    # Audit
    "ShellAudit",
    "EnvironmentShellAuditor",
    "get_environment_shell_auditor",
    "reset_environment_shell_auditor_for_tests",
    # Review
    "ShellReviewResult",
    "ShellReview",
    "get_shell_review",
    "reset_shell_review_for_tests",
    # Statistics
    "ShellStatRecord",
    "ShellStatistics",
    "get_shell_statistics",
    "reset_shell_statistics_for_tests",
    # Serializer
    "ShellSerializer",
    "get_shell_serializer",
    "reset_shell_serializer_for_tests",
    # Main builder
    "EnvironmentShellBuildResult",
    "EnvironmentShellBuilder",
    "get_environment_shell_builder",
    "reset_environment_shell_builder_for_tests",
]
