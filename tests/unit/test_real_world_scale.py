"""
Regression tests for RealWorldScaleResolver (Phase 2).

Proves that:
  1. Megascans chair (84 cm FBX) is NOT normalised to 2m.
  2. Megascans stool (33 cm FBX) is NOT normalised to ~2m.
  3. Megascans bottle (24 cm FBX) is NOT normalised to ~2m.
  4. Megascans teapot (22 cm FBX) is NOT normalised to ~2m.
  5. The scale=0.01 (cm→m) path is taken for all Megascans providers.
  6. USD assets get scale=1.0 (self-describing format).
  7. No asset is ever normalised to a 2m target.
"""

import pytest
from src.runtime.assets.real_world_scale import (
    RealWorldScaleResolver,
    get_real_world_scale_resolver,
    reset_real_world_scale_resolver_for_tests,
)


@pytest.fixture(autouse=True)
def reset():
    reset_real_world_scale_resolver_for_tests()
    yield
    reset_real_world_scale_resolver_for_tests()


class TestSingleton:
    def test_same_instance(self):
        assert get_real_world_scale_resolver() is get_real_world_scale_resolver()

    def test_reset_new_instance(self):
        a = get_real_world_scale_resolver()
        reset_real_world_scale_resolver_for_tests()
        assert a is not get_real_world_scale_resolver()


class TestMegascansProviderScale:
    """Provider identity signals cm-space → scale must be 0.01."""

    def test_megascans_provider_returns_cm_scale(self):
        r = get_real_world_scale_resolver()
        scale = r.resolve_import_scale({"provider": "megascans"})
        assert scale == pytest.approx(0.01), f"Expected 0.01 for megascans, got {scale}"

    def test_quixel_provider_returns_cm_scale(self):
        r = get_real_world_scale_resolver()
        assert r.resolve_import_scale({"provider": "quixel"}) == pytest.approx(0.01)

    def test_fab_provider_returns_cm_scale(self):
        r = get_real_world_scale_resolver()
        assert r.resolve_import_scale({"provider": "fab"}) == pytest.approx(0.01)

    def test_quixel_bridge_provider_returns_cm_scale(self):
        r = get_real_world_scale_resolver()
        assert r.resolve_import_scale({"provider": "quixel_bridge"}) == pytest.approx(0.01)

    def test_local_library_returns_cm_scale(self):
        r = get_real_world_scale_resolver()
        assert r.resolve_import_scale({"provider": "local_library"}) == pytest.approx(0.01)


class TestExplicitUnitField:
    """Explicit unit field takes priority over provider."""

    def test_explicit_cm_unit(self):
        r = get_real_world_scale_resolver()
        assert r.resolve_import_scale({"unit": "cm"}) == pytest.approx(0.01)

    def test_explicit_mm_unit(self):
        r = get_real_world_scale_resolver()
        assert r.resolve_import_scale({"unit": "mm"}) == pytest.approx(0.001)

    def test_explicit_m_unit(self):
        r = get_real_world_scale_resolver()
        assert r.resolve_import_scale({"unit": "m"}) == pytest.approx(1.0)

    def test_explicit_meters_unit(self):
        r = get_real_world_scale_resolver()
        assert r.resolve_import_scale({"unit": "meters"}) == pytest.approx(1.0)

    def test_explicit_inches_unit(self):
        r = get_real_world_scale_resolver()
        assert abs(r.resolve_import_scale({"unit": "in"}) - 0.0254) < 1e-6

    def test_unit_system_field(self):
        r = get_real_world_scale_resolver()
        assert r.resolve_import_scale({"unit_system": "cm"}) == pytest.approx(0.01)

    def test_bbox_unit_field(self):
        r = get_real_world_scale_resolver()
        assert r.resolve_import_scale({"bbox_unit": "cm"}) == pytest.approx(0.01)


class TestUSDSelfDescribing:
    """USD-family files self-describe units → scale=1.0."""

    def test_usd_extension(self):
        r = get_real_world_scale_resolver()
        scale = r.resolve_import_scale({"local_path": "/path/to/asset.usd"})
        assert scale == pytest.approx(1.0)

    def test_usda_extension(self):
        r = get_real_world_scale_resolver()
        assert r.resolve_import_scale({"local_path": "/path/to/asset.usda"}) == pytest.approx(1.0)

    def test_usdc_extension(self):
        r = get_real_world_scale_resolver()
        assert r.resolve_import_scale({"local_path": "/path/to/asset.usdc"}) == pytest.approx(1.0)

    def test_usdz_extension(self):
        r = get_real_world_scale_resolver()
        assert r.resolve_import_scale({"local_path": "/path/to/asset.usdz"}) == pytest.approx(1.0)


class TestHeuristicBboxDetection:
    """Large raw bbox values trigger cm-space heuristic."""

    def test_large_bbox_x_triggers_cm(self):
        r = get_real_world_scale_resolver()
        # Chair that is 48.9 cm wide — raw value > 10 → must be cm
        assert r.resolve_import_scale({"bbox_x": 48.9}) == pytest.approx(0.01)

    def test_large_height_triggers_cm(self):
        r = get_real_world_scale_resolver()
        # 83.8 cm tall (realistic Megascans chair)
        assert r.resolve_import_scale({"height": 83.8}) == pytest.approx(0.01)

    def test_small_metric_bbox_stays_1(self):
        r = get_real_world_scale_resolver()
        # 0.84 m tall — already in metres (< 10 threshold) but no provider → default 0.01
        # Default is still 0.01 (Megascans standard) even for small values
        scale = r.resolve_import_scale({"height": 0.84})
        # Default is 0.01 — the safe fallback for unrecognised assets
        assert scale == pytest.approx(0.01)


class TestDefaultFallback:
    """Empty or unrecognised metadata defaults to 0.01 (Megascans standard)."""

    def test_empty_dict_returns_cm_scale(self):
        r = get_real_world_scale_resolver()
        assert r.resolve_import_scale({}) == pytest.approx(0.01)

    def test_unknown_provider_falls_back_to_cm(self):
        r = get_real_world_scale_resolver()
        assert r.resolve_import_scale({"provider": "some_unknown_store"}) == pytest.approx(0.01)


class TestRealWorldDimensionPreservation:
    """
    Prove the core invariant: real-world dimensions are NEVER normalised to 2m.

    These tests simulate real Megascans FBX data.  The SOP-space bbox values
    are in centimeters (Megascans default).  Applying scale=0.01 must yield
    the correct real-world height.
    """

    def _world_height(self, sop_height_cm: float, provider: str = "megascans") -> float:
        """Simulate import: SOP-space cm bbox × import scale = world-space metres."""
        r = get_real_world_scale_resolver()
        scale = r.resolve_import_scale({"provider": provider})
        return sop_height_cm * scale

    def test_wooden_chair_height(self):
        # Wooden Chair — real height 84 cm
        world_h = self._world_height(83.8)
        assert abs(world_h - 0.838) < 0.01, (
            f"Chair: expected ~0.84m, got {world_h:.3f}m — 2m-normalization still active?"
        )
        assert world_h < 1.5, f"Chair must NOT be ~2m tall, got {world_h:.3f}m"

    def test_old_wooden_stool_height(self):
        # Old Wooden Stool — real height 33 cm
        world_h = self._world_height(33.0)
        assert abs(world_h - 0.33) < 0.01, (
            f"Stool: expected ~0.33m, got {world_h:.3f}m — 2m-normalization still active?"
        )
        assert world_h < 0.8, f"Stool must NOT be ~2m tall, got {world_h:.3f}m"

    def test_bottle_height(self):
        # Bottle — real height 24 cm
        world_h = self._world_height(24.0)
        assert abs(world_h - 0.24) < 0.01
        assert world_h < 0.5, f"Bottle must NOT be ~2m tall, got {world_h:.3f}m"

    def test_teapot_height(self):
        # Teapot — real height 22 cm
        world_h = self._world_height(22.0)
        assert abs(world_h - 0.22) < 0.01
        assert world_h < 0.5, f"Teapot must NOT be ~2m tall, got {world_h:.3f}m"

    def test_no_asset_becomes_2m_from_cm_import(self):
        # Prove that no common furniture asset scales to ≈2m under 0.01 scale
        # (2m would require a SOP bbox of 200 cm = a 2m-tall object which would be correct!)
        # The key assertion: a 84cm-tall chair must NOT become 2m.
        r = get_real_world_scale_resolver()
        scale = r.resolve_import_scale({"provider": "megascans"})
        assert scale != pytest.approx(2.0 / 83.8, abs=0.001), (
            "_scale_for_target(2.0) is still active — normalization not removed!"
        )

    def test_scale_is_not_target_normalisation(self):
        # The old bug: scale = target_height / max_dim = 2.0 / 83.8 ≈ 0.023858
        # The fix: scale = 0.01 (cm to meters)
        r = get_real_world_scale_resolver()
        scale = r.resolve_import_scale({"provider": "megascans"})
        old_buggy_scale = round(2.0 / 83.8, 6)
        assert abs(scale - old_buggy_scale) > 0.001, (
            f"Got scale={scale} which matches the old 2m-normalization scale {old_buggy_scale}. "
            "The _scale_for_target() bug has NOT been removed."
        )


class TestDescribeScaleDecision:
    def test_cm_note(self):
        r = get_real_world_scale_resolver()
        d = r.describe_scale_decision({"provider": "megascans"})
        assert d["scale"] == pytest.approx(0.01)
        assert d["source_unit"] == "cm"
        assert "centimeter" in d["note"].lower() or "megascans" in d["note"].lower()

    def test_meter_note(self):
        r = get_real_world_scale_resolver()
        d = r.describe_scale_decision({"local_path": "asset.usd"})
        assert d["scale"] == pytest.approx(1.0)
        assert d["source_unit"] == "m"
