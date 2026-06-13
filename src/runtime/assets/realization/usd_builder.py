"""
USD Builder (Tier 13)
======================
Generates USD-ready asset hierarchy, metadata, and build descriptors.
No real USD SDK usage — generates descriptive data structures.

DESIGN RULES:
  1. No bridge calls, no USD SDK imports.
  2. No randomness — same input → same output.
  3. Never raises in public methods.
  4. Singleton pattern.

Public API:
    USD_SCHEMA_VERSION
    UsdAsset
    UsdBuildResult
    UsdBuilder
    get_usd_builder()
    reset_usd_builder_for_tests()
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

USD_SCHEMA_VERSION = "1.0"

_USD_CATEGORY_TYPES: Dict[str, str] = {
    "vehicle":      "UsdGeomMesh",
    "character":    "UsdGeomMesh",
    "prop":         "UsdGeomMesh",
    "structure":    "UsdGeomMesh",
    "electronic":   "UsdGeomMesh",
    "machinery":    "UsdGeomMesh",
    "robot":        "UsdGeomMesh",
    "terrain":      "UsdGeomMesh",
    "vegetation":   "UsdGeomMesh",
    "material":     "UsdShadeMaterial",
    "hdri":         "UsdLuxDomeLight",
    "environment":  "UsdGeomMesh",
}

_DEFAULT_USD_TYPE = "UsdGeomMesh"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class UsdAsset:
    """USD-ready asset descriptor."""

    asset_id:      str              = ""
    asset_name:    str              = ""
    usd_path:      str              = ""
    usd_variant:   str              = "default"
    hierarchy:     Dict[str, Any]   = field(default_factory=dict)
    materials:     List[Dict[str, Any]] = field(default_factory=list)
    metadata:      Dict[str, Any]   = field(default_factory=dict)
    schema_version: str             = USD_SCHEMA_VERSION
    built_at:      float            = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id":      self.asset_id,
            "asset_name":    self.asset_name,
            "usd_path":      self.usd_path,
            "usd_variant":   self.usd_variant,
            "hierarchy":     dict(self.hierarchy),
            "materials":     [dict(m) for m in self.materials],
            "metadata":      dict(self.metadata),
            "schema_version": self.schema_version,
            "built_at":      self.built_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "UsdAsset":
        return cls(
            asset_id=str(d.get("asset_id", "")),
            asset_name=str(d.get("asset_name", "")),
            usd_path=str(d.get("usd_path", "")),
            usd_variant=str(d.get("usd_variant", "default")),
            hierarchy=dict(d.get("hierarchy") or {}),
            materials=list(d.get("materials") or []),
            metadata=dict(d.get("metadata") or {}),
            schema_version=str(d.get("schema_version", USD_SCHEMA_VERSION)),
            built_at=float(d.get("built_at") or time.time()),
        )


@dataclass
class UsdBuildResult:
    """Result of building a USD asset descriptor."""

    ok:        bool        = True
    asset:     Optional[UsdAsset] = None
    errors:    List[str]   = field(default_factory=list)
    warnings:  List[str]   = field(default_factory=list)
    built_at:  float       = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok":       self.ok,
            "asset":    self.asset.to_dict() if self.asset else None,
            "errors":   list(self.errors),
            "warnings": list(self.warnings),
            "built_at": self.built_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "UsdBuildResult":
        asset_data = d.get("asset")
        asset = UsdAsset.from_dict(asset_data) if isinstance(asset_data, dict) else None
        return cls(
            ok=bool(d.get("ok", True)),
            asset=asset,
            errors=list(d.get("errors") or []),
            warnings=list(d.get("warnings") or []),
            built_at=float(d.get("built_at") or time.time()),
        )


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class UsdBuilder:
    """
    Generates USD-ready asset hierarchy and metadata descriptors.
    No real USD SDK — descriptive data only.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._build_count = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_usd_asset(
        self,
        asset_dict: Dict[str, Any],
        materials: Optional[List[Dict[str, Any]]] = None,
    ) -> UsdBuildResult:
        """Build a UsdAsset descriptor. Never raises."""
        try:
            return self._do_build(asset_dict, materials or [])
        except Exception as exc:
            return UsdBuildResult(
                ok=False,
                errors=[f"USD build failed: {exc if asset_dict is not None else 'asset_dict is None'}"],
            )

    def build_usd_metadata(self, asset_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Build USD metadata dict from asset fields."""
        asset_id   = str(asset_dict.get("asset_id", ""))
        asset_name = str(asset_dict.get("name", asset_id))
        category   = str(asset_dict.get("category", ""))
        provider   = str(asset_dict.get("provider", ""))
        return {
            "asset_identifier": f"{provider}/{asset_id}" if provider else asset_id,
            "asset_name":       asset_name,
            "category":         category,
            "provider":         provider,
            "schema_version":   USD_SCHEMA_VERSION,
            "usd_type":         _USD_CATEGORY_TYPES.get(category, _DEFAULT_USD_TYPE),
            "has_variants":     False,
            "is_assembly":      False,
            "created_at":       time.time(),
        }

    def build_usd_hierarchy(self, asset_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Build a USD-style hierarchy description."""
        asset_name = str(asset_dict.get("name", asset_dict.get("asset_id", "asset")))
        category   = str(asset_dict.get("category", ""))
        usd_type   = _USD_CATEGORY_TYPES.get(category, _DEFAULT_USD_TYPE)
        safe_name  = asset_name.replace(" ", "_").replace("-", "_")

        return {
            "root":      f"/{safe_name}",
            "xform":     f"/{safe_name}/xform",
            "mesh":      f"/{safe_name}/xform/mesh",
            "materials": f"/{safe_name}/materials",
            "schema":    usd_type,
            "variants":  [],
        }

    def validate_usd_asset(self, usd_asset: UsdAsset) -> Dict[str, Any]:
        """Validate a UsdAsset descriptor."""
        errors:   List[str] = []
        warnings: List[str] = []
        if not usd_asset.asset_id:
            errors.append("UsdAsset has no asset_id.")
        if not usd_asset.hierarchy:
            warnings.append("UsdAsset has no hierarchy — will use default paths.")
        if not usd_asset.usd_path:
            warnings.append("UsdAsset has no usd_path — path will be derived at realization.")
        return {
            "valid":    len(errors) == 0,
            "errors":   errors,
            "warnings": warnings,
        }

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {"build_count": self._build_count}

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _do_build(
        self,
        asset_dict: Dict[str, Any],
        materials: List[Dict[str, Any]],
    ) -> UsdBuildResult:
        asset_id   = str(asset_dict.get("asset_id", "") or str(uuid.uuid4()))
        asset_name = str(asset_dict.get("name", asset_id))
        safe_name  = asset_name.replace(" ", "_").replace("-", "_")
        usd_path   = f"/{safe_name}"

        hierarchy = self.build_usd_hierarchy(asset_dict)
        metadata  = self.build_usd_metadata(asset_dict)

        usd_asset = UsdAsset(
            asset_id=asset_id,
            asset_name=asset_name,
            usd_path=usd_path,
            hierarchy=hierarchy,
            materials=list(materials),
            metadata=metadata,
        )

        with self._lock:
            self._build_count += 1

        return UsdBuildResult(ok=True, asset=usd_asset)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[UsdBuilder] = None
_INSTANCE_LOCK = threading.Lock()


def get_usd_builder() -> UsdBuilder:
    """Return the module-level singleton UsdBuilder."""
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = UsdBuilder()
    return _INSTANCE


def reset_usd_builder_for_tests() -> None:
    """Replace the singleton. For test isolation only."""
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
