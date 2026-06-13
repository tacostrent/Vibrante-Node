"""Tests for src/runtime/assets/acquisition_online/acquisition_pipeline.py"""
import pytest
from src.runtime.assets.acquisition_online import (
    get_acquisition_pipeline,
    get_asset_cache_manager,
    get_megascans_auth,
    get_megascans_downloader,
    reset_acquisition_pipeline_for_tests,
    reset_asset_cache_manager_for_tests,
    reset_asset_fetcher_for_tests,
    reset_megascans_auth_for_tests,
    reset_megascans_downloader_for_tests,
    reset_asset_provenance_tracker_for_tests,
    reset_project_asset_staging_for_tests,
    reset_download_statistics_for_tests,
    reset_download_serializer_for_tests,
    AcquisitionPipelineResult,
)


class _MockAuthTransport:
    def get_user_info(self, token):
        return {"user_id": "u1", "username": "t"}


class _MockDownloadTransport:
    def __init__(self, ok=True):
        self.ok = ok

    def resolve_url(self, asset_id, token, quality):
        return f"https://mock/{asset_id}.zip"

    def download(self, url, token, dest_path):
        if self.ok:
            with open(dest_path, "wb") as f:
                f.write(b"data")
            return {"ok": True, "bytes": 4, "error": ""}
        return {"ok": False, "bytes": 0, "error": "fail"}


@pytest.fixture(autouse=True)
def reset_all(tmp_path, monkeypatch):
    monkeypatch.setenv("VIBRANTE_ASSET_CACHE", str(tmp_path))
    monkeypatch.setenv("VIBRANTE_PROJECT_STAGING", str(tmp_path / "staging"))
    monkeypatch.setenv("VIBRANTE_MEGASCANS_TOKEN", "tok")
    reset_download_serializer_for_tests()
    reset_download_statistics_for_tests()
    reset_asset_provenance_tracker_for_tests()
    reset_asset_cache_manager_for_tests()
    reset_project_asset_staging_for_tests()
    reset_megascans_auth_for_tests()
    reset_megascans_downloader_for_tests()
    reset_asset_fetcher_for_tests()
    reset_acquisition_pipeline_for_tests()
    auth = get_megascans_auth()
    auth._transport = _MockAuthTransport()
    yield
    reset_acquisition_pipeline_for_tests()
    reset_asset_fetcher_for_tests()
    reset_megascans_downloader_for_tests()
    reset_megascans_auth_for_tests()
    reset_project_asset_staging_for_tests()
    reset_asset_cache_manager_for_tests()
    reset_asset_provenance_tracker_for_tests()
    reset_download_statistics_for_tests()
    reset_download_serializer_for_tests()
    monkeypatch.delenv("VIBRANTE_ASSET_CACHE", raising=False)
    monkeypatch.delenv("VIBRANTE_PROJECT_STAGING", raising=False)
    monkeypatch.delenv("VIBRANTE_MEGASCANS_TOKEN", raising=False)


def test_singleton():
    a = get_acquisition_pipeline()
    b = get_acquisition_pipeline()
    assert a is b


def test_acquire_for_intent_no_intent():
    pipeline = get_acquisition_pipeline()
    result = pipeline.acquire_for_intent("")
    assert result.ok is False
    assert "required" in result.error.lower()


def test_acquire_for_intent_no_semantic_pipeline():
    # Without vector search loaded, retrieval returns empty → pipeline returns OK with 0 assets
    pipeline = get_acquisition_pipeline()
    result = pipeline.acquire_for_intent("industrial hangar machinery")
    assert isinstance(result, AcquisitionPipelineResult)
    assert result.total == 0


def test_acquire_environment_no_env():
    pipeline = get_acquisition_pipeline()
    result = pipeline.acquire_environment("")
    assert result.ok is False


def test_acquire_environment_empty_returns_ok():
    pipeline = get_acquisition_pipeline()
    result = pipeline.acquire_environment("industrial_hangar")
    assert isinstance(result, AcquisitionPipelineResult)


def test_acquire_asset_set_cached(tmp_path):
    f = tmp_path / "asset_a.zip"
    f.write_bytes(b"data")
    get_asset_cache_manager().cache_asset("asset_a", "megascans", str(f))

    pipeline = get_acquisition_pipeline()
    result = pipeline.acquire_asset_set([{"asset_id": "asset_a", "provider": "megascans"}],
                                        stage_assets=False)
    assert result.ok is True
    assert result.cached == 1
    assert result.downloaded == 0


def test_acquire_asset_set_downloads(tmp_path):
    dl = get_megascans_downloader()
    dl._transport = _MockDownloadTransport(ok=True)

    pipeline = get_acquisition_pipeline()
    result = pipeline.acquire_asset_set(
        [{"asset_id": "dl_asset", "provider": "megascans"}],
        dest_dir=str(tmp_path),
        stage_assets=False,
    )
    assert result.ok is True
    assert result.downloaded == 1


def test_acquire_asset_set_failure(tmp_path):
    dl = get_megascans_downloader()
    dl._transport = _MockDownloadTransport(ok=False)

    pipeline = get_acquisition_pipeline()
    result = pipeline.acquire_asset_set(
        [{"asset_id": "fail_asset", "provider": "megascans"}],
        dest_dir=str(tmp_path),
        stage_assets=False,
    )
    assert result.ok is False
    assert result.failed == 1


def test_pipeline_result_to_dict():
    r = AcquisitionPipelineResult(ok=True, intent="test", total=2, cached=1, downloaded=1)
    d = r.to_dict()
    assert d["ok"] is True
    assert d["total"] == 2
    assert d["intent"] == "test"


def test_pipeline_result_from_dict():
    d = {"ok": False, "intent": "x", "total": 0, "errors": ["err1"]}
    r = AcquisitionPipelineResult.from_dict(d)
    assert r.ok is False
    assert r.errors == ["err1"]


def test_stage_assets_called(tmp_path):
    f = tmp_path / "stage_asset.zip"
    f.write_bytes(b"x")
    get_asset_cache_manager().cache_asset("stage_asset", "megascans", str(f))

    pipeline = get_acquisition_pipeline()
    result = pipeline.acquire_asset_set(
        [{"asset_id": "stage_asset", "provider": "megascans"}],
        project_id="test_project",
        stage_assets=True,
    )
    assert result.ok is True
