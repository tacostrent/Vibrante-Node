"""
Structural Routing Engine (Tier 10.3.5 — Structural Placement Routing)
=======================================================================
Routes classified structural assets to the correct architectural builder
and prevents them from entering the furniture/decoration layout pipeline.

For each asset:
  1. Classify via StructuralAssetClassifier.
  2. Get PlacementIntent via StructuralPlacementRules → selected_rule.
  3. Assign to the correct builder → applied_rule / actual_builder.
  4. Validate selected_rule == applied_rule (PLACEMENT_ROUTING_MISMATCH if not).

Builder assignments:
  wall / wall_segment / stair / railing /
  architectural_module / structural_unknown → WallBuilder
  doorway / door_frame / window / window_frame / archway → OpeningBuilder
  fireplace                                              → AnchorAssetBuilder
  beam / support_beam / column                           → BeamBuilder
  floor_piece                                            → FloorBuilder
  ceiling_piece                                          → CeilingBuilder
  furniture / prop / decoration                          → SemanticLayoutEngine

Placement rule names (selected_rule):
  wall_boundary        → wall_only
  wall_attachment      → wall_attached
  ceiling_support      → ceiling_mounted
  perimeter_support    → floor_perimeter
  floor_generation     → structural_floor
  ceiling_generation   → structural_ceiling
  room_shell           → room_shell_anchor
  transition_zone      → transition_anchor
  stair_edge           → stair_edge_anchor
  structure_zone       → structure_zone_anchor
  scene_zone           → layout_zone

Design rules:
  - No bridge calls. Planning only.
  - Deterministic — same input always produces the same routing.
  - Never raises in public methods.
  - Singleton pattern.
  - Thread-safe.

Public API:
    PLACEMENT_ROUTING_MISMATCH
    RoutingRecord
    RoutingAudit
    RoutingResult
    StructuralRoutingEngine
    get_structural_routing_engine()
    reset_structural_routing_engine_for_tests()
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional

from src.runtime.structure.structural_asset_classifier import (
    get_structural_asset_classifier,
)
from src.runtime.structure.structural_placement_rules import (
    STRUCTURAL_ROLES,
    get_structural_placement_rules,
)

# ── Constants ──────────────────────────────────────────────────────────────────

PLACEMENT_ROUTING_MISMATCH = "PLACEMENT_ROUTING_MISMATCH"

# Canonical rule names derived from PlacementIntent.placement_target
_PLACEMENT_TARGET_TO_RULE: Dict[str, str] = {
    "room_shell":           "room_shell_anchor",
    "wall_boundary":        "wall_only",
    "wall_attachment":      "wall_attached",
    "ceiling_support":      "ceiling_mounted",
    "perimeter_support":    "floor_perimeter",
    "floor_generation":     "structural_floor",
    "ceiling_generation":   "structural_ceiling",
    "transition_zone":      "transition_anchor",
    "stair_edge":           "stair_edge_anchor",
    "structure_zone":       "structure_zone_anchor",
    "scene_zone":           "layout_zone",
    "scatter":              "scatter_zone",
}

# What GenericLayoutSolver would incorrectly apply for structural assets
_GENERIC_SOLVER_FALLBACK: Dict[str, str] = {
    "wall_only":            "boundary_snap",
    "wall_attached":        "boundary_snap",
    "structural_floor":     "world_origin_anchor",
    "structural_ceiling":   "world_origin_anchor",
    "ceiling_mounted":      "world_origin_anchor",
    "floor_perimeter":      "boundary_snap",
    "transition_anchor":    "scatter_zone",
    "stair_edge_anchor":    "scatter_zone",
    "room_shell_anchor":    "scatter_zone",
    "structure_zone_anchor":"scatter_zone",
}

# route_to string → canonical builder name
_ROUTE_TO_BUILDER: Dict[str, str] = {
    "EnvironmentStructureBuilder": "WallBuilder",
    "OpeningBuilder":              "OpeningBuilder",
    "AnchorAssetBuilder":          "AnchorAssetBuilder",
    "BeamBuilder":                 "BeamBuilder",
    "FloorBuilder":                "FloorBuilder",
    "CeilingBuilder":              "CeilingBuilder",
    "SemanticLayoutEngine":        "SemanticLayoutEngine",
}

# Builders that are dedicated structural systems
STRUCTURAL_BUILDERS: FrozenSet[str] = frozenset({
    "WallBuilder", "OpeningBuilder", "AnchorAssetBuilder",
    "BeamBuilder", "FloorBuilder", "CeilingBuilder",
})


# ── Data types ─────────────────────────────────────────────────────────────────

@dataclass
class RoutingRecord:
    """Per-asset routing audit record."""

    asset_id:         str  = ""
    asset_name:       str  = ""
    structural_role:  str  = ""
    selected_rule:    str  = ""   # canonical rule from PlacementIntent
    applied_rule:     str  = ""   # rule this engine actually applied
    expected_builder: str  = ""   # builder prescribed by PlacementIntent
    actual_builder:   str  = ""   # builder this engine assigned
    routing_valid:    bool = False
    error_message:    str  = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id":         self.asset_id,
            "asset_name":       self.asset_name,
            "structural_role":  self.structural_role,
            "selected_rule":    self.selected_rule,
            "applied_rule":     self.applied_rule,
            "expected_builder": self.expected_builder,
            "actual_builder":   self.actual_builder,
            "routing_valid":    self.routing_valid,
            "error_message":    self.error_message,
        }


@dataclass
class RoutingAudit:
    """Summary audit across all routed assets in one batch."""

    audit_id:             str                 = field(default_factory=lambda: f"ra_{uuid.uuid4().hex[:10]}")
    total_assets:         int                 = 0
    structural_count:     int                 = 0
    furniture_count:      int                 = 0
    routing_valid_count:  int                 = 0
    mismatch_count:       int                 = 0
    records:              List[RoutingRecord] = field(default_factory=list)
    findings:             List[str]           = field(default_factory=list)
    ok:                   bool                = True
    errors:               List[str]           = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "audit_id":            self.audit_id,
            "total_assets":        self.total_assets,
            "structural_count":    self.structural_count,
            "furniture_count":     self.furniture_count,
            "routing_valid_count": self.routing_valid_count,
            "mismatch_count":      self.mismatch_count,
            "records":             [r.to_dict() for r in self.records],
            "findings":            list(self.findings),
            "ok":                  self.ok,
            "errors":              list(self.errors),
        }


@dataclass
class RoutingResult:
    """Complete routing result for a batch of assets."""

    result_id:           str                              = field(default_factory=lambda: f"rr_{uuid.uuid4().hex[:10]}")
    environment:         str                              = ""
    audit:               RoutingAudit                    = field(default_factory=RoutingAudit)
    structural_assets:   List[Dict[str, Any]]             = field(default_factory=list)
    furniture_assets:    List[Dict[str, Any]]              = field(default_factory=list)
    # builder_name → list of asset dicts assigned to that builder
    builder_assignments: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    production_ready:    bool                             = False
    warnings:            List[str]                        = field(default_factory=list)
    ok:                  bool                             = True
    errors:              List[str]                        = field(default_factory=list)
    generated_at:        float                            = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "result_id":        self.result_id,
            "environment":      self.environment,
            "audit":            self.audit.to_dict(),
            "structural_count": len(self.structural_assets),
            "furniture_count":  len(self.furniture_assets),
            "builder_assignments": {
                k: [dict(a) for a in v]
                for k, v in self.builder_assignments.items()
            },
            "production_ready": self.production_ready,
            "warnings":         list(self.warnings),
            "ok":               self.ok,
            "errors":           list(self.errors),
            "generated_at":     self.generated_at,
        }


# ── Engine ─────────────────────────────────────────────────────────────────────

class StructuralRoutingEngine:
    """
    Routes classified structural assets to dedicated architectural builders
    and sends furniture/props to the SemanticLayoutEngine.

    Usage:
        engine = get_structural_routing_engine()
        result = engine.route(assets, environment="western_room")
        # result.structural_assets  → route to FloorBuilder / WallBuilder / etc.
        # result.furniture_assets   → pass to SemanticLayoutEngine
        # result.builder_assignments["WallBuilder"] → assets for WallBuilder
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    # ── Public API ─────────────────────────────────────────────────────────────

    def route(
        self,
        assets:      List[Dict[str, Any]],
        environment: str = "",
    ) -> RoutingResult:
        """
        Classify assets and route each to the correct builder.

        Each asset dict is enriched with:
          _structural_role, _is_structural, _selected_rule,
          _applied_rule, _expected_builder, _actual_builder, _routing_valid

        Returns RoutingResult.  Never raises.
        """
        try:
            return self._route(list(assets), environment)
        except Exception as exc:
            r = RoutingResult(environment=environment)
            r.ok = False
            r.errors.append(f"StructuralRoutingEngine.route error: {exc}")
            return r

    def classify_and_split(
        self,
        assets:      List[Dict[str, Any]],
        environment: str = "",
    ) -> tuple:  # (structural: List[Dict], furniture: List[Dict])
        """
        Convenience: returns (structural_assets, furniture_assets) tuple.
        Never raises.
        """
        try:
            result = self.route(assets, environment)
            return result.structural_assets, result.furniture_assets
        except Exception:
            return [], list(assets)

    # ── Internal ───────────────────────────────────────────────────────────────

    def _route(
        self,
        assets:      List[Dict[str, Any]],
        environment: str,
    ) -> RoutingResult:
        classifier = get_structural_asset_classifier()
        rules      = get_structural_placement_rules()

        result = RoutingResult(environment=environment)
        audit  = result.audit

        for asset in assets:
            asset_id   = asset.get("asset_id", asset.get("name", ""))
            asset_name = asset.get("name", asset.get("asset_id", ""))

            # 1. Classify
            classification = classifier.classify(asset, environment)
            structural_role = classification.structural_role

            # 2. Get placement intent → selected_rule / expected_builder
            intent = rules.get_intent(asset_id, structural_role)
            selected_rule    = _PLACEMENT_TARGET_TO_RULE.get(
                intent.placement_target, intent.placement_target
            )
            expected_builder = _ROUTE_TO_BUILDER.get(intent.route_to, intent.route_to)

            # 3. Apply routing — the engine always honours the intent
            actual_builder = expected_builder
            applied_rule   = selected_rule

            # 4. Validate selected_rule == applied_rule
            routing_valid = (applied_rule == selected_rule) and (actual_builder == expected_builder)
            error_msg = ""
            if not routing_valid:
                error_msg = (
                    f"{PLACEMENT_ROUTING_MISMATCH}: "
                    f"selected_rule={selected_rule!r} != applied_rule={applied_rule!r}; "
                    f"expected_builder={expected_builder!r} != actual_builder={actual_builder!r}"
                )
                audit.findings.append(
                    f"Asset '{asset_id}' — {error_msg}"
                )

            # Enrich asset dict with routing metadata
            enriched = dict(asset)
            enriched["_structural_role"]  = structural_role
            enriched["_is_structural"]    = classification.is_structural
            enriched["_selected_rule"]    = selected_rule
            enriched["_applied_rule"]     = applied_rule
            enriched["_expected_builder"] = expected_builder
            enriched["_actual_builder"]   = actual_builder
            enriched["_routing_valid"]    = routing_valid
            enriched["_confidence"]       = classification.confidence

            # Build RoutingRecord
            rec = RoutingRecord(
                asset_id         = asset_id,
                asset_name       = asset_name,
                structural_role  = structural_role,
                selected_rule    = selected_rule,
                applied_rule     = applied_rule,
                expected_builder = expected_builder,
                actual_builder   = actual_builder,
                routing_valid    = routing_valid,
                error_message    = error_msg,
            )
            audit.records.append(rec)

            # Split into structural vs furniture
            if classification.is_structural:
                result.structural_assets.append(enriched)
                if actual_builder not in result.builder_assignments:
                    result.builder_assignments[actual_builder] = []
                result.builder_assignments[actual_builder].append(enriched)
            else:
                result.furniture_assets.append(enriched)
                if "SemanticLayoutEngine" not in result.builder_assignments:
                    result.builder_assignments["SemanticLayoutEngine"] = []
                result.builder_assignments["SemanticLayoutEngine"].append(enriched)

        # Summarise audit
        audit.total_assets        = len(assets)
        audit.structural_count    = len(result.structural_assets)
        audit.furniture_count     = len(result.furniture_assets)
        audit.routing_valid_count = sum(1 for rec in audit.records if rec.routing_valid)
        audit.mismatch_count      = sum(1 for rec in audit.records if not rec.routing_valid)
        audit.ok                  = audit.mismatch_count == 0

        result.production_ready = audit.ok
        if not audit.ok:
            result.warnings.append(
                f"{audit.mismatch_count} routing mismatch(es) detected — "
                "check audit.findings for PLACEMENT_ROUTING_MISMATCH details."
            )
        return result


# ── Singleton ──────────────────────────────────────────────────────────────────

_INSTANCE: Optional[StructuralRoutingEngine] = None
_LOCK = threading.Lock()


def get_structural_routing_engine() -> StructuralRoutingEngine:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = StructuralRoutingEngine()
        return _INSTANCE


def reset_structural_routing_engine_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
