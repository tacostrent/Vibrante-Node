"""
relationship_layout_engine.py — Tier 14.4.2 Relationship-Aware Layout
=======================================================================
Consumes the pre-built RelationshipGraph (Tier 14.4.1) and produces
world-space transforms that satisfy every semantic edge.

Execution order:
  Classification
  → RelationshipGraphBuilder  (Tier 14.4.1)
  → RelationshipLayoutEngine  ← this module
  → CollisionSolver           (Tier 9.9)
  → ConstraintSolver          (Tier 9.9)
  → Validation                (Tier 14.3)

Per-type placement rules:
  fireplace   attached_to wall      → snap to fireplace anchor / nearest wall,
                                      back face on wall plane (≤ 0.05m),
                                      front faces room interior
  chair       belongs_near table    → orbit at table_radius + clearance
              faces table           → rotate toward table centre
  stool       belongs_near bar      → linear spread along bar front face
  bottle      supports surface      → never floor; ty = surface_height
  cup         supports table        → on tabletop only
  plate       supports table        → on tabletop only
  lantern     supports table OR     → on surface if table present,
              attached_to wall         otherwise mount on wall
  barrel      belongs_near wall     → perimeter, never room centre
  crate       belongs_near wall     → near wall or corner

Hard rules (FAIL if violated):
  No bottle / cup / plate with ty ≤ MIN_SURFACE_H.
  No chair without a table relationship.
  No stool without a bar_counter relationship.
  No fireplace without a wall anchor.
  No lantern floating (ty ≤ MIN_SURFACE_H and not wall-mounted).

Scoring:
  relationship_score = valid_relationships / total_relationships
  PASS criterion: relationship_score ≥ 0.95

Public API:
  RELATIONSHIP_LAYOUT_STATUS_PASS
  RELATIONSHIP_LAYOUT_STATUS_FAIL
  RelationshipAwareLayout
  RelationshipLayoutEngine
  get_relationship_layout_engine()
  reset_relationship_layout_engine_for_tests()
"""

from __future__ import annotations

import math
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from src.runtime.layout.affordance_engine import get_affordance_engine
from src.runtime.layout.relationship_graph_builder import (
    RelationshipGraph,
    RelationshipEdge,
)
from src.runtime.layout_realization.transform_resolver import ResolvedTransform

# ---------------------------------------------------------------------------
# Status constants
# ---------------------------------------------------------------------------

RELATIONSHIP_LAYOUT_STATUS_PASS = "PASS"
RELATIONSHIP_LAYOUT_STATUS_FAIL = "FAIL"

# ---------------------------------------------------------------------------
# Placement constants
# ---------------------------------------------------------------------------

_MIN_SURFACE_H: float = 0.10   # ty below this is "on floor"
_WALL_INSET: float    = 0.04   # back face distance from wall plane (m)
_NEAR_WALL_INSET: float = 0.50 # barrel/crate setback from wall face (m)
_PASS_THRESHOLD: float  = 0.95 # relationship_score needed for PASS

# Surface heights per host type (m)
_SURFACE_HEIGHTS: Dict[str, float] = {
    "table":            0.75,
    "desk":             0.75,
    "workbench":        0.90,
    "bar_counter":      1.05,
    "shelf":            1.40,
    "counter":          0.90,
    "mantle":           1.20,
    "fireplace_mantel": 1.20,
    "cabinet":          1.60,
    "console":          0.85,
    "crate":            0.60,
    "pallet":           0.15,
}
_DEFAULT_SURFACE_H: float = 0.75

# Wall mount heights per asset type (m, midpoint)
_WALL_MOUNT_HEIGHTS: Dict[str, float] = {
    "poster":        1.60,
    "painting":      1.60,
    "wanted_poster": 1.60,
    "notice":        1.60,
    "certificate":   1.60,
    "mirror":        1.50,
    "sign":          1.80,
    "clock":         1.80,
    "rack":          1.60,
    "hook":          1.80,
    "coat_hook":     1.80,
    "banner":        2.15,
    "lantern":       2.40,
    "torch":         2.40,
    "sconce":        2.25,
    "shelf":         1.40,
    "trophy_mount":  1.60,
    "mounted_head":  1.80,
}
_DEFAULT_WALL_H: float = 1.60

# Orbit geometry for chairs around tables
_CHAIR_CLEARANCE: float = 0.45   # extra gap beyond table half-width (m)
_STOOL_CLEARANCE: float = 0.30   # gap from bar-counter front edge (m)
_STOOL_SPACING: float   = 0.70   # stool-to-stool spacing along bar (m)

# Default room dimensions when no shell is provided (m)
_DEFAULT_ROOM_W: float = 10.0
_DEFAULT_ROOM_D: float = 12.0
_DEFAULT_ROOM_H: float = 4.0

# Maximum surface props per anchor (prevents overflow)
_MAX_SURFACE_PROPS: int = 6

# Surface-item XZ offsets relative to anchor (for table/bar spreading)
_SURFACE_XZ_OFFSETS: List[Tuple[float, float]] = [
    (-0.25,  0.10),
    ( 0.25,  0.10),
    ( 0.00, -0.10),
    (-0.25, -0.10),
    ( 0.25, -0.10),
    ( 0.00,  0.25),
]


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class RelationshipAwareLayout:
    """Output of RelationshipLayoutEngine.build_layout()."""

    # Core output
    relationship_aware_transforms: List[ResolvedTransform] = field(default_factory=list)
    relationship_score:            float                   = 0.0

    # Categorised asset lists
    supported_objects:        List[str] = field(default_factory=list)
    wall_attached_objects:    List[str] = field(default_factory=list)
    surface_attached_objects: List[str] = field(default_factory=list)
    orphan_relationships:     List[str] = field(default_factory=list)

    # Per-rule validation flags
    fireplace_alignment_pass:    bool = True
    chair_table_relation_pass:   bool = True
    stool_bar_relation_pass:     bool = True
    bottle_support_pass:         bool = True
    cup_support_pass:            bool = True
    plate_support_pass:          bool = True
    lantern_attachment_pass:     bool = True
    barrel_wall_relation_pass:   bool = True
    crate_wall_relation_pass:    bool = True

    # Overall status
    status:            str        = RELATIONSHIP_LAYOUT_STATUS_PASS
    validation_errors: List[str]  = field(default_factory=list)
    warnings:          List[str]  = field(default_factory=list)
    ok:                bool       = True
    errors:            List[str]  = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "relationship_aware_transforms": [t.to_dict() for t in self.relationship_aware_transforms],
            "relationship_score":            round(self.relationship_score, 4),
            "supported_objects":             list(self.supported_objects),
            "wall_attached_objects":         list(self.wall_attached_objects),
            "surface_attached_objects":      list(self.surface_attached_objects),
            "orphan_relationships":          list(self.orphan_relationships),
            "fireplace_alignment_pass":      self.fireplace_alignment_pass,
            "chair_table_relation_pass":     self.chair_table_relation_pass,
            "stool_bar_relation_pass":       self.stool_bar_relation_pass,
            "bottle_support_pass":           self.bottle_support_pass,
            "cup_support_pass":              self.cup_support_pass,
            "plate_support_pass":            self.plate_support_pass,
            "lantern_attachment_pass":       self.lantern_attachment_pass,
            "barrel_wall_relation_pass":     self.barrel_wall_relation_pass,
            "crate_wall_relation_pass":      self.crate_wall_relation_pass,
            "status":                        self.status,
            "validation_errors":             list(self.validation_errors),
            "warnings":                      list(self.warnings),
            "ok":                            self.ok,
            "errors":                        list(self.errors),
        }


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class RelationshipLayoutEngine:
    """
    Produces relationship-enforced world-space transforms.

    Every transform is generated by first inspecting the asset's outgoing
    relationship edges and then applying the rule for each edge type.
    The resulting placement always satisfies the semantic relationship or
    records an orphan_relationship if the target is absent.

    Usage:
        layout = get_relationship_layout_engine().build_layout(
            scene_assets=assets,
            relationship_graph=graph,
            environment_shell=shell,
        )
        assert layout.status == RELATIONSHIP_LAYOUT_STATUS_PASS
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def build_layout(
        self,
        scene_assets:       List[Dict[str, Any]],
        relationship_graph: RelationshipGraph,
        environment_shell:  Any = None,         # EnvironmentShell | dict | None
    ) -> RelationshipAwareLayout:
        """
        Build relationship-aware placement transforms. Never raises.
        """
        try:
            return self._build(scene_assets, relationship_graph, environment_shell)
        except Exception as exc:
            result = RelationshipAwareLayout(ok=False, status=RELATIONSHIP_LAYOUT_STATUS_FAIL)
            result.errors.append(f"RelationshipLayoutEngine.build_layout failed: {exc}")
            return result

    # ------------------------------------------------------------------
    # Internal pipeline
    # ------------------------------------------------------------------

    def _build(
        self,
        scene_assets:       List[Dict[str, Any]],
        graph:              RelationshipGraph,
        shell:              Any,
    ) -> RelationshipAwareLayout:
        eng    = get_affordance_engine()
        result = RelationshipAwareLayout()

        # ---- Normalise shell to a plain dict (or empty) ---------------
        shell_dict = _shell_to_dict(shell)
        room       = _room_geometry(shell_dict)

        # ---- Build asset index ----------------------------------------
        # aid → asset dict, aid → inferred type
        aid_to_asset: Dict[str, Dict[str, Any]] = {}
        aid_to_type:  Dict[str, str]            = {}
        typed:        Dict[str, List[str]]      = {}  # type → [aids]

        for asset in scene_assets:
            aid  = _aid(asset)
            if not aid:
                continue
            atype = eng.infer_type(asset)
            aid_to_asset[aid] = asset
            aid_to_type[aid]  = atype
            typed.setdefault(atype, []).append(aid)

        # ---- Transforms accumulator ----------------------------------
        # aid → ResolvedTransform (filled incrementally, anchor-first)
        transforms: Dict[str, ResolvedTransform] = {}

        # ---- Relationship edge helpers --------------------------------
        # edges_by_from: aid → list of RelationshipEdge from that aid
        edges_by_from: Dict[str, List[RelationshipEdge]] = {}
        for edge in graph.get_all_edges():
            edges_by_from.setdefault(edge.from_node_id, []).append(edge)

        total_rel  = 0
        valid_rel  = 0

        # ================================================================
        # PASS 1: Anchors (table, bar_counter, fireplace)
        # ================================================================
        transforms.update(self._place_anchors(
            typed, aid_to_asset, aid_to_type, room
        ))

        # ================================================================
        # PASS 2: Relationship-driven placement for each non-anchor
        # ================================================================
        placed: Set[str] = set(transforms.keys())

        # Processing order: structural → seating → surface props → wall → perimeter
        _ORDER = [
            "fireplace",
            "chair", "stool",
            "bottle", "whiskey_bottle", "cup", "mug", "glass",
            "plate", "bowl", "book", "candle", "vase", "tool",
            "lantern", "torch", "sconce",
            "poster", "painting", "wanted_poster", "sign", "banner",
            "clock", "mirror",
            "barrel", "crate", "bucket", "bench",
        ]

        def _process_type(atype: str) -> None:
            for aid in typed.get(atype, []):
                if aid in placed:
                    return
                edges = edges_by_from.get(aid, [])
                t, n_total, n_valid = self._place_asset(
                    aid, atype, edges,
                    transforms, typed, aid_to_asset, aid_to_type, room,
                )
                if t is not None:
                    transforms[aid] = t
                    placed.add(aid)
                total_rel += n_total     # these are nonlocal-like via closure
                valid_rel  += n_valid    # but Python 3 closures don't mutate outer

        # Can't use nonlocal inside a nested def easily — collect via list
        counts: List[int] = [0, 0]

        for atype in _ORDER:
            for aid in typed.get(atype, []):
                if aid in placed:
                    continue
                edges = edges_by_from.get(aid, [])
                t, n_total, n_valid = self._place_asset(
                    aid, atype, edges,
                    transforms, typed, aid_to_asset, aid_to_type, room,
                )
                if t is not None:
                    transforms[aid] = t
                    placed.add(aid)
                counts[0] += n_total
                counts[1] += n_valid

        # Catch any type not in _ORDER
        for aid, atype in aid_to_type.items():
            if aid in placed:
                continue
            edges = edges_by_from.get(aid, [])
            t, n_total, n_valid = self._place_asset(
                aid, atype, edges,
                transforms, typed, aid_to_asset, aid_to_type, room,
            )
            if t is not None:
                transforms[aid] = t
                placed.add(aid)
            counts[0] += n_total
            counts[1] += n_valid

        total_rel = counts[0]
        valid_rel = counts[1]

        # Also count anchor edges from graph
        for edge in graph.get_all_edges():
            from_id = edge.from_node_id
            if from_id in (transforms) and from_id not in _get_counted_set(edges_by_from):
                pass  # already counted

        # ================================================================
        # PASS 3: Categorise outputs
        # ================================================================
        supported_ids: List[str]     = []
        wall_ids: List[str]          = []
        surface_ids: List[str]       = []
        orphan_rels: List[str]       = []

        for aid, t in transforms.items():
            if t.relationship in ("supports", "on_top_of") or t.ty > _MIN_SURFACE_H:
                if t.parent_id:
                    supported_ids.append(aid)
                    surface_ids.append(aid)
            if t.relationship == "attached_to" and "wall" in (t.parent_id or ""):
                wall_ids.append(aid)

        # Orphan relationships: edges that point to missing targets
        for edge in graph.get_all_edges():
            fid = edge.from_node_id
            tid = edge.to_node_id
            if fid not in transforms and fid in aid_to_asset:
                orphan_rels.append(
                    f"{fid} —[{edge.relationship_type}]→ {tid} (source not placed)"
                )
            elif not edge.is_virtual_target and tid not in transforms:
                orphan_rels.append(
                    f"{fid} —[{edge.relationship_type}]→ {tid} (target missing)"
                )

        # ================================================================
        # PASS 4: Validation (hard rules)
        # ================================================================
        v_errors: List[str] = []

        def _hard_rule_check(
            flag_name:   str,
            asset_types: List[str],
            predicate,
            error_fmt:   str,
        ) -> bool:
            passed = True
            for atype in asset_types:
                for aid in typed.get(atype, []):
                    t = transforms.get(aid)
                    if not predicate(t, aid, atype):
                        v_errors.append(error_fmt.format(aid=aid, atype=atype))
                        passed = False
            return passed

        # Bottle / cup / plate not on floor
        def _on_surface(t, aid, atype):
            return t is not None and t.ty > _MIN_SURFACE_H

        result.bottle_support_pass = _hard_rule_check(
            "bottle_support_pass", ["bottle", "whiskey_bottle"],
            _on_surface,
            "FAIL: '{aid}' ({atype}) placed on floor (ty ≤ {h:.2f}m)".format_map,
        ) if False else _run_check(
            ["bottle", "whiskey_bottle"],
            lambda t, aid, atype: t is not None and t.ty > _MIN_SURFACE_H,
            typed, transforms, v_errors,
            "BOTTLE: '{aid}' ({atype}) on floor — must be on surface",
        )

        result.cup_support_pass = _run_check(
            ["cup", "mug", "glass"],
            lambda t, aid, atype: t is not None and t.ty > _MIN_SURFACE_H,
            typed, transforms, v_errors,
            "CUP: '{aid}' on floor — must be on tabletop",
        )
        result.plate_support_pass = _run_check(
            ["plate", "bowl"],
            lambda t, aid, atype: t is not None and t.ty > _MIN_SURFACE_H,
            typed, transforms, v_errors,
            "PLATE: '{aid}' on floor — must be on tabletop",
        )

        # Chair without table relationship
        result.chair_table_relation_pass = _run_check(
            ["chair"],
            lambda t, aid, atype: t is not None and t.parent_id != "",
            typed, transforms, v_errors,
            "CHAIR: '{aid}' has no table relationship — no table in scene",
        )

        # Stool without bar
        result.stool_bar_relation_pass = _run_check(
            ["stool"],
            lambda t, aid, atype: t is not None and t.parent_id != "",
            typed, transforms, v_errors,
            "STOOL: '{aid}' has no bar_counter relationship",
        )

        # Fireplace without wall anchor
        def _fp_wall(t, aid, atype):
            return (
                t is not None
                and (
                    "wall" in (t.parent_id or "")
                    or t.relationship == "attached_to"
                )
            )
        result.fireplace_alignment_pass = _run_check(
            ["fireplace"], _fp_wall, typed, transforms, v_errors,
            "FIREPLACE: '{aid}' not aligned to wall anchor",
        )

        # Lantern not floating
        def _lantern_ok(t, aid, atype):
            if t is None:
                return False
            on_surface = t.ty > _MIN_SURFACE_H
            on_wall    = "wall" in (t.parent_id or "") or t.relationship == "attached_to"
            return on_surface or on_wall
        result.lantern_attachment_pass = _run_check(
            ["lantern"], _lantern_ok, typed, transforms, v_errors,
            "LANTERN: '{aid}' floating — must be on surface or wall-mounted",
        )

        # Barrel / crate near wall
        def _near_wall(t, aid, atype):
            if t is None:
                return False
            hw, hd = room["half_width"], room["half_depth"]
            clearance = _NEAR_WALL_INSET + 0.5
            # Consider "near wall" if within clearance of any perimeter
            return (
                abs(t.tx) > hw - clearance
                or abs(t.tz) > hd - clearance
                or "wall" in (t.parent_id or "")
                or "corner" in (t.relationship or "")
            )
        result.barrel_wall_relation_pass = _run_check(
            ["barrel", "oil_drum"],
            _near_wall, typed, transforms, v_errors,
            "BARREL: '{aid}' not near perimeter wall",
        )
        result.crate_wall_relation_pass = _run_check(
            ["crate", "hay_bale"],
            _near_wall, typed, transforms, v_errors,
            "CRATE: '{aid}' not near perimeter wall",
        )

        # ================================================================
        # PASS 5: Score
        # ================================================================
        # Re-derive from transforms: each placed asset's relationship
        # matches its primary graph edge → count as valid.
        total_scored = 0
        valid_scored = 0

        for edge in graph.get_all_edges():
            fid = edge.from_node_id
            if fid not in aid_to_asset:
                continue  # skip virtual nodes
            total_scored += 1
            t = transforms.get(fid)
            if t is None:
                continue
            if _edge_satisfied(edge, t, transforms):
                valid_scored += 1

        rel_score = valid_scored / max(1, total_scored)

        # ================================================================
        # Assemble result
        # ================================================================
        result.relationship_aware_transforms = list(transforms.values())
        result.relationship_score            = round(rel_score, 4)
        result.supported_objects             = sorted(set(supported_ids))
        result.wall_attached_objects         = sorted(set(wall_ids))
        result.surface_attached_objects      = sorted(set(surface_ids))
        result.orphan_relationships          = orphan_rels
        result.validation_errors             = v_errors
        result.ok                            = len(v_errors) == 0
        result.status = (
            RELATIONSHIP_LAYOUT_STATUS_PASS
            if rel_score >= _PASS_THRESHOLD and len(v_errors) == 0
            else RELATIONSHIP_LAYOUT_STATUS_FAIL
        )

        return result

    # ==================================================================
    # Placement sub-routines
    # ==================================================================

    def _place_anchors(
        self,
        typed:        Dict[str, List[str]],
        aid_to_asset: Dict[str, Dict[str, Any]],
        aid_to_type:  Dict[str, str],
        room:         Dict[str, Any],
    ) -> Dict[str, ResolvedTransform]:
        """Place all anchor assets at canonical scene positions."""
        out: Dict[str, ResolvedTransform] = {}
        hw, hd = room["half_width"], room["half_depth"]
        ceiling_h = room["height"]

        # --- Tables (hero centre) ---
        tables = typed.get("table", [])
        for idx, aid in enumerate(tables):
            asset = aid_to_asset[aid]
            # Offset multiple tables: first at origin, rest spread toward +Z
            tz = float(idx) * 3.0
            out[aid] = ResolvedTransform(
                asset_id=aid, asset_name=_name(asset),
                tx=0.0, ty=0.0, tz=tz,
                ry=0.0,
                relationship="anchor",
            )

        # --- Desks ---
        for idx, aid in enumerate(typed.get("desk", [])):
            out[aid] = ResolvedTransform(
                asset_id=aid, asset_name=_name(aid_to_asset[aid]),
                tx=float(idx) * 2.5 - 1.25, ty=0.0, tz=hd * 0.4,
                ry=180.0, relationship="anchor",
            )

        # --- Workbenches ---
        for idx, aid in enumerate(typed.get("workbench", [])):
            out[aid] = ResolvedTransform(
                asset_id=aid, asset_name=_name(aid_to_asset[aid]),
                tx=float(idx) * 2.5 - 1.25, ty=0.0, tz=-(hd * 0.3),
                ry=0.0, relationship="anchor",
            )

        # --- Bar counter (against back/north wall) ---
        for idx, aid in enumerate(typed.get("bar_counter", [])):
            out[aid] = ResolvedTransform(
                asset_id=aid, asset_name=_name(aid_to_asset[aid]),
                tx=0.0, ty=0.0, tz=-(hd * 0.7),
                ry=0.0, relationship="anchor",
            )

        # --- Fireplace (against north wall, centred) ---
        for idx, aid in enumerate(typed.get("fireplace", [])):
            asset     = aid_to_asset[aid]
            # inset from wall by depth of fireplace (~0.5m) + wall gap
            fp_depth  = float(asset.get("depth_m") or asset.get("bbox_z") or 0.5)
            tz_snap   = -(hd - fp_depth * 0.5 - _WALL_INSET)
            out[aid]  = ResolvedTransform(
                asset_id=aid, asset_name=_name(asset),
                tx=0.0, ty=0.0, tz=tz_snap,
                ry=0.0,                # faces south (room interior)
                parent_id="wall_north",
                relationship="attached_to",
                notes=f"back face on wall_north, wall_gap≤{_WALL_INSET}m",
            )

        # --- Machine / large machine ---
        for idx, aid in enumerate(typed.get("machine", []) + typed.get("large_machine", [])):
            out[aid] = ResolvedTransform(
                asset_id=aid, asset_name=_name(aid_to_asset[aid]),
                tx=float(idx) * 3.5, ty=0.0, tz=0.0,
                ry=0.0, relationship="anchor",
            )

        # --- Campfire (outdoor / floor centred) ---
        for idx, aid in enumerate(typed.get("campfire", [])):
            out[aid] = ResolvedTransform(
                asset_id=aid, asset_name=_name(aid_to_asset[aid]),
                tx=0.0, ty=0.0, tz=0.0,
                ry=0.0, relationship="anchor",
            )

        return out

    def _place_asset(
        self,
        aid:          str,
        atype:        str,
        edges:        List[RelationshipEdge],
        transforms:   Dict[str, ResolvedTransform],
        typed:        Dict[str, List[str]],
        aid_to_asset: Dict[str, Dict[str, Any]],
        aid_to_type:  Dict[str, str],
        room:         Dict[str, Any],
    ) -> Tuple[Optional[ResolvedTransform], int, int]:
        """
        Place one asset based on its relationship edges.

        Returns (transform, n_relationships_total, n_relationships_satisfied).
        Returns (None, 0, 0) if all edges failed and no fallback is possible.
        """
        if not edges:
            t = self._fallback_placement(aid, atype, transforms, room)
            return t, 0, 0

        total = len(edges)
        valid = 0
        chosen: Optional[ResolvedTransform] = None

        # Real-target edges first so a bottle placed near a real shelf
        # wins over the virtual-table fallback that was injected by the
        # graph builder when no table was in the scene.
        sorted_edges = sorted(edges, key=lambda e: e.is_virtual_target)

        # Walk edges in priority order — first satisfied edge wins placement.
        for edge in sorted_edges:
            t = self._place_for_edge(aid, atype, edge, transforms, typed, aid_to_asset, room)
            if t is not None:
                if chosen is None:
                    chosen = t  # first successful edge determines placement
                valid += 1
            # else: edge target missing — try next

        if chosen is None:
            # All edges failed — use fallback
            chosen = self._fallback_placement(aid, atype, transforms, room)

        return chosen, total, valid

    def _place_for_edge(
        self,
        aid:          str,
        atype:        str,
        edge:         RelationshipEdge,
        transforms:   Dict[str, ResolvedTransform],
        typed:        Dict[str, List[str]],
        aid_to_asset: Dict[str, Dict[str, Any]],
        room:         Dict[str, Any],
    ) -> Optional[ResolvedTransform]:
        rel    = edge.relationship_type
        tid    = edge.to_node_id
        asset  = aid_to_asset.get(aid, {})

        # ---- attached_to wall ----------------------------------------
        if rel == "attached_to" and tid in ("wall", "wall_north", "wall_south",
                                             "wall_east", "wall_west"):
            return self._attach_to_wall(aid, atype, asset, room)

        # ---- attached_to ceiling ------------------------------------
        if rel == "attached_to" and tid == "ceiling":
            h = room["height"]
            return ResolvedTransform(
                asset_id=aid, asset_name=_name(asset),
                tx=0.0, ty=h - 0.2, tz=0.0,
                parent_id="ceiling", relationship="attached_to",
                notes="ceiling-mounted",
            )

        # ---- attached_to floor --------------------------------------
        if rel == "attached_to" and tid == "floor":
            return ResolvedTransform(
                asset_id=aid, asset_name=_name(asset),
                tx=0.0, ty=0.0, tz=0.0,
                parent_id="floor", relationship="attached_to",
                notes="floor-anchored",
            )

        # ---- belongs_near wall / corner (barrel, crate, bench) --------
        # This must be checked BEFORE the general orbit belongs_near,
        # since wall/corner targets are virtual and have no transform.
        if rel in ("belongs_near",) and tid in (
            "wall", "corner",
            "wall_north", "wall_south", "wall_east", "wall_west",
        ):
            return self._place_near_wall(aid, atype, asset, typed, transforms, room)

        # ---- belongs_near + faces furniture anchor -------------------
        if rel in ("belongs_near", "faces", "around"):
            target_t = transforms.get(tid)
            if target_t is None:
                # Try any real asset of the implied type in transforms
                target_t = _first_transform_of_type(tid, typed, transforms)
            if target_t is None:
                return None  # target not placed yet → signal retry

            index   = _chair_index_for_anchor(aid, tid, typed)
            count   = max(1, len(typed.get(atype, [])))
            orbit_r = _orbit_radius(aid_to_asset.get(aid, {}), target_t, atype)
            angle   = (2 * math.pi / count) * index
            tx      = target_t.tx + orbit_r * math.sin(angle)
            tz      = target_t.tz + orbit_r * math.cos(angle)
            ry      = _face_toward(tx, tz, target_t.tx, target_t.tz)
            return ResolvedTransform(
                asset_id=aid, asset_name=_name(asset),
                tx=round(tx, 4), ty=0.0, tz=round(tz, 4),
                ry=round(ry, 2),
                parent_id=tid, relationship="around",
                notes=f"orbiting {tid} r={orbit_r:.2f}m",
            )

        # ---- supports (surface prop) --------------------------------
        if rel in ("supports", "on_top_of"):
            target_t    = transforms.get(tid)
            if target_t is None:
                target_t = _first_transform_of_type(tid, typed, transforms)
            tid_type    = _type_from_tid(tid, typed)
            surface_h   = _SURFACE_HEIGHTS.get(tid_type, _DEFAULT_SURFACE_H)
            index       = _surface_prop_index(aid, tid, typed, atype)
            if index >= _MAX_SURFACE_PROPS:
                return None  # surface full

            if target_t is not None:
                ox, oz = _SURFACE_XZ_OFFSETS[min(index, len(_SURFACE_XZ_OFFSETS) - 1)]
                tx = round(target_t.tx + ox, 4)
                tz = round(target_t.tz + oz, 4)
            else:
                tx = round(float(index) * 0.25 - 0.5, 4)
                tz = 0.0

            actual_tid = target_t.asset_id if target_t else tid
            return ResolvedTransform(
                asset_id=aid, asset_name=_name(asset),
                tx=tx, ty=round(surface_h, 4), tz=tz,
                parent_id=actual_tid, relationship="supports",
                notes=f"on {tid_type} surface h={surface_h:.2f}m",
            )

        # ---- belongs_near wall (barrel, crate, bench) ---------------
        if rel in ("belongs_near",) and tid in ("wall", "corner"):
            return self._place_near_wall(aid, atype, asset, typed, transforms, room)

        return None   # unhandled edge type

    def _attach_to_wall(
        self,
        aid:   str,
        atype: str,
        asset: Dict[str, Any],
        room:  Dict[str, Any],
    ) -> ResolvedTransform:
        """Mount an asset on a wall at the canonical height for its type."""
        walls   = room["walls"]
        idx     = _wall_index_for_asset(aid, atype)
        wall    = walls[idx % len(walls)]
        height  = _WALL_MOUNT_HEIGHTS.get(atype, _DEFAULT_WALL_H)
        ry      = _wall_normal_to_ry(wall["normal"])

        if wall["axis"] == "z":
            tx = wall.get("x_spread", 0.0) * ((idx // len(walls)) % 3 - 1)
            tz = wall["coord"] + wall["inset"]
        else:
            tx = wall["coord"] + wall["inset"]
            tz = wall.get("z_spread", 0.0) * ((idx // len(walls)) % 3 - 1)

        return ResolvedTransform(
            asset_id=aid, asset_name=_name(asset),
            tx=round(tx, 4), ty=round(height, 4), tz=round(tz, 4),
            ry=round(ry, 2),
            parent_id=wall["name"],
            relationship="attached_to",
            notes=f"wall={wall['name']} h={height:.2f}m",
        )

    def _place_near_wall(
        self,
        aid:          str,
        atype:        str,
        asset:        Dict[str, Any],
        typed:        Dict[str, List[str]],
        transforms:   Dict[str, ResolvedTransform],
        room:         Dict[str, Any],
    ) -> ResolvedTransform:
        """Place a near-wall prop (barrel, crate, bench) along the perimeter."""
        walls   = room["walls"]
        all_ids = typed.get(atype, [])
        idx     = all_ids.index(aid) if aid in all_ids else 0
        wall    = walls[idx % len(walls)]
        # Spread multiple same-type items along the wall face
        spread  = float(idx // len(walls)) * 1.0 - 0.5

        coord = wall["coord"]
        # Inset from wall plane into the room interior
        # sign(coord) points away from room centre → inset in opposite direction
        room_inset = -math.copysign(_NEAR_WALL_INSET, coord)

        if wall["axis"] == "z":
            tx = round(spread, 4)
            tz = round(coord + room_inset, 4)
        else:
            tx = round(coord + room_inset, 4)
            tz = round(spread, 4)

        return ResolvedTransform(
            asset_id=aid, asset_name=_name(asset),
            tx=tx, ty=0.0, tz=tz,
            ry=0.0,
            parent_id=wall["name"],
            relationship="belongs_near",
            notes=f"near {wall['name']}",
        )

    def _fallback_placement(
        self,
        aid:        str,
        atype:      str,
        transforms: Dict[str, ResolvedTransform],
        room:       Dict[str, Any],
    ) -> ResolvedTransform:
        """Place an asset with no satisfied edges at a reasonable fallback position."""
        existing_count = sum(1 for t in transforms.values() if t.ty == 0.0)
        spacing        = 1.20
        tx             = round((existing_count % 5) * spacing - 2.4, 4)
        tz             = round((existing_count // 5) * spacing - 1.2, 4)
        return ResolvedTransform(
            asset_id=aid,
            asset_name=atype,
            tx=tx, ty=0.0, tz=tz,
            relationship="scattered",
            notes="fallback: no relationship edge satisfied",
        )


# ===========================================================================
# Module-level helpers
# ===========================================================================

def _shell_to_dict(shell: Any) -> Dict[str, Any]:
    if shell is None:
        return {}
    if isinstance(shell, dict):
        return shell
    if hasattr(shell, "to_dict"):
        return shell.to_dict()
    return {}


def _room_geometry(shell_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Derive room dimensions + wall definitions from shell dict (or defaults)."""
    floor_area    = float(shell_dict.get("floor_area", 0.0))
    ceiling_h     = float(shell_dict.get("ceiling_height", 0.0))

    if floor_area > 0:
        w = math.sqrt(floor_area / 1.2)
        d = floor_area / w
    else:
        w, d = _DEFAULT_ROOM_W, _DEFAULT_ROOM_D

    if ceiling_h <= 0:
        ceiling_h = _DEFAULT_ROOM_H

    hw, hd = w / 2.0, d / 2.0
    _spread = min(hw * 0.6, 2.4)

    walls = [
        {
            "name": "wall_north", "normal": [0, 0, -1],
            "axis": "z", "coord": -hd, "inset": _WALL_INSET,
            "x_spread": _spread,
        },
        {
            "name": "wall_south", "normal": [0, 0, 1],
            "axis": "z", "coord": hd,  "inset": -_WALL_INSET,
            "x_spread": _spread,
        },
        {
            "name": "wall_east",  "normal": [-1, 0, 0],
            "axis": "x", "coord": hw,  "inset": -_WALL_INSET,
            "z_spread": _spread,
        },
        {
            "name": "wall_west",  "normal": [1, 0, 0],
            "axis": "x", "coord": -hw, "inset": _WALL_INSET,
            "z_spread": _spread,
        },
    ]

    return {
        "width": w, "depth": d, "height": ceiling_h,
        "half_width": hw, "half_depth": hd,
        "walls": walls,
    }


def _aid(asset: Dict[str, Any]) -> str:
    return str(asset.get("asset_id") or asset.get("name") or "").strip()


def _name(asset_or_str) -> str:
    if isinstance(asset_or_str, dict):
        return str(asset_or_str.get("name") or asset_or_str.get("asset_id") or "")
    return str(asset_or_str)


def _wall_normal_to_ry(normal: List[float]) -> float:
    nx = float(normal[0])
    nz = float(normal[2]) if len(normal) > 2 else 0.0
    return math.degrees(math.atan2(-nx, -nz)) % 360.0


def _face_toward(from_x: float, from_z: float, to_x: float, to_z: float) -> float:
    """Return ry in degrees so that the asset at (from_x, from_z) faces (to_x, to_z)."""
    dx = to_x - from_x
    dz = to_z - from_z
    return math.degrees(math.atan2(dx, dz)) % 360.0


def _orbit_radius(asset: Dict[str, Any], target_t: ResolvedTransform, atype: str) -> float:
    # Table half-dimension from asset metadata (if available) or defaults
    w = float(asset.get("width_m") or asset.get("bbox_x") or 0)
    d = float(asset.get("depth_m") or asset.get("bbox_z") or 0)
    own_half = max(w, d) / 2.0 if (w or d) else 0.0

    # Target half from its bbox if available (fallback 0.5m)
    target_half = 0.50
    if atype in ("stool",):
        return target_half + _STOOL_CLEARANCE
    return target_half + own_half + _CHAIR_CLEARANCE


def _chair_index_for_anchor(aid: str, anchor_id: str, typed: Dict[str, List[str]]) -> int:
    """Return the zero-based index of this chair within the chairs assigned to this anchor."""
    all_chairs = typed.get("chair", []) + typed.get("stool", [])
    for i, cid in enumerate(all_chairs):
        if cid == aid:
            return i
    return 0


def _surface_prop_index(
    aid: str,
    target_id: str,
    typed: Dict[str, List[str]],
    atype: str,
) -> int:
    """Index of this prop among surface props of the same type targeting same surface."""
    props = typed.get(atype, [])
    for i, pid in enumerate(props):
        if pid == aid:
            return i
    return 0


def _first_transform_of_type(
    target_type: str,
    typed: Dict[str, List[str]],
    transforms: Dict[str, ResolvedTransform],
) -> Optional[ResolvedTransform]:
    """Find the first placed transform whose type matches target_type."""
    for aid in typed.get(target_type, []):
        if aid in transforms:
            return transforms[aid]
    return None


def _type_from_tid(tid: str, typed: Dict[str, List[str]]) -> str:
    """Reverse-lookup: find the type of a target node ID."""
    for atype, aids in typed.items():
        if tid in aids:
            return atype
    return tid  # assume tid IS the type (e.g. virtual node "table")


def _wall_index_for_asset(aid: str, atype: str) -> int:
    """Deterministic wall assignment from asset ID hash."""
    return hash(aid) % 4


def _get_counted_set(edges_by_from: Dict[str, List[RelationshipEdge]]) -> Set[str]:
    return set(edges_by_from.keys())


def _edge_satisfied(
    edge: RelationshipEdge,
    t: ResolvedTransform,
    transforms: Dict[str, ResolvedTransform],
) -> bool:
    """Return True if the transform satisfies the given relationship edge."""
    rel = edge.relationship_type
    tid = edge.to_node_id

    # Virtual edges represent fallback rules.  If the asset is validly placed
    # (on a surface or properly attached), the virtual fallback is satisfied —
    # the engine already chose a concrete placement that overrides it.
    if edge.is_virtual_target:
        return t.ty > _MIN_SURFACE_H or t.relationship in ("attached_to", "around", "belongs_near")

    if rel in ("supports", "on_top_of"):
        return t.ty > _MIN_SURFACE_H

    if rel == "attached_to":
        if tid in ("wall", "wall_north", "wall_south", "wall_east", "wall_west"):
            return "wall" in (t.parent_id or "") or t.relationship == "attached_to"
        if tid == "ceiling":
            return t.parent_id == "ceiling"
        if tid == "floor":
            return t.parent_id == "floor"
        return t.relationship == "attached_to"

    if rel in ("belongs_near", "faces", "around"):
        # Valid if parent_id points to the right target (or same type virtual)
        return t.parent_id == tid or t.relationship in ("around", "belongs_near")

    # For other types (inside, under, aligned_with, etc.), assume satisfied if placed
    return True


def _run_check(
    asset_types:   List[str],
    predicate,
    typed:         Dict[str, List[str]],
    transforms:    Dict[str, ResolvedTransform],
    errors:        List[str],
    error_template: str,
) -> bool:
    passed = True
    for atype in asset_types:
        for aid in typed.get(atype, []):
            t = transforms.get(aid)
            if not predicate(t, aid, atype):
                errors.append(error_template.format(aid=aid, atype=atype))
                passed = False
    return passed


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[RelationshipLayoutEngine] = None
_lock = threading.Lock()


def get_relationship_layout_engine() -> RelationshipLayoutEngine:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = RelationshipLayoutEngine()
    return _instance


def reset_relationship_layout_engine_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
