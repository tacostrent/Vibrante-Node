"""
layout_validator.py — §47 Layout Realization & Scene Constraint Solver
=======================================================================
Pre-realization validation gate.

Before any layout is applied to the scene, this module checks every asset
for physically plausible dimensions.  Assets whose scale is outside the
expected range for their role (chair 15× too tall, bottle 20× too wide)
indicate that the import scale was not corrected and the 2m-normalization
bug is still active somewhere upstream.

The validator blocks realization if any asset fails validation with a
clear message identifying the outlier and the corrective action.

Rules:
  - Expected ranges are per placement-type (chair 0.70–1.20m tall, etc.)
  - Outlier threshold: height > 3× upper bound OR height < 0.25× lower bound
  - Wall / structural elements are exempt from the height outlier check
  - Never raises. Returns a LayoutValidationResult.

DESIGN RULES:
  1. No bridge calls. No Houdini imports.
  2. Deterministic — same inputs → same result.
  3. Never raises.
  4. Singleton pattern.

Public API:
    LayoutValidationResult
    LayoutValidator
    get_layout_validator()
    reset_layout_validator_for_tests()
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# Expected height range [min_m, max_m] per placement type
_HEIGHT_RANGES: Dict[str, Tuple[float, float]] = {
    "chair":         (0.70, 1.20),
    "stool":         (0.30, 0.80),
    "table":         (0.60, 1.20),
    "desk":          (0.60, 1.00),
    "workbench":     (0.75, 1.10),
    "bar_counter":   (0.90, 1.30),
    "bench":         (0.40, 0.80),
    "cabinet":       (0.80, 2.20),
    "shelf":         (1.00, 2.20),
    "sofa":          (0.70, 1.10),
    "bed":           (0.40, 0.90),
    "bottle":        (0.10, 0.50),
    "bucket":        (0.20, 0.80),
    "barrel":        (0.50, 1.40),
    "crate":         (0.30, 1.20),
    "lantern":       (0.20, 0.70),
    "cup":           (0.06, 0.25),
    "book":          (0.15, 0.40),
    "door":          (1.80, 2.50),
    "window":        (0.50, 2.00),
    "machine":       (0.80, 4.00),
    "vehicle":       (1.20, 3.50),
    "beam":          (0.10, 1.00),   # height = cross-section
    "column":        (1.50, 8.00),
    "wall":          (1.50, 6.00),
    "tree":          (1.00, 25.0),
    "plant":         (0.10, 3.00),
}

# Placement types exempt from height outlier checking
_EXEMPT_TYPES = frozenset({"wall", "beam", "column", "platform", "terrain",
                            "floor", "roof", "support_column", "support_beam"})

# Outlier thresholds (multiples of the expected range)
_UPPER_OUTLIER_FACTOR = 3.0   # height > 3× upper bound → outlier
_LOWER_OUTLIER_FACTOR = 0.25  # height < 0.25× lower bound → outlier


@dataclass
class AssetValidationRecord:
    asset_id:       str
    asset_name:     str
    placement_type: str
    height_m:       float
    expected_min_m: float
    expected_max_m: float
    issue:          str    # "invalid_scale" | "invalid_bbox" | "outlier" | ""
    note:           str = ""

    @property
    def valid(self) -> bool:
        return not self.issue

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id":       self.asset_id,
            "asset_name":     self.asset_name,
            "placement_type": self.placement_type,
            "height_m":       round(self.height_m, 4),
            "expected_min_m": self.expected_min_m,
            "expected_max_m": self.expected_max_m,
            "issue":          self.issue,
            "note":           self.note,
            "valid":          self.valid,
        }


@dataclass
class LayoutValidationResult:
    """
    Pre-realization layout validation report.

    ok = True   → all assets passed; realization may proceed
    ok = False  → one or more assets failed; realization is blocked

    Fields:
      invalid_scale_assets  — assets whose height is impossibly large (2m-norm artifact)
      invalid_bbox_assets   — assets with missing or zero bbox data
      outlier_assets        — assets outside expected height range
      records               — per-asset details
    """
    ok:                   bool = True
    total_assets:         int  = 0
    passed:               int  = 0
    failed:               int  = 0
    invalid_scale_assets: List[str] = field(default_factory=list)
    invalid_bbox_assets:  List[str] = field(default_factory=list)
    outlier_assets:       List[str] = field(default_factory=list)
    records:              List[AssetValidationRecord] = field(default_factory=list)
    errors:               List[str] = field(default_factory=list)
    message:              str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok":                   self.ok,
            "total_assets":         self.total_assets,
            "passed":               self.passed,
            "failed":               self.failed,
            "invalid_scale_assets": list(self.invalid_scale_assets),
            "invalid_bbox_assets":  list(self.invalid_bbox_assets),
            "outlier_assets":       list(self.outlier_assets),
            "records":              [r.to_dict() for r in self.records],
            "errors":               list(self.errors),
            "message":              self.message,
        }


class LayoutValidator:
    """
    Validates that all assets have physically plausible dimensions before
    layout realization is allowed to proceed.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def validate(self, assets: List[Dict[str, Any]]) -> LayoutValidationResult:
        """
        Validate a list of asset dicts.

        Each dict must have at minimum:
          - asset_id / name
          - height_m OR bbox_y (in meters)
          - placement_type (optional — skips range check if absent)

        Never raises.
        """
        try:
            return self._validate(assets)
        except Exception as exc:
            return LayoutValidationResult(
                ok=False,
                errors=[f"LayoutValidator.validate failed: {exc}"],
                message="Validation failed due to an internal error.",
            )

    def _validate(self, assets: List[Dict[str, Any]]) -> LayoutValidationResult:
        result = LayoutValidationResult(total_assets=len(assets))

        for asset in assets:
            rec = self._check_asset(asset)
            result.records.append(rec)
            if rec.valid:
                result.passed += 1
            else:
                result.failed += 1
                if rec.issue == "invalid_scale":
                    result.invalid_scale_assets.append(rec.asset_id)
                elif rec.issue == "invalid_bbox":
                    result.invalid_bbox_assets.append(rec.asset_id)
                elif rec.issue == "outlier":
                    result.outlier_assets.append(rec.asset_id)

        all_bad = result.invalid_scale_assets + result.invalid_bbox_assets + result.outlier_assets
        result.ok = len(all_bad) == 0

        if result.ok:
            result.message = (
                f"All {result.total_assets} assets passed scale validation."
            )
        else:
            result.message = (
                f"{result.failed} of {result.total_assets} assets failed validation. "
                "Likely cause: 2m-normalization still active upstream in the import pipeline. "
                f"Failing assets: {all_bad[:5]}"
                + (" …" if len(all_bad) > 5 else "")
            )

        return result

    def _check_asset(self, asset: Dict[str, Any]) -> AssetValidationRecord:
        asset_id = str(asset.get("asset_id") or asset.get("name") or "unknown")
        asset_name = str(asset.get("name") or asset_id)
        pt = str(asset.get("placement_type") or "").lower().strip()

        # Extract height in meters
        height_m = self._get_height_m(asset)

        # Invalid bbox: no height data at all
        if height_m <= 0.0:
            return AssetValidationRecord(
                asset_id=asset_id, asset_name=asset_name,
                placement_type=pt, height_m=height_m,
                expected_min_m=0.0, expected_max_m=0.0,
                issue="invalid_bbox",
                note="No height_m or bbox_y data found.",
            )

        # Exempt placement types (structural) — skip range check
        if pt in _EXEMPT_TYPES:
            return AssetValidationRecord(
                asset_id=asset_id, asset_name=asset_name,
                placement_type=pt, height_m=height_m,
                expected_min_m=0.0, expected_max_m=0.0,
                issue="",
                note="Exempt structural type.",
            )

        # No known range for this type — accept without range check
        if pt not in _HEIGHT_RANGES:
            return AssetValidationRecord(
                asset_id=asset_id, asset_name=asset_name,
                placement_type=pt, height_m=height_m,
                expected_min_m=0.0, expected_max_m=0.0,
                issue="",
            )

        lo, hi = _HEIGHT_RANGES[pt]

        # Outlier: impossibly large → 2m-normalization artifact
        if height_m > hi * _UPPER_OUTLIER_FACTOR:
            return AssetValidationRecord(
                asset_id=asset_id, asset_name=asset_name,
                placement_type=pt, height_m=height_m,
                expected_min_m=lo, expected_max_m=hi,
                issue="invalid_scale",
                note=(
                    f"Height {height_m:.3f}m is {height_m/hi:.1f}× above expected max {hi}m. "
                    "This is the 2m-normalization artifact — import scale not corrected."
                ),
            )

        # Outlier: impossibly small
        if height_m < lo * _LOWER_OUTLIER_FACTOR:
            return AssetValidationRecord(
                asset_id=asset_id, asset_name=asset_name,
                placement_type=pt, height_m=height_m,
                expected_min_m=lo, expected_max_m=hi,
                issue="outlier",
                note=f"Height {height_m:.3f}m is below minimum threshold {lo * _LOWER_OUTLIER_FACTOR:.3f}m.",
            )

        # Within expected range (allow ±50% beyond stated range for unusual assets)
        return AssetValidationRecord(
            asset_id=asset_id, asset_name=asset_name,
            placement_type=pt, height_m=height_m,
            expected_min_m=lo, expected_max_m=hi,
            issue="",
        )

    @staticmethod
    def _get_height_m(asset: Dict[str, Any]) -> float:
        """Extract height in meters from asset dict. Returns 0.0 if unavailable."""
        for key in ("height_m", "bbox_y", "h", "height"):
            v = asset.get(key)
            if v is not None:
                try:
                    return float(v)
                except (TypeError, ValueError):
                    pass
        return 0.0


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[LayoutValidator] = None
_LOCK = threading.Lock()


def get_layout_validator() -> LayoutValidator:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = LayoutValidator()
        return _INSTANCE


def reset_layout_validator_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
