"""Tests for src/runtime/assets/acquisition_online/project_asset_staging.py"""
import os
import pytest
from src.runtime.assets.acquisition_online import (
    get_project_asset_staging,
    get_asset_cache_manager,
    reset_project_asset_staging_for_tests,
    reset_asset_cache_manager_for_tests,
    reset_download_serializer_for_tests,
    StagingEntry,
)


@pytest.fixture(autouse=True)
def reset_all(tmp_path, monkeypatch):
    monkeypatch.setenv("VIBRANTE_ASSET_CACHE", str(tmp_path / "cache"))
    monkeypatch.setenv("VIBRANTE_PROJECT_STAGING", str(tmp_path / "staging"))
    reset_download_serializer_for_tests()
    reset_asset_cache_manager_for_tests()
    reset_project_asset_staging_for_tests()
    yield
    reset_project_asset_staging_for_tests()
    reset_asset_cache_manager_for_tests()
    reset_download_serializer_for_tests()
    monkeypatch.delenv("VIBRANTE_ASSET_CACHE", raising=False)
    monkeypatch.delenv("VIBRANTE_PROJECT_STAGING", raising=False)


def test_singleton():
    a = get_project_asset_staging()
    b = get_project_asset_staging()
    assert a is b


def test_stage_asset_no_cache():
    staging = get_project_asset_staging()
    entry = staging.stage_asset("proj1", "asset1", provider="megascans")
    assert entry.project_id == "proj1"
    assert entry.asset_id == "asset1"


def test_stage_asset_with_cached_file(tmp_path):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(exist_ok=True)
    f = cache_dir / "asset2.zip"
    f.write_bytes(b"data")
    cache = get_asset_cache_manager()
    cache.cache_asset("asset2", "megascans", str(f))

    staging = get_project_asset_staging()
    entry = staging.stage_asset("proj1", "asset2", provider="megascans")
    assert entry.source_path == str(f)


def test_stage_environment_returns_list():
    staging = get_project_asset_staging()
    # Without real retrieval, this returns empty (no vector pipeline in tests)
    entries = staging.stage_environment("proj2", "industrial_hangar", top_k=5)
    assert isinstance(entries, list)


def test_build_project_cache():
    cache = get_asset_cache_manager()
    cache.cache_asset("x1", "megascans", "/p1")
    cache.cache_asset("x2", "megascans", "/p2")
    staging = get_project_asset_staging()
    result = staging.build_project_cache("proj3")
    assert result["project_id"] == "proj3"
    assert result["staged"] == 2


def test_cleanup_removes_missing():
    staging = get_project_asset_staging()
    # Stage asset with missing path
    staging._index["proj4"] = [
        StagingEntry(project_id="proj4", asset_id="gone", local_path="/nonexistent/path.zip")
    ]
    result = staging.cleanup("proj4")
    assert "gone" in result["removed"]


def test_cleanup_dry_run():
    staging = get_project_asset_staging()
    staging._index["proj5"] = [
        StagingEntry(project_id="proj5", asset_id="gone2", local_path="/nonexistent2.zip")
    ]
    result = staging.cleanup("proj5", dry_run=True)
    assert result["dry_run"] is True
    # Entry should still be there after dry run
    assert len(staging.get_project_assets("proj5")) == 1


def test_get_project_assets():
    staging = get_project_asset_staging()
    staging.stage_asset("proj6", "asset3", provider="megascans")
    staging.stage_asset("proj6", "asset4", provider="megascans")
    assets = staging.get_project_assets("proj6")
    assert len(assets) == 2


def test_get_statistics():
    staging = get_project_asset_staging()
    staging.stage_asset("proj7", "asset5", provider="megascans")
    stats = staging.get_statistics()
    assert stats["total_staged"] >= 1
    assert "staging_root" in stats


def test_staging_entry_to_dict():
    e = StagingEntry(project_id="p", asset_id="a", provider="megascans",
                     local_path="/local", environment="industrial_hangar")
    d = e.to_dict()
    assert d["project_id"] == "p"
    assert d["environment"] == "industrial_hangar"


def test_staging_entry_from_dict():
    d = {"project_id": "p2", "asset_id": "a2", "provider": "fab",
         "local_path": "/lp", "source_path": "/sp", "environment": "lab"}
    e = StagingEntry.from_dict(d)
    assert e.provider == "fab"
    assert e.environment == "lab"


def test_no_staging_root_returns_none(monkeypatch):
    monkeypatch.delenv("VIBRANTE_PROJECT_STAGING", raising=False)
    reset_project_asset_staging_for_tests()
    staging = get_project_asset_staging()
    d = staging._project_dir("p")
    assert d is None
