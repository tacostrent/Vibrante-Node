"""
Tests for environment workflow packs (§39 — Environment Expansion Pack)
"""
import pytest

from src.runtime.workflows.workflow_pack import (
    WorkflowPack,
    VALID_ENVIRONMENT_TYPES,
    PACK_SCHEMA_VERSION,
    get_builtin_packs,
    reset_workflow_pack_for_tests,
)


@pytest.fixture(autouse=True)
def reset():
    reset_workflow_pack_for_tests()
    yield
    reset_workflow_pack_for_tests()


# ---------------------------------------------------------------------------
# VALID_ENVIRONMENT_TYPES
# ---------------------------------------------------------------------------

def test_valid_environment_types_has_55():
    assert len(VALID_ENVIRONMENT_TYPES) == 55


def test_valid_types_original_5_present():
    originals = {"industrial_hangar", "robotics_lab", "control_room", "sci_fi_corridor", "abandoned_factory"}
    assert originals <= VALID_ENVIRONMENT_TYPES


def test_valid_types_industrial_expansion():
    for env in ["warehouse", "shipyard", "oil_refinery", "power_station", "mining_facility", "construction_site"]:
        assert env in VALID_ENVIRONMENT_TYPES


def test_valid_types_nature():
    for env in ["forest", "jungle", "desert", "canyon", "mountain", "coastline", "swamp"]:
        assert env in VALID_ENVIRONMENT_TYPES


def test_valid_types_fantasy():
    for env in ["castle_hall", "dungeon", "wizard_tower", "ancient_ruins", "temple"]:
        assert env in VALID_ENVIRONMENT_TYPES


def test_valid_types_post_apocalyptic():
    for env in ["abandoned_city", "destroyed_highway", "ruined_industrial_site", "survival_camp"]:
        assert env in VALID_ENVIRONMENT_TYPES


# ---------------------------------------------------------------------------
# Builtin pack count and content
# ---------------------------------------------------------------------------

def test_13_builtin_packs():
    packs = get_builtin_packs()
    assert len(packs) == 13


def test_original_5_packs_present():
    packs = get_builtin_packs()
    names = {p.name for p in packs}
    assert "industrial_hangar_pack" in names
    assert "robotics_lab_pack" in names
    assert "control_room_pack" in names
    assert "sci_fi_corridor_pack" in names
    assert "abandoned_factory_pack" in names


def test_8_new_packs_present():
    packs = get_builtin_packs()
    names = {p.name for p in packs}
    expected = {
        "western_room_pack", "space_station_pack", "research_lab_pack",
        "forest_pack", "city_street_pack", "castle_hall_pack",
        "military_base_pack", "survival_camp_pack",
    }
    assert expected <= names


def test_all_packs_valid():
    packs = get_builtin_packs()
    for pack in packs:
        errors = pack.validate()
        assert errors == [], f"{pack.name}: {errors}"


# ---------------------------------------------------------------------------
# Individual pack properties
# ---------------------------------------------------------------------------

def test_western_room_pack_warm_lighting():
    packs = get_builtin_packs()
    pack = next(p for p in packs if p.name == "western_room_pack")
    assert pack.environment_type == "western_room"
    assert "warm" in pack.lighting_strategy.get("style", "").lower() or \
           "lantern" in pack.lighting_strategy.get("style", "").lower()
    assert pack.review_strategy["production_threshold"] > 0


def test_forest_pack_natural_lighting():
    packs = get_builtin_packs()
    pack = next(p for p in packs if p.name == "forest_pack")
    assert pack.environment_type == "forest"
    assert "vegetation" in pack.asset_strategy["hero_categories"] or \
           "terrain" in pack.asset_strategy["hero_categories"]
    assert pack.atmosphere_strategy["fog_density"] in ("medium", "heavy", "light")


def test_space_station_pack_cool_atmosphere():
    packs = get_builtin_packs()
    pack = next(p for p in packs if p.name == "space_station_pack")
    assert pack.environment_type == "space_station"
    assert pack.atmosphere_strategy["fog_density"] == "none"


def test_military_base_pack():
    packs = get_builtin_packs()
    pack = next(p for p in packs if p.name == "military_base_pack")
    assert pack.environment_type == "military_base"
    assert "vehicle" in pack.asset_strategy["hero_categories"] or \
           "structure" in pack.asset_strategy["hero_categories"]


def test_survival_camp_pack_has_fog():
    packs = get_builtin_packs()
    pack = next(p for p in packs if p.name == "survival_camp_pack")
    assert pack.environment_type == "survival_camp"
    assert pack.atmosphere_strategy["fog_density"] in ("medium", "heavy")


def test_castle_hall_pack():
    packs = get_builtin_packs()
    pack = next(p for p in packs if p.name == "castle_hall_pack")
    assert pack.environment_type == "castle_hall"
    assert "furniture" in pack.asset_strategy["hero_categories"] or \
           "architecture" in pack.asset_strategy["hero_categories"]


# ---------------------------------------------------------------------------
# Pack serialization
# ---------------------------------------------------------------------------

def test_pack_to_dict_from_dict_roundtrip():
    packs = get_builtin_packs()
    for pack in packs:
        d = pack.to_dict()
        restored = WorkflowPack.from_dict(d)
        assert restored.name == pack.name
        assert restored.environment_type == pack.environment_type
        assert restored.schema_version == PACK_SCHEMA_VERSION


def test_pack_to_json_from_json_roundtrip():
    packs = get_builtin_packs()
    pack = packs[0]
    j = pack.to_json()
    restored = WorkflowPack.from_json(j)
    assert restored.name == pack.name


# ---------------------------------------------------------------------------
# Clone with new environment type
# ---------------------------------------------------------------------------

def test_clone_changes_environment_type():
    packs = get_builtin_packs()
    original = packs[0]
    cloned = original.clone(environment_type="forest")
    assert cloned.environment_type == "forest"
    assert cloned.name == original.name
    assert cloned.pack_id != original.pack_id


def test_clone_invalid_environment_still_validates():
    packs = get_builtin_packs()
    original = packs[0]
    cloned = original.clone(environment_type="invalid_env")
    errors = cloned.validate()
    assert any("environment_type" in e for e in errors)


# ---------------------------------------------------------------------------
# Custom pack for new environment
# ---------------------------------------------------------------------------

def test_create_custom_pack_for_new_env():
    pack = WorkflowPack(
        name="jungle_pack",
        version="1.0.0",
        environment_type="jungle",
        asset_strategy={"hero_categories": ["vegetation", "terrain"], "max_hero_assets": 2,
                        "preferred_formats": ["fbx"], "deduplication": True},
        population_strategy={"hero_max": 2, "detail_cap": 0.5, "balance": "standard"},
        placement_strategy={"template": "jungle", "back_to_front": True, "deterministic": True},
        lighting_strategy={"style": "tropical_diffuse", "key_target": "hero_zone", "volumetric": True},
        camera_strategy={"mode": "atmospheric_tracking", "establishing_shot": True, "hero_shot": True},
        atmosphere_strategy={"atmosphere_type": "jungle_mist", "fog_density": "medium", "particles": True},
        review_strategy={"production_threshold": 0.65, "require_hero": True, "require_depth": True,
                         "min_readability": 0.60},
    )
    errors = pack.validate()
    assert errors == []


def test_pack_validates_forest_environment():
    pack = WorkflowPack(
        name="test_forest",
        version="1.0.0",
        environment_type="forest",
        asset_strategy={"hero_categories": ["vegetation"], "max_hero_assets": 2,
                        "preferred_formats": ["fbx"], "deduplication": True},
        population_strategy={"hero_max": 2, "detail_cap": 0.5, "balance": "standard"},
        placement_strategy={"template": "forest", "back_to_front": True, "deterministic": True},
        lighting_strategy={"style": "natural_forest", "key_target": "hero_zone", "volumetric": True},
        camera_strategy={"mode": "atmospheric", "establishing_shot": True, "hero_shot": True},
        atmosphere_strategy={"atmosphere_type": "forest_mist", "fog_density": "medium", "particles": True},
        review_strategy={"production_threshold": 0.65, "require_hero": True, "require_depth": True,
                         "min_readability": 0.55},
    )
    assert pack.validate() == []
