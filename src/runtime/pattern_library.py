"""
Pattern Library (Tier 5 — Production Knowledge System)
=======================================================
Stores and ranks reusable production patterns for lighting, camera,
atmosphere, composition, and full scene configurations.

Built-in patterns cover the five canonical Vibrante environments.
Custom patterns can be registered at runtime. Pattern usage is tracked
(success/failure counts) to power ranked recommendations.

DESIGN RULE: NO bridge calls. No persistence of patterns (patterns are
             code-defined + optionally user-registered in-memory).
             Usage counters are in-memory only.

Pattern types:
    lighting_pattern     — lighting style configuration
    camera_pattern       — camera mode and focus configuration
    atmosphere_pattern   — fog / particle / volumetric configuration
    composition_pattern  — zone assignments and balance rules
    scene_pattern        — full combined scene configuration

Public API:
    PatternLibrary
        .register_pattern(pattern_id, pattern_type, data) -> str
        .get_pattern(pattern_id) -> dict | None
        .search_patterns(scene_type=None, pattern_type=None, tags=None) -> list
        .rank_patterns(patterns) -> list
        .record_pattern_success(pattern_id, scene_type=None) -> None
        .record_pattern_failure(pattern_id, scene_type=None) -> None
        .stats() -> dict

    get_pattern_library() -> PatternLibrary   (singleton)
    reset_pattern_library_for_tests()
"""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, List, Optional

_VALID_PATTERN_TYPES = frozenset({
    "lighting_pattern",
    "camera_pattern",
    "atmosphere_pattern",
    "composition_pattern",
    "scene_pattern",
})

# ---------------------------------------------------------------------------
# Built-in patterns
# ---------------------------------------------------------------------------

_BUILTIN_PATTERNS: List[Dict[str, Any]] = [
    # Industrial Hangar — full scene pattern
    {
        "pattern_id":   "industrial_hangar_v1",
        "pattern_type": "scene_pattern",
        "scene_type":   "industrial_hangar",
        "lighting":     "cinematic_industrial",
        "camera":       "cinematic_push_in",
        "atmosphere":   "industrial_fog",
        "composition":  "hero_center_with_depth",
        "description":  "Proven cinematic industrial hangar configuration.",
        "tags":         ["industrial", "cinematic", "production"],
        "builtin":      True,
    },
    {
        "pattern_id":   "robotics_lab_v1",
        "pattern_type": "scene_pattern",
        "scene_type":   "robotics_lab",
        "lighting":     "cold_scifi",
        "camera":       "cinematic_push_in",
        "atmosphere":   "volumetric_scifi",
        "composition":  "hero_workbench",
        "description":  "Clean technical robotics lab with hero workbench focus.",
        "tags":         ["scifi", "technical", "robotics"],
        "builtin":      True,
    },
    {
        "pattern_id":   "scifi_corridor_v1",
        "pattern_type": "scene_pattern",
        "scene_type":   "sci_fi_corridor",
        "lighting":     "bladerunner_noir",
        "camera":       "atmospheric_tracking",
        "atmosphere":   "volumetric_scifi",
        "composition":  "corridor_path",
        "description":  "Atmospheric sci-fi corridor with neon noir lighting.",
        "tags":         ["scifi", "noir", "atmospheric"],
        "builtin":      True,
    },
    {
        "pattern_id":   "control_room_v1",
        "pattern_type": "scene_pattern",
        "scene_type":   "cinematic_control_room",
        "lighting":     "warm_control_room",
        "camera":       "orbital_reveal",
        "atmosphere":   "cold_atmosphere",
        "composition":  "central_console",
        "description":  "Command center with screen-glow lighting and orbital camera.",
        "tags":         ["control", "command", "dramatic"],
        "builtin":      True,
    },
    {
        "pattern_id":   "abandoned_factory_v1",
        "pattern_type": "scene_pattern",
        "scene_type":   "abandoned_factory",
        "lighting":     "atmospheric_lab",
        "camera":       "hero_focus",
        "atmosphere":   "dusty_hangar",
        "composition":  "rubble_center",
        "description":  "Post-industrial abandoned space with decay atmosphere.",
        "tags":         ["industrial", "decay", "atmospheric"],
        "builtin":      True,
    },
    # Lighting patterns
    {
        "pattern_id":   "cinematic_industrial_lighting",
        "pattern_type": "lighting_pattern",
        "scene_type":   None,
        "lighting":     "cinematic_industrial",
        "description":  "High-contrast industrial key with strong rim separation.",
        "tags":         ["cinematic", "industrial", "high_contrast"],
        "builtin":      True,
    },
    {
        "pattern_id":   "bladerunner_noir_lighting",
        "pattern_type": "lighting_pattern",
        "scene_type":   None,
        "lighting":     "bladerunner_noir",
        "description":  "Low-key noir with coloured practicals and deep shadows.",
        "tags":         ["noir", "dramatic", "moody"],
        "builtin":      True,
    },
    # Camera patterns
    {
        "pattern_id":   "hero_push_in",
        "pattern_type": "camera_pattern",
        "scene_type":   None,
        "camera":       "cinematic_push_in",
        "description":  "Slow deliberate push toward the hero asset.",
        "tags":         ["cinematic", "hero", "push"],
        "builtin":      True,
    },
    {
        "pattern_id":   "orbital_reveal_camera",
        "pattern_type": "camera_pattern",
        "scene_type":   None,
        "camera":       "orbital_reveal",
        "description":  "Circling orbital reveal — best for environments and sets.",
        "tags":         ["reveal", "orbital", "environment"],
        "builtin":      True,
    },
    # Atmosphere patterns
    {
        "pattern_id":   "depth_fog_atmosphere",
        "pattern_type": "atmosphere_pattern",
        "scene_type":   None,
        "atmosphere":   "cinematic_depth_fog",
        "description":  "Exponential depth fog for maximum zone separation.",
        "tags":         ["depth", "fog", "cinematic"],
        "builtin":      True,
    },
    {
        "pattern_id":   "volumetric_scifi_atmosphere",
        "pattern_type": "atmosphere_pattern",
        "scene_type":   None,
        "atmosphere":   "volumetric_scifi",
        "description":  "Light haze with visible light shafts for sci-fi environments.",
        "tags":         ["scifi", "volumetric", "light_shafts"],
        "builtin":      True,
    },
]


class PatternLibrary:
    """Registry of production patterns with usage-based ranking."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # pattern_id → pattern dict (with _success_count, _failure_count)
        self._patterns: Dict[str, Dict[str, Any]] = {}
        self._register_builtins()

    def _register_builtins(self) -> None:
        for p in _BUILTIN_PATTERNS:
            entry = dict(p)
            entry["_success_count"] = 0
            entry["_failure_count"] = 0
            entry["_registered_at"] = 0.0  # builtins have epoch timestamp
            self._patterns[p["pattern_id"]] = entry

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_pattern(
        self,
        pattern_id: str,
        pattern_type: str,
        data: Dict[str, Any],
    ) -> str:
        """Register a custom pattern.

        Args:
            pattern_id:   Unique string id (e.g. "my_studio_v1").
            pattern_type: One of the _VALID_PATTERN_TYPES strings.
            data:         Pattern configuration dict.

        Returns:
            pattern_id

        Raises:
            ValueError: If pattern_type is invalid.
        """
        if pattern_type not in _VALID_PATTERN_TYPES:
            raise ValueError(
                f"Invalid pattern_type {pattern_type!r}. "
                f"Must be one of: {sorted(_VALID_PATTERN_TYPES)}"
            )
        entry = dict(data)
        entry["pattern_id"]      = pattern_id
        entry["pattern_type"]    = pattern_type
        entry["builtin"]         = False
        entry["_success_count"]  = 0
        entry["_failure_count"]  = 0
        entry["_registered_at"]  = time.time()
        with self._lock:
            self._patterns[pattern_id] = entry
        return pattern_id

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def get_pattern(self, pattern_id: str) -> Optional[Dict[str, Any]]:
        """Return a copy of the pattern or None if not found."""
        with self._lock:
            p = self._patterns.get(pattern_id)
        return dict(p) if p else None

    def search_patterns(
        self,
        scene_type: Optional[str] = None,
        pattern_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Return matching patterns (copies), ranked by score descending."""
        with self._lock:
            patterns = list(self._patterns.values())

        results = []
        for p in patterns:
            if scene_type is not None:
                pt = p.get("scene_type")
                if pt is not None and pt != scene_type:
                    continue
            if pattern_type is not None and p.get("pattern_type") != pattern_type:
                continue
            if tags:
                p_tags = set(p.get("tags") or [])
                if not any(t in p_tags for t in tags):
                    continue
            results.append(dict(p))

        return self.rank_patterns(results)

    def rank_patterns(self, patterns: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Rank patterns by production score (success_rate then recency).

        Builtins start with a synthetic 0.5 base score.
        """
        def _score(p: Dict[str, Any]) -> float:
            s = p.get("_success_count", 0)
            f = p.get("_failure_count", 0)
            total = s + f
            if total == 0:
                base = 0.5 if p.get("builtin") else 0.3
            else:
                base = s / total
            # Small recency bonus (newer = +0.01) capped
            age = time.time() - p.get("_registered_at", 0.0)
            recency = max(0.0, 0.01 - age / 1e8)
            return base + recency

        return sorted(patterns, key=_score, reverse=True)

    # ------------------------------------------------------------------
    # Usage tracking
    # ------------------------------------------------------------------

    def record_pattern_success(
        self, pattern_id: str, scene_type: Optional[str] = None
    ) -> None:
        """Increment the success counter for a pattern."""
        with self._lock:
            if pattern_id in self._patterns:
                self._patterns[pattern_id]["_success_count"] += 1

    def record_pattern_failure(
        self, pattern_id: str, scene_type: Optional[str] = None
    ) -> None:
        """Increment the failure counter for a pattern."""
        with self._lock:
            if pattern_id in self._patterns:
                self._patterns[pattern_id]["_failure_count"] += 1

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._patterns)
            builtin = sum(1 for p in self._patterns.values() if p.get("builtin"))
            by_type: Dict[str, int] = {}
            for p in self._patterns.values():
                pt = p.get("pattern_type", "unknown")
                by_type[pt] = by_type.get(pt, 0) + 1
        return {
            "total_patterns":   total,
            "builtin_patterns": builtin,
            "custom_patterns":  total - builtin,
            "by_type":          by_type,
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[PatternLibrary] = None
_INSTANCE_LOCK = threading.Lock()


def get_pattern_library() -> PatternLibrary:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = PatternLibrary()
    return _INSTANCE


def reset_pattern_library_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
