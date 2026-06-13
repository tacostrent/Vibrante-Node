"""
Asset Catalog Sync (Tier 12.7)
================================
Synchronizes the semantic catalog with Megascans and local library sources.

Workflow:
  Megascans API / Local Manifest
    → Metadata Fetch
    → Semantic Enrichment
    → Catalog Update

Design rules:
  - No direct Houdini calls
  - No network calls when token not set (offline mode)
  - Deterministic normalization
  - Never raises in public methods
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .asset_catalog import get_asset_catalog, CatalogEntry
from .asset_metadata_provider import get_asset_metadata_provider
from .semantic_asset_enricher import get_semantic_asset_enricher
from .megascans_metadata_client import get_megascans_metadata_client
from .asset_catalog_statistics import get_catalog_statistics


@dataclass
class SyncReport:
    ok:            bool = True
    added:         int = 0
    updated:       int = 0
    skipped:       int = 0
    removed:       int = 0
    source:        str = ""
    errors:        List[str] = field(default_factory=list)
    warnings:      List[str] = field(default_factory=list)
    synced_at:     float = field(default_factory=time.time)
    duration_ms:   float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok":          bool(self.ok),
            "added":       int(self.added),
            "updated":     int(self.updated),
            "skipped":     int(self.skipped),
            "removed":     int(self.removed),
            "source":      str(self.source),
            "errors":      list(self.errors),
            "warnings":    list(self.warnings),
            "synced_at":   float(self.synced_at),
            "duration_ms": float(self.duration_ms),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SyncReport":
        d = d if isinstance(d, dict) else {}
        return cls(
            ok=bool(d.get("ok", True)),
            added=int(d.get("added", 0)),
            updated=int(d.get("updated", 0)),
            skipped=int(d.get("skipped", 0)),
            removed=int(d.get("removed", 0)),
            source=str(d.get("source", "")),
            errors=list(d.get("errors") or []),
            warnings=list(d.get("warnings") or []),
            synced_at=float(d.get("synced_at") or time.time()),
            duration_ms=float(d.get("duration_ms", 0.0)),
        )


class AssetCatalogSync:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sync_count = 0
        self._last_sync: float = 0.0

    def sync_catalog(
        self,
        query: str = "",
        category: str = "",
        limit: int = 100,
        force_update: bool = False,
    ) -> SyncReport:
        """Full catalog sync: search Megascans, enrich, and register. Never raises."""
        try:
            return self._do_sync(
                query=str(query).strip(),
                category=str(category).strip(),
                limit=int(limit),
                force_update=bool(force_update),
            )
        except Exception as exc:
            return SyncReport(ok=False, source="error", errors=[f"sync_catalog failed: {exc}"])

    def _do_sync(self, query: str, category: str, limit: int, force_update: bool) -> SyncReport:
        t0 = time.perf_counter()
        report = SyncReport(source="megascans_api")

        client = get_megascans_metadata_client()
        search_result = client.search_assets(query or "industrial", category=category, limit=limit)

        if not search_result.ok:
            report.ok = False
            report.warnings.append(
                "Megascans API unavailable — operating in offline mode. "
                "Set VIBRANTE_MEGASCANS_TOKEN to enable sync."
            )
            report.source = "offline"
            report.duration_ms = (time.perf_counter() - t0) * 1000
            return report

        for ms_record in search_result.assets:
            result = self.sync_asset(ms_record.to_dict(), force_update=force_update)
            if result == "added":
                report.added += 1
            elif result == "updated":
                report.updated += 1
            elif result == "skipped":
                report.skipped += 1

        report.duration_ms = round((time.perf_counter() - t0) * 1000, 2)
        get_catalog_statistics().record("sync", duration_ms=report.duration_ms)

        with self._lock:
            self._sync_count += 1
            self._last_sync = time.time()

        return report

    def sync_asset(self, asset_dict: Dict[str, Any], force_update: bool = False) -> str:
        """Sync a single asset dict into the catalog.

        Returns: "added" | "updated" | "skipped" | "error"
        Never raises.
        """
        try:
            asset_id = str(asset_dict.get("asset_id") or asset_dict.get("id") or "").strip()
            if not asset_id:
                return "error"
            catalog = get_asset_catalog()
            existing = catalog.asset_exists(asset_id)
            if existing and not force_update:
                return "skipped"
            enriched = get_semantic_asset_enricher().enrich_asset(asset_dict)
            extra = {
                "download_url":    str(asset_dict.get("download_url", "")),
                "preview_url":     str(asset_dict.get("preview_url", "")),
                "metadata_source": str(asset_dict.get("metadata_source", "api")),
            }
            catalog.register_asset(asset_id, enriched.to_dict(), extra)
            return "updated" if existing else "added"
        except Exception:
            return "error"

    def sync_new_assets(
        self,
        query: str = "",
        limit: int = 50,
    ) -> SyncReport:
        """Sync only assets not yet in the catalog."""
        try:
            return self._do_sync(
                query=str(query).strip(),
                category="",
                limit=int(limit),
                force_update=False,
            )
        except Exception as exc:
            return SyncReport(ok=False, errors=[f"sync_new_assets failed: {exc}"])

    def refresh_existing_assets(self, limit: int = 50) -> SyncReport:
        """Re-enrich all existing catalog entries. Never raises."""
        try:
            t0 = time.perf_counter()
            report = SyncReport(source="catalog_refresh")
            catalog = get_asset_catalog()
            enricher = get_semantic_asset_enricher()
            count = 0
            for entry in catalog.iter_all():
                if count >= limit:
                    break
                enriched = enricher.enrich_asset(entry.to_dict())
                catalog.register_asset(entry.asset_id, enriched.to_dict(), {
                    "download_url":    entry.download_url,
                    "preview_url":     entry.preview_url,
                    "local_path":      entry.local_path,
                    "metadata_source": entry.metadata_source,
                    "downloaded":      entry.downloaded,
                })
                report.updated += 1
                count += 1
            report.duration_ms = round((time.perf_counter() - t0) * 1000, 2)
            return report
        except Exception as exc:
            return SyncReport(ok=False, errors=[f"refresh_existing_assets failed: {exc}"])

    def remove_deleted_assets(self, known_ids: List[str]) -> SyncReport:
        """Remove catalog entries whose IDs are not in known_ids. Never raises."""
        try:
            catalog = get_asset_catalog()
            known = set(known_ids)
            report = SyncReport(source="cleanup")
            to_remove = [e.asset_id for e in catalog.iter_all() if e.asset_id not in known]
            for aid in to_remove:
                catalog.remove_asset(aid)
                report.removed += 1
            return report
        except Exception as exc:
            return SyncReport(ok=False, errors=[f"remove_deleted_assets failed: {exc}"])

    def build_sync_report(self) -> Dict[str, Any]:
        """Return a summary of sync activity."""
        with self._lock:
            return {
                "sync_count": self._sync_count,
                "last_sync":  self._last_sync,
            }

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "sync_count": self._sync_count,
                "last_sync":  self._last_sync,
            }


_INSTANCE: Optional[AssetCatalogSync] = None
_INSTANCE_LOCK = threading.Lock()


def get_asset_catalog_sync() -> AssetCatalogSync:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = AssetCatalogSync()
    return _INSTANCE


def reset_asset_catalog_sync_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
