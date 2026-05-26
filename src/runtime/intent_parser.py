"""
Intent Parser (Tier 3)
========================
Convert natural language prompts to structured semantic intents.

DETERMINISTIC by default — uses keyword/synonym tables and regex parameter
extraction. An optional LLM provider (see llm_provider.py) can be configured
to enhance disambiguation of ambiguous prompts; the deterministic layer runs
first and the LLM layer supplements it.

The parser does NOT:
  - execute operations
  - mutate scenes
  - generate Houdini operations directly

It ONLY:
  - extracts a semantic operation id
  - normalizes known parameters (parent path, name, radius, etc.)
  - detects ambiguity
  - maps synonyms

Public API:
    get_intent_parser() -> IntentParser
    reset_intent_parser_for_tests()

    IntentParser.parse(prompt, context=None) -> dict
"""

import re
import threading
from typing import Any, Dict, List, Optional, Tuple

from src.runtime.llm_provider import get_llm_provider

# ---------------------------------------------------------------------------
# Synonym / keyword tables
# ---------------------------------------------------------------------------

# Intent id → list of trigger keywords (any match → candidate)
_INTENT_KEYWORDS: Dict[str, List[str]] = {
    "build_pyro_source": [
        "pyro", "fire", "smoke", "explosion", "blast", "combustion",
        "flame", "burning", "ignite", "pyrosim", "puff",
    ],
    "create_geo_container": [
        "geo", "geometry", "object", "container", "mesh",
        "create object", "new object", "geo node", "geo container",
        "model", "polygon", "create geo",
    ],
    "setup_karma_renderer": [
        "karma", "render", "rendering", "renderer", "solaris render",
        "usd render", "karma render", "set up render", "configure render",
    ],
    "export_to_usd": [
        "usd", "export usd", "usd export", "universal scene description",
        "stage export", "write usd", "save usd",
    ],
    "cache_geometry": [
        "cache", "file cache", "bake", "geometry cache", "bgeo",
        "write cache", "save cache", "alembic", "abc cache",
    ],
    "asset_publish_scaffold": [
        "asset", "publish", "scaffold", "asset publish", "pipeline asset",
        "studio asset", "publish setup", "asset structure",
    ],
    "solaris_lighting_setup": [
        "lighting", "lights", "light rig", "three point", "solaris light",
        "usd lighting", "distant light", "key fill rim",
    ],
}

# Synonyms that map to specific parameter values
_STYLE_SYNONYMS: Dict[str, Dict[str, str]] = {
    "build_pyro_source": {
        "explosion": "explosion", "blast": "explosion",
        "smoke": "smoke", "wispy": "smoke", "puff": "smoke",
        "fire": "fire", "flame": "fire", "burning": "fire",
    },
}

# Parameter extraction patterns (name → list of regex patterns)
_PARAM_PATTERNS: Dict[str, List[str]] = {
    "name": [
        r'(?:called?|named?)\s+["\']?(\w[\w\d_-]*)["\']?',
        r'["\'](\w[\w\d_-]*)["\']',
    ],
    "parent": [
        r'(?:inside?|in|under|within|at)\s+([/][/\w]+)',
        r'(?:parent|container|network)[:\s]+([/][/\w]+)',
    ],
    "radius": [
        r'radius\s+(?:of\s+)?(\d+\.?\d*)',
        r'(\d+\.?\d*)\s*(?:units?|u)\s+radius',
    ],
    "stage_path": [
        r'(?:stage|solaris)\s+(?:at|in|path)?\s*([/][/\w]+)',
    ],
    "output_path": [
        r'(?:output|save|write|export)\s+(?:to\s+)?([^\s,;]+\.(?:usd|exr|abc|bgeo|sc))',
    ],
}

# Conflict resolution: when two intents score equally, prefer the one listed first
_INTENT_PRIORITY: List[str] = [
    "build_pyro_source",
    "setup_karma_renderer",
    "export_to_usd",
    "cache_geometry",
    "asset_publish_scaffold",
    "solaris_lighting_setup",
    "create_geo_container",
]

# Ambiguity threshold: if top-2 scores are within this fraction, flag as ambiguous
_AMBIGUITY_THRESHOLD = 0.3


def _score_intents(tokens: List[str]) -> List[Tuple[str, float]]:
    """Return (intent_id, score) pairs sorted highest-first.

    Score = fraction of tokens that match the intent's keyword list.
    """
    scores: Dict[str, float] = {}
    for intent_id, keywords in _INTENT_KEYWORDS.items():
        hits = sum(1 for kw in keywords if any(kw in tok for tok in tokens))
        scores[intent_id] = hits / max(len(keywords), 1)

    # Sort: primary = score descending, secondary = priority order
    ordered = sorted(
        scores.items(),
        key=lambda pair: (
            -pair[1],
            _INTENT_PRIORITY.index(pair[0]) if pair[0] in _INTENT_PRIORITY else 99,
        ),
    )
    return ordered


def _extract_parameters(prompt: str) -> Dict[str, str]:
    """Extract known parameter values from the prompt via regex."""
    params: Dict[str, str] = {}
    for param, patterns in _PARAM_PATTERNS.items():
        for pat in patterns:
            m = re.search(pat, prompt, re.IGNORECASE)
            if m:
                params[param] = m.group(1)
                break
    return params


def _extract_style(prompt: str, intent_id: str) -> Dict[str, str]:
    """Extract style-specific parameter hints for a given intent."""
    styles = _STYLE_SYNONYMS.get(intent_id, {})
    p = prompt.lower()
    for word, style_value in styles.items():
        if word in p:
            return {"style": style_value}
    return {}


# ---------------------------------------------------------------------------
# Parser class
# ---------------------------------------------------------------------------

class IntentParser:
    """Deterministic intent parser with optional LLM enhancement layer."""

    async def parse(
        self,
        prompt:  str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Convert a natural language prompt to a structured semantic intent.

        Returns:
            {
                "intent":           str | None,    # best semantic operation id
                "parameters":       dict,          # extracted parameters
                "confidence":       float,         # 0.0–1.0
                "alternatives":     list[dict],    # other plausible intents
                "ambiguous":        bool,
                "raw_prompt":       str,
                "matched_keywords": list[str],
                "llm_enhanced":     bool,
            }
        """
        context  = dict(context or {})
        p_lower  = prompt.lower()
        tokens   = re.split(r'\W+', p_lower)

        # 1. Deterministic keyword scoring
        scored   = _score_intents(tokens)
        top_id, top_score     = scored[0] if scored else ("", 0.0)
        second_id, second_score = scored[1] if len(scored) > 1 else ("", 0.0)

        # 2. Detect matched keywords for transparency
        matched_kws: List[str] = []
        if top_id:
            for kw in _INTENT_KEYWORDS.get(top_id, []):
                if kw in p_lower:
                    matched_kws.append(kw)

        # 3. Parameter extraction
        params = _extract_parameters(prompt)
        if top_id:
            params.update(_extract_style(prompt, top_id))

        # 4. Ambiguity detection
        ambiguous = (
            top_score > 0.0
            and second_score > 0.0
            and (top_score - second_score) / max(top_score, 1e-9) < _AMBIGUITY_THRESHOLD
        )

        intent     = top_id if top_score > 0.0 else None
        confidence = min(1.0, top_score * 2.0) if top_score > 0.0 else 0.0

        alternatives = [
            {"intent": aid, "confidence": min(1.0, asc * 2.0)}
            for aid, asc in scored[1:4]
            if asc > 0.0 and aid != top_id
        ]

        result: Dict[str, Any] = {
            "intent":           intent,
            "parameters":       params,
            "confidence":       round(confidence, 3),
            "alternatives":     alternatives,
            "ambiguous":        ambiguous,
            "raw_prompt":       prompt,
            "matched_keywords": matched_kws,
            "llm_enhanced":     False,
        }

        # 5. Optional LLM enhancement
        provider = get_llm_provider()
        if provider.is_available and provider.provider_name != "noop":
            llm_result = await provider.enhance_intent(prompt, context)
            if llm_result.get("enhanced") and llm_result.get("intent"):
                llm_intent = llm_result["intent"]
                llm_conf   = float(llm_result.get("confidence", 0.5))
                # LLM result wins only if confidence > deterministic confidence
                # or if deterministic layer found nothing
                if llm_conf > confidence or intent is None:
                    result["intent"]       = llm_intent
                    result["confidence"]   = round(llm_conf, 3)
                    result["parameters"].update(llm_result.get("parameters", {}))
                    result["ambiguous"]    = llm_conf < 0.7
                    result["llm_enhanced"] = True
                    if llm_result.get("alternatives"):
                        result["alternatives"] = llm_result["alternatives"]

        return result


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_PARSER: Optional[IntentParser] = None
_LOCK = threading.Lock()


def get_intent_parser() -> IntentParser:
    global _PARSER
    with _LOCK:
        if _PARSER is None:
            _PARSER = IntentParser()
        return _PARSER


def reset_intent_parser_for_tests() -> None:
    global _PARSER
    with _LOCK:
        _PARSER = None
