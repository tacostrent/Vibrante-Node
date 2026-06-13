"""
Semantic Similarity (Tier 12.8)
=================================
Pure-Python + optional NumPy cosine similarity utilities.
No external ML dependencies required.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

try:
    import numpy as _np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Cosine similarity between two vectors. Returns 0.0 for zero vectors."""
    try:
        if not a or not b or len(a) != len(b):
            return 0.0
        if _HAS_NUMPY:
            va = _np.array(a, dtype=float)
            vb = _np.array(b, dtype=float)
            norm_a = float(_np.linalg.norm(va))
            norm_b = float(_np.linalg.norm(vb))
            if norm_a == 0.0 or norm_b == 0.0:
                return 0.0
            return float(_np.dot(va, vb) / (norm_a * norm_b))
        else:
            dot = sum(x * y for x, y in zip(a, b))
            norm_a = sum(x * x for x in a) ** 0.5
            norm_b = sum(x * x for x in b) ** 0.5
            if norm_a == 0.0 or norm_b == 0.0:
                return 0.0
            return dot / (norm_a * norm_b)
    except Exception:
        return 0.0


def rank_similarity(
    query_vector: List[float],
    candidates: List[Tuple[str, List[float]]],
) -> List[Tuple[str, float]]:
    """Rank candidate (id, vector) pairs by cosine similarity to query. Sorted descending."""
    try:
        scored = [(cid, cosine_similarity(query_vector, vec)) for cid, vec in candidates]
        return sorted(scored, key=lambda x: x[1], reverse=True)
    except Exception:
        return []


def score_match(query_dict: Dict[str, Any], candidate_dict: Dict[str, Any]) -> float:
    """Structural semantic match based on shared list fields.

    Computes Jaccard-like overlap across environments, roles, lookdev, storytelling,
    and cinematic_usage. Returns a [0, 1] score.
    """
    try:
        _MATCH_FIELDS = (
            ("environments",    0.30),
            ("roles",           0.25),
            ("lookdev",         0.20),
            ("cinematic_usage", 0.15),
            ("storytelling",    0.10),
        )
        total_weight = 0.0
        total_score  = 0.0
        for field, weight in _MATCH_FIELDS:
            q_vals = set(str(v) for v in (query_dict.get(field) or []))
            c_vals = set(str(v) for v in (candidate_dict.get(field) or []))
            # Handle scalar storytelling field
            if not q_vals and isinstance(query_dict.get(field), str) and query_dict[field]:
                q_vals = {str(query_dict[field])}
            if not c_vals and isinstance(candidate_dict.get(field), str) and candidate_dict[field]:
                c_vals = {str(candidate_dict[field])}
            if q_vals:
                overlap = len(q_vals & c_vals) / max(len(q_vals | c_vals), 1)
                total_score  += overlap * weight
                total_weight += weight
        return round(total_score / max(total_weight, 1e-9), 4)
    except Exception:
        return 0.0


def normalize_scores(scores: List[float]) -> List[float]:
    """Min-max normalize a list of scores to [0, 1]. Returns zeros if all equal."""
    try:
        if not scores:
            return []
        min_s = min(scores)
        max_s = max(scores)
        if max_s == min_s:
            return [0.0] * len(scores)
        return [round((s - min_s) / (max_s - min_s), 6) for s in scores]
    except Exception:
        return [0.0] * len(scores)


def l2_normalize(vec: List[float]) -> List[float]:
    """L2-normalize a vector in place. Returns original if norm is 0."""
    try:
        if _HAS_NUMPY:
            v = _np.array(vec, dtype=float)
            norm = float(_np.linalg.norm(v))
            if norm == 0.0:
                return list(vec)
            return list(v / norm)
        else:
            norm = sum(x * x for x in vec) ** 0.5
            if norm == 0.0:
                return list(vec)
            return [x / norm for x in vec]
    except Exception:
        return list(vec)
