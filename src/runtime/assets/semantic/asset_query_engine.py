"""
Asset Query Engine (Tier 12.7)
================================
Semantic retrieval from the asset catalog using production intent.

Instead of filename matching, queries use:
  - Environment intent (industrial_hangar, robotics_lab, …)
  - Production role (hero, support, set_dressing, …)
  - Storytelling role (hero_object, context_builder, …)
  - Lookdev style (weathered, industrial, sci_fi, …)
  - Cinematic usage (hero_focus, depth_layer, …)
  - Free-text query against name, tags, semantic_tags

Example:
  query("Industrial Hangar Hero Machinery")
  → Top ranked assets from catalog
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .asset_catalog import get_asset_catalog, CatalogEntry
from .asset_knowledge_graph import get_asset_knowledge_graph
from .asset_catalog_statistics import get_catalog_statistics
from .asset_environment_mapper import BUILTIN_ENVIRONMENTS
from .asset_role_classifier import BUILTIN_ROLES
from .asset_storytelling_mapper import STORYTELLING_ROLES
from .asset_lookdev_mapper import LOOKDEV_TAGS
from .asset_cinematic_mapper import CINEMATIC_USAGES


@dataclass
class QueryResult:
    ok:       bool = True
    assets:   List[Dict[str, Any]] = field(default_factory=list)
    total:    int = 0
    query:    str = ""
    filters:  Dict[str, str] = field(default_factory=dict)
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok":          bool(self.ok),
            "assets":      list(self.assets),
            "total":       int(self.total),
            "query":       str(self.query),
            "filters":     dict(self.filters),
            "duration_ms": float(self.duration_ms),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "QueryResult":
        d = d if isinstance(d, dict) else {}
        return cls(
            ok=bool(d.get("ok", True)),
            assets=list(d.get("assets") or []),
            total=int(d.get("total", 0)),
            query=str(d.get("query", "")),
            filters=dict(d.get("filters") or {}),
            duration_ms=float(d.get("duration_ms", 0.0)),
        )


class AssetQueryEngine:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._query_count = 0

    def query(
        self,
        text: str = "",
        environment: str = "",
        role: str = "",
        storytelling: str = "",
        lookdev: str = "",
        cinematic: str = "",
        provider: str = "",
        category: str = "",
        downloaded_only: bool = False,
        include_graph_neighbors: bool = False,
        limit: int = 20,
    ) -> QueryResult:
        """Full semantic query with optional knowledge graph expansion. Never raises."""
        try:
            return self._do_query(
                text=str(text).strip().lower(),
                environment=str(environment).strip().lower(),
                role=str(role).strip().lower(),
                storytelling=str(storytelling).strip().lower(),
                lookdev=str(lookdev).strip().lower(),
                cinematic=str(cinematic).strip().lower(),
                provider=str(provider).strip().lower(),
                category=str(category).strip().lower(),
                downloaded_only=bool(downloaded_only),
                include_graph_neighbors=bool(include_graph_neighbors),
                limit=int(limit),
            )
        except Exception as exc:
            return QueryResult(ok=False, query=str(text), assets=[])

    def _do_query(
        self, text, environment, role, storytelling,
        lookdev, cinematic, provider, category,
        downloaded_only, include_graph_neighbors, limit,
    ) -> QueryResult:
        t0 = time.perf_counter()
        with self._lock:
            self._query_count += 1

        catalog = get_asset_catalog()
        entries = catalog.search_assets(
            query=text,
            environment=environment,
            role=role,
            lookdev=lookdev,
            storytelling=storytelling,
            cinematic=cinematic,
            provider=provider,
            category=category,
            downloaded_only=downloaded_only,
            limit=limit,
        )

        # Optionally expand with graph neighbors
        if include_graph_neighbors and entries:
            graph = get_asset_knowledge_graph()
            extra_ids: List[str] = []
            for entry in entries[:5]:
                neighbors = graph.get_neighbors(entry.asset_id)
                extra_ids.extend(n for n in neighbors if n not in [e.asset_id for e in entries])
            for aid in list(dict.fromkeys(extra_ids))[:limit]:
                neighbor_entry = catalog.get_asset(aid)
                if neighbor_entry:
                    entries.append(neighbor_entry)

        entries = entries[:limit]
        get_catalog_statistics().record("query", duration_ms=(time.perf_counter() - t0) * 1000)

        filters = {
            k: v for k, v in {
                "environment": environment,
                "role":        role,
                "storytelling": storytelling,
                "lookdev":     lookdev,
                "cinematic":   cinematic,
                "provider":    provider,
                "category":    category,
            }.items() if v
        }

        return QueryResult(
            ok=True,
            assets=[e.to_dict() for e in entries],
            total=len(entries),
            query=text,
            filters=filters,
            duration_ms=round((time.perf_counter() - t0) * 1000, 2),
        )

    # ------------------------------------------------------------------
    # Convenience filters
    # ------------------------------------------------------------------

    def query_environment(self, environment: str, limit: int = 20) -> QueryResult:
        """Query assets for a specific environment."""
        return self.query(environment=environment, limit=limit)

    def query_role(self, role: str, limit: int = 20) -> QueryResult:
        """Query assets for a specific production role."""
        return self.query(role=role, limit=limit)

    def query_storytelling(self, storytelling_role: str, limit: int = 20) -> QueryResult:
        """Query assets for a specific storytelling role."""
        return self.query(storytelling=storytelling_role, limit=limit)

    def query_lookdev(self, lookdev_tag: str, limit: int = 20) -> QueryResult:
        """Query assets for a specific lookdev style."""
        return self.query(lookdev=lookdev_tag, limit=limit)

    def query_cinematic(self, cinematic_usage: str, limit: int = 20) -> QueryResult:
        """Query assets for a specific cinematic usage."""
        return self.query(cinematic=cinematic_usage, limit=limit)

    def query_intent(self, intent_text: str, limit: int = 20) -> QueryResult:
        """Parse a natural production intent string and run a combined query.

        Examples:
          "Industrial Hangar Hero Machinery"
          "Sci-Fi Corridor Weathered Set Dressing"
          "Robotics Lab Support Visual Balance"
        """
        text = intent_text.lower()
        environment = next((e for e in BUILTIN_ENVIRONMENTS if e.replace("_", " ") in text or e in text.replace(" ", "_")), "")
        role = next((r for r in BUILTIN_ROLES if r.replace("_", " ") in text or r in text.replace(" ", "_")), "")
        story = next((s for s in STORYTELLING_ROLES if s.replace("_", " ") in text), "")
        lookdev = next((l for l in LOOKDEV_TAGS if l in text), "")
        cinematic = next((c for c in CINEMATIC_USAGES if c.replace("_", " ") in text), "")

        # Remaining text is a free-text query
        known_tokens = {environment, role, story, lookdev, cinematic}
        free_text = " ".join(
            t for t in text.split()
            if t not in known_tokens and t.replace("_", " ") not in known_tokens
        )

        return self.query(
            text=free_text,
            environment=environment,
            role=role,
            storytelling=story,
            lookdev=lookdev,
            cinematic=cinematic,
            limit=limit,
        )

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            return {"query_count": self._query_count}


_INSTANCE: Optional[AssetQueryEngine] = None
_INSTANCE_LOCK = threading.Lock()


def get_asset_query_engine() -> AssetQueryEngine:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = AssetQueryEngine()
    return _INSTANCE


def reset_asset_query_engine_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
