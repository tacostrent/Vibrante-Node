"""
src/runtime/asset_identity — Tier 14.4.5 Asset Identity Audit
=============================================================
Verifies that every realized Houdini node has a persistent, non-opaque,
semantically consistent identity.

Design rules:
  - No bridge calls except HoudiniIdentityFetcher (isolated adapter).
  - Deterministic — same metadata always produces the same audit result.
  - Never raises in public methods.
  - Singleton pattern with reset_…_for_tests() on every module.
  - Thread-safe throughout.
"""

from src.runtime.asset_identity.opaque_id_detector import (
    OPAQUE_PATTERN,
    VOCABULARY_WORDS,
    OpaqueIdDetector,
    is_opaque_id,
    get_opaque_id_detector,
    reset_opaque_id_detector_for_tests,
)
from src.runtime.asset_identity.role_engine_validator import (
    ROLE_ENGINE_MAP,
    RoleEngineValidator,
    get_role_engine_validator,
    reset_role_engine_validator_for_tests,
)
from src.runtime.asset_identity.role_geometry_validator import (
    ROLE_CATEGORY_MAP,
    RoleGeometryValidator,
    get_role_geometry_validator,
    reset_role_geometry_validator_for_tests,
)
from src.runtime.asset_identity.asset_identity_auditor import (
    IDENTITY_AUDIT_PASS,
    IDENTITY_AUDIT_FAIL,
    IDENTITY_RESOLVED,
    IDENTITY_OPAQUE_NAME,
    IDENTITY_OPAQUE_ID,
    IDENTITY_MISSING_ROLE,
    IDENTITY_MISSING_CATEGORY,
    IDENTITY_MISSING_NAME,
    IDENTITY_ROLE_ENGINE_MISMATCH,
    IDENTITY_ROLE_CATEGORY_MISMATCH,
    IDENTITY_UNCLASSIFIED,
    ALL_IDENTITY_KEYS,
    AssetIdentityRecord,
    IdentityAuditResult,
    AssetIdentityAuditor,
    HoudiniIdentityFetcher,
    get_asset_identity_auditor,
    reset_asset_identity_auditor_for_tests,
)
from src.runtime.asset_identity.identity_review import (
    IdentityReviewResult,
    IdentityReview,
    get_identity_review,
    reset_identity_review_for_tests,
)
from src.runtime.asset_identity.identity_statistics import (
    IdentityStatRecord,
    IdentityStatistics,
    get_identity_statistics,
    reset_identity_statistics_for_tests,
)
from src.runtime.asset_identity.identity_serializer import (
    IdentitySerializer,
    get_identity_serializer,
    reset_identity_serializer_for_tests,
)

__all__ = [
    # Opaque ID detector
    "OPAQUE_PATTERN", "VOCABULARY_WORDS",
    "OpaqueIdDetector", "is_opaque_id",
    "get_opaque_id_detector", "reset_opaque_id_detector_for_tests",
    # Role/engine validator
    "ROLE_ENGINE_MAP", "RoleEngineValidator",
    "get_role_engine_validator", "reset_role_engine_validator_for_tests",
    # Role/geometry (category) validator
    "ROLE_CATEGORY_MAP", "RoleGeometryValidator",
    "get_role_geometry_validator", "reset_role_geometry_validator_for_tests",
    # Identity auditor
    "IDENTITY_AUDIT_PASS", "IDENTITY_AUDIT_FAIL",
    "IDENTITY_RESOLVED", "IDENTITY_OPAQUE_NAME", "IDENTITY_OPAQUE_ID",
    "IDENTITY_MISSING_ROLE", "IDENTITY_MISSING_CATEGORY", "IDENTITY_MISSING_NAME",
    "IDENTITY_ROLE_ENGINE_MISMATCH", "IDENTITY_ROLE_CATEGORY_MISMATCH",
    "IDENTITY_UNCLASSIFIED",
    "ALL_IDENTITY_KEYS",
    "AssetIdentityRecord", "IdentityAuditResult",
    "AssetIdentityAuditor", "HoudiniIdentityFetcher",
    "get_asset_identity_auditor", "reset_asset_identity_auditor_for_tests",
    # Review
    "IdentityReviewResult", "IdentityReview",
    "get_identity_review", "reset_identity_review_for_tests",
    # Statistics
    "IdentityStatRecord", "IdentityStatistics",
    "get_identity_statistics", "reset_identity_statistics_for_tests",
    # Serializer
    "IdentitySerializer",
    "get_identity_serializer", "reset_identity_serializer_for_tests",
]
