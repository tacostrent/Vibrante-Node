"""
Download Statistics (Tier 12.9)
==================================
In-memory acquisition metrics tracker. Capped at 2000 records.
"""
from __future__ import annotations

import threading
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_MAX_RECORDS = 2000


@dataclass
class DownloadRecord:
    operation:        str = ""
    asset_id:         str = ""
    provider:         str = ""
    source:           str = ""
    bytes_downloaded: int = 0
    cache_hit:        bool = False
    ok:               bool = True
    duration_ms:      float = 0.0
    ts:               float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operation":        str(self.operation),
            "asset_id":         str(self.asset_id),
            "provider":         str(self.provider),
            "source":           str(self.source),
            "bytes_downloaded": int(self.bytes_downloaded),
            "cache_hit":        bool(self.cache_hit),
            "ok":               bool(self.ok),
            "duration_ms":      float(self.duration_ms),
            "ts":               float(self.ts),
        }


class DownloadStatistics:
    def __init__(self) -> None:
        self._lock              = threading.Lock()
        self._records:          List[DownloadRecord] = []
        self._total_downloads   = 0
        self._cache_hits        = 0
        self._cache_misses      = 0
        self._total_bytes       = 0
        self._provider_counter: Counter = Counter()
        self._error_count       = 0

    def record(
        self,
        operation:        str = "download",
        asset_id:         str = "",
        provider:         str = "",
        source:           str = "",
        bytes_downloaded: int = 0,
        bytes_dl:         int = 0,   # legacy alias
        cache_hit:        bool = False,
        ok:               bool = True,
        duration_ms:      float = 0.0,
        error:            str = "",  # accepted, not stored
    ) -> None:
        """Append a download record. Never raises."""
        try:
            # Derive cache_hit from source when not explicitly set
            effective_cache_hit = cache_hit or (source == "cache")
            effective_bytes = bytes_downloaded or bytes_dl

            rec = DownloadRecord(
                operation=str(operation),
                asset_id=str(asset_id),
                provider=str(provider),
                source=str(source),
                bytes_downloaded=int(effective_bytes),
                cache_hit=bool(effective_cache_hit),
                ok=bool(ok),
                duration_ms=float(duration_ms),
            )
            with self._lock:
                if len(self._records) >= _MAX_RECORDS:
                    self._records = self._records[-(len(self._records) // 2):]
                self._records.append(rec)
                self._total_downloads += 1
                self._total_bytes += int(effective_bytes)
                if effective_cache_hit:
                    self._cache_hits += 1
                else:
                    self._cache_misses += 1
                if provider:
                    self._provider_counter[provider] += 1
                if not ok:
                    self._error_count += 1
        except Exception:
            pass

    def get_summary(self) -> Dict[str, Any]:
        with self._lock:
            total = max(self._cache_hits + self._cache_misses, 1)
            return {
                "total_downloads": self._total_downloads,
                "cache_hits":      self._cache_hits,
                "cache_misses":    self._cache_misses,
                "cache_hit_rate":  round(self._cache_hits / total, 4),
                "total_bytes":     self._total_bytes,
                "top_providers":   self._provider_counter.most_common(5),
                "error_count":     self._error_count,
                "record_count":    len(self._records),
            }

    def get_recent(self, n: int = 20) -> List[Dict[str, Any]]:
        with self._lock:
            return [r.to_dict() for r in self._records[-n:]]

    def reset(self) -> None:
        with self._lock:
            self._records.clear()
            self._total_downloads  = 0
            self._cache_hits       = 0
            self._cache_misses     = 0
            self._total_bytes      = 0
            self._provider_counter = Counter()
            self._error_count      = 0


_INSTANCE: Optional[DownloadStatistics] = None
_INSTANCE_LOCK = threading.Lock()


def get_download_statistics() -> DownloadStatistics:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = DownloadStatistics()
    return _INSTANCE


def reset_download_statistics_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
