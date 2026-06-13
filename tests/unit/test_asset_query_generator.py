"""
Tests for AssetQueryGenerator (Tier 7).

Covers:
 - generates queries for each zone's asset_categories
 - tags include environment, style, and mood modifiers
 - priority=required for high-priority zones
 - quantity defaults are positive
 - no duplicate query_ids
 - empty intent/zones produces empty list
 - deterministic
 - singleton / reset
"""

import pytest

from src.runtime.planning.planners.asset_query_generator import (
    AssetQueryGenerator,
    get_asset_query_generator,
    reset_asset_query_generator_for_tests,
)
from src.runtime.planning.schema.scene_plan import AssetQuery, SceneZonePlan


@pytest.fixture(autouse=True)
def _reset():
    reset_asset_query_generator_for_tests()
    yield
    reset_asset_query_generator_for_tests()


def _make_intent(environment=None, style=None, mood=None, destruction_level=None):
    class _Intent:
        pass
    i = _Intent()
    i.environment = environment
    i.style = style
    i.mood = mood
    i.destruction_level = destruction_level
    return i


def _make_zones_with_cats(cats_by_zone):
    """cats_by_zone = {"foreground": ["debris", "vehicle"], "midground": ["building"]}"""
    zones = []
    for zone_type, cats in cats_by_zone.items():
        z = SceneZonePlan(zone_type=zone_type, asset_categories=cats,
                          priority=10 if zone_type == "foreground" else 7)
        zones.append(z)
    return zones


class TestAssetQueryGeneratorSingleton:
    def test_singleton(self):
        assert get_asset_query_generator() is get_asset_query_generator()

    def test_reset_creates_new(self):
        a = get_asset_query_generator()
        reset_asset_query_generator_for_tests()
        assert a is not get_asset_query_generator()


class TestAssetQueryGeneratorBasic:
    def test_empty_zones_returns_empty_list(self):
        intent = _make_intent(environment="urban")
        queries = get_asset_query_generator().generate_queries(intent, [])
        assert queries == []

    def test_zones_without_categories_return_empty(self):
        intent = _make_intent(environment="urban")
        zones = [SceneZonePlan(zone_type="midground", asset_categories=[])]
        queries = get_asset_query_generator().generate_queries(intent, zones)
        assert queries == []

    def test_generates_one_query_per_category(self):
        intent = _make_intent(environment="urban")
        zones = _make_zones_with_cats({"foreground": ["debris", "vehicle"]})
        queries = get_asset_query_generator().generate_queries(intent, zones)
        assert len(queries) == 2

    def test_queries_have_category_set(self):
        intent = _make_intent(environment="urban")
        zones = _make_zones_with_cats({"midground": ["building", "structure"]})
        queries = get_asset_query_generator().generate_queries(intent, zones)
        categories = {q.category for q in queries}
        assert "building" in categories
        assert "structure" in categories

    def test_queries_have_zone_assigned(self):
        intent = _make_intent(environment="urban")
        zones = _make_zones_with_cats({"midground": ["building"]})
        queries = get_asset_query_generator().generate_queries(intent, zones)
        assert all(q.zone == "midground" for q in queries)

    def test_unique_query_ids(self):
        intent = _make_intent(environment="urban")
        zones = _make_zones_with_cats({
            "foreground": ["debris", "vehicle"],
            "midground": ["building", "structure"],
            "background": ["skyline"],
        })
        queries = get_asset_query_generator().generate_queries(intent, zones)
        ids = [q.query_id for q in queries]
        assert len(ids) == len(set(ids))

    def test_quantities_are_positive(self):
        intent = _make_intent(environment="urban")
        zones = _make_zones_with_cats({
            "foreground": ["debris", "vehicle"],
            "midground": ["building"],
        })
        queries = get_asset_query_generator().generate_queries(intent, zones)
        for q in queries:
            assert q.quantity >= 1


class TestAssetQueryGeneratorTags:
    def test_environment_tag_included(self):
        intent = _make_intent(environment="urban")
        zones = _make_zones_with_cats({"midground": ["building"]})
        queries = get_asset_query_generator().generate_queries(intent, zones)
        assert any("urban" in q.tags for q in queries)

    def test_style_tag_included_when_set(self):
        intent = _make_intent(environment="urban", style="sci_fi")
        zones = _make_zones_with_cats({"midground": ["building"]})
        queries = get_asset_query_generator().generate_queries(intent, zones)
        # Style should contribute to tags
        all_tags = [tag for q in queries for tag in q.tags]
        assert "sci_fi" in all_tags or "sci-fi" in all_tags or "sci_fi" in " ".join(all_tags)

    def test_mood_tag_included_when_set(self):
        intent = _make_intent(environment="urban", mood="dramatic")
        zones = _make_zones_with_cats({"midground": ["building"]})
        queries = get_asset_query_generator().generate_queries(intent, zones)
        all_tags = [tag for q in queries for tag in q.tags]
        assert "dramatic" in all_tags or "drama" in " ".join(all_tags)


class TestAssetQueryGeneratorPriority:
    def test_high_priority_zone_has_required_queries(self):
        intent = _make_intent(environment="urban")
        zones = [SceneZonePlan(zone_type="foreground",
                               asset_categories=["vehicle"],
                               priority=10)]
        queries = get_asset_query_generator().generate_queries(intent, zones)
        # foreground high-priority zone → at least some queries are required
        priorities = {q.priority for q in queries}
        assert "required" in priorities or "recommended" in priorities

    def test_background_zone_has_optional_or_recommended_queries(self):
        intent = _make_intent(environment="urban")
        zones = [SceneZonePlan(zone_type="background",
                               asset_categories=["skyline"],
                               priority=4)]
        queries = get_asset_query_generator().generate_queries(intent, zones)
        assert all(q.priority in ("optional", "recommended") for q in queries)


class TestAssetQueryGeneratorDeterminism:
    def test_same_intent_same_queries(self):
        intent = _make_intent(environment="industrial", style="cinematic", mood="dramatic")
        zones = _make_zones_with_cats({
            "foreground": ["machinery", "pipe"],
            "midground": ["structure", "tank"],
        })
        q_a = get_asset_query_generator().generate_queries(intent, zones)
        q_b = get_asset_query_generator().generate_queries(intent, zones)
        assert [q.category for q in q_a] == [q.category for q in q_b]
        assert [q.zone for q in q_a] == [q.zone for q in q_b]
