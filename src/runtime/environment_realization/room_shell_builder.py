"""
room_shell_builder.py — §49 Structural Environment Realization
==============================================================
Generates the complete RoomShell for an environment by orchestrating
floor, ceiling, wall, opening, and beam builders.

Environment dimensions lookup (width × height × depth in meters):
  Based on production standards — enough space for hero assets,
  natural camera framing, and crowd/traffic flow.

Public API:
    RoomShellBuilder
    get_room_shell_builder()
    reset_room_shell_builder_for_tests()
"""

from __future__ import annotations

import threading
from typing import Any, Dict, Optional, Tuple

from src.runtime.environment_realization.structural_elements import RoomShell
from src.runtime.environment_realization.floor_builder import get_floor_builder
from src.runtime.environment_realization.ceiling_builder import get_ceiling_builder
from src.runtime.environment_realization.wall_builder import get_wall_builder
from src.runtime.environment_realization.opening_builder import get_opening_builder
from src.runtime.environment_realization.beam_builder import get_beam_builder


# (width_m, height_m, depth_m, primary_material)
_ENV_DIMENSIONS: Dict[str, Tuple[float, float, float, str]] = {
    # Interior – western
    "western_room":      (10.0,  4.0,  12.0, "wood"),
    "saloon":            (14.0,  4.5,  18.0, "wood"),
    # Interior – residential
    "living_room":       ( 8.0,  3.0,  10.0, "plaster"),
    "restaurant":        (15.0,  3.5,  18.0, "wood"),
    "library":           (12.0,  5.0,  15.0, "wood"),
    "hotel_lobby":       (20.0,  6.0,  25.0, "marble"),
    "office":            (10.0,  3.0,  12.0, "drywall"),
    "workshop":          ( 8.0,  3.5,  10.0, "wood"),
    # Industrial
    "warehouse":         (20.0,  8.0,  30.0, "concrete"),
    "industrial_hangar": (30.0, 12.0,  40.0, "industrial_metal"),
    "abandoned_factory": (25.0, 10.0,  35.0, "concrete"),
    "shipyard":          (40.0, 15.0,  60.0, "industrial_metal"),
    "oil_refinery":      (20.0, 10.0,  25.0, "industrial_metal"),
    "power_station":     (15.0,  8.0,  20.0, "concrete"),
    "mining_facility":   (15.0,  6.0,  20.0, "concrete"),
    "construction_site": ( 0.0,  0.0,   0.0, "concrete"),  # outdoor
    # Scientific
    "robotics_lab":      (15.0,  3.5,  20.0, "concrete"),
    "control_room":      (12.0,  3.0,  15.0, "concrete"),
    "medical_lab":       (10.0,  3.0,  12.0, "tile"),
    "clean_room":        (10.0,  3.0,  12.0, "tile"),
    "biohazard_facility":(12.0,  3.0,  15.0, "concrete"),
    "research_lab":      (15.0,  3.5,  18.0, "concrete"),
    # Military
    "military_base":     ( 0.0,  0.0,   0.0, "concrete"),  # outdoor compound
    "command_center":    (12.0,  3.0,  15.0, "concrete"),
    "military_hangar":   (25.0, 10.0,  35.0, "industrial_metal"),
    "checkpoint":        ( 6.0,  3.0,   8.0, "concrete"),
    "bunker":            (15.0,  3.0,  20.0, "concrete"),
    # Sci-Fi
    "sci_fi_corridor":   ( 4.0,  3.0,  20.0, "sci_fi_panel"),
    "space_station":     (20.0,  5.0,  30.0, "sci_fi_panel"),
    "spaceship_bridge":  (15.0,  4.0,  20.0, "sci_fi_panel"),
    "engineering_bay":   (12.0,  4.0,  18.0, "sci_fi_panel"),
    "alien_facility":    (18.0,  6.0,  25.0, "stone"),
    "cyberpunk_city":    ( 0.0,  0.0,   0.0, "concrete"),  # outdoor
    # Urban
    "city_street":       ( 0.0,  0.0,   0.0, "concrete"),  # outdoor
    "alleyway":          ( 0.0,  0.0,   0.0, "brick"),      # outdoor
    "subway_station":    (15.0,  4.0,  30.0, "concrete"),
    "parking_garage":    (20.0,  3.5,  40.0, "concrete"),
    "rooftop":           ( 0.0,  0.0,   0.0, "concrete"),  # outdoor
    "shopping_mall":     (30.0,  6.0,  50.0, "marble"),
    # Fantasy
    "castle_hall":       (20.0, 10.0,  30.0, "stone"),
    "dungeon":           ( 8.0,  3.0,  10.0, "stone"),
    "wizard_tower":      ( 8.0, 12.0,   8.0, "stone"),
    "ancient_ruins":     (15.0,  5.0,  20.0, "stone"),
    "temple":            (15.0,  8.0,  20.0, "stone"),
    # Nature
    "forest":            ( 0.0,  0.0,   0.0, "dirt"),
    "jungle":            ( 0.0,  0.0,   0.0, "dirt"),
    "desert":            ( 0.0,  0.0,   0.0, "sand"),
    "canyon":            ( 0.0,  0.0,   0.0, "stone"),
    "mountain":          ( 0.0,  0.0,   0.0, "stone"),
    "coastline":         ( 0.0,  0.0,   0.0, "sand"),
    "swamp":             ( 0.0,  0.0,   0.0, "dirt"),
    # Post-Apocalyptic
    "abandoned_city":    ( 0.0,  0.0,   0.0, "cracked_concrete"),
    "destroyed_highway": ( 0.0,  0.0,   0.0, "cracked_concrete"),
    "ruined_industrial_site": (20.0, 8.0, 30.0, "cracked_concrete"),
    "survival_camp":     ( 0.0,  0.0,   0.0, "dirt"),
}
_DEFAULT_DIM = (10.0, 4.0, 12.0, "concrete")
_OUTDOOR_ZERO = frozenset({
    e for e, (w, h, d, _) in _ENV_DIMENSIONS.items() if w == 0.0
})


class RoomShellBuilder:
    """
    Builds a complete RoomShell by orchestrating all sub-builders.

    Usage:
        shell = get_room_shell_builder().build("western_room")
        # shell.floor, shell.walls, shell.openings, shell.beams, shell.room_closed
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def build(
        self,
        environment: str,
        override_dims: Optional[Tuple[float, float, float]] = None,
    ) -> RoomShell:
        """
        Build the complete architectural shell for an environment.

        Args:
            environment:   environment name
            override_dims: optional (width, height, depth) override in meters

        Returns: RoomShell. Never raises.
        """
        try:
            return self._build(environment, override_dims)
        except Exception as exc:
            return RoomShell(
                environment=environment,
                ok=False,
                errors=[f"RoomShellBuilder.build failed: {exc}"],
            )

    def _build(
        self,
        environment: str,
        override_dims: Optional[Tuple[float, float, float]],
    ) -> RoomShell:
        env = environment.lower()
        dim_entry = _ENV_DIMENSIONS.get(env, _DEFAULT_DIM)
        dw, dh, dd, primary_mat = dim_entry

        if override_dims:
            width, height, depth = override_dims
        else:
            width, height, depth = dw, dh, dd

        is_outdoor = env in _OUTDOOR_ZERO

        shell = RoomShell(
            environment=env,
            width=width,
            height=height,
            depth=depth,
            primary_material=primary_mat,
            is_outdoor=is_outdoor,
        )

        # Floor (always built — outdoor gets large ground plane)
        shell.floor = get_floor_builder().build_floor(env, width or 50.0, depth or 50.0)

        # Ceiling (None for outdoor)
        shell.ceiling = get_ceiling_builder().build_ceiling(env, width, depth, height)

        # Walls (empty for outdoor)
        shell.walls = {} if is_outdoor else get_wall_builder().build_walls(env, width, height, depth)

        # Openings (doors, windows, etc.)
        shell.openings = get_opening_builder().build_openings(env, shell.walls)

        # Beams and columns
        beams, cols = get_beam_builder().build_beams(env, width, height, depth)
        shell.beams   = beams
        shell.columns = cols

        # Room closure check
        has_floor   = shell.floor is not None
        has_ceiling = shell.ceiling is not None or is_outdoor
        has_walls   = len(shell.walls) == 4 or is_outdoor
        shell.room_closed = has_floor and has_ceiling and has_walls

        return shell

    def get_dimensions(self, environment: str) -> Tuple[float, float, float]:
        """Return (width, height, depth) for an environment."""
        w, h, d, _ = _ENV_DIMENSIONS.get(environment.lower(), _DEFAULT_DIM)
        return w, h, d


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[RoomShellBuilder] = None
_lock = threading.Lock()


def get_room_shell_builder() -> RoomShellBuilder:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = RoomShellBuilder()
    return _instance


def reset_room_shell_builder_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
