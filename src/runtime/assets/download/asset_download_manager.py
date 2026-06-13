"""
Asset Download Manager (Tier 12 — Asset Ecosystem Expansion)
=============================================================
Manages asset acquisition. Downloads are SIMULATED (no real HTTP).

For seed data assets: download_asset() marks the task as "completed" immediately.
Real download logic would be wired in a future tier via the same interface.

Status values: "queued", "downloading", "completed", "failed", "cancelled"

Public API:
    DownloadTask                         — task descriptor dict
    AssetDownloadManager                 — manager class
    get_asset_download_manager()         — singleton
    reset_asset_download_manager_for_tests()
"""

from __future__ import annotations

import os
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

from src.runtime.assets.schema import AssetDescriptor

# Status constants
STATUS_QUEUED      = "queued"
STATUS_DOWNLOADING = "downloading"
STATUS_COMPLETED   = "completed"
STATUS_FAILED      = "failed"
STATUS_CANCELLED   = "cancelled"


class DownloadTask:
    """Descriptor for a single asset download task."""

    def __init__(
        self,
        asset_descriptor: AssetDescriptor,
        destination: Optional[str] = None,
    ) -> None:
        self.task_id:      str   = f"dl_{uuid.uuid4().hex[:12]}"
        self.asset_id:     str   = asset_descriptor.asset_id
        self.provider:     str   = asset_descriptor.provider
        self.url:          str   = asset_descriptor.download_url
        self.destination:  str   = destination or ""
        self.status:       str   = STATUS_QUEUED
        self.progress:     float = 0.0
        self.error:        str   = ""
        self.created_at:   float = time.time()
        self.completed_at: Optional[float] = None
        # Store asset name for reference
        self.asset_name:   str   = asset_descriptor.name

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id":      self.task_id,
            "asset_id":     self.asset_id,
            "provider":     self.provider,
            "url":          self.url,
            "destination":  self.destination,
            "status":       self.status,
            "progress":     self.progress,
            "error":        self.error,
            "created_at":   self.created_at,
            "completed_at": self.completed_at,
            "asset_name":   self.asset_name,
        }


class AssetDownloadManager:
    """
    Manages asset download tasks.

    Downloads are SIMULATED — no real HTTP requests in this implementation.
    For seed data assets, download_asset() marks the task as completed
    immediately. Real download logic would replace the simulation block.
    """

    def __init__(self) -> None:
        self._lock:  threading.Lock = threading.Lock()
        self._tasks: Dict[str, DownloadTask] = {}  # task_id → DownloadTask

    # ------------------------------------------------------------------
    # Queue management
    # ------------------------------------------------------------------

    def queue_download(
        self,
        asset_descriptor: AssetDescriptor,
        destination: Optional[str] = None,
    ) -> str:
        """
        Queue an asset for download.

        Args:
            asset_descriptor: The asset to download.
            destination:      Local path to save the file.
                              Defaults to a path under the asset storage root.

        Returns:
            task_id (str)
        """
        if not destination:
            destination = self._default_destination(
                asset_descriptor.provider, asset_descriptor.asset_id
            )
        task = DownloadTask(asset_descriptor, destination)
        with self._lock:
            self._tasks[task.task_id] = task
        return task.task_id

    def cancel_download(self, task_id: str) -> bool:
        """
        Cancel a queued download.

        Returns True if the task was found and is in a cancellable state
        (queued or downloading).  Does not stop already-completed tasks.
        """
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return False
            if task.status in (STATUS_QUEUED, STATUS_DOWNLOADING):
                task.status = STATUS_CANCELLED
                return True
            return False

    # ------------------------------------------------------------------
    # Download (simulated)
    # ------------------------------------------------------------------

    def download_asset(self, task_id: str) -> bool:
        """
        Execute the download for a queued task.

        SIMULATED: Marks the task as completed immediately.
        In a real implementation, this would issue an HTTP request,
        write bytes to disk, and update progress.

        Returns:
            True on success, False on failure.
        """
        with self._lock:
            task = self._tasks.get(task_id)
        if task is None:
            return False
        if task.status == STATUS_CANCELLED:
            return False
        if task.status == STATUS_COMPLETED:
            return True

        # Simulate download
        with self._lock:
            task.status = STATUS_DOWNLOADING
            task.progress = 0.5

        # Simulate immediate completion (seed data — no real file transfer)
        with self._lock:
            task.status = STATUS_COMPLETED
            task.progress = 1.0
            task.completed_at = time.time()

        return True

    # ------------------------------------------------------------------
    # Status / query
    # ------------------------------------------------------------------

    def validate_download(self, task_id: str) -> Dict[str, Any]:
        """
        Validate a completed download.

        For simulated downloads: always returns valid=True when completed.
        """
        with self._lock:
            task = self._tasks.get(task_id)
        if task is None:
            return {"valid": False, "file_exists": False, "checksum_ok": False, "size_ok": False}
        if task.status != STATUS_COMPLETED:
            return {"valid": False, "file_exists": False, "checksum_ok": False, "size_ok": False}
        # Real implementation would check file on disk
        file_exists = bool(task.destination and os.path.isfile(task.destination))
        return {
            "valid":       True,  # Simulated: always valid
            "file_exists": file_exists,
            "checksum_ok": True,  # Simulated
            "size_ok":     True,  # Simulated
        }

    def get_download_status(self, task_id: str) -> Dict[str, Any]:
        """Return the current status dict for a task."""
        with self._lock:
            task = self._tasks.get(task_id)
        if task is None:
            return {
                "task_id": task_id,
                "status":  "not_found",
                "error":   f"Task '{task_id}' not found.",
            }
        return task.to_dict()

    def get_all_downloads(self) -> List[Dict[str, Any]]:
        """Return all download task dicts, sorted by created_at."""
        with self._lock:
            tasks = list(self._tasks.values())
        return sorted([t.to_dict() for t in tasks], key=lambda d: d["created_at"])

    def clear_completed(self) -> int:
        """Remove all completed and cancelled tasks.  Returns count removed."""
        with self._lock:
            to_remove = [
                tid for tid, t in self._tasks.items()
                if t.status in (STATUS_COMPLETED, STATUS_CANCELLED, STATUS_FAILED)
            ]
            for tid in to_remove:
                del self._tasks[tid]
        return len(to_remove)

    def get_statistics(self) -> Dict[str, Any]:
        """Return usage statistics."""
        with self._lock:
            tasks = list(self._tasks.values())
        by_status: Dict[str, int] = {}
        for task in tasks:
            by_status[task.status] = by_status.get(task.status, 0) + 1
        return {
            "total_tasks":     len(tasks),
            "by_status":       by_status,
            "queued":          by_status.get(STATUS_QUEUED, 0),
            "downloading":     by_status.get(STATUS_DOWNLOADING, 0),
            "completed":       by_status.get(STATUS_COMPLETED, 0),
            "failed":          by_status.get(STATUS_FAILED, 0),
            "cancelled":       by_status.get(STATUS_CANCELLED, 0),
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _default_destination(self, provider: str, asset_id: str) -> str:
        """Build a default destination path."""
        try:
            from src.runtime.assets.cache.asset_storage import get_asset_storage
            root = get_asset_storage().get_storage_root()
        except Exception:
            root = os.path.expanduser("~/VibranteAssets")
        return os.path.join(root, provider, asset_id)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_MANAGER: Optional[AssetDownloadManager] = None
_MANAGER_LOCK = threading.Lock()


def get_asset_download_manager() -> AssetDownloadManager:
    """Return the module-level singleton AssetDownloadManager."""
    global _MANAGER
    if _MANAGER is None:
        with _MANAGER_LOCK:
            if _MANAGER is None:
                _MANAGER = AssetDownloadManager()
    return _MANAGER


def reset_asset_download_manager_for_tests() -> None:
    """Replace the singleton.  For test isolation only."""
    global _MANAGER
    with _MANAGER_LOCK:
        _MANAGER = None
