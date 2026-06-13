"""
Megascans Authentication (Tier 12.9)
=======================================
Official Megascans / Fab API authentication using the Quixel application credential flow.

Authentication flow (from https://quixel.github.io/megascans-api-docs/quick-start-guide/):
  1. POST https://accounts.quixel.se/api/v1/applications/{APP_ID}/tokens
     Headers: Authorization: Basic base64(username:password)
              Content-Type: application/json
     Body:    {"secret": "APP_KEY"}
  2. Response: {"token": "...", "refreshToken": "..."}
  3. Use token in all API calls: Authorization: Bearer {token}

Environment variables (all read at call time, never at import):
  VIBRANTE_MEGASCANS_APP_ID    — Application ID from Quixel developer portal (required)
  VIBRANTE_MEGASCANS_APP_KEY   — Application Key (secret) from developer portal (required)
  VIBRANTE_MEGASCANS_USERNAME  — Quixel account email/username (required)
  VIBRANTE_MEGASCANS_PASSWORD  — Quixel account password (required)
  VIBRANTE_MEGASCANS_TOKEN     — Pre-existing bearer token (optional, skips exchange flow)

Security rules:
  - No hardcoded credentials
  - Credentials read from environment only, never stored to disk
  - AuthToken.to_dict() always returns "***" for the token field
  - AuthToken.from_dict() never restores the token value
  - Offline-safe: returns AuthToken(is_valid=False) when credentials are missing

Injectable transport for tests:
  auth._transport = MyMockTransport()
  # transport.exchange(app_id, app_key, username, password) → {"token": ..., "refreshToken": ...}
  # transport.get_user_info(token) → {"user_id": ..., "username": ...}
"""
from __future__ import annotations

import base64
import json
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

# Environment variable names
ENV_MEGASCANS_APP_ID   = "VIBRANTE_MEGASCANS_APP_ID"
ENV_MEGASCANS_APP_KEY  = "VIBRANTE_MEGASCANS_APP_KEY"
ENV_MEGASCANS_USERNAME = "VIBRANTE_MEGASCANS_USERNAME"
ENV_MEGASCANS_PASSWORD = "VIBRANTE_MEGASCANS_PASSWORD"
ENV_MEGASCANS_TOKEN    = "VIBRANTE_MEGASCANS_TOKEN"   # fallback: pre-existing bearer token

_AUTH_BASE_URL  = "https://accounts.quixel.se/api/v1/applications"
_TOKEN_TTL_SECONDS = 3600   # Quixel tokens expire in ~1 hour


@dataclass
class AuthToken:
    token:         str   = ""
    refresh_token: str   = ""
    user_id:       str   = ""
    username:      str   = ""
    expires_at:    float = 0.0
    is_valid:      bool  = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "token":         "***" if self.token else "",   # Never expose token
            "refresh_token": "***" if self.refresh_token else "",
            "user_id":       str(self.user_id),
            "username":      str(self.username),
            "expires_at":    float(self.expires_at),
            "is_valid":      bool(self.is_valid),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AuthToken":
        d = d if isinstance(d, dict) else {}
        return cls(
            token="",          # Never restore token from serialized form
            refresh_token="",  # Never restore refresh_token from serialized form
            user_id=str(d.get("user_id", "")),
            username=str(d.get("username", "")),
            expires_at=float(d.get("expires_at", 0.0)),
            is_valid=bool(d.get("is_valid", False)),
        )


class MegascansAuth:
    """
    Manages Megascans API authentication via the Quixel application credential flow.

    Priority:
      1. VIBRANTE_MEGASCANS_TOKEN (direct bearer token — no exchange needed)
      2. APP_ID + APP_KEY + USERNAME + PASSWORD → token exchange endpoint

    All methods are offline-safe and never raise.
    """

    def __init__(self) -> None:
        self._lock          = threading.Lock()
        self._token:        Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._token_ts:     float = 0.0
        self._user_info:    Dict[str, Any] = {}
        self._transport:    Optional[Any] = None  # Injectable for tests

    # ------------------------------------------------------------------
    # Public authentication API
    # ------------------------------------------------------------------

    def _is_jwt_expired(self, token: str) -> bool:
        """Return True if the JWT exp claim is in the past. Never raises."""
        try:
            parts = token.split('.')
            if len(parts) != 3:
                return False  # not a standard JWT — assume valid
            padding = '=' * (4 - len(parts[1]) % 4)
            payload = json.loads(base64.b64decode(parts[1] + padding).decode('utf-8', errors='replace'))
            exp = float(payload.get('exp', 0))
            return exp > 0 and time.time() > exp
        except Exception:
            return False  # on any parse error, assume not expired

    def authenticate(self, token: Optional[str] = None) -> AuthToken:
        """
        Authenticate using the best available method. Never raises.

        Priority:
          1. Explicit token argument
          2. VIBRANTE_MEGASCANS_TOKEN env var  (also read from vibrante_node.json)
          3. App credential exchange (APP_ID + APP_KEY + USERNAME + PASSWORD)
        """
        try:
            # Always re-read from the live Houdini session so a stale _applied flag
            # from an earlier call (before the bridge was up) doesn't block auth.
            from src.utils.vibrante_config import apply_vibrante_config
            apply_vibrante_config(force=True)

            # 1. Explicit or env-var bearer token (no exchange needed)
            direct = (str(token) if token else "").strip() or \
                     os.environ.get(ENV_MEGASCANS_TOKEN, "").strip()
            if direct and not self._is_jwt_expired(direct):
                with self._lock:
                    self._token    = direct
                    self._token_ts = time.time()
                return self._build_auth_token(direct)

            # 2. App credential exchange (also runs when direct token is expired)
            return self._exchange_credentials()
        except Exception:
            return AuthToken(is_valid=False)

    def refresh_token(self) -> AuthToken:
        """
        Re-authenticate: try refresh token first, then full re-exchange. Never raises.
        """
        try:
            with self._lock:
                rt = self._refresh_token

            if rt:
                result = self._try_refresh(rt)
                if result.is_valid:
                    return result

            # Refresh failed or no refresh token — full re-exchange
            with self._lock:
                self._token         = None
                self._refresh_token = None
                self._token_ts      = 0.0
            return self.authenticate()
        except Exception:
            return AuthToken(is_valid=False)

    def validate_token(self) -> AuthToken:
        """Check if the current cached token is still valid. Never raises."""
        try:
            with self._lock:
                token = self._token
                ts    = self._token_ts
            if not token:
                return AuthToken(is_valid=False)
            if time.time() - ts > _TOKEN_TTL_SECONDS:
                return AuthToken(is_valid=False)
            info = self._get_user_info_remote(token)
            with self._lock:
                self._user_info = dict(info)
            return AuthToken(
                token=token,
                user_id=str(info.get("user_id", info.get("id", ""))),
                username=str(info.get("username", info.get("email", ""))),
                expires_at=ts + _TOKEN_TTL_SECONDS,
                is_valid=True,
            )
        except Exception:
            return AuthToken(is_valid=False)

    def get_user_info(self) -> Dict[str, Any]:
        """Return cached user info. Never raises."""
        try:
            with self._lock:
                return dict(self._user_info)
        except Exception:
            return {}

    def get_token(self) -> Optional[str]:
        """
        Return a valid bearer token, or None if not authenticated.
        Auto-exchanges credentials on first call if APP_ID/KEY/USERNAME/PASSWORD are set.
        """
        with self._lock:
            token = self._token
            ts    = self._token_ts

        # Already have a valid cached token
        if token and (time.time() - ts < _TOKEN_TTL_SECONDS):
            return token

        # Try direct env-var token first
        direct = os.environ.get(ENV_MEGASCANS_TOKEN, "").strip()
        if direct:
            with self._lock:
                self._token    = direct
                self._token_ts = time.time()
            return direct

        # Try credential exchange
        result = self._exchange_credentials()
        if result.is_valid:
            return result.token
        return None

    def is_authenticated(self) -> bool:
        return bool(self.get_token())

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "authenticated":   bool(self._token),
                "token_age_s":     round(time.time() - self._token_ts, 1) if self._token_ts else 0,
                "has_refresh":     bool(self._refresh_token),
                "user_id":         self._user_info.get("user_id", self._user_info.get("id", "")),
                "auth_source":     (
                    "direct_token" if os.environ.get(ENV_MEGASCANS_TOKEN)
                    else "app_credentials" if os.environ.get(ENV_MEGASCANS_APP_ID)
                    else "none"
                ),
            }

    # ------------------------------------------------------------------
    # Internal: credential exchange
    # ------------------------------------------------------------------

    def _exchange_credentials(self) -> AuthToken:
        """Exchange app credentials for a bearer token. Never raises."""
        try:
            app_id   = os.environ.get(ENV_MEGASCANS_APP_ID, "").strip()
            app_key  = os.environ.get(ENV_MEGASCANS_APP_KEY, "").strip()
            username = os.environ.get(ENV_MEGASCANS_USERNAME, "").strip()
            password = os.environ.get(ENV_MEGASCANS_PASSWORD, "").strip()

            if not (app_id and app_key and username and password):
                return AuthToken(is_valid=False)

            if self._transport is not None:
                data = self._transport.exchange(app_id, app_key, username, password)
            else:
                data = self._post_token_endpoint(app_id, app_key, username, password)

            if not data or not data.get("token"):
                return AuthToken(is_valid=False)

            bearer = str(data["token"])
            rt     = str(data.get("refreshToken") or data.get("refresh_token") or "")
            now    = time.time()
            with self._lock:
                self._token         = bearer
                self._refresh_token = rt
                self._token_ts      = now

            return AuthToken(
                token=bearer,
                refresh_token=rt,
                expires_at=now + _TOKEN_TTL_SECONDS,
                is_valid=True,
            )
        except Exception:
            return AuthToken(is_valid=False)

    def _try_refresh(self, refresh_token: str) -> AuthToken:
        """Attempt to use a refresh token to get a new bearer token. Never raises."""
        try:
            app_id  = os.environ.get(ENV_MEGASCANS_APP_ID, "").strip()
            app_key = os.environ.get(ENV_MEGASCANS_APP_KEY, "").strip()
            if not (app_id and app_key):
                return AuthToken(is_valid=False)

            if self._transport is not None:
                # Tests can optionally implement refresh
                exchange_fn = getattr(self._transport, "refresh", None)
                if exchange_fn:
                    data = exchange_fn(app_id, refresh_token)
                else:
                    return AuthToken(is_valid=False)
            else:
                import urllib.request
                url  = f"{_AUTH_BASE_URL}/{app_id}/tokens/refresh"
                body = json.dumps({"refreshToken": refresh_token,
                                   "secret": app_key}).encode()
                req  = urllib.request.Request(url, data=body, method="POST")
                req.add_header("Content-Type", "application/json")
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode("utf-8", errors="replace"))

            if not data or not data.get("token"):
                return AuthToken(is_valid=False)

            bearer = str(data["token"])
            rt     = str(data.get("refreshToken") or data.get("refresh_token") or "")
            now    = time.time()
            with self._lock:
                self._token         = bearer
                self._refresh_token = rt
                self._token_ts      = now
            return AuthToken(token=bearer, refresh_token=rt,
                             expires_at=now + _TOKEN_TTL_SECONDS, is_valid=True)
        except Exception:
            return AuthToken(is_valid=False)

    def _build_auth_token(self, bearer: str) -> AuthToken:
        """Build an AuthToken from a known bearer token. Never raises."""
        try:
            info = self._get_user_info_remote(bearer)
            with self._lock:
                self._user_info = dict(info)
            return AuthToken(
                token=bearer,
                user_id=str(info.get("user_id", info.get("id", ""))),
                username=str(info.get("username", info.get("email", ""))),
                expires_at=time.time() + _TOKEN_TTL_SECONDS,
                is_valid=True,
            )
        except Exception:
            # Token set but can't verify — treat as valid (offline)
            return AuthToken(token=bearer, is_valid=True,
                             expires_at=time.time() + _TOKEN_TTL_SECONDS)

    # ------------------------------------------------------------------
    # Internal: HTTP helpers (injectable)
    # ------------------------------------------------------------------

    def _post_token_endpoint(
        self,
        app_id:   str,
        app_key:  str,
        username: str,
        password: str,
    ) -> Optional[Dict[str, Any]]:
        """
        POST https://accounts.quixel.se/api/v1/applications/{app_id}/tokens
        Authorization: Basic base64(username:password)
        Body: {"secret": app_key}
        """
        try:
            import urllib.request
            url      = f"{_AUTH_BASE_URL}/{app_id}/tokens"
            body     = json.dumps({"secret": app_key}).encode()
            raw_cred = f"{username}:{password}"
            b64_cred = base64.b64encode(raw_cred.encode()).decode()
            req      = urllib.request.Request(url, data=body, method="POST")
            req.add_header("Authorization", f"Basic {b64_cred}")
            req.add_header("Content-Type", "application/json")
            req.add_header("Accept", "application/json")
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8", errors="replace"))
        except Exception:
            return None

    def _get_user_info_remote(self, token: str) -> Dict[str, Any]:
        if self._transport is not None:
            return self._transport.get_user_info(token)
        try:
            import urllib.request
            req = urllib.request.Request("https://megascans.se/v1/account")
            req.add_header("Authorization", f"Bearer {token}")
            req.add_header("Accept", "application/json")
            with urllib.request.urlopen(req, timeout=5) as resp:
                return json.loads(resp.read().decode("utf-8", errors="replace"))
        except Exception:
            # Server unreachable but token was set — offline fallback
            return {"user_id": "offline", "username": "offline"}


_INSTANCE: Optional[MegascansAuth] = None
_INSTANCE_LOCK = threading.Lock()


def get_megascans_auth() -> MegascansAuth:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = MegascansAuth()
    return _INSTANCE


def reset_megascans_auth_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
