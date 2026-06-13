import pytest
from src.runtime.lookdev import (
    SUPPORTED_RENDERERS,
    RendererProfile,
    get_renderer_profiles,
    reset_renderer_profiles_for_tests,
)


@pytest.fixture(autouse=True)
def reset_singleton():
    reset_renderer_profiles_for_tests()
    yield
    reset_renderer_profiles_for_tests()


def test_singleton_identity():
    assert get_renderer_profiles() is get_renderer_profiles()


def test_supported_renderers_set():
    assert "arnold" in SUPPORTED_RENDERERS
    assert "karma" in SUPPORTED_RENDERERS
    assert "usd_preview_surface" in SUPPORTED_RENDERERS
    assert len(SUPPORTED_RENDERERS) == 3


def test_arnold_profile_material_class():
    profile = get_renderer_profiles().get_profile("arnold")
    assert profile.material_class == "standard_surface"
    assert profile.renderer == "arnold"


def test_karma_profile_material_class():
    profile = get_renderer_profiles().get_profile("karma")
    assert profile.material_class == "mtlxstandard_surface"
    assert profile.renderer == "karma"


def test_usd_profile_material_class():
    profile = get_renderer_profiles().get_profile("usd_preview_surface")
    assert profile.material_class == "UsdPreviewSurface"
    assert profile.renderer == "usd_preview_surface"


def test_arnold_supports_displacement():
    profile = get_renderer_profiles().get_profile("arnold")
    assert profile.supports_displacement is True


def test_usd_no_displacement():
    profile = get_renderer_profiles().get_profile("usd_preview_surface")
    assert profile.supports_displacement is False


def test_unknown_renderer_fallback():
    profile = get_renderer_profiles().get_profile("unknown_renderer")
    assert profile.material_class == "UsdPreviewSurface"


def test_validate_renderer_support_true():
    assert get_renderer_profiles().validate_renderer_support("arnold") is True
    assert get_renderer_profiles().validate_renderer_support("karma") is True


def test_validate_renderer_support_false():
    assert get_renderer_profiles().validate_renderer_support("mantra") is False
    assert get_renderer_profiles().validate_renderer_support("") is False


def test_map_material_returns_dict():
    mapping = get_renderer_profiles().map_material("industrial_metal", "arnold")
    assert isinstance(mapping, dict)
    assert mapping["renderer"] == "arnold"
    assert mapping["material_class"] == "standard_surface"
    assert "base_color_input" in mapping
    assert "roughness_input" in mapping


def test_map_material_arnold_roughness_input():
    mapping = get_renderer_profiles().map_material("concrete", "arnold")
    assert mapping["roughness_input"] == "specular_roughness"


def test_map_material_usd_roughness_input():
    mapping = get_renderer_profiles().map_material("concrete", "usd_preview_surface")
    assert mapping["roughness_input"] == "roughness"


def test_renderer_profile_to_dict_keys():
    profile = RendererProfile(renderer="arnold", material_class="standard_surface")
    d = profile.to_dict()
    for key in ("renderer", "material_class", "properties", "supports_displacement",
                "supports_subsurface", "supported_maps"):
        assert key in d


def test_renderer_profile_from_dict_round_trip():
    p = RendererProfile(renderer="karma", material_class="mtlxstandard_surface",
                        supports_displacement=True, supported_maps=["base_color"])
    restored = RendererProfile.from_dict(p.to_dict())
    assert restored.renderer == "karma"
    assert restored.material_class == "mtlxstandard_surface"
    assert restored.supports_displacement is True


def test_never_raises_none():
    profile = get_renderer_profiles().get_profile(None)  # type: ignore
    assert isinstance(profile, RendererProfile)
