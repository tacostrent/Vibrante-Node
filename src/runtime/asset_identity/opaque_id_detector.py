"""
opaque_id_detector.py — Tier 14.4.5 Asset Identity Audit
==========================================================
Detects opaque Megascans-style identifiers that convey no semantic meaning
and cannot be used to classify or understand an asset.

An identifier is opaque if:
    - All characters are lowercase ASCII letters [a-z] only
    - Length 5–15
    - Contains NO production vocabulary word as a substring

Opaque examples  : "xgihfgbqx", "wgxobac", "ukphdffaw", "abcdefghi"
Non-opaque       : "wooden_chair", "table_01", "old_barrel", "chair",
                   "megascans_wood_abc123", "WoodenChair_lod0"

Public API:
    OPAQUE_PATTERN
    VOCABULARY_WORDS
    OpaqueIdDetector
    is_opaque_id(s)
    get_opaque_id_detector()
    reset_opaque_id_detector_for_tests()
"""

from __future__ import annotations

import re
import threading
from typing import FrozenSet, Optional

# ---------------------------------------------------------------------------
# Regex: all lowercase [a-z], 5–15 chars, NO digits, NO underscores/hyphens/spaces
# ---------------------------------------------------------------------------

OPAQUE_PATTERN: re.Pattern = re.compile(r'^[a-z]{5,15}$')

# ---------------------------------------------------------------------------
# Production vocabulary — strings that disqualify a name from being opaque
# ---------------------------------------------------------------------------

VOCABULARY_WORDS: FrozenSet[str] = frozenset({
    # Furniture / seating
    "chair", "table", "bench", "stool", "sofa", "couch", "throne", "desk",
    "cabinet", "shelf", "shelve", "wardrobe", "dresser", "chest", "counter",
    # Props / containers
    "barrel", "crate", "box", "bucket", "bottle", "cup", "mug", "bowl",
    "vase", "pot", "jar", "glass", "plate", "tray", "basket", "sack",
    # Lighting / signage
    "lantern", "torch", "candle", "lamp", "light", "sconce", "chandelier",
    "poster", "sign", "banner", "clock", "mirror", "frame", "painting",
    # Architecture / structure
    "wall", "floor", "ceiling", "beam", "column", "pillar", "arch", "door",
    "window", "frame", "gate", "fence", "railing", "stair", "ladder",
    "archway", "doorway", "portal", "vault",
    # Machines / equipment
    "machine", "engine", "reactor", "console", "panel", "monitor", "screen",
    "terminal", "server", "rack", "pump", "pipe", "valve", "cable",
    # Nature / terrain
    "rock", "stone", "dirt", "grass", "tree", "plant", "root", "branch",
    "wood", "metal", "steel", "iron", "copper", "brass", "silver", "gold",
    # Clothing / fabric
    "cloth", "fabric", "rope", "chain", "strap", "belt", "hook",
    # Vehicles / transport
    "wagon", "cart", "barrel", "wheel", "axle", "crane", "track",
    # General descriptors
    "large", "small", "round", "square", "flat", "long", "short", "wide",
    "narrow", "thick", "thin", "rough", "smooth", "clean", "dirty",
    "broken", "rusty", "wooden", "stone", "metal", "leather",
    # Common asset name segments
    "prop", "asset", "item", "object", "piece", "part", "mesh", "model",
    "static", "hero", "support", "deco",
})


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------

class OpaqueIdDetector:
    """
    Determines whether an identifier string is an opaque, semantically empty ID
    such as a Megascans asset code ("xgihfgbqx") rather than a human-readable name.

    Rules applied in order:
    1. Empty or whitespace-only → NOT opaque (just missing).
    2. Contains whitespace, underscore, hyphen, or digit → NOT opaque
       (has structural separators or numbering).
    3. Matches OPAQUE_PATTERN (all lowercase [a-z], 5–15 chars) AND
       no VOCABULARY_WORDS appear as a substring → OPAQUE.
    4. Otherwise → NOT opaque.

    Thread-safe (stateless computation, no shared mutable state).
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def is_opaque(self, identifier: str) -> bool:
        """
        Return True if identifier appears to be an opaque, semantically empty ID.
        Never raises.
        """
        try:
            return self._check(identifier)
        except Exception:
            return False

    def _check(self, s: str) -> bool:
        if not s or not s.strip():
            return False  # missing, not opaque

        # Any structural character → human-authored name
        if re.search(r'[_\- \d]', s):
            return False

        # Any uppercase → intentional naming
        if any(c.isupper() for c in s):
            return False

        if not OPAQUE_PATTERN.fullmatch(s):
            return False

        # Check vocabulary membership (substring match)
        lower = s.lower()
        for word in VOCABULARY_WORDS:
            if word in lower:
                return False

        return True

    def describe(self, identifier: str) -> str:
        """Return a short diagnostic string for logging."""
        if self.is_opaque(identifier):
            return f"OPAQUE: '{identifier}' matches Megascans ID pattern with no vocabulary match"
        return f"OK: '{identifier}'"


# ---------------------------------------------------------------------------
# Module-level shortcut
# ---------------------------------------------------------------------------

def is_opaque_id(s: str) -> bool:
    """Module-level helper; delegates to the singleton."""
    return get_opaque_id_detector().is_opaque(s)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[OpaqueIdDetector] = None
_lock = threading.Lock()


def get_opaque_id_detector() -> OpaqueIdDetector:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = OpaqueIdDetector()
    return _instance


def reset_opaque_id_detector_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
