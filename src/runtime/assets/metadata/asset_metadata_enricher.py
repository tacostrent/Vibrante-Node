"""
Asset Metadata Enricher (Tier 12 — Asset Ecosystem Expansion)
==============================================================
Expands asset metadata using deterministic rules.
No LLM calls.  No bridge calls.  Pure keyword matching.

Public API:
    AssetMetadataEnricher           — class
    get_asset_metadata_enricher()   — singleton
    reset_asset_metadata_enricher_for_tests()
"""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional

from src.runtime.assets.schema import AssetDescriptor

# ---------------------------------------------------------------------------
# Keyword tables (deterministic, single source of truth)
# ---------------------------------------------------------------------------

_ENVIRONMENT_KEYWORDS: Dict[str, List[str]] = {
    "industrial_hangar": [
        "pipe", "barrel", "forklift", "crane", "crate", "pallet", "tank",
        "duct", "scaffolding", "hangar", "industrial", "factory", "machinery",
        "conveyor", "drill", "compressor", "gauge", "valve", "flange",
    ],
    "control_room": [
        "screen", "terminal", "console", "monitor", "panel", "control",
        "desk", "server", "rack", "display", "button", "tactical", "keyboard",
    ],
    "robotics_lab": [
        "robot", "arm", "mechanical", "electronic", "circuit", "lab",
        "equipment", "drone", "sensor", "servo", "encoder", "automated",
    ],
    "sci_fi_corridor": [
        "corridor", "hallway", "door", "hatch", "sci-fi", "scifi",
        "neon", "futuristic", "modular", "airlock", "bulkhead",
    ],
    "abandoned_factory": [
        "rusted", "broken", "debris", "rubble", "decay", "abandoned",
        "collapsed", "worn", "graffiti", "overgrown", "shattered",
    ],
}

_STYLE_KEYWORDS: Dict[str, List[str]] = {
    "weathered": [
        "rusted", "worn", "aged", "dirty", "weathered", "corroded",
        "damaged", "old", "decayed", "tarnished", "oxidized",
    ],
    "clean": [
        "clean", "pristine", "new", "modern", "polished", "smooth",
        "shiny", "glossy", "fresh", "spotless",
    ],
    "industrial": [
        "industrial", "heavy", "metal", "steel", "iron", "mechanical",
        "factory", "warehouse", "utility",
    ],
    "sci_fi": [
        "sci-fi", "scifi", "futuristic", "space", "neon", "holographic",
        "cyberpunk", "alien", "advanced",
    ],
}

_USAGE_KEYWORDS: Dict[str, List[str]] = {
    "hero_vehicle": ["forklift", "truck", "vehicle", "crane", "excavator"],
    "mid_ground":   ["barrel", "crate", "pallet", "container", "box"],
    "wall_detail":  ["pipe", "duct", "conduit", "cable", "wire"],
    "ceiling_detail": ["vent", "duct", "sprinkler", "light_fixture", "beam"],
    "floor_prop":   ["debris", "rubble", "scatter", "ground", "floor"],
    "hero_machine": ["robot", "arm", "automated", "industrial", "machinery"],
    "atmosphere":   ["fog", "smoke", "particle", "cloud", "mist"],
    "backdrop":     ["wall", "panel", "structure", "scaffold", "pillar"],
}


class AssetMetadataEnricher:
    """
    Enriches AssetDescriptor metadata using deterministic keyword rules.

    All enrichments are rule-based — no LLM, no ML, no randomness.
    """

    def __init__(self) -> None:
        self._lock:          threading.Lock = threading.Lock()
        self._enriched_count: int = 0

    def enrich_asset(self, asset: AssetDescriptor) -> AssetDescriptor:
        """
        Enrich asset metadata in-place and return the asset.

        Mutates: environment_suitability, style, and adds inferred tags.
        """
        # Infer environments
        envs = self.infer_environments(asset)
        for env in envs:
            if env not in asset.environment_suitability:
                asset.environment_suitability.append(env)

        # Infer style (only if not already set)
        if not asset.style or asset.style in ("unknown", ""):
            style = self.infer_style(asset)
            if style:
                asset.style = style

        # Infer categories for tags
        inferred_cats = self.infer_categories(asset)
        for cat in inferred_cats:
            cat_tag = f"env:{cat}"
            if cat_tag not in asset.tags:
                asset.tags.append(cat_tag)

        with self._lock:
            self._enriched_count += 1

        return asset

    def infer_environments(self, asset: AssetDescriptor) -> List[str]:
        """
        Infer suitable environments from asset tags and name.

        Returns a list of environment names that match keyword patterns.
        """
        all_terms = self._get_all_terms(asset)
        matched: List[str] = []
        for env, keywords in _ENVIRONMENT_KEYWORDS.items():
            if any(kw.lower() in all_terms for kw in keywords):
                if env not in matched:
                    matched.append(env)
        return sorted(matched)

    def infer_style(self, asset: AssetDescriptor) -> Optional[str]:
        """
        Infer asset style from tags and name.

        Returns a style string or None.
        """
        all_terms = self._get_all_terms(asset)
        for style, keywords in _STYLE_KEYWORDS.items():
            if any(kw.lower() in all_terms for kw in keywords):
                return style
        return None

    def infer_categories(self, asset: AssetDescriptor) -> List[str]:
        """
        Cross-check tags against ASSET_CATEGORIES and infer additional ones.
        """
        from src.runtime.assets.schema import ASSET_CATEGORIES
        all_terms = self._get_all_terms(asset)
        inferred = []
        for cat in ASSET_CATEGORIES:
            if cat.lower() in all_terms and cat not in inferred:
                inferred.append(cat)
        return sorted(inferred)

    def infer_usage(self, asset: AssetDescriptor) -> List[str]:
        """
        Infer usage hints from asset name and tags.

        Returns a list of usage context strings.
        """
        all_terms = self._get_all_terms(asset)
        hints: List[str] = []
        for usage, keywords in _USAGE_KEYWORDS.items():
            if any(kw.lower() in all_terms for kw in keywords):
                if usage not in hints:
                    hints.append(usage)
        return sorted(hints)

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            return {"enriched_count": self._enriched_count}

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _get_all_terms(self, asset: AssetDescriptor) -> set:
        """Collect all searchable terms from an asset."""
        terms = set()
        terms.add(asset.name.lower())
        for t in asset.tags + asset.keywords:
            terms.add(t.lower())
        # Also split name by common separators
        import re
        for part in re.split(r"[\s_\-]+", asset.name.lower()):
            terms.add(part)
        return terms


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_ENRICHER: Optional[AssetMetadataEnricher] = None
_ENRICHER_LOCK = threading.Lock()


def get_asset_metadata_enricher() -> AssetMetadataEnricher:
    """Return the module-level singleton AssetMetadataEnricher."""
    global _ENRICHER
    if _ENRICHER is None:
        with _ENRICHER_LOCK:
            if _ENRICHER is None:
                _ENRICHER = AssetMetadataEnricher()
    return _ENRICHER


def reset_asset_metadata_enricher_for_tests() -> None:
    """Replace the singleton.  For test isolation only."""
    global _ENRICHER
    with _ENRICHER_LOCK:
        _ENRICHER = None
