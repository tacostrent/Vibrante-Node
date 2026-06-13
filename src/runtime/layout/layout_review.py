"""
layout_review.py — §46 Semantic Furniture Layout Engine
=======================================================
Reviews the semantic quality of a completed layout plan.

Metrics:
  relationship_accuracy  (0.30) — assets placed according to their affordances
  surface_accuracy       (0.25) — surface items actually on surfaces
  wall_attachment_accuracy(0.20) — wall items actually on walls
  cluster_quality        (0.15) — clusters have appropriate members
  contextual_quality     (0.10) — decorations match environment

Blocking failures (force production_ready = False):
  "bottle on floor when table exists"
  "poster not attached to wall"
  "no relationships defined"
  "no anchors placed"

Grade mapping: ≥0.85=A, ≥0.70=B, ≥0.55=C, ≥0.40=D, <0.40=F
production_ready requires overall_score ≥ 0.70 and no blocking findings.

Public API:
    LayoutReviewResult
    LayoutReview
    get_layout_review()
    reset_layout_review_for_tests()
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


_GRADE_THRESHOLDS = (
    (0.85, "A"),
    (0.70, "B"),
    (0.55, "C"),
    (0.40, "D"),
)

_BLOCKING_KEYWORDS = (
    "bottle on floor",
    "poster not attached",
    "no relationships",
    "no anchors placed",
)

_W_REL  = 0.30
_W_SURF = 0.25
_W_WALL = 0.20
_W_CLUS = 0.15
_W_CTX  = 0.10
assert abs(_W_REL + _W_SURF + _W_WALL + _W_CLUS + _W_CTX - 1.0) < 1e-9


@dataclass
class LayoutReviewResult:
    relationship_accuracy:    float
    surface_accuracy:         float
    wall_attachment_accuracy: float
    cluster_quality:          float
    contextual_quality:       float
    overall_score:            float
    grade:                    str
    production_ready:         bool
    findings: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "relationship_accuracy":    round(self.relationship_accuracy, 4),
            "surface_accuracy":         round(self.surface_accuracy, 4),
            "wall_attachment_accuracy": round(self.wall_attachment_accuracy, 4),
            "cluster_quality":          round(self.cluster_quality, 4),
            "contextual_quality":       round(self.contextual_quality, 4),
            "overall_score":            round(self.overall_score, 4),
            "grade":                    self.grade,
            "production_ready":         self.production_ready,
            "findings":                 list(self.findings),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "LayoutReviewResult":
        return cls(
            relationship_accuracy=float(d.get("relationship_accuracy", 0.0)),
            surface_accuracy=float(d.get("surface_accuracy", 0.0)),
            wall_attachment_accuracy=float(d.get("wall_attachment_accuracy", 0.0)),
            cluster_quality=float(d.get("cluster_quality", 0.0)),
            contextual_quality=float(d.get("contextual_quality", 0.0)),
            overall_score=float(d.get("overall_score", 0.0)),
            grade=d.get("grade", "F"),
            production_ready=bool(d.get("production_ready", False)),
            findings=list(d.get("findings", [])),
        )


class LayoutReview:
    """Evaluates semantic layout quality. Never raises."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def review(self, layout_plan: Dict[str, Any]) -> LayoutReviewResult:
        """
        Review a layout plan dict from SemanticLayoutEngine.

        Expected keys:
            anchor_placements, clusters, wall_attachments, surface_placements,
            relationships, decoration_items, environment
        """
        try:
            return self._review(layout_plan)
        except Exception as exc:
            return LayoutReviewResult(
                relationship_accuracy=0.0,
                surface_accuracy=0.0,
                wall_attachment_accuracy=0.0,
                cluster_quality=0.0,
                contextual_quality=0.0,
                overall_score=0.0,
                grade="F",
                production_ready=False,
                findings=[f"review error: {exc}"],
            )

    def _review(self, plan: Dict[str, Any]) -> LayoutReviewResult:
        findings: List[str] = []

        anchors      = plan.get("anchor_placements", [])
        clusters     = plan.get("clusters", [])
        wall_attach  = plan.get("wall_attachments", [])
        surf_place   = plan.get("surface_placements", [])
        relationships = plan.get("relationships", [])
        decorations  = plan.get("decoration_items", [])

        # ---- Relationship accuracy ----
        if not anchors:
            findings.append("no anchors placed — layout has no focal points")
            rel_score = 0.0
        elif not relationships and not clusters:
            findings.append("no relationships defined — assets placed independently")
            rel_score = 0.30
        else:
            rel_score = min(1.0, 0.50 + len(relationships) * 0.05)

        # Bottle-on-floor check
        anchor_types = {a.get("anchor_type", "") for a in anchors}
        has_table = any(t in ("table", "workbench", "desk", "bar_counter") for t in anchor_types)
        on_surface_ids = {s.get("child_asset_id", "") for s in surf_place}
        on_wall_types  = {a.get("asset_type", "") for a in wall_attach}

        for deco in decorations:
            name_lower = (deco.get("asset_name") or deco.get("asset_type") or "").lower()
            d_type = deco.get("asset_type", "")
            d_id   = deco.get("asset_id", "")
            if any(kw in name_lower for kw in ("bottle", "cup", "glass", "mug")):
                if has_table and d_id not in on_surface_ids:
                    if deco.get("placement_target", "") not in ("on_surface", "wall_mounted", "wall_only"):
                        findings.append(
                            f"bottle on floor when table exists: "
                            f"'{deco.get('asset_name') or d_type}' not on any surface"
                        )
                        rel_score = max(0.0, rel_score - 0.30)

        # Poster-not-on-wall check
        poster_on_floor = []
        for deco in decorations:
            d_type = deco.get("asset_type", "")
            if d_type in ("poster", "painting", "wanted_poster", "banner", "sign"):
                if deco.get("placement_target", "") not in ("wall_only", "wall_mounted", "attached_to"):
                    poster_on_floor.append(deco.get("asset_name") or d_type)
        if poster_on_floor:
            findings.append(
                f"poster not attached to wall: "
                f"{len(poster_on_floor)} asset(s) not wall-mounted"
            )

        # ---- Surface accuracy ----
        if len(surf_place) > 0:
            surf_score = min(1.0, 0.60 + len(surf_place) * 0.05)
        elif has_table:
            surf_score = 0.40   # table exists but nothing on it
        else:
            surf_score = 0.75   # no table → not applicable

        # ---- Wall attachment accuracy ----
        if len(wall_attach) > 0:
            wall_score = min(1.0, 0.65 + len(wall_attach) * 0.05)
        elif poster_on_floor:
            wall_score = 0.20
        else:
            wall_score = 0.60

        # ---- Cluster quality ----
        if not clusters:
            cluster_score = 0.50
        else:
            membered = [c for c in clusters if len(c.get("members", [])) > 0]
            cluster_score = min(1.0, 0.50 + len(membered) / max(1, len(clusters)) * 0.50)

        # ---- Contextual quality ----
        if not decorations:
            ctx_score = 0.50
        else:
            ctx_count = sum(1 for d in decorations if d.get("contextual", False))
            ctx_score = min(1.0, 0.40 + ctx_count / max(1, len(decorations)) * 0.60)

        # ---- Overall ----
        overall = (
            _W_REL  * rel_score
            + _W_SURF * surf_score
            + _W_WALL * wall_score
            + _W_CLUS * cluster_score
            + _W_CTX  * ctx_score
        )
        overall = max(0.0, min(1.0, overall))

        # ---- Grade ----
        grade = "F"
        for threshold, letter in _GRADE_THRESHOLDS:
            if overall >= threshold:
                grade = letter
                break

        # ---- Blocking check ----
        has_blocking = any(
            any(kw in f for kw in _BLOCKING_KEYWORDS) for f in findings
        )
        production_ready = overall >= 0.70 and not has_blocking

        return LayoutReviewResult(
            relationship_accuracy=rel_score,
            surface_accuracy=surf_score,
            wall_attachment_accuracy=wall_score,
            cluster_quality=cluster_score,
            contextual_quality=ctx_score,
            overall_score=overall,
            grade=grade,
            production_ready=production_ready,
            findings=findings,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[LayoutReview] = None
_lock = threading.Lock()


def get_layout_review() -> LayoutReview:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = LayoutReview()
    return _instance


def reset_layout_review_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
