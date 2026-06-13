"""
architectural_plan_builder.py — Tier 10.5 Structural Openings & Architectural Features
========================================================================================
Builds a complete ArchitecturalPlan from an EnvironmentShell (or shell dict).

Pipeline:
  1. Extract room geometry (width / length / height) from shell.
  2. For every door_anchor in shell.anchors → ArchitecturalOpening (door).
  3. For every window_anchor in shell.anchors → ArchitecturalOpening (window).
  4. For every fireplace_anchor → FireplacePlacement (with wall-snap metrics).
  5. For every beam_anchor → BeamPlacement (with ceiling-gap metrics).
  6. Generate WallShelfPlacements for shelf environments.

Design rules:
  - No bridge calls. Pure planning.
  - Deterministic — same shell always produces the same plan.
  - Never raises in public methods.
  - Singleton pattern + reset_for_tests.

Public API:
    ArchitecturalPlanBuilder
    get_architectural_plan_builder()
    reset_architectural_plan_builder_for_tests()
"""

from __future__ import annotations

import math
import threading
from typing import Any, Dict, List, Optional

from src.runtime.architectural_features.architectural_plan import (
    ArchitecturalOpening,
    FireplacePlacement,
    BeamPlacement,
    WallShelfPlacement,
    ArchitecturalPlan,
    WALL_THICKNESS,
    _WALL_NORMALS,
    _INTERIOR_VECTORS,
)

# ── Constants ─────────────────────────────────────────────────────────────────

# Extra clearance so the boolean cut goes fully through the wall
_OPENING_DEPTH_MARGIN: float = 0.20

# Fireplace wall-snap tolerance (accepted in review)
_FP_WALL_TOL: float = 0.05

# Beam cross-section dims by ceiling type
_BEAM_DIMS: Dict[str, tuple] = {
    "beam_ceiling":       (0.20, 0.30),   # (width_m, height_m)
    "industrial_ceiling": (0.35, 0.45),
    "vaulted_ceiling":    (0.25, 0.35),
    "arched_ceiling":     (0.20, 0.30),
    "sci_fi_ceiling":     (0.15, 0.20),
    "high_ceiling":       (0.20, 0.30),
}
_DEFAULT_BEAM_DIMS: tuple = (0.15, 0.25)

# Gap between beam top and ceiling (beam hangs slightly from ceiling)
_BEAM_CEILING_GAP: float = 0.02

# Environments that receive wall shelves and their shelf counts
_SHELF_ENVS: Dict[str, int] = {
    "library":      6,
    "western_room": 2,
    "saloon":       2,
    "workshop":     3,
    "living_room":  2,
    "robotics_lab": 2,
    "research_lab": 3,
    "control_room": 2,
    "office":       2,
}

# Default shelf geometry
_SHELF_WIDTH:     float = 1.00
_SHELF_DEPTH:     float = 0.30
_SHELF_THICKNESS: float = 0.05
_SHELF_HEIGHTS:   List[float] = [1.20, 1.60, 2.00, 2.40, 1.00, 1.80]  # cycling heights


class ArchitecturalPlanBuilder:
    """
    Produces an ArchitecturalPlan from an EnvironmentShell.

    Call:
        plan = get_architectural_plan_builder().build(shell_dict)
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def build(self, shell: Any) -> ArchitecturalPlan:
        """
        Build a complete ArchitecturalPlan. Never raises.

        Args:
            shell: EnvironmentShell instance or dict from to_dict().
        """
        try:
            shell_dict = _shell_to_dict(shell)
            return self._build(shell_dict)
        except Exception as exc:
            plan = ArchitecturalPlan(environment="unknown", ok=False)
            plan.errors.append(f"ArchitecturalPlanBuilder.build failed: {exc}")
            return plan

    # ─────────────────────────────────────────────────────────────────────────

    def _build(self, s: Dict[str, Any]) -> ArchitecturalPlan:
        env    = s.get("environment", "")
        w      = float(s.get("room_width",  0.0) or
                       _from_structural_elements(s, "width",  10.0))
        d      = float(s.get("room_length", 0.0) or
                       _from_structural_elements(s, "depth",  12.0))
        h      = float(s.get("ceiling_height", 0.0) or
                       _from_structural_elements(s, "height",  4.0))
        outdoor = bool(s.get("is_outdoor", False))

        # Normalise: ensure we have reasonable defaults
        if w <= 0: w = 10.0
        if d <= 0: d = 12.0
        if h <= 0: h = 4.0

        half_w, half_d = w / 2.0, d / 2.0

        anchors: List[Dict[str, Any]] = list(s.get("anchors", []))

        # Ceiling type for beam sizing
        ceiling_type = s.get("ceiling_type", "flat_ceiling")

        plan = ArchitecturalPlan(
            environment=env,
            room_width=w, room_length=d, room_height=h,
            is_outdoor=outdoor,
        )

        if outdoor:
            # Outdoor environments have no structural openings or beams
            return plan

        # ── 1. Door openings ────────────────────────────────────────────────
        door_anchors = [a for a in anchors if a.get("anchor_type") == "door_anchor"]
        for idx, anchor in enumerate(door_anchors):
            plan.door_openings.append(
                self._make_opening(anchor, "door", idx, half_w, half_d, h)
            )

        # ── 2. Window openings ──────────────────────────────────────────────
        win_anchors = [a for a in anchors if a.get("anchor_type") == "window_anchor"]
        for idx, anchor in enumerate(win_anchors):
            plan.window_openings.append(
                self._make_opening(anchor, "window", idx, half_w, half_d, h)
            )

        # ── 3. Fireplace placements ─────────────────────────────────────────
        fp_anchors = [a for a in anchors if a.get("anchor_type") == "fireplace_anchor"]
        for idx, anchor in enumerate(fp_anchors):
            plan.fireplace_placements.append(
                self._make_fireplace(anchor, idx, half_w, half_d, h)
            )

        # ── 4. Beam placements ───────────────────────────────────────────────
        beam_anchors = [a for a in anchors if a.get("anchor_type") == "beam_anchor"]
        bw, bh = _BEAM_DIMS.get(ceiling_type, _DEFAULT_BEAM_DIMS)
        for idx, anchor in enumerate(beam_anchors):
            plan.beam_placements.append(
                self._make_beam(anchor, idx, bw, bh, h, half_w, half_d, d)
            )

        # ── 5. Wall shelves ──────────────────────────────────────────────────
        shelf_count = _SHELF_ENVS.get(env, 0)
        if shelf_count > 0:
            plan.shelf_placements = self._make_shelves(
                env, shelf_count, half_w, half_d, h
            )

        return plan

    # ─────────────────────────────────────────────────────────────────────────

    def _make_opening(
        self,
        anchor:      Dict[str, Any],
        otype:       str,   # "door" | "window"
        idx:         int,
        half_w:      float,
        half_d:      float,
        room_height: float,
    ) -> ArchitecturalOpening:
        """Convert an anchor dict to an ArchitecturalOpening."""
        wall_face = anchor.get("wall_face", "south")
        normal    = _WALL_NORMALS.get(wall_face, [0.0, 0.0, 1.0])
        ow        = float(anchor.get("door_width", anchor.get("window_width", 0.9)))
        oh        = float(anchor.get("door_height", anchor.get("window_height", 1.2)))

        # The anchor's (tx, ty, tz) is the world-space centre of the opening
        cx = float(anchor.get("tx", 0.0))
        # For doors: ty in the anchor is h*0.45 (centre at ~h/2).
        # We want cy = oh/2 (opening bottom at floor) for doors,
        # ty as-is for windows.
        if otype == "door":
            cy = oh / 2.0
        else:
            cy = float(anchor.get("ty", room_height * 0.55))
        cz = float(anchor.get("tz", 0.0))

        return ArchitecturalOpening(
            opening_id        = f"{otype}_opening_{idx}",
            opening_type      = otype,
            anchor_id         = anchor.get("anchor_id", f"{otype}_anchor_{idx}"),
            wall_face         = wall_face,
            wall_normal       = normal,
            cx=cx, cy=cy, cz=cz,
            width             = ow,
            height            = oh,
            depth             = WALL_THICKNESS + _OPENING_DEPTH_MARGIN,
            houdini_node_name = f"sh_{otype}_opening_{idx}",
        )

    def _make_fireplace(
        self,
        anchor:  Dict[str, Any],
        idx:     int,
        half_w:  float,
        half_d:  float,
        h:       float,
    ) -> FireplacePlacement:
        """Convert a fireplace_anchor to a FireplacePlacement."""
        wall_face   = anchor.get("wall_face", "north")
        normal      = _WALL_NORMALS.get(wall_face, [0.0, 0.0, -1.0])
        interior    = _INTERIOR_VECTORS.get(wall_face, [0.0, 0.0, 1.0])
        fp_w        = float(anchor.get("fireplace_width",  1.2))
        fp_h        = float(anchor.get("fireplace_height", 1.5))
        fp_d        = 0.60   # standard fireplace depth

        tx = float(anchor.get("tx", 0.0))
        ty = float(anchor.get("ty", 0.0))
        tz = float(anchor.get("tz", 0.0))

        # Wall coordinate and back-face metrics
        if wall_face == "north":
            wall_coord     = -half_d
            back_face_coord = tz - fp_d / 2.0
        elif wall_face == "south":
            wall_coord     = half_d
            back_face_coord = tz + fp_d / 2.0
        elif wall_face == "east":
            wall_coord     = half_w
            back_face_coord = tx + fp_d / 2.0
        else:  # west
            wall_coord     = -half_w
            back_face_coord = tx - fp_d / 2.0

        back_face_distance = abs(back_face_coord - wall_coord)

        # Center offset: how far lateral from the wall's centrepoint
        if wall_face in ("north", "south"):
            center_offset = abs(tx)   # deviation from x=0
        else:
            center_offset = abs(tz)   # deviation from z=0

        return FireplacePlacement(
            feature_id         = f"fireplace_{idx}",
            anchor_id          = anchor.get("anchor_id", f"fireplace_anchor_{idx}"),
            wall_face          = wall_face,
            wall_normal        = normal,
            forward_axis       = interior,
            tx=tx, ty=ty, tz=tz,
            width=fp_w, height=fp_h, depth=fp_d,
            wall_coord         = wall_coord,
            back_face_coord    = back_face_coord,
            back_face_distance = back_face_distance,
            center_offset      = center_offset,
            houdini_node_name  = f"sh_fireplace_{idx}",
        )

    def _make_beam(
        self,
        anchor:  Dict[str, Any],
        idx:     int,
        bw:      float,
        bh:      float,
        h:       float,
        half_w:  float,
        half_d:  float,
        room_d:  float,
    ) -> BeamPlacement:
        """Convert a beam_anchor to a BeamPlacement."""
        tx         = float(anchor.get("tx", 0.0))
        tz         = float(anchor.get("tz", 0.0))
        beam_span  = float(anchor.get("beam_span", room_d))

        # Beam hangs from ceiling: top face touches ceiling, beam extends down
        ty         = h - bh / 2.0 - _BEAM_CEILING_GAP
        beam_top_y = ty + bh / 2.0
        gap        = abs(h - beam_top_y)

        # Long axis: beams in anchor generator span the room depth (Z axis)
        long_axis = "z"

        # Wall intersection check: beam extends from -room_d/2 to +room_d/2
        # Check if the beam's width (in X) extends past the walls
        beam_half_width = bw / 2.0
        intersects_wall = abs(tx) + beam_half_width > half_w

        is_below_ceiling = ty + bh / 2.0 <= h

        return BeamPlacement(
            feature_id       = f"beam_{idx}",
            anchor_id        = anchor.get("anchor_id", f"beam_anchor_{idx}"),
            tx=round(tx, 4), ty=round(ty, 4), tz=round(tz, 4),
            long_axis        = long_axis,
            length           = round(beam_span, 4),
            width            = round(bw, 4),
            height           = round(bh, 4),
            ceiling_height   = round(h, 4),
            beam_top_y       = round(beam_top_y, 4),
            gap_to_ceiling   = round(gap, 4),
            intersects_wall  = intersects_wall,
            is_below_ceiling = is_below_ceiling,
            houdini_node_name = f"sh_beam_{idx}",
        )

    def _make_shelves(
        self,
        env:     str,
        count:   int,
        half_w:  float,
        half_d:  float,
        h:       float,
    ) -> List[WallShelfPlacement]:
        """Generate wall-mounted shelves for environments that have them."""
        shelves: List[WallShelfPlacement] = []

        # Distribute shelves across north and east walls
        walls = [
            ("west",  -half_w,  True),    # (face, coord, is_x_wall)
            ("east",   half_w,  True),
            ("north", -half_d, False),
            ("south",  half_d, False),
        ]

        shelf_depth = _SHELF_DEPTH

        for idx in range(count):
            wall_face, wall_coord, is_x_wall = walls[idx % len(walls)]
            height_idx = idx % len(_SHELF_HEIGHTS)
            mount_height = _SHELF_HEIGHTS[height_idx]

            # Inset shelf front face from wall by depth/2
            inset = shelf_depth / 2.0 + 0.02   # slight clearance
            if is_x_wall:
                tx = wall_coord - math.copysign(inset, wall_coord)
                tz = (float(idx // len(walls)) - 0.5) * 1.5
            else:
                tx = (float(idx // len(walls)) - 0.5) * 1.5
                tz = wall_coord - math.copysign(inset, wall_coord)

            # Shelf is never floating when we compute it from wall geometry
            is_floating = False

            shelves.append(WallShelfPlacement(
                feature_id        = f"shelf_{idx}",
                anchor_id         = f"wall_shelf_anchor_{idx}_{env}",
                wall_face         = wall_face,
                tx=round(tx, 4), ty=round(mount_height, 4), tz=round(tz, 4),
                width             = _SHELF_WIDTH,
                depth             = shelf_depth,
                thickness         = _SHELF_THICKNESS,
                wall_coord        = wall_coord,
                is_floating       = is_floating,
                houdini_node_name = f"sh_shelf_{idx}",
            ))

        return shelves


# ── Helpers ────────────────────────────────────────────────────────────────────

def _shell_to_dict(shell: Any) -> Dict[str, Any]:
    if shell is None:
        return {}
    if isinstance(shell, dict):
        return shell
    if hasattr(shell, "to_dict"):
        return shell.to_dict()
    return {}


def _from_structural_elements(
    s: Dict[str, Any],
    key: str,
    default: float,
) -> float:
    """Attempt to read a dimension from structural_elements list."""
    for el in s.get("structural_elements", []):
        v = el.get(key) or el.get(f"{key}_m") or el.get(f"room_{key}")
        if v:
            try:
                return float(v)
            except (TypeError, ValueError):
                pass
    return default


# ── Singleton ──────────────────────────────────────────────────────────────────

_instance: Optional[ArchitecturalPlanBuilder] = None
_lock = threading.Lock()


def get_architectural_plan_builder() -> ArchitecturalPlanBuilder:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = ArchitecturalPlanBuilder()
    return _instance


def reset_architectural_plan_builder_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
