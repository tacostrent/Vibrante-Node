"""
visual_review_engine.py — §54 Reality Intelligence (Tier 15.0+)
================================================================
Visual Review Pass. Before declaring success, mentally render the viewport
and ask the four artist questions:

    Would an experienced Environment Artist approve this layout?
    Would this appear in a production game level?
    Would this appear in a film set?
    Would a human actually use this room?

A scene is successful ONLY when all nine §54 success criteria hold:
physically plausible, functionally usable, architecturally valid, visually
believable, compositionally balanced, relationship-consistent, free of
floating objects, free of orphan assets, free of impossible placements.

Passing tests alone is not success. Visual believability is the final
authority — production_ready requires ALL criteria, regardless of score.

Public API:
    VisualReviewResult
    VisualReviewEngine
    get_visual_review_engine()
    reset_visual_review_engine_for_tests()
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.runtime.reality.reality_scene_model import parse_scene
from src.runtime.reality.support_rule_engine import get_support_rule_engine
from src.runtime.reality.floating_object_detector import get_floating_object_detector
from src.runtime.reality.beam_connection_validator import get_beam_connection_validator
from src.runtime.reality.architectural_integrity_validator import (
    get_architectural_integrity_validator,
)
from src.runtime.reality.density_engine import get_environment_density_engine
from src.runtime.reality.composition_engine import get_composition_engine
from src.runtime.reality.functional_zone_builder import get_functional_zone_builder
from src.runtime.reality.human_reasoning_engine import get_human_reasoning_engine
from src.runtime.reality.correction_pass_engine import get_reality_correction_pass

_CRITERIA = (
    "physically_plausible",
    "functionally_usable",
    "architecturally_valid",
    "visually_believable",
    "compositionally_balanced",
    "relationship_consistent",
    "no_floating_objects",
    "no_orphan_assets",
    "no_impossible_placements",
)


@dataclass
class VisualReviewResult:
    # §54 success criteria
    physically_plausible:      bool = False
    functionally_usable:       bool = False
    architecturally_valid:     bool = False
    visually_believable:       bool = False
    compositionally_balanced:  bool = False
    relationship_consistent:   bool = False
    no_floating_objects:       bool = False
    no_orphan_assets:          bool = False
    no_impossible_placements:  bool = False

    # The four artist questions
    artist_would_approve:       bool = False
    production_game_quality:    bool = False
    film_set_quality:           bool = False
    human_would_use_room:       bool = False

    criteria_met:    int = 0
    criteria_total:  int = len(_CRITERIA)
    score:           float = 0.0
    grade:           str = "F"
    production_ready: bool = False
    findings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            **{name: getattr(self, name) for name in _CRITERIA},
            "artist_would_approve":    self.artist_would_approve,
            "production_game_quality": self.production_game_quality,
            "film_set_quality":        self.film_set_quality,
            "human_would_use_room":    self.human_would_use_room,
            "criteria_met":            self.criteria_met,
            "criteria_total":          self.criteria_total,
            "score":                   round(self.score, 4),
            "grade":                   self.grade,
            "production_ready":        self.production_ready,
            "findings":                list(self.findings),
        }


def _grade(score: float) -> str:
    if score >= 0.95:
        return "A"
    if score >= 0.80:
        return "B"
    if score >= 0.60:
        return "C"
    if score >= 0.40:
        return "D"
    return "F"


class VisualReviewEngine:
    """Final §54 review — visual believability is the authority. Never raises."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def review(self, scene_layout: Dict[str, Any]) -> VisualReviewResult:
        try:
            return self._review(scene_layout)
        except Exception as exc:
            r = VisualReviewResult()
            r.findings.append(f"VisualReviewEngine internal error: {exc}")
            return r

    # ------------------------------------------------------------------

    def _review(self, scene_layout: Dict[str, Any]) -> VisualReviewResult:
        result = VisualReviewResult()
        snap = parse_scene(scene_layout)

        support   = get_support_rule_engine().check_snapshot(snap)
        floating  = get_floating_object_detector().detect_snapshot(snap)
        beams     = get_beam_connection_validator().validate_snapshot(snap)
        integrity = get_architectural_integrity_validator().validate_snapshot(snap)
        density   = get_environment_density_engine().evaluate(scene_layout)
        compo     = get_composition_engine().evaluate_snapshot(snap)
        zones     = get_functional_zone_builder().build_from_snapshot(snap)
        reasoning = get_human_reasoning_engine().justify_scene(scene_layout)
        correction = get_reality_correction_pass().build_correction_plan(scene_layout)

        result.no_floating_objects      = floating.ok
        result.no_orphan_assets         = zones.no_orphans
        result.physically_plausible     = floating.ok and support.ok
        result.architecturally_valid    = integrity.architecturally_valid and beams.ok
        result.compositionally_balanced = compo.composition_ok
        result.relationship_consistent  = support.ok and correction.facing_fixes == 0
        result.functionally_usable      = (
            zones.no_orphans and len(zones.zones) > 0 and reasoning.all_justified
        )
        result.visually_believable      = (
            density.density_ok and compo.composition_ok and floating.ok
        )
        result.no_impossible_placements = (
            support.ok and integrity.architecturally_valid
            and reasoning.all_justified
        )

        for sub in (support, floating, beams, integrity, density, compo,
                    zones, reasoning):
            result.findings.extend(sub.findings)

        result.criteria_met = sum(
            1 for name in _CRITERIA if getattr(result, name)
        )
        result.score = result.criteria_met / float(result.criteria_total)
        result.grade = _grade(result.score)

        # The four artist questions — derived, never hand-waved.
        result.artist_would_approve = (
            result.physically_plausible
            and result.compositionally_balanced
            and result.no_floating_objects
        )
        result.production_game_quality = (
            result.artist_would_approve and result.visually_believable
        )
        result.film_set_quality = (
            result.production_game_quality and result.architecturally_valid
        )
        result.human_would_use_room = (
            result.functionally_usable and result.relationship_consistent
        )

        # Visual believability is the final authority: ALL criteria required.
        result.production_ready = result.criteria_met == result.criteria_total
        if not result.production_ready:
            failed = [n for n in _CRITERIA if not getattr(result, n)]
            result.findings.append(
                "NOT_PRODUCTION_READY: continue improving — failed criteria: "
                + ", ".join(failed)
            )
        return result


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[VisualReviewEngine] = None
_lock = threading.Lock()


def get_visual_review_engine() -> VisualReviewEngine:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = VisualReviewEngine()
    return _instance


def reset_visual_review_engine_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
