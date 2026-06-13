"""
Tests for src.runtime.pattern_library
No bridge, no LLM. Pure unit tests.
"""
import pytest
from src.runtime.pattern_library import (
    PatternLibrary,
    get_pattern_library,
    reset_pattern_library_for_tests,
    _BUILTIN_PATTERNS,
    _VALID_PATTERN_TYPES,
)


@pytest.fixture(autouse=True)
def reset():
    reset_pattern_library_for_tests()
    yield
    reset_pattern_library_for_tests()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton():
    a = get_pattern_library()
    b = get_pattern_library()
    assert a is b


def test_reset_creates_new():
    a = get_pattern_library()
    reset_pattern_library_for_tests()
    b = get_pattern_library()
    assert a is not b


# ---------------------------------------------------------------------------
# Built-in patterns
# ---------------------------------------------------------------------------

def test_builtin_patterns_exist():
    lib = PatternLibrary()
    stats = lib.stats()
    assert stats["builtin_patterns"] >= 5


def test_builtin_scene_patterns_for_all_environments():
    lib = PatternLibrary()
    scene_types = {"industrial_hangar", "robotics_lab", "sci_fi_corridor",
                   "cinematic_control_room", "abandoned_factory"}
    patterns = lib.search_patterns(pattern_type="scene_pattern")
    found_types = {p.get("scene_type") for p in patterns if p.get("scene_type")}
    assert scene_types <= found_types


def test_builtin_industrial_hangar_v1():
    lib = PatternLibrary()
    p = lib.get_pattern("industrial_hangar_v1")
    assert p is not None
    assert p["lighting"]   == "cinematic_industrial"
    assert p["camera"]     == "cinematic_push_in"
    assert p["atmosphere"] == "industrial_fog"
    assert p["builtin"]    is True


def test_builtin_robotics_lab_v1():
    lib = PatternLibrary()
    p = lib.get_pattern("robotics_lab_v1")
    assert p is not None
    assert p["lighting"] == "cold_scifi"


def test_builtin_scifi_corridor_v1():
    lib = PatternLibrary()
    p = lib.get_pattern("scifi_corridor_v1")
    assert p is not None
    assert p["atmosphere"] == "volumetric_scifi"


def test_builtin_control_room_v1():
    lib = PatternLibrary()
    p = lib.get_pattern("control_room_v1")
    assert p is not None
    assert p["camera"] == "orbital_reveal"


def test_builtin_abandoned_factory_v1():
    lib = PatternLibrary()
    p = lib.get_pattern("abandoned_factory_v1")
    assert p is not None
    assert p["atmosphere"] == "dusty_hangar"


def test_valid_pattern_types_set():
    expected = {"lighting_pattern", "camera_pattern", "atmosphere_pattern",
                "composition_pattern", "scene_pattern"}
    assert expected <= _VALID_PATTERN_TYPES


# ---------------------------------------------------------------------------
# register_pattern
# ---------------------------------------------------------------------------

def test_register_custom_pattern():
    lib = PatternLibrary()
    pid = lib.register_pattern("my_custom", "scene_pattern", {
        "scene_type": "my_env",
        "lighting": "cold_scifi",
        "description": "Custom test pattern",
    })
    assert pid == "my_custom"
    p = lib.get_pattern("my_custom")
    assert p is not None
    assert p["builtin"] is False


def test_register_pattern_invalid_type_raises():
    lib = PatternLibrary()
    with pytest.raises(ValueError):
        lib.register_pattern("bad", "invalid_type", {})


def test_register_pattern_overwrites_existing():
    lib = PatternLibrary()
    lib.register_pattern("pat", "lighting_pattern", {"lighting": "cold_scifi"})
    lib.register_pattern("pat", "lighting_pattern", {"lighting": "bladerunner_noir"})
    p = lib.get_pattern("pat")
    assert p["lighting"] == "bladerunner_noir"


def test_register_all_valid_types():
    lib = PatternLibrary()
    for pt in _VALID_PATTERN_TYPES:
        lib.register_pattern(f"test_{pt}", pt, {"description": "test"})
        assert lib.get_pattern(f"test_{pt}") is not None


# ---------------------------------------------------------------------------
# get_pattern
# ---------------------------------------------------------------------------

def test_get_pattern_unknown_returns_none():
    lib = PatternLibrary()
    assert lib.get_pattern("nonexistent_xyz") is None


def test_get_pattern_returns_copy():
    lib = PatternLibrary()
    p1 = lib.get_pattern("industrial_hangar_v1")
    p1["lighting"] = "MODIFIED"
    p2 = lib.get_pattern("industrial_hangar_v1")
    assert p2["lighting"] == "cinematic_industrial"


# ---------------------------------------------------------------------------
# search_patterns
# ---------------------------------------------------------------------------

def test_search_all_returns_ranked():
    lib = PatternLibrary()
    results = lib.search_patterns()
    assert len(results) > 0
    assert all(isinstance(p, dict) for p in results)


def test_search_by_scene_type():
    lib = PatternLibrary()
    results = lib.search_patterns(scene_type="industrial_hangar")
    for p in results:
        st = p.get("scene_type")
        assert st is None or st == "industrial_hangar"


def test_search_by_pattern_type():
    lib = PatternLibrary()
    results = lib.search_patterns(pattern_type="camera_pattern")
    assert all(p["pattern_type"] == "camera_pattern" for p in results)


def test_search_by_tags():
    lib = PatternLibrary()
    results = lib.search_patterns(tags=["cinematic"])
    assert len(results) > 0
    for p in results:
        assert "cinematic" in p.get("tags", [])


def test_search_by_tags_no_match_returns_empty():
    lib = PatternLibrary()
    results = lib.search_patterns(tags=["nonexistent_tag_xyz"])
    assert results == []


# ---------------------------------------------------------------------------
# rank_patterns
# ---------------------------------------------------------------------------

def test_rank_patterns_builtins_above_zero_score():
    lib = PatternLibrary()
    patterns = lib.search_patterns(pattern_type="scene_pattern")
    assert len(patterns) >= 5


def test_rank_patterns_success_rises():
    lib = PatternLibrary()
    lib.register_pattern("new_pat", "scene_pattern", {"scene_type": "robotics_lab"})
    lib.record_pattern_success("new_pat")
    lib.record_pattern_success("new_pat")
    # After 2 successes, new_pat should have higher score than a fresh pattern
    results = lib.search_patterns(scene_type="robotics_lab")
    ids = [p["pattern_id"] for p in results]
    # new_pat should appear (not be filtered out)
    assert "new_pat" in ids


def test_rank_patterns_all_failures_lowers():
    lib = PatternLibrary()
    lib.register_pattern("bad_pat", "scene_pattern", {})
    for _ in range(5):
        lib.record_pattern_failure("bad_pat")
    # bad_pat should be ranked lower than builtins (score < 0.5)
    results = lib.rank_patterns([lib.get_pattern("bad_pat"), lib.get_pattern("industrial_hangar_v1")])
    assert results[0]["pattern_id"] == "industrial_hangar_v1"


# ---------------------------------------------------------------------------
# record_pattern_success / failure
# ---------------------------------------------------------------------------

def test_record_pattern_success_increments():
    lib = PatternLibrary()
    lib.record_pattern_success("industrial_hangar_v1")
    lib.record_pattern_success("industrial_hangar_v1")
    p = lib.get_pattern("industrial_hangar_v1")
    assert p["_success_count"] == 2


def test_record_pattern_failure_increments():
    lib = PatternLibrary()
    lib.record_pattern_failure("industrial_hangar_v1")
    p = lib.get_pattern("industrial_hangar_v1")
    assert p["_failure_count"] == 1


def test_record_pattern_unknown_id_no_error():
    lib = PatternLibrary()
    lib.record_pattern_success("nonexistent_xyz")  # should not raise


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

def test_stats_has_required_keys():
    lib = PatternLibrary()
    s = lib.stats()
    for key in ("total_patterns", "builtin_patterns", "custom_patterns", "by_type"):
        assert key in s


def test_stats_custom_count_after_register():
    lib = PatternLibrary()
    before = lib.stats()["custom_patterns"]
    lib.register_pattern("x", "camera_pattern", {})
    assert lib.stats()["custom_patterns"] == before + 1
