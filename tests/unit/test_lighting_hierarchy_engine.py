"""Tests for LightingHierarchyEngine (Tier 15)."""
import pytest
from src.runtime.lighting import (
    get_lighting_hierarchy_engine,
    reset_lighting_hierarchy_engine_for_tests,
    FocusHierarchy,
    HierarchyEntry,
    HIERARCHY_ROLES,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_lighting_hierarchy_engine_for_tests()
    yield
    reset_lighting_hierarchy_engine_for_tests()


class TestLightingHierarchyEngine:
    def test_hero_identified(self):
        engine = get_lighting_hierarchy_engine()
        hero = engine.identify_hero_subject(["hero_robot", "support_crate", "background_wall"])
        assert hero == "hero_robot"

    def test_hero_fallback_to_first(self):
        engine = get_lighting_hierarchy_engine()
        hero = engine.identify_hero_subject(["crate", "barrel"])
        assert hero == "crate"

    def test_rank_importance_order(self):
        engine = get_lighting_hierarchy_engine()
        ranked = engine.rank_importance(["hero_subject", "background_wall", "support_prop"])
        assert ranked[0]["subject"] == "hero_subject"
        assert ranked[0]["importance"] == 1.0

    def test_build_hierarchy_classifies(self):
        engine = get_lighting_hierarchy_engine()
        subjects = ["hero_robot", "support_panel", "background_floor", "atmosphere_fog"]
        h = engine.build_focus_hierarchy(subjects)
        assert isinstance(h, FocusHierarchy)
        assert len(h.hero) >= 1
        assert h.hero[0].subject == "hero_robot"

    def test_no_explicit_hero_promotes_first(self):
        engine = get_lighting_hierarchy_engine()
        h = engine.build_focus_hierarchy(["crate", "barrel"])
        assert len(h.hero) == 1
        assert h.hero[0].role == "hero"

    def test_empty_subjects(self):
        engine = get_lighting_hierarchy_engine()
        h = engine.build_focus_hierarchy([])
        assert isinstance(h, FocusHierarchy)
        assert h.hero == []

    def test_hierarchy_entry_has_priority(self):
        engine = get_lighting_hierarchy_engine()
        h = engine.build_focus_hierarchy(["hero_subject"])
        assert h.hero[0].lighting_priority.get("key_target") is True

    def test_hierarchy_roles_constant(self):
        assert "hero" in HIERARCHY_ROLES
        assert "background" in HIERARCHY_ROLES

    def test_to_from_dict(self):
        engine = get_lighting_hierarchy_engine()
        h = engine.build_focus_hierarchy(["hero_subject", "support_crate"])
        d = h.to_dict()
        h2 = FocusHierarchy.from_dict(d)
        assert len(h2.hero) == len(h.hero)

    def test_singleton(self):
        assert get_lighting_hierarchy_engine() is get_lighting_hierarchy_engine()
