"""
identity_review.py — Tier 14.4.5 Asset Identity Audit
======================================================
4-dimension quality review of an IdentityAuditResult.

Dimensions and weights:
    identity_completeness  0.40   fraction of assets with all 3 identity keys present
    name_quality           0.30   fraction of assets with non-opaque names
    role_validity          0.20   fraction of assets with valid role/engine + role/category
    classification_rate    0.10   fraction of assets that are RESOLVED (not UNCLASSIFIED)

Grade mapping:
    >= 0.85  A  production_ready = True
    >= 0.70  B  production_ready = True
    >= 0.55  C  production_ready = False
    >= 0.40  D  production_ready = False
    <  0.40  F  production_ready = False

Blocking findings (force production_ready = False regardless of score):
    "unclassified assets"   — any asset has UNCLASSIFIED status
    "opaque identifiers"    — any asset has an opaque name or id
    "missing roles"         — any asset is missing vibrante_asset_role

Public API:
    IdentityReviewResult
    IdentityReview
    get_identity_review()
    reset_identity_review_for_tests()
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.runtime.asset_identity.asset_identity_auditor import (
    IdentityAuditResult,
    IDENTITY_RESOLVED,
    IDENTITY_UNCLASSIFIED,
)


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

@dataclass
class IdentityReviewResult:
    """Output of IdentityReview.review()."""

    overall_score:            float = 0.0
    identity_completeness:    float = 0.0
    name_quality:             float = 0.0
    role_validity:            float = 0.0
    classification_rate:      float = 0.0

    grade:           str  = "F"
    production_ready: bool = False

    findings:     List[str] = field(default_factory=list)
    blocking:     List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_score":         round(self.overall_score, 4),
            "identity_completeness": round(self.identity_completeness, 4),
            "name_quality":          round(self.name_quality, 4),
            "role_validity":         round(self.role_validity, 4),
            "classification_rate":   round(self.classification_rate, 4),
            "grade":                 self.grade,
            "production_ready":      self.production_ready,
            "findings":              list(self.findings),
            "blocking":              list(self.blocking),
        }


# ---------------------------------------------------------------------------
# Reviewer
# ---------------------------------------------------------------------------

_WEIGHTS = {
    "identity_completeness": 0.40,
    "name_quality":          0.30,
    "role_validity":         0.20,
    "classification_rate":   0.10,
}

_BLOCKING_KEYWORDS = (
    "unclassified assets",
    "opaque identifiers",
    "missing roles",
)


class IdentityReview:
    """
    Scores a completed IdentityAuditResult across 4 dimensions.
    Thread-safe (stateless computation).
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def review(self, audit_result: IdentityAuditResult) -> IdentityReviewResult:
        """
        Score and grade the audit result.
        Never raises.
        """
        try:
            return self._review(audit_result)
        except Exception:
            return IdentityReviewResult(
                findings=["review computation failed"],
                production_ready=False,
                grade="F",
            )

    def _review(self, r: IdentityAuditResult) -> IdentityReviewResult:
        total = r.total_assets
        findings: List[str] = []
        blocking: List[str] = []

        if total == 0:
            # Vacuous pass: no assets to audit
            return IdentityReviewResult(
                overall_score=1.0,
                identity_completeness=1.0,
                name_quality=1.0,
                role_validity=1.0,
                classification_rate=1.0,
                grade="A",
                production_ready=True,
                findings=["no assets to audit — vacuous pass"],
            )

        # --- Dimension 1: identity completeness ---
        # Assets with all 3 identity keys present
        complete = total - r.missing_identity
        d_complete = complete / total

        # --- Dimension 2: name quality ---
        non_opaque = total - r.opaque_assets
        d_name = non_opaque / total

        # --- Dimension 3: role validity ---
        # Assets where role/engine AND role/category are both OK
        n_role_ok = sum(
            1 for rec in r.records
            if rec.role_engine_ok and rec.role_category_ok
        )
        d_role = n_role_ok / total

        # --- Dimension 4: classification rate ---
        d_class = r.identity_coverage  # resolved / total

        score = (
            d_complete * _WEIGHTS["identity_completeness"]
            + d_name   * _WEIGHTS["name_quality"]
            + d_role   * _WEIGHTS["role_validity"]
            + d_class  * _WEIGHTS["classification_rate"]
        )

        # Findings
        if r.missing_identity > 0:
            findings.append(
                f"{r.missing_identity} asset(s) have incomplete identity keys"
            )
        if r.opaque_assets > 0:
            findings.append(
                f"{r.opaque_assets} asset(s) have opaque identifiers — "
                "replace with human-readable names (e.g. 'Wooden Chair' not 'xgihfgbqx')"
            )
        if r.unclassified_assets > 0:
            findings.append(
                f"{r.unclassified_assets} asset(s) are unclassified "
                "(multiple missing identity fields)"
            )
        for rec in r.records:
            if not rec.role_engine_ok:
                findings.append(
                    f"role/engine mismatch on '{rec.asset_name}': {rec.findings}"
                )
            if not rec.role_category_ok:
                findings.append(
                    f"role/category mismatch on '{rec.asset_name}': {rec.findings}"
                )

        # Blocking findings
        if r.unclassified_assets > 0:
            blocking.append("unclassified assets")
        if r.opaque_assets > 0:
            blocking.append("opaque identifiers")
        if any(rec.asset_role == "" for rec in r.records):
            blocking.append("missing roles")

        grade = _grade(score)
        prod_ready = (
            score >= 0.70
            and len(blocking) == 0
        )

        return IdentityReviewResult(
            overall_score         = round(score, 4),
            identity_completeness = round(d_complete, 4),
            name_quality          = round(d_name, 4),
            role_validity         = round(d_role, 4),
            classification_rate   = round(d_class, 4),
            grade                 = grade,
            production_ready      = prod_ready,
            findings              = findings,
            blocking              = blocking,
        )


def _grade(score: float) -> str:
    if score >= 0.85:
        return "A"
    if score >= 0.70:
        return "B"
    if score >= 0.55:
        return "C"
    if score >= 0.40:
        return "D"
    return "F"


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[IdentityReview] = None
_lock = threading.Lock()


def get_identity_review() -> IdentityReview:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = IdentityReview()
    return _instance


def reset_identity_review_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
