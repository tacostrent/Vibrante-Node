"""
Ground Contact Detector (Tier 9.7 — Geometry Intelligence)
===========================================================
Determines which points on an asset make contact with the floor and how.
Contact information drives floor-plane snapping and structural validation.

Contact types:
  leg          — discrete point contacts (chair, table)
  base_ring    — circular base perimeter (bucket, barrel, cylinder)
  base_plane   — full flat base plane (machine, crate, pallet)
  wheel        — rolling contact points (vehicle, cart)
  foot         — padded feet (electronic equipment)
  skid         — sliding rails (heavy equipment)
  track        — continuous surface contact (tracked vehicle)
  spike        — narrow point contacts (tripod)

DESIGN RULES:
  1. No bridge calls. No Houdini imports.
  2. Deterministic — same asset dict → same contacts.
  3. Never raises.
  4. Singleton pattern.

Public API:
    GroundContactDetector
    get_ground_contact_detector()
    reset_ground_contact_detector_for_tests()
"""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional

from src.runtime.assets.geometry.asset_metrics import GroundContact


def _leg_positions(w: float, d: float, inset: float = 0.05) -> List[List[float]]:
    """Four-leg positions at corners, inset slightly from edge."""
    hx = max(w / 2.0 - inset, 0.0)
    hz = max(d / 2.0 - inset, 0.0)
    return [[-hx, 0.0, -hz], [hx, 0.0, -hz], [-hx, 0.0, hz], [hx, 0.0, hz]]


def _three_leg_positions(radius: float) -> List[List[float]]:
    import math
    r = radius * 0.7
    return [
        [0.0, 0.0, r],
        [-r * math.sin(2 * math.pi / 3), 0.0, r * math.cos(2 * math.pi / 3)],
        [r * math.sin(2 * math.pi / 3), 0.0, r * math.cos(2 * math.pi / 3)],
    ]


def _base_ring_positions(w: float, d: float, n: int = 8) -> List[List[float]]:
    import math
    rx = w / 2.0 * 0.9
    rz = d / 2.0 * 0.9
    positions = []
    for i in range(n):
        angle = 2 * math.pi * i / n
        positions.append([rx * math.cos(angle), 0.0, rz * math.sin(angle)])
    return positions


def _wheel_positions(w: float, d: float, axle_count: int = 2) -> List[List[float]]:
    """Wheel contact positions along axles."""
    hw = w / 2.0 * 0.85
    step = d / max(axle_count, 1)
    positions = []
    for i in range(axle_count):
        z = -d / 2.0 + step * (i + 0.5)
        positions.append([-hw, 0.0, z])
        positions.append([hw, 0.0, z])
    return positions


# Mapping: placement_type → GroundContact builder
# Each value is (contact_type, count_fn, positions_fn, description)
_TYPE_CONTACT_RULES: Dict[str, Dict[str, Any]] = {
    "chair":       {"type": "leg",        "count": 4,  "desc": "Four chair legs"},
    "stool":       {"type": "leg",        "count": 4,  "desc": "Four stool legs"},
    "table":       {"type": "leg",        "count": 4,  "desc": "Four table legs"},
    "desk":        {"type": "leg",        "count": 4,  "desc": "Four desk legs"},
    "workbench":   {"type": "leg",        "count": 4,  "desc": "Four workbench legs"},
    "bench":       {"type": "leg",        "count": 4,  "desc": "Four bench legs"},
    "sofa":        {"type": "leg",        "count": 4,  "desc": "Four sofa legs"},
    "bed":         {"type": "leg",        "count": 4,  "desc": "Four bed legs"},
    "cabinet":     {"type": "base_plane", "count": 1,  "desc": "Full cabinet base"},
    "wardrobe":    {"type": "base_plane", "count": 1,  "desc": "Full wardrobe base"},
    "shelf":       {"type": "base_plane", "count": 1,  "desc": "Full shelf unit base"},
    "server_rack": {"type": "foot",       "count": 4,  "desc": "Four rack feet"},
    "rack":        {"type": "foot",       "count": 4,  "desc": "Four rack feet"},
    "barrel":      {"type": "base_ring",  "count": 8,  "desc": "Circular barrel base"},
    "bucket":      {"type": "base_ring",  "count": 8,  "desc": "Circular bucket base"},
    "crate":       {"type": "base_plane", "count": 1,  "desc": "Full crate base"},
    "pallet":      {"type": "skid",       "count": 2,  "desc": "Two pallet skids"},
    "machine":     {"type": "base_plane", "count": 1,  "desc": "Full machine base plate"},
    "large_machine":      {"type": "base_plane", "count": 1,  "desc": "Full machine base plate"},
    "industrial_machine": {"type": "base_plane", "count": 1,  "desc": "Full machine base plate"},
    "reactor":     {"type": "base_plane", "count": 1,  "desc": "Reactor base ring"},
    "engine":      {"type": "base_plane", "count": 1,  "desc": "Engine mount base"},
    "console":     {"type": "base_plane", "count": 1,  "desc": "Console base"},
    "counter":     {"type": "base_plane", "count": 1,  "desc": "Counter base"},
    "bar_counter": {"type": "base_plane", "count": 1,  "desc": "Bar counter base"},
    "display_case":{"type": "foot",       "count": 4,  "desc": "Display case feet"},
    "vehicle":     {"type": "wheel",      "count": 4,  "desc": "Four wheels (2 axles)"},
    "vehicle_small": {"type": "wheel",    "count": 4,  "desc": "Four wheels"},
    "crane":       {"type": "track",      "count": 2,  "desc": "Two crane tracks"},
    "lantern":     {"type": "base_plane", "count": 1,  "desc": "Lantern flat base"},
    "terrain":     {"type": "base_plane", "count": 1,  "desc": "Terrain base plane"},
    "wall":        {"type": "base_plane", "count": 1,  "desc": "Wall base"},
    "column":      {"type": "base_ring",  "count": 8,  "desc": "Column base ring"},
    "beam":        {"type": "base_plane", "count": 1,  "desc": "Beam resting surface"},
    "platform":    {"type": "base_plane", "count": 1,  "desc": "Platform base"},
    "tree":        {"type": "base_plane", "count": 1,  "desc": "Tree root base"},
    "plant":       {"type": "base_plane", "count": 1,  "desc": "Pot base"},
}

# Hanging placement types — no ground contact
_NO_GROUND_CONTACT = frozenset({
    "hanging_light", "pendant_light", "ceiling_mount",
    "sprinkler", "hanging_prop", "light_volume",
    "trigger_volume", "particle_emitter", "floating_prop",
})


class GroundContactDetector:
    """Determines ground contact points for an asset."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def detect(
        self,
        asset: Dict[str, Any],
        width_m: float,
        height_m: float,
        depth_m: float,
    ) -> List[GroundContact]:
        """
        Detect ground contact points.

        Args:
            asset:    asset metadata dict
            width_m, height_m, depth_m: asset dimensions in meters

        Returns:
            List of GroundContact. Empty list for hanging/floating assets.
            Never raises.
        """
        try:
            return self._detect(asset, width_m, height_m, depth_m)
        except Exception:
            return [GroundContact(
                contact_type="base_plane",
                count=1,
                positions=[[0.0, 0.0, 0.0]],
                description="Fallback contact",
            )]

    def _detect(
        self,
        asset: Dict[str, Any],
        w: float,
        h: float,
        d: float,
    ) -> List[GroundContact]:
        pt = str(asset.get("placement_type") or "").lower().strip()
        cat = str(asset.get("category") or "").lower().strip()

        # --- Priority 1: no contact (hanging/floating) ---
        if pt in _NO_GROUND_CONTACT:
            return []

        # --- Priority 2: explicit ground_contacts field ---
        explicit = asset.get("ground_contacts")
        if isinstance(explicit, list) and explicit:
            contacts = []
            for item in explicit:
                if isinstance(item, dict):
                    contacts.append(GroundContact(
                        contact_type = str(item.get("contact_type", "base_plane")),
                        count        = int(item.get("count", 1)),
                        positions    = [list(p) for p in item.get("positions", [[0, 0, 0]])],
                        description  = str(item.get("description", "")),
                    ))
            if contacts:
                return contacts

        # --- Priority 3: placement-type rule ---
        rule = _TYPE_CONTACT_RULES.get(pt)
        if rule:
            return [self._build_contact(rule, w, h, d)]

        # --- Priority 4: category fallback ---
        if cat in ("furniture", "seating"):
            return [GroundContact(
                contact_type="leg", count=4,
                positions=_leg_positions(w, d),
                description="Four furniture legs",
            )]
        if cat in ("vehicle",):
            return [GroundContact(
                contact_type="wheel", count=4,
                positions=_wheel_positions(w, d),
                description="Vehicle wheel contacts",
            )]
        if cat in ("structure", "architectural", "terrain"):
            return [GroundContact(
                contact_type="base_plane", count=1,
                positions=[[0.0, 0.0, 0.0]],
                description="Structural base plane",
            )]

        # --- Generic fallback ---
        return [GroundContact(
            contact_type="base_plane", count=1,
            positions=[[0.0, 0.0, 0.0]],
            description="Generic base contact",
        )]

    @staticmethod
    def _build_contact(rule: Dict[str, Any], w: float, h: float, d: float) -> GroundContact:
        ctype = rule["type"]
        count = rule["count"]
        desc  = rule["desc"]

        if ctype == "leg":
            positions = _leg_positions(w, d)
        elif ctype == "base_ring":
            positions = _base_ring_positions(w, d, n=count)
        elif ctype == "base_plane":
            positions = [[0.0, 0.0, 0.0]]
        elif ctype == "wheel":
            axles = max(count // 2, 1)
            positions = _wheel_positions(w, d, axle_count=axles)
        elif ctype == "foot":
            positions = _leg_positions(w, d, inset=0.08)
        elif ctype == "skid":
            hx = w / 2.0 * 0.7
            positions = [[-hx, 0.0, 0.0], [hx, 0.0, 0.0]]
        elif ctype == "track":
            hx = w / 2.0 * 0.75
            positions = [[-hx, 0.0, 0.0], [hx, 0.0, 0.0]]
        elif ctype == "spike":
            positions = _three_leg_positions(min(w, d) / 2.0)
        else:
            positions = [[0.0, 0.0, 0.0]]

        return GroundContact(
            contact_type=ctype,
            count=len(positions),
            positions=positions,
            description=desc,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[GroundContactDetector] = None
_LOCK = threading.Lock()


def get_ground_contact_detector() -> GroundContactDetector:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = GroundContactDetector()
        return _INSTANCE


def reset_ground_contact_detector_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
