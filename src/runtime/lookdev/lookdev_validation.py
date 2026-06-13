"""
Lookdev Validation (Tier 14)
==============================
Validates lookdev objects: materials, patterns, renderer profiles, assignments,
and review thresholds.
Deterministic, thread-safe, no Houdini dependency, never raises.
"""
from __future__ import annotations

import threading
import time
from typing import Any, Dict, List, Optional

from .material_library import BUILTIN_MATERIAL_CATEGORIES
from .renderer_profiles import SUPPORTED_RENDERERS


class LookdevValidation:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._validate_count = 0

    def _result(
        self,
        ok: bool,
        errors: List[str],
        warnings: List[str],
    ) -> Dict[str, Any]:
        with self._lock:
            self._validate_count += 1
        return {
            "ok":           ok,
            "errors":       list(errors),
            "warnings":     list(warnings),
            "validated_at": time.time(),
        }

    def validate_material(self, material_dict: Dict[str, Any]) -> Dict[str, Any]:
        try:
            d = material_dict if isinstance(material_dict, dict) else {}
            errors: List[str] = []
            warnings: List[str] = []

            name = str(d.get("name", "")).strip()
            if not name:
                errors.append("Material must have a 'name' field.")

            category = str(d.get("category", "")).strip()
            if not category:
                errors.append("Material must have a 'category' field.")
            elif category not in BUILTIN_MATERIAL_CATEGORIES:
                warnings.append(
                    f"Category '{category}' is not a builtin category. "
                    f"Known categories: {', '.join(sorted(BUILTIN_MATERIAL_CATEGORIES))}."
                )

            properties = d.get("properties")
            if properties is not None and not isinstance(properties, dict):
                errors.append("'properties' must be a dict if provided.")

            return self._result(len(errors) == 0, errors, warnings)
        except Exception as exc:
            return self._result(False, [f"validate_material error: {exc}"], [])

    def validate_pattern(self, pattern_dict: Dict[str, Any]) -> Dict[str, Any]:
        try:
            d = pattern_dict if isinstance(pattern_dict, dict) else {}
            errors: List[str] = []
            warnings: List[str] = []

            name = str(d.get("name", "")).strip()
            if not name:
                errors.append("Pattern must have a 'name' field.")

            environment = str(d.get("environment", "")).strip()
            if not environment:
                errors.append("Pattern must have an 'environment' field.")

            materials = d.get("materials")
            if materials is None:
                errors.append("Pattern must have a 'materials' list.")
            elif not isinstance(materials, list):
                errors.append("'materials' must be a list.")
            elif len(materials) == 0:
                errors.append("Pattern 'materials' list must have at least one entry.")

            tags = d.get("tags")
            if tags is not None and not isinstance(tags, list):
                warnings.append("'tags' should be a list.")

            return self._result(len(errors) == 0, errors, warnings)
        except Exception as exc:
            return self._result(False, [f"validate_pattern error: {exc}"], [])

    def validate_renderer_profile(self, profile_dict: Dict[str, Any]) -> Dict[str, Any]:
        try:
            d = profile_dict if isinstance(profile_dict, dict) else {}
            errors: List[str] = []
            warnings: List[str] = []

            renderer = str(d.get("renderer", "")).strip()
            if not renderer:
                errors.append("Renderer profile must have a 'renderer' field.")
            elif renderer not in SUPPORTED_RENDERERS:
                errors.append(
                    f"Renderer '{renderer}' is not supported. "
                    f"Supported: {', '.join(sorted(SUPPORTED_RENDERERS))}."
                )

            material_class = str(d.get("material_class", "")).strip()
            if not material_class:
                errors.append("Renderer profile must have a 'material_class' field.")

            properties = d.get("properties")
            if properties is not None and not isinstance(properties, dict):
                warnings.append("'properties' should be a dict.")

            return self._result(len(errors) == 0, errors, warnings)
        except Exception as exc:
            return self._result(False, [f"validate_renderer_profile error: {exc}"], [])

    def validate_assignment(self, assignment_dict: Dict[str, Any]) -> Dict[str, Any]:
        try:
            d = assignment_dict if isinstance(assignment_dict, dict) else {}
            errors: List[str] = []
            warnings: List[str] = []

            asset_id = str(d.get("asset_id", "")).strip()
            if not asset_id:
                warnings.append("Assignment is missing 'asset_id'.")

            material_name = str(d.get("material_name", "")).strip()
            if not material_name:
                errors.append("Assignment must have a 'material_name' field.")

            renderer = str(d.get("renderer", "")).strip()
            if not renderer:
                warnings.append("Assignment is missing 'renderer'.")
            elif renderer not in SUPPORTED_RENDERERS:
                warnings.append(f"Assignment renderer '{renderer}' is not in SUPPORTED_RENDERERS.")

            confidence = d.get("confidence")
            if confidence is not None:
                try:
                    c = float(confidence)
                    if not (0.0 <= c <= 1.0):
                        warnings.append(f"Assignment confidence {c} is outside [0, 1].")
                except (ValueError, TypeError):
                    warnings.append("Assignment 'confidence' must be a float.")

            return self._result(len(errors) == 0, errors, warnings)
        except Exception as exc:
            return self._result(False, [f"validate_assignment error: {exc}"], [])

    def validate_review_threshold(
        self,
        score: float,
        threshold: float = 0.70,
    ) -> Dict[str, Any]:
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


_INSTANCE: Optional[LookdevValidation] = None
_INSTANCE_LOCK = threading.Lock()


def get_lookdev_validation() -> LookdevValidation:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = LookdevValidation()
    return _INSTANCE


def reset_lookdev_validation_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
