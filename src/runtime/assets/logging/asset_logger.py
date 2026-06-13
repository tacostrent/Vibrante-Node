"""
Asset Logger (Tier 8 — Asset Intelligence Runtime)
====================================================
Lightweight pipeline trace log for the Asset Intelligence layer.

Records pipeline events with stage name, duration, counts, and notes.
In-memory only — no disk I/O.  Capped at 500 entries.

Public API:
    AssetLogEntry
    AssetLogger
    get_asset_logger()
    reset_asset_logger_for_tests()
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_MAX_ENTRIES = 500

ASSET_LOG_EVENT_TYPES = frozenset({
    "discovery_start",
    "discovery_complete",
    "validation_start",
    "validation_complete",
    "ranking_start",
    "ranking_complete",
    "recommendation_start",
    "recommendation_complete",
    "cache_hit",
    "cache_miss",
    "provider_query",
    "error",
    "warning",
})


@dataclass
class AssetLogEntry:
    """A single pipeline event record."""

    event_type: str
    stage:      str       = ""
    provider:   str       = ""
    category:   str       = ""
    zone:       str       = ""
    count:      int       = 0
    duration:   float     = 0.0
    notes:      str       = ""
    timestamp:  float     = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "stage":      self.stage,
            "provider":   self.provider,
            "category":   self.category,
            "zone":       self.zone,
            "count":      self.count,
            "duration":   self.duration,
            "notes":      self.notes,
            "timestamp":  self.timestamp,
        }


class AssetLogger:
    """In-memory pipeline trace log capped at 500 entries."""

    def __init__(self) -> None:
        self._lock:    threading.Lock     = threading.Lock()
        self._entries: List[AssetLogEntry] = []
        self._event_count: int = 0

    def log(
        self,
        event_type: str,
        stage: str = "",
        provider: str = "",
        category: str = "",
        zone: str = "",
        count: int = 0,
        duration: float = 0.0,
        notes: str = "",
    ) -> None:
        """Record a pipeline event."""
        normalized = event_type if event_type in ASSET_LOG_EVENT_TYPES else "warning"
        entry = AssetLogEntry(
            event_type=normalized,
            stage=stage,
            provider=provider,
            category=category,
            zone=zone,
            count=count,
            duration=duration,
            notes=notes,
        )
        with self._lock:
            if len(self._entries) >= _MAX_ENTRIES:
                self._entries = self._entries[_MAX_ENTRIES // 2:]
            self._entries.append(entry)
            self._event_count += 1

    def get_entries(
        self,
        event_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[AssetLogEntry]:
        with self._lock:
            entries = list(self._entries)
        if event_type:
            entries = [e for e in entries if e.event_type == event_type]
        return entries[-limit:]

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            n = len(self._entries)
        return {
            "entry_count":   n,
            "total_events":  self._event_count,
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[AssetLogger] = None
_INSTANCE_LOCK = threading.Lock()


def get_asset_logger() -> AssetLogger:
    """Return the module-level singleton AssetLogger."""
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = AssetLogger()
    return _INSTANCE


def reset_asset_logger_for_tests() -> None:
    """Replace the singleton.  For test isolation only."""
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
