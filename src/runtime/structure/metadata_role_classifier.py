"""
Metadata Role Classifier (Tier 10.3 — Structural Asset Classification)
=======================================================================
Classify an asset's structural role from its name, tags, category, and
Megascans metadata fields.  Keyword tables map terminology to structural
roles.  Case-insensitive; underscores and hyphens treated as spaces.

No bridge calls. Deterministic.

Public API:
    MetadataRoleClassifier
    get_metadata_role_classifier()
    reset_metadata_role_classifier_for_tests()
"""

from __future__ import annotations

import re
import threading
from typing import Any, Dict, List, Optional, Tuple


# ──────────────────────────────────────────────────────────────────────────────
# Keyword → role tables  (order matters: first match wins within a group)
# ──────────────────────────────────────────────────────────────────────────────

# Each entry: (keyword, role, confidence)
# Longer/more-specific keywords listed first so they match before shorter ones.
_KEYWORD_TABLE: List[Tuple[str, str, float]] = [
    # ── door / portal ────────────────────────────────────────────────────
    ("door frame",      "door_frame",           0.92),
    ("doorframe",       "door_frame",           0.92),
    ("door_frame",      "door_frame",           0.92),
    ("door way",        "doorway",              0.90),
    ("doorway",         "doorway",              0.90),
    ("portal",          "doorway",              0.85),
    ("entrance door",   "doorway",              0.88),
    ("exit door",       "doorway",              0.88),
    ("hatch",           "doorway",              0.80),
    ("bulkhead door",   "doorway",              0.85),
    ("sliding door",    "doorway",              0.85),
    ("swing door",      "doorway",              0.85),
    ("gate",            "doorway",              0.80),
    ("door",            "doorway",              0.88),

    # ── window / viewport ────────────────────────────────────────────────
    ("window frame",    "window_frame",         0.92),
    ("window_frame",    "window_frame",         0.92),
    ("windowframe",     "window_frame",         0.92),
    ("viewport",        "window",               0.80),
    ("glass pane",      "window",               0.78),
    ("window",          "window",               0.90),

    # ── fireplace / hearth ───────────────────────────────────────────────
    ("mantelpiece",     "fireplace",            0.90),
    ("mantel",          "fireplace",            0.88),
    ("chimney",         "fireplace",            0.85),
    ("hearth",          "fireplace",            0.88),
    ("fireplace",       "fireplace",            0.92),

    # ── beam / girder ────────────────────────────────────────────────────
    ("crossbeam",       "beam",                 0.88),
    ("cross beam",      "beam",                 0.88),
    ("steel girder",    "beam",                 0.90),
    ("girder",          "beam",                 0.88),
    ("joist",           "beam",                 0.85),
    ("rafter",          "beam",                 0.85),
    ("truss",           "beam",                 0.85),
    ("timber beam",     "beam",                 0.90),
    ("wooden beam",     "beam",                 0.90),
    ("support beam",    "support_beam",         0.90),
    ("load beam",       "support_beam",         0.88),
    ("structural beam", "support_beam",         0.90),
    ("beam",            "beam",                 0.85),

    # ── column / pillar ──────────────────────────────────────────────────
    ("stone pillar",    "column",               0.90),
    ("stone column",    "column",               0.90),
    ("concrete column", "column",               0.90),
    ("support column",  "column",               0.90),
    ("steel column",    "column",               0.90),
    ("colonnade",       "column",               0.85),
    ("pillar",          "column",               0.88),
    ("column",          "column",               0.88),

    # ── arch / archway ───────────────────────────────────────────────────
    ("arcade",          "archway",              0.82),
    ("arch way",        "archway",              0.90),
    ("archway",         "archway",              0.92),
    ("arch",            "archway",              0.80),

    # ── wall / segment ───────────────────────────────────────────────────
    ("wainscoting",     "wall_segment",         0.85),
    ("baseboard",       "wall_segment",         0.80),
    ("skirting",        "wall_segment",         0.80),
    ("wall moulding",   "wall_segment",         0.85),
    ("wall molding",    "wall_segment",         0.85),
    ("wall panel",      "wall_segment",         0.88),
    ("wall module",     "wall_segment",         0.88),
    ("wall segment",    "wall_segment",         0.90),
    ("wall piece",      "wall_segment",         0.85),
    ("wall tile",       "wall_segment",         0.80),
    ("partition",       "wall_segment",         0.82),
    ("panel",           "wall_segment",         0.70),
    ("wall",            "wall",                 0.85),

    # ── floor ────────────────────────────────────────────────────────────
    ("floor plank",     "floor_piece",          0.88),
    ("floor board",     "floor_piece",          0.88),
    ("floorboard",      "floor_piece",          0.88),
    ("floor tile",      "floor_piece",          0.85),
    ("floor panel",     "floor_piece",          0.88),
    ("floor piece",     "floor_piece",          0.90),
    ("floor",           "floor_piece",          0.78),

    # ── ceiling ──────────────────────────────────────────────────────────
    ("ceiling tile",    "ceiling_piece",        0.88),
    ("ceiling panel",   "ceiling_piece",        0.88),
    ("ceiling piece",   "ceiling_piece",        0.90),
    ("ceiling",         "ceiling_piece",        0.80),

    # ── stair ────────────────────────────────────────────────────────────
    ("staircase",       "stair",                0.90),
    ("stairway",        "stair",                0.88),
    ("stairs",          "stair",                0.90),
    ("stair",           "stair",                0.88),
    ("steps",           "stair",                0.82),
    ("step",            "stair",                0.78),

    # ── railing ──────────────────────────────────────────────────────────
    ("balustrade",      "railing",              0.90),
    ("banister",        "railing",              0.88),
    ("handrail",        "railing",              0.88),
    ("railing",         "railing",              0.90),
    ("rail",            "railing",              0.78),
    ("fence",           "railing",              0.70),

    # ── modular architectural ─────────────────────────────────────────────
    ("set piece",       "architectural_module", 0.72),
    ("set dressing",    "prop",                 0.65),
    ("modular kit",     "architectural_module", 0.78),
    ("kit bash",        "architectural_module", 0.72),
    ("kitbash",         "architectural_module", 0.72),
    ("modular",         "architectural_module", 0.70),
]

# Category names that indicate structural assets
_STRUCTURAL_CATEGORIES = frozenset({
    "architecture", "architectural", "building", "structure", "structural",
    "interior_architecture", "building_element", "construction",
    "architectural_element", "environment_kit", "modular_kit",
})

# Category names that indicate furniture
_FURNITURE_CATEGORIES = frozenset({
    "furniture", "seating", "table", "chair", "desk", "cabinet",
    "shelving", "bed", "sofa",
})

# Category names that indicate props/decoration
_PROP_CATEGORIES = frozenset({
    "prop", "decoration", "decor", "accessory", "item",
    "small_prop", "clutter",
})


def _normalise(text: str) -> str:
    """Lowercase, replace underscores/hyphens with spaces, collapse whitespace."""
    text = text.lower()
    text = re.sub(r"[_\-]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


class MetadataRoleClassifier:
    """
    Classify structural role from asset name, tags, and category.

    Returns (role, confidence, features) where features is a list of
    matched keyword strings that drove the classification.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def classify(
        self,
        asset: Dict[str, Any],
    ) -> Tuple[str, float, List[str]]:
        """
        Classify from asset metadata dict.

        Keys examined (all optional): name, asset_name, asset_id, tags, category,
        categories, type, asset_type, placement_type, collection, description.

        Returns:
            (role, confidence, supporting_features)  — never raises.
        """
        try:
            return self._classify(asset)
        except Exception:
            return "structural_unknown", 0.20, []

    def _classify(
        self, asset: Dict[str, Any]
    ) -> Tuple[str, float, List[str]]:
        # ── Build a combined text bag from all relevant fields ─────────────
        text_parts: List[str] = []
        for key in (
            "name", "asset_name", "asset_id", "title",
            "type", "asset_type", "placement_type", "collection",
        ):
            v = asset.get(key)
            if v and isinstance(v, str):
                text_parts.append(_normalise(v))

        # Tags (list or comma-separated string)
        tags = asset.get("tags") or asset.get("megascans_tags") or []
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",")]
        for t in tags:
            if isinstance(t, str):
                text_parts.append(_normalise(t))

        combined = " ".join(text_parts)

        # ── Category classification (high-confidence fast path) ───────────
        categories = asset.get("categories") or []
        if isinstance(categories, str):
            categories = [c.strip() for c in categories.split(",")]
        cat_str = _normalise(asset.get("category") or "")

        for cat in [cat_str] + [_normalise(c) for c in categories]:
            if cat in _STRUCTURAL_CATEGORIES:
                # Category says structural — do keyword scan for specific role
                role, conf, feats = self._keyword_scan(combined)
                if conf < 0.60:
                    return "architectural_module", 0.72, [f"category:{cat}"]
                return role, min(1.0, conf + 0.05), [f"category:{cat}"] + feats

            if cat in _FURNITURE_CATEGORIES:
                return "furniture", 0.78, [f"category:{cat}"]

            if cat in _PROP_CATEGORIES:
                return "prop", 0.72, [f"category:{cat}"]

        # ── Full keyword scan ─────────────────────────────────────────────
        return self._keyword_scan(combined)

    @staticmethod
    def _keyword_scan(
        text: str,
    ) -> Tuple[str, float, List[str]]:
        """Scan `text` against the keyword table. Returns first match."""
        for keyword, role, conf in _KEYWORD_TABLE:
            if keyword in text:
                return role, conf, [f"keyword:{keyword}"]
        return "prop", 0.40, []


# ──────────────────────────────────────────────────────────────────────────────
# Singleton
# ──────────────────────────────────────────────────────────────────────────────

_INSTANCE: Optional[MetadataRoleClassifier] = None
_LOCK = threading.Lock()


def get_metadata_role_classifier() -> MetadataRoleClassifier:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = MetadataRoleClassifier()
        return _INSTANCE


def reset_metadata_role_classifier_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
