"""
Asset Dependency Resolver (Tier 13)
====================================
Resolves asset dependencies: textures, materials, external references.
No real file I/O — analyzes asset metadata to surface dependency lists.

DESIGN RULES:
  1. No bridge calls, no file I/O.
  2. No randomness — same input → same output.
  3. Never raises in public methods.
  4. Singleton pattern.

Public API:
    DependencyResult
    AssetDependencyResolver
    get_asset_dependency_resolver()
    reset_asset_dependency_resolver_for_tests()
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class DependencyResult:
    """Result of dependency resolution for a single asset."""

    ok:             bool      = True
    asset_id:       str       = ""
    asset_name:     str       = ""
    textures:       List[Dict[str, Any]] = field(default_factory=list)
    materials:      List[Dict[str, Any]] = field(default_factory=list)
    references:     List[Dict[str, Any]] = field(default_factory=list)
    external_files: List[str]            = field(default_factory=list)
    missing_deps:   List[str]            = field(default_factory=list)
    errors:         List[str]            = field(default_factory=list)
    warnings:       List[str]            = field(default_factory=list)
    resolved_at:    float                = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok":             self.ok,
            "asset_id":       self.asset_id,
            "asset_name":     self.asset_name,
            "textures":       [dict(t) for t in self.textures],
            "materials":      [dict(m) for m in self.materials],
            "references":     [dict(r) for r in self.references],
            "external_files": list(self.external_files),
            "missing_deps":   list(self.missing_deps),
            "errors":         list(self.errors),
            "warnings":       list(self.warnings),
            "resolved_at":    self.resolved_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DependencyResult":
        return cls(
            ok=bool(d.get("ok", True)),
            asset_id=str(d.get("asset_id", "")),
            asset_name=str(d.get("asset_name", "")),
            textures=list(d.get("textures") or []),
            materials=list(d.get("materials") or []),
            references=list(d.get("references") or []),
            external_files=list(d.get("external_files") or []),
            missing_deps=list(d.get("missing_deps") or []),
            errors=list(d.get("errors") or []),
            warnings=list(d.get("warnings") or []),
            resolved_at=float(d.get("resolved_at") or time.time()),
        )


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class AssetDependencyResolver:
    """
    Resolves asset dependency graphs from metadata.
    No real file or network operations.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._resolve_count = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def collect_dependencies(self, asset_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Collect all dependency info from an asset dict."""
        return {
            "textures":       self.resolve_textures(asset_dict),
            "materials":      self.resolve_materials(asset_dict),
            "references":     self.resolve_references(asset_dict),
            "external_files": self._collect_external_files(asset_dict),
        }

    def resolve_materials(self, asset_dict: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract material descriptors from asset metadata."""
        materials: List[Dict[str, Any]] = []
        raw = asset_dict.get("materials", None)
        if isinstance(raw, list):
            for m in raw:
                if isinstance(m, dict):
                    materials.append(dict(m))
                elif isinstance(m, str):
                    materials.append({"name": m, "type": "unknown"})
        elif isinstance(raw, dict):
            materials.append(dict(raw))
        elif raw is None:
            # Infer a default material from category
            category = str(asset_dict.get("category", ""))
            if category:
                materials.append({
                    "name":  f"{category}_default_material",
                    "type":  "pbr",
                    "inferred": True,
                })
        return materials

    def resolve_textures(self, asset_dict: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract texture descriptors from asset metadata."""
        textures: List[Dict[str, Any]] = []
        # Check common texture fields
        for tex_key in ("textures", "texture_maps", "maps"):
            raw = asset_dict.get(tex_key, None)
            if isinstance(raw, list):
                for t in raw:
                    if isinstance(t, dict):
                        textures.append(dict(t))
                    elif isinstance(t, str):
                        textures.append({"path": t, "type": "unknown"})
                break
            elif isinstance(raw, dict):
                for map_name, map_path in raw.items():
                    textures.append({
                        "name": map_name,
                        "path": str(map_path),
                        "type": map_name,
                    })
                break
        return textures

    def resolve_references(self, asset_dict: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract external asset references."""
        references: List[Dict[str, Any]] = []
        raw = asset_dict.get("references", None)
        if isinstance(raw, list):
            for r in raw:
                if isinstance(r, dict):
                    references.append(dict(r))
                elif isinstance(r, str):
                    references.append({"path": r, "type": "external"})
        elif isinstance(raw, str) and raw:
            references.append({"path": raw, "type": "external"})
        return references

    def validate_dependencies(self, result: DependencyResult) -> Dict[str, Any]:
        """Validate a DependencyResult."""
        errors:   List[str] = list(result.errors)
        warnings: List[str] = list(result.warnings)
        if result.missing_deps:
            warnings.extend([
                f"Missing dependency: {dep}" for dep in result.missing_deps
            ])
        return {
            "valid":    len(errors) == 0 and result.ok,
            "errors":   errors,
            "warnings": warnings,
        }

    def resolve(self, asset_dict: Dict[str, Any]) -> DependencyResult:
        """Full dependency resolution. Never raises."""
        try:
            return self._do_resolve(asset_dict)
        except Exception as exc:
            safe = asset_dict if isinstance(asset_dict, dict) else {}
            return DependencyResult(
                ok=False,
                asset_id=str(safe.get("asset_id", "")),
                asset_name=str(safe.get("name", "")),
                errors=[f"Dependency resolution failed: {exc}"],
            )

    def build_dependency_report(self, results: List[DependencyResult]) -> Dict[str, Any]:
        """Summarise dependency resolution results."""
        total = len(results)
        successful = sum(1 for r in results if r.ok)
        total_textures = sum(len(r.textures) for r in results)
        total_materials = sum(len(r.materials) for r in results)
        total_missing = sum(len(r.missing_deps) for r in results)
        return {
            "total":            total,
            "successful":       successful,
            "failed":           total - successful,
            "total_textures":   total_textures,
            "total_materials":  total_materials,
            "total_missing":    total_missing,
        }

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {"resolve_count": self._resolve_count}

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _collect_external_files(self, asset_dict: Dict[str, Any]) -> List[str]:
        files: List[str] = []
        for key in ("file_path", "source_path", "archive_path"):
            v = asset_dict.get(key, "")
            if v and isinstance(v, str):
                files.append(v)
        return files

    def _do_resolve(self, asset_dict: Dict[str, Any]) -> DependencyResult:
        asset_id   = str(asset_dict.get("asset_id", ""))
        asset_name = str(asset_dict.get("name", asset_id))

        deps      = self.collect_dependencies(asset_dict)
        textures  = deps["textures"]
        materials = deps["materials"]
        references = deps["references"]
        external  = deps["external_files"]

        # Identify missing deps (paths that look absent)
        missing: List[str] = []
        for t in textures:
            p = str(t.get("path", ""))
            if p and not p.startswith("http") and not p.startswith("/"):
                # Relative path — mark as potentially missing
                pass  # Advisory only, not an error

        warnings: List[str] = []
        if not materials:
            warnings.append("No materials found — asset will use default material.")

        with self._lock:
            self._resolve_count += 1

        return DependencyResult(
            ok=True,
            asset_id=asset_id,
            asset_name=asset_name,
            textures=textures,
            materials=materials,
            references=references,
            external_files=external,
            missing_deps=missing,
            warnings=warnings,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[AssetDependencyResolver] = None
_INSTANCE_LOCK = threading.Lock()


def get_asset_dependency_resolver() -> AssetDependencyResolver:
    """Return the module-level singleton AssetDependencyResolver."""
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = AssetDependencyResolver()
    return _INSTANCE


def reset_asset_dependency_resolver_for_tests() -> None:
    """Replace the singleton. For test isolation only."""
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
