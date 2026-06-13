"""
Geometry Analyzer (Tier 9.7 — Geometry Intelligence)
====================================================
Main orchestrator for geometry intelligence. Produces a complete
GeometryAnalysisResult by coordinating all detectors.

This is the public entry point for any system that needs reliable
asset geometry — placement, environment construction, lookdev,
lighting, and cinematic systems.

Methods:
  analyze_asset(asset)            → GeometryAnalysisResult
  build_metrics(asset)            → AssetMetrics
  extract_geometry_information(asset) → Dict[str, Any]

DESIGN RULES:
  1. No bridge calls. No Houdini imports.
  2. Deterministic — same asset dict → same result.
  3. Never raises in public methods.
  4. Singleton pattern.

Public API:
    GeometryAnalysisResult
    GeometryAnalyzer
    get_geometry_analyzer()
    reset_geometry_analyzer_for_tests()
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.runtime.assets.geometry.asset_metrics import (
    AssetMetrics,
    get_asset_metrics_builder,
)


@dataclass
class GeometryAnalysisResult:
    """Full geometry intelligence output for one asset."""

    analysis_id:     str   = field(default_factory=lambda: f"geo_{uuid.uuid4().hex[:10]}")
    asset_id:        str   = ""
    asset_name:      str   = ""

    # Core geometry
    metrics:         Optional[AssetMetrics] = None

    # Summary values (mirrored from metrics for quick access)
    width_m:         float = 1.0
    height_m:        float = 1.0
    depth_m:         float = 1.0
    volume_m3:       float = 1.0
    footprint_m2:    float = 1.0
    placement_radius: float = 0.5

    pivot_type:      str   = "bottom_center"
    scale_class:     str   = "medium"
    role:            str   = "prop"
    is_structural:   bool  = False
    is_hero:         bool  = False

    surface_count:   int   = 0
    contact_count:   int   = 0

    source:          str   = "estimated"
    ok:              bool  = True

    errors:          List[str] = field(default_factory=list)
    warnings:        List[str] = field(default_factory=list)
    generated_at:    float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "analysis_id":      self.analysis_id,
            "asset_id":         self.asset_id,
            "asset_name":       self.asset_name,
            "metrics":          self.metrics.to_dict() if self.metrics else None,
            "width_m":          self.width_m,
            "height_m":         self.height_m,
            "depth_m":          self.depth_m,
            "volume_m3":        self.volume_m3,
            "footprint_m2":     self.footprint_m2,
            "placement_radius": self.placement_radius,
            "pivot_type":       self.pivot_type,
            "scale_class":      self.scale_class,
            "role":             self.role,
            "is_structural":    self.is_structural,
            "is_hero":          self.is_hero,
            "surface_count":    self.surface_count,
            "contact_count":    self.contact_count,
            "source":           self.source,
            "ok":               self.ok,
            "errors":           list(self.errors),
            "warnings":         list(self.warnings),
            "generated_at":     self.generated_at,
        }


class GeometryAnalyzer:
    """
    Orchestrates geometry intelligence for asset imports.

    Usage:
        result = get_geometry_analyzer().analyze_asset(asset_dict)
        metrics = result.metrics   # AssetMetrics instance
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._analyze_count: int = 0

    def analyze_asset(self, asset: Dict[str, Any]) -> GeometryAnalysisResult:
        """
        Full geometry analysis for one asset.

        Args:
            asset: asset metadata dict. May contain any combination of geometry
                   fields — the system uses what is available and falls back
                   gracefully when data is missing.

        Returns:
            GeometryAnalysisResult. Never raises.
        """
        try:
            return self._analyze(asset)
        except Exception as exc:
            d = asset if isinstance(asset, dict) else {}
            return GeometryAnalysisResult(
                asset_id  = str(d.get("asset_id") or d.get("name") or ""),
                asset_name= str(d.get("name") or d.get("asset_id") or ""),
                ok        = False,
                errors    = [f"GeometryAnalyzer.analyze_asset failed: {exc}"],
            )

    def build_metrics(self, asset: Dict[str, Any]) -> AssetMetrics:
        """
        Build AssetMetrics for one asset.

        Convenience method that returns just the AssetMetrics without the
        full GeometryAnalysisResult wrapper. Never raises.
        """
        result = self.analyze_asset(asset)
        if result.metrics is not None:
            return result.metrics
        # Fallback
        m = AssetMetrics(
            asset_id   = str(asset.get("asset_id") or asset.get("name") or ""),
            asset_name = str(asset.get("name") or asset.get("asset_id") or ""),
        )
        m.errors.extend(result.errors)
        return m

    def extract_geometry_information(self, asset: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract structured geometry information as a plain dict.

        Returns a dict suitable for logging, serialization, or node output.
        Never raises.
        """
        result = self.analyze_asset(asset)
        info: Dict[str, Any] = {
            "asset_id":         result.asset_id,
            "dimensions_m": {
                "width":  result.width_m,
                "height": result.height_m,
                "depth":  result.depth_m,
            },
            "volume_m3":        result.volume_m3,
            "footprint_m2":     result.footprint_m2,
            "placement_radius": result.placement_radius,
            "pivot_type":       result.pivot_type,
            "scale_class":      result.scale_class,
            "role":             result.role,
            "is_structural":    result.is_structural,
            "is_hero":          result.is_hero,
            "source":           result.source,
            "surface_count":    result.surface_count,
            "contact_count":    result.contact_count,
        }
        if result.metrics:
            info["bbox_min"] = result.metrics.bbox_min
            info["bbox_max"] = result.metrics.bbox_max
            info["support_surfaces"] = [s.to_dict() for s in result.metrics.support_surfaces]
            info["ground_contacts"]  = [c.to_dict() for c in result.metrics.ground_contacts]
        return info

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _analyze(self, asset: Dict[str, Any]) -> GeometryAnalysisResult:
        with self._lock:
            self._analyze_count += 1

        metrics = get_asset_metrics_builder().build(asset)

        result = GeometryAnalysisResult(
            asset_id         = metrics.asset_id,
            asset_name       = metrics.asset_name,
            metrics          = metrics,
            width_m          = metrics.width_m,
            height_m         = metrics.height_m,
            depth_m          = metrics.depth_m,
            volume_m3        = metrics.volume_m3,
            footprint_m2     = metrics.footprint_m2,
            placement_radius = metrics.placement_radius,
            pivot_type       = metrics.pivot_type,
            scale_class      = metrics.scale_class,
            role             = metrics.role,
            is_structural    = metrics.is_structural,
            is_hero          = metrics.is_hero,
            surface_count    = len(metrics.support_surfaces),
            contact_count    = sum(c.count for c in metrics.ground_contacts),
            source           = metrics.source,
            ok               = not bool(metrics.errors),
            errors           = list(metrics.errors),
            warnings         = list(metrics.warnings),
        )
        return result

    @property
    def analyze_count(self) -> int:
        return self._analyze_count


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[GeometryAnalyzer] = None
_LOCK = threading.Lock()


def get_geometry_analyzer() -> GeometryAnalyzer:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = GeometryAnalyzer()
        return _INSTANCE


def reset_geometry_analyzer_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
