"""
Sketchfab Live Provider (Tier 12 — Asset Ecosystem Expansion)
===============================================================
Extended simulated Sketchfab provider with 20+ assets and pagination.
NO real HTTP calls — extended seed data only.

provider_name = "sketchfab_live"

DESIGN RULES:
  - No HTTP calls.  No authentication.  No downloads.
  - Pagination simulated via page/page_size parameters.
  - More assets than the basic SketchfabProvider.
  - normalize_result() is the authoritative normalizer for this provider.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from src.runtime.assets.schema import (
    AssetDescriptor, AssetMetadata, AssetPreview, AssetProviderResult,
)
from .base import AssetProvider

# ---------------------------------------------------------------------------
# Extended seed data (20+ assets)
# ---------------------------------------------------------------------------

_SEED: List[Dict[str, Any]] = [
    # --- Industrial ---
    {
        "uid": "live_industrial_pipe_rack",
        "name": "Industrial Pipe Rack",
        "categories": ["structure", "prop"],
        "tags": ["industrial", "pipe", "metal", "factory", "machinery"],
        "license": {"slug": "by"},
        "formats": ["fbx", "obj", "gltf"],
        "preview": {"images": [{"url": "https://preview.sketchfab.com/pipe_rack.jpg"}]},
        "viewerUrl": "https://sketchfab.com/models/pipe_rack",
        "stats": {"viewCount": 4200, "likeCount": 180},
        "faceCount": 12400, "vertexCount": 8900, "isAnimated": False,
        "scale": "architectural", "style": "photorealistic",
        "environments": ["industrial_hangar", "abandoned_factory"],
    },
    {
        "uid": "live_maintenance_robot",
        "name": "Maintenance Robot MK-7",
        "categories": ["robot", "character"],
        "tags": ["robot", "industrial", "sci_fi", "mechanical", "automation"],
        "license": {"slug": "by"},
        "formats": ["fbx", "gltf", "obj"],
        "preview": {"images": [{"url": "https://preview.sketchfab.com/robot_mk7.jpg"}]},
        "viewerUrl": "https://sketchfab.com/models/robot_mk7",
        "stats": {"viewCount": 9800, "likeCount": 640},
        "faceCount": 28000, "vertexCount": 18500, "isAnimated": True,
        "scale": "human", "style": "sci_fi",
        "environments": ["industrial_hangar", "robotics_lab"],
    },
    {
        "uid": "live_sci_fi_terminal",
        "name": "Sci-Fi Control Terminal",
        "categories": ["prop", "electronic"],
        "tags": ["sci_fi", "terminal", "console", "panel", "electronic", "futuristic"],
        "license": {"slug": "cc0"},
        "formats": ["fbx", "obj", "gltf", "usd"],
        "preview": {"images": [{"url": "https://preview.sketchfab.com/terminal.jpg"}]},
        "viewerUrl": "https://sketchfab.com/models/terminal",
        "stats": {"viewCount": 6100, "likeCount": 320},
        "faceCount": 8600, "vertexCount": 5200, "isAnimated": False,
        "scale": "human", "style": "sci_fi",
        "environments": ["sci_fi_corridor", "control_room"],
    },
    {
        "uid": "live_rusted_machinery",
        "name": "Rusted Factory Machinery",
        "categories": ["machinery", "prop"],
        "tags": ["industrial", "rusted", "machinery", "abandoned", "decay", "factory"],
        "license": {"slug": "by"},
        "formats": ["fbx", "obj"],
        "preview": {"images": [{"url": "https://preview.sketchfab.com/rusted.jpg"}]},
        "viewerUrl": "https://sketchfab.com/models/rusted",
        "stats": {"viewCount": 3400, "likeCount": 210},
        "faceCount": 18000, "vertexCount": 12000, "isAnimated": False,
        "scale": "architectural", "style": "photorealistic",
        "environments": ["abandoned_factory"],
    },
    {
        "uid": "live_cargo_container",
        "name": "Shipping Cargo Container",
        "categories": ["structure", "vehicle"],
        "tags": ["cargo", "container", "industrial", "logistics", "metal"],
        "license": {"slug": "cc0"},
        "formats": ["fbx", "obj", "gltf", "usd"],
        "preview": {"images": [{"url": "https://preview.sketchfab.com/container.jpg"}]},
        "viewerUrl": "https://sketchfab.com/models/container",
        "stats": {"viewCount": 12000, "likeCount": 890},
        "faceCount": 6200, "vertexCount": 4100, "isAnimated": False,
        "scale": "vehicle", "style": "photorealistic",
        "environments": ["industrial_hangar"],
    },
    {
        "uid": "live_industrial_forklift",
        "name": "Industrial Forklift",
        "categories": ["vehicle", "machinery"],
        "tags": ["forklift", "vehicle", "industrial", "warehouse", "machinery"],
        "license": {"slug": "by"},
        "formats": ["fbx", "obj", "gltf"],
        "preview": {"images": [{"url": "https://preview.sketchfab.com/forklift.jpg"}]},
        "viewerUrl": "https://sketchfab.com/models/forklift",
        "stats": {"viewCount": 4900, "likeCount": 260},
        "faceCount": 16500, "vertexCount": 11200, "isAnimated": False,
        "scale": "vehicle", "style": "photorealistic",
        "environments": ["industrial_hangar"],
    },
    {
        "uid": "live_surveillance_camera",
        "name": "Industrial Surveillance Camera",
        "categories": ["prop", "electronic"],
        "tags": ["camera", "surveillance", "security", "industrial", "electronic"],
        "license": {"slug": "by"},
        "formats": ["fbx", "gltf"],
        "preview": {"images": [{"url": "https://preview.sketchfab.com/camera.jpg"}]},
        "viewerUrl": "https://sketchfab.com/models/camera",
        "stats": {"viewCount": 2800, "likeCount": 145},
        "faceCount": 4100, "vertexCount": 2600, "isAnimated": False,
        "scale": "small", "style": "photorealistic",
        "environments": ["industrial_hangar", "control_room"],
    },
    # --- Sci-Fi ---
    {
        "uid": "live_holographic_display",
        "name": "Holographic Display Panel",
        "categories": ["prop", "electronic"],
        "tags": ["sci_fi", "hologram", "display", "futuristic", "interface", "panel"],
        "license": {"slug": "cc0"},
        "formats": ["fbx", "obj", "gltf", "usd"],
        "preview": {"images": [{"url": "https://preview.sketchfab.com/holo.jpg"}]},
        "viewerUrl": "https://sketchfab.com/models/holo",
        "stats": {"viewCount": 7600, "likeCount": 520},
        "faceCount": 3200, "vertexCount": 2100, "isAnimated": False,
        "scale": "human", "style": "sci_fi",
        "environments": ["sci_fi_corridor", "control_room"],
    },
    {
        "uid": "live_sci_fi_corridor_wall",
        "name": "Sci-Fi Corridor Wall Panel",
        "categories": ["structure", "architectural"],
        "tags": ["sci_fi", "corridor", "wall", "panel", "futuristic", "modular"],
        "license": {"slug": "cc0"},
        "formats": ["fbx", "gltf", "usd"],
        "preview": {"images": [{"url": "https://preview.sketchfab.com/wall_panel.jpg"}]},
        "viewerUrl": "https://sketchfab.com/models/wall_panel",
        "stats": {"viewCount": 3100, "likeCount": 190},
        "faceCount": 5600, "vertexCount": 3800, "isAnimated": False,
        "scale": "architectural", "style": "sci_fi",
        "environments": ["sci_fi_corridor"],
    },
    {
        "uid": "live_neon_sign",
        "name": "Neon Sign Holo Array",
        "categories": ["prop"],
        "tags": ["neon", "sci_fi", "sign", "futuristic", "light", "display"],
        "license": {"slug": "cc0"},
        "formats": ["fbx", "gltf", "usd"],
        "preview": {"images": [{"url": "https://preview.sketchfab.com/neon_sign.jpg"}]},
        "viewerUrl": "https://sketchfab.com/models/neon_sign",
        "stats": {"viewCount": 5200, "likeCount": 380},
        "faceCount": 2100, "vertexCount": 1400, "isAnimated": False,
        "scale": "architectural", "style": "sci_fi",
        "environments": ["sci_fi_corridor"],
    },
    # --- Robotics Lab ---
    {
        "uid": "live_robot_arm",
        "name": "Industrial Robot Arm 6-DOF",
        "categories": ["robot", "machinery"],
        "tags": ["robot", "arm", "mechanical", "industrial", "automated", "6dof"],
        "license": {"slug": "by"},
        "formats": ["fbx", "obj", "gltf"],
        "preview": {"images": [{"url": "https://preview.sketchfab.com/robot_arm.jpg"}]},
        "viewerUrl": "https://sketchfab.com/models/robot_arm",
        "stats": {"viewCount": 8900, "likeCount": 710},
        "faceCount": 32000, "vertexCount": 21000, "isAnimated": True,
        "scale": "architectural", "style": "photorealistic",
        "environments": ["robotics_lab"],
    },
    {
        "uid": "live_lab_workbench",
        "name": "Laboratory Workbench",
        "categories": ["furniture", "prop"],
        "tags": ["lab", "workbench", "table", "equipment", "laboratory", "clean"],
        "license": {"slug": "cc0"},
        "formats": ["fbx", "obj", "gltf"],
        "preview": {"images": [{"url": "https://preview.sketchfab.com/workbench.jpg"}]},
        "viewerUrl": "https://sketchfab.com/models/workbench",
        "stats": {"viewCount": 1800, "likeCount": 95},
        "faceCount": 4800, "vertexCount": 3200, "isAnimated": False,
        "scale": "architectural", "style": "photorealistic",
        "environments": ["robotics_lab"],
    },
    {
        "uid": "live_sensor_array",
        "name": "Sensor Array Unit",
        "categories": ["electronic", "prop"],
        "tags": ["sensor", "electronic", "laboratory", "equipment", "device"],
        "license": {"slug": "by"},
        "formats": ["fbx", "gltf"],
        "preview": {"images": [{"url": "https://preview.sketchfab.com/sensor.jpg"}]},
        "viewerUrl": "https://sketchfab.com/models/sensor",
        "stats": {"viewCount": 2200, "likeCount": 110},
        "faceCount": 6200, "vertexCount": 4100, "isAnimated": False,
        "scale": "human", "style": "photorealistic",
        "environments": ["robotics_lab"],
    },
    # --- Control Room ---
    {
        "uid": "live_control_console",
        "name": "Cinematic Control Console",
        "categories": ["prop", "electronic"],
        "tags": ["console", "control", "panel", "screen", "monitor", "tactical"],
        "license": {"slug": "by"},
        "formats": ["fbx", "obj", "gltf", "usd"],
        "preview": {"images": [{"url": "https://preview.sketchfab.com/console.jpg"}]},
        "viewerUrl": "https://sketchfab.com/models/console",
        "stats": {"viewCount": 6800, "likeCount": 490},
        "faceCount": 14200, "vertexCount": 9600, "isAnimated": False,
        "scale": "architectural", "style": "photorealistic",
        "environments": ["control_room"],
    },
    {
        "uid": "live_server_rack",
        "name": "Server Rack Unit",
        "categories": ["electronic", "prop"],
        "tags": ["server", "rack", "data", "electronic", "blinking", "led"],
        "license": {"slug": "cc0"},
        "formats": ["fbx", "obj", "gltf"],
        "preview": {"images": [{"url": "https://preview.sketchfab.com/server.jpg"}]},
        "viewerUrl": "https://sketchfab.com/models/server",
        "stats": {"viewCount": 4100, "likeCount": 240},
        "faceCount": 8400, "vertexCount": 5700, "isAnimated": False,
        "scale": "architectural", "style": "photorealistic",
        "environments": ["control_room"],
    },
    # --- Abandoned / Decay ---
    {
        "uid": "live_abandoned_vehicle",
        "name": "Abandoned Industrial Truck",
        "categories": ["vehicle"],
        "tags": ["vehicle", "truck", "abandoned", "rusted", "industrial"],
        "license": {"slug": "by"},
        "formats": ["fbx", "obj"],
        "preview": {"images": [{"url": "https://preview.sketchfab.com/truck.jpg"}]},
        "viewerUrl": "https://sketchfab.com/models/truck",
        "stats": {"viewCount": 5400, "likeCount": 280},
        "faceCount": 22000, "vertexCount": 15000, "isAnimated": False,
        "scale": "vehicle", "style": "photorealistic",
        "environments": ["abandoned_factory"],
    },
    {
        "uid": "live_debris_pile",
        "name": "Industrial Debris Pile",
        "categories": ["prop", "structure"],
        "tags": ["debris", "rubble", "industrial", "destroyed", "concrete", "metal"],
        "license": {"slug": "cc0"},
        "formats": ["fbx", "obj", "gltf"],
        "preview": {"images": [{"url": "https://preview.sketchfab.com/debris.jpg"}]},
        "viewerUrl": "https://sketchfab.com/models/debris",
        "stats": {"viewCount": 3700, "likeCount": 195},
        "faceCount": 9800, "vertexCount": 6700, "isAnimated": False,
        "scale": "human", "style": "photorealistic",
        "environments": ["abandoned_factory"],
    },
    {
        "uid": "live_cracked_floor",
        "name": "Cracked Concrete Floor Section",
        "categories": ["structure", "terrain"],
        "tags": ["floor", "concrete", "cracked", "decay", "industrial", "ground"],
        "license": {"slug": "cc0"},
        "formats": ["fbx", "obj", "gltf"],
        "preview": {"images": [{"url": "https://preview.sketchfab.com/cracked_floor.jpg"}]},
        "viewerUrl": "https://sketchfab.com/models/cracked_floor",
        "stats": {"viewCount": 2900, "likeCount": 155},
        "faceCount": 7200, "vertexCount": 5100, "isAnimated": False,
        "scale": "architectural", "style": "photorealistic",
        "environments": ["abandoned_factory", "industrial_hangar"],
    },
    # --- Generic / Multi-env ---
    {
        "uid": "live_barrel_cluster",
        "name": "Industrial Barrel Cluster",
        "categories": ["prop"],
        "tags": ["barrel", "drum", "industrial", "storage", "metal", "cluster"],
        "license": {"slug": "cc0"},
        "formats": ["fbx", "obj", "gltf"],
        "preview": {"images": [{"url": "https://preview.sketchfab.com/barrel.jpg"}]},
        "viewerUrl": "https://sketchfab.com/models/barrel",
        "stats": {"viewCount": 6300, "likeCount": 410},
        "faceCount": 5400, "vertexCount": 3700, "isAnimated": False,
        "scale": "human", "style": "photorealistic",
        "environments": ["industrial_hangar", "abandoned_factory"],
    },
    {
        "uid": "live_scaffolding",
        "name": "Industrial Scaffolding Section",
        "categories": ["structure"],
        "tags": ["scaffolding", "structure", "industrial", "metal", "construction"],
        "license": {"slug": "by"},
        "formats": ["fbx", "obj"],
        "preview": {"images": [{"url": "https://preview.sketchfab.com/scaffolding.jpg"}]},
        "viewerUrl": "https://sketchfab.com/models/scaffolding",
        "stats": {"viewCount": 3600, "likeCount": 175},
        "faceCount": 11000, "vertexCount": 7800, "isAnimated": False,
        "scale": "architectural", "style": "photorealistic",
        "environments": ["industrial_hangar"],
    },
    {
        "uid": "live_drone_unit",
        "name": "Autonomous Scout Drone",
        "categories": ["vehicle", "robot"],
        "tags": ["drone", "uav", "robot", "flying", "sci_fi", "scout", "autonomous"],
        "license": {"slug": "cc0"},
        "formats": ["fbx", "gltf", "usd"],
        "preview": {"images": [{"url": "https://preview.sketchfab.com/drone.jpg"}]},
        "viewerUrl": "https://sketchfab.com/models/drone",
        "stats": {"viewCount": 11200, "likeCount": 820},
        "faceCount": 18500, "vertexCount": 12300, "isAnimated": True,
        "scale": "small", "style": "sci_fi",
        "environments": ["robotics_lab", "sci_fi_corridor"],
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


class SketchfabLiveProvider(AssetProvider):
    """
    Extended simulated Sketchfab provider with pagination and richer seed data.
    No real HTTP calls — uses curated seed data.
    """

    @property
    def provider_name(self) -> str:
        return "sketchfab_live"

    @property
    def supported_categories(self) -> List[str]:
        return [
            "vehicle", "character", "prop", "machinery", "electronic",
            "structure", "robot", "weapon", "creature", "furniture",
            "architectural", "terrain", "other",
        ]

    @property
    def is_available(self) -> bool:
        return True  # Always available — seed data only

    def search(
        self,
        category: str,
        tags: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None,
        style_hints: Optional[List[str]] = None,
        limit: int = 20,
        page: int = 1,
        page_size: int = 20,
        **kwargs: Any,
    ) -> AssetProviderResult:
        """
        Search seed data with optional pagination.

        Args:
            page:      1-based page number (default 1).
            page_size: Results per page (default 20).
        """
        t0 = time.perf_counter()
        try:
            all_matched = self._filter_seed(
                category, tags or [], keywords or [], style_hints or []
            )
            # Pagination
            start = (page - 1) * page_size
            end = start + min(limit, page_size)
            paged = all_matched[start:end]
            normalized = [self.normalize_result(r) for r in paged]
            return AssetProviderResult(
                provider=self.provider_name,
                query_params={
                    "category": category,
                    "tags": tags or [],
                    "keywords": keywords or [],
                    "limit": limit,
                    "page": page,
                    "page_size": page_size,
                },
                raw_data=paged,
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
        """Alias for normalize_result for ABC compliance."""
        return self.normalize_result(raw)

    def normalize_result(self, raw: Dict[str, Any]) -> AssetDescriptor:
        """Convert a seed record to an AssetDescriptor."""
        cats = list(raw.get("categories", ["other"]))
        primary_cat = cats[0] if cats else "other"
        tags = list(raw.get("tags", []))
        envs = list(raw.get("environments", []))
        stats = raw.get("stats", {})
        preview_imgs = raw.get("preview", {}).get("images", [])
        preview_url = preview_imgs[0].get("url", "") if preview_imgs else ""
        licence_slug = raw.get("license", {}).get("slug", "unknown")
        asset_id = f"skfbl_{raw.get('uid', '')}"
        return AssetDescriptor(
            asset_id=asset_id,
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
                asset_id=asset_id,
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

    def lookup(self, asset_id: str) -> Optional[AssetDescriptor]:
        """Look up a specific asset by its normalized asset_id."""
        for rec in _SEED:
            # asset_id format: skfbl_live_{uid_part}
            expected_id = f"skfbl_{rec['uid']}"
            if expected_id == asset_id:
                return self.normalize_result(rec)
        return None

    def get_preview(self, asset_id: str) -> Optional[AssetPreview]:
        """Return preview for a given asset_id."""
        asset = self.lookup(asset_id)
        if asset:
            return asset.preview
        return None

    def get_metadata(self, asset_id: str) -> Optional[AssetMetadata]:
        """Return metadata for a given asset_id."""
        asset = self.lookup(asset_id)
        if asset:
            return asset.metadata
        return None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _filter_seed(
        self,
        category: str,
        tags: List[str],
        keywords: List[str],
        style_hints: List[str],
    ) -> List[Dict[str, Any]]:
        query_terms = {t.lower() for t in tags + keywords}
        style_set = {s.lower() for s in style_hints}
        results = []
        for rec in _SEED:
            cats = [c.lower() for c in rec.get("categories", [])]
            rec_tags = {t.lower() for t in rec.get("tags", [])}
            # Category filter
            cat_match = not category or category.lower() in cats
            # Tag filter
            tag_match = not query_terms or bool(query_terms & rec_tags)
            # Style hint filter (optional — only applied when style_hints provided)
            style_match = not style_set or rec.get("style", "").lower() in style_set
            if cat_match and tag_match and style_match:
                results.append(rec)
        # Deterministic: sort by name
        return sorted(results, key=lambda r: r.get("name", ""))
