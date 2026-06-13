"""
Workflow Recommendation Engine (Tier 10 — Workflow Packs & Production Blueprints)
==================================================================================
Recommends workflow packs from semantic intent using a priority chain:

  ProductionMemory (0.95) → PatternLibrary (0.80) → Graph (0.65) → Default (0.50)

DESIGN RULES:
  1. Deterministic — same intent + registry state → same recommendation.
  2. All Tier 5 source failures silently caught — always returns a result.
  3. No bridge calls.  Advisory only.
  4. LLM-free — all matching is keyword + environment-based.

Public API:
    WorkflowRecommendation
    RecommendationResult
    WorkflowRecommendationEngine
    get_workflow_recommendation_engine()
    reset_workflow_recommendation_engine_for_tests()
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.runtime.workflows.workflow_pack import VALID_ENVIRONMENT_TYPES

# ---------------------------------------------------------------------------
# Keyword → environment intent mapping
# ---------------------------------------------------------------------------

_INTENT_KEYWORDS: Dict[str, List[str]] = {
    "industrial_hangar": [
        "industrial", "hangar", "factory", "workshop", "warehouse",
        "machinery", "repair", "maintenance", "heavy", "equipment",
    ],
    "robotics_lab": [
        "robotics", "lab", "laboratory", "robot", "precision",
        "engineering", "testing", "automation", "assembly",
    ],
    "control_room": [
        "control", "command", "monitor", "console", "mission",
        "operations", "hub", "screens", "dispatch", "hq",
    ],
    "sci_fi_corridor": [
        "corridor", "scifi", "sci-fi", "passage", "hallway",
        "futuristic", "space", "starship", "station", "tunnel",
    ],
    "abandoned_factory": [
        "abandoned", "derelict", "ruined", "post-apocalyptic",
        "decay", "broken", "old", "dilapidated", "rust",
    ],
}

# Default pack names per environment
_DEFAULT_PACK_NAMES: Dict[str, str] = {
    "industrial_hangar": "industrial_hangar_pack",
    "robotics_lab":      "robotics_lab_pack",
    "control_room":      "control_room_pack",
    "sci_fi_corridor":   "sci_fi_corridor_pack",
    "abandoned_factory": "abandoned_factory_pack",
}


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class WorkflowRecommendation:
    """A single workflow pack recommendation."""
    pack_name:    str
    confidence:   float
    source:       str       # "memory" | "pattern" | "graph" | "default" | "keyword"
    reason:       str
    environment:  str
    metadata:     Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pack_name":   self.pack_name,
            "confidence":  self.confidence,
            "source":      self.source,
            "reason":      self.reason,
            "environment": self.environment,
            "metadata":    self.metadata,
        }


@dataclass
class RecommendationResult:
    """Result of a recommendation query."""
    ok:               bool
    intent:           str
    recommendations:  List[WorkflowRecommendation] = field(default_factory=list)
    matched_environment: Optional[str] = None
    source_counts:    Dict[str, int]   = field(default_factory=dict)
    generated_at:     float            = field(default_factory=time.time)

    @property
    def top_recommendation(self) -> Optional[WorkflowRecommendation]:
        return self.recommendations[0] if self.recommendations else None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok":                    self.ok,
            "intent":                self.intent,
            "recommendations":       [r.to_dict() for r in self.recommendations],
            "matched_environment":   self.matched_environment,
            "source_counts":         self.source_counts,
            "top_recommendation":    self.top_recommendation.to_dict() if self.top_recommendation else None,
            "generated_at":          self.generated_at,
        }


# ---------------------------------------------------------------------------
# WorkflowRecommendationEngine
# ---------------------------------------------------------------------------

class WorkflowRecommendationEngine:
    """Recommends workflow packs from semantic intent."""

    def __init__(self) -> None:
        self._recommendation_count = 0
        self._lock = threading.Lock()

    # -----------------------------------------------------------------
    def recommend_pack(
        self,
        intent:        str,
        context:       Optional[Dict[str, Any]] = None,
        max_results:   int = 3,
    ) -> RecommendationResult:
        """
        Main entry point.  Returns up to max_results ranked recommendations.
        """
        with self._lock:
            self._recommendation_count += 1

        intent_lower  = intent.lower()
        matched_env   = self.match_environment(intent_lower)
        recommendations: List[WorkflowRecommendation] = []
        source_counts:   Dict[str, int] = {}

        # Priority 1 — ProductionMemory
        mem_recs = self._from_memory(matched_env, intent_lower)
        for r in mem_recs:
            recommendations.append(r)
        source_counts["memory"] = len(mem_recs)

        # Priority 2 — PatternLibrary
        pat_recs = self._from_pattern_library(matched_env)
        for r in pat_recs:
            if not any(x.pack_name == r.pack_name for x in recommendations):
                recommendations.append(r)
        source_counts["pattern"] = len(pat_recs)

        # Priority 3 — production patterns / knowledge graph
        prod_recs = self._from_production_patterns(matched_env, intent_lower)
        for r in prod_recs:
            if not any(x.pack_name == r.pack_name for x in recommendations):
                recommendations.append(r)
        source_counts["production"] = len(prod_recs)

        # Priority 4 — Default
        if matched_env:
            default_name = _DEFAULT_PACK_NAMES.get(matched_env, "")
            if default_name and not any(r.pack_name == default_name for r in recommendations):
                recommendations.append(WorkflowRecommendation(
                    pack_name   = default_name,
                    confidence  = 0.50,
                    source      = "default",
                    reason      = f"Default production pack for {matched_env}.",
                    environment = matched_env,
                ))
                source_counts["default"] = 1

        # Rank and limit
        ranked = self.rank_candidates(recommendations)
        ranked = ranked[:max_results]

        return RecommendationResult(
            ok                   = True,
            intent               = intent,
            recommendations      = ranked,
            matched_environment  = matched_env,
            source_counts        = source_counts,
        )

    # -----------------------------------------------------------------
    def match_environment(self, intent_lower: str) -> Optional[str]:
        """Return the best-matching environment name from the intent string."""
        scores: Dict[str, int] = {}
        for env, keywords in _INTENT_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in intent_lower)
            if score:
                scores[env] = score
        if not scores:
            return None
        return max(scores, key=lambda e: scores[e])

    # -----------------------------------------------------------------
    def rank_candidates(
        self, candidates: List[WorkflowRecommendation]
    ) -> List[WorkflowRecommendation]:
        """Sort by confidence descending, then name for stability."""
        return sorted(candidates, key=lambda r: (-r.confidence, r.pack_name))

    # -----------------------------------------------------------------
    def match_production_patterns(
        self, environment: Optional[str], intent: str
    ) -> List[WorkflowRecommendation]:
        """Extract recommendations from production knowledge sources."""
        return self._from_production_patterns(environment, intent.lower())

    # -----------------------------------------------------------------
    def build_recommendation(
        self, intent: str, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Convenience wrapper returning the top recommendation as a flat dict.
        """
        result = self.recommend_pack(intent, context=context)
        top    = result.top_recommendation
        return {
            "recommended_pack": top.pack_name if top else None,
            "confidence":       top.confidence if top else 0.0,
            "source":           top.source if top else "none",
            "reason":           top.reason if top else "No matching pack found.",
            "environment":      result.matched_environment,
            "all_candidates":   [r.to_dict() for r in result.recommendations],
        }

    # -----------------------------------------------------------------
    # Internal source helpers
    # -----------------------------------------------------------------

    def _from_memory(
        self, environment: Optional[str], intent: str
    ) -> List[WorkflowRecommendation]:
        """Pull best pack name from ProductionMemory."""
        if not environment:
            return []
        try:
            from src.runtime.production_memory import get_production_memory
            mem = get_production_memory()
            history = mem.get_scene_history(scene_type=environment, status="success", limit=5)
            recs: List[WorkflowRecommendation] = []
            seen: set = set()
            for record in history:
                pack_name = record.get("pack_name") or _DEFAULT_PACK_NAMES.get(environment, "")
                if pack_name and pack_name not in seen:
                    seen.add(pack_name)
                    recs.append(WorkflowRecommendation(
                        pack_name   = pack_name,
                        confidence  = 0.95,
                        source      = "memory",
                        reason      = (
                            f"Previously successful scene of type '{environment}' "
                            "recorded in production memory."
                        ),
                        environment = environment,
                    ))
            return recs
        except Exception:
            return []

    def _from_pattern_library(
        self, environment: Optional[str]
    ) -> List[WorkflowRecommendation]:
        """Pull best-ranked patterns from PatternLibrary."""
        if not environment:
            return []
        try:
            from src.runtime.pattern_library import get_pattern_library
            lib  = get_pattern_library()
            pats = lib.search_patterns(scene_type=environment, pattern_type="scene_pattern")
            if not pats:
                return []
            best = pats[0]
            pack_name = _DEFAULT_PACK_NAMES.get(environment, "")
            if not pack_name:
                return []
            return [WorkflowRecommendation(
                pack_name   = pack_name,
                confidence  = 0.80,
                source      = "pattern",
                reason      = (
                    f"Pattern '{best.get('pattern_id', '')}' has a high success rate "
                    f"for {environment}."
                ),
                environment = environment,
            )]
        except Exception:
            return []

    def _from_production_patterns(
        self, environment: Optional[str], intent: str
    ) -> List[WorkflowRecommendation]:
        """Pull proven configurations from StudioKnowledge."""
        if not environment:
            return []
        try:
            from src.runtime.studio_knowledge import get_studio_knowledge
            sk     = get_studio_knowledge()
            recipe = sk.get_best_recipe(environment)
            if not recipe:
                return []
            pack_name = _DEFAULT_PACK_NAMES.get(environment, "")
            if not pack_name:
                return []
            return [WorkflowRecommendation(
                pack_name   = pack_name,
                confidence  = 0.65,
                source      = "production",
                reason      = (
                    f"Studio knowledge has a proven recipe for {environment} "
                    f"with {recipe.get('op_count', 0)} ops."
                ),
                environment = environment,
                metadata    = {"recipe": recipe},
            )]
        except Exception:
            return []

    def stats(self) -> Dict[str, Any]:
        return {"recommendation_count": self._recommendation_count}


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[WorkflowRecommendationEngine] = None
_lock = threading.Lock()


def get_workflow_recommendation_engine() -> WorkflowRecommendationEngine:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = WorkflowRecommendationEngine()
    return _instance


def reset_workflow_recommendation_engine_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
