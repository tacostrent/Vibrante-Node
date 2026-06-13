"""
Room Shell Completeness Validator (Tier 10.3.5)
================================================
Validates that an EnvironmentRealizationPlan contains the minimum required
structural elements before scene commit.

Requirements are per environment type:
  western_room:      floor >= 1, wall >= 4, ceiling >= 1, door >= 1
  industrial_hangar: floor >= 1, wall >= 4, ceiling >= 1, door >= 1
  forest (outdoor):  floor >= 1, wall >= 0, ceiling >= 0, door >= 0

Blocking findings (production_ready = False):
  "ROOM_SHELL_INCOMPLETE: floor missing"   — floor_count < min_floor
  "ROOM_SHELL_INCOMPLETE: wall missing"    — wall_count  < min_wall
  "ROOM_SHELL_INCOMPLETE: ceiling missing" — ceiling_count < min_ceiling
  "ROOM_SHELL_INCOMPLETE: door missing"    — door_count < min_door

Design rules:
  - No bridge calls. Planning only.
  - Deterministic.
  - Never raises.
  - Singleton pattern.

Public API:
    ShellRequirements
    CompletenessValidationResult
    RoomShellCompletenessValidator
    get_room_shell_completeness_validator()
    reset_room_shell_completeness_validator_for_tests()
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ── Requirements tables ────────────────────────────────────────────────────────

@dataclass
class ShellRequirements:
    """Minimum element counts required for a production-ready room shell."""
    environment: str   = ""
    min_floor:   int   = 1
    min_wall:    int   = 4
    min_ceiling: int   = 1
    min_door:    int   = 1
    min_window:  int   = 0


# Per-environment requirements. Outdoor envs have no wall/ceiling/door requirement.
_REQUIREMENTS: Dict[str, ShellRequirements] = {
    # Interior – western
    "western_room":      ShellRequirements("western_room",   1, 4, 1, 1, 0),
    "saloon":            ShellRequirements("saloon",         1, 4, 1, 1, 1),
    # Interior – residential
    "living_room":       ShellRequirements("living_room",    1, 4, 1, 1, 1),
    "restaurant":        ShellRequirements("restaurant",     1, 4, 1, 1, 1),
    "library":           ShellRequirements("library",        1, 4, 1, 1, 1),
    "hotel_lobby":       ShellRequirements("hotel_lobby",    1, 4, 1, 2, 2),
    "office":            ShellRequirements("office",         1, 4, 1, 1, 2),
    "workshop":          ShellRequirements("workshop",       1, 4, 1, 1, 0),
    # Industrial
    "warehouse":         ShellRequirements("warehouse",      1, 4, 1, 1, 0),
    "industrial_hangar": ShellRequirements("industrial_hangar", 1, 4, 1, 1, 0),
    "abandoned_factory": ShellRequirements("abandoned_factory", 1, 4, 1, 1, 0),
    "shipyard":          ShellRequirements("shipyard",       1, 4, 1, 1, 0),
    "oil_refinery":      ShellRequirements("oil_refinery",   1, 4, 1, 1, 0),
    "power_station":     ShellRequirements("power_station",  1, 4, 1, 1, 0),
    "mining_facility":   ShellRequirements("mining_facility",1, 4, 1, 1, 0),
    "construction_site": ShellRequirements("construction_site", 1, 0, 0, 0, 0),
    # Scientific
    "robotics_lab":      ShellRequirements("robotics_lab",   1, 4, 1, 1, 1),
    "control_room":      ShellRequirements("control_room",   1, 4, 1, 1, 1),
    "medical_lab":       ShellRequirements("medical_lab",    1, 4, 1, 1, 1),
    "clean_room":        ShellRequirements("clean_room",     1, 4, 1, 1, 0),
    "biohazard_facility":ShellRequirements("biohazard_facility", 1, 4, 1, 2, 0),
    "research_lab":      ShellRequirements("research_lab",   1, 4, 1, 1, 1),
    # Military
    "military_base":     ShellRequirements("military_base",  1, 4, 1, 1, 0),
    "command_center":    ShellRequirements("command_center", 1, 4, 1, 1, 0),
    "military_hangar":   ShellRequirements("military_hangar",1, 4, 1, 1, 0),
    "checkpoint":        ShellRequirements("checkpoint",     1, 0, 0, 0, 0),
    "bunker":            ShellRequirements("bunker",         1, 4, 1, 1, 0),
    # Sci-Fi
    "sci_fi_corridor":   ShellRequirements("sci_fi_corridor",1, 4, 1, 2, 0),
    "space_station":     ShellRequirements("space_station",  1, 4, 1, 1, 0),
    "spaceship_bridge":  ShellRequirements("spaceship_bridge",1, 4, 1, 1, 1),
    "engineering_bay":   ShellRequirements("engineering_bay",1, 4, 1, 1, 0),
    "alien_facility":    ShellRequirements("alien_facility", 1, 4, 1, 1, 0),
    # Urban (semi-outdoor)
    "cyberpunk_city":    ShellRequirements("cyberpunk_city", 1, 0, 0, 0, 0),
    "city_street":       ShellRequirements("city_street",    1, 0, 0, 0, 0),
    "alleyway":          ShellRequirements("alleyway",       1, 0, 0, 0, 0),
    "subway_station":    ShellRequirements("subway_station", 1, 4, 1, 1, 0),
    "parking_garage":    ShellRequirements("parking_garage", 1, 4, 1, 1, 0),
    "rooftop":           ShellRequirements("rooftop",        1, 0, 0, 0, 0),
    "shopping_mall":     ShellRequirements("shopping_mall",  1, 4, 1, 2, 4),
    # Fantasy
    "castle_hall":       ShellRequirements("castle_hall",    1, 4, 1, 1, 2),
    "dungeon":           ShellRequirements("dungeon",        1, 4, 1, 1, 0),
    "wizard_tower":      ShellRequirements("wizard_tower",   1, 4, 1, 1, 0),
    "ancient_ruins":     ShellRequirements("ancient_ruins",  1, 0, 0, 0, 0),
    "temple":            ShellRequirements("temple",         1, 4, 1, 1, 0),
    # Post-Apocalyptic
    "abandoned_city":    ShellRequirements("abandoned_city", 1, 0, 0, 0, 0),
    "destroyed_highway": ShellRequirements("destroyed_highway", 1, 0, 0, 0, 0),
    "ruined_industrial_site": ShellRequirements("ruined_industrial_site", 1, 0, 0, 0, 0),
    "survival_camp":     ShellRequirements("survival_camp",  1, 0, 0, 0, 0),
    # Nature (fully outdoor)
    "forest":            ShellRequirements("forest",         1, 0, 0, 0, 0),
    "jungle":            ShellRequirements("jungle",         1, 0, 0, 0, 0),
    "desert":            ShellRequirements("desert",         1, 0, 0, 0, 0),
    "canyon":            ShellRequirements("canyon",         1, 0, 0, 0, 0),
    "mountain":          ShellRequirements("mountain",       1, 0, 0, 0, 0),
    "coastline":         ShellRequirements("coastline",      1, 0, 0, 0, 0),
    "swamp":             ShellRequirements("swamp",          1, 0, 0, 0, 0),
}

_DEFAULT_REQUIREMENTS = ShellRequirements(min_floor=1, min_wall=4, min_ceiling=1, min_door=1)


# ── Result type ────────────────────────────────────────────────────────────────

@dataclass
class CompletenessValidationResult:
    """Completeness check result for one EnvironmentRealizationPlan."""

    validation_id:   str       = field(default_factory=lambda: f"cv_{uuid.uuid4().hex[:10]}")
    environment:     str       = ""

    # Actual counts (from plan)
    floor_count:     int       = 0
    wall_count:      int       = 0
    ceiling_count:   int       = 0
    door_count:      int       = 0
    window_count:    int       = 0

    # Required minimums
    min_floor:       int       = 1
    min_wall:        int       = 4
    min_ceiling:     int       = 1
    min_door:        int       = 1
    min_window:      int       = 0

    # Per-element pass/fail
    floor_ok:        bool      = False
    wall_ok:         bool      = False
    ceiling_ok:      bool      = False
    door_ok:         bool      = False
    window_ok:       bool      = False

    production_ready: bool     = False
    findings:        List[str] = field(default_factory=list)
    validated_at:    float     = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "validation_id":   self.validation_id,
            "environment":     self.environment,
            "floor_count":     self.floor_count,
            "wall_count":      self.wall_count,
            "ceiling_count":   self.ceiling_count,
            "door_count":      self.door_count,
            "window_count":    self.window_count,
            "min_floor":       self.min_floor,
            "min_wall":        self.min_wall,
            "min_ceiling":     self.min_ceiling,
            "min_door":        self.min_door,
            "min_window":      self.min_window,
            "floor_ok":        self.floor_ok,
            "wall_ok":         self.wall_ok,
            "ceiling_ok":      self.ceiling_ok,
            "door_ok":         self.door_ok,
            "window_ok":       self.window_ok,
            "production_ready":self.production_ready,
            "findings":        list(self.findings),
            "validated_at":    self.validated_at,
        }


# ── Validator ──────────────────────────────────────────────────────────────────

class RoomShellCompletenessValidator:
    """
    Validates minimum structural element counts for an environment.

    Usage:
        validator = get_room_shell_completeness_validator()
        result = validator.validate_from_dict(plan.to_dict())
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def validate(self, plan: Any) -> CompletenessValidationResult:
        """
        Validate an EnvironmentRealizationPlan object.
        Accepts the plan object directly (with to_dict()) or any object with
        floor_count / wall_count / ceiling_count / door_count / window_count fields.
        Never raises.
        """
        try:
            if hasattr(plan, "to_dict"):
                return self.validate_from_dict(plan.to_dict())
            return self.validate_from_dict(dict(plan))
        except Exception as exc:
            r = CompletenessValidationResult()
            r.findings.append(f"RoomShellCompletenessValidator.validate error: {exc}")
            return r

    def validate_from_dict(self, plan_dict: Dict[str, Any]) -> CompletenessValidationResult:
        """
        Validate from an EnvironmentRealizationPlan dict.
        Never raises.
        """
        try:
            return self._validate(plan_dict)
        except Exception as exc:
            r = CompletenessValidationResult()
            r.findings.append(f"RoomShellCompletenessValidator error: {exc}")
            return r

    def get_requirements(self, environment: str) -> ShellRequirements:
        """Return the minimum requirements for an environment. Never raises."""
        return _REQUIREMENTS.get(environment.lower(), _DEFAULT_REQUIREMENTS)

    def _validate(self, plan_dict: Dict[str, Any]) -> CompletenessValidationResult:
        env = str(plan_dict.get("environment", "")).lower()
        req = _REQUIREMENTS.get(env, _DEFAULT_REQUIREMENTS)

        r = CompletenessValidationResult(environment=env)
        r.min_floor   = req.min_floor
        r.min_wall    = req.min_wall
        r.min_ceiling = req.min_ceiling
        r.min_door    = req.min_door
        r.min_window  = req.min_window

        # Read counts from plan dict
        r.floor_count   = int(plan_dict.get("floor_count",   0))
        r.wall_count    = int(plan_dict.get("wall_count",    0))
        r.ceiling_count = int(plan_dict.get("ceiling_count", 0))
        r.door_count    = int(plan_dict.get("door_count",    0))
        r.window_count  = int(plan_dict.get("window_count",  0))

        # Evaluate each requirement
        r.floor_ok   = r.floor_count   >= req.min_floor
        r.wall_ok    = r.wall_count    >= req.min_wall
        r.ceiling_ok = r.ceiling_count >= req.min_ceiling
        r.door_ok    = r.door_count    >= req.min_door
        r.window_ok  = r.window_count  >= req.min_window

        # Generate blocking findings
        if not r.floor_ok:
            r.findings.append(
                f"ROOM_SHELL_INCOMPLETE: floor missing — "
                f"found {r.floor_count}, need {req.min_floor} for '{env}'."
            )
        if not r.wall_ok:
            r.findings.append(
                f"ROOM_SHELL_INCOMPLETE: wall missing — "
                f"found {r.wall_count}, need {req.min_wall} for '{env}'."
            )
        if not r.ceiling_ok:
            r.findings.append(
                f"ROOM_SHELL_INCOMPLETE: ceiling missing — "
                f"found {r.ceiling_count}, need {req.min_ceiling} for '{env}'."
            )
        if not r.door_ok:
            r.findings.append(
                f"ROOM_SHELL_INCOMPLETE: door missing — "
                f"found {r.door_count}, need {req.min_door} for '{env}'."
            )
        if req.min_window > 0 and not r.window_ok:
            r.findings.append(
                f"ROOM_SHELL_INCOMPLETE: window missing — "
                f"found {r.window_count}, need {req.min_window} for '{env}'."
            )

        r.production_ready = not r.findings
        return r


# ── Singleton ──────────────────────────────────────────────────────────────────

_INSTANCE: Optional[RoomShellCompletenessValidator] = None
_LOCK = threading.Lock()


def get_room_shell_completeness_validator() -> RoomShellCompletenessValidator:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = RoomShellCompletenessValidator()
        return _INSTANCE


def reset_room_shell_completeness_validator_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
