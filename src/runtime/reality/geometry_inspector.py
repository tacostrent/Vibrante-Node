"""
geometry_inspector.py — §54 Reality Intelligence (Tier 15.0+)
==============================================================
Reality First Rule: the viewport is the source of truth. Not metadata, not
planner output, not audit scores, not relationship graphs.

This is one of only two modules in the reality package that touches the
Houdini bridge (the other is correction_applier.py). It reads the ACTUAL
geometry of realized nodes — world transform and cooked bounding box — and
builds an observed scene snapshot.

reconcile(): when observed geometry contradicts metadata, GEOMETRY WINS —
the observed transform and bbox replace the planned values.

Public API:
    ObservedAsset
    ObservedScene
    GeometryInspector
    get_geometry_inspector()
    reset_geometry_inspector_for_tests()
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.runtime.reality.reality_scene_model import infer_asset_type


@dataclass
class ObservedAsset:
    node_path:  str
    asset_name: str
    tx: float = 0.0
    ty: float = 0.0
    tz: float = 0.0
    ry: float = 0.0
    half_x: float = 0.0
    half_y: float = 0.0
    half_z: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_path":  self.node_path,
            "asset_name": self.asset_name,
            "asset_type": infer_asset_type(self.asset_name),
            "tx": round(self.tx, 4), "ty": round(self.ty, 4), "tz": round(self.tz, 4),
            "ry": round(self.ry, 4),
            "bbox_half_x": round(self.half_x, 4),
            "bbox_half_y": round(self.half_y, 4),
            "bbox_half_z": round(self.half_z, 4),
            "source": "viewport",
        }


@dataclass
class ObservedScene:
    root_path: str = ""
    assets: List[ObservedAsset] = field(default_factory=list)
    ok: bool = True
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "root_path": self.root_path,
            "assets":    [a.to_dict() for a in self.assets],
            "ok":        self.ok,
            "errors":    list(self.errors),
        }


# Runs inside Houdini. Walks children of the root, reads world transform and
# the cooked geometry bounding box of each child's display SOP.
_INSPECT_CODE_TEMPLATE = """
import json
_root = hou.node({root!r})
_out = []
if _root:
    for _c in _root.children():
        try:
            _t = _c.worldTransform()
            _pos = hou.Vector3(0, 0, 0) * _t
            _rot = _t.extractRotates()
            _entry = {{
                "path": _c.path(),
                "name": _c.name(),
                "tx": float(_pos[0]), "ty": float(_pos[1]), "tz": float(_pos[2]),
                "ry": float(_rot[1]),
                "hx": 0.0, "hy": 0.0, "hz": 0.0,
            }}
            try:
                _d = _c.displayNode() if hasattr(_c, "displayNode") else None
                _g = _d.geometry() if _d is not None else None
                if _g is not None:
                    _bb = _g.boundingBox()
                    _entry["hx"] = float(_bb.sizevec()[0]) / 2.0
                    _entry["hy"] = float(_bb.sizevec()[1]) / 2.0
                    _entry["hz"] = float(_bb.sizevec()[2]) / 2.0
                    _ctr = _bb.center() * _t
                    _entry["tx"] = float(_ctr[0])
                    _entry["ty"] = float(_ctr[1])
                    _entry["tz"] = float(_ctr[2])
            except Exception:
                pass
            _out.append(_entry)
        except Exception:
            pass
result = json.dumps(_out)
"""


class GeometryInspector:
    """Reads actual realized geometry from Houdini. Never raises."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def inspect(self, root_path: str = "/obj") -> ObservedScene:
        """
        Inspect every child node of root_path in the live Houdini session and
        return their observed world transforms and cooked bounding boxes.
        """
        scene = ObservedScene(root_path=root_path)
        try:
            from src.utils.hou_bridge import get_bridge   # isolated import
            bridge = get_bridge()
            run_result = bridge.run_code(
                _INSPECT_CODE_TEMPLATE.format(root=root_path)
            )
            raw = run_result.get("result")
            if not raw:
                scene.ok = False
                scene.errors.append(f"no geometry observed under {root_path}")
                return scene
            import json
            for entry in json.loads(raw):
                scene.assets.append(ObservedAsset(
                    node_path=str(entry.get("path", "")),
                    asset_name=str(entry.get("name", "")),
                    tx=float(entry.get("tx", 0.0)),
                    ty=float(entry.get("ty", 0.0)),
                    tz=float(entry.get("tz", 0.0)),
                    ry=float(entry.get("ry", 0.0)),
                    half_x=float(entry.get("hx", 0.0)),
                    half_y=float(entry.get("hy", 0.0)),
                    half_z=float(entry.get("hz", 0.0)),
                ))
            return scene
        except Exception as exc:
            scene.ok = False
            scene.errors.append(f"GeometryInspector.inspect failed: {exc}")
            return scene

    def reconcile(self, observed: Dict[str, Any],
                  planned_scene: Dict[str, Any]) -> Dict[str, Any]:
        """
        GEOMETRY WINS. Merge an ObservedScene.to_dict() into a planned scene
        layout dict: any planned transform whose asset matches an observed
        node (by name, case-insensitive) gets its position, rotation and bbox
        replaced by the observed values and is tagged source="viewport".

        Pure computation — no bridge call. Never raises.
        """
        try:
            merged = dict(planned_scene or {})
            transforms = [dict(t) for t in (merged.get("transforms") or [])
                          if isinstance(t, dict)]
            observed_assets = (observed or {}).get("assets") or []
            by_name: Dict[str, Dict[str, Any]] = {}
            for oa in observed_assets:
                if isinstance(oa, dict):
                    by_name[str(oa.get("asset_name", "")).lower()] = oa

            overridden = 0
            for t in transforms:
                key = str(t.get("asset_name") or t.get("asset_id") or "").lower()
                oa = by_name.get(key)
                if oa is None:
                    # also try the sanitized node-name form (spaces → underscores)
                    oa = by_name.get(key.replace(" ", "_"))
                if oa is None:
                    continue
                for src_key, dst_key in (
                    ("tx", "tx"), ("ty", "ty"), ("tz", "tz"), ("ry", "ry"),
                    ("bbox_half_x", "bbox_half_x"),
                    ("bbox_half_y", "bbox_half_y"),
                    ("bbox_half_z", "bbox_half_z"),
                ):
                    value = oa.get(src_key)
                    if value is not None and (src_key.startswith("bbox") is False
                                              or float(value) > 0.0):
                        t[dst_key] = float(value)
                t["source"] = "viewport"
                overridden += 1

            merged["transforms"] = transforms
            merged["viewport_reconciled"] = True
            merged["viewport_overrides"] = overridden
            return merged
        except Exception as exc:
            fallback = dict(planned_scene or {})
            fallback["viewport_reconciled"] = False
            fallback["reconcile_error"] = str(exc)
            return fallback


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[GeometryInspector] = None
_lock = threading.Lock()


def get_geometry_inspector() -> GeometryInspector:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = GeometryInspector()
    return _instance


def reset_geometry_inspector_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
