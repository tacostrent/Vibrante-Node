"""
asset_suitability_serializer.py — §45 Semantic Asset Suitability Ranking
=========================================================================
Sorted-key JSON serialization for suitability results.

Public API:
    AssetSuitabilitySerializer.serialize(data) -> str
    AssetSuitabilitySerializer.deserialize(json_str) -> dict
"""

import json
import threading

_SCHEMA_VERSION = "1.0.0"


class AssetSuitabilitySerializer:

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def serialize(self, data) -> str:
        """Serialize a to_dict()-compatible object or dict to sorted-key JSON."""
        try:
            if hasattr(data, "to_dict"):
                raw = data.to_dict()
            else:
                raw = dict(data)
            raw["_schema_version"] = _SCHEMA_VERSION
            return json.dumps(raw, sort_keys=True, indent=2)
        except Exception as exc:
            return json.dumps({"error": str(exc), "_schema_version": _SCHEMA_VERSION})

    def deserialize(self, json_str: str) -> dict:
        """Parse JSON string into a dict."""
        try:
            return json.loads(json_str)
        except Exception as exc:
            return {"error": str(exc)}

    def serialize_report(self, report: dict) -> str:
        """Serialize a selection report dict."""
        try:
            d = dict(report)
            d["_schema_version"] = _SCHEMA_VERSION
            return json.dumps(d, sort_keys=True, indent=2)
        except Exception as exc:
            return json.dumps({"error": str(exc)})


_instance: AssetSuitabilitySerializer | None = None
_instance_lock = threading.Lock()


def get_asset_suitability_serializer() -> AssetSuitabilitySerializer:
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = AssetSuitabilitySerializer()
    return _instance


def reset_asset_suitability_serializer_for_tests() -> None:
    global _instance
    with _instance_lock:
        _instance = None
