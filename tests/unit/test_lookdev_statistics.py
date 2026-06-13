import pytest
from src.runtime.lookdev import (
    get_lookdev_statistics,
    reset_lookdev_statistics_for_tests,
)


@pytest.fixture(autouse=True)
def reset_singleton():
    reset_lookdev_statistics_for_tests()
    yield
    reset_lookdev_statistics_for_tests()


def test_singleton_identity():
    assert get_lookdev_statistics() is get_lookdev_statistics()


def test_initial_statistics_zeros():
    stats = get_lookdev_statistics().generate_statistics()
    assert stats["total_assignments"] == 0
    assert stats["total_reviews"] == 0
    assert stats["total_material_usages"] == 0
    assert stats["top_materials"] == []
    assert stats["top_patterns"] == []


def test_record_assignment_increments():
    s = get_lookdev_statistics()
    s.record_assignment({"asset_id": "a1", "material_name": "glass", "renderer": "arnold"})
    stats = s.generate_statistics()
    assert stats["total_assignments"] == 1


def test_record_multiple_assignments():
    s = get_lookdev_statistics()
    for i in range(5):
        s.record_assignment({"asset_id": f"a{i}", "material_name": "concrete"})
    stats = s.generate_statistics()
    assert stats["total_assignments"] == 5


def test_record_material_usage():
    s = get_lookdev_statistics()
    s.record_material_usage("industrial_metal", "arnold")
    s.record_material_usage("industrial_metal", "arnold")
    s.record_material_usage("concrete")
    stats = s.generate_statistics()
    assert stats["total_material_usages"] == 3
    top = {e["name"]: e["count"] for e in stats["top_materials"]}
    assert top["industrial_metal"] == 2
    assert top["concrete"] == 1


def test_record_pattern_usage():
    s = get_lookdev_statistics()
    s.record_pattern_usage("builtin_industrial_hangar_lookdev")
    s.record_pattern_usage("builtin_industrial_hangar_lookdev")
    stats = s.generate_statistics()
    top_pats = {e["pattern_id"]: e["count"] for e in stats["top_patterns"]}
    assert top_pats["builtin_industrial_hangar_lookdev"] == 2


def test_record_review_increments():
    s = get_lookdev_statistics()
    s.record_review({"score": 0.85, "grade": "A", "production_ready": True})
    stats = s.generate_statistics()
    assert stats["total_reviews"] == 1


def test_average_review_score():
    s = get_lookdev_statistics()
    s.record_review({"score": 0.8})
    s.record_review({"score": 0.6})
    stats = s.generate_statistics()
    assert abs(stats["average_review_score"] - 0.7) < 0.01


def test_top_materials_sorted_by_count():
    s = get_lookdev_statistics()
    for _ in range(3):
        s.record_material_usage("glass")
    for _ in range(1):
        s.record_material_usage("plastic")
    stats = s.generate_statistics()
    names = [e["name"] for e in stats["top_materials"]]
    assert names[0] == "glass"


def test_top_materials_max_10():
    s = get_lookdev_statistics()
    for i in range(15):
        s.record_material_usage(f"mat_{i}")
    stats = s.generate_statistics()
    assert len(stats["top_materials"]) <= 10


def test_top_patterns_max_5():
    s = get_lookdev_statistics()
    for i in range(8):
        s.record_pattern_usage(f"pat_{i}")
    stats = s.generate_statistics()
    assert len(stats["top_patterns"]) <= 5


def test_record_assignment_never_raises_none():
    s = get_lookdev_statistics()
    s.record_assignment(None)  # type: ignore
    assert s.generate_statistics()["total_assignments"] == 0


def test_record_material_empty_name_ignored():
    s = get_lookdev_statistics()
    s.record_material_usage("")
    s.record_material_usage(None)  # type: ignore
    assert s.generate_statistics()["total_material_usages"] == 0


def test_generate_statistics_structure():
    stats = get_lookdev_statistics().generate_statistics()
    for key in ("total_assignments", "total_reviews", "total_material_usages",
                "top_materials", "top_patterns", "average_review_score"):
        assert key in stats
