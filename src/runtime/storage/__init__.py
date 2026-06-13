"""
Vibrante Runtime — Storage Backend Abstraction (Tier 5)
========================================================
Provides a pluggable persistence layer for Tier 5 production knowledge modules.

Backends:
    MemoryBackend     — pure in-memory (default; no persistence, used by tests)
    SQLiteBackend     — WAL-mode SQLite with JSONL migration support

Public surface:
    from src.runtime.storage import MemoryBackend, SQLiteBackend
    from src.runtime.storage.serialization import serialize_record, deserialize_record
"""

from src.runtime.storage.memory_backend import MemoryBackend
from src.runtime.storage.sqlite_backend import SQLiteBackend

__all__ = ["MemoryBackend", "SQLiteBackend"]
