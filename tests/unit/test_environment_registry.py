"""
Tests for EnvironmentRegistry (§39 — Environment Expansion Pack)
"""
import pytest

from src.runtime.environments.environment_registry import (
    EnvironmentDefinition,
    EnvironmentRegistry,
    get_environment_registry,
    reset_environment_registry_for_tests,
    BUILTIN_ENVIRONMENT_NAMES,
    ALL_CATEGORIES,
    ENV_CATEGORY_INDUSTRIAL,
    ENV_CATEGORY_SCIENTIFIC,
    ENV_CATEGORY_MILITARY,
    ENV_CATEGORY_SCI_FI,
    ENV_CATEGORY_URBAN,
    ENV_CATEGORY_INTERIOR,
    ENV_CATEGORY_NATURE,
    ENV_CATEGORY_FANTASY,
    ENV_CATEGORY_POST_APOCALYPTIC,
)


@pytest.fixture(autouse=True)
def reset():
    reset_environment_registry_for_tests()
    yield
    reset_environment_registry_for_tests()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

def test_all_categories_present():
    assert ENV_CATEGORY_INDUSTRIAL in ALL_CATEGORIES
    assert ENV_CATEGORY_SCIENTIFIC in ALL_CATEGORIES
    assert ENV_CATEGORY_MILITARY in ALL_CATEGORIES
    assert ENV_CATEGORY_SCI_FI in ALL_CATEGORIES
    assert ENV_CATEGORY_URBAN in ALL_CATEGORIES
    assert ENV_CATEGORY_INTERIOR in ALL_CATEGORIES
    assert ENV_CATEGORY_NATURE in ALL_CATEGORIES
    assert ENV_CATEGORY_FANTASY in ALL_CATEGORIES
    assert ENV_CATEGORY_POST_APOCALYPTIC in ALL_CATEGORIES
    assert len(ALL_CATEGORIES) == 9


def test_builtin_environment_names_count():
    # 55 built-in environments
    assert len(BUILTIN_ENVIRONMENT_NAMES) == 55


def test_builtin_contains_original_5():
    original = {"industrial_hangar", "robotics_lab", "control_room", "sci_fi_corridor", "abandoned_factory"}
    assert original <= BUILTIN_ENVIRONMENT_NAMES


def test_builtin_contains_all_new_categories():
    # Sample checks across categories
    assert "warehouse" in BUILTIN_ENVIRONMENT_NAMES
    assert "space_station" in BUILTIN_ENVIRONMENT_NAMES
    assert "military_base" in BUILTIN_ENVIRONMENT_NAMES
    assert "forest" in BUILTIN_ENVIRONMENT_NAMES
    assert "western_room" in BUILTIN_ENVIRONMENT_NAMES
    assert "castle_hall" in BUILTIN_ENVIRONMENT_NAMES
    assert "survival_camp" in BUILTIN_ENVIRONMENT_NAMES


# ---------------------------------------------------------------------------
# Registry construction
# ---------------------------------------------------------------------------

def test_registry_creates_singleton():
    r1 = get_environment_registry()
    r2 = get_environment_registry()
    assert r1 is r2


def test_registry_has_55_environments():
    reg = get_environment_registry()
    assert reg.get_statistics()["total"] == 55


def test_all_categories_populated():
    reg = get_environment_registry()
    stats = reg.get_statistics()
    by_cat = stats["by_category"]
    assert by_cat[ENV_CATEGORY_INDUSTRIAL] == 8
    assert by_cat[ENV_CATEGORY_SCIENTIFIC] == 6
    assert by_cat[ENV_CATEGORY_MILITARY] == 5
    assert by_cat[ENV_CATEGORY_SCI_FI] == 6
    assert by_cat[ENV_CATEGORY_URBAN] == 6
    assert by_cat[ENV_CATEGORY_INTERIOR] == 8
    assert by_cat[ENV_CATEGORY_NATURE] == 7
    assert by_cat[ENV_CATEGORY_FANTASY] == 5
    assert by_cat[ENV_CATEGORY_POST_APOCALYPTIC] == 4


# ---------------------------------------------------------------------------
# get_environment
# ---------------------------------------------------------------------------

def test_get_existing_environment():
    reg = get_environment_registry()
    env = reg.get_environment("industrial_hangar")
    assert env is not None
    assert env.name == "industrial_hangar"
    assert env.category == ENV_CATEGORY_INDUSTRIAL


def test_get_new_environment_western_room():
    reg = get_environment_registry()
    env = reg.get_environment("western_room")
    assert env is not None
    assert env.category == ENV_CATEGORY_INTERIOR
    assert "wood" in env.keywords or "cowboy" in env.keywords
    assert "furniture" in env.asset_categories or "prop" in env.asset_categories


def test_get_space_station():
    reg = get_environment_registry()
    env = reg.get_environment("space_station")
    assert env is not None
    assert env.category == ENV_CATEGORY_SCI_FI
    assert "space" in env.keywords or "orbital" in env.keywords


def test_get_forest():
    reg = get_environment_registry()
    env = reg.get_environment("forest")
    assert env is not None
    assert env.category == ENV_CATEGORY_NATURE
    assert "tree" in env.keywords or "foliage" in env.keywords


def test_get_nonexistent_returns_none():
    reg = get_environment_registry()
    assert reg.get_environment("nonexistent_env") is None


def test_get_empty_string_returns_none():
    reg = get_environment_registry()
    assert reg.get_environment("") is None


# ---------------------------------------------------------------------------
# list_environments
# ---------------------------------------------------------------------------

def test_list_all_environments():
    reg = get_environment_registry()
    names = reg.list_environments()
    assert len(names) == 55
    assert "industrial_hangar" in names
    assert "survival_camp" in names


def test_list_by_category_industrial():
    reg = get_environment_registry()
    industrial = reg.list_environments(category=ENV_CATEGORY_INDUSTRIAL)
    assert len(industrial) == 8
    assert "industrial_hangar" in industrial
    assert "warehouse" in industrial
    assert "shipyard" in industrial


def test_list_by_category_nature():
    reg = get_environment_registry()
    nature = reg.list_environments(category=ENV_CATEGORY_NATURE)
    assert len(nature) == 7
    assert "forest" in nature
    assert "jungle" in nature
    assert "swamp" in nature


def test_list_by_category_fantasy():
    reg = get_environment_registry()
    fantasy = reg.list_environments(category=ENV_CATEGORY_FANTASY)
    assert len(fantasy) == 5
    assert "castle_hall" in fantasy
    assert "dungeon" in fantasy
    assert "temple" in fantasy


def test_list_by_category_post_apoc():
    reg = get_environment_registry()
    pa = reg.list_environments(category=ENV_CATEGORY_POST_APOCALYPTIC)
    assert len(pa) == 4
    assert "survival_camp" in pa
    assert "abandoned_city" in pa


def test_list_by_unknown_category_returns_empty():
    reg = get_environment_registry()
    result = reg.list_environments(category="nonexistent_category")
    assert result == []


# ---------------------------------------------------------------------------
# search_environments
# ---------------------------------------------------------------------------

def test_search_by_keyword():
    reg = get_environment_registry()
    results = reg.search_environments(query="cowboy")
    assert any(e.name == "western_room" for e in results)


def test_search_by_name_fragment():
    reg = get_environment_registry()
    results = reg.search_environments(query="factory")
    names = [e.name for e in results]
    assert "industrial_hangar" in names or "abandoned_factory" in names


def test_search_by_category_filter():
    reg = get_environment_registry()
    results = reg.search_environments(category=ENV_CATEGORY_MILITARY)
    assert len(results) == 5


def test_search_combined_query_and_category():
    reg = get_environment_registry()
    results = reg.search_environments(query="lab", category=ENV_CATEGORY_SCIENTIFIC)
    names = [e.name for e in results]
    assert any("lab" in n for n in names)


def test_search_returns_sorted():
    reg = get_environment_registry()
    results = reg.search_environments(category=ENV_CATEGORY_URBAN)
    names = [e.name for e in results]
    assert names == sorted(names)


def test_search_no_results():
    reg = get_environment_registry()
    results = reg.search_environments(query="zzznomatch")
    assert results == []


# ---------------------------------------------------------------------------
# get_by_category
# ---------------------------------------------------------------------------

def test_get_by_category_sci_fi():
    reg = get_environment_registry()
    sci_fi = reg.get_by_category(ENV_CATEGORY_SCI_FI)
    assert len(sci_fi) == 6
    names = {e.name for e in sci_fi}
    assert "sci_fi_corridor" in names
    assert "space_station" in names
    assert "cyberpunk_city" in names


# ---------------------------------------------------------------------------
# register_environment (custom)
# ---------------------------------------------------------------------------

def test_register_custom_environment():
    reg = get_environment_registry()
    custom = EnvironmentDefinition(
        name="test_custom_env",
        category=ENV_CATEGORY_INDUSTRIAL,
        description="A test environment",
        keywords=["test", "custom"],
    )
    reg.register_environment(custom)
    retrieved = reg.get_environment("test_custom_env")
    assert retrieved is not None
    assert retrieved.name == "test_custom_env"


def test_register_empty_name_is_noop():
    reg = get_environment_registry()
    before = reg.get_statistics()["total"]
    reg.register_environment(EnvironmentDefinition(name="", category="industrial", description=""))
    after = reg.get_statistics()["total"]
    assert after == before


# ---------------------------------------------------------------------------
# EnvironmentDefinition to_dict / from_dict
# ---------------------------------------------------------------------------

def test_environment_definition_roundtrip():
    reg = get_environment_registry()
    env = reg.get_environment("forest")
    assert env is not None
    d = env.to_dict()
    restored = EnvironmentDefinition.from_dict(d)
    assert restored.name == env.name
    assert restored.category == env.category
    assert restored.keywords == env.keywords
    assert restored.lighting_tags == env.lighting_tags


def test_environment_definition_from_dict_empty():
    env = EnvironmentDefinition.from_dict({})
    assert env.name == ""
    assert env.category == ""
    assert env.keywords == []


# ---------------------------------------------------------------------------
# All environments have required fields
# ---------------------------------------------------------------------------

def test_all_environments_have_name_and_category():
    reg = get_environment_registry()
    for name in BUILTIN_ENVIRONMENT_NAMES:
        env = reg.get_environment(name)
        assert env is not None, f"Missing: {name}"
        assert env.name == name
        assert env.category != "", f"No category for: {name}"


def test_all_environments_have_keywords():
    reg = get_environment_registry()
    for name in BUILTIN_ENVIRONMENT_NAMES:
        env = reg.get_environment(name)
        assert env is not None
        assert len(env.keywords) > 0, f"No keywords for: {name}"


def test_all_environments_have_asset_categories():
    reg = get_environment_registry()
    for name in BUILTIN_ENVIRONMENT_NAMES:
        env = reg.get_environment(name)
        assert env is not None
        assert len(env.asset_categories) > 0, f"No asset_categories for: {name}"
