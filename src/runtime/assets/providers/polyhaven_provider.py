"""
Polyhaven Provider (Tier 8 — Asset Intelligence Runtime)
=========================================================
Simulated Polyhaven provider with CC0-licensed seed data.

Polyhaven specialises in:
  - CC0 HDRIs (lighting environments)
  - CC0 Textures / materials
  - CC0 3D models (architectural, vegetation, props)

DESIGN RULES:
  - No HTTP calls.  No authentication.  No downloads.
  - All seed assets use CC0 licence — a key Polyhaven differentiator.
  - normalize() maps Polyhaven-shaped dicts to AssetDescriptor.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from src.runtime.assets.schema import (
    AssetDescriptor, AssetMetadata, AssetPreview, AssetProviderResult,
)
from .base import AssetProvider

_SEED: List[Dict[str, Any]] = [
    {
        "id": "concrete_wall_001",
        "name": "Concrete Wall Panel",
        "type": "material",
        "categories": ["material", "architectural"],
        "tags": ["concrete", "wall", "industrial", "architectural", "rough"],
        "formats": ["gltf", "fbx", "obj"],
        "downloads": 18400,
        "scale": "architectural",
        "style": "photorealistic",
        "environments": ["industrial", "urban", "architectural"],
        "face_count": 2,
        "vertex_count": 4,
    },
    {
        "id": "metal_grating_floor",
        "name": "Metal Grating Floor Panel",
        "type": "material",
        "categories": ["material", "structure"],
        "tags": ["metal", "grating", "floor", "industrial", "grid"],
        "formats": ["gltf", "fbx", "obj"],
        "downloads": 12100,
        "scale": "architectural",
        "style": "photorealistic",
        "environments": ["industrial"],
        "face_count": 8,
        "vertex_count": 16,
    },
    {
        "id": "oak_tree_autumn",
        "name": "Oak Tree — Autumn",
        "type": "model",
        "categories": ["vegetation"],
        "tags": ["tree", "oak", "vegetation", "forest", "nature", "autumn"],
        "formats": ["gltf", "fbx", "abc"],
        "downloads": 22000,
        "scale": "architectural",
        "style": "photorealistic",
        "environments": ["forest", "urban", "landscape"],
        "face_count": 45000,
        "vertex_count": 32000,
    },
    {
        "id": "stone_pavement_cobble",
        "name": "Cobblestone Pavement",
        "type": "material",
        "categories": ["material", "terrain"],
        "tags": ["stone", "cobblestone", "pavement", "urban", "street", "road"],
        "formats": ["gltf", "obj"],
        "downloads": 31000,
        "scale": "architectural",
        "style": "photorealistic",
        "environments": ["urban"],
        "face_count": 2,
        "vertex_count": 4,
    },
    {
        "id": "hdri_overcast_sky",
        "name": "Overcast Sky — HDRI",
        "type": "hdri",
        "categories": ["hdri", "environment"],
        "tags": ["hdri", "sky", "overcast", "diffuse", "lighting"],
        "formats": ["exr", "hdr"],
        "downloads": 48000,
        "scale": "landscape",
        "style": "photorealistic",
        "environments": ["urban", "landscape", "industrial"],
        "face_count": 0,
        "vertex_count": 0,
    },
    {
        "id": "rough_metal_01",
        "name": "Rough Metal Surface",
        "type": "material",
        "categories": ["material"],
        "tags": ["metal", "rough", "industrial", "scratched", "oxidized"],
        "formats": ["gltf", "obj"],
        "downloads": 25000,
        "scale": "unknown",
        "style": "photorealistic",
        "environments": ["industrial", "sci_fi"],
        "face_count": 2,
        "vertex_count": 4,
    },
    {
        "id": "wooden_planks_worn",
        "name": "Worn Wooden Planks",
        "type": "material",
        "categories": ["material", "architectural"],
        "tags": ["wood", "planks", "worn", "aged", "floor"],
        "formats": ["gltf", "obj"],
        "downloads": 19000,
        "scale": "architectural",
        "style": "photorealistic",
        "environments": ["architectural", "urban"],
        "face_count": 2,
        "vertex_count": 4,
    },
    {
        "id": "industrial_barrel",
        "name": "Industrial Metal Barrel",
        "type": "model",
        "categories": ["prop"],
        "tags": ["barrel", "industrial", "metal", "container", "prop"],
        "formats": ["gltf", "fbx", "obj", "usd"],
        "downloads": 35000,
        "scale": "human",
        "style": "photorealistic",
        "environments": ["industrial", "urban"],
        "face_count": 1200,
        "vertex_count": 800,
    },
    {
        "id": "gravel_ground_01",
        "name": "Gravel Ground",
        "type": "material",
        "categories": ["material", "terrain"],
        "tags": ["gravel", "ground", "rocks", "terrain", "outdoor"],
        "formats": ["gltf", "obj"],
        "downloads": 42000,
        "scale": "unknown",
        "style": "photorealistic",
        "environments": ["industrial", "landscape", "urban"],
        "face_count": 2,
        "vertex_count": 4,
    },
    {
        "id": "hdri_golden_hour",
        "name": "Golden Hour Sunset — HDRI",
        "type": "hdri",
        "categories": ["hdri", "environment"],
        "tags": ["hdri", "golden_hour", "sunset", "warm", "lighting", "dramatic"],
        "formats": ["exr", "hdr"],
        "downloads": 62000,
        "scale": "landscape",
        "style": "photorealistic",
        "environments": ["urban", "landscape", "industrial"],
        "face_count": 0,
        "vertex_count": 0,
    },
]


class PolyhavenProvider(AssetProvider):
    """Simulated Polyhaven CC0 provider (no API calls, curated seed data)."""

    @property
    def provider_name(self) -> str:
        return "polyhaven"

    @property
    def supported_categories(self) -> List[str]:
        return [
            "material", "hdri", "environment", "vegetation",
            "prop", "terrain", "architectural", "structure", "other",
        ]

    def search(
        self,
        category: str,
        tags: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None,
        style_hints: Optional[List[str]] = None,
        limit: int = 20,
        **kwargs: Any,
    ) -> AssetProviderResult:
        t0 = time.perf_counter()
        try:
            matched = self._filter_seed(category, tags or [], keywords or [], limit)
            normalized = [self.normalize(r) for r in matched]
            return AssetProviderResult(
                provider=self.provider_name,
                query_params={"category": category, "tags": tags or [], "limit": limit},
                raw_data=matched,
                normalized_assets=normalized,
                success=True,
                errors=[],
                query_time=time.perf_counter() - t0,
                cached=False,
            )
        except Exception as exc:
            return AssetProviderResult(
                provider=self.provider_name,
                success=False,
                errors=[str(exc)],
                query_time=time.perf_counter() - t0,
            )

    def normalize(self, raw: Dict[str, Any]) -> AssetDescriptor:
        cats = list(raw.get("categories", ["other"]))
        primary_cat = cats[0] if cats else "other"
        tags = list(raw.get("tags", []))
        downloads = int(raw.get("downloads", 0))
        return AssetDescriptor(
            asset_id=f"ph_{raw.get('id', '')}",
            provider=self.provider_name,
            name=str(raw.get("name", "")),
            category=primary_cat,
            subcategory=cats[1] if len(cats) > 1 else "",
            tags=tags,
            keywords=tags,
            license="cc0",
            formats=list(raw.get("formats", [])),
            preview_url=f"https://dl.polyhaven.org/previews/{raw.get('id', '')}.jpg",
            download_url=f"https://dl.polyhaven.org/{raw.get('id', '')}",
            preview=AssetPreview(
                asset_id=f"ph_{raw.get('id', '')}",
                provider=self.provider_name,
                url=f"https://dl.polyhaven.org/previews/{raw.get('id', '')}.jpg",
                thumbnail_url=f"https://dl.polyhaven.org/previews/{raw.get('id', '')}_thumb.jpg",
            ),
            scale=str(raw.get("scale", "unknown")),
            rating=min(5.0, downloads / 10000.0),
            popularity=downloads,
            style=str(raw.get("style", "photorealistic")),
            environment_suitability=list(raw.get("environments", [])),
            metadata=AssetMetadata(
                face_count=int(raw.get("face_count", 0)),
                vertex_count=int(raw.get("vertex_count", 0)),
            ),
        )

    def _filter_seed(
        self,
        category: str,
        tags: List[str],
        keywords: List[str],
        limit: int,
    ) -> List[Dict[str, Any]]:
        query_terms = {t.lower() for t in tags + keywords}
        results = []
        for rec in _SEED:
            cats = [c.lower() for c in rec.get("categories", [])]
            rec_tags = {t.lower() for t in rec.get("tags", [])}
            cat_match = not category or category.lower() in cats
            tag_match = not query_terms or bool(query_terms & rec_tags)
            if cat_match and tag_match:
                results.append(rec)
            if len(results) >= limit:
                break
        return results
