"""
Tests for Environment Expansion Pack integration (§39)
Verifies that all new environments are properly integrated across all systems.
"""
import pytest

from src.runtime.environments.environment_registry import (
    BUILTIN_ENVIRONMENT_NAMES,
    get_environment_registry,
    reset_environment_registry_for_tests,
)
from src.runtime.assets.semantic.asset_environment_mapper import (
    BUILTIN_ENVIRONMENTS,
    get_asset_environment_mapper,
    reset_asset_environment_mapper_for_tests,
)
from src.runtime.assets.vector_search.intent_parser import (
    get_intent_parser,
    reset_intent_parser_for_tests,
)
from src.runtime.lighting.lighting_environment_mapper import (
    get_lighting_environment_mapper,
    reset_lighting_environment_mapper_for_tests,
)
from src.runtime.lighting.lighting_patterns import (
    get_lighting_patterns,
    reset_lighting_patterns_for_tests,
)
from src.runtime.capability_registry import (
    get_capability_registry,
    reset_capability_registry_for_tests,
)
from src.runtime.workflows.workflow_pack import (
    VALID_ENVIRONMENT_TYPES,
    get_builtin_packs,
    reset_workflow_pack_for_tests,
)


@pytest.fixture(autouse=True)
def reset_all():
    reset_environment_registry_for_tests()
    reset_asset_environment_mapper_for_tests()
    reset_intent_parser_for_tests()
    reset_lighting_environment_mapper_for_tests()
    reset_lighting_patterns_for_tests()
    reset_capability_registry_for_tests()
    reset_workflow_pack_for_tests()
    yield
    reset_environment_registry_for_tests()
    reset_asset_environment_mapper_for_tests()
    reset_intent_parser_for_tests()
    reset_lighting_environment_mapper_for_tests()
    reset_lighting_patterns_for_tests()
    reset_capability_registry_for_tests()
    reset_workflow_pack_for_tests()


# ---------------------------------------------------------------------------
# BUILTIN_ENVIRONMENTS in mapper matches registry
# ---------------------------------------------------------------------------

def test_mapper_environment_count():
    assert len(BUILTIN_ENVIRONMENTS) == 55


def test_mapper_contains_all_new_environments():
    new_envs = [
        "warehouse", "shipyard", "oil_refinery", "power_station",
        "mining_facility", "construction_site",
        "research_lab", "medical_lab", "clean_room", "biohazard_facility",
        "military_base", "command_center", "military_hangar", "checkpoint", "bunker",
        "space_station", "spaceship_bridge", "engineering_bay", "alien_facility", "cyberpunk_city",
        "city_street", "alleyway", "subway_station", "parking_garage", "rooftop", "shopping_mall",
        "western_room", "saloon", "living_room", "office", "hotel_lobby",
        "restaurant", "workshop", "library",
        "forest", "jungle", "desert", "canyon", "mountain", "coastline", "swamp",
        "castle_hall", "dungeon", "wizard_tower", "ancient_ruins", "temple",
        "abandoned_city", "destroyed_highway", "ruined_industrial_site", "survival_camp",
    ]
    for env in new_envs:
        assert env in BUILTIN_ENVIRONMENTS, f"Missing from BUILTIN_ENVIRONMENTS: {env}"


# ---------------------------------------------------------------------------
# Asset environment mapper keyword inference
# ---------------------------------------------------------------------------

def test_mapper_forest_asset():
    mapper = get_asset_environment_mapper()
    mapping = mapper.map_environments({
        "asset_id": "tree_001",
        "name": "Oak Tree",
        "category": "vegetation",
        "tags": ["tree", "foliage", "moss", "woodland"],
    })
    assert "forest" in mapping.environments


def test_mapper_western_room_asset():
    mapper = get_asset_environment_mapper()
    mapping = mapper.map_environments({
        "asset_id": "barrel_001",
        "name": "Wooden Barrel",
        "category": "prop",
        "tags": ["wood", "barrel_western", "rustic"],
    })
    assert "western_room" in mapping.environments or "saloon" in mapping.environments


def test_mapper_military_vehicle():
    mapper = get_asset_environment_mapper()
    mapping = mapper.map_environments({
        "asset_id": "tank_001",
        "name": "Military Tank",
        "category": "vehicle",
        "tags": ["military", "tank"],
    })
    assert "military_base" in mapping.environments or "military_hangar" in mapping.environments


def test_mapper_castle_asset():
    mapper = get_asset_environment_mapper()
    mapping = mapper.map_environments({
        "asset_id": "throne_001",
        "name": "Royal Throne",
        "category": "furniture",
        "tags": ["throne", "castle", "tapestry"],
    })
    assert "castle_hall" in mapping.environments


def test_mapper_space_station_asset():
    mapper = get_asset_environment_mapper()
    mapping = mapper.map_environments({
        "asset_id": "module_001",
        "name": "Space Station Module",
        "category": "structure",
        "tags": ["orbital", "module_space", "astronaut"],
    })
    assert "space_station" in mapping.environments


def test_mapper_survival_camp_asset():
    mapper = get_asset_environment_mapper()
    mapping = mapper.map_environments({
        "asset_id": "fire_001",
        "name": "Campfire",
        "category": "prop",
        "tags": ["campfire", "survival", "makeshift"],
    })
    assert "survival_camp" in mapping.environments


def test_mapper_returns_environment_mapping_never_raises():
    mapper = get_asset_environment_mapper()
    result = mapper.map_environments(None)  # type: ignore
    assert result is not None


# ---------------------------------------------------------------------------
# Intent parser environment recognition
# ---------------------------------------------------------------------------

def test_intent_parser_western_room():
    parser = get_intent_parser()
    intent = parser.parse("cowboy saloon western")
    assert intent.environment in ("western_room", "saloon")


def test_intent_parser_space_station():
    parser = get_intent_parser()
    intent = parser.parse("space station orbital module")
    assert intent.environment == "space_station"


def test_intent_parser_military_base():
    parser = get_intent_parser()
    intent = parser.parse("military barracks tactical base")
    assert intent.environment in ("military_base", "command_center")


def test_intent_parser_forest():
    parser = get_intent_parser()
    intent = parser.parse("deep forest woodland trees")
    assert intent.environment == "forest"


def test_intent_parser_castle():
    parser = get_intent_parser()
    intent = parser.parse("medieval castle hall")
    assert intent.environment == "castle_hall"


def test_intent_parser_survival():
    parser = get_intent_parser()
    intent = parser.parse("post apocalyptic survival camp fire")
    assert intent.environment in ("survival_camp", "abandoned_city")


def test_intent_parser_cyberpunk():
    parser = get_intent_parser()
    intent = parser.parse("cyberpunk neon rain city")
    assert intent.environment == "cyberpunk_city"


# ---------------------------------------------------------------------------
# Lighting environment mapper profiles
# ---------------------------------------------------------------------------

def test_lighting_mapper_has_new_environments():
    mapper = get_lighting_environment_mapper()
    new_envs = [
        "warehouse", "western_room", "forest", "military_base",
        "space_station", "castle_hall", "survival_camp", "cyberpunk_city",
        "desert", "dungeon", "swamp", "bunker",
    ]
    for env in new_envs:
        result = mapper.map_environment(env)
        assert len(result.recommended_sources) > 0, f"No sources for: {env}"


def test_lighting_mapper_western_room_is_warm():
    mapper = get_lighting_environment_mapper()
    result = mapper.map_environment("western_room")
    assert result.color_temperature == "warm"


def test_lighting_mapper_space_station_is_cool():
    mapper = get_lighting_environment_mapper()
    result = mapper.map_environment("space_station")
    assert result.color_temperature == "cool"


def test_lighting_mapper_forest_has_volumetrics():
    mapper = get_lighting_environment_mapper()
    result = mapper.map_environment("forest")
    assert result.volumetrics is True


def test_lighting_mapper_desert_high_exposure():
    mapper = get_lighting_environment_mapper()
    result = mapper.map_environment("desert")
    assert result.exposure_ev > 0


def test_lighting_mapper_dungeon_very_dark():
    mapper = get_lighting_environment_mapper()
    result = mapper.map_environment("dungeon")
    assert result.exposure_ev < -2.0


def test_lighting_mapper_list_environments_includes_new():
    mapper = get_lighting_environment_mapper()
    envs = mapper.list_environments()
    assert "forest" in envs
    assert "castle_hall" in envs
    assert "cyberpunk_city" in envs


# ---------------------------------------------------------------------------
# Lighting patterns for new environments
# ---------------------------------------------------------------------------

def test_lighting_patterns_has_western_room():
    patterns = get_lighting_patterns()
    result = patterns.search_patterns(environment="western_room")
    assert len(result) > 0


def test_lighting_patterns_has_space_station():
    patterns = get_lighting_patterns()
    result = patterns.search_patterns(environment="space_station")
    assert len(result) > 0


def test_lighting_patterns_has_forest():
    patterns = get_lighting_patterns()
    result = patterns.search_patterns(environment="forest")
    assert len(result) > 0


def test_lighting_patterns_western_room_warm():
    patterns = get_lighting_patterns()
    result = patterns.search_patterns(environment="western_room")
    assert result[0].color_temperature == "warm"


def test_lighting_patterns_cyberpunk_cool():
    patterns = get_lighting_patterns()
    result = patterns.search_patterns(environment="cyberpunk_city")
    assert result[0].color_temperature == "cool"


# ---------------------------------------------------------------------------
# Capability registry
# ---------------------------------------------------------------------------

def test_capability_registry_has_new_environment_caps():
    reg = get_capability_registry()
    assert reg.supports("environment_registry")
    assert reg.supports("environment_expansion")
    assert reg.supports("environment_statistics")
    assert reg.supports("environment_recommendation")
    assert reg.supports("environment_workflow_pack")


# ---------------------------------------------------------------------------
# Workflow packs
# ---------------------------------------------------------------------------

def test_valid_environment_types_count():
    # 55 environments
    assert len(VALID_ENVIRONMENT_TYPES) == 55


def test_valid_environment_types_contains_new():
    assert "western_room" in VALID_ENVIRONMENT_TYPES
    assert "space_station" in VALID_ENVIRONMENT_TYPES
    assert "forest" in VALID_ENVIRONMENT_TYPES
    assert "castle_hall" in VALID_ENVIRONMENT_TYPES
    assert "survival_camp" in VALID_ENVIRONMENT_TYPES
    assert "military_base" in VALID_ENVIRONMENT_TYPES


def test_builtin_packs_count():
    packs = get_builtin_packs()
    # 5 original + 8 new = 13
    assert len(packs) == 13


def test_builtin_packs_include_new():
    packs = get_builtin_packs()
    names = {p.name for p in packs}
    assert "western_room_pack" in names
    assert "space_station_pack" in names
    assert "forest_pack" in names
    assert "castle_hall_pack" in names
    assert "military_base_pack" in names
    assert "survival_camp_pack" in names
    assert "research_lab_pack" in names
    assert "city_street_pack" in names


def test_all_builtin_packs_valid():
    packs = get_builtin_packs()
    for pack in packs:
        errors = pack.validate()
        assert errors == [], f"Pack {pack.name} validation errors: {errors}"
