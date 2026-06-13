"""
furniture_cluster_builder.py — §46 Semantic Furniture Layout Engine
===================================================================
Builds semantically coherent furniture clusters from anchor assets.

A FurnitureCluster groups a primary anchor with its semantic dependents:
  Dining Cluster:    table → [chair ×4, bottle, lantern]
  Saloon Cluster:    table → [chair ×4, whiskey_bottle, lantern]
  Workbench Cluster: workbench → [tool ×3, container ×2]
  Bar Cluster:       bar_counter → [stool ×3, bottle ×3]
  Campfire Cluster:  campfire → [bench, barrel, stool]

Public API:
    ClusterMember
    FurnitureCluster
    ClusterBuildResult
    FurnitureClusterBuilder
    get_furniture_cluster_builder()
    reset_furniture_cluster_builder_for_tests()
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.runtime.layout.affordance_engine import get_affordance_engine


# Default chair orbit radius (meters) — used when anchor has no geometry data
_CHAIR_ORBIT_RADIUS = 0.90
_STOOL_ORBIT_RADIUS = 0.65

# Surface height per anchor type (meters above floor) — used for correct Y on surface items
_ANCHOR_SURFACE_HEIGHTS: Dict[str, float] = {
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

# Clearance and seating margins (meters) used in dimension-aware orbit computation
_CHAIR_CLEARANCE  = 0.30   # minimum chair-leg-to-table-edge clearance
_SEATING_OFFSET   = 0.15   # chair centre set-back from clearance point
_STOOL_CLEARANCE  = 0.25   # tighter clearance for bar stools
_STOOL_OFFSET     = 0.10


def _compute_orbit_positions(
    orbit_radius: float,
    is_stool: bool = False,
) -> list:
    """Return 4 (position, orientation_deg) tuples at the given orbit radius."""
    r = orbit_radius
    if is_stool:
        return [
            ([-r, 0.0, 0.0],  90.0),   # west  → faces east
            ([0.0, 0.0, -r],   0.0),   # north → faces south
            ([ r, 0.0, 0.0], 270.0),   # east  → faces west
            ([0.0, 0.0,  r],  180.0),  # south → faces north
        ]
    return [
        ([0.0, 0.0,  r],  180.0),  # south → faces north
        ([0.0, 0.0, -r],    0.0),  # north → faces south
        ([ r, 0.0, 0.0],  270.0),  # east  → faces west
        ([-r, 0.0, 0.0],   90.0),  # west  → faces east
    ]


# Pre-built default orbit pools (used when no geometry data available)
_CHAIR_POSITIONS = _compute_orbit_positions(_CHAIR_ORBIT_RADIUS, is_stool=False)
_STOOL_POSITIONS = _compute_orbit_positions(_STOOL_ORBIT_RADIUS, is_stool=True)

# Surface item XZ offsets relative to anchor (Y is computed per anchor type)
_SURFACE_ITEM_XZ: List[List[float]] = [
    [-0.25,  0.15],
    [ 0.25,  0.15],
    [ 0.00, -0.10],
    [-0.25, -0.10],
    [ 0.25, -0.10],
    [ 0.00,  0.25],
]


@dataclass
class ClusterMember:
    asset_id: str
    asset_name: str
    asset_type: str
    relationship: str
    relative_position: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    orientation_deg: float = 0.0

    def to_dict(self) -> dict:
        return {
            "asset_id":          self.asset_id,
            "asset_name":        self.asset_name,
            "asset_type":        self.asset_type,
            "relationship":      self.relationship,
            "relative_position": [round(v, 3) for v in self.relative_position],
            "orientation_deg":   round(self.orientation_deg, 1),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ClusterMember":
        return cls(
            asset_id=d.get("asset_id", ""),
            asset_name=d.get("asset_name", ""),
            asset_type=d.get("asset_type", ""),
            relationship=d.get("relationship", "near"),
            relative_position=list(d.get("relative_position", [0.0, 0.0, 0.0])),
            orientation_deg=float(d.get("orientation_deg", 0.0)),
        )


@dataclass
class FurnitureCluster:
    cluster_id: str
    cluster_type: str
    anchor_asset_id: str
    anchor_asset_name: str
    anchor_asset_type: str
    anchor_position: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    members: List[ClusterMember] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "cluster_id":        self.cluster_id,
            "cluster_type":      self.cluster_type,
            "anchor_asset_id":   self.anchor_asset_id,
            "anchor_asset_name": self.anchor_asset_name,
            "anchor_asset_type": self.anchor_asset_type,
            "anchor_position":   [round(v, 3) for v in self.anchor_position],
            "members":           [m.to_dict() for m in self.members],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "FurnitureCluster":
        return cls(
            cluster_id=d.get("cluster_id", ""),
            cluster_type=d.get("cluster_type", ""),
            anchor_asset_id=d.get("anchor_asset_id", ""),
            anchor_asset_name=d.get("anchor_asset_name", ""),
            anchor_asset_type=d.get("anchor_asset_type", ""),
            anchor_position=list(d.get("anchor_position", [0.0, 0.0, 0.0])),
            members=[ClusterMember.from_dict(m) for m in d.get("members", [])],
        )


@dataclass
class ClusterBuildResult:
    clusters: List[FurnitureCluster] = field(default_factory=list)
    unassigned: List[Dict[str, Any]] = field(default_factory=list)
    ok: bool = True
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "clusters":   [c.to_dict() for c in self.clusters],
            "unassigned": list(self.unassigned),
            "ok":         self.ok,
            "errors":     list(self.errors),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ClusterBuildResult":
        return cls(
            clusters=[FurnitureCluster.from_dict(c) for c in d.get("clusters", [])],
            unassigned=list(d.get("unassigned", [])),
            ok=bool(d.get("ok", True)),
            errors=list(d.get("errors", [])),
        )


class FurnitureClusterBuilder:
    """Builds semantically grouped furniture clusters from an asset list."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counter = 0

    def build_clusters(
        self,
        assets: List[Dict[str, Any]],
        environment: str = "",
    ) -> ClusterBuildResult:
        """
        Build furniture clusters from a list of assets.

        Anchor assets become cluster roots. Child assets are assigned to
        the most semantically appropriate anchor. Never raises.
        """
        try:
            return self._build(assets, environment)
        except Exception as exc:
            return ClusterBuildResult(
                ok=False,
                errors=[f"FurnitureClusterBuilder.build_clusters failed: {exc}"],
            )

    def _build(
        self,
        assets: List[Dict[str, Any]],
        environment: str,
    ) -> ClusterBuildResult:
        eng = get_affordance_engine()

        anchors: List[Dict[str, Any]] = []
        children: List[Dict[str, Any]] = []
        for asset in assets:
            t = eng.infer_type(asset)
            if eng.get_affordances(t).is_anchor:
                anchors.append(asset)
            else:
                children.append(asset)

        assigned_ids: set = set()
        clusters: List[FurnitureCluster] = []
        for anchor in anchors:
            cluster = self._build_cluster(anchor, children, assigned_ids, environment)
            clusters.append(cluster)

        unassigned = [
            c for c in children
            if str(c.get("asset_id") or c.get("name") or "") not in assigned_ids
        ]
        return ClusterBuildResult(clusters=clusters, unassigned=unassigned)

    def _build_cluster(
        self,
        anchor: Dict[str, Any],
        children: List[Dict[str, Any]],
        assigned_ids: set,
        environment: str,
    ) -> FurnitureCluster:
        eng = get_affordance_engine()
        anchor_type = eng.infer_type(anchor)
        anchor_id   = str(anchor.get("asset_id") or anchor.get("name") or f"anchor_{self._counter}")
        anchor_name = str(anchor.get("name") or anchor_id)

        with self._lock:
            self._counter += 1
            cid = f"cluster_{self._counter:04d}"

        cluster_type = self._cluster_type(anchor_type, environment)
        cluster = FurnitureCluster(
            cluster_id=cid,
            cluster_type=cluster_type,
            anchor_asset_id=anchor_id,
            anchor_asset_name=anchor_name,
            anchor_asset_type=anchor_type,
        )

        affordances = eng.get_affordances(anchor_type)

        # Around members (chairs, stools) — orbit radius based on real anchor dims
        is_stool_context = anchor_type in ("bar_counter", "counter")
        orbit_radius = self._orbit_radius_for(anchor, is_stool_context)
        orbit_pool = _compute_orbit_positions(orbit_radius, is_stool=is_stool_context)
        around_count = 0
        for child in children:
            child_id   = str(child.get("asset_id") or child.get("name") or "")
            child_type = eng.infer_type(child)
            if child_type in affordances.around_children and child_id not in assigned_ids:
                if around_count < len(orbit_pool):
                    pos, orient = orbit_pool[around_count]
                    cluster.members.append(ClusterMember(
                        asset_id=child_id,
                        asset_name=str(child.get("name") or child_id),
                        asset_type=child_type,
                        relationship="around",
                        relative_position=list(pos),
                        orientation_deg=orient,
                    ))
                    assigned_ids.add(child_id)
                    around_count += 1

        # Surface members (props on tabletop) — exclude wall-attachable and corner-placed
        # Y = anchor surface height so props land ON the surface, not at floor level
        surf_h = _ANCHOR_SURFACE_HEIGHTS.get(anchor_type, _DEFAULT_SURFACE_H)
        surf_count = 0
        for child in children:
            child_id   = str(child.get("asset_id") or child.get("name") or "")
            child_type = eng.infer_type(child)
            if child_id in assigned_ids:
                continue
            child_aff = eng.get_affordances(child_type)
            if child_aff.is_wall_attachable or child_aff.is_corner_placed:
                continue
            if eng.can_support(anchor_type, child_type) and surf_count < len(_SURFACE_ITEM_XZ):
                xz = _SURFACE_ITEM_XZ[surf_count]
                cluster.members.append(ClusterMember(
                    asset_id=child_id,
                    asset_name=str(child.get("name") or child_id),
                    asset_type=child_type,
                    relationship="supports",
                    relative_position=[xz[0], surf_h, xz[1]],
                    orientation_deg=0.0,
                ))
                assigned_ids.add(child_id)
                surf_count += 1

        return cluster

    @staticmethod
    def _orbit_radius_for(anchor: dict, is_stool: bool) -> float:
        """
        Compute orbit radius from real-world anchor dimensions when available.

        Formula: max(half_w, half_d) + clearance + seating_offset

        Falls back to _STOOL_ORBIT_RADIUS / _CHAIR_ORBIT_RADIUS when no
        geometry data is present on the anchor dict.
        """
        w = anchor.get("width_m") or anchor.get("bbox_x")
        d = anchor.get("depth_m") or anchor.get("bbox_z")
        if w or d:
            try:
                half_w = float(w or 0) / 2.0
                half_d = float(d or 0) / 2.0
                half   = max(half_w, half_d)
                if half > 0:
                    if is_stool:
                        return round(half + _STOOL_CLEARANCE + _STOOL_OFFSET, 3)
                    return round(half + _CHAIR_CLEARANCE + _SEATING_OFFSET, 3)
            except (TypeError, ValueError):
                pass
        return _STOOL_ORBIT_RADIUS if is_stool else _CHAIR_ORBIT_RADIUS

    @staticmethod
    def _cluster_type(anchor_type: str, environment: str) -> str:
        env = environment.lower()
        if anchor_type == "table":
            if any(k in env for k in ("saloon", "western", "tavern")):
                return "saloon_table_cluster"
            if any(k in env for k in ("dining", "restaurant", "cafe")):
                return "dining_cluster"
            return "table_cluster"
        if anchor_type in ("workbench", "desk"):
            return "workbench_cluster"
        if anchor_type == "bar_counter":
            return "bar_cluster"
        if anchor_type in ("fireplace",):
            return "fireplace_cluster"
        if anchor_type == "campfire":
            return "campfire_cluster"
        if anchor_type in ("machine", "large_machine"):
            return "machine_cluster"
        if anchor_type == "console":
            return "console_cluster"
        return f"{anchor_type}_cluster"


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[FurnitureClusterBuilder] = None
_lock = threading.Lock()


def get_furniture_cluster_builder() -> FurnitureClusterBuilder:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = FurnitureClusterBuilder()
    return _instance


def reset_furniture_cluster_builder_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
