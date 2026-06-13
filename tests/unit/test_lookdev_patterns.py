import pytest
from src.runtime.lookdev import (
    LookdevPattern,
    get_lookdev_patterns,
    reset_lookdev_patterns_for_tests,
)


@pytest.fixture(autouse=True)
def reset_singleton():
    reset_lookdev_patterns_for_tests()
    yield
    reset_lookdev_patterns_for_tests()


def test_singleton_identity():
    assert get_lookdev_patterns() is get_lookdev_patterns()


def test_builtin_patterns_loaded():
    lib = get_lookdev_patterns()
    patterns = lib.list_all = lib.search_patterns()
    assert len(patterns) >= 5


def test_builtin_pattern_names_present():
    lib = get_lookdev_patterns()
    names = {p.name for p in lib.search_patterns()}
    for expected in (
        "industrial_hangar_lookdev",
        "robotics_lab_lookdev",
        "control_room_lookdev",
        "sci_fi_corridor_lookdev",
        "abandoned_factory_lookdev",
    ):
        assert expected in names


def test_search_by_query():
    lib = get_lookdev_patterns()
    results = lib.search_patterns(query="hangar")
    assert len(results) >= 1
    assert any("hangar" in p.name or "hangar" in p.environment for p in results)


def test_search_by_environment():
    lib = get_lookdev_patterns()
    results = lib.search_patterns(environment="robotics_lab")
    assert len(results) >= 1
    assert all(p.environment == "robotics_lab" for p in results)


def test_register_pattern():
    lib = get_lookdev_patterns()
    p = lib.register_pattern(
        "test_env_lookdev", "test_environment",
        ["industrial_metal", "concrete"], description="test", tags=["test"],
    )
    assert p.pattern_id.startswith("pat_")
    assert p.name == "test_env_lookdev"
    assert "industrial_metal" in p.materials


def test_get_pattern_by_id():
    lib = get_lookdev_patterns()
    p = lib.register_pattern("lookup_test", "test_env", ["glass"])
    found = lib.get_pattern(p.pattern_id)
    assert found is not None
    assert found.name == "lookup_test"


def test_get_pattern_nonexistent_returns_none():
    assert get_lookdev_patterns().get_pattern("no_such_id") is None


def test_rank_patterns_returns_list():
    lib = get_lookdev_patterns()
    ranked = lib.rank_patterns({"name": "industrial_hangar_asset"})
    assert isinstance(ranked, list)
    assert len(ranked) > 0


def test_rank_patterns_hangar_first():
    lib = get_lookdev_patterns()
    ranked = lib.rank_patterns({"name": "hangar_forklift", "tags": ["hangar", "industrial"]})
    assert ranked[0].environment == "industrial_hangar"


def test_rank_patterns_abandoned_first():
    lib = get_lookdev_patterns()
    ranked = lib.rank_patterns({"name": "abandoned_crane", "tags": ["abandoned", "derelict"]})
    assert ranked[0].environment == "abandoned_factory"


def test_pattern_to_dict_keys():
    p = LookdevPattern(name="p1", environment="env1", materials=["mat1"])
    d = p.to_dict()
    for key in ("pattern_id", "name", "environment", "materials", "description",
                "tags", "usage_count", "created_at"):
        assert key in d


def test_pattern_from_dict_round_trip():
    p = LookdevPattern(name="rt", environment="e", materials=["a", "b"], tags=["x"])
    restored = LookdevPattern.from_dict(p.to_dict())
    assert restored.name == "rt"
    assert restored.materials == ["a", "b"]
    assert restored.tags == ["x"]


def test_never_raises_none_rank():
    ranked = get_lookdev_patterns().rank_patterns(None)  # type: ignore
    assert isinstance(ranked, list)
