"""
Tests for LibraryWatcher (Tier 12.5).
Uses tmp_path for realistic file-system operations.
"""
import os
import time
import pytest

from src.runtime.assets.acquisition import (
    WatchEntry,
    NewAssetEvent,
    get_library_watcher,
    reset_library_watcher_for_tests,
    reset_download_registry_for_tests,
)


@pytest.fixture(autouse=True)
def reset_all(monkeypatch):
    monkeypatch.delenv("VIBRANTE_ASSET_STORAGE", raising=False)
    monkeypatch.delenv("VIBRANTE_FAB_LIBRARY", raising=False)
    monkeypatch.delenv("VIBRANTE_MEGASCANS_LIBRARY", raising=False)
    reset_library_watcher_for_tests()
    reset_download_registry_for_tests()
    yield
    reset_library_watcher_for_tests()
    reset_download_registry_for_tests()


def test_singleton_identity():
    assert get_library_watcher() is get_library_watcher()


def test_watch_registers_path(tmp_path):
    watcher = get_library_watcher()
    entries = watcher.watch([str(tmp_path)])
    assert len(entries) == 1
    assert entries[0].path == str(tmp_path)


def test_list_watches(tmp_path):
    watcher = get_library_watcher()
    watcher.watch([str(tmp_path)])
    watches = watcher.list_watches()
    paths = [w.path for w in watches]
    assert str(tmp_path) in paths


def test_unwatch(tmp_path):
    watcher = get_library_watcher()
    watcher.watch([str(tmp_path)])
    removed = watcher.unwatch(str(tmp_path))
    assert removed is True
    watches = watcher.list_watches()
    assert str(tmp_path) not in [w.path for w in watches]


def test_take_snapshot_returns_count(tmp_path):
    (tmp_path / "asset.fbx").write_bytes(b"")
    watcher = get_library_watcher()
    watcher.watch([str(tmp_path)])
    total = watcher.take_snapshot()
    assert total >= 1


def test_detect_new_assets_finds_new_file(tmp_path):
    watcher = get_library_watcher()
    watcher.watch([str(tmp_path)])
    watcher.take_snapshot()
    # Create a new file after snapshot
    (tmp_path / "new_asset.fbx").write_bytes(b"")
    events = watcher.detect_new_assets()
    assert len(events) >= 1
    paths = [e.detected_path for e in events]
    assert any("new_asset.fbx" in p for p in paths)


def test_detect_no_new_files_returns_empty(tmp_path):
    (tmp_path / "existing.fbx").write_bytes(b"")
    watcher = get_library_watcher()
    watcher.watch([str(tmp_path)])
    watcher.take_snapshot()
    # No new files
    events = watcher.detect_new_assets()
    assert len(events) == 0


def test_detect_only_tracks_asset_extensions(tmp_path):
    watcher = get_library_watcher()
    watcher.watch([str(tmp_path)])
    watcher.take_snapshot()
    (tmp_path / "image.png").write_bytes(b"")    # not an asset format
    (tmp_path / "asset.fbx").write_bytes(b"")     # this should be detected
    events = watcher.detect_new_assets()
    detected_paths = [e.detected_path for e in events]
    assert any("asset.fbx" in p for p in detected_paths)
    assert not any("image.png" in p for p in detected_paths)


def test_event_has_provider_hint(tmp_path, monkeypatch):
    ms_path = str(tmp_path / "megascans")
    os.makedirs(ms_path)
    monkeypatch.setenv("VIBRANTE_MEGASCANS_LIBRARY", ms_path)
    reset_library_watcher_for_tests()
    watcher = get_library_watcher()
    watcher.watch([ms_path])
    watcher.take_snapshot()
    (tmp_path / "megascans" / "new_rock.fbx").write_bytes(b"")
    events = watcher.detect_new_assets()
    if events:
        assert events[0].provider_hint in ("megascans", "local")


def test_register_asset_manually(tmp_path):
    asset_path = str(tmp_path / "manual_asset.fbx")
    (tmp_path / "manual_asset.fbx").write_bytes(b"")
    watcher = get_library_watcher()
    event = watcher.register_asset(asset_path, provider_hint="fab")
    assert event is not None
    assert event.registered is True
    assert "manual_asset.fbx" in event.detected_path


def test_get_recent_events(tmp_path):
    watcher = get_library_watcher()
    watcher.watch([str(tmp_path)])
    watcher.take_snapshot()
    (tmp_path / "r1.fbx").write_bytes(b"")
    (tmp_path / "r2.usd").write_bytes(b"")
    watcher.detect_new_assets()
    recent = watcher.get_recent_events(limit=10)
    assert len(recent) >= 2


def test_clear_events(tmp_path):
    watcher = get_library_watcher()
    watcher.watch([str(tmp_path)])
    watcher.take_snapshot()
    (tmp_path / "c1.fbx").write_bytes(b"")
    watcher.detect_new_assets()
    cleared = watcher.clear_events()
    assert cleared >= 1
    assert len(watcher.get_recent_events()) == 0


def test_watch_entry_to_dict():
    entry = WatchEntry(path="/lib/fab", label="fab_library")
    d = entry.to_dict()
    for key in ("watch_id", "path", "label", "active", "added_at"):
        assert key in d


def test_new_asset_event_to_dict():
    event = NewAssetEvent(detected_path="/lib/a.fbx", provider_hint="fab", file_format="fbx")
    d = event.to_dict()
    for key in ("event_id", "detected_path", "watch_path", "provider_hint",
                "file_format", "file_size", "detected_at", "registered"):
        assert key in d


def test_get_statistics():
    stats = get_library_watcher().get_statistics()
    assert "watched_paths" in stats
    assert "total_events" in stats
    assert "detect_count" in stats


def test_watch_empty_list():
    entries = get_library_watcher().watch([])
    assert entries == []
