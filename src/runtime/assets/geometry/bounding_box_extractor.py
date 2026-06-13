"""
Geometry Bounding Box Extractor (Tier 9.7 — Geometry Intelligence)
===================================================================
Extracts bounding box information from asset metadata using a priority chain
that prefers explicit geometry data over estimates.

Priority chain:
  1. Explicit bbox_min / bbox_max vectors in asset metadata
  2. bounding_box dict with min/max keys
  3. extent list (USD format)  [[min_x,y,z], [max_x,y,z]]
  4. aabb or mesh_bounds dict
  5. dimensions / size dict with w/h/d keys
  6. bbox_x / bbox_y / bbox_z scalar fields (Tier 9.4/9.6 format)
  7. GLTF accessor bounds (gltf_bbox, gltf_bounds, gltf_extent)
  8. Placement-type dimension tables
  9. Category dimension tables
 10. Generic fallback (1.0 × 1.0 × 1.0 m)

Unit normalization is applied at every step. The geometry layer converts
all values to meters before returning.

DESIGN RULES:
  1. No bridge calls. No Houdini imports.
  2. Deterministic — same asset dict → same result.
  3. Never raises.
  4. Singleton pattern.

Public API:
    GeometryBBoxExtractor
    get_geometry_bbox_extractor()
    reset_geometry_bbox_extractor_for_tests()
"""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional, Tuple

# Unit conversion factors to meters
_UNIT_TO_METERS: Dict[str, float] = {
    "m":           1.0,
    "meters":      1.0,
    "meter":       1.0,
    "cm":          0.01,
    "centimeters": 0.01,
    "centimeter":  0.01,
    "mm":          0.001,
    "millimeters": 0.001,
    "millimeter":  0.001,
    "in":          0.0254,
    "inch":        0.0254,
    "inches":      0.0254,
    "ft":          0.3048,
    "feet":        0.3048,
    "foot":        0.3048,
}

# Heuristic: if any raw bbox dimension exceeds this threshold, assume centimeters
_CM_HEURISTIC_THRESHOLD = 10.0

# Placement-type default dimensions [width, height, depth] in meters
_PLACEMENT_TYPE_DIMS: Dict[str, Tuple[float, float, float]] = {
    "table":         (1.20, 0.75, 0.80),
    "desk":          (1.40, 0.76, 0.70),
    "workbench":     (1.80, 0.90, 0.75),
    "chair":         (0.55, 0.90, 0.55),
    "stool":         (0.38, 0.65, 0.38),
    "bench":         (1.50, 0.50, 0.45),
    "cabinet":       (0.90, 1.80, 0.50),
    "shelf":         (0.90, 1.80, 0.35),
    "server_rack":   (0.60, 2.00, 1.00),
    "rack":          (0.60, 2.00, 0.80),
    "machine":       (2.50, 2.00, 2.00),
    "large_machine": (4.00, 3.00, 3.00),
    "industrial_machine": (3.50, 2.50, 2.50),
    "crane":         (3.00, 8.00, 3.00),
    "reactor":       (2.00, 3.00, 2.00),
    "engine":        (2.00, 1.50, 1.20),
    "vehicle":       (4.50, 1.80, 2.00),
    "door":          (0.90, 2.10, 0.10),
    "window":        (1.20, 1.50, 0.15),
    "wall":          (5.00, 3.00, 0.25),
    "column":        (0.40, 3.00, 0.40),
    "beam":          (4.00, 0.30, 0.30),
    "platform":      (3.00, 0.20, 3.00),
    "barrel":        (0.55, 0.90, 0.55),
    "crate":         (0.80, 0.80, 0.80),
    "pallet":        (1.20, 0.15, 1.00),
    "bucket":        (0.30, 0.38, 0.30),
    "lantern":       (0.25, 0.40, 0.25),
    "sofa":          (2.00, 0.95, 0.85),
    "bed":           (1.60, 0.60, 2.00),
    "wardrobe":      (1.20, 2.00, 0.60),
    "counter":       (2.50, 0.90, 0.70),
    "bar_counter":   (3.00, 1.10, 0.65),
    "console":       (1.50, 0.75, 0.60),
    "display_case":  (1.20, 1.80, 0.50),
    "terrain":       (10.0, 0.50, 10.0),
    "tree":          (2.00, 5.00, 2.00),
    "plant":         (0.50, 0.80, 0.50),
    "vehicle_small": (3.00, 1.50, 1.50),
}

# Category fallback dimensions [width, height, depth] in meters
_CATEGORY_DIMS: Dict[str, Tuple[float, float, float]] = {
    "furniture":     (1.00, 0.90, 0.70),
    "seating":       (0.55, 0.90, 0.55),
    "storage":       (0.90, 1.60, 0.50),
    "vehicle":       (4.50, 1.80, 2.00),
    "character":     (0.50, 1.80, 0.30),
    "structure":     (3.00, 3.00, 0.25),
    "architectural": (3.00, 2.50, 0.20),
    "prop":          (0.40, 0.50, 0.40),
    "container":     (0.60, 0.80, 0.60),
    "electronic":    (0.40, 0.40, 0.20),
    "industrial":    (2.00, 2.00, 1.50),
    "vegetation":    (1.50, 3.00, 1.50),
    "terrain":       (10.0, 0.50, 10.0),
    "lighting":      (0.30, 0.50, 0.30),
    "signage":       (0.80, 1.20, 0.05),
}

_GENERIC_FALLBACK: Tuple[float, float, float] = (1.0, 1.0, 1.0)


class GeometryBBoxExtractor:
    """
    Extracts bounding box from asset metadata.

    Returns a result dict:
    {
        "width_m":  float,
        "height_m": float,
        "depth_m":  float,
        "bbox_min": [x, y, z],
        "bbox_max": [x, y, z],
        "source":   "explicit" | "format_metadata" | "estimated",
        "source_unit": str,
        "warnings": [str],
    }
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def extract(self, asset: Dict[str, Any]) -> Dict[str, Any]:
        """Extract bounding box. Never raises."""
        try:
            return self._extract(asset)
        except Exception as exc:
            return self._fallback_result(asset, warning=f"BBox extraction error: {exc}")

    def _extract(self, asset: Dict[str, Any]) -> Dict[str, Any]:
        warnings: List[str] = []
        pt = str(asset.get("placement_type") or "").lower().strip()
        cat = str(asset.get("category") or "").lower().strip()

        # Detect source unit
        source_unit = self._detect_unit(asset)

        # --- Priority 1: explicit bbox_min / bbox_max ---
        bbox_min_raw = asset.get("bbox_min")
        bbox_max_raw = asset.get("bbox_max")
        if bbox_min_raw and bbox_max_raw:
            try:
                mn = [float(v) for v in bbox_min_raw]
                mx = [float(v) for v in bbox_max_raw]
                if len(mn) == 3 and len(mx) == 3:
                    w_raw = abs(mx[0] - mn[0])
                    h_raw = abs(mx[1] - mn[1])
                    d_raw = abs(mx[2] - mn[2])
                    factor = _UNIT_TO_METERS.get(source_unit, 1.0)
                    return self._make_result(
                        w_raw * factor, h_raw * factor, d_raw * factor,
                        [v * factor for v in mn], [v * factor for v in mx],
                        source="explicit", source_unit=source_unit, warnings=warnings
                    )
            except (TypeError, ValueError):
                pass

        # --- Priority 2: bounding_box dict ---
        bb = asset.get("bounding_box")
        if isinstance(bb, dict):
            result = self._from_minmax_dict(bb, source_unit, warnings)
            if result:
                return result

        # --- Priority 3: USD extent list [[min],[max]] ---
        ext = asset.get("extent")
        if isinstance(ext, (list, tuple)) and len(ext) == 2:
            try:
                mn = [float(v) for v in ext[0]]
                mx = [float(v) for v in ext[1]]
                if len(mn) == 3 and len(mx) == 3:
                    factor = _UNIT_TO_METERS.get(source_unit, 1.0)
                    w = abs(mx[0] - mn[0]) * factor
                    h = abs(mx[1] - mn[1]) * factor
                    d = abs(mx[2] - mn[2]) * factor
                    return self._make_result(
                        w, h, d,
                        [v * factor for v in mn], [v * factor for v in mx],
                        source="format_metadata", source_unit=source_unit, warnings=warnings
                    )
            except (TypeError, ValueError):
                pass

        # --- Priority 4: aabb or mesh_bounds dict ---
        for key in ("aabb", "mesh_bounds", "world_bounds"):
            bb2 = asset.get(key)
            if isinstance(bb2, dict):
                result = self._from_minmax_dict(bb2, source_unit, warnings)
                if result:
                    result["source"] = "format_metadata"
                    return result

        # --- Priority 5: dimensions / size dict ---
        dims = asset.get("dimensions") or asset.get("size")
        if isinstance(dims, dict):
            result = self._from_dimensions_dict(dims, source_unit, warnings)
            if result:
                return result

        # --- Priority 6: GLTF-specific bounds ---
        for key in ("gltf_bbox", "gltf_bounds", "gltf_extent"):
            gltf = asset.get(key)
            if isinstance(gltf, dict):
                result = self._from_minmax_dict(gltf, source_unit, warnings)
                if result:
                    result["source"] = "format_metadata"
                    return result

        # --- Priority 7: scalar bbox_x / bbox_y / bbox_z ---
        bx = asset.get("bbox_x")
        by = asset.get("bbox_y")
        bz = asset.get("bbox_z")
        if bx or by or bz:
            bx_raw = float(bx or 0)
            by_raw = float(by or 0)
            bz_raw = float(bz or 0)
            factor = _UNIT_TO_METERS.get(source_unit, 1.0)
            bx_m = bx_raw * factor or 1.0
            by_m = by_raw * factor or 1.0
            bz_m = bz_raw * factor or 1.0
            return self._make_result(
                bx_m, by_m, bz_m,
                [0.0, 0.0, 0.0], [bx_m, by_m, bz_m],
                source="estimated", source_unit=source_unit, warnings=warnings
            )

        # --- Priority 8: width / height / depth scalars ---
        w_s = asset.get("width") or asset.get("w")
        h_s = asset.get("height") or asset.get("h")
        d_s = asset.get("depth") or asset.get("d")
        if w_s or h_s or d_s:
            factor = _UNIT_TO_METERS.get(source_unit, 1.0)
            w_m = float(w_s or 1.0) * factor
            h_m = float(h_s or 1.0) * factor
            d_m = float(d_s or 1.0) * factor
            return self._make_result(
                w_m, h_m, d_m,
                [0.0, 0.0, 0.0], [w_m, h_m, d_m],
                source="estimated", source_unit=source_unit, warnings=warnings
            )

        # --- Priority 9: placement-type dimension table ---
        if pt in _PLACEMENT_TYPE_DIMS:
            w, h, d = _PLACEMENT_TYPE_DIMS[pt]
            warnings.append(f"Using placement-type default dimensions for '{pt}'.")
            return self._make_result(
                w, h, d, [0.0, 0.0, 0.0], [w, h, d],
                source="estimated", source_unit="meters", warnings=warnings
            )

        # --- Priority 10: category dimension table ---
        if cat in _CATEGORY_DIMS:
            w, h, d = _CATEGORY_DIMS[cat]
            warnings.append(f"Using category default dimensions for '{cat}'.")
            return self._make_result(
                w, h, d, [0.0, 0.0, 0.0], [w, h, d],
                source="estimated", source_unit="meters", warnings=warnings
            )

        # --- Fallback ---
        warnings.append("No geometry data found — using 1×1×1 m fallback.")
        w, h, d = _GENERIC_FALLBACK
        return self._make_result(
            w, h, d, [0.0, 0.0, 0.0], [w, h, d],
            source="estimated", source_unit="meters", warnings=warnings
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _detect_unit(self, asset: Dict[str, Any]) -> str:
        for key in ("unit", "unit_system", "units", "bbox_unit", "source_unit"):
            val = str(asset.get(key) or "").lower().strip()
            if val in _UNIT_TO_METERS:
                return val

        # Heuristic: large raw values suggest centimeters
        for key in ("bbox_x", "bbox_y", "bbox_z", "width", "height", "depth"):
            v = asset.get(key)
            if v and float(v) > _CM_HEURISTIC_THRESHOLD:
                return "cm"

        return "meters"

    def _from_minmax_dict(
        self,
        d: Dict[str, Any],
        source_unit: str,
        warnings: List[str],
    ) -> Optional[Dict[str, Any]]:
        for mk, xk in (("min", "max"), ("minimum", "maximum"), ("lower", "upper")):
            mn_raw = d.get(mk)
            mx_raw = d.get(xk)
            if mn_raw and mx_raw:
                try:
                    mn = [float(v) for v in mn_raw]
                    mx = [float(v) for v in mx_raw]
                    if len(mn) == 3 and len(mx) == 3:
                        factor = _UNIT_TO_METERS.get(source_unit, 1.0)
                        w = abs(mx[0] - mn[0]) * factor
                        h = abs(mx[1] - mn[1]) * factor
                        d_ = abs(mx[2] - mn[2]) * factor
                        return self._make_result(
                            w, h, d_,
                            [v * factor for v in mn], [v * factor for v in mx],
                            source="explicit", source_unit=source_unit, warnings=warnings
                        )
                except (TypeError, ValueError):
                    pass
        # Try size/extents sub-keys
        center = d.get("center")
        extents = d.get("extents") or d.get("half_extents")
        if center and extents:
            try:
                cx, cy, cz = float(center[0]), float(center[1]), float(center[2])
                ex, ey, ez = float(extents[0]), float(extents[1]), float(extents[2])
                factor = _UNIT_TO_METERS.get(source_unit, 1.0)
                # half_extents vs full extents heuristic: if key says "half" use as-is
                if "half" in str(d.get("extents_type", "")):
                    ex, ey, ez = ex * 2, ey * 2, ez * 2
                else:
                    pass  # already full extents
                w = ex * factor
                h = ey * factor
                d_ = ez * factor
                return self._make_result(
                    w, h, d_,
                    [(cx - ex / 2) * factor, (cy - ey / 2) * factor, (cz - ez / 2) * factor],
                    [(cx + ex / 2) * factor, (cy + ey / 2) * factor, (cz + ez / 2) * factor],
                    source="explicit", source_unit=source_unit, warnings=warnings
                )
            except (TypeError, ValueError, IndexError):
                pass
        return None

    def _from_dimensions_dict(
        self,
        d: Dict[str, Any],
        source_unit: str,
        warnings: List[str],
    ) -> Optional[Dict[str, Any]]:
        w_raw = d.get("width") or d.get("w") or d.get("x")
        h_raw = d.get("height") or d.get("h") or d.get("y")
        dep_raw = d.get("depth") or d.get("d") or d.get("z")
        if not (w_raw or h_raw or dep_raw):
            return None
        try:
            factor = _UNIT_TO_METERS.get(source_unit, 1.0)
            w = float(w_raw or 1.0) * factor
            h = float(h_raw or 1.0) * factor
            dep = float(dep_raw or 1.0) * factor
            return self._make_result(
                w, h, dep,
                [0.0, 0.0, 0.0], [w, h, dep],
                source="explicit", source_unit=source_unit, warnings=warnings
            )
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _make_result(
        w: float, h: float, d: float,
        bbox_min: List[float], bbox_max: List[float],
        source: str, source_unit: str, warnings: List[str],
    ) -> Dict[str, Any]:
        # Clamp to sane minimums
        w = max(w, 0.001)
        h = max(h, 0.001)
        d = max(d, 0.001)
        return {
            "width_m":    w,
            "height_m":   h,
            "depth_m":    d,
            "bbox_min":   bbox_min,
            "bbox_max":   bbox_max,
            "source":     source,
            "source_unit": source_unit,
            "warnings":   list(warnings),
        }

    # ------------------------------------------------------------------
    # Cooked-geometry entry point (highest priority source)
    # ------------------------------------------------------------------

    def from_houdini_bbox(
        self,
        houdini_bbox: Dict[str, Any],
        import_scale: float,
    ) -> Dict[str, Any]:
        """
        Build a world-space bbox result from a Houdini geometry bounding box.

        houdini_bbox is the dict returned by _get_bbox() in mcp_tool_registry
        (keys: "size" [w,h,d], "center" [cx,cy,cz], "min" [min_x,min_y,min_z]
        — all in SOP-space units before the geo-node scale is applied).

        import_scale is the value from RealWorldScaleResolver (e.g. 0.01 for
        Megascans cm-space FBX).  Multiplying SOP-space by import_scale gives
        real-world meters.

        Returns the standard bbox result dict with "source": "cooked_geometry".
        """
        try:
            size = houdini_bbox.get("size") or []
            mn   = houdini_bbox.get("min") or []
            if not size or len(size) < 3:
                return self._fallback_result({}, "Houdini bbox has no size data.")
            w_raw, h_raw, d_raw = float(size[0]), float(size[1]), float(size[2])
            w_m = max(w_raw * import_scale, 0.001)
            h_m = max(h_raw * import_scale, 0.001)
            d_m = max(d_raw * import_scale, 0.001)
            if len(mn) == 3:
                bbox_min_m = [float(v) * import_scale for v in mn]
            else:
                bbox_min_m = [0.0, 0.0, 0.0]
            bbox_max_m = [bbox_min_m[0] + w_m, bbox_min_m[1] + h_m, bbox_min_m[2] + d_m]
            return self._make_result(
                w_m, h_m, d_m, bbox_min_m, bbox_max_m,
                source="cooked_geometry",
                source_unit="meters",
                warnings=[],
            )
        except Exception as exc:
            return self._fallback_result({}, f"from_houdini_bbox error: {exc}")

    def _fallback_result(self, asset: Dict[str, Any], warning: str = "") -> Dict[str, Any]:
        w, h, d = _GENERIC_FALLBACK
        warns = [warning] if warning else ["BBox extraction failed — using 1×1×1 m fallback."]
        return self._make_result(
            w, h, d, [0.0, 0.0, 0.0], [w, h, d],
            source="estimated", source_unit="meters", warnings=warns
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[GeometryBBoxExtractor] = None
_LOCK = threading.Lock()


def get_geometry_bbox_extractor() -> GeometryBBoxExtractor:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = GeometryBBoxExtractor()
        return _INSTANCE


def reset_geometry_bbox_extractor_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
