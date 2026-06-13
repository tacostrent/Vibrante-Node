"""
validation_serializer.py — §53 Scene Reality Validation (Tier 14.3)
====================================================================
Sorted-key JSON serialization for scene reality validation results.
Schema version 1.0.0.

Public API:
    ValidationSerializer
    get_validation_serializer()
    reset_validation_serializer_for_tests()
"""

from __future__ import annotations

import json
import threading
from typing import Any, Optional

_SCHEMA_VERSION = "1.0.0"


class ValidationSerializer:
    """Serialize/deserialize SceneValidationResult and friends to/from JSON."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def serialize(self, obj: Any, indent: int = 2) -> str:
        if isinstance(obj, dict):
            payload = {"_schema_version": _SCHEMA_VERSION, **obj}
        else:
            payload = obj
        return json.dumps(payload, sort_keys=True, indent=indent, default=str)

    def deserialize(self, text: str) -> Any:
        try:
            return json.loads(text)
        except Exception:
            return {}

    def serialize_validation(self, result: Any) -> str:
        d = result.to_dict() if hasattr(result, "to_dict") else result
        return self.serialize(d)

    def serialize_review(self, review: Any) -> str:
        d = review.to_dict() if hasattr(review, "to_dict") else review
        return self.serialize(d)

    @property
    def schema_version(self) -> str:
        return _SCHEMA_VERSION


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[ValidationSerializer] = None
_lock = threading.Lock()


def get_validation_serializer() -> ValidationSerializer:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = ValidationSerializer()
    return _instance


def reset_validation_serializer_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
