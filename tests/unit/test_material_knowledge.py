import pytest
from src.runtime.lookdev import (
    MaterialInference,
    get_material_knowledge,
    reset_material_knowledge_for_tests,
)


@pytest.fixture(autouse=True)
def reset_singleton():
    reset_material_knowledge_for_tests()
    yield
    reset_material_knowledge_for_tests()


def test_singleton_identity():
    assert get_material_knowledge() is get_material_knowledge()


def test_infer_pipe_gives_oxidized_pipe():
    mk = get_material_knowledge()
    result = mk.infer_material_type({"name": "industrial_pipe", "tags": ["pipe"]})
    assert result == "oxidized_pipe"


def test_infer_rust_gives_rusty_metal():
    mk = get_material_knowledge()
    result = mk.infer_material_type({"name": "rusty_beam", "description": "heavily rusted"})
    assert result == "rusty_metal"


def test_infer_concrete_gives_concrete():
    mk = get_material_knowledge()
    result = mk.infer_material_type({"name": "concrete_pillar", "tags": ["concrete"]})
    assert result == "concrete"


def test_infer_glass_gives_glass():
    mk = get_material_knowledge()
    result = mk.infer_material_type({"name": "glass_panel", "tags": ["glass", "transparent"]})
    assert result == "glass"


def test_infer_age_aged():
    mk = get_material_knowledge()
    result = mk.infer_surface_age({"name": "old_machine", "description": "aged and worn"})
    assert result == "aged"


def test_infer_age_new():
    mk = get_material_knowledge()
    result = mk.infer_surface_age({"name": "new_panel", "description": "pristine clean surface"})
    assert result == "new"


def test_infer_condition_corroded():
    mk = get_material_knowledge()
    result = mk.infer_surface_condition({"description": "heavily corroded surface with rust"})
    assert result == "corroded"


def test_infer_condition_pristine():
    mk = get_material_knowledge()
    result = mk.infer_surface_condition({"name": "polished_surface", "tags": ["pristine", "clean"]})
    assert result == "pristine"


def test_infer_material_context_returns_dict():
    mk = get_material_knowledge()
    ctx = mk.infer_material_context({"name": "factory_tank"})
    assert isinstance(ctx, dict)
    assert "environment" in ctx
    assert "usage" in ctx
    assert "style" in ctx


def test_build_material_profile_returns_inference():
    mk = get_material_knowledge()
    asset = {"asset_id": "a1", "name": "rusty_pipe", "tags": ["pipe", "rust"]}
    result = mk.build_material_profile(asset)
    assert isinstance(result, MaterialInference)
    assert result.asset_id == "a1"
    assert result.material_type in ("oxidized_pipe", "rusty_metal")
    assert 0.0 <= result.confidence <= 1.0


def test_inference_to_dict_keys():
    inf = MaterialInference(asset_id="x", material_type="concrete")
    d = inf.to_dict()
    for key in ("inference_id", "asset_id", "material_type", "surface_age",
                "surface_condition", "material_context", "confidence", "inferred_at"):
        assert key in d


def test_inference_from_dict_round_trip():
    inf = MaterialInference(asset_id="y", material_type="glass", surface_age="new")
    restored = MaterialInference.from_dict(inf.to_dict())
    assert restored.asset_id == "y"
    assert restored.material_type == "glass"
    assert restored.surface_age == "new"


def test_never_raises_none():
    mk = get_material_knowledge()
    result = mk.build_material_profile(None)  # type: ignore
    assert isinstance(result, MaterialInference)


def test_never_raises_empty():
    mk = get_material_knowledge()
    result = mk.build_material_profile({})
    assert isinstance(result, MaterialInference)
