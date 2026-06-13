"""
Lighting Validation (Tier 15)
================================
Validates lighting plans, strategies, and individual light specs.
Deterministic, thread-safe, no Houdini dependency, never raises.
"""
from __future__ import annotations

import threading
import time
from typing import Any, Dict, List, Optional

from .lighting_knowledge import BUILTIN_LIGHTING_ROLES
from .lighting_mood_engine import _MOOD_PROFILES


class LightingValidation:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._validate_count = 0

    def _result(self, ok: bool, errors: List[str], warnings: List[str]) -> Dict[str, Any]:
        with self._lock:
            self._validate_count += 1
        return {
            "ok":           ok,
            "errors":       list(errors),
            "warnings":     list(warnings),
            "validated_at": time.time(),
        }

    def validate_light_spec(self, spec_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a single LightSpec dict."""
        try:
            d = spec_dict if isinstance(spec_dict, dict) else {}
            errors: List[str] = []
            warnings: List[str] = []

            role = str(d.get("role", "")).strip()
            if not role:
                errors.append("LightSpec must have a 'role' field.")
            elif role not in BUILTIN_LIGHTING_ROLES:
                warnings.append(
                    f"Role '{role}' is not a builtin role. "
                    f"Known roles: {', '.join(sorted(BUILTIN_LIGHTING_ROLES))}."
                )

            intensity = d.get("intensity")
            if intensity is not None:
                try:
                    i = float(intensity)
                    if not (0.0 <= i <= 1.0):
                        warnings.append(f"Intensity {i:.3f} outside [0, 1] — verify intent.")
                except (ValueError, TypeError):
                    errors.append("'intensity' must be a float.")

            temp_k = d.get("color_temperature_k")
            if temp_k is not None:
                try:
                    k = int(temp_k)
                    if not (1000 <= k <= 20000):
                        warnings.append(f"color_temperature_k {k}K is outside typical range [1000, 20000].")
                except (ValueError, TypeError):
                    errors.append("'color_temperature_k' must be an integer.")

            return self._result(len(errors) == 0, errors, warnings)
        except Exception as exc:
            return self._result(False, [f"validate_light_spec error: {exc}"], [])

    def validate_plan(self, plan_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a LightPlan dict."""
        try:
            d = plan_dict if isinstance(plan_dict, dict) else {}
            errors: List[str] = []
            warnings: List[str] = []

            # Key light is mandatory
            key_light = d.get("key_light")
            if not key_light:
                errors.append("Lighting plan must have a 'key_light' entry.")
            elif isinstance(key_light, dict):
                key_result = self.validate_light_spec(key_light)
                errors.extend(key_result.get("errors", []))
                warnings.extend(key_result.get("warnings", []))

            # Fill and rim are recommended
            if not d.get("fill_light"):
                warnings.append("No 'fill_light' — shadows may be completely black.")
            if not d.get("rim_light"):
                warnings.append("No 'rim_light' — subject separation may be poor.")

            # Mood optional but recommended
            if not str(d.get("mood", "")).strip():
                warnings.append("No 'mood' defined in plan — emotional direction is unspecified.")

            # Color strategy optional
            if not d.get("color_strategy"):
                warnings.append("No 'color_strategy' — color coordination is unspecified.")

            return self._result(len(errors) == 0, errors, warnings)
        except Exception as exc:
            return self._result(False, [f"validate_plan error: {exc}"], [])

    def validate_strategy(self, strategy_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a LightingStrategy dict."""
        try:
            d = strategy_dict if isinstance(strategy_dict, dict) else {}
            errors: List[str] = []
            warnings: List[str] = []

            if not str(d.get("key_concept", "")).strip():
                errors.append("Strategy must have a 'key_concept'.")

            mood = str(d.get("mood", "")).strip()
            if not mood:
                warnings.append("No mood in strategy — emotional direction missing.")
            elif mood not in _MOOD_PROFILES:
                warnings.append(
                    f"Mood '{mood}' is not a builtin mood. "
                    f"Known moods: {', '.join(sorted(_MOOD_PROFILES.keys()))}."
                )

            if not str(d.get("environment", "")).strip():
                warnings.append("No environment in strategy — defaults will be used.")

            contrast = str(d.get("contrast", "")).strip()
            if contrast and contrast not in ("high", "medium", "low"):
                warnings.append(f"Contrast '{contrast}' is not one of: high, medium, low.")

            return self._result(len(errors) == 0, errors, warnings)
        except Exception as exc:
            return self._result(False, [f"validate_strategy error: {exc}"], [])

    def validate_review_threshold(
        self,
        score: float,
        threshold: float = 0.70,
    ) -> Dict[str, Any]:
        """Compare score vs threshold and return production_ready verdict."""
        try:
            score     = float(score     if score     is not None else 0.0)
            threshold = float(threshold if threshold is not None else 0.70)
            gap       = round(threshold - score, 3)
            production_ready = score >= threshold
            with self._lock:
                self._validate_count += 1
            return {
                "ok":              True,
                "score":           round(score, 3),
                "threshold":       round(threshold, 3),
                "production_ready": production_ready,
                "gap":             max(0.0, gap),
                "validated_at":    time.time(),
            }
        except Exception as exc:
            return {
                "ok":              False,
                "score":           0.0,
                "threshold":       0.70,
                "production_ready": False,
                "gap":             0.70,
                "validated_at":    time.time(),
                "error":           str(exc),
            }


_INSTANCE: Optional[LightingValidation] = None
_INSTANCE_LOCK = threading.Lock()


def get_lighting_validation() -> LightingValidation:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = LightingValidation()
    return _INSTANCE


def reset_lighting_validation_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
