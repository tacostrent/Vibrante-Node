"""
Lighting Language (Tier 15)
============================
Translates cinematic intent text into structured lighting intent.
Keyword-based, deterministic, no ML dependency.
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

BUILTIN_MOODS = frozenset({
    "hopeful", "dramatic", "tense", "dangerous",
    "mystical", "industrial", "clinical", "cinematic",
})

BUILTIN_CONTRASTS = frozenset({"high", "medium", "low"})

BUILTIN_STYLES = frozenset({
    "low_key", "high_key", "rembrandt", "three_point",
    "naturalistic", "stylized", "chiaroscuro", "flat",
})

_MOOD_KEYWORDS: Dict[str, List[str]] = {
    "hopeful":    ["hope", "bright", "dawn", "sunrise", "warm", "golden", "optimistic", "light"],
    "dramatic":   ["dramatic", "intense", "powerful", "bold", "contrast", "cinematic", "epic"],
    "tense":      ["tense", "suspense", "thriller", "anxious", "nervous", "tight", "confined"],
    "dangerous":  ["danger", "threat", "dark", "evil", "menace", "warning", "alarm", "red"],
    "mystical":   ["mystic", "magical", "fantasy", "ethereal", "dream", "otherworldly", "glow"],
    "industrial": ["industrial", "gritty", "factory", "warehouse", "hangar", "mechanical", "harsh"],
    "clinical":   ["clinical", "clean", "sterile", "lab", "medical", "white", "cold", "precise"],
    "cinematic":  ["cinematic", "film", "movie", "widescreen", "anamorphic", "scope", "narrative"],
}

_CONTRAST_KEYWORDS: Dict[str, List[str]] = {
    "high":   ["high contrast", "stark", "deep shadow", "dramatic", "noir", "chiaroscuro", "harsh"],
    "low":    ["low contrast", "soft", "diffuse", "flat", "hazy", "misty", "overcast", "gentle"],
    "medium": ["medium", "balanced", "normal", "moderate", "standard"],
}

_STYLE_KEYWORDS: Dict[str, List[str]] = {
    "low_key":       ["low key", "dark", "shadow", "night", "noir", "underexposed", "dim"],
    "high_key":      ["high key", "bright", "light", "clean", "overexposed", "airy", "white"],
    "rembrandt":     ["rembrandt", "triangle", "portrait", "dramatic shadow", "classical"],
    "three_point":   ["three point", "3-point", "key fill rim", "standard setup", "commercial"],
    "naturalistic":  ["natural", "naturalistic", "realistic", "motivated", "real world"],
    "stylized":      ["stylized", "stylish", "artistic", "non-realistic", "abstract", "neon"],
    "chiaroscuro":   ["chiaroscuro", "extreme contrast", "renaissance", "deep black", "baroque"],
    "flat":          ["flat", "even", "no shadow", "shadowless", "broadcast", "neutral"],
}

_TEMPERATURE_KEYWORDS: Dict[str, List[str]] = {
    "warm":    ["warm", "golden", "orange", "amber", "sunset", "firelight", "tungsten", "incandescent"],
    "cool":    ["cool", "blue", "cold", "moonlight", "daylight", "overcast", "cyanotype", "arctic"],
    "neutral": ["neutral", "daylight", "5500k", "balanced", "white"],
}

_ENVIRONMENT_KEYWORDS: Dict[str, List[str]] = {
    "industrial_hangar":  ["hangar", "warehouse", "factory", "industrial", "facility", "plant"],
    "robotics_lab":       ["lab", "laboratory", "robotics", "research", "workshop", "tech"],
    "control_room":       ["control", "ops", "operation", "monitoring", "command"],
    "sci_fi_corridor":    ["corridor", "hallway", "passage", "sci-fi", "scifi", "futuristic", "ship"],
    "abandoned_factory":  ["abandoned", "derelict", "ruin", "decay", "forgotten", "decrepit"],
    "night_exterior":     ["night exterior", "outdoors night", "night sky", "street", "outdoor night"],
    "dramatic_interior":  ["dramatic interior", "interior", "room", "chamber", "inside"],
    "hero_reveal":        ["hero", "reveal", "entrance", "introduction", "character"],
}


@dataclass
class LightingIntent:
    intent_id: str = field(default_factory=lambda: f"li_{uuid.uuid4().hex[:8]}")
    intent_text: str = ""
    mood: str = ""
    contrast: str = ""
    style: str = ""
    temperature: str = ""
    environments: List[str] = field(default_factory=list)
    key_words: List[str] = field(default_factory=list)
    parsed_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent_id":    str(self.intent_id),
            "intent_text":  str(self.intent_text),
            "mood":         str(self.mood),
            "contrast":     str(self.contrast),
            "style":        str(self.style),
            "temperature":  str(self.temperature),
            "environments": list(self.environments),
            "key_words":    list(self.key_words),
            "parsed_at":    float(self.parsed_at),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "LightingIntent":
        d = d if isinstance(d, dict) else {}
        return cls(
            intent_id=str(d.get("intent_id") or f"li_{uuid.uuid4().hex[:8]}"),
            intent_text=str(d.get("intent_text", "")),
            mood=str(d.get("mood", "")),
            contrast=str(d.get("contrast", "")),
            style=str(d.get("style", "")),
            temperature=str(d.get("temperature", "")),
            environments=list(d.get("environments") or []),
            key_words=list(d.get("key_words") or []),
            parsed_at=float(d.get("parsed_at") or time.time()),
        )


def _best_match(text: str, keyword_map: Dict[str, List[str]]) -> str:
    """Return the key with the most keyword hits in text."""
    text_lower = text.lower()
    best_key = ""
    best_score = 0
    for key, kws in keyword_map.items():
        score = sum(1 for kw in kws if kw in text_lower)
        if score > best_score:
            best_score = score
            best_key = key
    return best_key


def _all_matches(text: str, keyword_map: Dict[str, List[str]]) -> List[str]:
    """Return all keys that have at least one keyword match, sorted by score desc."""
    text_lower = text.lower()
    scored = []
    for key, kws in keyword_map.items():
        score = sum(1 for kw in kws if kw in text_lower)
        if score > 0:
            scored.append((score, key))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [k for _, k in scored]


class LightingLanguage:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._parse_count = 0

    def extract_mood(self, text: str) -> str:
        """Extract the dominant lighting mood from intent text."""
        try:
            return _best_match(str(text or ""), _MOOD_KEYWORDS)
        except Exception:
            return ""

    def extract_contrast(self, text: str) -> str:
        """Extract contrast level (high/medium/low) from intent text."""
        try:
            result = _best_match(str(text or ""), _CONTRAST_KEYWORDS)
            return result or "medium"
        except Exception:
            return "medium"

    def extract_style(self, text: str) -> str:
        """Extract lighting style from intent text."""
        try:
            return _best_match(str(text or ""), _STYLE_KEYWORDS)
        except Exception:
            return ""

    def extract_temperature(self, text: str) -> str:
        """Extract color temperature preference (warm/cool/neutral) from intent text."""
        try:
            result = _best_match(str(text or ""), _TEMPERATURE_KEYWORDS)
            return result or "neutral"
        except Exception:
            return "neutral"

    def parse_lighting_intent(self, intent_text: str) -> LightingIntent:
        """Parse a natural-language lighting description into a structured LightingIntent."""
        try:
            return self._do_parse(str(intent_text or ""))
        except Exception as exc:
            return LightingIntent(
                intent_text=str(intent_text or ""),
                key_words=[f"parse_error: {exc}"],
            )

    def _do_parse(self, text: str) -> LightingIntent:
        text_lower = text.lower()

        mood = self.extract_mood(text)
        contrast = self.extract_contrast(text)
        style = self.extract_style(text)
        temperature = self.extract_temperature(text)
        environments = _all_matches(text, _ENVIRONMENT_KEYWORDS)

        # Collect notable keywords from the text
        key_words: List[str] = []
        for kw_list in _MOOD_KEYWORDS.values():
            for kw in kw_list:
                if kw in text_lower and kw not in key_words:
                    key_words.append(kw)
        for kw_list in _STYLE_KEYWORDS.values():
            for kw in kw_list:
                if kw in text_lower and kw not in key_words:
                    key_words.append(kw)
        key_words = sorted(set(key_words))[:20]

        with self._lock:
            self._parse_count += 1

        return LightingIntent(
            intent_text=text,
            mood=mood,
            contrast=contrast,
            style=style,
            temperature=temperature,
            environments=environments,
            key_words=key_words,
        )

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            return {"parse_calls": self._parse_count}


_INSTANCE: Optional[LightingLanguage] = None
_INSTANCE_LOCK = threading.Lock()


def get_lighting_language() -> LightingLanguage:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = LightingLanguage()
    return _INSTANCE


def reset_lighting_language_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
