"""Tests for CollisionSolver — §47 Layout Realization."""
import pytest
from src.runtime.layout_realization import (
    get_collision_solver,
    reset_collision_solver_for_tests,
    ResolvedTransform,
)


@pytest.fixture(autouse=True)
def reset():
    reset_collision_solver_for_tests()
    yield
    reset_collision_solver_for_tests()


def _xf(asset_id, tx, tz, relationship="scattered"):
    return ResolvedTransform(
        asset_id=asset_id, asset_name=asset_id,
        tx=tx, ty=0.0, tz=tz, relationship=relationship,
    )


# ---- detect ----------------------------------------------------------------

def test_detect_overlapping_chairs():
    transforms = [_xf("chair_a", 0.0, 0.0), _xf("chair_b", 0.0, 0.0)]
    cols = get_collision_solver().detect_only(transforms, {"chair_a": "chair", "chair_b": "chair"})
    assert len(cols) > 0


def test_detect_no_collision_when_far_apart():
    transforms = [_xf("a", 0.0, 0.0), _xf("b", 5.0, 0.0)]
    cols = get_collision_solver().detect_only(transforms)
    assert len(cols) == 0


# ---- solve -----------------------------------------------------------------

def test_solve_separates_overlapping_assets():
    transforms = [_xf("chair_a", 0.0, 0.0), _xf("chair_b", 0.1, 0.0)]
    result = get_collision_solver().solve(transforms)
    a = next(x for x in result.transforms if x.asset_id == "chair_a")
    b = next(x for x in result.transforms if x.asset_id == "chair_b")
    dist = abs(a.tx - b.tx)
    assert dist > 0.3, f"assets still too close: {dist:.3f}m"


def test_solve_zero_collisions_remaining_for_two_chairs():
    transforms = [_xf("a", 0.0, 0.0), _xf("b", 0.05, 0.0)]
    result = get_collision_solver().solve(transforms)
    assert result.collisions_remaining == 0


def test_wall_penetration_corrected():
    transforms = [_xf("barrel", 4.8, 0.0)]
    result = get_collision_solver().solve(transforms, room_half_width=4.0)
    b = next(x for x in result.transforms if x.asset_id == "barrel")
    assert abs(b.tx) < 4.0, f"barrel still outside room: {b.tx}"


def test_zero_radius_assets_not_collide():
    """Wall-mounted assets (poster) have radius 0 — should never collide."""
    transforms = [
        ResolvedTransform(asset_id="p1", asset_name="Poster", tx=0.0, tz=-4.0),
        ResolvedTransform(asset_id="p2", asset_name="Poster", tx=0.0, tz=-4.0),
    ]
    cols = get_collision_solver().detect_only(transforms, {"p1": "poster", "p2": "poster"})
    assert len(cols) == 0


def test_non_overlapping_stays_unchanged():
    t1 = _xf("a", 0.0, 0.0)
    t2 = _xf("b", 3.0, 0.0)
    orig_tx_a = t1.tx
    orig_tx_b = t2.tx
    result = get_collision_solver().solve([t1, t2])
    a = next(x for x in result.transforms if x.asset_id == "a")
    b = next(x for x in result.transforms if x.asset_id == "b")
    assert a.tx == pytest.approx(orig_tx_a)
    assert b.tx == pytest.approx(orig_tx_b)


def test_collisions_found_count():
    transforms = [_xf(f"a{i}", float(i) * 0.01, 0.0) for i in range(4)]
    result = get_collision_solver().solve(transforms)
    assert result.collisions_found >= 1
