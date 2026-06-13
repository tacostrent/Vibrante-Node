"""Tests for LightingPlanBuilder (Tier 15)."""
import pytest
from src.runtime.lighting import (
    get_lighting_plan_builder,
    reset_lighting_plan_builder_for_tests,
    reset_lighting_strategy_engine_for_tests,
    reset_lighting_mood_engine_for_tests,
    reset_lighting_environment_mapper_for_tests,
    reset_lighting_patterns_for_tests,
    reset_lighting_color_engine_for_tests,
    reset_lighting_exposure_engine_for_tests,
    reset_lighting_hierarchy_engine_for_tests,
    reset_lighting_knowledge_for_tests,
    LightPlan,
    LightingStrategy,
)


@pytest.fixture(autouse=True)
def _reset():
    for fn in [
        reset_lighting_plan_builder_for_tests,
        reset_lighting_strategy_engine_for_tests,
        reset_lighting_mood_engine_for_tests,
        reset_lighting_environment_mapper_for_tests,
        reset_lighting_patterns_for_tests,
        reset_lighting_color_engine_for_tests,
        reset_lighting_exposure_engine_for_tests,
        reset_lighting_hierarchy_engine_for_tests,
        reset_lighting_knowledge_for_tests,
    ]:
        fn()
    yield
    for fn in [
        reset_lighting_plan_builder_for_tests,
        reset_lighting_strategy_engine_for_tests,
        reset_lighting_mood_engine_for_tests,
        reset_lighting_environment_mapper_for_tests,
        reset_lighting_patterns_for_tests,
        reset_lighting_color_engine_for_tests,
        reset_lighting_exposure_engine_for_tests,
        reset_lighting_hierarchy_engine_for_tests,
        reset_lighting_knowledge_for_tests,
    ]:
        fn()


class TestLightingPlanBuilder:
    def test_build_plan_returns_light_plan(self):
        builder = get_lighting_plan_builder()
        plan = builder.build_plan(environment="industrial_hangar", mood="industrial")
        assert isinstance(plan, LightPlan)

    def test_key_light_present(self):
        builder = get_lighting_plan_builder()
        plan = builder.build_plan(environment="sci_fi_corridor", mood="dramatic")
        assert plan.key_light is not None
        assert plan.key_light.intensity > 0

    def test_fill_light_present(self):
        builder = get_lighting_plan_builder()
        plan = builder.build_plan(environment="control_room", mood="tense")
        assert plan.fill_light is not None

    def test_rim_light_present(self):
        builder = get_lighting_plan_builder()
        plan = builder.build_plan(environment="hero_reveal", mood="cinematic")
        assert plan.rim_light is not None

    def test_volumetrics_sci_fi(self):
        builder = get_lighting_plan_builder()
        plan = builder.build_plan(environment="sci_fi_corridor")
        assert plan.volumetrics.get("enabled") is True

    def test_no_volumetrics_lab(self):
        builder = get_lighting_plan_builder()
        plan = builder.build_plan(environment="robotics_lab")
        assert not plan.volumetrics.get("enabled", False)

    def test_color_strategy_set(self):
        builder = get_lighting_plan_builder()
        plan = builder.build_plan(environment="dramatic_interior", mood="dramatic")
        assert plan.color_strategy != {}

    def test_exposure_set(self):
        builder = get_lighting_plan_builder()
        plan = builder.build_plan(mood="dramatic")
        assert "ev_target" in plan.exposure

    def test_subjects_build_hierarchy(self):
        builder = get_lighting_plan_builder()
        plan = builder.build_plan(subjects=["hero_robot", "support_crate"])
        assert "hero" in plan.hierarchy_notes
        assert "hero_robot" in plan.hierarchy_notes["hero"]

    def test_build_from_strategy(self):
        builder = get_lighting_plan_builder()
        strategy = LightingStrategy(
            intent_text="test",
            environment="control_room",
            mood="tense",
            key_concept="motivated_light",
        )
        plan = builder.build_from_strategy(strategy)
        assert isinstance(plan, LightPlan)

    def test_to_from_dict(self):
        builder = get_lighting_plan_builder()
        plan = builder.build_plan(environment="industrial_hangar", mood="industrial")
        d = plan.to_dict()
        plan2 = LightPlan.from_dict(d)
        assert plan2.environment == plan.environment
        assert plan2.mood == plan.mood

    def test_never_raises_on_empty(self):
        builder = get_lighting_plan_builder()
        plan = builder.build_plan()
        assert isinstance(plan, LightPlan)

    def test_singleton(self):
        assert get_lighting_plan_builder() is get_lighting_plan_builder()
