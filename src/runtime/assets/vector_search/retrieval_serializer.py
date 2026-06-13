"""
Retrieval Serializer (Tier 12.8)
===================================
Sorted-key JSON serialization for retrieval state persistence.
Schema version: 1.0.0
"""
from __future__ import annotations

import json
import threading
from typing import Any, Dict, List, Optional

_SCHEMA_VERSION = "1.0.0"
_SCHEMA_KEY     = "__retrieval_schema_version__"


class RetrievalSerializer:
    def __init__(self) -> None:
        self._lock = threading.Lock()

    @property
    def schema_version(self) -> str:
        return _SCHEMA_VERSION

    def serialize(self, data: Dict[str, Any]) -> str:
        """Serialize a retrieval result or state dict to sorted-key JSON."""
        try:
            payload = {_SCHEMA_KEY: _SCHEMA_VERSION, **self._normalize(data)}
            return json.dumps(payload, sort_keys=True, indent=2, default=str)
        except Exception as exc:
            return json.dumps({"error": str(exc), _SCHEMA_KEY: _SCHEMA_VERSION})

    def deserialize(self, data: str) -> Dict[str, Any]:
        """Deserialize JSON string back to a dict."""
        try:
            result = json.loads(data)
            if not isinstance(result, dict):
                return {}
            result.pop(_SCHEMA_KEY, None)
            return result
        except Exception:
            return {}

    def serialize_list(self, items: List[Dict[str, Any]]) -> str:
        """Serialize a list of result dicts."""
        try:
            payload = {
                _SCHEMA_KEY: _SCHEMA_VERSION,
                "items": [self._normalize(d) for d in items],
            }
            return json.dumps(payload, sort_keys=True, indent=2, default=str)
        except Exception as exc:
            return json.dumps({"error": str(exc)})

    def deserialize_list(self, data: str) -> List[Dict[str, Any]]:
        """Deserialize a list JSON string."""
        try:
            payload = json.loads(data)
            if not isinstance(payload, dict):
                return []
            return [dict(d) for d in (payload.get("items") or [])]
        except Exception:
            return []

    def _normalize(self, v: Any) -> Any:
        if isinstance(v, dict):
            return {str(k): self._normalize(vv) for k, vv in v.items()}
        if isinstance(v, (list, tuple)):
            return [self._normalize(i) for i in v]
        if isinstance(v, (str, int, float, bool, type(None))):
            return v
        return str(v)


_INSTANCE: Optional[RetrievalSerializer] = None
_INSTANCE_LOCK = threading.Lock()


def get_retrieval_serializer() -> RetrievalSerializer:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = RetrievalSerializer()
    return _INSTANCE


def reset_retrieval_serializer_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
