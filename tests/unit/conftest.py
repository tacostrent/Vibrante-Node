"""Shared fixtures for tests/unit — §54 Reality Intelligence (Tier 15.0+)."""

import pytest


def _asset(asset_id, name, tx, ty, tz, hx, hy, hz, ry=0.0, **extra):
    d = {
        "asset_id": asset_id, "asset_name": name,
        "tx": tx, "ty": ty, "tz": tz, "ry": ry,
        "bbox_half_x": hx, "bbox_half_y": hy, "bbox_half_z": hz,
    }
    d.update(extra)
    return d


def build_western_room_scene():
    """Canonical §54 production-ready western_room: 10×12 m room (walls at
    x=±5, z=±6), dining cluster, fireplace zone, storage corner, wall decor,
    wall-to-wall beams, real door/window in the wall planes. 19 assets."""
    return {
        "environment": "western_room",
        "room_width": 10.0, "room_height": 4.0, "room_depth": 12.0,
        "transforms": [
            # Dining zone
            _asset("table_01", "Saloon Table", 0.0, 0.375, 0.0, 1.10, 0.375, 0.65),
            _asset("chair_01", "Saloon Chair", 0.0, 0.45, 1.55, 0.25, 0.45, 0.25, ry=180.0),
            _asset("chair_02", "Saloon Chair", 0.0, 0.45, -1.55, 0.25, 0.45, 0.25, ry=0.0),
            _asset("chair_03", "Saloon Chair", 1.85, 0.45, 0.0, 0.25, 0.45, 0.25, ry=270.0),
            _asset("chair_04", "Saloon Chair", -1.85, 0.45, 0.0, 0.25, 0.45, 0.25, ry=90.0),
            _asset("bottle_01", "Whiskey Bottle", 0.3, 0.90, 0.2, 0.05, 0.15, 0.05),
            _asset("cup_01", "Tin Cup", -0.3, 0.81, 0.1, 0.05, 0.06, 0.05),
            _asset("plate_01", "Tin Plate", 0.0, 0.77, -0.3, 0.12, 0.02, 0.12),
            _asset("lantern_01", "Oil Lantern", 0.6, 0.90, -0.2, 0.10, 0.15, 0.10),
            # Fireplace zone
            _asset("fireplace_01", "Stone Fireplace", 0.0, 1.0, -5.65, 0.90, 1.0, 0.35),
            _asset("chair_05", "Saloon Chair", -1.2, 0.45, -4.6, 0.25, 0.45, 0.25, ry=131.19),
            _asset("chair_06", "Saloon Chair", 1.2, 0.45, -4.6, 0.25, 0.45, 0.25, ry=228.81),
            # Storage corner
            _asset("crate_01", "Wooden Crate", 4.3, 0.40, 5.3, 0.40, 0.40, 0.40),
            _asset("barrel_01", "Oak Barrel", 3.4, 0.45, 5.2, 0.30, 0.45, 0.30),
            # Wall decor
            _asset("poster_01", "Wanted Poster", -4.97, 1.6, 2.0, 0.02, 0.50, 0.40),
            # Structure
            _asset("beam_01", "Wooden Beam", 0.0, 3.8, -2.0, 5.0, 0.15, 0.15),
            _asset("beam_02", "Wooden Beam", 0.0, 3.8, 2.0, 5.0, 0.15, 0.15),
            _asset("door_01", "Swing Door", 0.0, 1.05, 5.97, 0.50, 1.05, 0.06),
            _asset("window_01", "Window", 4.98, 1.5, -2.0, 0.05, 0.60, 0.50),
        ],
    }


@pytest.fixture
def western_room_scene():
    return build_western_room_scene()


@pytest.fixture
def make_asset():
    return _asset
