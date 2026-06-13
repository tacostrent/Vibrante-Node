"""
Download Serializer (Tier 12.9)
==================================
Sorted-key JSON serialization for acquisition state persistence.
Schema version: 1.0.0
"""
from __future__ import annotations

import json
import threading
from typing import Any, Dict, List, Optional

_SCHEMA_VERSION = "1.0.0"
_SCHEMA_KEY     = "__download_schema_version__"


class DownloadSerializer:
    def __init__(self) -> None:
        self._lock = threading.Lock()

    @property
    def schema_version(self) -> str:
        return _SCHEMA_VERSION

    def serialize(self, data: Dict[str, Any]) -> str:
        try:
            payload = {_SCHEMA_KEY: _SCHEMA_VERSION, **self._normalize(data)}
            return json.dumps(payload, sort_keys=True, indent=2, default=str)
        except Exception as exc:
            return json.dumps({"error": str(exc), _SCHEMA_KEY: _SCHEMA_VERSION})

    def deserialize(self, data: str) -> Dict[str, Any]:
        try:
            result = json.loads(data)
            if not isinstance(result, dict):
                return {}
            result.pop(_SCHEMA_KEY, None)
            return result
        except Exception:
            return {}

    def serialize_list(self, items: List[Dict[str, Any]]) -> str:
        try:
            payload = {_SCHEMA_KEY: _SCHEMA_VERSION,
                       "items": [self._normalize(d) for d in items]}
            return json.dumps(payload, sort_keys=True, indent=2, default=str)
        except Exception as exc:
            return json.dumps({"error": str(exc)})

    def deserialize_list(self, data: str) -> List[Dict[str, Any]]:
        try:
            payload = json.loads(data)
            if not isinstance(payload, dict):
                return []
            return [dict(d) for d in (payload.get("items") or [])]
        except Exception:
            return []

    def write_jsonl(self, path: str, record: Dict[str, Any]) -> bool:
        """Append one JSONL record to a file. Returns True on success."""
        try:
            import os
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            line = json.dumps(self._normalize(record), sort_keys=True, default=str)
            with open(path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
            return True
        except Exception:
            return False

    def read_jsonl(self, path: str) -> List[Dict[str, Any]]:
        """Read all JSONL records from a file."""
        try:
            import os
            if not os.path.isfile(path):
                return []
            records = []
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            records.append(json.loads(line))
                        except Exception:
                            pass
            return records
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


_INSTANCE: Optional[DownloadSerializer] = None
_INSTANCE_LOCK = threading.Lock()


def get_download_serializer() -> DownloadSerializer:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = DownloadSerializer()
    return _INSTANCE


def reset_download_serializer_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
