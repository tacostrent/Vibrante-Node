"""
Lookdev Patterns (Tier 14)
==========================
Stores and retrieves reusable lookdev recipes: environment-matched
material sets proven in production. Deterministic, thread-safe.
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_BUILTIN_PATTERNS: List[Dict[str, Any]] = [
    {
        "name": "industrial_hangar_lookdev",
        "environment": "industrial_hangar",
        "materials": ["industrial_metal", "weathered_concrete", "industrial_rubber", "painted_metal", "oxidized_pipe"],
        "description": "Heavy industry hangar: concrete floors, metal walls, pipe infrastructure.",
        "tags": ["industrial", "hangar", "heavy", "concrete", "metal"],
    },
    {
        "name": "robotics_lab_lookdev",
        "environment": "robotics_lab",
        "materials": ["brushed_steel", "plastic", "glass", "emissive_panel", "painted_metal"],
        "description": "Clean robotics facility: brushed steel, plastic panels, glowing displays.",
        "tags": ["robotics", "lab", "clean", "sci-fi", "tech"],
    },
    {
        "name": "control_room_lookdev",
        "environment": "control_room",
        "materials": ["painted_wall", "plastic", "glass", "emissive_panel", "brushed_steel"],
        "description": "Operations control room: matte walls, display screens, clean steel.",
        "tags": ["control", "room", "screens", "operations", "tech"],
    },
    {
        "name": "sci_fi_corridor_lookdev",
        "environment": "sci_fi_corridor",
        "materials": ["polished_steel", "emissive_panel", "glass", "painted_metal", "industrial_rubber"],
        "description": "Sci-fi corridor: polished surfaces, glowing panels, rubber floor.",
        "tags": ["sci-fi", "corridor", "futuristic", "clean", "polished"],
    },
    {
        "name": "abandoned_factory_lookdev",
        "environment": "abandoned_factory",
        "materials": ["rusty_metal", "weathered_concrete", "oxidized_pipe", "industrial_rubber", "painted_metal"],
        "description": "Derelict factory: heavy rust, cracked concrete, corroded pipes.",
        "tags": ["abandoned", "factory", "derelict", "rust", "decay", "industrial"],
    },
]

_ENV_KEYWORDS: Dict[str, List[str]] = {
    "industrial_hangar":  ["hangar", "warehouse", "factory", "industrial", "facility", "plant"],
    "robotics_lab":       ["lab", "laboratory", "robotics", "research", "workshop", "tech"],
    "control_room":       ["control", "ops", "operation", "monitoring", "command", "command_center"],
    "sci_fi_corridor":    ["corridor", "hallway", "passage", "sci-fi", "scifi", "futuristic", "ship"],
    "abandoned_factory":  ["abandoned", "derelict", "ruin", "decay", "forgotten", "decrepit"],
}


@dataclass
class LookdevPattern:
    pattern_id: str = field(default_factory=lambda: f"pat_{uuid.uuid4().hex[:8]}")
    name: str = ""
    environment: str = ""
    materials: List[str] = field(default_factory=list)
    description: str = ""
    tags: List[str] = field(default_factory=list)
    usage_count: int = 0
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern_id":  str(self.pattern_id),
            "name":        str(self.name),
            "environment": str(self.environment),
            "materials":   list(self.materials),
            "description": str(self.description),
            "tags":        list(self.tags),
            "usage_count": int(self.usage_count),
            "created_at":  float(self.created_at),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "LookdevPattern":
        d = d if isinstance(d, dict) else {}
        return cls(
            pattern_id=str(d.get("pattern_id") or f"pat_{uuid.uuid4().hex[:8]}"),
            name=str(d.get("name", "")),
            environment=str(d.get("environment", "")),
            materials=list(d.get("materials") or []),
            description=str(d.get("description", "")),
            tags=list(d.get("tags") or []),
            usage_count=int(d.get("usage_count") or 0),
            created_at=float(d.get("created_at") or time.time()),
        )


class LookdevPatterns:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._patterns: Dict[str, LookdevPattern] = {}
        self._register_count = 0
        self._register_builtins()

    def _register_builtins(self) -> None:
        for p in _BUILTIN_PATTERNS:
            pattern = LookdevPattern(
                pattern_id=f"builtin_{p['name']}",
                name=p["name"],
                environment=p["environment"],
                materials=list(p["materials"]),
                description=p["description"],
                tags=list(p["tags"]),
            )
            self._patterns[pattern.pattern_id] = pattern

    def register_pattern(
        self,
        name: str,
        environment: str,
        materials: List[str],
        description: str = "",
        tags: Optional[List[str]] = None,
    ) -> LookdevPattern:
        pattern = LookdevPattern(
            name=str(name),
            environment=str(environment),
            materials=list(materials),
            description=str(description),
            tags=list(tags or []),
        )
        with self._lock:
            self._patterns[pattern.pattern_id] = pattern
            self._register_count += 1
        return pattern

    def get_pattern(self, pattern_id: str) -> Optional[LookdevPattern]:
        with self._lock:
            return self._patterns.get(pattern_id)

    def search_patterns(self, query: str = "", environment: str = "") -> List[LookdevPattern]:
        with self._lock:
            results = list(self._patterns.values())
        q = str(query or "").lower().strip()
        env = str(environment or "").lower().strip()
        if q:
            results = [
                p for p in results
                if q in p.name.lower()
                or q in p.description.lower()
                or any(q in t.lower() for t in p.tags)
                or q in p.environment.lower()
            ]
        if env:
            results = [p for p in results if p.environment.lower() == env]
        return sorted(results, key=lambda p: p.name)

    def rank_patterns(self, asset_dict: Dict[str, Any]) -> List[LookdevPattern]:
        """Rank patterns by environment + material affinity against asset metadata."""
        try:
            asset_dict = asset_dict if isinstance(asset_dict, dict) else {}
            text = " ".join([
                str(asset_dict.get("name", "")),
                str(asset_dict.get("description", "")),
                " ".join(str(t) for t in (asset_dict.get("tags") or [])),
                str(asset_dict.get("category", "")),
                str(asset_dict.get("environment", "")),
            ]).lower()

            scored: List[tuple[float, LookdevPattern]] = []
            with self._lock:
                patterns = list(self._patterns.values())

            for p in patterns:
                score = 0.0
                # Environment keyword match
                env_kws = _ENV_KEYWORDS.get(p.environment, [p.environment])
                for kw in env_kws:
                    if kw in text:
                        score += 0.4
                        break
                # Tag match
                for tag in p.tags:
                    if tag.lower() in text:
                        score += 0.1
                # Direct environment name match
                if p.environment.lower().replace("_", " ") in text:
                    score += 0.3
                scored.append((score, p))

            scored.sort(key=lambda x: (-x[0], x[1].name))
            return [p for _, p in scored]
        except Exception:
            with self._lock:
                return sorted(self._patterns.values(), key=lambda p: p.name)


_INSTANCE: Optional[LookdevPatterns] = None
_INSTANCE_LOCK = threading.Lock()


def get_lookdev_patterns() -> LookdevPatterns:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = LookdevPatterns()
    return _INSTANCE


def reset_lookdev_patterns_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
