"""
reality_scene_model.py — §54 Reality Intelligence (Tier 15.0+)
===============================================================
Shared scene model and geometry helpers used by every Reality Intelligence
rule. Parses a ResolvedSceneLayout-style dict into a SceneSnapshot with
normalized transforms, room bounds, and one canonical asset-type inference
table so every rule agrees on what a "bottle" or "beam" is.

Core principle (§54): the viewport is the source of truth. Snapshots built
from observed geometry carry source="viewport" and always win over
metadata-derived values.

Pure functions + dataclasses — no singletons, no bridge calls, no randomness.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

FLOAT_TOLERANCE = 0.10   # §54 No Floating Objects Rule: ty > floor + 0.10 needs support
WALL_PROXIMITY  = 0.40   # metres — "against a wall" / wall-mounted threshold

# Ordered (type, keywords) — first match wins. Multi-word keywords first.
_ASSET_TYPE_KEYWORDS: List[Tuple[str, List[str]]] = [
    ("bar",        ["bar_counter", "bar counter", "bar top"]),
    ("wall",       ["wall_segment", "wall segment", "wall moulding", "wall"]),
    ("door",       ["doorway", "door frame", "door"]),
    ("window",     ["window frame", "window"]),
    ("fireplace",  ["fireplace", "hearth", "chimney"]),
    ("beam",       ["beam", "girder", "rafter", "truss"]),
    ("column",     ["column", "pillar"]),
    ("floor",      ["floor"]),
    ("ceiling",    ["ceiling", "roof"]),
    ("stool",      ["stool"]),
    ("chair",      ["chair", "armchair", "bench seat"]),
    ("bench",      ["bench"]),
    ("table",      ["side table", "table"]),
    ("desk",       ["workbench", "desk"]),
    ("shelf",      ["bookshelf", "shelf", "shelves"]),
    ("bed",        ["bed"]),
    ("bottle",     ["whiskey bottle", "beer bottle", "bottle", "whiskey", "flask"]),
    ("cup",        ["cup", "mug", "glass", "tankard"]),
    ("plate",      ["plate", "bowl", "dish"]),
    ("lantern",    ["lantern", "oil lamp", "candle", "torch"]),
    ("lamp",       ["lamp", "sconce", "chandelier", "light"]),
    ("book",       ["book", "tome", "journal", "paper"]),
    ("tool",       ["tool", "hammer", "wrench", "saw"]),
    ("crate",      ["crate", "box", "chest"]),
    ("barrel",     ["barrel", "keg", "drum"]),
    ("bucket",     ["bucket", "pail"]),
    ("poster",     ["wanted poster", "poster", "painting", "banner", "sign",
                    "mirror", "tapestry", "clock"]),
    ("rug",        ["rug", "carpet"]),
    ("plant",      ["plant", "fern", "tree"]),
    ("machine",    ["machine", "robot", "console", "terminal", "reactor"]),
    ("vehicle",    ["vehicle", "cart", "wagon", "car"]),
    ("pillow",     ["pillow", "cushion", "blanket"]),
    ("rope",       ["rope", "chain"]),
    ("hay",        ["hay bale", "hay"]),
]

# Structural / architectural types — exempt from floating checks (validated by
# the beam and architectural-integrity rules instead).
STRUCTURAL_TYPES = frozenset({
    "beam", "column", "wall", "floor", "ceiling", "door", "window",
})

# Default half-extents (metres) used when a transform carries no bbox.
_DEFAULT_HALF_EXTENTS: Dict[str, Tuple[float, float, float]] = {
    "table":     (1.10, 0.375, 0.65),
    "desk":      (0.80, 0.375, 0.40),
    "bar":       (1.50, 0.525, 0.40),
    "shelf":     (0.60, 0.90, 0.20),
    "chair":     (0.25, 0.45, 0.25),
    "stool":     (0.20, 0.35, 0.20),
    "bench":     (0.75, 0.25, 0.25),
    "bed":       (1.00, 0.30, 0.80),
    "bottle":    (0.05, 0.15, 0.05),
    "cup":       (0.05, 0.06, 0.05),
    "plate":     (0.12, 0.02, 0.12),
    "lantern":   (0.10, 0.15, 0.10),
    "lamp":      (0.15, 0.25, 0.15),
    "book":      (0.12, 0.03, 0.09),
    "tool":      (0.15, 0.05, 0.05),
    "crate":     (0.40, 0.40, 0.40),
    "barrel":    (0.30, 0.45, 0.30),
    "bucket":    (0.15, 0.18, 0.15),
    "poster":    (0.40, 0.50, 0.02),
    "fireplace": (0.90, 1.00, 0.35),
    "beam":      (2.00, 0.15, 0.15),
    "column":    (0.25, 1.50, 0.25),
    "door":      (0.50, 1.05, 0.06),
    "window":    (0.50, 0.60, 0.05),
    "machine":   (1.00, 1.00, 1.00),
    "rug":       (1.00, 0.01, 0.70),
}
_GENERIC_HALF_EXTENTS = (0.25, 0.25, 0.25)

# Room dimensions (width, height, depth) per environment — §49.2 subset.
_ENV_ROOM_DIMENSIONS: Dict[str, Tuple[float, float, float]] = {
    "western_room":      (10.0, 4.0, 12.0),
    "saloon":            (14.0, 4.5, 18.0),
    "living_room":       (8.0, 3.0, 10.0),
    "office":            (8.0, 3.0, 10.0),
    "library":           (12.0, 5.0, 15.0),
    "warehouse":         (20.0, 8.0, 30.0),
    "industrial_hangar": (30.0, 12.0, 40.0),
    "robotics_lab":      (15.0, 3.5, 20.0),
    "control_room":      (10.0, 3.0, 12.0),
    "sci_fi_corridor":   (4.0, 3.0, 20.0),
    "castle_hall":       (20.0, 10.0, 30.0),
    "dungeon":           (8.0, 3.0, 10.0),
    "survival_camp":     (15.0, 5.0, 15.0),
}
_DEFAULT_ROOM = (10.0, 4.0, 12.0)


def infer_asset_type(name: str) -> str:
    """Canonical asset-type inference from a display name. '' if unknown."""
    n = (name or "").lower()
    if not n:
        return ""
    for asset_type, keywords in _ASSET_TYPE_KEYWORDS:
        for kw in keywords:
            if kw in n:
                return asset_type
    return ""


@dataclass
class SceneAsset:
    """One normalized asset in the snapshot (metadata- or viewport-sourced)."""
    asset_id:   str = ""
    asset_name: str = ""
    asset_type: str = ""
    tx: float = 0.0
    ty: float = 0.0
    tz: float = 0.0
    ry: float = 0.0
    half_x: float = 0.25
    half_y: float = 0.25
    half_z: float = 0.25
    parent_id:    str = ""
    relationship: str = ""
    cluster_id:   str = ""
    source:       str = "metadata"   # "metadata" | "viewport"

    @property
    def bottom_y(self) -> float:
        return self.ty - self.half_y

    @property
    def top_y(self) -> float:
        return self.ty + self.half_y

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id":     self.asset_id,
            "asset_name":   self.asset_name,
            "asset_type":   self.asset_type,
            "tx": round(self.tx, 4), "ty": round(self.ty, 4), "tz": round(self.tz, 4),
            "ry": round(self.ry, 4),
            "half_x": round(self.half_x, 4),
            "half_y": round(self.half_y, 4),
            "half_z": round(self.half_z, 4),
            "parent_id":    self.parent_id,
            "relationship": self.relationship,
            "cluster_id":   self.cluster_id,
            "source":       self.source,
        }


@dataclass
class SceneSnapshot:
    """Normalized view of a scene layout used by every §54 rule."""
    environment:  str = ""
    room_width:   float = 10.0
    room_height:  float = 4.0
    room_depth:   float = 12.0
    floor_height: float = 0.0
    assets:   List[SceneAsset]    = field(default_factory=list)
    openings: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def room_area(self) -> float:
        return self.room_width * self.room_depth

    @property
    def wall_x(self) -> float:
        return self.room_width / 2.0

    @property
    def wall_z(self) -> float:
        return self.room_depth / 2.0

    def assets_of_type(self, asset_type: str) -> List[SceneAsset]:
        return [a for a in self.assets if a.asset_type == asset_type]

    def find(self, asset_id: str) -> Optional[SceneAsset]:
        for a in self.assets:
            if a.asset_id == asset_id:
                return a
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "environment":  self.environment,
            "room_width":   self.room_width,
            "room_height":  self.room_height,
            "room_depth":   self.room_depth,
            "floor_height": self.floor_height,
            "assets":       [a.to_dict() for a in self.assets],
            "openings":     list(self.openings),
        }


def parse_scene(scene_layout: Dict[str, Any]) -> SceneSnapshot:
    """
    Build a SceneSnapshot from a ResolvedSceneLayout.to_dict()-style dict.
    Accepts "transforms" (Tier 9.9) or pre-normalized "assets" lists.
    Room bounds: explicit room_width/room_depth keys, then environment
    defaults, then a generic 10×12 m room. Never raises.
    """
    snap = SceneSnapshot()
    if not isinstance(scene_layout, dict):
        return snap

    snap.environment  = str(scene_layout.get("environment", "") or "")
    snap.floor_height = float(scene_layout.get("floor_height", 0.0) or 0.0)

    env_dims = _ENV_ROOM_DIMENSIONS.get(snap.environment, _DEFAULT_ROOM)
    room = scene_layout.get("room") if isinstance(scene_layout.get("room"), dict) else {}
    snap.room_width  = float(scene_layout.get("room_width")  or room.get("width")  or env_dims[0])
    snap.room_height = float(scene_layout.get("room_height") or room.get("height") or env_dims[1])
    snap.room_depth  = float(scene_layout.get("room_depth")  or room.get("depth")  or env_dims[2])

    raw_openings = scene_layout.get("openings")
    if isinstance(raw_openings, list):
        snap.openings = [o for o in raw_openings if isinstance(o, dict)]

    raw = scene_layout.get("transforms")
    if not isinstance(raw, list):
        raw = scene_layout.get("assets")
    if not isinstance(raw, list):
        raw = []

    for entry in raw:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("asset_name") or entry.get("name") or "")
        asset_type = str(entry.get("asset_type") or "") or infer_asset_type(name)
        hx = float(entry.get("bbox_half_x") or entry.get("half_x") or 0.0)
        hy = float(entry.get("bbox_half_y") or entry.get("half_y") or 0.0)
        hz = float(entry.get("bbox_half_z") or entry.get("half_z") or 0.0)
        if hx <= 0.0 and hy <= 0.0 and hz <= 0.0:
            hx, hy, hz = _DEFAULT_HALF_EXTENTS.get(asset_type, _GENERIC_HALF_EXTENTS)
        snap.assets.append(SceneAsset(
            asset_id=str(entry.get("asset_id") or name or f"asset_{len(snap.assets)}"),
            asset_name=name,
            asset_type=asset_type,
            tx=float(entry.get("tx", 0.0) or 0.0),
            ty=float(entry.get("ty", 0.0) or 0.0),
            tz=float(entry.get("tz", 0.0) or 0.0),
            ry=float(entry.get("ry", 0.0) or 0.0),
            half_x=hx, half_y=hy, half_z=hz,
            parent_id=str(entry.get("parent_id", "") or ""),
            relationship=str(entry.get("relationship", "") or ""),
            cluster_id=str(entry.get("cluster_id", "") or ""),
            source=str(entry.get("source", "metadata") or "metadata"),
        ))
    return snap


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def distance_to_nearest_wall(snap: SceneSnapshot, x: float, z: float) -> float:
    """Distance from a point to the nearest of the four room wall planes."""
    return min(
        abs(snap.wall_x - x), abs(-snap.wall_x - x),
        abs(snap.wall_z - z), abs(-snap.wall_z - z),
    )


def is_against_wall(snap: SceneSnapshot, asset: SceneAsset,
                    proximity: float = WALL_PROXIMITY) -> bool:
    """True when the asset face (centre ± half extent) touches a wall plane."""
    margin = max(asset.half_x, asset.half_z)
    return distance_to_nearest_wall(snap, asset.tx, asset.tz) <= proximity + margin


def is_wall_mounted(snap: SceneSnapshot, asset: SceneAsset) -> bool:
    """Wall-mounted: explicit relationship, or above floor and within wall proximity."""
    if asset.relationship in ("attached_to", "mounted_on", "wall_mount", "against"):
        return True
    return (
        asset.bottom_y > snap.floor_height + FLOAT_TOLERANCE
        and distance_to_nearest_wall(snap, asset.tx, asset.tz) <= WALL_PROXIMITY
    )


def is_ceiling_mounted(snap: SceneSnapshot, asset: SceneAsset) -> bool:
    if asset.relationship == "hanging_from":
        return True
    return asset.top_y >= snap.floor_height + snap.room_height - 0.6


def xz_overlap(host: SceneAsset, x: float, z: float, margin: float = 0.05) -> bool:
    """True when (x, z) is inside the host's XZ footprint (plus margin)."""
    return (
        abs(x - host.tx) <= host.half_x + margin
        and abs(z - host.tz) <= host.half_z + margin
    )


def raycast_down(snap: SceneSnapshot, asset: SceneAsset,
                 gap_tolerance: float = FLOAT_TOLERANCE) -> Optional[SceneAsset]:
    """
    §54 raycast_down(): cast from the asset's bottom centre straight down and
    return the highest support asset whose footprint contains the point and
    whose top surface lies within gap_tolerance below the asset bottom.
    Returns None when nothing supports the asset.
    """
    best: Optional[SceneAsset] = None
    best_top = -math.inf
    for other in snap.assets:
        if other is asset or other.asset_id == asset.asset_id:
            continue
        if not xz_overlap(other, asset.tx, asset.tz):
            continue
        top = other.top_y
        if top <= asset.bottom_y + gap_tolerance and top > best_top:
            best = other
            best_top = top
    if best is not None and asset.bottom_y - best_top <= gap_tolerance:
        return best
    return None


def horizontal_distance(a: SceneAsset, b: SceneAsset) -> float:
    return math.hypot(a.tx - b.tx, a.tz - b.tz)


def facing_ry_towards(from_x: float, from_z: float,
                      to_x: float, to_z: float) -> float:
    """ry (degrees, §47.4 convention: forward = (sin ry, 0, cos ry)) that
    makes an asset at (from_x, from_z) face the point (to_x, to_z)."""
    return math.degrees(math.atan2(to_x - from_x, to_z - from_z)) % 360.0
