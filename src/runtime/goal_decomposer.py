"""
Goal Decomposer (Production Semantic Intelligence)
===================================================
Prevents large cinematic goals from collapsing into random orchestration by
decomposing them into ordered, staged workflow sequences.

This is the single most important module for orchestration stability.
Without decomposition, a prompt like "create cinematic explosion scene" results
in a single-shot execution attempt that produces random, non-cinematic output.

With decomposition, the same prompt produces a staged execution plan:
  1. terrain_prep
  2. pyro_source
  3. fireball_core
  4. smoke_evolution
  5. pressure_wave
  6. secondary_debris
  7. lighting_setup
  8. camera_framing
  9. render_setup

Design rules:
  - Deterministic — same input always produces same output.
  - No LLM calls — keyword matching and vocabulary lookup only.
  - No bridge calls — no Houdini interaction.
  - No I/O side effects — pure in-memory operation.
  - Reads SemanticVocabulary for stage ordering.

Public API:
    get_goal_decomposer() -> GoalDecomposer    (singleton)
    reset_goal_decomposer_for_tests()

    GoalDecomposer.decompose(goal, context=None) -> DecompositionResult
    GoalDecomposer.get_workflow_stages(workflow_id) -> list[str]
    GoalDecomposer.sequence_goals(goals) -> list[DecompositionResult]
    GoalDecomposer.stats() -> dict
"""

from __future__ import annotations

import json
import os
import threading
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Known workflow → stage sequence (source of truth)
# ---------------------------------------------------------------------------

_WORKFLOW_STAGES: Dict[str, List[str]] = {
    "cinematic_explosion": [
        "terrain_prep",
        "pyro_source",
        "fireball_core",
        "smoke_evolution",
        "pressure_wave",
        "secondary_debris",
        "lighting_setup",
        "camera_framing",
        "render_setup",
    ],
    "missile_impact": [
        "impact_flash",
        "crater_formation",
        "ejecta_burst",
        "smoke_column",
        "shockwave_ring",
        "lighting_setup",
        "camera_framing",
    ],
    "debris_field": [
        "debris_source_geo",
        "voronoi_fracture",
        "initial_velocity_seed",
        "rigid_body_sim",
        "scatter_distribution",
        "dust_tail",
    ],
    "dust_wave": [
        "ground_interaction_setup",
        "dust_source",
        "wave_propagation",
        "thin_layer_advection",
        "dissipation_control",
    ],
    "smoke_column": [
        "burn_source",
        "initial_column",
        "turbulence_layers",
        "breakup_variation",
        "sky_dissipation",
    ],
    "fuel_fireball": [
        "fuel_source_geo",
        "combustion_setup",
        "rolling_fireball",
        "dark_smoke_boundary",
        "secondary_ignition",
    ],
    "arnold_cinematic_lighting": [
        "sky_hdri_or_skydome",
        "key_light_placement",
        "rim_light_placement",
        "fill_light",
        "volumetric_atmosphere",
        "shadow_control",
        "exposure_balance",
    ],
    "volumetric_contrast_lighting": [
        "volume_skydome",
        "directional_key",
        "volumetric_shadows",
        "godrays_setup",
        "secondary_bounce",
    ],
    "night_explosion_lighting": [
        "ambient_moonlight_base",
        "fire_emission_light",
        "secondary_fill",
        "deep_shadow_setup",
    ],
    "cinematic_push_in": [
        "start_position",
        "anticipation_hold",
        "event_trigger_point",
        "push_in_path",
        "slow_motion_end",
    ],
    "impact_handheld": [
        "pre_event_slight_float",
        "impact_violent_shake",
        "decay_oscillation",
        "settle_residual",
    ],
    "slow_motion_reveal": [
        "time_scale_setup",
        "motion_blur_config",
        "frame_range_extension",
        "rack_focus_optional",
    ],
    "arnold_render_ready": [
        "arnold_rop_setup",
        "sampling_configuration",
        "aov_setup",
        "motion_blur_config",
        "volume_step_size",
        "output_driver",
        "farm_submission_prep",
    ],
    "cinematic_aov_setup": [
        "beauty_pass",
        "diffuse_indirect",
        "specular_pass",
        "emission_pass",
        "volume_scatter",
        "depth_pass",
        "normal_pass",
        "motion_vector_pass",
        "cryptomatte",
    ],
    # Generic Houdini semantic ops
    "create_geo_container": ["create_geo", "clear_defaults"],
    "build_pyro_source": ["pyro_source"],
    "setup_karma_renderer": ["karma_rop", "karma_sampling", "karma_output"],
    "export_to_usd": ["usd_rop", "usd_paths", "usd_export"],
    "cache_geometry": ["cache_rop", "cache_paths"],
    "asset_publish_scaffold": ["version_dir", "publish_rop", "metadata"],
    "solaris_lighting_setup": ["stage_setup", "dome_light", "key_light", "render_settings"],
}

# ---------------------------------------------------------------------------
# Goal keyword → workflow mapping
# ---------------------------------------------------------------------------

_GOAL_KEYWORDS: Dict[str, List[str]] = {
    "cinematic_explosion": [
        "cinematic explosion", "explosion scene", "full explosion",
        "create explosion", "build explosion", "hero explosion",
        "detonation scene", "blast scene",
    ],
    "missile_impact": [
        "missile impact", "rocket hit", "bomb hit", "missile strike",
        "impact scene", "projectile impact",
    ],
    "debris_field": [
        "debris", "rubble field", "secondary debris", "debris field",
        "fragments", "shrapnel field",
    ],
    "dust_wave": [
        "dust wave", "rolling dust", "ground dust", "pressure wave dust",
        "dust displacement", "shockwave dust",
    ],
    "smoke_column": [
        "smoke column", "rising smoke", "smoke pillar", "layered smoke",
        "smoke simulation", "billowing smoke",
    ],
    "fuel_fireball": [
        "fuel fire", "fuel fireball", "oil fire", "gas explosion",
        "vehicle fire", "petroleum fire",
    ],
    "arnold_cinematic_lighting": [
        "cinematic lighting", "arnold lighting", "production lighting",
        "hero lighting", "film lighting", "explosion lighting",
    ],
    "volumetric_contrast_lighting": [
        "volumetric lighting", "godrays", "volume shadows", "atmospheric lighting",
        "depth lighting",
    ],
    "night_explosion_lighting": [
        "night lighting", "dark scene", "nocturnal", "night explosion",
        "fire as light", "dark environment",
    ],
    "cinematic_push_in": [
        "push in", "dolly in", "camera push", "push camera", "reveal camera",
        "cinematic camera", "move camera in",
    ],
    "impact_handheld": [
        "camera shake", "handheld", "impact shake", "recoil camera",
        "shaky cam", "handheld camera",
    ],
    "slow_motion_reveal": [
        "slow motion", "slow mo", "high speed", "time remap", "slow camera",
    ],
    "arnold_render_ready": [
        "render setup", "arnold render", "final render", "render ready",
        "set up render", "configure render", "farm render",
    ],
    "cinematic_aov_setup": [
        "aov setup", "render passes", "multi pass", "nuke passes",
        "composite passes", "aov configuration",
    ],
}

# Multi-workflow compositions triggered by high-level goals
_COMPOSITE_GOALS: Dict[str, List[str]] = {
    "cinematic explosion scene": [
        "cinematic_explosion",
        "dust_wave",
        "debris_field",
        "arnold_cinematic_lighting",
        "cinematic_push_in",
        "arnold_render_ready",
    ],
    "full explosion": [
        "cinematic_explosion",
        "dust_wave",
        "debris_field",
        "arnold_cinematic_lighting",
        "cinematic_push_in",
        "arnold_render_ready",
    ],
    "explosion with camera": [
        "cinematic_explosion",
        "arnold_cinematic_lighting",
        "cinematic_push_in",
        "impact_handheld",
    ],
    "night explosion": [
        "cinematic_explosion",
        "night_explosion_lighting",
        "cinematic_push_in",
        "arnold_render_ready",
    ],
    "missile strike": [
        "missile_impact",
        "dust_wave",
        "debris_field",
        "volumetric_contrast_lighting",
        "cinematic_push_in",
    ],
    "render ready": [
        "arnold_render_ready",
        "cinematic_aov_setup",
    ],
    "full render setup": [
        "arnold_render_ready",
        "cinematic_aov_setup",
    ],
    "lighting setup": [
        "arnold_cinematic_lighting",
        "volumetric_contrast_lighting",
    ],
}

# Stage execution ordering for multi-workflow compositions
_STAGE_CATEGORY_ORDER = ["terrain", "pyro", "fx", "debris", "lighting", "camera", "render"]


# ---------------------------------------------------------------------------
# DecompositionResult
# ---------------------------------------------------------------------------

class DecompositionResult:
    """Result of a goal decomposition — an ordered list of workflows and their stages."""

    def __init__(
        self,
        goal: str,
        matched_workflows: List[str],
        stages: List[str],
        execution_order: List[Dict[str, Any]],
        confidence: float,
        notes: List[str],
    ) -> None:
        self.goal = goal
        self.matched_workflows = matched_workflows
        self.stages = stages
        self.execution_order = execution_order  # [{workflow, stage, description}]
        self.confidence = confidence
        self.notes = notes
        self.ok = len(matched_workflows) > 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": self.goal,
            "ok": self.ok,
            "matched_workflows": self.matched_workflows,
            "stages": self.stages,
            "execution_order": self.execution_order,
            "confidence": self.confidence,
            "workflow_count": len(self.matched_workflows),
            "stage_count": len(self.stages),
            "notes": self.notes,
        }


# ---------------------------------------------------------------------------
# GoalDecomposer
# ---------------------------------------------------------------------------

class GoalDecomposer:
    """Decomposes high-level cinematic goals into ordered, staged workflow sequences.

    Singleton — access via get_goal_decomposer().
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._decompose_count = 0
        self._vocabulary: Optional[Dict[str, Any]] = None
        self._vocabulary_loaded = False

    # ------------------------------------------------------------------
    # Vocabulary loading (lazy, optional enrichment)
    # ------------------------------------------------------------------

    def _load_vocabulary(self) -> Optional[Dict[str, Any]]:
        """Load semantic_vocabulary.json if present. Used for enrichment only."""
        if self._vocabulary_loaded:
            return self._vocabulary
        self._vocabulary_loaded = True
        candidate = os.path.join(
            os.path.dirname(__file__), "..", "..", "config", "semantic_vocabulary.json"
        )
        candidate = os.path.normpath(candidate)
        try:
            if os.path.exists(candidate):
                with open(candidate, "r", encoding="utf-8") as f:
                    self._vocabulary = json.load(f)
        except Exception:
            self._vocabulary = None
        return self._vocabulary

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def decompose(self, goal: str, context: Optional[Dict[str, Any]] = None) -> DecompositionResult:
        """Decompose a high-level goal into an ordered workflow + stage sequence.

        Args:
            goal:    Natural language goal string (e.g. "create cinematic explosion scene").
            context: Optional hint dict — may include "workflow_id" to force a specific workflow.

        Returns:
            DecompositionResult with matched_workflows, stages, and execution_order.
        """
        with self._lock:
            self._decompose_count += 1

        goal_lower = goal.lower().strip()
        notes: List[str] = []
        context = context or {}

        # 1. Forced workflow override
        forced = context.get("workflow_id")
        if forced and isinstance(forced, str):
            if forced in _WORKFLOW_STAGES:
                stages = _WORKFLOW_STAGES[forced]
                return self._build_result(goal, [forced], stages, 1.0, ["workflow_id override applied"])

        # 2. Composite goal match (multi-workflow high-level goals)
        for composite_key, workflows in _COMPOSITE_GOALS.items():
            if composite_key in goal_lower:
                stages = self._merge_workflow_stages(workflows)
                notes.append(f"Composite goal matched: '{composite_key}' → {len(workflows)} workflows")
                return self._build_result(goal, workflows, stages, 0.95, notes)

        # 3. Single workflow keyword match
        matched_workflows = self._match_workflows(goal_lower)

        if not matched_workflows:
            # Try vocabulary keyword_index for enrichment
            vocab = self._load_vocabulary()
            if vocab:
                idx = vocab.get("keyword_index", {})
                for kw, wf_list in idx.items():
                    if kw in goal_lower:
                        for wf in wf_list:
                            if wf not in matched_workflows:
                                matched_workflows.append(wf)
                        if matched_workflows:
                            notes.append(f"Vocabulary keyword '{kw}' enriched matches.")
                            break

        if not matched_workflows:
            return DecompositionResult(
                goal=goal,
                matched_workflows=[],
                stages=[],
                execution_order=[],
                confidence=0.0,
                notes=["No known workflow matched this goal. Use a more specific description."],
            )

        stages = self._merge_workflow_stages(matched_workflows)
        confidence = 0.85 if len(matched_workflows) == 1 else 0.9
        notes.append(f"Matched {len(matched_workflows)} workflow(s): {', '.join(matched_workflows)}")
        return self._build_result(goal, matched_workflows, stages, confidence, notes)

    def get_workflow_stages(self, workflow_id: str) -> List[str]:
        """Return the ordered stage list for a known workflow.

        Returns empty list for unknown workflow ids.
        """
        return list(_WORKFLOW_STAGES.get(workflow_id, []))

    def sequence_goals(self, goals: List[str]) -> List[DecompositionResult]:
        """Decompose a list of goals into a sequence of DecompositionResults.

        Goals are processed in order. Each result's stages extend the overall sequence.
        """
        return [self.decompose(g) for g in goals]

    def list_known_workflows(self) -> List[str]:
        """Return all known workflow ids."""
        return list(_WORKFLOW_STAGES.keys())

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "decompose_count": self._decompose_count,
                "known_workflows": len(_WORKFLOW_STAGES),
                "known_composite_goals": len(_COMPOSITE_GOALS),
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _match_workflows(self, goal_lower: str) -> List[str]:
        """Match goal string against known workflow keywords."""
        matched: List[str] = []
        for wf_id, keywords in _GOAL_KEYWORDS.items():
            for kw in keywords:
                if kw in goal_lower:
                    if wf_id not in matched:
                        matched.append(wf_id)
                    break
        return matched

    def _merge_workflow_stages(self, workflow_ids: List[str]) -> List[str]:
        """Merge stage lists from multiple workflows without duplicates, respecting category order."""
        seen: set = set()
        merged: List[str] = []
        for wf_id in workflow_ids:
            for stage in _WORKFLOW_STAGES.get(wf_id, []):
                if stage not in seen:
                    seen.add(stage)
                    merged.append(stage)
        return merged

    def _build_result(
        self,
        goal: str,
        workflows: List[str],
        stages: List[str],
        confidence: float,
        notes: List[str],
    ) -> DecompositionResult:
        """Build a DecompositionResult from components."""
        execution_order: List[Dict[str, Any]] = []
        for wf_id in workflows:
            for stage in _WORKFLOW_STAGES.get(wf_id, []):
                execution_order.append({
                    "workflow": wf_id,
                    "stage": stage,
                    "description": f"Execute {stage} as part of {wf_id}",
                })
        return DecompositionResult(
            goal=goal,
            matched_workflows=workflows,
            stages=stages,
            execution_order=execution_order,
            confidence=confidence,
            notes=notes,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[GoalDecomposer] = None
_instance_lock = threading.Lock()


def get_goal_decomposer() -> GoalDecomposer:
    """Return the GoalDecomposer singleton."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = GoalDecomposer()
    return _instance


def reset_goal_decomposer_for_tests() -> None:
    """Reset singleton for test isolation."""
    global _instance
    with _instance_lock:
        _instance = None
