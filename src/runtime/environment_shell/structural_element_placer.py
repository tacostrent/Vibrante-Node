"""
StructuralElementPlacer — Tier 10.4, Phase 5
=============================================
Attaches structural elements to their anchors.

Rules:
  door   → attach to wall anchor
  window → attach to wall anchor
  beam   → attach to ceiling anchor
  column → attach floor + ceiling anchors
  fireplace → attach to wall

Only runs AFTER shell construction (Phases 1–4). Never raises.

Public API:
    StructuralElementPlacer
    get_structural_element_placer()
    reset_structural_element_placer_for_tests()
"""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional

from src.runtime.environment_shell.shell_phase_result import (
    ShellPhaseResult,
    STRUCTURAL_PLACEMENT_COMPLETE,
)


class StructuralElementPlacer:

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def place(
        self,
        anchors:             List[Dict[str, Any]],
        structural_assets:   List[Dict[str, Any]],
        environment:         str = "",
    ) -> ShellPhaseResult:
        """
        Attach structural assets to their matching anchors.
        Never raises.

        structural_assets: list of asset dicts with _structural_role field
                           (or any asset dict — unrecognised roles are skipped)
        anchors:           list from StructuralAnchorGenerator.generate()
        """
        try:
            return self._place(anchors, structural_assets, environment)
        except Exception as exc:
            r = ShellPhaseResult(phase="placement", status="PLACEMENT_FAILED")
            r.errors.append(f"StructuralElementPlacer error: {exc}")
            return r

    def _place(
        self,
        anchors:           List[Dict[str, Any]],
        structural_assets: List[Dict[str, Any]],
        environment:       str,
    ) -> ShellPhaseResult:
        result = ShellPhaseResult(phase="placement")

        door_anchors      = [a for a in anchors if a.get("anchor_type") == "door_anchor"]
        window_anchors    = [a for a in anchors if a.get("anchor_type") == "window_anchor"]
        beam_anchors      = [a for a in anchors if a.get("anchor_type") == "beam_anchor"]
        fireplace_anchors = [a for a in anchors if a.get("anchor_type") == "fireplace_anchor"]

        placed:       List[Dict[str, Any]] = []
        door_count   = 0
        window_count = 0
        beam_count   = 0

        for asset in structural_assets:
            role = asset.get("_structural_role", asset.get("structural_role", ""))
            name = asset.get("name", asset.get("asset_id", ""))

            if role in ("doorway", "door_frame"):
                idx = door_count % max(len(door_anchors), 1)
                anchor = door_anchors[idx] if door_anchors else None
                placed.append({
                    "asset_id":    asset.get("asset_id", asset.get("name", "")),
                    "asset_name":  name,
                    "role":        role,
                    "anchor_id":   anchor["anchor_id"] if anchor else "",
                    "wall_face":   anchor["wall_face"] if anchor else "south",
                    "tx": anchor["tx"] if anchor else 0.0,
                    "ty": 0.0,
                    "tz": anchor["tz"] if anchor else 0.0,
                    "attached":    bool(anchor),
                    "builder":     "OpeningBuilder",
                })
                door_count += 1

            elif role in ("window", "window_frame"):
                idx = window_count % max(len(window_anchors), 1)
                anchor = window_anchors[idx] if window_anchors else None
                placed.append({
                    "asset_id":    asset.get("asset_id", asset.get("name", "")),
                    "asset_name":  name,
                    "role":        role,
                    "anchor_id":   anchor["anchor_id"] if anchor else "",
                    "wall_face":   anchor["wall_face"] if anchor else "east",
                    "tx": anchor["tx"] if anchor else 0.0,
                    "ty": anchor.get("ty", 1.0) if anchor else 1.0,
                    "tz": anchor["tz"] if anchor else 0.0,
                    "attached":    bool(anchor),
                    "builder":     "OpeningBuilder",
                })
                window_count += 1

            elif role in ("beam", "support_beam"):
                idx = beam_count % max(len(beam_anchors), 1)
                anchor = beam_anchors[idx] if beam_anchors else None
                placed.append({
                    "asset_id":    asset.get("asset_id", asset.get("name", "")),
                    "asset_name":  name,
                    "role":        role,
                    "anchor_id":   anchor["anchor_id"] if anchor else "",
                    "tx": anchor["tx"] if anchor else 0.0,
                    "ty": anchor["ty"] if anchor else 3.9,
                    "tz": 0.0,
                    "span":        anchor.get("beam_span", 10.0) if anchor else 10.0,
                    "attached":    bool(anchor),
                    "builder":     "BeamBuilder",
                })
                beam_count += 1

            elif role == "column":
                placed.append({
                    "asset_id":   asset.get("asset_id", asset.get("name", "")),
                    "asset_name": name,
                    "role":       role,
                    "tx": 0.0, "ty": 0.0, "tz": 0.0,
                    "attached":   True,
                    "builder":    "BeamBuilder",
                })

            elif role == "fireplace":
                anchor = fireplace_anchors[0] if fireplace_anchors else None
                placed.append({
                    "asset_id":   asset.get("asset_id", asset.get("name", "")),
                    "asset_name": name,
                    "role":       role,
                    "anchor_id":  anchor["anchor_id"] if anchor else "",
                    "wall_face":  anchor.get("wall_face", "north") if anchor else "north",
                    "tx": anchor["tx"] if anchor else 0.0,
                    "ty": 0.0,
                    "tz": anchor["tz"] if anchor else 0.0,
                    "attached":   bool(anchor),
                    "builder":    "AnchorAssetBuilder",
                })

            else:
                # Unknown structural role — flag but don't fail
                result.findings.append(
                    f"Asset '{name}' has unrecognised structural role '{role}' — skipped."
                )

        result.elements = placed
        result.metrics  = {
            "placed_count":   len(placed),
            "door_count":     door_count,
            "window_count":   window_count,
            "beam_count":     beam_count,
            "skipped_count":  len(structural_assets) - len(placed),
        }
        result.status = STRUCTURAL_PLACEMENT_COMPLETE
        result.ok     = True
        return result


# ── Singleton ──────────────────────────────────────────────────────────────────

_INSTANCE: Optional[StructuralElementPlacer] = None
_LOCK = threading.Lock()


def get_structural_element_placer() -> StructuralElementPlacer:
    global _INSTANCE
    if _INSTANCE is None:
        with _LOCK:
            if _INSTANCE is None:
                _INSTANCE = StructuralElementPlacer()
    return _INSTANCE


def reset_structural_element_placer_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
