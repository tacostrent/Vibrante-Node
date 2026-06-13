"""
role_engine_validator.py — Tier 14.4.5 Asset Identity Audit
=============================================================
Cross-validates vibrante_asset_role against vibrante_placement_engine.

Each placement engine is responsible for exactly one set of roles:
    AnchorLayoutEngine      → anchor, container
    FurnitureClusterBuilder → cluster_member, prop
    SurfacePlacementEngine  → surface_child, container_child
    WallAttachmentEngine    → wall_mount, wall_adjacent, ceiling_mount
    DecorationLayoutEngine  → decoration, proximity_prop, prop, wall_adjacent
    SemanticLayoutEngine    → anchor, prop, decoration  (fallback engine)

A role/engine pair is VALID if the engine is in the compatible set for that role.
A role/engine pair is INVALID (mismatch) if neither is empty and the engine
is NOT in the compatible set.
Empty role or empty engine → NOT a mismatch (flagged as missing instead).

Public API:
    ROLE_ENGINE_MAP
    RoleEngineValidator
    get_role_engine_validator()
    reset_role_engine_validator_for_tests()
"""

from __future__ import annotations

import threading
from typing import Dict, FrozenSet, Optional

# ---------------------------------------------------------------------------
# Compatibility table
# ---------------------------------------------------------------------------

ROLE_ENGINE_MAP: Dict[str, FrozenSet[str]] = {
    "anchor":          frozenset({"AnchorLayoutEngine", "SemanticLayoutEngine"}),
    "cluster_member":  frozenset({"FurnitureClusterBuilder", "AnchorLayoutEngine"}),
    "surface_child":   frozenset({"SurfacePlacementEngine"}),
    "container_child": frozenset({"SurfacePlacementEngine", "DecorationLayoutEngine"}),
    "wall_mount":      frozenset({"WallAttachmentEngine"}),
    "wall_adjacent":   frozenset({"WallAttachmentEngine", "DecorationLayoutEngine"}),
    "ceiling_mount":   frozenset({"WallAttachmentEngine"}),
    "decoration":      frozenset({"DecorationLayoutEngine", "SemanticLayoutEngine"}),
    "proximity_prop":  frozenset({"DecorationLayoutEngine", "SemanticLayoutEngine"}),
    "prop":            frozenset({"DecorationLayoutEngine", "SemanticLayoutEngine",
                                  "FurnitureClusterBuilder"}),
    "container":       frozenset({"AnchorLayoutEngine", "DecorationLayoutEngine"}),
}

# Reverse: engine → acceptable roles (for diagnostics only)
_ENGINE_ROLE_MAP: Dict[str, FrozenSet[str]] = {
    "AnchorLayoutEngine":      frozenset({"anchor", "cluster_member", "container"}),
    "FurnitureClusterBuilder": frozenset({"cluster_member", "prop"}),
    "SurfacePlacementEngine":  frozenset({"surface_child", "container_child"}),
    "WallAttachmentEngine":    frozenset({"wall_mount", "wall_adjacent", "ceiling_mount"}),
    "DecorationLayoutEngine":  frozenset({"decoration", "proximity_prop", "prop",
                                          "container_child", "wall_adjacent"}),
    "SemanticLayoutEngine":    frozenset({"anchor", "prop", "decoration"}),
}


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------

class RoleEngineValidator:
    """
    Validates that vibrante_asset_role is consistent with vibrante_placement_engine.

    Thread-safe (stateless computation).
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def is_compatible(self, role: str, engine: str) -> bool:
        """
        Return True if role and engine are compatible, or if either is empty
        (empty → not a mismatch, just missing).
        Never raises.
        """
        try:
            return self._check(role.strip(), engine.strip())
        except Exception:
            return True  # conservative: unknown → assume compatible

    def _check(self, role: str, engine: str) -> bool:
        if not role or not engine:
            return True  # missing fields handled separately
        compatible_engines = ROLE_ENGINE_MAP.get(role)
        if compatible_engines is None:
            return True  # unknown role → cannot determine mismatch
        return engine in compatible_engines

    def expected_engines(self, role: str) -> FrozenSet[str]:
        """Return the set of engines expected for a given role."""
        return ROLE_ENGINE_MAP.get(role.strip(), frozenset())

    def expected_roles(self, engine: str) -> FrozenSet[str]:
        """Return the set of roles expected for a given engine."""
        return _ENGINE_ROLE_MAP.get(engine.strip(), frozenset())

    def describe_mismatch(self, role: str, engine: str) -> str:
        """Return a human-readable mismatch description."""
        expected = self.expected_engines(role)
        if expected:
            return (
                f"role='{role}' expects engine in {sorted(expected)!r}, "
                f"got '{engine}'"
            )
        return f"unknown role='{role}' with engine='{engine}'"


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[RoleEngineValidator] = None
_lock = threading.Lock()


def get_role_engine_validator() -> RoleEngineValidator:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = RoleEngineValidator()
    return _instance


def reset_role_engine_validator_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
