"""
Asset Validation Pipeline (Tier 13)
=====================================
Multi-stage validation for the full asset realization pipeline.
Validates import → conversion → normalization → dependency → realization.

DESIGN RULES:
  1. No bridge calls, no Houdini imports.
  2. No randomness — same input → same output.
  3. Never raises in public methods.
  4. Singleton pattern.

Public API:
    PipelineValidationResult
    AssetValidationPipeline
    get_asset_validation_pipeline()
    reset_asset_validation_pipeline_for_tests()
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .asset_importer import get_asset_importer
from .asset_converter import get_asset_converter
from .asset_normalizer import get_asset_normalizer
from .asset_dependency_resolver import get_asset_dependency_resolver
from .scene_asset_realizer import get_scene_asset_realizer

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class PipelineValidationResult:
    """Validation result across all pipeline stages."""

    ok:                   bool      = True
    asset_id:             str       = ""
    asset_name:           str       = ""
    import_valid:         bool      = False
    conversion_valid:     bool      = False
    normalization_valid:  bool      = False
    dependency_valid:     bool      = False
    realization_valid:    bool      = False
    errors:               List[str] = field(default_factory=list)
    warnings:             List[str] = field(default_factory=list)
    checks_passed:        List[str] = field(default_factory=list)
    checks_failed:        List[str] = field(default_factory=list)
    validated_at:         float     = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok":                  self.ok,
            "asset_id":            self.asset_id,
            "asset_name":          self.asset_name,
            "import_valid":        self.import_valid,
            "conversion_valid":    self.conversion_valid,
            "normalization_valid": self.normalization_valid,
            "dependency_valid":    self.dependency_valid,
            "realization_valid":   self.realization_valid,
            "errors":              list(self.errors),
            "warnings":            list(self.warnings),
            "checks_passed":       list(self.checks_passed),
            "checks_failed":       list(self.checks_failed),
            "validated_at":        self.validated_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PipelineValidationResult":
        return cls(
            ok=bool(d.get("ok", True)),
            asset_id=str(d.get("asset_id", "")),
            asset_name=str(d.get("asset_name", "")),
            import_valid=bool(d.get("import_valid", False)),
            conversion_valid=bool(d.get("conversion_valid", False)),
            normalization_valid=bool(d.get("normalization_valid", False)),
            dependency_valid=bool(d.get("dependency_valid", False)),
            realization_valid=bool(d.get("realization_valid", False)),
            errors=list(d.get("errors") or []),
            warnings=list(d.get("warnings") or []),
            checks_passed=list(d.get("checks_passed") or []),
            checks_failed=list(d.get("checks_failed") or []),
            validated_at=float(d.get("validated_at") or time.time()),
        )


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class AssetValidationPipeline:
    """
    Multi-stage validation across the full realization pipeline.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._validate_count = 0

    # ------------------------------------------------------------------
    # Per-stage validators (accept dicts for flexibility)
    # ------------------------------------------------------------------

    def validate_import(self, import_result: Any) -> Dict[str, Any]:
        """Validate an import result (dict or ImportResult)."""
        if isinstance(import_result, dict):
            result_dict = import_result
        else:
            result_dict = import_result.to_dict() if hasattr(import_result, "to_dict") else {}

        errors:   List[str] = list(result_dict.get("errors") or [])
        warnings: List[str] = list(result_dict.get("warnings") or [])
        ok = result_dict.get("ok", True)
        if not ok:
            errors.append("Import failed.")
        if not result_dict.get("asset_id"):
            errors.append("Import result missing asset_id.")
        return {
            "valid":    len(errors) == 0,
            "errors":   errors,
            "warnings": warnings,
        }

    def validate_conversion(self, conversion_result: Any) -> Dict[str, Any]:
        """Validate a conversion result."""
        if isinstance(conversion_result, dict):
            result_dict = conversion_result
        else:
            result_dict = conversion_result.to_dict() if hasattr(conversion_result, "to_dict") else {}

        errors:   List[str] = list(result_dict.get("errors") or [])
        warnings: List[str] = list(result_dict.get("warnings") or [])
        ok = result_dict.get("ok", True)
        if not ok:
            errors.append("Conversion failed.")
        if not result_dict.get("target_format"):
            warnings.append("Conversion result has no target_format.")
        return {
            "valid":    len(errors) == 0,
            "errors":   errors,
            "warnings": warnings,
        }

    def validate_normalization(self, normalization_result: Any) -> Dict[str, Any]:
        """Validate a normalization result."""
        if isinstance(normalization_result, dict):
            result_dict = normalization_result
        else:
            result_dict = normalization_result.to_dict() if hasattr(normalization_result, "to_dict") else {}

        errors:   List[str] = list(result_dict.get("errors") or [])
        warnings: List[str] = list(result_dict.get("warnings") or [])
        ok = result_dict.get("ok", True)
        if not ok:
            errors.append("Normalization failed.")
        return {
            "valid":    len(errors) == 0,
            "errors":   errors,
            "warnings": warnings,
        }

    def validate_dependencies(self, dependency_result: Any) -> Dict[str, Any]:
        """Validate a dependency resolution result."""
        if isinstance(dependency_result, dict):
            result_dict = dependency_result
        else:
            result_dict = dependency_result.to_dict() if hasattr(dependency_result, "to_dict") else {}

        errors:   List[str] = list(result_dict.get("errors") or [])
        warnings: List[str] = list(result_dict.get("warnings") or [])
        ok = result_dict.get("ok", True)
        if not ok:
            errors.append("Dependency resolution failed.")
        missing = result_dict.get("missing_deps", [])
        if missing:
            warnings.extend([f"Missing dependency: {d}" for d in missing])
        return {
            "valid":    len(errors) == 0,
            "errors":   errors,
            "warnings": warnings,
        }

    def validate_realization(self, realization_plan: Any) -> Dict[str, Any]:
        """Validate a realization plan."""
        if isinstance(realization_plan, dict):
            plan_dict = realization_plan
        else:
            plan_dict = realization_plan.to_dict() if hasattr(realization_plan, "to_dict") else {}

        errors:   List[str] = list(plan_dict.get("errors") or [])
        warnings: List[str] = list(plan_dict.get("warnings") or [])
        ops = plan_dict.get("transaction_ops", [])
        if not ops:
            warnings.append("Realization plan has no transaction ops.")
        return {
            "valid":    len(errors) == 0,
            "errors":   errors,
            "warnings": warnings,
        }

    def validate_full_pipeline(self, asset_dict: Dict[str, Any]) -> PipelineValidationResult:
        """Run full pipeline validation on an asset dict. Never raises."""
        try:
            return self._do_validate(asset_dict)
        except Exception as exc:
            safe = asset_dict if isinstance(asset_dict, dict) else {}
            return PipelineValidationResult(
                ok=False,
                asset_id=str(safe.get("asset_id", "")),
                asset_name=str(safe.get("name", "")),
                errors=[f"Pipeline validation failed: {exc}"],
                checks_failed=["import", "conversion", "normalization", "dependencies", "realization"],
            )

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {"validate_count": self._validate_count}

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _do_validate(self, asset_dict: Dict[str, Any]) -> PipelineValidationResult:
        asset_id   = str(asset_dict.get("asset_id", ""))
        asset_name = str(asset_dict.get("name", asset_id))
        all_errors:   List[str] = []
        all_warnings: List[str] = []
        passed: List[str] = []
        failed: List[str] = []

        # Stage 1: Import
        import_result = get_asset_importer().import_asset(asset_dict)
        iv = self.validate_import(import_result)
        import_valid = iv["valid"]
        all_errors.extend(iv["errors"])
        all_warnings.extend(iv["warnings"])
        (passed if import_valid else failed).append("import")

        # Stage 2: Conversion
        conversion_result = get_asset_converter().convert_to_usd(asset_dict)
        cv = self.validate_conversion(conversion_result)
        conversion_valid = cv["valid"]
        all_errors.extend(cv["errors"])
        all_warnings.extend(cv["warnings"])
        (passed if conversion_valid else failed).append("conversion")

        # Stage 3: Normalization
        norm_result = get_asset_normalizer().normalize(asset_dict)
        nv = self.validate_normalization(norm_result)
        normalization_valid = nv["valid"]
        all_errors.extend(nv["errors"])
        all_warnings.extend(nv["warnings"])
        (passed if normalization_valid else failed).append("normalization")

        # Stage 4: Dependencies
        dep_result = get_asset_dependency_resolver().resolve(asset_dict)
        dv = self.validate_dependencies(dep_result)
        dependency_valid = dv["valid"]
        all_errors.extend(dv["errors"])
        all_warnings.extend(dv["warnings"])
        (passed if dependency_valid else failed).append("dependencies")

        # Stage 5: Realization
        plan = get_scene_asset_realizer().build_realization_plan([asset_dict])
        rv = self.validate_realization(plan)
        realization_valid = rv["valid"]
        all_errors.extend(rv["errors"])
        all_warnings.extend(rv["warnings"])
        (passed if realization_valid else failed).append("realization")

        with self._lock:
            self._validate_count += 1

        return PipelineValidationResult(
            ok=len(all_errors) == 0,
            asset_id=asset_id,
            asset_name=asset_name,
            import_valid=import_valid,
            conversion_valid=conversion_valid,
            normalization_valid=normalization_valid,
            dependency_valid=dependency_valid,
            realization_valid=realization_valid,
            errors=all_errors,
            warnings=all_warnings,
            checks_passed=passed,
            checks_failed=failed,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[AssetValidationPipeline] = None
_INSTANCE_LOCK = threading.Lock()


def get_asset_validation_pipeline() -> AssetValidationPipeline:
    """Return the module-level singleton AssetValidationPipeline."""
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = AssetValidationPipeline()
    return _INSTANCE


def reset_asset_validation_pipeline_for_tests() -> None:
    """Replace the singleton. For test isolation only."""
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
