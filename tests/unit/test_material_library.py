import pytest
from src.runtime.lookdev import (
    BUILTIN_MATERIAL_CATEGORIES,
    MaterialEntry,
    get_material_library,
    reset_material_library_for_tests,
)


@pytest.fixture(autouse=True)
def reset_singleton():
    reset_material_library_for_tests()
    yield
    reset_material_library_for_tests()


def test_singleton_identity():
    assert get_material_library() is get_material_library()


def test_builtin_materials_loaded():
    stats = get_material_library().get_statistics()
    assert stats["total_materials"] >= 13


def test_builtin_categories_count():
    assert len(BUILTIN_MATERIAL_CATEGORIES) == 13


def test_builtin_categories_include_expected():
    for expected in ("industrial_metal", "oxidized_pipe", "glass", "emissive_panel", "concrete"):
        assert expected in BUILTIN_MATERIAL_CATEGORIES


def test_search_by_name_rust():
    results = get_material_library().search_materials(query="rust")
    assert len(results) > 0
    assert any("rust" in m.name for m in results)


def test_search_by_tag():
    results = get_material_library().search_materials(query="corroded")
    assert len(results) > 0


def test_list_by_category():
    results = get_material_library().list_materials(category="glass")
    assert len(results) >= 1
    assert all(m.category == "glass" for m in results)


def test_register_material_returns_entry():
    lib = get_material_library()
    entry = lib.register_material("test_steel", "brushed_steel", description="A test.", tags=["test"])
    assert entry.material_id.startswith("mat_")
    assert entry.name == "test_steel"
    assert entry.category == "brushed_steel"
    assert "test" in entry.tags


def test_registered_material_is_findable():
    lib = get_material_library()
    entry = lib.register_material("findable_mat", "plastic")
    found = lib.get_material(entry.material_id)
    assert found is not None
    assert found.name == "findable_mat"


def test_remove_material():
    lib = get_material_library()
    entry = lib.register_material("removable", "plastic")
    assert lib.remove_material(entry.material_id) is True
    assert lib.get_material(entry.material_id) is None


def test_remove_nonexistent_returns_false():
    assert get_material_library().remove_material("nonexistent_xyz") is False


def test_material_entry_to_dict_keys():
    entry = MaterialEntry(name="metal", category="industrial_metal", properties={"roughness": 0.7})
    d = entry.to_dict()
    for key in ("material_id", "name", "category", "description", "properties", "tags", "created_at"):
        assert key in d


def test_material_entry_from_dict_round_trip():
    entry = MaterialEntry(name="round", category="plastic", tags=["a", "b"])
    restored = MaterialEntry.from_dict(entry.to_dict())
    assert restored.name == "round"
    assert restored.category == "plastic"
    assert restored.tags == ["a", "b"]


def test_material_entry_from_dict_missing_fields():
    entry = MaterialEntry.from_dict({})
    assert entry.name == ""
    assert entry.category == ""
    assert isinstance(entry.tags, list)


def test_get_statistics_structure():
    stats = get_material_library().get_statistics()
    assert "total_materials" in stats
    assert "by_category" in stats
    assert "register_calls" in stats


def test_never_raises_none_inputs():
    lib = get_material_library()
    results = lib.search_materials(query=None, category=None)  # type: ignore
    assert isinstance(results, list)
