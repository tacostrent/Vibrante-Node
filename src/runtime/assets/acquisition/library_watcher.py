"""
Library Watcher (Tier 12.5)
============================
Detects newly downloaded assets by comparing directory snapshots.

Uses file-system modification times and sizes rather than real-time
OS file-system event APIs, ensuring cross-platform portability and
eliminating the need for OS-specific dependencies.

Workflow:
  1. Call watch(paths) to register directories to monitor.
  2. Call take_snapshot() to record the current state.
  3. When needed, call detect_new_assets() to find what changed.
  4. New assets are automatically registered with the DownloadRegistry.

Supported sources: VIBRANTE_FAB_LIBRARY, VIBRANTE_MEGASCANS_LIBRARY,
                   VIBRANTE_ASSET_STORAGE, or any custom path list.

Deterministic, thread-safe, no Houdini dependency, no network calls.
"""
from __future__ import annotations

import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .download_registry import get_download_registry

_SCAN_EXTENSIONS = frozenset({
    ".fbx", ".obj", ".gltf", ".glb",
    ".usd", ".usda", ".usdc", ".usdz",
    ".abc", ".blend", ".ma", ".mb",
    ".hip", ".bgeo",
})


@dataclass
class WatchEntry:
    watch_id:   str = field(default_factory=lambda: f"watch_{uuid.uuid4().hex[:8]}")
    path:       str = ""
    label:      str = ""
    active:     bool = True
    added_at:   float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "watch_id":  str(self.watch_id),
            "path":      str(self.path),
            "label":     str(self.label),
            "active":    bool(self.active),
            "added_at":  float(self.added_at),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "WatchEntry":
        d = d if isinstance(d, dict) else {}
        return cls(
            watch_id=str(d.get("watch_id") or f"watch_{uuid.uuid4().hex[:8]}"),
            path=str(d.get("path", "")),
            label=str(d.get("label", "")),
            active=bool(d.get("active", True)),
            added_at=float(d.get("added_at") or time.time()),
        )


@dataclass
class NewAssetEvent:
    event_id:       str = field(default_factory=lambda: f"evt_{uuid.uuid4().hex[:8]}")
    detected_path:  str = ""
    watch_path:     str = ""
    provider_hint:  str = ""
    file_format:    str = ""
    file_size:      int = 0
    detected_at:    float = field(default_factory=time.time)
    registered:     bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id":      str(self.event_id),
            "detected_path": str(self.detected_path),
            "watch_path":    str(self.watch_path),
            "provider_hint": str(self.provider_hint),
            "file_format":   str(self.file_format),
            "file_size":     int(self.file_size),
            "detected_at":   float(self.detected_at),
            "registered":    bool(self.registered),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "NewAssetEvent":
        d = d if isinstance(d, dict) else {}
        return cls(
            event_id=str(d.get("event_id") or f"evt_{uuid.uuid4().hex[:8]}"),
            detected_path=str(d.get("detected_path", "")),
            watch_path=str(d.get("watch_path", "")),
            provider_hint=str(d.get("provider_hint", "")),
            file_format=str(d.get("file_format", "")),
            file_size=int(d.get("file_size") or 0),
            detected_at=float(d.get("detected_at") or time.time()),
            registered=bool(d.get("registered", False)),
        )


def _infer_provider(watch_path: str) -> str:
    path_lower = watch_path.lower()
    fab_lib  = os.environ.get("VIBRANTE_FAB_LIBRARY", "").lower()
    ms_lib   = os.environ.get("VIBRANTE_MEGASCANS_LIBRARY", "").lower()
    if ms_lib and path_lower.startswith(ms_lib):
        return "megascans"
    if fab_lib and path_lower.startswith(fab_lib):
        return "fab"
    if "megascans" in path_lower or "bridge" in path_lower:
        return "megascans"
    if "fab" in path_lower:
        return "fab"
    return "local"


def _snapshot_dir(path: str, max_depth: int = 4) -> Dict[str, int]:
    """Return {filepath: mtime_ns} for all asset files under path."""
    snapshot: Dict[str, int] = {}
    try:
        root_parts_count = len(path.replace("\\", "/").split("/"))
        for root, dirs, files in os.walk(path):
            dirs.sort()
            depth = len(root.replace("\\", "/").split("/")) - root_parts_count
            if depth > max_depth:
                dirs.clear()
                continue
            for fname in files:
                ext = os.path.splitext(fname)[1].lower()
                if ext in _SCAN_EXTENSIONS:
                    fpath = os.path.join(root, fname)
                    try:
                        snapshot[fpath] = int(os.path.getmtime(fpath) * 1e9)
                    except Exception:
                        pass
    except Exception:
        pass
    return snapshot


class LibraryWatcher:
    def __init__(self) -> None:
        self._lock       = threading.Lock()
        self._watches:   Dict[str, WatchEntry] = {}
        self._snapshots: Dict[str, Dict[str, int]] = {}   # watch_path → {filepath: mtime_ns}
        self._events:    List[NewAssetEvent] = []
        self._watch_count = 0
        self._detect_count = 0
        self._auto_register = True
        self._init_default_watches()

    def _init_default_watches(self) -> None:
        for env_var, label in (
            ("VIBRANTE_FAB_LIBRARY",       "fab_library"),
            ("VIBRANTE_MEGASCANS_LIBRARY",  "megascans_library"),
        ):
            path = os.environ.get(env_var, "").strip()
            if path and os.path.isdir(path):
                self._add_watch(path, label)

    def _add_watch(self, path: str, label: str = "") -> WatchEntry:
        entry = WatchEntry(path=path, label=label or os.path.basename(path))
        with self._lock:
            self._watches[path] = entry
        return entry

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def watch(self, paths: List[str], label: str = "") -> List[WatchEntry]:
        """Register one or more directories to monitor. Never raises."""
        added: List[WatchEntry] = []
        try:
            for path in (paths if isinstance(paths, list) else []):
                path = str(path).strip()
                if not path:
                    continue
                entry = self._add_watch(path, label)
                added.append(entry)
                with self._lock:
                    self._watch_count += 1
        except Exception:
            pass
        return added

    def unwatch(self, path: str) -> bool:
        path = str(path).strip()
        with self._lock:
            if path in self._watches:
                self._watches[path].active = False
                self._watches.pop(path, None)
                self._snapshots.pop(path, None)
                return True
            return False

    def list_watches(self) -> List[WatchEntry]:
        with self._lock:
            return [w for w in self._watches.values() if w.active]

    def take_snapshot(self) -> Dict[str, int]:
        """Record current state of all watched directories. Returns total file count."""
        total = 0
        with self._lock:
            watches = list(self._watches.values())
        for watch in watches:
            if not watch.active or not os.path.isdir(watch.path):
                continue
            snap = _snapshot_dir(watch.path)
            with self._lock:
                self._snapshots[watch.path] = snap
            total += len(snap)
        return total

    def detect_new_assets(self) -> List[NewAssetEvent]:
        """Compare current state against snapshot and return newly appeared files."""
        try:
            return self._do_detect()
        except Exception as exc:
            return []

    def _do_detect(self) -> List[NewAssetEvent]:
        with self._lock:
            watches = list(self._watches.values())
            old_snaps = {p: dict(s) for p, s in self._snapshots.items()}

        new_events: List[NewAssetEvent] = []

        for watch in watches:
            if not watch.active or not os.path.isdir(watch.path):
                continue
            old_snap = old_snaps.get(watch.path, {})
            new_snap = _snapshot_dir(watch.path)

            # Files that are new (not in old snapshot)
            for fpath, mtime_ns in new_snap.items():
                if fpath not in old_snap:
                    ext = os.path.splitext(fpath)[1].lower().lstrip(".")
                    try:
                        size = os.path.getsize(fpath)
                    except Exception:
                        size = 0
                    provider_hint = _infer_provider(watch.path)
                    event = NewAssetEvent(
                        detected_path=fpath,
                        watch_path=watch.path,
                        provider_hint=provider_hint,
                        file_format=ext,
                        file_size=size,
                    )
                    new_events.append(event)

                    # Auto-register in DownloadRegistry
                    if self._auto_register:
                        try:
                            asset_id = os.path.splitext(os.path.basename(fpath))[0]
                            get_download_registry().register(
                                asset_id=asset_id,
                                provider=provider_hint,
                                local_path=fpath,
                                formats=[ext],
                                provenance={"source": "library_watcher", "watch_path": watch.path},
                            )
                            event.registered = True
                        except Exception:
                            pass

            # Update snapshot
            with self._lock:
                self._snapshots[watch.path] = new_snap

        with self._lock:
            self._events.extend(new_events)
            self._detect_count += 1

        return new_events

    def register_asset(
        self,
        file_path: str,
        provider_hint: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[NewAssetEvent]:
        """Manually register a newly appeared asset file."""
        try:
            file_path = str(file_path).strip()
            if not file_path:
                return None
            ext  = os.path.splitext(file_path)[1].lower().lstrip(".")
            size = 0
            try:
                size = os.path.getsize(file_path)
            except Exception:
                pass
            provider = provider_hint or _infer_provider(file_path)
            event = NewAssetEvent(
                detected_path=file_path,
                watch_path=os.path.dirname(file_path),
                provider_hint=provider,
                file_format=ext,
                file_size=size,
            )
            asset_id = str((metadata or {}).get("asset_id") or os.path.splitext(os.path.basename(file_path))[0])
            name     = str((metadata or {}).get("name") or asset_id)
            get_download_registry().register(
                asset_id=asset_id,
                provider=provider,
                local_path=file_path,
                name=name,
                formats=[ext],
                provenance={"source": "manual_registration", **(metadata or {})},
            )
            event.registered = True
            with self._lock:
                self._events.append(event)
            return event
        except Exception:
            return None

    def get_recent_events(self, limit: int = 50) -> List[NewAssetEvent]:
        with self._lock:
            return list(self._events[-limit:])

    def clear_events(self) -> int:
        with self._lock:
            count = len(self._events)
            self._events.clear()
            return count

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "watched_paths":  len(self._watches),
                "total_events":   len(self._events),
                "detect_count":   self._detect_count,
                "watch_count":    self._watch_count,
                "auto_register":  self._auto_register,
            }


_INSTANCE: Optional[LibraryWatcher] = None
_INSTANCE_LOCK = threading.Lock()


def get_library_watcher() -> LibraryWatcher:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = LibraryWatcher()
    return _INSTANCE


def reset_library_watcher_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
