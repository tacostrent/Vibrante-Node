"""
Workflow Review (Tier 10 — Workflow Packs & Production Blueprints)
==================================================================
Evaluates workflow execution quality across four dimensions:
  - Environment  — hierarchy structure and zone coverage
  - Cinematic    — lighting, camera, atmosphere quality
  - Production   — overall score against pack threshold
  - Execution    — operation success rate and rollback state

All critique is specific — "Execution successful" is never acceptable.
Every finding names the failing criterion.

DESIGN RULES:
  1. No bridge calls.  Advisory only.
  2. Deterministic — same inputs → same report.
  3. production_ready requires all dimensions pass threshold.
  4. Never raises.

Public API:
    WorkflowReviewResult
    WorkflowReview
    get_workflow_review()
    reset_workflow_review_for_tests()
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.runtime.workflows.workflow_pack import WorkflowPack

# ---------------------------------------------------------------------------
# Dimension weights
# ---------------------------------------------------------------------------

_WEIGHTS = {
    "environment":  0.25,
    "cinematic":    0.30,
    "production":   0.30,
    "execution":    0.15,
}

# Specific critique messages — never generic
_CRITIQUES: Dict[str, str] = {
    "no_phases":           "Workflow produced no phases — blueprint failed to generate.",
    "no_operations":       "Execution plan is empty — no operations were generated.",
    "rollback_performed":  "Execution was rolled back — scene may be in a partial state.",
    "low_score":           "Overall score is below production threshold — review findings before signing off.",
    "no_hero":             "Hero zone is empty — the scene has no primary focal point.",
    "flat_lighting":       "Lighting plan has no volumetric component — scene will appear flat.",
    "no_camera":           "No camera targets were generated — the scene has no defined viewpoint.",
    "high_fog":            "Fog density is heavy — background assets may be obscured.",
    "low_execution_rate":  "Operation success rate is below 80% — execution was unreliable.",
    "execution_failed":    "Execution reported errors — inspect the transaction log.",
}


@dataclass
class WorkflowReviewResult:
    """Result of a workflow quality review."""
    ok:               bool
    workflow:         str
    grade:            str        # A/B/C/D/F
    overall_score:    float
    production_ready: bool
    dimensions:       Dict[str, float] = field(default_factory=dict)
    findings:         List[str] = field(default_factory=list)
    recommendations:  List[str] = field(default_factory=list)
    review_summary:   str = ""
    review_id:        str = field(default_factory=lambda: str(uuid.uuid4()))
    reviewed_at:      float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok":               self.ok,
            "workflow":         self.workflow,
            "grade":            self.grade,
            "overall_score":    self.overall_score,
            "production_ready": self.production_ready,
            "dimensions":       self.dimensions,
            "findings":         self.findings,
            "recommendations":  self.recommendations,
            "review_summary":   self.review_summary,
            "review_id":        self.review_id,
            "reviewed_at":      self.reviewed_at,
        }


class WorkflowReview:
    """Evaluates workflow quality across four dimensions."""

    def __init__(self) -> None:
        self._review_count = 0
        self._lock = threading.Lock()

    # -----------------------------------------------------------------
    def review_execution(
        self, execution_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Evaluate the raw execution outcome."""
        ops        = execution_result.get("operations", [])
        status     = execution_result.get("status", "failed")
        errors     = execution_result.get("errors", [])
        phase_res  = execution_result.get("phase_results", [])

        ok_count = sum(1 for p in phase_res if p.get("status") == "ok")
        total    = max(len(phase_res), 1)
        success_rate = ok_count / total

        findings:       List[str] = []
        recommendations: List[str] = []

        if not ops:
            findings.append(_CRITIQUES["no_operations"])
        if status == "rolled_back":
            findings.append(_CRITIQUES["rollback_performed"])
        if errors:
            findings.append(_CRITIQUES["execution_failed"])
        if success_rate < 0.80:
            findings.append(_CRITIQUES["low_execution_rate"])

        if findings:
            recommendations.append(
                "Inspect the transaction log and retry with dry_run=True first."
            )

        score = (
            (0.6 if status == "committed" else 0.2) +
            success_rate * 0.4
        )
        return {
            "score":         min(score, 1.0),
            "status":        status,
            "success_rate":  success_rate,
            "findings":      findings,
            "recommendations": recommendations,
        }

    # -----------------------------------------------------------------
    def review_environment(self, blueprint: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate the environment / hierarchy phase."""
        phases    = blueprint.get("phases", [])
        phase_det = {p["phase_name"]: p for p in blueprint.get("phase_details", [])}
        findings:       List[str] = []
        recommendations: List[str] = []

        if not phases:
            findings.append(_CRITIQUES["no_phases"])
        if not blueprint.get("ok", False):
            findings.append("Blueprint is invalid — pack validation failed.")

        env_phase = phase_det.get("environment", {})
        env_ops   = env_phase.get("operations", [])
        if not env_ops:
            findings.append("Environment phase produced no operations.")

        score = 1.0 - (len(findings) * 0.25)
        score = max(0.0, min(score, 1.0))
        return {
            "score":          score,
            "phase_count":    len(phases),
            "env_op_count":   len(env_ops),
            "findings":       findings,
            "recommendations": recommendations,
        }

    # -----------------------------------------------------------------
    def review_cinematic_quality(self, pack: WorkflowPack) -> Dict[str, Any]:
        """Evaluate cinematic-specific quality criteria."""
        findings:       List[str] = []
        recommendations: List[str] = []

        # Lighting check
        if not pack.lighting_strategy.get("volumetric", True):
            findings.append(_CRITIQUES["flat_lighting"])
            recommendations.append(
                "Enable volumetric lighting in the pack's lighting_strategy."
            )

        # Camera check
        if not pack.camera_strategy.get("establishing_shot", True):
            findings.append(_CRITIQUES["no_camera"])
            recommendations.append(
                "Enable establishing_shot in the pack's camera_strategy."
            )

        # Atmosphere check
        fog = pack.atmosphere_strategy.get("fog_density", "medium")
        if fog == "heavy":
            findings.append(_CRITIQUES["high_fog"])
            recommendations.append(
                "Consider reducing fog_density to 'medium' for better background readability."
            )

        score = max(0.0, 1.0 - len(findings) * 0.20)
        return {
            "score":          score,
            "lighting_style": pack.lighting_strategy.get("style", ""),
            "camera_mode":    pack.camera_strategy.get("mode", ""),
            "fog_density":    fog,
            "findings":       findings,
            "recommendations": recommendations,
        }

    # -----------------------------------------------------------------
    def review_production_quality(
        self,
        pack:              WorkflowPack,
        overall_score:     float,
    ) -> Dict[str, Any]:
        """Evaluate whether the scene meets production threshold."""
        threshold = pack.review_strategy.get("production_threshold", 0.70)
        passed    = overall_score >= threshold
        findings: List[str] = []
        if not passed:
            findings.append(
                f"{_CRITIQUES['low_score']} "
                f"(got {overall_score:.2f}, required {threshold:.2f})"
            )
        return {
            "score":      overall_score,
            "threshold":  threshold,
            "passed":     passed,
            "findings":   findings,
        }

    # -----------------------------------------------------------------
    def generate_report(
        self,
        pack:             WorkflowPack,
        blueprint:        Dict[str, Any],
        execution_result: Dict[str, Any],
    ) -> WorkflowReviewResult:
        """Full integrated workflow review."""
        with self._lock:
            self._review_count += 1

        exec_dim = self.review_execution(execution_result)
        env_dim  = self.review_environment(blueprint)
        cine_dim = self.review_cinematic_quality(pack)

        # Weighted overall
        overall = (
            _WEIGHTS["execution"]   * exec_dim["score"] +
            _WEIGHTS["environment"] * env_dim["score"] +
            _WEIGHTS["cinematic"]   * cine_dim["score"]
        )
        # production_quality uses overall
        prod_dim = self.review_production_quality(pack, overall)
        overall  = overall * (1.0 - _WEIGHTS["production"]) + prod_dim["score"] * _WEIGHTS["production"]
        overall  = min(1.0, max(0.0, overall))

        # Aggregate findings
        findings: List[str] = (
            exec_dim["findings"] + env_dim["findings"] +
            cine_dim["findings"] + prod_dim["findings"]
        )
        recs: List[str] = (
            exec_dim.get("recommendations", []) +
            cine_dim.get("recommendations", [])
        )

        production_ready = prod_dim["passed"] and len(findings) == 0
        grade            = self._grade(overall)
        summary          = self._summary(pack.name, overall, grade, production_ready, findings)

        return WorkflowReviewResult(
            ok               = True,
            workflow         = pack.name,
            grade            = grade,
            overall_score    = overall,
            production_ready = production_ready,
            dimensions       = {
                "execution":   exec_dim["score"],
                "environment": env_dim["score"],
                "cinematic":   cine_dim["score"],
                "production":  prod_dim["score"],
            },
            findings         = findings,
            recommendations  = recs,
            review_summary   = summary,
        )

    # -----------------------------------------------------------------
    @staticmethod
    def _grade(score: float) -> str:
        if score >= 0.90:
            return "A"
        if score >= 0.80:
            return "B"
        if score >= 0.70:
            return "C"
        if score >= 0.60:
            return "D"
        return "F"

    @staticmethod
    def _summary(
        name: str, score: float, grade: str,
        ready: bool, findings: List[str]
    ) -> str:
        status = "meets production criteria" if ready else "does NOT meet production criteria"
        base   = f"Grade {grade} — overall {score:.2f}. Workflow '{name}' {status}."
        if findings:
            base += f" {len(findings)} finding(s) require attention."
        return base

    def stats(self) -> Dict[str, Any]:
        return {"review_count": self._review_count}


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[WorkflowReview] = None
_lock = threading.Lock()


def get_workflow_review() -> WorkflowReview:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = WorkflowReview()
    return _instance


def reset_workflow_review_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
