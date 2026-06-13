"""
JSON Serialization Layer (Tier 5 — Storage Architecture)
=========================================================
Centralised deterministic JSON serialization for all Tier 5 record types.

Design principles:
    - Sorted keys → deterministic output regardless of dict insertion order
    - Schema version embedded → migration-safe round-trips
    - Round-trip fidelity → serialize → deserialize produces equal dicts
    - Type-specific helpers → self-documenting call sites
    - Migration framework → future schema changes apply transparently on load

Schema version: 1

Migration framework
-------------------
When ``SCHEMA_VERSION`` is bumped, register a migrator::

    from src.runtime.storage.serialization import register_migrator

    def _v1_to_v2_scene(record):
        # Add a new field introduced in v2 with a safe default
        return {**record, "new_field": record.get("new_field", "")}

    register_migrator(from_version=1, record_type="scene", fn=_v1_to_v2_scene)

On deserialization the framework walks ``from_version → SCHEMA_VERSION`` and
applies any registered migrator at each version step:
  - A type-specific migrator ``(v, "scene")`` takes priority over a generic
    migrator ``(v, None)`` at the same version step.
  - Missing version entries are skipped; partial migrations are safe.

Public API:
    serialize_record(record)   -> str   (JSON, sorted keys, _schema_version embedded)
    deserialize_record(s)      -> dict  (_schema_version stripped, migrations applied)

    register_migrator(from_version, record_type, fn) -> None
    reset_migrators_for_tests()                      -> None

    serialize_scene(data)           -> str
    deserialize_scene(s)            -> dict
    serialize_review(data)          -> str
    deserialize_review(s)           -> dict
    serialize_pattern(data)         -> str
    deserialize_pattern(s)          -> dict
    serialize_failure(data)         -> str
    deserialize_failure(s)          -> dict
    serialize_asset(data)           -> str
    deserialize_asset(s)            -> dict
    serialize_relationship(data)    -> str
    deserialize_relationship(s)     -> dict
"""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, Optional, Tuple

SCHEMA_VERSION: int = 1
_VERSION_KEY:   str = "_schema_version"

# ---------------------------------------------------------------------------
# Migration registry
# ---------------------------------------------------------------------------

# Keys:   (from_version, record_type)  where record_type=None means "all types"
# Values: pure function  dict -> dict  (must not mutate its argument)
_MIGRATORS: Dict[
    Tuple[int, Optional[str]],
    Callable[[Dict[str, Any]], Dict[str, Any]],
] = {}


def register_migrator(
    from_version: int,
    record_type: Optional[str],
    fn: Callable[[Dict[str, Any]], Dict[str, Any]],
) -> None:
    """Register a migration for records at *from_version* → *from_version + 1*.

    Args:
        from_version:  Schema version the migration upgrades *from*.
        record_type:   Apply only when ``record["record_type"] == record_type``,
                       or ``None`` to apply to every record at this version step.
        fn:            Pure function ``dict -> dict``.  Must not mutate its input.

    A type-specific migrator ``(v, "scene")`` takes priority over a generic
    migrator ``(v, None)`` at the same version step — at most one migrator fires
    per step.
    """
    _MIGRATORS[(from_version, record_type)] = fn


def reset_migrators_for_tests() -> None:
    """Clear all registered migrators.  For test isolation only."""
    _MIGRATORS.clear()


def _apply_migrations(record: Dict[str, Any], from_version: int) -> Dict[str, Any]:
    """Walk the migration chain from *from_version* to ``SCHEMA_VERSION``."""
    result = dict(record)
    for v in range(from_version, SCHEMA_VERSION):
        rt = result.get("record_type")
        # Type-specific migrator takes priority; generic (None) is the fallback.
        for key in ((v, rt), (v, None)):
            fn = _MIGRATORS.get(key)
            if fn is not None:
                result = fn(result)
                break  # exactly one migrator per version step
    return result


# ---------------------------------------------------------------------------
# Generic record helpers
# ---------------------------------------------------------------------------

def serialize_record(record: Dict[str, Any]) -> str:
    """Serialize any record to deterministic JSON.

    - Keys are sorted alphabetically so output is identical regardless of the
      dict's insertion order.
    - ``_schema_version`` is embedded (set to ``SCHEMA_VERSION`` if absent).
    - Non-JSON-serializable values are coerced to strings via ``default=str``.
    """
    out = dict(record)
    out.setdefault(_VERSION_KEY, SCHEMA_VERSION)
    return json.dumps(out, sort_keys=True, default=str)


def deserialize_record(s: str) -> Dict[str, Any]:
    """Deserialize a JSON string back to a record dict.

    - Strips ``_schema_version`` (internal storage field).
    - Applies any registered migrations when the stored version is older than
      ``SCHEMA_VERSION``.
    - Returns an empty dict on any parse error or if the JSON is not a dict.
    """
    try:
        data = json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return {}
    if not isinstance(data, dict):
        return {}
    version = int(data.pop(_VERSION_KEY, 1))
    if version < SCHEMA_VERSION:
        data = _apply_migrations(data, version)
    return data


# ---------------------------------------------------------------------------
# Type-specific helpers
# ---------------------------------------------------------------------------

def serialize_scene(data: Dict[str, Any]) -> str:
    """Serialize a scene record."""
    return serialize_record(data)


def deserialize_scene(s: str) -> Dict[str, Any]:
    """Deserialize a scene record."""
    return deserialize_record(s)


def serialize_review(data: Dict[str, Any]) -> str:
    """Serialize a review record."""
    return serialize_record(data)


def deserialize_review(s: str) -> Dict[str, Any]:
    """Deserialize a review record."""
    return deserialize_record(s)


def serialize_pattern(data: Dict[str, Any]) -> str:
    """Serialize a pattern-usage record."""
    return serialize_record(data)


def deserialize_pattern(s: str) -> Dict[str, Any]:
    """Deserialize a pattern-usage record."""
    return deserialize_record(s)


def serialize_failure(data: Dict[str, Any]) -> str:
    """Serialize a failure record."""
    return serialize_record(data)


def deserialize_failure(s: str) -> Dict[str, Any]:
    """Deserialize a failure record."""
    return deserialize_record(s)


def serialize_asset(data: Dict[str, Any]) -> str:
    """Serialize an asset record."""
    return serialize_record(data)


def deserialize_asset(s: str) -> Dict[str, Any]:
    """Deserialize an asset record."""
    return deserialize_record(s)


def serialize_relationship(data: Dict[str, Any]) -> str:
    """Serialize a relationship record."""
    return serialize_record(data)


def deserialize_relationship(s: str) -> Dict[str, Any]:
    """Deserialize a relationship record."""
    return deserialize_record(s)
