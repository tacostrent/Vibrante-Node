"""
Tests for AssetEnvironmentMapper expansion to 55 environments (§39)
"""
import pytest

from src.runtime.assets.semantic.asset_environment_mapper import (
    BUILTIN_ENVIRONMENTS,
    AssetEnvironmentMapper,
    EnvironmentMapping,
    get_asset_environment_mapper,
    reset_asset_environment_mapper_for_tests,
)


@pytest.fixture(autouse=True)
def reset():
    reset_asset_environment_mapper_for_tests()
    yield
    reset_asset_environment_mapper_for_tests()


# ---------------------------------------------------------------------------
# BUILTIN_ENVIRONMENTS constant
# ---------------------------------------------------------------------------

def test_55_environments():
    assert len(BUILTIN_ENVIRONMENTS) == 55


def test_original_5_present():
    assert "industrial_hangar" in BUILTIN_ENVIRONMENTS
    assert "robotics_lab" in BUILTIN_ENVIRONMENTS
    assert "control_room" in BUILTIN_ENVIRONMENTS
    assert "sci_fi_corridor" in BUILTIN_ENVIRONMENTS
    assert "abandoned_factory" in BUILTIN_ENVIRONMENTS


def test_industrial_category_all_present():
    for env in ["warehouse", "shipyard", "oil_refinery", "power_station",
                "mining_facility", "construction_site"]:
        assert env in BUILTIN_ENVIRONMENTS


def test_scientific_category_all_present():
    for env in ["research_lab", "medical_lab", "clean_room", "biohazard_facility"]:
        assert env in BUILTIN_ENVIRONMENTS


def test_military_category_all_present():
    for env in ["military_base", "command_center", "military_hangar", "checkpoint", "bunker"]:
        assert env in BUILTIN_ENVIRONMENTS


def test_scifi_category_all_present():
    for env in ["space_station", "spaceship_bridge", "engineering_bay", "alien_facility", "cyberpunk_city"]:
        assert env in BUILTIN_ENVIRONMENTS


def test_urban_category_all_present():
    for env in ["city_street", "alleyway", "subway_station", "parking_garage", "rooftop", "shopping_mall"]:
        assert env in BUILTIN_ENVIRONMENTS


def test_interior_category_all_present():
    for env in ["western_room", "saloon", "living_room", "office",
                "hotel_lobby", "restaurant", "workshop", "library"]:
        assert env in BUILTIN_ENVIRONMENTS


def test_nature_category_all_present():
    for env in ["forest", "jungle", "desert", "canyon", "mountain", "coastline", "swamp"]:
        assert env in BUILTIN_ENVIRONMENTS


def test_fantasy_category_all_present():
    for env in ["castle_hall", "dungeon", "wizard_tower", "ancient_ruins", "temple"]:
        assert env in BUILTIN_ENVIRONMENTS


def test_post_apoc_category_all_present():
    for env in ["abandoned_city", "destroyed_highway", "ruined_industrial_site", "survival_camp"]:
        assert env in BUILTIN_ENVIRONMENTS


# ---------------------------------------------------------------------------
# Keyword inference for new environments
# ---------------------------------------------------------------------------

def _map(tags, name="", category=""):
    mapper = get_asset_environment_mapper()
    return mapper.map_environments({"asset_id": "test", "name": name, "category": category, "tags": tags})


def test_forest_tree_asset():
    result = _map(["tree", "foliage", "woodland"])
    assert "forest" in result.environments


def test_jungle_vine_asset():
    result = _map(["jungle", "tropical", "vine"])
    assert "jungle" in result.environments


def test_desert_dune_asset():
    result = _map(["desert", "sand", "dune", "arid"])
    assert "desert" in result.environments


def test_canyon_rock_asset():
    result = _map(["canyon", "cliff", "red_rock"])
    assert "canyon" in result.environments


def test_swamp_murky_asset():
    result = _map(["swamp", "bayou", "murky", "cypress"])
    assert "swamp" in result.environments


def test_western_room_cowboy_asset():
    result = _map(["cowboy", "western", "rustic", "rope"])
    assert "western_room" in result.environments


def test_saloon_bar_asset():
    result = _map(["saloon", "bartender", "piano", "poker"])
    assert "saloon" in result.environments


def test_military_base_tank():
    result = _map(["military", "barracks", "tactical"])
    assert "military_base" in result.environments


def test_bunker_blast_door():
    result = _map(["bunker", "underground_bunker", "blast_door", "fortification"])
    assert "bunker" in result.environments


def test_space_station_orbital():
    result = _map(["orbital", "module_space", "astronaut", "solar_panel"])
    assert "space_station" in result.environments


def test_spaceship_bridge():
    result = _map(["bridge", "spaceship", "captain", "helm"])
    assert "spaceship_bridge" in result.environments


def test_alien_facility():
    result = _map(["alien", "bioluminescent", "organic", "xenomorph"])
    assert "alien_facility" in result.environments


def test_cyberpunk_neon():
    result = _map(["cyberpunk", "neon", "dystopia", "hologram"])
    assert "cyberpunk_city" in result.environments


def test_city_street_traffic():
    result = _map(["city", "street", "urban", "traffic", "downtown"])
    assert "city_street" in result.environments


def test_castle_hall_throne():
    result = _map(["castle", "throne", "tapestry", "stained_glass"])
    assert "castle_hall" in result.environments


def test_dungeon_chain():
    result = _map(["dungeon", "prison_cell", "chain", "dark_underground"])
    assert "dungeon" in result.environments


def test_wizard_tower_magic():
    result = _map(["wizard", "mage", "spell", "arcane", "orb"])
    assert "wizard_tower" in result.environments


def test_temple_sacred():
    result = _map(["shrine", "sacred", "altar", "incense", "spiritual"])
    assert "temple" in result.environments


def test_survival_camp():
    result = _map(["campfire", "survival", "makeshift", "barricade"])
    assert "survival_camp" in result.environments


def test_abandoned_city():
    result = _map(["apocalyptic", "desolate", "overgrown_city", "post_apocalyptic"])
    assert "abandoned_city" in result.environments


# ---------------------------------------------------------------------------
# Category affinity
# ---------------------------------------------------------------------------

def test_vegetation_category_maps_to_forest():
    result = _map(["tree", "leaf"], category="vegetation")
    assert "forest" in result.environments


def test_weapon_category_maps_to_military():
    result = _map(["rifle", "gun"], category="weapon")
    assert any(e in result.environments for e in ["military_base", "military_hangar", "bunker", "dungeon"])


def test_creature_category_maps_to_nature():
    result = _map(["creature", "animal"], category="creature")
    assert any(e in result.environments for e in ["forest", "jungle", "swamp", "alien_facility"])


def test_terrain_maps_to_nature():
    result = _map(["terrain"], category="terrain")
    assert any(e in result.environments for e in ["desert", "canyon", "mountain", "forest"])


# ---------------------------------------------------------------------------
# rank_environment_fit
# ---------------------------------------------------------------------------

def test_rank_environment_fit_returns_all_envs():
    mapper = get_asset_environment_mapper()
    ranking = mapper.rank_environment_fit({"asset_id": "x", "name": "test", "tags": []})
    assert len(ranking) == 55


def test_rank_environment_fit_descending():
    mapper = get_asset_environment_mapper()
    ranking = mapper.rank_environment_fit({
        "asset_id": "x",
        "name": "forest tree",
        "tags": ["tree", "foliage"],
    })
    scores = [r["score"] for r in ranking]
    assert scores == sorted(scores, reverse=True)


def test_rank_with_explicit_env_list():
    mapper = get_asset_environment_mapper()
    envs = ["forest", "desert", "jungle"]
    ranking = mapper.rank_environment_fit(
        {"asset_id": "x", "tags": ["tree", "foliage"]},
        environments=envs,
    )
    assert len(ranking) == 3
    assert ranking[0]["environment"] in envs


# ---------------------------------------------------------------------------
# EnvironmentMapping dataclass
# ---------------------------------------------------------------------------

def test_environment_mapping_to_dict():
    em = EnvironmentMapping(
        asset_id="a1",
        environments=["forest", "jungle"],
        scores={"forest": 0.8, "jungle": 0.4},
        primary="forest",
    )
    d = em.to_dict()
    assert d["asset_id"] == "a1"
    assert "forest" in d["environments"]
    assert d["primary"] == "forest"


def test_environment_mapping_roundtrip():
    original = EnvironmentMapping(
        asset_id="a2",
        environments=["desert"],
        scores={"desert": 0.7},
        primary="desert",
    )
    restored = EnvironmentMapping.from_dict(original.to_dict())
    assert restored.asset_id == original.asset_id
    assert restored.primary == original.primary


def test_environment_mapping_from_empty_dict():
    em = EnvironmentMapping.from_dict({})
    assert em.asset_id == ""
    assert em.environments == []
    assert em.primary == ""


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

def test_statistics_increments():
    mapper = get_asset_environment_mapper()
    mapper.map_environments({"asset_id": "x", "tags": ["tree"]})
    mapper.map_environments({"asset_id": "y", "tags": ["sand"]})
    stats = mapper.get_statistics()
    assert stats["map_count"] == 2


# ---------------------------------------------------------------------------
# Never raises
# ---------------------------------------------------------------------------

def test_map_none_does_not_raise():
    mapper = get_asset_environment_mapper()
    result = mapper.map_environments(None)  # type: ignore
    assert isinstance(result, EnvironmentMapping)


def test_map_empty_dict_does_not_raise():
    mapper = get_asset_environment_mapper()
    result = mapper.map_environments({})
    assert isinstance(result, EnvironmentMapping)


def test_rank_none_does_not_raise():
    mapper = get_asset_environment_mapper()
    result = mapper.rank_environment_fit(None)  # type: ignore
    assert isinstance(result, list)
