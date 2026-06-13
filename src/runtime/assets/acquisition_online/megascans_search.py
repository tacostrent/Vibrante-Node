"""
Megascans / Fab Search (Tier 12.9 — updated for Fab migration)
================================================================
Search Fab / Megascans assets by query, tags, category, or environment.

After the Quixel → Fab migration (2024) the old megascans.se/v1 API was shut
down. This module now uses the Fab public search API which requires no auth for
general catalogue searches. Auth is still used for "my assets only" queries.

Public search endpoint (no auth required):
  GET https://www.fab.com/i/listings/search?q={query}&limit={n}

Output: normalized AssetDescriptor-compatible dicts.
Offline-safe: returns empty results with advisory when no token or network.
Injectable transport for tests.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .megascans_auth import get_megascans_auth

# Old dead endpoint (kept for reference only — returns 404):
#   _DEFAULT_BASE_URL = "https://megascans.se/v1"
# New live public search endpoint (no auth required):
_FAB_SEARCH_URL = "https://www.fab.com/i/listings/search"

# Megascans category → Vibrante environment hints
_ENV_CATEGORY_MAP: Dict[str, List[str]] = {
    "3d":           ["industrial_hangar", "robotics_lab"],
    "3dplant":      ["abandoned_factory"],
    "surface":      ["industrial_hangar", "abandoned_factory"],
    "decal":        ["abandoned_factory"],
    "imperfection": ["industrial_hangar", "abandoned_factory"],
}


@dataclass
class MegascansSearchRecord:
    asset_id:     str = ""
    name:         str = ""
    provider:     str = "megascans"
    category:     str = ""
    ms_type:      str = ""
    tags:         List[str] = field(default_factory=list)
    description:  str = ""
    preview_url:  str = ""
    download_url: str = ""
    environments: List[str] = field(default_factory=list)
    is_free:      bool = False
    raw:          Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id":    str(self.asset_id),
            "name":        str(self.name),
            "provider":    str(self.provider),
            "category":    str(self.category),
            "ms_type":     str(self.ms_type),
            "tags":        list(self.tags),
            "description": str(self.description),
            "preview_url": str(self.preview_url),
            "download_url":str(self.download_url),
            "environments":list(self.environments),
            "is_free":     bool(self.is_free),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MegascansSearchRecord":
        d = d if isinstance(d, dict) else {}
        return cls(
            asset_id=str(d.get("asset_id", "")),
            name=str(d.get("name", "")),
            provider=str(d.get("provider", "megascans")),
            category=str(d.get("category", "")),
            ms_type=str(d.get("ms_type", "")),
            tags=list(d.get("tags") or []),
            description=str(d.get("description", "")),
            preview_url=str(d.get("preview_url", "")),
            download_url=str(d.get("download_url", "")),
            environments=list(d.get("environments") or []),
            is_free=bool(d.get("is_free", False)),
        )


class MegascansSearch:
    def __init__(self) -> None:
        self._lock       = threading.Lock()
        self._search_count = 0
        self._transport: Optional[Any] = None  # Injectable for tests

    def search_assets(
        self,
        query:    str,
        category: str = "",
        limit:    int = 20,
    ) -> List[MegascansSearchRecord]:
        """Search by free-text query. Never raises."""
        try:
            return self._do_search({"search": str(query), "category": str(category),
                                    "limit": int(limit)})
        except Exception:
            return []

    def search_by_tags(self, tags: List[str], limit: int = 20) -> List[MegascansSearchRecord]:
        """Search by tag list. Never raises."""
        try:
            query = " ".join(str(t) for t in (tags or []))
            return self._do_search({"search": query, "limit": int(limit)})
        except Exception:
            return []

    def search_by_category(self, category: str, limit: int = 20) -> List[MegascansSearchRecord]:
        """Search by Megascans asset type category. Never raises."""
        try:
            return self._do_search({"category": str(category), "limit": int(limit)})
        except Exception:
            return []

    def search_my_assets(
        self,
        query: str,
        limit: int = 20,
    ) -> List[MegascansSearchRecord]:
        """
        Search the Fab catalogue.
        Note: the old Megascans "myscans" (owned-only) filter no longer exists in
        the Fab public API. Results include both owned and purchasable assets.
        Use FabSocketReceiver to receive assets you actually own after exporting
        them from the Fab desktop app.
        Never raises.
        """
        try:
            return self._do_search({"search": str(query), "limit": int(limit)})
        except Exception:
            return []

    def search_by_environment(self, environment: str, limit: int = 20) -> List[MegascansSearchRecord]:
        """Search by Vibrante environment name using category hints. Never raises."""
        try:
            # Map environment → likely ms_type categories
            from src.runtime.assets.semantic.asset_environment_mapper import _ENV_KEYWORDS
            env_words = list(_ENV_KEYWORDS.get(environment, []))
            query = " ".join(env_words[:5]) if env_words else str(environment).replace("_", " ")
            return self._do_search({"search": query, "limit": int(limit)})
        except Exception:
            return []

    def lookup_asset(self, asset_id: str) -> Optional[MegascansSearchRecord]:
        """
        Look up a single asset by its Fab UID or Megascans ID.
        Falls back to a search query. Never raises.
        """
        try:
            # Try direct UID search first
            results = self._do_search({"search": str(asset_id), "limit": 5})
            for r in results:
                if r.asset_id == asset_id:
                    return r
            return results[0] if results else None
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _do_search(self, params: Dict[str, Any]) -> List[MegascansSearchRecord]:
        # Build query string for Fab public search API
        query = str(params.get("search") or params.get("query") or "").strip()
        limit = int(params.get("limit") or 20)
        # "view=myscans" was the old Megascans-only-assets flag — no equivalent
        # in the Fab public API; we still pass it through for injectable transport.
        token = get_megascans_auth().get_token()  # optional — needed only for owned assets

        fab_params: Dict[str, Any] = {}
        if query:
            fab_params["q"] = query
        if limit:
            fab_params["limit"] = min(limit, 48)  # Fab API max page size
        cat = str(params.get("category") or "").strip()
        if cat:
            fab_params["category"] = cat

        data = self._fetch_fab(fab_params, token)
        if not data:
            return []
        raw_list = data.get("results") or data.get("assets") or []
        if not isinstance(raw_list, list):
            return []
        records = [self._normalize_record(r) for r in raw_list if isinstance(r, dict)]
        with self._lock:
            self._search_count += 1
        return records

    def _normalize_record(self, raw: Dict[str, Any]) -> MegascansSearchRecord:
        """Normalize a Fab API result dict (or old Megascans dict) to MegascansSearchRecord."""
        try:
            from src.runtime.assets.semantic.megascans_metadata_client import _MS_TYPE_TO_CATEGORY
        except ImportError:
            _MS_TYPE_TO_CATEGORY: Dict[str, str] = {}

        # Fab API uses "listingType" ("3d-model", "surface", "decal", etc.)
        # Old Megascans API used "type" ("3d", "surface", etc.)
        listing_type = str(raw.get("listingType") or raw.get("type") or raw.get("assetType") or "").lower()
        # Map "3d-model" → "3d" for category lookup
        ms_type = listing_type.replace("3d-model", "3d").replace("-", "_")
        category_info = raw.get("category") or {}
        if isinstance(category_info, dict):
            category = str(category_info.get("slug") or category_info.get("name") or ms_type or "prop")
        else:
            category = _MS_TYPE_TO_CATEGORY.get(ms_type, ms_type or "prop")

        # Tags: Fab returns [{"slug": "...", "uid": "...", "name": "..."}]
        tags_raw = raw.get("tags") or raw.get("keywords") or []
        if isinstance(tags_raw, str):
            tags_raw = [t.strip() for t in tags_raw.split(",") if t.strip()]
        tags = []
        for t in tags_raw:
            if isinstance(t, dict):
                slug = str(t.get("slug") or t.get("name") or "").strip()
                if slug:
                    tags.append(slug.lower())
            elif isinstance(t, str) and t.strip():
                tags.append(t.lower().strip())

        environments = _ENV_CATEGORY_MAP.get(ms_type, [])

        # Fab uses "uid" as the asset ID; old Megascans used "id"
        asset_id = str(raw.get("uid") or raw.get("id") or raw.get("asset_id") or "").strip()

        # Thumbnails: Fab returns [{"url": "...", "type": "thumbnail"}]
        thumbs = raw.get("thumbnails") or raw.get("previews") or []
        preview_url = ""
        if isinstance(thumbs, list) and thumbs:
            t0 = thumbs[0]
            preview_url = str(t0.get("url") or t0.get("mediaUrl") or "").strip() if isinstance(t0, dict) else str(t0)
        elif isinstance(thumbs, str):
            preview_url = thumbs

        return MegascansSearchRecord(
            asset_id=asset_id,
            name=str(raw.get("title") or raw.get("name") or "").strip(),
            provider="fab",
            category=category,
            ms_type=ms_type,
            tags=tags,
            description=str(raw.get("description") or "").strip(),
            preview_url=preview_url,
            download_url="",   # download requires auth — use FabSocketReceiver instead
            environments=environments,
            is_free=bool(raw.get("isFree") or raw.get("free") or False),
            raw=dict(raw),
        )

    def _fetch_fab(self, params: Dict[str, Any], token: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Fetch from the Fab public search API. Never raises."""
        if self._transport is not None:
            # Tests inject a transport with .get(url, token, params) → dict
            return self._transport.get(_FAB_SEARCH_URL, token or "", params)
        try:
            import urllib.request, urllib.parse, json
            full_url = f"{_FAB_SEARCH_URL}?{urllib.parse.urlencode(params)}" if params else _FAB_SEARCH_URL
            req = urllib.request.Request(full_url)
            req.add_header("Accept", "application/json")
            req.add_header("User-Agent", "VibrateNode/1.0 FabSearch")
            if token:
                req.add_header("Authorization", f"Bearer {token}")
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
                return data if isinstance(data, dict) else None
        except Exception:
            return None

    def _fetch(self, url: str, token: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Legacy fetch helper — delegates to _fetch_fab. Kept for backward compat."""
        return self._fetch_fab(params, token)

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            return {"search_count": self._search_count}


_INSTANCE: Optional[MegascansSearch] = None
_INSTANCE_LOCK = threading.Lock()


def get_megascans_search() -> MegascansSearch:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = MegascansSearch()
    return _INSTANCE


def reset_megascans_search_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
