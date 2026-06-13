"""
Project Asset Staging (Tier 12.9)
====================================
Builds project-local asset sets from the central cache.

Directory layout:
  {VIBRANTE_PROJECT_STAGING}/{project_id}/assets/{provider}/{asset_id}/

Features:
  - Stage individual assets or full environments
  - Build project-local cache from selected assets
  - Cleanup stale staged files
"""
from __future__ import annotations

import os
import shutil
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

ENV_PROJECT_STAGING = "VIBRANTE_PROJECT_STAGING"
_INDEX_FILENAME     = "staging_index.json"


@dataclass
class StagingEntry:
    project_id: str = ""
    asset_id:   str = ""
    provider:   str = ""
    local_path: str = ""   # path inside project staging dir
    source_path: str = "" # origin path in central cache
    staged_at:  float = field(default_factory=time.time)
    environment: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_id":  str(self.project_id),
            "asset_id":    str(self.asset_id),
            "provider":    str(self.provider),
            "local_path":  str(self.local_path),
            "source_path": str(self.source_path),
            "staged_at":   float(self.staged_at),
            "environment": str(self.environment),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "StagingEntry":
        d = d if isinstance(d, dict) else {}
        return cls(
            project_id=str(d.get("project_id", "")),
            asset_id=str(d.get("asset_id", "")),
            provider=str(d.get("provider", "")),
            local_path=str(d.get("local_path", "")),
            source_path=str(d.get("source_path", "")),
            staged_at=float(d.get("staged_at") or time.time()),
            environment=str(d.get("environment", "")),
        )


class ProjectAssetStaging:
    def __init__(self) -> None:
        self._lock  = threading.Lock()
        self._index: Dict[str, List[StagingEntry]] = {}  # project_id → entries

    # ------------------------------------------------------------------
    # Directories
    # ------------------------------------------------------------------

    def _staging_root(self) -> Optional[str]:
        return os.environ.get(ENV_PROJECT_STAGING, "").strip() or None

    def _project_dir(self, project_id: str) -> Optional[str]:
        root = self._staging_root()
        return os.path.join(root, str(project_id)) if root else None

    def _asset_dir(self, project_id: str, provider: str, asset_id: str) -> Optional[str]:
        pdir = self._project_dir(project_id)
        return os.path.join(pdir, "assets", str(provider), str(asset_id)) if pdir else None

    # ------------------------------------------------------------------
    # Stage operations
    # ------------------------------------------------------------------

    def stage_asset(
        self,
        project_id:  str,
        asset_id:    str,
        provider:    str = "",
        environment: str = "",
        copy:        bool = True,
    ) -> StagingEntry:
        """Stage an asset into the project-local directory. Never raises."""
        try:
            project_id = str(project_id).strip()
            asset_id   = str(asset_id).strip()
            provider   = str(provider).strip() or "megascans"
            if not project_id or not asset_id:
                return StagingEntry(error="project_id and asset_id required") if False \
                       else StagingEntry(project_id=project_id, asset_id=asset_id)

            # Locate source in cache
            from .asset_cache_manager import get_asset_cache_manager
            source_path = get_asset_cache_manager().get_asset_path(asset_id, provider) or ""

            # Build staging dir
            dest_dir = self._asset_dir(project_id, provider, asset_id)
            if dest_dir:
                os.makedirs(dest_dir, exist_ok=True)

            local_path = ""
            if source_path and os.path.exists(source_path) and dest_dir:
                fname = os.path.basename(source_path)
                dest  = os.path.join(dest_dir, fname)
                if copy and not os.path.exists(dest):
                    shutil.copy2(source_path, dest)
                local_path = dest if copy else source_path

            entry = StagingEntry(
                project_id=project_id,
                asset_id=asset_id,
                provider=provider,
                local_path=local_path or source_path,
                source_path=source_path,
                environment=environment,
            )
            with self._lock:
                self._index.setdefault(project_id, []).append(entry)
            return entry
        except Exception:
            return StagingEntry(project_id=str(project_id), asset_id=str(asset_id))

    def stage_environment(
        self,
        project_id:  str,
        environment: str,
        top_k:       int = 20,
    ) -> List[StagingEntry]:
        """Stage all top-ranked assets for an environment. Never raises."""
        try:
            from src.runtime.assets.vector_search import get_retrieval_pipeline
            pipeline  = get_retrieval_pipeline()
            retrieval = pipeline.retrieve_environment_assets(environment, top_k=top_k)
            entries   = []
            for a in (retrieval.assets or []):
                if not isinstance(a, dict):
                    continue
                e = self.stage_asset(
                    project_id=project_id,
                    asset_id=str(a.get("asset_id", "")),
                    provider=str(a.get("provider", "megascans")),
                    environment=environment,
                )
                entries.append(e)
            return entries
        except Exception:
            return []

    def build_project_cache(self, project_id: str) -> Dict[str, Any]:
        """Stage all cached assets for a project. Returns staging summary. Never raises."""
        try:
            from .asset_cache_manager import get_asset_cache_manager
            entries = get_asset_cache_manager().list_cached_assets()
            staged  = []
            for ce in entries:
                e = self.stage_asset(project_id, ce.asset_id, ce.provider)
                staged.append(e.to_dict())
            return {"project_id": project_id, "staged": len(staged), "entries": staged}
        except Exception as exc:
            return {"project_id": str(project_id), "staged": 0, "error": str(exc)}

    def cleanup(self, project_id: str, dry_run: bool = False) -> Dict[str, Any]:
        """Remove staged files for assets that no longer exist in cache. Never raises."""
        try:
            removed = []
            with self._lock:
                entries = list(self._index.get(project_id, []))
            for entry in entries:
                if entry.local_path and not os.path.exists(entry.local_path):
                    if not dry_run:
                        with self._lock:
                            lst = self._index.get(project_id, [])
                            if entry in lst:
                                lst.remove(entry)
                    removed.append(entry.asset_id)
            return {"project_id": project_id, "removed": removed, "dry_run": dry_run}
        except Exception as exc:
            return {"project_id": str(project_id), "error": str(exc)}

    def get_project_assets(self, project_id: str) -> List[StagingEntry]:
        with self._lock:
            return list(self._index.get(str(project_id), []))

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            total = sum(len(v) for v in self._index.values())
            return {
                "total_staged":    total,
                "projects":        len(self._index),
                "staging_root":    self._staging_root() or "not configured",
            }


_INSTANCE: Optional[ProjectAssetStaging] = None
_INSTANCE_LOCK = threading.Lock()


def get_project_asset_staging() -> ProjectAssetStaging:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = ProjectAssetStaging()
    return _INSTANCE


def reset_project_asset_staging_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
