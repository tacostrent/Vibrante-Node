"""
identity_serializer.py — Tier 14.4.5 Asset Identity Audit
==========================================================
Sorted-key JSON serializer for IdentityAuditResult and IdentityReviewResult.

Public API:
    IdentitySerializer
    get_identity_serializer()
    reset_identity_serializer_for_tests()
"""

from __future__ import annotations

import json
import threading
from typing import Any, Dict, Optional

from src.runtime.asset_identity.asset_identity_auditor import IdentityAuditResult
from src.runtime.asset_identity.identity_review import IdentityReviewResult

_SCHEMA_VERSION = "1.0.0"


class IdentitySerializer:
    """Serializes identity audit data to sorted-key JSON."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def serialize_audit(self, result: IdentityAuditResult, indent: int = 2) -> str:
        """Return sorted-key JSON string for an IdentityAuditResult. Never raises."""
        try:
            payload = result.to_dict()
            payload["_schema_version"] = _SCHEMA_VERSION
            return json.dumps(payload, sort_keys=True, indent=indent)
        except Exception as exc:
            return json.dumps({"error": str(exc), "_schema_version": _SCHEMA_VERSION})

    def serialize_review(self, result: IdentityReviewResult, indent: int = 2) -> str:
        """Return sorted-key JSON string for an IdentityReviewResult. Never raises."""
        try:
            payload = result.to_dict()
            payload["_schema_version"] = _SCHEMA_VERSION
            return json.dumps(payload, sort_keys=True, indent=indent)
        except Exception as exc:
            return json.dumps({"error": str(exc), "_schema_version": _SCHEMA_VERSION})

    def deserialize_audit(self, json_str: str) -> Dict[str, Any]:
        """Parse a JSON string back to a dict. Never raises."""
        try:
            return json.loads(json_str)
        except Exception:
            return {}


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[IdentitySerializer] = None
_lock = threading.Lock()


def get_identity_serializer() -> IdentitySerializer:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = IdentitySerializer()
    return _instance


def reset_identity_serializer_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
