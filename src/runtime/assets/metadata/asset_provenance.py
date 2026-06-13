"""
Asset Provenance (Tier 12 — Asset Ecosystem Expansion)
=======================================================
Track asset origin, download history, and usage across sessions.

Public API:
    ProvenanceRecord             — record descriptor
    AssetProvenance              — provenance tracker class
    get_asset_provenance()       — singleton
    reset_asset_provenance_for_tests()
"""

from __future__ import annotations

import threading
import time
import uuid
from typing import Any, Dict, List, Optional

from src.runtime.assets.schema import AssetDescriptor

# Valid event types
SESSION_EVENT_TYPES = frozenset({
    "source_registered",
    "download_queued",
    "download_completed",
    "import_attempted",
    "import_completed",
    "usage_recorded",
    "validation_passed",
    "validation_failed",
})


class ProvenanceRecord:
    """A single provenance event for an asset."""

    def __init__(
        self,
        asset_id:    str,
        provider:    str,
        event_type:  str,
        event_data:  Optional[Dict[str, Any]] = None,
    ) -> None:
        self.record_id:  str   = f"prov_{uuid.uuid4().hex[:12]}"
        self.asset_id:   str   = asset_id
        self.provider:   str   = provider
        self.event_type: str   = event_type if event_type in SESSION_EVENT_TYPES else "source_registered"
        self.event_data: Dict[str, Any] = dict(event_data or {})
        self.timestamp:  float = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id":  self.record_id,
            "asset_id":   self.asset_id,
            "provider":   self.provider,
            "event_type": self.event_type,
            "event_data": dict(self.event_data),
            "timestamp":  self.timestamp,
        }


class AssetProvenance:
    """
    Tracks asset origin, download, import, and usage history.

    Thread-safe.  In-memory only — no disk persistence in this implementation.
    """

    def __init__(self) -> None:
        self._lock:    threading.Lock = threading.Lock()
        self._records: List[ProvenanceRecord] = []

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record_source(self, asset_descriptor: AssetDescriptor) -> str:
        """Record that an asset was discovered from a provider."""
        record = ProvenanceRecord(
            asset_id=asset_descriptor.asset_id,
            provider=asset_descriptor.provider,
            event_type="source_registered",
            event_data={
                "name":     asset_descriptor.name,
                "category": asset_descriptor.category,
                "license":  asset_descriptor.license,
                "formats":  list(asset_descriptor.formats),
            },
        )
        with self._lock:
            self._records.append(record)
        return record.record_id

    def record_download(
        self,
        asset_id:  str,
        provider:  str,
        task_id:   str,
        status:    str,
    ) -> str:
        """Record a download event for an asset."""
        event_type = "download_completed" if status in ("completed", "ok") else "download_queued"
        record = ProvenanceRecord(
            asset_id=asset_id,
            provider=provider,
            event_type=event_type,
            event_data={"task_id": task_id, "status": status},
        )
        with self._lock:
            self._records.append(record)
        return record.record_id

    def record_import(
        self,
        asset_id:      str,
        provider:      str,
        scene_context: Optional[str],
        success:       bool,
    ) -> str:
        """Record an import attempt for an asset."""
        event_type = "import_completed" if success else "import_attempted"
        record = ProvenanceRecord(
            asset_id=asset_id,
            provider=provider,
            event_type=event_type,
            event_data={
                "scene_context": scene_context or "",
                "success": success,
            },
        )
        with self._lock:
            self._records.append(record)
        return record.record_id

    def record_usage(
        self,
        asset_id:      str,
        provider:      str,
        scene_type:    Optional[str],
        workflow_name: Optional[str],
    ) -> str:
        """Record that an asset was used in a scene."""
        record = ProvenanceRecord(
            asset_id=asset_id,
            provider=provider,
            event_type="usage_recorded",
            event_data={
                "scene_type":    scene_type or "",
                "workflow_name": workflow_name or "",
            },
        )
        with self._lock:
            self._records.append(record)
        return record.record_id

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def build_provenance_report(
        self,
        asset_id: str,
        provider: str,
    ) -> Dict[str, Any]:
        """
        Build a full provenance report for an asset.

        Returns:
            {asset_id, provider, records, first_seen, last_used,
             download_count, import_count, usage_count}
        """
        with self._lock:
            recs = [
                r for r in self._records
                if r.asset_id == asset_id and r.provider == provider
            ]
        if not recs:
            return {
                "asset_id":       asset_id,
                "provider":       provider,
                "records":        [],
                "first_seen":     None,
                "last_used":      None,
                "download_count": 0,
                "import_count":   0,
                "usage_count":    0,
            }

        timestamps = sorted(r.timestamp for r in recs)
        download_count = sum(
            1 for r in recs
            if r.event_type in ("download_queued", "download_completed")
        )
        import_count = sum(
            1 for r in recs
            if r.event_type in ("import_attempted", "import_completed")
        )
        usage_count = sum(
            1 for r in recs
            if r.event_type == "usage_recorded"
        )
        return {
            "asset_id":       asset_id,
            "provider":       provider,
            "records":        [r.to_dict() for r in recs],
            "first_seen":     timestamps[0],
            "last_used":      timestamps[-1],
            "download_count": download_count,
            "import_count":   import_count,
            "usage_count":    usage_count,
        }

    def get_asset_history(
        self,
        asset_id: str,
        provider: str,
        limit:    int = 50,
    ) -> List[Dict[str, Any]]:
        """Return recent provenance records for an asset (newest first)."""
        with self._lock:
            recs = [
                r for r in self._records
                if r.asset_id == asset_id and r.provider == provider
            ]
        sorted_recs = sorted(recs, key=lambda r: r.timestamp, reverse=True)
        return [r.to_dict() for r in sorted_recs[:limit]]

    def get_statistics(self) -> Dict[str, Any]:
        """Return usage statistics."""
        with self._lock:
            recs = list(self._records)
        assets_tracked = len({(r.asset_id, r.provider) for r in recs})
        event_type_counts: Dict[str, int] = {}
        for r in recs:
            event_type_counts[r.event_type] = event_type_counts.get(r.event_type, 0) + 1
        return {
            "total_records":    len(recs),
            "assets_tracked":   assets_tracked,
            "event_type_counts": event_type_counts,
        }

    def clear(self) -> None:
        """Clear all provenance records."""
        with self._lock:
            self._records.clear()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_PROVENANCE: Optional[AssetProvenance] = None
_PROVENANCE_LOCK = threading.Lock()


def get_asset_provenance() -> AssetProvenance:
    """Return the module-level singleton AssetProvenance."""
    global _PROVENANCE
    if _PROVENANCE is None:
        with _PROVENANCE_LOCK:
            if _PROVENANCE is None:
                _PROVENANCE = AssetProvenance()
    return _PROVENANCE


def reset_asset_provenance_for_tests() -> None:
    """Replace the singleton.  For test isolation only."""
    global _PROVENANCE
    with _PROVENANCE_LOCK:
        _PROVENANCE = None
