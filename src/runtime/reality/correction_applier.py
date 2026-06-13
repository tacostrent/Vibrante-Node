"""
correction_applier.py — §54 Reality Intelligence (Tier 15.0+)
==============================================================
Applies a CorrectionPlan to ACTUAL Houdini geometry. The §54 Relationship
Correction Pass "modifies Houdini geometry. Not metadata. Not plans."

This is one of only two modules in the reality package that touches the
Houdini bridge (the other is geometry_inspector.py). Per-op failures are
non-fatal — the batch continues.

Public API:
    AppliedCorrection
    CorrectionApplyResult
    CorrectionApplier
    get_correction_applier()
    reset_correction_applier_for_tests()
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AppliedCorrection:
    asset_id:  str
    node_path: str
    parms:     Dict[str, float] = field(default_factory=dict)
    ok:        bool = True
    error:     str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id":  self.asset_id,
            "node_path": self.node_path,
            "parms":     dict(self.parms),
            "ok":        self.ok,
            "error":     self.error,
        }


@dataclass
class CorrectionApplyResult:
    applied: int = 0
    skipped: int = 0
    failed:  int = 0
    records: List[AppliedCorrection] = field(default_factory=list)
    ok:      bool = True
    errors:  List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "applied": self.applied,
            "skipped": self.skipped,
            "failed":  self.failed,
            "records": [r.to_dict() for r in self.records],
            "ok":      self.ok,
            "errors":  list(self.errors),
        }


class CorrectionApplier:
    """Executes correction op dicts against live Houdini nodes."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def apply(self, ops: List[Dict[str, Any]],
              node_path_map: Dict[str, str]) -> CorrectionApplyResult:
        """
        Apply correction ops (from RealityCorrectionPass.build_correction_plan)
        to Houdini via set_parms. node_path_map maps asset_id → node path.
        Never raises.
        """
        try:
            return self._apply(ops or [], node_path_map or {})
        except Exception as exc:
            return CorrectionApplyResult(
                ok=False,
                errors=[f"CorrectionApplier.apply failed: {exc}"],
            )

    def _apply(self, ops: List[Dict[str, Any]],
               node_path_map: Dict[str, str]) -> CorrectionApplyResult:
        from src.utils.hou_bridge import get_bridge   # isolated import
        bridge = get_bridge()

        result = CorrectionApplyResult()
        for op in ops:
            if not isinstance(op, dict):
                result.skipped += 1
                continue
            asset_id = str(op.get("asset_id", ""))
            parms = op.get("parms") or {}
            node_path = node_path_map.get(asset_id, "")
            if not node_path or not parms:
                result.skipped += 1
                result.records.append(AppliedCorrection(
                    asset_id=asset_id, node_path=node_path, parms=dict(parms),
                    ok=False, error="no node path mapping" if not node_path
                                    else "empty parms",
                ))
                continue
            try:
                bridge.set_parms(node_path, {k: float(v) for k, v in parms.items()})
                result.applied += 1
                result.records.append(AppliedCorrection(
                    asset_id=asset_id, node_path=node_path, parms=dict(parms),
                ))
            except Exception as exc:
                result.failed += 1
                result.records.append(AppliedCorrection(
                    asset_id=asset_id, node_path=node_path, parms=dict(parms),
                    ok=False, error=str(exc),
                ))
        return result

    def build_op_dicts(self, ops: List[Dict[str, Any]],
                       node_path_map: Dict[str, str]) -> List[Dict[str, Any]]:
        """Dry-run preview: resolve node paths without touching the bridge."""
        resolved = []
        for op in ops or []:
            if not isinstance(op, dict):
                continue
            node_path = (node_path_map or {}).get(str(op.get("asset_id", "")), "")
            if not node_path:
                continue
            resolved.append({
                "type":      "set_parms",
                "node_path": node_path,
                "parms":     dict(op.get("parms") or {}),
                "reason":    str(op.get("reason", "")),
            })
        return resolved


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[CorrectionApplier] = None
_lock = threading.Lock()


def get_correction_applier() -> CorrectionApplier:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = CorrectionApplier()
    return _instance


def reset_correction_applier_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
