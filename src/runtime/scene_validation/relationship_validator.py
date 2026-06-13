"""
relationship_validator.py — §53 Scene Reality Validation (Tier 14.3)
=====================================================================
Rule 3 — Functional Relationship Validation.

Checks that every asset holds its expected semantic relationship to a valid
parent. Relationships are declared per asset-name keyword in _EXPECTED_RELS.

Expected relationships checked:
    chair/stool  → around  a table/bar_counter/fireplace/campfire
    bottle/cup/glass/mug/teapot/plate → supports  (on a table/shelf/counter)
    poster/painting/banner/wanted_poster → attached_to  wall
    beam         → attached_to  ceiling
    door/doorway → attached_to  wall

Violation code : RELATIONSHIP_FAILURE
Severity       : WARNING  (relationships can be inferred; not always BLOCKING)

Public API:
    RelationshipFailure
    RelationshipValidator
    get_relationship_validator()
    reset_relationship_validator_for_tests()
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

# Each rule: asset keyword → (expected relationship tag, valid parent keywords)
_EXPECTED_RELS: List[Dict[str, Any]] = [
    {
        "kw": "chair",
        "rel": "around",
        "parent_kws": ["table", "bar_counter", "bar counter", "fireplace", "campfire",
                       "workbench", "desk", "counter", "throne"],
    },
    {
        "kw": "stool",
        "rel": "around",
        "parent_kws": ["table", "bar_counter", "bar counter", "campfire"],
    },
    {
        "kw": "bottle",
        "rel": "supports",
        "parent_kws": ["table", "bar_counter", "bar counter", "shelf", "workbench", "counter"],
    },
    {
        "kw": "teapot",
        "rel": "supports",
        "parent_kws": ["table", "counter", "workbench", "desk"],
    },
    {
        "kw": "cup",
        "rel": "supports",
        "parent_kws": ["table", "bar_counter", "bar counter", "shelf", "counter"],
    },
    {
        "kw": "glass",
        "rel": "supports",
        "parent_kws": ["table", "bar_counter", "bar counter", "counter"],
    },
    {
        "kw": "mug",
        "rel": "supports",
        "parent_kws": ["table", "bar_counter", "bar counter", "counter", "desk"],
    },
    {
        "kw": "plate",
        "rel": "supports",
        "parent_kws": ["table", "counter", "workbench"],
    },
    {
        "kw": "book",
        "rel": "supports",
        "parent_kws": ["table", "desk", "shelf"],
    },
    {
        "kw": "poster",
        "rel": "attached_to",
        "parent_kws": ["wall"],
    },
    {
        "kw": "painting",
        "rel": "attached_to",
        "parent_kws": ["wall"],
    },
    {
        "kw": "wanted_poster",
        "rel": "attached_to",
        "parent_kws": ["wall"],
    },
    {
        "kw": "banner",
        "rel": "attached_to",
        "parent_kws": ["wall"],
    },
    {
        "kw": "beam",
        "rel": "attached_to",
        "parent_kws": ["ceiling", "roof"],
    },
    {
        "kw": "door",
        "rel": "attached_to",
        "parent_kws": ["wall"],
    },
]


def _match_kw(name: str, kw: str) -> bool:
    return kw in name.lower()


def _parent_name_for(transforms: List[Dict[str, Any]], parent_id: str) -> str:
    """Look up the asset_name of a given parent_id in transforms."""
    for t in transforms:
        if t.get("asset_id") == parent_id:
            return t.get("asset_name", "").lower()
    return ""


@dataclass
class RelationshipFailure:
    asset_id:       str
    asset_name:     str
    expected_rel:   str
    actual_rel:     str
    parent_id:      str
    violation_code: str = "RELATIONSHIP_FAILURE"
    severity:       str = "WARNING"
    detail:         str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id":       self.asset_id,
            "asset_name":     self.asset_name,
            "expected_rel":   self.expected_rel,
            "actual_rel":     self.actual_rel,
            "parent_id":      self.parent_id,
            "violation_code": self.violation_code,
            "severity":       self.severity,
            "detail":         self.detail,
        }


class RelationshipValidator:
    """Checks that each asset holds its expected semantic relationship."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def validate(self, scene_layout: Dict[str, Any]) -> List[RelationshipFailure]:
        """Return all RELATIONSHIP_FAILURE records. Never raises."""
        try:
            return self._validate(scene_layout)
        except Exception:
            return []

    def _validate(self, scene: Dict[str, Any]) -> List[RelationshipFailure]:
        transforms = scene.get("transforms") or []
        failures: List[RelationshipFailure] = []

        for t in transforms:
            name = t.get("asset_name", "")
            rel  = t.get("relationship", "")
            pid  = t.get("parent_id", "")
            aid  = t.get("asset_id", "")

            for rule in _EXPECTED_RELS:
                if not _match_kw(name, rule["kw"]):
                    continue

                expected_rel = rule["rel"]
                parent_kws   = rule["parent_kws"]

                # Relationship tag check (allow near/around interchangeably)
                rel_ok = rel == expected_rel or (
                    rel in ("near", "around", "near_anchor")
                    and expected_rel in ("around", "near")
                )

                # Parent keyword match — check the resolved parent name AND the parent_id
                # directly (wall assets like "wall_north" are not in transforms list)
                parent_name = _parent_name_for(transforms, pid) if pid else ""
                parent_ok   = bool(pid) and (
                    any(kw in parent_name for kw in parent_kws)
                    or any(kw in pid.lower() for kw in parent_kws)
                )

                if not rel_ok or not parent_ok:
                    parts: List[str] = []
                    if not rel_ok:
                        parts.append(
                            f"expected relationship='{expected_rel}' got='{rel}'"
                        )
                    if not parent_ok:
                        exp = "/".join(parent_kws[:3])
                        parts.append(
                            f"expected parent in [{exp}], "
                            f"got parent='{parent_name or pid or 'none'}'"
                        )
                    failures.append(RelationshipFailure(
                        asset_id=aid,
                        asset_name=name,
                        expected_rel=expected_rel,
                        actual_rel=rel,
                        parent_id=pid,
                        detail="; ".join(parts),
                    ))
                break  # first matching rule wins per asset

        return failures


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[RelationshipValidator] = None
_lock = threading.Lock()


def get_relationship_validator() -> RelationshipValidator:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = RelationshipValidator()
    return _instance


def reset_relationship_validator_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
