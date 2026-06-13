"""Tests for §46 WallAttachmentEngine."""

import pytest
from src.runtime.layout import (
    WallAttachment,
    WallAttachmentResult,
    get_wall_attachment_engine,
    reset_wall_attachment_engine_for_tests,
    reset_affordance_engine_for_tests,
)


@pytest.fixture(autouse=True)
def reset():
    reset_wall_attachment_engine_for_tests()
    reset_affordance_engine_for_tests()
    yield
    reset_wall_attachment_engine_for_tests()
    reset_affordance_engine_for_tests()


def _asset(name, a_type):
    return {"asset_id": name, "name": name, "placement_type": a_type}


# ---------------------------------------------------------------------------
# Basic attachment
# ---------------------------------------------------------------------------

def test_poster_attached_to_wall():
    eng = get_wall_attachment_engine()
    result = eng.attach_to_walls([_asset("poster_01", "poster")])
    assert result.ok
    assert len(result.attachments) == 1
    a = result.attachments[0]
    assert "wall" in a.wall_name
    assert a.mount_height == pytest.approx((1.40 + 1.80) / 2.0, abs=0.01)


def test_lantern_attached_higher():
    eng = get_wall_attachment_engine()
    result = eng.attach_to_walls([_asset("lantern_01", "lantern")])
    a = result.attachments[0]
    # lantern range: 2.0–2.8 m → midpoint 2.4
    assert a.mount_height > 2.0


def test_non_wall_asset_rejected():
    eng = get_wall_attachment_engine()
    result = eng.attach_to_walls([_asset("barrel_01", "barrel")])
    assert len(result.attachments) == 0
    assert len(result.rejected) == 1


def test_multiple_assets_distribute_across_walls():
    eng = get_wall_attachment_engine()
    assets = [_asset(f"poster_{i}", "poster") for i in range(5)]
    result = eng.attach_to_walls(assets)
    assert len(result.attachments) == 5
    wall_names = [a.wall_name for a in result.attachments]
    # With 3 per wall, 5 assets should span at least 2 walls
    assert len(set(wall_names)) >= 2


def test_wall_normal_is_unit_vector():
    eng = get_wall_attachment_engine()
    result = eng.attach_to_walls([_asset("sign_01", "sign")])
    a = result.attachments[0]
    n = a.wall_normal
    length = sum(v ** 2 for v in n) ** 0.5
    assert length == pytest.approx(1.0, abs=0.01)


def test_mount_height_within_range():
    eng = get_wall_attachment_engine()
    for a_type, (lo, hi) in [
        ("poster", (1.40, 1.80)),
        ("lantern", (2.00, 2.80)),
        ("shelf", (1.20, 1.60)),
        ("clock", (1.60, 2.00)),
    ]:
        result = eng.attach_to_walls([_asset(a_type, a_type)])
        h = result.attachments[0].mount_height
        assert lo <= h <= hi, f"{a_type} height {h} not in [{lo}, {hi}]"


def test_get_mount_height():
    eng = get_wall_attachment_engine()
    assert eng.get_mount_height("poster") == pytest.approx(1.60, abs=0.01)
    assert eng.get_mount_height("lantern") == pytest.approx(2.40, abs=0.01)


def test_wanted_poster_eye_level():
    eng = get_wall_attachment_engine()
    result = eng.attach_to_walls([_asset("wp", "wanted_poster")])
    h = result.attachments[0].mount_height
    assert 1.40 <= h <= 1.80


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------

def test_wall_attachment_to_dict_roundtrip():
    eng = get_wall_attachment_engine()
    result = eng.attach_to_walls([_asset("painting_01", "painting")])
    a = result.attachments[0]
    d = a.to_dict()
    a2 = WallAttachment.from_dict(d)
    assert a2.asset_type == a.asset_type
    assert a2.mount_height == pytest.approx(a.mount_height)
    assert a2.wall_name == a.wall_name


def test_wall_attachment_result_to_dict():
    eng = get_wall_attachment_engine()
    result = eng.attach_to_walls([
        _asset("p1", "poster"),
        _asset("b1", "barrel"),  # rejected
    ])
    d = result.to_dict()
    assert len(d["attachments"]) == 1
    assert len(d["rejected"]) == 1
