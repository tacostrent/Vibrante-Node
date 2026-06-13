"""
Structural Asset Classifier (Tier 10.3 — Structural Asset Classification)
=========================================================================
Main entry point.  Combines three classification signals:
  1. Geometry — bounding-box dimensions (GeometryRoleDetector)
  2. Metadata — name/tags/category keywords (MetadataRoleClassifier)
  3. Environment — context-aware affinity (EnvironmentStructuralAffinity)

The highest-confidence signal wins.  Metadata overrides geometry when
keyword confidence is ≥ 0.80.  Environment adjusts the winner's confidence.

DESIGN RULES:
  1. No bridge calls.
  2. Deterministic — same inputs → same result.
  3. Never raises in public methods.
  4. Singleton pattern.

Public API:
    StructuralClassificationResult
    StructuralAssetClassifier
    get_structural_asset_classifier()
    reset_structural_asset_classifier_for_tests()
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.runtime.structure.geometry_role_detector import (
    get_geometry_role_detector,
)
from src.runtime.structure.metadata_role_classifier import (
    get_metadata_role_classifier,
)
from src.runtime.structure.environment_structural_affinity import (
    get_environment_structural_affinity,
)
from src.runtime.structure.structural_placement_rules import (
    STRUCTURAL_ROLES,
    get_structural_placement_rules,
    PlacementIntent,
)


# ──────────────────────────────────────────────────────────────────────────────
# All valid structural roles
# ──────────────────────────────────────────────────────────────────────────────

ALL_STRUCTURAL_ROLES: frozenset = frozenset({
    "furniture", "prop", "decoration",
    "wall", "wall_segment", "doorway", "door_frame",
    "window", "window_frame", "fireplace",
    "beam", "support_beam", "column",
    "floor_piece", "ceiling_piece",
    "stair", "railing", "archway",
    "architectural_module", "structural_unknown",
})

# Metadata confidence must reach this to override geometry
_METADATA_OVERRIDE_THRESHOLD = 0.80

# Minimum confidence for production_ready classification
_PRODUCTION_CONFIDENCE = 0.65


@dataclass
class StructuralClassificationResult:
    """Full structural classification output for one asset."""

    classification_id:    str   = field(default_factory=lambda: f"sc_{uuid.uuid4().hex[:10]}")
    asset_id:             str   = ""
    asset_name:           str   = ""

    structural_role:      str   = "structural_unknown"
    confidence:           float = 0.0
    classification_source: str  = "none"    # "geometry", "metadata", "combined", "placement_type"
    supporting_features:  List[str] = field(default_factory=list)

    # Convenience flags
    is_structural:            bool = False
    route_to_structure_builder: bool = False
    placement_intent:         Optional[PlacementIntent] = None

    # Per-signal detail (for debugging)
    geometry_role:        str   = ""
    geometry_confidence:  float = 0.0
    metadata_role:        str   = ""
    metadata_confidence:  float = 0.0
    environment_adjusted: bool  = False

    ok:               bool      = True
    errors:           List[str] = field(default_factory=list)
    generated_at:     float     = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "classification_id":      self.classification_id,
            "asset_id":               self.asset_id,
            "asset_name":             self.asset_name,
            "structural_role":        self.structural_role,
            "confidence":             self.confidence,
            "classification_source":  self.classification_source,
            "supporting_features":    list(self.supporting_features),
            "is_structural":          self.is_structural,
            "route_to_structure_builder": self.route_to_structure_builder,
            "placement_intent":       self.placement_intent.to_dict() if self.placement_intent else None,
            "geometry_role":          self.geometry_role,
            "geometry_confidence":    self.geometry_confidence,
            "metadata_role":          self.metadata_role,
            "metadata_confidence":    self.metadata_confidence,
            "environment_adjusted":   self.environment_adjusted,
            "ok":                     self.ok,
            "errors":                 list(self.errors),
            "generated_at":           self.generated_at,
        }


class StructuralAssetClassifier:
    """
    Classifies an asset's structural role using geometry, metadata, and
    environment context.

    Usage:
        classifier = get_structural_asset_classifier()
        result = classifier.classify(asset_dict)
        result = classifier.classify(asset_dict, environment="western_room")
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._classify_count = 0

    def classify(
        self,
        asset:       Dict[str, Any],
        environment: str = "",
    ) -> StructuralClassificationResult:
        """
        Classify one asset.

        Args:
            asset:       Asset metadata dict (name, tags, category, bbox fields, …)
            environment: Optional environment name — boosts/caps role confidence.

        Returns:
            StructuralClassificationResult.  Never raises.
        """
        try:
            return self._classify(asset, environment)
        except Exception as exc:
            d = asset if isinstance(asset, dict) else {}
            return StructuralClassificationResult(
                asset_id  = str(d.get("asset_id") or d.get("name") or ""),
                asset_name= str(d.get("name") or d.get("asset_id") or ""),
                structural_role = "structural_unknown",
                confidence      = 0.20,
                ok              = False,
                errors          = [f"StructuralAssetClassifier.classify failed: {exc}"],
            )

    def classify_batch(
        self,
        assets:      List[Dict[str, Any]],
        environment: str = "",
    ) -> List[StructuralClassificationResult]:
        """Classify a list of assets.  Never raises."""
        results = []
        for asset in assets:
            results.append(self.classify(asset, environment))
        return results

    # ──────────────────────────────────────────────────────────────────────
    # Internal
    # ──────────────────────────────────────────────────────────────────────

    def _classify(
        self,
        asset: Dict[str, Any],
        environment: str,
    ) -> StructuralClassificationResult:
        with self._lock:
            self._classify_count += 1

        asset_id   = str(asset.get("asset_id") or asset.get("name") or "")
        asset_name = str(asset.get("name") or asset.get("asset_id") or "")

        # ── Fast path: explicit placement_type override ────────────────────
        pt_role, pt_conf = self._from_placement_type(asset)

        # ── Signal 1: Geometry ─────────────────────────────────────────────
        w = float(asset.get("width_m") or asset.get("bbox_x") or 1.0)
        h = float(asset.get("height_m") or asset.get("bbox_y") or 1.0)
        d = float(asset.get("depth_m") or asset.get("bbox_z") or 1.0)
        geo_role, geo_conf = get_geometry_role_detector().detect(w, h, d)

        # ── Signal 2: Metadata ─────────────────────────────────────────────
        meta_role, meta_conf, meta_features = get_metadata_role_classifier().classify(asset)

        # ── Signal 3: Placement-type fast path (highest priority) ──────────
        if pt_role and pt_conf >= 0.85:
            winner_role = pt_role
            winner_conf = pt_conf
            source      = "placement_type"
            features    = [f"placement_type:{asset.get('placement_type', '')}"]
        elif meta_conf >= _METADATA_OVERRIDE_THRESHOLD:
            # Metadata keyword is strong — override geometry
            winner_role = meta_role
            winner_conf = meta_conf
            source      = "metadata"
            features    = meta_features
        elif meta_conf > geo_conf:
            # Metadata wins on confidence
            winner_role = meta_role
            winner_conf = meta_conf
            source      = "metadata"
            features    = meta_features
        else:
            winner_role = geo_role
            winner_conf = geo_conf
            source      = "geometry"
            features    = [f"dims:{w:.2f}x{h:.2f}x{d:.2f}m"]

        # ── Combine if both signals agree ──────────────────────────────────
        if (source not in ("placement_type",)
                and geo_role == meta_role
                and meta_conf > 0.0
                and geo_conf > 0.0):
            combined_conf = min(1.0, (geo_conf + meta_conf) / 2 + 0.05)
            winner_role  = geo_role
            winner_conf  = combined_conf
            source       = "combined"
            features     = [f"dims:{w:.2f}x{h:.2f}x{d:.2f}m"] + meta_features

        # ── Environment affinity adjustment ────────────────────────────────
        env_adjusted = False
        if environment:
            affinity     = get_environment_structural_affinity()
            adj_conf     = affinity.adjust(winner_role, winner_conf, environment)
            if abs(adj_conf - winner_conf) > 0.001:
                env_adjusted = True
                score = affinity.affinity_score(winner_role, environment)
                if score > 0:
                    features = features + [f"env_preferred:{environment}"]
                elif score < 0:
                    features = features + [f"env_irrelevant:{environment}"]
            winner_conf = adj_conf

        # ── Derive flags ───────────────────────────────────────────────────
        is_structural = winner_role in STRUCTURAL_ROLES
        rules         = get_structural_placement_rules()
        intent        = rules.get_intent(asset_id, winner_role)
        route_to_sb   = is_structural

        result = StructuralClassificationResult(
            asset_id              = asset_id,
            asset_name            = asset_name,
            structural_role       = winner_role,
            confidence            = round(winner_conf, 4),
            classification_source = source,
            supporting_features   = features,
            is_structural         = is_structural,
            route_to_structure_builder = route_to_sb,
            placement_intent      = intent,
            geometry_role         = geo_role,
            geometry_confidence   = round(geo_conf, 4),
            metadata_role         = meta_role,
            metadata_confidence   = round(meta_conf, 4),
            environment_adjusted  = env_adjusted,
        )
        return result

    @staticmethod
    def _from_placement_type(asset: Dict[str, Any]) -> tuple:
        """
        Map explicit placement_type to a structural role if it unambiguously
        implies one.  Returns (role, confidence) or ("", 0.0).
        """
        _PLACEMENT_STRUCTURAL_MAP = {
            "door":          ("doorway",              0.92),
            "door_frame":    ("door_frame",           0.92),
            "window":        ("window",               0.92),
            "window_frame":  ("window_frame",         0.92),
            "wall":          ("wall",                 0.92),
            "wall_panel":    ("wall_segment",         0.90),
            "floor_panel":   ("floor_piece",          0.90),
            "ceiling":       ("ceiling_piece",        0.90),
            "ceiling_panel": ("ceiling_piece",        0.88),
            "beam":          ("beam",                 0.92),
            "support_beam":  ("support_beam",         0.92),
            "column":        ("column",               0.92),
            "support_column":("column",               0.90),
            "arch":          ("archway",              0.88),
            "archway":       ("archway",              0.90),
            "stair":         ("stair",                0.90),
            "railing":       ("railing",              0.90),
            "fireplace":     ("fireplace",            0.92),
        }
        pt = str(asset.get("placement_type") or "").lower().strip()
        if pt in _PLACEMENT_STRUCTURAL_MAP:
            return _PLACEMENT_STRUCTURAL_MAP[pt]
        return ("", 0.0)

    @property
    def classify_count(self) -> int:
        return self._classify_count


# ──────────────────────────────────────────────────────────────────────────────
# Singleton
# ──────────────────────────────────────────────────────────────────────────────

_INSTANCE: Optional[StructuralAssetClassifier] = None
_LOCK = threading.Lock()


def get_structural_asset_classifier() -> StructuralAssetClassifier:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = StructuralAssetClassifier()
        return _INSTANCE


def reset_structural_asset_classifier_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
