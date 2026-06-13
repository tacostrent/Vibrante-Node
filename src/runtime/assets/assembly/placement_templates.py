"""
Placement Templates (Tier 9 — Semantic Asset Assembly)
========================================================
Deterministic placement rules for the 5 canonical Vibrante environments.

Each template defines:
  - zone names and their world-space depth
  - asset slot positions (deterministic arithmetic, never random)
  - category preferences per zone
  - facing directions and rotation conventions
  - cluster formation rules

DESIGN RULES:
  1. All positions are literal floats — no noise, no RNG.
  2. Templates are immutable after registration — copy on use.
  3. Built-in templates cannot be deregistered.
  4. Custom templates must include all _REQUIRED_FIELDS.
  5. No bridge calls.  No Houdini imports.  Pure data.

Public API:
    PlacementTemplates
    get_placement_templates()
    reset_placement_templates_for_tests()
"""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional, Tuple

_REQUIRED_FIELDS = frozenset({
    "hero_zone", "midground", "background",
    "zone_depths", "zone_widths",
})

# ---------------------------------------------------------------------------
# Built-in templates
# ---------------------------------------------------------------------------

_BUILTIN_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "industrial_hangar": {
        # World-space depth per zone (negative Z = away from camera)
        "zone_depths": {
            "hero_zone":    0.0,
            "midground":   -12.0,
            "background":  -28.0,
            "service_area": -6.0,
            "ceiling_edge": 5.0,
        },
        # X-spread width per zone
        "zone_widths": {
            "hero_zone":    12.0,
            "midground":    22.0,
            "background":   30.0,
            "service_area": 18.0,
        },
        # Hero zone — center stage, camera-facing
        "hero_zone": {
            "max_assets":   3,
            "categories":   ["machinery", "vehicle", "robot"],
            "facing":       "camera",
            "y_offset":     0.0,
            # Fixed slot offsets for 1/2/3 assets (symmetric)
            "slots": {
                1: [(0.0,   0.0, 0.0)],
                2: [(-4.0,  0.0, 0.0), (4.0,  0.0, 0.0)],
                3: [(-5.5,  0.0, 0.5), (0.0,  0.0, 0.0), (5.5, 0.0, 0.5)],
            },
            "rotation_y_per_slot": {
                1: [0.0],
                2: [15.0, -15.0],
                3: [20.0, 0.0, -20.0],
            },
        },
        # Midground — flanking support
        "midground": {
            "max_assets":   5,
            "categories":   ["structure", "prop", "electronic", "machinery"],
            "facing":       "inward",
            "y_offset":     0.0,
            "slots": [
                (-9.0,  0.0, -10.0),
                ( 9.0,  0.0, -10.0),
                (-14.0, 0.0, -14.0),
                ( 14.0, 0.0, -14.0),
                ( 0.0,  0.0, -18.0),
            ],
            "rotation_y_base": 30.0,  # inward angle
        },
        # Background — depth, atmosphere
        "background": {
            "max_assets":   5,
            "categories":   ["structure", "architectural", "terrain"],
            "facing":       "forward",
            "y_offset":     0.0,
            "slots": [
                (-14.0, 0.0, -25.0),
                ( -7.0, 0.0, -28.0),
                (  0.0, 0.0, -32.0),
                (  7.0, 0.0, -28.0),
                ( 14.0, 0.0, -25.0),
            ],
            "rotation_y_base": 0.0,
        },
        # Service area — side pathways
        "service_area": {
            "max_assets":   4,
            "categories":   ["prop", "electronic", "robot"],
            "facing":       "outward",
            "y_offset":     0.0,
            "slots": [
                (-12.0, 0.0, -4.0),
                (-12.0, 0.0, -9.0),
                ( 12.0, 0.0, -4.0),
                ( 12.0, 0.0, -9.0),
            ],
            "rotation_y_base": 90.0,
        },
        # Pipe/wall run slots — along side walls
        "wall_run_left":  [(-16.0, 1.5, z) for z in (-2.0, -6.0, -10.0, -14.0, -18.0)],
        "wall_run_right": [( 16.0, 1.5, z) for z in (-2.0, -6.0, -10.0, -14.0, -18.0)],
        # Cluster formation rules
        "cluster_rules": {
            "machinery_cluster": {"radius": 3.0, "max_members": 3},
            "pipe_cluster":      {"radius": 2.0, "max_members": 5, "linear": True},
            "workstation_cluster": {"radius": 2.5, "max_members": 3},
        },
        # Storytelling narrative
        "narrative": {
            "theme":       "industrial operation",
            "hero_beat":   "central machinery in active use",
            "support_beat": "surrounding equipment contextualizes scale",
            "atmosphere_beat": "fog depth creates industrial mood",
        },
    },

    "robotics_lab": {
        "zone_depths": {
            "hero_zone":   0.0,
            "midground":  -10.0,
            "background": -22.0,
            "workstation_row": -5.0,
        },
        "zone_widths": {
            "hero_zone":    8.0,
            "midground":   18.0,
            "background":  24.0,
            "workstation_row": 20.0,
        },
        "hero_zone": {
            "max_assets":   2,
            "categories":   ["robot", "machinery", "electronic"],
            "facing":       "camera",
            "y_offset":     0.0,
            "slots": {
                1: [(0.0,  0.0, 0.0)],
                2: [(-3.5, 0.0, 0.0), (3.5, 0.0, 0.0)],
                3: [(-4.0, 0.0, 0.5), (0.0, 0.0, 0.0), (4.0, 0.0, 0.5)],
            },
            "rotation_y_per_slot": {
                1: [0.0],
                2: [10.0, -10.0],
                3: [15.0, 0.0, -15.0],
            },
        },
        "midground": {
            "max_assets":   6,
            "categories":   ["electronic", "prop", "furniture"],
            "facing":       "inward",
            "y_offset":     0.0,
            "slots": [
                (-7.0,  0.0,  -8.0),
                ( 7.0,  0.0,  -8.0),
                (-11.0, 0.0, -11.0),
                ( 11.0, 0.0, -11.0),
                ( -4.0, 0.0, -14.0),
                (  4.0, 0.0, -14.0),
            ],
            "rotation_y_base": 20.0,
        },
        "background": {
            "max_assets":   4,
            "categories":   ["structure", "electronic", "architectural"],
            "facing":       "forward",
            "y_offset":     0.0,
            "slots": [
                (-10.0, 0.0, -19.0),
                ( -4.0, 0.0, -22.0),
                (  4.0, 0.0, -22.0),
                ( 10.0, 0.0, -19.0),
            ],
            "rotation_y_base": 0.0,
        },
        "workstation_row": {
            "max_assets":   4,
            "categories":   ["electronic", "furniture", "prop"],
            "facing":       "camera",
            "y_offset":     0.0,
            "slots": [
                (-8.0,  0.0, -4.0),
                (-3.0,  0.0, -4.0),
                ( 3.0,  0.0, -4.0),
                ( 8.0,  0.0, -4.0),
            ],
            "rotation_y_base": 0.0,
        },
        "cluster_rules": {
            "workstation_cluster": {"radius": 2.0, "max_members": 3},
            "control_cluster":     {"radius": 2.5, "max_members": 3},
        },
        "narrative": {
            "theme":        "precision robotics",
            "hero_beat":    "featured robot in primary display area",
            "support_beat": "workstations and tools frame the narrative",
            "atmosphere_beat": "clean white light reinforces precision",
        },
    },

    "control_room": {
        "zone_depths": {
            "hero_zone":     0.0,
            "midground":    -8.0,
            "background":  -18.0,
            "console_arc":  -3.0,
        },
        "zone_widths": {
            "hero_zone":   10.0,
            "midground":   20.0,
            "background":  26.0,
            "console_arc": 16.0,
        },
        "hero_zone": {
            "max_assets":   1,
            "categories":   ["electronic", "prop", "robot"],
            "facing":       "camera",
            "y_offset":     0.0,
            "slots": {
                1: [(0.0, 0.0, 0.0)],
                2: [(-3.0, 0.0, 0.0), (3.0, 0.0, 0.0)],
                3: [(-4.0, 0.0, 0.0), (0.0, 0.0, -1.0), (4.0, 0.0, 0.0)],
            },
            "rotation_y_per_slot": {
                1: [0.0],
                2: [5.0, -5.0],
                3: [10.0, 0.0, -10.0],
            },
        },
        "midground": {
            "max_assets":   4,
            "categories":   ["electronic", "prop", "structure"],
            "facing":       "inward",
            "y_offset":     0.0,
            "slots": [
                (-7.0,  0.0, -6.0),
                ( 7.0,  0.0, -6.0),
                (-11.0, 0.0, -9.0),
                ( 11.0, 0.0, -9.0),
            ],
            "rotation_y_base": 25.0,
        },
        "background": {
            "max_assets":   4,
            "categories":   ["electronic", "architectural", "structure"],
            "facing":       "forward",
            "y_offset":     0.0,
            "slots": [
                (-10.0, 0.0, -16.0),
                ( -3.0, 0.0, -18.0),
                (  3.0, 0.0, -18.0),
                ( 10.0, 0.0, -16.0),
            ],
            "rotation_y_base": 0.0,
        },
        "console_arc": {
            "max_assets":   5,
            "categories":   ["electronic", "prop"],
            "facing":       "camera",
            "y_offset":     0.0,
            "slots": [
                (-7.0,  0.0, -2.0),
                (-3.5,  0.0, -3.0),
                ( 0.0,  0.0, -3.5),
                ( 3.5,  0.0, -3.0),
                ( 7.0,  0.0, -2.0),
            ],
            "rotation_y_base": 0.0,
        },
        "cluster_rules": {
            "control_cluster":   {"radius": 2.5, "max_members": 3},
            "workstation_cluster": {"radius": 2.0, "max_members": 3},
        },
        "narrative": {
            "theme":        "command and control",
            "hero_beat":    "central command console as decision nexus",
            "support_beat": "surrounding stations create authority",
            "atmosphere_beat": "screen glow illuminates operators",
        },
    },

    "sci_fi_corridor": {
        "zone_depths": {
            "hero_zone":    0.0,
            "midground":   -8.0,
            "background": -20.0,
            "wall_left":   -5.0,
            "wall_right":  -5.0,
        },
        "zone_widths": {
            "hero_zone":   6.0,
            "midground":   6.0,
            "background":  6.0,
            "wall_left":   1.0,
            "wall_right":  1.0,
        },
        "hero_zone": {
            "max_assets":   2,
            "categories":   ["electronic", "prop", "robot", "character"],
            "facing":       "camera",
            "y_offset":     0.0,
            "slots": {
                1: [(0.0,  0.0, 0.0)],
                2: [(-2.0, 0.0, 0.0), (2.0, 0.0, 0.0)],
                3: [(-2.5, 0.0, 0.5), (0.0, 0.0, 0.0), (2.5, 0.0, 0.5)],
            },
            "rotation_y_per_slot": {
                1: [0.0],
                2: [0.0, 0.0],
                3: [5.0, 0.0, -5.0],
            },
        },
        "midground": {
            "max_assets":   3,
            "categories":   ["electronic", "prop", "structure"],
            "facing":       "forward",
            "y_offset":     0.0,
            "slots": [
                (-2.0, 0.0,  -7.0),
                ( 2.0, 0.0,  -7.0),
                ( 0.0, 0.0, -10.0),
            ],
            "rotation_y_base": 0.0,
        },
        "background": {
            "max_assets":   2,
            "categories":   ["structure", "architectural", "electronic"],
            "facing":       "forward",
            "y_offset":     0.0,
            "slots": [
                (-1.5, 0.0, -18.0),
                ( 1.5, 0.0, -18.0),
            ],
            "rotation_y_base": 0.0,
        },
        "wall_panel_left":  [(-3.5, 1.0, z) for z in (0.0, -4.0, -8.0, -12.0, -16.0)],
        "wall_panel_right": [( 3.5, 1.0, z) for z in (0.0, -4.0, -8.0, -12.0, -16.0)],
        "cluster_rules": {
            "pipe_cluster":      {"radius": 1.0, "max_members": 3, "linear": True},
            "control_cluster":   {"radius": 1.5, "max_members": 2},
        },
        "narrative": {
            "theme":        "corridor traversal",
            "hero_beat":    "central corridor element creates focus",
            "support_beat": "wall panels create spatial rhythm",
            "atmosphere_beat": "neon glow directs the eye forward",
        },
    },

    "abandoned_factory": {
        "zone_depths": {
            "hero_zone":    0.0,
            "midground":  -14.0,
            "background": -30.0,
            "rubble_field": -7.0,
        },
        "zone_widths": {
            "hero_zone":   14.0,
            "midground":   24.0,
            "background":  32.0,
            "rubble_field": 20.0,
        },
        "hero_zone": {
            "max_assets":   2,
            "categories":   ["machinery", "vehicle", "structure"],
            "facing":       "camera",
            "y_offset":     0.0,
            "slots": {
                1: [(0.0,  0.0, 0.0)],
                2: [(-5.0, 0.0, 0.0), (5.0, 0.0, 0.0)],
                3: [(-6.0, 0.0, 0.5), (0.0, 0.0, 0.0), (6.0, 0.0, 0.5)],
            },
            "rotation_y_per_slot": {
                1: [0.0],
                2: [10.0, -10.0],
                3: [15.0, 0.0, -15.0],
            },
        },
        "midground": {
            "max_assets":   5,
            "categories":   ["structure", "prop", "machinery"],
            "facing":       "inward",
            "y_offset":     0.0,
            "slots": [
                (-10.0, 0.0, -12.0),
                ( 10.0, 0.0, -12.0),
                ( -5.0, 0.0, -16.0),
                (  5.0, 0.0, -16.0),
                (  0.0, 0.0, -20.0),
            ],
            "rotation_y_base": 25.0,
        },
        "background": {
            "max_assets":   4,
            "categories":   ["architectural", "structure", "terrain"],
            "facing":       "forward",
            "y_offset":     0.0,
            "slots": [
                (-15.0, 0.0, -26.0),
                ( -6.0, 0.0, -30.0),
                (  6.0, 0.0, -30.0),
                ( 15.0, 0.0, -26.0),
            ],
            "rotation_y_base": 0.0,
        },
        "rubble_field": {
            "max_assets":   6,
            "categories":   ["prop", "terrain"],
            "facing":       "scattered",
            "y_offset":     0.0,
            "slots": [
                (-8.0,  0.0, -5.0),
                (-3.0,  0.0, -6.0),
                ( 0.0,  0.0, -8.0),
                ( 4.0,  0.0, -5.0),
                ( 9.0,  0.0, -7.0),
                (-5.0,  0.0, -9.0),
            ],
            "rotation_y_base": 45.0,  # scattered
        },
        "cluster_rules": {
            "machinery_cluster": {"radius": 3.5, "max_members": 3},
            "pipe_cluster":      {"radius": 2.0, "max_members": 4, "linear": True},
        },
        "narrative": {
            "theme":        "post-industrial decay",
            "hero_beat":    "dominant abandoned machinery evokes scale of past industry",
            "support_beat": "debris and smaller props build decay narrative",
            "atmosphere_beat": "heavy fog hides and reveals the ruins",
        },
    },

    # -----------------------------------------------------------------------
    # §39 — warehouse
    # -----------------------------------------------------------------------
    "warehouse": {
        "zone_depths": {
            "hero_zone":    0.0,
            "midground":  -12.0,
            "background": -26.0,
            "aisle_left":  -6.0,
            "aisle_right": -6.0,
        },
        "zone_widths": {
            "hero_zone":   10.0,
            "midground":   22.0,
            "background":  28.0,
            "aisle_left":   6.0,
            "aisle_right":  6.0,
        },
        "hero_zone": {
            "max_assets": 2,
            "categories": ["vehicle", "machinery", "prop"],
            "facing": "camera",
            "y_offset": 0.0,
            "slots": {
                1: [(0.0, 0.0, 0.0)],
                2: [(-4.0, 0.0, 0.0), (4.0, 0.0, 0.0)],
                3: [(-5.0, 0.0, 0.5), (0.0, 0.0, 0.0), (5.0, 0.0, 0.5)],
            },
            "rotation_y_per_slot": {1: [0.0], 2: [10.0, -10.0], 3: [15.0, 0.0, -15.0]},
        },
        "midground": {
            "max_assets": 6,
            "categories": ["prop", "structure", "furniture"],
            "facing": "inward",
            "y_offset": 0.0,
            "slots": [
                (-9.0, 0.0, -10.0), (9.0, 0.0, -10.0),
                (-13.0, 0.0, -13.0), (13.0, 0.0, -13.0),
                (-4.0, 0.0, -16.0), (4.0, 0.0, -16.0),
            ],
            "rotation_y_base": 20.0,
        },
        "background": {
            "max_assets": 4,
            "categories": ["structure", "architectural"],
            "facing": "forward",
            "y_offset": 0.0,
            "slots": [
                (-12.0, 0.0, -23.0), (-5.0, 0.0, -26.0),
                (5.0, 0.0, -26.0), (12.0, 0.0, -23.0),
            ],
            "rotation_y_base": 0.0,
        },
        "cluster_rules": {
            "pallet_cluster": {"radius": 2.5, "max_members": 4},
            "rack_run": {"radius": 1.5, "max_members": 6, "linear": True},
        },
        "narrative": {
            "theme": "logistics operation",
            "hero_beat": "forklift or pallet rack dominates the loading area",
            "support_beat": "stacked crates contextualize the scale of inventory",
            "atmosphere_beat": "fluorescent rows recede into industrial depth",
        },
    },
    # -----------------------------------------------------------------------
    # §39 — space_station
    # -----------------------------------------------------------------------
    "space_station": {
        "zone_depths": {
            "hero_zone":    0.0,
            "midground":   -8.0,
            "background": -18.0,
            "module_left":  -4.0,
            "module_right": -4.0,
        },
        "zone_widths": {
            "hero_zone":   8.0,
            "midground":  16.0,
            "background": 20.0,
            "module_left":  3.0,
            "module_right": 3.0,
        },
        "hero_zone": {
            "max_assets": 2,
            "categories": ["electronics", "equipment", "prop"],
            "facing": "camera",
            "y_offset": 0.0,
            "slots": {
                1: [(0.0, 0.0, 0.0)],
                2: [(-3.0, 0.0, 0.0), (3.0, 0.0, 0.0)],
                3: [(-4.0, 0.0, 0.5), (0.0, 0.0, 0.0), (4.0, 0.0, 0.5)],
            },
            "rotation_y_per_slot": {1: [0.0], 2: [5.0, -5.0], 3: [10.0, 0.0, -10.0]},
        },
        "midground": {
            "max_assets": 4,
            "categories": ["electronics", "structure", "prop"],
            "facing": "inward",
            "y_offset": 0.0,
            "slots": [
                (-6.0, 0.0, -7.0), (6.0, 0.0, -7.0),
                (-9.0, 0.0, -10.0), (9.0, 0.0, -10.0),
            ],
            "rotation_y_base": 15.0,
        },
        "background": {
            "max_assets": 3,
            "categories": ["structure", "architectural", "electronics"],
            "facing": "forward",
            "y_offset": 0.0,
            "slots": [
                (-8.0, 0.0, -16.0), (0.0, 0.0, -18.0), (8.0, 0.0, -16.0),
            ],
            "rotation_y_base": 0.0,
        },
        "cluster_rules": {
            "equipment_rack": {"radius": 1.5, "max_members": 3},
            "panel_run": {"radius": 1.0, "max_members": 4, "linear": True},
        },
        "narrative": {
            "theme": "orbital isolation",
            "hero_beat": "command console or observation window frames the mission",
            "support_beat": "equipment racks contextualize the operational environment",
            "atmosphere_beat": "cool panel glow and viewport create depth",
        },
    },
    # -----------------------------------------------------------------------
    # §39 — western_room
    # -----------------------------------------------------------------------
    "western_room": {
        "zone_depths": {
            "hero_zone":    0.0,
            "midground":   -8.0,
            "background": -18.0,
            "bar_area":    -3.0,
        },
        "zone_widths": {
            "hero_zone":   10.0,
            "midground":   18.0,
            "background":  22.0,
            "bar_area":    14.0,
        },
        "hero_zone": {
            "max_assets": 2,
            "categories": ["furniture", "prop"],
            "facing": "camera",
            "y_offset": 0.0,
            "slots": {
                1: [(0.0, 0.0, 0.0)],
                2: [(-3.5, 0.0, 0.0), (3.5, 0.0, 0.0)],
                3: [(-4.0, 0.0, 0.5), (0.0, 0.0, 0.0), (4.0, 0.0, 0.5)],
            },
            "rotation_y_per_slot": {1: [0.0], 2: [10.0, -10.0], 3: [15.0, 0.0, -15.0]},
        },
        "midground": {
            "max_assets": 5,
            "categories": ["furniture", "prop"],
            "facing": "inward",
            "y_offset": 0.0,
            "slots": [
                (-7.0, 0.0, -7.0), (7.0, 0.0, -7.0),
                (-10.0, 0.0, -10.0), (10.0, 0.0, -10.0),
                (0.0, 0.0, -12.0),
            ],
            "rotation_y_base": 20.0,
        },
        "background": {
            "max_assets": 3,
            "categories": ["architecture", "structure", "prop"],
            "facing": "forward",
            "y_offset": 0.0,
            "slots": [
                (-9.0, 0.0, -15.0), (0.0, 0.0, -18.0), (9.0, 0.0, -15.0),
            ],
            "rotation_y_base": 0.0,
        },
        "cluster_rules": {
            "table_cluster": {"radius": 2.0, "max_members": 3},
            "barrel_stack": {"radius": 1.5, "max_members": 3},
        },
        "narrative": {
            "theme": "frontier gathering place",
            "hero_beat": "central table or bar counter anchors the scene",
            "support_beat": "barrels and crates establish the era",
            "atmosphere_beat": "warm lantern light tells the time and place",
        },
    },
    # -----------------------------------------------------------------------
    # §39 — forest
    # -----------------------------------------------------------------------
    "forest": {
        "zone_depths": {
            "hero_zone":    0.0,
            "midground":  -12.0,
            "background": -28.0,
            "canopy":       6.0,
        },
        "zone_widths": {
            "hero_zone":   14.0,
            "midground":   24.0,
            "background":  32.0,
            "canopy":      32.0,
        },
        "hero_zone": {
            "max_assets": 2,
            "categories": ["vegetation", "terrain", "prop"],
            "facing": "camera",
            "y_offset": 0.0,
            "slots": {
                1: [(0.0, 0.0, 0.0)],
                2: [(-5.0, 0.0, 0.0), (5.0, 0.0, 0.0)],
                3: [(-6.0, 0.0, 0.5), (0.0, 0.0, 0.0), (6.0, 0.0, 0.5)],
            },
            "rotation_y_per_slot": {1: [0.0], 2: [0.0, 0.0], 3: [10.0, 0.0, -10.0]},
        },
        "midground": {
            "max_assets": 6,
            "categories": ["vegetation", "terrain", "prop"],
            "facing": "scattered",
            "y_offset": 0.0,
            "slots": [
                (-10.0, 0.0, -10.0), (10.0, 0.0, -10.0),
                (-5.0, 0.0, -14.0), (5.0, 0.0, -14.0),
                (-14.0, 0.0, -16.0), (14.0, 0.0, -16.0),
            ],
            "rotation_y_base": 45.0,
        },
        "background": {
            "max_assets": 5,
            "categories": ["vegetation", "terrain", "architectural"],
            "facing": "forward",
            "y_offset": 0.0,
            "slots": [
                (-15.0, 0.0, -24.0), (-7.0, 0.0, -27.0), (0.0, 0.0, -28.0),
                (7.0, 0.0, -27.0), (15.0, 0.0, -24.0),
            ],
            "rotation_y_base": 0.0,
        },
        "cluster_rules": {
            "tree_cluster": {"radius": 3.0, "max_members": 4},
            "undergrowth_scatter": {"radius": 2.0, "max_members": 5},
        },
        "narrative": {
            "theme": "nature immersion",
            "hero_beat": "ancient tree or forest clearing commands the eye",
            "support_beat": "ferns and undergrowth build layered depth",
            "atmosphere_beat": "canopy shafts and mist reveal the forest spirit",
        },
    },
    # -----------------------------------------------------------------------
    # §39 — military_base
    # -----------------------------------------------------------------------
    "military_base": {
        "zone_depths": {
            "hero_zone":    0.0,
            "midground":  -14.0,
            "background": -30.0,
            "perimeter":  -7.0,
        },
        "zone_widths": {
            "hero_zone":   12.0,
            "midground":   24.0,
            "background":  32.0,
            "perimeter":   20.0,
        },
        "hero_zone": {
            "max_assets": 2,
            "categories": ["vehicle", "structure", "equipment"],
            "facing": "camera",
            "y_offset": 0.0,
            "slots": {
                1: [(0.0, 0.0, 0.0)],
                2: [(-5.0, 0.0, 0.0), (5.0, 0.0, 0.0)],
                3: [(-6.0, 0.0, 0.5), (0.0, 0.0, 0.0), (6.0, 0.0, 0.5)],
            },
            "rotation_y_per_slot": {1: [0.0], 2: [10.0, -10.0], 3: [15.0, 0.0, -15.0]},
        },
        "midground": {
            "max_assets": 5,
            "categories": ["structure", "prop", "vehicle"],
            "facing": "inward",
            "y_offset": 0.0,
            "slots": [
                (-10.0, 0.0, -12.0), (10.0, 0.0, -12.0),
                (-5.0, 0.0, -16.0), (5.0, 0.0, -16.0),
                (0.0, 0.0, -20.0),
            ],
            "rotation_y_base": 25.0,
        },
        "background": {
            "max_assets": 4,
            "categories": ["architecture", "structure", "terrain"],
            "facing": "forward",
            "y_offset": 0.0,
            "slots": [
                (-15.0, 0.0, -26.0), (-6.0, 0.0, -30.0),
                (6.0, 0.0, -30.0), (15.0, 0.0, -26.0),
            ],
            "rotation_y_base": 0.0,
        },
        "cluster_rules": {
            "vehicle_cluster": {"radius": 4.0, "max_members": 3},
            "sandbag_barrier": {"radius": 1.5, "max_members": 5, "linear": True},
        },
        "narrative": {
            "theme": "tactical readiness",
            "hero_beat": "armored vehicle or watchtower establishes military authority",
            "support_beat": "barriers and equipment convey operational readiness",
            "atmosphere_beat": "harsh light and dust reinforce tactical atmosphere",
        },
    },
    # -----------------------------------------------------------------------
    # §39 — castle_hall
    # -----------------------------------------------------------------------
    "castle_hall": {
        "zone_depths": {
            "hero_zone":    0.0,
            "midground":  -10.0,
            "background": -24.0,
            "column_left": -5.0,
            "column_right": -5.0,
        },
        "zone_widths": {
            "hero_zone":   12.0,
            "midground":   22.0,
            "background":  28.0,
            "column_left":  2.0,
            "column_right": 2.0,
        },
        "hero_zone": {
            "max_assets": 2,
            "categories": ["furniture", "architecture", "prop"],
            "facing": "camera",
            "y_offset": 0.0,
            "slots": {
                1: [(0.0, 0.0, 0.0)],
                2: [(-4.0, 0.0, 0.0), (4.0, 0.0, 0.0)],
                3: [(-5.0, 0.0, 0.5), (0.0, 0.0, 0.0), (5.0, 0.0, 0.5)],
            },
            "rotation_y_per_slot": {1: [0.0], 2: [5.0, -5.0], 3: [10.0, 0.0, -10.0]},
        },
        "midground": {
            "max_assets": 4,
            "categories": ["architecture", "prop", "decoration"],
            "facing": "inward",
            "y_offset": 0.0,
            "slots": [
                (-8.0, 0.0, -8.0), (8.0, 0.0, -8.0),
                (-12.0, 0.0, -12.0), (12.0, 0.0, -12.0),
            ],
            "rotation_y_base": 15.0,
        },
        "background": {
            "max_assets": 3,
            "categories": ["architecture", "structure"],
            "facing": "forward",
            "y_offset": 0.0,
            "slots": [
                (-11.0, 0.0, -21.0), (0.0, 0.0, -24.0), (11.0, 0.0, -21.0),
            ],
            "rotation_y_base": 0.0,
        },
        "column_run_left":  [(-13.0, 0.0, z) for z in (0.0, -4.0, -8.0, -12.0, -16.0)],
        "column_run_right": [(13.0, 0.0, z) for z in (0.0, -4.0, -8.0, -12.0, -16.0)],
        "cluster_rules": {
            "torch_run": {"radius": 1.5, "max_members": 4, "linear": True},
        },
        "narrative": {
            "theme": "royal authority",
            "hero_beat": "throne or great fireplace dominates the hall",
            "support_beat": "tapestries and columns frame the power structure",
            "atmosphere_beat": "torch light and stained glass echo medieval grandeur",
        },
    },
    # -----------------------------------------------------------------------
    # §39 — survival_camp
    # -----------------------------------------------------------------------
    "survival_camp": {
        "zone_depths": {
            "hero_zone":    0.0,
            "midground":  -12.0,
            "background": -24.0,
            "perimeter":   -6.0,
        },
        "zone_widths": {
            "hero_zone":   10.0,
            "midground":   20.0,
            "background":  26.0,
            "perimeter":   16.0,
        },
        "hero_zone": {
            "max_assets": 2,
            "categories": ["prop", "structure", "equipment"],
            "facing": "camera",
            "y_offset": 0.0,
            "slots": {
                1: [(0.0, 0.0, 0.0)],
                2: [(-3.0, 0.0, 0.0), (3.0, 0.0, 0.0)],
                3: [(-4.0, 0.0, 0.5), (0.0, 0.0, 0.0), (4.0, 0.0, 0.5)],
            },
            "rotation_y_per_slot": {1: [0.0], 2: [10.0, -10.0], 3: [15.0, 0.0, -15.0]},
        },
        "midground": {
            "max_assets": 5,
            "categories": ["prop", "structure", "vehicle"],
            "facing": "inward",
            "y_offset": 0.0,
            "slots": [
                (-8.0, 0.0, -10.0), (8.0, 0.0, -10.0),
                (-4.0, 0.0, -14.0), (4.0, 0.0, -14.0),
                (0.0, 0.0, -17.0),
            ],
            "rotation_y_base": 30.0,
        },
        "background": {
            "max_assets": 4,
            "categories": ["structure", "terrain", "architectural"],
            "facing": "forward",
            "y_offset": 0.0,
            "slots": [
                (-12.0, 0.0, -20.0), (-5.0, 0.0, -23.0),
                (5.0, 0.0, -23.0), (12.0, 0.0, -20.0),
            ],
            "rotation_y_base": 0.0,
        },
        "cluster_rules": {
            "supply_cluster": {"radius": 2.0, "max_members": 4},
            "shelter_group": {"radius": 3.0, "max_members": 3},
        },
        "narrative": {
            "theme": "human resilience",
            "hero_beat": "campfire or central barricade holds the survivors together",
            "support_beat": "scavenged supplies and improvised shelter tell the story",
            "atmosphere_beat": "smoke and grey light frame hope against despair",
        },
    },
}

_BUILTIN_NAMES = frozenset(_BUILTIN_TEMPLATES.keys())


# ---------------------------------------------------------------------------
# Registry class
# ---------------------------------------------------------------------------

class PlacementTemplates:
    """Registry of deterministic placement templates for each environment."""

    def __init__(self) -> None:
        self._lock: threading.Lock = threading.Lock()
        self._templates: Dict[str, Dict[str, Any]] = {}
        self._load_builtins()

    def _load_builtins(self) -> None:
        for name, tmpl in _BUILTIN_TEMPLATES.items():
            self._templates[name] = _deep_copy(tmpl)

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_template(self, name: str, template: Dict[str, Any]) -> None:
        """Register a custom template.  Validates required fields."""
        missing = _REQUIRED_FIELDS - set(template.keys())
        if missing:
            raise ValueError(f"Template {name!r} missing required fields: {sorted(missing)}")
        with self._lock:
            self._templates[name] = _deep_copy(template)

    def deregister_template(self, name: str) -> bool:
        """Remove a custom template.  Raises ValueError for built-ins."""
        if name in _BUILTIN_NAMES:
            raise ValueError(f"Cannot deregister built-in template {name!r}.")
        with self._lock:
            if name in self._templates:
                del self._templates[name]
                return True
            return False

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def get_template(self, name: str) -> Optional[Dict[str, Any]]:
        """Return a deep copy of the template, or None if not found."""
        with self._lock:
            tmpl = self._templates.get(name)
            return _deep_copy(tmpl) if tmpl else None

    def get_template_or_default(self, name: str) -> Dict[str, Any]:
        """Return the named template, or the industrial_hangar default."""
        tmpl = self.get_template(name)
        if tmpl is None:
            tmpl = self.get_template("industrial_hangar")
        return tmpl  # type: ignore[return-value]

    def list_templates(self) -> List[str]:
        """Return sorted list of all registered template names."""
        with self._lock:
            return sorted(self._templates.keys())

    def is_builtin(self, name: str) -> bool:
        return name in _BUILTIN_NAMES

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            names = list(self._templates.keys())
        builtins = [n for n in names if n in _BUILTIN_NAMES]
        return {
            "total": len(names),
            "builtin_count": len(builtins),
            "custom_count": len(names) - len(builtins),
            "template_names": sorted(names),
        }

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_template(self, template: Dict[str, Any]) -> Dict[str, Any]:
        """Check a template dict for structural correctness."""
        errors = []
        warnings = []
        missing = _REQUIRED_FIELDS - set(template.keys())
        if missing:
            errors.append(f"Missing required fields: {sorted(missing)}")
        for zone in ("hero_zone", "midground", "background"):
            if zone in template and not isinstance(template[zone], dict):
                errors.append(f"{zone!r} must be a dict.")
        return {
            "valid":    len(errors) == 0,
            "errors":   errors,
            "warnings": warnings,
        }


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _deep_copy(obj: Any) -> Any:
    """Minimal deep-copy that handles dicts, lists, tuples, and scalars."""
    if isinstance(obj, dict):
        return {k: _deep_copy(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_deep_copy(v) for v in obj]
    if isinstance(obj, tuple):
        return tuple(_deep_copy(v) for v in obj)
    return obj


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[PlacementTemplates] = None
_INSTANCE_LOCK = threading.Lock()


def get_placement_templates() -> PlacementTemplates:
    """Return the module-level singleton PlacementTemplates."""
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = PlacementTemplates()
    return _INSTANCE


def reset_placement_templates_for_tests() -> None:
    """Replace the singleton.  For test isolation only."""
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
