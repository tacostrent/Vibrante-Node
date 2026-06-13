"""
reality_serializer.py — §54 Reality Intelligence (Tier 15.0+)
==============================================================
Sorted-key JSON serializer for Reality Intelligence results.
Schema version 1.0.0 — same convention as every other tier.

Public API:
    RealitySerializer
    get_reality_serializer()
    reset_reality_serializer_for_tests()
"""

from __future__ import annotations

import json
import threading
from typing import Any, Dict, Optional

REALITY_SCHEMA_VERSION = "1.0.0"


class RealitySerializer:
    """Deterministic JSON serialization for §54 result dicts. Never raises."""

    _schema_version = REALITY_SCHEMA_VERSION

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def serialize(self, result: Dict[str, Any], indent: int = 2) -> str:
        try:
            payload = {
                "schema_version": self._schema_version,
                "result": result if isinstance(result, dict) else {},
            }
            return json.dumps(payload, sort_keys=True, indent=indent, default=str)
        except Exception as exc:
            return json.dumps({
                "schema_version": self._schema_version,
                "result": {},
                "error": f"serialization failed: {exc}",
            }, sort_keys=True, indent=indent)

    def deserialize(self, raw: str) -> Dict[str, Any]:
        try:
            payload = json.loads(raw or "{}")
            if not isinstance(payload, dict):
                return {}
            result = payload.get("result")
            return result if isinstance(result, dict) else {}
        except Exception:
            return {}


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[RealitySerializer] = None
_lock = threading.Lock()


def get_reality_serializer() -> RealitySerializer:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = RealitySerializer()
    return _instance


def reset_reality_serializer_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
