"""
Workflow Pack (Tier 10 — Workflow Packs & Production Blueprints)
================================================================
Represents a reusable, production-grade workflow configuration that
encapsulates every strategic decision for a canonical environment type.

A WorkflowPack is a value object — it is immutable after construction
and safe to share across threads.  All methods that return modified
versions return new instances via clone().

DESIGN RULES:
  1. Deterministic — same dict input always produces the same pack.
  2. No bridge calls.  No Houdini imports.  Data only.
  3. Never raises — validate() returns an error list instead.
  4. Immutable after construction — use clone() for modifications.

Public API:
    WorkflowPack
    get_builtin_packs() -> List[WorkflowPack]
    reset_workflow_pack_for_tests()
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Schema version — bump when adding required fields
# ---------------------------------------------------------------------------

PACK_SCHEMA_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Required top-level strategy keys
# ---------------------------------------------------------------------------

_REQUIRED_STRATEGY_KEYS = {
    "environment_type",
    "asset_strategy",
    "population_strategy",
    "placement_strategy",
    "lighting_strategy",
    "camera_strategy",
    "atmosphere_strategy",
    "review_strategy",
}

# ---------------------------------------------------------------------------
# Valid environment types (mirrors Tier 9)
# ---------------------------------------------------------------------------

VALID_ENVIRONMENT_TYPES = frozenset({
    # Original 5
    "industrial_hangar", "robotics_lab", "control_room",
    "sci_fi_corridor", "abandoned_factory",
    # §39 Industrial
    "warehouse", "shipyard", "oil_refinery", "power_station",
    "mining_facility", "construction_site",
    # §39 Scientific
    "research_lab", "medical_lab", "clean_room", "biohazard_facility",
    # §39 Military
    "military_base", "command_center", "military_hangar", "checkpoint", "bunker",
    # §39 Sci-Fi
    "space_station", "spaceship_bridge", "engineering_bay",
    "alien_facility", "cyberpunk_city",
    # §39 Urban
    "city_street", "alleyway", "subway_station", "parking_garage",
    "rooftop", "shopping_mall",
    # §39 Interior
    "western_room", "saloon", "living_room", "office",
    "hotel_lobby", "restaurant", "workshop", "library",
    # §39 Nature
    "forest", "jungle", "desert", "canyon", "mountain", "coastline", "swamp",
    # §39 Fantasy
    "castle_hall", "dungeon", "wizard_tower", "ancient_ruins", "temple",
    # §39 Post-Apocalyptic
    "abandoned_city", "destroyed_highway", "ruined_industrial_site", "survival_camp",
})


# ---------------------------------------------------------------------------
# WorkflowPack
# ---------------------------------------------------------------------------

@dataclass
class WorkflowPack:
    """Reusable production workflow configuration."""

    name:                 str
    version:              str
    environment_type:     str
    asset_strategy:       Dict[str, Any]
    population_strategy:  Dict[str, Any]
    placement_strategy:   Dict[str, Any]
    lighting_strategy:    Dict[str, Any]
    camera_strategy:      Dict[str, Any]
    atmosphere_strategy:  Dict[str, Any]
    review_strategy:      Dict[str, Any]
    metadata:             Dict[str, Any] = field(default_factory=dict)

    # Auto-assigned
    pack_id:    str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: float = field(default_factory=time.time)
    schema_version: str = field(default=PACK_SCHEMA_VERSION)

    # -----------------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        return {
            "pack_id":              self.pack_id,
            "name":                 self.name,
            "version":              self.version,
            "schema_version":       self.schema_version,
            "environment_type":     self.environment_type,
            "asset_strategy":       self.asset_strategy,
            "population_strategy":  self.population_strategy,
            "placement_strategy":   self.placement_strategy,
            "lighting_strategy":    self.lighting_strategy,
            "camera_strategy":      self.camera_strategy,
            "atmosphere_strategy":  self.atmosphere_strategy,
            "review_strategy":      self.review_strategy,
            "metadata":             self.metadata,
            "created_at":           self.created_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "WorkflowPack":
        return cls(
            pack_id             = d.get("pack_id", str(uuid.uuid4())),
            name                = d.get("name", ""),
            version             = d.get("version", "1.0.0"),
            schema_version      = d.get("schema_version", PACK_SCHEMA_VERSION),
            environment_type    = d.get("environment_type", ""),
            asset_strategy      = d.get("asset_strategy", {}),
            population_strategy = d.get("population_strategy", {}),
            placement_strategy  = d.get("placement_strategy", {}),
            lighting_strategy   = d.get("lighting_strategy", {}),
            camera_strategy     = d.get("camera_strategy", {}),
            atmosphere_strategy = d.get("atmosphere_strategy", {}),
            review_strategy     = d.get("review_strategy", {}),
            metadata            = d.get("metadata", {}),
            created_at          = d.get("created_at", time.time()),
        )

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, indent=indent)

    @classmethod
    def from_json(cls, s: str) -> "WorkflowPack":
        return cls.from_dict(json.loads(s))

    # -----------------------------------------------------------------
    def validate(self) -> List[str]:
        """Return a list of error strings.  Empty list means valid."""
        errors: List[str] = []
        if not self.name:
            errors.append("name must not be empty")
        if not self.environment_type:
            errors.append("environment_type must not be empty")
        if self.environment_type and self.environment_type not in VALID_ENVIRONMENT_TYPES:
            errors.append(
                f"environment_type {self.environment_type!r} is not a known environment; "
                f"valid: {sorted(VALID_ENVIRONMENT_TYPES)}"
            )
        if not isinstance(self.asset_strategy, dict) or not self.asset_strategy:
            errors.append("asset_strategy must be a non-empty dict")
        if not isinstance(self.lighting_strategy, dict) or not self.lighting_strategy:
            errors.append("lighting_strategy must be a non-empty dict")
        if not isinstance(self.camera_strategy, dict) or not self.camera_strategy:
            errors.append("camera_strategy must be a non-empty dict")
        threshold = self.review_strategy.get("production_threshold")
        if threshold is not None and not (0.0 <= float(threshold) <= 1.0):
            errors.append(
                f"review_strategy.production_threshold must be in [0, 1]; got {threshold}"
            )
        return errors

    # -----------------------------------------------------------------
    def clone(self, **overrides: Any) -> "WorkflowPack":
        """Return a new WorkflowPack with the given fields replaced."""
        d = self.to_dict()
        d.update(overrides)
        d.pop("pack_id", None)   # new identity
        d.pop("created_at", None)
        return WorkflowPack.from_dict(d)


# ---------------------------------------------------------------------------
# Built-in packs
# ---------------------------------------------------------------------------

def _make_pack(
    name: str,
    env: str,
    lighting: str,
    camera: str,
    atmosphere: str,
    hero_categories: List[str],
    fog_density: str = "medium",
    review_threshold: float = 0.70,
    tags: Optional[List[str]] = None,
) -> WorkflowPack:
    return WorkflowPack(
        name             = name,
        version          = "1.0.0",
        environment_type = env,
        asset_strategy   = {
            "hero_categories":       hero_categories,
            "preferred_formats":     ["fbx", "obj", "usd", "abc"],
            "max_hero_assets":       3,
            "deduplication":         True,
        },
        population_strategy = {
            "hero_max":   3,
            "detail_cap": 0.60,
            "balance":    "standard",
        },
        placement_strategy = {
            "template":       env,
            "back_to_front":  True,
            "deterministic":  True,
        },
        lighting_strategy = {
            "style":      lighting,
            "key_target": "hero_zone",
            "volumetric": fog_density != "none",
        },
        camera_strategy = {
            "mode":                camera,
            "establishing_shot":   True,
            "hero_shot":           True,
        },
        atmosphere_strategy = {
            "atmosphere_type": f"{env.replace('_', '_')}",
            "fog_density":     fog_density,
            "particles":       True,
        },
        review_strategy = {
            "production_threshold": review_threshold,
            "require_hero":         True,
            "require_depth":        True,
            "min_readability":      0.60,
        },
        metadata = {
            "tags":        tags or [env.replace("_", "-"), "production"],
            "description": f"Production-grade workflow pack for {env.replace('_', ' ')}.",
            "builtin":     True,
        },
    )


_BUILTIN_PACKS: Optional[List[WorkflowPack]] = None


def get_builtin_packs() -> List[WorkflowPack]:
    """Return the list of built-in workflow packs (lazy init, singleton)."""
    global _BUILTIN_PACKS
    if _BUILTIN_PACKS is None:
        _BUILTIN_PACKS = [
            _make_pack(
                "industrial_hangar_pack", "industrial_hangar",
                lighting="cinematic_industrial",
                camera="cinematic_push_in",
                atmosphere="industrial_fog",
                hero_categories=["machinery", "vehicle", "robot"],
                fog_density="medium",
                review_threshold=0.70,
                tags=["industrial", "cinematic", "hangar", "production"],
            ),
            _make_pack(
                "robotics_lab_pack", "robotics_lab",
                lighting="cold_scifi",
                camera="orbital_reveal",
                atmosphere="cold_atmosphere",
                hero_categories=["robot", "machinery", "electronic"],
                fog_density="light",
                review_threshold=0.70,
                tags=["robotics", "lab", "scifi", "precision"],
            ),
            _make_pack(
                "control_room_pack", "control_room",
                lighting="warm_control_room",
                camera="hero_focus",
                atmosphere="volumetric_scifi",
                hero_categories=["electronic", "prop", "robot"],
                fog_density="none",
                review_threshold=0.68,
                tags=["control-room", "command", "cinematic"],
            ),
            _make_pack(
                "sci_fi_corridor_pack", "sci_fi_corridor",
                lighting="bladerunner_noir",
                camera="atmospheric_tracking",
                atmosphere="dusty_hangar",
                hero_categories=["electronic", "prop", "robot", "character"],
                fog_density="light",
                review_threshold=0.68,
                tags=["scifi", "corridor", "noir", "atmospheric"],
            ),
            _make_pack(
                "abandoned_factory_pack", "abandoned_factory",
                lighting="atmospheric_lab",
                camera="handheld_subtle",
                atmosphere="industrial_fog",
                hero_categories=["machinery", "vehicle", "structure"],
                fog_density="heavy",
                review_threshold=0.65,
                tags=["abandoned", "factory", "post-apocalyptic", "atmospheric"],
            ),
            # -------------------------------------------------------------------
            # §39 New packs
            # -------------------------------------------------------------------
            _make_pack(
                "western_room_pack", "western_room",
                lighting="warm_lantern",
                camera="hero_focus",
                atmosphere="warm_dusty",
                hero_categories=["furniture", "prop", "vehicle"],
                fog_density="none",
                review_threshold=0.65,
                tags=["western", "interior", "warm", "period", "frontier"],
            ),
            _make_pack(
                "space_station_pack", "space_station",
                lighting="cold_scifi",
                camera="orbital_reveal",
                atmosphere="cold_atmosphere",
                hero_categories=["electronics", "equipment", "prop"],
                fog_density="none",
                review_threshold=0.70,
                tags=["space", "orbital", "sci-fi", "isolation", "cool"],
            ),
            _make_pack(
                "research_lab_pack", "research_lab",
                lighting="cold_scifi",
                camera="orbital_reveal",
                atmosphere="cold_atmosphere",
                hero_categories=["equipment", "furniture", "electronics"],
                fog_density="light",
                review_threshold=0.70,
                tags=["research", "lab", "scientific", "clean", "clinical"],
            ),
            _make_pack(
                "forest_pack", "forest",
                lighting="natural_forest",
                camera="atmospheric_tracking",
                atmosphere="forest_mist",
                hero_categories=["vegetation", "terrain", "prop"],
                fog_density="medium",
                review_threshold=0.65,
                tags=["forest", "nature", "natural", "dappled", "organic"],
            ),
            _make_pack(
                "city_street_pack", "city_street",
                lighting="urban_golden_hour",
                camera="cinematic_push_in",
                atmosphere="city_smog",
                hero_categories=["vehicle", "architecture", "prop"],
                fog_density="light",
                review_threshold=0.65,
                tags=["city", "urban", "street", "traffic", "modern"],
            ),
            _make_pack(
                "castle_hall_pack", "castle_hall",
                lighting="torch_warm",
                camera="hero_focus",
                atmosphere="medieval_smoke",
                hero_categories=["furniture", "architecture", "prop"],
                fog_density="none",
                review_threshold=0.65,
                tags=["castle", "medieval", "fantasy", "royal", "torch"],
            ),
            _make_pack(
                "military_base_pack", "military_base",
                lighting="harsh_exterior",
                camera="handheld_subtle",
                atmosphere="desert_dust",
                hero_categories=["vehicle", "structure", "equipment"],
                fog_density="light",
                review_threshold=0.68,
                tags=["military", "tactical", "exterior", "harsh", "operational"],
            ),
            _make_pack(
                "survival_camp_pack", "survival_camp",
                lighting="campfire_warm",
                camera="hero_focus",
                atmosphere="campfire_smoke",
                hero_categories=["prop", "structure", "vehicle"],
                fog_density="medium",
                review_threshold=0.62,
                tags=["survival", "post-apocalyptic", "camp", "hope", "makeshift"],
            ),
        ]
    return list(_BUILTIN_PACKS)


def reset_workflow_pack_for_tests() -> None:
    """Reset mutable module state for test isolation."""
    global _BUILTIN_PACKS
    _BUILTIN_PACKS = None
