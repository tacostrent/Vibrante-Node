"""
metadata_application_engine.py — §47 Tier 14.4.4 Relationship Metadata Persistence
======================================================================================
Houdini bridge adapter: writes relationship metadata onto every realized node
via hou.Node.setUserData().

This is the ONLY module in the layout_realization package (besides
layout_application_engine) that calls get_bridge().

Each node receives exactly 9 user-data keys (METADATA_KEYS from
relationship_metadata_writer.py).  The write is non-fatal per asset — one
failed node does not abort the batch.

Public API:
    MetadataWriteRecord
    MetadataWriteResult
    MetadataApplicationEngine
    get_metadata_application_engine()
    reset_metadata_application_engine_for_tests()
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.runtime.layout_realization.relationship_metadata_writer import (
    AssetRelationshipMetadata,
    METADATA_KEYS,
)


@dataclass
class MetadataWriteRecord:
    asset_id:  str
    node_path: str
    ok:        bool = True
    error:     str  = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id":  self.asset_id,
            "node_path": self.node_path,
            "ok":        self.ok,
            "error":     self.error,
        }


@dataclass
class MetadataWriteResult:
    written:  int = 0
    skipped:  int = 0
    failed:   int = 0
    records:  List[MetadataWriteRecord] = field(default_factory=list)
    ok:       bool = True
    errors:   List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "written":  self.written,
            "skipped":  self.skipped,
            "failed":   self.failed,
            "records":  [r.to_dict() for r in self.records],
            "ok":       self.ok,
            "errors":   list(self.errors),
        }


class MetadataApplicationEngine:
    """
    Writes AssetRelationshipMetadata onto Houdini nodes via setUserData().

    Each metadata key is stored as a string user-data entry. The entire dict is
    serialised to JSON and passed as a repr()-safe literal inside a run_code()
    call so no shell-injection is possible regardless of asset names.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def write_metadata(
        self,
        metadata_records: List[AssetRelationshipMetadata],
    ) -> MetadataWriteResult:
        """
        Write all metadata records to their Houdini nodes.

        Records with an empty node_path are skipped (not failed).
        Never raises.
        """
        try:
            return self._write(metadata_records)
        except Exception as exc:
            return MetadataWriteResult(
                ok=False,
                errors=[f"MetadataApplicationEngine.write_metadata failed: {exc}"],
            )

    def _write(self, records: List[AssetRelationshipMetadata]) -> MetadataWriteResult:
        from src.utils.hou_bridge import get_bridge  # isolated import
        bridge = get_bridge()

        result = MetadataWriteResult()
        for rec in records:
            if not rec.node_path:
                result.skipped += 1
                result.records.append(MetadataWriteRecord(
                    asset_id=rec.asset_id,
                    node_path="",
                    ok=False,
                    error="no node path",
                ))
                continue

            try:
                self._write_single(bridge, rec)
                result.written += 1
                result.records.append(MetadataWriteRecord(
                    asset_id=rec.asset_id,
                    node_path=rec.node_path,
                    ok=True,
                ))
            except Exception as exc:
                result.failed += 1
                result.records.append(MetadataWriteRecord(
                    asset_id=rec.asset_id,
                    node_path=rec.node_path,
                    ok=False,
                    error=str(exc),
                ))

        if result.failed > 0:
            result.ok = False
            result.errors.append(
                f"{result.failed} node(s) failed metadata write"
            )
        return result

    def _write_single(self, bridge: Any, rec: AssetRelationshipMetadata) -> None:
        """
        Write all 9 metadata keys to a single Houdini node.
        Uses run_code() so the data is embedded as a repr()-safe JSON literal —
        no injection risk regardless of asset name content.
        """
        userdata   = rec.to_houdini_userdata()
        ud_repr    = repr(json.dumps(userdata))   # safe repr of JSON string
        path_repr  = repr(rec.node_path)

        code = (
            "import json\n"
            "_n = hou.node(" + path_repr + ")\n"
            "if _n:\n"
            "    _meta = json.loads(" + ud_repr + ")\n"
            "    for _k, _v in _meta.items():\n"
            "        _n.setUserData(_k, str(_v))\n"
            "    result = True\n"
            "else:\n"
            "    result = False\n"
        )
        run_result = bridge.run_code(code)
        if not run_result.get("result", False):
            raise RuntimeError(f"Node not found: {rec.node_path}")


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[MetadataApplicationEngine] = None
_lock = threading.Lock()


def get_metadata_application_engine() -> MetadataApplicationEngine:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = MetadataApplicationEngine()
    return _instance


def reset_metadata_application_engine_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
