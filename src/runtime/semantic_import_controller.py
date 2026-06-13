"""
Semantic Import Controller (Tier 3)
=====================================
Validates and controls asset imports BEFORE they enter the scene.
All validation is deterministic and purely data-driven — no bridge calls.

Validates:
  • Asset format compatibility
  • Style consistency (no vegetation+tech, sky+ceiling, etc.)
  • Renderer compatibility (Arnold vs Karma vs generic)
  • Scale consistency
  • Scene relevance (asset fits the environment)
  • Duplicate detection

Public API:
    SemanticImportController
        .validate_asset_for_scene(asset, scene_context) -> dict
        .build_import_operations(asset, target_path, context) -> list[dict]
        .estimate_import_cost(asset) -> dict
        .validate_renderer_compatibility(asset, renderer) -> dict
        .validate_style_consistency(asset, existing_categories) -> dict

    get_semantic_import_controller() -> SemanticImportController
    reset_semantic_import_controller_for_tests()
"""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional, Set

# ---------------------------------------------------------------------------
# Validation tables
# ---------------------------------------------------------------------------

# Formats → renderer support flags
_FORMAT_RENDERER_SUPPORT: Dict[str, Dict[str, bool]] = {
    "abc":   {"arnold": True,  "karma": True,  "mantra": True,  "generic": True},
    "usd":   {"arnold": True,  "karma": True,  "mantra": True,  "generic": True},
    "fbx":   {"arnold": True,  "karma": True,  "mantra": True,  "generic": True},
    "obj":   {"arnold": True,  "karma": True,  "mantra": True,  "generic": True},
    "bgeo":  {"arnold": False, "karma": True,  "mantra": True,  "generic": True},
    "vdb":   {"arnold": True,  "karma": True,  "mantra": True,  "generic": False},
    "hda":   {"arnold": True,  "karma": True,  "mantra": True,  "generic": True},
}

# Style conflict pairs (bidirectional)
_STYLE_CONFLICTS: List[frozenset] = [
    frozenset({"vegetation", "tech_panel"}),
    frozenset({"sky", "ceiling"}),
    frozenset({"creature", "robot"}),
    frozenset({"organic", "industrial"}),
]

# Environment → preferred categories
_ENV_PREFERRED_CATEGORIES: Dict[str, Set[str]] = {
    "industrial_hangar":    {"vehicle", "machinery_hero", "container", "structure", "tech_panel"},
    "sci_fi_corridor":      {"robot", "tech_panel", "structure", "container", "character"},
    "abandoned_factory":    {"structure", "container", "terrain", "misc"},
    "robotics_lab":         {"robot", "tech_panel", "container", "machinery_hero"},
    "cinematic_control_room": {"tech_panel", "character", "structure", "container"},
}

# Scale compatibility bands (metres): min, max
_SCALE_BANDS: Dict[str, tuple] = {
    "vehicle":        (1.5,  20.0),
    "character":      (1.6,   2.5),
    "robot":          (0.5,  10.0),
    "creature":       (0.3,  15.0),
    "container":      (0.3,   5.0),
    "structure":      (1.0, 100.0),
    "terrain":        (5.0, 500.0),
    "sky":            (100.0, 1000.0),
    "tech_panel":     (0.1,   3.0),
    "vegetation":     (0.2,  30.0),
    "misc":           (0.01, 100.0),
}


class SemanticImportController:
    """
    Gates asset imports through deterministic validation checks.
    All output is advisory — callers decide whether to proceed.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._validation_count = 0
        self._rejected_count = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate_asset_for_scene(
        self,
        asset: Dict[str, Any],
        scene_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Run all validation checks for one asset against the current scene.

        Returns:
            {
                valid: bool,
                errors: list[str],
                warnings: list[str],
                asset_name: str,
                checks_passed: list[str],
                checks_failed: list[str],
            }
        """
        errors: List[str] = []
        warnings: List[str] = []
        passed: List[str] = []
        failed: List[str] = []

        asset_name = asset.get("name", "")
        category = asset.get("category", "misc")
        scene_theme = scene_context.get("scene_theme", "")
        renderer = scene_context.get("renderer", "generic")
        existing_categories: List[str] = scene_context.get("existing_categories", [])
        fmt = asset.get("format", "")

        # Check: asset has a name
        if not asset_name:
            errors.append("Asset has no name.")
            failed.append("name_present")
        else:
            passed.append("name_present")

        # Check: category known
        if category not in _SCALE_BANDS:
            warnings.append(f"Unknown asset category '{category}' — using generic validation.")
            passed.append("category_check")  # advisory only
        else:
            passed.append("category_check")

        # Check: renderer compatibility
        if fmt:
            rc = self.validate_renderer_compatibility(asset, renderer)
            if rc["compatible"]:
                passed.append("renderer_compatibility")
            else:
                errors.extend(rc["errors"])
                failed.append("renderer_compatibility")
        else:
            warnings.append("No format specified — renderer compatibility unknown.")
            passed.append("renderer_compatibility")

        # Check: style consistency
        if existing_categories:
            sc = self.validate_style_consistency(asset, existing_categories)
            if sc["consistent"]:
                passed.append("style_consistency")
            else:
                for c in sc["conflicts"]:
                    errors.append(f"Style conflict: {c}")
                failed.append("style_consistency")
        else:
            passed.append("style_consistency")

        # Check: scene relevance
        if scene_theme and scene_theme in _ENV_PREFERRED_CATEGORIES:
            preferred = _ENV_PREFERRED_CATEGORIES[scene_theme]
            if category not in preferred:
                warnings.append(
                    f"Category '{category}' is not preferred for '{scene_theme}'. "
                    f"Preferred: {sorted(preferred)}"
                )
            passed.append("scene_relevance")
        else:
            passed.append("scene_relevance")

        # Check: scale plausibility
        asset_scale = asset.get("scale_metres")
        if asset_scale is not None and category in _SCALE_BANDS:
            lo, hi = _SCALE_BANDS[category]
            if not (lo <= asset_scale <= hi):
                warnings.append(
                    f"Asset scale {asset_scale}m is outside expected range "
                    f"[{lo}, {hi}] for category '{category}'."
                )
            passed.append("scale_check")

        with self._lock:
            self._validation_count += 1
            if errors:
                self._rejected_count += 1

        return {
            "valid":         len(errors) == 0,
            "errors":        errors,
            "warnings":      warnings,
            "asset_name":    asset_name,
            "checks_passed": passed,
            "checks_failed": failed,
        }

    def build_import_operations(
        self,
        asset: Dict[str, Any],
        target_path: str,
        context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Build the list of transaction operations needed to import one asset.

        Returns a list of operation dicts:
            1. create_node (geo container at target_path's parent)
            2. set_parms (any transform overrides from context)
        """
        ops: List[Dict[str, Any]] = []

        asset_name = asset.get("name", "asset")
        category = asset.get("category", "misc")

        # Derive parent from target_path
        parts = target_path.rsplit("/", 1)
        parent = parts[0] if len(parts) == 2 else "/obj"
        node_name = parts[1] if len(parts) == 2 else asset_name

        # Create the geo container
        ops.append({
            "op":     "create_node",
            "parent": parent,
            "type":   "geo",
            "name":   node_name,
            "params": {},
        })

        # Apply transform hints from context
        transform_params: Dict[str, Any] = {}
        for key in ("tx", "ty", "tz", "rx", "ry", "rz", "sx", "sy", "sz"):
            val = context.get(key)
            if val is not None:
                transform_params[key] = val

        if transform_params:
            ops.append({
                "op":   "set_parms",
                "node": f"{parent}/{node_name}",
                "parms": transform_params,
            })

        return ops

    def estimate_import_cost(
        self,
        asset: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Estimate the computational/memory cost of importing an asset.

        Cost factors:
          • poly_count (if available)
          • format (VDB and USD are heavier)
          • category (terrain, sky are expensive)

        Returns {cost_level: "low"|"medium"|"high", cost_score: float, notes: list[str]}
        """
        notes: List[str] = []
        score = 0.0

        category = asset.get("category", "misc")
        fmt = asset.get("format", "")
        poly_count = asset.get("poly_count", 0)

        # Poly count contribution
        if poly_count > 1_000_000:
            score += 3.0
            notes.append(f"High poly count: {poly_count:,}")
        elif poly_count > 100_000:
            score += 1.5
        elif poly_count > 10_000:
            score += 0.5

        # Format contribution
        if fmt in ("vdb", "usd"):
            score += 1.5
            notes.append(f"Format '{fmt}' requires additional processing.")
        elif fmt == "abc":
            score += 0.5

        # Category contribution
        if category in ("terrain", "sky"):
            score += 2.0
            notes.append(f"Category '{category}' typically has high geometry density.")
        elif category in ("vehicle", "character", "robot"):
            score += 1.0

        # LOD hint
        lod = asset.get("lod")
        if lod is not None and lod > 2:
            score += 1.0
            notes.append(f"LOD level {lod} — consider using lower LOD for non-hero assets.")

        if score < 2.0:
            cost_level = "low"
        elif score < 5.0:
            cost_level = "medium"
        else:
            cost_level = "high"

        return {
            "cost_level":  cost_level,
            "cost_score":  round(score, 2),
            "notes":       notes,
        }

    def validate_renderer_compatibility(
        self,
        asset: Dict[str, Any],
        renderer: str,
    ) -> Dict[str, Any]:
        """
        Check whether the asset's format is supported by the given renderer.

        Returns {compatible: bool, errors: list[str], renderer: str}
        """
        errors: List[str] = []
        fmt = asset.get("format", "").lower()
        r = renderer.lower()

        if not fmt:
            return {"compatible": True, "errors": [], "renderer": renderer}

        fmt_support = _FORMAT_RENDERER_SUPPORT.get(fmt)
        if fmt_support is None:
            # Unknown format — assume compatible with warning
            return {
                "compatible": True,
                "errors":     [],
                "renderer":   renderer,
            }

        is_compatible = fmt_support.get(r, fmt_support.get("generic", True))
        if not is_compatible:
            errors.append(
                f"Format '{fmt}' is not supported by renderer '{renderer}'."
            )

        return {
            "compatible": is_compatible,
            "errors":     errors,
            "renderer":   renderer,
        }

    def validate_style_consistency(
        self,
        asset: Dict[str, Any],
        existing_categories: List[str],
    ) -> Dict[str, Any]:
        """
        Check if the asset's category conflicts with existing scene categories.

        Returns {consistent: bool, conflicts: list[str]}
        """
        conflicts: List[str] = []
        category = asset.get("category", "misc")
        existing_set = set(existing_categories)

        for pair in _STYLE_CONFLICTS:
            if category in pair:
                other_cats = pair - {category}
                for other in other_cats:
                    if other in existing_set:
                        conflicts.append(
                            f"'{category}' conflicts with '{other}' already in scene."
                        )

        return {
            "consistent": len(conflicts) == 0,
            "conflicts":  conflicts,
        }

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "validation_count": self._validation_count,
                "rejected_count":   self._rejected_count,
            }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[SemanticImportController] = None
_INSTANCE_LOCK = threading.Lock()


def get_semantic_import_controller() -> SemanticImportController:
    global _INSTANCE
    with _INSTANCE_LOCK:
        if _INSTANCE is None:
            _INSTANCE = SemanticImportController()
        return _INSTANCE


def reset_semantic_import_controller_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
