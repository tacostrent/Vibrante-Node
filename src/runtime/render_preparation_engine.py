"""
Render Preparation Engine (Tier 4 — Cinematic Orchestration)
=============================================================
Generates renderer-aware cinematic scene setup plans.
Supported renderers: Arnold, Karma.

DESIGN RULE: NO bridge calls. Planning only. Deterministic.

Public API:
    RenderPreparationEngine
        .generate_render_plan(scene_context, renderer, layout_plan) -> dict
        .build_renderer_settings(renderer, quality_preset) -> dict
        .build_aov_strategy(renderer, scene_has_fx) -> list
        .estimate_render_complexity(layout_plan, atmosphere_plan, lighting_plan) -> dict
        .validate_render_readiness(scene_context, render_plan) -> dict
    get_render_preparation_engine() -> RenderPreparationEngine
    reset_render_preparation_engine_for_tests()
"""

from __future__ import annotations

import threading
import time
import uuid
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Renderer constants
# ---------------------------------------------------------------------------

_SUPPORTED_RENDERERS = ("arnold", "karma")
_DEFAULT_RENDERER = "arnold"

_ARNOLD_PRESETS: Dict[str, Dict[str, Any]] = {
    "preview": {
        "AA_samples": 3,
        "diffuse_samples": 2,
        "specular_samples": 2,
        "transmission_samples": 2,
        "sss_samples": 2,
        "ray_depth_total": 6,
        "ray_depth_diffuse": 1,
        "ray_depth_specular": 1,
        "enable_motion_blur": False,
        "motion_blur_keys": 2,
        "enable_dof": False,
        "volume_step_size": 0.1,
        "bucket_size": 64,
    },
    "production": {
        "AA_samples": 6,
        "diffuse_samples": 3,
        "specular_samples": 3,
        "transmission_samples": 3,
        "sss_samples": 3,
        "ray_depth_total": 12,
        "ray_depth_diffuse": 2,
        "ray_depth_specular": 2,
        "enable_motion_blur": True,
        "motion_blur_keys": 2,
        "enable_dof": True,
        "volume_step_size": 0.05,
        "bucket_size": 64,
    },
    "final": {
        "AA_samples": 10,
        "diffuse_samples": 4,
        "specular_samples": 4,
        "transmission_samples": 4,
        "sss_samples": 4,
        "ray_depth_total": 16,
        "ray_depth_diffuse": 3,
        "ray_depth_specular": 3,
        "enable_motion_blur": True,
        "motion_blur_keys": 3,
        "enable_dof": True,
        "volume_step_size": 0.02,
        "bucket_size": 64,
    },
}

_KARMA_PRESETS: Dict[str, Dict[str, Any]] = {
    "preview": {
        "path_trace_samples": 64,
        "light_samples": 4,
        "enable_motion_blur": False,
        "motion_blur_steps": 2,
        "enable_dof": False,
        "volume_max_depth": 5,
        "use_xpu": True,
    },
    "production": {
        "path_trace_samples": 256,
        "light_samples": 8,
        "enable_motion_blur": True,
        "motion_blur_steps": 2,
        "enable_dof": True,
        "volume_max_depth": 10,
        "use_xpu": True,
    },
    "final": {
        "path_trace_samples": 1024,
        "light_samples": 16,
        "enable_motion_blur": True,
        "motion_blur_steps": 3,
        "enable_dof": True,
        "volume_max_depth": 16,
        "use_xpu": False,   # CPU for final quality
    },
}

# ---------------------------------------------------------------------------
# AOV lists
# ---------------------------------------------------------------------------

_ARNOLD_BASE_AOVS: List[str] = [
    "beauty", "diffuse", "specular", "emission", "N", "P", "depth",
    "crypto_object", "crypto_material", "motionvector",
]
_ARNOLD_FX_AOVS: List[str] = ["volume", "volume_opacity", "scatter"]

_KARMA_BASE_AOVS: List[str] = [
    "beauty", "diffuse", "specular", "emission", "cryptomatte", "depth", "motionvector",
]
_KARMA_FX_AOVS: List[str] = ["volume", "scatter"]

# ---------------------------------------------------------------------------
# Render time estimate mapping
# ---------------------------------------------------------------------------

_RENDER_TIME_MAP: Dict[str, str] = {
    "low":     "< 1 min",
    "medium":  "1–5 min",
    "high":    "5–30 min",
    "extreme": "> 30 min",
}


class RenderPreparationEngine:
    """
    Generates renderer-aware cinematic scene setup plans.
    Planning only — no bridge calls, no randomness.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._plan_count = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_render_plan(
        self,
        scene_context: Dict[str, Any],
        renderer: str,
        layout_plan: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate a complete renderer-aware render plan.

        Args:
            scene_context: Dict from houdini_runtime.scene_context (may be empty).
            renderer:      "arnold" or "karma"; unknown values fall back to arnold.
            layout_plan:   Optional layout plan from SceneLayoutPlanner.

        Returns a dict with plan_id, renderer, quality_preset, renderer_settings,
        aov_strategy, complexity, readiness, operations, and generated_at.
        """
        renderer = renderer.lower() if isinstance(renderer, str) else _DEFAULT_RENDERER
        if renderer not in _SUPPORTED_RENDERERS:
            renderer = _DEFAULT_RENDERER

        quality_preset = "production"

        renderer_settings = self.build_renderer_settings(renderer, quality_preset)

        # Detect FX presence from layout_plan
        scene_has_fx = False
        if layout_plan:
            fx_layers = layout_plan.get("fx_layers") or layout_plan.get("recommended_fx", [])
            scene_has_fx = len(fx_layers) > 0

        aov_strategy = self.build_aov_strategy(renderer, scene_has_fx=scene_has_fx)

        complexity = self.estimate_render_complexity(
            layout_plan=layout_plan,
            atmosphere_plan=None,
            lighting_plan=None,
        )

        # Build ROP operations
        rop_name = f"{renderer}_render"
        rop_path = f"/out/{rop_name}"

        # Separate renderer_settings (without meta keys) for set_parms
        parms = {k: v for k, v in renderer_settings.items()
                 if k not in ("renderer", "quality_preset")}

        operations: List[Dict[str, Any]] = [
            {
                "op": "create_node",
                "parent": "/out",
                "type": renderer,
                "name": rop_name,
            },
            {
                "op": "set_parms",
                "node": rop_path,
                "parms": parms,
            },
            {
                "op": "layout_children",
                "path": "/out",
            },
        ]

        render_plan: Dict[str, Any] = {
            "plan_id": str(uuid.uuid4()),
            "renderer": renderer,
            "quality_preset": quality_preset,
            "renderer_settings": renderer_settings,
            "aov_strategy": aov_strategy,
            "complexity": complexity,
            "readiness": {},   # populated below
            "operations": operations,
            "generated_at": time.time(),
        }

        render_plan["readiness"] = self.validate_render_readiness(scene_context, render_plan)

        with self._lock:
            self._plan_count += 1

        return render_plan

    def build_renderer_settings(
        self,
        renderer: str,
        quality_preset: str = "production",
    ) -> Dict[str, Any]:
        """
        Return the renderer preset dict for the given renderer and quality level.

        Unknown renderer falls back to "arnold". Unknown quality_preset falls back
        to "production". Always adds "renderer" and "quality_preset" keys.
        """
        renderer = renderer.lower() if isinstance(renderer, str) else _DEFAULT_RENDERER
        if renderer not in _SUPPORTED_RENDERERS:
            renderer = _DEFAULT_RENDERER

        if quality_preset not in ("preview", "production", "final"):
            quality_preset = "production"

        if renderer == "karma":
            presets = _KARMA_PRESETS
        else:
            presets = _ARNOLD_PRESETS

        settings = dict(presets[quality_preset])
        settings["renderer"] = renderer
        settings["quality_preset"] = quality_preset
        return settings

    def build_aov_strategy(
        self,
        renderer: str,
        scene_has_fx: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Return the AOV list for the given renderer.

        Base AOVs are required=True. FX AOVs (added when scene_has_fx=True) are required=False.
        Unknown renderer falls back to Arnold AOVs.
        """
        renderer = renderer.lower() if isinstance(renderer, str) else _DEFAULT_RENDERER
        if renderer not in _SUPPORTED_RENDERERS:
            renderer = _DEFAULT_RENDERER

        if renderer == "karma":
            base = _KARMA_BASE_AOVS
            fx = _KARMA_FX_AOVS
        else:
            base = _ARNOLD_BASE_AOVS
            fx = _ARNOLD_FX_AOVS

        aovs: List[Dict[str, Any]] = [
            {"name": name, "type": "aov", "renderer": renderer, "required": True}
            for name in base
        ]

        if scene_has_fx:
            for name in fx:
                aovs.append({"name": name, "type": "aov", "renderer": renderer, "required": False})

        return aovs

    def estimate_render_complexity(
        self,
        layout_plan: Optional[Dict[str, Any]] = None,
        atmosphere_plan: Optional[Dict[str, Any]] = None,
        lighting_plan: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Heuristic render complexity estimation.

        Scoring (additive):
        - asset_count * 0.5
        - zone_count * 1.0
        - fx_count * 2.0
        - volumetric enabled: +5.0
        - atmosphere density > 0: +3.0

        Returns complexity_level, complexity_score, contributions, estimated_render_time, notes.
        """
        notes: List[str] = []
        score = 0.0

        asset_contribution = 0.0
        volumetric_contribution = 0.0
        atmosphere_contribution = 0.0

        if layout_plan:
            asset_count = layout_plan.get("total_assets", 0)
            asset_contribution = asset_count * 0.5
            score += asset_contribution

            zones = layout_plan.get("zones", {})
            zone_count = len(zones)
            score += zone_count * 1.0

            # fx_layers preferred; fall back to recommended_fx
            fx_layers = layout_plan.get("fx_layers")
            if fx_layers is None:
                fx_layers = layout_plan.get("recommended_fx", [])
            fx_count = len(fx_layers)
            score += fx_count * 2.0

        # Volumetric lighting contribution
        if lighting_plan:
            volumetric = lighting_plan.get("volumetric", {})
            if isinstance(volumetric, dict) and volumetric.get("enabled"):
                volumetric_contribution = 5.0
                score += volumetric_contribution
                notes.append("Volumetric lighting significantly increases render time.")

        # Atmosphere contribution
        density = 0.0
        if atmosphere_plan:
            density = atmosphere_plan.get("recommended_density", 0.0)
            if isinstance(density, (int, float)) and density > 0:
                atmosphere_contribution = 3.0
                score += atmosphere_contribution
                if density > 0.05:
                    notes.append("High atmosphere density adds volume ray cost.")

        # Determine complexity level
        if score < 10:
            complexity_level = "low"
        elif score < 25:
            complexity_level = "medium"
        elif score < 50:
            complexity_level = "high"
        else:
            complexity_level = "extreme"

        return {
            "complexity_level":            complexity_level,
            "complexity_score":            round(score, 2),
            "asset_contribution":          round(asset_contribution, 2),
            "volumetric_contribution":     round(volumetric_contribution, 2),
            "atmosphere_contribution":     round(atmosphere_contribution, 2),
            "estimated_render_time":       _RENDER_TIME_MAP[complexity_level],
            "notes":                       notes,
        }

    def validate_render_readiness(
        self,
        scene_context: Optional[Dict[str, Any]],
        render_plan: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Check whether the scene is ready to render.

        Checks:
        1. has_renderer  — renderer in _SUPPORTED_RENDERERS
        2. has_geometry  — scene_context.networks.obj is non-empty
        3. has_camera    — renderer is set (Tier 4 scope)
        4. has_aovs      — aov_strategy is non-empty
        5. output_format — always EXR (production default)

        Returns ready, checks, warnings, blocking_issues.
        """
        checks: Dict[str, bool] = {}
        warnings: List[str] = []
        blocking_issues: List[str] = []

        # 1. has_renderer
        renderer = render_plan.get("renderer", "")
        checks["has_renderer"] = renderer in _SUPPORTED_RENDERERS
        if not checks["has_renderer"]:
            blocking_issues.append("Unsupported renderer — render plan cannot be executed.")

        # 2. has_geometry
        if not scene_context:
            checks["has_geometry"] = False
            warnings.append("Scene context not available — geometry/camera checks skipped.")
        else:
            obj_network = scene_context.get("networks", {}).get("obj", [])
            checks["has_geometry"] = len(obj_network) > 0
            if not checks["has_geometry"]:
                warnings.append("No geometry nodes found in /obj — scene may be empty.")

        # 3. has_camera (Tier 4 scope: verify renderer is set; actual camera requires bridge)
        checks["has_camera"] = checks["has_renderer"]

        # 4. has_aovs
        aov_strategy = render_plan.get("aov_strategy", [])
        checks["has_aovs"] = len(aov_strategy) > 0
        if not checks["has_aovs"]:
            blocking_issues.append("No AOVs configured — render output will be beauty only.")

        # 5. output_format — always EXR for production
        checks["output_format"] = True

        ready = all(checks.values()) and len(blocking_issues) == 0

        return {
            "ready":           ready,
            "checks":          checks,
            "warnings":        warnings,
            "blocking_issues": blocking_issues,
        }

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {"plan_count": self._plan_count}


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[RenderPreparationEngine] = None
_INSTANCE_LOCK = threading.Lock()


def get_render_preparation_engine() -> RenderPreparationEngine:
    global _INSTANCE
    with _INSTANCE_LOCK:
        if _INSTANCE is None:
            _INSTANCE = RenderPreparationEngine()
        return _INSTANCE


def reset_render_preparation_engine_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
