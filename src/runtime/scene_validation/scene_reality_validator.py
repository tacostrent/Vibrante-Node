"""
scene_reality_validator.py — §53 Scene Reality Validation (Tier 14.3)
======================================================================
Main orchestrator. Runs all five validation rules on a ResolvedSceneLayout
and produces a SceneValidationResult with four composite metrics.

New metrics (replace single production_ready):
    geometry_valid      — no BLOCKING occupancy or support violations (Rules 1+2)
    semantic_valid      — relationships OK + no orphans + score >= 0.95 (Rules 3+5)
    plausibility_valid  — plausibility_score >= 0.90 (Rule 4)
    production_ready    — all three valid + at least one asset

Acceptance criteria (§53 audit doc):
    ✓ No props inside chair volumes
    ✓ No props beneath furniture
    ✓ All small props assigned to valid support surfaces
    ✓ All chairs attached to valid furniture anchor
    ✓ plausibility_score >= 0.90
    ✓ semantic_validation_score >= 0.95

Pipeline insertion:
    classify → layout → realization → collision → constraint
    → scene_reality_validation  ← this module

Public API:
    SceneValidationResult
    SceneRealityValidator
    get_scene_reality_validator()
    reset_scene_reality_validator_for_tests()
"""

from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.runtime.scene_validation.support_surface_validator import (
    get_support_surface_validator,
)
from src.runtime.scene_validation.occupancy_validator import (
    get_occupancy_validator,
)
from src.runtime.scene_validation.relationship_validator import (
    get_relationship_validator,
)
from src.runtime.scene_validation.plausibility_engine import (
    get_plausibility_engine,
)
from src.runtime.scene_validation.orphan_detector import (
    get_orphan_detector,
)

SEMANTIC_SCORE_THRESHOLD = 0.95   # §53 acceptance criterion


@dataclass
class SceneValidationResult:
    """
    Composite result of all five Scene Reality Validation rules.
    Replaces bare production_ready with four independent verdicts.
    """

    # Composite metrics
    geometry_valid:      bool  = False
    semantic_valid:      bool  = False
    plausibility_valid:  bool  = False
    production_ready:    bool  = False

    # Per-rule results (serialized violation dicts)
    support_violations:   List[Dict[str, Any]] = field(default_factory=list)
    occupancy_violations: List[Dict[str, Any]] = field(default_factory=list)
    relationship_failures:List[Dict[str, Any]] = field(default_factory=list)
    orphan_objects:       List[Dict[str, Any]] = field(default_factory=list)
    plausibility:         Dict[str, Any]        = field(default_factory=dict)

    # Aggregate scores
    plausibility_score:         float = 0.0
    semantic_validation_score:  float = 0.0

    # Counts
    blocking_count: int = 0
    warning_count:  int = 0

    findings: List[str] = field(default_factory=list)
    blocking: List[str] = field(default_factory=list)
    validated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "geometry_valid":            self.geometry_valid,
            "semantic_valid":            self.semantic_valid,
            "plausibility_valid":        self.plausibility_valid,
            "production_ready":          self.production_ready,
            "support_violations":        self.support_violations,
            "occupancy_violations":      self.occupancy_violations,
            "relationship_failures":     self.relationship_failures,
            "orphan_objects":            self.orphan_objects,
            "plausibility":              self.plausibility,
            "plausibility_score":        round(self.plausibility_score, 4),
            "semantic_validation_score": round(self.semantic_validation_score, 4),
            "blocking_count":            self.blocking_count,
            "warning_count":             self.warning_count,
            "findings":                  list(self.findings),
            "blocking":                  list(self.blocking),
            "validated_at":              self.validated_at,
        }


class SceneRealityValidator:
    """
    Runs all five Scene Reality Validation rules on a ResolvedSceneLayout.

    Usage:
        scene = get_layout_realization_engine().realize(plan)
        result = get_scene_reality_validator().validate(scene.to_dict())
        # result.production_ready → True only when all criteria met
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def validate(self, scene_layout: Dict[str, Any]) -> SceneValidationResult:
        """
        Validate a ResolvedSceneLayout.to_dict() against all five rules.
        Never raises.
        """
        try:
            return self._validate(scene_layout)
        except Exception as exc:
            r = SceneValidationResult()
            r.findings.append(f"SceneRealityValidator internal error: {exc}")
            return r

    def _validate(self, scene: Dict[str, Any]) -> SceneValidationResult:
        result = SceneValidationResult()
        n_transforms = len(scene.get("transforms") or [])

        # --- Rule 1: Support Surface Validation ---
        sv = get_support_surface_validator().validate(scene)
        result.support_violations = [v.to_dict() for v in sv]

        # --- Rule 2: Occupancy Validation ---
        ov = get_occupancy_validator().validate(scene)
        result.occupancy_violations = [v.to_dict() for v in ov]

        # --- Rule 3: Functional Relationship Validation ---
        rv = get_relationship_validator().validate(scene)
        result.relationship_failures = [f.to_dict() for f in rv]

        # --- Rule 4: Human Plausibility ---
        plaus = get_plausibility_engine().evaluate(scene)
        result.plausibility       = plaus.to_dict()
        result.plausibility_score = plaus.plausibility_score

        # --- Rule 5: Orphan Detection ---
        od = get_orphan_detector().detect(scene)
        result.orphan_objects = [o.to_dict() for o in od]

        # --- Blocking findings (BLOCKING severity) ---
        blocking: List[str] = []
        for v in sv:
            blocking.append(f"INVALID_SUPPORT_RELATION: {v.detail}")
        for v in ov:
            blocking.append(f"OCCUPANCY_VIOLATION: {v.detail}")
        result.blocking       = blocking
        result.blocking_count = len(blocking)

        # --- Warning findings (WARNING severity) ---
        warnings: List[str] = []
        for f in rv:
            warnings.append(f"RELATIONSHIP_FAILURE: {f.detail}")
        for o in od:
            warnings.append(f"ORPHAN_OBJECT: {o.detail}")
        result.warning_count = len(warnings)

        result.findings = list(warnings) + list(blocking)
        result.findings.extend(plaus.findings)

        # --- geometry_valid: no BLOCKING violations ---
        result.geometry_valid = (len(sv) == 0 and len(ov) == 0)

        # --- semantic_validation_score ---
        if n_transforms == 0:
            sem_score = 0.0
        else:
            # Each relationship failure or orphan reduces score by 5 pp, floor 0
            rel_count    = len(rv)
            orphan_count = len(od)
            sem_score = max(0.0, 1.0 - (rel_count + orphan_count) * 0.05)
        result.semantic_validation_score = sem_score
        result.semantic_valid = sem_score >= SEMANTIC_SCORE_THRESHOLD

        # --- plausibility_valid ---
        result.plausibility_valid = plaus.plausibility_valid

        # --- production_ready ---
        result.production_ready = (
            result.geometry_valid
            and result.semantic_valid
            and result.plausibility_valid
            and n_transforms > 0
        )

        return result


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[SceneRealityValidator] = None
_lock = threading.Lock()


def get_scene_reality_validator() -> SceneRealityValidator:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = SceneRealityValidator()
    return _instance


def reset_scene_reality_validator_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
