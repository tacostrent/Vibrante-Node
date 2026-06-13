"""
Acquisition Pipeline (Tier 12.9)
===================================
Full intelligent acquisition pipeline:
  Intent → Asset Retrieval → Top Ranked Assets → Fetch Missing → Cache → Staging

Rules:
  - Only fetches assets selected by semantic intelligence layers.
  - Prefer cache over download.
  - Never downloads entire libraries.
  - Never duplicates existing assets.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .asset_fetcher import get_asset_fetcher, FetchResult
from .project_asset_staging import get_project_asset_staging
from .download_statistics import get_download_statistics


@dataclass
class AcquisitionPipelineResult:
    ok:          bool  = False
    intent:      str   = ""
    environment: str   = ""
    total:       int   = 0
    cached:      int   = 0
    downloaded:  int   = 0
    failed:      int   = 0
    duration_ms: float = 0.0
    assets:      List[Dict[str, Any]] = field(default_factory=list)
    errors:      List[str] = field(default_factory=list)
    error:       str   = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok":          bool(self.ok),
            "intent":      str(self.intent),
            "environment": str(self.environment),
            "total":       int(self.total),
            "cached":      int(self.cached),
            "downloaded":  int(self.downloaded),
            "failed":      int(self.failed),
            "duration_ms": float(self.duration_ms),
            "assets":      list(self.assets),
            "errors":      list(self.errors),
            "error":       str(self.error),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AcquisitionPipelineResult":
        d = d if isinstance(d, dict) else {}
        return cls(
            ok=bool(d.get("ok", False)),
            intent=str(d.get("intent", "")),
            environment=str(d.get("environment", "")),
            total=int(d.get("total", 0)),
            cached=int(d.get("cached", 0)),
            downloaded=int(d.get("downloaded", 0)),
            failed=int(d.get("failed", 0)),
            duration_ms=float(d.get("duration_ms", 0.0)),
            assets=list(d.get("assets") or []),
            errors=list(d.get("errors") or []),
            error=str(d.get("error", "")),
        )


class AcquisitionPipeline:
    def __init__(self) -> None:
        self._lock = threading.Lock()

    def acquire_for_intent(
        self,
        intent_text:  str,
        top_k:        int = 10,
        project_id:   str = "",
        dest_dir:     str = "",
        quality:      str = "medium",
        stage_assets: bool = True,
    ) -> AcquisitionPipelineResult:
        """
        Full pipeline: parse intent → retrieve ranked assets → fetch only what's missing.
        Never raises.
        """
        t0 = time.time()
        try:
            intent_text = str(intent_text).strip()
            if not intent_text:
                return AcquisitionPipelineResult(
                    ok=False, intent=intent_text,
                    error="intent_text is required",
                )
            # Retrieve ranked assets using semantic intelligence
            asset_list = self._retrieve_assets(intent_text, top_k=top_k)
            return self._fetch_and_stage(
                intent_text=intent_text,
                environment="",
                asset_list=asset_list,
                project_id=project_id,
                dest_dir=dest_dir,
                quality=quality,
                stage_assets=stage_assets,
                t0=t0,
            )
        except Exception as exc:
            return AcquisitionPipelineResult(
                ok=False, intent=str(intent_text),
                error=str(exc),
                duration_ms=round((time.time() - t0) * 1000, 1),
            )

    def acquire_environment(
        self,
        environment:  str,
        top_k:        int = 20,
        project_id:   str = "",
        dest_dir:     str = "",
        quality:      str = "medium",
        stage_assets: bool = True,
    ) -> AcquisitionPipelineResult:
        """Acquire all semantic top-ranked assets for a production environment. Never raises."""
        t0 = time.time()
        try:
            environment = str(environment).strip()
            if not environment:
                return AcquisitionPipelineResult(
                    ok=False, environment=environment,
                    error="environment is required",
                )
            asset_list = self._retrieve_environment_assets(environment, top_k=top_k)
            return self._fetch_and_stage(
                intent_text="",
                environment=environment,
                asset_list=asset_list,
                project_id=project_id,
                dest_dir=dest_dir,
                quality=quality,
                stage_assets=stage_assets,
                t0=t0,
            )
        except Exception as exc:
            return AcquisitionPipelineResult(
                ok=False, environment=str(environment),
                error=str(exc),
                duration_ms=round((time.time() - t0) * 1000, 1),
            )

    def acquire_asset_set(
        self,
        asset_list:   List[Dict[str, Any]],
        project_id:   str = "",
        dest_dir:     str = "",
        quality:      str = "medium",
        stage_assets: bool = True,
    ) -> AcquisitionPipelineResult:
        """Acquire a pre-selected list of assets. Never raises."""
        t0 = time.time()
        try:
            return self._fetch_and_stage(
                intent_text="",
                environment="",
                asset_list=list(asset_list or []),
                project_id=project_id,
                dest_dir=dest_dir,
                quality=quality,
                stage_assets=stage_assets,
                t0=t0,
            )
        except Exception as exc:
            return AcquisitionPipelineResult(
                ok=False, error=str(exc),
                duration_ms=round((time.time() - t0) * 1000, 1),
            )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _retrieve_assets(
        self, intent_text: str, top_k: int
    ) -> List[Dict[str, Any]]:
        try:
            from src.runtime.assets.vector_search import get_retrieval_pipeline
            pipeline  = get_retrieval_pipeline()
            result    = pipeline.retrieve(intent_text, top_k=top_k)
            return [a if isinstance(a, dict) else {} for a in (result.assets or [])]
        except Exception:
            return []

    def _retrieve_environment_assets(
        self, environment: str, top_k: int
    ) -> List[Dict[str, Any]]:
        try:
            from src.runtime.assets.vector_search import get_retrieval_pipeline
            pipeline  = get_retrieval_pipeline()
            result    = pipeline.retrieve_environment_assets(environment, top_k=top_k)
            return [a if isinstance(a, dict) else {} for a in (result.assets or [])]
        except Exception:
            return []

    def _fetch_and_stage(
        self,
        intent_text:  str,
        environment:  str,
        asset_list:   List[Dict[str, Any]],
        project_id:   str,
        dest_dir:     str,
        quality:      str,
        stage_assets: bool,
        t0:           float,
    ) -> AcquisitionPipelineResult:
        fetcher  = get_asset_fetcher()
        staging  = get_project_asset_staging()
        fetched_assets: List[Dict[str, Any]] = []
        errors:   List[str] = []
        cached = downloaded = failed = 0

        for a in asset_list:
            if not isinstance(a, dict):
                continue
            aid = str(a.get("asset_id") or "")
            prv = str(a.get("provider") or "megascans")
            if not aid:
                continue
            r: FetchResult = fetcher.fetch_asset(
                asset_id=aid,
                provider=prv,
                download_url=str(a.get("download_url") or ""),
                dest_dir=dest_dir,
                quality=quality,
            )
            if r.ok:
                if r.source == "cache":
                    cached += 1
                else:
                    downloaded += 1
                if stage_assets and project_id:
                    staging.stage_asset(project_id, aid, prv, environment=environment)
                fetched_assets.append({**a, "local_path": r.local_path, "source": r.source})
            else:
                failed += 1
                if r.error:
                    errors.append(f"{aid}: {r.error}")

        return AcquisitionPipelineResult(
            ok=failed == 0,
            intent=intent_text,
            environment=environment,
            total=cached + downloaded + failed,
            cached=cached,
            downloaded=downloaded,
            failed=failed,
            duration_ms=round((time.time() - t0) * 1000, 1),
            assets=fetched_assets,
            errors=errors,
        )


_INSTANCE: Optional[AcquisitionPipeline] = None
_INSTANCE_LOCK = threading.Lock()


def get_acquisition_pipeline() -> AcquisitionPipeline:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = AcquisitionPipeline()
    return _INSTANCE


def reset_acquisition_pipeline_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
