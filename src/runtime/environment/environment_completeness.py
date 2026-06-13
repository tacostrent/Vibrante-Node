"""
Environment Completeness (§44 — Structural Environment Assembly)
================================================================
Checks overall environment completeness by examining all pipeline stages:
structure, zones, anchors, support assets, decorative items, and atmosphere.

DESIGN RULES:
  1. No bridge calls. No Houdini imports. Advisory only.
  2. Deterministic.
  3. Never raises.
  4. Singleton pattern.
  5. Thread-safe.

Public API:
    CompletenessResult
    EnvironmentCompleteness
    get_environment_completeness()
    reset_environment_completeness_for_tests()
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.runtime.environment.environment_structure_builder import EnvironmentStructurePlan
from src.runtime.environment.environment_zone_builder import ZonePlan
from src.runtime.environment.anchor_asset_builder import AnchorPlan
from src.runtime.environment.support_asset_builder import SupportPlan
from src.runtime.environment.decorative_population import DecorationPlan
from src.runtime.environment.atmosphere_builder import AtmospherePlan


@dataclass
class CompletenessResult:
    """Overall completeness of a built environment."""

    environment_name: str = ""

    # Structural presence flags
    floor_exists: bool = False
    walls_exist: bool = False
    ceiling_exists: bool = False
    required_doors_exist: bool = False
    required_windows_exist: bool = False

    # Pipeline stage presence
    zones_exist: bool = False
    anchors_exist: bool = False
    support_assets_exist: bool = False
    decorative_assets_exist: bool = False
    atmosphere_exists: bool = False

    # Summary
    all_required_met: bool = False
    missing_required: List[str] = field(default_factory=list)
    completeness_score: float = 0.0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "environment_name":       self.environment_name,
            "floor_exists":           self.floor_exists,
            "walls_exist":            self.walls_exist,
            "ceiling_exists":         self.ceiling_exists,
            "required_doors_exist":   self.required_doors_exist,
            "required_windows_exist": self.required_windows_exist,
            "zones_exist":            self.zones_exist,
            "anchors_exist":          self.anchors_exist,
            "support_assets_exist":   self.support_assets_exist,
            "decorative_assets_exist": self.decorative_assets_exist,
            "atmosphere_exists":       self.atmosphere_exists,
            "all_required_met":        self.all_required_met,
            "missing_required":        list(self.missing_required),
            "completeness_score":      round(self.completeness_score, 4),
            "errors":                  list(self.errors),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CompletenessResult":
        return cls(
            environment_name        = str(d.get("environment_name", "")),
            floor_exists            = bool(d.get("floor_exists", False)),
            walls_exist             = bool(d.get("walls_exist", False)),
            ceiling_exists          = bool(d.get("ceiling_exists", False)),
            required_doors_exist    = bool(d.get("required_doors_exist", False)),
            required_windows_exist  = bool(d.get("required_windows_exist", False)),
            zones_exist             = bool(d.get("zones_exist", False)),
            anchors_exist           = bool(d.get("anchors_exist", False)),
            support_assets_exist    = bool(d.get("support_assets_exist", False)),
            decorative_assets_exist = bool(d.get("decorative_assets_exist", False)),
            atmosphere_exists       = bool(d.get("atmosphere_exists", False)),
            all_required_met        = bool(d.get("all_required_met", False)),
            missing_required        = list(d.get("missing_required", [])),
            completeness_score      = float(d.get("completeness_score", 0.0)),
            errors                  = list(d.get("errors", [])),
        )


class EnvironmentCompleteness:
    """Check overall environment construction completeness."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def check(
        self,
        environment_name: str,
        structure_plan: Optional[EnvironmentStructurePlan] = None,
        zone_plan: Optional[ZonePlan] = None,
        anchor_plan: Optional[AnchorPlan] = None,
        support_plan: Optional[SupportPlan] = None,
        decoration_plan: Optional[DecorationPlan] = None,
        atmosphere_plan: Optional[AtmospherePlan] = None,
    ) -> CompletenessResult:
        """Check environment completeness across all pipeline stages."""
        with self._lock:
            try:
                return self._check(
                    environment_name,
                    structure_plan,
                    zone_plan,
                    anchor_plan,
                    support_plan,
                    decoration_plan,
                    atmosphere_plan,
                )
            except Exception as exc:
                return CompletenessResult(
                    environment_name = environment_name,
                    errors           = [f"Completeness check error: {exc}"],
                )

    def _check(
        self,
        environment_name: str,
        structure_plan: Optional[EnvironmentStructurePlan],
        zone_plan: Optional[ZonePlan],
        anchor_plan: Optional[AnchorPlan],
        support_plan: Optional[SupportPlan],
        decoration_plan: Optional[DecorationPlan],
        atmosphere_plan: Optional[AtmospherePlan],
    ) -> CompletenessResult:
        missing: List[str] = []

        # -- Structural checks -----------------------------------------------
        floor_exists  = bool(structure_plan and structure_plan.floor_present)
        walls_exist   = bool(structure_plan and structure_plan.walls_present)
        ceil_exists   = bool(structure_plan and structure_plan.ceiling_present)
        doors_exist   = bool(structure_plan and structure_plan.doors_present)
        windows_exist = bool(structure_plan and structure_plan.windows_present)

        if not floor_exists:
            missing.append("floor")
        if not walls_exist:
            missing.append("walls")

        # -- Zone checks -------------------------------------------------------
        zones_exist = bool(zone_plan and zone_plan.zone_count > 0)
        if not zones_exist:
            missing.append("zones")

        # -- Anchor checks -----------------------------------------------------
        anchors_exist = bool(anchor_plan and anchor_plan.anchor_count > 0)
        if not anchors_exist:
            missing.append("anchors")

        # -- Support checks ----------------------------------------------------
        support_exist = bool(support_plan and support_plan.total_count > 0)

        # -- Decoration checks -------------------------------------------------
        deco_exist = bool(decoration_plan and decoration_plan.total_count > 0)

        # -- Atmosphere checks -------------------------------------------------
        atm_exist = bool(atmosphere_plan and not atmosphere_plan.errors and atmosphere_plan.profile is not None)

        # -- Score (10 dimensions, equal weight 0.1 each) ----------------------
        # floor, walls, ceiling(if required), doors(if required), windows(if required),
        # zones, anchors, support, decoration, atmosphere
        score_parts = [
            1.0 if floor_exists else 0.0,
            1.0 if walls_exist else 0.0,
            1.0 if ceil_exists else 0.0,   # ceiling may be False if not required
            1.0 if doors_exist else 0.5,   # doors are sometimes optional
            1.0 if windows_exist else 0.5, # windows are sometimes optional
            1.0 if zones_exist else 0.0,
            1.0 if anchors_exist else 0.0,
            1.0 if support_exist else 0.0,
            1.0 if deco_exist else 0.0,
            1.0 if atm_exist else 0.0,
        ]
        score = sum(score_parts) / len(score_parts)

        all_required_met = len(missing) == 0

        return CompletenessResult(
            environment_name        = environment_name,
            floor_exists            = floor_exists,
            walls_exist             = walls_exist,
            ceiling_exists          = ceil_exists,
            required_doors_exist    = doors_exist,
            required_windows_exist  = windows_exist,
            zones_exist             = zones_exist,
            anchors_exist           = anchors_exist,
            support_assets_exist    = support_exist,
            decorative_assets_exist = deco_exist,
            atmosphere_exists       = atm_exist,
            all_required_met        = all_required_met,
            missing_required        = missing,
            completeness_score      = score,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[EnvironmentCompleteness] = None
_LOCK = threading.Lock()


def get_environment_completeness() -> EnvironmentCompleteness:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = EnvironmentCompleteness()
        return _INSTANCE


def reset_environment_completeness_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
