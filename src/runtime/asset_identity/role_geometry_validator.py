"""
role_geometry_validator.py — Tier 14.4.5 Asset Identity Audit
==============================================================
Validates that vibrante_asset_role is consistent with vibrante_asset_category,
which encodes the physical type of the asset and serves as the geometry proxy
when raw bbox data is not available in Houdini user-data.

Examples of violations:
    category="structural"  + role="surface_child"   → mismatch (beams cannot sit on tables)
    category="decoration"  + role="anchor"           → mismatch (decorations cannot be anchors)
    category="furniture"   + role="ceiling_mount"    → mismatch (furniture hangs on ceilings)
    category="structural"  + role="cluster_member"   → mismatch (beams in furniture clusters)

Both fields empty or unknown → NOT a mismatch.
One field missing           → NOT a mismatch (missing is a separate issue).

Public API:
    ROLE_CATEGORY_MAP
    RoleGeometryValidator
    get_role_geometry_validator()
    reset_role_geometry_validator_for_tests()
"""

from __future__ import annotations

import threading
from typing import Dict, FrozenSet, Optional

# ---------------------------------------------------------------------------
# Compatibility table: role → acceptable category values
# ---------------------------------------------------------------------------

ROLE_CATEGORY_MAP: Dict[str, FrozenSet[str]] = {
    "anchor": frozenset({
        "furniture", "machine", "prop", "hero_asset", "equipment",
        "industrial", "vehicle", "appliance", "structure",
    }),
    "cluster_member": frozenset({
        "furniture", "prop", "seating", "decoration", "smallprop",
        "tableware", "tool",
    }),
    "surface_child": frozenset({
        "prop", "decoration", "container", "tableware", "tool",
        "smallprop", "book", "document", "food",
    }),
    "wall_mount": frozenset({
        "prop", "decoration", "signage", "lighting", "artwork",
        "structural", "fixture",
    }),
    "ceiling_mount": frozenset({
        "lighting", "decoration", "fixture", "structural",
    }),
    "wall_adjacent": frozenset({
        "furniture", "prop", "container", "storage", "equipment",
        "machine", "decoration",
    }),
    "decoration": frozenset({
        "prop", "decoration", "smallprop", "container", "tableware",
        "tool", "book", "document", "food", "natural",
    }),
    "proximity_prop": frozenset({
        "prop", "decoration", "container", "storage", "smallprop",
        "furniture", "equipment",
    }),
    "prop": frozenset({
        "prop", "decoration", "container", "furniture", "structural",
        "machine", "equipment", "vehicle", "tool", "smallprop",
        "book", "tableware", "food", "natural", "industrial",
    }),
    "container": frozenset({
        "furniture", "storage", "prop", "machine", "equipment",
        "container", "industrial",
    }),
    "container_child": frozenset({
        "prop", "decoration", "tool", "tableware", "smallprop",
        "book", "document", "food",
    }),
}

# Categories that are NEVER valid for anchor or cluster_member roles
_STRUCTURAL_CATEGORIES: FrozenSet[str] = frozenset({
    "structural", "architecture", "terrain", "wall", "floor",
    "ceiling", "beam", "column", "arch",
})


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------

class RoleGeometryValidator:
    """
    Validates role ↔ category (geometry proxy) consistency.

    Structural category override: if category is in _STRUCTURAL_CATEGORIES,
    the asset should NOT be in roles like surface_child, cluster_member, or
    ceiling_mount (structural elements do not orbit tables or hang from ceilings).

    Thread-safe (stateless computation).
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def is_compatible(self, role: str, category: str) -> bool:
        """
        Return True if role and category are compatible, or if either is empty.
        Never raises.
        """
        try:
            return self._check(role.strip().lower(), category.strip().lower())
        except Exception:
            return True

    def _check(self, role: str, category: str) -> bool:
        if not role or not category:
            return True  # missing fields handled separately
        if category == "unknown":
            return True  # unknown category → cannot determine

        # Hard structural override
        if category in _STRUCTURAL_CATEGORIES:
            if role in ("surface_child", "cluster_member", "ceiling_mount", "container_child"):
                return False

        compatible = ROLE_CATEGORY_MAP.get(role)
        if compatible is None:
            return True  # unknown role → cannot determine

        return category in compatible

    def describe_mismatch(self, role: str, category: str) -> str:
        """Return a human-readable mismatch description."""
        compatible = ROLE_CATEGORY_MAP.get(role.strip().lower(), frozenset())
        return (
            f"role='{role}' is not compatible with category='{category}'; "
            f"expected one of {sorted(compatible)!r}"
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[RoleGeometryValidator] = None
_lock = threading.Lock()


def get_role_geometry_validator() -> RoleGeometryValidator:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = RoleGeometryValidator()
    return _instance


def reset_role_geometry_validator_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
