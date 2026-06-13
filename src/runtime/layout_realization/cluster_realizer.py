"""
cluster_realizer.py — §47 Layout Realization & Scene Constraint Solver
=======================================================================
Converts FurnitureCluster data from LayoutPlan.clusters into a full set
of world-space transforms for the cluster anchor and all its members.

Cluster realization rules:
  - Anchor goes to its assigned world position (from anchor_placements)
  - Members' relative_position is added to the anchor world position
  - orientation_deg becomes ry on the member transform
  - All members inherit the cluster_id tag for grouping

Public API:
    ClusterRealizationResult
    ClusterRealizer
    get_cluster_realizer()
    reset_cluster_realizer_for_tests()
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.runtime.layout_realization.transform_resolver import ResolvedTransform


# Surface height per anchor type — safety net so surface members never land at floor level
_SURFACE_H: Dict[str, float] = {
    "table":       0.75,
    "desk":        0.75,
    "workbench":   0.90,
    "bar_counter": 1.05,
    "shelf":       1.40,
    "counter":     0.90,
    "mantle":      1.20,
    "cabinet":     1.60,
    "console":     0.85,
}
_DEFAULT_SURFACE_H = 0.75


@dataclass
class ClusterRealizationResult:
    cluster_id:       str
    cluster_type:     str
    anchor_transform: Optional[ResolvedTransform]
    member_transforms: List[ResolvedTransform] = field(default_factory=list)
    ok:     bool = True
    errors: List[str] = field(default_factory=list)

    def all_transforms(self) -> List[ResolvedTransform]:
        """Return anchor + all member transforms."""
        result = []
        if self.anchor_transform:
            result.append(self.anchor_transform)
        result.extend(self.member_transforms)
        return result

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cluster_id":        self.cluster_id,
            "cluster_type":      self.cluster_type,
            "anchor_transform":  self.anchor_transform.to_dict() if self.anchor_transform else None,
            "member_transforms": [t.to_dict() for t in self.member_transforms],
            "ok":                self.ok,
            "errors":            list(self.errors),
        }


class ClusterRealizer:
    """Converts FurnitureCluster plan data into concrete world transforms."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def realize_cluster(
        self,
        cluster: Dict[str, Any],
        anchor_world_pos: Optional[List[float]] = None,
    ) -> ClusterRealizationResult:
        """
        Realize a single FurnitureCluster into world-space transforms.

        Args:
            cluster:          FurnitureCluster.to_dict()
            anchor_world_pos: override the anchor position (from anchor_placements);
                              falls back to cluster["anchor_position"]

        Returns: ClusterRealizationResult. Never raises.
        """
        try:
            return self._realize(cluster, anchor_world_pos)
        except Exception as exc:
            return ClusterRealizationResult(
                cluster_id=cluster.get("cluster_id", ""),
                cluster_type=cluster.get("cluster_type", ""),
                anchor_transform=None,
                ok=False,
                errors=[f"ClusterRealizer.realize_cluster failed: {exc}"],
            )

    def realize_all_clusters(
        self,
        clusters: List[Dict[str, Any]],
        anchor_pos_map: Dict[str, List[float]],
    ) -> List[ClusterRealizationResult]:
        """
        Realize all clusters in a LayoutPlan.

        Args:
            clusters:       plan.clusters dicts
            anchor_pos_map: map anchor_asset_id → world [tx, ty, tz]

        Never raises.
        """
        results = []
        for cluster in clusters:
            anchor_id  = cluster.get("anchor_asset_id", "")
            anchor_pos = anchor_pos_map.get(anchor_id)
            results.append(self.realize_cluster(cluster, anchor_pos))
        return results

    def _realize(
        self,
        cluster: Dict[str, Any],
        anchor_world_pos: Optional[List[float]],
    ) -> ClusterRealizationResult:
        cluster_id   = cluster.get("cluster_id", "")
        cluster_type = cluster.get("cluster_type", "")
        anchor_id    = cluster.get("anchor_asset_id", "")
        anchor_name  = cluster.get("anchor_asset_name", "")
        anchor_type  = cluster.get("anchor_asset_type", "")

        # World position for anchor
        if anchor_world_pos is not None:
            wp = list(anchor_world_pos)
        else:
            cp = cluster.get("anchor_position") or [0.0, 0.0, 0.0]
            wp = [float(cp[0]), float(cp[1]), float(cp[2])]

        anchor_xf = ResolvedTransform(
            asset_id=anchor_id,
            asset_name=anchor_name,
            tx=wp[0], ty=wp[1], tz=wp[2],
            relationship="anchor",
            cluster_id=cluster_id,
            notes=f"cluster anchor type={anchor_type}",
        )

        members = cluster.get("members") or []
        member_xfs: List[ResolvedTransform] = []
        # Pre-compute surface height for this cluster's anchor type
        surf_h = _SURFACE_H.get(anchor_type, _DEFAULT_SURFACE_H)

        for m in members:
            rel_pos  = m.get("relative_position") or [0.0, 0.0, 0.0]
            orient   = float(m.get("orientation_deg", 0.0))
            m_id     = m.get("asset_id", "")
            m_name   = m.get("asset_name", "")
            rel_type = m.get("relationship", "near")

            rel_y = float(rel_pos[1])
            if rel_type == "supports":
                # Surface props must land on the surface, not at floor.
                # Use anchor surface height when the stored Y offset is at floor (< 0.3m).
                item_ty = wp[1] + (rel_y if rel_y >= 0.3 else surf_h)
            else:
                item_ty = wp[1] + rel_y

            member_xfs.append(ResolvedTransform(
                asset_id=m_id,
                asset_name=m_name,
                tx=wp[0] + float(rel_pos[0]),
                ty=item_ty,
                tz=wp[2] + float(rel_pos[2]),
                ry=orient,
                parent_id=anchor_id,
                relationship=rel_type,
                cluster_id=cluster_id,
            ))

        return ClusterRealizationResult(
            cluster_id=cluster_id,
            cluster_type=cluster_type,
            anchor_transform=anchor_xf,
            member_transforms=member_xfs,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[ClusterRealizer] = None
_lock = threading.Lock()


def get_cluster_realizer() -> ClusterRealizer:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = ClusterRealizer()
    return _instance


def reset_cluster_realizer_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
