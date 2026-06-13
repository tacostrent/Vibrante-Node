"""
Structural Serializer (Tier 10.3 — Structural Asset Classification)
====================================================================
Deterministic JSON serialization for structural classification objects.
All output uses sorted keys at schema version 1.0.0.

Public API:
    StructuralSerializer
    get_structural_serializer()
    reset_structural_serializer_for_tests()
"""

from __future__ import annotations

import json
import threading
from typing import Any, Dict, List, Optional

_SCHEMA_VERSION = "1.0.0"


class StructuralSerializer:
    """Sorted-key JSON serializer for structural classification objects."""

    _schema_version: str = _SCHEMA_VERSION

    def serialize_classification(self, result: Any) -> str:
        """Serialize a StructuralClassificationResult to JSON. Never raises."""
        try:
            d = result.to_dict() if hasattr(result, "to_dict") else dict(result)
            d["_schema_version"] = self._schema_version
            return json.dumps(d, sort_keys=True, default=str)
        except Exception as exc:
            return json.dumps(
                {"error": str(exc), "_schema_version": self._schema_version},
                sort_keys=True,
            )

    def serialize_review(self, review: Any) -> str:
        """Serialize a StructuralReviewResult to JSON. Never raises."""
        try:
            d = review.to_dict() if hasattr(review, "to_dict") else dict(review)
            d["_schema_version"] = self._schema_version
            return json.dumps(d, sort_keys=True, default=str)
        except Exception as exc:
            return json.dumps(
                {"error": str(exc), "_schema_version": self._schema_version},
                sort_keys=True,
            )

    def serialize_statistics(self, stats: Any) -> str:
        """Serialize a statistics summary dict to JSON. Never raises."""
        try:
            d = stats.summary() if hasattr(stats, "summary") else dict(stats)
            d["_schema_version"] = self._schema_version
            return json.dumps(d, sort_keys=True, default=str)
        except Exception as exc:
            return json.dumps(
                {"error": str(exc), "_schema_version": self._schema_version},
                sort_keys=True,
            )

    def serialize_batch(self, items: List[Any]) -> str:
        """Serialize a list of classification results. Never raises."""
        try:
            out = []
            for item in items:
                d = item.to_dict() if hasattr(item, "to_dict") else dict(item)
                d["_schema_version"] = self._schema_version
                out.append(d)
            return json.dumps(out, sort_keys=True, default=str)
        except Exception as exc:
            return json.dumps(
                [{"error": str(exc), "_schema_version": self._schema_version}],
                sort_keys=True,
            )

    def deserialize_classification(self, json_str: str) -> Dict[str, Any]:
        """Parse classification JSON. Returns dict. Never raises."""
        try:
            return json.loads(json_str)
        except Exception as exc:
            return {"error": str(exc)}

    def deserialize_batch(self, json_str: str) -> List[Dict[str, Any]]:
        """Parse a batch JSON string. Returns list. Never raises."""
        try:
            result = json.loads(json_str)
            return result if isinstance(result, list) else [result]
        except Exception as exc:
            return [{"error": str(exc)}]


# ──────────────────────────────────────────────────────────────────────────────
# Singleton
# ──────────────────────────────────────────────────────────────────────────────

_INSTANCE: Optional[StructuralSerializer] = None
_LOCK = threading.Lock()


def get_structural_serializer() -> StructuralSerializer:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = StructuralSerializer()
        return _INSTANCE


def reset_structural_serializer_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
