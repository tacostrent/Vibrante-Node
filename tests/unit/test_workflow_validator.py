"""Tests for WorkflowValidator (Tier 10 — §30)."""
import pytest
from src.runtime.workflows.workflow_validator import (
    ValidationReport,
    WorkflowValidator,
    get_workflow_validator,
    reset_workflow_validator_for_tests,
)
from src.runtime.workflows.workflow_pack import (
    WorkflowPack,
    get_builtin_packs,
    reset_workflow_pack_for_tests,
)
from src.runtime.workflows.workflow_blueprint import (
    PHASE_ORDER,
    get_workflow_blueprint,
    reset_workflow_blueprint_for_tests,
)


@pytest.fixture(autouse=True)
def reset():
    reset_workflow_validator_for_tests()
    reset_workflow_pack_for_tests()
    reset_workflow_blueprint_for_tests()
    yield
    reset_workflow_validator_for_tests()
    reset_workflow_pack_for_tests()
    reset_workflow_blueprint_for_tests()


def _hangar_pack():
    return next(p for p in get_builtin_packs() if p.name == "industrial_hangar_pack")


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton():
    assert get_workflow_validator() is get_workflow_validator()


# ---------------------------------------------------------------------------
# ValidationReport
# ---------------------------------------------------------------------------

def test_validation_report_to_dict():
    r = ValidationReport(valid=True, warnings=["w"], errors=[])
    d = r.to_dict()
    assert d["valid"]    is True
    assert d["warnings"] == ["w"]
    assert d["errors"]   == []


# ---------------------------------------------------------------------------
# validate_pack
# ---------------------------------------------------------------------------

def test_validate_pack_builtin_passes():
    v      = get_workflow_validator()
    report = v.validate_pack(_hangar_pack())
    assert report.valid is True
    assert report.errors == []


def test_validate_pack_empty_name_fails():
    pack = _hangar_pack().clone(name="")
    report = get_workflow_validator().validate_pack(pack)
    assert report.valid is False


def test_validate_pack_unknown_environment_fails():
    pack = _hangar_pack().clone(environment_type="mars_crater")
    report = get_workflow_validator().validate_pack(pack)
    assert report.valid is False
    assert any("mars_crater" in e for e in report.errors)


def test_validate_pack_unknown_lighting_warns():
    pack = _hangar_pack()
    pack.lighting_strategy["style"] = "magic_style"
    report = get_workflow_validator().validate_pack(pack)
    assert any("magic_style" in w for w in report.warnings)


def test_validate_pack_unknown_camera_warns():
    pack = _hangar_pack()
    pack.camera_strategy["mode"] = "teleportation_cam"
    report = get_workflow_validator().validate_pack(pack)
    assert any("teleportation_cam" in w for w in report.warnings)


def test_validate_pack_bad_fog_warns():
    pack = _hangar_pack()
    pack.atmosphere_strategy["fog_density"] = "extreme_fog"
    report = get_workflow_validator().validate_pack(pack)
    assert any("extreme_fog" in w for w in report.warnings)


def test_validate_pack_low_threshold_warns():
    pack = _hangar_pack()
    pack.review_strategy["production_threshold"] = 0.30
    report = get_workflow_validator().validate_pack(pack)
    assert any("low" in w for w in report.warnings)


# ---------------------------------------------------------------------------
# validate_dependencies
# ---------------------------------------------------------------------------

def test_validate_dependencies_valid():
    deps   = {"a": [], "b": ["a"], "c": ["b"]}
    report = get_workflow_validator().validate_dependencies(deps)
    assert report.valid is True


def test_validate_dependencies_unknown_dep_fails():
    deps   = {"a": ["z"]}
    report = get_workflow_validator().validate_dependencies(deps)
    assert report.valid is False
    assert any("unknown" in e for e in report.errors)


def test_validate_dependencies_self_cycle_fails():
    deps   = {"a": ["a"]}
    report = get_workflow_validator().validate_dependencies(deps)
    assert report.valid is False


def test_validate_dependencies_cycle_fails():
    deps   = {"a": ["b"], "b": ["c"], "c": ["a"]}
    report = get_workflow_validator().validate_dependencies(deps)
    assert report.valid is False


# ---------------------------------------------------------------------------
# validate_execution_plan
# ---------------------------------------------------------------------------

def test_validate_execution_plan_from_blueprint():
    pack      = _hangar_pack()
    builder   = get_workflow_blueprint()
    blueprint = builder.build_blueprint(pack)
    plan      = builder.generate_execution_plan(blueprint)
    report    = get_workflow_validator().validate_execution_plan(plan)
    assert report.valid is True


def test_validate_execution_plan_not_ok_fails():
    report = get_workflow_validator().validate_execution_plan(
        {"ok": False, "errors": ["bad"]}
    )
    assert report.valid is False


def test_validate_execution_plan_missing_op_key_fails():
    plan = {
        "ok": True, "operations": [{}],
        "phase_order": PHASE_ORDER,
    }
    report = get_workflow_validator().validate_execution_plan(plan)
    assert report.valid is False


# ---------------------------------------------------------------------------
# validate_environment
# ---------------------------------------------------------------------------

def test_validate_environment_known():
    report = get_workflow_validator().validate_environment("robotics_lab")
    assert report.valid is True


def test_validate_environment_unknown():
    report = get_workflow_validator().validate_environment("moon_base")
    assert report.valid is False


def test_validate_environment_empty():
    report = get_workflow_validator().validate_environment("")
    assert report.valid is False


# ---------------------------------------------------------------------------
# validate_review_thresholds
# ---------------------------------------------------------------------------

def test_validate_threshold_valid():
    report = get_workflow_validator().validate_review_thresholds(
        {"production_threshold": 0.70}
    )
    assert report.valid is True


def test_validate_threshold_out_of_range():
    report = get_workflow_validator().validate_review_thresholds(
        {"production_threshold": 1.5}
    )
    assert report.valid is False


def test_validate_threshold_non_numeric():
    report = get_workflow_validator().validate_review_thresholds(
        {"production_threshold": "high"}
    )
    assert report.valid is False


def test_validate_min_readability_out_of_range():
    report = get_workflow_validator().validate_review_thresholds(
        {"production_threshold": 0.70, "min_readability": -0.5}
    )
    assert report.valid is False


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

def test_stats_increments():
    v = get_workflow_validator()
    v.validate_pack(_hangar_pack())
    assert v.stats()["validation_count"] >= 1
