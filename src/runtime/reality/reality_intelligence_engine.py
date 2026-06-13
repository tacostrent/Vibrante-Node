"""
reality_intelligence_engine.py — §54 Reality Intelligence (Tier 15.0+)
=======================================================================
Main orchestrator. Runs the full §54 pipeline on a scene layout:

    1. Human Reasoning        — every asset must justify its existence
    2. Functional Zones       — every asset must belong to a zone
    3. Support Rules          — required supports must exist
    4. No Floating Objects    — raycast_down() for every elevated asset
    5. Beam Connections       — beams must connect architecture
    6. Architectural Integrity— doors/windows need real openings
    7. Density                — empty rooms are invalid
    8. Composition            — focal points + negative space
    9. Correction Plan        — geometry fixes for everything found
   10. Visual Review          — the final authority

Optionally reconciles the planned scene against observed Houdini geometry
first (GEOMETRY WINS) when an observed scene dict is supplied.

Public API:
    RealityIntelligenceResult
    RealityIntelligenceEngine
    get_reality_intelligence_engine()
    reset_reality_intelligence_engine_for_tests()
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.runtime.reality.human_reasoning_engine import get_human_reasoning_engine
from src.runtime.reality.functional_zone_builder import get_functional_zone_builder
from src.runtime.reality.support_rule_engine import get_support_rule_engine
from src.runtime.reality.floating_object_detector import get_floating_object_detector
from src.runtime.reality.beam_connection_validator import get_beam_connection_validator
from src.runtime.reality.architectural_integrity_validator import (
    get_architectural_integrity_validator,
)
from src.runtime.reality.density_engine import get_environment_density_engine
from src.runtime.reality.composition_engine import get_composition_engine
from src.runtime.reality.correction_pass_engine import get_reality_correction_pass
from src.runtime.reality.visual_review_engine import get_visual_review_engine
from src.runtime.reality.geometry_inspector import get_geometry_inspector
from src.runtime.reality.reality_statistics import get_reality_statistics


@dataclass
class RealityIntelligenceResult:
    environment: str = ""
    reasoning:   Dict[str, Any] = field(default_factory=dict)
    zones:       Dict[str, Any] = field(default_factory=dict)
    support:     Dict[str, Any] = field(default_factory=dict)
    floating:    Dict[str, Any] = field(default_factory=dict)
    beams:       Dict[str, Any] = field(default_factory=dict)
    integrity:   Dict[str, Any] = field(default_factory=dict)
    density:     Dict[str, Any] = field(default_factory=dict)
    composition: Dict[str, Any] = field(default_factory=dict)
    correction_plan: Dict[str, Any] = field(default_factory=dict)
    visual_review:   Dict[str, Any] = field(default_factory=dict)
    viewport_reconciled: bool = False
    production_ready: bool = False
    grade: str = "F"
    score: float = 0.0
    findings: List[str] = field(default_factory=list)
    evaluated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "environment":         self.environment,
            "reasoning":           self.reasoning,
            "zones":               self.zones,
            "support":             self.support,
            "floating":            self.floating,
            "beams":               self.beams,
            "integrity":           self.integrity,
            "density":             self.density,
            "composition":         self.composition,
            "correction_plan":     self.correction_plan,
            "visual_review":       self.visual_review,
            "viewport_reconciled": self.viewport_reconciled,
            "production_ready":    self.production_ready,
            "grade":               self.grade,
            "score":               round(self.score, 4),
            "findings":            list(self.findings),
            "evaluated_at":        self.evaluated_at,
        }


class RealityIntelligenceEngine:
    """Runs the full §54 Reality Intelligence pipeline. Never raises."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def evaluate(
        self,
        scene_layout: Dict[str, Any],
        observed_scene: Optional[Dict[str, Any]] = None,
    ) -> RealityIntelligenceResult:
        """
        Evaluate a scene layout against every §54 rule.

        When observed_scene (a GeometryInspector ObservedScene dict) is given,
        the planned layout is reconciled against it first — GEOMETRY WINS.
        """
        try:
            return self._evaluate(scene_layout or {}, observed_scene)
        except Exception as exc:
            r = RealityIntelligenceResult()
            r.findings.append(f"RealityIntelligenceEngine internal error: {exc}")
            return r

    def _evaluate(
        self,
        scene_layout: Dict[str, Any],
        observed_scene: Optional[Dict[str, Any]],
    ) -> RealityIntelligenceResult:
        result = RealityIntelligenceResult()

        if observed_scene:
            scene_layout = get_geometry_inspector().reconcile(
                observed_scene, scene_layout
            )
            result.viewport_reconciled = bool(
                scene_layout.get("viewport_reconciled", False)
            )

        result.environment = str(scene_layout.get("environment", "") or "")

        result.reasoning   = get_human_reasoning_engine().justify_scene(scene_layout).to_dict()
        result.zones       = get_functional_zone_builder().build_zones(scene_layout).to_dict()
        result.support     = get_support_rule_engine().check_scene(scene_layout).to_dict()
        result.floating    = get_floating_object_detector().detect(scene_layout).to_dict()
        result.beams       = get_beam_connection_validator().validate(scene_layout).to_dict()
        result.integrity   = get_architectural_integrity_validator().validate(scene_layout).to_dict()
        result.density     = get_environment_density_engine().evaluate(scene_layout).to_dict()
        result.composition = get_composition_engine().evaluate(scene_layout).to_dict()
        result.correction_plan = (
            get_reality_correction_pass().build_correction_plan(scene_layout).to_dict()
        )

        review = get_visual_review_engine().review(scene_layout)
        result.visual_review    = review.to_dict()
        result.production_ready = review.production_ready
        result.grade            = review.grade
        result.score            = review.score
        result.findings         = list(review.findings)

        get_reality_statistics().record(
            environment=result.environment,
            production_ready=result.production_ready,
            score=result.score,
            grade=result.grade,
            correction_count=len(result.correction_plan.get("ops") or []),
        )
        return result


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[RealityIntelligenceEngine] = None
_lock = threading.Lock()


def get_reality_intelligence_engine() -> RealityIntelligenceEngine:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = RealityIntelligenceEngine()
    return _instance


def reset_reality_intelligence_engine_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
