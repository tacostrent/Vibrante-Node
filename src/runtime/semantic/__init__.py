"""
Semantic Scene Intent Pipeline (Phase 1)
==========================================
Provides the full NL → structured intent extraction pipeline:

  User Prompt
      → IntentPromptBuilder   (structured LLM prompts)
      → LLMProvider           (optional AI enhancement)
      → SceneIntentExtractor  (orchestration + fallback)
      → SceneIntentValidator  (enum/range/contradiction checks)
      → SceneIntentEnricher   (inferred requirements)
      → SceneIntent           (canonical typed output)
      → IntentSerializer      (JSON persistence)
      → SemanticLogger        (pipeline trace)

Design rules:
  - LLM is optional — all extraction also works without an LLM.
  - Structured output only — no free-form text in SceneIntent fields.
  - Provider-agnostic — any LLMProvider implementation works.
  - Deterministic — same input always produces same output without LLM.
"""

from .schema import (
    SCHEMA_VERSION,
    AssetRequirement,
    SceneZone,
    SceneIntent,
)
from .scene_intent_extractor import (
    ExtractionResult,
    SceneIntentExtractor,
    get_scene_intent_extractor,
    reset_scene_intent_extractor_for_tests,
)
from .validators import (
    ValidationResult,
    SceneIntentValidator,
    get_scene_intent_validator,
    reset_scene_intent_validator_for_tests,
)
from .enrichers import (
    SceneIntentEnricher,
    get_scene_intent_enricher,
    reset_scene_intent_enricher_for_tests,
)
from .serialization import (
    SchemaVersionError,
    IntentSerializationError,
    IntentSerializer,
    get_intent_serializer,
    reset_intent_serializer_for_tests,
)
from .logging import (
    SemanticLogEntry,
    SemanticLogger,
    get_semantic_logger,
    reset_semantic_logger_for_tests,
)
from .prompts import (
    IntentPromptBuilder,
    get_intent_prompt_builder,
    reset_intent_prompt_builder_for_tests,
)

__all__ = [
    # Schema
    "SCHEMA_VERSION",
    "AssetRequirement",
    "SceneZone",
    "SceneIntent",
    # Extractor
    "ExtractionResult",
    "SceneIntentExtractor",
    "get_scene_intent_extractor",
    "reset_scene_intent_extractor_for_tests",
    # Validator
    "ValidationResult",
    "SceneIntentValidator",
    "get_scene_intent_validator",
    "reset_scene_intent_validator_for_tests",
    # Enricher
    "SceneIntentEnricher",
    "get_scene_intent_enricher",
    "reset_scene_intent_enricher_for_tests",
    # Serializer
    "SchemaVersionError",
    "IntentSerializationError",
    "IntentSerializer",
    "get_intent_serializer",
    "reset_intent_serializer_for_tests",
    # Logger
    "SemanticLogEntry",
    "SemanticLogger",
    "get_semantic_logger",
    "reset_semantic_logger_for_tests",
    # Prompts
    "IntentPromptBuilder",
    "get_intent_prompt_builder",
    "reset_intent_prompt_builder_for_tests",
]
