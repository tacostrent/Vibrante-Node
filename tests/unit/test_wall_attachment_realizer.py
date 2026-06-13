"""Tests for WallAttachmentRealizer — §47 Layout Realization."""
import math
import pytest
from src.runtime.layout_realization import (
    get_wall_attachment_realizer,
    reset_wall_attachment_realizer_for_tests,
)


@pytest.fixture(autouse=True)
def reset():
    reset_wall_attachment_realizer_for_tests()
    yield
    reset_wall_attachment_realizer_for_tests()


def _att(asset_id, wall, normal, height, px, pz):
    return {
        "asset_id": asset_id, "asset_name": asset_id, "asset_type": "poster",
        "wall_name": wall, "wall_normal": normal,
        "mount_height": height, "position": [px, height, pz], "ok": True,
    }


# ---- poster on wall -------------------------------------------------------

def test_poster_on_north_wall_faces_into_room():
    att = _att("poster_01", "wall_north", [0.0, 0.0, -1.0], 1.6, 0.0, -4.0)
    result = get_wall_attachment_realizer().realize_wall_attachments([att])
    assert len(result.transforms) == 1
    xf = result.transforms[0]
    assert xf.ty == pytest.approx(1.6)
    assert abs(xf.ry) < 5.0 or abs(xf.ry - 360.0) < 5.0  # ~0°


def test_poster_not_outside_wall():
    """Poster must be at wall face, not floating outside room."""
    att = _att("poster_01", "wall_north", [0.0, 0.0, -1.0], 1.6, 0.0, -4.0)
    result = get_wall_attachment_realizer().realize_wall_attachments([att], room_half_width=4.0)
    xf = result.transforms[0]
    assert abs(xf.tz) <= 4.0, f"poster outside room boundary at tz={xf.tz}"


def test_east_wall_ry_90():
    att = _att("lantern_01", "wall_east", [-1.0, 0.0, 0.0], 2.4, 4.0, 0.0)
    result = get_wall_attachment_realizer().realize_wall_attachments([att])
    xf = result.transforms[0]
    assert abs(xf.ry - 90.0) < 5.0


def test_west_wall_ry_270():
    att = _att("sign_01", "wall_west", [1.0, 0.0, 0.0], 1.8, -4.0, 0.0)
    result = get_wall_attachment_realizer().realize_wall_attachments([att])
    xf = result.transforms[0]
    assert abs(xf.ry - 270.0) < 5.0


def test_south_wall_ry_180():
    # south wall [0,0,+1] → faces north (-Z) → ry≈180°
    att = _att("banner_01", "wall_south", [0.0, 0.0, 1.0], 2.15, 0.0, 4.0)
    result = get_wall_attachment_realizer().realize_wall_attachments([att])
    xf = result.transforms[0]
    assert abs(xf.ry - 180.0) < 5.0


def test_lantern_height_correct():
    att = _att("lantern_01", "wall_north", [0.0, 0.0, -1.0], 2.4, 0.0, -4.0)
    result = get_wall_attachment_realizer().realize_wall_attachments([att])
    xf = result.transforms[0]
    assert xf.ty == pytest.approx(2.4)


def test_relationship_is_attached_to():
    att = _att("p", "wall_north", [0.0, 0.0, -1.0], 1.6, 0.0, -4.0)
    result = get_wall_attachment_realizer().realize_wall_attachments([att])
    assert result.transforms[0].relationship == "attached_to"


def test_not_ok_attachment_skipped():
    att = _att("p", "wall_north", [0.0, 0.0, -1.0], 1.6, 0.0, -4.0)
    att["ok"] = False
    result = get_wall_attachment_realizer().realize_wall_attachments([att])
    assert len(result.transforms) == 0
    assert len(result.rejected) == 1


def test_multiple_wall_items():
    atts = [
        _att("p1", "wall_north", [0.0, 0.0, -1.0], 1.6, -1.0, -4.0),
        _att("p2", "wall_north", [0.0, 0.0, -1.0], 1.6,  0.0, -4.0),
        _att("p3", "wall_north", [0.0, 0.0, -1.0], 1.6,  1.0, -4.0),
    ]
    result = get_wall_attachment_realizer().realize_wall_attachments(atts)
    assert len(result.transforms) == 3
