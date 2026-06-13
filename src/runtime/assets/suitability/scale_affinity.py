"""
scale_affinity.py — §45 Semantic Asset Suitability Ranking
===========================================================
Scores how well an asset's scale class matches the expected scale for the
requested role. Prevents structural beams filling chair slots and tiny
props filling machine slots.

Public API:
    get_scale_affinity() -> ScaleAffinity
    reset_scale_affinity_for_tests()

    ScaleAffinity.score(asset, role, expected_scale) -> float  0.0–1.0
    ScaleAffinity.expected_scale_for_role(role) -> str
"""

import threading
from typing import Dict, Optional

# Scale classes aligned with Tier 9.6 / 9.7 AssetScaleAnalyzer
_SCALE_CLASSES = ("tiny", "small", "medium", "large", "structural", "hero")

# Expected scale per role (best match)
_ROLE_EXPECTED_SCALE: Dict[str, str] = {
    # tiny (< 0.15 m)
    "cup": "tiny",
    "mug": "tiny",
    "bottle": "tiny",
    "flask": "tiny",
    "vial": "tiny",
    "book": "tiny",
    "candle": "tiny",
    # small (< 0.50 m)
    "bucket": "small",
    "lantern": "small",
    "lamp": "small",
    "stool": "small",
    "toolbox": "small",
    "poster": "small",
    "sign": "small",
    "box": "small",
    "torch": "small",
    # medium (< 1.50 m)
    "chair": "medium",
    "barrel": "medium",
    "crate": "medium",
    "cabinet": "medium",
    "door": "medium",
    "statue": "medium",
    "plant": "medium",
    "drum": "medium",
    "anvil": "medium",
    "fireplace": "medium",
    # large (< 4.0 m)
    "table": "large",
    "shelf": "large",
    "bench": "large",
    "sofa": "large",
    "wardrobe": "large",
    "window": "large",
    "workbench": "large",
    "desk": "large",
    "rack": "large",
    "tank": "large",
    # hero (major focal, often large)
    "machine": "hero",
    "console": "hero",
    "vehicle": "hero",
    # structural (architecture)
    "crane": "structural",
    "beam": "structural",
    "wall": "structural",
    "column": "structural",
    "floor": "structural",
}

# Compatibility matrix: expected_scale × actual_scale → 0.0–1.0
_SCALE_COMPAT: Dict[str, Dict[str, float]] = {
    "tiny":       {"tiny": 1.0, "small": 0.70, "medium": 0.20, "large": 0.05, "structural": 0.0, "hero": 0.0},
    "small":      {"tiny": 0.70, "small": 1.0, "medium": 0.60, "large": 0.10, "structural": 0.0, "hero": 0.0},
    "medium":     {"tiny": 0.20, "small": 0.60, "medium": 1.0, "large": 0.50, "structural": 0.0, "hero": 0.30},
    "large":      {"tiny": 0.05, "small": 0.10, "medium": 0.50, "large": 1.0, "structural": 0.30, "hero": 0.70},
    "structural": {"tiny": 0.0,  "small": 0.0,  "medium": 0.0,  "large": 0.30, "structural": 1.0, "hero": 0.70},
    "hero":       {"tiny": 0.0,  "small": 0.0,  "medium": 0.30, "large": 0.70, "structural": 0.70, "hero": 1.0},
}


def _get_asset_scale(asset: dict) -> Optional[str]:
    """Extract scale_class from asset metadata."""
    for field in ("scale_class", "scale", "size_class"):
        v = asset.get(field, "")
        if isinstance(v, str) and v.lower() in _SCALE_CLASSES:
            return v.lower()
    return None


class ScaleAffinity:
    """Scores scale class compatibility between an asset and its slot role."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def score(self, asset: dict, role: str = "", expected_scale: str = "") -> float:
        """Return 0.0–1.0 scale fit score."""
        try:
            actual = _get_asset_scale(asset)
            if actual is None:
                return 0.5  # no scale info — neutral

            # Determine expected scale
            exp = expected_scale.lower() if expected_scale else ""
            if not exp and role:
                exp = _ROLE_EXPECTED_SCALE.get(role.lower(), "")
            if not exp:
                return 0.5  # no expectation — neutral

            row = _SCALE_COMPAT.get(exp)
            if row is None:
                return 0.5
            return row.get(actual, 0.5)
        except Exception:
            return 0.5

    def expected_scale_for_role(self, role: str) -> str:
        return _ROLE_EXPECTED_SCALE.get(role.lower(), "")

    def known_roles(self):
        return sorted(_ROLE_EXPECTED_SCALE.keys())


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: ScaleAffinity | None = None
_instance_lock = threading.Lock()


def get_scale_affinity() -> ScaleAffinity:
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = ScaleAffinity()
    return _instance


def reset_scale_affinity_for_tests() -> None:
    global _instance
    with _instance_lock:
        _instance = None
