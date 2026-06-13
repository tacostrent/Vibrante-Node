"""
Scene Population Engine (Tier 9 — Semantic Asset Assembly)
===========================================================
Populates environments intelligently by assigning assets to semantic
population groups and validating the result for production balance.

Population groups:
    hero_assets          — 1–3 primary narrative assets
    support_assets       — flanking/contextual assets
    detail_assets        — small props and dressing
    atmosphere_assets    — fog, particles, HDRI
    storytelling_assets  — narrative-specific items (debris, damage, etc.)

DESIGN RULES:
  1. Deterministic — same EnvironmentPlan → same population every time.
  2. No bridge calls.  No Houdini imports.  Planning only.
  3. Population is driven by zone role + category.
  4. Never raises — errors captured in PopulationPlan.errors.

Public API:
    PopulationGroup
    PopulationPlan
    ScenePopulationEngine
    get_scene_population_engine()
    reset_scene_population_engine_for_tests()
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from src.runtime.assets.assembly.environment_builder import EnvironmentPlan

# ---------------------------------------------------------------------------
# Category → population group mapping
# ---------------------------------------------------------------------------

_CAT_TO_GROUP: Dict[str, str] = {
    # hero
    "vehicle":       "hero_assets",
    "character":     "hero_assets",
    "robot":         "hero_assets",
    "machinery":     "hero_assets",
    "creature":      "hero_assets",
    # support
    "structure":     "support_assets",
    "electronic":    "support_assets",
    "furniture":     "support_assets",
    "weapon":        "support_assets",
    # detail
    "prop":          "detail_assets",
    "pipe":          "detail_assets",
    "conduit":       "detail_assets",
    # atmosphere
    "hdri":          "atmosphere_assets",
    "material":      "atmosphere_assets",
    "terrain":       "atmosphere_assets",
    "vegetation":    "atmosphere_assets",
    # storytelling (architectural context)
    "architectural": "storytelling_assets",
}

_ALL_GROUPS = frozenset({
    "hero_assets", "support_assets", "detail_assets",
    "atmosphere_assets", "storytelling_assets",
})

# Max assets per group — used for balance validation
_GROUP_MAX: Dict[str, int] = {
    "hero_assets":         3,
    "support_assets":     10,
    "detail_assets":      12,
    "atmosphere_assets":   6,
    "storytelling_assets": 8,
}


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class PopulationGroup:
    """One named population group within a scene."""

    group_name:   str
    level:        str           # sparse, moderate, dense
    assets:       List[Dict[str, Any]] = field(default_factory=list)
    max_assets:   int = 8
    zone_names:   List[str] = field(default_factory=list)
    notes:        List[str] = field(default_factory=list)

    @property
    def asset_count(self) -> int:
        return len(self.assets)

    @property
    def fill_ratio(self) -> float:
        if self.max_assets <= 0:
            return 0.0
        return min(1.0, self.asset_count / self.max_assets)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "group_name": self.group_name,
            "level":      self.level,
            "assets":     list(self.assets),
            "max_assets": self.max_assets,
            "zone_names": list(self.zone_names),
            "notes":      list(self.notes),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PopulationGroup":
        return cls(
            group_name=str(d.get("group_name", "")),
            level=str(d.get("level", "moderate")),
            assets=list(d.get("assets") or []),
            max_assets=int(d.get("max_assets", 8)),
            zone_names=list(d.get("zone_names") or []),
            notes=list(d.get("notes") or []),
        )


@dataclass
class PopulationPlan:
    """Full population plan for an environment."""

    plan_id:        str = field(default_factory=lambda: f"pop_{uuid.uuid4().hex[:10]}")
    environment:    str = ""
    groups:         Dict[str, PopulationGroup] = field(default_factory=dict)
    total_assets:   int = 0
    balance_score:  float = 0.0  # 0.0–1.0
    ok:             bool = True
    errors:         List[str] = field(default_factory=list)
    warnings:       List[str] = field(default_factory=list)
    generated_at:   float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id":       self.plan_id,
            "environment":   self.environment,
            "groups":        {n: g.to_dict() for n, g in self.groups.items()},
            "total_assets":  self.total_assets,
            "balance_score": self.balance_score,
            "ok":            self.ok,
            "errors":        list(self.errors),
            "warnings":      list(self.warnings),
            "generated_at":  self.generated_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PopulationPlan":
        return cls(
            plan_id=str(d.get("plan_id", f"pop_{uuid.uuid4().hex[:10]}")),
            environment=str(d.get("environment", "")),
            groups={n: PopulationGroup.from_dict(g) for n, g in (d.get("groups") or {}).items()},
            total_assets=int(d.get("total_assets", 0)),
            balance_score=float(d.get("balance_score", 0.0)),
            ok=bool(d.get("ok", True)),
            errors=list(d.get("errors") or []),
            warnings=list(d.get("warnings") or []),
            generated_at=float(d.get("generated_at", 0.0)),
        )


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class ScenePopulationEngine:
    """
    Populates environments by assigning assets to population groups
    and validating production balance.
    """

    def populate_scene(self, env_plan: EnvironmentPlan) -> PopulationPlan:
        """
        Build a PopulationPlan from an EnvironmentPlan.
        Never raises — errors captured in PopulationPlan.errors.
        """
        plan = PopulationPlan(environment=env_plan.environment)
        try:
            # Initialise empty groups
            plan.groups = {name: PopulationGroup(
                group_name=name,
                level="sparse",
                max_assets=_GROUP_MAX[name],
            ) for name in _ALL_GROUPS}

            # Assign assets
            self.assign_population_levels(env_plan, plan)

            # Validate balance
            balance = self.validate_population_balance(plan)
            plan.balance_score = balance.get("balance_score", 0.0)
            plan.warnings.extend(balance.get("warnings", []))

            plan.total_assets = sum(g.asset_count for g in plan.groups.values())
            plan.ok = True

        except Exception as exc:
            plan.ok = False
            plan.errors.append(f"Population failed: {exc}")

        return plan

    def assign_population_levels(
        self,
        env_plan: EnvironmentPlan,
        plan: PopulationPlan,
    ) -> None:
        """
        Assign all zone assets to their population groups in-place.
        Mutates plan.groups.
        """
        for zone_name, zone in env_plan.zones.items():
            for rec in zone.assigned_assets:
                asset    = rec.get("asset") or {}
                category = str(asset.get("category", "")).lower()
                group_name = _CAT_TO_GROUP.get(category, "support_assets")

                group = plan.groups.get(group_name)
                if group is None:
                    continue

                if group.asset_count < group.max_assets:
                    group.assets.append(rec)
                    if zone_name not in group.zone_names:
                        group.zone_names.append(zone_name)
                else:
                    # Overflow to detail_assets
                    detail = plan.groups.get("detail_assets")
                    if detail and detail.asset_count < detail.max_assets * 2:
                        detail.assets.append(rec)
                    else:
                        plan.warnings.append(
                            f"Asset {asset.get('name', '?')!r} could not be placed "
                            f"in any group — all groups full."
                        )

        # Update levels based on fill ratio
        for group in plan.groups.values():
            group.level = _fill_level(group.fill_ratio)

    def assign_support_assets(
        self,
        assets: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Filter a recommendation list to support-category assets."""
        support_cats = {"structure", "electronic", "furniture", "weapon"}
        return [
            a for a in assets
            if str((a.get("asset") or {}).get("category", "")).lower() in support_cats
        ]

    def assign_detail_assets(
        self,
        assets: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Filter a recommendation list to detail-category assets."""
        detail_cats = {"prop", "pipe", "conduit"}
        return [
            a for a in assets
            if str((a.get("asset") or {}).get("category", "")).lower() in detail_cats
        ]

    def validate_population_balance(self, plan: PopulationPlan) -> Dict[str, Any]:
        """
        Check that population groups are proportionally balanced.
        Returns balance_score (0–1) and advisory warnings.
        """
        warnings: List[str] = []
        score = 1.0

        hero  = plan.groups.get("hero_assets")
        supp  = plan.groups.get("support_assets")
        det   = plan.groups.get("detail_assets")

        # Hero must have at least one asset
        if hero and hero.asset_count == 0:
            warnings.append("No hero assets — scene lacks a primary narrative focal point.")
            score -= 0.4

        # Support should not be empty if hero is populated
        if hero and hero.asset_count > 0 and supp and supp.asset_count == 0:
            warnings.append("No support assets — hero will look isolated without context.")
            score -= 0.2

        # Hero should not exceed its max
        if hero and hero.asset_count > hero.max_assets:
            warnings.append(
                f"Hero group over-populated ({hero.asset_count} > {hero.max_assets})."
            )
            score -= 0.15

        # Detail should not dominate
        total = sum(g.asset_count for g in plan.groups.values())
        if total > 0 and det:
            detail_ratio = det.asset_count / total
            if detail_ratio > 0.6:
                warnings.append(
                    f"Detail assets dominate ({detail_ratio:.0%}) — scene may look cluttered."
                )
                score -= 0.1

        return {
            "balance_score": max(0.0, score),
            "warnings":      warnings,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fill_level(ratio: float) -> str:
    if ratio <= 0.25:
        return "sparse"
    if ratio <= 0.65:
        return "moderate"
    return "dense"


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[ScenePopulationEngine] = None
_INSTANCE_LOCK = threading.Lock()


def get_scene_population_engine() -> ScenePopulationEngine:
    """Return the module-level singleton ScenePopulationEngine."""
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = ScenePopulationEngine()
    return _INSTANCE


def reset_scene_population_engine_for_tests() -> None:
    """Replace the singleton.  For test isolation only."""
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
