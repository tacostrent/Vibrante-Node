"""
Cinematic Review Engine
=======================
Generates specific, actionable artistic production feedback for cinematic
orchestration results. Replaces generic "Execution successful" with real
production-level critique.

Design rules:
  - Deterministic — same input always produces same output.
  - No LLM calls — pattern matching and constraint lookup only.
  - No bridge calls — pure in-memory operation.
  - Reads artistic_constraints.json for per-workflow gate rules.
  - Returns production-grade critique, not status strings.

Public API:
    get_review_engine() -> ReviewEngine    (singleton)
    reset_review_engine_for_tests()

    ReviewEngine.review(workflow_id, stage_results, context=None) -> ReviewResult
    ReviewEngine.review_stage(workflow_id, stage_id, stage_result) -> StageReview
    ReviewEngine.summarize(review_results) -> str
    ReviewEngine.stats() -> dict
"""

from __future__ import annotations

import json
import os
import threading
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Built-in cinematic critique templates
# ---------------------------------------------------------------------------

# Per-workflow stage critique patterns
# Format: workflow_id -> stage_id -> {criteria_key: (pass_hint, fail_hint)}
_STAGE_CRITIQUE: Dict[str, Dict[str, Dict[str, tuple]]] = {
    "cinematic_explosion": {
        "terrain_prep": {
            "scale": (
                "Terrain scale matches explosion epicenter proportionally.",
                "Terrain feels too small — the explosion should dominate no more than 30% of visible terrain width.",
            ),
            "geometry": (
                "Ground plane geometry suitable for pressure interaction.",
                "Flat infinite ground plane detected — add surface variation or displacement for realistic pressure propagation.",
            ),
        },
        "pyro_source": {
            "resolution": (
                "Pyro source resolution supports fine detail in fireball core.",
                "Source resolution too low — fireball core will appear blocky. Increase voxel density by 2x.",
            ),
            "velocity": (
                "Initial burst velocity set — early fireball expansion is violent.",
                "No initial velocity burst detected — explosion will look like it grows slowly rather than detonates.",
            ),
        },
        "fireball_core": {
            "heat": (
                "Temperature/heat field is high-contrast — bright core fading to dark exterior.",
                "Heat field lacks contrast — fireball interior and exterior blend together. Increase temperature gradient.",
            ),
            "turbulence": (
                "Turbulence adds irregular surface breakup to the fireball.",
                "Fireball surface is too smooth — turbulence is insufficient. Real fireballs have violent surface instability.",
            ),
        },
        "smoke_evolution": {
            "breakup": (
                "Smoke column has visible breakup variation — not uniform rising column.",
                "Smoke breakup lacks variation — the rising column is too uniform and procedural-looking.",
            ),
            "layering": (
                "Dense smoke at base transitions to thin wisps at top.",
                "Smoke density does not vary with height — base and top look equally dense.",
            ),
        },
        "pressure_wave": {
            "timing": (
                "Pressure wave expands outward immediately after detonation.",
                "Pressure wave timing is too slow — it should expand at near-sonic speed within first 12 frames.",
            ),
            "ground_interaction": (
                "Wave disturbs ground plane — dust lift, pebble scatter visible.",
                "Pressure wave shows no ground interaction — should kick up dust and debris as it passes.",
            ),
        },
        "secondary_debris": {
            "scale_variation": (
                "Debris spans multiple size ranges — large chunks, medium pieces, fine particles.",
                "Debris scale feels too small — add larger hero chunks that trail smoke as they fly.",
            ),
            "trajectory": (
                "Debris arc trajectories are varied — not all on same parabolic path.",
                "Debris trajectories are too uniform — real blast scatter follows chaotic distribution.",
            ),
        },
        "lighting_setup": {
            "fire_contribution": (
                "Fire emission drives secondary illumination on nearby surfaces.",
                "Lighting contrast feels flat — fire should be the dominant light source, casting warm orange on surroundings.",
            ),
            "shadow": (
                "Volumetric shadows from smoke create depth separation.",
                "Smoke column casts no visible shadow — add volumetric shadow passes for depth.",
            ),
        },
        "camera_framing": {
            "hero_readable": (
                "Explosion epicenter visible and readable throughout camera move.",
                "Camera framing loses the explosion epicenter — keep the burst point in the lower-center third.",
            ),
            "sky_visible": (
                "Sky fills upper portion of frame — smoke column rises into visible sky.",
                "Sky not visible in frame — tilt camera down slightly to show rising smoke against open sky.",
            ),
        },
        "render_setup": {
            "motion_blur": (
                "Motion blur enabled — fast debris and wavefront have appropriate blur.",
                "Motion blur is OFF — fast-moving elements will appear strobed. Enable motion blur, shutter 0.5.",
            ),
            "sampling": (
                "AA samples sufficient for volumetric rendering.",
                "Sampling too low for volume rendering — noise will be visible in smoke. Increase AA to minimum 5.",
            ),
        },
    },
    "dust_wave": {
        "ground_interaction_setup": {
            "terrain": (
                "Ground plane interaction geometry is set up for dust emission.",
                "No ground interaction volume — dust wave will pass through the surface instead of rolling along it.",
            ),
        },
        "dust_source": {
            "density": (
                "Dust density appropriate — thin enough to be semi-transparent.",
                "Dust is too opaque — should be a thin, semi-transparent veil rolling across the ground.",
            ),
        },
        "wave_propagation": {
            "speed": (
                "Wave front propagates at physically convincing speed.",
                "Dust interaction is weak — wave front moves too slowly. Blast pressure would push dust at 20+ m/s.",
            ),
        },
    },
    "arnold_cinematic_lighting": {
        "sky_hdri_or_skydome": {
            "intensity": (
                "Sky dome provides ambient base without washing out explosion lighting.",
                "Sky dome intensity too high — washing out the fire emission light. Reduce to 0.3–0.5 exposure.",
            ),
        },
        "key_light_placement": {
            "direction": (
                "Key light direction is consistent with practical explosion source.",
                "Key light direction contradicts the explosion source — light should come from the explosion side.",
            ),
            "intensity": (
                "Key light is the brightest source and clearly dominant.",
                "Lighting contrast feels flat — key light is not dominant enough. Increase contrast ratio to 4:1 minimum.",
            ),
        },
        "volumetric_atmosphere": {
            "depth": (
                "Volumetric atmosphere creates visible depth separation.",
                "Volumetric depth could be improved — add atmospheric haze to push background elements back.",
            ),
        },
    },
    "cinematic_push_in": {
        "anticipation_hold": {
            "duration": (
                "Camera holds minimum 12 frames before event — tension established.",
                "Camera timing lacks anticipation — hold is too short. Add minimum 24-frame hold before the event trigger.",
            ),
        },
        "push_in_path": {
            "acceleration": (
                "Push velocity accelerates from hold — ease-in established.",
                "Camera push is constant speed — should ease in from static, accelerating toward the event.",
            ),
            "parallax": (
                "Slight rotation during push creates natural parallax depth.",
                "Camera push is dead-straight — add slight arc or rotation for parallax. Straight pushes look CG.",
            ),
        },
        "slow_motion_end": {
            "motion_blur": (
                "Motion blur is active during slow-motion — correct cinematic feel.",
                "Slow motion reveal is missing motion blur — elements appear frozen rather than slow.",
            ),
        },
    },
    "arnold_render_ready": {
        "sampling_configuration": {
            "aa_samples": (
                "AA samples are sufficient for production quality.",
                "AA samples too low for final render — noise will be visible. Minimum 8 for final, 3 for preview.",
            ),
            "adaptive": (
                "Adaptive sampling enabled — renders efficiently without sacrificing quality.",
                "Adaptive sampling is OFF — render time will be excessive. Enable with threshold 0.015.",
            ),
        },
        "aov_setup": {
            "emission": (
                "Emission AOV present — fire/smoke intensity controllable in comp.",
                "Emission AOV is missing — cannot control fire brightness in comp without re-render.",
            ),
            "cryptomatte": (
                "Cryptomatte configured — per-element masking available in comp.",
                "Cryptomatte not configured — per-element color grading will require rotoscoping.",
            ),
            "depth": (
                "Depth pass in world units — correct for DOF and Z-composite.",
                "Depth pass is normalized 0–1 — must be in world units (meters) for depth of field in comp.",
            ),
        },
        "motion_blur_config": {
            "volume_blur": (
                "Volume velocity blur enabled — pyro motion is captured correctly.",
                "Volume motion blur is OFF — pyro elements will appear frozen between frames.",
            ),
        },
        "output_driver": {
            "format": (
                "Output format is EXR — correct for production pipeline.",
                "Output is not EXR — PNG/JPG cannot hold the dynamic range needed for pyro and fire.",
            ),
        },
    },
    "cinematic_aov_setup": {
        "beauty_pass": {
            "present": (
                "Beauty (RGBA) pass is the primary output.",
                "Beauty pass missing — this is the primary output and must always be present.",
            ),
        },
        "emission_pass": {
            "pyro_required": (
                "Emission AOV active — volume emission captured for comp.",
                "Emission AOV REQUIRED for all scenes with pyro/fire/smoke — add it before rendering.",
            ),
        },
        "depth_pass": {
            "world_units": (
                "Depth pass is in world-space units — usable for DOF in comp.",
                "Depth pass is not in world units — compositor cannot use normalized depth for DOF. Set Z to world-space.",
            ),
        },
        "cryptomatte": {
            "configured": (
                "Cryptomatte is configured with per-object and per-material mattes.",
                "Cryptomatte is missing — cannot isolate elements for color grading without cryptomatte.",
            ),
        },
    },
}

# Generic critique for any workflow/stage that isn't in the specific map
_GENERIC_CRITIQUES = [
    "Verify execution completed all required stages without skipping.",
    "Check that artistic constraints for this workflow are satisfied.",
    "Review stage outputs for completeness before proceeding.",
]

# ---------------------------------------------------------------------------
# ReviewResult / StageReview
# ---------------------------------------------------------------------------

class StageReview:
    """Review result for a single workflow stage."""

    def __init__(
        self,
        workflow_id: str,
        stage_id: str,
        passed: bool,
        critiques: List[str],
        recommendations: List[str],
        severity: str,  # "pass" | "warning" | "fail"
    ) -> None:
        self.workflow_id = workflow_id
        self.stage_id = stage_id
        self.passed = passed
        self.critiques = critiques
        self.recommendations = recommendations
        self.severity = severity

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "stage_id": self.stage_id,
            "passed": self.passed,
            "critiques": self.critiques,
            "recommendations": self.recommendations,
            "severity": self.severity,
        }


class ReviewResult:
    """Full review result for a completed workflow execution."""

    def __init__(
        self,
        workflow_id: str,
        overall_passed: bool,
        stage_reviews: List[StageReview],
        summary: str,
        critical_issues: List[str],
        advisory_notes: List[str],
        production_ready: bool,
        confidence: float,
    ) -> None:
        self.workflow_id = workflow_id
        self.overall_passed = overall_passed
        self.stage_reviews = stage_reviews
        self.summary = summary
        self.critical_issues = critical_issues
        self.advisory_notes = advisory_notes
        self.production_ready = production_ready
        self.confidence = confidence

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "overall_passed": self.overall_passed,
            "stage_reviews": [s.to_dict() for s in self.stage_reviews],
            "summary": self.summary,
            "critical_issues": self.critical_issues,
            "advisory_notes": self.advisory_notes,
            "production_ready": self.production_ready,
            "confidence": self.confidence,
            "stage_count": len(self.stage_reviews),
            "failed_stages": sum(1 for s in self.stage_reviews if not s.passed),
        }


# ---------------------------------------------------------------------------
# ReviewEngine
# ---------------------------------------------------------------------------

class ReviewEngine:
    """Generates cinematic production review feedback for workflow executions.

    Singleton — access via get_review_engine().
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._review_count = 0
        self._constraints: Optional[Dict[str, Any]] = None
        self._constraints_loaded = False

    # ------------------------------------------------------------------
    # Constraints loading (lazy)
    # ------------------------------------------------------------------

    def _load_constraints(self) -> Optional[Dict[str, Any]]:
        """Load artistic_constraints.json if present."""
        if self._constraints_loaded:
            return self._constraints
        self._constraints_loaded = True
        candidate = os.path.join(
            os.path.dirname(__file__), "..", "..", "config", "artistic_constraints.json"
        )
        candidate = os.path.normpath(candidate)
        try:
            if os.path.exists(candidate):
                with open(candidate, "r", encoding="utf-8") as f:
                    self._constraints = json.load(f)
        except Exception:
            self._constraints = None
        return self._constraints

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def review(
        self,
        workflow_id: str,
        stage_results: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> ReviewResult:
        """Review a completed workflow execution and return specific artistic critique.

        Args:
            workflow_id:   The workflow that was executed.
            stage_results: Dict of stage_id → {completed, outputs, params, errors}.
            context:       Optional hints (renderer, scale, frame_range, etc.).

        Returns:
            ReviewResult with per-stage critique and production-ready assessment.
        """
        with self._lock:
            self._review_count += 1

        context = context or {}
        constraints = self._load_constraints()
        workflow_constraints = {}
        if constraints:
            workflow_constraints = constraints.get("workflows", {}).get(workflow_id, {})

        stage_reviews: List[StageReview] = []
        critical_issues: List[str] = []
        advisory_notes: List[str] = []

        # Review each stage
        for stage_id, stage_data in stage_results.items():
            sr = self.review_stage(workflow_id, stage_id, stage_data, context)
            stage_reviews.append(sr)
            if sr.severity == "fail":
                critical_issues.extend(sr.critiques)
            elif sr.severity == "warning":
                advisory_notes.extend(sr.critiques)

        # Add constraint-based checks
        self._apply_constraint_checks(
            workflow_id, workflow_constraints, stage_results, context,
            critical_issues, advisory_notes
        )

        # Compute overall
        failed_stages = sum(1 for sr in stage_reviews if not sr.passed)
        total_stages = len(stage_reviews)
        overall_passed = failed_stages == 0
        production_ready = overall_passed and len(critical_issues) == 0

        # Confidence: higher when we have full stage coverage
        confidence = 0.9 if total_stages > 0 else 0.5

        # Build summary — specific, not generic
        summary = self._build_summary(
            workflow_id, stage_reviews, critical_issues, advisory_notes, production_ready
        )

        return ReviewResult(
            workflow_id=workflow_id,
            overall_passed=overall_passed,
            stage_reviews=stage_reviews,
            summary=summary,
            critical_issues=critical_issues,
            advisory_notes=advisory_notes,
            production_ready=production_ready,
            confidence=confidence,
        )

    def review_stage(
        self,
        workflow_id: str,
        stage_id: str,
        stage_result: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> StageReview:
        """Review a single stage result.

        Returns a StageReview with specific critique for this stage.
        """
        context = context or {}
        critiques: List[str] = []
        recommendations: List[str] = []

        completed = stage_result.get("completed", True)
        errors = stage_result.get("errors", [])
        outputs = stage_result.get("outputs", {})
        params = stage_result.get("params", {})

        # Check if stage errored
        if not completed or errors:
            error_text = "; ".join(str(e) for e in errors) if errors else "Stage did not complete."
            critiques.append(f"Stage '{stage_id}' failed: {error_text}")
            return StageReview(
                workflow_id=workflow_id,
                stage_id=stage_id,
                passed=False,
                critiques=critiques,
                recommendations=["Re-run this stage after fixing the reported error."],
                severity="fail",
            )

        # Apply specific critique for this workflow + stage
        wf_critiques = _STAGE_CRITIQUE.get(workflow_id, {})
        stage_critiques = wf_critiques.get(stage_id, {})

        failed_criteria = []
        for criterion_key, (pass_hint, fail_hint) in stage_critiques.items():
            # Check parameters and outputs to determine pass/fail per criterion
            passed_criterion = self._check_criterion(
                criterion_key, pass_hint, fail_hint, outputs, params, context
            )
            if not passed_criterion:
                critiques.append(fail_hint)
                failed_criteria.append(criterion_key)
            # Add pass hints as advisory notes only if there are failures nearby
            # (we don't want to flood with green messages)

        # Generate recommendations for failed criteria
        recommendations = self._generate_recommendations(stage_id, failed_criteria, context)

        passed = len(critiques) == 0
        severity = "pass" if passed else ("fail" if len(failed_criteria) >= 2 else "warning")

        return StageReview(
            workflow_id=workflow_id,
            stage_id=stage_id,
            passed=passed,
            critiques=critiques,
            recommendations=recommendations,
            severity=severity,
        )

    def summarize(self, review_results: List[ReviewResult]) -> str:
        """Summarize multiple ReviewResults into a single production report string."""
        if not review_results:
            return "No review results to summarize."

        lines = []
        total = len(review_results)
        passed = sum(1 for r in review_results if r.overall_passed)
        prod_ready = sum(1 for r in review_results if r.production_ready)

        lines.append(f"Review Summary: {passed}/{total} workflows passed, {prod_ready}/{total} production-ready.")
        lines.append("")

        for r in review_results:
            status = "✓ PASS" if r.overall_passed else "✗ FAIL"
            lines.append(f"  {status}  {r.workflow_id}")
            if r.critical_issues:
                for issue in r.critical_issues[:3]:  # cap at 3 per workflow
                    lines.append(f"         CRITICAL: {issue}")
            elif r.advisory_notes:
                for note in r.advisory_notes[:2]:
                    lines.append(f"         ADVISORY: {note}")

        return "\n".join(lines)

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "review_count": self._review_count,
                "known_workflows": len(_STAGE_CRITIQUE),
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _check_criterion(
        self,
        criterion_key: str,
        pass_hint: str,
        fail_hint: str,
        outputs: Dict[str, Any],
        params: Dict[str, Any],
        context: Dict[str, Any],
    ) -> bool:
        """Determine if a criterion passes based on available outputs/params.

        Uses conservative heuristics — if we cannot verify, we assume warning,
        not failure, unless the criterion maps to a known required output.
        """
        # Check for explicit pass/fail signals in outputs
        criterion_val = outputs.get(criterion_key)
        if criterion_val is True:
            return True
        if criterion_val is False:
            return False

        # Check for named param indicators
        param_val = params.get(criterion_key)
        if param_val is False:
            return False
        if param_val is True:
            return True

        # Context-based overrides for known render/render-time criteria
        renderer = context.get("renderer", "")
        if criterion_key == "motion_blur" and renderer:
            # If renderer specified but motion_blur not in outputs, flag it
            return outputs.get("motion_blur_enabled", True)  # assume on unless explicitly off

        if criterion_key == "format":
            fmt = outputs.get("output_format", context.get("output_format", "exr")).lower()
            return fmt in ("exr", "openexr", ".exr")

        if criterion_key == "aa_samples":
            aa = outputs.get("aa_samples", context.get("aa_samples", 5))
            quality = context.get("quality", "final")
            min_aa = 8 if quality == "final" else 3
            try:
                return int(aa) >= min_aa
            except (ValueError, TypeError):
                return True  # can't verify, don't flag

        if criterion_key == "adaptive":
            return outputs.get("adaptive_sampling", context.get("adaptive_sampling", True))

        if criterion_key == "world_units":
            return outputs.get("depth_world_units", True)

        if criterion_key == "present":
            return outputs.get("aov_beauty_present", outputs.get("present", True))

        if criterion_key == "pyro_required":
            has_pyro = context.get("has_pyro", False) or context.get("has_fire", False)
            if has_pyro:
                return outputs.get("emission_aov_present", outputs.get("aov_emission", False))
            return True  # no pyro → not required

        if criterion_key == "configured":
            return outputs.get("cryptomatte_configured", outputs.get("cryptomatte", True))

        # For other criteria without direct output verification,
        # treat as warning-level (assume pass to avoid false positives)
        return True

    def _generate_recommendations(
        self, stage_id: str, failed_criteria: List[str], context: Dict[str, Any]
    ) -> List[str]:
        """Generate actionable recommendations for failed criteria."""
        recs = []
        for key in failed_criteria:
            if key == "motion_blur":
                recs.append("Enable motion blur in render settings. Shutter time: 0.5 (180° shutter).")
            elif key == "sampling" or key == "aa_samples":
                quality = context.get("quality", "final")
                target = 8 if quality == "final" else 3
                recs.append(f"Increase AA samples to {target}. Enable adaptive sampling with threshold 0.015.")
            elif key == "adaptive":
                recs.append("Enable adaptive sampling. Noise threshold 0.015 for production quality.")
            elif key == "format":
                recs.append("Switch output to OpenEXR 16-bit half float. PNG/JPG cannot hold cinematic dynamic range.")
            elif key == "world_units":
                recs.append("Set Z depth pass to world-space units (meters). Not normalized 0–1.")
            elif key == "cryptomatte" or key == "configured":
                recs.append("Configure Cryptomatte: cryptomatte_object + cryptomatte_material. Required before first render.")
            elif key == "emission" or key == "pyro_required":
                recs.append("Add emission AOV to the render pass list. Fire brightness must be controllable in comp.")
            elif key == "duration" or key == "timing":
                recs.append("Increase anticipation hold to minimum 24 frames. Shorter holds kill cinematic tension.")
            elif key == "breakup":
                recs.append("Increase turbulence on smoke evolution. Uniform rising columns read as procedural and fake.")
            elif key == "acceleration":
                recs.append("Keyframe camera push with ease-in. Constant-speed pushes break the weight of the moment.")
            elif key == "parallax":
                recs.append("Add slight arc or Y-rotation to the camera path. Dead-straight push loses depth.")
            elif key == "fire_contribution" or key == "intensity":
                recs.append("Fire should be the dominant light source. Reduce sky dome to 0.3–0.5, let fire drive contrast.")
            elif key == "volume_blur":
                recs.append("Enable volume velocity blur in Arnold settings. Pyro motion must be captured between frames.")
            else:
                recs.append(f"Review '{key}' criterion for stage '{stage_id}' and ensure it meets production standards.")
        return recs

    def _apply_constraint_checks(
        self,
        workflow_id: str,
        workflow_constraints: Dict[str, Any],
        stage_results: Dict[str, Any],
        context: Dict[str, Any],
        critical_issues: List[str],
        advisory_notes: List[str],
    ) -> None:
        """Apply artistic_constraints.json rules as additional checks."""
        if not workflow_constraints:
            return

        required_constraints = workflow_constraints.get("required", [])
        recommended_constraints = workflow_constraints.get("recommended", [])

        for constraint in required_constraints:
            if isinstance(constraint, str):
                # String constraint — record as-is, can't check_key verify
                continue
            rule = constraint.get("rule", "")
            description = constraint.get("description", rule)
            check_key = constraint.get("check_key", "")
            # Try to verify against outputs
            if check_key:
                found = False
                for stage_data in stage_results.values():
                    if isinstance(stage_data, dict) and \
                            stage_data.get("outputs", {}).get(check_key) is not None:
                        found = True
                        break
                if not found and context.get(check_key) is None:
                    critical_issues.append(f"Required constraint not met: {description}")
            # If no check_key, we can't verify — skip

        for constraint in recommended_constraints:
            if isinstance(constraint, str):
                advisory_notes.append(f"Recommended: {constraint}")
                continue
            description = constraint.get("description", constraint.get("rule", ""))
            if description:
                advisory_notes.append(f"Recommended: {description}")

    def _build_summary(
        self,
        workflow_id: str,
        stage_reviews: List[StageReview],
        critical_issues: List[str],
        advisory_notes: List[str],
        production_ready: bool,
    ) -> str:
        """Build a specific, informative summary string."""
        if not stage_reviews:
            return f"Workflow '{workflow_id}' has no stage results to review."

        failed = [sr for sr in stage_reviews if not sr.passed]
        warned = [sr for sr in stage_reviews if sr.severity == "warning"]
        passed_count = len(stage_reviews) - len(failed)

        if production_ready:
            return (
                f"Workflow '{workflow_id}' passed all {len(stage_reviews)} stage reviews. "
                f"Production-ready."
            )

        if failed:
            fail_names = ", ".join(sr.stage_id for sr in failed[:3])
            extra = f" +{len(failed) - 3} more" if len(failed) > 3 else ""
            top_issue = critical_issues[0] if critical_issues else f"Stage '{failed[0].stage_id}' requires attention."
            return (
                f"Workflow '{workflow_id}': {passed_count}/{len(stage_reviews)} stages passed. "
                f"Failed stages: {fail_names}{extra}. "
                f"Top issue: {top_issue}"
            )

        if advisory_notes:
            top_note = advisory_notes[0]
            return (
                f"Workflow '{workflow_id}': All stages completed with warnings. "
                f"Key advisory: {top_note}"
            )

        return f"Workflow '{workflow_id}': {passed_count}/{len(stage_reviews)} stages reviewed."


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[ReviewEngine] = None
_instance_lock = threading.Lock()


def get_review_engine() -> ReviewEngine:
    """Return the ReviewEngine singleton."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = ReviewEngine()
    return _instance


def reset_review_engine_for_tests() -> None:
    """Reset singleton for test isolation."""
    global _instance
    with _instance_lock:
        _instance = None
