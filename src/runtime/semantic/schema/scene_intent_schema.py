"""
Scene Intent Schema (Tier 2.9 / Phase 1)
==========================================
Canonical typed representation of a user's scene intent, extracted from
natural language by the SceneIntentExtractor pipeline.

This is the contract that every layer downstream receives:
  - Validators check it for correctness
  - Enrichers extend it with inferred requirements
  - Serializers persist and replay it
  - Future orchestration nodes consume it to plan Houdini operations

Design rules:
  1. All fields are Optional with sensible defaults — extraction is partial by design.
  2. Enum values are lowercase strings — easy to compare, easy to serialize.
  3. No Houdini-specific types at this layer — pure semantic description.
  4. Structured output only — no free-form text blobs stored in fields.
  5. Schema is versioned — consumers must check SCHEMA_VERSION.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Schema version
# ---------------------------------------------------------------------------

SCHEMA_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Allowed enum values (constants — single source of truth)
# ---------------------------------------------------------------------------

ENVIRONMENT_TYPES = frozenset({
    "urban", "industrial", "desert", "forest", "ocean", "mountain",
    "arctic", "space", "underground", "interior", "abstract",
})

STYLE_TYPES = frozenset({
    "photorealistic", "cinematic", "stylized", "abstract",
    "noir", "sci_fi", "fantasy", "documentary",
})

MOOD_TYPES = frozenset({
    "dramatic", "tense", "peaceful", "chaotic", "melancholic",
    "triumphant", "ominous", "neutral",
})

TIME_OF_DAY_VALUES = frozenset({
    "dawn", "morning", "noon", "afternoon", "dusk",
    "evening", "night", "overcast", "unknown",
})

WEATHER_TYPES = frozenset({
    "clear", "cloudy", "rain", "storm", "fog", "snow",
    "dust", "smoke", "haze", "unknown",
})

SCALE_VALUES = frozenset({
    "microscopic", "human", "architectural", "urban", "landscape",
    "planetary",
})

DENSITY_LEVELS = frozenset({"sparse", "moderate", "dense", "extreme"})

DESTRUCTION_LEVELS = frozenset({
    "none", "light", "moderate", "heavy", "catastrophic",
})

CINEMATIC_STYLE_VALUES = frozenset({
    "action", "thriller", "drama", "horror", "documentary",
    "commercial", "music_video", "vfx_showcase",
})

LIGHTING_STYLE_VALUES = frozenset({
    "natural", "practical", "three_point", "hdri",
    "volumetric", "practical_fire", "night", "golden_hour",
    "overcast_diffuse",
})

ZONE_TYPES = frozenset({
    "center", "foreground", "midground", "background",
    "periphery", "overhead", "underground",
})

ATMOSPHERIC_EFFECT_TYPES = frozenset({
    "smoke", "dust", "haze", "fog", "rain", "sparks",
    "embers", "steam", "mist", "debris_particles",
})

ASSET_PROVIDER_VALUES = frozenset({
    "polyhaven", "sketchfab", "quixel", "local", "procedural", "unknown",
})

# ---------------------------------------------------------------------------
# Supporting structures
# ---------------------------------------------------------------------------

@dataclass
class AssetRequirement:
    """A single asset type required for the scene.

    Attributes:
        asset_type:   Semantic category ("vegetation", "vehicle", "structure", ...).
        description:  Optional natural language description of the asset.
        quantity:     Approximate number of instances needed (None = unspecified).
        style_hints:  Style descriptors that should filter provider results.
        required:     True if missing this asset invalidates the scene.
        provider:     Preferred asset provider, or "unknown" if any will do.
    """
    asset_type:   str
    description:  Optional[str]  = None
    quantity:     Optional[int]  = None
    style_hints:  List[str]      = field(default_factory=list)
    required:     bool           = False
    provider:     str            = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_type":  self.asset_type,
            "description": self.description,
            "quantity":    self.quantity,
            "style_hints": list(self.style_hints),
            "required":    self.required,
            "provider":    self.provider,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AssetRequirement":
        return cls(
            asset_type=d.get("asset_type", "unknown"),
            description=d.get("description"),
            quantity=d.get("quantity"),
            style_hints=list(d.get("style_hints") or []),
            required=bool(d.get("required", False)),
            provider=d.get("provider", "unknown"),
        )


@dataclass
class SceneZone:
    """A spatial zone in the scene with its own intent description.

    Attributes:
        zone_type:     Where in the scene this zone is ("center", "background", ...).
        description:   Natural language description of this zone's content.
        assets:        Asset requirements specific to this zone.
        fx_types:      FX types present in this zone ("pyro", "rbd", "flip").
        priority:      Render/simulation priority 1–10 (10 = highest).
    """
    zone_type:   str
    description: Optional[str]        = None
    assets:      List[AssetRequirement] = field(default_factory=list)
    fx_types:    List[str]            = field(default_factory=list)
    priority:    int                  = 5

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_type":   self.zone_type,
            "description": self.description,
            "assets":      [a.to_dict() for a in self.assets],
            "fx_types":    list(self.fx_types),
            "priority":    self.priority,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SceneZone":
        return cls(
            zone_type=d.get("zone_type", "center"),
            description=d.get("description"),
            assets=[AssetRequirement.from_dict(a) for a in (d.get("assets") or [])],
            fx_types=list(d.get("fx_types") or []),
            priority=int(d.get("priority", 5)),
        )


# ---------------------------------------------------------------------------
# Primary schema
# ---------------------------------------------------------------------------

@dataclass
class SceneIntent:
    """Canonical structured representation of a user's scene intent.

    All fields are Optional — the extraction pipeline fills what it can from
    the user's prompt. Downstream validators check completeness; enrichers
    fill in implied fields before the intent reaches orchestration nodes.

    Attributes:
        intent_id:          Unique identifier for this intent instance.
        schema_version:     Version string — consumers should check this.
        source_prompt:      The original user prompt (preserved verbatim).
        extracted_at:       Unix timestamp of extraction.

        environment:        Scene environment type.
        style:              Overall visual style.
        mood:               Emotional tone.
        time_of_day:        Lighting time of day.
        weather:            Weather/atmospheric conditions.
        scale:              Spatial scale of the scene.
        density:            Population/asset density.
        destruction_level:  Level of destruction present.
        cinematic_style:    Genre/use-case for the shot.
        lighting_style:     Lighting approach.

        asset_requirements: List of asset types needed.
        zones:              List of spatial zones with per-zone intent.
        atmospheric_effects: Active atmospheric effects.
        keywords:           Raw keyword list extracted from the prompt.

        confidence:         Overall extraction confidence 0.0–1.0.
        extraction_notes:   Human-readable notes about the extraction.
        llm_enhanced:       True if an LLM provider contributed to extraction.
        validation_errors:  Populated by SceneIntentValidator after validation.
        enrichment_applied: True if SceneIntentEnricher has run.
    """

    # Identity
    intent_id:         str            = field(default_factory=lambda: str(uuid.uuid4()))
    schema_version:    str            = SCHEMA_VERSION
    source_prompt:     str            = ""
    extracted_at:      float          = field(default_factory=time.time)

    # Primary descriptors
    environment:       Optional[str]  = None
    style:             Optional[str]  = None
    mood:              Optional[str]  = None
    time_of_day:       Optional[str]  = None
    weather:           Optional[str]  = None
    scale:             Optional[str]  = None
    density:           Optional[str]  = None
    destruction_level: Optional[str]  = None
    cinematic_style:   Optional[str]  = None
    lighting_style:    Optional[str]  = None

    # Structured requirements
    asset_requirements:  List[AssetRequirement] = field(default_factory=list)
    zones:               List[SceneZone]        = field(default_factory=list)
    atmospheric_effects: List[str]              = field(default_factory=list)
    keywords:            List[str]              = field(default_factory=list)

    # Metadata
    confidence:          float      = 0.0
    extraction_notes:    List[str]  = field(default_factory=list)
    llm_enhanced:        bool       = False
    validation_errors:   List[str]  = field(default_factory=list)
    enrichment_applied:  bool       = False

    # ---------------------------------------------------------------------------
    # Convenience properties
    # ---------------------------------------------------------------------------

    @property
    def is_valid(self) -> bool:
        """True when the validator has run and found no errors."""
        return len(self.validation_errors) == 0 and self.confidence > 0.0

    @property
    def has_fx(self) -> bool:
        """True if any zone declares FX types, or keywords suggest FX."""
        if any(z.fx_types for z in self.zones):
            return True
        fx_words = {"pyro", "smoke", "explosion", "fire", "rbd", "flip", "fluid",
                    "dust", "debris", "vellum", "cloth", "particles"}
        return bool(fx_words & {k.lower() for k in self.keywords})

    @property
    def primary_fx_types(self) -> List[str]:
        """Deduplicated list of FX types from all zones."""
        types: list = []
        for z in self.zones:
            for fx in z.fx_types:
                if fx not in types:
                    types.append(fx)
        return types

    # ---------------------------------------------------------------------------
    # Serialization
    # ---------------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a JSON-serializable dict."""
        return {
            "intent_id":          self.intent_id,
            "schema_version":     self.schema_version,
            "source_prompt":      self.source_prompt,
            "extracted_at":       self.extracted_at,
            "environment":        self.environment,
            "style":              self.style,
            "mood":               self.mood,
            "time_of_day":        self.time_of_day,
            "weather":            self.weather,
            "scale":              self.scale,
            "density":            self.density,
            "destruction_level":  self.destruction_level,
            "cinematic_style":    self.cinematic_style,
            "lighting_style":     self.lighting_style,
            "asset_requirements": [a.to_dict() for a in self.asset_requirements],
            "zones":              [z.to_dict() for z in self.zones],
            "atmospheric_effects":list(self.atmospheric_effects),
            "keywords":           list(self.keywords),
            "confidence":         self.confidence,
            "extraction_notes":   list(self.extraction_notes),
            "llm_enhanced":       self.llm_enhanced,
            "validation_errors":  list(self.validation_errors),
            "enrichment_applied": self.enrichment_applied,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SceneIntent":
        """Reconstruct a SceneIntent from a previously serialized dict."""
        return cls(
            intent_id=d.get("intent_id", str(uuid.uuid4())),
            schema_version=d.get("schema_version", SCHEMA_VERSION),
            source_prompt=d.get("source_prompt", ""),
            extracted_at=float(d.get("extracted_at", time.time())),
            environment=d.get("environment"),
            style=d.get("style"),
            mood=d.get("mood"),
            time_of_day=d.get("time_of_day"),
            weather=d.get("weather"),
            scale=d.get("scale"),
            density=d.get("density"),
            destruction_level=d.get("destruction_level"),
            cinematic_style=d.get("cinematic_style"),
            lighting_style=d.get("lighting_style"),
            asset_requirements=[AssetRequirement.from_dict(a)
                                 for a in (d.get("asset_requirements") or [])],
            zones=[SceneZone.from_dict(z) for z in (d.get("zones") or [])],
            atmospheric_effects=list(d.get("atmospheric_effects") or []),
            keywords=list(d.get("keywords") or []),
            confidence=float(d.get("confidence", 0.0)),
            extraction_notes=list(d.get("extraction_notes") or []),
            llm_enhanced=bool(d.get("llm_enhanced", False)),
            validation_errors=list(d.get("validation_errors") or []),
            enrichment_applied=bool(d.get("enrichment_applied", False)),
        )

    def __repr__(self) -> str:
        env = self.environment or "?"
        style = self.style or "?"
        return (
            f"SceneIntent(id={self.intent_id[:8]}, env={env}, style={style}, "
            f"confidence={self.confidence:.2f}, valid={self.is_valid})"
        )
