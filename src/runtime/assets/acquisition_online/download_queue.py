"""
Download Queue (Tier 12.9)
============================
Persistent, deterministically-ordered download task queue.

Ordering: priority (higher = sooner), then enqueue_time (FIFO within same priority).
Status transitions: pending → in_progress → completed | failed | cancelled
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .download_serializer import get_download_serializer

ENV_ASSET_CACHE     = "VIBRANTE_ASSET_CACHE"
_QUEUE_FILENAME     = "download_queue.json"
_VALID_STATUSES     = frozenset({"pending", "in_progress", "completed", "failed", "cancelled"})


@dataclass
class DownloadTask:
    task_id:       str = field(default_factory=lambda: f"dl_{uuid.uuid4().hex[:10]}")
    asset_id:      str = ""
    provider:      str = ""
    quality:       str = "medium"
    dest_dir:      str = ""
    priority:      int = 5         # 1 (lowest) – 10 (highest)
    status:        str = "pending"
    enqueue_time:  float = field(default_factory=time.time)
    started_at:    Optional[float] = None
    completed_at:  Optional[float] = None
    error:         str = ""
    retry_count:   int = 0
    metadata:      Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id":      str(self.task_id),
            "asset_id":     str(self.asset_id),
            "provider":     str(self.provider),
            "quality":      str(self.quality),
            "dest_dir":     str(self.dest_dir),
            "priority":     int(self.priority),
            "status":       str(self.status),
            "enqueue_time": float(self.enqueue_time),
            "started_at":   self.started_at,
            "completed_at": self.completed_at,
            "error":        str(self.error),
            "retry_count":  int(self.retry_count),
            "metadata":     dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DownloadTask":
        d = d if isinstance(d, dict) else {}
        return cls(
            task_id=str(d.get("task_id") or f"dl_{uuid.uuid4().hex[:10]}"),
            asset_id=str(d.get("asset_id", "")),
            provider=str(d.get("provider", "")),
            quality=str(d.get("quality", "medium")),
            dest_dir=str(d.get("dest_dir", "")),
            priority=int(d.get("priority", 5)),
            status=str(d.get("status", "pending")),
            enqueue_time=float(d.get("enqueue_time") or time.time()),
            started_at=d.get("started_at"),
            completed_at=d.get("completed_at"),
            error=str(d.get("error", "")),
            retry_count=int(d.get("retry_count", 0)),
            metadata=dict(d.get("metadata") or {}),
        )


class DownloadQueue:
    _MAX_SIZE = 5000

    def __init__(self) -> None:
        self._lock  = threading.Lock()
        self._tasks: Dict[str, DownloadTask] = {}
        self._load_from_disk()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _queue_path(self) -> Optional[str]:
        storage = os.environ.get(ENV_ASSET_CACHE, "").strip()
        if not storage:
            return None
        return os.path.join(storage, _QUEUE_FILENAME)

    def _load_from_disk(self) -> None:
        try:
            path = self._queue_path()
            if not path or not os.path.isfile(path):
                return
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return
            with self._lock:
                for tid, td in (data.get("tasks") or {}).items():
                    task = DownloadTask.from_dict(td)
                    self._tasks[task.task_id] = task
        except Exception:
            pass

    def _save_to_disk(self) -> None:
        try:
            path = self._queue_path()
            if not path:
                return
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            with self._lock:
                payload = {
                    "__download_schema_version__": "1.0.0",
                    "tasks": {tid: t.to_dict() for tid, t in self._tasks.items()},
                }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, sort_keys=True)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Queue operations
    # ------------------------------------------------------------------

    def enqueue(
        self,
        asset_id:  str,
        provider:  str = "",
        quality:   str = "medium",
        dest_dir:  str = "",
        priority:  int = 5,
        metadata:  Optional[Dict[str, Any]] = None,
    ) -> DownloadTask:
        """Add a task to the queue. Returns the created task. Never raises."""
        try:
            asset_id = str(asset_id).strip()
            if not asset_id:
                return DownloadTask(status="failed", error="asset_id is required")
            with self._lock:
                # Dedup: don't enqueue same asset_id+provider if pending
                for t in self._tasks.values():
                    if t.asset_id == asset_id and t.provider == str(provider) and \
                       t.status in ("pending", "in_progress"):
                        return t
                if len(self._tasks) >= self._MAX_SIZE:
                    # Evict oldest completed/cancelled tasks
                    evictable = sorted(
                        [t for t in self._tasks.values() if t.status in ("completed", "cancelled")],
                        key=lambda t: t.enqueue_time,
                    )
                    for t in evictable[:len(self._tasks) - self._MAX_SIZE + 1]:
                        self._tasks.pop(t.task_id, None)
                task = DownloadTask(
                    asset_id=asset_id,
                    provider=str(provider),
                    quality=str(quality),
                    dest_dir=str(dest_dir),
                    priority=max(1, min(10, int(priority))),
                    metadata=dict(metadata or {}),
                )
                self._tasks[task.task_id] = task
            self._save_to_disk()
            return task
        except Exception as exc:
            return DownloadTask(asset_id=str(asset_id), status="failed", error=str(exc))

    def dequeue(self) -> Optional[DownloadTask]:
        """Remove and return the next pending task (highest priority, oldest first)."""
        try:
            with self._lock:
                pending = [t for t in self._tasks.values() if t.status == "pending"]
                if not pending:
                    return None
                # Sort by priority (desc) then enqueue_time (asc)
                pending.sort(key=lambda t: (-t.priority, t.enqueue_time))
                task = pending[0]
                task.status     = "in_progress"
                task.started_at = time.time()
            self._save_to_disk()
            return task
        except Exception:
            return None

    def complete(self, task_id: str) -> bool:
        """Mark a task as completed."""
        return self._set_status(task_id, "completed")

    def fail(self, task_id: str, error: str = "") -> bool:
        """Mark a task as failed."""
        try:
            with self._lock:
                task = self._tasks.get(task_id)
                if not task:
                    return False
                task.status       = "failed"
                task.completed_at = time.time()
                task.error        = str(error)
            self._save_to_disk()
            return True
        except Exception:
            return False

    def cancel(self, task_id: str) -> bool:
        """Cancel a pending task."""
        return self._set_status(task_id, "cancelled")

    def retry(self, task_id: str) -> bool:
        """Reset a failed task to pending for retry."""
        try:
            with self._lock:
                task = self._tasks.get(task_id)
                if not task or task.status not in ("failed", "cancelled"):
                    return False
                task.status      = "pending"
                task.error       = ""
                task.retry_count += 1
                task.started_at  = None
                task.completed_at= None
            self._save_to_disk()
            return True
        except Exception:
            return False

    def _set_status(self, task_id: str, status: str) -> bool:
        try:
            with self._lock:
                task = self._tasks.get(task_id)
                if not task:
                    return False
                task.status       = status
                task.completed_at = time.time()
            self._save_to_disk()
            return True
        except Exception:
            return False

    def get_status(self, task_id: str) -> Optional[DownloadTask]:
        with self._lock:
            return self._tasks.get(task_id)

    def get_pending(self) -> List[DownloadTask]:
        with self._lock:
            return sorted(
                [t for t in self._tasks.values() if t.status == "pending"],
                key=lambda t: (-t.priority, t.enqueue_time),
            )

    def get_all(self) -> List[DownloadTask]:
        with self._lock:
            return sorted(self._tasks.values(), key=lambda t: t.enqueue_time)

    def clear_completed(self) -> int:
        """Remove all completed and cancelled tasks. Returns count removed."""
        try:
            with self._lock:
                to_remove = [tid for tid, t in self._tasks.items()
                             if t.status in ("completed", "cancelled")]
                for tid in to_remove:
                    del self._tasks[tid]
            self._save_to_disk()
            return len(to_remove)
        except Exception:
            return 0

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            by_status: Dict[str, int] = {}
            for t in self._tasks.values():
                by_status[t.status] = by_status.get(t.status, 0) + 1
            return {"total": len(self._tasks), "by_status": by_status}


_INSTANCE: Optional[DownloadQueue] = None
_INSTANCE_LOCK = threading.Lock()


def get_download_queue() -> DownloadQueue:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = DownloadQueue()
    return _INSTANCE


def reset_download_queue_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
