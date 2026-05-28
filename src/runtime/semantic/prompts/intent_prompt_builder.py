"""
Intent Prompt Builder (Phase 1)
=================================
Constructs structured extraction prompts that force the LLM to return
validated JSON only — never free-form text, never markdown, never code.

Every prompt includes:
  1. A strict system instruction block (role + output format)
  2. The schema contract (field names, allowed values, types)
  3. Few-shot examples to anchor the output format
  4. The user's raw prompt

Design rules:
  - Output format is always JSON only. Any deviation is a provider error.
  - Field value constraints (enums, ranges) are embedded in the prompt so the
    LLM self-validates — we still validate downstream regardless.
  - Prompts are composable: callers can add extra context via `extra_context`.
  - No Houdini-specific terms at this layer — pure semantic scene description.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from ..schema.scene_intent_schema import (
    ENVIRONMENT_TYPES,
    STYLE_TYPES,
    MOOD_TYPES,
    TIME_OF_DAY_VALUES,
    WEATHER_TYPES,
    SCALE_VALUES,
    DENSITY_LEVELS,
    DESTRUCTION_LEVELS,
    CINEMATIC_STYLE_VALUES,
    LIGHTING_STYLE_VALUES,
    ATMOSPHERIC_EFFECT_TYPES,
    ZONE_TYPES,
    ASSET_PROVIDER_VALUES,
    SCHEMA_VERSION,
)

# ---------------------------------------------------------------------------
# Few-shot examples (embedded in every extraction prompt)
# ---------------------------------------------------------------------------

_FEW_SHOT_EXAMPLES: List[Dict[str, Any]] = [
    {
        "prompt": "Apocalyptic city at night after a missile strike with heavy smoke and debris",
        "output": {
            "environment":        "urban",
            "style":              "cinematic",
            "mood":               "dramatic",
            "time_of_day":        "night",
            "weather":            "smoke",
            "scale":              "urban",
            "density":            "moderate",
            "destruction_level":  "heavy",
            "cinematic_style":    "action",
            "lighting_style":     "practical_fire",
            "atmospheric_effects": ["smoke", "debris_particles", "embers"],
            "keywords":           ["apocalyptic", "city", "night", "missile", "strike",
                                   "smoke", "debris"],
            "asset_requirements": [
                {"asset_type": "structure", "description": "damaged urban buildings",
                 "required": True, "provider": "unknown"},
                {"asset_type": "vehicle", "description": "destroyed military vehicles",
                 "required": False, "provider": "unknown"},
            ],
            "zones": [
                {"zone_type": "center", "description": "explosion epicenter with crater",
                 "fx_types": ["pyro", "rbd"], "priority": 10},
                {"zone_type": "background", "description": "burning city skyline",
                 "fx_types": ["pyro"], "priority": 6},
            ],
        },
    },
    {
        "prompt": "Desert sandstorm at golden hour with sparse vegetation",
        "output": {
            "environment":        "desert",
            "style":              "photorealistic",
            "mood":               "ominous",
            "time_of_day":        "dusk",
            "weather":            "dust",
            "scale":              "landscape",
            "density":            "sparse",
            "destruction_level":  "none",
            "cinematic_style":    "documentary",
            "lighting_style":     "golden_hour",
            "atmospheric_effects": ["dust", "haze"],
            "keywords":           ["desert", "sandstorm", "golden hour", "vegetation"],
            "asset_requirements": [
                {"asset_type": "vegetation", "description": "sparse desert plants",
                 "required": False, "provider": "polyhaven"},
            ],
            "zones": [
                {"zone_type": "foreground", "description": "rolling sand dunes",
                 "fx_types": [], "priority": 8},
                {"zone_type": "background", "description": "dust wall approaching",
                 "fx_types": ["dust"], "priority": 7},
            ],
        },
    },
]


# ---------------------------------------------------------------------------
# System instruction block
# ---------------------------------------------------------------------------

_SYSTEM_INSTRUCTION = """\
You are a Scene Intent Extraction AI. Your ONLY job is to parse a natural language
scene description and output a single valid JSON object — nothing else.

STRICT OUTPUT RULES:
1. Output ONLY raw JSON. No markdown. No code fences. No explanations. No prose.
2. The JSON must exactly match the schema described below.
3. Every string field must be one of the allowed values listed, or null.
4. Never invent values not in the allowed lists.
5. If a field cannot be determined, output null (not "unknown", not an empty string).
6. confidence must be a float between 0.0 and 1.0 reflecting certainty.

SCHEMA VERSION: {schema_version}

OUTPUT SCHEMA:
{{
  "environment":        <string | null>  — one of: {environments}
  "style":              <string | null>  — one of: {styles}
  "mood":               <string | null>  — one of: {moods}
  "time_of_day":        <string | null>  — one of: {times_of_day}
  "weather":            <string | null>  — one of: {weather_types}
  "scale":              <string | null>  — one of: {scales}
  "density":            <string | null>  — one of: {densities}
  "destruction_level":  <string | null>  — one of: {destruction_levels}
  "cinematic_style":    <string | null>  — one of: {cinematic_styles}
  "lighting_style":     <string | null>  — one of: {lighting_styles}
  "atmospheric_effects": <array of strings>  — each item must be from: {atmospheric_effects}
  "keywords":           <array of strings>   — important words from the prompt
  "asset_requirements": <array of AssetRequirement objects>
  "zones":              <array of SceneZone objects>
  "confidence":         <float 0.0–1.0>
  "extraction_notes":   <array of strings>  — optional notes about ambiguities
}}

AssetRequirement schema:
{{
  "asset_type":  <string>           — semantic category (e.g. "vehicle", "structure")
  "description": <string | null>    — what the asset looks like
  "quantity":    <integer | null>   — approximate count needed
  "style_hints": <array of strings> — style descriptors
  "required":    <boolean>          — true if scene fails without this asset
  "provider":    <string>           — one of: {providers}
}}

SceneZone schema:
{{
  "zone_type":   <string>  — one of: {zone_types}
  "description": <string | null>
  "assets":      <array of AssetRequirement>
  "fx_types":    <array of strings>  — e.g. ["pyro", "rbd", "flip"]
  "priority":    <integer 1–10>      — render/simulation priority
}}
"""


class IntentPromptBuilder:
    """Builds structured extraction prompts for scene intent parsing.

    The builder is stateless — it produces prompt strings without caching
    or maintaining any conversation history.

    Usage::

        builder = IntentPromptBuilder()
        system_msg, user_msg = builder.build("burning city at night")
        # Pass system_msg and user_msg to your LLM provider.
    """

    def __init__(self, include_examples: bool = True):
        self._include_examples = include_examples

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build(
        self,
        user_prompt: str,
        extra_context: Optional[Dict[str, Any]] = None,
    ) -> tuple[str, str]:
        """Build a (system_message, user_message) pair for intent extraction.

        Args:
            user_prompt:    The raw user scene description.
            extra_context:  Optional dict of ambient context to include.

        Returns:
            (system_msg, user_msg) ready to pass to an LLM provider.
        """
        system_msg = self._build_system_message()
        user_msg = self._build_user_message(user_prompt, extra_context)
        return system_msg, user_msg

    def build_refinement(
        self,
        user_prompt: str,
        previous_intent: Dict[str, Any],
        feedback: str,
    ) -> tuple[str, str]:
        """Build a refinement prompt to correct a previous extraction.

        Args:
            user_prompt:      Original prompt.
            previous_intent:  Previous extraction result dict.
            feedback:         Specific correction or clarification.

        Returns:
            (system_msg, user_msg) for a refinement pass.
        """
        system_msg = self._build_system_message()
        user_msg = self._build_refinement_message(user_prompt, previous_intent, feedback)
        return system_msg, user_msg

    def format_schema_contract(self) -> str:
        """Return just the schema description string (useful for logging/debug)."""
        return self._build_system_message()

    # ------------------------------------------------------------------
    # Private builders
    # ------------------------------------------------------------------

    def _build_system_message(self) -> str:
        return _SYSTEM_INSTRUCTION.format(
            schema_version=SCHEMA_VERSION,
            environments=", ".join(sorted(ENVIRONMENT_TYPES)),
            styles=", ".join(sorted(STYLE_TYPES)),
            moods=", ".join(sorted(MOOD_TYPES)),
            times_of_day=", ".join(sorted(TIME_OF_DAY_VALUES)),
            weather_types=", ".join(sorted(WEATHER_TYPES)),
            scales=", ".join(sorted(SCALE_VALUES)),
            densities=", ".join(sorted(DENSITY_LEVELS)),
            destruction_levels=", ".join(sorted(DESTRUCTION_LEVELS)),
            cinematic_styles=", ".join(sorted(CINEMATIC_STYLE_VALUES)),
            lighting_styles=", ".join(sorted(LIGHTING_STYLE_VALUES)),
            atmospheric_effects=", ".join(sorted(ATMOSPHERIC_EFFECT_TYPES)),
            providers=", ".join(sorted(ASSET_PROVIDER_VALUES)),
            zone_types=", ".join(sorted(ZONE_TYPES)),
        )

    def _build_user_message(
        self,
        user_prompt: str,
        extra_context: Optional[Dict[str, Any]],
    ) -> str:
        parts: List[str] = []

        if self._include_examples:
            parts.append("EXAMPLES (for output format reference only):\n")
            for ex in _FEW_SHOT_EXAMPLES:
                parts.append(f"Input: {ex['prompt']}")
                parts.append(f"Output: {json.dumps(ex['output'], indent=2)}")
                parts.append("")

        if extra_context:
            parts.append("CONTEXT:")
            parts.append(json.dumps(extra_context, indent=2))
            parts.append("")

        parts.append("NOW EXTRACT THE INTENT FROM THIS SCENE DESCRIPTION:")
        parts.append(user_prompt)
        parts.append("")
        parts.append("OUTPUT JSON ONLY:")

        return "\n".join(parts)

    def _build_refinement_message(
        self,
        user_prompt: str,
        previous_intent: Dict[str, Any],
        feedback: str,
    ) -> str:
        return "\n".join([
            "REFINEMENT TASK:",
            "The previous extraction produced the following result:",
            json.dumps(previous_intent, indent=2),
            "",
            "The following correction or clarification was provided:",
            feedback,
            "",
            "Original scene description:",
            user_prompt,
            "",
            "Output a corrected JSON object only. Apply the correction strictly.",
            "OUTPUT JSON ONLY:",
        ])


# ---------------------------------------------------------------------------
# Module-level convenience
# ---------------------------------------------------------------------------

_builder: Optional[IntentPromptBuilder] = None


def get_intent_prompt_builder(include_examples: bool = True) -> IntentPromptBuilder:
    """Return a shared IntentPromptBuilder instance."""
    global _builder
    if _builder is None:
        _builder = IntentPromptBuilder(include_examples=include_examples)
    return _builder


def reset_intent_prompt_builder_for_tests() -> None:
    """Reset the shared instance (test isolation)."""
    global _builder
    _builder = None
