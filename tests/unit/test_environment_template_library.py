"""Tests for src.runtime.environment.environment_template_library"""
import pytest
from src.runtime.environment.environment_template_library import (
    get_environment_template_library,
    reset_environment_template_library_for_tests,
    _BUILTIN_TEMPLATES,
)


@pytest.fixture(autouse=True)
def reset_singletons():
    reset_environment_template_library_for_tests()
    yield
    reset_environment_template_library_for_tests()


class TestEnvironmentTemplateLibraryTemplates:
    def test_all_20_templates_can_be_retrieved(self):
        lib = get_environment_template_library()
        names = lib.list_templates()
        assert len(names) >= 20
        for name in names:
            bp = lib.get_template(name)
            assert bp.environment_name == name

    def test_get_template_returns_generic_fallback_for_unknown(self):
        lib = get_environment_template_library()
        bp = lib.get_template("nonexistent_environment_xyz")
        assert bp.environment_name == "generic"
        assert "generic" in bp.description.lower() or "fallback" in bp.description.lower()

    def test_list_templates_returns_20_plus_names(self):
        lib = get_environment_template_library()
        names = lib.list_templates()
        assert len(names) >= 20

    def test_list_templates_is_sorted(self):
        lib = get_environment_template_library()
        names = lib.list_templates()
        assert names == sorted(names)

    def test_western_room_template(self):
        lib = get_environment_template_library()
        bp = lib.get_template("western_room")
        assert bp.environment_name == "western_room"
        assert bp.environment_category == "interior"
        assert "floor" in bp.required_structure or any("floor" in s for s in bp.required_structure)
        assert bp.atmosphere_profile == "western_dust"
        assert len(bp.required_anchors) >= 1

    def test_industrial_hangar_template(self):
        lib = get_environment_template_library()
        bp = lib.get_template("industrial_hangar")
        assert bp.environment_name == "industrial_hangar"
        assert bp.environment_category == "industrial"
        assert bp.atmosphere_profile == "industrial_haze"

    def test_castle_hall_template(self):
        lib = get_environment_template_library()
        bp = lib.get_template("castle_hall")
        assert bp.environment_category == "fantasy"
        assert "throne" in bp.required_anchors


class TestEnvironmentTemplateLibrarySearch:
    def test_get_by_category_interior(self):
        lib = get_environment_template_library()
        interiors = lib.get_by_category("interior")
        assert len(interiors) >= 5
        for bp in interiors:
            assert bp.environment_category == "interior"

    def test_get_by_category_industrial(self):
        lib = get_environment_template_library()
        industrial = lib.get_by_category("industrial")
        assert len(industrial) >= 2

    def test_get_by_category_fantasy(self):
        lib = get_environment_template_library()
        fantasy = lib.get_by_category("fantasy")
        assert len(fantasy) >= 2

    def test_get_by_category_unknown_returns_empty(self):
        lib = get_environment_template_library()
        result = lib.get_by_category("nonexistent_cat_xyz")
        assert result == []

    def test_search_by_name_keyword(self):
        lib = get_environment_template_library()
        results = lib.search("saloon")
        assert any(bp.environment_name == "saloon" for bp in results)

    def test_search_by_category_keyword(self):
        lib = get_environment_template_library()
        results = lib.search("industrial")
        assert len(results) >= 1

    def test_search_empty_query_returns_all(self):
        lib = get_environment_template_library()
        all_results = lib.search("")
        assert len(all_results) == len(_BUILTIN_TEMPLATES)

    def test_search_no_match_returns_empty(self):
        lib = get_environment_template_library()
        results = lib.search("zzz_no_match_xyz_abc")
        assert results == []


class TestEnvironmentTemplateLibrarySingleton:
    def test_singleton_returns_same_instance(self):
        lib1 = get_environment_template_library()
        lib2 = get_environment_template_library()
        assert lib1 is lib2

    def test_reset_creates_new_instance(self):
        lib1 = get_environment_template_library()
        reset_environment_template_library_for_tests()
        lib2 = get_environment_template_library()
        assert lib1 is not lib2
