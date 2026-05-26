"""
LLM Provider Abstraction (Tier 3)
===================================
Provider-agnostic interface for OPTIONAL AI enhancement of intent parsing
and semantic planning. The runtime works fully without any LLM — all core
operations are deterministic. LLM providers add optional intelligence for:

  - ambiguous intent disambiguation
  - plan refinement suggestions
  - contextual reasoning summaries

Safety rules (non-negotiable):
  1. Providers return STRUCTURED DICTS only — never raw executable text.
  2. No provider may execute operations or mutate Houdini state.
  3. All provider output is validated/schema-checked before use.
  4. Providers are stateless between calls (no conversation history stored here).
  5. API keys and endpoints never appear in operation logs or audit trails.

Provider implementations:
    NoOpLLMProvider    — always-available default; returns empty enhancements.
    MockLLMProvider    — deterministic responses for testing (injectable).
    ClaudeLLMProvider  — uses Anthropic SDK (requires `anthropic` pkg + key).

Public API:
    get_llm_provider() -> LLMProvider
    set_llm_provider(provider) -> None
    reset_llm_provider_for_tests() -> None

    LLMProvider.enhance_intent(prompt, context) -> dict
    LLMProvider.suggest_plan_refinement(intent, plan, scene_context) -> dict
    LLMProvider.provider_name -> str
    LLMProvider.is_available -> bool
"""

import threading
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# Base interface
# ---------------------------------------------------------------------------

class LLMProvider(ABC):
    """Abstract base class for LLM providers.

    All methods are async. All return structured dicts.
    None may trigger execution or mutate external state.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable name for this provider."""

    @property
    def is_available(self) -> bool:
        """Return True if the provider is usable (API key set, SDK present, etc.)."""
        return True

    @abstractmethod
    async def enhance_intent(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Attempt to clarify or enhance a parsed intent.

        Args:
            prompt:   Raw user prompt text.
            context:  Optional dict of ambient context (scene state, capabilities).

        Returns:
            {
                "enhanced":    bool,           # True if provider added anything
                "intent":      str | None,     # Suggested semantic operation id
                "parameters":  dict,           # Extracted or refined parameters
                "confidence":  float,          # 0.0–1.0
                "reasoning":   list[str],      # Why this intent was chosen
                "alternatives":list[dict],     # Other plausible intents
            }
        """

    @abstractmethod
    async def suggest_plan_refinement(
        self,
        intent: str,
        plan:   Dict[str, Any],
        scene_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Optionally refine a deterministically-generated plan.

        Args:
            intent:        The semantic operation id.
            plan:          The current plan dict from ai_planner.
            scene_context: Optional current scene state.

        Returns:
            {
                "refined":      bool,
                "suggestions":  list[str],    # Human-readable advisory notes
                "warnings":     list[str],
                "parameters":   dict,          # Suggested parameter overrides
            }
        """


# ---------------------------------------------------------------------------
# No-op provider (always-available default)
# ---------------------------------------------------------------------------

class NoOpLLMProvider(LLMProvider):
    """Passthrough provider — adds no intelligence but never fails.

    Use when no LLM is configured. All methods return empty/neutral responses
    that signal to callers that no LLM enhancement was applied.
    """

    @property
    def provider_name(self) -> str:
        return "noop"

    @property
    def is_available(self) -> bool:
        return True

    async def enhance_intent(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return {
            "enhanced":     False,
            "intent":       None,
            "parameters":   {},
            "confidence":   0.0,
            "reasoning":    [],
            "alternatives": [],
        }

    async def suggest_plan_refinement(
        self,
        intent:        str,
        plan:          Dict[str, Any],
        scene_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return {
            "refined":    False,
            "suggestions": [],
            "warnings":   [],
            "parameters": {},
        }


# ---------------------------------------------------------------------------
# Mock provider (deterministic, for testing)
# ---------------------------------------------------------------------------

class MockLLMProvider(LLMProvider):
    """Deterministic mock for unit tests.

    Accepts a responses dict keyed by prompt substring, enabling predictable
    test scenarios without API calls.
    """

    def __init__(self, responses: Optional[Dict[str, Dict[str, Any]]] = None):
        self._responses = responses or {}

    @property
    def provider_name(self) -> str:
        return "mock"

    async def enhance_intent(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        p = prompt.lower()
        for key, resp in self._responses.items():
            if key.lower() in p:
                return {
                    "enhanced":     True,
                    "intent":       resp.get("intent"),
                    "parameters":   resp.get("parameters", {}),
                    "confidence":   resp.get("confidence", 0.9),
                    "reasoning":    resp.get("reasoning", [f"mock matched keyword '{key}'"]),
                    "alternatives": resp.get("alternatives", []),
                }
        return {
            "enhanced": False, "intent": None, "parameters": {},
            "confidence": 0.0, "reasoning": [], "alternatives": [],
        }

    async def suggest_plan_refinement(
        self,
        intent:        str,
        plan:          Dict[str, Any],
        scene_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return {
            "refined": False, "suggestions": [], "warnings": [], "parameters": {},
        }


# ---------------------------------------------------------------------------
# Claude provider stub (requires `anthropic` SDK + ANTHROPIC_API_KEY)
# ---------------------------------------------------------------------------

class ClaudeLLMProvider(LLMProvider):
    """Anthropic Claude provider for production use.

    Requires:
        pip install anthropic
        ANTHROPIC_API_KEY environment variable

    Returns STRUCTURED JSON outputs only. Raw model text is parsed and
    validated before being returned — never passed directly to the planner.
    """

    def __init__(self, model: str = "claude-sonnet-4-6", timeout: float = 30.0):
        self._model   = model
        self._timeout = timeout
        self._client  = None

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            import anthropic
            import os
            key = os.environ.get("ANTHROPIC_API_KEY", "")
            if not key:
                raise RuntimeError("ANTHROPIC_API_KEY not set")
            self._client = anthropic.Anthropic(api_key=key)
            return self._client
        except ImportError:
            raise RuntimeError("anthropic package not installed. Run: pip install anthropic")

    @property
    def provider_name(self) -> str:
        return f"claude/{self._model}"

    @property
    def is_available(self) -> bool:
        try:
            import anthropic  # noqa: F401
            import os
            return bool(os.environ.get("ANTHROPIC_API_KEY", ""))
        except ImportError:
            return False

    async def enhance_intent(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        import json
        import asyncio
        client = self._get_client()

        system = (
            "You are a Houdini semantic intent parser. "
            "Given a user prompt, extract the semantic operation intent as a JSON object. "
            "Known operation ids: create_geo_container, build_pyro_source, "
            "setup_karma_renderer, export_to_usd, cache_geometry, "
            "asset_publish_scaffold, solaris_lighting_setup. "
            "Reply ONLY with valid JSON matching this schema: "
            '{"intent": str, "parameters": dict, "confidence": float, '
            '"reasoning": [str], "alternatives": [{"intent": str, "confidence": float}]}'
        )
        user_msg = f"Prompt: {prompt}\nContext: {json.dumps(context or {})}"

        def _call():
            msg = client.messages.create(
                model=self._model,
                max_tokens=512,
                system=system,
                messages=[{"role": "user", "content": user_msg}],
            )
            return msg.content[0].text

        try:
            raw = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(None, _call),
                timeout=self._timeout,
            )
            parsed = json.loads(raw)
            return {
                "enhanced":     True,
                "intent":       str(parsed.get("intent", "")),
                "parameters":   dict(parsed.get("parameters", {})),
                "confidence":   float(parsed.get("confidence", 0.8)),
                "reasoning":    list(parsed.get("reasoning", [])),
                "alternatives": list(parsed.get("alternatives", [])),
            }
        except Exception as exc:
            return {
                "enhanced": False, "intent": None, "parameters": {},
                "confidence": 0.0,
                "reasoning": [f"Claude provider error: {exc}"],
                "alternatives": [],
            }

    async def suggest_plan_refinement(
        self,
        intent:        str,
        plan:          Dict[str, Any],
        scene_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        # Stub — can be expanded as needed
        return {"refined": False, "suggestions": [], "warnings": [], "parameters": {}}


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_PROVIDER: Optional[LLMProvider] = None
_LOCK = threading.Lock()


def get_llm_provider() -> LLMProvider:
    """Return the active LLM provider. Defaults to NoOpLLMProvider."""
    global _PROVIDER
    with _LOCK:
        if _PROVIDER is None:
            _PROVIDER = NoOpLLMProvider()
        return _PROVIDER


def set_llm_provider(provider: LLMProvider) -> None:
    """Replace the active provider. Use in startup code or tests."""
    global _PROVIDER
    with _LOCK:
        _PROVIDER = provider


def reset_llm_provider_for_tests() -> None:
    global _PROVIDER
    with _LOCK:
        _PROVIDER = None
