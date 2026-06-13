"""
Asset Material Mapper (Tier 13)
================================
Maps asset material metadata to renderer-specific material profiles.
No real shader creation — generates MaterialProfile descriptors.

DESIGN RULES:
  1. No bridge calls, no Houdini imports.
  2. No randomness — same input → same output.
  3. Never raises in public methods.
  4. Singleton pattern.

Public API:
    SUPPORTED_RENDERERS
    MaterialProfile
    MaterialMappingResult
    AssetMaterialMapper
    get_asset_material_mapper()
    reset_asset_material_mapper_for_tests()
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

SUPPORTED_RENDERERS = frozenset({
    "arnold",
    "usd_preview_surface",
    "generic_pbr",
    "karma",
})

# Default material profile values per renderer
_RENDERER_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "arnold": {
        "material_type":  "standard_surface",
        "base_color":     [0.8, 0.8, 0.8, 1.0],
        "roughness":      0.5,
        "metallic":       0.0,
        "normal_map":     "",
        "opacity":        1.0,
        "emission":       [0.0, 0.0, 0.0],
    },
    "usd_preview_surface": {
        "material_type":  "UsdPreviewSurface",
        "base_color":     [0.8, 0.8, 0.8, 1.0],
        "roughness":      0.5,
        "metallic":       0.0,
        "normal_map":     "",
        "opacity":        1.0,
        "emission":       [0.0, 0.0, 0.0],
    },
    "generic_pbr": {
        "material_type":  "pbr",
        "base_color":     [0.8, 0.8, 0.8, 1.0],
        "roughness":      0.5,
        "metallic":       0.0,
        "normal_map":     "",
        "opacity":        1.0,
        "emission":       [0.0, 0.0, 0.0],
    },
    "karma": {
        "material_type":  "karma_physical",
        "base_color":     [0.8, 0.8, 0.8, 1.0],
        "roughness":      0.5,
        "metallic":       0.0,
        "normal_map":     "",
        "opacity":        1.0,
        "emission":       [0.0, 0.0, 0.0],
    },
}


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class MaterialProfile:
    """Renderer-specific material descriptor."""

    material_id:   str              = field(default_factory=lambda: f"mat_{uuid.uuid4().hex[:8]}")
    name:          str              = "default_material"
    renderer:      str              = "usd_preview_surface"
    base_color:    List[float]      = field(default_factory=lambda: [0.8, 0.8, 0.8, 1.0])
    roughness:     float            = 0.5
    metallic:      float            = 0.0
    normal_map:    str              = ""
    opacity:       float            = 1.0
    emission:      List[float]      = field(default_factory=lambda: [0.0, 0.0, 0.0])
    material_type: str              = "pbr"
    properties:    Dict[str, Any]   = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "material_id":   self.material_id,
            "name":          self.name,
            "renderer":      self.renderer,
            "base_color":    list(self.base_color),
            "roughness":     self.roughness,
            "metallic":      self.metallic,
            "normal_map":    self.normal_map,
            "opacity":       self.opacity,
            "emission":      list(self.emission),
            "material_type": self.material_type,
            "properties":    dict(self.properties),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MaterialProfile":
        return cls(
            material_id=str(d.get("material_id", f"mat_{uuid.uuid4().hex[:8]}")),
            name=str(d.get("name", "default_material")),
            renderer=str(d.get("renderer", "usd_preview_surface")),
            base_color=list(d.get("base_color") or [0.8, 0.8, 0.8, 1.0]),
            roughness=float(d.get("roughness", 0.5)),
            metallic=float(d.get("metallic", 0.0)),
            normal_map=str(d.get("normal_map", "")),
            opacity=float(d.get("opacity", 1.0)),
            emission=list(d.get("emission") or [0.0, 0.0, 0.0]),
            material_type=str(d.get("material_type", "pbr")),
            properties=dict(d.get("properties") or {}),
        )


@dataclass
class MaterialMappingResult:
    """Result of mapping asset materials to a target renderer."""

    ok:             bool                 = True
    asset_id:       str                  = ""
    asset_name:     str                  = ""
    renderer:       str                  = "usd_preview_surface"
    profiles:       List[MaterialProfile] = field(default_factory=list)
    material_count: int                  = 0
    errors:         List[str]            = field(default_factory=list)
    warnings:       List[str]            = field(default_factory=list)
    mapped_at:      float                = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok":             self.ok,
            "asset_id":       self.asset_id,
            "asset_name":     self.asset_name,
            "renderer":       self.renderer,
            "profiles":       [p.to_dict() for p in self.profiles],
            "material_count": self.material_count,
            "errors":         list(self.errors),
            "warnings":       list(self.warnings),
            "mapped_at":      self.mapped_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MaterialMappingResult":
        profiles = [
            MaterialProfile.from_dict(p) if isinstance(p, dict) else p
            for p in (d.get("profiles") or [])
        ]
        return cls(
            ok=bool(d.get("ok", True)),
            asset_id=str(d.get("asset_id", "")),
            asset_name=str(d.get("asset_name", "")),
            renderer=str(d.get("renderer", "usd_preview_surface")),
            profiles=profiles,
            material_count=int(d.get("material_count", len(profiles))),
            errors=list(d.get("errors") or []),
            warnings=list(d.get("warnings") or []),
            mapped_at=float(d.get("mapped_at") or time.time()),
        )


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class AssetMaterialMapper:
    """
    Maps asset material metadata to renderer-specific profiles.
    Supports arnold, usd_preview_surface, generic_pbr, karma.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._map_count = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def map_materials(
        self,
        asset_dict: Dict[str, Any],
        renderer: str = "usd_preview_surface",
    ) -> MaterialMappingResult:
        """Map asset materials to renderer-specific profiles. Never raises."""
        try:
            return self._do_map(asset_dict, renderer)
        except Exception as exc:
            safe = asset_dict if isinstance(asset_dict, dict) else {}
            return MaterialMappingResult(
                ok=False,
                asset_id=str(safe.get("asset_id", "")),
                asset_name=str(safe.get("name", "")),
                renderer=renderer,
                errors=[f"Material mapping failed: {exc}"],
            )

    def build_material_profile(
        self,
        material_dict: Dict[str, Any],
        renderer: str,
    ) -> MaterialProfile:
        """Build a MaterialProfile from a material dict and renderer."""
        defaults = _RENDERER_DEFAULTS.get(renderer, _RENDERER_DEFAULTS["usd_preview_surface"])
        return MaterialProfile(
            name=str(material_dict.get("name", "default_material")),
            renderer=renderer,
            base_color=list(material_dict.get("base_color") or defaults["base_color"]),
            roughness=float(material_dict.get("roughness", defaults["roughness"])),
            metallic=float(material_dict.get("metallic", defaults["metallic"])),
            normal_map=str(material_dict.get("normal_map", "")),
            opacity=float(material_dict.get("opacity", defaults["opacity"])),
            emission=list(material_dict.get("emission") or defaults["emission"]),
            material_type=str(material_dict.get("material_type", defaults["material_type"])),
            properties={
                k: v for k, v in material_dict.items()
                if k not in {
                    "name", "base_color", "roughness", "metallic",
                    "normal_map", "opacity", "emission", "material_type",
                }
            },
        )

    def validate_materials(self, result: MaterialMappingResult) -> Dict[str, Any]:
        """Validate a MaterialMappingResult."""
        errors:   List[str] = list(result.errors)
        warnings: List[str] = list(result.warnings)
        if not result.profiles:
            warnings.append("No material profiles generated — will use renderer default.")
        return {
            "valid":    len(errors) == 0 and result.ok,
            "errors":   errors,
            "warnings": warnings,
        }

    def extract_material_metadata(self, asset_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Extract raw material metadata from an asset dict."""
        return {
            "materials":   asset_dict.get("materials", []),
            "category":    asset_dict.get("category", ""),
            "style":       asset_dict.get("style", ""),
            "has_pbr":     bool(asset_dict.get("has_pbr", False)),
            "face_count":  asset_dict.get("face_count", 0),
        }

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {"map_count": self._map_count}

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _do_map(
        self,
        asset_dict: Dict[str, Any],
        renderer: str,
    ) -> MaterialMappingResult:
        asset_id   = str(asset_dict.get("asset_id", ""))
        asset_name = str(asset_dict.get("name", asset_id))
        warnings:  List[str] = []

        if renderer not in SUPPORTED_RENDERERS:
            warnings.append(
                f"Renderer '{renderer}' is not in SUPPORTED_RENDERERS "
                f"({sorted(SUPPORTED_RENDERERS)}) — using generic_pbr fallback."
            )
            renderer = "generic_pbr"

        # Extract materials
        raw_materials = asset_dict.get("materials", None)
        material_list: List[Dict[str, Any]] = []
        if isinstance(raw_materials, list):
            material_list = [m if isinstance(m, dict) else {"name": str(m)} for m in raw_materials]
        elif isinstance(raw_materials, dict):
            material_list = [raw_materials]
        else:
            # No materials — create a default one
            material_list = [{"name": f"{asset_name}_material"}]

        profiles = [self.build_material_profile(m, renderer) for m in material_list]

        with self._lock:
            self._map_count += 1

        return MaterialMappingResult(
            ok=True,
            asset_id=asset_id,
            asset_name=asset_name,
            renderer=renderer,
            profiles=profiles,
            material_count=len(profiles),
            warnings=warnings,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[AssetMaterialMapper] = None
_INSTANCE_LOCK = threading.Lock()


def get_asset_material_mapper() -> AssetMaterialMapper:
    """Return the module-level singleton AssetMaterialMapper."""
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = AssetMaterialMapper()
    return _INSTANCE


def reset_asset_material_mapper_for_tests() -> None:
    """Replace the singleton. For test isolation only."""
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
