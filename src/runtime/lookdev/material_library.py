"""
Material Library (Tier 14)
==========================
Stores reusable material definitions with categories, properties, and tags.
Deterministic, thread-safe, no Houdini dependency, no file I/O.
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

BUILTIN_MATERIAL_CATEGORIES = frozenset({
    "industrial_metal",
    "painted_metal",
    "rusty_metal",
    "brushed_steel",
    "polished_steel",
    "concrete",
    "weathered_concrete",
    "industrial_rubber",
    "plastic",
    "glass",
    "emissive_panel",
    "painted_wall",
    "oxidized_pipe",
})

_BUILTIN_MATERIALS: List[Dict[str, Any]] = [
    {
        "name": "industrial_metal",
        "category": "industrial_metal",
        "description": "Worn industrial metal with surface variation and scratches.",
        "properties": {
            "roughness": 0.65, "metallic": 1.0,
            "base_color": [0.45, 0.45, 0.45, 1.0],
            "normal_map": "normal_worn", "displacement": 0.02,
        },
        "tags": ["metal", "industrial", "worn", "aged"],
    },
    {
        "name": "painted_metal",
        "category": "painted_metal",
        "description": "Metal with painted surface, chipped edges, and slight rust.",
        "properties": {
            "roughness": 0.55, "metallic": 0.3,
            "base_color": [0.3, 0.35, 0.4, 1.0],
            "normal_map": "normal_paint_chips", "displacement": 0.01,
        },
        "tags": ["metal", "painted", "industrial"],
    },
    {
        "name": "rusty_metal",
        "category": "rusty_metal",
        "description": "Heavily corroded metal with flaking rust and rough surface.",
        "properties": {
            "roughness": 0.85, "metallic": 0.6,
            "base_color": [0.55, 0.25, 0.1, 1.0],
            "normal_map": "normal_rust", "displacement": 0.05,
        },
        "tags": ["metal", "rust", "corroded", "aged", "worn"],
    },
    {
        "name": "brushed_steel",
        "category": "brushed_steel",
        "description": "Brushed stainless steel with directional grain.",
        "properties": {
            "roughness": 0.3, "metallic": 1.0,
            "base_color": [0.7, 0.7, 0.72, 1.0],
            "anisotropy": 0.8, "displacement": 0.0,
        },
        "tags": ["metal", "steel", "clean", "industrial"],
    },
    {
        "name": "polished_steel",
        "category": "polished_steel",
        "description": "Mirror-finish polished steel.",
        "properties": {
            "roughness": 0.05, "metallic": 1.0,
            "base_color": [0.8, 0.8, 0.82, 1.0],
            "displacement": 0.0,
        },
        "tags": ["metal", "steel", "polished", "clean", "reflective"],
    },
    {
        "name": "concrete",
        "category": "concrete",
        "description": "Industrial poured concrete with surface variation.",
        "properties": {
            "roughness": 0.9, "metallic": 0.0,
            "base_color": [0.55, 0.52, 0.5, 1.0],
            "normal_map": "normal_concrete", "displacement": 0.03,
        },
        "tags": ["concrete", "industrial", "floor", "wall"],
    },
    {
        "name": "weathered_concrete",
        "category": "weathered_concrete",
        "description": "Aged concrete with stains, cracks, and spalling.",
        "properties": {
            "roughness": 0.95, "metallic": 0.0,
            "base_color": [0.45, 0.42, 0.4, 1.0],
            "normal_map": "normal_concrete_cracked", "displacement": 0.06,
        },
        "tags": ["concrete", "weathered", "aged", "cracked", "industrial"],
    },
    {
        "name": "industrial_rubber",
        "category": "industrial_rubber",
        "description": "Black industrial rubber with grip texture.",
        "properties": {
            "roughness": 0.95, "metallic": 0.0,
            "base_color": [0.08, 0.08, 0.08, 1.0],
            "normal_map": "normal_rubber_grip", "displacement": 0.01,
        },
        "tags": ["rubber", "industrial", "grip", "floor"],
    },
    {
        "name": "plastic",
        "category": "plastic",
        "description": "Matte industrial plastic with scuff marks.",
        "properties": {
            "roughness": 0.7, "metallic": 0.0,
            "base_color": [0.25, 0.25, 0.28, 1.0],
            "normal_map": "normal_plastic_scuff", "displacement": 0.0,
        },
        "tags": ["plastic", "industrial", "matte"],
    },
    {
        "name": "glass",
        "category": "glass",
        "description": "Clear industrial glass panel, slightly dirty.",
        "properties": {
            "roughness": 0.05, "metallic": 0.0,
            "base_color": [0.8, 0.9, 0.95, 0.15],
            "transmission": 0.92, "ior": 1.52,
        },
        "tags": ["glass", "transparent", "industrial"],
    },
    {
        "name": "emissive_panel",
        "category": "emissive_panel",
        "description": "Glowing control panel or status light surface.",
        "properties": {
            "roughness": 0.4, "metallic": 0.2,
            "base_color": [0.2, 0.8, 0.4, 1.0],
            "emission": [0.2, 0.8, 0.4], "emission_strength": 2.5,
        },
        "tags": ["emissive", "glow", "panel", "sci-fi", "control"],
    },
    {
        "name": "painted_wall",
        "category": "painted_wall",
        "description": "Interior painted wall with minor scuffs and variation.",
        "properties": {
            "roughness": 0.85, "metallic": 0.0,
            "base_color": [0.6, 0.58, 0.55, 1.0],
            "normal_map": "normal_wall_subtle", "displacement": 0.01,
        },
        "tags": ["wall", "painted", "interior"],
    },
    {
        "name": "oxidized_pipe",
        "category": "oxidized_pipe",
        "description": "Industrial pipe with heavy oxidation and verdigris.",
        "properties": {
            "roughness": 0.8, "metallic": 0.7,
            "base_color": [0.35, 0.45, 0.3, 1.0],
            "normal_map": "normal_oxidized", "displacement": 0.03,
        },
        "tags": ["metal", "pipe", "oxidized", "industrial", "aged"],
    },
]


@dataclass
class MaterialEntry:
    material_id: str = field(default_factory=lambda: f"mat_{uuid.uuid4().hex[:8]}")
    name: str = ""
    category: str = ""
    description: str = ""
    properties: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "material_id": str(self.material_id),
            "name": str(self.name),
            "category": str(self.category),
            "description": str(self.description),
            "properties": dict(self.properties),
            "tags": list(self.tags),
            "created_at": float(self.created_at),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MaterialEntry":
        d = d if isinstance(d, dict) else {}
        return cls(
            material_id=str(d.get("material_id") or f"mat_{uuid.uuid4().hex[:8]}"),
            name=str(d.get("name", "")),
            category=str(d.get("category", "")),
            description=str(d.get("description", "")),
            properties=dict(d.get("properties") or {}),
            tags=list(d.get("tags") or []),
            created_at=float(d.get("created_at") or time.time()),
        )


class MaterialLibrary:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._materials: Dict[str, MaterialEntry] = {}
        self._register_count = 0
        self._register_builtins()

    def _register_builtins(self) -> None:
        for m in _BUILTIN_MATERIALS:
            entry = MaterialEntry(
                material_id=f"builtin_{m['name']}",
                name=m["name"],
                category=m["category"],
                description=m["description"],
                properties=dict(m["properties"]),
                tags=list(m["tags"]),
            )
            self._materials[entry.material_id] = entry

    def register_material(
        self,
        name: str,
        category: str,
        description: str = "",
        properties: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
    ) -> MaterialEntry:
        entry = MaterialEntry(
            name=str(name),
            category=str(category),
            description=str(description),
            properties=dict(properties or {}),
            tags=list(tags or []),
        )
        with self._lock:
            self._materials[entry.material_id] = entry
            self._register_count += 1
        return entry

    def remove_material(self, material_id: str) -> bool:
        with self._lock:
            if material_id in self._materials:
                del self._materials[material_id]
                return True
            return False

    def get_material(self, material_id: str) -> Optional[MaterialEntry]:
        with self._lock:
            return self._materials.get(material_id)

    def search_materials(self, query: str = "", category: str = "") -> List[MaterialEntry]:
        with self._lock:
            results = list(self._materials.values())
        q = str(query or "").lower().strip()
        cat = str(category or "").lower().strip()
        if q:
            results = [
                m for m in results
                if q in m.name.lower()
                or q in m.description.lower()
                or any(q in t.lower() for t in m.tags)
            ]
        if cat:
            results = [m for m in results if m.category.lower() == cat]
        return sorted(results, key=lambda m: m.name)

    def list_materials(self, category: str = "") -> List[MaterialEntry]:
        return self.search_materials(category=category)

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._materials)
            by_category: Dict[str, int] = {}
            for m in self._materials.values():
                by_category[m.category] = by_category.get(m.category, 0) + 1
            return {
                "total_materials": total,
                "by_category": dict(sorted(by_category.items())),
                "register_calls": self._register_count,
            }


_INSTANCE: Optional[MaterialLibrary] = None
_INSTANCE_LOCK = threading.Lock()


def get_material_library() -> MaterialLibrary:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = MaterialLibrary()
    return _INSTANCE


def reset_material_library_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
