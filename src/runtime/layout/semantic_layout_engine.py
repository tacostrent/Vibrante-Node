"""
semantic_layout_engine.py — §46 Semantic Furniture Layout Engine
================================================================
Main orchestrator for the Tier 9.8 semantic furniture layout pipeline.

Pipeline stages:
  1. Anchor Placement    — hero focal assets placed first
  2. Relationship Graph  — semantic edges built between all assets
  3. Furniture Clusters  — related assets grouped (table + chairs + props)
  4. Surface Placement   — small props placed on host surfaces
  5. Wall Attachment     — poster/lantern/sign mounted on walls
  6. Decoration Layout   — contextual dressing per environment
  7. Layout Review       — quality evaluation

Result:
  Assets are no longer placed independently.
  Every asset is placed relative to another asset via a semantic relationship.

  Before:  Table / Chair / Bottle / Lantern placed independently.
  After:   Table → [Chair ×4, Bottle, Lantern] + Poster → Wall

Public API:
    LayoutPlan
    SemanticLayoutEngine
    get_semantic_layout_engine()
    reset_semantic_layout_engine_for_tests()
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.runtime.layout.anchor_layout_engine import (
    get_anchor_layout_engine, AnchorPlacement,
)
from src.runtime.layout.relationship_graph import (
    get_relationship_graph, AssetRelationship,
)
from src.runtime.layout.furniture_cluster_builder import (
    get_furniture_cluster_builder,
)
from src.runtime.layout.surface_placement_engine import (
    get_surface_placement_engine,
)
from src.runtime.layout.wall_attachment_engine import (
    get_wall_attachment_engine,
)
from src.runtime.layout.decoration_layout_engine import (
    get_decoration_layout_engine,
)
from src.runtime.layout.affordance_engine import get_affordance_engine
from src.runtime.layout.layout_review import get_layout_review
from src.runtime.layout.layout_statistics import get_layout_statistics


@dataclass
class LayoutPlan:
    """Complete semantic layout output for one environment."""
    plan_id:    str = field(default_factory=lambda: f"layout_{uuid.uuid4().hex[:10]}")
    environment: str = ""

    anchor_placements:  List[Dict[str, Any]] = field(default_factory=list)
    relationships:      List[Dict[str, Any]] = field(default_factory=list)
    clusters:           List[Dict[str, Any]] = field(default_factory=list)
    surface_placements: List[Dict[str, Any]] = field(default_factory=list)
    wall_attachments:   List[Dict[str, Any]] = field(default_factory=list)
    decoration_items:   List[Dict[str, Any]] = field(default_factory=list)

    review:       Optional[Dict[str, Any]] = None
    ok:           bool = True
    errors:       List[str] = field(default_factory=list)
    generated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id":            self.plan_id,
            "environment":        self.environment,
            "anchor_placements":  list(self.anchor_placements),
            "relationships":      list(self.relationships),
            "clusters":           list(self.clusters),
            "surface_placements": list(self.surface_placements),
            "wall_attachments":   list(self.wall_attachments),
            "decoration_items":   list(self.decoration_items),
            "review":             dict(self.review) if self.review else None,
            "ok":                 self.ok,
            "errors":             list(self.errors),
            "generated_at":       self.generated_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "LayoutPlan":
        return cls(
            plan_id=d.get("plan_id", ""),
            environment=d.get("environment", ""),
            anchor_placements=list(d.get("anchor_placements", [])),
            relationships=list(d.get("relationships", [])),
            clusters=list(d.get("clusters", [])),
            surface_placements=list(d.get("surface_placements", [])),
            wall_attachments=list(d.get("wall_attachments", [])),
            decoration_items=list(d.get("decoration_items", [])),
            review=d.get("review"),
            ok=bool(d.get("ok", True)),
            errors=list(d.get("errors", [])),
            generated_at=float(d.get("generated_at", 0.0)),
        )


class SemanticLayoutEngine:
    """
    Orchestrates the full semantic furniture layout pipeline.

    Usage:
        plan = get_semantic_layout_engine().build_layout(assets, "western_room")
        # plan.clusters[0].members → [chair, chair, chair, chair, bottle, lantern]
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def build_layout(
        self,
        assets: List[Dict[str, Any]],
        environment: str = "",
    ) -> LayoutPlan:
        """
        Build a complete semantic layout plan.

        Args:
            assets:      list of asset metadata dicts
            environment: environment name (e.g. "western_room")

        Returns:
            LayoutPlan. Never raises.
        """
        try:
            return self._build(assets, environment)
        except Exception as exc:
            return LayoutPlan(
                environment=environment,
                ok=False,
                errors=[f"SemanticLayoutEngine.build_layout failed: {exc}"],
            )

    def _build(
        self,
        assets: List[Dict[str, Any]],
        environment: str,
    ) -> LayoutPlan:
        plan = LayoutPlan(environment=environment)
        eng  = get_affordance_engine()

        # ---- Stage 1: Anchor Placement ----
        anchor_result = get_anchor_layout_engine().place_anchors(assets, environment)
        plan.anchor_placements = [p.to_dict() for p in anchor_result.placements]

        anchor_pos_map: Dict[str, List[float]] = {
            p.anchor_id: p.position for p in anchor_result.placements
        }

        # ---- Stage 2: Relationship Graph ----
        graph = get_relationship_graph()
        graph.clear()
        self._build_relationships(assets, anchor_result.placements, graph, eng)
        plan.relationships = [r.to_dict() for r in graph.all_relationships()]

        # ---- Stage 3: Furniture Clusters ----
        cluster_result = get_furniture_cluster_builder().build_clusters(assets, environment)
        plan.clusters = [c.to_dict() for c in cluster_result.clusters]

        # ---- Stage 4: Surface Placement ----
        # Collect cluster member IDs so they are tracked as placed
        cluster_member_ids: set = set()
        for c in cluster_result.clusters:
            for m in c.members:
                cluster_member_ids.add(m.asset_id)

        surface_placements: List[Dict[str, Any]] = []
        for anchor_p in anchor_result.placements:
            anchor_asset = next(
                (a for a in assets
                 if str(a.get("asset_id") or a.get("name") or "") == anchor_p.anchor_id),
                None,
            )
            if anchor_asset is None:
                continue
            # Exclude orbit-children (chairs/stools), wall-attachable, corner-placed,
            # and items already assigned to a cluster (they carry the correct Y there)
            around_types = set(eng.get_affordances(anchor_p.anchor_type).around_children)
            surf_children = [
                a for a in assets
                if (eng.can_support(anchor_p.anchor_type, eng.infer_type(a))
                    and str(a.get("asset_id") or a.get("name") or "") != anchor_p.anchor_id
                    and eng.infer_type(a) not in around_types
                    and not eng.get_affordances(eng.infer_type(a)).is_wall_attachable
                    and not eng.get_affordances(eng.infer_type(a)).is_corner_placed
                    and str(a.get("asset_id") or a.get("name") or "") not in cluster_member_ids)
            ]
            if surf_children:
                spr = get_surface_placement_engine().place_on_surface(
                    anchor_asset,
                    surf_children,
                    anchor_pos_map.get(anchor_p.anchor_id, [0.0, 0.0, 0.0]),
                )
                surface_placements.extend(p.to_dict() for p in spr.placements)
        plan.surface_placements = surface_placements

        # ---- Stage 5: Wall Attachment ----
        wall_candidates = [
            a for a in assets
            if eng.get_affordances(eng.infer_type(a)).is_wall_attachable
        ]
        wall_result = get_wall_attachment_engine().attach_to_walls(wall_candidates)
        plan.wall_attachments = [a.to_dict() for a in wall_result.attachments]

        # ---- Stage 6: Decoration Layout ----
        placed_ids: set = (
            {s.get("child_asset_id", "") for s in surface_placements}
            | {a.get("asset_id", "") for a in plan.wall_attachments}
            | {p.anchor_id for p in anchor_result.placements}
            | cluster_member_ids          # cluster members are placed via their cluster
        )
        deco_candidates = [
            a for a in assets
            if str(a.get("asset_id") or a.get("name") or "") not in placed_ids
        ]
        deco_result = get_decoration_layout_engine().place_decorations(deco_candidates, environment)
        plan.decoration_items = [i.to_dict() for i in deco_result.items]

        # ---- Stage 7: Layout Review ----
        review = get_layout_review().review(plan.to_dict())
        plan.review = review.to_dict()

        # ---- Statistics ----
        get_layout_statistics().record(
            environment=environment,
            cluster_count=len(plan.clusters),
            relationship_count=len(plan.relationships),
            surface_placement_count=len(plan.surface_placements),
            wall_attachment_count=len(plan.wall_attachments),
            overall_score=review.overall_score,
            grade=review.grade,
            production_ready=review.production_ready,
        )

        return plan

    def _build_relationships(
        self,
        assets: List[Dict[str, Any]],
        anchor_placements: List[AnchorPlacement],
        graph,
        eng,
    ) -> None:
        """Build relationship graph edges from affordances."""
        anchor_id_set = {p.anchor_id for p in anchor_placements}

        for asset in assets:
            asset_id = str(asset.get("asset_id") or asset.get("name") or "")
            a_type   = eng.infer_type(asset)
            aff      = eng.get_affordances(a_type)

            if asset_id in anchor_id_set:
                # Anchor: other assets relate TO this anchor
                for other in assets:
                    other_id   = str(other.get("asset_id") or other.get("name") or "")
                    if other_id == asset_id:
                        continue
                    other_type = eng.infer_type(other)
                    if eng.can_support(a_type, other_type):
                        graph.add_relationship(AssetRelationship(
                            from_asset_id=other_id,
                            to_asset_id=asset_id,
                            relationship_type="supports",
                        ))
                    elif eng.can_surround(a_type, other_type):
                        graph.add_relationship(AssetRelationship(
                            from_asset_id=other_id,
                            to_asset_id=asset_id,
                            relationship_type="around",
                        ))
            else:
                mode = aff.placement_mode
                if mode in ("wall_only", "wall_or_ceiling"):
                    graph.add_relationship(AssetRelationship(
                        from_asset_id=asset_id,
                        to_asset_id="wall",
                        relationship_type="attached_to",
                    ))
                elif mode == "against_wall":
                    graph.add_relationship(AssetRelationship(
                        from_asset_id=asset_id,
                        to_asset_id="wall",
                        relationship_type="against",
                    ))
                elif mode == "corner":
                    graph.add_relationship(AssetRelationship(
                        from_asset_id=asset_id,
                        to_asset_id="corner",
                        relationship_type="near",
                    ))


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[SemanticLayoutEngine] = None
_lock = threading.Lock()


def get_semantic_layout_engine() -> SemanticLayoutEngine:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = SemanticLayoutEngine()
    return _instance


def reset_semantic_layout_engine_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
