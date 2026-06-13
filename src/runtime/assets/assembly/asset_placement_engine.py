"""
Asset Placement Engine (Tier 9 — Semantic Asset Assembly)
==========================================================
Generates deterministic world-space placement for each asset in an
EnvironmentPlan.

Each asset receives:
  - position  (tx, ty, tz)  — world-space translation
  - rotation  (rx, ry, rz)  — Y-axis facing + optional tilt
  - scale     (sx, sy, sz)  — uniform per category

Positions come from PlacementTemplates slot data.
Rotations come from facing-direction tables + per-slot overrides.
Scales come from category heuristics.

DESIGN RULES:
  1. Deterministic — same EnvironmentPlan → same placement every time.
  2. No randomness.  No noise.  Only arithmetic and lookup tables.
  3. No bridge calls.  No Houdini imports.  Planning only.
  4. Never raises — errors captured in PlacementPlan.errors.

Public API:
    AssetPlacement
    PlacementPlan
    AssetPlacementEngine
    get_asset_placement_engine()
    reset_asset_placement_engine_for_tests()
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.runtime.assets.assembly.environment_builder import EnvironmentPlan, EnvironmentZone
from src.runtime.assets.assembly.placement_templates import get_placement_templates
from src.runtime.assets.assembly.bounding_box_extractor import get_bbox_extractor
from src.runtime.assets.assembly.collision_detector import get_collision_detector
from src.runtime.assets.assembly.clearance_validator import get_clearance_validator
from src.runtime.assets.assembly.placement_optimizer import get_placement_optimizer
from src.runtime.assets.assembly.asset_scale_analyzer import get_asset_scale_analyzer
from src.runtime.assets.assembly.layout_spacing_engine import get_layout_spacing_engine
from src.runtime.assets.assembly.placement_relationships import get_placement_relationships

# ---------------------------------------------------------------------------
# Category → uniform scale
# ---------------------------------------------------------------------------

_CATEGORY_SCALES: Dict[str, float] = {
    "vehicle":       1.0,
    "character":     1.0,
    "robot":         1.0,
    "machinery":     1.0,
    "electronic":    0.8,
    "prop":          0.7,
    "furniture":     0.8,
    "structure":     1.2,
    "architectural": 1.4,
    "terrain":       2.0,
    "pipe":          0.9,
    "vegetation":    1.0,
    "creature":      1.0,
    "weapon":        0.85,
    "hdri":          1.0,
    "material":      1.0,
}

_DEFAULT_SCALE = 1.0

# Facing direction → base Y rotation (degrees)
_FACING_ROTY: Dict[str, float] = {
    "camera":    0.0,
    "inward":    180.0,
    "outward":   0.0,
    "forward":   0.0,
    "scattered": 45.0,
}


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class AssetPlacement:
    """World-space placement for one asset."""

    asset_name:       str
    zone_name:        str
    slot_index:       int
    position:         Tuple[float, float, float] = (0.0, 0.0, 0.0)
    rotation:         Tuple[float, float, float] = (0.0, 0.0, 0.0)
    scale:            Tuple[float, float, float] = (1.0, 1.0, 1.0)
    category:         str = ""
    facing:           str = "camera"
    notes:            List[str] = field(default_factory=list)
    spatial_metadata: Optional[Dict[str, Any]] = field(default=None)  # SpatialMetadata.to_dict()
    # Tier 9.6: scale classification and semantic role
    scale_class:      str = "medium"   # tiny/small/medium/large/structural
    role:             str = "prop"     # seating/furniture_anchor/decoration/structure/…
    is_structural:    bool = False     # True → routed to structure builder

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_name":      self.asset_name,
            "zone_name":       self.zone_name,
            "slot_index":      self.slot_index,
            "position":        list(self.position),
            "rotation":        list(self.rotation),
            "scale":           list(self.scale),
            "category":        self.category,
            "facing":          self.facing,
            "notes":           list(self.notes),
            "spatial_metadata": self.spatial_metadata,
            "scale_class":     self.scale_class,
            "role":            self.role,
            "is_structural":   self.is_structural,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AssetPlacement":
        return cls(
            asset_name=str(d.get("asset_name", "")),
            zone_name=str(d.get("zone_name", "")),
            slot_index=int(d.get("slot_index", 0)),
            position=tuple(d.get("position", [0.0, 0.0, 0.0])),  # type: ignore[arg-type]
            rotation=tuple(d.get("rotation", [0.0, 0.0, 0.0])),  # type: ignore[arg-type]
            scale=tuple(d.get("scale", [1.0, 1.0, 1.0])),        # type: ignore[arg-type]
            category=str(d.get("category", "")),
            facing=str(d.get("facing", "camera")),
            notes=list(d.get("notes") or []),
            spatial_metadata=d.get("spatial_metadata"),
            scale_class=str(d.get("scale_class", "medium")),
            role=str(d.get("role", "prop")),
            is_structural=bool(d.get("is_structural", False)),
        )


@dataclass
class PlacementPlan:
    """Placement plan for an entire environment."""

    plan_id:             str = field(default_factory=lambda: f"place_{uuid.uuid4().hex[:10]}")
    environment:         str = ""
    placements:          List[AssetPlacement] = field(default_factory=list)
    zone_counts:         Dict[str, int] = field(default_factory=dict)
    total_placed:        int  = 0
    collision_count:     int  = 0   # collisions remaining after optimization
    clearance_violations: int = 0   # clearance violations remaining after optimization
    spatial_optimized:   bool = False
    ok:                  bool = True
    errors:              List[str] = field(default_factory=list)
    warnings:            List[str] = field(default_factory=list)
    generated_at:        float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id":             self.plan_id,
            "environment":         self.environment,
            "placements":          [p.to_dict() for p in self.placements],
            "zone_counts":         dict(self.zone_counts),
            "total_placed":        self.total_placed,
            "collision_count":     self.collision_count,
            "clearance_violations": self.clearance_violations,
            "spatial_optimized":   self.spatial_optimized,
            "ok":                  self.ok,
            "errors":              list(self.errors),
            "warnings":            list(self.warnings),
            "generated_at":        self.generated_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PlacementPlan":
        return cls(
            plan_id=str(d.get("plan_id", f"place_{uuid.uuid4().hex[:10]}")),
            environment=str(d.get("environment", "")),
            placements=[AssetPlacement.from_dict(p) for p in (d.get("placements") or [])],
            zone_counts=dict(d.get("zone_counts") or {}),
            total_placed=int(d.get("total_placed", 0)),
            collision_count=int(d.get("collision_count", 0)),
            clearance_violations=int(d.get("clearance_violations", 0)),
            spatial_optimized=bool(d.get("spatial_optimized", False)),
            ok=bool(d.get("ok", True)),
            errors=list(d.get("errors") or []),
            warnings=list(d.get("warnings") or []),
            generated_at=float(d.get("generated_at", 0.0)),
        )


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class AssetPlacementEngine:
    """
    Generates deterministic asset placement plans from an EnvironmentPlan.
    No randomness. No noise. Only arithmetic and lookup tables.
    """

    def generate_placement_plan(self, env_plan: EnvironmentPlan) -> PlacementPlan:
        """
        Build a full PlacementPlan from an EnvironmentPlan.

        Steps:
          1. Assign slot positions, rotations, and scales from templates.
          2. Build SpatialMetadata for every asset (real bbox / footprint).
          3. Run PlacementOptimizer to resolve collisions and clearance.
          4. Run final collision / clearance validation for reporting.

        Never raises — errors captured in PlacementPlan.errors.
        """
        plan = PlacementPlan(environment=env_plan.environment)
        try:
            tmpl = get_placement_templates().get_template_or_default(env_plan.environment)
            positions = self.assign_asset_positions(env_plan, tmpl)
            rotations = self.assign_asset_rotations(env_plan, tmpl)
            scales    = self.assign_asset_scales(env_plan)

            bbox_ext      = get_bbox_extractor()
            scale_analyzer = get_asset_scale_analyzer()
            relationships  = get_placement_relationships()

            # Phase 1: build initial placements + collect spatial data
            # 7-step scale-aware pipeline per asset:
            #  1. Analyze asset scale (unit normalize + classify)
            #  2. Calculate footprint
            #  3. Select semantic zone (already done by EnvironmentBuilder)
            #  4. Compute valid position (template slot or scale-aware fallback)
            #  5. Validate spacing (via PlacementOptimizer below)
            #  6. Validate collisions (via CollisionDetector below)
            #  7. Commit placement
            spatial_input: List[Tuple[
                str,
                Tuple[float, float, float],
                Any,  # SpatialMetadata
            ]] = []

            for zone_name in env_plan.zone_order or list(env_plan.zones.keys()):
                zone = env_plan.zones.get(zone_name)
                if not zone:
                    continue
                for idx, rec in enumerate(zone.assigned_assets):
                    asset      = rec.get("asset") or {}
                    asset_name = str(asset.get("name") or asset.get("asset_id") or f"asset_{idx}")
                    key        = f"{zone_name}/{asset_name}"
                    pos        = positions.get(key, (0.0, 0.0, 0.0))
                    rot        = rotations.get(key, (0.0, 0.0, 0.0))
                    scl        = scales.get(str(asset.get("category", "")))
                    uniform_s  = scl if scl is not None else _DEFAULT_SCALE

                    # Step 1: Analyze scale — normalizes units and classifies
                    scale_profile = scale_analyzer.analyze_asset(asset)

                    # Step 2: Get role for semantic routing
                    a_type = str(asset.get("type") or asset.get("asset_type") or "")
                    a_cat  = str(asset.get("category") or "")
                    role   = relationships.get_role(a_type, a_cat)
                    is_structural = scale_profile.is_structural

                    # Structural assets get flagged; position still assigned
                    # (physical realization routes them to StructureBuilder)
                    if is_structural:
                        plan.warnings.append(
                            f"Structural asset '{asset_name}' in zone '{zone_name}' "
                            f"— route to EnvironmentStructureBuilder for physical placement."
                        )

                    # Step 4: Build spatial metadata from unit-normalized dimensions
                    meta = bbox_ext.build_spatial_metadata(asset)

                    placement = AssetPlacement(
                        asset_name    = asset_name,
                        zone_name     = zone_name,
                        slot_index    = idx,
                        position      = pos,
                        rotation      = rot,
                        scale         = (uniform_s, uniform_s, uniform_s),
                        category      = a_cat,
                        facing        = zone.facing,
                        spatial_metadata = meta.to_dict(),
                        scale_class   = scale_profile.asset_scale_class,
                        role          = role,
                        is_structural = is_structural,
                    )
                    plan.placements.append(placement)
                    spatial_input.append((key, pos, meta))
                plan.zone_counts[zone_name] = len(zone.assigned_assets)

            # Phase 2: spatial optimization — resolve collisions & clearance
            if spatial_input:
                opt_plan = get_placement_optimizer().optimize_layout(spatial_input)
                plan.spatial_optimized = True
                plan.warnings.extend(opt_plan.warnings)

                # Map optimized positions back to placements
                pos_map = {p.asset_id: p.final_pos for p in opt_plan.placements}
                for p in plan.placements:
                    opt_key = f"{p.zone_name}/{p.asset_name}"
                    if opt_key in pos_map:
                        p.position = pos_map[opt_key]

            # Phase 3: post-optimization spatial validation (for reporting)
            final_spatial = [
                (f"{p.zone_name}/{p.asset_name}", p.position,
                 bbox_ext.build_spatial_metadata(
                     {"category": p.category, "asset_id": p.asset_name}
                 ))
                for p in plan.placements
            ]
            if final_spatial:
                col_report = get_collision_detector().validate_scene(final_spatial)
                clr_report = get_clearance_validator().validate_scene_clearance(final_spatial)
                plan.collision_count      = col_report.collision_count
                plan.clearance_violations = clr_report.violation_count
                if col_report.collision_count > 0:
                    plan.warnings.append(
                        f"{col_report.collision_count} collision(s) remain after optimization."
                    )
                if clr_report.violation_count > 0:
                    plan.warnings.append(
                        f"{clr_report.violation_count} clearance violation(s) remain."
                    )

            # Legacy spacing check (duplicate-position guard)
            spacing_result = self.validate_spacing(plan)
            plan.warnings.extend(spacing_result.get("warnings", []))

            plan.total_placed = len(plan.placements)
            plan.ok = True

        except Exception as exc:
            plan.ok = False
            plan.errors.append(f"Placement plan failed: {exc}")

        return plan

    def assign_asset_positions(
        self,
        env_plan: EnvironmentPlan,
        template: Dict[str, Any],
    ) -> Dict[str, Tuple[float, float, float]]:
        """
        Map each asset to a world-space (tx, ty, tz) position.
        Key: "{zone_name}/{asset_name}"
        """
        result: Dict[str, Tuple[float, float, float]] = {}
        depths = template.get("zone_depths", {})

        for zone_name in env_plan.zone_order or list(env_plan.zones.keys()):
            zone = env_plan.zones.get(zone_name)
            if not zone:
                continue
            zone_tmpl = template.get(zone_name)
            depth_z   = float(depths.get(zone_name, 0.0))

            for idx, rec in enumerate(zone.assigned_assets):
                asset      = rec.get("asset") or {}
                asset_name = str(asset.get("name") or asset.get("asset_id") or f"asset_{idx}")
                key        = f"{zone_name}/{asset_name}"

                pos = _slot_position(zone_tmpl, idx, depth_z, zone.width)
                result[key] = pos

        return result

    def assign_asset_rotations(
        self,
        env_plan: EnvironmentPlan,
        template: Dict[str, Any],
    ) -> Dict[str, Tuple[float, float, float]]:
        """
        Map each asset to a (rx, ry, rz) rotation tuple.
        Key: "{zone_name}/{asset_name}"
        """
        result: Dict[str, Tuple[float, float, float]] = {}

        for zone_name in env_plan.zone_order or list(env_plan.zones.keys()):
            zone = env_plan.zones.get(zone_name)
            if not zone:
                continue
            zone_tmpl = template.get(zone_name)
            count     = len(zone.assigned_assets)

            for idx, rec in enumerate(zone.assigned_assets):
                asset      = rec.get("asset") or {}
                asset_name = str(asset.get("name") or asset.get("asset_id") or f"asset_{idx}")
                key        = f"{zone_name}/{asset_name}"
                ry         = _slot_rotation_y(zone_tmpl, idx, count, zone.facing)
                result[key] = (0.0, ry, 0.0)

        return result

    def assign_asset_scales(
        self,
        env_plan: EnvironmentPlan,
    ) -> Dict[str, float]:
        """
        Return category → uniform scale factor mapping.
        """
        result: Dict[str, float] = dict(_CATEGORY_SCALES)
        # Override from zone categories to catch any environment-specific hints
        for zone in env_plan.zones.values():
            for cat in zone.categories:
                if cat not in result:
                    result[cat] = _DEFAULT_SCALE
        return result

    def validate_spacing(self, plan: PlacementPlan) -> Dict[str, Any]:
        """
        Check that no two assets in the same zone share the same slot position.
        Returns warnings list.
        """
        warnings: List[str] = []
        seen: Dict[str, set] = {}
        for p in plan.placements:
            key = p.zone_name
            pos_key = (round(p.position[0], 2), round(p.position[1], 2), round(p.position[2], 2))
            if key not in seen:
                seen[key] = set()
            if pos_key in seen[key]:
                warnings.append(
                    f"Duplicate position {pos_key} in zone {p.zone_name!r} "
                    f"for asset {p.asset_name!r}."
                )
            seen[key].add(pos_key)
        return {"warnings": warnings}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _slot_position(
    zone_tmpl: Any,
    idx: int,
    depth_z: float,
    width: float,
) -> Tuple[float, float, float]:
    """Resolve world-space (tx, ty, tz) for a slot index in a zone template."""
    if zone_tmpl is None:
        # Evenly-spaced fallback
        return (_even_offset(idx, width), 0.0, depth_z)

    if isinstance(zone_tmpl, list):
        # Wall-run / panel list — raw (x, y, z) tuples
        if idx < len(zone_tmpl):
            s = zone_tmpl[idx]
            return (float(s[0]), float(s[1]), float(s[2]))
        # Scale-aware overflow: use ~1.5 m step (replaces fixed 2.0 m)
        base = zone_tmpl[-1] if zone_tmpl else (0.0, 0.0, depth_z)
        step = _scale_aware_step(width)
        return (float(base[0]), float(base[1]), float(base[2]) - (idx - len(zone_tmpl) + 1) * step)

    if isinstance(zone_tmpl, dict):
        slots_raw = zone_tmpl.get("slots")
        y_offset  = float(zone_tmpl.get("y_offset", 0.0))

        if isinstance(slots_raw, dict):
            # hero_zone keyed by count — pick actual count key or nearest
            count = idx + 1
            best_key = min(slots_raw.keys(), key=lambda k: abs(int(k) - count))
            slot_list = slots_raw[best_key]
            if idx < len(slot_list):
                s = slot_list[idx]
                return (float(s[0]), y_offset + float(s[1]), float(s[2]))
            # Scale-aware overflow (replaces fixed 3.0 m)
            last = slot_list[-1] if slot_list else (0.0, 0.0, depth_z)
            step = _scale_aware_step(width)
            return (float(last[0]) + (idx - len(slot_list) + 1) * step, y_offset, float(last[2]))

        if isinstance(slots_raw, list):
            if idx < len(slots_raw):
                s = slots_raw[idx]
                return (float(s[0]), y_offset + float(s[1]), float(s[2]))
            last = slots_raw[-1] if slots_raw else (0.0, 0.0, depth_z)
            step = _scale_aware_step(width)
            return (float(last[0]) + (idx - len(slots_raw) + 1) * step, y_offset, float(last[2]))

    # Fallback
    return (_even_offset(idx, width), 0.0, depth_z)


def _slot_rotation_y(
    zone_tmpl: Any,
    idx: int,
    count: int,
    facing: str,
) -> float:
    """Resolve Y rotation for a slot."""
    base = _FACING_ROTY.get(facing, 0.0)

    if not isinstance(zone_tmpl, dict):
        return base

    # Per-slot rotation table (hero_zone pattern)
    per_slot = zone_tmpl.get("rotation_y_per_slot")
    if isinstance(per_slot, dict):
        best_key = min(per_slot.keys(), key=lambda k: abs(int(k) - count))
        rots = per_slot[best_key]
        if idx < len(rots):
            return float(rots[idx])

    # Single base rotation (inward / outward zones)
    rot_base = zone_tmpl.get("rotation_y_base")
    if rot_base is not None:
        side = 1.0 if idx % 2 == 0 else -1.0
        return float(rot_base) * side

    return base


def _even_offset(idx: int, width: float) -> float:
    """Simple evenly-spaced X offset centred at 0."""
    return (idx - 0) * (width / max(1, 3))


def _scale_aware_step(zone_width: float) -> float:
    """Return a sensible overflow step (metres) based on zone width.

    Replaces the hard-coded 2.0 / 3.0 m constants so overflow assets are
    spaced relative to the zone's declared width rather than an arbitrary
    fixed distance.  Clamped to [0.8, 3.0] m.
    """
    step = zone_width / 4.0
    return max(0.8, min(3.0, step))


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[AssetPlacementEngine] = None
_INSTANCE_LOCK = threading.Lock()


def get_asset_placement_engine() -> AssetPlacementEngine:
    """Return the module-level singleton AssetPlacementEngine."""
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = AssetPlacementEngine()
    return _INSTANCE


def reset_asset_placement_engine_for_tests() -> None:
    """Replace the singleton.  For test isolation only."""
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
