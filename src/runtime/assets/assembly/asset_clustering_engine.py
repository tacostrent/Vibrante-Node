"""
Asset Clustering Engine (Tier 9 — Semantic Asset Assembly)
===========================================================
Groups assets from an EnvironmentPlan into production-style clusters.

Cluster types:
    machinery_cluster    — heavy mechanical equipment
    pipe_cluster         — pipe runs and conduit groups (linear)
    workstation_cluster  — desk / console groupings
    control_cluster      — control panels and monitors
    atmosphere_cluster   — fog / particle / atmosphere props

DESIGN RULES:
  1. Deterministic — same EnvironmentPlan → same clusters every time.
  2. No bridge calls.  No Houdini imports.  Planning only.
  3. Cluster assignment is category-affinity based, not spatial.
  4. Never raises — errors captured in ClusterPlan.errors.

Public API:
    AssetCluster
    ClusterPlan
    AssetClusteringEngine
    get_asset_clustering_engine()
    reset_asset_clustering_engine_for_tests()
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from src.runtime.assets.assembly.environment_builder import EnvironmentPlan

# ---------------------------------------------------------------------------
# Cluster type → category affinity
# ---------------------------------------------------------------------------

_CLUSTER_AFFINITIES: Dict[str, Set[str]] = {
    "machinery_cluster":   {"machinery", "vehicle", "robot"},
    "pipe_cluster":        {"pipe", "conduit", "structure"},
    "workstation_cluster": {"electronic", "furniture", "prop"},
    "control_cluster":     {"electronic", "prop"},
    "atmosphere_cluster":  {"hdri", "material", "terrain", "vegetation"},
}

# Maximum members per cluster type (from template rules)
_CLUSTER_MAX: Dict[str, int] = {
    "machinery_cluster":   3,
    "pipe_cluster":        5,
    "workstation_cluster": 3,
    "control_cluster":     3,
    "atmosphere_cluster":  6,
}

# Cluster → preferred zone
_CLUSTER_ZONES: Dict[str, str] = {
    "machinery_cluster":   "hero_zone",
    "pipe_cluster":        "service_area",
    "workstation_cluster": "midground",
    "control_cluster":     "console_arc",
    "atmosphere_cluster":  "background",
}


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class AssetCluster:
    """One named cluster of assets."""

    cluster_id:   str
    cluster_type: str
    role:         str           # primary, support, detail, atmosphere
    zone_name:    str
    members:      List[Dict[str, Any]] = field(default_factory=list)
    max_members:  int = 3
    is_linear:    bool = False
    density:      float = 0.5   # 0.0 = sparse  1.0 = packed
    notes:        List[str] = field(default_factory=list)

    @property
    def member_count(self) -> int:
        return len(self.members)

    @property
    def is_full(self) -> bool:
        return self.member_count >= self.max_members

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cluster_id":   self.cluster_id,
            "cluster_type": self.cluster_type,
            "role":         self.role,
            "zone_name":    self.zone_name,
            "members":      list(self.members),
            "max_members":  self.max_members,
            "is_linear":    self.is_linear,
            "density":      self.density,
            "notes":        list(self.notes),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AssetCluster":
        return cls(
            cluster_id=str(d.get("cluster_id", "")),
            cluster_type=str(d.get("cluster_type", "")),
            role=str(d.get("role", "support")),
            zone_name=str(d.get("zone_name", "")),
            members=list(d.get("members") or []),
            max_members=int(d.get("max_members", 3)),
            is_linear=bool(d.get("is_linear", False)),
            density=float(d.get("density", 0.5)),
            notes=list(d.get("notes") or []),
        )


@dataclass
class ClusterPlan:
    """Clustering result for an entire environment."""

    plan_id:        str = field(default_factory=lambda: f"clust_{uuid.uuid4().hex[:10]}")
    environment:    str = ""
    clusters:       List[AssetCluster] = field(default_factory=list)
    cluster_counts: Dict[str, int] = field(default_factory=dict)
    total_members:  int = 0
    ok:             bool = True
    errors:         List[str] = field(default_factory=list)
    warnings:       List[str] = field(default_factory=list)
    generated_at:   float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id":        self.plan_id,
            "environment":    self.environment,
            "clusters":       [c.to_dict() for c in self.clusters],
            "cluster_counts": dict(self.cluster_counts),
            "total_members":  self.total_members,
            "ok":             self.ok,
            "errors":         list(self.errors),
            "warnings":       list(self.warnings),
            "generated_at":   self.generated_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ClusterPlan":
        return cls(
            plan_id=str(d.get("plan_id", f"clust_{uuid.uuid4().hex[:10]}")),
            environment=str(d.get("environment", "")),
            clusters=[AssetCluster.from_dict(c) for c in (d.get("clusters") or [])],
            cluster_counts=dict(d.get("cluster_counts") or {}),
            total_members=int(d.get("total_members", 0)),
            ok=bool(d.get("ok", True)),
            errors=list(d.get("errors") or []),
            warnings=list(d.get("warnings") or []),
            generated_at=float(d.get("generated_at", 0.0)),
        )


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class AssetClusteringEngine:
    """
    Creates production-style asset clusters from an EnvironmentPlan.
    Clustering is category-affinity based.
    """

    def build_clusters(self, env_plan: EnvironmentPlan) -> ClusterPlan:
        """
        Build a ClusterPlan from an EnvironmentPlan.
        Never raises — errors captured in ClusterPlan.errors.
        """
        plan = ClusterPlan(environment=env_plan.environment)
        try:
            # Collect all assigned assets
            all_assets: List[Dict[str, Any]] = []
            for zone_name, zone in env_plan.zones.items():
                for rec in zone.assigned_assets:
                    asset = rec.get("asset") or {}
                    all_assets.append({
                        "rec":       rec,
                        "asset":     asset,
                        "zone_name": zone_name,
                        "category":  str(asset.get("category", "")).lower(),
                        "name":      str(asset.get("name") or asset.get("asset_id") or "?"),
                    })

            clusters = self.assign_cluster_roles(all_assets, env_plan)
            plan.clusters = clusters

            for c in clusters:
                plan.cluster_counts[c.cluster_type] = (
                    plan.cluster_counts.get(c.cluster_type, 0) + 1
                )
                plan.total_members += c.member_count

            balance = self.validate_cluster_balance(plan)
            plan.warnings.extend(balance.get("warnings", []))
            plan.ok = True

        except Exception as exc:
            plan.ok = False
            plan.errors.append(f"Clustering failed: {exc}")

        return plan

    def assign_cluster_roles(
        self,
        assets: List[Dict[str, Any]],
        env_plan: EnvironmentPlan,
    ) -> List[AssetCluster]:
        """
        Assign each asset to the most-appropriate cluster type.
        Returns a list of AssetClusters sorted by zone depth (hero first).
        """
        # Build cluster buckets (cluster_type → list of members)
        buckets: Dict[str, List[Dict[str, Any]]] = {ct: [] for ct in _CLUSTER_AFFINITIES}
        unassigned: List[Dict[str, Any]] = []

        for asset_info in assets:
            cat   = asset_info["category"]
            placed = False
            # Check affinity in priority order
            for ctype, cats in _CLUSTER_AFFINITIES.items():
                if cat in cats and len(buckets[ctype]) < _CLUSTER_MAX[ctype]:
                    buckets[ctype].append(asset_info)
                    placed = True
                    break
            if not placed:
                unassigned.append(asset_info)

        # Overflow → workstation_cluster (generic catch-all)
        for asset_info in unassigned:
            if len(buckets["workstation_cluster"]) < _CLUSTER_MAX["workstation_cluster"] * 2:
                buckets["workstation_cluster"].append(asset_info)

        # Convert buckets → AssetCluster objects
        clusters: List[AssetCluster] = []
        for ctype, members in buckets.items():
            if not members:
                continue
            zone_name = _best_zone(ctype, env_plan)
            density   = self.calculate_cluster_density(members, _CLUSTER_MAX[ctype])
            cluster   = AssetCluster(
                cluster_id=f"{ctype}_{uuid.uuid4().hex[:6]}",
                cluster_type=ctype,
                role=_cluster_role(ctype),
                zone_name=zone_name,
                members=[a["rec"] for a in members],
                max_members=_CLUSTER_MAX[ctype],
                is_linear=(ctype == "pipe_cluster"),
                density=density,
            )
            clusters.append(cluster)

        # Sort: primary first
        _ROLE_ORDER = {"primary": 0, "support": 1, "detail": 2, "atmosphere": 3}
        clusters.sort(key=lambda c: _ROLE_ORDER.get(c.role, 9))
        return clusters

    def calculate_cluster_density(
        self,
        members: List[Dict[str, Any]],
        max_members: int,
    ) -> float:
        """Density = member_count / max_members, clamped to [0, 1]."""
        if max_members <= 0:
            return 0.0
        return min(1.0, len(members) / max_members)

    def validate_cluster_balance(self, plan: ClusterPlan) -> Dict[str, Any]:
        """
        Warn when the primary cluster is absent or too sparse.
        """
        warnings: List[str] = []
        primary_clusters = [c for c in plan.clusters if c.role == "primary"]
        if not primary_clusters:
            warnings.append("No primary cluster — hero zone will lack visual weight.")
        for c in primary_clusters:
            if c.density < 0.33:
                warnings.append(
                    f"Primary cluster {c.cluster_type!r} is under-populated "
                    f"(density {c.density:.2f})."
                )
        return {"warnings": warnings}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cluster_role(cluster_type: str) -> str:
    primary_types  = {"machinery_cluster"}
    detail_types   = {"pipe_cluster"}
    atm_types      = {"atmosphere_cluster"}
    if cluster_type in primary_types:
        return "primary"
    if cluster_type in detail_types:
        return "detail"
    if cluster_type in atm_types:
        return "atmosphere"
    return "support"


def _best_zone(cluster_type: str, env_plan: EnvironmentPlan) -> str:
    preferred = _CLUSTER_ZONES.get(cluster_type, "midground")
    if preferred in env_plan.zones:
        return preferred
    # Fallback to first available zone
    if env_plan.zones:
        return next(iter(env_plan.zones))
    return preferred


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[AssetClusteringEngine] = None
_INSTANCE_LOCK = threading.Lock()


def get_asset_clustering_engine() -> AssetClusteringEngine:
    """Return the module-level singleton AssetClusteringEngine."""
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = AssetClusteringEngine()
    return _INSTANCE


def reset_asset_clustering_engine_for_tests() -> None:
    """Replace the singleton.  For test isolation only."""
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
