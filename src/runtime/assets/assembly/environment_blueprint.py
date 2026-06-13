"""
Environment Blueprint (Tier 9.5 — Structural Environment Assembly)
===================================================================
Defines the structural requirements for each environment type.
An EnvironmentBlueprint declares what must exist in a scene for it to qualify
as a coherent environment rather than a collection of scattered assets.

DESIGN RULES:
  1. No bridge calls. No Houdini imports. Planning only.
  2. Blueprints are pure data — no behaviour.
  3. All blueprints are deterministic and read-only once constructed.
  4. Unknown environments get the generic fallback blueprint.
  5. Never raises.

Public API:
    EnvironmentBlueprint
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class EnvironmentBlueprint:
    """Structural requirements and asset layers for a coherent environment."""

    environment_name: str = ""

    # Required structural elements
    floor_required:   bool = True
    wall_required:    bool = True
    ceiling_required: bool = False
    door_required:    bool = False
    window_required:  bool = False

    # Asset type lists at each semantic layer (populated by ArchitecturalTemplates)
    structural_assets:   List[str] = field(default_factory=list)  # floors, walls, columns
    anchor_assets:       List[str] = field(default_factory=list)  # hero focal elements
    support_assets:      List[str] = field(default_factory=list)  # secondary props
    decorative_assets:   List[str] = field(default_factory=list)  # small dressing
    atmosphere_assets:   List[str] = field(default_factory=list)  # volumetrics / HDRI
    structural_optional: List[str] = field(default_factory=list)  # nice-to-have structure

    # Zone population execution order (always structure-first)
    zone_order: List[str] = field(default_factory=lambda: [
        "entrance_zone", "hero_zone", "support_zone",
        "decoration_zone", "atmosphere_zone", "background_zone",
    ])

    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "environment_name":    self.environment_name,
            "floor_required":      self.floor_required,
            "wall_required":       self.wall_required,
            "ceiling_required":    self.ceiling_required,
            "door_required":       self.door_required,
            "window_required":     self.window_required,
            "structural_assets":   list(self.structural_assets),
            "anchor_assets":       list(self.anchor_assets),
            "support_assets":      list(self.support_assets),
            "decorative_assets":   list(self.decorative_assets),
            "atmosphere_assets":   list(self.atmosphere_assets),
            "structural_optional": list(self.structural_optional),
            "zone_order":          list(self.zone_order),
            "description":         self.description,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "EnvironmentBlueprint":
        return cls(
            environment_name    = str(d.get("environment_name", "")),
            floor_required      = bool(d.get("floor_required", True)),
            wall_required       = bool(d.get("wall_required", True)),
            ceiling_required    = bool(d.get("ceiling_required", False)),
            door_required       = bool(d.get("door_required", False)),
            window_required     = bool(d.get("window_required", False)),
            structural_assets   = list(d.get("structural_assets", [])),
            anchor_assets       = list(d.get("anchor_assets", [])),
            support_assets      = list(d.get("support_assets", [])),
            decorative_assets   = list(d.get("decorative_assets", [])),
            atmosphere_assets   = list(d.get("atmosphere_assets", [])),
            structural_optional = list(d.get("structural_optional", [])),
            zone_order          = list(d.get("zone_order") or [
                "entrance_zone", "hero_zone", "support_zone",
                "decoration_zone", "atmosphere_zone", "background_zone",
            ]),
            description         = str(d.get("description", "")),
        )
