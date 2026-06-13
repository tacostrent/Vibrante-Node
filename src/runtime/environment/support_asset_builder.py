"""
Support Asset Builder (§44 — Structural Environment Assembly)
=============================================================
Places secondary props relative to anchor assets. Support assets are the
contextual elements that reinforce an anchor's meaning — chairs around a
table, pipes near a machine, stools at a bar.

DESIGN RULES:
  1. No bridge calls. No Houdini imports. Planning only.
  2. Deterministic — same environment always yields the same support plan.
  3. Never raises — errors captured in SupportPlan.errors.
  4. Singleton pattern.
  5. Thread-safe.

Public API:
    SupportAsset
    SupportPlan
    SupportAssetBuilder
    get_support_asset_builder()
    reset_support_asset_builder_for_tests()
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.runtime.environment.anchor_asset_builder import AnchorPlan, get_anchor_asset_builder


# ---------------------------------------------------------------------------
# Per-environment support asset definitions (independent of anchors)
# ---------------------------------------------------------------------------

# Fallback support definitions per environment (in addition to anchor children)
_ENV_SUPPORT: Dict[str, List[Dict[str, Any]]] = {
    "western_room":      [{"asset_type": "barrel",     "zone_type": "wall_zone",    "position_mode": "near_wall",    "parent_anchor_type": None, "count": 2}],
    "saloon":            [{"asset_type": "spittoon",    "zone_type": "service_zone", "position_mode": "corner",       "parent_anchor_type": None, "count": 2},
                          {"asset_type": "hat_rack",    "zone_type": "wall_zone",    "position_mode": "near_wall",    "parent_anchor_type": None, "count": 1}],
    "living_room":       [{"asset_type": "rug",         "zone_type": "hero_zone",    "position_mode": "around_anchor","parent_anchor_type": "sofa", "count": 1},
                          {"asset_type": "side_table",  "zone_type": "seating_zone", "position_mode": "around_anchor","parent_anchor_type": "sofa", "count": 2}],
    "office":            [{"asset_type": "trash_bin",   "zone_type": "support_zone", "position_mode": "near_wall",    "parent_anchor_type": None, "count": 2},
                          {"asset_type": "chair",       "zone_type": "hero_zone",    "position_mode": "around_anchor","parent_anchor_type": "main_desk", "count": 2}],
    "hotel_lobby":       [{"asset_type": "luggage_cart","zone_type": "entrance_zone","position_mode": "near_wall",    "parent_anchor_type": None, "count": 1},
                          {"asset_type": "plant",       "zone_type": "decoration_zone","position_mode": "corner",    "parent_anchor_type": None, "count": 3}],
    "restaurant":        [{"asset_type": "chair",       "zone_type": "seating_zone", "position_mode": "around_anchor","parent_anchor_type": "main_table_cluster", "count": 6},
                          {"asset_type": "wine_rack",   "zone_type": "wall_zone",    "position_mode": "near_wall",   "parent_anchor_type": None, "count": 1}],
    "library":           [{"asset_type": "chair",       "zone_type": "seating_zone", "position_mode": "around_anchor","parent_anchor_type": "reading_table", "count": 4},
                          {"asset_type": "ladder",      "zone_type": "wall_zone",    "position_mode": "near_wall",   "parent_anchor_type": "bookshelf_row", "count": 1}],
    "warehouse":         [{"asset_type": "forklift",    "zone_type": "support_zone", "position_mode": "midground",   "parent_anchor_type": None, "count": 1},
                          {"asset_type": "safety_cone", "zone_type": "decoration_zone","position_mode": "scattered", "parent_anchor_type": None, "count": 6}],
    "industrial_hangar": [{"asset_type": "oil_drum",    "zone_type": "support_zone", "position_mode": "corner",      "parent_anchor_type": None, "count": 4},
                          {"asset_type": "toolbox",     "zone_type": "decoration_zone","position_mode": "near_wall", "parent_anchor_type": None, "count": 3}],
    "abandoned_factory": [{"asset_type": "rust_pipe",   "zone_type": "wall_zone",    "position_mode": "near_wall",   "parent_anchor_type": None, "count": 3},
                          {"asset_type": "broken_barrel","zone_type": "decoration_zone","position_mode": "scattered","parent_anchor_type": None, "count": 4}],
    "robotics_lab":      [{"asset_type": "cable_bundle","zone_type": "wall_zone",    "position_mode": "near_wall",   "parent_anchor_type": None, "count": 3},
                          {"asset_type": "monitor",     "zone_type": "support_zone", "position_mode": "around_anchor","parent_anchor_type": "main_robot_station", "count": 2}],
    "control_room":      [{"asset_type": "chair",       "zone_type": "hero_zone",    "position_mode": "around_anchor","parent_anchor_type": "master_console", "count": 3},
                          {"asset_type": "status_light","zone_type": "decoration_zone","position_mode": "scattered", "parent_anchor_type": None, "count": 4}],
    "medical_lab":       [{"asset_type": "stool",       "zone_type": "support_zone", "position_mode": "around_anchor","parent_anchor_type": "examination_table", "count": 2},
                          {"asset_type": "waste_bin",   "zone_type": "decoration_zone","position_mode": "corner",   "parent_anchor_type": None, "count": 2}],
    "research_lab":      [{"asset_type": "stool",       "zone_type": "support_zone", "position_mode": "around_anchor","parent_anchor_type": "central_workbench", "count": 3},
                          {"asset_type": "fire_extinguisher","zone_type": "wall_zone","position_mode": "near_wall",  "parent_anchor_type": None, "count": 1}],
    "sci_fi_corridor":   [{"asset_type": "status_light","zone_type": "wall_zone",    "position_mode": "near_wall",   "parent_anchor_type": None, "count": 4},
                          {"asset_type": "fire_extinguisher","zone_type": "decoration_zone","position_mode": "near_wall","parent_anchor_type": None, "count": 2}],
    "city_street":       [{"asset_type": "bench",       "zone_type": "support_zone", "position_mode": "near_wall",   "parent_anchor_type": None, "count": 3},
                          {"asset_type": "trash_can",   "zone_type": "decoration_zone","position_mode": "scattered", "parent_anchor_type": None, "count": 4}],
    "forest":            [{"asset_type": "fern",        "zone_type": "decoration_zone","position_mode": "scattered", "parent_anchor_type": None, "count": 8},
                          {"asset_type": "small_rock",  "zone_type": "support_zone", "position_mode": "scattered",   "parent_anchor_type": None, "count": 6}],
    "desert":            [{"asset_type": "cactus",      "zone_type": "support_zone", "position_mode": "scattered",   "parent_anchor_type": None, "count": 4},
                          {"asset_type": "tumbleweed",  "zone_type": "decoration_zone","position_mode": "scattered", "parent_anchor_type": None, "count": 3}],
    "castle_hall":       [{"asset_type": "chair",       "zone_type": "seating_zone", "position_mode": "around_anchor","parent_anchor_type": "long_table", "count": 8},
                          {"asset_type": "torch",       "zone_type": "wall_zone",    "position_mode": "near_wall",   "parent_anchor_type": None, "count": 4}],
    "survival_camp":     [{"asset_type": "log",         "zone_type": "hero_zone",    "position_mode": "around_anchor","parent_anchor_type": "camp_fire", "count": 4},
                          {"asset_type": "rope_coil",   "zone_type": "decoration_zone","position_mode": "near_wall", "parent_anchor_type": None, "count": 2}],
}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class SupportAsset:
    """A secondary prop placed in relation to an anchor or zone."""

    support_id: str = field(default_factory=lambda: f"sup_{uuid.uuid4().hex[:8]}")
    asset_type: str = ""
    zone_type: str = ""
    position_mode: str = "around_anchor"  # around_anchor / near_wall / corner / midground / scattered
    parent_anchor_type: Optional[str] = None
    count: int = 1
    display_name: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "support_id":         self.support_id,
            "asset_type":         self.asset_type,
            "zone_type":          self.zone_type,
            "position_mode":      self.position_mode,
            "parent_anchor_type": self.parent_anchor_type,
            "count":              self.count,
            "display_name":       self.display_name,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SupportAsset":
        return cls(
            support_id         = str(d.get("support_id", f"sup_{uuid.uuid4().hex[:8]}")),
            asset_type         = str(d.get("asset_type", "")),
            zone_type          = str(d.get("zone_type", "")),
            position_mode      = str(d.get("position_mode", "around_anchor")),
            parent_anchor_type = d.get("parent_anchor_type"),
            count              = int(d.get("count", 1)),
            display_name       = str(d.get("display_name", "")),
        )


@dataclass
class SupportPlan:
    """The complete support asset layout for an environment."""

    environment_name: str = ""
    support_assets: List[SupportAsset] = field(default_factory=list)
    total_count: int = 0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "environment_name": self.environment_name,
            "support_assets":   [s.to_dict() for s in self.support_assets],
            "total_count":      self.total_count,
            "errors":           list(self.errors),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SupportPlan":
        return cls(
            environment_name = str(d.get("environment_name", "")),
            support_assets   = [SupportAsset.from_dict(s) for s in d.get("support_assets", [])],
            total_count      = int(d.get("total_count", 0)),
            errors           = list(d.get("errors", [])),
        )


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

class SupportAssetBuilder:
    """Build the support asset plan, optionally driven by an AnchorPlan."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def build_support_assets(
        self,
        environment_name: str,
        anchor_plan: Optional[AnchorPlan] = None,
    ) -> SupportPlan:
        """Build the support plan.

        Uses:
        1. Per-environment definitions from _ENV_SUPPORT.
        2. Anchor child_types from anchor_plan (if provided).
        """
        with self._lock:
            try:
                return self._build(environment_name, anchor_plan)
            except Exception as exc:
                return SupportPlan(
                    environment_name = environment_name,
                    errors           = [f"Support build error: {exc}"],
                )

    def _build(
        self,
        environment_name: str,
        anchor_plan: Optional[AnchorPlan],
    ) -> SupportPlan:
        key = (environment_name or "").strip().lower()
        assets: List[SupportAsset] = []

        # 1. Built-in env support definitions
        for d in _ENV_SUPPORT.get(key, []):
            atype = d["asset_type"]
            assets.append(SupportAsset(
                asset_type         = atype,
                zone_type          = d.get("zone_type", "support_zone"),
                position_mode      = d.get("position_mode", "around_anchor"),
                parent_anchor_type = d.get("parent_anchor_type"),
                count              = int(d.get("count", 1)),
                display_name       = atype.replace("_", " ").title(),
            ))

        # 2. Anchor children from anchor_plan
        if anchor_plan:
            for anchor in anchor_plan.anchors:
                for child_type in anchor.child_types:
                    # Skip if already covered
                    if any(a.asset_type == child_type and a.parent_anchor_type == anchor.anchor_type
                           for a in assets):
                        continue
                    assets.append(SupportAsset(
                        asset_type         = child_type,
                        zone_type          = anchor.zone_type,
                        position_mode      = "around_anchor",
                        parent_anchor_type = anchor.anchor_type,
                        count              = 1,
                        display_name       = child_type.replace("_", " ").title(),
                    ))

        total = sum(a.count for a in assets)
        return SupportPlan(
            environment_name = environment_name,
            support_assets   = assets,
            total_count      = total,
            errors           = [],
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[SupportAssetBuilder] = None
_LOCK = threading.Lock()


def get_support_asset_builder() -> SupportAssetBuilder:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = SupportAssetBuilder()
        return _INSTANCE


def reset_support_asset_builder_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
