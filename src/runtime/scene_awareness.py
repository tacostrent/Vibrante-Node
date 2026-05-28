"""
Scene Awareness
===============
Analyzes the current Houdini scene context for cinematic production requirements.
Extracts terrain scale, camera distance, renderer, lighting environment, and
scene scale metrics — all without LLM calls or direct bridge interaction.

Reads data from a structured scene_context dict (as produced by
houdini_runtime.scene_context()) and computes production-relevant metrics.

Design rules:
  - Deterministic — same input always produces same output.
  - No LLM calls — heuristic analysis only.
  - No bridge calls — reads structured scene_context dicts only.
  - No I/O side effects — pure in-memory operation.

Public API:
    get_scene_awareness() -> SceneAwareness    (singleton)
    reset_scene_awareness_for_tests()

    SceneAwareness.analyze(scene_context) -> SceneAnalysis
    SceneAwareness.get_production_hints(scene_context) -> list[str]
    SceneAwareness.estimate_render_cost(scene_context, renderer=None) -> dict
    SceneAwareness.stats() -> dict
"""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Scale reference constants (in Houdini world units — meters)
# ---------------------------------------------------------------------------

# Explosion scale categories (based on epicenter diameter)
_EXPLOSION_SCALE = {
    "small":    (0.0, 5.0),     # grenade / small IED
    "medium":   (5.0, 20.0),    # vehicle explosion
    "large":    (20.0, 60.0),   # cinematic hero explosion
    "massive":  (60.0, 300.0),  # building / infrastructure destruction
}

# Camera distance categories from epicenter
_CAMERA_DISTANCE = {
    "extreme_close_up": (0.0, 5.0),
    "close":            (5.0, 15.0),
    "medium":           (15.0, 40.0),
    "wide":             (40.0, 100.0),
    "extreme_wide":     (100.0, 9999.0),
}

# Renderer node type patterns
_KNOWN_RENDERERS = {
    "arnold":       ["arnold", "arnold_render"],
    "karma":        ["karma", "karma_rop", "karma_xl"],
    "mantra":       ["ifd", "mantra"],
    "redshift":     ["redshift_rop", "rs_rop"],
    "vray":         ["vray_renderer"],
    "octane":       ["octane"],
}

# Lighting environment classification
_LIGHTING_KEYWORDS = {
    "hdri":             ["hdri", "hdr", "hdri_light", "envlight", "env_light"],
    "skydome":          ["skydome", "sky_dome", "dome_light", "domelight"],
    "three_point":      ["key_light", "fill_light", "rim_light", "back_light"],
    "practical":        ["fire_light", "explosion_light", "practical_light", "emission_light"],
    "night":            ["night", "moonlight", "ambient_moonlight"],
    "daylight":         ["sun", "sunlight", "physical_sky", "sky_rop"],
}

# Node type → workflow relevance
_FX_NODE_TYPES = {
    "pyro":         ["pyro_solver", "pyrosolver", "pyro", "smoke", "smokesolver"],
    "rbd":          ["rbd", "rbd_solver", "rbdsolver", "voronoi", "vellum"],
    "flip":         ["flip", "flip_solver", "flipsolver"],
    "particles":    ["popnet", "pop_solver"],
    "wire":         ["wiresolver", "wire_solver"],
    "cloth":        ["clothsolver", "cloth_solver"],
}


# ---------------------------------------------------------------------------
# SceneAnalysis
# ---------------------------------------------------------------------------

class SceneAnalysis:
    """Result of analyzing a scene_context for production awareness."""

    def __init__(
        self,
        renderer: Optional[str],
        renderer_node_paths: List[str],
        lighting_environment: str,
        lighting_nodes: List[str],
        fx_types_present: List[str],
        camera_paths: List[str],
        scene_scale: str,
        estimated_camera_distance: str,
        frame_range: Tuple[int, int],
        fps: float,
        production_hints: List[str],
        warnings: List[str],
        metrics: Dict[str, Any],
    ) -> None:
        self.renderer = renderer
        self.renderer_node_paths = renderer_node_paths
        self.lighting_environment = lighting_environment
        self.lighting_nodes = lighting_nodes
        self.fx_types_present = fx_types_present
        self.camera_paths = camera_paths
        self.scene_scale = scene_scale
        self.estimated_camera_distance = estimated_camera_distance
        self.frame_range = frame_range
        self.fps = fps
        self.production_hints = production_hints
        self.warnings = warnings
        self.metrics = metrics

    def to_dict(self) -> Dict[str, Any]:
        return {
            "renderer": self.renderer,
            "renderer_node_paths": self.renderer_node_paths,
            "lighting_environment": self.lighting_environment,
            "lighting_nodes": self.lighting_nodes,
            "fx_types_present": self.fx_types_present,
            "camera_paths": self.camera_paths,
            "scene_scale": self.scene_scale,
            "estimated_camera_distance": self.estimated_camera_distance,
            "frame_range": list(self.frame_range),
            "fps": self.fps,
            "production_hints": self.production_hints,
            "warnings": self.warnings,
            "metrics": self.metrics,
        }


# ---------------------------------------------------------------------------
# SceneAwareness
# ---------------------------------------------------------------------------

class SceneAwareness:
    """Analyzes scene_context for production-relevant metrics and hints.

    Singleton — access via get_scene_awareness().
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._analyze_count = 0

    def analyze(self, scene_context: Dict[str, Any]) -> SceneAnalysis:
        """Analyze a structured scene_context dict.

        Args:
            scene_context: Output from houdini_runtime.scene_context().

        Returns:
            SceneAnalysis with production-relevant metrics and hints.
        """
        with self._lock:
            self._analyze_count += 1

        scene_context = scene_context or {}
        networks = scene_context.get("networks", {})
        render_data = scene_context.get("render", {})
        scene_meta = scene_context.get("scene", {})

        # Gather all nodes across networks for analysis
        all_nodes: List[Dict[str, Any]] = []
        for net_name, net_nodes in networks.items():
            if isinstance(net_nodes, list):
                all_nodes.extend(net_nodes)

        # Renderer detection
        renderer, renderer_paths = self._detect_renderer(render_data, all_nodes)

        # Lighting analysis
        lighting_env, lighting_nodes = self._analyze_lighting(all_nodes)

        # FX types
        fx_types = self._detect_fx_types(all_nodes)

        # Camera detection
        camera_paths = self._detect_cameras(all_nodes, networks)

        # Frame range and FPS
        frame_range_raw = scene_meta.get("frame_range", [1, 240])
        frame_range = (
            int(frame_range_raw[0]) if frame_range_raw else 1,
            int(frame_range_raw[1]) if len(frame_range_raw) > 1 else 240,
        )
        fps = float(scene_meta.get("fps", 24.0))

        # Scene scale estimation (heuristic)
        scene_scale = self._estimate_scene_scale(all_nodes, fx_types, scene_meta)

        # Camera distance estimation
        camera_distance = self._estimate_camera_distance(camera_paths, all_nodes, scene_scale)

        # Production hints
        production_hints = self._generate_production_hints(
            renderer, lighting_env, fx_types, camera_paths,
            scene_scale, frame_range, fps, scene_meta
        )

        # Warnings
        warnings = self._generate_warnings(
            renderer, lighting_env, fx_types, frame_range, fps
        )

        metrics = {
            "total_nodes": len(all_nodes),
            "render_nodes": len(renderer_paths),
            "camera_nodes": len(camera_paths),
            "lighting_nodes": len(lighting_nodes),
            "fx_node_count": len(fx_types),
            "frame_count": frame_range[1] - frame_range[0] + 1,
            "scene_has_pyro": "pyro" in fx_types,
            "scene_has_rbd": "rbd" in fx_types,
        }

        return SceneAnalysis(
            renderer=renderer,
            renderer_node_paths=renderer_paths,
            lighting_environment=lighting_env,
            lighting_nodes=lighting_nodes,
            fx_types_present=fx_types,
            camera_paths=camera_paths,
            scene_scale=scene_scale,
            estimated_camera_distance=camera_distance,
            frame_range=frame_range,
            fps=fps,
            production_hints=production_hints,
            warnings=warnings,
            metrics=metrics,
        )

    def get_production_hints(self, scene_context: Dict[str, Any]) -> List[str]:
        """Quick path — returns just the production hints list."""
        analysis = self.analyze(scene_context)
        return analysis.production_hints

    def estimate_render_cost(
        self, scene_context: Dict[str, Any], renderer: Optional[str] = None
    ) -> Dict[str, Any]:
        """Estimate render cost category based on scene complexity.

        Returns:
            Dict with: cost_tier, estimated_seconds_per_frame (range),
                       primary_cost_drivers, recommendations.
        """
        analysis = self.analyze(scene_context)
        r = renderer or analysis.renderer or "unknown"

        # Base cost from renderer
        base = {"arnold": 3, "karma": 4, "mantra": 2, "redshift": 1, "vray": 2}.get(r, 2)

        # Add FX cost
        fx_cost = 0
        if "pyro" in analysis.fx_types_present:
            fx_cost += 4
        if "rbd" in analysis.fx_types_present:
            fx_cost += 2
        if "flip" in analysis.fx_types_present:
            fx_cost += 3

        total_cost = base + fx_cost
        if total_cost <= 3:
            tier = "fast"
            est_range = "15–60 seconds/frame"
        elif total_cost <= 6:
            tier = "moderate"
            est_range = "1–5 minutes/frame"
        elif total_cost <= 9:
            tier = "heavy"
            est_range = "5–20 minutes/frame"
        else:
            tier = "extreme"
            est_range = "20–60+ minutes/frame"

        drivers = []
        if "pyro" in analysis.fx_types_present:
            drivers.append("pyro volume — highest cost driver; optimize step size")
        if "rbd" in analysis.fx_types_present:
            drivers.append("RBD geometry — ensure mesh count is under control")
        if r == "arnold":
            drivers.append("Arnold — use adaptive sampling to reduce waste")
        if r == "karma":
            drivers.append("Karma XPU — check GPU VRAM vs scene resolution")

        recs = []
        if tier in ("heavy", "extreme"):
            recs.append("Render on farm — not suitable for local machine rendering.")
            recs.append("Render proxy for playblast review before committing to final render.")
        if "pyro" in analysis.fx_types_present and r == "arnold":
            recs.append("Set volume step size explicitly — auto step size is not accurate for dense pyro.")

        return {
            "cost_tier": tier,
            "estimated_seconds_per_frame": est_range,
            "primary_cost_drivers": drivers,
            "recommendations": recs,
            "renderer": r,
        }

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {"analyze_count": self._analyze_count}

    # ------------------------------------------------------------------
    # Internal analysis helpers
    # ------------------------------------------------------------------

    def _detect_renderer(
        self, render_data: Dict[str, Any], all_nodes: List[Dict[str, Any]]
    ) -> Tuple[Optional[str], List[str]]:
        """Detect active renderer and its node paths."""
        render_nodes = render_data.get("render_nodes", [])
        if not render_nodes and not all_nodes:
            return None, []

        renderer_paths: List[str] = []
        detected: Optional[str] = None

        for rn in render_nodes:
            node_type = rn.get("type", "").lower()
            path = rn.get("path", "")
            for rname, patterns in _KNOWN_RENDERERS.items():
                if any(p in node_type for p in patterns):
                    renderer_paths.append(path)
                    if detected is None:
                        detected = rname
                    break

        # Fallback: scan all nodes for renderer types
        if not detected:
            for node in all_nodes:
                node_type = node.get("type", "").lower()
                for rname, patterns in _KNOWN_RENDERERS.items():
                    if any(p in node_type for p in patterns):
                        renderer_paths.append(node.get("path", ""))
                        if detected is None:
                            detected = rname
                        break

        return detected, renderer_paths

    def _analyze_lighting(
        self, all_nodes: List[Dict[str, Any]]
    ) -> Tuple[str, List[str]]:
        """Determine lighting environment type."""
        lighting_nodes: List[str] = []
        found_types: List[str] = []

        for node in all_nodes:
            node_type = node.get("type", "").lower()
            node_name = node.get("name", "").lower()
            path = node.get("path", "")
            combined = f"{node_type} {node_name}"

            for lit_type, keywords in _LIGHTING_KEYWORDS.items():
                if any(kw in combined for kw in keywords):
                    if lit_type not in found_types:
                        found_types.append(lit_type)
                    lighting_nodes.append(path)
                    break

        if not found_types:
            return "none_detected", lighting_nodes

        # Classify based on found types
        if "night" in found_types:
            env = "night_practical"
        elif "hdri" in found_types or "skydome" in found_types:
            if "three_point" in found_types:
                env = "hdri_plus_practical"
            else:
                env = "hdri_ambient"
        elif "three_point" in found_types:
            env = "three_point_practical"
        elif "practical" in found_types:
            env = "explosion_practical"
        elif "daylight" in found_types:
            env = "physical_sky"
        else:
            env = "minimal"

        return env, lighting_nodes

    def _detect_fx_types(self, all_nodes: List[Dict[str, Any]]) -> List[str]:
        """Detect which FX simulation types are present in the scene."""
        found: List[str] = []
        for node in all_nodes:
            node_type = node.get("type", "").lower()
            for fx_type, patterns in _FX_NODE_TYPES.items():
                if fx_type not in found and any(p in node_type for p in patterns):
                    found.append(fx_type)
        return found

    def _detect_cameras(
        self, all_nodes: List[Dict[str, Any]], networks: Dict[str, Any]
    ) -> List[str]:
        """Find camera nodes in the scene."""
        cameras: List[str] = []
        for node in all_nodes:
            node_type = node.get("type", "").lower()
            if node_type in ("cam", "camera", "houdini_cam"):
                cameras.append(node.get("path", ""))
        return cameras

    def _estimate_scene_scale(
        self,
        all_nodes: List[Dict[str, Any]],
        fx_types: List[str],
        scene_meta: Dict[str, Any],
    ) -> str:
        """Estimate overall scene scale from node count and type patterns."""
        # Heuristic: node count + FX presence gives rough scale estimate
        node_count = len(all_nodes)
        has_heavy_fx = bool(set(fx_types) & {"pyro", "flip", "rbd"})

        if node_count < 20 and not has_heavy_fx:
            return "small"
        elif node_count < 80 or not has_heavy_fx:
            return "medium"
        elif node_count < 200:
            return "large"
        else:
            return "massive"

    def _estimate_camera_distance(
        self,
        camera_paths: List[str],
        all_nodes: List[Dict[str, Any]],
        scene_scale: str,
    ) -> str:
        """Estimate camera distance based on scene scale and camera count."""
        if not camera_paths:
            return "unknown"

        # Without live scene data we can only guess from scale context
        # These are advisory estimates — a real distance requires bridge query
        distance_map = {
            "small": "close",
            "medium": "medium",
            "large": "medium",
            "massive": "wide",
        }
        return distance_map.get(scene_scale, "medium")

    def _generate_production_hints(
        self,
        renderer: Optional[str],
        lighting_env: str,
        fx_types: List[str],
        camera_paths: List[str],
        scene_scale: str,
        frame_range: Tuple[int, int],
        fps: float,
        scene_meta: Dict[str, Any],
    ) -> List[str]:
        """Generate actionable production hints for the current scene."""
        hints: List[str] = []

        # Renderer hints
        if not renderer:
            hints.append("No renderer detected — add an Arnold or Karma ROP before render setup.")
        elif renderer == "arnold":
            if "pyro" in fx_types:
                hints.append("Arnold + Pyro: set volume step size explicitly (0.02m final, 0.1m preview).")
        elif renderer == "karma":
            hints.append("Karma XPU: verify GPU VRAM is sufficient for scene complexity.")

        # Lighting hints
        if lighting_env == "none_detected":
            hints.append("No lighting nodes found — cinematic orchestration requires at least HDRI + key light.")
        elif lighting_env == "hdri_ambient" and "pyro" in fx_types:
            hints.append("Pyro scene: add practical fire emission light on top of HDRI for fire contribution on surroundings.")
        elif lighting_env == "night_practical":
            hints.append("Night scene: keep ambient very low (moonlight 0.05–0.1), let fire/explosion drive all key lighting.")

        # FX hints
        if "pyro" in fx_types:
            hints.append("Pyro present: emission AOV is required — cannot control fire brightness in comp without it.")
        if "rbd" in fx_types and "pyro" in fx_types:
            hints.append("RBD + Pyro: secondary debris needs pyro sources at impact points for realistic smoke trails.")

        # Camera hints
        if not camera_paths:
            hints.append("No camera node found — cinematic render requires a named camera, not the default perspective view.")
        elif len(camera_paths) > 3:
            hints.append(f"Multiple cameras ({len(camera_paths)}) — ensure the render ROP targets the hero camera, not a diagnostic one.")

        # Frame range hints
        frame_count = frame_range[1] - frame_range[0] + 1
        if frame_count < 48:
            hints.append(f"Frame range is only {frame_count} frames — cinematic FX needs minimum 72–120 frames for full evolution.")
        elif frame_count > 600:
            hints.append(f"Frame range is {frame_count} frames — verify this is intentional for this shot.")

        # FPS hints
        if fps not in (24.0, 25.0, 48.0, 60.0):
            hints.append(f"FPS is {fps} — cinematic standard is 24 fps. Verify this is correct for your delivery.")

        # Scale hints
        if scene_scale == "massive" and renderer == "arnold":
            hints.append("Massive scene + Arnold: expect 20–60 min/frame. Submit to farm for full frame range.")

        return hints

    def _generate_warnings(
        self,
        renderer: Optional[str],
        lighting_env: str,
        fx_types: List[str],
        frame_range: Tuple[int, int],
        fps: float,
    ) -> List[str]:
        """Generate warning-level production notices."""
        warnings: List[str] = []

        if not renderer:
            warnings.append("No render node configured — cannot proceed to render stage without a ROP.")

        if "pyro" in fx_types and lighting_env == "none_detected":
            warnings.append("Pyro FX with no lighting — fire emission will not illuminate the scene without a light setup.")

        frame_count = frame_range[1] - frame_range[0] + 1
        if frame_count < 24:
            warnings.append(f"Frame range {frame_range[0]}–{frame_range[1]} is very short ({frame_count} frames) — explosion evolution needs more time.")

        return warnings


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[SceneAwareness] = None
_instance_lock = threading.Lock()


def get_scene_awareness() -> SceneAwareness:
    """Return the SceneAwareness singleton."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = SceneAwareness()
    return _instance


def reset_scene_awareness_for_tests() -> None:
    """Reset singleton for test isolation."""
    global _instance
    with _instance_lock:
        _instance = None
