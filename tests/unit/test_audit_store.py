"""
Unit tests for src.runtime.audit_store.

Covers:
  • log_transaction assigns audit_id + audit_ts and persists
  • get_transaction finds by id, transaction_id, and audit_id
  • query_transactions returns newest first, respects limit
  • query_transactions status filter
  • compact() prunes by age and by max_records
  • in-memory-only store (path=None)
  • disk round-trip: write → reload from JSONL
  • corrupt lines in JSONL are skipped
  • stats() shape
  • get_audit_store() singleton
  • reset_audit_store_for_tests()
"""

from __future__ import annotations

import json
import time

import pytest

from src.runtime.audit_store import AuditStore, get_audit_store, reset_audit_store_for_tests


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset():
    reset_audit_store_for_tests()
    yield
    reset_audit_store_for_tests()


@pytest.fixture
def mem_store():
    """In-memory AuditStore — no disk I/O."""
    return AuditStore(path=None)


# ---------------------------------------------------------------------------
# log_transaction
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_log_assigns_audit_id(mem_store):
    audit_id = await mem_store.log_transaction({"status": "committed", "name": "t1"})
    assert isinstance(audit_id, str) and len(audit_id) >= 32


@pytest.mark.asyncio
async def test_log_assigns_audit_ts(mem_store):
    before = time.time()
    await mem_store.log_transaction({"status": "committed"})
    records = await mem_store.query_transactions(limit=1)
    assert records[0]["audit_ts"] >= before


@pytest.mark.asyncio
async def test_log_preserves_existing_audit_id(mem_store):
    await mem_store.log_transaction({"audit_id": "my-custom-id", "status": "committed"})
    record = await mem_store.get_transaction("my-custom-id")
    assert record is not None
    assert record["audit_id"] == "my-custom-id"


@pytest.mark.asyncio
async def test_log_multiple_records(mem_store):
    for i in range(5):
        await mem_store.log_transaction({"seq": i, "status": "committed"})
    records = await mem_store.query_transactions(limit=10)
    assert len(records) == 5


# ---------------------------------------------------------------------------
# get_transaction
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_by_audit_id(mem_store):
    audit_id = await mem_store.log_transaction({"status": "committed"})
    r = await mem_store.get_transaction(audit_id)
    assert r is not None
    assert r["audit_id"] == audit_id


@pytest.mark.asyncio
async def test_get_by_transaction_id(mem_store):
    await mem_store.log_transaction({"transaction_id": "txn-abc", "status": "committed"})
    r = await mem_store.get_transaction("txn-abc")
    assert r is not None


@pytest.mark.asyncio
async def test_get_by_id_field(mem_store):
    await mem_store.log_transaction({"id": "manager-uuid-xyz", "status": "committed"})
    r = await mem_store.get_transaction("manager-uuid-xyz")
    assert r is not None


@pytest.mark.asyncio
async def test_get_unknown_returns_none(mem_store):
    r = await mem_store.get_transaction("does-not-exist")
    assert r is None


# ---------------------------------------------------------------------------
# query_transactions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_query_returns_newest_first(mem_store):
    for i in range(3):
        await mem_store.log_transaction({"seq": i, "status": "committed"})
    records = await mem_store.query_transactions(limit=10)
    seqs = [r["seq"] for r in records]
    assert seqs == [2, 1, 0]


@pytest.mark.asyncio
async def test_query_respects_limit(mem_store):
    for i in range(10):
        await mem_store.log_transaction({"seq": i})
    records = await mem_store.query_transactions(limit=3)
    assert len(records) == 3


@pytest.mark.asyncio
async def test_query_status_filter(mem_store):
    await mem_store.log_transaction({"status": "committed"})
    await mem_store.log_transaction({"status": "rolled_back"})
    await mem_store.log_transaction({"status": "committed"})
    committed = await mem_store.query_transactions(status="committed")
    assert len(committed) == 2
    assert all(r["status"] == "committed" for r in committed)


# ---------------------------------------------------------------------------
# compact()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_compact_prunes_old_records(mem_store):
    old_ts = time.time() - 40 * 86400  # 40 days ago
    mem_store._memory = [
        {"audit_id": "old", "audit_ts": old_ts, "status": "committed"},
    ]
    mem_store._loaded = True
    pruned = await mem_store.compact()
    assert pruned == 1
    assert len(mem_store._memory) == 0


@pytest.mark.asyncio
async def test_compact_prunes_excess_records():
    store = AuditStore(path=None, max_records=5)
    for i in range(12):
        await store.log_transaction({"seq": i})
    # compact manually
    pruned = await store.compact()
    assert len(store._memory) <= 5


@pytest.mark.asyncio
async def test_compact_keeps_recent_records(mem_store):
    await mem_store.log_transaction({"status": "committed"})
    pruned = await mem_store.compact()
    assert pruned == 0
    assert len(mem_store._memory) == 1


# ---------------------------------------------------------------------------
# Disk round-trip
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_disk_round_trip(tmp_path):
    path = tmp_path / "test_audit.jsonl"
    store = AuditStore(path=path)
    await store.log_transaction({"status": "committed", "name": "round_trip_test"})

    # Re-read from disk via a fresh store instance
    store2 = AuditStore(path=path)
    records = await store2.query_transactions()
    assert len(records) == 1
    assert records[0]["name"] == "round_trip_test"


@pytest.mark.asyncio
async def test_corrupt_lines_skipped(tmp_path):
    path = tmp_path / "corrupt.jsonl"
    path.write_text(
        '{"audit_id": "good", "status": "committed", "audit_ts": 1000}\n'
        'NOT VALID JSON\n'
        '{"audit_id": "good2", "status": "committed", "audit_ts": 1001}\n',
        encoding="utf-8",
    )
    store = AuditStore(path=path)
    records = await store.query_transactions()
    assert len(records) == 2
    assert all(r.get("status") == "committed" for r in records)


# ---------------------------------------------------------------------------
# In-memory only store
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_memory_only_does_not_write_file(tmp_path):
    store = AuditStore(path=None)
    await store.log_transaction({"status": "committed"})
    # Nothing should be written to disk
    jsonl_files = list(tmp_path.glob("*.jsonl"))
    assert len(jsonl_files) == 0


# ---------------------------------------------------------------------------
# stats()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stats_shape(mem_store):
    await mem_store.log_transaction({"status": "committed"})
    s = mem_store.stats()
    assert "records_in_memory" in s
    assert "path" in s
    assert "write_count" in s
    assert s["write_count"] == 1
    assert s["records_in_memory"] == 1


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton_returns_same_instance():
    a = get_audit_store()
    b = get_audit_store()
    assert a is b


def test_reset_creates_fresh_singleton():
    a = get_audit_store()
    reset_audit_store_for_tests()
    b = get_audit_store()
    assert a is not b
