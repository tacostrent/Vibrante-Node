"""
Lighting Hierarchy Engine (Tier 15)
=====================================
Controls visual focus by building a lighting importance hierarchy.
Deterministic, thread-safe, no Houdini dependency.
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

HIERARCHY_ROLES = frozenset({"hero", "support", "background", "atmosphere"})

_ROLE_KEYWORDS: Dict[str, List[str]] = {
    "hero":       ["hero", "protagonist", "main_character", "subject", "primary", "focal", "lead"],
    "support":    ["support", "secondary", "companion", "assistant", "foreground_prop"],
    "background": ["background", "backdrop", "set", "environment_detail", "distant"],
    "atmosphere": ["atmosphere", "ambient", "fog", "haze", "sky", "volumetric", "particles"],
}

_IMPORTANCE_WEIGHTS: Dict[str, float] = {
    "hero":       1.0,
    "support":    0.6,
    "background": 0.3,
    "atmosphere": 0.15,
}

_LIGHTING_PRIORITY: Dict[str, Dict[str, Any]] = {
    "hero": {
        "rim_intensity_boost": 0.3,
        "key_target": True,
        "separate_from_background": True,
        "notes": "Maximum rim to separate from background. Key aimed directly at hero.",
    },
    "support": {
        "rim_intensity_boost": 0.1,
        "key_target": False,
        "separate_from_background": False,
        "notes": "Moderate fill. Key spill acceptable. No dedicated rim needed.",
    },
    "background": {
        "rim_intensity_boost": 0.0,
        "key_target": False,
        "separate_from_background": False,
        "notes": "Exposure lower than hero. Minimize competing detail. Reduce contrast.",
    },
    "atmosphere": {
        "rim_intensity_boost": 0.0,
        "key_target": False,
        "separate_from_background": False,
        "notes": "Volumetric lighting only. No hard directional lights needed.",
    },
}


@dataclass
class HierarchyEntry:
    entry_id: str = field(default_factory=lambda: f"he_{uuid.uuid4().hex[:8]}")
    subject: str = ""
    role: str = ""
    importance: float = 1.0
    lighting_priority: Dict[str, Any] = field(default_factory=dict)
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id":          str(self.entry_id),
            "subject":           str(self.subject),
            "role":              str(self.role),
            "importance":        float(self.importance),
            "lighting_priority": dict(self.lighting_priority),
            "notes":             str(self.notes),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "HierarchyEntry":
        d = d if isinstance(d, dict) else {}
        return cls(
            entry_id=str(d.get("entry_id") or f"he_{uuid.uuid4().hex[:8]}"),
            subject=str(d.get("subject", "")),
            role=str(d.get("role", "")),
            importance=float(d.get("importance") or 1.0),
            lighting_priority=dict(d.get("lighting_priority") or {}),
            notes=str(d.get("notes", "")),
        )


@dataclass
class FocusHierarchy:
    hierarchy_id: str = field(default_factory=lambda: f"fh_{uuid.uuid4().hex[:8]}")
    hero: List[HierarchyEntry] = field(default_factory=list)
    support: List[HierarchyEntry] = field(default_factory=list)
    background: List[HierarchyEntry] = field(default_factory=list)
    atmosphere: List[HierarchyEntry] = field(default_factory=list)
    built_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hierarchy_id": str(self.hierarchy_id),
            "hero":         [e.to_dict() for e in self.hero],
            "support":      [e.to_dict() for e in self.support],
            "background":   [e.to_dict() for e in self.background],
            "atmosphere":   [e.to_dict() for e in self.atmosphere],
            "built_at":     float(self.built_at),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "FocusHierarchy":
        d = d if isinstance(d, dict) else {}
        return cls(
            hierarchy_id=str(d.get("hierarchy_id") or f"fh_{uuid.uuid4().hex[:8]}"),
            hero=[HierarchyEntry.from_dict(e) for e in (d.get("hero") or [])],
            support=[HierarchyEntry.from_dict(e) for e in (d.get("support") or [])],
            background=[HierarchyEntry.from_dict(e) for e in (d.get("background") or [])],
            atmosphere=[HierarchyEntry.from_dict(e) for e in (d.get("atmosphere") or [])],
            built_at=float(d.get("built_at") or time.time()),
        )


def _infer_role(subject: str) -> str:
    """Infer hierarchy role from subject name/description."""
    text = str(subject or "").lower()
    for role, kws in _ROLE_KEYWORDS.items():
        if any(kw in text for kw in kws):
            return role
    return "support"


class LightingHierarchyEngine:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._build_count = 0

    def identify_hero_subject(self, subjects: List[Any]) -> Optional[str]:
        """Return the name of the most likely hero subject from a list."""
        try:
            subjects = subjects if isinstance(subjects, list) else []
            for s in subjects:
                name = str(s.get("name", s) if isinstance(s, dict) else s)
                if _infer_role(name) == "hero":
                    return name
            # Fallback: first subject is hero
            if subjects:
                s = subjects[0]
                return str(s.get("name", s) if isinstance(s, dict) else s)
            return None
        except Exception:
            return None

    def rank_importance(self, subjects: List[Any]) -> List[Dict[str, Any]]:
        """Return subjects sorted by lighting importance (hero first)."""
        try:
            subjects = subjects if isinstance(subjects, list) else []
            ranked = []
            for s in subjects:
                name = str(s.get("name", s) if isinstance(s, dict) else s)
                role = _infer_role(name)
                importance = _IMPORTANCE_WEIGHTS.get(role, 0.5)
                ranked.append({
                    "subject":    name,
                    "role":       role,
                    "importance": importance,
                })
            ranked.sort(key=lambda x: (-x["importance"], x["subject"]))
            return ranked
        except Exception:
            return []

    def build_focus_hierarchy(self, subjects: List[Any]) -> FocusHierarchy:
        """Build a FocusHierarchy from a list of subject names or dicts."""
        try:
            return self._do_build(subjects if isinstance(subjects, list) else [])
        except Exception as exc:
            return FocusHierarchy(atmosphere=[
                HierarchyEntry(subject="error", notes=f"build_focus_hierarchy error: {exc}")
            ])

    def _do_build(self, subjects: List[Any]) -> FocusHierarchy:
        hero_entries: List[HierarchyEntry] = []
        support_entries: List[HierarchyEntry] = []
        background_entries: List[HierarchyEntry] = []
        atmosphere_entries: List[HierarchyEntry] = []

        for s in subjects:
            name = str(s.get("name", s) if isinstance(s, dict) else s)
            role = _infer_role(name)
            importance = _IMPORTANCE_WEIGHTS.get(role, 0.5)
            priority = dict(_LIGHTING_PRIORITY.get(role, {}))
            entry = HierarchyEntry(
                subject=name,
                role=role,
                importance=importance,
                lighting_priority=priority,
                notes=priority.get("notes", ""),
            )
            if role == "hero":
                hero_entries.append(entry)
            elif role == "support":
                support_entries.append(entry)
            elif role == "background":
                background_entries.append(entry)
            else:
                atmosphere_entries.append(entry)

        # If no explicit hero, promote first support to hero
        if not hero_entries and support_entries:
            promoted = support_entries.pop(0)
            promoted.role = "hero"
            promoted.importance = 1.0
            promoted.lighting_priority = dict(_LIGHTING_PRIORITY["hero"])
            promoted.notes = "Promoted to hero — no explicit hero subject found. " + _LIGHTING_PRIORITY["hero"]["notes"]
            hero_entries.append(promoted)

        with self._lock:
            self._build_count += 1

        return FocusHierarchy(
            hero=hero_entries,
            support=support_entries,
            background=background_entries,
            atmosphere=atmosphere_entries,
        )

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            return {"build_calls": self._build_count}


_INSTANCE: Optional[LightingHierarchyEngine] = None
_INSTANCE_LOCK = threading.Lock()


def get_lighting_hierarchy_engine() -> LightingHierarchyEngine:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = LightingHierarchyEngine()
    return _INSTANCE


def reset_lighting_hierarchy_engine_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
