"""
routing_audit.py — §53.1 Placement Routing Audit (Tier 14.3.1)
==============================================================
Validates that every classified asset is routed to the correct placement
engine BEFORE layout realization.

classification_success != routing_success

A beam classified correctly but routed to DecorationLayoutEngine will
produce a visually invalid scene even if collision_count == 0.

Pipeline insertion:
    classify → routing_audit → layout → realization → collision → constraint
    → scene_reality_validation

Expected routing table:

  Structural roles → EnvironmentStructureBuilder:
      wall, wall_segment, doorway, door_frame, window, window_frame,
      beam, support_beam, ceiling_beam, column, stair, railing, archway,
      architectural_module, structural_unknown

  Special structural:
      floor_piece   → FloorBuilder
      ceiling_piece → CeilingBuilder
      fireplace     → AnchorAssetBuilder

  Furniture types → FurnitureClusterBuilder:
      table, chair, stool, bench, bar_counter, cabinet, shelf,
      sofa, desk, workbench

  Surface prop types → SurfacePlacementEngine:
      bottle, cup, teapot, book, plate, lantern (+ aliases)

  Decorative types → DecorationLayoutEngine:
      crate, barrel, rope, cloth, sign (+ aliases)
      catch-all "decoration" role

Failure categories:
  STRUCTURAL_ROUTING_FAILURE
  FURNITURE_ROUTING_FAILURE
  SURFACE_ROUTING_FAILURE
  DECORATION_ROUTING_FAILURE

Blocking rule:
  production_ready = False if any ROUTING_FAILURE exists.
  A scene with incorrect routing is invalid even when collision_count == 0,
  constraint_violations == 0, and semantic_score >= threshold — because
  routing errors are upstream causes of invalid placements.

Input format (list of asset dicts):
  {
      "asset_id":       str,
      "asset_name":     str,
      "role":           str,   # structural_role from StructuralAssetClassifier
      "placement_type": str,   # optional — used as tie-breaker
      "assigned_engine":str,   # which engine the pipeline intends to use
  }

  Also accepts StructuralRoutingEngine-enriched dicts directly:
  {
      "_structural_role":  str,   # accepted as alias for "role"
      "_actual_builder":   str,   # accepted as alias for "assigned_engine"
  }

  Engine name aliases (both are accepted as "correct"):
      WallBuilder            ↔  EnvironmentStructureBuilder
      SemanticLayoutEngine   ↔  FurnitureClusterBuilder | SurfacePlacementEngine | DecorationLayoutEngine

Public API:
    RoutingRecord
    RoutingAuditResult
    PlacementRoutingAuditor
    get_placement_routing_auditor()
    reset_placement_routing_auditor_for_tests()
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ──────────────────────────────────────────────────────────────────────────────
# Routing tables
# ──────────────────────────────────────────────────────────────────────────────

# Structural role → expected engine.  These win unconditionally over type/name.
_STRUCTURAL_ROLE_TO_ENGINE: Dict[str, str] = {
    "wall":                 "EnvironmentStructureBuilder",
    "wall_segment":         "EnvironmentStructureBuilder",
    "doorway":              "EnvironmentStructureBuilder",
    "door_frame":           "EnvironmentStructureBuilder",
    "window":               "EnvironmentStructureBuilder",
    "window_frame":         "EnvironmentStructureBuilder",
    "beam":                 "EnvironmentStructureBuilder",
    "support_beam":         "EnvironmentStructureBuilder",
    "ceiling_beam":         "EnvironmentStructureBuilder",
    "column":               "EnvironmentStructureBuilder",
    "stair":                "EnvironmentStructureBuilder",
    "railing":              "EnvironmentStructureBuilder",
    "archway":              "EnvironmentStructureBuilder",
    "architectural_module": "EnvironmentStructureBuilder",
    "structural_unknown":   "EnvironmentStructureBuilder",
    "floor_piece":          "FloorBuilder",
    "ceiling_piece":        "CeilingBuilder",
    "fireplace":            "AnchorAssetBuilder",
}

# Asset type / placement_type keyword → expected engine for furniture & props.
_TYPE_TO_ENGINE: Dict[str, str] = {
    # Furniture → FurnitureClusterBuilder
    "table":         "FurnitureClusterBuilder",
    "chair":         "FurnitureClusterBuilder",
    "stool":         "FurnitureClusterBuilder",
    "bench":         "FurnitureClusterBuilder",
    "bar_counter":   "FurnitureClusterBuilder",
    "cabinet":       "FurnitureClusterBuilder",
    "shelf":         "FurnitureClusterBuilder",
    "sofa":          "FurnitureClusterBuilder",
    "desk":          "FurnitureClusterBuilder",
    "workbench":     "FurnitureClusterBuilder",
    # Surface props → SurfacePlacementEngine
    "bottle":        "SurfacePlacementEngine",
    "whiskey_bottle":"SurfacePlacementEngine",
    "cup":           "SurfacePlacementEngine",
    "glass":         "SurfacePlacementEngine",
    "mug":           "SurfacePlacementEngine",
    "teapot":        "SurfacePlacementEngine",
    "book":          "SurfacePlacementEngine",
    "plate":         "SurfacePlacementEngine",
    "bowl":          "SurfacePlacementEngine",
    "candle":        "SurfacePlacementEngine",
    "lantern":       "SurfacePlacementEngine",
    # Decorative → DecorationLayoutEngine
    "crate":         "DecorationLayoutEngine",
    "barrel":        "DecorationLayoutEngine",
    "rope":          "DecorationLayoutEngine",
    "cloth":         "DecorationLayoutEngine",
    "sign":          "DecorationLayoutEngine",
    "poster":        "DecorationLayoutEngine",
    "wanted_poster": "DecorationLayoutEngine",
    "oil_drum":      "DecorationLayoutEngine",
    "hay_bale":      "DecorationLayoutEngine",
}

# Coarse-role fallbacks when type lookup finds nothing.
_ROLE_FALLBACK: Dict[str, str] = {
    "furniture":  "FurnitureClusterBuilder",
    "prop":       "SurfacePlacementEngine",
    "decoration": "DecorationLayoutEngine",
}

# Which failure category maps to which expected engine.
_ENGINE_FAILURE_CATEGORY: Dict[str, str] = {
    "EnvironmentStructureBuilder": "STRUCTURAL_ROUTING_FAILURE",
    "WallBuilder":                 "STRUCTURAL_ROUTING_FAILURE",
    "OpeningBuilder":              "STRUCTURAL_ROUTING_FAILURE",
    "FloorBuilder":                "STRUCTURAL_ROUTING_FAILURE",
    "CeilingBuilder":              "STRUCTURAL_ROUTING_FAILURE",
    "BeamBuilder":                 "STRUCTURAL_ROUTING_FAILURE",
    "AnchorAssetBuilder":          "STRUCTURAL_ROUTING_FAILURE",
    "FurnitureClusterBuilder":     "FURNITURE_ROUTING_FAILURE",
    "SurfacePlacementEngine":      "SURFACE_ROUTING_FAILURE",
    "DecorationLayoutEngine":      "DECORATION_ROUTING_FAILURE",
    "SemanticLayoutEngine":        "FURNITURE_ROUTING_FAILURE",  # coarse-level alias
}

# StructuralRoutingEngine uses specific builder names; both are "correct" for structural roles.
# Map the fine-grained builders back to the canonical group expected by this auditor.
_BUILDER_CANONICAL: Dict[str, str] = {
    # Structural variants all map to the EnvironmentStructureBuilder group
    "WallBuilder":          "EnvironmentStructureBuilder",
    "OpeningBuilder":       "EnvironmentStructureBuilder",
    "BeamBuilder":          "EnvironmentStructureBuilder",
    # SemanticLayoutEngine covers furniture+surface+deco when no finer engine is set
    "SemanticLayoutEngine": "SemanticLayoutEngine",
}

# When the actual engine is SemanticLayoutEngine, any non-structural expected engine is OK.
_SEMANTIC_LAYOUT_COVERS: frozenset = frozenset({
    "FurnitureClusterBuilder",
    "SurfacePlacementEngine",
    "DecorationLayoutEngine",
})


def _expected_engine(role: str, placement_type: str, asset_name: str) -> str:
    """
    Determine the expected placement engine for one asset.

    Priority:
      1. Structural role table  — absolute override for any structural role
      2. Explicit placement_type keyword in _TYPE_TO_ENGINE
      3. Asset name keyword scan through _TYPE_TO_ENGINE
      4. Coarse role fallback  — "furniture", "prop", "decoration"
      5. "DecorationLayoutEngine" as generic default
    """
    # 1. Structural role wins unconditionally
    if role in _STRUCTURAL_ROLE_TO_ENGINE:
        return _STRUCTURAL_ROLE_TO_ENGINE[role]

    # 2. Explicit placement_type
    pt = (placement_type or "").lower().strip()
    if pt in _TYPE_TO_ENGINE:
        return _TYPE_TO_ENGINE[pt]

    # 3. Asset name keyword scan (longest keyword wins to avoid "bar" in "barrel")
    name_lower = (asset_name or "").lower()
    best_kw, best_engine = "", ""
    for keyword, engine in _TYPE_TO_ENGINE.items():
        if keyword in name_lower and len(keyword) > len(best_kw):
            best_kw    = keyword
            best_engine = engine
    if best_engine:
        return best_engine

    # 4. Coarse role fallback
    if role in _ROLE_FALLBACK:
        return _ROLE_FALLBACK[role]

    # 5. Default
    return "DecorationLayoutEngine"


def _engines_match(actual: str, expected: str) -> bool:
    """
    True when actual and expected refer to the same engine, accounting for the
    two naming conventions used across the pipeline:

      StructuralRoutingEngine produces:  WallBuilder / OpeningBuilder / BeamBuilder
      This auditor expects:              EnvironmentStructureBuilder   (for all three)

      StructuralRoutingEngine produces:  SemanticLayoutEngine
      This auditor expects:              FurnitureClusterBuilder | SurfacePlacementEngine |
                                         DecorationLayoutEngine   (depending on asset type)
    """
    if actual == expected:
        return True
    # Normalise actual to canonical group
    canon_actual = _BUILDER_CANONICAL.get(actual, actual)
    # WallBuilder / OpeningBuilder / BeamBuilder → EnvironmentStructureBuilder
    if canon_actual == "EnvironmentStructureBuilder" and expected == "EnvironmentStructureBuilder":
        return True
    # SemanticLayoutEngine covers all non-structural engine expectations
    if actual == "SemanticLayoutEngine" and expected in _SEMANTIC_LAYOUT_COVERS:
        return True
    return False


def _failure_category(expected_engine: str) -> str:
    return _ENGINE_FAILURE_CATEGORY.get(expected_engine, "DECORATION_ROUTING_FAILURE")


# ──────────────────────────────────────────────────────────────────────────────
# Data classes
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class RoutingRecord:
    """Per-asset routing audit record."""
    asset_id:         str
    asset_name:       str
    role:             str
    expected_engine:  str
    actual_engine:    str
    status:           str = "OK"   # "OK" | "FAIL"
    failure_category: str = ""     # "" | "STRUCTURAL_ROUTING_FAILURE" | …

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id":         self.asset_id,
            "asset_name":       self.asset_name,
            "role":             self.role,
            "expected_engine":  self.expected_engine,
            "actual_engine":    self.actual_engine,
            "status":           self.status,
            "failure_category": self.failure_category,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RoutingRecord":
        return cls(
            asset_id         = str(d.get("asset_id", "")),
            asset_name       = str(d.get("asset_name", "")),
            role             = str(d.get("role", "")),
            expected_engine  = str(d.get("expected_engine", "")),
            actual_engine    = str(d.get("actual_engine", "")),
            status           = str(d.get("status", "OK")),
            failure_category = str(d.get("failure_category", "")),
        )


@dataclass
class RoutingAuditResult:
    """
    Aggregate result of one placement routing audit run.

    routing_valid   = True only when misrouted_assets == 0
    production_ready = False when any ROUTING_FAILURE exists — even if
                       collision_count == 0 and semantic_score >= threshold.
    """
    total_assets:            int   = 0
    correctly_routed_assets: int   = 0
    misrouted_assets:        int   = 0
    routing_score:           float = 0.0
    routing_valid:           bool  = False
    production_ready:        bool  = False

    records:  List[RoutingRecord] = field(default_factory=list)
    failures: List[RoutingRecord] = field(default_factory=list)

    # Failure breakdown by category
    structural_routing_failures: int = 0
    furniture_routing_failures:  int = 0
    surface_routing_failures:    int = 0
    decoration_routing_failures: int = 0

    findings: List[str] = field(default_factory=list)
    blocking: List[str] = field(default_factory=list)

    audited_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_assets":                  self.total_assets,
            "correctly_routed_assets":       self.correctly_routed_assets,
            "misrouted_assets":              self.misrouted_assets,
            "routing_score":                 round(self.routing_score, 4),
            "routing_valid":                 self.routing_valid,
            "production_ready":              self.production_ready,
            "records":                       [r.to_dict() for r in self.records],
            "failures":                      [f.to_dict() for f in self.failures],
            "structural_routing_failures":   self.structural_routing_failures,
            "furniture_routing_failures":    self.furniture_routing_failures,
            "surface_routing_failures":      self.surface_routing_failures,
            "decoration_routing_failures":   self.decoration_routing_failures,
            "findings":                      list(self.findings),
            "blocking":                      list(self.blocking),
            "audited_at":                    self.audited_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RoutingAuditResult":
        return cls(
            total_assets                  = int(d.get("total_assets", 0)),
            correctly_routed_assets       = int(d.get("correctly_routed_assets", 0)),
            misrouted_assets              = int(d.get("misrouted_assets", 0)),
            routing_score                 = float(d.get("routing_score", 0.0)),
            routing_valid                 = bool(d.get("routing_valid", False)),
            production_ready              = bool(d.get("production_ready", False)),
            records                       = [RoutingRecord.from_dict(r) for r in d.get("records", [])],
            failures                      = [RoutingRecord.from_dict(f) for f in d.get("failures", [])],
            structural_routing_failures   = int(d.get("structural_routing_failures", 0)),
            furniture_routing_failures    = int(d.get("furniture_routing_failures", 0)),
            surface_routing_failures      = int(d.get("surface_routing_failures", 0)),
            decoration_routing_failures   = int(d.get("decoration_routing_failures", 0)),
            findings                      = list(d.get("findings", [])),
            blocking                      = list(d.get("blocking", [])),
            audited_at                    = float(d.get("audited_at", 0.0)),
        )


# ──────────────────────────────────────────────────────────────────────────────
# Auditor
# ──────────────────────────────────────────────────────────────────────────────

class PlacementRoutingAuditor:
    """
    Validates that every asset in a classified batch is routed to the
    correct placement engine.

    Expected input — list of asset dicts, each with:
        asset_id        (str)  — unique identifier
        asset_name      (str)  — human-readable name
        role            (str)  — structural_role from StructuralAssetClassifier
        placement_type  (str)  — optional; used as a type tie-breaker
        assigned_engine (str)  — which engine the pipeline intends to use

    Example:
        assets = [
            {
                "asset_id":       "beam_001",
                "asset_name":     "Old Wooden Beam",
                "role":           "beam",
                "placement_type": "beam",
                "assigned_engine":"DecorationLayoutEngine",   # ← FAIL
            },
            {
                "asset_id":       "chair_003",
                "asset_name":     "Wooden Chair",
                "role":           "furniture",
                "placement_type": "chair",
                "assigned_engine":"FurnitureClusterBuilder",  # ← OK
            },
        ]
        result = get_placement_routing_auditor().audit(assets)
        # result.routing_valid       → False
        # result.misrouted_assets    → 1
        # result.failures[0].status  → "FAIL"
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def audit(self, assets: List[Dict[str, Any]]) -> RoutingAuditResult:
        """
        Audit a list of classified assets for correct engine routing.
        Never raises.
        """
        try:
            return self._audit(assets)
        except Exception as exc:
            r = RoutingAuditResult()
            r.findings.append(f"PlacementRoutingAuditor internal error: {exc}")
            return r

    def _audit(self, assets: List[Dict[str, Any]]) -> RoutingAuditResult:
        with self._lock:
            return self._run(assets)

    def _run(self, assets: List[Dict[str, Any]]) -> RoutingAuditResult:
        result = RoutingAuditResult()

        if not assets:
            result.routing_score    = 1.0
            result.routing_valid    = True
            result.production_ready = True
            result.findings.append("No assets provided — audit passed vacuously.")
            return result

        records: List[RoutingRecord] = []

        for asset in assets:
            asset_id       = str(asset.get("asset_id")  or asset.get("id")   or "")
            asset_name     = str(asset.get("asset_name") or asset.get("name") or asset_id)
            # Accept both "role" (generic) and "_structural_role" (StructuralRoutingEngine)
            role           = str(
                asset.get("role")
                or asset.get("structural_role")
                or asset.get("_structural_role")
                or ""
            )
            placement_type = str(asset.get("placement_type") or "")
            # Accept both "assigned_engine" (generic) and "_actual_builder" (StructuralRoutingEngine)
            actual_engine  = str(
                asset.get("assigned_engine")
                or asset.get("_actual_builder")
                or ""
            )

            exp_engine = _expected_engine(role, placement_type, asset_name)

            if not actual_engine:
                status   = "FAIL"
                fail_cat = _failure_category(exp_engine)
                result.findings.append(
                    f"{asset_name!r} (role={role!r}): no assigned_engine — "
                    f"expected {exp_engine!r}"
                )
                actual_engine = "NONE"
            elif _engines_match(actual_engine, exp_engine):
                status   = "OK"
                fail_cat = ""
            else:
                status   = "FAIL"
                fail_cat = _failure_category(exp_engine)

            records.append(RoutingRecord(
                asset_id         = asset_id,
                asset_name       = asset_name,
                role             = role,
                expected_engine  = exp_engine,
                actual_engine    = actual_engine,
                status           = status,
                failure_category = fail_cat,
            ))

        result.records = records
        result.total_assets            = len(records)
        result.correctly_routed_assets = sum(1 for r in records if r.status == "OK")
        result.misrouted_assets        = sum(1 for r in records if r.status == "FAIL")
        result.failures                = [r for r in records if r.status == "FAIL"]

        # Breakdown by failure category
        result.structural_routing_failures = sum(
            1 for r in result.failures
            if r.failure_category == "STRUCTURAL_ROUTING_FAILURE"
        )
        result.furniture_routing_failures  = sum(
            1 for r in result.failures
            if r.failure_category == "FURNITURE_ROUTING_FAILURE"
        )
        result.surface_routing_failures    = sum(
            1 for r in result.failures
            if r.failure_category == "SURFACE_ROUTING_FAILURE"
        )
        result.decoration_routing_failures = sum(
            1 for r in result.failures
            if r.failure_category == "DECORATION_ROUTING_FAILURE"
        )

        # Aggregate score
        result.routing_score = (
            result.correctly_routed_assets / result.total_assets
            if result.total_assets > 0 else 1.0
        )

        # Blocking findings — one line per misrouted asset
        for f in result.failures:
            result.blocking.append(
                f"ROUTING_FAILURE: {f.asset_name!r} "
                f"(role={f.role!r}) — "
                f"expected {f.expected_engine!r}, "
                f"got {f.actual_engine!r} "
                f"[{f.failure_category}]"
            )

        # Verdicts
        result.routing_valid    = result.misrouted_assets == 0
        result.production_ready = result.routing_valid

        return result

    def expected_engine(
        self,
        role:           str,
        placement_type: str = "",
        asset_name:     str = "",
    ) -> str:
        """Public helper: look up the expected engine for a role/type without auditing."""
        return _expected_engine(role, placement_type, asset_name)


# ──────────────────────────────────────────────────────────────────────────────
# Singleton
# ──────────────────────────────────────────────────────────────────────────────

_instance: Optional[PlacementRoutingAuditor] = None
_lock = threading.Lock()


def get_placement_routing_auditor() -> PlacementRoutingAuditor:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = PlacementRoutingAuditor()
    return _instance


def reset_placement_routing_auditor_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
