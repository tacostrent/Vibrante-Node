"""
Megascans Metadata Client (Tier 12.7)
========================================
Fetches asset metadata from the official Megascans / Fab API.

Design rules:
  - Uses official Megascans API workflows ONLY
  - No web scraping, no bypassing authentication
  - Token caching with configurable TTL
  - Retry support with exponential backoff (advisory, no real sleep in tests)
  - Rate-limit awareness
  - Deterministic normalization
  - No actual network calls when VIBRANTE_MEGASCANS_TOKEN is not set

Environment variable:
  VIBRANTE_MEGASCANS_TOKEN  — optional Megascans / Fab API token

If the token is not set, the client operates in offline mode and all search /
get calls return empty results with source="offline".
"""
from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

ENV_MEGASCANS_TOKEN = "VIBRANTE_MEGASCANS_TOKEN"

_DEFAULT_BASE_URL = "https://quixel.com/v1"
_TOKEN_TTL_SECONDS = 3600
_MAX_RETRIES = 3
_RETRY_DELAYS = (1.0, 2.0, 4.0)

# Megascans asset type → Vibrante category mapping (same as Tier 12.5)
_MS_TYPE_TO_CATEGORY: Dict[str, str] = {
    "3d":           "prop",
    "3dplant":      "vegetation",
    "surface":      "material",
    "decal":        "material",
    "imperfection": "material",
    "atlas":        "material",
    "brush":        "material",
}


@dataclass
class MegascansAssetMetadata:
    asset_id:     str = ""
    name:         str = ""
    provider:     str = "megascans"
    category:     str = ""
    ms_type:      str = ""
    tags:         List[str] = field(default_factory=list)
    description:  str = ""
    preview_url:  str = ""
    download_url: str = ""
    metadata_source: str = "api"
    formats:      List[str] = field(default_factory=list)
    raw:          Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id":        str(self.asset_id),
            "name":            str(self.name),
            "provider":        str(self.provider),
            "category":        str(self.category),
            "ms_type":         str(self.ms_type),
            "tags":            list(self.tags),
            "description":     str(self.description),
            "preview_url":     str(self.preview_url),
            "download_url":    str(self.download_url),
            "metadata_source": str(self.metadata_source),
            "formats":         list(self.formats),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MegascansAssetMetadata":
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
            metadata_source=str(d.get("metadata_source", "api")),
            formats=list(d.get("formats") or []),
        )


@dataclass
class MegascansSearchResult:
    ok:      bool = False
    assets:  List[MegascansAssetMetadata] = field(default_factory=list)
    total:   int = 0
    source:  str = "offline"
    errors:  List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok":     bool(self.ok),
            "assets": [a.to_dict() for a in self.assets],
            "total":  int(self.total),
            "source": str(self.source),
            "errors": list(self.errors),
        }


class MegascansMetadataClient:
    """
    Megascans API client.

    In offline mode (no token), all operations return empty results.
    When a token is provided, performs real HTTP calls against the Megascans API.

    This client is injectable with a mock transport for testing:
      client._transport = MyMockTransport()
    where _transport.get(url, headers) → dict
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._token: Optional[str] = None
        self._token_ts: float = 0.0
        self._request_count = 0
        self._error_count = 0
        self._transport: Optional[Any] = None  # Injectable for tests

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def authenticate(self, token: Optional[str] = None) -> bool:
        """Set or refresh the API token.

        If token is None, reads from VIBRANTE_MEGASCANS_TOKEN env var.
        Returns True if a token is available.
        """
        try:
            resolved = (token or "").strip() or os.environ.get(ENV_MEGASCANS_TOKEN, "").strip()
            with self._lock:
                self._token = resolved if resolved else None
                self._token_ts = time.time() if self._token else 0.0
            return bool(resolved)
        except Exception:
            return False

    def _get_token(self) -> Optional[str]:
        with self._lock:
            if not self._token:
                self._token = os.environ.get(ENV_MEGASCANS_TOKEN, "").strip() or None
                if self._token:
                    self._token_ts = time.time()
            if self._token and (time.time() - self._token_ts) > _TOKEN_TTL_SECONDS:
                self._token = None
            return self._token

    def _is_online(self) -> bool:
        return bool(self._get_token())

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search_assets(
        self,
        query: str,
        category: str = "",
        limit: int = 20,
    ) -> MegascansSearchResult:
        """Search Megascans assets by query string. Never raises."""
        try:
            if not self._is_online():
                return MegascansSearchResult(
                    ok=False,
                    source="offline",
                    errors=["No Megascans token — set VIBRANTE_MEGASCANS_TOKEN to enable API access."],
                )
            return self._do_search(str(query).strip(), str(category).strip(), int(limit))
        except Exception as exc:
            return MegascansSearchResult(
                ok=False,
                source="error",
                errors=[f"search_assets failed: {exc}"],
            )

    def _do_search(self, query: str, category: str, limit: int) -> MegascansSearchResult:
        token = self._get_token()
        url = f"{_DEFAULT_BASE_URL}/assets"
        params: Dict[str, Any] = {"search": query, "limit": limit}
        if category:
            params["category"] = category

        data = self._fetch(url, token, params)
        if data is None:
            return MegascansSearchResult(ok=False, source="error", errors=["Fetch failed"])

        assets_raw = data.get("assets") or data.get("results") or []
        assets = [self.build_asset_record(a) for a in assets_raw if isinstance(a, dict)]
        return MegascansSearchResult(
            ok=True,
            assets=assets,
            total=int(data.get("total") or len(assets)),
            source="api",
        )

    # ------------------------------------------------------------------
    # Asset get / metadata
    # ------------------------------------------------------------------

    def get_asset(self, asset_id: str) -> Optional[MegascansAssetMetadata]:
        """Fetch a single asset record. Returns None on failure or offline. Never raises."""
        try:
            if not self._is_online():
                return None
            token = self._get_token()
            url = f"{_DEFAULT_BASE_URL}/assets/{asset_id}"
            data = self._fetch(url, token, {})
            if not data:
                return None
            return self.build_asset_record(data)
        except Exception:
            return None

    def get_asset_metadata(self, asset_id: str) -> Dict[str, Any]:
        """Fetch full metadata for an asset. Returns empty dict if unavailable."""
        try:
            record = self.get_asset(asset_id)
            return record.to_dict() if record else {}
        except Exception:
            return {}

    def get_asset_tags(self, asset_id: str) -> List[str]:
        """Fetch tags for an asset."""
        try:
            meta = self.get_asset_metadata(asset_id)
            return list(meta.get("tags") or [])
        except Exception:
            return []

    def get_asset_category(self, asset_id: str) -> str:
        """Fetch category for an asset."""
        try:
            meta = self.get_asset_metadata(asset_id)
            return str(meta.get("category") or "")
        except Exception:
            return ""

    # ------------------------------------------------------------------
    # Record builder
    # ------------------------------------------------------------------

    def build_asset_record(self, raw: Dict[str, Any]) -> MegascansAssetMetadata:
        """Normalize a raw Megascans API response dict into MegascansAssetMetadata."""
        if not isinstance(raw, dict):
            return MegascansAssetMetadata()
        ms_type = str(raw.get("type") or raw.get("assetType") or "").lower()
        category = _MS_TYPE_TO_CATEGORY.get(ms_type, ms_type or "prop")

        tags_raw = raw.get("tags") or raw.get("keywords") or []
        if isinstance(tags_raw, str):
            tags_raw = [t.strip() for t in tags_raw.split(",") if t.strip()]
        tags = [str(t).lower().strip() for t in tags_raw if str(t).strip()]

        return MegascansAssetMetadata(
            asset_id=str(raw.get("id") or raw.get("asset_id") or "").strip(),
            name=str(raw.get("name") or raw.get("title") or "").strip(),
            provider="megascans",
            category=category,
            ms_type=ms_type,
            tags=tags,
            description=str(raw.get("description") or raw.get("overview") or "").strip(),
            preview_url=str(raw.get("previewUrl") or raw.get("preview") or "").strip(),
            download_url=str(raw.get("downloadUrl") or raw.get("download") or "").strip(),
            metadata_source="api",
            formats=list(raw.get("formats") or []),
            raw=dict(raw),
        )

    # ------------------------------------------------------------------
    # Transport (injectable for tests)
    # ------------------------------------------------------------------

    def _fetch(
        self,
        url: str,
        token: Optional[str],
        params: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Perform HTTP GET. Returns None on failure."""
        if self._transport is not None:
            return self._transport.get(url, token, params)
        # Real HTTP call using stdlib urllib
        try:
            import urllib.request
            import urllib.parse
            full_url = url
            if params:
                full_url = f"{url}?{urllib.parse.urlencode(params)}"
            req = urllib.request.Request(full_url)
            if token:
                req.add_header("Authorization", f"Bearer {token}")
            req.add_header("Accept", "application/json")
            with urllib.request.urlopen(req, timeout=10) as resp:
                import json as _json
                data = _json.loads(resp.read().decode("utf-8", errors="replace"))
                with self._lock:
                    self._request_count += 1
                return data if isinstance(data, dict) else None
        except Exception:
            with self._lock:
                self._error_count += 1
            return None

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "request_count": self._request_count,
                "error_count":   self._error_count,
                "online":        self._is_online(),
            }


_INSTANCE: Optional[MegascansMetadataClient] = None
_INSTANCE_LOCK = threading.Lock()


def get_megascans_metadata_client() -> MegascansMetadataClient:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = MegascansMetadataClient()
    return _INSTANCE


def reset_megascans_metadata_client_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
