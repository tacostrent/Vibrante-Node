"""
Geometry Serializer (Tier 9.7 — Geometry Intelligence)
=======================================================
Deterministic JSON serialization for geometry intelligence results.
All output is sorted-key JSON at schema version 1.0.0.

Public API:
    GeometrySerializer
    get_geometry_serializer()
    reset_geometry_serializer_for_tests()
"""

from __future__ import annotations

import json
import threading
from typing import Any, Dict, List, Optional, Union

_SCHEMA_VERSION = "1.0.0"


class GeometrySerializer:
    """Sorted-key JSON serializer for geometry intelligence objects."""

    _schema_version: str = _SCHEMA_VERSION

    def serialize_metrics(self, metrics: Any) -> str:
        """Serialize an AssetMetrics instance to JSON string. Never raises."""
        try:
            d = metrics.to_dict() if hasattr(metrics, "to_dict") else dict(metrics)
            d["_schema_version"] = self._schema_version
            return json.dumps(d, sort_keys=True, default=str, indent=None)
        except Exception as exc:
            return json.dumps(
                {"error": str(exc), "_schema_version": self._schema_version},
                sort_keys=True,
            )

    def serialize_analysis(self, result: Any) -> str:
        """Serialize a GeometryAnalysisResult to JSON string. Never raises."""
        try:
            d = result.to_dict() if hasattr(result, "to_dict") else dict(result)
            d["_schema_version"] = self._schema_version
            return json.dumps(d, sort_keys=True, default=str, indent=None)
        except Exception as exc:
            return json.dumps(
                {"error": str(exc), "_schema_version": self._schema_version},
                sort_keys=True,
            )

    def serialize_review(self, review: Any) -> str:
        """Serialize a GeometryReviewResult to JSON string. Never raises."""
        try:
            d = review.to_dict() if hasattr(review, "to_dict") else dict(review)
            d["_schema_version"] = self._schema_version
            return json.dumps(d, sort_keys=True, default=str, indent=None)
        except Exception as exc:
            return json.dumps(
                {"error": str(exc), "_schema_version": self._schema_version},
                sort_keys=True,
            )

    def deserialize_metrics(self, json_str: str) -> Dict[str, Any]:
        """Parse metrics JSON. Returns dict. Never raises."""
        try:
            return json.loads(json_str)
        except Exception as exc:
            return {"error": str(exc)}

    def deserialize_review(self, json_str: str) -> Dict[str, Any]:
        """Parse review JSON. Returns dict. Never raises."""
        try:
            return json.loads(json_str)
        except Exception as exc:
            return {"error": str(exc)}

    def serialize_batch(self, items: List[Any]) -> str:
        """Serialize a list of geometry objects. Never raises."""
        try:
            out = []
            for item in items:
                if hasattr(item, "to_dict"):
                    out.append(item.to_dict())
                else:
                    out.append(dict(item))
            return json.dumps(
                {"_schema_version": self._schema_version, "items": out},
                sort_keys=True,
                default=str,
            )
        except Exception as exc:
            return json.dumps(
                {"error": str(exc), "_schema_version": self._schema_version},
                sort_keys=True,
            )

    @property
    def schema_version(self) -> str:
        return self._schema_version


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[GeometrySerializer] = None
_LOCK = threading.Lock()


def get_geometry_serializer() -> GeometrySerializer:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = GeometrySerializer()
        return _INSTANCE


def reset_geometry_serializer_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
