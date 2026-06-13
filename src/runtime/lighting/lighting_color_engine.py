"""
Lighting Color Engine (Tier 15)
=================================
Determines color strategy for cinematic lighting.
Deterministic, thread-safe, no Houdini dependency.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# Color palettes keyed by mood or environment
_PALETTES: Dict[str, Dict[str, Any]] = {
    "industrial": {
        "name":        "Industrial Steel",
        "primary":     [0.72, 0.76, 0.82],   # cool gray-blue
        "accent":      [0.95, 0.78, 0.40],   # warm amber
        "shadow":      [0.08, 0.10, 0.14],   # deep cool shadow
        "harmony":     "complementary",
        "temperature": "cool",
        "notes":       "Cool overhead key, warm amber accent from practicals.",
    },
    "clinical": {
        "name":        "Clinical White",
        "primary":     [0.92, 0.94, 1.0],    # near-white cool
        "accent":      [0.4, 0.8, 0.95],     # cyan screen light
        "shadow":      [0.15, 0.18, 0.22],   # blue-gray shadow
        "harmony":     "analogous",
        "temperature": "cool",
        "notes":       "Even cool white. Cyan screen accents. Minimal shadow saturation.",
    },
    "dramatic": {
        "name":        "Dramatic Amber",
        "primary":     [0.95, 0.70, 0.30],   # warm tungsten amber
        "accent":      [0.25, 0.40, 0.70],   # cool blue fill
        "shadow":      [0.04, 0.03, 0.06],   # near-black warm shadow
        "harmony":     "complementary",
        "temperature": "warm",
        "notes":       "Warm key against cool fill. Complementary tension creates drama.",
    },
    "tense": {
        "name":        "Tense Screen Glow",
        "primary":     [0.30, 0.55, 0.85],   # blue screen glow
        "accent":      [0.85, 0.30, 0.30],   # red emergency
        "shadow":      [0.04, 0.06, 0.10],   # very dark cool shadow
        "harmony":     "split_complementary",
        "temperature": "cool",
        "notes":       "Blue-green screen dominates. Red emergency accent. Very dark shadows.",
    },
    "dangerous": {
        "name":        "Danger Red",
        "primary":     [0.80, 0.08, 0.08],   # emergency red
        "accent":      [0.15, 0.15, 0.20],   # near-black cool
        "shadow":      [0.02, 0.02, 0.03],   # near-black
        "harmony":     "monochromatic",
        "temperature": "warm",
        "notes":       "Near-monochromatic red. Threat and menace. Minimal detail in shadows.",
    },
    "mystical": {
        "name":        "Mystical Purple",
        "primary":     [0.55, 0.35, 0.85],   # purple-violet
        "accent":      [0.20, 0.85, 0.70],   # teal-green glow
        "shadow":      [0.06, 0.04, 0.12],   # dark purple shadow
        "harmony":     "split_complementary",
        "temperature": "cool",
        "notes":       "Purple key with teal accent. Ethereal contrast.",
    },
    "hopeful": {
        "name":        "Golden Hour",
        "primary":     [0.98, 0.82, 0.40],   # golden yellow
        "accent":      [0.65, 0.80, 0.98],   # sky blue
        "shadow":      [0.20, 0.18, 0.25],   # warm shadow
        "harmony":     "complementary",
        "temperature": "warm",
        "notes":       "Golden sunrise/sunset. Warm key, cool sky fill.",
    },
    "cinematic": {
        "name":        "Cinematic Teal-Orange",
        "primary":     [0.95, 0.65, 0.25],   # warm orange
        "accent":      [0.20, 0.55, 0.75],   # teal fill
        "shadow":      [0.05, 0.08, 0.12],   # teal-blue shadow
        "harmony":     "complementary",
        "temperature": "warm",
        "notes":       "Classic teal-orange. Warm skin-tone key, teal cool fill and shadows.",
    },
    "night_exterior": {
        "name":        "Moonlit Night",
        "primary":     [0.45, 0.55, 0.82],   # moonlight blue
        "accent":      [0.92, 0.72, 0.35],   # warm street practical
        "shadow":      [0.03, 0.04, 0.08],   # near-black cool
        "harmony":     "complementary",
        "temperature": "cool",
        "notes":       "Cool moonlight key, warm street lamp accents.",
    },
}

_TEMPERATURE_MAP: Dict[str, Tuple[int, int]] = {
    # name → (typical_k, range_k_delta)
    "warm":    (3200, 600),
    "neutral": (5000, 300),
    "cool":    (6500, 500),
}

_HARMONY_TYPES = frozenset({
    "complementary",
    "analogous",
    "split_complementary",
    "triadic",
    "monochromatic",
})


@dataclass
class ColorStrategy:
    palette_name: str = ""
    temperature: str = "neutral"
    temperature_k: int = 5000
    primary_color: List[float] = field(default_factory=lambda: [1.0, 1.0, 1.0])
    accent_color: List[float] = field(default_factory=lambda: [0.5, 0.5, 0.5])
    shadow_color: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    harmony_type: str = "complementary"
    notes: str = ""
    built_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "palette_name":   str(self.palette_name),
            "temperature":    str(self.temperature),
            "temperature_k":  int(self.temperature_k),
            "primary_color":  list(self.primary_color),
            "accent_color":   list(self.accent_color),
            "shadow_color":   list(self.shadow_color),
            "harmony_type":   str(self.harmony_type),
            "notes":          str(self.notes),
            "built_at":       float(self.built_at),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ColorStrategy":
        d = d if isinstance(d, dict) else {}
        return cls(
            palette_name=str(d.get("palette_name", "")),
            temperature=str(d.get("temperature", "neutral")),
            temperature_k=int(d.get("temperature_k") or 5000),
            primary_color=list(d.get("primary_color") or [1.0, 1.0, 1.0]),
            accent_color=list(d.get("accent_color") or [0.5, 0.5, 0.5]),
            shadow_color=list(d.get("shadow_color") or [0.0, 0.0, 0.0]),
            harmony_type=str(d.get("harmony_type", "complementary")),
            notes=str(d.get("notes", "")),
            built_at=float(d.get("built_at") or time.time()),
        )


class LightingColorEngine:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._recommend_count = 0

    def recommend_palette(self, mood: str = "", environment: str = "") -> ColorStrategy:
        """Recommend a color palette for the given mood and/or environment."""
        try:
            key = str(mood or environment or "").lower().strip()
            palette = _PALETTES.get(key)
            if not palette:
                # Try partial match
                for k, p in _PALETTES.items():
                    if key in k or k in key:
                        palette = p
                        break
            if not palette:
                palette = _PALETTES.get("cinematic", {})
            with self._lock:
                self._recommend_count += 1
            temp = str(palette.get("temperature", "neutral"))
            temp_k, _ = _TEMPERATURE_MAP.get(temp, (5000, 300))
            return ColorStrategy(
                palette_name=str(palette.get("name", key)),
                temperature=temp,
                temperature_k=temp_k,
                primary_color=list(palette.get("primary", [1.0, 1.0, 1.0])),
                accent_color=list(palette.get("accent", [0.5, 0.5, 0.5])),
                shadow_color=list(palette.get("shadow", [0.0, 0.0, 0.0])),
                harmony_type=str(palette.get("harmony", "complementary")),
                notes=str(palette.get("notes", "")),
            )
        except Exception as exc:
            return ColorStrategy(notes=f"recommend_palette error: {exc}")

    def recommend_temperature(self, mood: str = "", environment: str = "") -> Dict[str, Any]:
        """Return color temperature recommendation (warm/cool/neutral + Kelvin value)."""
        try:
            strategy = self.recommend_palette(mood=mood, environment=environment)
            temp_k, delta = _TEMPERATURE_MAP.get(strategy.temperature, (5000, 300))
            return {
                "temperature":     strategy.temperature,
                "temperature_k":   temp_k,
                "range_k":         [temp_k - delta, temp_k + delta],
                "notes":           strategy.notes,
            }
        except Exception as exc:
            return {"temperature": "neutral", "temperature_k": 5000, "range_k": [4700, 5300], "notes": str(exc)}

    def evaluate_harmony(self, primary: List[float], accent: List[float]) -> Dict[str, Any]:
        """Evaluate color harmony between key and accent colors."""
        try:
            p = [float(x) for x in (primary or [1.0, 1.0, 1.0])]
            a = [float(x) for x in (accent or [0.5, 0.5, 0.5])]
            # Compute approximate hue distance as a proxy for harmony type
            p_lum = sum(p[:3]) / 3.0
            a_lum = sum(a[:3]) / 3.0
            lum_contrast = abs(p_lum - a_lum)
            findings: List[str] = []
            if lum_contrast < 0.1:
                findings.append("Low luminance contrast between primary and accent — colors may compete.")
            return {
                "luminance_contrast": round(lum_contrast, 3),
                "harmony_ok":         lum_contrast >= 0.1,
                "findings":           findings,
            }
        except Exception as exc:
            return {"luminance_contrast": 0.0, "harmony_ok": False, "findings": [str(exc)]}

    def list_palettes(self) -> List[str]:
        return sorted(_PALETTES.keys())

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "recommend_calls": self._recommend_count,
                "known_palettes":  len(_PALETTES),
            }


_INSTANCE: Optional[LightingColorEngine] = None
_INSTANCE_LOCK = threading.Lock()


def get_lighting_color_engine() -> LightingColorEngine:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = LightingColorEngine()
    return _INSTANCE


def reset_lighting_color_engine_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
