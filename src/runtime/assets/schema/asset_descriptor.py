"""
Asset Descriptor Schema (Tier 8 — Asset Intelligence Runtime)
==============================================================
Canonical typed models for the Asset Intelligence layer.

  AssetMetadata        — extended provider-specific metadata
  AssetPreview         — preview / thumbnail information
  AssetDescriptor      — the primary normalized asset model
  AssetProviderResult  — raw + normalized result from one provider call
  AssetQueryResult     — merged multi-provider result for one AssetQuery
  AssetRecommendation  — ranked, scored, explainable asset recommendation

DESIGN RULES:
  1. All fields typed — no free-form blobs.
  2. All models have to_dict() / from_dict() / to_json() / from_json().
  3. Schema versioned — SCHEMA_VERSION for forward-compatibility.
  4. Defaults are sensible — partial results are valid.
  5. No Houdini imports.  No bridge calls.  Pure data.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

SCHEMA_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Enum constants
# ---------------------------------------------------------------------------

ASSET_CATEGORIES = frozenset({
    "vehicle", "character", "structure", "prop", "vegetation", "creature",
    "furniture", "machinery", "weapon", "material", "hdri", "environment",
    "robot", "electronic", "organic", "abstract", "architectural", "terrain",
    "effects", "animation", "other",
})

ASSET_FORMATS = frozenset({
    "fbx", "obj", "gltf", "glb", "usd", "usda", "usdc", "usdz",
    "abc", "ply", "stl", "blend", "max", "ma", "mb", "hip",
    "bgeo", "vdb", "exr", "hdr", "png", "jpg", "mp4",
})

LICENSE_TYPES = frozenset({
    "cc0", "cc-by", "cc-by-sa", "cc-by-nc", "cc-by-nc-sa",
    "royalty_free", "editorial_only", "commercial", "custom", "unknown",
})

SCALE_TYPES = frozenset({
    "microscopic", "tiny", "small", "human", "architectural",
    "vehicle", "urban", "landscape", "planetary", "unknown",
})

ASSET_STYLES = frozenset({
    "photorealistic", "stylized", "low_poly", "cartoon", "abstract",
    "sci_fi", "fantasy", "noir", "sketch", "painterly", "unknown",
})


# ---------------------------------------------------------------------------
# Supporting models
# ---------------------------------------------------------------------------

@dataclass
class AssetMetadata:
    """Extended metadata attached to an AssetDescriptor."""

    face_count:     int   = 0
    vertex_count:   int   = 0
    animation_count: int  = 0
    is_animated:    bool  = False
    is_rigged:      bool  = False
    lod_levels:     int   = 1
    texture_count:  int   = 0
    material_count: int   = 0
    file_size_mb:   float = 0.0
    upload_date:    str   = ""
    author:         str   = ""
    source_url:     str   = ""
    extra:          Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "face_count":      self.face_count,
            "vertex_count":    self.vertex_count,
            "animation_count": self.animation_count,
            "is_animated":     self.is_animated,
            "is_rigged":       self.is_rigged,
            "lod_levels":      self.lod_levels,
            "texture_count":   self.texture_count,
            "material_count":  self.material_count,
            "file_size_mb":    self.file_size_mb,
            "upload_date":     self.upload_date,
            "author":          self.author,
            "source_url":      self.source_url,
            "extra":           dict(self.extra),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AssetMetadata":
        return cls(
            face_count=int(d.get("face_count", 0)),
            vertex_count=int(d.get("vertex_count", 0)),
            animation_count=int(d.get("animation_count", 0)),
            is_animated=bool(d.get("is_animated", False)),
            is_rigged=bool(d.get("is_rigged", False)),
            lod_levels=int(d.get("lod_levels", 1)),
            texture_count=int(d.get("texture_count", 0)),
            material_count=int(d.get("material_count", 0)),
            file_size_mb=float(d.get("file_size_mb", 0.0)),
            upload_date=str(d.get("upload_date", "")),
            author=str(d.get("author", "")),
            source_url=str(d.get("source_url", "")),
            extra=dict(d.get("extra") or {}),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_json(cls, s: str) -> "AssetMetadata":
        return cls.from_dict(json.loads(s))


@dataclass
class AssetPreview:
    """Preview / thumbnail information for an asset."""

    preview_id:    str = field(default_factory=lambda: f"prev_{uuid.uuid4().hex[:8]}")
    asset_id:      str = ""
    provider:      str = ""
    url:           str = ""
    thumbnail_url: str = ""
    format:        str = "jpg"
    width:         int = 0
    height:        int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "preview_id":    self.preview_id,
            "asset_id":      self.asset_id,
            "provider":      self.provider,
            "url":           self.url,
            "thumbnail_url": self.thumbnail_url,
            "format":        self.format,
            "width":         self.width,
            "height":        self.height,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AssetPreview":
        return cls(
            preview_id=str(d.get("preview_id", f"prev_{uuid.uuid4().hex[:8]}")),
            asset_id=str(d.get("asset_id", "")),
            provider=str(d.get("provider", "")),
            url=str(d.get("url", "")),
            thumbnail_url=str(d.get("thumbnail_url", "")),
            format=str(d.get("format", "jpg")),
            width=int(d.get("width", 0)),
            height=int(d.get("height", 0)),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_json(cls, s: str) -> "AssetPreview":
        return cls.from_dict(json.loads(s))


# ---------------------------------------------------------------------------
# Primary model
# ---------------------------------------------------------------------------

@dataclass
class AssetDescriptor:
    """
    Normalized, provider-agnostic representation of a 3D asset.

    All fields are typed.  Provider-specific data is isolated in
    ``metadata.extra`` so it never leaks into the core model.
    """

    asset_id:     str = field(default_factory=lambda: f"asset_{uuid.uuid4().hex[:12]}")
    provider:     str = ""
    name:         str = ""

    category:     str = "other"
    subcategory:  str = ""

    tags:         List[str] = field(default_factory=list)
    keywords:     List[str] = field(default_factory=list)

    license:      str = "unknown"
    formats:      List[str] = field(default_factory=list)

    preview_url:  str = ""
    download_url: str = ""
    preview:      Optional[AssetPreview] = None

    dimensions:   Dict[str, float] = field(default_factory=dict)
    scale:        str = "unknown"

    rating:       float = 0.0
    popularity:   int   = 0

    style:        str  = "unknown"
    environment_suitability: List[str] = field(default_factory=list)

    metadata:     AssetMetadata = field(default_factory=AssetMetadata)

    schema_version: str = SCHEMA_VERSION

    # ------------------------------------------------------------------
    # Computed properties
    # ------------------------------------------------------------------

    @property
    def is_cc0(self) -> bool:
        return self.license == "cc0"

    @property
    def has_usd(self) -> bool:
        return any(f in ("usd", "usda", "usdc", "usdz") for f in self.formats)

    @property
    def has_vdb(self) -> bool:
        return "vdb" in self.formats

    @property
    def tag_set(self) -> frozenset:
        return frozenset(t.lower() for t in self.tags + self.keywords)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id":               self.asset_id,
            "provider":               self.provider,
            "name":                   self.name,
            "category":               self.category,
            "subcategory":            self.subcategory,
            "tags":                   list(self.tags),
            "keywords":               list(self.keywords),
            "license":                self.license,
            "formats":                list(self.formats),
            "preview_url":            self.preview_url,
            "download_url":           self.download_url,
            "preview":                self.preview.to_dict() if self.preview else None,
            "dimensions":             dict(self.dimensions),
            "scale":                  self.scale,
            "rating":                 self.rating,
            "popularity":             self.popularity,
            "style":                  self.style,
            "environment_suitability": list(self.environment_suitability),
            "metadata":               self.metadata.to_dict(),
            "schema_version":         self.schema_version,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AssetDescriptor":
        preview_data = d.get("preview")
        preview = AssetPreview.from_dict(preview_data) if isinstance(preview_data, dict) else None
        meta_data = d.get("metadata")
        meta = AssetMetadata.from_dict(meta_data) if isinstance(meta_data, dict) else AssetMetadata()
        return cls(
            asset_id=str(d.get("asset_id", f"asset_{uuid.uuid4().hex[:12]}")),
            provider=str(d.get("provider", "")),
            name=str(d.get("name", "")),
            category=str(d.get("category", "other")),
            subcategory=str(d.get("subcategory", "")),
            tags=list(d.get("tags") or []),
            keywords=list(d.get("keywords") or []),
            license=str(d.get("license", "unknown")),
            formats=list(d.get("formats") or []),
            preview_url=str(d.get("preview_url", "")),
            download_url=str(d.get("download_url", "")),
            preview=preview,
            dimensions=dict(d.get("dimensions") or {}),
            scale=str(d.get("scale", "unknown")),
            rating=float(d.get("rating", 0.0)),
            popularity=int(d.get("popularity", 0)),
            style=str(d.get("style", "unknown")),
            environment_suitability=list(d.get("environment_suitability") or []),
            metadata=meta,
            schema_version=str(d.get("schema_version", SCHEMA_VERSION)),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_json(cls, s: str) -> "AssetDescriptor":
        return cls.from_dict(json.loads(s))


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------

@dataclass
class AssetProviderResult:
    """Raw + normalized output from one provider for one query."""

    provider:          str               = ""
    query_params:      Dict[str, Any]    = field(default_factory=dict)
    raw_data:          List[Dict[str, Any]] = field(default_factory=list)
    normalized_assets: List[AssetDescriptor] = field(default_factory=list)
    success:           bool              = True
    errors:            List[str]         = field(default_factory=list)
    query_time:        float             = 0.0
    cached:            bool              = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider":          self.provider,
            "query_params":      dict(self.query_params),
            "raw_data":          list(self.raw_data),
            "normalized_assets": [a.to_dict() for a in self.normalized_assets],
            "success":           self.success,
            "errors":            list(self.errors),
            "query_time":        self.query_time,
            "cached":            self.cached,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AssetProviderResult":
        assets = [
            AssetDescriptor.from_dict(a)
            for a in (d.get("normalized_assets") or [])
            if isinstance(a, dict)
        ]
        return cls(
            provider=str(d.get("provider", "")),
            query_params=dict(d.get("query_params") or {}),
            raw_data=list(d.get("raw_data") or []),
            normalized_assets=assets,
            success=bool(d.get("success", True)),
            errors=list(d.get("errors") or []),
            query_time=float(d.get("query_time", 0.0)),
            cached=bool(d.get("cached", False)),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_json(cls, s: str) -> "AssetProviderResult":
        return cls.from_dict(json.loads(s))


@dataclass
class AssetQueryResult:
    """
    Merged multi-provider result for one AssetQuery from a ScenePlan.

    Produced by AssetDiscoveryEngine after querying all registered
    providers, deduplicating, and normalizing outputs.
    """

    result_id:  str = field(default_factory=lambda: f"aqr_{uuid.uuid4().hex[:10]}")
    query_id:   str = ""
    category:   str = ""
    zone:       str = ""
    assets:     List[AssetDescriptor] = field(default_factory=list)
    total_found: int = 0
    provider_results: List[AssetProviderResult] = field(default_factory=list)
    errors:     List[str] = field(default_factory=list)
    query_time: float = 0.0
    cached:     bool  = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "result_id":       self.result_id,
            "query_id":        self.query_id,
            "category":        self.category,
            "zone":            self.zone,
            "assets":          [a.to_dict() for a in self.assets],
            "total_found":     self.total_found,
            "provider_results": [r.to_dict() for r in self.provider_results],
            "errors":          list(self.errors),
            "query_time":      self.query_time,
            "cached":          self.cached,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AssetQueryResult":
        assets = [
            AssetDescriptor.from_dict(a)
            for a in (d.get("assets") or [])
            if isinstance(a, dict)
        ]
        prs = [
            AssetProviderResult.from_dict(r)
            for r in (d.get("provider_results") or [])
            if isinstance(r, dict)
        ]
        return cls(
            result_id=str(d.get("result_id", f"aqr_{uuid.uuid4().hex[:10]}")),
            query_id=str(d.get("query_id", "")),
            category=str(d.get("category", "")),
            zone=str(d.get("zone", "")),
            assets=assets,
            total_found=int(d.get("total_found", 0)),
            provider_results=prs,
            errors=list(d.get("errors") or []),
            query_time=float(d.get("query_time", 0.0)),
            cached=bool(d.get("cached", False)),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_json(cls, s: str) -> "AssetQueryResult":
        return cls.from_dict(json.loads(s))


@dataclass
class AssetRecommendation:
    """
    A ranked, scored, explainable asset recommendation.

    Produced by AssetRecommendationEngine after Discovery → Validation →
    Ranking.  Every score factor is named so downstream modules can
    explain why a particular asset was recommended.
    """

    recommendation_id: str   = field(default_factory=lambda: f"rec_{uuid.uuid4().hex[:10]}")
    asset:             Optional[AssetDescriptor] = None
    score:             float = 0.0
    rank:              int   = 0
    zone:              str   = ""
    category:          str   = ""
    score_breakdown:   Dict[str, float] = field(default_factory=dict)
    boost_reasons:     List[str]        = field(default_factory=list)
    source:            str   = "provider"     # memory | pattern | graph | provider
    confidence:        float = 0.5
    notes:             List[str]        = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recommendation_id": self.recommendation_id,
            "asset":             self.asset.to_dict() if self.asset else None,
            "score":             self.score,
            "rank":              self.rank,
            "zone":              self.zone,
            "category":          self.category,
            "score_breakdown":   dict(self.score_breakdown),
            "boost_reasons":     list(self.boost_reasons),
            "source":            self.source,
            "confidence":        self.confidence,
            "notes":             list(self.notes),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AssetRecommendation":
        asset_data = d.get("asset")
        asset = AssetDescriptor.from_dict(asset_data) if isinstance(asset_data, dict) else None
        return cls(
            recommendation_id=str(d.get("recommendation_id", f"rec_{uuid.uuid4().hex[:10]}")),
            asset=asset,
            score=float(d.get("score", 0.0)),
            rank=int(d.get("rank", 0)),
            zone=str(d.get("zone", "")),
            category=str(d.get("category", "")),
            score_breakdown=dict(d.get("score_breakdown") or {}),
            boost_reasons=list(d.get("boost_reasons") or []),
            source=str(d.get("source", "provider")),
            confidence=float(d.get("confidence", 0.5)),
            notes=list(d.get("notes") or []),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_json(cls, s: str) -> "AssetRecommendation":
        return cls.from_dict(json.loads(s))
