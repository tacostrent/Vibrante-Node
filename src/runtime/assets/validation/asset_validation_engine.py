"""
Asset Validation Engine (Tier 8 — Asset Intelligence Runtime)
==============================================================
Validates AssetDescriptors for suitability before ranking.

Checks performed:
  1. Category compatibility with target zone
  2. Format compatibility with target renderer
  3. Scale compatibility with scene scale
  4. Duplicate detection across a set of assets
  5. Invalid / incomplete metadata

Assets failing validation are flagged and excluded from recommendation.

DESIGN RULES:
  - No bridge calls.  Stateless — safe to call from any context.
  - Deterministic — same input always produces the same report.
  - All checks are named so callers can reason about failures.
  - Never raises — errors captured in ValidationReport.errors.

Public API:
    ValidationReport
    AssetValidationEngine
    get_asset_validation_engine()
    reset_asset_validation_engine_for_tests()
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional, Set

from src.runtime.assets.schema import AssetDescriptor

# ---------------------------------------------------------------------------
# Compatibility tables
# ---------------------------------------------------------------------------

# Renderer → incompatible formats
_RENDERER_FORMAT_INCOMPATIBILITY: Dict[str, FrozenSet[str]] = {
    "arnold":  frozenset({"bgeo"}),
    "karma":   frozenset(),
    "mantra":  frozenset(),
    "redshift": frozenset(),
    "generic": frozenset({"vdb"}),
}

# Zone → expected scale types (permissive — "unknown" always passes)
_ZONE_SCALES: Dict[str, FrozenSet[str]] = {
    "foreground": frozenset({"tiny", "small", "human", "vehicle", "architectural", "unknown"}),
    "midground":  frozenset({"human", "vehicle", "architectural", "urban", "unknown"}),
    "background": frozenset({"architectural", "urban", "landscape", "unknown"}),
    "overhead":   frozenset({"landscape", "architectural", "unknown"}),
}

# Conflicting category pairs (style incompatibility)
_CONFLICTING_PAIRS: FrozenSet[FrozenSet[str]] = frozenset({
    frozenset({"vegetation", "electronic"}),
    frozenset({"organic", "industrial"}),
    frozenset({"creature", "robot"}),
})


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass
class ValidationReport:
    """Result of validating one or more AssetDescriptors."""

    valid_assets:    List[AssetDescriptor] = field(default_factory=list)
    rejected_assets: List[AssetDescriptor] = field(default_factory=list)
    rejection_reasons: Dict[str, List[str]] = field(default_factory=dict)
    warnings:        Dict[str, List[str]]   = field(default_factory=dict)
    checks_run:      List[str]              = field(default_factory=list)
    errors:          List[str]              = field(default_factory=list)

    @property
    def valid_count(self) -> int:
        return len(self.valid_assets)

    @property
    def rejected_count(self) -> int:
        return len(self.rejected_assets)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid_assets":      [a.to_dict() for a in self.valid_assets],
            "rejected_assets":   [a.to_dict() for a in self.rejected_assets],
            "rejection_reasons": dict(self.rejection_reasons),
            "warnings":          dict(self.warnings),
            "checks_run":        list(self.checks_run),
            "errors":            list(self.errors),
            "valid_count":       self.valid_count,
            "rejected_count":    self.rejected_count,
        }


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class AssetValidationEngine:
    """
    Validates AssetDescriptors for suitability.

    Stateless — all context is passed as arguments so the same instance
    can serve multiple concurrent pipelines.
    """

    def validate(
        self,
        assets: List[AssetDescriptor],
        zone: str = "",
        renderer: str = "",
        scene_scale: str = "",
        existing_categories: Optional[List[str]] = None,
    ) -> ValidationReport:
        """
        Validate a list of assets.

        Args:
            assets:               Assets to validate.
            zone:                 Target scene zone (foreground/midground/background/…).
            renderer:             Target renderer key (arnold/karma/mantra/…).
            scene_scale:          Overall scene scale for scale-compatibility checks.
            existing_categories:  Categories already present in the scene (for conflict check).

        Returns:
            :class:`ValidationReport` with valid_assets populated.
            Never raises.
        """
        report = ValidationReport()
        try:
            report.checks_run = self._checks_run(zone, renderer, scene_scale)
            seen_ids: Set[str] = set()
            existing_cats = set(existing_categories or [])

            for asset in assets:
                blocking, advisory = self._validate_one(
                    asset, zone, renderer, scene_scale, seen_ids, existing_cats
                )
                asset_key = f"{asset.provider}:{asset.asset_id}"
                if blocking:
                    report.rejected_assets.append(asset)
                    report.rejection_reasons[asset_key] = blocking
                else:
                    report.valid_assets.append(asset)
                    seen_ids.add(asset_key)
                if advisory:
                    report.warnings[asset_key] = advisory

        except Exception as exc:
            report.errors.append(f"Validation failed: {exc}")

        return report

    def validate_one(
        self,
        asset: AssetDescriptor,
        zone: str = "",
        renderer: str = "",
        scene_scale: str = "",
    ) -> Dict[str, Any]:
        """
        Validate a single asset in isolation.

        Returns:
            {"valid": bool, "errors": [...], "warnings": [...], "checks_passed": [...], "checks_failed": [...]}
        """
        blocking, advisory = self._validate_one(asset, zone, renderer, scene_scale, set(), set())
        checks_run = self._checks_run(zone, renderer, scene_scale)
        return {
            "valid":         len(blocking) == 0,
            "errors":        blocking,
            "warnings":      advisory,
            "checks_passed": [c for c in checks_run if c not in _failed_check_names(blocking)],
            "checks_failed":  _failed_check_names(blocking),
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _validate_one(
        self,
        asset: AssetDescriptor,
        zone: str,
        renderer: str,
        scene_scale: str,
        seen_ids: Set[str],
        existing_cats: Set[str],
    ):
        blocking: List[str] = []
        advisory: List[str] = []

        # 1. Required fields
        if not asset.name:
            blocking.append("name_missing: Asset name is empty.")
        if not asset.category:
            advisory.append("category_missing: Category not set.")

        # 2. Duplicate detection
        key = f"{asset.provider}:{asset.asset_id}"
        if key in seen_ids:
            blocking.append(f"duplicate: Asset {key!r} already in validated set.")

        # 3. Format compatibility with renderer
        if renderer:
            bad_formats = _RENDERER_FORMAT_INCOMPATIBILITY.get(renderer.lower(), frozenset())
            bad = [f for f in asset.formats if f.lower() in bad_formats]
            if bad and not set(asset.formats) - bad_formats:
                blocking.append(
                    f"format_incompatible: Formats {bad} incompatible with renderer {renderer!r}."
                )

        # 4. Scale compatibility with zone
        if zone and asset.scale and asset.scale != "unknown":
            allowed = _ZONE_SCALES.get(zone.lower(), frozenset())
            if allowed and asset.scale not in allowed:
                advisory.append(
                    f"scale_mismatch: Scale {asset.scale!r} may not suit zone {zone!r}."
                )

        # 5. Style conflict with existing categories
        if existing_cats and asset.category:
            for pair in _CONFLICTING_PAIRS:
                if asset.category in pair:
                    conflicting = pair - {asset.category}
                    overlap = conflicting & existing_cats
                    if overlap:
                        advisory.append(
                            f"style_conflict: {asset.category!r} conflicts with {sorted(overlap)}."
                        )

        # 6. Invalid rating
        if asset.rating < 0.0 or asset.rating > 5.0:
            blocking.append(f"invalid_rating: Rating {asset.rating} outside [0, 5].")

        return blocking, advisory

    @staticmethod
    def _checks_run(zone: str, renderer: str, scene_scale: str) -> List[str]:
        checks = ["required_fields", "duplicate_detection", "invalid_rating"]
        if renderer:
            checks.append("format_compatibility")
        if zone:
            checks.append("scale_compatibility")
        checks.append("style_conflict")
        return checks


def _failed_check_names(blocking: List[str]) -> List[str]:
    return [msg.split(":")[0] for msg in blocking]


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[AssetValidationEngine] = None
_INSTANCE_LOCK = threading.Lock()


def get_asset_validation_engine() -> AssetValidationEngine:
    """Return the module-level singleton AssetValidationEngine."""
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = AssetValidationEngine()
    return _INSTANCE


def reset_asset_validation_engine_for_tests() -> None:
    """Replace the singleton.  For test isolation only."""
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
