"""Tests for SceneConstraintSolver — §47 Layout Realization."""
import pytest
from src.runtime.layout_realization import (
    get_scene_constraint_solver,
    reset_scene_constraint_solver_for_tests,
    ResolvedTransform,
)


@pytest.fixture(autouse=True)
def reset():
    reset_scene_constraint_solver_for_tests()
    yield
    reset_scene_constraint_solver_for_tests()


def _xf(asset_id, tx, tz, relationship="scattered", cluster_id=""):
    return ResolvedTransform(
        asset_id=asset_id, asset_name=asset_id,
        tx=tx, ty=0.0, tz=tz,
        relationship=relationship,
        cluster_id=cluster_id,
    )


# ---- wall clearance --------------------------------------------------------

def test_wall_clearance_corrects_position():
    xfs = [_xf("barrel", 3.9, 0.0)]   # too close to east wall (limit ~3.4)
    result = get_scene_constraint_solver().solve_constraints(xfs, room_half_width=4.0)
    barrel = result.transforms[0]
    assert abs(barrel.tx) < 4.0 - 0.30


def test_wall_attached_asset_not_pushed():
    """Wall-mounted assets must NOT be pushed away from wall."""
    xfs = [_xf("poster", 0.0, -3.95, relationship="attached_to")]
    result = get_scene_constraint_solver().solve_constraints(xfs, room_half_width=4.0)
    # No wall clearance correction should be applied to wall-attached assets
    assert result.violations_found == 0 or not any(
        v.constraint_type == "wall_clearance"
        for v in result.violations
        if v.asset_id == "poster"
    )


def test_no_violations_for_well_placed_assets():
    xfs = [
        _xf("table", 0.0, 0.0),
        _xf("chair_s", 0.0, 0.9),
        _xf("barrel", -2.0, 2.0),
    ]
    result = get_scene_constraint_solver().solve_constraints(xfs, room_half_width=4.0)
    assert result.violations_remaining == 0


# ---- hero visibility -------------------------------------------------------

def test_hero_visibility_occluder_pushed():
    hero   = _xf("table_hero", 0.0, 0.0, relationship="anchor")
    # Large machine at same Z between camera (z=6) and hero (z=0) → occluder
    occluder = _xf("machine_01", 0.0, 3.0)
    result = get_scene_constraint_solver().solve_constraints(
        [hero, occluder],
        hero_asset_id="table_hero",
        type_hints={"machine_01": "machine"},
    )
    vis_violations = [v for v in result.violations if v.constraint_type == "hero_visibility"]
    # Either corrected or still flagged — the key is machine moved
    machine_after = next(x for x in result.transforms if x.asset_id == "machine_01")
    assert machine_after.tx != pytest.approx(0.0) or vis_violations[0].corrected


# ---- cluster spacing -------------------------------------------------------

def test_cluster_spacing_violation_detected():
    xfs = [
        _xf("a1", 0.0, 0.0, cluster_id="c1"),
        _xf("a2", 0.5, 0.0, cluster_id="c2"),   # clusters 0.5m apart, min=2.5m
    ]
    result = get_scene_constraint_solver().solve_constraints(xfs)
    cluster_viols = [v for v in result.violations if v.constraint_type == "cluster_spacing"]
    assert len(cluster_viols) >= 1


# ---- general ---------------------------------------------------------------

def test_violations_found_ge_violations_fixed():
    xfs = [_xf("a", 3.9, 3.9)]  # corner, both X and Z too close
    result = get_scene_constraint_solver().solve_constraints(xfs, room_half_width=4.0)
    assert result.violations_found >= result.violations_fixed


def test_never_raises_on_empty_input():
    result = get_scene_constraint_solver().solve_constraints([])
    assert result.ok


def test_deterministic():
    xfs1 = [_xf("a", 3.9, 0.0), _xf("b", 0.0, -3.8)]
    xfs2 = [_xf("a", 3.9, 0.0), _xf("b", 0.0, -3.8)]
    r1 = get_scene_constraint_solver().solve_constraints(xfs1)
    r2 = get_scene_constraint_solver().solve_constraints(xfs2)
    for a, b in zip(r1.transforms, r2.transforms):
        assert a.tx == pytest.approx(b.tx)
        assert a.tz == pytest.approx(b.tz)
