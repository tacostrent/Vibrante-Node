"""
Environment Blueprint (§44 — Structural Environment Assembly)
=============================================================
Defines the high-level structural profile and construction requirements for an
environment type. Unlike the Tier 9.5 assembly blueprint (which declares raw
asset type lists), this blueprint works at the *template-library* level: it
knows which atmosphere profile to use, what the canonical construction order
is, and which anchor types define the scene's identity.

DESIGN RULES:
  1. No bridge calls. No Houdini imports. Planning only.
  2. Pure data — no behaviour beyond serialization and validation.
  3. Deterministic and read-only once constructed.
  4. Unknown environments get a generic fallback blueprint.
  5. Never raises.

Public API:
    EnvironmentBlueprint
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class EnvironmentBlueprint:
    """High-level structural profile for a coherent environment."""

    environment_name: str = ""
    environment_category: str = "interior"  # interior / industrial / scientific / sci-fi / outdoor / fantasy

    # Structural requirements
    required_structure: List[str] = field(default_factory=list)   # ["floor", "wall", "ceiling", "door"]
    optional_structure: List[str] = field(default_factory=list)   # ["window", "support_column"]

    # Zone and anchor requirements
    required_zones: List[str] = field(default_factory=list)       # ["hero_zone", "entrance_zone"]
    required_anchors: List[str] = field(default_factory=list)     # ["main_table", "fireplace"]

    # Asset recommendations
    recommended_assets: List[str] = field(default_factory=list)   # broad asset type hints

    # Atmosphere
    atmosphere_profile: str = "warm_interior"  # name of AtmosphereProfile to use

    # Construction pipeline
    construction_order: List[str] = field(default_factory=lambda: [
        "structure", "zones", "anchors", "support", "decoration", "atmosphere",
    ])

    description: str = ""

    # ---------------------------------------------------------------------------
    # Serialization
    # ---------------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "environment_name":    self.environment_name,
            "environment_category": self.environment_category,
            "required_structure":  list(self.required_structure),
            "optional_structure":  list(self.optional_structure),
            "required_zones":      list(self.required_zones),
            "required_anchors":    list(self.required_anchors),
            "recommended_assets":  list(self.recommended_assets),
            "atmosphere_profile":  self.atmosphere_profile,
            "construction_order":  list(self.construction_order),
            "description":         self.description,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "EnvironmentBlueprint":
        return cls(
            environment_name    = str(d.get("environment_name", "")),
            environment_category = str(d.get("environment_category", "interior")),
            required_structure  = list(d.get("required_structure", [])),
            optional_structure  = list(d.get("optional_structure", [])),
            required_zones      = list(d.get("required_zones", [])),
            required_anchors    = list(d.get("required_anchors", [])),
            recommended_assets  = list(d.get("recommended_assets", [])),
            atmosphere_profile  = str(d.get("atmosphere_profile", "warm_interior")),
            construction_order  = list(d.get("construction_order") or [
                "structure", "zones", "anchors", "support", "decoration", "atmosphere",
            ]),
            description         = str(d.get("description", "")),
        )

    # ---------------------------------------------------------------------------
    # Validation
    # ---------------------------------------------------------------------------

    def validate(self) -> List[str]:
        """Return a list of validation errors. Empty list means valid."""
        errors: List[str] = []
        if not self.environment_name:
            errors.append("environment_name is empty")
        if not self.required_structure:
            errors.append("required_structure is empty — at least 'floor' is expected")
        if not self.required_zones:
            errors.append("required_zones is empty — at least 'hero_zone' is expected")
        if not self.required_anchors:
            errors.append("required_anchors is empty — at least one anchor must be defined")
        if not self.atmosphere_profile:
            errors.append("atmosphere_profile is empty")
        return errors
