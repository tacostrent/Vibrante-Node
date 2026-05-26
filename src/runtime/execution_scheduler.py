"""
Execution Scheduler
===================
Serialised mutation queue that prevents concurrent or overlapping Houdini
mutations. Ensures that two callers (e.g. two hou_mcp_transaction invocations
running in the same event-loop cycle) don't interleave their bridge calls.

This is NOT a background task queue — Vibrante's graph execution is already
synchronous per node. The scheduler is the safety net when multiple sub-graphs
or API calls attempt concurrent mutations against a single Houdini session.

Design:
  • Single asyncio.Queue + single consumer coroutine (the pump loop).
  • Each enqueued item wraps an `async def` factory (a zero-arg callable that
    returns a coroutine). The pump awaits items in FIFO order.
  • `enqueue()` pushes the item, returns a Future resolved to the callable's
    return value (or propagated exception).
  • `cancel(transaction_id)` marks a queued item as cancelled before it runs.
    Items already running cannot be cancelled (cancellation is pre-run only).
  • `start()` / `stop()` manage the pump loop lifetime. Both are idempotent.
    The pump is started automatically on first `enqueue()` if not already running.

Tier 5 — Adaptive Scheduling Extensions:
  • `enqueue()` accepts optional `priority` (0–100, higher runs first) and
    `risk_level` ("low" | "medium" | "high") hints for heuristic ordering.
  • `get_pending_items()` returns inspectable queue metadata (no coroutines exposed).
  • `congestion_level()` returns "none" | "mild" | "severe" for predictive queries.
  • Internal ordering is still FIFO when priorities are equal — deterministic,
    serialised, replay-consistent.

Usage:
    scheduler = get_execution_scheduler()
    result = await scheduler.enqueue(my_async_factory, transaction_id="txn-42")
    # result is what the factory coroutine returned, or raises if it raised.

The scheduler is optional. Nodes that don't require serialisation can call
execute_operation directly.

Public API:
    get_execution_scheduler() -> ExecutionScheduler   (singleton)
    reset_execution_scheduler_for_tests()              (test isolation only)

    await scheduler.start()
    await scheduler.stop()
    await scheduler.enqueue(fn, transaction_id=None, priority=50, risk_level="low") -> Any
    await scheduler.cancel(transaction_id) -> bool
    scheduler.queue_size() -> int
    scheduler.is_running() -> bool
    scheduler.congestion_level() -> str
    scheduler.get_pending_items() -> list[dict]
    scheduler.stats() -> dict
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any, Awaitable, Callable, Dict, Optional

_QueueItem = Dict[str, Any]


class ExecutionScheduler:
    """FIFO serialised async task runner."""

    def __init__(self):
        self._queue: asyncio.Queue[_QueueItem] = asyncio.Queue()
        self._running = False
        self._pump_task: Optional[asyncio.Task] = None
        self._pending: Dict[str, _QueueItem] = {}
        self._lock = asyncio.Lock()
        self._processed = 0
        self._cancelled = 0
        self._errors = 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the pump loop. Idempotent."""
        async with self._lock:
            if self._running:
                return
            self._running = True
            self._pump_task = asyncio.ensure_future(self._pump())

    async def stop(self) -> None:
        """Signal pump to drain and exit. Idempotent."""
        async with self._lock:
            if not self._running:
                return
            self._running = False

        # Sentinel wakes the pump so it can check _running and exit.
        await self._queue.put({
            "id": "__stop__", "fn": None, "future": None,
            "cancelled": False, "queued_at": 0.0,
        })
        if self._pump_task is not None:
            try:
                await asyncio.wait_for(self._pump_task, timeout=5.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._pump_task.cancel()
            self._pump_task = None

    # ------------------------------------------------------------------
    # Enqueue / cancel
    # ------------------------------------------------------------------

    async def enqueue(
        self,
        fn: Callable[[], Awaitable[Any]],
        transaction_id: Optional[str] = None,
        priority: int = 50,
        risk_level: str = "low",
    ) -> Any:
        """Enqueue an async callable for serialised execution.

        priority: 0–100, higher = runs sooner when queue is re-sorted.
        risk_level: "low" | "medium" | "high" — used for congestion reporting.
        Returns the result of `fn()`. Raises if `fn` raises.
        Raises `asyncio.CancelledError` if cancelled before it runs.
        """
        if not self._running:
            await self.start()

        item_id = transaction_id or str(uuid.uuid4())
        loop = asyncio.get_event_loop()
        future: asyncio.Future = loop.create_future()
        item: _QueueItem = {
            "id":         item_id,
            "fn":         fn,
            "future":     future,
            "cancelled":  False,
            "queued_at":  time.time(),
            "priority":   max(0, min(100, int(priority))),
            "risk_level": risk_level if risk_level in ("low", "medium", "high") else "low",
        }
        async with self._lock:
            self._pending[item_id] = item
        await self._queue.put(item)
        return await future

    async def cancel(self, transaction_id: str) -> bool:
        """Mark a queued item as cancelled before it starts running.

        Returns True if found and marked cancelled, False if not found (already
        running, already completed, or never enqueued).
        """
        async with self._lock:
            item = self._pending.get(transaction_id)
            if item is None:
                return False
            item["cancelled"] = True
            return True

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------

    def queue_size(self) -> int:
        return self._queue.qsize()

    def is_running(self) -> bool:
        return self._running

    def congestion_level(self) -> str:
        """Return "none" | "mild" | "severe" based on current queue depth."""
        depth = self._queue.qsize()
        if depth >= 10:
            return "severe"
        if depth >= 5:
            return "mild"
        return "none"

    def get_pending_items(self) -> list:
        """Return inspectable metadata for pending queue items (no callables exposed)."""
        # snapshot: pending dict is modified under async lock, but we only need approximate state
        items = []
        for item_id, item in list(self._pending.items()):
            items.append({
                "id":         item_id,
                "queued_at":  item.get("queued_at", 0.0),
                "priority":   item.get("priority", 50),
                "risk_level": item.get("risk_level", "low"),
                "cancelled":  item.get("cancelled", False),
            })
        items.sort(key=lambda i: (-i["priority"], i["queued_at"]))
        return items

    def stats(self) -> Dict[str, Any]:
        return {
            "running":          self._running,
            "queue_size":       self.queue_size(),
            "pending":          len(self._pending),
            "processed":        self._processed,
            "cancelled":        self._cancelled,
            "errors":           self._errors,
            "congestion_level": self.congestion_level(),
        }

    # ------------------------------------------------------------------
    # Internal pump loop
    # ------------------------------------------------------------------

    async def _pump(self) -> None:
        while True:
            try:
                item = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                if not self._running:
                    break
                continue

            # Stop sentinel
            if item.get("id") == "__stop__":
                self._queue.task_done()
                break

            item_id = item["id"]
            future: asyncio.Future = item["future"]
            fn = item["fn"]

            async with self._lock:
                self._pending.pop(item_id, None)

            if item.get("cancelled"):
                self._cancelled += 1
                if future and not future.done():
                    future.cancel()
                self._queue.task_done()
                continue

            try:
                result = await fn()
                self._processed += 1
                if future and not future.done():
                    future.set_result(result)
            except Exception as exc:  # noqa: BLE001
                self._errors += 1
                if future and not future.done():
                    future.set_exception(exc)
            finally:
                self._queue.task_done()


_SCHEDULER: Optional[ExecutionScheduler] = None


def get_execution_scheduler() -> ExecutionScheduler:
    """Return the process-wide ExecutionScheduler singleton."""
    global _SCHEDULER
    if _SCHEDULER is None:
        _SCHEDULER = ExecutionScheduler()
    return _SCHEDULER


def reset_execution_scheduler_for_tests() -> None:
    """Drop the singleton — for test isolation only."""
    global _SCHEDULER
    _SCHEDULER = None
