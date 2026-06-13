"""Tests for src/runtime/assets/acquisition_online/megascans_auth.py

Auth flow (from Quixel API docs):
  POST https://accounts.quixel.se/api/v1/applications/{APP_ID}/tokens
  Authorization: Basic base64(username:password)
  Body: {"secret": APP_KEY}
  → {"token": "...", "refreshToken": "..."}
"""
import pytest
from src.runtime.assets.acquisition_online import (
    get_megascans_auth,
    reset_megascans_auth_for_tests,
    AuthToken,
    ENV_MEGASCANS_APP_ID,
    ENV_MEGASCANS_APP_KEY,
    ENV_MEGASCANS_USERNAME,
    ENV_MEGASCANS_PASSWORD,
    ENV_MEGASCANS_TOKEN,
)


class _MockTransport:
    """Simulates the token exchange + user info endpoints."""
    def __init__(self, user_id="u1", username="testuser", token="mock_bearer_token"):
        self.user_id    = user_id
        self.username   = username
        self._token     = token
        self.exchange_calls = 0
        self.user_info_calls = 0

    def exchange(self, app_id, app_key, username, password):
        self.exchange_calls += 1
        return {"token": self._token, "refreshToken": "mock_refresh_token"}

    def get_user_info(self, token):
        self.user_info_calls += 1
        return {"user_id": self.user_id, "username": self.username}


@pytest.fixture(autouse=True)
def reset_all(monkeypatch):
    for var in (ENV_MEGASCANS_TOKEN, ENV_MEGASCANS_APP_ID,
                ENV_MEGASCANS_APP_KEY, ENV_MEGASCANS_USERNAME, ENV_MEGASCANS_PASSWORD):
        monkeypatch.delenv(var, raising=False)
    reset_megascans_auth_for_tests()
    yield
    reset_megascans_auth_for_tests()


# ------------------------------------------------------------------
# Singleton
# ------------------------------------------------------------------

def test_singleton():
    a = get_megascans_auth()
    b = get_megascans_auth()
    assert a is b


# ------------------------------------------------------------------
# Direct bearer token (VIBRANTE_MEGASCANS_TOKEN)
# ------------------------------------------------------------------

def test_authenticate_with_explicit_token():
    auth = get_megascans_auth()
    transport = _MockTransport()
    auth._transport = transport
    result = auth.authenticate(token="direct_bearer")
    assert result.is_valid is True
    assert transport.user_info_calls == 1  # validates via user info
    assert transport.exchange_calls == 0   # no credential exchange needed


def test_authenticate_env_token(monkeypatch):
    monkeypatch.setenv(ENV_MEGASCANS_TOKEN, "env_bearer")
    reset_megascans_auth_for_tests()
    auth = get_megascans_auth()
    transport = _MockTransport()
    auth._transport = transport
    result = auth.authenticate()
    assert result.is_valid is True
    assert transport.exchange_calls == 0  # direct token path, no exchange


def test_get_token_from_env(monkeypatch):
    monkeypatch.setenv(ENV_MEGASCANS_TOKEN, "tok123")
    reset_megascans_auth_for_tests()
    auth = get_megascans_auth()
    assert auth.get_token() == "tok123"


def test_is_authenticated_true_via_direct_token(monkeypatch):
    monkeypatch.setenv(ENV_MEGASCANS_TOKEN, "tok")
    reset_megascans_auth_for_tests()
    auth = get_megascans_auth()
    assert auth.is_authenticated() is True


# ------------------------------------------------------------------
# App credential exchange flow (APP_ID + APP_KEY + USERNAME + PASSWORD)
# ------------------------------------------------------------------

def test_authenticate_via_credential_exchange(monkeypatch):
    monkeypatch.setenv(ENV_MEGASCANS_APP_ID,   "my_app_id")
    monkeypatch.setenv(ENV_MEGASCANS_APP_KEY,  "my_app_key")
    monkeypatch.setenv(ENV_MEGASCANS_USERNAME,  "user@example.com")
    monkeypatch.setenv(ENV_MEGASCANS_PASSWORD,  "securepass")
    reset_megascans_auth_for_tests()
    auth = get_megascans_auth()
    transport = _MockTransport()
    auth._transport = transport
    result = auth.authenticate()
    assert result.is_valid is True
    assert transport.exchange_calls == 1   # called the exchange endpoint
    assert result.token == "mock_bearer_token"


def test_exchange_called_with_correct_args(monkeypatch):
    monkeypatch.setenv(ENV_MEGASCANS_APP_ID,   "app1")
    monkeypatch.setenv(ENV_MEGASCANS_APP_KEY,  "key1")
    monkeypatch.setenv(ENV_MEGASCANS_USERNAME,  "user1")
    monkeypatch.setenv(ENV_MEGASCANS_PASSWORD,  "pass1")
    reset_megascans_auth_for_tests()

    call_args = {}
    class _CapturingTransport:
        def exchange(self, app_id, app_key, username, password):
            call_args.update(app_id=app_id, app_key=app_key,
                             username=username, password=password)
            return {"token": "t", "refreshToken": "rt"}
        def get_user_info(self, token):
            return {"user_id": "u", "username": "u"}

    auth = get_megascans_auth()
    auth._transport = _CapturingTransport()
    auth.authenticate()
    assert call_args["app_id"] == "app1"
    assert call_args["app_key"] == "key1"
    assert call_args["username"] == "user1"
    assert call_args["password"] == "pass1"


def test_get_token_triggers_exchange(monkeypatch):
    monkeypatch.setenv(ENV_MEGASCANS_APP_ID,   "app2")
    monkeypatch.setenv(ENV_MEGASCANS_APP_KEY,  "key2")
    monkeypatch.setenv(ENV_MEGASCANS_USERNAME,  "u2")
    monkeypatch.setenv(ENV_MEGASCANS_PASSWORD,  "p2")
    reset_megascans_auth_for_tests()
    auth = get_megascans_auth()
    transport = _MockTransport(token="exchanged_token")
    auth._transport = transport
    token = auth.get_token()
    assert token == "exchanged_token"
    assert transport.exchange_calls == 1


def test_no_credentials_returns_invalid():
    auth = get_megascans_auth()
    result = auth.authenticate()
    assert result.is_valid is False


def test_partial_credentials_returns_invalid(monkeypatch):
    monkeypatch.setenv(ENV_MEGASCANS_APP_ID, "app3")  # key/username/password missing
    reset_megascans_auth_for_tests()
    auth = get_megascans_auth()
    result = auth.authenticate()
    assert result.is_valid is False


# ------------------------------------------------------------------
# Refresh token
# ------------------------------------------------------------------

def test_refresh_token_uses_refresh_token(monkeypatch):
    monkeypatch.setenv(ENV_MEGASCANS_APP_ID,   "app4")
    monkeypatch.setenv(ENV_MEGASCANS_APP_KEY,  "key4")
    monkeypatch.setenv(ENV_MEGASCANS_USERNAME,  "u4")
    monkeypatch.setenv(ENV_MEGASCANS_PASSWORD,  "p4")
    reset_megascans_auth_for_tests()

    class _RefreshTransport:
        def exchange(self, app_id, app_key, username, password):
            return {"token": "first_token", "refreshToken": "my_refresh_tok"}
        def get_user_info(self, token):
            return {"user_id": "u4", "username": "u4"}
        def refresh(self, app_id, refresh_token):
            return {"token": "refreshed_token", "refreshToken": "new_refresh"}

    auth = get_megascans_auth()
    auth._transport = _RefreshTransport()
    auth.authenticate()
    result = auth.refresh_token()
    assert result.is_valid is True
    assert result.token == "refreshed_token"


# ------------------------------------------------------------------
# Security: token never serialized
# ------------------------------------------------------------------

def test_auth_token_never_exposes_token():
    t = AuthToken(token="supersecret", refresh_token="alsosecret", is_valid=True)
    d = t.to_dict()
    assert "supersecret" not in str(d)
    assert "alsosecret"  not in str(d)
    assert d["token"] == "***"
    assert d["refresh_token"] == "***"


def test_auth_token_from_dict_never_restores_secrets():
    d = {"token": "shouldnotrestore", "refresh_token": "neitherme",
         "user_id": "u99", "is_valid": True}
    t = AuthToken.from_dict(d)
    assert t.token == ""
    assert t.refresh_token == ""
    assert t.user_id == "u99"


# ------------------------------------------------------------------
# Validate / status
# ------------------------------------------------------------------

def test_validate_token_no_token():
    auth = get_megascans_auth()
    result = auth.validate_token()
    assert result.is_valid is False


def test_is_authenticated_false_no_credentials():
    auth = get_megascans_auth()
    assert auth.is_authenticated() is False


def test_get_user_info_empty_without_auth():
    auth = get_megascans_auth()
    assert isinstance(auth.get_user_info(), dict)


def test_statistics_auth_source_none():
    auth = get_megascans_auth()
    stats = auth.get_statistics()
    assert stats["auth_source"] == "none"
    assert "authenticated" in stats
    assert "has_refresh" in stats


def test_statistics_auth_source_direct_token(monkeypatch):
    monkeypatch.setenv(ENV_MEGASCANS_TOKEN, "tok")
    reset_megascans_auth_for_tests()
    auth = get_megascans_auth()
    stats = auth.get_statistics()
    assert stats["auth_source"] == "direct_token"


def test_statistics_auth_source_app_credentials(monkeypatch):
    monkeypatch.setenv(ENV_MEGASCANS_APP_ID, "myapp")
    reset_megascans_auth_for_tests()
    auth = get_megascans_auth()
    stats = auth.get_statistics()
    assert stats["auth_source"] == "app_credentials"
