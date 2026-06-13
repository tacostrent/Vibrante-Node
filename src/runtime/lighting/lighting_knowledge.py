"""
Lighting Knowledge (Tier 15)
============================
Stores production lighting concepts: key, fill, rim, practical, atmospheric, and more.
Deterministic, thread-safe, no Houdini dependency, no file I/O.
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

BUILTIN_LIGHTING_ROLES = frozenset({
    "key",
    "fill",
    "rim",
    "bounce",
    "practical",
    "motivated",
    "atmospheric",
    "volumetric",
})

_BUILTIN_CONCEPTS: List[Dict[str, Any]] = [
    {
        "name": "key_light",
        "role": "key",
        "description": "Primary light source defining dominant illumination direction and establishing scene mood.",
        "properties": {
            "purpose": "dominant_illumination",
            "shadow_quality": "hard_or_soft",
            "typical_angle": "45_high",
            "intensity_range": [0.6, 1.0],
        },
        "tags": ["primary", "dominant", "directional", "shadow_casting"],
    },
    {
        "name": "fill_light",
        "role": "fill",
        "description": "Secondary light that reduces shadow harshness without eliminating it. Controls contrast ratio.",
        "properties": {
            "purpose": "shadow_fill",
            "ratio_to_key": 0.25,
            "soft": True,
            "intensity_range": [0.1, 0.4],
        },
        "tags": ["secondary", "soft", "contrast_control", "shadow_reduction"],
    },
    {
        "name": "rim_light",
        "role": "rim",
        "description": "Back or side light separating subject from background and defining silhouette.",
        "properties": {
            "purpose": "separation",
            "position": "behind_subject",
            "intensity_range": [0.3, 0.8],
        },
        "tags": ["back_light", "separation", "silhouette", "hero_definition"],
    },
    {
        "name": "bounce_light",
        "role": "bounce",
        "description": "Indirect light simulating reflection off floor, walls, or large surfaces.",
        "properties": {
            "purpose": "indirect_fill",
            "soft": True,
            "color_influenced_by": "surface",
            "intensity_range": [0.05, 0.3],
        },
        "tags": ["indirect", "reflected", "ambient", "soft"],
    },
    {
        "name": "practical_light",
        "role": "practical",
        "description": "Visible light source within scene: lamps, screens, neon signs, monitors.",
        "properties": {
            "purpose": "motivated_source",
            "visible_in_frame": True,
            "drives_motivated_light": True,
        },
        "tags": ["practical", "visible_source", "motivated", "environmental"],
    },
    {
        "name": "motivated_light",
        "role": "motivated",
        "description": "Invisible light justified by a visible practical source. Simulates spill from lamps, windows, screens.",
        "properties": {
            "purpose": "practical_simulation",
            "visible_in_frame": False,
            "justified_by": "practical_source",
            "intensity_range": [0.2, 0.9],
        },
        "tags": ["motivated", "practical_simulation", "justified", "spill"],
    },
    {
        "name": "atmospheric_light",
        "role": "atmospheric",
        "description": "Ambient environmental lighting establishing overall mood: overcast sky, environment bounce.",
        "properties": {
            "purpose": "ambient_mood",
            "color_drives_mood": True,
            "directionless": True,
            "intensity_range": [0.05, 0.4],
        },
        "tags": ["ambient", "environment", "mood", "atmospheric"],
    },
    {
        "name": "volumetric_light",
        "role": "volumetric",
        "description": "Light with visible atmosphere: god rays, fog shafts, smoke illumination.",
        "properties": {
            "purpose": "atmosphere_visibility",
            "requires_participating_medium": True,
            "depth_enhancing": True,
        },
        "tags": ["volumetric", "fog", "god_rays", "depth", "atmosphere"],
    },
    {
        "name": "window_light",
        "role": "motivated",
        "description": "Soft directional light entering through windows. Natural or architectural source.",
        "properties": {
            "purpose": "architectural_natural",
            "soft": True,
            "color_temperature_k": 5600,
            "typical_angle": "horizontal_side",
        },
        "tags": ["window", "natural", "architectural", "soft", "side_light"],
    },
    {
        "name": "industrial_fixture",
        "role": "practical",
        "description": "Overhead industrial lighting: fluorescent tubes, high-bay fixtures, warehouse lights.",
        "properties": {
            "purpose": "overhead_practical",
            "color_temperature_k": 4000,
            "typical_position": "overhead",
            "shadow_direction": "downward",
        },
        "tags": ["industrial", "overhead", "fluorescent", "fixture", "practical"],
    },
    {
        "name": "neon_source",
        "role": "practical",
        "description": "Colored neon or LED strip light adding color accent and atmosphere to sci-fi or urban scenes.",
        "properties": {
            "purpose": "color_accent",
            "saturated": True,
            "colors": ["cyan", "magenta", "red", "blue", "amber"],
            "intensity_range": [0.1, 0.5],
        },
        "tags": ["neon", "colored", "accent", "sci-fi", "cyberpunk", "urban"],
    },
    {
        "name": "emergency_light",
        "role": "practical",
        "description": "Red or amber emergency/warning lighting for tension or danger storytelling.",
        "properties": {
            "purpose": "dramatic_warning",
            "color": "red_or_amber",
            "animated": True,
            "intensity_range": [0.2, 0.6],
        },
        "tags": ["emergency", "danger", "tension", "red", "alarm", "warning"],
    },
    {
        "name": "moonlight",
        "role": "key",
        "description": "Soft cool directional light simulating moonlight for night exterior scenes.",
        "properties": {
            "purpose": "night_key",
            "color_temperature_k": 4100,
            "color_bias": "blue_cool",
            "intensity_range": [0.1, 0.4],
            "shadow_softness": "medium",
        },
        "tags": ["moonlight", "night", "exterior", "cool", "blue", "atmospheric"],
    },
    {
        "name": "sunlight",
        "role": "key",
        "description": "Hard directional sunlight for exterior or window-lit interior scenes.",
        "properties": {
            "purpose": "solar_key",
            "color_temperature_k": 5600,
            "hard_shadows": True,
            "intensity_range": [0.8, 1.0],
        },
        "tags": ["sunlight", "solar", "exterior", "warm", "hard", "directional"],
    },
]


@dataclass
class LightingConcept:
    concept_id: str = field(default_factory=lambda: f"lc_{uuid.uuid4().hex[:8]}")
    name: str = ""
    role: str = ""
    description: str = ""
    properties: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "concept_id":  str(self.concept_id),
            "name":        str(self.name),
            "role":        str(self.role),
            "description": str(self.description),
            "properties":  dict(self.properties),
            "tags":        list(self.tags),
            "created_at":  float(self.created_at),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "LightingConcept":
        d = d if isinstance(d, dict) else {}
        return cls(
            concept_id=str(d.get("concept_id") or f"lc_{uuid.uuid4().hex[:8]}"),
            name=str(d.get("name", "")),
            role=str(d.get("role", "")),
            description=str(d.get("description", "")),
            properties=dict(d.get("properties") or {}),
            tags=list(d.get("tags") or []),
            created_at=float(d.get("created_at") or time.time()),
        )


class LightingKnowledge:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._concepts: Dict[str, LightingConcept] = {}
        self._register_count = 0
        self._register_builtins()

    def _register_builtins(self) -> None:
        for c in _BUILTIN_CONCEPTS:
            concept = LightingConcept(
                concept_id=f"builtin_{c['name']}",
                name=c["name"],
                role=c["role"],
                description=c["description"],
                properties=dict(c["properties"]),
                tags=list(c["tags"]),
            )
            self._concepts[concept.concept_id] = concept

    def register_concept(
        self,
        name: str,
        role: str,
        description: str = "",
        properties: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
    ) -> LightingConcept:
        concept = LightingConcept(
            name=str(name),
            role=str(role),
            description=str(description),
            properties=dict(properties or {}),
            tags=list(tags or []),
        )
        with self._lock:
            self._concepts[concept.concept_id] = concept
            self._register_count += 1
        return concept

    def lookup_concept(self, name_or_id: str) -> Optional[LightingConcept]:
        key = str(name_or_id or "").strip().lower()
        with self._lock:
            if name_or_id in self._concepts:
                return self._concepts[name_or_id]
            builtin_id = f"builtin_{key}"
            if builtin_id in self._concepts:
                return self._concepts[builtin_id]
            for c in self._concepts.values():
                if c.name.lower() == key:
                    return c
        return None

    def recommend_concept(self, role: str = "", tags: Optional[List[str]] = None) -> List[LightingConcept]:
        r = str(role or "").lower().strip()
        search_tags = [t.lower() for t in (tags or [])]
        with self._lock:
            results = list(self._concepts.values())
        if r:
            results = [c for c in results if c.role.lower() == r]
        if search_tags:
            results = [
                c for c in results
                if any(t in [tag.lower() for tag in c.tags] for t in search_tags)
            ]
        return sorted(results, key=lambda c: c.name)

    def search_concepts(self, query: str = "", role: str = "") -> List[LightingConcept]:
        with self._lock:
            results = list(self._concepts.values())
        q = str(query or "").lower().strip()
        r = str(role or "").lower().strip()
        if q:
            results = [
                c for c in results
                if q in c.name.lower()
                or q in c.description.lower()
                or any(q in t.lower() for t in c.tags)
            ]
        if r:
            results = [c for c in results if c.role.lower() == r]
        return sorted(results, key=lambda c: c.name)

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._concepts)
            by_role: Dict[str, int] = {}
            for c in self._concepts.values():
                by_role[c.role] = by_role.get(c.role, 0) + 1
            return {
                "total_concepts":  total,
                "by_role":         dict(sorted(by_role.items())),
                "register_calls":  self._register_count,
            }


_INSTANCE: Optional[LightingKnowledge] = None
_INSTANCE_LOCK = threading.Lock()


def get_lighting_knowledge() -> LightingKnowledge:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = LightingKnowledge()
    return _INSTANCE


def reset_lighting_knowledge_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
