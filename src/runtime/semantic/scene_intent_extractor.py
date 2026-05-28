"""
Scene Intent Extractor (Phase 1)
====================================
Orchestrates the full extraction pipeline:
  1. Build a structured LLM prompt (IntentPromptBuilder)
  2. Call the LLM provider (LLMProvider.enhance_intent)
  3. Parse and validate the LLM's JSON response into a SceneIntent
  4. Fall back to deterministic keyword extraction if LLM is unavailable
  5. Validate the result (SceneIntentValidator)
  6. Enrich with implied requirements (SceneIntentEnricher)
  7. Log the pipeline trace (SemanticLogger)

Output:
  Always returns a SceneIntent with a structured ExtractionResult wrapper.
  Never returns free-form text.
  Never raises on LLM failure — falls through to deterministic extraction.

Architecture:
  The extractor is the single entry point for the node layer.
  The Vibrante node (`scene_intent_extractor`) calls
  `get_scene_intent_extractor().extract(prompt)` and forwards the
  structured result to downstream nodes.

Design rules:
  1. LLM is optional — deterministic extraction works without it.
  2. All LLM output is schema-validated before use.
  3. Unknown LLM fields are silently discarded.
  4. Pipeline never raises — errors are captured in ExtractionResult.
  5. Thread-safe (uses async; no shared mutable state per call).
"""

from __future__ import annotations

import json
import re
import time
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .schema.scene_intent_schema import (
    ATMOSPHERIC_EFFECT_TYPES,
    DENSITY_LEVELS,
    DESTRUCTION_LEVELS,
    ENVIRONMENT_TYPES,
    LIGHTING_STYLE_VALUES,
    MOOD_TYPES,
    SCALE_VALUES,
    STYLE_TYPES,
    TIME_OF_DAY_VALUES,
    WEATHER_TYPES,
    SceneIntent,
)
from .prompts.intent_prompt_builder import get_intent_prompt_builder
from .validators.scene_intent_validator import get_scene_intent_validator
from .enrichers.scene_intent_enricher import get_scene_intent_enricher
from .logging.semantic_logger import get_semantic_logger


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class ExtractionResult:
    """Wraps a SceneIntent with extraction pipeline metadata.

    Attributes:
        intent:           The extracted and enriched SceneIntent.
        ok:               True if extraction succeeded with no blocking errors.
        extraction_time:  Seconds the extraction pipeline took.
        errors:           Blocking errors from validation.
        warnings:         Advisory issues.
        pipeline_stages:  Ordered list of stages that ran.
    """
    intent:           Optional[SceneIntent] = None
    ok:               bool                  = False
    extraction_time:  float                 = 0.0
    errors:           List[str]             = field(default_factory=list)
    warnings:         List[str]             = field(default_factory=list)
    pipeline_stages:  List[str]             = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok":              self.ok,
            "extraction_time": round(self.extraction_time, 3),
            "errors":          list(self.errors),
            "warnings":        list(self.warnings),
            "pipeline_stages": list(self.pipeline_stages),
            "intent":          self.intent.to_dict() if self.intent else None,
        }


# ---------------------------------------------------------------------------
# Deterministic keyword extractor (no LLM)
# ---------------------------------------------------------------------------

# Maps keywords in the prompt to (field, value) pairs for basic extraction.
_KEYWORD_MAP: List[tuple] = []

def _build_keyword_map() -> List[tuple]:
    """Build a flat list of (keyword, field, value) extraction rules."""
    rules = []
    # Environments
    for env in ENVIRONMENT_TYPES:
        rules.append((env, "environment", env))
    # Styles
    for s in STYLE_TYPES:
        rules.append((s.replace("_", " "), "style", s))
    # Moods
    for m in MOOD_TYPES:
        rules.append((m, "mood", m))
    # Time of day
    for t in TIME_OF_DAY_VALUES:
        rules.append((t.replace("_", " "), "time_of_day", t))
    # Weather
    for w in WEATHER_TYPES:
        rules.append((w, "weather", w))
    # Scale
    for sc in SCALE_VALUES:
        rules.append((sc, "scale", sc))
    # Density
    for d in DENSITY_LEVELS:
        rules.append((d, "density", d))
    # Destruction levels — map common synonyms
    extra_destruction = [
        ("destroyed",    "catastrophic"),
        ("explosion",    "heavy"),
        ("burning",      "moderate"),
        ("on fire",      "moderate"),
        ("collapsed",    "heavy"),
        ("rubble",       "heavy"),
        ("apocalypse",   "catastrophic"),
        ("apocalyptic",  "catastrophic"),
        ("bombed",       "heavy"),
        ("blast",        "heavy"),
    ]
    for keyword, val in extra_destruction:
        rules.append((keyword, "destruction_level", val))
    for d in DESTRUCTION_LEVELS:
        rules.append((d, "destruction_level", d))
    # Lighting
    for ls in LIGHTING_STYLE_VALUES:
        rules.append((ls.replace("_", " "), "lighting_style", ls))
    # Atmospheric effects
    for ae in ATMOSPHERIC_EFFECT_TYPES:
        rules.append((ae.replace("_", " "), "_atmospheric", ae))
    return rules

_KEYWORD_MAP = _build_keyword_map()


def _deterministic_extract(prompt: str) -> SceneIntent:
    """Extract a SceneIntent from a prompt using keyword matching only."""
    text = prompt.lower()
    intent = SceneIntent(source_prompt=prompt)
    intent.keywords = _extract_keywords(prompt)
    intent.extraction_notes.append("Extracted via deterministic keyword matching (no LLM)")

    fields_hit = 0
    atmospheric: List[str] = []

    for keyword, field_name, value in _KEYWORD_MAP:
        if keyword.lower() not in text:
            continue
        if field_name == "_atmospheric":
            if value not in atmospheric:
                atmospheric.append(value)
            continue
        current = getattr(intent, field_name, None)
        if current is None:
            setattr(intent, field_name, value)
            fields_hit += 1

    intent.atmospheric_effects = atmospheric
    # Confidence is proportional to how many fields were filled
    total_fields = 10  # environment, style, mood, etc.
    intent.confidence = min(0.85, fields_hit / total_fields) if fields_hit > 0 else 0.15
    return intent


def _extract_keywords(prompt: str) -> List[str]:
    """Extract meaningful words from the prompt (simple stopword filter)."""
    stopwords = frozenset({
        "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "shall", "can", "need", "dare", "that",
        "this", "it", "its", "i", "we", "you", "he", "she", "they",
    })
    words = re.findall(r"[a-zA-Z]+(?:'[a-zA-Z]+)?", prompt.lower())
    return [w for w in words if w not in stopwords and len(w) > 2]


def _parse_llm_json(raw: str) -> Optional[Dict[str, Any]]:
    """Parse the LLM's response, extracting JSON even if wrapped in text."""
    # Direct parse
    raw = raw.strip()
    try:
        d = json.loads(raw)
        if isinstance(d, dict):
            return d
    except json.JSONDecodeError:
        pass

    # Find first {...} block
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            d = json.loads(match.group())
            if isinstance(d, dict):
                return d
        except json.JSONDecodeError:
            pass

    return None


def _llm_dict_to_intent(d: Dict[str, Any], source_prompt: str) -> SceneIntent:
    """Convert a validated LLM response dict to a SceneIntent."""
    # Strip unsupported fields that aren't in SceneIntent
    allowed_scalar_fields = {
        "environment", "style", "mood", "time_of_day", "weather",
        "scale", "density", "destruction_level", "cinematic_style",
        "lighting_style", "confidence",
    }
    allowed_list_fields = {
        "atmospheric_effects", "keywords", "extraction_notes",
    }

    intent = SceneIntent(source_prompt=source_prompt)
    intent.llm_enhanced = True

    for f in allowed_scalar_fields:
        val = d.get(f)
        if val is not None:
            setattr(intent, f, val)

    for f in allowed_list_fields:
        val = d.get(f)
        if isinstance(val, list):
            setattr(intent, f, list(val))

    # Confidence
    conf = d.get("confidence", 0.0)
    if isinstance(conf, (int, float)):
        intent.confidence = max(0.0, min(1.0, float(conf)))

    # asset_requirements
    from .schema.scene_intent_schema import AssetRequirement
    for item in (d.get("asset_requirements") or []):
        if isinstance(item, dict) and item.get("asset_type"):
            intent.asset_requirements.append(AssetRequirement.from_dict(item))

    # zones
    from .schema.scene_intent_schema import SceneZone
    for item in (d.get("zones") or []):
        if isinstance(item, dict) and item.get("zone_type"):
            intent.zones.append(SceneZone.from_dict(item))

    # notes
    for note in (d.get("extraction_notes") or []):
        if isinstance(note, str) and note not in intent.extraction_notes:
            intent.extraction_notes.append(note)

    # Add keywords from prompt
    if not intent.keywords:
        intent.keywords = _extract_keywords(source_prompt)

    return intent


# ---------------------------------------------------------------------------
# Extractor
# ---------------------------------------------------------------------------

class SceneIntentExtractor:
    """Orchestrates the full scene intent extraction pipeline.

    Usage::

        extractor = SceneIntentExtractor()
        result = await extractor.extract("burning city at night with heavy smoke")
        if result.ok:
            intent = result.intent
            print(intent.to_dict())
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._extract_count = 0

    async def extract(
        self,
        prompt: str,
        extra_context: Optional[Dict[str, Any]] = None,
        skip_enrichment: bool = False,
    ) -> ExtractionResult:
        """Run the full extraction pipeline for a natural language prompt.

        Args:
            prompt:          Natural language scene description.
            extra_context:   Optional context dict (scene state, capabilities).
            skip_enrichment: If True, skip the enrichment phase.

        Returns:
            ExtractionResult with `ok=True` if extraction succeeded.
        """
        t0 = time.perf_counter()
        result = ExtractionResult()
        logger = get_semantic_logger()

        logger.log_extraction_start(prompt)

        # -- Phase 1: attempt LLM extraction ---------------------------------
        intent = await self._try_llm_extract(prompt, extra_context, result)

        # -- Phase 2: deterministic fallback if LLM unavailable or failed ----
        if intent is None:
            intent = _deterministic_extract(prompt)
            result.pipeline_stages.append("deterministic_extraction")
        else:
            result.pipeline_stages.append("llm_extraction")

        # -- Phase 3: validate -----------------------------------------------
        validator = get_scene_intent_validator()
        val_result = validator.validate(intent)
        result.pipeline_stages.append("validation")
        result.errors.extend(val_result.errors)
        result.warnings.extend(val_result.warnings)

        logger.log_validation_complete(
            intent.intent_id,
            valid=val_result.valid,
            error_count=len(val_result.errors),
            warning_count=len(val_result.warnings),
        )

        # -- Phase 4: enrich -------------------------------------------------
        if not skip_enrichment:
            notes_before = len(intent.extraction_notes)
            enricher = get_scene_intent_enricher()
            enricher.enrich(intent)
            result.pipeline_stages.append("enrichment")
            logger.log_enrichment_complete(
                intent.intent_id,
                rules_fired=len(intent.extraction_notes) - notes_before,
            )

        # -- Finalize --------------------------------------------------------
        result.intent = intent
        result.ok = val_result.valid and intent.confidence > 0.0
        result.extraction_time = time.perf_counter() - t0

        logger.log_extraction_complete(
            intent.intent_id,
            confidence=intent.confidence,
            fields_extracted=self._count_populated_fields(intent),
            llm_enhanced=intent.llm_enhanced,
        )

        with self._lock:
            self._extract_count += 1

        return result

    async def _try_llm_extract(
        self,
        prompt: str,
        extra_context: Optional[Dict[str, Any]],
        result: ExtractionResult,
    ) -> Optional[SceneIntent]:
        """Attempt LLM-based extraction; return None if unavailable or failed."""
        try:
            from src.runtime.llm_provider import get_llm_provider
            provider = get_llm_provider()
            if not provider.is_available:
                result.pipeline_stages.append("llm_skipped")
                return None

            # Build the extraction prompt
            builder = get_intent_prompt_builder()
            _system_msg, user_msg = builder.build(prompt, extra_context)

            # Call the provider — use enhance_intent with the full user message as prompt
            response = await provider.enhance_intent(user_msg, context=extra_context or {})

            if not response.get("enhanced", False):
                result.pipeline_stages.append("llm_skipped")
                return None

            # The provider may return an "intent" field (op id) or raw "parameters"
            # For scene intent, we expect the parameters to contain the JSON fields.
            raw_json = response.get("parameters", {})
            if isinstance(raw_json, dict) and raw_json:
                intent = _llm_dict_to_intent(raw_json, prompt)
                return intent

            # Fallback: try to parse the reasoning field as JSON
            for field_candidate in ("intent", "reasoning"):
                candidate = response.get(field_candidate, "")
                if isinstance(candidate, str) and "{" in candidate:
                    parsed = _parse_llm_json(candidate)
                    if parsed:
                        return _llm_dict_to_intent(parsed, prompt)

        except Exception as exc:
            get_semantic_logger().log_extraction_error(str(exc))
            result.warnings.append(f"LLM extraction failed: {exc}; using deterministic fallback")

        return None

    @staticmethod
    def _count_populated_fields(intent: SceneIntent) -> int:
        scalar_fields = [
            intent.environment, intent.style, intent.mood, intent.time_of_day,
            intent.weather, intent.scale, intent.density, intent.destruction_level,
            intent.cinematic_style, intent.lighting_style,
        ]
        count = sum(1 for f in scalar_fields if f is not None)
        if intent.atmospheric_effects:
            count += 1
        if intent.asset_requirements:
            count += 1
        if intent.zones:
            count += 1
        return count

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {"extract_count": self._extract_count}


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_extractor: Optional[SceneIntentExtractor] = None
_extractor_lock = threading.Lock()


def get_scene_intent_extractor() -> SceneIntentExtractor:
    """Return the shared SceneIntentExtractor instance."""
    global _extractor
    with _extractor_lock:
        if _extractor is None:
            _extractor = SceneIntentExtractor()
    return _extractor


def reset_scene_intent_extractor_for_tests() -> None:
    """Reset shared instance for test isolation."""
    global _extractor
    with _extractor_lock:
        _extractor = None
