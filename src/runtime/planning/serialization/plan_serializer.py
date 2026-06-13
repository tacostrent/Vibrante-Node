"""
Plan Serializer (Tier 7 — Scene Planning Runtime)
==================================================
JSON serialization for ScenePlan objects using the existing storage
serialization layer from Tier 5.

Uses:
  - src.runtime.storage.serialization.serialize_record (sorted-key JSON)
  - src.runtime.storage.serialization.deserialize_record

Public API:
    PlanSerializationError
    PlanSerializer
        .to_json(plan, compact=False) -> str
        .from_json(s, lenient=True) -> ScenePlan
        .save(plan, path) -> None
        .load(path, lenient=True) -> ScenePlan
        .to_json_list(plans, compact=False) -> str
        .from_json_list(s, lenient=True) -> List[ScenePlan]
    get_plan_serializer() -> PlanSerializer   (singleton)
    reset_plan_serializer_for_tests()
"""

from __future__ import annotations

import json
import threading
from typing import List, Optional

from src.runtime.storage.serialization import serialize_record, deserialize_record
from src.runtime.planning.schema.scene_plan import ScenePlan

_RECORD_TYPE = "scene_plan"


class PlanSerializationError(ValueError):
    """Raised when ScenePlan serialization fails in non-lenient mode."""


class PlanSerializer:
    """Serialize / deserialize :class:`ScenePlan` objects."""

    def to_json(self, plan: ScenePlan, compact: bool = False) -> str:
        """Return a deterministic JSON string for *plan*.

        Args:
            plan:    The plan to serialize.
            compact: If True, omit whitespace (useful for wire transport).
        """
        data = plan.to_dict()
        data["record_type"] = _RECORD_TYPE
        if compact:
            return json.dumps(data, sort_keys=True, separators=(",", ":"))
        return serialize_record(data)

    def from_json(self, s: str, lenient: bool = True) -> ScenePlan:
        """Deserialize a JSON string back to :class:`ScenePlan`.

        Args:
            s:       JSON string produced by :meth:`to_json`.
            lenient: If True, return an empty ScenePlan on error.
                     If False, raise :class:`PlanSerializationError`.
        """
        try:
            data = deserialize_record(s)
            if not data:
                raise ValueError("Empty or invalid JSON.")
            data.pop("record_type", None)
            return ScenePlan.from_dict(data)
        except Exception as exc:
            if not lenient:
                raise PlanSerializationError(str(exc)) from exc
            return ScenePlan()

    def save(self, plan: ScenePlan, path: str) -> None:
        """Write a ScenePlan to *path* as JSON."""
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(self.to_json(plan))

    def load(self, path: str, lenient: bool = True) -> ScenePlan:
        """Read a ScenePlan from *path*.

        Args:
            path:    Filesystem path.
            lenient: If True, return empty plan on error.
                     If False, raise on missing file or corrupt JSON.
        """
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return self.from_json(fh.read(), lenient=lenient)
        except FileNotFoundError:
            if not lenient:
                raise
            return ScenePlan()
        except Exception as exc:
            if not lenient:
                raise PlanSerializationError(str(exc)) from exc
            return ScenePlan()

    def to_json_list(self, plans: List[ScenePlan], compact: bool = False) -> str:
        """Serialize a list of ScenePlan objects to a JSON array string."""
        return json.dumps(
            [json.loads(self.to_json(p, compact=compact)) for p in plans],
            sort_keys=True,
        )

    def from_json_list(self, s: str, lenient: bool = True) -> List[ScenePlan]:
        """Deserialize a JSON array string to a list of ScenePlan objects."""
        try:
            items = json.loads(s)
            if not isinstance(items, list):
                raise ValueError("Expected a JSON array.")
            result: List[ScenePlan] = []
            for item in items:
                if isinstance(item, dict):
                    item.pop("record_type", None)
                    result.append(ScenePlan.from_dict(item))
            return result
        except Exception as exc:
            if not lenient:
                raise PlanSerializationError(str(exc)) from exc
            return []


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[PlanSerializer] = None
_INSTANCE_LOCK = threading.Lock()


def get_plan_serializer() -> PlanSerializer:
    """Return the module-level singleton PlanSerializer."""
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = PlanSerializer()
    return _INSTANCE


def reset_plan_serializer_for_tests() -> None:
    """Replace the singleton. For test isolation only."""
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
