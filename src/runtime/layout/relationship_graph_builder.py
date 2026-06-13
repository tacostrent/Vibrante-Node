"""
relationship_graph_builder.py — Tier 14.4.1 Relationship Graph Builder
=======================================================================
Builds a semantic relationship graph from a list of assets BEFORE any
layout, realization, collision, or decoration phase.

Execution order:
  Asset Classification
  → Relationship Graph Builder   ← this module
  → Layout (SemanticLayoutEngine)
  → Realization (LayoutRealizationEngine)
  → Collision (CollisionSolver)
  → Constraint (SceneConstraintSolver)
  → Validation (SceneRealityValidation)

Data model:
  RelationshipNode  — one node per asset (or virtual structural anchor)
  RelationshipEdge  — directed semantic edge: from_node → to_node
  RelationshipGraph — full directed graph (nodes + edges, thread-safe)

Supported relationship types:
  attached_to   — child physically mounted/attached to host  (poster→wall)
  supports      — child is placed on host surface            (bottle→table)
  belongs_near  — child clusters near host                   (chair→table)
  faces         — child is oriented toward host              (chair→table)
  inside        — child is spatially inside host
  under         — child placed beneath host
  on_top_of     — child resting on top of host surface
  surrounded_by — child contextually surrounded by host
  aligned_with  — child aligned along host axis

Asset rules (deterministic, applied before any layout engine sees the assets):
  fireplace   → attached_to wall
  door        → attached_to wall
  window      → attached_to wall
  beam        → attached_to ceiling
  column      → attached_to floor
  chair       → belongs_near table, faces table
  stool       → belongs_near bar_counter
  bottle      → supports table, supports shelf, supports fireplace_mantel
  cup         → supports table
  plate       → supports table
  lantern     → supports table, attached_to wall
  barrel      → belongs_near wall
  crate       → belongs_near wall

Status:
  RELATIONSHIP_GRAPH_STATUS_PASS = "PASS"
  RELATIONSHIP_GRAPH_STATUS_FAIL = "FAIL"

Validation (FAIL if violated after graph is built):
  - Every chair must have at least one relationship pointing to a table
    (belongs_near | faces | around)
  - Every fireplace must have at least one attached_to wall relationship
  - Every bottle must have at least one support relationship
    (supports | on_top_of) pointing to table / shelf / fireplace_mantel /
    bar_counter (real asset or virtual node)

Runtime state:
  The last built graph is stored on the builder singleton as `current_graph`.
  Downstream engines (FurnitureClusterBuilder, SemanticLayoutEngine,
  StructuralElementPlacer, DecorationLayoutEngine) can retrieve it via:
      get_relationship_graph_builder().current_graph

Public API:
  RelationshipNode
  RelationshipEdge
  RelationshipGraph
  GraphBuildResult
  RelationshipGraphBuilder
  GRAPH_RELATIONSHIP_TYPES
  RELATIONSHIP_GRAPH_STATUS_PASS
  RELATIONSHIP_GRAPH_STATUS_FAIL
  get_relationship_graph_builder()
  reset_relationship_graph_builder_for_tests()
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple

from src.runtime.layout.affordance_engine import get_affordance_engine

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GRAPH_RELATIONSHIP_TYPES: FrozenSet[str] = frozenset({
    "attached_to",
    "supports",
    "belongs_near",
    "faces",
    "inside",
    "under",
    "on_top_of",
    "surrounded_by",
    "aligned_with",
})

RELATIONSHIP_GRAPH_STATUS_PASS = "PASS"
RELATIONSHIP_GRAPH_STATUS_FAIL = "FAIL"

# Virtual structural nodes injected into every graph so that assets whose
# required target type is absent from the scene can still form relationships.
# They carry is_virtual=True and never appear in assets_with_relationships.
_VIRTUAL_NODE_TYPES: Tuple[str, ...] = (
    "wall", "ceiling", "floor", "corner",
    "fireplace_mantel", "bar_counter",
    "table", "shelf", "workbench", "mantle",
)

# Structural virtual targets that are treated as always-available, so
# secondary rules whose target is one of these always fire (not just primary).
_ALWAYS_PRESENT_TARGETS: FrozenSet[str] = frozenset({
    "wall", "ceiling", "floor", "corner",
})

# ---------------------------------------------------------------------------
# Per-type relationship rules
# Each entry: (relationship_type, target_type)
# Primary rule = first entry; secondary rules only fire when a real asset of
# target_type is present in the scene.
# ---------------------------------------------------------------------------
_ASSET_TYPE_RULES: Dict[str, List[Tuple[str, str]]] = {
    # Structural / architectural
    "fireplace":        [("attached_to", "wall")],
    "door":             [("attached_to", "wall")],
    "doorway":          [("attached_to", "wall")],
    "door_frame":       [("attached_to", "wall")],
    "archway":          [("attached_to", "wall")],
    "window":           [("attached_to", "wall")],
    "window_frame":     [("attached_to", "wall")],
    "beam":             [("attached_to", "ceiling")],
    "support_beam":     [("attached_to", "ceiling")],
    "column":           [("attached_to", "floor")],
    # Seating
    "chair":            [("belongs_near", "table"), ("faces", "table")],
    "stool":            [("belongs_near", "bar_counter")],
    # Surface props
    "bottle":           [("supports", "table"), ("supports", "shelf"), ("supports", "fireplace_mantel")],
    "whiskey_bottle":   [("supports", "table"), ("supports", "bar_counter"), ("supports", "shelf")],
    "beer_mug":         [("supports", "table"), ("supports", "bar_counter")],
    "cup":              [("supports", "table")],
    "mug":              [("supports", "table"), ("supports", "bar_counter")],
    "glass":            [("supports", "table"), ("supports", "bar_counter")],
    "plate":            [("supports", "table")],
    "bowl":             [("supports", "table"), ("supports", "bar_counter")],
    "book":             [("supports", "shelf"), ("supports", "table")],
    "candle":           [("supports", "table"), ("supports", "mantle")],
    "vase":             [("supports", "shelf"), ("supports", "table")],
    "tool":             [("supports", "workbench")],
    # Wall-mounted
    "lantern":          [("supports", "table"), ("attached_to", "wall")],
    "torch":            [("attached_to", "wall")],
    "sconce":           [("attached_to", "wall")],
    "poster":           [("attached_to", "wall")],
    "painting":         [("attached_to", "wall")],
    "wanted_poster":    [("attached_to", "wall")],
    "sign":             [("attached_to", "wall")],
    "banner":           [("attached_to", "wall")],
    "clock":            [("attached_to", "wall")],
    "mirror":           [("attached_to", "wall")],
    # Near-wall / corner props
    "bench":            [("belongs_near", "wall")],
    "barrel":           [("belongs_near", "wall")],
    "crate":            [("belongs_near", "wall")],
    "bucket":           [("belongs_near", "wall")],
    "oil_drum":         [("belongs_near", "wall")],
    "hay_bale":         [("belongs_near", "corner")],
    "plant":            [("belongs_near", "corner")],
}

# ---------------------------------------------------------------------------
# Validation rules
# (asset_type_to_check, acceptable_relationship_types, acceptable_target_types)
# FAIL if any asset of asset_type_to_check has no matching edge.
# ---------------------------------------------------------------------------
_VALIDATION_RULES: List[Tuple[str, List[str], List[str]]] = [
    ("chair",     ["belongs_near", "faces", "around"], ["table"]),
    ("fireplace", ["attached_to"],                      ["wall"]),
    ("bottle",    ["supports", "on_top_of"],            ["table", "shelf", "fireplace_mantel", "bar_counter"]),
]

# Target types that always warrant a warning when absent from the real scene.
_WARN_ABSENT_TARGETS: FrozenSet[str] = frozenset({"table", "wall", "ceiling", "floor"})


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class RelationshipNode:
    """One node in the pre-layout relationship graph."""
    node_id:    str
    asset_type: str
    asset_name: str
    is_virtual: bool = False
    metadata:   Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "node_id":    self.node_id,
            "asset_type": self.asset_type,
            "asset_name": self.asset_name,
            "is_virtual": self.is_virtual,
            "metadata":   dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "RelationshipNode":
        return cls(
            node_id=d.get("node_id", ""),
            asset_type=d.get("asset_type", ""),
            asset_name=d.get("asset_name", ""),
            is_virtual=bool(d.get("is_virtual", False)),
            metadata=dict(d.get("metadata", {})),
        )


@dataclass
class RelationshipEdge:
    """One directed semantic edge in the pre-layout relationship graph."""
    from_node_id:      str
    to_node_id:        str
    relationship_type: str
    confidence:        float = 1.0
    is_virtual_target: bool  = False
    metadata:          Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "from_node_id":      self.from_node_id,
            "to_node_id":        self.to_node_id,
            "relationship_type": self.relationship_type,
            "confidence":        round(self.confidence, 3),
            "is_virtual_target": self.is_virtual_target,
            "metadata":          dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "RelationshipEdge":
        return cls(
            from_node_id=d.get("from_node_id", ""),
            to_node_id=d.get("to_node_id", ""),
            relationship_type=d.get("relationship_type", ""),
            confidence=float(d.get("confidence", 1.0)),
            is_virtual_target=bool(d.get("is_virtual_target", False)),
            metadata=dict(d.get("metadata", {})),
        )


class RelationshipGraph:
    """
    Directed pre-layout semantic relationship graph.

    Distinct from AssetRelationshipGraph (§46) in that it:
      - Tracks nodes explicitly, including virtual structural anchors.
      - Expands relationship vocabulary (belongs_near, faces, on_top_of…).
      - Is built BEFORE any layout engine runs.
      - Is stored in runtime state and passed to downstream engines.

    Thread-safe. All public methods never raise.
    """

    def __init__(self) -> None:
        self._lock   = threading.Lock()
        self._nodes:       Dict[str, RelationshipNode] = {}
        self._edges:       List[RelationshipEdge]      = []
        self._edges_from:  Dict[str, List[int]]        = {}
        self._edges_to:    Dict[str, List[int]]        = {}

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add_node(self, node: RelationshipNode) -> None:
        with self._lock:
            self._nodes[node.node_id] = node

    def add_edge(self, edge: RelationshipEdge) -> None:
        if edge.relationship_type not in GRAPH_RELATIONSHIP_TYPES:
            edge = RelationshipEdge(
                from_node_id=edge.from_node_id,
                to_node_id=edge.to_node_id,
                relationship_type="belongs_near",
                confidence=round(edge.confidence * 0.5, 3),
                is_virtual_target=edge.is_virtual_target,
                metadata=edge.metadata,
            )
        with self._lock:
            idx = len(self._edges)
            self._edges.append(edge)
            self._edges_from.setdefault(edge.from_node_id, []).append(idx)
            self._edges_to.setdefault(edge.to_node_id, []).append(idx)

    def clear(self) -> None:
        with self._lock:
            self._nodes.clear()
            self._edges.clear()
            self._edges_from.clear()
            self._edges_to.clear()

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_node(self, node_id: str) -> Optional[RelationshipNode]:
        with self._lock:
            return self._nodes.get(node_id)

    def get_edges_from(self, node_id: str) -> List[RelationshipEdge]:
        with self._lock:
            return [self._edges[i] for i in self._edges_from.get(node_id, [])]

    def get_edges_to(self, node_id: str) -> List[RelationshipEdge]:
        with self._lock:
            return [self._edges[i] for i in self._edges_to.get(node_id, [])]

    def get_all_nodes(self) -> List[RelationshipNode]:
        with self._lock:
            return list(self._nodes.values())

    def get_real_nodes(self) -> List[RelationshipNode]:
        with self._lock:
            return [n for n in self._nodes.values() if not n.is_virtual]

    def get_all_edges(self) -> List[RelationshipEdge]:
        with self._lock:
            return list(self._edges)

    def edges_of_type(self, relationship_type: str) -> List[RelationshipEdge]:
        with self._lock:
            return [e for e in self._edges if e.relationship_type == relationship_type]

    @property
    def node_count(self) -> int:
        with self._lock:
            return len(self._nodes)

    @property
    def edge_count(self) -> int:
        with self._lock:
            return len(self._edges)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        with self._lock:
            return {
                "nodes":      [n.to_dict() for n in self._nodes.values()],
                "edges":      [e.to_dict() for e in self._edges],
                "node_count": len(self._nodes),
                "edge_count": len(self._edges),
            }

    @classmethod
    def from_dict(cls, d: dict) -> "RelationshipGraph":
        g = cls()
        for nd in d.get("nodes", []):
            g.add_node(RelationshipNode.from_dict(nd))
        for ed in d.get("edges", []):
            g.add_edge(RelationshipEdge.from_dict(ed))
        return g


# ---------------------------------------------------------------------------
# Build result
# ---------------------------------------------------------------------------

@dataclass
class GraphBuildResult:
    """Output of RelationshipGraphBuilder.build_graph()."""
    relationship_graph:         RelationshipGraph = field(default_factory=RelationshipGraph)
    relationship_count:         int               = 0
    assets_with_relationships:  List[str]         = field(default_factory=list)
    orphan_assets:              List[str]         = field(default_factory=list)
    status:                     str               = RELATIONSHIP_GRAPH_STATUS_PASS
    validation_errors:          List[str]         = field(default_factory=list)
    warnings:                   List[str]         = field(default_factory=list)
    ok:                         bool              = True
    errors:                     List[str]         = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "relationship_graph":        self.relationship_graph.to_dict(),
            "relationship_count":        self.relationship_count,
            "assets_with_relationships": list(self.assets_with_relationships),
            "orphan_assets":             list(self.orphan_assets),
            "status":                    self.status,
            "validation_errors":         list(self.validation_errors),
            "warnings":                  list(self.warnings),
            "ok":                        self.ok,
            "errors":                    list(self.errors),
        }


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

class RelationshipGraphBuilder:
    """
    Analyses a list of asset dicts and builds a typed RelationshipGraph.

    Rules are applied deterministically:
      1. Build RelationshipNode for every real asset.
      2. Inject virtual structural nodes (wall, ceiling, floor, …).
      3. For each asset, apply _ASSET_TYPE_RULES:
           - Primary rule  → edge to first real target if present,
                             else edge to virtual target node.
           - Secondary rules → edge to each real target found; skip if absent
                               (avoids cluttering the graph with virtual multi-edges).
      4. Affordance-based fallback for types not covered by _ASSET_TYPE_RULES.
      5. Validate required relationships.
      6. Detect orphan assets (no edges at all).
      7. Return GraphBuildResult.

    The last built graph is stored as `current_graph` so downstream engines
    can retrieve it without re-running the pipeline.
    """

    def __init__(self) -> None:
        self._lock          = threading.Lock()
        self._current_graph: Optional[RelationshipGraph] = None

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    @property
    def current_graph(self) -> Optional[RelationshipGraph]:
        """The graph from the most recent build_graph() call (or None)."""
        with self._lock:
            return self._current_graph

    def build_graph(
        self,
        assets:      List[Dict[str, Any]],
        environment: str = "",
    ) -> GraphBuildResult:
        """
        Build the semantic relationship graph for an asset list.

        Args:
            assets:      list of asset metadata dicts
            environment: environment name (used in node metadata only)

        Returns:
            GraphBuildResult — never raises.
        """
        try:
            result = self._build(assets, environment)
        except Exception as exc:
            result = GraphBuildResult(ok=False)
            result.errors.append(f"RelationshipGraphBuilder.build_graph failed: {exc}")
            result.status = RELATIONSHIP_GRAPH_STATUS_FAIL

        with self._lock:
            self._current_graph = result.relationship_graph

        return result

    # ------------------------------------------------------------------
    # Internal pipeline
    # ------------------------------------------------------------------

    def _build(
        self,
        assets:      List[Dict[str, Any]],
        environment: str,
    ) -> GraphBuildResult:
        eng    = get_affordance_engine()
        graph  = RelationshipGraph()
        result = GraphBuildResult(relationship_graph=graph)

        # ---- Step 1: Real asset nodes + type index -----------------------
        # typed_assets[type] = ordered list of assets of that type
        typed_assets:     Dict[str, List[Dict[str, Any]]] = {}
        asset_id_to_type: Dict[str, str]                  = {}

        for asset in assets:
            aid  = _asset_id(asset)
            if not aid:
                continue
            atype = eng.infer_type(asset)
            aname = str(asset.get("name") or aid)

            graph.add_node(RelationshipNode(
                node_id=aid,
                asset_type=atype,
                asset_name=aname,
                is_virtual=False,
                metadata={"environment": environment},
            ))
            asset_id_to_type[aid] = atype
            typed_assets.setdefault(atype, []).append(asset)

        # ---- Step 2: Virtual structural anchor nodes ---------------------
        for vtype in _VIRTUAL_NODE_TYPES:
            if vtype not in typed_assets:
                graph.add_node(RelationshipNode(
                    node_id=vtype,
                    asset_type=vtype,
                    asset_name=f"[virtual] {vtype}",
                    is_virtual=True,
                ))

        # ---- Step 3: Apply type rules ------------------------------------
        assets_with_rel: Set[str] = set()

        for asset in assets:
            aid   = _asset_id(asset)
            if not aid:
                continue
            atype = asset_id_to_type.get(aid, eng.infer_type(asset))
            rules = _ASSET_TYPE_RULES.get(atype, [])

            # ---- Step 4: Affordance-based fallback for unknown types -----
            if not rules:
                rules = self._affordance_fallback_rules(atype, eng)

            if not rules:
                continue  # truly unknown type — becomes orphan

            primary_done = False
            for idx_rule, (rel_type, target_type) in enumerate(rules):
                is_primary     = (idx_rule == 0)
                always_present = target_type in _ALWAYS_PRESENT_TARGETS
                real_targets   = [
                    a for a in typed_assets.get(target_type, [])
                    if _asset_id(a) != aid
                ]

                if real_targets:
                    for tgt in real_targets:
                        tid = _asset_id(tgt)
                        if not tid:
                            continue
                        graph.add_edge(RelationshipEdge(
                            from_node_id=aid,
                            to_node_id=tid,
                            relationship_type=rel_type,
                            confidence=1.0,
                            is_virtual_target=False,
                        ))
                        assets_with_rel.add(aid)
                        assets_with_rel.add(tid)
                    primary_done = True

                elif is_primary or always_present:
                    # Primary rules always fire (virtual fallback).
                    # Secondary rules also fire when target is a structural
                    # virtual always-present in every environment (wall / ceiling
                    # / floor / corner) — these are guaranteed to exist.
                    vnode_id = target_type
                    if graph.get_node(vnode_id) is None:
                        graph.add_node(RelationshipNode(
                            node_id=vnode_id,
                            asset_type=target_type,
                            asset_name=f"[virtual] {target_type}",
                            is_virtual=True,
                        ))
                    graph.add_edge(RelationshipEdge(
                        from_node_id=aid,
                        to_node_id=vnode_id,
                        relationship_type=rel_type,
                        confidence=0.7,
                        is_virtual_target=True,
                    ))
                    assets_with_rel.add(aid)
                    if is_primary:
                        primary_done = True

                    if target_type in _WARN_ABSENT_TARGETS and not real_targets:
                        result.warnings.append(
                            f"'{aid}' ({atype}): no real '{target_type}' in scene — "
                            f"virtual node used for '{rel_type}' edge"
                        )

        # ---- Step 5: Orphan detection ------------------------------------
        real_ids = [_asset_id(a) for a in assets if _asset_id(a)]
        orphans  = sorted(rid for rid in real_ids if rid not in assets_with_rel)

        # ---- Step 6: Validation ------------------------------------------
        validation_errors: List[str] = []
        for check_type, acceptable_rels, acceptable_targets in _VALIDATION_RULES:
            if check_type not in typed_assets:
                continue

            # Build the full set of valid target node IDs (real + virtual)
            valid_target_ids: Set[str] = set(acceptable_targets)
            for ttype in acceptable_targets:
                for ta in typed_assets.get(ttype, []):
                    tid = _asset_id(ta)
                    if tid:
                        valid_target_ids.add(tid)

            for asset in typed_assets[check_type]:
                aid = _asset_id(asset)
                if not aid:
                    continue
                edges_out = graph.get_edges_from(aid)
                satisfied = any(
                    e.relationship_type in acceptable_rels
                    and e.to_node_id in valid_target_ids
                    for e in edges_out
                )
                if not satisfied:
                    validation_errors.append(
                        f"'{aid}' ({check_type}) has no {acceptable_rels} edge "
                        f"pointing to {acceptable_targets}"
                    )

        # ---- Step 7: Assemble result -------------------------------------
        result.relationship_count        = graph.edge_count
        result.assets_with_relationships = sorted(assets_with_rel - set(_VIRTUAL_NODE_TYPES))
        result.orphan_assets             = orphans
        result.validation_errors         = validation_errors
        result.status = (
            RELATIONSHIP_GRAPH_STATUS_FAIL if validation_errors
            else RELATIONSHIP_GRAPH_STATUS_PASS
        )
        result.ok = not bool(validation_errors)

        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _affordance_fallback_rules(
        asset_type: str,
        eng,
    ) -> List[Tuple[str, str]]:
        """
        Derive relationship rules from AffordanceEngine for types not in
        _ASSET_TYPE_RULES.  Returns an empty list for unknown types.
        """
        aff = eng.get_affordances(asset_type)
        if aff.is_wall_attachable:
            return [("attached_to", "wall")]
        if aff.is_ceiling_hangable:
            return [("attached_to", "ceiling")]
        if aff.is_against_wall:
            return [("belongs_near", "wall")]
        if aff.is_corner_placed:
            return [("belongs_near", "corner")]
        if aff.placement_mode == "around_anchor":
            # Find the most common anchor this type orbits.
            # Scan AROUND_SUPPORTS via affordance engine surface.
            for anchor_type in (
                "table", "bar_counter", "fireplace", "campfire",
                "throne", "altar", "workbench",
            ):
                around_kids = eng.get_around_children(anchor_type)
                if asset_type in around_kids:
                    return [("belongs_near", anchor_type), ("faces", anchor_type)]
        if aff.placement_mode == "on_surface":
            return [("supports", "table")]
        return []


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[RelationshipGraphBuilder] = None
_lock = threading.Lock()


def get_relationship_graph_builder() -> RelationshipGraphBuilder:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = RelationshipGraphBuilder()
    return _instance


def reset_relationship_graph_builder_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _asset_id(asset: Dict[str, Any]) -> str:
    """Return a stable string ID for an asset dict."""
    return str(asset.get("asset_id") or asset.get("name") or "").strip()
