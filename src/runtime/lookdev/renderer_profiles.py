"""
Renderer Profiles (Tier 14)
===========================
Renderer-aware material class mappings for Arnold, Karma, and USD Preview Surface.
Deterministic, thread-safe, no renderer dependency (planning only).
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

SUPPORTED_RENDERERS = frozenset({"arnold", "karma", "usd_preview_surface"})

_MATERIAL_CLASS_MAP: Dict[str, Dict[str, str]] = {
    "arnold": {
        "default":          "standard_surface",
        "industrial_metal": "standard_surface",
        "painted_metal":    "standard_surface",
        "rusty_metal":      "standard_surface",
        "brushed_steel":    "standard_surface",
        "polished_steel":   "standard_surface",
        "concrete":         "standard_surface",
        "weathered_concrete":"standard_surface",
        "industrial_rubber":"standard_surface",
        "plastic":          "standard_surface",
        "glass":            "standard_surface",
        "emissive_panel":   "standard_surface",
        "painted_wall":     "standard_surface",
        "oxidized_pipe":    "standard_surface",
    },
    "karma": {
        "default":          "mtlxstandard_surface",
        "industrial_metal": "mtlxstandard_surface",
        "painted_metal":    "mtlxstandard_surface",
        "rusty_metal":      "mtlxstandard_surface",
        "brushed_steel":    "mtlxstandard_surface",
        "polished_steel":   "mtlxstandard_surface",
        "concrete":         "mtlxstandard_surface",
        "weathered_concrete":"mtlxstandard_surface",
        "industrial_rubber":"mtlxstandard_surface",
        "plastic":          "mtlxstandard_surface",
        "glass":            "mtlxstandard_surface",
        "emissive_panel":   "mtlxstandard_surface",
        "painted_wall":     "mtlxstandard_surface",
        "oxidized_pipe":    "mtlxstandard_surface",
    },
    "usd_preview_surface": {
        "default":          "UsdPreviewSurface",
        "industrial_metal": "UsdPreviewSurface",
        "painted_metal":    "UsdPreviewSurface",
        "rusty_metal":      "UsdPreviewSurface",
        "brushed_steel":    "UsdPreviewSurface",
        "polished_steel":   "UsdPreviewSurface",
        "concrete":         "UsdPreviewSurface",
        "weathered_concrete":"UsdPreviewSurface",
        "industrial_rubber":"UsdPreviewSurface",
        "plastic":          "UsdPreviewSurface",
        "glass":            "UsdPreviewSurface",
        "emissive_panel":   "UsdPreviewSurface",
        "painted_wall":     "UsdPreviewSurface",
        "oxidized_pipe":    "UsdPreviewSurface",
    },
}

_INPUT_NAME_MAP: Dict[str, Dict[str, str]] = {
    "arnold": {
        "base_color":  "base_color",
        "roughness":   "specular_roughness",
        "metallic":    "metalness",
        "normal":      "normal",
        "emission":    "emission_color",
        "displacement":"disp_map",
        "opacity":     "opacity",
    },
    "karma": {
        "base_color":  "base_color",
        "roughness":   "specular_roughness",
        "metallic":    "metalness",
        "normal":      "normal",
        "emission":    "emission_color",
        "displacement":"displacement",
        "opacity":     "opacity",
    },
    "usd_preview_surface": {
        "base_color":  "diffuseColor",
        "roughness":   "roughness",
        "metallic":    "metallic",
        "normal":      "normal",
        "emission":    "emissiveColor",
        "displacement":"",
        "opacity":     "opacity",
    },
}


@dataclass
class RendererProfile:
    renderer: str = "usd_preview_surface"
    material_class: str = "UsdPreviewSurface"
    properties: Dict[str, Any] = field(default_factory=dict)
    supports_displacement: bool = False
    supports_subsurface: bool = False
    supported_maps: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "renderer":             str(self.renderer),
            "material_class":       str(self.material_class),
            "properties":           dict(self.properties),
            "supports_displacement": bool(self.supports_displacement),
            "supports_subsurface":   bool(self.supports_subsurface),
            "supported_maps":        list(self.supported_maps),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RendererProfile":
        d = d if isinstance(d, dict) else {}
        return cls(
            renderer=str(d.get("renderer", "usd_preview_surface")),
            material_class=str(d.get("material_class", "UsdPreviewSurface")),
            properties=dict(d.get("properties") or {}),
            supports_displacement=bool(d.get("supports_displacement", False)),
            supports_subsurface=bool(d.get("supports_subsurface", False)),
            supported_maps=list(d.get("supported_maps") or []),
        )


_BUILTIN_PROFILES: Dict[str, RendererProfile] = {
    "arnold": RendererProfile(
        renderer="arnold",
        material_class="standard_surface",
        properties={
            "base": 1.0,
            "base_color": [0.8, 0.8, 0.8, 1.0],
            "specular": 1.0,
            "specular_roughness": 0.5,
            "metalness": 0.0,
            "coat": 0.0,
            "emission": 0.0,
            "emission_color": [1.0, 1.0, 1.0],
            "subsurface": 0.0,
            "opacity": [1.0, 1.0, 1.0],
        },
        supports_displacement=True,
        supports_subsurface=True,
        supported_maps=[
            "base_color", "specular_roughness", "metalness",
            "normal", "displacement", "emission_color", "opacity",
        ],
    ),
    "karma": RendererProfile(
        renderer="karma",
        material_class="mtlxstandard_surface",
        properties={
            "base_color": [0.8, 0.8, 0.8, 1.0],
            "specular_roughness": 0.5,
            "metalness": 0.0,
            "emission_color": [0.0, 0.0, 0.0],
            "subsurface": 0.0,
            "opacity": 1.0,
        },
        supports_displacement=True,
        supports_subsurface=True,
        supported_maps=[
            "base_color", "specular_roughness", "metalness",
            "normal", "displacement", "emission_color", "opacity",
        ],
    ),
    "usd_preview_surface": RendererProfile(
        renderer="usd_preview_surface",
        material_class="UsdPreviewSurface",
        properties={
            "diffuseColor": [0.8, 0.8, 0.8],
            "roughness": 0.5,
            "metallic": 0.0,
            "opacity": 1.0,
            "emissiveColor": [0.0, 0.0, 0.0],
            "ior": 1.5,
            "useSpecularWorkflow": 0,
        },
        supports_displacement=False,
        supports_subsurface=False,
        supported_maps=["diffuseColor", "roughness", "metallic", "normal", "opacity"],
    ),
}


class RendererProfiles:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._query_count = 0

    def get_profile(self, renderer: str) -> RendererProfile:
        try:
            renderer = str(renderer or "usd_preview_surface").lower().strip()
            with self._lock:
                self._query_count += 1
            if renderer in _BUILTIN_PROFILES:
                p = _BUILTIN_PROFILES[renderer]
                return RendererProfile(
                    renderer=p.renderer,
                    material_class=p.material_class,
                    properties=dict(p.properties),
                    supports_displacement=p.supports_displacement,
                    supports_subsurface=p.supports_subsurface,
                    supported_maps=list(p.supported_maps),
                )
            # Unknown renderer — return USD as safe fallback
            p = _BUILTIN_PROFILES["usd_preview_surface"]
            return RendererProfile(
                renderer=renderer,
                material_class=p.material_class,
                properties=dict(p.properties),
                supports_displacement=p.supports_displacement,
                supports_subsurface=p.supports_subsurface,
                supported_maps=list(p.supported_maps),
            )
        except Exception:
            return RendererProfile()

    def map_material(self, material_name: str, renderer: str) -> Dict[str, Any]:
        try:
            renderer = str(renderer or "usd_preview_surface").lower().strip()
            material_name = str(material_name or "").lower().strip()
            if renderer not in SUPPORTED_RENDERERS:
                renderer = "usd_preview_surface"
            class_map = _MATERIAL_CLASS_MAP.get(renderer, _MATERIAL_CLASS_MAP["usd_preview_surface"])
            mat_class = class_map.get(material_name, class_map.get("default", "UsdPreviewSurface"))
            input_map = _INPUT_NAME_MAP.get(renderer, _INPUT_NAME_MAP["usd_preview_surface"])
            return {
                "renderer":          renderer,
                "material_name":     material_name,
                "material_class":    mat_class,
                "network_type":      "material" if renderer == "arnold" else "matnet",
                "base_color_input":  input_map.get("base_color", "diffuseColor"),
                "roughness_input":   input_map.get("roughness", "roughness"),
                "metallic_input":    input_map.get("metallic", "metallic"),
                "normal_input":      input_map.get("normal", "normal"),
                "emission_input":    input_map.get("emission", "emissiveColor"),
                "mapped_at":         time.time(),
            }
        except Exception:
            return {
                "renderer": "usd_preview_surface",
                "material_name": str(material_name or ""),
                "material_class": "UsdPreviewSurface",
                "network_type": "matnet",
                "base_color_input": "diffuseColor",
                "roughness_input": "roughness",
                "metallic_input": "metallic",
                "normal_input": "normal",
                "emission_input": "emissiveColor",
                "mapped_at": time.time(),
            }

    def validate_renderer_support(self, renderer: str) -> bool:
        try:
            return str(renderer or "").lower().strip() in SUPPORTED_RENDERERS
        except Exception:
            return False


_INSTANCE: Optional[RendererProfiles] = None
_INSTANCE_LOCK = threading.Lock()


def get_renderer_profiles() -> RendererProfiles:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = RendererProfiles()
    return _INSTANCE


def reset_renderer_profiles_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
