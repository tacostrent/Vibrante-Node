"""
Structural Review Engine (Tier 10.3 / 10.3.5 — Structural Asset Classification)
=================================================================================
Validates that classified structural assets are placed correctly relative
to the room shell and that architectural assets have not leaked into
furniture/decoration pipelines.

When called with optional routing/attachment/completeness results (Tier 10.3.5),
the review uses the extended 6-dimension weight scheme.  When called without
those results the legacy 4-dimension scheme is used for backward compatibility.

Extended dimensions (weights) — used when routing_result / attachment_result /
completeness_result are supplied:
  placement_validity       (0.25)  — attachment target is physically valid
  routing_integrity        (0.20)  — selected_rule == applied_rule for all structural
  builder_integrity        (0.20)  — structural assets routed to dedicated builders
  attachment_integrity     (0.15)  — elements have valid physical attachments
  role_accuracy            (0.10)  — role matches evidence
  coverage                 (0.10)  — fraction of assets with non-unknown role
  room_shell_completeness  (bonus) — recorded but does not affect overall_score directly;
                                     a failing shell forces production_ready = False

Legacy dimensions (weights) — used when no routing/attachment results:
  placement_validity   (0.35)
  pipeline_integrity   (0.30)
  role_accuracy        (0.20)
  coverage             (0.15)

Grade mapping:
  ≥ 0.85 → A  (production_ready)
  ≥ 0.70 → B  (production_ready)
  ≥ 0.55 → C
  ≥ 0.40 → D
  < 0.40 → F

Blocking findings (force production_ready = False regardless of score):
  "floating structural asset"          — structural placed at y=0 without wall/floor attachment
  "architectural asset in cluster"     — doorway/beam/column inside furniture cluster
  "doorway placed on floor center"     — doorway at origin without wall reference
  "beam treated as decoration"         — beam role in decoration list
  "fireplace placed as free-standing"  — fireplace not attached to wall
  "PLACEMENT_ROUTING_MISMATCH"         — routing engine detected a rule mismatch (Tier 10.3.5)
  "ROOM_SHELL_INCOMPLETE"              — room shell fails minimum element counts (Tier 10.3.5)
  "door not attached to wall"          — attachment enforcer finding (Tier 10.3.5)
  "beam not attached to ceiling"       — attachment enforcer finding (Tier 10.3.5)
  "column not attached to floor"       — attachment enforcer finding (Tier 10.3.5)
  "fireplace not attached to wall"     — attachment enforcer finding (Tier 10.3.5)

DESIGN RULES:
  1. No bridge calls. No Houdini imports.
  2. Deterministic.
  3. Never raises.
  4. Singleton pattern.
  5. Backward compatible — existing callers that omit the new optional params
     continue to receive scores computed with the legacy weights.

Public API:
    StructuralReviewResult
    StructuralReview
    get_structural_review()
    reset_structural_review_for_tests()
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.runtime.structure.structural_placement_rules import (
    STRUCTURAL_ROLES,
    get_structural_placement_rules,
)

_PRODUCTION_THRESHOLD = 0.70

# Legacy weights (4-dimension, backward-compatible)
_W_PLACEMENT  = 0.35
_W_PIPELINE   = 0.30
_W_ROLE       = 0.20
_W_COVERAGE   = 0.15

# Extended weights (6-dimension, Tier 10.3.5)
_EW_PLACEMENT    = 0.25
_EW_ROUTING      = 0.20
_EW_BUILDER      = 0.20
_EW_ATTACHMENT   = 0.15
_EW_ROLE         = 0.10
_EW_COVERAGE     = 0.10

# Blocking keywords introduced by Tier 10.3.5
_BLOCKING_T1035 = frozenset({
    "PLACEMENT_ROUTING_MISMATCH",
    "ROOM_SHELL_INCOMPLETE",
    "door not attached to wall",
    "beam not attached to ceiling",
    "column not attached to floor",
    "fireplace not attached to wall",
})

# Roles that must never appear in furniture/decoration pipelines
_MUST_NOT_CLUSTER = frozenset({
    "doorway", "door_frame", "beam", "support_beam", "column",
    "archway", "floor_piece", "ceiling_piece", "wall", "wall_segment",
})

# Roles that must be attached to a wall
_WALL_ATTACHED = frozenset({
    "doorway", "door_frame", "window", "window_frame", "fireplace",
    "wall_segment", "archway",
})

# Roles that must be above eye level (y_min > 1.8 m)
_ABOVE_EYE_LEVEL = frozenset({"beam", "support_beam"})

# Roles that must have y_min ≈ 0 (floor-touching)
_FLOOR_TOUCHING = frozenset({"column", "floor_piece", "stair", "railing"})


@dataclass
class StructuralReviewResult:
    """Structural placement quality review for a batch of classified assets."""

    review_id:          str   = field(default_factory=lambda: f"sr_{uuid.uuid4().hex[:10]}")

    # Core dimension scores (legacy + extended)
    placement_validity:     float = 0.0
    pipeline_integrity:     float = 0.0   # legacy dimension (also routing_integrity in extended)
    role_accuracy:          float = 0.0
    coverage:               float = 0.0
    overall_score:          float = 0.0

    # Extended dimensions (Tier 10.3.5) — 0.0 when not evaluated
    routing_integrity:      float = 0.0
    builder_integrity:      float = 0.0
    attachment_integrity:   float = 0.0
    room_shell_completeness: float = 0.0  # recorded; failing shell → production_ready=False

    grade:              str   = "F"
    production_ready:   bool  = False

    asset_count:        int   = 0
    structural_count:   int   = 0
    classified_count:   int   = 0

    findings:           List[str] = field(default_factory=list)
    recommendations:    List[str] = field(default_factory=list)
    review_summary:     str   = ""
    generated_at:       float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "review_id":              self.review_id,
            "placement_validity":     self.placement_validity,
            "pipeline_integrity":     self.pipeline_integrity,
            "routing_integrity":      self.routing_integrity,
            "builder_integrity":      self.builder_integrity,
            "attachment_integrity":   self.attachment_integrity,
            "room_shell_completeness":self.room_shell_completeness,
            "role_accuracy":          self.role_accuracy,
            "coverage":               self.coverage,
            "overall_score":          self.overall_score,
            "grade":                  self.grade,
            "production_ready":       self.production_ready,
            "asset_count":            self.asset_count,
            "structural_count":       self.structural_count,
            "classified_count":       self.classified_count,
            "findings":               list(self.findings),
            "recommendations":        list(self.recommendations),
            "review_summary":         self.review_summary,
            "generated_at":           self.generated_at,
        }


class StructuralReview:
    """
    Validates structural classification results against placement rules.

    Usage:
        review = get_structural_review()
        result = review.review(classifications)          # list of result dicts or StructuralClassificationResult
        result = review.review_single(classification)    # one asset
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def review(
        self,
        classifications:      List[Any],
        cluster_asset_ids:    Optional[List[str]] = None,
        decoration_asset_ids: Optional[List[str]] = None,
        routing_result:       Optional[Any]       = None,
        attachment_result:    Optional[Any]       = None,
        completeness_result:  Optional[Any]       = None,
    ) -> StructuralReviewResult:
        """
        Review a batch of StructuralClassificationResult objects (or dicts).

        Args:
            classifications:      List of classification results.
            cluster_asset_ids:    Asset IDs currently in furniture clusters.
            decoration_asset_ids: Asset IDs currently in decoration lists.
            routing_result:       RoutingResult (or dict) from StructuralRoutingEngine.
                                  When supplied activates extended 6-dimension scoring.
            attachment_result:    AttachmentResult (or dict) from StructuralAttachmentEnforcer.
            completeness_result:  CompletenessValidationResult (or dict) from
                                  RoomShellCompletenessValidator.

        Returns:
            StructuralReviewResult.  Never raises.
        """
        try:
            return self._review(
                classifications,
                cluster_asset_ids or [],
                decoration_asset_ids or [],
                routing_result,
                attachment_result,
                completeness_result,
            )
        except Exception as exc:
            r = StructuralReviewResult()
            r.findings.append(f"StructuralReview engine error: {exc}")
            r.review_summary = f"Review failed: {exc}"
            return r

    def _review(
        self,
        items:              List[Any],
        cluster_ids:        List[str],
        decoration_ids:     List[str],
        routing_result:     Optional[Any],
        attachment_result:  Optional[Any],
        completeness_result: Optional[Any],
    ) -> StructuralReviewResult:
        r = StructuralReviewResult()
        blocking: List[str] = []

        cluster_set    = set(cluster_ids)
        decoration_set = set(decoration_ids)

        # Normalise to dicts
        dicts = [i.to_dict() if hasattr(i, "to_dict") else dict(i) for i in items]

        r.asset_count       = len(dicts)
        r.structural_count  = sum(1 for d in dicts if d.get("is_structural"))
        r.classified_count  = sum(
            1 for d in dicts
            if d.get("structural_role", "structural_unknown") != "structural_unknown"
        )

        # Normalise optional result args to dicts (or None)
        routing_dict     = _to_dict(routing_result)
        attachment_dict  = _to_dict(attachment_result)
        completeness_dict = _to_dict(completeness_result)
        extended_mode    = any(x is not None for x in (routing_dict, attachment_dict, completeness_dict))

        # ── 1. Placement validity ──────────────────────────────────────────
        r.placement_validity = self._score_placement(dicts, r.findings, blocking)

        # ── 2. Pipeline integrity (legacy) / Routing + Builder (extended) ──
        r.pipeline_integrity = self._score_pipeline(
            dicts, cluster_set, decoration_set, r.findings, blocking
        )

        if extended_mode:
            # routing_integrity — from RoutingAudit
            r.routing_integrity  = _score_routing(routing_dict, r.findings, blocking)
            # builder_integrity — from routing builder_assignments
            r.builder_integrity  = _score_builder_integrity(routing_dict, r.findings, blocking)
            # attachment_integrity — from AttachmentResult
            r.attachment_integrity = _score_attachment(attachment_dict, r.findings, blocking)
            # room_shell_completeness — from CompletenessValidationResult
            r.room_shell_completeness = _score_completeness(completeness_dict, r.findings, blocking)
        else:
            # Mirror pipeline_integrity into routing/builder for completeness
            r.routing_integrity  = r.pipeline_integrity
            r.builder_integrity  = r.pipeline_integrity

        # ── 3. Role accuracy ───────────────────────────────────────────────
        r.role_accuracy = self._score_role_accuracy(dicts, r.findings)

        # ── 4. Coverage ────────────────────────────────────────────────────
        r.coverage = self._score_coverage(r, r.findings)

        # ── Overall score ─────────────────────────────────────────────────
        if extended_mode:
            r.overall_score = (
                r.placement_validity   * _EW_PLACEMENT  +
                r.routing_integrity    * _EW_ROUTING    +
                r.builder_integrity    * _EW_BUILDER    +
                r.attachment_integrity * _EW_ATTACHMENT +
                r.role_accuracy        * _EW_ROLE       +
                r.coverage             * _EW_COVERAGE
            )
        else:
            r.overall_score = (
                r.placement_validity * _W_PLACEMENT +
                r.pipeline_integrity * _W_PIPELINE  +
                r.role_accuracy      * _W_ROLE      +
                r.coverage           * _W_COVERAGE
            )

        r.grade           = _grade(r.overall_score)
        r.production_ready = (
            r.overall_score >= _PRODUCTION_THRESHOLD
            and not blocking
        )
        r.recommendations  = _build_recommendations(r, dicts, extended_mode)
        r.review_summary   = _build_summary(r, blocking)
        return r

    @staticmethod
    def _score_placement(
        dicts:    List[Dict],
        findings: List[str],
        blocking: List[str],
    ) -> float:
        if not dicts:
            return 1.0

        violations = 0
        for d in dicts:
            role = d.get("structural_role", "prop")
            if role not in STRUCTURAL_ROLES:
                continue  # non-structural — skip

            intent = d.get("placement_intent") or {}
            attach_to = intent.get("attach_to", "")

            # Doorways must attach to a wall
            if role in _WALL_ATTACHED and not attach_to:
                findings.append(
                    f"Asset '{d.get('asset_id')}' has role '{role}' but has no "
                    "wall attachment target — floating structural asset."
                )
                blocking.append("floating structural asset")
                violations += 1

            # Beams must be above eye level
            if role in _ABOVE_EYE_LEVEL:
                # We check placement_target — "ceiling_support" is the expected value
                pt = intent.get("placement_target", "")
                if pt and "ceiling" not in pt and "above" not in pt:
                    findings.append(
                        f"Beam asset '{d.get('asset_id')}' has placement_target '{pt}' — "
                        "beams must target ceiling_support (above eye level)."
                    )
                    violations += 1

            # Doorways at floor center (no wall reference)
            if role == "doorway":
                pt = intent.get("placement_target", "")
                if pt == "floor_center" or attach_to == "floor":
                    findings.append(
                        f"Doorway '{d.get('asset_id')}' is targeting floor/floor_center — "
                        "doorway placed on floor center."
                    )
                    blocking.append("doorway placed on floor center")
                    violations += 1

            # Fireplace not attached to wall
            if role == "fireplace":
                if attach_to not in ("wall_face", "wall_attachment", "wall_boundary"):
                    findings.append(
                        f"Fireplace '{d.get('asset_id')}' has attach_to='{attach_to}' — "
                        "fireplace placed as free-standing (not wall-attached)."
                    )
                    blocking.append("fireplace placed as free-standing")
                    violations += 1

        structural = [d for d in dicts if d.get("is_structural")]
        if not structural:
            return 1.0
        return max(0.0, 1.0 - violations / len(structural))

    @staticmethod
    def _score_pipeline(
        dicts:          List[Dict],
        cluster_set:    set,
        decoration_set: set,
        findings:       List[str],
        blocking:       List[str],
    ) -> float:
        if not dicts:
            return 1.0

        violations = 0
        for d in dicts:
            role     = d.get("structural_role", "prop")
            asset_id = d.get("asset_id", "")

            # Check if a must-not-cluster role leaked into furniture cluster
            if role in _MUST_NOT_CLUSTER and asset_id in cluster_set:
                findings.append(
                    f"Architectural asset '{asset_id}' (role='{role}') found inside a "
                    "furniture cluster — architectural asset in cluster."
                )
                blocking.append("architectural asset in cluster")
                violations += 1

            # Check if a structural role leaked into decoration list
            if role in STRUCTURAL_ROLES and role not in ("prop", "decoration") \
                    and asset_id in decoration_set:
                if role == "beam":
                    findings.append(
                        f"Beam '{asset_id}' found in decoration list — beam treated as decoration."
                    )
                    blocking.append("beam treated as decoration")
                else:
                    findings.append(
                        f"Structural asset '{asset_id}' (role='{role}') found in decoration "
                        "list — structural role in decoration pipeline."
                    )
                violations += 1

        total = len(dicts)
        if total == 0:
            return 1.0
        return max(0.0, 1.0 - violations / total)

    @staticmethod
    def _score_role_accuracy(
        dicts:    List[Dict],
        findings: List[str],
    ) -> float:
        if not dicts:
            return 1.0

        unknown = sum(
            1 for d in dicts
            if d.get("structural_role", "structural_unknown") == "structural_unknown"
        )
        low_conf = sum(
            1 for d in dicts
            if float(d.get("confidence", 1.0)) < 0.50
        )

        total = len(dicts)
        unknown_frac = unknown / total
        low_frac     = low_conf / total

        if unknown_frac > 0.3:
            findings.append(
                f"{unknown}/{total} assets have unknown structural role — "
                "classification quality is low."
            )
        if low_frac > 0.3:
            findings.append(
                f"{low_conf}/{total} assets have confidence below 0.50 — "
                "metadata or geometry data is insufficient."
            )

        score = 1.0 - (unknown_frac * 0.5 + low_frac * 0.3)
        return max(0.0, score)

    @staticmethod
    def _score_coverage(
        r:        StructuralReviewResult,
        findings: List[str],
    ) -> float:
        if r.asset_count == 0:
            return 1.0
        frac = r.classified_count / r.asset_count
        if frac < 0.8:
            findings.append(
                f"Only {r.classified_count}/{r.asset_count} assets successfully classified "
                f"({frac:.0%}) — target is 100%."
            )
        return frac


# ──────────────────────────────────────────────────────────────────────────────
# Tier 10.3.5 scoring helpers
# ──────────────────────────────────────────────────────────────────────────────

def _to_dict(obj: Optional[Any]) -> Optional[Dict]:
    if obj is None:
        return None
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if isinstance(obj, dict):
        return obj
    return None


def _score_routing(
    routing_dict: Optional[Dict],
    findings:     List[str],
    blocking:     List[str],
) -> float:
    if not routing_dict:
        return 1.0
    audit = routing_dict.get("audit") or {}
    total    = int(audit.get("total_assets", 0))
    valid    = int(audit.get("routing_valid_count", total))
    mismatches = int(audit.get("mismatch_count", 0))
    if mismatches > 0:
        msg = f"{mismatches} PLACEMENT_ROUTING_MISMATCH — selected_rule != applied_rule."
        findings.append(msg)
        blocking.append("PLACEMENT_ROUTING_MISMATCH")
    if total == 0:
        return 1.0
    return max(0.0, valid / total)


def _score_builder_integrity(
    routing_dict: Optional[Dict],
    findings:     List[str],
    blocking:     List[str],
) -> float:
    if not routing_dict:
        return 1.0
    assignments = routing_dict.get("builder_assignments") or {}
    structural_to_generic = 0
    structural_total      = 0
    for builder, assets in assignments.items():
        for asset in (assets or []):
            if asset.get("_is_structural"):
                structural_total += 1
                if builder == "SemanticLayoutEngine" or builder == "GenericLayoutSolver":
                    structural_to_generic += 1
                    findings.append(
                        f"Structural asset '{asset.get('asset_id', '')}' "
                        f"(role='{asset.get('_structural_role', '')}') "
                        "routed to GenericLayoutSolver instead of a dedicated builder."
                    )
    if structural_to_generic > 0:
        blocking.append("PLACEMENT_ROUTING_MISMATCH")
    if structural_total == 0:
        return 1.0
    return max(0.0, 1.0 - structural_to_generic / structural_total)


def _score_attachment(
    attachment_dict: Optional[Dict],
    findings:        List[str],
    blocking:        List[str],
) -> float:
    if not attachment_dict:
        return 1.0
    total   = int(attachment_dict.get("total_checked", 0))
    valid   = int(attachment_dict.get("valid_count",   total))
    invalid = int(attachment_dict.get("invalid_count", 0))
    for bf in (attachment_dict.get("blocking") or []):
        if bf not in blocking:
            blocking.append(bf)
    for f in (attachment_dict.get("findings") or []):
        if f not in findings:
            findings.append(f)
    if total == 0:
        return 1.0
    return max(0.0, valid / total)


def _score_completeness(
    completeness_dict: Optional[Dict],
    findings:          List[str],
    blocking:          List[str],
) -> float:
    if not completeness_dict:
        return 1.0
    ok = bool(completeness_dict.get("production_ready", True))
    for f in (completeness_dict.get("findings") or []):
        if f not in findings:
            findings.append(f)
        if "ROOM_SHELL_INCOMPLETE" in f and "ROOM_SHELL_INCOMPLETE" not in blocking:
            blocking.append("ROOM_SHELL_INCOMPLETE")
    return 1.0 if ok else 0.0


# ──────────────────────────────────────────────────────────────────────────────
# Legacy helpers
# ──────────────────────────────────────────────────────────────────────────────

def _grade(score: float) -> str:
    if score >= 0.85: return "A"
    if score >= 0.70: return "B"
    if score >= 0.55: return "C"
    if score >= 0.40: return "D"
    return "F"


def _build_recommendations(r: StructuralReviewResult, dicts: List[Dict], extended: bool = False) -> List[str]:
    recs: List[str] = []
    if r.placement_validity < 0.8:
        recs.append(
            "Ensure all doorways, windows, and fireplaces reference a wall attachment "
            "target.  Run hou_mcp_structural_debug to visualise placement intents."
        )
    if r.pipeline_integrity < 0.8:
        recs.append(
            "Remove structural assets from furniture clusters and decoration lists. "
            "Route beams/columns to EnvironmentStructureBuilder before SemanticLayoutEngine."
        )
    if extended and r.routing_integrity < 0.9:
        recs.append(
            "Routing mismatches detected. Run hou_mcp_structural_routing_debug to see "
            "expected_builder vs actual_builder for each asset. Ensure StructuralRoutingEngine "
            "is called before SemanticLayoutEngine."
        )
    if extended and r.builder_integrity < 0.9:
        recs.append(
            "Structural assets found in GenericLayoutSolver pipeline. "
            "Insert StructuralRoutingEngine.route() before SemanticLayoutEngine.build_layout(). "
            "Use result.structural_assets for builders and result.furniture_assets for layout."
        )
    if extended and r.attachment_integrity < 0.9:
        recs.append(
            "Attachment violations detected. Check StructuralAttachmentEnforcer findings. "
            "Ensure doors reference a wall_id, beams are above 1.5m, columns touch floor."
        )
    if extended and r.room_shell_completeness < 1.0:
        recs.append(
            "Room shell is incomplete. Run hou_mcp_build_environment to generate floor, "
            "walls, ceiling, and doors before placing furniture assets."
        )
    if r.role_accuracy < 0.8:
        recs.append(
            "Add explicit 'placement_type' or richer 'tags' to assets with unknown roles. "
            "Use hou_mcp_structural_classifier to inspect per-asset classification signals."
        )
    if r.coverage < 0.9:
        recs.append(
            "All assets should be classified before layout generation. "
            "Add name/tag metadata to assets returning 'structural_unknown'."
        )
    if not recs:
        if extended:
            recs.append(
                "Structural routing and attachment validated. All structural assets correctly "
                "routed to dedicated builders. Room shell complete. Proceed to scene application."
            )
        else:
            recs.append(
                "Structural classification validated. Proceed to EnvironmentStructureBuilder "
                "and SemanticLayoutEngine."
            )
    return recs


def _build_summary(r: StructuralReviewResult, blocking: List[str]) -> str:
    if r.production_ready:
        return (
            f"Grade {r.grade} — overall {r.overall_score:.2f}. "
            f"{r.structural_count} structural / {r.asset_count} total assets. "
            "All structural assets correctly classified and routed."
        )
    if blocking:
        return (
            f"Grade {r.grade} — overall {r.overall_score:.2f}. "
            f"Blocking: {', '.join(blocking)}."
        )
    return (
        f"Grade {r.grade} — overall {r.overall_score:.2f}. "
        "Structural classification below production threshold."
    )


# ──────────────────────────────────────────────────────────────────────────────
# Singleton
# ──────────────────────────────────────────────────────────────────────────────

_INSTANCE: Optional[StructuralReview] = None
_LOCK = threading.Lock()


def get_structural_review() -> StructuralReview:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = StructuralReview()
        return _INSTANCE


def reset_structural_review_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
