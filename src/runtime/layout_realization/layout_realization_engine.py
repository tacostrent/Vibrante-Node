"""
layout_realization_engine.py — §47 Layout Realization & Scene Constraint Solver
================================================================================
Main orchestrator: converts a Tier 9.8 LayoutPlan into a ResolvedSceneLayout —
a concrete set of world-space transforms ready for scene application.

Pipeline stages:
  1. Cluster Realization    — FurnitureClusters → world transforms for all members
  2. Surface Realization    — surface_placements → ty-corrected transforms
  3. Wall Realization       — wall_attachments → wall-face transforms + ry
  4. Decoration Realization — decoration_items → floor-level or contextual transforms
  5. Anchor Deduplication   — remove duplicates already resolved via clusters
  6. Collision Solving      — push-apart AABB resolution
  7. Constraint Solving     — min-spacing, wall clearance, hero visibility
  8. Final Assembly         — merge all transforms into ResolvedSceneLayout

Public API:
    ResolvedSceneLayout
    LayoutRealizationEngine
    get_layout_realization_engine()
    reset_layout_realization_engine_for_tests()
"""

from __future__ import annotations

import time
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.runtime.layout_realization.transform_resolver import (
    ResolvedTransform,
    get_transform_resolver,
)
from src.runtime.layout_realization.cluster_realizer import get_cluster_realizer
from src.runtime.layout_realization.surface_realizer import get_surface_realizer
from src.runtime.layout_realization.wall_attachment_realizer import get_wall_attachment_realizer
from src.runtime.layout_realization.collision_solver import get_collision_solver
from src.runtime.layout_realization.scene_constraint_solver import get_scene_constraint_solver


@dataclass
class ResolvedSceneLayout:
    """
    The realized output of LayoutRealizationEngine.
    Contains one ResolvedTransform per asset, ready for scene application.
    """
    layout_id:   str = field(default_factory=lambda: f"realized_{uuid.uuid4().hex[:10]}")
    plan_id:     str = ""
    environment: str = ""

    transforms: List[ResolvedTransform] = field(default_factory=list)

    # Quality metrics
    asset_count:          int = 0
    cluster_count:        int = 0
    surface_placement_count: int = 0
    wall_attachment_count:   int = 0
    collision_count:         int = 0
    constraint_violations:   int = 0

    # Flags
    production_ready: bool = False
    warnings:  List[str] = field(default_factory=list)
    ok:        bool = True
    errors:    List[str] = field(default_factory=list)
    realized_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "layout_id":               self.layout_id,
            "plan_id":                 self.plan_id,
            "environment":             self.environment,
            "transforms":              [t.to_dict() for t in self.transforms],
            "asset_count":             self.asset_count,
            "cluster_count":           self.cluster_count,
            "surface_placement_count": self.surface_placement_count,
            "wall_attachment_count":   self.wall_attachment_count,
            "collision_count":         self.collision_count,
            "constraint_violations":   self.constraint_violations,
            "production_ready":        self.production_ready,
            "warnings":                list(self.warnings),
            "ok":                      self.ok,
            "errors":                  list(self.errors),
            "realized_at":             self.realized_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ResolvedSceneLayout":
        return cls(
            layout_id=d.get("layout_id", ""),
            plan_id=d.get("plan_id", ""),
            environment=d.get("environment", ""),
            transforms=[ResolvedTransform.from_dict(t) for t in d.get("transforms", [])],
            asset_count=int(d.get("asset_count", 0)),
            cluster_count=int(d.get("cluster_count", 0)),
            surface_placement_count=int(d.get("surface_placement_count", 0)),
            wall_attachment_count=int(d.get("wall_attachment_count", 0)),
            collision_count=int(d.get("collision_count", 0)),
            constraint_violations=int(d.get("constraint_violations", 0)),
            production_ready=bool(d.get("production_ready", False)),
            warnings=list(d.get("warnings", [])),
            ok=bool(d.get("ok", True)),
            errors=list(d.get("errors", [])),
            realized_at=float(d.get("realized_at", 0.0)),
        )


class LayoutRealizationEngine:
    """
    Converts a LayoutPlan (from Tier 9.8) into a ResolvedSceneLayout.

    Usage:
        plan  = get_semantic_layout_engine().build_layout(assets, "western_room")
        scene = get_layout_realization_engine().realize(plan.to_dict())
        # scene.transforms → list of ResolvedTransform with tx/ty/tz/rx/ry/rz
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def realize(
        self,
        layout_plan: Dict[str, Any],
        room_half_width: float = 4.0,
        type_hints: Optional[Dict[str, str]] = None,
    ) -> ResolvedSceneLayout:
        """
        Convert a LayoutPlan dict into a ResolvedSceneLayout.

        Args:
            layout_plan:     LayoutPlan.to_dict()
            room_half_width: room half-extent for boundary checks
            type_hints:      map asset_id → placement_type for radii

        Returns: ResolvedSceneLayout. Never raises.
        """
        try:
            return self._realize(layout_plan, room_half_width, type_hints or {})
        except Exception as exc:
            return ResolvedSceneLayout(
                plan_id=layout_plan.get("plan_id", "") if isinstance(layout_plan, dict) else "",
                ok=False,
                errors=[f"LayoutRealizationEngine.realize failed: {exc}"],
            )

    def _realize(
        self,
        plan: Dict[str, Any],
        room_half_width: float,
        type_hints: Dict[str, str],
    ) -> ResolvedSceneLayout:
        scene = ResolvedSceneLayout(
            plan_id=plan.get("plan_id", ""),
            environment=plan.get("environment", ""),
        )

        resolver  = get_transform_resolver()
        clusterer = get_cluster_realizer()
        surfer    = get_surface_realizer()
        waller    = get_wall_attachment_realizer()

        anchor_placements  = plan.get("anchor_placements")  or []
        clusters           = plan.get("clusters")           or []
        surface_placements = plan.get("surface_placements") or []
        wall_attachments   = plan.get("wall_attachments")   or []
        decoration_items   = plan.get("decoration_items")   or []

        all_transforms: List[ResolvedTransform] = []
        placed_ids: set = set()

        # Build anchor world position map
        anchor_pos_map: Dict[str, List[float]] = {
            ap["anchor_id"]: list(ap.get("position", [0.0, 0.0, 0.0]))
            for ap in anchor_placements
        }
        # Build anchor transforms map (for surface/relationship lookup)
        anchor_xf_map: Dict[str, ResolvedTransform] = {}
        for ap in anchor_placements:
            axf = resolver.resolve_anchor(ap)
            anchor_xf_map[ap["anchor_id"]] = axf

        # --- Stage 1: Cluster realization ---
        cluster_results = clusterer.realize_all_clusters(clusters, anchor_pos_map)
        for cr in cluster_results:
            for xf in cr.all_transforms():
                if xf.asset_id not in placed_ids:
                    all_transforms.append(xf)
                    placed_ids.add(xf.asset_id)

        scene.cluster_count = len(cluster_results)

        # --- Stage 2: Surface realization ---
        surf_xfs = surfer.realize_surface_placements(surface_placements, anchor_xf_map)
        for xf in surf_xfs:
            if xf.asset_id not in placed_ids:
                all_transforms.append(xf)
                placed_ids.add(xf.asset_id)

        scene.surface_placement_count = len(surf_xfs)

        # --- Stage 3: Wall realization ---
        wall_result = waller.realize_wall_attachments(wall_attachments, room_half_width)
        for xf in wall_result.transforms:
            if xf.asset_id not in placed_ids:
                all_transforms.append(xf)
                placed_ids.add(xf.asset_id)
        scene.warnings.extend(wall_result.errors)

        scene.wall_attachment_count = len(wall_result.transforms)

        # --- Stage 4: Decoration realization (floor-level fallback) ---
        deco_slot = 0
        # Usable interior bound (leave 0.8 m from wall) clamped to room_half_width
        inner = max(1.0, room_half_width - 0.8)
        # Maximum rows before wrapping so z never exits the room
        max_rows = max(1, int(inner))
        for item in decoration_items:
            item_id = item.get("asset_id") or item.get("item_id") or ""
            if item_id in placed_ids:
                continue
            pos = item.get("position") or [0.0, 0.0, 0.0]
            # If position is [0,0,0] (unset) give a bounded floor slot
            if pos == [0, 0, 0] or pos == [0.0, 0.0, 0.0]:
                col = deco_slot % 4
                row = (deco_slot // 4) % max_rows          # wrap rows within room
                x_off = max(-inner, min(inner, (col - 1.5) * 1.0))
                z_off = max(-inner, min(inner, row * 1.0 - inner / 2.0))
                pos = [x_off, 0.0, z_off]
                deco_slot += 1
            xf = resolver.resolve_decoration({**item, "position": pos})
            all_transforms.append(xf)
            placed_ids.add(item_id)

        # --- Stage 5: Anchors not yet placed (no cluster) ---
        for ap in anchor_placements:
            if ap["anchor_id"] not in placed_ids:
                all_transforms.append(resolver.resolve_anchor(ap))
                placed_ids.add(ap["anchor_id"])

        # --- Stage 6: Collision solving ---
        col_result = get_collision_solver().solve(all_transforms, room_half_width, type_hints)
        all_transforms = col_result.transforms
        scene.collision_count = col_result.collisions_remaining
        scene.warnings.extend(col_result.warnings)

        # --- Stage 7: Constraint solving ---
        hero_id = ""
        for ap in anchor_placements:
            if ap.get("is_hero"):
                hero_id = ap.get("anchor_id", "")
                break
        con_result = get_scene_constraint_solver().solve_constraints(
            all_transforms, room_half_width, type_hints, hero_id
        )
        all_transforms = con_result.transforms
        scene.constraint_violations = con_result.violations_remaining

        # --- Stage 8: Final assembly ---
        scene.transforms  = all_transforms
        scene.asset_count = len(all_transforms)
        scene.production_ready = (
            scene.collision_count == 0
            and scene.constraint_violations == 0
            and scene.asset_count > 0
            and scene.ok
        )

        return scene


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[LayoutRealizationEngine] = None
_lock = threading.Lock()


def get_layout_realization_engine() -> LayoutRealizationEngine:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = LayoutRealizationEngine()
    return _instance


def reset_layout_realization_engine_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
