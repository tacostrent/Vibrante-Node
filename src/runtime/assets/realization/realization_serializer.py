"""
Realization Serializer (Tier 13)
==================================
Deterministic sorted-key JSON serializer for all Tier 13 models.

DESIGN RULES:
  1. No bridge calls, no file I/O side effects.
  2. Deterministic sorted-key JSON output.
  3. Embeds _schema_version = "1.0.0".
  4. Never raises in lenient mode.
  5. Singleton pattern.

Public API:
    RealizationSerializer
    get_realization_serializer()
    reset_realization_serializer_for_tests()
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SCHEMA_VERSION = "1.0.0"


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class RealizationSerializer:
    """
    Deterministic JSON serializer for Tier 13 models.
    Uses sort_keys=True for deterministic output.
    Embeds _schema_version in all serialized objects.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._serialize_count = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def to_json(self, obj: Any, compact: bool = False) -> str:
        """Serialize any dataclass or dict to sorted-key JSON string."""
        d = self._to_dict(obj)
        d["_schema_version"] = _SCHEMA_VERSION
        with self._lock:
            self._serialize_count += 1
        indent = None if compact else 2
        return json.dumps(d, sort_keys=True, indent=indent, default=str)

    def from_json(self, s: str, lenient: bool = True) -> Any:
        """Deserialize from JSON string. Returns dict or None on error."""
        try:
            d = json.loads(s)
            if isinstance(d, dict):
                d.pop("_schema_version", None)
            return d
        except Exception as exc:
            if lenient:
                return None
            raise ValueError(f"Deserialization failed: {exc}") from exc

    def save(self, obj: Any, path: str) -> None:
        """Save object to a JSON file."""
        content = self.to_json(obj)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def load(self, path: str, lenient: bool = True) -> Any:
        """Load object from a JSON file."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                return self.from_json(f.read(), lenient=lenient)
        except FileNotFoundError:
            if lenient:
                return None
            raise
        except Exception as exc:
            if lenient:
                return None
            raise ValueError(f"Load failed: {exc}") from exc

    def export(self, obj: Any) -> Dict[str, Any]:
        """Export object as a portable dict."""
        d = self._to_dict(obj)
        d["_schema_version"] = _SCHEMA_VERSION
        return d

    def import_(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and return a data dict."""
        if not isinstance(data, dict):
            return {}
        result = dict(data)
        result.pop("_schema_version", None)
        return result

    def to_json_list(self, objects: List[Any]) -> str:
        """Serialize a list of objects to a JSON array."""
        items = []
        for obj in objects:
            d = self._to_dict(obj)
            d["_schema_version"] = _SCHEMA_VERSION
            items.append(d)
        return json.dumps(items, sort_keys=True, indent=2, default=str)

    def from_json_list(self, s: str, lenient: bool = True) -> List[Any]:
        """Deserialize a JSON array."""
        try:
            items = json.loads(s)
            if isinstance(items, list):
                return [
                    {k: v for k, v in d.items() if k != "_schema_version"}
                    if isinstance(d, dict) else d
                    for d in items
                ]
            return []
        except Exception as exc:
            if lenient:
                return []
            raise ValueError(f"List deserialization failed: {exc}") from exc

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {"serialize_count": self._serialize_count}

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _to_dict(self, obj: Any) -> Dict[str, Any]:
        if isinstance(obj, dict):
            return dict(obj)
        if hasattr(obj, "to_dict"):
            return obj.to_dict()
        if hasattr(obj, "__dict__"):
            return dict(obj.__dict__)
        return {"value": str(obj)}


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[RealizationSerializer] = None
_INSTANCE_LOCK = threading.Lock()


def get_realization_serializer() -> RealizationSerializer:
    """Return the module-level singleton RealizationSerializer."""
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = RealizationSerializer()
    return _INSTANCE


def reset_realization_serializer_for_tests() -> None:
    """Replace the singleton. For test isolation only."""
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
