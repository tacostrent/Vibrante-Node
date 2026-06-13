"""
Tests for AcquisitionManager (Tier 12.5).
All local-library scanning tests use tmp_path.
"""
import json
import os
import pytest

from src.runtime.assets.acquisition import (
    AcquisitionRequest,
    AcquisitionResult,
    get_acquisition_manager,
    reset_acquisition_manager_for_tests,
    reset_download_registry_for_tests,
    reset_library_index_for_tests,
    reset_fab_library_scanner_for_tests,
    reset_megascans_scanner_for_tests,
)


@pytest.fixture(autouse=True)
def reset_all(monkeypatch):
    monkeypatch.delenv("VIBRANTE_ASSET_STORAGE", raising=False)
    monkeypatch.delenv("VIBRANTE_FAB_LIBRARY", raising=False)
    monkeypatch.delenv("VIBRANTE_MEGASCANS_LIBRARY", raising=False)
    reset_acquisition_manager_for_tests()
    reset_download_registry_for_tests()
    reset_library_index_for_tests()
    reset_fab_library_scanner_for_tests()
    reset_megascans_scanner_for_tests()
    yield
    reset_acquisition_manager_for_tests()
    reset_download_registry_for_tests()
    reset_library_index_for_tests()
    reset_fab_library_scanner_for_tests()
    reset_megascans_scanner_for_tests()


def test_singleton_identity():
    assert get_acquisition_manager() is get_acquisition_manager()


def test_ensure_not_found_returns_advisory():
    result = get_acquisition_manager().ensure_asset_available("fab", "nonexistent_asset")
    assert result.ok is False
    assert result.source == "not_found"
    assert len(result.warnings) > 0
    assert any("Fab" in w or "fab" in w.lower() for w in result.warnings)


def test_ensure_finds_from_registry(tmp_path):
    from src.runtime.assets.acquisition import get_download_registry
    local_file = str(tmp_path / "asset.fbx")
    (tmp_path / "asset.fbx").write_bytes(b"")
    get_download_registry().register("reg_asset_01", "fab", local_file)
    result = get_acquisition_manager().ensure_asset_available("fab", "reg_asset_01")
    assert result.ok is True
    assert result.source == "registry"
    assert result.local_path == local_file


def test_ensure_finds_from_library_index(tmp_path):
    from src.runtime.assets.acquisition import get_library_index
    local_file = str(tmp_path / "idx_asset.fbx")
    (tmp_path / "idx_asset.fbx").write_bytes(b"")
    get_library_index().add_entry(
        "idx_asset_01", "fab", "Index Asset",
        formats=["fbx"], local_path=local_file
    )
    result = get_acquisition_manager().ensure_asset_available("fab", "idx_asset_01")
    assert result.ok is True
    assert result.source == "library_index"


def test_ensure_missing_registry_marks_missing(tmp_path):
    from src.runtime.assets.acquisition import get_download_registry
    get_download_registry().register("gone_asset", "fab", "/nonexistent/path.fbx")
    result = get_acquisition_manager().ensure_asset_available("fab", "gone_asset")
    assert result.ok is False
    entry = get_download_registry().find("fab", "gone_asset")
    assert entry is not None
    assert entry.status == "missing"


def test_locate_asset_returns_path(tmp_path):
    from src.runtime.assets.acquisition import get_download_registry
    local_file = str(tmp_path / "loc_asset.fbx")
    (tmp_path / "loc_asset.fbx").write_bytes(b"")
    get_download_registry().register("loc_01", "fab", local_file)
    path = get_acquisition_manager().locate_asset("fab", "loc_01")
    assert path == local_file


def test_locate_asset_not_found_returns_none():
    path = get_acquisition_manager().locate_asset("fab", "no_such")
    assert path is None


def test_request_acquisition_returns_pending():
    asset = {"asset_id": "req_001", "provider": "megascans", "name": "Rock Pack", "category": "material"}
    req = get_acquisition_manager().request_acquisition(asset, reason="needed for scene")
    assert isinstance(req, AcquisitionRequest)
    assert req.status == "pending"
    assert req.asset_id == "req_001"


def test_list_pending_requests():
    mgr = get_acquisition_manager()
    mgr.request_acquisition({"asset_id": "pend01", "provider": "fab"})
    mgr.request_acquisition({"asset_id": "pend02", "provider": "fab"})
    pending = mgr.list_pending_requests()
    assert len(pending) == 2


def test_cancel_request():
    mgr = get_acquisition_manager()
    req = mgr.request_acquisition({"asset_id": "cancel01", "provider": "fab"})
    assert mgr.cancel_request(req.request_id) is True
    pending = mgr.list_pending_requests()
    assert all(r.request_id != req.request_id for r in pending)


def test_register_downloaded_asset(tmp_path):
    local_file = str(tmp_path / "dl_asset.fbx")
    (tmp_path / "dl_asset.fbx").write_bytes(b"")
    result = get_acquisition_manager().register_downloaded_asset(
        local_file,
        {"asset_id": "dl_001", "provider": "fab", "name": "Downloaded Tank", "category": "prop"},
    )
    assert result.ok is True
    assert result.local_path == local_file
    assert result.source == "manual_registration"


def test_register_resolves_pending_request(tmp_path):
    local_file = str(tmp_path / "resolved.fbx")
    (tmp_path / "resolved.fbx").write_bytes(b"")
    mgr = get_acquisition_manager()
    req = mgr.request_acquisition({"asset_id": "res_001", "provider": "fab"})
    mgr.register_downloaded_asset(local_file, {"asset_id": "res_001", "provider": "fab"})
    with mgr._lock:
        stored_req = mgr._requests.get(req.request_id)
    assert stored_req is not None
    assert stored_req.status == "available"


def test_acquisition_result_to_dict():
    result = AcquisitionResult(ok=True, asset_id="a1", provider="fab", local_path="/x.fbx", source="registry")
    d = result.to_dict()
    for key in ("ok", "asset_id", "provider", "local_path", "source", "errors", "warnings", "resolved_at"):
        assert key in d


def test_request_to_dict():
    req = AcquisitionRequest(asset_id="rq1", provider="megascans", status="pending")
    d = req.to_dict()
    for key in ("request_id", "asset_id", "provider", "name", "category",
                "reason", "status", "requested_at"):
        assert key in d


def test_get_statistics():
    stats = get_acquisition_manager().get_statistics()
    assert "ensure_count" in stats
    assert "register_count" in stats
    assert "total_requests" in stats
    assert "pending_requests" in stats


def test_never_raises_none():
    result = get_acquisition_manager().ensure_asset_available(None, None)  # type: ignore
    assert isinstance(result, AcquisitionResult)


def test_register_empty_path_returns_error():
    result = get_acquisition_manager().register_downloaded_asset("")
    assert result.ok is False
    assert len(result.errors) > 0
