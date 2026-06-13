"""
Acquisition Manager (Tier 12.5)
================================
Orchestrates the full asset acquisition pipeline:
  locate → register → index → make available

Responsibilities:
  - ensure_asset_available():  checks local sources, returns path if found
  - locate_asset():            searches all registered local library sources
  - request_acquisition():     records that an asset is needed (user must fetch it via Fab)
  - register_downloaded_asset(): integrates a newly appeared local asset

Environment variables read:
  VIBRANTE_ASSET_STORAGE        — root storage directory
  VIBRANTE_FAB_LIBRARY          — Fab local library path
  VIBRANTE_MEGASCANS_LIBRARY    — Megascans local library path

Deterministic, thread-safe, no Houdini dependency, no network calls.
"""
from __future__ import annotations

import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .download_registry import get_download_registry, RegistryEntry
from .library_index import get_library_index
from .fab_library_scanner import get_fab_library_scanner
from .megascans_scanner import get_megascans_scanner

_ACQUISITION_REQUESTS_MAX = 5000


@dataclass
class AcquisitionRequest:
    request_id:  str = field(default_factory=lambda: f"acq_{uuid.uuid4().hex[:10]}")
    asset_id:    str = ""
    provider:    str = ""
    name:        str = ""
    category:    str = ""
    reason:      str = ""
    status:      str = "pending"   # "pending" | "available" | "cancelled"
    requested_at: float = field(default_factory=time.time)
    resolved_at:  Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id":   str(self.request_id),
            "asset_id":     str(self.asset_id),
            "provider":     str(self.provider),
            "name":         str(self.name),
            "category":     str(self.category),
            "reason":       str(self.reason),
            "status":       str(self.status),
            "requested_at": float(self.requested_at),
            "resolved_at":  self.resolved_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AcquisitionRequest":
        d = d if isinstance(d, dict) else {}
        return cls(
            request_id=str(d.get("request_id") or f"acq_{uuid.uuid4().hex[:10]}"),
            asset_id=str(d.get("asset_id", "")),
            provider=str(d.get("provider", "")),
            name=str(d.get("name", "")),
            category=str(d.get("category", "")),
            reason=str(d.get("reason", "")),
            status=str(d.get("status", "pending")),
            requested_at=float(d.get("requested_at") or time.time()),
            resolved_at=d.get("resolved_at"),
        )


@dataclass
class AcquisitionResult:
    ok:            bool = False
    asset_id:      str = ""
    provider:      str = ""
    local_path:    str = ""
    source:        str = ""   # "registry" | "fab_scan" | "megascans_scan" | "not_found"
    registry_entry: Optional[Dict[str, Any]] = None
    errors:        List[str] = field(default_factory=list)
    warnings:      List[str] = field(default_factory=list)
    resolved_at:   float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok":             bool(self.ok),
            "asset_id":       str(self.asset_id),
            "provider":       str(self.provider),
            "local_path":     str(self.local_path),
            "source":         str(self.source),
            "registry_entry": dict(self.registry_entry) if self.registry_entry else None,
            "errors":         list(self.errors),
            "warnings":       list(self.warnings),
            "resolved_at":    float(self.resolved_at),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AcquisitionResult":
        d = d if isinstance(d, dict) else {}
        return cls(
            ok=bool(d.get("ok", False)),
            asset_id=str(d.get("asset_id", "")),
            provider=str(d.get("provider", "")),
            local_path=str(d.get("local_path", "")),
            source=str(d.get("source", "not_found")),
            registry_entry=dict(d["registry_entry"]) if isinstance(d.get("registry_entry"), dict) else None,
            errors=list(d.get("errors") or []),
            warnings=list(d.get("warnings") or []),
            resolved_at=float(d.get("resolved_at") or time.time()),
        )


class AcquisitionManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._requests: Dict[str, AcquisitionRequest] = {}
        self._ensure_count = 0
        self._register_count = 0

    # ------------------------------------------------------------------
    # Core: ensure asset is available locally
    # ------------------------------------------------------------------

    def ensure_asset_available(
        self,
        provider: str,
        asset_id: str,
    ) -> AcquisitionResult:
        """Return local path if asset exists in any local source. Never raises."""
        try:
            return self._do_ensure(str(provider), str(asset_id))
        except Exception as exc:
            return AcquisitionResult(
                ok=False,
                asset_id=str(asset_id),
                provider=str(provider),
                source="not_found",
                errors=[f"ensure_asset_available failed: {exc}"],
            )

    def _do_ensure(self, provider: str, asset_id: str) -> AcquisitionResult:
        with self._lock:
            self._ensure_count += 1

        # 1. Check DownloadRegistry (fastest — in memory)
        entry = get_download_registry().find(provider, asset_id)
        if entry and entry.local_path:
            if os.path.exists(entry.local_path):
                return AcquisitionResult(
                    ok=True,
                    asset_id=asset_id,
                    provider=provider,
                    local_path=entry.local_path,
                    source="registry",
                    registry_entry=entry.to_dict(),
                )
            # Entry exists but path is gone — mark missing
            get_download_registry().mark_missing(entry.entry_id)

        # 2. Check LibraryIndex
        index_entry = get_library_index().get_entry(provider, asset_id)
        if index_entry and index_entry.local_path and os.path.exists(index_entry.local_path):
            # Register in DownloadRegistry for future lookups
            get_download_registry().register(
                asset_id=asset_id,
                provider=provider,
                local_path=index_entry.local_path,
                name=index_entry.name,
                category=index_entry.category,
                formats=list(index_entry.formats),
                provenance={"source": "library_index"},
            )
            return AcquisitionResult(
                ok=True,
                asset_id=asset_id,
                provider=provider,
                local_path=index_entry.local_path,
                source="library_index",
            )

        # 3. Scan Fab library
        if provider in ("fab", ""):
            located = self._scan_fab_for(asset_id)
            if located:
                return located

        # 4. Scan Megascans library
        if provider in ("megascans", "quixel", ""):
            located = self._scan_megascans_for(asset_id)
            if located:
                return located

        return AcquisitionResult(
            ok=False,
            asset_id=asset_id,
            provider=provider,
            source="not_found",
            warnings=[
                f"Asset '{asset_id}' not found in local libraries. "
                "Use the official Fab desktop application to download it first."
            ],
        )

    def _scan_fab_for(self, asset_id: str) -> Optional[AcquisitionResult]:
        try:
            index = get_fab_library_scanner().index_assets()
            record = index.get(asset_id)
            if record and record.local_path and os.path.exists(record.local_path):
                get_download_registry().register(
                    asset_id=record.asset_id,
                    provider="fab",
                    local_path=record.local_path,
                    name=record.name,
                    category=record.category,
                    formats=list(record.formats),
                    provenance={"source": "fab_scan"},
                )
                return AcquisitionResult(
                    ok=True,
                    asset_id=record.asset_id,
                    provider="fab",
                    local_path=record.local_path,
                    source="fab_scan",
                )
        except Exception:
            pass
        return None

    def _scan_megascans_for(self, asset_id: str) -> Optional[AcquisitionResult]:
        try:
            result = get_megascans_scanner().scan_megascans()
            for record in result.assets_found:
                if record.asset_id == asset_id:
                    if record.local_path and os.path.exists(record.local_path):
                        get_download_registry().register(
                            asset_id=record.asset_id,
                            provider="megascans",
                            local_path=record.local_path,
                            name=record.name,
                            category=record.category,
                            formats=list(record.formats),
                            provenance={"source": "megascans_scan"},
                        )
                        return AcquisitionResult(
                            ok=True,
                            asset_id=record.asset_id,
                            provider="megascans",
                            local_path=record.local_path,
                            source="megascans_scan",
                        )
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------
    # Locate: find without ensuring registration
    # ------------------------------------------------------------------

    def locate_asset(self, provider: str, asset_id: str) -> Optional[str]:
        """Return local path of asset if it exists anywhere, else None."""
        try:
            result = self.ensure_asset_available(provider, asset_id)
            return result.local_path if result.ok else None
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Request acquisition (user must download externally)
    # ------------------------------------------------------------------

    def request_acquisition(
        self,
        asset_dict: Dict[str, Any],
        reason: str = "",
    ) -> AcquisitionRequest:
        """Record that an asset is needed. User fetches it through Fab. Never raises."""
        try:
            asset_dict = asset_dict if isinstance(asset_dict, dict) else {}
            asset_id = str(asset_dict.get("asset_id", "")).strip() or f"req_{uuid.uuid4().hex[:8]}"
            provider = str(asset_dict.get("provider", "")).strip()

            req = AcquisitionRequest(
                asset_id=asset_id,
                provider=provider,
                name=str(asset_dict.get("name", "")),
                category=str(asset_dict.get("category", "")),
                reason=str(reason),
                status="pending",
            )
            with self._lock:
                if len(self._requests) >= _ACQUISITION_REQUESTS_MAX:
                    oldest = sorted(self._requests.values(), key=lambda r: r.requested_at)
                    for old in oldest[:len(self._requests) - _ACQUISITION_REQUESTS_MAX + 1]:
                        self._requests.pop(old.request_id, None)
                self._requests[req.request_id] = req
            return req
        except Exception as exc:
            return AcquisitionRequest(
                asset_id=str((asset_dict or {}).get("asset_id", "")),
                status="pending",
                reason=f"request_acquisition error: {exc}",
            )

    def list_pending_requests(self) -> List[AcquisitionRequest]:
        with self._lock:
            return sorted(
                [r for r in self._requests.values() if r.status == "pending"],
                key=lambda r: r.requested_at,
            )

    def cancel_request(self, request_id: str) -> bool:
        with self._lock:
            req = self._requests.get(request_id)
            if req:
                req.status = "cancelled"
                req.resolved_at = time.time()
                return True
            return False

    # ------------------------------------------------------------------
    # Register a newly downloaded asset
    # ------------------------------------------------------------------

    def register_downloaded_asset(
        self,
        local_path: str,
        metadata:   Optional[Dict[str, Any]] = None,
    ) -> AcquisitionResult:
        """Integrate a newly appeared local asset file into the registry and index."""
        try:
            return self._do_register(str(local_path).strip(), dict(metadata or {}))
        except Exception as exc:
            return AcquisitionResult(
                ok=False,
                local_path=str(local_path),
                source="not_found",
                errors=[f"register_downloaded_asset failed: {exc}"],
            )

    def _do_register(self, local_path: str, metadata: Dict[str, Any]) -> AcquisitionResult:
        import os as _os
        if not local_path:
            return AcquisitionResult(ok=False, errors=["local_path is required."])

        ext     = _os.path.splitext(local_path)[1].lower().lstrip(".")
        formats = [ext] if ext else []
        asset_id = str(metadata.get("asset_id") or _os.path.splitext(_os.path.basename(local_path))[0])
        provider = str(metadata.get("provider") or "local")
        name     = str(metadata.get("name") or asset_id)
        category = str(metadata.get("category") or "")

        entry = get_download_registry().register(
            asset_id=asset_id,
            provider=provider,
            local_path=local_path,
            name=name,
            category=category,
            formats=formats,
            tags=list(metadata.get("tags") or []),
            provenance={"source": "manual_registration", "registered_at": time.time()},
        )

        # Also index it
        get_library_index().add_entry(
            asset_id=asset_id,
            provider=provider,
            name=name,
            category=category,
            formats=formats,
            tags=list(metadata.get("tags") or []),
            local_path=local_path,
            provenance="manual_registration",
        )

        # Resolve pending requests
        with self._lock:
            for req in self._requests.values():
                if req.asset_id == asset_id and req.status == "pending":
                    req.status = "available"
                    req.resolved_at = time.time()

        with self._lock:
            self._register_count += 1

        return AcquisitionResult(
            ok=True,
            asset_id=asset_id,
            provider=provider,
            local_path=local_path,
            source="manual_registration",
            registry_entry=entry.to_dict(),
        )

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            pending = sum(1 for r in self._requests.values() if r.status == "pending")
            return {
                "ensure_count":      self._ensure_count,
                "register_count":    self._register_count,
                "total_requests":    len(self._requests),
                "pending_requests":  pending,
            }


_INSTANCE: Optional[AcquisitionManager] = None
_INSTANCE_LOCK = threading.Lock()


def get_acquisition_manager() -> AcquisitionManager:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = AcquisitionManager()
    return _INSTANCE


def reset_acquisition_manager_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
