"""
Provider Session Manager (Tier 12.9)
=======================================
Manages authenticated provider sessions for Megascans, Fab, and future providers.

Security rules:
  - No hardcoded credentials.
  - Tokens read from environment only.
  - Token values never serialized to disk.
  - Offline-safe: all operations return safe defaults when not authenticated.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .megascans_auth import get_megascans_auth

_SUPPORTED_PROVIDERS = frozenset({"megascans", "fab"})
_SESSION_TTL_SECONDS = 3600


@dataclass
class ProviderSession:
    provider:      str = ""
    status:        str = "unauthenticated"   # "active" | "offline" | "expired" | "unauthenticated"
    user_id:       str = ""
    username:      str = ""
    token_masked:  str = ""
    created_at:    float = field(default_factory=time.time)
    expires_at:    float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider":     str(self.provider),
            "status":       str(self.status),
            "user_id":      str(self.user_id),
            "username":     str(self.username),
            "token_masked": str(self.token_masked),
            "created_at":   float(self.created_at),
            "expires_at":   float(self.expires_at),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ProviderSession":
        d = d if isinstance(d, dict) else {}
        return cls(
            provider=str(d.get("provider", "")),
            status=str(d.get("status", "unauthenticated")),
            user_id=str(d.get("user_id", "")),
            username=str(d.get("username", "")),
            token_masked=str(d.get("token_masked", "")),
            created_at=float(d.get("created_at") or time.time()),
            expires_at=float(d.get("expires_at", 0.0)),
        )


class ProviderSessionManager:
    """
    Central manager for provider authentication sessions.

    Megascans session delegates to MegascansAuth singleton.
    Fab shares the same token as Megascans (same API).
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: Dict[str, ProviderSession] = {}

    # ------------------------------------------------------------------
    # Session operations
    # ------------------------------------------------------------------

    def login(self, provider: str, token: Optional[str] = None) -> ProviderSession:
        """Authenticate a provider session. Never raises."""
        try:
            provider = str(provider).strip().lower()
            if provider not in _SUPPORTED_PROVIDERS:
                return ProviderSession(provider=provider, status="unauthenticated")
            if provider in ("megascans", "fab"):
                auth   = get_megascans_auth()
                result = auth.authenticate(token)
                masked = ("***" + result.token[-4:]) if (result.is_valid and result.token) else ""
                session = ProviderSession(
                    provider=provider,
                    status="active" if result.is_valid else "offline",
                    user_id=result.user_id,
                    username=result.username,
                    token_masked=masked,
                    expires_at=result.expires_at,
                )
                with self._lock:
                    self._sessions[provider] = session
                return session
            return ProviderSession(provider=provider, status="unauthenticated")
        except Exception:
            return ProviderSession(provider=str(provider), status="unauthenticated")

    def logout(self, provider: str) -> bool:
        """Remove session for provider. Never raises."""
        try:
            provider = str(provider).strip().lower()
            with self._lock:
                if provider in self._sessions:
                    del self._sessions[provider]
                    return True
            return False
        except Exception:
            return False

    def validate_session(self, provider: str) -> ProviderSession:
        """Check if session is still valid. Never raises."""
        try:
            provider = str(provider).strip().lower()
            with self._lock:
                session = self._sessions.get(provider)
            if not session:
                return ProviderSession(provider=provider, status="unauthenticated")
            if session.expires_at and time.time() > session.expires_at:
                session.status = "expired"
                with self._lock:
                    self._sessions[provider] = session
            return session
        except Exception:
            return ProviderSession(provider=str(provider), status="unauthenticated")

    def refresh_session(self, provider: str) -> ProviderSession:
        """Refresh (re-authenticate) a provider session. Never raises."""
        try:
            provider = str(provider).strip().lower()
            if provider in ("megascans", "fab"):
                auth = get_megascans_auth()
                auth.refresh_token()
                return self.login(provider)
            return self.validate_session(provider)
        except Exception:
            return ProviderSession(provider=str(provider), status="unauthenticated")

    def get_provider_status(self, provider: str) -> Dict[str, Any]:
        """Return status dict for a provider. Never raises."""
        try:
            session = self.validate_session(provider)
            return session.to_dict()
        except Exception:
            return {"provider": str(provider), "status": "unauthenticated"}

    def get_all_statuses(self) -> List[Dict[str, Any]]:
        """Return status for all known providers."""
        try:
            return [self.get_provider_status(p) for p in sorted(_SUPPORTED_PROVIDERS)]
        except Exception:
            return []

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            active = sum(1 for s in self._sessions.values() if s.status == "active")
            return {
                "total_sessions":  len(self._sessions),
                "active_sessions": active,
                "providers":       sorted(self._sessions.keys()),
            }


_INSTANCE: Optional[ProviderSessionManager] = None
_INSTANCE_LOCK = threading.Lock()


def get_provider_session_manager() -> ProviderSessionManager:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = ProviderSessionManager()
    return _INSTANCE


def reset_provider_session_manager_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
