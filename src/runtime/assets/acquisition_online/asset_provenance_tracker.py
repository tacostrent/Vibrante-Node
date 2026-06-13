"""
Asset Provenance Tracker (Tier 12.9)
=======================================
Tracks asset origins, download history, and integrity records.

Storage:
  Append-only JSONL log at {VIBRANTE_ASSET_CACHE}/provenance_log.jsonl
  In-memory index for fast lookup: {provider}:{asset_id} → latest record

Fields tracked:
  provider, asset_id, download_time, version, checksum, local_path, source
"""
from __future__ import annotations

import hashlib
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .download_serializer import get_download_serializer

ENV_ASSET_CACHE      = "VIBRANTE_ASSET_CACHE"
_PROVENANCE_FILENAME = "provenance_log.jsonl"


@dataclass
class ProvenanceRecord:
    asset_id:      str = ""
    provider:      str = ""
    local_path:    str = ""
    version:       str = ""
    checksum:      str = ""
    download_time: float = field(default_factory=time.time)
    source:        str = "download"   # "download" | "local" | "cache"
    metadata:      Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id":      str(self.asset_id),
            "provider":      str(self.provider),
            "local_path":    str(self.local_path),
            "version":       str(self.version),
            "checksum":      str(self.checksum),
            "download_time": float(self.download_time),
            "source":        str(self.source),
            "metadata":      dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ProvenanceRecord":
        d = d if isinstance(d, dict) else {}
        return cls(
            asset_id=str(d.get("asset_id", "")),
            provider=str(d.get("provider", "")),
            local_path=str(d.get("local_path", "")),
            version=str(d.get("version", "")),
            checksum=str(d.get("checksum", "")),
            download_time=float(d.get("download_time") or time.time()),
            source=str(d.get("source", "download")),
            metadata=dict(d.get("metadata") or {}),
        )


def compute_file_checksum(path: str) -> str:
    """Compute SHA-256 checksum of a file. Returns '' on error."""
    try:
        sha = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha.update(chunk)
        return sha.hexdigest()
    except Exception:
        return ""


class AssetProvenanceTracker:
    def __init__(self) -> None:
        self._lock  = threading.Lock()
        self._index: Dict[str, ProvenanceRecord] = {}   # "provider:asset_id" → latest
        self._history: Dict[str, List[ProvenanceRecord]] = {}  # same key → all records
        self._register_count = 0
        self._load_from_disk()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _log_path(self) -> Optional[str]:
        storage = os.environ.get(ENV_ASSET_CACHE, "").strip()
        if not storage:
            return None
        return os.path.join(storage, _PROVENANCE_FILENAME)

    def _load_from_disk(self) -> None:
        try:
            path = self._log_path()
            if not path:
                return
            records = get_download_serializer().read_jsonl(path)
            with self._lock:
                for d in records:
                    rec = ProvenanceRecord.from_dict(d)
                    if rec.asset_id:
                        key = f"{rec.provider}:{rec.asset_id}"
                        self._index[key] = rec
                        self._history.setdefault(key, []).append(rec)
        except Exception:
            pass

    def _append_to_disk(self, record: ProvenanceRecord) -> None:
        try:
            path = self._log_path()
            if path:
                get_download_serializer().write_jsonl(path, record.to_dict())
        except Exception:
            pass

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def register(
        self,
        asset_id:   str,
        provider:   str,
        local_path: str,
        version:    str = "",
        checksum:   str = "",
        source:     str = "download",
        metadata:   Optional[Dict[str, Any]] = None,
    ) -> ProvenanceRecord:
        """Register a new provenance record. Never raises."""
        try:
            rec = ProvenanceRecord(
                asset_id=str(asset_id).strip(),
                provider=str(provider).strip(),
                local_path=str(local_path).strip(),
                version=str(version).strip(),
                checksum=str(checksum).strip(),
                source=str(source),
                metadata=dict(metadata or {}),
            )
            key = f"{rec.provider}:{rec.asset_id}"
            with self._lock:
                self._index[key] = rec
                self._history.setdefault(key, []).append(rec)
                self._register_count += 1
            self._append_to_disk(rec)
            return rec
        except Exception:
            return ProvenanceRecord(asset_id=str(asset_id), provider=str(provider))

    def lookup(self, asset_id: str, provider: str = "") -> Optional[ProvenanceRecord]:
        """Return the latest provenance record for an asset. Never raises."""
        try:
            with self._lock:
                # Exact provider match
                if provider:
                    key = f"{provider}:{asset_id}"
                    rec = self._index.get(key)
                    if rec:
                        return rec
                # Search all providers
                for key, rec in self._index.items():
                    if rec.asset_id == str(asset_id):
                        return rec
            return None
        except Exception:
            return None

    def get_history(self, asset_id: str, provider: str = "") -> List[ProvenanceRecord]:
        """Return all provenance records for an asset."""
        try:
            with self._lock:
                if provider:
                    key = f"{provider}:{asset_id}"
                    return list(self._history.get(key, []))
                result = []
                for key, recs in self._history.items():
                    for r in recs:
                        if r.asset_id == str(asset_id):
                            result.append(r)
                return result
        except Exception:
            return []

    def verify(self, asset_id: str, provider: str = "") -> Dict[str, Any]:
        """Verify the integrity of a tracked asset. Never raises."""
        try:
            rec = self.lookup(asset_id, provider)
            if not rec:
                return {"verified": False, "reason": "no_provenance_record"}
            if not rec.local_path or not os.path.exists(rec.local_path):
                return {"verified": False, "reason": "file_missing", "path": rec.local_path}
            if rec.checksum:
                actual = compute_file_checksum(rec.local_path)
                if actual != rec.checksum:
                    return {"verified": False, "reason": "checksum_mismatch",
                            "expected": rec.checksum, "actual": actual}
            return {"verified": True, "path": rec.local_path, "checksum": rec.checksum}
        except Exception as exc:
            return {"verified": False, "reason": str(exc)}

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_records":   sum(len(v) for v in self._history.values()),
                "unique_assets":   len(self._index),
                "register_count":  self._register_count,
            }


_INSTANCE: Optional[AssetProvenanceTracker] = None
_INSTANCE_LOCK = threading.Lock()


def get_asset_provenance_tracker() -> AssetProvenanceTracker:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = AssetProvenanceTracker()
    return _INSTANCE


def reset_asset_provenance_tracker_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
