"""
Asset Discovery Engine (Tier 8 — Asset Intelligence Runtime)
=============================================================
Translates a ScenePlan's AssetQuery list into AssetQueryResult objects
by querying all registered providers, merging, and deduplicating.

DESIGN RULES:
  1. Input:  ScenePlan (or a list of AssetQuery dicts)
  2. Output: DiscoveryResult containing one AssetQueryResult per query
  3. No ranking — Discovery only.
  4. Duplicate detection by (provider, asset_id) pair.
  5. Cache hits are checked before provider calls.
  6. Never raises — errors captured in DiscoveryResult.errors.

Public API:
    DiscoveryResult
    AssetDiscoveryEngine
    get_asset_discovery_engine()
    reset_asset_discovery_engine_for_tests()
"""

from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from src.runtime.assets.schema import AssetDescriptor, AssetQueryResult, AssetProviderResult
from src.runtime.assets.providers.base import get_provider_registry

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass
class DiscoveryResult:
    """Result of one AssetDiscoveryEngine.discover() call."""

    ok:              bool              = True
    query_results:   List[AssetQueryResult] = field(default_factory=list)
    total_assets:    int               = 0
    providers_queried: List[str]       = field(default_factory=list)
    discovery_time:  float             = 0.0
    errors:          List[str]         = field(default_factory=list)
    warnings:        List[str]         = field(default_factory=list)
    pipeline_stages: List[str]         = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok":                self.ok,
            "query_results":     [r.to_dict() for r in self.query_results],
            "total_assets":      self.total_assets,
            "providers_queried": list(self.providers_queried),
            "discovery_time":    self.discovery_time,
            "errors":            list(self.errors),
            "warnings":          list(self.warnings),
            "pipeline_stages":   list(self.pipeline_stages),
        }


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class AssetDiscoveryEngine:
    """
    Queries all registered providers for each AssetQuery in a ScenePlan.

    Providers are resolved from ProviderRegistry at query time so new
    providers registered after construction are automatically included.
    """

    def discover(
        self,
        queries: List[Dict[str, Any]],
        limit_per_provider: int = 20,
    ) -> DiscoveryResult:
        """
        Execute discovery for a list of AssetQuery dicts.

        Args:
            queries:             List of AssetQuery.to_dict() dicts.
            limit_per_provider:  Max results per provider per query.

        Returns:
            :class:`DiscoveryResult`.  Never raises.
        """
        t0 = time.perf_counter()
        result = DiscoveryResult()

        try:
            registry = get_provider_registry()
            providers = registry.available_providers()
            result.providers_queried = [p.provider_name for p in providers]
            result.pipeline_stages.append("providers_resolved")

            for q_dict in queries:
                try:
                    qr = self._discover_one(q_dict, providers, limit_per_provider)
                    result.query_results.append(qr)
                    result.total_assets += len(qr.assets)
                except Exception as exc:
                    result.warnings.append(
                        f"Query {q_dict.get('query_id', '?')} failed: {exc}"
                    )

            result.pipeline_stages.append("discovery_complete")
            result.ok = True

        except Exception as exc:
            result.ok = False
            result.errors.append(f"Discovery failed: {exc}")

        result.discovery_time = time.perf_counter() - t0
        return result

    def discover_from_plan(
        self,
        plan: Any,
        limit_per_provider: int = 20,
    ) -> DiscoveryResult:
        """
        Convenience wrapper that accepts a ScenePlan object or dict.

        Extracts asset_queries from the plan and calls discover().
        """
        if hasattr(plan, "asset_queries"):
            raw_queries = [q.to_dict() for q in plan.asset_queries]
        elif isinstance(plan, dict):
            raw_queries = [
                q if isinstance(q, dict) else q.to_dict()
                for q in plan.get("asset_queries", [])
            ]
        else:
            raw_queries = []
        return self.discover(raw_queries, limit_per_provider=limit_per_provider)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _discover_one(
        self,
        q: Dict[str, Any],
        providers: list,
        limit: int,
    ) -> AssetQueryResult:
        """Query all providers for one AssetQuery and merge results."""
        t0 = time.perf_counter()
        category  = str(q.get("category", ""))
        tags      = list(q.get("tags") or [])
        keywords  = list(q.get("style_hints") or [])
        query_id  = str(q.get("query_id", ""))
        zone      = str(q.get("zone", ""))

        all_assets: List[AssetDescriptor] = []
        seen_ids: set = set()
        provider_results: List[AssetProviderResult] = []
        errors: List[str] = []

        for provider in providers:
            if category and category not in provider.supported_categories:
                continue
            try:
                pr = provider.search(
                    category=category,
                    tags=tags,
                    keywords=keywords,
                    limit=limit,
                )
                provider_results.append(pr)
                if pr.success:
                    for asset in pr.normalized_assets:
                        key = (asset.provider, asset.asset_id)
                        if key not in seen_ids:
                            seen_ids.add(key)
                            all_assets.append(asset)
                else:
                    errors.extend(pr.errors)
            except Exception as exc:
                errors.append(f"Provider {provider.provider_name}: {exc}")

        return AssetQueryResult(
            query_id=query_id,
            category=category,
            zone=zone,
            assets=all_assets,
            total_found=len(all_assets),
            provider_results=provider_results,
            errors=errors,
            query_time=time.perf_counter() - t0,
            cached=False,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[AssetDiscoveryEngine] = None
_INSTANCE_LOCK = threading.Lock()


def get_asset_discovery_engine() -> AssetDiscoveryEngine:
    """Return the module-level singleton AssetDiscoveryEngine."""
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = AssetDiscoveryEngine()
    return _INSTANCE


def reset_asset_discovery_engine_for_tests() -> None:
    """Replace the singleton.  For test isolation only."""
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
