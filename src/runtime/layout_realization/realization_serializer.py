"""
realization_serializer.py — §47 Layout Realization & Scene Constraint Solver
=============================================================================
Sorted-key JSON serialization for ResolvedSceneLayout and related structures.
Schema version 1.0.0.

Public API:
    RealizationSerializer
    get_realization_serializer()
    reset_realization_serializer_for_tests()
"""

from __future__ import annotations

import json
import threading
from typing import Any, Dict, Optional

_SCHEMA_VERSION = "1.0.0"


class RealizationSerializer:
    """Serialize/deserialize ResolvedSceneLayout and friends to/from JSON."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def serialize(self, obj: Any, indent: int = 2) -> str:
        """Serialize any dict/list to sorted-key JSON with schema version header."""
        if isinstance(obj, dict):
            payload = {"_schema_version": _SCHEMA_VERSION, **obj}
        else:
            payload = obj
        return json.dumps(payload, sort_keys=True, indent=indent, default=str)

    def deserialize(self, text: str) -> Any:
        """Parse JSON text. Returns empty dict on error."""
        try:
            return json.loads(text)
        except Exception:
            return {}

    def serialize_layout(self, scene_layout: Dict[str, Any]) -> str:
        return self.serialize(scene_layout)

    def serialize_transforms(self, transforms: list) -> str:
        return json.dumps(transforms, sort_keys=True, indent=2, default=str)

    def serialize_review(self, review: Dict[str, Any]) -> str:
        return self.serialize(review)

    @property
    def schema_version(self) -> str:
        return _SCHEMA_VERSION


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[RealizationSerializer] = None
_lock = threading.Lock()


def get_realization_serializer() -> RealizationSerializer:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = RealizationSerializer()
    return _instance


def reset_realization_serializer_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
