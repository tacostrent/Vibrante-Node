"""Tests for LightingStrategyEngine (Tier 15)."""
import pytest
from src.runtime.lighting import (
    get_lighting_strategy_engine,
    reset_lighting_strategy_engine_for_tests,
    reset_lighting_mood_engine_for_tests,
    reset_lighting_environment_mapper_for_tests,
    reset_lighting_patterns_for_tests,
    reset_lighting_color_engine_for_tests,
    reset_lighting_exposure_engine_for_tests,
    LightingStrategy,
)


@pytest.fixture(autouse=True)
def _reset():
    for fn in [
        reset_lighting_strategy_engine_for_tests,
        reset_lighting_mood_engine_for_tests,
        reset_lighting_environment_mapper_for_tests,
        reset_lighting_patterns_for_tests,
        reset_lighting_color_engine_for_tests,
        reset_lighting_exposure_engine_for_tests,
    ]:
        fn()
    yield
    for fn in [
        reset_lighting_strategy_engine_for_tests,
        reset_lighting_mood_engine_for_tests,
        reset_lighting_environment_mapper_for_tests,
        reset_lighting_patterns_for_tests,
        reset_lighting_color_engine_for_tests,
        reset_lighting_exposure_engine_for_tests,
    ]:
        fn()


class TestLightingStrategyEngine:
    def test_generate_industrial(self):
        engine = get_lighting_strategy_engine()
        s = engine.generate_strategy(environment="industrial_hangar", mood="industrial")
        assert isinstance(s, LightingStrategy)
        assert s.environment == "industrial_hangar"
        assert s.mood == "industrial"

    def test_generate_infers_mood_from_intent(self):
        engine = get_lighting_strategy_engine()
        s = engine.generate_strategy(intent_text="dramatic intense cinematic scene", environment="dramatic_interior")
        assert s.mood in ("dramatic", "cinematic")

    def test_generate_populates_key_concept(self):
        engine = get_lighting_strategy_engine()
        s = engine.generate_strategy(environment="sci_fi_corridor", mood="dramatic")
        assert s.key_concept != ""

    def test_generate_volumetrics_flag(self):
        engine = get_lighting_strategy_engine()
        s = engine.generate_strategy(environment="sci_fi_corridor")
        assert s.volumetrics is True

    def test_generate_no_volumetrics(self):
        engine = get_lighting_strategy_engine()
        s = engine.generate_strategy(environment="robotics_lab")
        assert s.volumetrics is False

    def test_evaluate_complete_strategy(self):
        engine = get_lighting_strategy_engine()
        s = engine.generate_strategy(environment="industrial_hangar", mood="industrial")
        eval_result = engine.evaluate_strategy(s)
        assert eval_result["complete"] is True
        assert eval_result["score"] > 0.0

    def test_evaluate_empty_strategy(self):
        engine = get_lighting_strategy_engine()
        s = LightingStrategy()
        eval_result = engine.evaluate_strategy(s)
        assert eval_result["complete"] is False

    def test_to_from_dict(self):
        engine = get_lighting_strategy_engine()
        s = engine.generate_strategy(environment="control_room", mood="tense")
        d = s.to_dict()
        s2 = LightingStrategy.from_dict(d)
        assert s2.environment == s.environment
        assert s2.mood == s.mood

    def test_singleton(self):
        assert get_lighting_strategy_engine() is get_lighting_strategy_engine()

    def test_never_raises_on_empty(self):
        engine = get_lighting_strategy_engine()
        s = engine.generate_strategy()
        assert isinstance(s, LightingStrategy)
