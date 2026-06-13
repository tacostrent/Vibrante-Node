"""
src/runtime/architectural_features — Tier 10.5 Structural Openings & Architectural Features
============================================================================================
Converts EnvironmentShell from a logical enclosure into a real architectural room
by generating physical openings, beam placements, fireplace attachments, and wall shelves.

Pipeline:
  EnvironmentShell (Tier 10.4)
  → ArchitecturalPlanBuilder      builds ArchitecturalPlan from shell anchors
  → EnvironmentArchitectureReview validates plan; produces ARCHITECTURE_STATUS
  → ArchitecturalFeatureRealizer  creates Houdini geometry (/obj/sh_door_opening_*, etc.)

Design rules:
  - No bridge calls except in ArchitecturalFeatureRealizer.
  - Deterministic throughout.
  - Never raises in public methods.
  - Singleton + reset_for_tests on every class.
"""

from src.runtime.architectural_features.architectural_plan import (
    ArchitecturalOpening,
    FireplacePlacement,
    BeamPlacement,
    WallShelfPlacement,
    ArchitecturalPlan,
    WALL_THICKNESS,
)
from src.runtime.architectural_features.architectural_plan_builder import (
    ArchitecturalPlanBuilder,
    get_architectural_plan_builder,
    reset_architectural_plan_builder_for_tests,
)
from src.runtime.architectural_features.environment_architecture_review import (
    ARCHITECTURE_STATUS_PASS,
    ARCHITECTURE_STATUS_FAIL,
    ArchitectureReviewResult,
    EnvironmentArchitectureReview,
    get_environment_architecture_review,
    reset_environment_architecture_review_for_tests,
)
from src.runtime.architectural_features.architectural_feature_realizer import (
    RealizationRecord,
    RealizationResult,
    ArchitecturalFeatureRealizer,
    get_architectural_feature_realizer,
    reset_architectural_feature_realizer_for_tests,
)

__all__ = [
    # Data models
    "ArchitecturalOpening", "FireplacePlacement",
    "BeamPlacement", "WallShelfPlacement",
    "ArchitecturalPlan", "WALL_THICKNESS",
    # Plan builder
    "ArchitecturalPlanBuilder",
    "get_architectural_plan_builder",
    "reset_architectural_plan_builder_for_tests",
    # Review
    "ARCHITECTURE_STATUS_PASS", "ARCHITECTURE_STATUS_FAIL",
    "ArchitectureReviewResult", "EnvironmentArchitectureReview",
    "get_environment_architecture_review",
    "reset_environment_architecture_review_for_tests",
    # Realizer
    "RealizationRecord", "RealizationResult",
    "ArchitecturalFeatureRealizer",
    "get_architectural_feature_realizer",
    "reset_architectural_feature_realizer_for_tests",
]
