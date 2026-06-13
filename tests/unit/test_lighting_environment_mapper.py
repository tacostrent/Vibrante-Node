"""Tests for LightingEnvironmentMapper (Tier 15)."""
import pytest
from src.runtime.lighting import (
    get_lighting_environment_mapper,
    reset_lighting_environment_mapper_for_tests,
    EnvironmentLightingMapping,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_lighting_environment_mapper_for_tests()
    yield
    reset_lighting_environment_mapper_for_tests()


class TestLightingEnvironmentMapper:
    def test_map_industrial_hangar(self):
        mapper = get_lighting_environment_mapper()
        m = mapper.map_environment("industrial_hangar")
        assert m.environment == "industrial_hangar"
        assert "industrial_fixture" in m.recommended_sources
        assert m.volumetrics is True

    def test_map_robotics_lab(self):
        mapper = get_lighting_environment_mapper()
        m = mapper.map_environment("robotics_lab")
        assert m.environment == "robotics_lab"
        assert m.volumetrics is False

    def test_map_alias_hangar(self):
        mapper = get_lighting_environment_mapper()
        m = mapper.map_environment("hangar")
        assert m.environment == "industrial_hangar"

    def test_map_alias_lab(self):
        mapper = get_lighting_environment_mapper()
        m = mapper.map_environment("lab")
        assert m.environment == "robotics_lab"

    def test_map_unknown_returns_default(self):
        mapper = get_lighting_environment_mapper()
        m = mapper.map_environment("unknown_xyz_environment")
        assert isinstance(m, EnvironmentLightingMapping)
        assert len(m.recommended_sources) >= 1

    def test_recommend_sources(self):
        mapper = get_lighting_environment_mapper()
        sources = mapper.recommend_sources("sci_fi_corridor")
        assert isinstance(sources, list)
        assert len(sources) >= 1

    def test_recommend_volumetrics(self):
        mapper = get_lighting_environment_mapper()
        assert mapper.recommend_volumetrics("abandoned_factory") is True
        assert mapper.recommend_volumetrics("robotics_lab") is False

    def test_recommend_exposure(self):
        mapper = get_lighting_environment_mapper()
        exp = mapper.recommend_exposure("night_exterior")
        assert "exposure_ev" in exp
        assert exp["exposure_ev"] < 0

    def test_list_environments(self):
        mapper = get_lighting_environment_mapper()
        envs = mapper.list_environments()
        assert "industrial_hangar" in envs
        assert "control_room" in envs

    def test_cool_temperature_for_lab(self):
        mapper = get_lighting_environment_mapper()
        m = mapper.map_environment("robotics_lab")
        assert m.color_temperature == "cool"

    def test_to_from_dict(self):
        mapper = get_lighting_environment_mapper()
        m = mapper.map_environment("control_room")
        d = m.to_dict()
        m2 = EnvironmentLightingMapping.from_dict(d)
        assert m2.environment == m.environment

    def test_singleton(self):
        assert get_lighting_environment_mapper() is get_lighting_environment_mapper()
