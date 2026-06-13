"""
beam_connection_validator.py — §54 Reality Intelligence (Tier 15.0+)
=====================================================================
Beam Rule. Beams must connect architecture — never float in the room
center. Valid spans:

    wall-to-wall
    wall-to-column
    column-to-column

Both beam endpoints must intersect structural elements (a wall plane or a
column footprint).

Public API:
    BeamConnection
    BeamConnectionResult
    BeamConnectionValidator
    get_beam_connection_validator()
    reset_beam_connection_validator_for_tests()
"""

from __future__ import annotations

import math
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.runtime.reality.reality_scene_model import (
    SceneAsset,
    SceneSnapshot,
    parse_scene,
)

ENDPOINT_TOLERANCE = 0.50   # metres — endpoint must be this close to structure


@dataclass
class BeamConnection:
    asset_id:    str
    asset_name:  str
    endpoint_a:  List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    endpoint_b:  List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    connected_a: str = ""    # "wall" | "column:<id>" | ""
    connected_b: str = ""
    span_kind:   str = ""    # "wall-to-wall" | "wall-to-column" | "column-to-column" | "floating"
    ok:          bool = False
    detail:      str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id":    self.asset_id,
            "asset_name":  self.asset_name,
            "endpoint_a":  [round(v, 4) for v in self.endpoint_a],
            "endpoint_b":  [round(v, 4) for v in self.endpoint_b],
            "connected_a": self.connected_a,
            "connected_b": self.connected_b,
            "span_kind":   self.span_kind,
            "ok":          self.ok,
            "detail":      self.detail,
        }


@dataclass
class BeamConnectionResult:
    connections: List[BeamConnection] = field(default_factory=list)
    violations:  List[BeamConnection] = field(default_factory=list)
    beam_count:  int = 0
    ok:          bool = True
    findings:    List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "connections": [c.to_dict() for c in self.connections],
            "violations":  [v.to_dict() for v in self.violations],
            "beam_count":  self.beam_count,
            "ok":          self.ok,
            "findings":    list(self.findings),
        }


class BeamConnectionValidator:
    """Validates that every beam spans between structural elements. Never raises."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def validate(self, scene_layout: Dict[str, Any]) -> BeamConnectionResult:
        try:
            return self._validate(parse_scene(scene_layout))
        except Exception as exc:
            r = BeamConnectionResult(ok=False)
            r.findings.append(f"BeamConnectionValidator internal error: {exc}")
            return r

    def validate_snapshot(self, snap: SceneSnapshot) -> BeamConnectionResult:
        try:
            return self._validate(snap)
        except Exception as exc:
            r = BeamConnectionResult(ok=False)
            r.findings.append(f"BeamConnectionValidator internal error: {exc}")
            return r

    # ------------------------------------------------------------------

    def _validate(self, snap: SceneSnapshot) -> BeamConnectionResult:
        result = BeamConnectionResult()
        columns = snap.assets_of_type("column")

        for beam in snap.assets_of_type("beam"):
            result.beam_count += 1
            conn = self._check_beam(snap, beam, columns)
            result.connections.append(conn)
            if not conn.ok:
                result.violations.append(conn)
                result.findings.append(f"FLOATING_BEAM: {conn.detail}")

        result.ok = len(result.violations) == 0
        return result

    def _check_beam(self, snap: SceneSnapshot, beam: SceneAsset,
                    columns: List[SceneAsset]) -> BeamConnection:
        ep_a, ep_b = self._endpoints(beam)
        conn = BeamConnection(
            asset_id=beam.asset_id,
            asset_name=beam.asset_name,
            endpoint_a=list(ep_a),
            endpoint_b=list(ep_b),
        )
        conn.connected_a = self._endpoint_target(snap, ep_a, columns)
        conn.connected_b = self._endpoint_target(snap, ep_b, columns)

        if conn.connected_a and conn.connected_b:
            kinds = sorted(
                "wall" if c == "wall" else "column"
                for c in (conn.connected_a, conn.connected_b)
            )
            conn.span_kind = f"{kinds[0]}-to-{kinds[1]}"
            conn.ok = True
        else:
            conn.span_kind = "floating"
            missing = []
            if not conn.connected_a:
                missing.append(f"endpoint A {tuple(round(v, 2) for v in ep_a)}")
            if not conn.connected_b:
                missing.append(f"endpoint B {tuple(round(v, 2) for v in ep_b)}")
            conn.detail = (
                f"{beam.asset_name or beam.asset_id} does not connect architecture — "
                f"{' and '.join(missing)} intersect(s) no wall or column. Valid spans: "
                "wall-to-wall, wall-to-column, column-to-column."
            )
        return conn

    def _endpoints(self, beam: SceneAsset) -> Tuple[Tuple[float, float, float],
                                                    Tuple[float, float, float]]:
        """Endpoints along the beam's major horizontal axis, ry-rotated."""
        r = math.radians(beam.ry)
        if beam.half_x >= beam.half_z:
            half_len = beam.half_x
            dx, dz = math.cos(r), -math.sin(r)
        else:
            half_len = beam.half_z
            dx, dz = math.sin(r), math.cos(r)
        return (
            (beam.tx - dx * half_len, beam.ty, beam.tz - dz * half_len),
            (beam.tx + dx * half_len, beam.ty, beam.tz + dz * half_len),
        )

    def _endpoint_target(self, snap: SceneSnapshot,
                         endpoint: Tuple[float, float, float],
                         columns: List[SceneAsset]) -> str:
        x, _, z = endpoint
        # Wall planes (room perimeter)
        if (abs(abs(x) - snap.wall_x) <= ENDPOINT_TOLERANCE
                or abs(abs(z) - snap.wall_z) <= ENDPOINT_TOLERANCE):
            return "wall"
        # Column footprints
        for col in columns:
            if (abs(x - col.tx) <= col.half_x + ENDPOINT_TOLERANCE
                    and abs(z - col.tz) <= col.half_z + ENDPOINT_TOLERANCE):
                return f"column:{col.asset_id}"
        return ""


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[BeamConnectionValidator] = None
_lock = threading.Lock()


def get_beam_connection_validator() -> BeamConnectionValidator:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = BeamConnectionValidator()
    return _instance


def reset_beam_connection_validator_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
