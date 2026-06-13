"""
Material Knowledge (Tier 14)
============================
Understands material semantics from asset metadata using deterministic
keyword inference tables. No AI, no randomness, no Houdini dependency.
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_MATERIAL_TYPE_KEYWORDS: Dict[str, List[str]] = {
    "oxidized_pipe":     ["pipe", "tube", "duct", "conduit", "plumbing", "nozzle", "valve"],
    "rusty_metal":       ["rust", "rusty", "corroded", "oxidized", "corrode", "flaking"],
    "painted_metal":     ["painted", "paint", "coating", "coated", "enamel"],
    "polished_steel":    ["mirror", "chrome", "gleaming", "reflective", "polished"],
    "brushed_steel":     ["brushed", "stainless", "satin", "directional"],
    "weathered_concrete":["weathered_concrete", "cracked_concrete", "aged_concrete", "spalling", "crack"],
    "concrete":          ["concrete", "cement", "slab", "pillar", "column", "foundation"],
    "industrial_rubber": ["rubber", "grip", "mat", "gasket", "seal", "tire", "wheel", "bumper"],
    "plastic":           ["plastic", "resin", "polymer", "casing", "housing", "cover"],
    "glass":             ["glass", "window", "pane", "viewport", "transparent", "glazing"],
    "emissive_panel":    ["light", "glow", "emissive", "display", "screen", "monitor", "led", "neon", "indicator", "lamp"],
    "painted_wall":      ["wall", "bulkhead", "partition", "interior", "facade"],
    "industrial_metal":  ["metal", "steel", "iron", "machinery", "machine", "equipment", "gear", "tank", "frame", "strut", "beam", "industrial", "structure"],
}

_AGE_KEYWORDS: Dict[str, List[str]] = {
    "ancient": ["ancient", "ruin", "artifact", "archaic", "prehistoric", "historic"],
    "aged":    ["aged", "old", "worn", "weathered", "rusty", "corroded", "vintage", "antique", "decay", "decayed", "decrepit", "abandoned"],
    "new":     ["new", "pristine", "clean", "modern", "fresh", "shiny", "mint"],
}

_CONDITION_KEYWORDS: Dict[str, List[str]] = {
    "corroded": ["corroded", "rust", "rusty", "oxidized", "eaten", "decay", "verdigris"],
    "damaged":  ["damaged", "cracked", "broken", "smashed", "dented", "torn", "fractured", "shattered"],
    "worn":     ["worn", "weathered", "aged", "old", "scuffed", "scratched", "dirty", "grimy", "stained"],
    "pristine": ["pristine", "clean", "new", "polished", "perfect", "mint", "spotless"],
}

_CONTEXT_ENVIRONMENT_KEYWORDS: Dict[str, List[str]] = {
    "industrial_hangar":  ["hangar", "warehouse", "factory", "industrial", "facility"],
    "robotics_lab":       ["lab", "laboratory", "robotics", "research", "workshop"],
    "control_room":       ["control", "ops", "operation", "monitoring", "command"],
    "sci_fi_corridor":    ["corridor", "hallway", "passage", "sci-fi", "scifi", "futuristic"],
    "abandoned_factory":  ["abandoned", "derelict", "ruin", "decay", "forgotten"],
}


def _keyword_score(text: str, keywords: List[str]) -> int:
    t = text.lower()
    return sum(1 for kw in keywords if kw in t)


def _extract_text(asset_dict: Dict[str, Any]) -> str:
    parts = [
        str(asset_dict.get("name", "")),
        str(asset_dict.get("description", "")),
        " ".join(str(t) for t in (asset_dict.get("tags") or [])),
        str(asset_dict.get("category", "")),
    ]
    return " ".join(parts)


@dataclass
class MaterialInference:
    inference_id: str = field(default_factory=lambda: f"inf_{uuid.uuid4().hex[:8]}")
    asset_id: str = ""
    material_type: str = "industrial_metal"
    surface_age: str = "aged"
    surface_condition: str = "worn"
    material_context: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.5
    inferred_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "inference_id":     str(self.inference_id),
            "asset_id":         str(self.asset_id),
            "material_type":    str(self.material_type),
            "surface_age":      str(self.surface_age),
            "surface_condition": str(self.surface_condition),
            "material_context": dict(self.material_context),
            "confidence":       float(self.confidence),
            "inferred_at":      float(self.inferred_at),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MaterialInference":
        d = d if isinstance(d, dict) else {}
        return cls(
            inference_id=str(d.get("inference_id") or f"inf_{uuid.uuid4().hex[:8]}"),
            asset_id=str(d.get("asset_id", "")),
            material_type=str(d.get("material_type", "industrial_metal")),
            surface_age=str(d.get("surface_age", "aged")),
            surface_condition=str(d.get("surface_condition", "worn")),
            material_context=dict(d.get("material_context") or {}),
            confidence=float(d.get("confidence") or 0.5),
            inferred_at=float(d.get("inferred_at") or time.time()),
        )


class MaterialKnowledge:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._infer_count = 0

    def infer_material_type(self, asset_dict: Dict[str, Any]) -> str:
        try:
            asset_dict = asset_dict if isinstance(asset_dict, dict) else {}
            text = _extract_text(asset_dict)
            best_type = "industrial_metal"
            best_score = 0
            # Iterate in a fixed order for determinism
            for mat_type in sorted(_MATERIAL_TYPE_KEYWORDS.keys()):
                score = _keyword_score(text, _MATERIAL_TYPE_KEYWORDS[mat_type])
                if score > best_score:
                    best_score = score
                    best_type = mat_type
            return best_type
        except Exception:
            return "industrial_metal"

    def infer_surface_age(self, asset_dict: Dict[str, Any]) -> str:
        try:
            asset_dict = asset_dict if isinstance(asset_dict, dict) else {}
            text = _extract_text(asset_dict)
            best_age = "aged"
            best_score = 0
            for age in ("ancient", "new", "aged"):
                score = _keyword_score(text, _AGE_KEYWORDS[age])
                if score > best_score:
                    best_score = score
                    best_age = age
            return best_age
        except Exception:
            return "aged"

    def infer_surface_condition(self, asset_dict: Dict[str, Any]) -> str:
        try:
            asset_dict = asset_dict if isinstance(asset_dict, dict) else {}
            text = _extract_text(asset_dict)
            best_cond = "worn"
            best_score = 0
            for cond in ("corroded", "damaged", "pristine", "worn"):
                score = _keyword_score(text, _CONDITION_KEYWORDS[cond])
                if score > best_score:
                    best_score = score
                    best_cond = cond
            return best_cond
        except Exception:
            return "worn"

    def infer_material_context(self, asset_dict: Dict[str, Any]) -> Dict[str, Any]:
        try:
            asset_dict = asset_dict if isinstance(asset_dict, dict) else {}
            text = _extract_text(asset_dict)
            # Detect environment
            env = "industrial_hangar"
            best_score = 0
            for env_name in sorted(_CONTEXT_ENVIRONMENT_KEYWORDS.keys()):
                score = _keyword_score(text, _CONTEXT_ENVIRONMENT_KEYWORDS[env_name])
                if score > best_score:
                    best_score = score
                    env = env_name
            # Derive usage from material type
            mat_type = self.infer_material_type(asset_dict)
            usage_map = {
                "glass": "transparent_surface",
                "emissive_panel": "lighting_element",
                "industrial_rubber": "floor_covering",
                "concrete": "structural",
                "weathered_concrete": "structural",
                "painted_wall": "wall_surface",
                "oxidized_pipe": "infrastructure",
            }
            usage = usage_map.get(mat_type, "set_dressing")
            # Style
            age = self.infer_surface_age(asset_dict)
            style_map = {"ancient": "archaic", "new": "modern", "aged": "industrial"}
            style = style_map.get(age, "industrial")
            return {"environment": env, "usage": usage, "style": style}
        except Exception:
            return {"environment": "industrial_hangar", "usage": "set_dressing", "style": "industrial"}

    def build_material_profile(self, asset_dict: Dict[str, Any]) -> MaterialInference:
        try:
            asset_dict = asset_dict if isinstance(asset_dict, dict) else {}
            mat_type  = self.infer_material_type(asset_dict)
            age       = self.infer_surface_age(asset_dict)
            condition = self.infer_surface_condition(asset_dict)
            context   = self.infer_material_context(asset_dict)
            text = _extract_text(asset_dict)
            # Confidence: 0.5 base + 0.1 per matched keyword group (max 0.9)
            matched_groups = sum(
                1 for kws in _MATERIAL_TYPE_KEYWORDS.values()
                if _keyword_score(text, kws) > 0
            )
            confidence = min(0.9, 0.5 + matched_groups * 0.05)
            with self._lock:
                self._infer_count += 1
            return MaterialInference(
                asset_id=str(asset_dict.get("asset_id", "")),
                material_type=mat_type,
                surface_age=age,
                surface_condition=condition,
                material_context=context,
                confidence=confidence,
            )
        except Exception:
            return MaterialInference()


_INSTANCE: Optional[MaterialKnowledge] = None
_INSTANCE_LOCK = threading.Lock()


def get_material_knowledge() -> MaterialKnowledge:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = MaterialKnowledge()
    return _INSTANCE


def reset_material_knowledge_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
