"""
environment_scale_review.py — Environment Scale Validation (Tier 9 Assembly)
=============================================================================
Validates that every placed asset has dimensions consistent with its role and
the selected environment.  Flags assets whose scale is physically implausible
so that the import-scale correction can be verified end-to-end.

Three flag types:
  SCALE_OUTLIER       — height outside the expected range for this placement type
  ROLE_OUTLIER        — placement type does not match the asset's declared role
  ENVIRONMENT_OUTLIER — asset type unexpected in this environment

Grade mapping (same convention as all other review modules):
  score >= 0.90 → A  production_ready=True
  score >= 0.75 → B  production_ready=True
  score >= 0.55 → C  production_ready=False
  score >= 0.40 → D  production_ready=False
  score <  0.40 → F  production_ready=False

Blocking findings (force production_ready=False regardless of score):
  - "2m-normalization detected"  — any asset is ~2m regardless of type
  - "no assets"                  — environment is empty

DESIGN RULES:
  1. No bridge calls. No Houdini imports. Planning only.
  2. Deterministic — same inputs → same result.
  3. Never raises.
  4. Singleton pattern.

Public API:
    ScaleFlag
    AssetScaleReport
    EnvironmentScaleReviewResult
    EnvironmentScaleReview
    get_environment_scale_review()
    reset_environment_scale_review_for_tests()
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Expected height ranges per placement type  [min_m, max_m]
# ---------------------------------------------------------------------------

_HEIGHT_RANGES: Dict[str, Tuple[float, float]] = {
    # Seating
    "chair":          (0.70, 1.20),
    "stool":          (0.30, 0.80),
    "bench":          (0.40, 0.80),
    "sofa":           (0.70, 1.10),
    "armchair":       (0.70, 1.20),
    # Tables / work surfaces
    "table":          (0.60, 1.20),
    "desk":           (0.60, 1.00),
    "workbench":      (0.75, 1.10),
    "bar_counter":    (0.90, 1.30),
    "counter":        (0.80, 1.20),
    # Storage
    "cabinet":        (0.80, 2.20),
    "shelf":          (1.00, 2.20),
    "wardrobe":       (1.60, 2.30),
    "crate":          (0.30, 1.20),
    "barrel":         (0.50, 1.40),
    "bucket":         (0.20, 0.80),
    "pallet":         (0.10, 0.25),
    # Small props
    "bottle":         (0.10, 0.50),
    "cup":            (0.06, 0.25),
    "book":           (0.15, 0.40),
    "lantern":        (0.20, 0.70),
    "candle":         (0.05, 0.30),
    "teapot":         (0.10, 0.35),
    "vase":           (0.10, 0.50),
    "bowl":           (0.05, 0.25),
    "mug":            (0.08, 0.18),
    "tool":           (0.05, 0.80),
    # Doors / windows
    "door":           (1.80, 2.50),
    "window":         (0.50, 2.00),
    # Machines / vehicles
    "machine":        (0.80, 4.00),
    "large_machine":  (2.00, 6.00),
    "vehicle":        (1.20, 3.50),
    # Structural (checked differently)
    "beam":           (0.10, 1.00),
    "column":         (1.50, 8.00),
    "wall":           (1.50, 6.00),
    # Nature
    "tree":           (1.00, 25.0),
    "plant":          (0.10, 3.00),
    # Lighting
    "lantern":        (0.20, 0.70),
    "torch":          (0.30, 1.20),
    "chandelier":     (0.40, 2.00),
}

# Placement types that are structural — exempt from SCALE_OUTLIER flag
_STRUCTURAL_TYPES = frozenset({
    "wall", "beam", "column", "platform", "terrain", "floor", "roof",
    "support_column", "support_beam", "catwalk", "truss", "rafter",
})

# Ratio above expected upper bound that triggers SCALE_OUTLIER.
# 1.4× is deliberately tight: a chair flagged at 1.68m (1.4×1.2m max) catches
# the 2m-normalization artifact (chair at 2.0m = 1.67× expected max).
_UPPER_OUTLIER_FACTOR = 1.4
# Minimum ratio below expected lower bound before flagging SCALE_OUTLIER
_LOWER_OUTLIER_FACTOR = 0.25

# Heuristic: if ≥N assets have height within ±15% of 2.0 m, flag normalisation
_NORM_TARGET_M         = 2.0
_NORM_TOLERANCE        = 0.15   # ±15%
_NORM_CLUSTER_FRACTION = 0.40   # 40% of all assets near 2 m = suspicious


# ---------------------------------------------------------------------------
# Role → expected placement types
# ---------------------------------------------------------------------------

_ROLE_TO_PLACEMENT_TYPES: Dict[str, List[str]] = {
    "furniture":   ["chair", "table", "bench", "sofa", "stool", "desk",
                    "workbench", "bar_counter", "counter", "cabinet", "shelf",
                    "wardrobe", "bed", "armchair"],
    "prop":        ["bottle", "cup", "book", "lantern", "candle", "teapot",
                    "vase", "bowl", "mug", "tool", "crate", "barrel", "bucket",
                    "pallet", "torch", "chandelier"],
    "structure":   list(_STRUCTURAL_TYPES),
    "vehicle":     ["vehicle", "vehicle_small"],
    "character":   ["character"],
    "vegetation":  ["tree", "plant"],
}

# Reverse map: placement_type → expected role
_PT_TO_ROLE: Dict[str, str] = {}
for _role, _types in _ROLE_TO_PLACEMENT_TYPES.items():
    for _t in _types:
        _PT_TO_ROLE[_t] = _role


# ---------------------------------------------------------------------------
# Environment-expected asset types
# ---------------------------------------------------------------------------

_ENV_EXPECTED: Dict[str, List[str]] = {
    "western_room": [
        "chair", "table", "stool", "bench", "barrel", "bucket", "lantern",
        "bottle", "cup", "book", "crate", "beam", "wall", "floor",
    ],
    "saloon": [
        "chair", "table", "stool", "bar_counter", "barrel", "bottle", "lantern",
        "chandelier", "bench", "crate", "bucket",
    ],
    "robotics_lab": [
        "machine", "large_machine", "cabinet", "shelf", "desk", "chair",
        "stool", "crate", "lantern", "tool",
    ],
    "industrial_hangar": [
        "machine", "large_machine", "crate", "barrel", "pallet", "tool",
        "vehicle", "beam", "column",
    ],
    "sci_fi_corridor": [
        "machine", "cabinet", "crate", "door", "column", "bench", "tool",
    ],
    "castle_hall": [
        "chair", "table", "bench", "barrel", "lantern", "torch", "chandelier",
        "crate", "vase", "book",
    ],
    "forest": [
        "tree", "plant", "crate", "barrel", "lantern", "bucket",
    ],
    "office": [
        "desk", "chair", "cabinet", "shelf", "book", "cup", "mug", "crate",
    ],
}


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ScaleFlag:
    flag_type: str    # "SCALE_OUTLIER" | "ROLE_OUTLIER" | "ENVIRONMENT_OUTLIER"
    asset_id:  str
    message:   str

    def to_dict(self) -> Dict[str, Any]:
        return {"flag_type": self.flag_type, "asset_id": self.asset_id, "message": self.message}


@dataclass
class AssetScaleReport:
    asset_id:        str
    asset_name:      str
    placement_type:  str
    height_m:        float
    expected_min_m:  float
    expected_max_m:  float
    declared_role:   str
    expected_role:   str
    flags:           List[ScaleFlag] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.flags) == 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id":       self.asset_id,
            "asset_name":     self.asset_name,
            "placement_type": self.placement_type,
            "height_m":       round(self.height_m, 4),
            "expected_min_m": self.expected_min_m,
            "expected_max_m": self.expected_max_m,
            "declared_role":  self.declared_role,
            "expected_role":  self.expected_role,
            "ok":             self.ok,
            "flags":          [f.to_dict() for f in self.flags],
        }


@dataclass
class EnvironmentScaleReviewResult:
    """Complete scale review for an environment population."""
    environment:     str
    total_assets:    int = 0
    passed:          int = 0
    failed:          int = 0
    scale_outliers:  int = 0
    role_outliers:   int = 0
    env_outliers:    int = 0
    normalization_detected: bool = False
    score:           float = 1.0
    grade:           str   = "A"
    production_ready: bool = True
    findings:        List[str] = field(default_factory=list)
    reports:         List[AssetScaleReport] = field(default_factory=list)
    errors:          List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "environment":             self.environment,
            "total_assets":            self.total_assets,
            "passed":                  self.passed,
            "failed":                  self.failed,
            "scale_outliers":          self.scale_outliers,
            "role_outliers":           self.role_outliers,
            "env_outliers":            self.env_outliers,
            "normalization_detected":  self.normalization_detected,
            "score":                   round(self.score, 4),
            "grade":                   self.grade,
            "production_ready":        self.production_ready,
            "findings":                list(self.findings),
            "reports":                 [r.to_dict() for r in self.reports],
            "errors":                  list(self.errors),
        }


# ---------------------------------------------------------------------------
# Review engine
# ---------------------------------------------------------------------------

class EnvironmentScaleReview:
    """
    Reviews dimensional plausibility of every asset in a populated environment.

    Typical usage:
        review = get_environment_scale_review()
        result = review.review(assets, environment="western_room")
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def review(
        self,
        assets: List[Dict[str, Any]],
        environment: str = "",
    ) -> EnvironmentScaleReviewResult:
        """
        Review asset scale plausibility.

        Each asset dict should contain at least:
          - asset_id / name
          - placement_type
          - height_m  (or bbox_y)
          - role        (optional)

        Never raises.
        """
        try:
            return self._review(assets, environment)
        except Exception as exc:
            return EnvironmentScaleReviewResult(
                environment=environment,
                score=0.0,
                grade="F",
                production_ready=False,
                findings=["Review failed due to internal error."],
                errors=[str(exc)],
            )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _review(
        self,
        assets: List[Dict[str, Any]],
        environment: str,
    ) -> EnvironmentScaleReviewResult:
        env = environment.lower().strip()
        result = EnvironmentScaleReviewResult(environment=environment, total_assets=len(assets))

        if not assets:
            result.score = 0.0
            result.grade = "F"
            result.production_ready = False
            result.findings.append("no assets — environment is empty")
            return result

        reports: List[AssetScaleReport] = []
        for asset in assets:
            rep = self._check_asset(asset, env)
            reports.append(rep)
            if rep.ok:
                result.passed += 1
            else:
                result.failed += 1
                for flag in rep.flags:
                    if flag.flag_type == "SCALE_OUTLIER":
                        result.scale_outliers += 1
                    elif flag.flag_type == "ROLE_OUTLIER":
                        result.role_outliers += 1
                    elif flag.flag_type == "ENVIRONMENT_OUTLIER":
                        result.env_outliers += 1

        result.reports = reports

        # Detect 2m-normalisation cluster
        near_two = sum(
            1 for r in reports
            if abs(r.height_m - _NORM_TARGET_M) / _NORM_TARGET_M <= _NORM_TOLERANCE
            and r.height_m > 0.0
        )
        if near_two >= max(2, int(len(assets) * _NORM_CLUSTER_FRACTION)):
            result.normalization_detected = True
            result.findings.append(
                f"2m-normalization detected — {near_two}/{len(assets)} assets "
                f"cluster near {_NORM_TARGET_M}m. Import scale not corrected."
            )

        # Build score
        if result.total_assets > 0:
            fail_rate = result.failed / result.total_assets
            norm_penalty = 0.40 if result.normalization_detected else 0.0
            result.score = max(0.0, 1.0 - fail_rate * 0.6 - norm_penalty)
        else:
            result.score = 0.0

        # Collect blocking findings from individual flags
        for rep in reports:
            for flag in rep.flags:
                if flag.flag_type == "SCALE_OUTLIER":
                    result.findings.append(
                        f"SCALE_OUTLIER [{rep.asset_id}]: {flag.message}"
                    )

        # Grade
        result.grade, result.production_ready = self._grade(result.score)

        # Hard blocks
        if result.normalization_detected:
            result.production_ready = False

        return result

    def _check_asset(self, asset: Dict[str, Any], env: str) -> AssetScaleReport:
        asset_id   = str(asset.get("asset_id") or asset.get("name") or "unknown")
        asset_name = str(asset.get("name") or asset_id)
        pt         = str(asset.get("placement_type") or "").lower().strip()
        role       = str(asset.get("role") or "").lower().strip()
        height_m   = self._get_height(asset)

        expected_role = _PT_TO_ROLE.get(pt, "")
        lo, hi = _HEIGHT_RANGES.get(pt, (0.0, 0.0))

        report = AssetScaleReport(
            asset_id=asset_id, asset_name=asset_name,
            placement_type=pt, height_m=height_m,
            expected_min_m=lo, expected_max_m=hi,
            declared_role=role, expected_role=expected_role,
        )

        # SCALE_OUTLIER check (skip structural types)
        if pt not in _STRUCTURAL_TYPES and lo > 0 and hi > 0 and height_m > 0:
            if height_m > hi * _UPPER_OUTLIER_FACTOR:
                report.flags.append(ScaleFlag(
                    flag_type="SCALE_OUTLIER",
                    asset_id=asset_id,
                    message=(
                        f"{pt} height {height_m:.3f}m is "
                        f"{height_m / hi:.1f}× above expected max {hi}m. "
                        "Likely 2m-normalization artifact."
                    ),
                ))
            elif height_m < lo * _LOWER_OUTLIER_FACTOR:
                report.flags.append(ScaleFlag(
                    flag_type="SCALE_OUTLIER",
                    asset_id=asset_id,
                    message=(
                        f"{pt} height {height_m:.3f}m is below minimum "
                        f"threshold {lo * _LOWER_OUTLIER_FACTOR:.3f}m."
                    ),
                ))

        # ROLE_OUTLIER check
        if role and expected_role and role != expected_role:
            if not (pt in _STRUCTURAL_TYPES and role == "structure"):
                report.flags.append(ScaleFlag(
                    flag_type="ROLE_OUTLIER",
                    asset_id=asset_id,
                    message=(
                        f"placement_type='{pt}' expects role='{expected_role}' "
                        f"but asset declares role='{role}'."
                    ),
                ))

        # ENVIRONMENT_OUTLIER check
        if env and env in _ENV_EXPECTED and pt:
            if pt not in _ENV_EXPECTED[env] and pt not in _STRUCTURAL_TYPES:
                report.flags.append(ScaleFlag(
                    flag_type="ENVIRONMENT_OUTLIER",
                    asset_id=asset_id,
                    message=(
                        f"'{pt}' is not a typical asset type for '{env}'."
                    ),
                ))

        return report

    @staticmethod
    def _get_height(asset: Dict[str, Any]) -> float:
        for key in ("height_m", "bbox_y", "h", "height"):
            v = asset.get(key)
            if v is not None:
                try:
                    return float(v)
                except (TypeError, ValueError):
                    pass
        return 0.0

    @staticmethod
    def _grade(score: float) -> Tuple[str, bool]:
        if score >= 0.90:
            return "A", True
        if score >= 0.75:
            return "B", True
        if score >= 0.55:
            return "C", False
        if score >= 0.40:
            return "D", False
        return "F", False


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[EnvironmentScaleReview] = None
_LOCK = threading.Lock()


def get_environment_scale_review() -> EnvironmentScaleReview:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = EnvironmentScaleReview()
        return _INSTANCE


def reset_environment_scale_review_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
