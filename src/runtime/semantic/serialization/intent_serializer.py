"""
Scene Intent Serializer (Phase 1)
====================================
JSON serialization and deserialization for SceneIntent objects with:
  - Schema version compatibility checks
  - Pretty-print and compact modes
  - Batch serialization (list of intents)
  - Schema migration stubs for future version upgrades

Design rules:
  - Serializer never validates content — call SceneIntentValidator separately.
  - File I/O is synchronous (no asyncio — intent files are small).
  - `from_json_string` is lenient: skips unknown keys; fills missing with defaults.
  - Schema version mismatch raises SchemaVersionError unless `lenient=True`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..schema.scene_intent_schema import SCHEMA_VERSION, SceneIntent


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class SchemaVersionError(ValueError):
    """Raised when a serialized intent's schema version is incompatible."""


class IntentSerializationError(ValueError):
    """Raised when an intent cannot be serialized or deserialized."""


# ---------------------------------------------------------------------------
# Serializer
# ---------------------------------------------------------------------------

class IntentSerializer:
    """Serializes and deserializes SceneIntent objects to/from JSON.

    Usage::

        serializer = IntentSerializer()
        json_str = serializer.to_json(intent)
        intent2  = serializer.from_json(json_str)
        serializer.save(intent, "/path/to/intent.json")
        intent3  = serializer.load("/path/to/intent.json")
    """

    # Supported versions for reading (current + older compatible versions)
    _SUPPORTED_READ_VERSIONS = frozenset({"1.0.0"})

    def __init__(self, indent: int = 2):
        self._indent = indent

    # ------------------------------------------------------------------
    # Single intent
    # ------------------------------------------------------------------

    def to_json(self, intent: SceneIntent, compact: bool = False) -> str:
        """Serialize a SceneIntent to a JSON string.

        Args:
            intent:  The SceneIntent to serialize.
            compact: If True, output compact JSON (no indentation).

        Returns:
            JSON string.
        """
        try:
            d = intent.to_dict()
            return json.dumps(d, indent=None if compact else self._indent, ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            raise IntentSerializationError(f"Failed to serialize SceneIntent: {exc}") from exc

    def from_json(
        self,
        json_str: str,
        lenient: bool = False,
    ) -> SceneIntent:
        """Deserialize a SceneIntent from a JSON string.

        Args:
            json_str: JSON string produced by `to_json`.
            lenient:  If True, ignore schema version mismatches.

        Returns:
            Reconstructed SceneIntent.

        Raises:
            IntentSerializationError: If the JSON is malformed.
            SchemaVersionError:       If schema version is incompatible and lenient=False.
        """
        try:
            d = json.loads(json_str)
        except json.JSONDecodeError as exc:
            raise IntentSerializationError(f"Malformed JSON: {exc}") from exc

        if not isinstance(d, dict):
            raise IntentSerializationError(
                f"Expected a JSON object (dict), got {type(d).__name__}"
            )

        self._check_version(d, lenient)
        return self._migrate_and_load(d)

    def save(
        self,
        intent: SceneIntent,
        path: str | Path,
        compact: bool = False,
    ) -> None:
        """Write a SceneIntent to a JSON file.

        Args:
            intent:  The SceneIntent to save.
            path:    File path (created if absent; parent dirs must exist).
            compact: If True, write compact JSON.
        """
        p = Path(path)
        json_str = self.to_json(intent, compact=compact)
        p.write_text(json_str, encoding="utf-8")

    def load(
        self,
        path: str | Path,
        lenient: bool = False,
    ) -> SceneIntent:
        """Load a SceneIntent from a JSON file.

        Args:
            path:    File path to read.
            lenient: If True, ignore schema version mismatches.

        Returns:
            Deserialized SceneIntent.
        """
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Intent file not found: {p}")
        json_str = p.read_text(encoding="utf-8")
        return self.from_json(json_str, lenient=lenient)

    # ------------------------------------------------------------------
    # Batch operations
    # ------------------------------------------------------------------

    def to_json_list(self, intents: List[SceneIntent], compact: bool = False) -> str:
        """Serialize a list of SceneIntents to a JSON array string."""
        try:
            dicts = [intent.to_dict() for intent in intents]
            return json.dumps(dicts, indent=None if compact else self._indent, ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            raise IntentSerializationError(f"Failed to serialize intent list: {exc}") from exc

    def from_json_list(self, json_str: str, lenient: bool = False) -> List[SceneIntent]:
        """Deserialize a JSON array of SceneIntents."""
        try:
            items = json.loads(json_str)
        except json.JSONDecodeError as exc:
            raise IntentSerializationError(f"Malformed JSON array: {exc}") from exc

        if not isinstance(items, list):
            raise IntentSerializationError(
                f"Expected a JSON array, got {type(items).__name__}"
            )

        results: List[SceneIntent] = []
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                raise IntentSerializationError(
                    f"Item {i} in JSON array is not a dict: {type(item).__name__}"
                )
            self._check_version(item, lenient)
            results.append(self._migrate_and_load(item))
        return results

    def save_list(
        self,
        intents: List[SceneIntent],
        path: str | Path,
        compact: bool = False,
    ) -> None:
        """Write a list of SceneIntents to a JSON file (array)."""
        p = Path(path)
        json_str = self.to_json_list(intents, compact=compact)
        p.write_text(json_str, encoding="utf-8")

    def load_list(
        self,
        path: str | Path,
        lenient: bool = False,
    ) -> List[SceneIntent]:
        """Load a list of SceneIntents from a JSON file (array)."""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Intent list file not found: {p}")
        json_str = p.read_text(encoding="utf-8")
        return self.from_json_list(json_str, lenient=lenient)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _check_version(self, d: Dict[str, Any], lenient: bool) -> None:
        version = d.get("schema_version", SCHEMA_VERSION)
        if version not in self._SUPPORTED_READ_VERSIONS:
            msg = (
                f"Unsupported schema version '{version}'. "
                f"Supported: {sorted(self._SUPPORTED_READ_VERSIONS)}."
            )
            if lenient:
                pass  # silently continue
            else:
                raise SchemaVersionError(msg)

    def _migrate_and_load(self, d: Dict[str, Any]) -> SceneIntent:
        """Apply any version migrations then call SceneIntent.from_dict."""
        version = d.get("schema_version", SCHEMA_VERSION)
        # Migration stubs — add cases when schema version bumps
        # if version == "0.9.0":
        #     d = _migrate_0_9_to_1_0(d)
        return SceneIntent.from_dict(d)


# ---------------------------------------------------------------------------
# Shared instance
# ---------------------------------------------------------------------------

_serializer: Optional[IntentSerializer] = None


def get_intent_serializer() -> IntentSerializer:
    """Return the shared IntentSerializer instance."""
    global _serializer
    if _serializer is None:
        _serializer = IntentSerializer()
    return _serializer


def reset_intent_serializer_for_tests() -> None:
    """Reset shared instance for test isolation."""
    global _serializer
    _serializer = None
