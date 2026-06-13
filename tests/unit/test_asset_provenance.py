"""Tests for src/runtime/assets/metadata/asset_provenance.py"""
import time
import pytest

from src.runtime.assets.metadata.asset_provenance import (
    AssetProvenance,
    ProvenanceRecord,
    SESSION_EVENT_TYPES,
    get_asset_provenance,
    reset_asset_provenance_for_tests,
)
from src.runtime.assets.schema import AssetDescriptor


def _make_asset(asset_id="test_001", provider="sketchfab") -> AssetDescriptor:
    return AssetDescriptor(
        asset_id=asset_id,
        provider=provider,
        name="Test Asset",
        category="prop",
        formats=["fbx"],
        license="cc-by",
    )


@pytest.fixture(autouse=True)
def reset():
    reset_asset_provenance_for_tests()
    yield
    reset_asset_provenance_for_tests()


class TestSingleton:
    def test_singleton_identity(self):
        p1 = get_asset_provenance()
        p2 = get_asset_provenance()
        assert p1 is p2

    def test_reset_creates_new(self):
        p1 = get_asset_provenance()
        reset_asset_provenance_for_tests()
        p2 = get_asset_provenance()
        assert p1 is not p2


class TestProvenanceRecord:
    def test_record_has_required_fields(self):
        record = ProvenanceRecord(
            asset_id="test_001",
            provider="sketchfab",
            event_type="source_registered",
        )
        assert record.record_id.startswith("prov_")
        assert record.asset_id == "test_001"
        assert record.provider == "sketchfab"
        assert record.event_type == "source_registered"
        assert record.timestamp > 0

    def test_record_to_dict(self):
        record = ProvenanceRecord("a", "b", "source_registered", {"key": "val"})
        d = record.to_dict()
        assert "record_id" in d
        assert "asset_id" in d
        assert "provider" in d
        assert "event_type" in d
        assert "event_data" in d
        assert "timestamp" in d

    def test_invalid_event_type_normalized(self):
        record = ProvenanceRecord("a", "b", "invalid_type")
        # Should be normalized to a valid type
        assert record.event_type in SESSION_EVENT_TYPES


class TestRecordSource:
    def test_record_source_returns_id(self):
        prov = get_asset_provenance()
        rid = prov.record_source(_make_asset())
        assert isinstance(rid, str)
        assert rid.startswith("prov_")

    def test_record_source_stores_name(self):
        prov = get_asset_provenance()
        asset = _make_asset()
        prov.record_source(asset)
        history = prov.get_asset_history(asset.asset_id, asset.provider)
        assert len(history) == 1
        assert history[0]["event_type"] == "source_registered"

    def test_record_source_data(self):
        prov = get_asset_provenance()
        asset = _make_asset()
        prov.record_source(asset)
        history = prov.get_asset_history(asset.asset_id, asset.provider)
        data = history[0]["event_data"]
        assert "name" in data
        assert "category" in data
        assert "license" in data


class TestRecordDownload:
    def test_record_download_queued(self):
        prov = get_asset_provenance()
        rid = prov.record_download("asset_001", "sketchfab", "dl_task_1", "queued")
        assert rid.startswith("prov_")
        history = prov.get_asset_history("asset_001", "sketchfab")
        assert history[0]["event_type"] == "download_queued"

    def test_record_download_completed(self):
        prov = get_asset_provenance()
        prov.record_download("asset_001", "sketchfab", "dl_task_1", "completed")
        history = prov.get_asset_history("asset_001", "sketchfab")
        assert history[0]["event_type"] == "download_completed"


class TestRecordImport:
    def test_record_import_success(self):
        prov = get_asset_provenance()
        prov.record_import("asset_001", "sketchfab", "industrial_hangar", True)
        history = prov.get_asset_history("asset_001", "sketchfab")
        assert history[0]["event_type"] == "import_completed"

    def test_record_import_failure(self):
        prov = get_asset_provenance()
        prov.record_import("asset_001", "sketchfab", "industrial_hangar", False)
        history = prov.get_asset_history("asset_001", "sketchfab")
        assert history[0]["event_type"] == "import_attempted"


class TestRecordUsage:
    def test_record_usage(self):
        prov = get_asset_provenance()
        prov.record_usage("asset_001", "sketchfab", "industrial_hangar", "workflow_pack_v1")
        history = prov.get_asset_history("asset_001", "sketchfab")
        assert history[0]["event_type"] == "usage_recorded"
        data = history[0]["event_data"]
        assert data["scene_type"] == "industrial_hangar"
        assert data["workflow_name"] == "workflow_pack_v1"


class TestBuildProvenanceReport:
    def test_empty_report(self):
        prov = get_asset_provenance()
        report = prov.build_provenance_report("nonexistent", "sketchfab")
        assert report["asset_id"] == "nonexistent"
        assert report["records"] == []
        assert report["first_seen"] is None
        assert report["download_count"] == 0

    def test_full_report(self):
        prov = get_asset_provenance()
        asset = _make_asset()
        prov.record_source(asset)
        prov.record_download(asset.asset_id, asset.provider, "dl_1", "completed")
        prov.record_import(asset.asset_id, asset.provider, "scene", True)
        prov.record_usage(asset.asset_id, asset.provider, "hangar", "pack_v1")

        report = prov.build_provenance_report(asset.asset_id, asset.provider)
        assert report["asset_id"] == asset.asset_id
        assert len(report["records"]) == 4
        assert report["download_count"] == 1
        assert report["import_count"] == 1
        assert report["usage_count"] == 1
        assert report["first_seen"] is not None
        assert report["last_used"] is not None


class TestGetHistory:
    def test_history_newest_first(self):
        prov = get_asset_provenance()
        prov.record_source(_make_asset("a1"))
        time.sleep(0.01)
        prov.record_usage("a1", "sketchfab", None, None)
        history = prov.get_asset_history("a1", "sketchfab")
        # Newest first
        assert history[0]["timestamp"] >= history[-1]["timestamp"]

    def test_history_limit(self):
        prov = get_asset_provenance()
        for _ in range(10):
            prov.record_usage("a1", "sketchfab", None, None)
        history = prov.get_asset_history("a1", "sketchfab", limit=5)
        assert len(history) <= 5

    def test_history_filtered_by_asset(self):
        prov = get_asset_provenance()
        prov.record_source(_make_asset("a1"))
        prov.record_source(_make_asset("a2"))
        history = prov.get_asset_history("a1", "sketchfab")
        assert all(r["asset_id"] == "a1" for r in history)


class TestStatistics:
    def test_statistics_structure(self):
        prov = get_asset_provenance()
        s = prov.get_statistics()
        assert "total_records" in s
        assert "assets_tracked" in s
        assert "event_type_counts" in s

    def test_statistics_after_records(self):
        prov = get_asset_provenance()
        prov.record_source(_make_asset("a1"))
        prov.record_source(_make_asset("a2"))
        prov.record_usage("a1", "sketchfab", None, None)
        s = prov.get_statistics()
        assert s["total_records"] == 3
        assert s["assets_tracked"] == 2
        assert s["event_type_counts"].get("source_registered", 0) == 2
        assert s["event_type_counts"].get("usage_recorded", 0) == 1


class TestClear:
    def test_clear(self):
        prov = get_asset_provenance()
        prov.record_source(_make_asset())
        prov.clear()
        s = prov.get_statistics()
        assert s["total_records"] == 0
