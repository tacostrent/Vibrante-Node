"""
architectural_feature_realizer.py — Tier 10.5 Structural Openings & Architectural Features
============================================================================================
The ONLY module in this package that calls get_bridge().

Creates actual Houdini geometry nodes for every feature in an ArchitecturalPlan:

  /obj/sh_door_opening_{idx}    — box-SOP void volume for each door opening
  /obj/sh_window_opening_{idx}  — box-SOP void volume for each window opening
  /obj/sh_beam_{idx}            — box-SOP geometry for each beam
  /obj/sh_fireplace_{idx}       — box-SOP reference geometry for each fireplace
  /obj/sh_shelf_{idx}           — box-SOP geometry for each wall shelf

For opening nodes the box represents the void that should be subtracted from
the wall geometry. For structural nodes the box represents the asset itself.

Architecture:
  All other modules in this package are pure planning (no bridge).
  This adapter is called only from the Houdini node
  hou_mcp_architecture_realize.

Public API:
  RealizationRecord
  RealizationResult
  ArchitecturalFeatureRealizer
  get_architectural_feature_realizer()
  reset_architectural_feature_realizer_for_tests()
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.runtime.architectural_features.architectural_plan import (
    ArchitecturalPlan,
    ArchitecturalOpening,
    FireplacePlacement,
    BeamPlacement,
    WallShelfPlacement,
)


@dataclass
class RealizationRecord:
    feature_id:        str
    feature_type:      str          # "door_opening" | "window_opening" | "beam" | ...
    houdini_node_name: str
    houdini_path:      str = ""
    ok:                bool = True
    error:             str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "feature_id":        self.feature_id,
            "feature_type":      self.feature_type,
            "houdini_node_name": self.houdini_node_name,
            "houdini_path":      self.houdini_path,
            "ok":                self.ok,
            "error":             self.error,
        }


@dataclass
class RealizationResult:
    realized:  int = 0
    skipped:   int = 0
    failed:    int = 0
    records:   List[RealizationRecord] = field(default_factory=list)
    ok:        bool = True
    errors:    List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "realized": self.realized,
            "skipped":  self.skipped,
            "failed":   self.failed,
            "records":  [r.to_dict() for r in self.records],
            "ok":       self.ok,
            "errors":   list(self.errors),
        }


class ArchitecturalFeatureRealizer:
    """
    Creates Houdini geometry nodes for every feature in an ArchitecturalPlan.

    Each feature maps to one /obj-level geo container whose interior contains
    a single box SOP sized and positioned to represent that feature.

    Usage (tests — use build_op_dicts for dry-run without bridge):
        ops = ArchitecturalFeatureRealizer().build_op_dicts(plan)

    Usage (production):
        result = get_architectural_feature_realizer().realize(plan)
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    # ─────────────────────────────────────────────────────────────────────────
    # Public
    # ─────────────────────────────────────────────────────────────────────────

    def realize(self, plan: ArchitecturalPlan) -> RealizationResult:
        """
        Create Houdini geometry nodes for all features in the plan.
        Calls get_bridge(). Never raises.
        """
        try:
            return self._realize(plan)
        except Exception as exc:
            return RealizationResult(
                ok=False,
                errors=[f"ArchitecturalFeatureRealizer.realize failed: {exc}"],
            )

    def build_op_dicts(self, plan: ArchitecturalPlan) -> List[Dict[str, Any]]:
        """
        Return operation dicts describing what would be created (no bridge).
        Useful for dry-run / tests.
        """
        ops: List[Dict[str, Any]] = []
        for op in self._iter_ops(plan):
            ops.append(op)
        return ops

    # ─────────────────────────────────────────────────────────────────────────
    # Internal
    # ─────────────────────────────────────────────────────────────────────────

    def _realize(self, plan: ArchitecturalPlan) -> RealizationResult:
        from src.utils.hou_bridge import get_bridge   # isolated import
        bridge = get_bridge()
        result = RealizationResult()

        for op in self._iter_ops(plan):
            fid  = op["feature_id"]
            ftype = op["feature_type"]
            node_name = op["houdini_node_name"]

            try:
                # Create geo container
                geo   = bridge.create_node("/obj", "geo", node_name)
                gpath = geo["path"]

                # Clear default nodes Houdini adds automatically
                for child in bridge.children(gpath):
                    bridge.delete_node(child["path"])

                # Create box SOP inside the geo container
                box   = bridge.create_node(gpath, "box", "box1")
                bpath = box["path"]
                bridge.set_parms(bpath, {
                    "sizex": op["sizex"],
                    "sizey": op["sizey"],
                    "sizez": op["sizez"],
                })
                bridge.set_display_flag(bpath, True)
                bridge.set_render_flag(bpath, True)

                # Position the geo container in world space
                bridge.set_parms(gpath, {
                    "tx": op["tx"],
                    "ty": op["ty"],
                    "tz": op["tz"],
                    "ry": op.get("ry", 0.0),
                })

                bridge.layout_children(gpath)

                result.realized += 1
                result.records.append(RealizationRecord(
                    feature_id=fid, feature_type=ftype,
                    houdini_node_name=node_name,
                    houdini_path=gpath, ok=True,
                ))

            except Exception as exc:
                result.failed += 1
                result.records.append(RealizationRecord(
                    feature_id=fid, feature_type=ftype,
                    houdini_node_name=node_name,
                    ok=False, error=str(exc),
                ))

        result.ok = result.failed == 0
        return result

    # ─────────────────────────────────────────────────────────────────────────

    def _iter_ops(self, plan: ArchitecturalPlan):
        """Yield operation dicts for all features in the plan."""

        # Door openings
        for o in plan.door_openings:
            yield _opening_op(o, "door_opening")

        # Window openings
        for o in plan.window_openings:
            yield _opening_op(o, "window_opening")

        # Beams
        for b in plan.beam_placements:
            sx = b.length if b.long_axis == "x" else b.width
            sz = b.length if b.long_axis == "z" else b.width
            yield {
                "feature_id":        b.feature_id,
                "feature_type":      "beam",
                "houdini_node_name": b.houdini_node_name,
                "tx": b.tx, "ty": b.ty, "tz": b.tz,
                "sizex": sx, "sizey": b.height, "sizez": sz,
                "ry": 0.0,
            }

        # Fireplaces
        for fp in plan.fireplace_placements:
            yield {
                "feature_id":        fp.feature_id,
                "feature_type":      "fireplace",
                "houdini_node_name": fp.houdini_node_name,
                "tx": fp.tx, "ty": fp.height / 2.0, "tz": fp.tz,
                "sizex": fp.width, "sizey": fp.height, "sizez": fp.depth,
                "ry": 0.0,
            }

        # Shelves
        for s in plan.shelf_placements:
            sx = s.width
            sy = s.thickness
            sz = s.depth
            yield {
                "feature_id":        s.feature_id,
                "feature_type":      "shelf",
                "houdini_node_name": s.houdini_node_name,
                "tx": s.tx, "ty": s.ty, "tz": s.tz,
                "sizex": sx, "sizey": sy, "sizez": sz,
                "ry": 0.0,
            }


# ── Op helpers ─────────────────────────────────────────────────────────────────

def _opening_op(o: ArchitecturalOpening, ftype: str) -> Dict[str, Any]:
    # For wall-normal-oriented depth: sizex/z depends on wall face
    if o.wall_face in ("north", "south"):
        sx, sz = o.width, o.depth
    else:   # east | west
        sx, sz = o.depth, o.width
    return {
        "feature_id":        o.opening_id,
        "feature_type":      ftype,
        "houdini_node_name": o.houdini_node_name,
        "tx": o.cx, "ty": o.cy, "tz": o.cz,
        "sizex": sx, "sizey": o.height, "sizez": sz,
        "ry": 0.0,
    }


# ── Singleton ──────────────────────────────────────────────────────────────────

_instance: Optional[ArchitecturalFeatureRealizer] = None
_lock = threading.Lock()


def get_architectural_feature_realizer() -> ArchitecturalFeatureRealizer:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = ArchitecturalFeatureRealizer()
    return _instance


def reset_architectural_feature_realizer_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
