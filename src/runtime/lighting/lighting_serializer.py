"""
Lighting Serializer (Tier 15)
================================
Persists lighting plans as deterministic, sorted-key JSON with schema versioning.
Stateless utility — safe to instantiate multiple times.
"""
from __future__ import annotations

import json
import threading
from typing import Any, Dict, Optional

_SCHEMA_VERSION = "1.0.0"


class LightingSerializer:
    def save(self, data: Dict[str, Any], path: str) -> bool:
        """Write data to a JSON file at path. Returns True on success."""
        try:
            payload = dict(data) if isinstance(data, dict) else {}
            payload["_schema_version"] = _SCHEMA_VERSION
            with open(str(path), "w", encoding="utf-8") as f:
                json.dump(payload, f, sort_keys=True, indent=2, default=str)
            return True
        except Exception:
            return False

    def load(self, path: str) -> Dict[str, Any]:
        """Read a JSON file from path. Returns {} on failure."""
        try:
            with open(str(path), "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def export(self, data: Dict[str, Any]) -> str:
        """Serialize data to a JSON string with sorted keys and schema version."""
        try:
            payload = dict(data) if isinstance(data, dict) else {}
            payload["_schema_version"] = _SCHEMA_VERSION
            return json.dumps(payload, sort_keys=True, default=str)
        except Exception:
            return json.dumps({"_schema_version": _SCHEMA_VERSION, "_export_error": "serialization failed"})

    def import_(self, s: str) -> Dict[str, Any]:
        """Parse a JSON string. Returns {} on failure."""
        try:
            result = json.loads(str(s))
            return result if isinstance(result, dict) else {}
        except Exception:
            return {}


_INSTANCE: Optional[LightingSerializer] = None
_INSTANCE_LOCK = threading.Lock()


def get_lighting_serializer() -> LightingSerializer:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = LightingSerializer()
    return _INSTANCE


def reset_lighting_serializer_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
