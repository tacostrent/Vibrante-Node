"""
layout_serializer.py — §46 Semantic Furniture Layout Engine
===========================================================
Sorted-key JSON serialization for layout plans and results.
Schema version 1.0.0.

Public API:
    LayoutSerializer
    get_layout_serializer()
    reset_layout_serializer_for_tests()
"""

import json
import threading
from typing import Any, Optional

_SCHEMA_VERSION = "1.0.0"


class LayoutSerializer:
    """Sorted-key JSON serializer for layout data."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def serialize(self, data: Any) -> str:
        """Serialize a to_dict()-compatible object or dict to sorted-key JSON."""
        try:
            raw = data.to_dict() if hasattr(data, "to_dict") else dict(data)
            raw["_schema_version"] = _SCHEMA_VERSION
            return json.dumps(raw, sort_keys=True, indent=2)
        except Exception as exc:
            return json.dumps({"error": str(exc), "_schema_version": _SCHEMA_VERSION})

    def deserialize(self, json_str: str) -> dict:
        """Parse a JSON string into a dict."""
        try:
            return json.loads(json_str)
        except Exception as exc:
            return {"error": str(exc)}

    def serialize_plan(self, plan: dict) -> str:
        """Serialize a layout plan dict with schema version."""
        try:
            d = dict(plan)
            d["_schema_version"] = _SCHEMA_VERSION
            return json.dumps(d, sort_keys=True, indent=2)
        except Exception as exc:
            return json.dumps({"error": str(exc)})

    def serialize_debug_report(self, report: dict) -> str:
        """Serialize a debug/summary report dict."""
        try:
            d = dict(report)
            d["_schema_version"] = _SCHEMA_VERSION
            return json.dumps(d, sort_keys=True, indent=2)
        except Exception as exc:
            return json.dumps({"error": str(exc)})


_instance: Optional[LayoutSerializer] = None
_instance_lock = threading.Lock()


def get_layout_serializer() -> LayoutSerializer:
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = LayoutSerializer()
    return _instance


def reset_layout_serializer_for_tests() -> None:
    global _instance
    with _instance_lock:
        _instance = None
