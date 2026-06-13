"""Tests for intent_parser.py (Tier 12.8)."""
from __future__ import annotations
import pytest
from src.runtime.assets.vector_search import (
    ParsedIntent, IntentParser, get_intent_parser, reset_intent_parser_for_tests,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_intent_parser_for_tests()
    yield
    reset_intent_parser_for_tests()


class TestIntentParser:
    def test_parse_environment_industrial_hangar(self):
        parsed = get_intent_parser().parse("Industrial Hangar Hero Machinery")
        assert parsed.environment == "industrial_hangar"

    def test_parse_environment_robotics_lab(self):
        parsed = get_intent_parser().parse("Robotics Lab Support Sensor")
        assert parsed.environment == "robotics_lab"

    def test_parse_environment_control_room(self):
        parsed = get_intent_parser().parse("control room console terminal")
        assert parsed.environment == "control_room"

    def test_parse_environment_sci_fi_corridor(self):
        parsed = get_intent_parser().parse("sci-fi corridor hatch bulkhead")
        assert parsed.environment == "sci_fi_corridor"

    def test_parse_environment_abandoned_factory(self):
        parsed = get_intent_parser().parse("abandoned factory rust decay")
        assert parsed.environment == "abandoned_factory"

    def test_parse_role_hero(self):
        parsed = get_intent_parser().parse("hero machinery primary")
        assert parsed.role == "hero"

    def test_parse_role_set_dressing(self):
        parsed = get_intent_parser().parse("set dressing ambient prop")
        assert parsed.role == "set_dressing"

    def test_parse_role_background(self):
        parsed = get_intent_parser().parse("background architecture distant")
        assert parsed.role == "background"

    def test_parse_storytelling_hero_object(self):
        parsed = get_intent_parser().parse("hero object focal landmark")
        assert parsed.storytelling == "hero_object"

    def test_parse_storytelling_context_builder(self):
        parsed = get_intent_parser().parse("context builder environment setting")
        assert parsed.storytelling == "context_builder"

    def test_parse_lookdev_weathered(self):
        parsed = get_intent_parser().parse("weathered pipe metal structure")
        assert parsed.lookdev == "weathered"

    def test_parse_lookdev_rusted(self):
        parsed = get_intent_parser().parse("rusted corroded metal pipe")
        assert parsed.lookdev == "rusted"

    def test_parse_cinematic_hero_focus(self):
        parsed = get_intent_parser().parse("hero focus primary focal")
        assert parsed.cinematic == "hero_focus"

    def test_parse_cinematic_depth_layer(self):
        parsed = get_intent_parser().parse("depth layer background atmospheric")
        assert parsed.cinematic == "depth_layer"

    def test_parse_category_machinery(self):
        parsed = get_intent_parser().parse("industrial machinery gear turbine")
        assert parsed.category == "machinery"

    def test_parse_category_vehicle(self):
        parsed = get_intent_parser().parse("combat vehicle hero")
        assert parsed.category == "vehicle"

    def test_empty_text_no_exception(self):
        parsed = get_intent_parser().parse("")
        assert isinstance(parsed, ParsedIntent)
        assert parsed.confidence == 0.0

    def test_none_input_no_exception(self):
        parsed = get_intent_parser().parse(None)
        assert isinstance(parsed, ParsedIntent)

    def test_confidence_nonzero_when_fields_found(self):
        parsed = get_intent_parser().parse("Industrial Hangar Hero Machinery")
        assert parsed.confidence > 0.0

    def test_deterministic(self):
        text = "Industrial Hangar Hero Set Dressing Weathered"
        p1 = get_intent_parser().parse(text)
        p2 = get_intent_parser().parse(text)
        assert p1.to_dict() == p2.to_dict()

    def test_to_dict_from_dict(self):
        parsed = get_intent_parser().parse("robotics lab support sensor")
        d = parsed.to_dict()
        r = ParsedIntent.from_dict(d)
        assert r.environment == parsed.environment
        assert r.role == parsed.role

    def test_as_query_text(self):
        parsed = get_intent_parser().parse("industrial hangar hero machinery")
        text = parsed.as_query_text()
        assert isinstance(text, str)
        assert len(text) > 0

    def test_to_filter_dict_excludes_empty(self):
        parsed = get_intent_parser().parse("hero")
        filters = parsed.to_filter_dict()
        assert all(v for v in filters.values())

    def test_extract_environment(self):
        parser = get_intent_parser()
        assert parser.extract_environment("robotics lab") == "robotics_lab"
        assert parser.extract_environment("nothing here") == ""

    def test_extract_role(self):
        assert get_intent_parser().extract_role("hero asset") == "hero"

    def test_extract_category(self):
        assert get_intent_parser().extract_category("vehicle combat") == "vehicle"

    def test_statistics_increments(self):
        parser = get_intent_parser()
        before = parser.get_statistics()["parse_count"]
        parser.parse("pipe")
        assert parser.get_statistics()["parse_count"] == before + 1
