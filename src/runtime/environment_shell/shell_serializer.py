"""
ShellSerializer — Tier 10.4
=============================
Sorted-key JSON serializer for EnvironmentShell and ShellReviewResult.
Schema version: 1.0.0. Never raises.

Public API:
    ShellSerializer
    get_shell_serializer()
    reset_shell_serializer_for_tests()
"""

from __future__ import annotations

import json
import threading
from typing import Any, Dict, Optional

_SCHEMA_VERSION = "1.0.0"


class ShellSerializer:

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def serialize(self, data: Any) -> str:
        """Serialize any dict/dataclass to sorted-key JSON. Never raises."""
        try:
            if hasattr(data, "to_dict"):
                d = data.to_dict()
            elif isinstance(data, dict):
                d = data
            else:
                d = {"value": str(data)}
            d["_schema_version"] = _SCHEMA_VERSION
            return json.dumps(d, sort_keys=True, indent=2, default=str)
        except Exception as exc:
            return json.dumps({"error": str(exc), "_schema_version": _SCHEMA_VERSION}, sort_keys=True)

    def deserialize(self, raw: str) -> Dict[str, Any]:
        """Parse JSON string to dict. Never raises."""
        try:
            return json.loads(raw)
        except Exception as exc:
            return {"error": str(exc)}


# ── Singleton ──────────────────────────────────────────────────────────────────

_INSTANCE: Optional[ShellSerializer] = None
_LOCK = threading.Lock()


def get_shell_serializer() -> ShellSerializer:
    global _INSTANCE
    if _INSTANCE is None:
        with _LOCK:
            if _INSTANCE is None:
                _INSTANCE = ShellSerializer()
    return _INSTANCE


def reset_shell_serializer_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
