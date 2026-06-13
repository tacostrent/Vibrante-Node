"""
Environment Builder (Tier 9 — Semantic Asset Assembly)
=======================================================
Constructs semantic environment structures from an environment name and
an optional AssetRecommendationResult.

Output is an EnvironmentPlan — a zone-organized, role-tagged asset
assignment that downstream modules (placement, storytelling, population)
consume.  No Houdini calls.  No mutations.

DESIGN RULES:
  1. Environment plans are deterministic — same inputs → same plan.
  2. Zone assignment is rule-based, not heuristic.
  3. All 5 canonical environments have hard-coded zone rules.
  4. Unknown environments fall back to industrial_hangar rules.
  5. Never raises — errors captured in EnvironmentPlan.errors.

Public API:
    EnvironmentZone
    EnvironmentPlan
    EnvironmentBuilder
    get_environment_builder()
    reset_environment_builder_for_tests()
"""

from __future__ import annotations

import time
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.runtime.assets.assembly.placement_templates import get_placement_templates

# ---------------------------------------------------------------------------
# Zone-to-category mapping for each environment
# ---------------------------------------------------------------------------

_ENV_ZONE_CATEGORIES: Dict[str, Dict[str, List[str]]] = {
    "industrial_hangar": {
        "hero_zone":    ["machinery", "vehicle", "robot"],
        "midground":    ["structure", "prop", "electronic", "machinery"],
        "background":   ["structure", "architectural", "terrain"],
        "service_area": ["prop", "electronic", "robot"],
    },
    "robotics_lab": {
        "hero_zone":       ["robot", "machinery", "electronic"],
        "midground":       ["electronic", "prop", "furniture"],
        "background":      ["structure", "electronic", "architectural"],
        "workstation_row": ["electronic", "furniture", "prop"],
    },
    "control_room": {
        "hero_zone":    ["electronic", "prop", "robot"],
        "midground":    ["electronic", "prop", "structure"],
        "background":   ["electronic", "architectural", "structure"],
        "console_arc":  ["electronic", "prop"],
    },
    "sci_fi_corridor": {
        "hero_zone":  ["electronic", "prop", "robot", "character"],
        "midground":  ["electronic", "prop", "structure"],
        "background": ["structure", "architectural", "electronic"],
    },
    "abandoned_factory": {
        "hero_zone":    ["machinery", "vehicle", "structure"],
        "midground":    ["structure", "prop", "machinery"],
        "background":   ["architectural", "structure", "terrain"],
        "rubble_field": ["prop", "terrain"],
    },
}

# Default fallback
_DEFAULT_ENV = "industrial_hangar"

# Environment human-readable descriptions
_ENV_DESCRIPTIONS: Dict[str, str] = {
    "industrial_hangar": "Large industrial space with heavy machinery and operational equipment",
    "robotics_lab":      "Precision engineering environment for robotic assembly and testing",
    "control_room":      "Command and monitoring hub with displays and control consoles",
    "sci_fi_corridor":   "Futuristic passageway with technological installations",
    "abandoned_factory": "Decayed industrial space with evidence of past operations",
}


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class EnvironmentZone:
    """One zone within an environment plan."""

    zone_name:   str
    role:        str                  # primary, support, detail, atmosphere
    depth:       float                = 0.0
    width:       float                = 12.0
    categories:  List[str]           = field(default_factory=list)
    asset_slots: List[Tuple[float, float, float]] = field(default_factory=list)
    assigned_assets: List[Dict[str, Any]] = field(default_factory=list)
    max_assets:  int                  = 5
    facing:      str                  = "camera"
    notes:       List[str]            = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_name":       self.zone_name,
            "role":            self.role,
            "depth":           self.depth,
            "width":           self.width,
            "categories":      list(self.categories),
            "asset_slots":     [list(s) for s in self.asset_slots],
            "assigned_assets": list(self.assigned_assets),
            "max_assets":      self.max_assets,
            "facing":          self.facing,
            "notes":           list(self.notes),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "EnvironmentZone":
        return cls(
            zone_name=str(d.get("zone_name", "")),
            role=str(d.get("role", "support")),
            depth=float(d.get("depth", 0.0)),
            width=float(d.get("width", 12.0)),
            categories=list(d.get("categories") or []),
            asset_slots=[tuple(s) for s in (d.get("asset_slots") or [])],  # type: ignore[misc]
            assigned_assets=list(d.get("assigned_assets") or []),
            max_assets=int(d.get("max_assets", 5)),
            facing=str(d.get("facing", "camera")),
            notes=list(d.get("notes") or []),
        )


@dataclass
class EnvironmentPlan:
    """
    Output of EnvironmentBuilder — a zone-structured, role-tagged
    environment ready for placement and population.
    """

    plan_id:        str = field(default_factory=lambda: f"env_{uuid.uuid4().hex[:10]}")
    environment:    str = ""
    description:    str = ""
    zones:          Dict[str, EnvironmentZone] = field(default_factory=dict)
    zone_order:     List[str] = field(default_factory=list)  # render order
    asset_count:    int = 0
    total_capacity: int = 0
    ok:             bool = True
    errors:         List[str] = field(default_factory=list)
    warnings:       List[str] = field(default_factory=list)
    generated_at:   float = field(default_factory=time.time)

    # Structural check
    @property
    def has_hero_zone(self) -> bool:
        return "hero_zone" in self.zones

    @property
    def populated_zone_count(self) -> int:
        return sum(1 for z in self.zones.values() if z.assigned_assets)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id":        self.plan_id,
            "environment":    self.environment,
            "description":    self.description,
            "zones":          {name: z.to_dict() for name, z in self.zones.items()},
            "zone_order":     list(self.zone_order),
            "asset_count":    self.asset_count,
            "total_capacity": self.total_capacity,
            "ok":             self.ok,
            "errors":         list(self.errors),
            "warnings":       list(self.warnings),
            "generated_at":   self.generated_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "EnvironmentPlan":
        zones = {
            name: EnvironmentZone.from_dict(z)
            for name, z in (d.get("zones") or {}).items()
        }
        return cls(
            plan_id=str(d.get("plan_id", f"env_{uuid.uuid4().hex[:10]}")),
            environment=str(d.get("environment", "")),
            description=str(d.get("description", "")),
            zones=zones,
            zone_order=list(d.get("zone_order") or []),
            asset_count=int(d.get("asset_count", 0)),
            total_capacity=int(d.get("total_capacity", 0)),
            ok=bool(d.get("ok", True)),
            errors=list(d.get("errors") or []),
            warnings=list(d.get("warnings") or []),
            generated_at=float(d.get("generated_at", 0.0)),
        )


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class EnvironmentBuilder:
    """
    Constructs semantic environment structures from environment name
    and optional recommended assets.
    """

    def build_environment(
        self,
        environment: str,
        recommendations: Optional[List[Dict[str, Any]]] = None,
    ) -> EnvironmentPlan:
        """
        Build a full EnvironmentPlan for the given environment.

        Args:
            environment:     One of the 5 canonical environment names.
            recommendations: Optional list of AssetRecommendation.to_dict()
                             objects to assign into zones.

        Returns:
            :class:`EnvironmentPlan`.  Never raises.
        """
        plan = EnvironmentPlan(environment=environment)
        try:
            env_key = environment if environment in _ENV_ZONE_CATEGORIES else _DEFAULT_ENV
            if env_key != environment:
                plan.warnings.append(
                    f"Unknown environment {environment!r}; using {_DEFAULT_ENV!r} rules."
                )
            plan.description = _ENV_DESCRIPTIONS.get(env_key, "Production environment")
            plan.zones = self.build_environment_zones(env_key)
            plan.zone_order = _zone_render_order(env_key, plan.zones)
            plan.total_capacity = sum(z.max_assets for z in plan.zones.values())

            if recommendations:
                plan.asset_count = self._assign_recommendations(plan, recommendations)

            self.assign_environment_roles(plan)
            plan.ok = True

        except Exception as exc:
            plan.ok = False
            plan.errors.append(f"Environment build failed: {exc}")

        return plan

    def build_environment_zones(self, environment: str) -> Dict[str, EnvironmentZone]:
        """Construct the zone dict for an environment from the placement template."""
        tmpl = get_placement_templates().get_template_or_default(environment)
        zone_cats = _ENV_ZONE_CATEGORIES.get(environment, _ENV_ZONE_CATEGORIES[_DEFAULT_ENV])
        depths = tmpl.get("zone_depths", {})
        widths = tmpl.get("zone_widths", {})
        zones: Dict[str, EnvironmentZone] = {}

        for zone_name, cats in zone_cats.items():
            zone_cfg = tmpl.get(zone_name, {})
            max_assets = zone_cfg.get("max_assets", 4) if isinstance(zone_cfg, dict) else 4
            facing = zone_cfg.get("facing", "camera") if isinstance(zone_cfg, dict) else "camera"
            # Build slot list
            slots_raw = zone_cfg.get("slots", []) if isinstance(zone_cfg, dict) else []
            if isinstance(slots_raw, dict):
                # hero_zone uses slots keyed by count — use max key as canonical list
                max_key = max(slots_raw.keys())
                slots = [tuple(s) for s in slots_raw[max_key]]
            else:
                slots = [tuple(s) for s in slots_raw]
            role = _zone_role(zone_name)
            zones[zone_name] = EnvironmentZone(
                zone_name=zone_name,
                role=role,
                depth=depths.get(zone_name, 0.0),
                width=widths.get(zone_name, 12.0),
                categories=list(cats),
                asset_slots=slots,  # type: ignore[arg-type]
                max_assets=max_assets,
                facing=facing,
            )

        return zones

    def assign_environment_roles(self, plan: EnvironmentPlan) -> None:
        """Tag each zone with its narrative role (primary/support/detail/atmosphere)."""
        for zone_name, zone in plan.zones.items():
            zone.role = _zone_role(zone_name)

    def validate_environment_structure(self, plan: EnvironmentPlan) -> Dict[str, Any]:
        """Check that an EnvironmentPlan meets minimum structural requirements."""
        errors = []
        warnings = []
        if not plan.zones:
            errors.append("No zones defined.")
        if not plan.has_hero_zone:
            errors.append("hero_zone is required.")
        if "midground" not in plan.zones:
            warnings.append("No midground zone — depth will be shallow.")
        if "background" not in plan.zones:
            warnings.append("No background zone — scene will lack depth.")
        return {
            "valid":    len(errors) == 0,
            "errors":   errors,
            "warnings": warnings,
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _assign_recommendations(
        self,
        plan: EnvironmentPlan,
        recommendations: List[Dict[str, Any]],
    ) -> int:
        """
        Distribute recommendations into zones by category affinity.
        Returns total number of assets assigned.
        """
        assigned = 0
        # Assignment priority: hero_zone first, then support zones, then background.
        # (zone_order is the back-to-front RENDER order; for assignment we reverse it
        #  so the primary/support zones are filled before background zones.)
        render_order = plan.zone_order or list(plan.zones.keys())
        zone_order = list(reversed(render_order))

        for rec in recommendations:
            asset = rec.get("asset") or {}
            category = str(asset.get("category", "")).lower()
            # Find best-fit zone
            placed = False
            for zone_name in zone_order:
                zone = plan.zones.get(zone_name)
                if zone is None:
                    continue
                if len(zone.assigned_assets) >= zone.max_assets:
                    continue
                if not zone.categories or category in zone.categories or not category:
                    zone.assigned_assets.append(rec)
                    assigned += 1
                    placed = True
                    break
            if not placed:
                # Overflow into background as fallback
                bg = plan.zones.get("background")
                if bg and len(bg.assigned_assets) < bg.max_assets * 2:
                    bg.assigned_assets.append(rec)
                    assigned += 1
                else:
                    plan.warnings.append(
                        f"Asset {asset.get('name', '?')!r} could not be assigned to any zone."
                    )

        return assigned


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _zone_role(zone_name: str) -> str:
    hero_zones   = {"hero_zone"}
    detail_zones = {"service_area", "wall_run_left", "wall_run_right",
                    "wall_panel_left", "wall_panel_right", "rubble_field"}
    atm_zones    = {"atmosphere_zone", "ceiling_edge"}
    if zone_name in hero_zones:
        return "primary"
    if zone_name in detail_zones:
        return "detail"
    if zone_name in atm_zones:
        return "atmosphere"
    return "support"


def _zone_render_order(environment: str, zones: Dict[str, EnvironmentZone]) -> List[str]:
    """Return zones in back-to-front render order (background first)."""
    by_depth = sorted(zones.items(), key=lambda kv: kv[1].depth)
    return [name for name, _ in by_depth]


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[EnvironmentBuilder] = None
_INSTANCE_LOCK = threading.Lock()


def get_environment_builder() -> EnvironmentBuilder:
    """Return the module-level singleton EnvironmentBuilder."""
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = EnvironmentBuilder()
    return _INSTANCE


def reset_environment_builder_for_tests() -> None:
    """Replace the singleton.  For test isolation only."""
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
