"""
environment_serializer.py — §49 Structural Environment Realization
===================================================================
Sorted-key JSON serialization for EnvironmentRealizationPlan and related
structures. Schema version 1.0.0.

Public API:
    EnvRealizationSerializer
    get_env_realization_serializer()
    reset_env_realization_serializer_for_tests()
"""

from __future__ import annotations

import json
import threading
from typing import Any, Optional

_SCHEMA_VERSION = "1.0.0"


class EnvRealizationSerializer:
    """Serialize/deserialize EnvironmentRealizationPlan to/from JSON."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def serialize(self, obj: Any, indent: int = 2) -> str:
        """Serialize to sorted-key JSON with schema version."""
        if isinstance(obj, dict):
            payload = {"_schema_version": _SCHEMA_VERSION, **obj}
        else:
            payload = obj
        return json.dumps(payload, sort_keys=True, indent=indent, default=str)

    def deserialize(self, text: str) -> Any:
        """Parse JSON text; returns {} on error."""
        try:
            return json.loads(text)
        except Exception:
            return {}

    def serialize_plan(self, plan: dict) -> str:
        return self.serialize(plan)

    def serialize_shell(self, shell: dict) -> str:
        return self.serialize(shell)

    def serialize_elements(self, elements: list) -> str:
        return json.dumps(elements, sort_keys=True, indent=2, default=str)

    @property
    def schema_version(self) -> str:
        return _SCHEMA_VERSION


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[EnvRealizationSerializer] = None
_lock = threading.Lock()


def get_env_realization_serializer() -> EnvRealizationSerializer:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = EnvRealizationSerializer()
    return _instance


def reset_env_realization_serializer_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
