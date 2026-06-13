"""
Cinematic Camera Engine (Tier 4 — Cinematic Orchestration)
===========================================================
Generates production-aware cinematic camera orchestration plans.

DESIGN RULE: NO bridge calls. Planning only. Deterministic.
This module reads data structures and returns camera plans as
structured operation dicts ready for the transaction system.
It never calls get_bridge() or mutates any Houdini state.

Public API:
    CinematicCameraEngine
        .generate_camera_plan(zones, layout_rules, camera_mode) -> dict
        .calculate_camera_targets(zones, layout_rules) -> list
        .generate_camera_motion(camera_mode, targets) -> dict
        .build_focus_strategy(zones, targets) -> dict
        .evaluate_composition_readability(camera_plan) -> dict
        .stats() -> dict

    get_cinematic_camera_engine() -> CinematicCameraEngine
    reset_cinematic_camera_engine_for_tests()
"""

from __future__ import annotations

import threading
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Camera mode presets
# ---------------------------------------------------------------------------

_CAMERA_MODES: Dict[str, Dict[str, Any]] = {
    "cinematic_push_in": {
        "fov":           35.0,
        "near_clip":     0.1,
        "far_clip":      10000.0,
        "motion_type":   "translate",
        "motion_axis":   "z",
        "motion_start":  20.0,
        "motion_end":    5.0,
        "motion_frames": 120,
        "shake_intensity": 0.0,
        "description":   "Slow deliberate push toward hero.",
    },
    "orbital_reveal": {
        "fov":           28.0,
        "near_clip":     0.1,
        "far_clip":      10000.0,
        "motion_type":   "orbit",
        "motion_axis":   "y",
        "motion_start":  0.0,
        "motion_end":    45.0,
        "motion_frames": 150,
        "shake_intensity": 0.0,
        "description":   "Orbital reveal circling the hero asset.",
    },
    "hero_focus": {
        "fov":           50.0,
        "near_clip":     0.1,
        "far_clip":      10000.0,
        "motion_type":   "static",
        "motion_axis":   "none",
        "motion_start":  0.0,
        "motion_end":    0.0,
        "motion_frames": 0,
        "shake_intensity": 0.0,
        "description":   "Fixed frame, tight on hero asset.",
    },
    "atmospheric_tracking": {
        "fov":           40.0,
        "near_clip":     0.1,
        "far_clip":      10000.0,
        "motion_type":   "pan",
        "motion_axis":   "x",
        "motion_start":  -10.0,
        "motion_end":    10.0,
        "motion_frames": 200,
        "shake_intensity": 0.0,
        "description":   "Slow pan revealing depth layers.",
    },
    "handheld_subtle": {
        "fov":           45.0,
        "near_clip":     0.1,
        "far_clip":      10000.0,
        "motion_type":   "handheld",
        "motion_axis":   "none",
        "motion_start":  0.0,
        "motion_end":    0.0,
        "motion_frames": 1,
        "shake_intensity": 0.3,
        "description":   "Subtle handheld feel for documentary realism.",
    },
}

_DEFAULT_MODE = "cinematic_push_in"

_ZONE_CAMERA_POSITIONS: Dict[str, Tuple[float, float, float]] = {
    "hero_area":  (0.0, 1.5, 8.0),
    "midground":  (0.0, 2.5, 20.0),
    "background": (0.0, 3.0, 40.0),
}


# ---------------------------------------------------------------------------
# Engine class
# ---------------------------------------------------------------------------


class CinematicCameraEngine:
    """
    Generates production-aware cinematic camera orchestration plans.
    All output is planning data — no Houdini state is mutated.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._plan_count = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_camera_plan(
        self,
        zones: Dict[str, Any],
        layout_rules: Dict[str, Any],
        camera_mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate a complete cinematic camera plan.

        Unknown mode falls back to _DEFAULT_MODE.

        Returns:
            {
                plan_id:       str,
                camera_mode:   str,
                targets:       list,
                motion:        dict,
                focus_strategy: dict,
                operations:    list,
                readability:   dict,
                generated_at:  float,
            }
        """
        resolved_mode = camera_mode if camera_mode in _CAMERA_MODES else _DEFAULT_MODE

        targets = self.calculate_camera_targets(zones, layout_rules)
        motion = self.generate_camera_motion(resolved_mode, targets)
        focus_strategy = self.build_focus_strategy(zones, targets)
        operations = self._build_camera_operations(targets, motion, focus_strategy)

        # Assemble a partial plan for readability evaluation
        partial_plan: Dict[str, Any] = {
            "camera_mode": resolved_mode,
            "targets":     targets,
            "motion":      motion,
        }
        readability = self.evaluate_composition_readability(partial_plan)

        with self._lock:
            self._plan_count += 1

        return {
            "plan_id":        str(uuid.uuid4()),
            "camera_mode":    resolved_mode,
            "targets":        targets,
            "motion":         motion,
            "focus_strategy": focus_strategy,
            "operations":     operations,
            "readability":    readability,
            "generated_at":   time.time(),
        }

    def calculate_camera_targets(
        self,
        zones: Dict[str, Any],
        layout_rules: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Calculate the list of camera shot targets.

        Always includes a wide_establishing shot.
        If hero_area is populated, also adds a hero_focus shot.
        Additional mid_shot entries are added for midground zones.

        Each target:
            {
                name:      str,
                zone:      str,
                position:  tuple (tx, ty, tz),
                shot_type: "wide_establishing" | "hero_focus" | "mid_shot",
                priority:  int,
            }

        Priority: hero_focus=1 (highest), wide_establishing=2 unless no hero (then 1).
        """
        targets: List[Dict[str, Any]] = []

        hero_assets = zones.get("hero_area", [])
        has_hero = len(hero_assets) > 0

        if has_hero:
            targets.append({
                "name":      "hero_focus",
                "zone":      "hero_area",
                "position":  _ZONE_CAMERA_POSITIONS["hero_area"],
                "shot_type": "hero_focus",
                "priority":  1,
            })

        establishing_priority = 2 if has_hero else 1
        targets.append({
            "name":      "wide_establishing",
            "zone":      "background",
            "position":  _ZONE_CAMERA_POSITIONS["background"],
            "shot_type": "wide_establishing",
            "priority":  establishing_priority,
        })

        mid_assets = zones.get("midground", [])
        if mid_assets:
            targets.append({
                "name":      "mid_shot",
                "zone":      "midground",
                "position":  _ZONE_CAMERA_POSITIONS["midground"],
                "shot_type": "mid_shot",
                "priority":  3,
            })

        return targets

    def generate_camera_motion(
        self,
        camera_mode: str,
        targets: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Generate the camera motion configuration for the given mode.

        Returns the mode preset dict augmented with:
            mode:           str,
            primary_target: dict | None  — first target sorted by priority

        Falls back to _DEFAULT_MODE for unknown modes.
        """
        resolved_mode = camera_mode if camera_mode in _CAMERA_MODES else _DEFAULT_MODE
        preset = dict(_CAMERA_MODES[resolved_mode])

        primary_target: Optional[Dict[str, Any]] = None
        if targets:
            primary_target = min(targets, key=lambda t: t.get("priority", 99))

        return {
            "mode":           resolved_mode,
            "motion_type":    preset["motion_type"],
            "motion_axis":    preset["motion_axis"],
            "motion_start":   preset["motion_start"],
            "motion_end":     preset["motion_end"],
            "motion_frames":  preset["motion_frames"],
            "shake_intensity": preset["shake_intensity"],
            "description":    preset["description"],
            "primary_target": primary_target,
        }

    def build_focus_strategy(
        self,
        zones: Dict[str, Any],
        targets: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Build the focus (depth-of-field) strategy.

        hero_area present with assets → "hero_locked", dof_aperture=2.8
        No hero → "soft_focus", dof_aperture=8.0
        Multiple targets at different Z depths → rack_focus=True

        Returns:
            {
                primary_subject: str | None,
                focus_mode:      "hero_locked" | "depth_of_field" | "soft_focus",
                dof_aperture:    float,
                focus_distance:  float,
                rack_focus:      bool,
            }
        """
        hero_assets = zones.get("hero_area", [])
        primary_subject: Optional[str] = None

        if hero_assets:
            first = hero_assets[0]
            if isinstance(first, dict):
                primary_subject = first.get("name") or first.get("asset_name")
            else:
                primary_subject = str(first)

        has_hero = len(hero_assets) > 0

        if has_hero:
            focus_mode = "hero_locked"
            dof_aperture = 2.8
        else:
            focus_mode = "soft_focus"
            dof_aperture = 8.0

        # Determine focus distance from the primary target's Z position
        focus_distance = 5.0
        if targets:
            primary = min(targets, key=lambda t: t.get("priority", 99))
            pos = primary.get("position", (0.0, 0.0, 5.0))
            focus_distance = float(pos[2]) if len(pos) >= 3 else 5.0

        # Detect rack focus: multiple targets at differing Z depths
        rack_focus = False
        if len(targets) > 1:
            z_values = {
                t.get("position", (0.0, 0.0, 0.0))[2]
                for t in targets
                if len(t.get("position", ())) >= 3
            }
            rack_focus = len(z_values) > 1

        return {
            "primary_subject": primary_subject,
            "focus_mode":      focus_mode,
            "dof_aperture":    dof_aperture,
            "focus_distance":  focus_distance,
            "rack_focus":      rack_focus,
        }

    def evaluate_composition_readability(
        self,
        camera_plan: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Evaluate the compositional readability of the camera plan.

        Scoring (starts at 1.0):
        - No targets:               -0.3
        - No primary target:        -0.2
        - shake_intensity > 0.5:    -0.2 + adds blocking issue

        Strengths added for:
        - cinematic_push_in mode:   "Cinematic push-in reinforces hero focus."
        - hero_focus mode:          "Static frame provides stable hero focus."
        - wide_establishing target: "Wide establishing shot provides strong scene orientation."

        Returns:
            {
                readable:          bool,
                readability_score: float 0.0–1.0,
                issues:            list[str],
                strengths:         list[str],
            }
        """
        issues: List[str] = []
        strengths: List[str] = []
        score = 1.0

        targets: List[Dict[str, Any]] = camera_plan.get("targets", [])
        motion: Dict[str, Any] = camera_plan.get("motion", {})
        mode: str = camera_plan.get("camera_mode", "")

        shake_intensity = float(motion.get("shake_intensity", 0.0))
        motion_type = motion.get("motion_type", "")

        # Check: targets exist
        if not targets:
            score -= 0.3
            issues.append("No camera targets defined — scene has no framing.")
        else:
            # Check: primary target resolvable
            primary = min(targets, key=lambda t: t.get("priority", 99), default=None)
            if primary is None:
                score -= 0.2
                issues.append("No primary camera target — dominant shot type undefined.")

        # Check: shake intensity
        if shake_intensity > 0.5:
            score -= 0.2
            issues.append(
                "Camera shake too intense — hero readability compromised."
            )

        # Check: handheld on hero_focus mode
        if mode == "hero_focus" and motion_type == "handheld":
            issues.append(
                "Handheld motion on hero_focus mode reduces stability — consider static or push-in."
            )

        # Strengths
        if mode == "cinematic_push_in":
            strengths.append("Cinematic push-in reinforces hero focus.")
        elif mode == "hero_focus":
            strengths.append("Static frame provides stable hero focus.")

        has_establishing = any(
            t.get("shot_type") == "wide_establishing" for t in targets
        )
        if has_establishing:
            strengths.append(
                "Wide establishing shot provides strong scene orientation."
            )

        score = max(0.0, min(1.0, score))
        readable = score >= 0.5 and len(issues) == 0

        return {
            "readable":          readable,
            "readability_score": round(score, 3),
            "issues":            issues,
            "strengths":         strengths,
        }

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {"plan_count": self._plan_count}

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_camera_operations(
        self,
        targets: List[Dict[str, Any]],
        motion: Dict[str, Any],
        focus_strategy: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Generate ordered transaction op dicts for camera nodes.

        For each target:
        1. create_node cam in /obj/camera
        2. set_parms with position + focal length

        Then:
        3. layout_children on /obj/camera
        """
        ops: List[Dict[str, Any]] = []

        for target in targets:
            shot_type = target.get("shot_type", "shot")
            cam_name = f"cam_{shot_type}"
            pos = target.get("position", (0.0, 0.0, 10.0))

            ops.append({
                "op":     "create_node",
                "parent": "/obj/camera",
                "type":   "cam",
                "name":   cam_name,
            })
            ops.append({
                "op":   "set_parms",
                "node": f"/obj/camera/{cam_name}",
                "parms": {
                    "tx":    float(pos[0]) if len(pos) >= 1 else 0.0,
                    "ty":    float(pos[1]) if len(pos) >= 2 else 0.0,
                    "tz":    float(pos[2]) if len(pos) >= 3 else 10.0,
                    "focal": 50.0,
                },
            })

        ops.append({
            "op":   "layout_children",
            "path": "/obj/camera",
        })

        return ops


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[CinematicCameraEngine] = None
_LOCK = threading.Lock()


def get_cinematic_camera_engine() -> CinematicCameraEngine:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = CinematicCameraEngine()
        return _INSTANCE


def reset_cinematic_camera_engine_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
