"""
Production Memory (Tier 5 — Production Knowledge System)
=========================================================
Stores historical production experience: successful scenes, failed scenes,
pattern usage, and review outcomes. Provides the foundation for knowledge-
driven orchestration decisions.

DESIGN RULE: NO bridge calls. Append-only persistence via backend abstraction.
             Deterministic. Thread-safe.

What IS stored:
  - scene type, lighting/camera/atmosphere style, score, status
  - review findings and strength categories (no raw critique text)
  - pattern usage outcomes (pattern id, scene type, success/failure)
  - failure categories with structured cause descriptors

What is NOT stored:
  - raw user text, artist names, private file paths
  - full review prose or LLM output
  - asset file paths or identifiers

Public API:
    ProductionMemory
        .record_scene(data) -> str              scene_id
        .record_review(scene_id, review) -> str record_id
        .record_pattern_usage(pattern_id, scene_type, outcome) -> str
        .record_failure(data) -> str            failure_id
        .get_scene_history(scene_type=None, status=None, limit=50) -> list
        .get_successful_patterns(scene_type=None, limit=20) -> list
        .get_failure_patterns(scene_type=None, limit=20) -> list
        .get_statistics() -> dict
        .stats() -> dict

    get_production_memory() -> ProductionMemory   (singleton)
    reset_production_memory_for_tests()
"""

from __future__ import annotations

import os
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

from src.runtime.storage.memory_backend import (
    InMemoryBackend,
    JSONLBackend,
    ProductionMemoryBackend,
)
from src.runtime.storage.sqlite_backend import SQLiteBackend

# Extensions that trigger the SQLite backend instead of JSONL.
_SQLITE_EXTENSIONS = (".db", ".sqlite", ".sqlite3")

def _make_backend(path: str) -> ProductionMemoryBackend:
    """Return the appropriate backend for *path* based on its file extension.

    Paths ending in ``.db``, ``.sqlite``, or ``.sqlite3`` use ``SQLiteBackend``.
    All other paths (including ``.jsonl``) use ``JSONLBackend``.
    """
    if path.lower().endswith(_SQLITE_EXTENSIONS):
        return SQLiteBackend(path)
    return JSONLBackend(path)


_VALID_RECORD_TYPES = frozenset({
    "scene", "review", "pattern_usage", "failure"
})
_VALID_OUTCOMES = frozenset({"success", "partial", "failure", "unknown"})
_MAX_RECORDS = 5000


class ProductionMemory:
    """Append-only production experience store."""

    def __init__(
        self,
        path: Optional[str] = None,
        backend: Optional[ProductionMemoryBackend] = None,
    ) -> None:
        if backend is not None:
            self._backend: ProductionMemoryBackend = backend
        else:
            if path is None:
                path = os.environ.get("VIBRANTE_PRODUCTION_MEMORY_PATH")
            self._backend = _make_backend(path) if path else InMemoryBackend()

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record_scene(self, data: Dict[str, Any]) -> str:
        """Record a completed scene.

        data should include:
            scene_type (str)            — e.g. "industrial_hangar"
            lighting_style (str)        — e.g. "cold_scifi"
            camera_style (str)          — e.g. "hero_focus"
            atmosphere_type (str)       — e.g. "industrial_fog"
            score (float)               — 0.0–1.0 overall quality score
            status (str)                — "success"|"partial"|"failure"|"unknown"
        Optional:
            template_id (str), asset_count (int), op_count (int)
        Returns the scene_id.
        """
        scene_id = f"scene_{uuid.uuid4().hex[:12]}"
        record = {
            "record_type":    "scene",
            "scene_id":       scene_id,
            "scene_type":     str(data.get("scene_type", "unknown")),
            "lighting_style": str(data.get("lighting_style", "")),
            "camera_style":   str(data.get("camera_style", "")),
            "atmosphere_type": str(data.get("atmosphere_type", "")),
            "score":          float(data.get("score", 0.0)),
            "status":         str(data.get("status", "unknown")),
            "template_id":    str(data.get("template_id", "")),
            "asset_count":    int(data.get("asset_count", 0)),
            "op_count":       int(data.get("op_count", 0)),
            "timestamp":      time.time(),
        }
        if record["status"] not in _VALID_OUTCOMES:
            record["status"] = "unknown"
        self._backend.insert("scene", record)
        return scene_id

    def record_review(self, scene_id: str, review: Dict[str, Any]) -> str:
        """Record a review result tied to a scene.

        review should contain at least:
            overall_score (float), grade (str), production_ready (bool)
        Optional:
            findings (list[str]), recommendations (list[str])
        Returns record_id.
        """
        record_id = f"rev_{uuid.uuid4().hex[:12]}"
        record = {
            "record_type":      "review",
            "record_id":        record_id,
            "scene_id":         str(scene_id),
            "overall_score":    float(review.get("overall_score", 0.0)),
            "grade":            str(review.get("grade", "F")),
            "production_ready": bool(review.get("production_ready", False)),
            "finding_count":    len(review.get("findings", [])),
            "recommendation_count": len(review.get("recommendations", [])),
            "timestamp":        time.time(),
        }
        self._backend.insert("review", record)
        return record_id

    def record_pattern_usage(
        self, pattern_id: str, scene_type: str, outcome: str
    ) -> str:
        """Record that a pattern was used for a scene.

        outcome must be one of: success, partial, failure, unknown
        Returns record_id.
        """
        if outcome not in _VALID_OUTCOMES:
            outcome = "unknown"
        record_id = f"pu_{uuid.uuid4().hex[:12]}"
        record = {
            "record_type": "pattern_usage",
            "record_id":   record_id,
            "pattern_id":  str(pattern_id),
            "scene_type":  str(scene_type),
            "outcome":     outcome,
            "timestamp":   time.time(),
        }
        self._backend.insert("pattern_usage", record)
        return record_id

    def record_failure(self, data: Dict[str, Any]) -> str:
        """Record a production failure.

        data should include:
            scene_type (str), failure_type (str), description (str)
        Optional:
            pattern_id (str), lighting_style (str), camera_style (str)
        Returns failure_id.
        """
        failure_id = f"fail_{uuid.uuid4().hex[:12]}"
        record = {
            "record_type":  "failure",
            "failure_id":   failure_id,
            "scene_type":   str(data.get("scene_type", "unknown")),
            "failure_type": str(data.get("failure_type", "unknown")),
            "description":  str(data.get("description", "")),
            "pattern_id":   str(data.get("pattern_id", "")),
            "lighting_style": str(data.get("lighting_style", "")),
            "camera_style": str(data.get("camera_style", "")),
            "timestamp":    time.time(),
        }
        self._backend.insert("failure", record)
        return failure_id

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    def get_scene_history(
        self,
        scene_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Return scene records, newest first.

        Filter by scene_type and/or status if provided.
        """
        filters: Dict[str, Any] = {}
        if scene_type is not None:
            filters["scene_type"] = scene_type
        if status is not None:
            filters["status"] = status
        return self._backend.query("scene", filters, order_desc=True, limit=limit)

    def get_successful_patterns(
        self,
        scene_type: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Return pattern_usage records with outcome='success', newest first."""
        filters: Dict[str, Any] = {"outcome": "success"}
        if scene_type is not None:
            filters["scene_type"] = scene_type
        return self._backend.query("pattern_usage", filters, order_desc=True, limit=limit)

    def get_failure_patterns(
        self,
        scene_type: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Return failure records, newest first."""
        filters: Dict[str, Any] = {}
        if scene_type is not None:
            filters["scene_type"] = scene_type
        return self._backend.query("failure", filters, order_desc=True, limit=limit)

    def get_statistics(self) -> Dict[str, Any]:
        """Return aggregate statistics across all records."""
        scenes   = self._backend.all_records("scene")
        reviews  = self._backend.all_records("review")
        usages   = self._backend.all_records("pattern_usage")
        failures = self._backend.all_records("failure")

        total_scenes = len(scenes)
        successful_scenes = sum(1 for s in scenes if s.get("status") == "success")
        avg_score = (
            sum(s.get("score", 0.0) for s in scenes) / total_scenes
            if total_scenes else 0.0
        )

        # Count by scene_type
        by_type: Dict[str, int] = {}
        for s in scenes:
            st = s.get("scene_type", "unknown")
            by_type[st] = by_type.get(st, 0) + 1

        # Pattern success rate
        pattern_successes = sum(1 for u in usages if u.get("outcome") == "success")
        pattern_success_rate = (
            pattern_successes / len(usages) if usages else 0.0
        )

        return {
            "total_scenes":         total_scenes,
            "successful_scenes":    successful_scenes,
            "success_rate":         successful_scenes / total_scenes if total_scenes else 0.0,
            "avg_score":            round(avg_score, 4),
            "total_reviews":        len(reviews),
            "total_pattern_usages": len(usages),
            "pattern_success_rate": round(pattern_success_rate, 4),
            "total_failures":       len(failures),
            "scenes_by_type":       by_type,
            "total_records":        self._backend.record_count(),
        }

    def stats(self) -> Dict[str, Any]:
        """Lightweight stats."""
        return {
            "record_count": self._backend.record_count(),
            "write_count":  self._backend.write_count(),
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[ProductionMemory] = None
_INSTANCE_LOCK = threading.Lock()


def get_production_memory() -> ProductionMemory:
    """Return the module-level singleton ProductionMemory."""
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = ProductionMemory()
    return _INSTANCE


def reset_production_memory_for_tests() -> None:
    """Replace the singleton. For test isolation only."""
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
