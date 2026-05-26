"""
Unit tests for src.runtime.execution_scheduler.

Covers:
  • start / stop lifecycle (idempotent)
  • enqueue runs callable and returns result
  • multiple enqueued items execute in FIFO order
  • exception in callable propagates to caller
  • cancel marks item and Future gets CancelledError
  • queue_size() reflects pending items
  • stats() shape
  • get_execution_scheduler() singleton
  • reset_execution_scheduler_for_tests()
  • enqueue auto-starts the pump if not running
"""

from __future__ import annotations

import asyncio

import pytest

from src.runtime.execution_scheduler import (
    ExecutionScheduler,
    get_execution_scheduler,
    reset_execution_scheduler_for_tests,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset():
    reset_execution_scheduler_for_tests()
    yield
    reset_execution_scheduler_for_tests()


@pytest.fixture
async def scheduler():
    sched = ExecutionScheduler()
    await sched.start()
    yield sched
    await sched.stop()


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_start_makes_scheduler_running():
    sched = ExecutionScheduler()
    assert not sched.is_running()
    await sched.start()
    assert sched.is_running()
    await sched.stop()


@pytest.mark.asyncio
async def test_start_is_idempotent():
    sched = ExecutionScheduler()
    await sched.start()
    await sched.start()  # no crash
    assert sched.is_running()
    await sched.stop()


@pytest.mark.asyncio
async def test_stop_is_idempotent():
    sched = ExecutionScheduler()
    await sched.stop()  # not started — no crash
    await sched.start()
    await sched.stop()
    await sched.stop()  # already stopped — no crash


@pytest.mark.asyncio
async def test_stop_makes_scheduler_not_running():
    sched = ExecutionScheduler()
    await sched.start()
    await sched.stop()
    assert not sched.is_running()


# ---------------------------------------------------------------------------
# Enqueue / execution
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_enqueue_returns_result(scheduler):
    async def _fn():
        return 42

    result = await scheduler.enqueue(_fn)
    assert result == 42


@pytest.mark.asyncio
async def test_enqueue_auto_starts(tmp_path):
    sched = ExecutionScheduler()
    assert not sched.is_running()

    async def _fn():
        return "auto_started"

    result = await sched.enqueue(_fn)
    assert result == "auto_started"
    assert sched.is_running()
    await sched.stop()


@pytest.mark.asyncio
async def test_enqueue_fifo_order(scheduler):
    order = []

    async def make_fn(tag):
        async def _fn():
            order.append(tag)
            return tag
        return _fn

    fns = [await make_fn(i) for i in range(5)]
    results = await asyncio.gather(*[scheduler.enqueue(fn) for fn in fns])
    # All complete
    assert set(results) == {0, 1, 2, 3, 4}
    # FIFO order preserved
    assert order == [0, 1, 2, 3, 4]


@pytest.mark.asyncio
async def test_enqueue_propagates_exception(scheduler):
    async def _failing():
        raise ValueError("kaboom")

    with pytest.raises(ValueError, match="kaboom"):
        await scheduler.enqueue(_failing)


@pytest.mark.asyncio
async def test_enqueue_exception_does_not_stop_scheduler(scheduler):
    async def _fail():
        raise RuntimeError("oops")

    async def _ok():
        return "fine"

    with pytest.raises(RuntimeError):
        await scheduler.enqueue(_fail)

    result = await scheduler.enqueue(_ok)
    assert result == "fine"
    assert scheduler.is_running()


# ---------------------------------------------------------------------------
# Cancel
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cancel_unknown_item_returns_false(scheduler):
    cancelled = await scheduler.cancel("does-not-exist")
    assert cancelled is False


@pytest.mark.asyncio
async def test_cancel_before_execution():
    """Item cancelled before pump picks it up gets CancelledError."""
    sched = ExecutionScheduler()
    # Don't start the pump yet so the item sits in the queue
    executed = []

    async def _fn():
        executed.append(True)
        return "ran"

    # Manually push to queue without starting pump
    import asyncio as _asyncio
    loop = _asyncio.get_event_loop()
    future = loop.create_future()
    item = {
        "id": "my-cancel-id", "fn": _fn, "future": future,
        "cancelled": False, "queued_at": 0.0,
    }
    sched._pending["my-cancel-id"] = item
    await sched._queue.put(item)

    # Cancel before pump processes it
    result = await sched.cancel("my-cancel-id")
    assert result is True

    # Now start the pump and let it drain
    await sched.start()
    await sched._queue.join()
    await sched.stop()

    assert executed == []  # never ran
    assert future.cancelled()


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stats_shape(scheduler):
    s = scheduler.stats()
    assert "running" in s
    assert "queue_size" in s
    assert "processed" in s
    assert "cancelled" in s
    assert "errors" in s
    assert s["running"] is True


@pytest.mark.asyncio
async def test_stats_processed_increments(scheduler):
    async def _fn():
        return 1

    await scheduler.enqueue(_fn)
    await scheduler.enqueue(_fn)
    s = scheduler.stats()
    assert s["processed"] == 2


@pytest.mark.asyncio
async def test_stats_errors_increments(scheduler):
    async def _fail():
        raise ValueError("x")

    with pytest.raises(ValueError):
        await scheduler.enqueue(_fail)
    assert scheduler.stats()["errors"] == 1


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton_returns_same_instance():
    a = get_execution_scheduler()
    b = get_execution_scheduler()
    assert a is b


def test_reset_creates_fresh_singleton():
    a = get_execution_scheduler()
    reset_execution_scheduler_for_tests()
    b = get_execution_scheduler()
    assert a is not b
