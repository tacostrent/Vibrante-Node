"""
asset_suitability_engine.py — §45 Semantic Asset Suitability Ranking
=====================================================================
Orchestrates all affinity scorers to produce a single suitability score
per candidate asset. Ranking by suitability replaces pure semantic similarity.

Public API:
    get_asset_suitability_engine() -> AssetSuitabilityEngine
    reset_asset_suitability_engine_for_tests()

    AssetSuitabilityEngine.score_asset(asset, request, similarity_score) -> AssetSuitabilityScore
    AssetSuitabilityEngine.rank_assets(candidates, request, similarity_scores) -> SuitabilityResult
    AssetSuitabilityEngine.select_best(candidates, request, similarity_scores) -> AssetSuitabilityScore | None
"""

import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from src.runtime.assets.suitability.environment_affinity import get_environment_affinity
from src.runtime.assets.suitability.role_affinity import get_role_affinity
from src.runtime.assets.suitability.style_affinity import get_style_affinity
from src.runtime.assets.suitability.material_affinity import get_material_affinity
from src.runtime.assets.suitability.scale_affinity import get_scale_affinity
from src.runtime.assets.suitability.placement_affinity import get_placement_affinity
from src.runtime.assets.suitability.story_affinity import get_story_affinity

# ---------------------------------------------------------------------------
# Weights — must sum to 1.0
# ---------------------------------------------------------------------------
WEIGHTS: Dict[str, float] = {
    "environment": 0.25,
    "role":        0.20,
    "style":       0.15,
    "material":    0.10,
    "scale":       0.10,
    "placement":   0.10,
    "story":       0.10,
}

assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9, "Suitability weights must sum to 1.0"

_REJECTION_THRESHOLD = 0.30   # final_score below this is "rejected"
_SELECTION_THRESHOLD = 0.50   # best candidate should be above this


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class SuitabilityRequest:
    environment: str
    role: str = ""
    placement_context: str = ""
    expected_scale: str = ""

    def to_dict(self) -> dict:
        return {
            "environment": self.environment,
            "role": self.role,
            "placement_context": self.placement_context,
            "expected_scale": self.expected_scale,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SuitabilityRequest":
        return cls(
            environment=d.get("environment", ""),
            role=d.get("role", ""),
            placement_context=d.get("placement_context", ""),
            expected_scale=d.get("expected_scale", ""),
        )


@dataclass
class AssetSuitabilityScore:
    asset_id: str
    asset_name: str
    similarity_score: float      # from upstream vector layer (reference only)
    environment_score: float
    role_score: float
    style_score: float
    material_score: float
    scale_score: float
    placement_score: float
    story_score: float
    final_score: float

    def to_dict(self) -> dict:
        return {
            "asset_id": self.asset_id,
            "asset_name": self.asset_name,
            "similarity_score": round(self.similarity_score, 4),
            "environment_score": round(self.environment_score, 4),
            "role_score": round(self.role_score, 4),
            "style_score": round(self.style_score, 4),
            "material_score": round(self.material_score, 4),
            "scale_score": round(self.scale_score, 4),
            "placement_score": round(self.placement_score, 4),
            "story_score": round(self.story_score, 4),
            "final_score": round(self.final_score, 4),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AssetSuitabilityScore":
        return cls(
            asset_id=d.get("asset_id", ""),
            asset_name=d.get("asset_name", ""),
            similarity_score=float(d.get("similarity_score", 0.5)),
            environment_score=float(d.get("environment_score", 0.5)),
            role_score=float(d.get("role_score", 0.5)),
            style_score=float(d.get("style_score", 0.5)),
            material_score=float(d.get("material_score", 0.5)),
            scale_score=float(d.get("scale_score", 0.5)),
            placement_score=float(d.get("placement_score", 0.5)),
            story_score=float(d.get("story_score", 0.5)),
            final_score=float(d.get("final_score", 0.5)),
        )


@dataclass
class SuitabilityResult:
    request: SuitabilityRequest
    scores: List[AssetSuitabilityScore] = field(default_factory=list)
    best: Optional[AssetSuitabilityScore] = None
    total_candidates: int = 0
    rejected_count: int = 0         # final_score < _REJECTION_THRESHOLD

    @property
    def selection_report(self) -> dict:
        return {
            "role": self.request.role,
            "environment": self.request.environment,
            "selected_asset": self.best.asset_name if self.best else None,
            "score": round(self.best.final_score, 4) if self.best else None,
            "candidates": [
                {"name": s.asset_name, "score": round(s.final_score, 4)}
                for s in self.scores
            ],
        }

    def to_dict(self) -> dict:
        return {
            "request": self.request.to_dict(),
            "scores": [s.to_dict() for s in self.scores],
            "best": self.best.to_dict() if self.best else None,
            "total_candidates": self.total_candidates,
            "rejected_count": self.rejected_count,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SuitabilityResult":
        req = SuitabilityRequest.from_dict(d.get("request", {}))
        scores = [AssetSuitabilityScore.from_dict(s) for s in d.get("scores", [])]
        best_d = d.get("best")
        best = AssetSuitabilityScore.from_dict(best_d) if best_d else None
        return cls(
            request=req,
            scores=scores,
            best=best,
            total_candidates=d.get("total_candidates", len(scores)),
            rejected_count=d.get("rejected_count", 0),
        )


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class AssetSuitabilityEngine:
    """Orchestrates affinity scorers to rank assets by suitability."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Core scoring
    # ------------------------------------------------------------------

    def score_asset(
        self,
        asset: dict,
        request: SuitabilityRequest,
        similarity_score: float = 0.5,
    ) -> AssetSuitabilityScore:
        """Score a single asset against a suitability request."""
        try:
            env = request.environment
            role = request.role
            pctx = request.placement_context
            exp_scale = request.expected_scale

            env_score = get_environment_affinity().score(asset, env)
            role_score = get_role_affinity().score(asset, role) if role else 0.5
            style_score = get_style_affinity().score(asset, env)
            mat_score = get_material_affinity().score(asset, env)
            scale_score = get_scale_affinity().score(asset, role, exp_scale)
            place_score = get_placement_affinity().score(asset, pctx) if pctx else 0.5
            story_score = get_story_affinity().score(asset, env)

            final = (
                WEIGHTS["environment"] * env_score
                + WEIGHTS["role"]        * role_score
                + WEIGHTS["style"]       * style_score
                + WEIGHTS["material"]    * mat_score
                + WEIGHTS["scale"]       * scale_score
                + WEIGHTS["placement"]   * place_score
                + WEIGHTS["story"]       * story_score
            )
            final = max(0.0, min(1.0, final))

            return AssetSuitabilityScore(
                asset_id=str(asset.get("asset_id") or asset.get("name") or ""),
                asset_name=str(asset.get("name") or asset.get("asset_id") or ""),
                similarity_score=float(similarity_score),
                environment_score=env_score,
                role_score=role_score,
                style_score=style_score,
                material_score=mat_score,
                scale_score=scale_score,
                placement_score=place_score,
                story_score=story_score,
                final_score=final,
            )
        except Exception:
            return AssetSuitabilityScore(
                asset_id=str(asset.get("asset_id") or ""),
                asset_name=str(asset.get("name") or ""),
                similarity_score=float(similarity_score),
                environment_score=0.5,
                role_score=0.5,
                style_score=0.5,
                material_score=0.5,
                scale_score=0.5,
                placement_score=0.5,
                story_score=0.5,
                final_score=0.5,
            )

    # ------------------------------------------------------------------
    # Ranking
    # ------------------------------------------------------------------

    def rank_assets(
        self,
        candidates: List[dict],
        request: SuitabilityRequest,
        similarity_scores: Optional[Dict[str, float]] = None,
    ) -> SuitabilityResult:
        """Score and rank all candidates; return sorted SuitabilityResult."""
        try:
            sim = similarity_scores or {}
            scores: List[AssetSuitabilityScore] = []
            for asset in candidates:
                asset_id = str(asset.get("asset_id") or asset.get("name") or "")
                sim_score = sim.get(asset_id, sim.get(asset.get("name", ""), 0.5))
                s = self.score_asset(asset, request, similarity_score=sim_score)
                scores.append(s)

            scores.sort(key=lambda s: s.final_score, reverse=True)
            best = scores[0] if scores else None
            rejected = sum(1 for s in scores if s.final_score < _REJECTION_THRESHOLD)

            return SuitabilityResult(
                request=request,
                scores=scores,
                best=best,
                total_candidates=len(scores),
                rejected_count=rejected,
            )
        except Exception:
            return SuitabilityResult(
                request=request,
                scores=[],
                best=None,
                total_candidates=0,
                rejected_count=0,
            )

    def select_best(
        self,
        candidates: List[dict],
        request: SuitabilityRequest,
        similarity_scores: Optional[Dict[str, float]] = None,
    ) -> Optional[AssetSuitabilityScore]:
        """Return the single best-suited candidate, or None if list is empty."""
        result = self.rank_assets(candidates, request, similarity_scores)
        return result.best

    def validate_selection(
        self,
        selected_asset: dict,
        request: SuitabilityRequest,
    ) -> dict:
        """Validate that a selected asset actually matches the requested slot.

        Returns:
            {"valid": bool, "score": float, "findings": list[str]}
        """
        try:
            s = self.score_asset(selected_asset, request)
            findings = []
            if s.role_score < 0.4 and request.role:
                findings.append(
                    f"role mismatch: asset does not match requested role '{request.role}'"
                )
            if s.environment_score < 0.3 and request.environment:
                findings.append(
                    f"environment mismatch: asset unsuitable for '{request.environment}'"
                )
            if s.final_score < _REJECTION_THRESHOLD:
                findings.append(
                    f"below rejection threshold: score {s.final_score:.2f} < {_REJECTION_THRESHOLD}"
                )
            return {
                "valid": len(findings) == 0,
                "score": s.final_score,
                "findings": findings,
            }
        except Exception:
            return {"valid": False, "score": 0.0, "findings": ["validation error"]}


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: AssetSuitabilityEngine | None = None
_instance_lock = threading.Lock()


def get_asset_suitability_engine() -> AssetSuitabilityEngine:
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = AssetSuitabilityEngine()
    return _instance


def reset_asset_suitability_engine_for_tests() -> None:
    global _instance
    with _instance_lock:
        _instance = None
