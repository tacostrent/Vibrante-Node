"""
Environment Serializer (§44 — Structural Environment Assembly)
==============================================================
Sorted-key JSON serialization for environment pipeline data.

DESIGN RULES:
  1. No bridge calls. No Houdini imports.
  2. Deterministic — same input always produces the same JSON.
  3. Never raises — errors returned as empty dict / empty string.
  4. Singleton pattern.
  5. Thread-safe.

Public API:
    EnvironmentSerializer
    get_environment_serializer()
    reset_environment_serializer_for_tests()
"""

from __future__ import annotations

import json
import threading
from typing import Any, Dict, Optional


class EnvironmentSerializer:
    """JSON serializer with sorted keys and schema versioning."""

    _schema_version = "1.0.0"

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def serialize(self, data: Dict[str, Any]) -> str:
        """Serialize a dict to a sorted-key JSON string."""
        with self._lock:
            try:
                return json.dumps(data, sort_keys=True, default=str, indent=None)
            except Exception:
                return "{}"

    def deserialize(self, text: str) -> Dict[str, Any]:
        """Deserialize a JSON string to a dict."""
        with self._lock:
            try:
                result = json.loads(text or "{}")
                if not isinstance(result, dict):
                    return {}
                return result
            except Exception:
                return {}

    def serialize_to_file(self, data: Dict[str, Any], path: str) -> bool:
        """Serialize data and write to a file. Returns True on success."""
        with self._lock:
            try:
                text = json.dumps(data, sort_keys=True, default=str, indent=2)
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(text)
                return True
            except Exception:
                return False

    def deserialize_from_file(self, path: str) -> Dict[str, Any]:
        """Read and deserialize a JSON file. Returns empty dict on failure."""
        with self._lock:
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    text = fh.read()
                result = json.loads(text)
                if not isinstance(result, dict):
                    return {}
                return result
            except Exception:
                return {}

    def get_schema_version(self) -> str:
        return self._schema_version


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[EnvironmentSerializer] = None
_LOCK = threading.Lock()


def get_environment_serializer() -> EnvironmentSerializer:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = EnvironmentSerializer()
        return _INSTANCE


def reset_environment_serializer_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
