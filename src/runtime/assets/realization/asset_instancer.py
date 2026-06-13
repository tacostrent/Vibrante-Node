"""
Asset Instancer (Tier 13)
==========================
Creates instance plans from asset descriptors and transform data.
No real scene operations — generates InstancePlan descriptors.

DESIGN RULES:
  1. No bridge calls, no Houdini imports.
  2. No randomness — same input → same output.
  3. Never raises in public methods.
  4. Singleton pattern.

Public API:
    AssetInstance
    InstancePlan
    AssetInstancer
    get_asset_instancer()
    reset_asset_instancer_for_tests()
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_TRANSFORM: Dict[str, float] = {
    "tx": 0.0, "ty": 0.0, "tz": 0.0,
    "rx": 0.0, "ry": 0.0, "rz": 0.0,
    "sx": 1.0, "sy": 1.0, "sz": 1.0,
}


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class AssetInstance:
    """A single placed instance of an asset."""

    instance_id:  str              = field(default_factory=lambda: f"inst_{uuid.uuid4().hex[:10]}")
    asset_id:     str              = ""
    asset_name:   str              = ""
    transform:    Dict[str, float] = field(default_factory=dict)
    zone:         str              = "hero_zone"
    metadata:     Dict[str, Any]   = field(default_factory=dict)
    created_at:   float            = field(default_factory=time.time)

    def __post_init__(self) -> None:
        # Ensure transform has all required keys with defaults
        for k, v in _DEFAULT_TRANSFORM.items():
            self.transform.setdefault(k, v)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "asset_id":    self.asset_id,
            "asset_name":  self.asset_name,
            "transform":   dict(self.transform),
            "zone":        self.zone,
            "metadata":    dict(self.metadata),
            "created_at":  self.created_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AssetInstance":
        inst = cls(
            instance_id=str(d.get("instance_id", f"inst_{uuid.uuid4().hex[:10]}")),
            asset_id=str(d.get("asset_id", "")),
            asset_name=str(d.get("asset_name", "")),
            transform=dict(d.get("transform") or {}),
            zone=str(d.get("zone", "hero_zone")),
            metadata=dict(d.get("metadata") or {}),
            created_at=float(d.get("created_at") or time.time()),
        )
        return inst


@dataclass
class InstancePlan:
    """Plan for creating multiple instances of an asset."""

    plan_id:        str                  = field(default_factory=lambda: f"iplan_{uuid.uuid4().hex[:10]}")
    asset_id:       str                  = ""
    instances:      List[AssetInstance]  = field(default_factory=list)
    instance_count: int                  = 0
    zone:           str                  = "hero_zone"
    errors:         List[str]            = field(default_factory=list)
    created_at:     float                = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id":        self.plan_id,
            "asset_id":       self.asset_id,
            "instances":      [i.to_dict() for i in self.instances],
            "instance_count": self.instance_count,
            "zone":           self.zone,
            "errors":         list(self.errors),
            "created_at":     self.created_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "InstancePlan":
        instances = [
            AssetInstance.from_dict(i) if isinstance(i, dict) else i
            for i in (d.get("instances") or [])
        ]
        return cls(
            plan_id=str(d.get("plan_id", f"iplan_{uuid.uuid4().hex[:10]}")),
            asset_id=str(d.get("asset_id", "")),
            instances=instances,
            instance_count=int(d.get("instance_count", len(instances))),
            zone=str(d.get("zone", "hero_zone")),
            errors=list(d.get("errors") or []),
            created_at=float(d.get("created_at") or time.time()),
        )


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class AssetInstancer:
    """
    Creates instance plans with transforms.
    All instances are deterministic from input transforms.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._instance_count = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_instance(
        self,
        asset_dict: Dict[str, Any],
        transform: Optional[Dict[str, float]] = None,
        zone: str = "hero_zone",
    ) -> AssetInstance:
        """Create a single asset instance. Never raises."""
        try:
            return self._make_instance(asset_dict, transform or {}, zone)
        except Exception as exc:
            safe = asset_dict if isinstance(asset_dict, dict) else {}
            return AssetInstance(
                asset_id=str(safe.get("asset_id", "")),
                asset_name=str(safe.get("name", "")),
                zone=zone,
                metadata={"error": str(exc)},
            )

    def create_instances(
        self,
        asset_dict: Dict[str, Any],
        transforms: List[Dict[str, float]],
        zone: str = "hero_zone",
    ) -> InstancePlan:
        """Create an InstancePlan for multiple transforms. Never raises."""
        try:
            instances = [
                self._make_instance(asset_dict, t, zone)
                for t in transforms
            ]
            asset_id = str(asset_dict.get("asset_id", ""))
            return InstancePlan(
                asset_id=asset_id,
                instances=instances,
                instance_count=len(instances),
                zone=zone,
            )
        except Exception as exc:
            return InstancePlan(
                asset_id=str(asset_dict.get("asset_id", "")),
                errors=[f"Instance creation failed: {exc}"],
            )

    def build_instance_metadata(self, asset_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Extract instance metadata from asset dict."""
        return {
            "category":  str(asset_dict.get("category", "")),
            "style":     str(asset_dict.get("style", "")),
            "provider":  str(asset_dict.get("provider", "")),
            "face_count": asset_dict.get("face_count", 0),
            "is_animated": bool(asset_dict.get("is_animated", False)),
        }

    def validate_instance(self, instance: AssetInstance) -> Dict[str, Any]:
        """Validate an AssetInstance."""
        errors:   List[str] = []
        warnings: List[str] = []
        if not instance.asset_id:
            errors.append("Instance has no asset_id.")
        transform = instance.transform
        for key in ("tx", "ty", "tz", "rx", "ry", "rz", "sx", "sy", "sz"):
            if key not in transform:
                warnings.append(f"Transform missing key '{key}' — will use default.")
        return {
            "valid":    len(errors) == 0,
            "errors":   errors,
            "warnings": warnings,
        }

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {"instance_count": self._instance_count}

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _make_instance(
        self,
        asset_dict: Dict[str, Any],
        transform: Dict[str, float],
        zone: str,
    ) -> AssetInstance:
        # Build complete transform with defaults
        full_transform = dict(_DEFAULT_TRANSFORM)
        full_transform.update({
            k: float(v) for k, v in transform.items()
            if k in _DEFAULT_TRANSFORM
        })
        metadata = self.build_instance_metadata(asset_dict)

        with self._lock:
            self._instance_count += 1

        return AssetInstance(
            asset_id=str(asset_dict.get("asset_id", "")),
            asset_name=str(asset_dict.get("name", "")),
            transform=full_transform,
            zone=zone,
            metadata=metadata,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[AssetInstancer] = None
_INSTANCE_LOCK = threading.Lock()


def get_asset_instancer() -> AssetInstancer:
    """Return the module-level singleton AssetInstancer."""
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = AssetInstancer()
    return _INSTANCE


def reset_asset_instancer_for_tests() -> None:
    """Replace the singleton. For test isolation only."""
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
