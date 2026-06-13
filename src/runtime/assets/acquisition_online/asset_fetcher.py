"""
Asset Fetcher (Tier 12.9)
===========================
Central acquisition entry point.

Acquisition priority:
  1. Cache   (AssetCacheManager.asset_exists)
  2. Registry (AcquisitionManager / DownloadRegistry)
  3. Megascans API download (MegascansDownloader)
  4. Offline advisory

Never downloads assets that haven't been selected by the semantic intelligence layers.
"""
from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .asset_cache_manager import get_asset_cache_manager
from .asset_provenance_tracker import get_asset_provenance_tracker
from .download_statistics import get_download_statistics
from .megascans_download import get_megascans_downloader


@dataclass
class FetchResult:
    ok:         bool  = False
    asset_id:   str   = ""
    provider:   str   = ""
    local_path: str   = ""
    source:     str   = ""   # "cache" | "registry" | "megascans_api" | "offline"
    checksum:   str   = ""
    bytes_fetched: int = 0
    duration_ms: float = 0.0
    error:      str   = ""
    provenance: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok":          bool(self.ok),
            "asset_id":    str(self.asset_id),
            "provider":    str(self.provider),
            "local_path":  str(self.local_path),
            "source":      str(self.source),
            "checksum":    str(self.checksum),
            "bytes_fetched": int(self.bytes_fetched),
            "duration_ms": float(self.duration_ms),
            "error":       str(self.error),
            "provenance":  dict(self.provenance),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "FetchResult":
        d = d if isinstance(d, dict) else {}
        return cls(
            ok=bool(d.get("ok", False)),
            asset_id=str(d.get("asset_id", "")),
            provider=str(d.get("provider", "")),
            local_path=str(d.get("local_path", "")),
            source=str(d.get("source", "")),
            checksum=str(d.get("checksum", "")),
            bytes_fetched=int(d.get("bytes_fetched", 0)),
            duration_ms=float(d.get("duration_ms", 0.0)),
            error=str(d.get("error", "")),
            provenance=dict(d.get("provenance") or {}),
        )


class AssetFetcher:
    """
    Fetches assets using a cache-first, download-only-when-needed strategy.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def ensure_asset_available(self, asset_id: str, provider: str = "") -> FetchResult:
        """Check cache/registry first; only download if not available. Never raises."""
        return self.fetch_asset(asset_id, provider=provider, force_download=False)

    def fetch_asset(
        self,
        asset_id:       str,
        provider:       str = "",
        download_url:   str = "",
        dest_dir:       str = "",
        force_download: bool = False,
        quality:        str = "medium",
    ) -> FetchResult:
        """Fetch a single asset through the full acquisition chain. Never raises."""
        t0 = time.time()
        try:
            asset_id = str(asset_id).strip()
            provider = str(provider).strip() or "megascans"
            if not asset_id:
                return FetchResult(error="asset_id is required")

            # 1. Cache check
            if not force_download:
                cache = get_asset_cache_manager()
                cached_path = cache.get_asset_path(asset_id, provider)
                if cached_path:
                    elapsed = round((time.time() - t0) * 1000, 1)
                    get_download_statistics().record(
                        asset_id=asset_id, provider=provider, source="cache",
                        duration_ms=elapsed, ok=True,
                    )
                    prov = get_asset_provenance_tracker().lookup(asset_id, provider)
                    return FetchResult(
                        ok=True, asset_id=asset_id, provider=provider,
                        local_path=cached_path, source="cache",
                        duration_ms=elapsed,
                        provenance=prov.to_dict() if prov else {},
                    )

                # 2. Registry / local acquisition check
                registry_result = self._check_acquisition_registry(asset_id, provider)
                if registry_result:
                    elapsed = round((time.time() - t0) * 1000, 1)
                    get_download_statistics().record(
                        asset_id=asset_id, provider=provider, source="registry",
                        duration_ms=elapsed, ok=True,
                    )
                    return FetchResult(
                        ok=True, asset_id=asset_id, provider=provider,
                        local_path=registry_result, source="registry",
                        duration_ms=elapsed,
                    )

            # 3a. Fab Plugin socket receiver — assets pushed from Fab/UE5 desktop app
            fab_socket_result = self._check_fab_socket_receiver(asset_id)
            if fab_socket_result:
                elapsed = round((time.time() - t0) * 1000, 1)
                get_asset_cache_manager().cache_asset(
                    asset_id=asset_id, provider=provider,
                    local_path=fab_socket_result, size_bytes=0,
                )
                prov_rec = get_asset_provenance_tracker().register(
                    asset_id=asset_id, provider=provider,
                    local_path=fab_socket_result, source="fab_socket",
                )
                get_download_statistics().record(
                    asset_id=asset_id, provider=provider, source="fab_socket",
                    duration_ms=elapsed, ok=True,
                )
                return FetchResult(
                    ok=True, asset_id=asset_id, provider=provider,
                    local_path=fab_socket_result, source="fab_socket",
                    duration_ms=elapsed,
                    provenance=prov_rec.to_dict(),
                )

            # 3b. Local Bridge API (localhost:28241) — old Quixel Bridge (deprecated)
            effective_dest = dest_dir or self._default_dest(asset_id, provider)
            bridge_result  = self._try_bridge(asset_id, effective_dest, quality)
            if bridge_result:
                elapsed = round((time.time() - t0) * 1000, 1)
                get_asset_cache_manager().cache_asset(
                    asset_id=asset_id, provider=provider,
                    local_path=bridge_result, size_bytes=0,
                )
                prov_rec = get_asset_provenance_tracker().register(
                    asset_id=asset_id, provider=provider,
                    local_path=bridge_result, source="bridge",
                )
                get_download_statistics().record(
                    asset_id=asset_id, provider=provider, source="bridge",
                    duration_ms=elapsed, ok=True,
                )
                return FetchResult(
                    ok=True, asset_id=asset_id, provider=provider,
                    local_path=bridge_result, source="bridge",
                    duration_ms=elapsed,
                    provenance=prov_rec.to_dict(),
                )

            # 4. Megascans Web REST API — cloud download
            dl = get_megascans_downloader()
            dl_result = dl.download_asset(
                asset_id=asset_id,
                dest_dir=effective_dest,
                download_url=download_url,
                quality=quality,
            )
            elapsed = round((time.time() - t0) * 1000, 1)
            get_download_statistics().record(
                asset_id=asset_id, provider=provider,
                source=dl_result.source, bytes_downloaded=dl_result.bytes_downloaded,
                duration_ms=elapsed, ok=dl_result.ok, error=dl_result.error,
            )
            if not dl_result.ok:
                return FetchResult(
                    asset_id=asset_id, provider=provider,
                    source=dl_result.source, error=dl_result.error, duration_ms=elapsed,
                )
            # Register in cache + provenance
            get_asset_cache_manager().cache_asset(
                asset_id=asset_id, provider=provider,
                local_path=dl_result.local_path,
                checksum=dl_result.checksum,
                size_bytes=dl_result.bytes_downloaded,
            )
            prov_rec = get_asset_provenance_tracker().register(
                asset_id=asset_id, provider=provider,
                local_path=dl_result.local_path,
                checksum=dl_result.checksum, source="download",
            )
            return FetchResult(
                ok=True, asset_id=asset_id, provider=provider,
                local_path=dl_result.local_path,
                source=dl_result.source,
                checksum=dl_result.checksum,
                bytes_fetched=dl_result.bytes_downloaded,
                duration_ms=elapsed,
                provenance=prov_rec.to_dict(),
            )
        except Exception as exc:
            elapsed = round((time.time() - time.time()) * 1000, 1)
            return FetchResult(
                asset_id=str(asset_id), provider=str(provider),
                error=str(exc), duration_ms=elapsed,
            )

    def fetch_assets(
        self,
        asset_list: List[Dict[str, Any]],
        dest_dir:   str = "",
        quality:    str = "medium",
    ) -> List[FetchResult]:
        """Fetch multiple assets. asset_list items: {asset_id, provider, download_url}. Never raises."""
        results = []
        for item in (asset_list or []):
            if not isinstance(item, dict):
                continue
            r = self.fetch_asset(
                asset_id=str(item.get("asset_id") or ""),
                provider=str(item.get("provider") or ""),
                download_url=str(item.get("download_url") or ""),
                dest_dir=dest_dir,
                quality=quality,
            )
            results.append(r)
        return results

    def fetch_environment_assets(
        self,
        environment: str,
        top_k:       int = 10,
        dest_dir:    str = "",
        quality:     str = "medium",
    ) -> List[FetchResult]:
        """Retrieve top-ranked environment assets and fetch them. Never raises."""
        try:
            from src.runtime.assets.vector_search import get_retrieval_pipeline
            pipeline = get_retrieval_pipeline()
            retrieval = pipeline.retrieve_environment_assets(environment, top_k=top_k)
            asset_list = [
                {"asset_id": str(a.get("asset_id", "")),
                 "provider": str(a.get("provider", "megascans"))}
                for a in (retrieval.assets or [])
                if isinstance(a, dict) and a.get("asset_id")
            ]
            return self.fetch_assets(asset_list, dest_dir=dest_dir, quality=quality)
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _check_fab_socket_receiver(self, asset_id: str) -> Optional[str]:
        """
        Check if the Fab Plugin socket receiver has a queued asset matching asset_id.
        Returns the mesh file path if found, else None. Never raises.
        """
        try:
            from .fab_socket_receiver import get_fab_socket_receiver
            receiver = get_fab_socket_receiver()
            # Peek without draining — only consume if we find a match
            queued = receiver.get_received_assets(drain=False)
            for asset in queued:
                if asset.asset_id == asset_id or asset.name.lower() == asset_id.lower():
                    # Re-drain to remove this specific item
                    receiver.get_received_assets(drain=True)
                    path = asset.primary_mesh()
                    return path if path else (asset.export_path or None)
        except Exception:
            pass
        return None

    def _try_bridge(self, asset_id: str, dest_dir: str, quality: str) -> Optional[str]:
        """
        Try to export the asset via the local Quixel Bridge API (localhost:28241).
        Returns the local mesh file path if successful, else None.
        Never raises.
        """
        try:
            from .quixel_bridge_client import get_quixel_bridge_client
            bridge_client = get_quixel_bridge_client()
            if not bridge_client.is_bridge_running():
                return None
            result = bridge_client.export_asset(
                asset_id=asset_id,
                export_dir=dest_dir,
                quality=self._quality_to_bridge(quality),
                fmt="fbx",
            )
            return result.mesh_path if result.ok and result.mesh_path else None
        except Exception:
            return None

    @staticmethod
    def _quality_to_bridge(quality: str) -> str:
        """Map Vibrante quality string to Bridge quality label."""
        return {"low": "1K", "medium": "2K", "high": "4K", "ultra": "8K"}.get(
            str(quality).lower(), "2K"
        )

    def _check_acquisition_registry(self, asset_id: str, provider: str) -> Optional[str]:
        """Check Tier 12.5 AcquisitionManager + DownloadRegistry. Returns path or None."""
        try:
            from src.runtime.assets.acquisition import get_acquisition_manager
            mgr    = get_acquisition_manager()
            result = mgr.ensure_asset_available(provider, asset_id)
            if result and result.get("source") != "not_found":
                path = result.get("local_path") or result.get("path")
                if path and os.path.exists(str(path)):
                    return str(path)
        except Exception:
            pass
        return None

    def _default_dest(self, asset_id: str, provider: str) -> str:
        cache = get_asset_cache_manager()
        d = cache.get_asset_dir(asset_id, provider)
        if d:
            return d
        import tempfile
        return os.path.join(tempfile.gettempdir(), "vibrante_downloads", provider, asset_id)


_INSTANCE: Optional[AssetFetcher] = None
_INSTANCE_LOCK = threading.Lock()


def get_asset_fetcher() -> AssetFetcher:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = AssetFetcher()
    return _INSTANCE


def reset_asset_fetcher_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
