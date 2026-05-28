"""
Tests for src.runtime.scene_awareness
No Houdini, no bridge. Pure unit tests with mocked scene_context dicts.
"""

import pytest
from src.runtime.scene_awareness import (
    SceneAwareness,
    SceneAnalysis,
    get_scene_awareness,
    reset_scene_awareness_for_tests,
)


@pytest.fixture(autouse=True)
def reset():
    reset_scene_awareness_for_tests()
    yield
    reset_scene_awareness_for_tests()


def _make_scene_context(
    obj_nodes=None,
    out_nodes=None,
    render_nodes=None,
    frame_range=(1, 240),
    fps=24.0,
    hip_file="test.hip",
):
    """Build a minimal scene_context dict for testing."""
    return {
        "scene": {
            "hip_file": hip_file,
            "hip_name": "test",
            "houdini_version": "20.0.506",
            "fps": fps,
            "frame": 1,
            "frame_range": list(frame_range),
        },
        "networks": {
            "obj": obj_nodes or [],
            "out": out_nodes or [],
            "mat": [],
        },
        "render": {
            "render_nodes": render_nodes or []
        },
        "selection": [],
        "assets": {"hda_files": [], "definitions": []},
    }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton_returns_same_instance():
    a = get_scene_awareness()
    b = get_scene_awareness()
    assert a is b


def test_reset_creates_new_instance():
    a = get_scene_awareness()
    reset_scene_awareness_for_tests()
    b = get_scene_awareness()
    assert a is not b


# ---------------------------------------------------------------------------
# analyze — empty scene
# ---------------------------------------------------------------------------

def test_analyze_empty_scene():
    sa = SceneAwareness()
    ctx = _make_scene_context()
    analysis = sa.analyze(ctx)
    assert isinstance(analysis, SceneAnalysis)
    assert analysis.renderer is None
    assert analysis.fx_types_present == []
    assert analysis.frame_range == (1, 240)
    assert analysis.fps == 24.0


def test_analyze_none_scene():
    sa = SceneAwareness()
    analysis = sa.analyze({})
    assert isinstance(analysis, SceneAnalysis)


# ---------------------------------------------------------------------------
# Renderer detection
# ---------------------------------------------------------------------------

def test_detect_arnold_renderer():
    sa = SceneAwareness()
    ctx = _make_scene_context(
        render_nodes=[{"path": "/out/arnold1", "type": "arnold", "name": "arnold1"}]
    )
    analysis = sa.analyze(ctx)
    assert analysis.renderer == "arnold"
    assert "/out/arnold1" in analysis.renderer_node_paths


def test_detect_karma_renderer():
    sa = SceneAwareness()
    ctx = _make_scene_context(
        render_nodes=[{"path": "/out/karma1", "type": "karma_rop", "name": "karma1"}]
    )
    analysis = sa.analyze(ctx)
    assert analysis.renderer == "karma"


def test_detect_mantra_renderer():
    sa = SceneAwareness()
    ctx = _make_scene_context(
        render_nodes=[{"path": "/out/mantra1", "type": "ifd", "name": "mantra1"}]
    )
    analysis = sa.analyze(ctx)
    assert analysis.renderer == "mantra"


def test_no_renderer_when_no_render_nodes():
    sa = SceneAwareness()
    ctx = _make_scene_context()
    analysis = sa.analyze(ctx)
    assert analysis.renderer is None


# ---------------------------------------------------------------------------
# FX type detection
# ---------------------------------------------------------------------------

def test_detect_pyro_fx():
    sa = SceneAwareness()
    ctx = _make_scene_context(
        obj_nodes=[
            {"path": "/obj/pyro1", "type": "pyro_solver", "name": "pyro1", "category": "Object"},
        ]
    )
    analysis = sa.analyze(ctx)
    assert "pyro" in analysis.fx_types_present


def test_detect_rbd_fx():
    sa = SceneAwareness()
    ctx = _make_scene_context(
        obj_nodes=[
            {"path": "/obj/rbd1", "type": "rbd_solver", "name": "rbd1", "category": "Object"},
        ]
    )
    analysis = sa.analyze(ctx)
    assert "rbd" in analysis.fx_types_present


def test_detect_flip_fx():
    sa = SceneAwareness()
    ctx = _make_scene_context(
        obj_nodes=[
            {"path": "/obj/flip1", "type": "flip_solver", "name": "flip1", "category": "Object"},
        ]
    )
    analysis = sa.analyze(ctx)
    assert "flip" in analysis.fx_types_present


def test_no_fx_empty_scene():
    sa = SceneAwareness()
    ctx = _make_scene_context()
    analysis = sa.analyze(ctx)
    assert analysis.fx_types_present == []


# ---------------------------------------------------------------------------
# Lighting analysis
# ---------------------------------------------------------------------------

def test_detect_hdri_lighting():
    sa = SceneAwareness()
    ctx = _make_scene_context(
        obj_nodes=[
            {"path": "/obj/envlight1", "type": "envlight", "name": "hdri_light", "category": "Object"},
        ]
    )
    analysis = sa.analyze(ctx)
    assert "hdri" in analysis.lighting_environment or analysis.lighting_environment != "none_detected"


def test_detect_night_lighting():
    sa = SceneAwareness()
    ctx = _make_scene_context(
        obj_nodes=[
            {"path": "/obj/moonlight", "type": "distantlight", "name": "ambient_moonlight_base", "category": "Object"},
        ]
    )
    analysis = sa.analyze(ctx)
    assert "night" in analysis.lighting_environment


def test_no_lighting_detected():
    sa = SceneAwareness()
    ctx = _make_scene_context()
    analysis = sa.analyze(ctx)
    assert analysis.lighting_environment == "none_detected"


# ---------------------------------------------------------------------------
# Camera detection
# ---------------------------------------------------------------------------

def test_detect_camera():
    sa = SceneAwareness()
    ctx = _make_scene_context(
        obj_nodes=[
            {"path": "/obj/hero_cam", "type": "cam", "name": "hero_cam", "category": "Object"},
        ]
    )
    analysis = sa.analyze(ctx)
    assert "/obj/hero_cam" in analysis.camera_paths


def test_no_cameras():
    sa = SceneAwareness()
    ctx = _make_scene_context()
    analysis = sa.analyze(ctx)
    assert analysis.camera_paths == []


# ---------------------------------------------------------------------------
# Frame range and fps
# ---------------------------------------------------------------------------

def test_frame_range_parsed():
    sa = SceneAwareness()
    ctx = _make_scene_context(frame_range=(10, 300))
    analysis = sa.analyze(ctx)
    assert analysis.frame_range == (10, 300)


def test_fps_parsed():
    sa = SceneAwareness()
    ctx = _make_scene_context(fps=30.0)
    analysis = sa.analyze(ctx)
    assert analysis.fps == 30.0


# ---------------------------------------------------------------------------
# Production hints
# ---------------------------------------------------------------------------

def test_hint_no_renderer():
    sa = SceneAwareness()
    ctx = _make_scene_context()
    analysis = sa.analyze(ctx)
    assert any("renderer" in h.lower() or "ROP" in h or "Arnold" in h or "Karma" in h
               for h in analysis.production_hints)


def test_hint_no_camera():
    sa = SceneAwareness()
    ctx = _make_scene_context()
    analysis = sa.analyze(ctx)
    assert any("camera" in h.lower() for h in analysis.production_hints)


def test_hint_short_frame_range():
    sa = SceneAwareness()
    ctx = _make_scene_context(frame_range=(1, 24))
    analysis = sa.analyze(ctx)
    # 24 frames is very short — should warn
    assert any("frame" in h.lower() for h in analysis.production_hints + analysis.warnings)


def test_hint_pyro_emission_aov():
    sa = SceneAwareness()
    ctx = _make_scene_context(
        obj_nodes=[{"path": "/obj/pyro1", "type": "pyro_solver", "name": "pyro1", "category": "Object"}],
        render_nodes=[{"path": "/out/arnold1", "type": "arnold", "name": "arnold1"}]
    )
    analysis = sa.analyze(ctx)
    # Should hint about emission AOV for pyro
    assert any("emission" in h.lower() for h in analysis.production_hints)


def test_hint_non_standard_fps():
    sa = SceneAwareness()
    ctx = _make_scene_context(fps=23.976)
    analysis = sa.analyze(ctx)
    # Non-standard FPS hint
    assert any("fps" in h.lower() or "24" in h for h in analysis.production_hints)


# ---------------------------------------------------------------------------
# Warnings
# ---------------------------------------------------------------------------

def test_warning_no_renderer():
    sa = SceneAwareness()
    ctx = _make_scene_context()
    analysis = sa.analyze(ctx)
    assert any("render" in w.lower() or "ROP" in w for w in analysis.warnings)


def test_warning_pyro_no_lighting():
    sa = SceneAwareness()
    ctx = _make_scene_context(
        obj_nodes=[{"path": "/obj/pyro1", "type": "pyro_solver", "name": "pyro1", "category": "Object"}]
    )
    analysis = sa.analyze(ctx)
    assert any("light" in w.lower() for w in analysis.warnings)


def test_warning_very_short_frame_range():
    sa = SceneAwareness()
    ctx = _make_scene_context(frame_range=(1, 10))
    analysis = sa.analyze(ctx)
    assert any("frame" in w.lower() for w in analysis.warnings)


# ---------------------------------------------------------------------------
# to_dict
# ---------------------------------------------------------------------------

def test_analysis_to_dict():
    sa = SceneAwareness()
    ctx = _make_scene_context(
        render_nodes=[{"path": "/out/arnold1", "type": "arnold", "name": "arnold1"}]
    )
    analysis = sa.analyze(ctx)
    d = analysis.to_dict()
    assert "renderer" in d
    assert "lighting_environment" in d
    assert "fx_types_present" in d
    assert "production_hints" in d
    assert "warnings" in d
    assert "metrics" in d
    assert isinstance(d["frame_range"], list)


# ---------------------------------------------------------------------------
# estimate_render_cost
# ---------------------------------------------------------------------------

def test_render_cost_shape():
    sa = SceneAwareness()
    ctx = _make_scene_context(
        render_nodes=[{"path": "/out/arnold1", "type": "arnold", "name": "arnold1"}]
    )
    result = sa.estimate_render_cost(ctx)
    assert "cost_tier" in result
    assert "estimated_seconds_per_frame" in result
    assert "primary_cost_drivers" in result
    assert "recommendations" in result
    assert result["cost_tier"] in ("fast", "moderate", "heavy", "extreme")


def test_render_cost_pyro_is_heavy():
    sa = SceneAwareness()
    ctx = _make_scene_context(
        obj_nodes=[
            {"path": "/obj/pyro1", "type": "pyro_solver", "name": "pyro1", "category": "Object"},
            {"path": "/obj/rbd1", "type": "rbd_solver", "name": "rbd1", "category": "Object"},
        ],
        render_nodes=[{"path": "/out/arnold1", "type": "arnold", "name": "arnold1"}]
    )
    result = sa.estimate_render_cost(ctx)
    assert result["cost_tier"] in ("heavy", "extreme")


def test_render_cost_empty_scene_is_fast():
    sa = SceneAwareness()
    ctx = _make_scene_context()
    result = sa.estimate_render_cost(ctx, renderer="mantra")
    assert result["cost_tier"] in ("fast", "moderate")


# ---------------------------------------------------------------------------
# get_production_hints shortcut
# ---------------------------------------------------------------------------

def test_get_production_hints_returns_list():
    sa = SceneAwareness()
    ctx = _make_scene_context()
    hints = sa.get_production_hints(ctx)
    assert isinstance(hints, list)


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

def test_stats_shape():
    sa = SceneAwareness()
    s = sa.stats()
    assert "analyze_count" in s


def test_stats_count_increments():
    sa = SceneAwareness()
    sa.analyze({})
    sa.analyze({})
    assert sa.stats()["analyze_count"] == 2
