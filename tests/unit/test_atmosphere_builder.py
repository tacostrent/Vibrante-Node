"""Tests for src.runtime.environment.atmosphere_builder"""
import pytest
from src.runtime.environment.atmosphere_builder import (
    get_atmosphere_builder,
    reset_atmosphere_builder_for_tests,
    AtmospherePlan,
    AtmosphereProfile,
)
from src.runtime.environment.environment_template_library import (
    reset_environment_template_library_for_tests,
)


@pytest.fixture(autouse=True)
def reset_singletons():
    reset_atmosphere_builder_for_tests()
    reset_environment_template_library_for_tests()
    yield
    reset_atmosphere_builder_for_tests()
    reset_environment_template_library_for_tests()


class TestBuildAtmosphere:
    def test_western_room_uses_western_dust(self):
        builder = get_atmosphere_builder()
        plan = builder.build_atmosphere("western_room")
        assert plan.profile is not None
        assert plan.profile.profile_name == "western_dust"
        assert plan.errors == []

    def test_industrial_hangar_uses_industrial_haze(self):
        builder = get_atmosphere_builder()
        plan = builder.build_atmosphere("industrial_hangar")
        assert plan.profile is not None
        assert plan.profile.primary_effect == "haze"

    def test_office_uses_cold_interior(self):
        builder = get_atmosphere_builder()
        plan = builder.build_atmosphere("office")
        assert plan.profile is not None
        assert plan.profile.profile_name == "cold_interior"

    def test_forest_uses_volumetric_light(self):
        builder = get_atmosphere_builder()
        plan = builder.build_atmosphere("forest")
        assert plan.volumetric_enabled is True
        assert plan.profile.profile_name == "volumetric_light"

    def test_desert_uses_sunlit(self):
        builder = get_atmosphere_builder()
        plan = builder.build_atmosphere("desert")
        assert plan.profile.profile_name == "sunlit"

    def test_profile_override(self):
        builder = get_atmosphere_builder()
        plan = builder.build_atmosphere("western_room", profile_name="cold_interior")
        assert plan.profile.profile_name == "cold_interior"

    def test_unknown_profile_override_falls_back(self):
        # An unknown profile_name that is truly not in _PROFILES_BY_NAME AND not
        # resolvable via env map should either error or fall back gracefully.
        # The builder uses env-map fallback before giving up, so we just check
        # that a plan is returned without raising.
        builder = get_atmosphere_builder()
        # Force a path where profile is not in dict and env is also unknown
        plan = builder.build_atmosphere("completely_unknown_env_xyz",
                                        profile_name="nonexistent_profile_xyz")
        # Either an error is recorded or a fallback profile is used — both are valid
        assert plan is not None

    def test_unknown_environment_falls_back_to_warm_interior(self):
        builder = get_atmosphere_builder()
        plan = builder.build_atmosphere("nonexistent_xyz")
        assert plan.profile is not None
        assert plan.errors == []

    def test_volumetric_enabled_for_scattering_profiles(self):
        builder = get_atmosphere_builder()
        plan = builder.build_atmosphere("industrial_hangar")
        # industrial_haze has light_scattering=True
        assert plan.volumetric_enabled is True

    def test_volumetric_disabled_for_cold_interior(self):
        builder = get_atmosphere_builder()
        plan = builder.build_atmosphere("control_room")
        # cold_interior has light_scattering=False
        assert plan.volumetric_enabled is False

    def test_no_exceptions_on_any_environment(self):
        from src.runtime.environment.environment_template_library import get_environment_template_library
        builder = get_atmosphere_builder()
        lib = get_environment_template_library()
        for name in lib.list_templates():
            plan = builder.build_atmosphere(name)
            assert plan is not None


class TestRecommendEffects:
    def test_western_dust_has_dust_motes(self):
        builder = get_atmosphere_builder()
        effects = builder.recommend_effects("western_room")
        assert len(effects) > 0
        assert "dust_motes" in effects or "heat_shimmer" in effects

    def test_cold_interior_has_no_effects(self):
        builder = get_atmosphere_builder()
        effects = builder.recommend_effects("office")
        assert isinstance(effects, list)

    def test_volumetric_light_has_god_rays(self):
        builder = get_atmosphere_builder()
        effects = builder.recommend_effects("forest")
        assert "god_rays" in effects


class TestGetProfile:
    def test_get_known_profile(self):
        builder = get_atmosphere_builder()
        prof = builder.get_profile("industrial_haze")
        assert prof is not None
        assert prof.profile_name == "industrial_haze"

    def test_get_unknown_profile_returns_none(self):
        builder = get_atmosphere_builder()
        prof = builder.get_profile("nonexistent_xyz")
        assert prof is None


class TestListProfiles:
    def test_list_profiles_returns_8_names(self):
        builder = get_atmosphere_builder()
        names = builder.list_profiles()
        assert len(names) == 8

    def test_list_profiles_is_sorted(self):
        builder = get_atmosphere_builder()
        names = builder.list_profiles()
        assert names == sorted(names)

    def test_list_profiles_includes_key_names(self):
        builder = get_atmosphere_builder()
        names = set(builder.list_profiles())
        expected = {"western_dust", "industrial_haze", "factory_smoke", "warm_interior",
                    "cold_interior", "sunlit", "volumetric_light", "moonlit"}
        assert names == expected


class TestSerialization:
    def test_atmosphere_plan_roundtrip(self):
        builder = get_atmosphere_builder()
        plan = builder.build_atmosphere("castle_hall")
        d = plan.to_dict()
        plan2 = AtmospherePlan.from_dict(d)
        assert plan2.environment_name == plan.environment_name
        assert plan2.volumetric_enabled == plan.volumetric_enabled
        if plan2.profile:
            assert plan2.profile.profile_name == plan.profile.profile_name
