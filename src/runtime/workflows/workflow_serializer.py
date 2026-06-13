"""
Workflow Serializer (Tier 10 — Workflow Packs & Production Blueprints)
======================================================================
Persists WorkflowPack objects to/from deterministic sorted-key JSON.

DESIGN RULES:
  1. Deterministic — sorted keys, consistent schema_version embedding.
  2. Lenient mode available for partial deserialization.
  3. Never raises in lenient mode.

Public API:
    WorkflowSerializer
    get_workflow_serializer()
    reset_workflow_serializer_for_tests()
"""

from __future__ import annotations

import json
import os
import threading
from typing import Any, Dict, List, Optional

from src.runtime.workflows.workflow_pack import WorkflowPack, PACK_SCHEMA_VERSION


class WorkflowSerializer:
    """Serializes and persists WorkflowPack objects."""

    def __init__(self) -> None:
        self._serialize_count = 0
        self._lock = threading.Lock()

    # -----------------------------------------------------------------
    def to_json(self, pack: WorkflowPack, indent: int = 2) -> str:
        """Serialize a pack to deterministic sorted-key JSON."""
        with self._lock:
            self._serialize_count += 1
        d = pack.to_dict()
        d["_schema_version"] = PACK_SCHEMA_VERSION
        return json.dumps(d, sort_keys=True, indent=indent)

    def from_json(
        self, s: str, lenient: bool = False
    ) -> Optional[WorkflowPack]:
        """
        Deserialize from JSON.
        Raises json.JSONDecodeError / KeyError on error unless lenient=True.
        """
        try:
            d = json.loads(s)
            d.pop("_schema_version", None)
            return WorkflowPack.from_dict(d)
        except Exception:
            if lenient:
                return None
            raise

    # -----------------------------------------------------------------
    def save_pack(self, pack: WorkflowPack, path: str) -> bool:
        """Write a pack to a .json file.  Returns True on success."""
        try:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.to_json(pack))
            return True
        except Exception:
            return False

    def load_pack(self, path: str, lenient: bool = False) -> Optional[WorkflowPack]:
        """Load a pack from a .json file."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                return self.from_json(f.read(), lenient=lenient)
        except Exception:
            if lenient:
                return None
            raise

    # -----------------------------------------------------------------
    def export_pack(self, pack: WorkflowPack) -> Dict[str, Any]:
        """Export a pack as a portable dict (for API/UI use)."""
        d = pack.to_dict()
        d["_schema_version"] = PACK_SCHEMA_VERSION
        return d

    def import_pack(
        self, data: Dict[str, Any], lenient: bool = False
    ) -> Optional[WorkflowPack]:
        """Import a pack from a portable dict."""
        try:
            data.pop("_schema_version", None)
            return WorkflowPack.from_dict(data)
        except Exception:
            if lenient:
                return None
            raise

    # -----------------------------------------------------------------
    def to_json_list(self, packs: List[WorkflowPack], indent: int = 2) -> str:
        """Serialize a list of packs."""
        return json.dumps(
            [json.loads(self.to_json(p, indent=0)) for p in packs],
            sort_keys=True, indent=indent,
        )

    def from_json_list(
        self, s: str, lenient: bool = False
    ) -> List[WorkflowPack]:
        """Deserialize a list of packs from JSON array."""
        try:
            items = json.loads(s)
            result: List[WorkflowPack] = []
            for item in items:
                item.pop("_schema_version", None)
                pack = WorkflowPack.from_dict(item)
                if pack:
                    result.append(pack)
            return result
        except Exception:
            if lenient:
                return []
            raise

    def stats(self) -> Dict[str, Any]:
        return {"serialize_count": self._serialize_count}


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[WorkflowSerializer] = None
_lock = threading.Lock()


def get_workflow_serializer() -> WorkflowSerializer:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = WorkflowSerializer()
    return _instance


def reset_workflow_serializer_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
