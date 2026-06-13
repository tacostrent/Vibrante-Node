"""Tests for WorkflowBlueprint (Tier 10 — §30)."""
import pytest
from src.runtime.workflows.workflow_blueprint import (
    WorkflowBlueprint,
    BlueprintPhase,
    PHASE_ORDER,
    get_workflow_blueprint,
    reset_workflow_blueprint_for_tests,
)
from src.runtime.workflows.workflow_pack import (
    get_builtin_packs,
    reset_workflow_pack_for_tests,
)


@pytest.fixture(autouse=True)
def reset():
    reset_workflow_blueprint_for_tests()
    reset_workflow_pack_for_tests()
    yield
    reset_workflow_blueprint_for_tests()
    reset_workflow_pack_for_tests()


def _hangar_pack():
    packs = get_builtin_packs()
    return next(p for p in packs if p.name == "industrial_hangar_pack")


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton():
    assert get_workflow_blueprint() is get_workflow_blueprint()


# ---------------------------------------------------------------------------
# build_blueprint
# ---------------------------------------------------------------------------

def test_build_blueprint_ok():
    pack      = _hangar_pack()
    blueprint = get_workflow_blueprint().build_blueprint(pack)
    assert blueprint["ok"] is True


def test_build_blueprint_has_all_phases():
    blueprint = get_workflow_blueprint().build_blueprint(_hangar_pack())
    for phase in PHASE_ORDER:
        assert phase in blueprint["phases"]


def test_build_blueprint_has_dependencies():
    blueprint = get_workflow_blueprint().build_blueprint(_hangar_pack())
    deps = blueprint["dependencies"]
    assert "environment" in deps
    assert "population"  in deps
    assert isinstance(deps["population"], list)
    assert "environment" in deps["population"]


def test_build_blueprint_has_complexity():
    blueprint = get_workflow_blueprint().build_blueprint(_hangar_pack())
    assert blueprint["estimated_complexity"] in ("simple", "moderate", "complex", "epic")


def test_build_blueprint_has_total_ops():
    blueprint = get_workflow_blueprint().build_blueprint(_hangar_pack())
    assert blueprint["total_ops"] >= 0


def test_build_blueprint_invalid_pack_returns_errors():
    from src.runtime.workflows.workflow_pack import WorkflowPack
    bad = WorkflowPack(
        name="", version="1.0.0", environment_type="",
        asset_strategy={}, population_strategy={},
        placement_strategy={}, lighting_strategy={},
        camera_strategy={}, atmosphere_strategy={},
        review_strategy={},
    )
    result = get_workflow_blueprint().build_blueprint(bad)
    assert result["ok"] is False
    assert result["errors"]


# ---------------------------------------------------------------------------
# resolve_dependencies
# ---------------------------------------------------------------------------

def test_resolve_dependencies_ordering():
    blueprint = get_workflow_blueprint().build_blueprint(_hangar_pack())
    order     = get_workflow_blueprint().resolve_dependencies(blueprint)
    # environment must come before population and placement
    assert order.index("environment") < order.index("population")
    assert order.index("population")  < order.index("placement")


# ---------------------------------------------------------------------------
# generate_execution_plan
# ---------------------------------------------------------------------------

def test_generate_execution_plan_ok():
    builder   = get_workflow_blueprint()
    blueprint = builder.build_blueprint(_hangar_pack())
    plan      = builder.generate_execution_plan(blueprint)
    assert plan["ok"] is True
    assert isinstance(plan["operations"], list)
    assert "phase_order" in plan


def test_execution_plan_ops_have_op_key():
    builder   = get_workflow_blueprint()
    blueprint = builder.build_blueprint(_hangar_pack())
    plan      = builder.generate_execution_plan(blueprint)
    for op in plan["operations"]:
        assert "op" in op


def test_execution_plan_failed_blueprint():
    from src.runtime.workflows.workflow_pack import WorkflowPack
    bad  = WorkflowPack(
        name="", version="", environment_type="",
        asset_strategy={}, population_strategy={}, placement_strategy={},
        lighting_strategy={}, camera_strategy={}, atmosphere_strategy={},
        review_strategy={},
    )
    builder   = get_workflow_blueprint()
    blueprint = builder.build_blueprint(bad)
    plan      = builder.generate_execution_plan(blueprint)
    assert plan["ok"] is False


# ---------------------------------------------------------------------------
# validate_blueprint
# ---------------------------------------------------------------------------

def test_validate_blueprint_valid():
    builder   = get_workflow_blueprint()
    blueprint = builder.build_blueprint(_hangar_pack())
    result    = builder.validate_blueprint(blueprint)
    assert result["valid"] is True


def test_validate_blueprint_empty_phases():
    result = get_workflow_blueprint().validate_blueprint(
        {"ok": True, "workflow": "x", "phases": []}
    )
    assert result["valid"] is False


# ---------------------------------------------------------------------------
# estimate_complexity
# ---------------------------------------------------------------------------

def test_estimate_complexity_returns_level():
    builder   = get_workflow_blueprint()
    blueprint = builder.build_blueprint(_hangar_pack())
    level     = builder.estimate_complexity(blueprint)
    assert level in ("simple", "moderate", "complex", "epic")


# ---------------------------------------------------------------------------
# BlueprintPhase
# ---------------------------------------------------------------------------

def test_blueprint_phase_to_dict():
    p = BlueprintPhase(phase_name="environment", description="test", operations=[])
    d = p.to_dict()
    assert d["phase_name"]  == "environment"
    assert d["dependencies"] == []
    assert d["optional"] is False


def test_blueprint_phase_round_trip():
    p1 = BlueprintPhase(
        phase_name="lighting", description="x",
        operations=[{"op": "create_node"}],
        dependencies=["environment"],
    )
    p2 = BlueprintPhase.from_dict(p1.to_dict())
    assert p2.phase_name   == p1.phase_name
    assert p2.dependencies == p1.dependencies


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

def test_stats_increments():
    b = get_workflow_blueprint()
    b.build_blueprint(_hangar_pack())
    assert b.stats()["build_count"] >= 1
