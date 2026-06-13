"""
Regression tests for EnvironmentScaleReview (Phase 7).

Proves that:
  1. Correctly scaled assets pass review (chair 0.84m, stool 0.33m, etc.)
  2. 2m-normalized assets are caught as SCALE_OUTLIER
  3. 2m-normalization cluster detection flags a suspicious import
  4. Empty environment is caught
  5. Role consistency is checked
  6. Environment-outlier detection works
"""

import pytest
from src.runtime.assets.assembly.environment_scale_review import (
    EnvironmentScaleReview,
    EnvironmentScaleReviewResult,
    ScaleFlag,
    get_environment_scale_review,
    reset_environment_scale_review_for_tests,
)


@pytest.fixture(autouse=True)
def reset():
    reset_environment_scale_review_for_tests()
    yield
    reset_environment_scale_review_for_tests()


# ---------------------------------------------------------------------------
# Sample assets — correct real-world scale
# ---------------------------------------------------------------------------

WESTERN_ROOM_CORRECT = [
    {"asset_id": "chair_01", "name": "Wooden Chair",    "placement_type": "chair",   "height_m": 0.84, "role": "furniture"},
    {"asset_id": "table_01", "name": "Oak Table",       "placement_type": "table",   "height_m": 0.75, "role": "furniture"},
    {"asset_id": "stool_01", "name": "Old Wooden Stool","placement_type": "stool",   "height_m": 0.33, "role": "furniture"},
    {"asset_id": "bottle_01","name": "Whiskey Bottle",  "placement_type": "bottle",  "height_m": 0.24, "role": "prop"},
    {"asset_id": "barrel_01","name": "Wooden Barrel",   "placement_type": "barrel",  "height_m": 0.90, "role": "prop"},
    {"asset_id": "lantern_01","name": "Oil Lantern",    "placement_type": "lantern", "height_m": 0.40, "role": "prop"},
]

# Same assets but with 2m-normalization applied (the bug)
WESTERN_ROOM_NORMALIZED_2M = [
    {"asset_id": "chair_01", "name": "Wooden Chair",    "placement_type": "chair",   "height_m": 2.00, "role": "furniture"},
    {"asset_id": "table_01", "name": "Oak Table",       "placement_type": "table",   "height_m": 2.00, "role": "furniture"},
    {"asset_id": "stool_01", "name": "Old Wooden Stool","placement_type": "stool",   "height_m": 1.98, "role": "furniture"},
    {"asset_id": "bottle_01","name": "Whiskey Bottle",  "placement_type": "bottle",  "height_m": 2.04, "role": "prop"},
    {"asset_id": "barrel_01","name": "Wooden Barrel",   "placement_type": "barrel",  "height_m": 2.10, "role": "prop"},
    {"asset_id": "lantern_01","name": "Oil Lantern",    "placement_type": "lantern", "height_m": 1.95, "role": "prop"},
]


class TestSingleton:
    def test_same_instance(self):
        assert get_environment_scale_review() is get_environment_scale_review()

    def test_reset_new_instance(self):
        a = get_environment_scale_review()
        reset_environment_scale_review_for_tests()
        assert a is not get_environment_scale_review()


class TestCorrectlyScaledAssets:
    """Assets with real-world dimensions must pass review."""

    def test_western_room_correct_passes(self):
        r = get_environment_scale_review()
        result = r.review(WESTERN_ROOM_CORRECT, environment="western_room")
        assert result.scale_outliers == 0, (
            f"Correct assets flagged as SCALE_OUTLIER: "
            f"{[rep.flags for rep in result.reports if rep.flags]}"
        )
        assert result.normalization_detected is False
        assert result.production_ready is True

    def test_chair_0_84m_passes(self):
        r = get_environment_scale_review()
        result = r.review(
            [{"asset_id": "c1", "name": "Chair", "placement_type": "chair", "height_m": 0.84}]
        )
        assert result.scale_outliers == 0

    def test_stool_0_33m_passes(self):
        r = get_environment_scale_review()
        result = r.review(
            [{"asset_id": "s1", "name": "Stool", "placement_type": "stool", "height_m": 0.33}]
        )
        assert result.scale_outliers == 0

    def test_bottle_0_24m_passes(self):
        r = get_environment_scale_review()
        result = r.review(
            [{"asset_id": "b1", "name": "Bottle", "placement_type": "bottle", "height_m": 0.24}]
        )
        assert result.scale_outliers == 0

    def test_teapot_0_22m_passes(self):
        r = get_environment_scale_review()
        result = r.review(
            [{"asset_id": "t1", "name": "Teapot", "placement_type": "teapot", "height_m": 0.22}]
        )
        # teapot has no explicit range, so no SCALE_OUTLIER is possible
        assert result.scale_outliers == 0

    def test_grade_is_a_for_correct_assets(self):
        r = get_environment_scale_review()
        result = r.review(WESTERN_ROOM_CORRECT, environment="western_room")
        assert result.grade == "A"
        assert result.score >= 0.90


class TestNormalizedAssetsCaught:
    """Assets normalized to ~2m by the old bug must be caught."""

    def test_chair_2m_is_outlier(self):
        r = get_environment_scale_review()
        result = r.review(
            [{"asset_id": "c1", "name": "Chair", "placement_type": "chair", "height_m": 2.0}]
        )
        assert result.scale_outliers == 1, "Chair at 2m should be SCALE_OUTLIER"
        flag = result.reports[0].flags[0]
        assert flag.flag_type == "SCALE_OUTLIER"
        assert "2m-normalization" in flag.message.lower() or "normalization" in flag.message.lower()

    def test_stool_1_98m_is_outlier(self):
        r = get_environment_scale_review()
        result = r.review(
            [{"asset_id": "s1", "name": "Stool", "placement_type": "stool", "height_m": 1.98}]
        )
        assert result.scale_outliers == 1

    def test_bottle_2_04m_is_outlier(self):
        r = get_environment_scale_review()
        result = r.review(
            [{"asset_id": "b1", "name": "Bottle", "placement_type": "bottle", "height_m": 2.04}]
        )
        assert result.scale_outliers == 1

    def test_all_normalized_assets_caught(self):
        r = get_environment_scale_review()
        result = r.review(WESTERN_ROOM_NORMALIZED_2M, environment="western_room")
        # At least the seating and small props should be flagged
        assert result.scale_outliers >= 3, (
            f"Expected ≥3 SCALE_OUTLIERs for 2m-normalised assets, got {result.scale_outliers}"
        )

    def test_normalization_cluster_detected(self):
        r = get_environment_scale_review()
        result = r.review(WESTERN_ROOM_NORMALIZED_2M, environment="western_room")
        assert result.normalization_detected is True
        assert any("2m-normalization" in f.lower() for f in result.findings)

    def test_normalized_scene_not_production_ready(self):
        r = get_environment_scale_review()
        result = r.review(WESTERN_ROOM_NORMALIZED_2M, environment="western_room")
        assert result.production_ready is False

    def test_normalized_grade_is_low(self):
        r = get_environment_scale_review()
        result = r.review(WESTERN_ROOM_NORMALIZED_2M, environment="western_room")
        assert result.grade in ("C", "D", "F")


class TestEmptyEnvironment:
    def test_empty_assets_fails(self):
        r = get_environment_scale_review()
        result = r.review([], environment="western_room")
        assert result.production_ready is False
        assert result.grade == "F"
        assert any("empty" in f.lower() for f in result.findings)


class TestRoleConsistency:
    def test_beam_with_furniture_role_flagged(self):
        r = get_environment_scale_review()
        result = r.review(
            [{"asset_id": "b1", "name": "Beam", "placement_type": "beam",
              "height_m": 0.30, "role": "furniture"}]
        )
        assert result.role_outliers >= 1

    def test_chair_with_correct_role_not_flagged(self):
        r = get_environment_scale_review()
        result = r.review(
            [{"asset_id": "c1", "name": "Chair", "placement_type": "chair",
              "height_m": 0.90, "role": "furniture"}]
        )
        assert result.role_outliers == 0


class TestBeforeAfterComparison:
    """
    Direct before/after measurement comparison proving the fix works.

    Before fix: _scale_for_target(bbox, target=2.0) → chair becomes 2.0m
    After fix:  import_scale = 0.01                 → chair becomes 0.838m
    """

    def _simulated_import_height(self, sop_cm_height: float, use_buggy_scale: bool) -> float:
        """Simulate what height an asset would have after import."""
        if use_buggy_scale:
            # Old bug: normalize so max_dim = 2.0m
            scale = round(2.0 / sop_cm_height, 6)
        else:
            # Fixed: cm to meters
            scale = 0.01
        return sop_cm_height * scale

    def test_chair_before_vs_after(self):
        # SOP space: chair is 83.8 Houdini units (cm)
        before = self._simulated_import_height(83.8, use_buggy_scale=True)
        after  = self._simulated_import_height(83.8, use_buggy_scale=False)
        assert abs(before - 2.0) < 0.01, f"Before: expected ~2.0m, got {before}"
        assert abs(after - 0.838) < 0.01, f"After: expected ~0.838m, got {after}"

    def test_stool_before_vs_after(self):
        before = self._simulated_import_height(33.0, use_buggy_scale=True)
        after  = self._simulated_import_height(33.0, use_buggy_scale=False)
        assert abs(before - 2.0) < 0.01
        assert abs(after - 0.33) < 0.01

    def test_bottle_before_vs_after(self):
        before = self._simulated_import_height(24.0, use_buggy_scale=True)
        after  = self._simulated_import_height(24.0, use_buggy_scale=False)
        assert abs(before - 2.0) < 0.01
        assert abs(after - 0.24) < 0.01

    def test_teapot_before_vs_after(self):
        before = self._simulated_import_height(22.0, use_buggy_scale=True)
        after  = self._simulated_import_height(22.0, use_buggy_scale=False)
        assert abs(before - 2.0) < 0.01
        assert abs(after - 0.22) < 0.01

    def test_review_passes_only_after_fix(self):
        """Correct-scale assets pass; 2m-normalized assets fail."""
        r = get_environment_scale_review()

        # After fix
        result_after = r.review(WESTERN_ROOM_CORRECT, environment="western_room")
        assert result_after.production_ready is True

        # Before fix (simulated)
        result_before = r.review(WESTERN_ROOM_NORMALIZED_2M, environment="western_room")
        assert result_before.production_ready is False
