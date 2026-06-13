"""Tests for LightingKnowledge (Tier 15)."""
import pytest
from src.runtime.lighting import (
    get_lighting_knowledge,
    reset_lighting_knowledge_for_tests,
    BUILTIN_LIGHTING_ROLES,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_lighting_knowledge_for_tests()
    yield
    reset_lighting_knowledge_for_tests()


class TestLightingKnowledge:
    def test_builtins_loaded(self):
        lib = get_lighting_knowledge()
        stats = lib.get_statistics()
        assert stats["total_concepts"] >= 14

    def test_builtin_roles_coverage(self):
        lib = get_lighting_knowledge()
        stats = lib.get_statistics()
        present_roles = set(stats["by_role"].keys())
        assert "key" in present_roles
        assert "fill" in present_roles
        assert "rim" in present_roles

    def test_lookup_by_name(self):
        lib = get_lighting_knowledge()
        c = lib.lookup_concept("key_light")
        assert c is not None
        assert c.name == "key_light"
        assert c.role == "key"

    def test_lookup_by_builtin_id(self):
        lib = get_lighting_knowledge()
        c = lib.lookup_concept("builtin_fill_light")
        assert c is not None
        assert c.name == "fill_light"

    def test_lookup_missing(self):
        lib = get_lighting_knowledge()
        assert lib.lookup_concept("nonexistent_xyz") is None

    def test_register_concept(self):
        lib = get_lighting_knowledge()
        before = lib.get_statistics()["total_concepts"]
        c = lib.register_concept("test_light", "key", description="test", tags=["t"])
        assert c.name == "test_light"
        assert lib.get_statistics()["total_concepts"] == before + 1

    def test_recommend_by_role(self):
        lib = get_lighting_knowledge()
        results = lib.recommend_concept(role="rim")
        assert all(c.role == "rim" for c in results)
        assert len(results) >= 1

    def test_recommend_by_tag(self):
        lib = get_lighting_knowledge()
        results = lib.recommend_concept(tags=["danger"])
        assert any("danger" in c.tags or "emergency" in c.name for c in results)

    def test_search_by_query(self):
        lib = get_lighting_knowledge()
        results = lib.search_concepts(query="volumetric")
        assert any("volumetric" in c.name or "volumetric" in c.description.lower() for c in results)

    def test_search_by_role_filter(self):
        lib = get_lighting_knowledge()
        results = lib.search_concepts(role="atmospheric")
        assert all(c.role == "atmospheric" for c in results)

    def test_singleton(self):
        assert get_lighting_knowledge() is get_lighting_knowledge()

    def test_to_from_dict(self):
        lib = get_lighting_knowledge()
        c = lib.lookup_concept("rim_light")
        d = c.to_dict()
        c2 = c.from_dict(d)
        assert c2.name == c.name
        assert c2.role == c.role
