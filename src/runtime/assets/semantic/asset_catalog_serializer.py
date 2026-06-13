"""
Asset Catalog Serializer (Tier 12.7)
=======================================
Sorted-key JSON serialization for semantic catalog persistence.
Schema version: 1.0.0
"""
from __future__ import annotations

import json
import threading
from typing import Any, Dict, List, Optional

_SCHEMA_VERSION = "1.0.0"
_CATALOG_SCHEMA_KEY = "__catalog_schema_version__"


class AssetCatalogSerializer:
    def __init__(self) -> None:
        self._lock = threading.Lock()

    @property
    def schema_version(self) -> str:
        return _SCHEMA_VERSION

    def serialize_catalog(self, entries: List[Dict[str, Any]]) -> str:
        """Serialize a list of catalog entries to a sorted-key JSON string."""
        try:
            payload = {
                _CATALOG_SCHEMA_KEY: _SCHEMA_VERSION,
                "entries": [self._normalize_entry(e) for e in entries],
            }
            return json.dumps(payload, sort_keys=True, indent=2, default=str)
        except Exception as exc:
            return json.dumps({"error": str(exc), _CATALOG_SCHEMA_KEY: _SCHEMA_VERSION})

    def deserialize_catalog(self, data: str) -> List[Dict[str, Any]]:
        """Deserialize a JSON string back to a list of catalog entries."""
        try:
            payload = json.loads(data)
            if not isinstance(payload, dict):
                return []
            return [dict(e) for e in (payload.get("entries") or [])]
        except Exception:
            return []

    def serialize_entry(self, entry: Dict[str, Any]) -> str:
        """Serialize a single catalog entry."""
        try:
            return json.dumps(self._normalize_entry(entry), sort_keys=True, default=str)
        except Exception as exc:
            return json.dumps({"error": str(exc)})

    def deserialize_entry(self, data: str) -> Dict[str, Any]:
        """Deserialize a single catalog entry."""
        try:
            result = json.loads(data)
            return dict(result) if isinstance(result, dict) else {}
        except Exception:
            return {}

    def _normalize_entry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure all entry fields are JSON-serializable."""
        if not isinstance(entry, dict):
            return {}
        out: Dict[str, Any] = {}
        for k, v in entry.items():
            if isinstance(v, (str, int, float, bool, type(None))):
                out[str(k)] = v
            elif isinstance(v, (list, tuple)):
                out[str(k)] = [self._normalize_value(i) for i in v]
            elif isinstance(v, dict):
                out[str(k)] = {str(kk): self._normalize_value(vv) for kk, vv in v.items()}
            else:
                out[str(k)] = str(v)
        return out

    def _normalize_value(self, v: Any) -> Any:
        if isinstance(v, (str, int, float, bool, type(None))):
            return v
        if isinstance(v, (list, tuple)):
            return [self._normalize_value(i) for i in v]
        if isinstance(v, dict):
            return {str(k): self._normalize_value(vv) for k, vv in v.items()}
        return str(v)


_INSTANCE: Optional[AssetCatalogSerializer] = None
_INSTANCE_LOCK = threading.Lock()


def get_asset_catalog_serializer() -> AssetCatalogSerializer:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = AssetCatalogSerializer()
    return _INSTANCE


def reset_asset_catalog_serializer_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
