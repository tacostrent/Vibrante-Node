"""Tests for ArchitecturalTemplates (Tier 9.5)."""

import pytest
from src.runtime.assets.assembly.architectural_templates import (
    ArchitecturalTemplates,
    get_architectural_templates,
    reset_architectural_templates_for_tests,
    SUPPORTED_ENVIRONMENTS,
)
from src.runtime.assets.assembly.environment_blueprint import EnvironmentBlueprint


@pytest.fixture(autouse=True)
def reset():
    reset_architectural_templates_for_tests()
    yield
    reset_architectural_templates_for_tests()


class TestArchitecturalTemplatesSingleton:
    def test_singleton_returns_same_instance(self):
        a = get_architectural_templates()
        b = get_architectural_templates()
        assert a is b

    def test_reset_creates_fresh_instance(self):
        a = get_architectural_templates()
        reset_architectural_templates_for_tests()
        b = get_architectural_templates()
        assert a is not b


class TestSupportedEnvironments:
    def test_all_required_environments_present(self):
        required = {
            "western_room", "saloon", "living_room", "office", "hotel_lobby",
            "restaurant", "library", "industrial_hangar", "warehouse",
            "abandoned_factory", "robotics_lab", "research_lab", "medical_lab",
            "control_room", "sci_fi_corridor", "space_station", "city_street",
            "forest", "desert", "castle_hall", "survival_camp",
        }
        assert required.issubset(SUPPORTED_ENVIRONMENTS)

    def test_list_environments_is_sorted(self):
        tpl = get_architectural_templates()
        names = tpl.list_environments()
        assert names == sorted(names)

    def test_supports_returns_true_for_known(self):
        tpl = get_architectural_templates()
        assert tpl.supports("industrial_hangar") is True

    def test_supports_returns_false_for_unknown(self):
        tpl = get_architectural_templates()
        assert tpl.supports("imaginary_spaceship_deck") is False


class TestGetTemplate:
    def test_western_room_has_floor_required(self):
        tpl = get_architectural_templates()
        bp = tpl.get_template("western_room")
        assert bp.floor_required is True
        assert bp.wall_required is True

    def test_western_room_has_anchor_assets(self):
        tpl = get_architectural_templates()
        bp = tpl.get_template("western_room")
        assert "table" in bp.anchor_assets
        assert len(bp.anchor_assets) >= 2

    def test_industrial_hangar_has_structural_assets(self):
        tpl = get_architectural_templates()
        bp = tpl.get_template("industrial_hangar")
        types = bp.structural_assets
        assert any("floor" in t or "concrete" in t for t in types)
        assert any("wall" in t for t in types)

    def test_castle_hall_requires_ceiling_and_door_and_window(self):
        tpl = get_architectural_templates()
        bp = tpl.get_template("castle_hall")
        assert bp.ceiling_required is True
        assert bp.door_required is True
        assert bp.window_required is True

    def test_forest_does_not_require_wall(self):
        tpl = get_architectural_templates()
        bp = tpl.get_template("forest")
        assert bp.wall_required is False

    def test_desert_does_not_require_ceiling(self):
        tpl = get_architectural_templates()
        bp = tpl.get_template("desert")
        assert bp.ceiling_required is False

    def test_unknown_env_returns_generic_fallback(self):
        tpl = get_architectural_templates()
        bp = tpl.get_template("made_up_environment_xyz")
        assert isinstance(bp, EnvironmentBlueprint)
        assert bp.environment_name == "generic"
        assert bp.floor_required is True

    def test_all_templates_have_structural_assets(self):
        tpl = get_architectural_templates()
        for env in tpl.list_environments():
            bp = tpl.get_template(env)
            assert len(bp.structural_assets) > 0, f"{env} has no structural_assets"

    def test_all_templates_have_anchor_assets(self):
        tpl = get_architectural_templates()
        for env in tpl.list_environments():
            bp = tpl.get_template(env)
            assert len(bp.anchor_assets) > 0, f"{env} has no anchor_assets"

    def test_all_templates_have_atmosphere_assets(self):
        tpl = get_architectural_templates()
        for env in tpl.list_environments():
            bp = tpl.get_template(env)
            assert len(bp.atmosphere_assets) > 0, f"{env} has no atmosphere_assets"


class TestGetters:
    def test_get_anchor_types(self):
        tpl = get_architectural_templates()
        anchors = tpl.get_anchor_types("western_room")
        assert "table" in anchors

    def test_get_structural_requirements_western_room(self):
        tpl = get_architectural_templates()
        req = tpl.get_structural_requirements("western_room")
        assert req["floor_required"] is True
        assert req["wall_required"] is True
        assert "ceiling_required" in req

    def test_get_structural_requirements_forest(self):
        tpl = get_architectural_templates()
        req = tpl.get_structural_requirements("forest")
        assert req["wall_required"] is False
