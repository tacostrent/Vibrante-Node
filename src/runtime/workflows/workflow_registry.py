"""
Workflow Registry (Tier 10 — Workflow Packs & Production Blueprints)
====================================================================
Thread-safe singleton registry of all registered WorkflowPacks.

Built-in packs are loaded on first access and cannot be deregistered.
User packs can be registered and deregistered at runtime.

DESIGN RULES:
  1. Singleton — one registry per process.
  2. Thread-safe — all mutations under a single threading.Lock.
  3. Built-in packs cannot be removed (raises ValueError).
  4. Deterministic listing — packs sorted by name.

Public API:
    WorkflowRegistry
    get_workflow_registry() -> WorkflowRegistry
    reset_workflow_registry_for_tests()
"""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, List, Optional

from src.runtime.workflows.workflow_pack import WorkflowPack, get_builtin_packs


class WorkflowRegistry:
    """Registry of all workflow packs (singleton)."""

    def __init__(self) -> None:
        self._lock  = threading.Lock()
        self._packs: Dict[str, WorkflowPack] = {}
        self._builtin_names: set  = set()
        self._register_count: int = 0
        self._query_count:    int = 0
        self._load_builtins()

    # -----------------------------------------------------------------
    def _load_builtins(self) -> None:
        for pack in get_builtin_packs():
            self._packs[pack.name] = pack
            self._builtin_names.add(pack.name)

    # -----------------------------------------------------------------
    def register_pack(self, pack: WorkflowPack) -> bool:
        """
        Register a WorkflowPack.

        Returns True on success, False if validation fails.
        Raises ValueError if `pack.name` collides with a built-in.
        """
        if not pack.name:
            return False
        errors = pack.validate()
        if errors:
            return False
        with self._lock:
            if pack.name in self._builtin_names:
                raise ValueError(
                    f"Cannot overwrite built-in pack {pack.name!r}. "
                    "Use a different name for custom packs."
                )
            self._packs[pack.name] = pack
            self._register_count += 1
        return True

    def unregister_pack(self, name: str) -> bool:
        """
        Remove a user-registered pack.

        Returns True if removed, False if not found.
        Raises ValueError for built-in packs.
        """
        with self._lock:
            if name in self._builtin_names:
                raise ValueError(
                    f"Cannot remove built-in pack {name!r}."
                )
            if name not in self._packs:
                return False
            del self._packs[name]
        return True

    def get_pack(self, name: str) -> Optional[WorkflowPack]:
        """Return a pack by name, or None if not registered."""
        with self._lock:
            self._query_count += 1
            return self._packs.get(name)

    def list_packs(
        self,
        environment_type: Optional[str] = None,
        builtin_only: bool = False,
        custom_only: bool = False,
    ) -> List[WorkflowPack]:
        """Return sorted list of packs, optionally filtered."""
        with self._lock:
            packs = list(self._packs.values())

        if environment_type:
            packs = [p for p in packs if p.environment_type == environment_type]
        if builtin_only:
            packs = [p for p in packs if p.name in self._builtin_names]
        if custom_only:
            packs = [p for p in packs if p.name not in self._builtin_names]
        return sorted(packs, key=lambda p: p.name)

    def find_packs(
        self,
        tags: Optional[List[str]] = None,
        environment_type: Optional[str] = None,
        min_threshold: Optional[float] = None,
    ) -> List[WorkflowPack]:
        """Find packs matching optional criteria."""
        packs = self.list_packs(environment_type=environment_type)
        if tags:
            tag_set = {t.lower() for t in tags}
            packs = [
                p for p in packs
                if tag_set.intersection({t.lower() for t in p.metadata.get("tags", [])})
            ]
        if min_threshold is not None:
            packs = [
                p for p in packs
                if p.review_strategy.get("production_threshold", 0.0) >= min_threshold
            ]
        return packs

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            total   = len(self._packs)
            builtin = len(self._builtin_names)
        return {
            "total_packs":         total,
            "builtin_pack_count":  builtin,
            "custom_pack_count":   total - builtin,
            "register_count":      self._register_count,
            "query_count":         self._query_count,
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[WorkflowRegistry] = None
_lock = threading.Lock()


def get_workflow_registry() -> WorkflowRegistry:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = WorkflowRegistry()
    return _instance


def reset_workflow_registry_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
