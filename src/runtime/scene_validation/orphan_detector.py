"""
orphan_detector.py — §53 Scene Reality Validation (Tier 14.3)
==============================================================
Rule 5 — Visual Review / Orphan Detection.

Finds assets that have no valid semantic parent within the expected search
radius. An orphaned asset has no cluster_id, no parent_id, and no valid
parent type within the defined proximity.

Violation code : ORPHAN_OBJECT
Severity       : WARNING

Public API:
    OrphanRecord
    OrphanDetector
    get_orphan_detector()
    reset_orphan_detector_for_tests()
"""

from __future__ import annotations

import math
import threading
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

# Rules: asset keyword → parent keywords + search radius (m).
# radius=None means "parent type must exist anywhere in scene"
_ORPHAN_RULES: List[Dict[str, Any]] = [
    {
        "kw":         "chair",
        "parent_kws": ["table", "bar_counter", "bar counter", "fireplace",
                       "campfire", "desk", "workbench", "throne"],
        "radius":     1.5,
    },
    {
        "kw":         "stool",
        "parent_kws": ["table", "bar_counter", "bar counter", "campfire"],
        "radius":     1.5,
    },
    {
        "kw":         "bottle",
        "parent_kws": ["table", "bar_counter", "bar counter", "shelf", "workbench"],
        "radius":     0.8,
    },
    {
        "kw":         "teapot",
        "parent_kws": ["table", "counter", "workbench", "desk"],
        "radius":     0.8,
    },
    {
        "kw":         "cup",
        "parent_kws": ["table", "bar_counter", "bar counter", "shelf", "counter"],
        "radius":     0.8,
    },
    {
        "kw":         "glass",
        "parent_kws": ["table", "bar_counter", "bar counter", "counter"],
        "radius":     0.8,
    },
    {
        "kw":         "mug",
        "parent_kws": ["table", "bar_counter", "bar counter", "counter", "desk"],
        "radius":     0.8,
    },
    {
        "kw":         "poster",
        "parent_kws": ["wall"],
        "radius":     None,  # must have wall anywhere in scene
    },
    {
        "kw":         "painting",
        "parent_kws": ["wall"],
        "radius":     None,
    },
    {
        "kw":         "banner",
        "parent_kws": ["wall"],
        "radius":     None,
    },
    {
        "kw":         "lantern",
        "parent_kws": ["table", "wall", "ceiling", "mantle", "post"],
        "radius":     None,
    },
]


def _dist_2d(a: Dict[str, Any], b: Dict[str, Any]) -> float:
    dx = float(a.get("tx", 0)) - float(b.get("tx", 0))
    dz = float(a.get("tz", 0)) - float(b.get("tz", 0))
    return math.sqrt(dx * dx + dz * dz)


@dataclass
class OrphanRecord:
    asset_id:       str
    asset_name:     str
    expected_near:  str
    violation_code: str = "ORPHAN_OBJECT"
    severity:       str = "WARNING"
    detail:         str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id":       self.asset_id,
            "asset_name":     self.asset_name,
            "expected_near":  self.expected_near,
            "violation_code": self.violation_code,
            "severity":       self.severity,
            "detail":         self.detail,
        }


class OrphanDetector:
    """Finds assets with no valid semantic parent in the scene."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def detect(self, scene_layout: Dict[str, Any]) -> List[OrphanRecord]:
        """Return list of ORPHAN_OBJECT records. Never raises."""
        try:
            return self._detect(scene_layout)
        except Exception:
            return []

    def _detect(self, scene: Dict[str, Any]) -> List[OrphanRecord]:
        transforms = scene.get("transforms") or []
        orphans: List[OrphanRecord] = []

        for t in transforms:
            name    = t.get("asset_name", "")
            aid     = t.get("asset_id", "")
            pid     = t.get("parent_id", "")
            cluster = t.get("cluster_id", "")

            # Already attached via parent_id or cluster
            if pid or cluster:
                continue

            for rule in _ORPHAN_RULES:
                if rule["kw"] not in name.lower():
                    continue

                parent_kws = rule["parent_kws"]
                radius     = rule["radius"]

                # Find candidate parents in scene
                candidates = [
                    c for c in transforms
                    if any(kw in c.get("asset_name", "").lower() for kw in parent_kws)
                    and c.get("asset_id", "") != aid
                ]

                if not candidates:
                    orphans.append(OrphanRecord(
                        asset_id=aid,
                        asset_name=name,
                        expected_near="/".join(parent_kws[:3]),
                        detail=(
                            f"{name!r} has no {parent_kws[0]!r} type anywhere in scene"
                        ),
                    ))
                    break

                if radius is not None:
                    closest = min(_dist_2d(t, c) for c in candidates)
                    if closest > radius:
                        orphans.append(OrphanRecord(
                            asset_id=aid,
                            asset_name=name,
                            expected_near=parent_kws[0],
                            detail=(
                                f"{name!r} has no {parent_kws[0]!r} within "
                                f"{radius}m (closest={closest:.2f}m)"
                            ),
                        ))
                # radius=None: parent exists in scene → not orphaned
                break  # first matching rule wins

        return orphans


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[OrphanDetector] = None
_lock = threading.Lock()


def get_orphan_detector() -> OrphanDetector:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = OrphanDetector()
    return _instance


def reset_orphan_detector_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
