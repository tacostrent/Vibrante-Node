"""
Lighting Exposure Engine (Tier 15)
=====================================
Determines exposure strategy for cinematic lighting plans.
Deterministic, thread-safe, no Houdini dependency.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_EXPOSURE_PROFILES: Dict[str, Dict[str, Any]] = {
    "hopeful": {
        "ev_target":          0.7,
        "contrast_ratio":     "low",
        "dynamic_range_stops": 8.0,
        "shadow_detail":      "high",
        "highlight_detail":   "medium",
        "tone_mapping_notes": "Lift shadows. Protect highlights. Warm grade.",
    },
    "dramatic": {
        "ev_target":          0.0,
        "contrast_ratio":     "high",
        "dynamic_range_stops": 12.0,
        "shadow_detail":      "low",
        "highlight_detail":   "high",
        "tone_mapping_notes": "Crushed blacks. Open highlights. S-curve contrast.",
    },
    "tense": {
        "ev_target":          -0.5,
        "contrast_ratio":     "high",
        "dynamic_range_stops": 11.0,
        "shadow_detail":      "low",
        "highlight_detail":   "medium",
        "tone_mapping_notes": "Underexpose for threat. Preserve screen highlight specular.",
    },
    "dangerous": {
        "ev_target":          -2.0,
        "contrast_ratio":     "high",
        "dynamic_range_stops": 14.0,
        "shadow_detail":      "none",
        "highlight_detail":   "high",
        "tone_mapping_notes": "Near-black base. Only emergency lights visible as highlights.",
    },
    "mystical": {
        "ev_target":          -0.3,
        "contrast_ratio":     "medium",
        "dynamic_range_stops": 10.0,
        "shadow_detail":      "medium",
        "highlight_detail":   "high",
        "tone_mapping_notes": "Glow bloom on emissive sources. Soft shadow rolloff.",
    },
    "industrial": {
        "ev_target":          0.0,
        "contrast_ratio":     "high",
        "dynamic_range_stops": 12.0,
        "shadow_detail":      "low",
        "highlight_detail":   "medium",
        "tone_mapping_notes": "Hard industrial contrast. No lifted shadows. Exposed highlights OK.",
    },
    "clinical": {
        "ev_target":          0.5,
        "contrast_ratio":     "low",
        "dynamic_range_stops": 7.0,
        "shadow_detail":      "high",
        "highlight_detail":   "high",
        "tone_mapping_notes": "Near-linear tone map. No crush. Preserve all detail.",
    },
    "cinematic": {
        "ev_target":          0.0,
        "contrast_ratio":     "high",
        "dynamic_range_stops": 12.0,
        "shadow_detail":      "low",
        "highlight_detail":   "high",
        "tone_mapping_notes": "Film S-curve. Slight shadow lift (0.02 lift). Protect highlights.",
    },
}

_DEFAULT_EXPOSURE = {
    "ev_target":          0.0,
    "contrast_ratio":     "medium",
    "dynamic_range_stops": 10.0,
    "shadow_detail":      "medium",
    "highlight_detail":   "medium",
    "tone_mapping_notes": "Balanced exposure. No special treatment.",
}


@dataclass
class ExposureStrategy:
    mood: str = ""
    ev_target: float = 0.0
    contrast_ratio: str = "medium"
    dynamic_range_stops: float = 10.0
    shadow_detail: str = "medium"
    highlight_detail: str = "medium"
    tone_mapping_notes: str = ""
    built_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mood":                  str(self.mood),
            "ev_target":             float(self.ev_target),
            "contrast_ratio":        str(self.contrast_ratio),
            "dynamic_range_stops":   float(self.dynamic_range_stops),
            "shadow_detail":         str(self.shadow_detail),
            "highlight_detail":      str(self.highlight_detail),
            "tone_mapping_notes":    str(self.tone_mapping_notes),
            "built_at":              float(self.built_at),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ExposureStrategy":
        d = d if isinstance(d, dict) else {}
        return cls(
            mood=str(d.get("mood", "")),
            ev_target=float(d.get("ev_target") or 0.0),
            contrast_ratio=str(d.get("contrast_ratio", "medium")),
            dynamic_range_stops=float(d.get("dynamic_range_stops") or 10.0),
            shadow_detail=str(d.get("shadow_detail", "medium")),
            highlight_detail=str(d.get("highlight_detail", "medium")),
            tone_mapping_notes=str(d.get("tone_mapping_notes", "")),
            built_at=float(d.get("built_at") or time.time()),
        )


class LightingExposureEngine:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._recommend_count = 0

    def recommend_exposure(self, mood: str = "", environment: str = "") -> ExposureStrategy:
        """Return an ExposureStrategy for the given mood and/or environment."""
        try:
            key = str(mood or environment or "").lower().strip()
            profile = _EXPOSURE_PROFILES.get(key)
            if not profile:
                for k, p in _EXPOSURE_PROFILES.items():
                    if key in k or k in key:
                        profile = p
                        break
            if not profile:
                profile = _DEFAULT_EXPOSURE
            with self._lock:
                self._recommend_count += 1
            return ExposureStrategy(
                mood=key,
                ev_target=float(profile.get("ev_target", 0.0)),
                contrast_ratio=str(profile.get("contrast_ratio", "medium")),
                dynamic_range_stops=float(profile.get("dynamic_range_stops", 10.0)),
                shadow_detail=str(profile.get("shadow_detail", "medium")),
                highlight_detail=str(profile.get("highlight_detail", "medium")),
                tone_mapping_notes=str(profile.get("tone_mapping_notes", "")),
            )
        except Exception as exc:
            return ExposureStrategy(tone_mapping_notes=f"recommend_exposure error: {exc}")

    def recommend_contrast(self, mood: str = "") -> Dict[str, Any]:
        """Return contrast settings for the given mood."""
        try:
            strategy = self.recommend_exposure(mood=mood)
            ratio_labels = {"high": 8, "medium": 4, "low": 2}
            ratio = ratio_labels.get(strategy.contrast_ratio, 4)
            return {
                "contrast_ratio":  strategy.contrast_ratio,
                "stop_ratio":      ratio,
                "shadow_detail":   strategy.shadow_detail,
                "highlight_detail": strategy.highlight_detail,
                "notes":           strategy.tone_mapping_notes,
            }
        except Exception as exc:
            return {"contrast_ratio": "medium", "stop_ratio": 4, "notes": str(exc)}

    def recommend_dynamic_range(self, mood: str = "") -> Dict[str, Any]:
        """Return dynamic range recommendation for the given mood."""
        try:
            strategy = self.recommend_exposure(mood=mood)
            return {
                "dynamic_range_stops": strategy.dynamic_range_stops,
                "shadow_detail":       strategy.shadow_detail,
                "highlight_detail":    strategy.highlight_detail,
                "notes":               strategy.tone_mapping_notes,
            }
        except Exception as exc:
            return {"dynamic_range_stops": 10.0, "notes": str(exc)}

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "recommend_calls":  self._recommend_count,
                "known_profiles":   len(_EXPOSURE_PROFILES),
            }


_INSTANCE: Optional[LightingExposureEngine] = None
_INSTANCE_LOCK = threading.Lock()


def get_lighting_exposure_engine() -> LightingExposureEngine:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = LightingExposureEngine()
    return _INSTANCE


def reset_lighting_exposure_engine_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
