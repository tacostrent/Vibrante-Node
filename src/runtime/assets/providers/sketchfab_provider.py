"""
Sketchfab Provider (Tier 8 — Asset Intelligence Runtime)
=========================================================
Simulated Sketchfab provider with a curated seed dataset.

DESIGN RULES:
  - No HTTP calls.  No authentication.  No downloads.
  - Seed data covers industrial, sci-fi, and urban asset categories.
  - search() filters the seed data deterministically.
  - normalize() maps Sketchfab-shaped dicts to AssetDescriptor.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from src.runtime.assets.schema import (
    AssetDescriptor, AssetMetadata, AssetPreview, AssetProviderResult,
)
from .base import AssetProvider

# ---------------------------------------------------------------------------
# Seed data — representative Sketchfab-style records
# ---------------------------------------------------------------------------

_SEED: List[Dict[str, Any]] = [
    {
        "uid": "skfb_industrial_pipe_rack",
        "name": "Industrial Pipe Rack",
        "categories": ["structure", "prop"],
        "tags": ["industrial", "pipe", "metal", "factory", "machinery"],
        "license": {"slug": "by"},
        "formats": ["fbx", "obj", "gltf"],
        "preview": {"images": [{"url": "https://preview.sketchfab.com/pipe_rack.jpg"}]},
        "viewerUrl": "https://sketchfab.com/models/pipe_rack",
        "stats": {"viewCount": 4200, "likeCount": 180},
        "faceCount": 12400,
        "vertexCount": 8900,
        "isAnimated": False,
        "scale": "architectural",
        "style": "photorealistic",
        "environments": ["industrial", "urban"],
    },
    {
        "uid": "skfb_maintenance_robot",
        "name": "Maintenance Robot MK-7",
        "categories": ["character", "robot"],
        "tags": ["robot", "industrial", "sci_fi", "mechanical", "automation"],
        "license": {"slug": "by"},
        "formats": ["fbx", "gltf", "obj"],
        "preview": {"images": [{"url": "https://preview.sketchfab.com/robot_mk7.jpg"}]},
        "viewerUrl": "https://sketchfab.com/models/robot_mk7",
        "stats": {"viewCount": 9800, "likeCount": 640},
        "faceCount": 28000,
        "vertexCount": 18500,
        "isAnimated": True,
        "scale": "human",
        "style": "sci_fi",
        "environments": ["industrial", "sci_fi"],
    },
    {
        "uid": "skfb_sci_fi_terminal",
        "name": "Sci-Fi Control Terminal",
        "categories": ["prop", "electronic"],
        "tags": ["sci_fi", "terminal", "console", "panel", "electronic", "futuristic"],
        "license": {"slug": "cc0"},
        "formats": ["fbx", "obj", "gltf", "usd"],
        "preview": {"images": [{"url": "https://preview.sketchfab.com/terminal.jpg"}]},
        "viewerUrl": "https://sketchfab.com/models/terminal",
        "stats": {"viewCount": 6100, "likeCount": 320},
        "faceCount": 8600,
        "vertexCount": 5200,
        "isAnimated": False,
        "scale": "human",
        "style": "sci_fi",
        "environments": ["sci_fi", "industrial"],
    },
    {
        "uid": "skfb_rusted_machinery",
        "name": "Rusted Factory Machinery",
        "categories": ["machinery", "prop"],
        "tags": ["industrial", "rusted", "machinery", "abandoned", "decay", "factory"],
        "license": {"slug": "by"},
        "formats": ["fbx", "obj"],
        "preview": {"images": [{"url": "https://preview.sketchfab.com/rusted.jpg"}]},
        "viewerUrl": "https://sketchfab.com/models/rusted",
        "stats": {"viewCount": 3400, "likeCount": 210},
        "faceCount": 18000,
        "vertexCount": 12000,
        "isAnimated": False,
        "scale": "architectural",
        "style": "photorealistic",
        "environments": ["industrial"],
    },
    {
        "uid": "skfb_cargo_container",
        "name": "Shipping Cargo Container",
        "categories": ["structure", "vehicle"],
        "tags": ["cargo", "container", "industrial", "logistics", "metal"],
        "license": {"slug": "cc0"},
        "formats": ["fbx", "obj", "gltf", "usd"],
        "preview": {"images": [{"url": "https://preview.sketchfab.com/container.jpg"}]},
        "viewerUrl": "https://sketchfab.com/models/container",
        "stats": {"viewCount": 12000, "likeCount": 890},
        "faceCount": 6200,
        "vertexCount": 4100,
        "isAnimated": False,
        "scale": "vehicle",
        "style": "photorealistic",
        "environments": ["industrial", "urban"],
    },
    {
        "uid": "skfb_surveillance_camera",
        "name": "Industrial Surveillance Camera",
        "categories": ["prop", "electronic"],
        "tags": ["camera", "surveillance", "security", "industrial", "electronic"],
        "license": {"slug": "by"},
        "formats": ["fbx", "gltf"],
        "preview": {"images": [{"url": "https://preview.sketchfab.com/camera.jpg"}]},
        "viewerUrl": "https://sketchfab.com/models/camera",
        "stats": {"viewCount": 2800, "likeCount": 145},
        "faceCount": 4100,
        "vertexCount": 2600,
        "isAnimated": False,
        "scale": "small",
        "style": "photorealistic",
        "environments": ["industrial", "urban"],
    },
    {
        "uid": "skfb_holographic_display",
        "name": "Holographic Display Panel",
        "categories": ["prop", "electronic"],
        "tags": ["sci_fi", "hologram", "display", "futuristic", "interface", "panel"],
        "license": {"slug": "cc0"},
        "formats": ["fbx", "obj", "gltf", "usd"],
        "preview": {"images": [{"url": "https://preview.sketchfab.com/holo.jpg"}]},
        "viewerUrl": "https://sketchfab.com/models/holo",
        "stats": {"viewCount": 7600, "likeCount": 520},
        "faceCount": 3200,
        "vertexCount": 2100,
        "isAnimated": False,
        "scale": "human",
        "style": "sci_fi",
        "environments": ["sci_fi"],
    },
    {
        "uid": "skfb_abandoned_vehicle",
        "name": "Abandoned Industrial Truck",
        "categories": ["vehicle"],
        "tags": ["vehicle", "truck", "abandoned", "rusted", "industrial"],
        "license": {"slug": "by"},
        "formats": ["fbx", "obj"],
        "preview": {"images": [{"url": "https://preview.sketchfab.com/truck.jpg"}]},
        "viewerUrl": "https://sketchfab.com/models/truck",
        "stats": {"viewCount": 5400, "likeCount": 280},
        "faceCount": 22000,
        "vertexCount": 15000,
        "isAnimated": False,
        "scale": "vehicle",
        "style": "photorealistic",
        "environments": ["industrial", "urban"],
    },
    {
        "uid": "skfb_sci_fi_corridor_wall",
        "name": "Sci-Fi Corridor Wall Panel",
        "categories": ["structure", "architectural"],
        "tags": ["sci_fi", "corridor", "wall", "panel", "futuristic", "modular"],
        "license": {"slug": "cc0"},
        "formats": ["fbx", "gltf", "usd"],
        "preview": {"images": [{"url": "https://preview.sketchfab.com/wall_panel.jpg"}]},
        "viewerUrl": "https://sketchfab.com/models/wall_panel",
        "stats": {"viewCount": 3100, "likeCount": 190},
        "faceCount": 5600,
        "vertexCount": 3800,
        "isAnimated": False,
        "scale": "architectural",
        "style": "sci_fi",
        "environments": ["sci_fi"],
    },
    {
        "uid": "skfb_industrial_forklift",
        "name": "Industrial Forklift",
        "categories": ["vehicle", "machinery"],
        "tags": ["forklift", "vehicle", "industrial", "warehouse", "machinery"],
        "license": {"slug": "by"},
        "formats": ["fbx", "obj", "gltf"],
        "preview": {"images": [{"url": "https://preview.sketchfab.com/forklift.jpg"}]},
        "viewerUrl": "https://sketchfab.com/models/forklift",
        "stats": {"viewCount": 4900, "likeCount": 260},
        "faceCount": 16500,
        "vertexCount": 11200,
        "isAnimated": False,
        "scale": "vehicle",
        "style": "photorealistic",
        "environments": ["industrial"],
    },
]

# Licence slug → normalized license
_LICENCE_MAP: Dict[str, str] = {
    "cc0":        "cc0",
    "by":         "cc-by",
    "by-sa":      "cc-by-sa",
    "by-nc":      "cc-by-nc",
    "by-nc-sa":   "cc-by-nc-sa",
    "editorial":  "editorial_only",
    "commercial": "commercial",
}


class SketchfabProvider(AssetProvider):
    """Simulated Sketchfab provider (no API calls, curated seed data)."""

    @property
    def provider_name(self) -> str:
        return "sketchfab"

    @property
    def supported_categories(self) -> List[str]:
        return [
            "vehicle", "character", "structure", "prop", "vegetation",
            "creature", "furniture", "machinery", "weapon", "electronic",
            "robot", "architectural", "other",
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
                query_params={
                    "category": category,
                    "tags": tags or [],
                    "keywords": keywords or [],
                    "limit": limit,
                },
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
        envs = list(raw.get("environments", []))
        stats = raw.get("stats", {})
        preview_imgs = raw.get("preview", {}).get("images", [])
        preview_url = preview_imgs[0].get("url", "") if preview_imgs else ""
        licence_slug = raw.get("license", {}).get("slug", "unknown")
        return AssetDescriptor(
            asset_id=f"skfb_{raw.get('uid', '')}",
            provider=self.provider_name,
            name=str(raw.get("name", "")),
            category=primary_cat,
            subcategory=cats[1] if len(cats) > 1 else "",
            tags=tags,
            keywords=tags,
            license=_LICENCE_MAP.get(licence_slug, "unknown"),
            formats=list(raw.get("formats", [])),
            preview_url=preview_url,
            download_url=str(raw.get("viewerUrl", "")),
            preview=AssetPreview(
                asset_id=f"skfb_{raw.get('uid', '')}",
                provider=self.provider_name,
                url=preview_url,
                thumbnail_url=preview_url,
            ),
            dimensions={},
            scale=str(raw.get("scale", "unknown")),
            rating=min(5.0, float(stats.get("likeCount", 0)) / 200.0),
            popularity=int(stats.get("viewCount", 0)),
            style=str(raw.get("style", "unknown")),
            environment_suitability=envs,
            metadata=AssetMetadata(
                face_count=int(raw.get("faceCount", 0)),
                vertex_count=int(raw.get("vertexCount", 0)),
                is_animated=bool(raw.get("isAnimated", False)),
            ),
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

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
            # Category filter — pass if no category requested or category matches
            cat_match = not category or category.lower() in cats
            # Tag filter — pass if no tags requested or at least one tag overlaps
            tag_match = not query_terms or bool(query_terms & rec_tags)
            if cat_match and tag_match:
                results.append(rec)
            if len(results) >= limit:
                break
        return results
