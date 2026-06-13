"""Tests for src/runtime/assets/acquisition_online/download_review.py"""
import pytest
from src.runtime.assets.acquisition_online import (
    get_download_review,
    get_asset_cache_manager,
    get_asset_provenance_tracker,
    reset_download_review_for_tests,
    reset_asset_cache_manager_for_tests,
    reset_asset_provenance_tracker_for_tests,
    reset_download_serializer_for_tests,
    DownloadReviewResult,
)


@pytest.fixture(autouse=True)
def reset_all(tmp_path, monkeypatch):
    monkeypatch.setenv("VIBRANTE_ASSET_CACHE", str(tmp_path))
    reset_download_serializer_for_tests()
    reset_asset_cache_manager_for_tests()
    reset_asset_provenance_tracker_for_tests()
    reset_download_review_for_tests()
    yield
    reset_download_review_for_tests()
    reset_asset_provenance_tracker_for_tests()
    reset_asset_cache_manager_for_tests()
    reset_download_serializer_for_tests()
    monkeypatch.delenv("VIBRANTE_ASSET_CACHE", raising=False)


def test_singleton():
    a = get_download_review()
    b = get_download_review()
    assert a is b


def test_review_download_file_missing():
    review = get_download_review()
    result = review.review_download("asset1", local_path="/nonexistent.zip")
    assert result.ok is True
    assert result.overall_score < 0.70
    assert result.production_ready is False
    assert any("missing" in f.lower() for f in result.findings)


def test_review_download_file_exists_with_provenance(tmp_path):
    f = tmp_path / "asset2.zip"
    f.write_bytes(b"content")
    get_asset_cache_manager().cache_asset("asset2", "megascans", str(f))
    get_asset_provenance_tracker().register("asset2", "megascans", str(f))

    review = get_download_review()
    result = review.review_download("asset2", provider="megascans", local_path=str(f))
    assert result.ok is True
    assert result.overall_score >= 0.70
    assert result.production_ready is True


def test_review_pipeline_empty():
    review = get_download_review()
    result = review.review_pipeline({})
    assert result.ok is True
    assert result.production_ready is False


def test_review_pipeline_all_success():
    get_asset_provenance_tracker().register("p1", "megascans", "/p1")
    get_asset_provenance_tracker().register("p2", "megascans", "/p2")
    review = get_download_review()
    pipeline_result = {
        "total": 2, "downloaded": 2, "cached": 0, "failed": 0,
        "assets": [
            {"asset_id": "p1", "provider": "megascans"},
            {"asset_id": "p2", "provider": "megascans"},
        ],
    }
    result = review.review_pipeline(pipeline_result)
    assert result.ok is True
    assert result.overall_score > 0.5


def test_review_pipeline_all_failed():
    review = get_download_review()
    pipeline_result = {
        "total": 3, "downloaded": 0, "cached": 0, "failed": 3, "assets": [],
    }
    result = review.review_pipeline(pipeline_result)
    assert result.ok is True
    assert result.production_ready is False
    assert any("failed" in f.lower() or "all failed" in f.lower() for f in result.findings)


def test_grade_mapping():
    review = get_download_review()
    dims_a = {"download_success": 1.0, "integrity": 1.0, "cache_efficiency": 1.0, "provenance_quality": 1.0}
    score, grade, ready = review._compute_grade(dims_a, [])
    assert grade == "A"
    assert ready is True


def test_grade_f():
    review = get_download_review()
    dims_f = {"download_success": 0.0, "integrity": 0.0, "cache_efficiency": 0.0, "provenance_quality": 0.0}
    score, grade, ready = review._compute_grade(dims_f, [])
    assert grade == "F"
    assert ready is False


def test_review_result_to_dict():
    r = DownloadReviewResult(ok=True, overall_score=0.75, grade="B", production_ready=True)
    d = r.to_dict()
    assert d["ok"] is True
    assert d["overall_score"] == 0.75
    assert d["grade"] == "B"
    assert d["production_ready"] is True


def test_review_result_from_dict():
    d = {"ok": True, "overall_score": 0.8, "grade": "A", "production_ready": True,
         "dimensions": {}, "findings": ["ok"], "advisory": "ready"}
    r = DownloadReviewResult.from_dict(d)
    assert r.grade == "A"
    assert r.production_ready is True


def test_blocking_finding_prevents_production_ready():
    review = get_download_review()
    dims = {"download_success": 0.9, "integrity": 0.9, "cache_efficiency": 0.9, "provenance_quality": 0.9}
    _, _, ready = review._compute_grade(dims, ["all failed"])
    assert ready is False


def test_advisory_for_f_grade():
    review = get_download_review()
    advisory = review._build_advisory("F", ["file missing"])
    assert "below production" in advisory.lower()
