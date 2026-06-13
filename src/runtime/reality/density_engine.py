"""
density_engine.py — §54 Reality Intelligence (Tier 15.0+)
==========================================================
Environment Density Rule. Minimum density depends on room area:

    density_score = placed_assets / room_area

Targets:
    small room  (< 150 m²)  → 10–20 assets
    medium room (< 600 m²)  → 20–40 assets
    large room  (≥ 600 m²)  → 40–80 assets

Empty rooms are invalid. Large rooms require more assets.

Public API:
    DensityResult
    EnvironmentDensityEngine
    get_environment_density_engine()
    reset_environment_density_engine_for_tests()
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.runtime.reality.reality_scene_model import parse_scene

_SMALL_AREA  = 150.0   # m²
_MEDIUM_AREA = 600.0   # m²

_TARGETS: Dict[str, Any] = {
    "small":  (10, 20),
    "medium": (20, 40),
    "large":  (40, 80),
}


@dataclass
class DensityResult:
    environment:   str = ""
    room_area:     float = 0.0
    room_class:    str = "small"
    asset_count:   int = 0
    density_score: float = 0.0
    target_min:    int = 10
    target_max:    int = 20
    is_empty:      bool = True
    density_ok:    bool = False
    overcrowded:   bool = False
    findings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "environment":   self.environment,
            "room_area":     round(self.room_area, 4),
            "room_class":    self.room_class,
            "asset_count":   self.asset_count,
            "density_score": round(self.density_score, 4),
            "target_min":    self.target_min,
            "target_max":    self.target_max,
            "is_empty":      self.is_empty,
            "density_ok":    self.density_ok,
            "overcrowded":   self.overcrowded,
            "findings":      list(self.findings),
        }


class EnvironmentDensityEngine:
    """Computes density_score and validates it against room-class targets."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def evaluate(self, scene_layout: Dict[str, Any]) -> DensityResult:
        try:
            return self._evaluate(scene_layout)
        except Exception as exc:
            r = DensityResult()
            r.findings.append(f"EnvironmentDensityEngine internal error: {exc}")
            return r

    def _evaluate(self, scene_layout: Dict[str, Any]) -> DensityResult:
        snap = parse_scene(scene_layout)
        result = DensityResult(environment=snap.environment)
        result.room_area = snap.room_area
        result.asset_count = len(snap.assets)
        result.is_empty = result.asset_count == 0
        if result.room_area > 0:
            result.density_score = result.asset_count / result.room_area

        if result.room_area < _SMALL_AREA:
            result.room_class = "small"
        elif result.room_area < _MEDIUM_AREA:
            result.room_class = "medium"
        else:
            result.room_class = "large"
        result.target_min, result.target_max = _TARGETS[result.room_class]

        if result.is_empty:
            result.findings.append(
                "EMPTY_ROOM: the room contains no assets — empty rooms are invalid (§54)"
            )
        elif result.asset_count < result.target_min:
            result.findings.append(
                f"UNDER_DRESSED: {result.asset_count} assets in a "
                f"{result.room_class} room ({result.room_area:.0f} m²) — "
                f"target is {result.target_min}–{result.target_max}"
            )
        elif result.asset_count > result.target_max:
            result.overcrowded = True
            result.findings.append(
                f"OVERCROWDED: {result.asset_count} assets exceed the "
                f"{result.room_class}-room target of {result.target_max} — "
                "consider thinning set dressing"
            )

        result.density_ok = (
            not result.is_empty and result.asset_count >= result.target_min
        )
        return result


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[EnvironmentDensityEngine] = None
_lock = threading.Lock()


def get_environment_density_engine() -> EnvironmentDensityEngine:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = EnvironmentDensityEngine()
    return _instance


def reset_environment_density_engine_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
