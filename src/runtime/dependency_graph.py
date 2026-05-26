"""
Dependency Graph
================
Lightweight, in-memory tracking of inter-node dependencies in a Houdini session.
Used by the execution preview and validation systems to compute:
  - which nodes are affected by a proposed change
  - what cook-chain will be triggered
  - whether a delete operation would break downstream dependents

Dependency types:
  connection           — data wire from source to target
  parameter_reference  — node parameter references another node's attribute
  cook_dependency      — source must cook before target can cook
  display_dependency   — target uses source's display flag state
  render_dependency    — target uses source's render flag state

This graph is populated by the execution system as ops are applied, and by
scene context reads that discover the live network topology. It is advisory —
execution never blocks on it. The graph is never persisted to disk.

Public API:
    get_dependency_graph() -> DependencyGraph   (singleton)

    graph.register_dependency(source, target, dep_type="connection")
    graph.remove_dependency(source, target)
    graph.remove_node(path)
    graph.get_upstream(path, dep_type=None) -> list[dict]
    graph.get_downstream(path, dep_type=None) -> list[dict]
    graph.get_affected_nodes(paths, dep_type=None) -> list[str]
    graph.get_cook_chain(path) -> list[str]
    graph.clear()
    graph.stats() -> dict
    graph.all_edges() -> list[dict]
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional, Set

DEPENDENCY_TYPES = frozenset({
    "connection",
    "parameter_reference",
    "cook_dependency",
    "display_dependency",
    "render_dependency",
})


class DependencyGraph:
    """In-memory directed dependency graph for Houdini node paths.

    All operations are thread-safe. Edge direction follows data flow:
    source → target means "target depends on source".
    """

    def __init__(self):
        # _upstream[target] = {source: dep_type}
        self._upstream: Dict[str, Dict[str, str]] = {}
        # _downstream[source] = {target: dep_type}
        self._downstream: Dict[str, Dict[str, str]] = {}
        self._lock = threading.Lock()

    def register_dependency(
        self, source: str, target: str, dep_type: str = "connection"
    ) -> None:
        """Record that `target` depends on `source` with the given type.

        Idempotent — registering the same (source, target) pair multiple times
        is fine; registering with a different type updates the type (last write
        wins). Self-dependencies (source == target) are silently ignored.
        """
        if not source or not target or source == target:
            return
        if dep_type not in DEPENDENCY_TYPES:
            raise ValueError(
                f"unknown dependency type '{dep_type}'. Valid: {sorted(DEPENDENCY_TYPES)}"
            )
        with self._lock:
            self._upstream.setdefault(target, {})[source] = dep_type
            self._downstream.setdefault(source, {})[target] = dep_type

    def remove_dependency(self, source: str, target: str) -> None:
        """Remove a specific dependency edge (no-op if it doesn't exist)."""
        with self._lock:
            self._upstream.get(target, {}).pop(source, None)
            self._downstream.get(source, {}).pop(target, None)

    def remove_node(self, path: str) -> None:
        """Remove all edges incident on `path` (as source and as target)."""
        with self._lock:
            # Drop all edges where path is a target
            self._upstream.pop(path, None)
            # Drop path from all other nodes' upstream entries
            for up in self._upstream.values():
                up.pop(path, None)
            # Drop all edges where path is a source
            self._downstream.pop(path, None)
            # Drop path from all other nodes' downstream entries
            for down in self._downstream.values():
                down.pop(path, None)

    def get_upstream(
        self, path: str, dep_type: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """Return direct upstream dependencies of `path`.

        Each entry: {"source": str, "target": str, "type": str}
        Optionally filter by `dep_type`.
        """
        with self._lock:
            sources = self._upstream.get(path, {})
            return [
                {"source": src, "target": path, "type": t}
                for src, t in sorted(sources.items())
                if dep_type is None or t == dep_type
            ]

    def get_downstream(
        self, path: str, dep_type: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """Return direct downstream dependencies of `path`.

        Each entry: {"source": str, "target": str, "type": str}
        Optionally filter by `dep_type`.
        """
        with self._lock:
            targets = self._downstream.get(path, {})
            return [
                {"source": path, "target": tgt, "type": t}
                for tgt, t in sorted(targets.items())
                if dep_type is None or t == dep_type
            ]

    def get_affected_nodes(
        self, paths: List[str], dep_type: Optional[str] = None
    ) -> List[str]:
        """BFS over the downstream graph starting from all input `paths`.

        Returns a deduplicated sorted list of transitively affected nodes.
        The seed `paths` themselves are NOT included in the result.
        """
        seed = set(paths)
        visited: Set[str] = set()
        queue = list(paths)
        with self._lock:
            while queue:
                current = queue.pop(0)
                for tgt, t in self._downstream.get(current, {}).items():
                    if dep_type is not None and t != dep_type:
                        continue
                    if tgt not in visited and tgt not in seed:
                        visited.add(tgt)
                        queue.append(tgt)
        return sorted(visited)

    def get_cook_chain(self, path: str) -> List[str]:
        """Return nodes that would re-cook if `path` changes.

        Walks connection and cook_dependency edges, deduplicates, returns sorted.
        """
        via_connection = set(self.get_affected_nodes([path], dep_type="connection"))
        via_cook = set(self.get_affected_nodes([path], dep_type="cook_dependency"))
        return sorted(via_connection | via_cook)

    def clear(self) -> None:
        """Wipe the entire graph (e.g. after scene reload)."""
        with self._lock:
            self._upstream.clear()
            self._downstream.clear()

    def stats(self) -> dict:
        with self._lock:
            total_edges = sum(len(v) for v in self._upstream.values())
            return {
                "nodes_with_upstream": len(self._upstream),
                "nodes_with_downstream": len(self._downstream),
                "total_edges": total_edges,
            }

    def all_edges(self) -> List[Dict[str, str]]:
        """Dump all edges for serialisation / debugging."""
        with self._lock:
            return [
                {"source": src, "target": tgt, "type": t}
                for tgt, sources in sorted(self._upstream.items())
                for src, t in sorted(sources.items())
            ]


_GRAPH: Optional[DependencyGraph] = None


def get_dependency_graph() -> DependencyGraph:
    """Return the process-wide DependencyGraph singleton."""
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = DependencyGraph()
    return _GRAPH


def reset_dependency_graph_for_tests() -> None:
    """Drop the singleton — for test isolation only."""
    global _GRAPH
    _GRAPH = None
