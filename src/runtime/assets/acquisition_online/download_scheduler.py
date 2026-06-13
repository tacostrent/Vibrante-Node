"""
Download Scheduler (Tier 12.9)
================================
Controls acquisition execution from the download queue.

Features:
  - Deterministic single-threaded execution (no ThreadPoolExecutor to keep side effects testable)
  - Rate-limit handling via configurable inter-download delay
  - Pause / resume support
  - Cancel running batch
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .download_queue import get_download_queue, DownloadTask
from .asset_fetcher import get_asset_fetcher


@dataclass
class SchedulerResult:
    ok:           bool  = False
    total:        int   = 0
    succeeded:    int   = 0
    failed:       int   = 0
    skipped:      int   = 0
    duration_ms:  float = 0.0
    task_results: List[Dict[str, Any]] = field(default_factory=list)
    error:        str   = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok":           bool(self.ok),
            "total":        int(self.total),
            "succeeded":    int(self.succeeded),
            "failed":       int(self.failed),
            "skipped":      int(self.skipped),
            "duration_ms":  float(self.duration_ms),
            "task_results": list(self.task_results),
            "error":        str(self.error),
        }


class DownloadScheduler:
    def __init__(self) -> None:
        self._lock         = threading.Lock()
        self._paused       = False
        self._cancelled    = False
        self._delay_s      = 0.1       # inter-download delay for rate limiting
        self._total_runs   = 0
        self._total_errors = 0

    def schedule_download(
        self,
        asset_id: str,
        provider: str = "",
        quality:  str = "medium",
        dest_dir: str = "",
        priority: int = 5,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DownloadTask:
        """Enqueue an asset for scheduled download. Never raises."""
        try:
            return get_download_queue().enqueue(
                asset_id=asset_id,
                provider=provider,
                quality=quality,
                dest_dir=dest_dir,
                priority=priority,
                metadata=metadata,
            )
        except Exception as exc:
            from .download_queue import DownloadTask
            return DownloadTask(asset_id=str(asset_id), status="failed", error=str(exc))

    def process_queue(
        self,
        max_tasks: int = 50,
        dest_dir:  str = "",
    ) -> SchedulerResult:
        """Process up to max_tasks pending downloads from the queue. Never raises."""
        t0 = time.time()
        results: List[Dict[str, Any]] = []
        succeeded = failed = skipped = 0
        try:
            queue   = get_download_queue()
            fetcher = get_asset_fetcher()
            processed = 0
            while processed < max_tasks:
                with self._lock:
                    if self._cancelled:
                        break
                    if self._paused:
                        time.sleep(0.05)
                        continue
                task = queue.dequeue()
                if task is None:
                    break
                fetch_result = fetcher.fetch_asset(
                    asset_id=task.asset_id,
                    provider=task.provider,
                    dest_dir=task.dest_dir or dest_dir,
                    quality=task.quality,
                )
                processed += 1
                if fetch_result.ok:
                    queue.complete(task.task_id)
                    succeeded += 1
                else:
                    queue.fail(task.task_id, error=fetch_result.error)
                    failed += 1
                    with self._lock:
                        self._total_errors += 1
                results.append({
                    "task_id":     task.task_id,
                    "asset_id":    task.asset_id,
                    "ok":          fetch_result.ok,
                    "source":      fetch_result.source,
                    "local_path":  fetch_result.local_path,
                    "error":       fetch_result.error,
                })
                time.sleep(self._delay_s)
            with self._lock:
                self._total_runs += 1
                self._cancelled = False
            return SchedulerResult(
                ok=True, total=succeeded + failed,
                succeeded=succeeded, failed=failed, skipped=skipped,
                duration_ms=round((time.time() - t0) * 1000, 1),
                task_results=results,
            )
        except Exception as exc:
            return SchedulerResult(
                ok=False, total=succeeded + failed,
                succeeded=succeeded, failed=failed,
                duration_ms=round((time.time() - t0) * 1000, 1),
                task_results=results, error=str(exc),
            )

    def pause(self) -> None:
        with self._lock:
            self._paused = True

    def resume(self) -> None:
        with self._lock:
            self._paused = False

    def cancel(self) -> None:
        with self._lock:
            self._cancelled = True
            self._paused    = False

    def set_rate_limit_delay(self, seconds: float) -> None:
        with self._lock:
            self._delay_s = max(0.0, float(seconds))

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            queue_stats = get_download_queue().get_statistics()
            return {
                "total_runs":   self._total_runs,
                "total_errors": self._total_errors,
                "paused":       self._paused,
                "delay_s":      self._delay_s,
                "queue":        queue_stats,
            }


_INSTANCE: Optional[DownloadScheduler] = None
_INSTANCE_LOCK = threading.Lock()


def get_download_scheduler() -> DownloadScheduler:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = DownloadScheduler()
    return _INSTANCE


def reset_download_scheduler_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
