"""
layout_application_engine.py — §47 Layout Realization & Scene Constraint Solver
================================================================================
Houdini bridge adapter: applies a ResolvedSceneLayout to actual Houdini nodes
by calling set_parms() with tx, ty, tz, rx, ry, rz for each asset.

This is the ONLY module in the layout_realization package that calls get_bridge().
All other modules are pure planning/computation.

Rules:
  - Each ResolvedTransform maps to one Houdini node path
  - Node paths are resolved from asset_id via the node_path_map argument
  - Assets with no node path are skipped and logged
  - Failures on individual nodes do not abort the batch (non-fatal per-asset)
  - Returns ApplicationResult with success/failure counts

Public API:
    ApplicationRecord
    ApplicationResult
    LayoutApplicationEngine
    get_layout_application_engine()
    reset_layout_application_engine_for_tests()
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.runtime.layout_realization.transform_resolver import ResolvedTransform


@dataclass
class ApplicationRecord:
    asset_id:   str
    node_path:  str
    ok:         bool = True
    error:      str  = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id":  self.asset_id,
            "node_path": self.node_path,
            "ok":        self.ok,
            "error":     self.error,
        }


@dataclass
class ApplicationResult:
    applied:     int = 0
    skipped:     int = 0
    failed:      int = 0
    records:     List[ApplicationRecord] = field(default_factory=list)
    ok:          bool = True
    errors:      List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "applied":  self.applied,
            "skipped":  self.skipped,
            "failed":   self.failed,
            "records":  [r.to_dict() for r in self.records],
            "ok":       self.ok,
            "errors":   list(self.errors),
        }


class LayoutApplicationEngine:
    """
    Applies a ResolvedSceneLayout to Houdini by setting transform parameters
    on each asset's corresponding Houdini node.

    The caller supplies a node_path_map: {asset_id → "/obj/geo1/null1"} so the
    engine knows which Houdini node to update. This map is built by the calling
    Houdini node (hou_mcp_apply_layout) after creating the geo network.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def apply_layout(
        self,
        transforms: List[ResolvedTransform],
        node_path_map: Dict[str, str],
        write_metadata: bool = True,
    ) -> ApplicationResult:
        """
        Apply world-space transforms to Houdini nodes.

        Args:
            transforms:     list of ResolvedTransform (from ResolvedSceneLayout)
            node_path_map:  map asset_id → Houdini node path string
            write_metadata: if True (default), also write relationship metadata
                            as Houdini user-data on each node (Tier 14.4.4)

        Returns: ApplicationResult. Never raises.
        """
        try:
            return self._apply(transforms, node_path_map, write_metadata)
        except Exception as exc:
            return ApplicationResult(
                ok=False,
                errors=[f"LayoutApplicationEngine.apply_layout failed: {exc}"],
            )

    def _apply(
        self,
        transforms: List[ResolvedTransform],
        node_path_map: Dict[str, str],
        write_metadata: bool,
    ) -> ApplicationResult:
        from src.utils.hou_bridge import get_bridge   # isolated import
        bridge = get_bridge()

        result = ApplicationResult()

        for xf in transforms:
            node_path = node_path_map.get(xf.asset_id, "")
            if not node_path:
                result.skipped += 1
                result.records.append(ApplicationRecord(
                    asset_id=xf.asset_id,
                    node_path="",
                    ok=False,
                    error="no node path mapping",
                ))
                continue

            try:
                bridge.set_parms(node_path, {
                    "tx": xf.tx,
                    "ty": xf.ty,
                    "tz": xf.tz,
                    "rx": xf.rx,
                    "ry": xf.ry,
                    "rz": xf.rz,
                })
                if write_metadata:
                    self._write_node_metadata(bridge, node_path, xf)
                result.applied += 1
                result.records.append(ApplicationRecord(
                    asset_id=xf.asset_id,
                    node_path=node_path,
                    ok=True,
                ))
            except Exception as exc:
                result.failed += 1
                result.records.append(ApplicationRecord(
                    asset_id=xf.asset_id,
                    node_path=node_path,
                    ok=False,
                    error=str(exc),
                ))

        return result

    def _write_node_metadata(
        self,
        bridge: Any,
        node_path: str,
        xf: ResolvedTransform,
    ) -> None:
        """
        Write relationship metadata to one Houdini node as user-data keys.
        Non-fatal — exceptions are silently swallowed so a metadata failure
        never aborts the transform application batch.
        """
        try:
            from src.runtime.layout_realization.relationship_metadata_writer import (
                build_userdata_from_transform,
            )
            userdata  = build_userdata_from_transform(xf)
            ud_repr   = repr(json.dumps(userdata))
            path_repr = repr(node_path)
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
            bridge.run_code(code)
        except Exception:
            pass  # metadata write failure must not abort transform application

    def build_transform_op_dicts(
        self,
        transforms: List[ResolvedTransform],
        node_path_map: Dict[str, str],
    ) -> List[Dict[str, Any]]:
        """
        Return a list of transaction operation dicts (no bridge call).
        Useful for dry-run preview and testing.
        """
        ops = []
        for xf in transforms:
            node_path = node_path_map.get(xf.asset_id, "")
            if not node_path:
                continue
            ops.append({
                "type":      "set_parms",
                "node_path": node_path,
                "parms": {
                    "tx": xf.tx,
                    "ty": xf.ty,
                    "tz": xf.tz,
                    "rx": xf.rx,
                    "ry": xf.ry,
                    "rz": xf.rz,
                },
            })
        return ops


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[LayoutApplicationEngine] = None
_lock = threading.Lock()


def get_layout_application_engine() -> LayoutApplicationEngine:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = LayoutApplicationEngine()
    return _instance


def reset_layout_application_engine_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
