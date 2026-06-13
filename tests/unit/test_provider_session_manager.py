"""Tests for src/runtime/assets/acquisition_online/provider_session_manager.py"""
import pytest
from src.runtime.assets.acquisition_online import (
    get_provider_session_manager,
    get_megascans_auth,
    reset_provider_session_manager_for_tests,
    reset_megascans_auth_for_tests,
    ProviderSession,
)


class _MockAuthTransport:
    def get_user_info(self, token):
        return {"user_id": "u1", "username": "testuser"}


@pytest.fixture(autouse=True)
def reset_all(monkeypatch):
    monkeypatch.delenv("VIBRANTE_MEGASCANS_TOKEN", raising=False)
    reset_megascans_auth_for_tests()
    reset_provider_session_manager_for_tests()
    yield
    reset_provider_session_manager_for_tests()
    reset_megascans_auth_for_tests()


def test_singleton():
    a = get_provider_session_manager()
    b = get_provider_session_manager()
    assert a is b


def test_login_no_token():
    mgr = get_provider_session_manager()
    session = mgr.login("megascans")
    assert session.provider == "megascans"
    assert session.status == "offline"


def test_login_with_token():
    auth = get_megascans_auth()
    auth._transport = _MockAuthTransport()
    mgr = get_provider_session_manager()
    session = mgr.login("megascans", token="mytoken")
    assert session.status == "active"
    assert session.user_id == "u1"
    assert session.username == "testuser"


def test_login_unsupported_provider():
    mgr = get_provider_session_manager()
    session = mgr.login("unknown_provider")
    assert session.status == "unauthenticated"


def test_logout():
    auth = get_megascans_auth()
    auth._transport = _MockAuthTransport()
    mgr = get_provider_session_manager()
    mgr.login("megascans", token="tok")
    removed = mgr.logout("megascans")
    assert removed is True


def test_logout_not_logged_in():
    mgr = get_provider_session_manager()
    removed = mgr.logout("megascans")
    assert removed is False


def test_validate_session_unauthenticated():
    mgr = get_provider_session_manager()
    session = mgr.validate_session("megascans")
    assert session.status == "unauthenticated"


def test_validate_session_active():
    auth = get_megascans_auth()
    auth._transport = _MockAuthTransport()
    mgr = get_provider_session_manager()
    mgr.login("megascans", token="tok")
    session = mgr.validate_session("megascans")
    assert session.status == "active"


def test_get_provider_status():
    mgr = get_provider_session_manager()
    status = mgr.get_provider_status("megascans")
    assert isinstance(status, dict)
    assert "provider" in status
    assert "status" in status


def test_get_all_statuses():
    mgr = get_provider_session_manager()
    statuses = mgr.get_all_statuses()
    assert isinstance(statuses, list)
    assert len(statuses) >= 2  # megascans + fab


def test_fab_shares_megascans_token():
    auth = get_megascans_auth()
    auth._transport = _MockAuthTransport()
    mgr = get_provider_session_manager()
    mgr.login("fab", token="sharedtoken")
    session = mgr.validate_session("fab")
    assert session.provider == "fab"


def test_session_token_masked():
    auth = get_megascans_auth()
    auth._transport = _MockAuthTransport()
    mgr = get_provider_session_manager()
    session = mgr.login("megascans", token="mysecrettoken123")
    assert "mysecrettoken123" not in session.token_masked
    assert session.token_masked.startswith("***")


def test_provider_session_to_dict():
    s = ProviderSession(provider="megascans", status="active", user_id="u1", username="name")
    d = s.to_dict()
    assert d["provider"] == "megascans"
    assert d["status"] == "active"


def test_statistics():
    mgr = get_provider_session_manager()
    stats = mgr.get_statistics()
    assert "total_sessions" in stats
    assert "active_sessions" in stats
