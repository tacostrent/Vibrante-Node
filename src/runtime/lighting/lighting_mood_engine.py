"""
Lighting Mood Engine (Tier 15)
===============================
Infers emotional lighting mood from intent and builds mood profiles.
Deterministic, thread-safe, no Houdini dependency.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_MOOD_PROFILES: Dict[str, Dict[str, Any]] = {
    "hopeful": {
        "temperature":   "warm",
        "temperature_k": 4800,
        "contrast":      "low",
        "key_intensity": 0.85,
        "fill_ratio":    0.6,
        "ambient_level": 0.4,
        "color_notes":   "Golden-warm key, soft blue sky fill. High fill ratio reduces shadow depth.",
        "description":   "Optimistic dawn-inspired lighting. Warm golden key, generous fill.",
    },
    "dramatic": {
        "temperature":   "warm",
        "temperature_k": 3200,
        "contrast":      "high",
        "key_intensity": 1.0,
        "fill_ratio":    0.2,
        "ambient_level": 0.05,
        "color_notes":   "Warm tungsten key. Minimal cool fill. Deep shadows. High contrast ratio.",
        "description":   "Chiaroscuro-inspired. Strong directional key, minimal fill.",
    },
    "tense": {
        "temperature":   "cool",
        "temperature_k": 5500,
        "contrast":      "high",
        "key_intensity": 0.7,
        "fill_ratio":    0.15,
        "ambient_level": 0.1,
        "color_notes":   "Cool blue-green key. Practical motivated sources. Minimal fill.",
        "description":   "Screen and practical motivated. Cool, low fill, confined feeling.",
    },
    "dangerous": {
        "temperature":   "cool",
        "temperature_k": 6500,
        "contrast":      "high",
        "key_intensity": 0.5,
        "fill_ratio":    0.1,
        "ambient_level": 0.05,
        "color_notes":   "Near-dark. Red emergency or cool blue. Very low key. High shadow ratio.",
        "description":   "Near-darkness. Emergency red or cold blue. Threat and menace.",
    },
    "mystical": {
        "temperature":   "cool",
        "temperature_k": 4500,
        "contrast":      "medium",
        "key_intensity": 0.6,
        "fill_ratio":    0.4,
        "ambient_level": 0.3,
        "color_notes":   "Soft cool-purple or blue-green. Ethereal fill. Glowing accents.",
        "description":   "Otherworldly glow. Ethereal fill, mysterious accents.",
    },
    "industrial": {
        "temperature":   "cool",
        "temperature_k": 4000,
        "contrast":      "high",
        "key_intensity": 0.9,
        "fill_ratio":    0.25,
        "ambient_level": 0.15,
        "color_notes":   "Cool fluorescent overhead. Bounce off concrete. No decorative lighting.",
        "description":   "Harsh overhead industrial. Functional, gritty, no warmth.",
    },
    "clinical": {
        "temperature":   "neutral",
        "temperature_k": 5000,
        "contrast":      "low",
        "key_intensity": 0.9,
        "fill_ratio":    0.7,
        "ambient_level": 0.5,
        "color_notes":   "Neutral-cool even light. High fill. Minimal shadows. Sterile precision.",
        "description":   "Sterile even illumination. Maximum fill. Clean and precise.",
    },
    "cinematic": {
        "temperature":   "warm",
        "temperature_k": 3800,
        "contrast":      "high",
        "key_intensity": 0.95,
        "fill_ratio":    0.25,
        "ambient_level": 0.1,
        "color_notes":   "Warm pushed key. Cool fill for separation. High ratio. Controlled highlights.",
        "description":   "Film-style. Warm key against cool fill. Cinematic contrast ratio.",
    },
}

_MOOD_KEYWORDS: Dict[str, List[str]] = {
    "hopeful":    ["hope", "bright", "dawn", "sunrise", "warm", "golden", "optimistic"],
    "dramatic":   ["dramatic", "intense", "powerful", "bold", "contrast", "cinematic", "epic"],
    "tense":      ["tense", "suspense", "thriller", "anxious", "nervous", "tight", "confined"],
    "dangerous":  ["danger", "threat", "dark", "evil", "menace", "warning", "alarm"],
    "mystical":   ["mystic", "magical", "fantasy", "ethereal", "dream", "otherworldly", "glow"],
    "industrial": ["industrial", "gritty", "factory", "warehouse", "hangar", "mechanical"],
    "clinical":   ["clinical", "clean", "sterile", "lab", "medical", "white", "cold"],
    "cinematic":  ["cinematic", "film", "movie", "widescreen", "narrative", "scope"],
}


@dataclass
class MoodProfile:
    mood: str = ""
    temperature: str = "neutral"
    temperature_k: int = 5000
    contrast: str = "medium"
    key_intensity: float = 0.8
    fill_ratio: float = 0.3
    ambient_level: float = 0.2
    color_notes: str = ""
    description: str = ""
    built_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mood":           str(self.mood),
            "temperature":    str(self.temperature),
            "temperature_k":  int(self.temperature_k),
            "contrast":       str(self.contrast),
            "key_intensity":  float(self.key_intensity),
            "fill_ratio":     float(self.fill_ratio),
            "ambient_level":  float(self.ambient_level),
            "color_notes":    str(self.color_notes),
            "description":    str(self.description),
            "built_at":       float(self.built_at),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MoodProfile":
        d = d if isinstance(d, dict) else {}
        return cls(
            mood=str(d.get("mood", "")),
            temperature=str(d.get("temperature", "neutral")),
            temperature_k=int(d.get("temperature_k") or 5000),
            contrast=str(d.get("contrast", "medium")),
            key_intensity=float(d.get("key_intensity") or 0.8),
            fill_ratio=float(d.get("fill_ratio") or 0.3),
            ambient_level=float(d.get("ambient_level") or 0.2),
            color_notes=str(d.get("color_notes", "")),
            description=str(d.get("description", "")),
            built_at=float(d.get("built_at") or time.time()),
        )


class LightingMoodEngine:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._infer_count = 0

    def infer_mood(self, intent_text: str) -> str:
        """Infer mood from natural-language intent text. Returns mood string or ''."""
        try:
            text = str(intent_text or "").lower()
            best_mood = ""
            best_score = 0
            for mood, keywords in _MOOD_KEYWORDS.items():
                score = sum(1 for kw in keywords if kw in text)
                if score > best_score:
                    best_score = score
                    best_mood = mood
            with self._lock:
                self._infer_count += 1
            return best_mood
        except Exception:
            return ""

    def build_mood_profile(self, mood: str) -> MoodProfile:
        """Build a MoodProfile for the given mood. Returns a default profile if unknown."""
        try:
            key = str(mood or "").lower().strip()
            profile_data = _MOOD_PROFILES.get(key)
            if not profile_data:
                return MoodProfile(
                    mood=key,
                    color_notes=f"Unknown mood '{key}' — using default balanced profile.",
                    description=f"No builtin profile for mood '{key}'.",
                )
            return MoodProfile(
                mood=key,
                temperature=str(profile_data.get("temperature", "neutral")),
                temperature_k=int(profile_data.get("temperature_k", 5000)),
                contrast=str(profile_data.get("contrast", "medium")),
                key_intensity=float(profile_data.get("key_intensity", 0.8)),
                fill_ratio=float(profile_data.get("fill_ratio", 0.3)),
                ambient_level=float(profile_data.get("ambient_level", 0.2)),
                color_notes=str(profile_data.get("color_notes", "")),
                description=str(profile_data.get("description", "")),
            )
        except Exception as exc:
            return MoodProfile(
                mood=str(mood or ""),
                color_notes=f"build_mood_profile error: {exc}",
            )

    def list_moods(self) -> List[str]:
        return sorted(_MOOD_PROFILES.keys())

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "infer_calls":  self._infer_count,
                "known_moods":  len(_MOOD_PROFILES),
            }


_INSTANCE: Optional[LightingMoodEngine] = None
_INSTANCE_LOCK = threading.Lock()


def get_lighting_mood_engine() -> LightingMoodEngine:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = LightingMoodEngine()
    return _INSTANCE


def reset_lighting_mood_engine_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
