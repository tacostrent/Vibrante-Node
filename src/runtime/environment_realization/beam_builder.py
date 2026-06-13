"""
beam_builder.py — §49 Structural Environment Realization
=========================================================
Generates structural beams, columns, and support elements.

Beam types by environment:
  wooden_beam     western_room, saloon, warehouse, workshop
  steel_girder    industrial_hangar, shipyard, oil_refinery
  panel_rib       sci_fi_corridor, space_station
  stone_arch      castle_hall, dungeon, temple
  concrete_column robotics_lab, control_room, parking_garage
  support_column  office, hotel_lobby
  none            outdoor environments, simple rooms

Configuration per environment:
  western_room:     4 wooden ceiling beams (east-west across room width)
  saloon:           6 wooden beams + 2 support columns
  industrial_hangar: 8 steel girders + 6 columns
  sci_fi_corridor:  8 panel ribs at regular intervals
  castle_hall:      4 stone arches + 8 columns
  warehouse:        6 steel beams + 4 columns

Public API:
    BeamBuilder
    get_beam_builder()
    reset_beam_builder_for_tests()
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from src.runtime.environment_realization.structural_elements import StructuralElement


@dataclass
class BeamConfig:
    beam_type:   str
    beam_count:  int
    col_count:   int
    material:    str
    beam_section: Dict  # cross-section dimensions (width, height)
    col_section:  Dict  # column cross-section


_ENV_BEAMS: Dict[str, BeamConfig] = {
    "western_room": BeamConfig(
        "wooden_beam", 4, 0, "wood",
        {"width": 0.20, "height": 0.30}, {}),
    "saloon": BeamConfig(
        "wooden_beam", 6, 2, "wood",
        {"width": 0.20, "height": 0.30},
        {"width": 0.20, "depth": 0.20}),
    "warehouse": BeamConfig(
        "steel_girder", 6, 4, "industrial_metal",
        {"width": 0.30, "height": 0.40},
        {"width": 0.30, "depth": 0.30}),
    "industrial_hangar": BeamConfig(
        "steel_girder", 8, 6, "industrial_metal",
        {"width": 0.50, "height": 0.60},
        {"width": 0.40, "depth": 0.40}),
    "abandoned_factory": BeamConfig(
        "steel_girder", 4, 4, "industrial_metal",
        {"width": 0.40, "height": 0.50},
        {"width": 0.30, "depth": 0.30}),
    "sci_fi_corridor": BeamConfig(
        "panel_rib", 8, 0, "sci_fi_panel",
        {"width": 0.10, "height": 0.30}, {}),
    "space_station": BeamConfig(
        "panel_rib", 6, 4, "sci_fi_panel",
        {"width": 0.15, "height": 0.40},
        {"width": 0.20, "depth": 0.20}),
    "castle_hall": BeamConfig(
        "stone_arch", 4, 8, "stone",
        {"width": 0.60, "height": 0.80},
        {"width": 0.50, "depth": 0.50}),
    "dungeon": BeamConfig(
        "stone_arch", 2, 4, "stone",
        {"width": 0.40, "height": 0.60},
        {"width": 0.40, "depth": 0.40}),
    "robotics_lab": BeamConfig(
        "concrete_column", 0, 4, "concrete",
        {},
        {"width": 0.30, "depth": 0.30}),
    "control_room": BeamConfig(
        "concrete_column", 0, 0, "concrete",
        {}, {}),
    "hotel_lobby": BeamConfig(
        "support_column", 0, 6, "marble",
        {},
        {"width": 0.40, "depth": 0.40}),
    "library": BeamConfig(
        "wooden_beam", 4, 0, "wood",
        {"width": 0.20, "height": 0.25}, {}),
    "shipyard": BeamConfig(
        "steel_girder", 10, 8, "industrial_metal",
        {"width": 0.60, "height": 0.80},
        {"width": 0.50, "depth": 0.50}),
}
_NO_BEAM_ENVS = frozenset({
    "forest", "jungle", "desert", "canyon", "mountain", "coastline", "swamp",
    "city_street", "alleyway", "rooftop", "survival_camp",
    "abandoned_city", "destroyed_highway",
    "office", "living_room", "restaurant", "medical_lab", "clean_room",
    "research_lab", "biohazard_facility",
})
_DEFAULT_CONFIG = BeamConfig("wooden_beam", 2, 0, "wood", {"width": 0.20, "height": 0.25}, {})


class BeamBuilder:
    """Generates beam and column elements for an environment."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def build_beams(
        self,
        environment: str,
        width: float,
        height: float,
        depth: float,
    ) -> Tuple[List[StructuralElement], List[StructuralElement]]:
        """
        Build beams and columns for the environment.

        Returns:
            (beams, columns) — both may be empty lists.
        Never raises.
        """
        try:
            return self._build(environment.lower(), width, height, depth)
        except Exception:
            return [], []

    def _build(
        self,
        env: str,
        width: float,
        height: float,
        depth: float,
    ) -> Tuple[List[StructuralElement], List[StructuralElement]]:
        if env in _NO_BEAM_ENVS:
            return [], []

        cfg = _ENV_BEAMS.get(env, _DEFAULT_CONFIG)
        beams: List[StructuralElement] = []
        columns: List[StructuralElement] = []

        # Build beams (horizontal, spanning east-west at ceiling level)
        if cfg.beam_count > 0 and cfg.beam_section:
            beam_spacing = depth / (cfg.beam_count + 1)
            for i in range(cfg.beam_count):
                z_pos = -depth / 2.0 + beam_spacing * (i + 1)
                beams.append(StructuralElement(
                    element_id=f"beam_{i+1:02d}_{env}",
                    element_type="beam",
                    environment=env,
                    position=[0.0, height - cfg.beam_section.get("height", 0.3) / 2.0, z_pos],
                    dimensions={
                        "length":    width,
                        "width":     cfg.beam_section.get("width", 0.20),
                        "height":    cfg.beam_section.get("height", 0.30),
                    },
                    rotation=[0.0, 90.0, 0.0],
                    material=cfg.material,
                    is_structural=True,
                    metadata={"beam_type": cfg.beam_type, "index": i + 1},
                ))

        # Build columns (vertical, at room corners or regular intervals)
        if cfg.col_count > 0 and cfg.col_section:
            col_spacing = depth / (cfg.col_count // 2 + 1) if cfg.col_count >= 2 else depth / 2.0
            hw = width / 2.0 - 0.3
            col_pairs = cfg.col_count // 2
            for i in range(col_pairs):
                z_pos = -depth / 2.0 + col_spacing * (i + 1)
                for side, x_pos in [("east", hw), ("west", -hw)]:
                    columns.append(StructuralElement(
                        element_id=f"col_{side}_{i+1:02d}_{env}",
                        element_type="column",
                        environment=env,
                        position=[x_pos, height / 2.0, z_pos],
                        dimensions={
                            "width":  cfg.col_section.get("width", 0.30),
                            "height": height,
                            "depth":  cfg.col_section.get("depth", 0.30),
                        },
                        material=cfg.material,
                        is_structural=True,
                        metadata={"index": i + 1, "side": side},
                    ))

        return beams, columns

    def get_beam_config(self, environment: str) -> BeamConfig:
        return _ENV_BEAMS.get(environment.lower(), _DEFAULT_CONFIG)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[BeamBuilder] = None
_lock = threading.Lock()


def get_beam_builder() -> BeamBuilder:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = BeamBuilder()
    return _instance


def reset_beam_builder_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
