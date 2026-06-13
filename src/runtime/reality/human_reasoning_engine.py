"""
human_reasoning_engine.py — §54 Reality Intelligence (Tier 15.0+)
==================================================================
Human Reasoning Layer. Every asset must answer six questions before it may
be placed:

    1. Why does this asset exist?
    2. Who uses it?
    3. What activity happens around it?
    4. What supports it?
    5. What is it related to?
    6. Does it improve the scene story?

If no answer exists: do not place the asset.

Core rule: never ask "Can I place this asset?" — always ask "Would a human
intentionally place this asset here?"

Public API:
    AssetJustification
    HumanReasoningResult
    HumanReasoningEngine
    get_human_reasoning_engine()
    reset_human_reasoning_engine_for_tests()
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.runtime.reality.reality_scene_model import parse_scene, infer_asset_type

# Built-in justification profiles per asset type.
# (why_exists, who_uses, activity, supported_by, related_to, story_value)
_TYPE_PROFILES: Dict[str, Dict[str, str]] = {
    "table":     {"why": "central work/dining surface", "who": "occupants gathering around it",
                  "activity": "eating, drinking, playing cards, working",
                  "support": "floor", "related": "chairs, tableware, lantern",
                  "story": "anchors the social life of the room"},
    "desk":      {"why": "dedicated work surface", "who": "a worker or clerk",
                  "activity": "writing, repairing, studying",
                  "support": "floor", "related": "chair, books, tools, lamp",
                  "story": "shows someone works here"},
    "bar":       {"why": "serving counter", "who": "barkeeper and patrons",
                  "activity": "serving and drinking",
                  "support": "floor", "related": "stools, bottles, glasses",
                  "story": "social hub of the room"},
    "chair":     {"why": "seating at a work or dining spot", "who": "an occupant",
                  "activity": "sitting at the table/desk/fire",
                  "support": "floor, paired with table/desk/fireplace/bar",
                  "related": "table, desk, fireplace", "story": "implies human presence"},
    "stool":     {"why": "bar seating", "who": "a patron", "activity": "sitting at the bar",
                  "support": "floor, paired with bar", "related": "bar counter",
                  "story": "invites someone to sit"},
    "bench":     {"why": "shared seating", "who": "several occupants",
                  "activity": "resting against a wall or table",
                  "support": "floor", "related": "wall, table", "story": "communal space"},
    "bed":       {"why": "sleeping place", "who": "the resident", "activity": "sleeping",
                  "support": "floor", "related": "side table, lamp",
                  "story": "someone lives here"},
    "bottle":    {"why": "drink container in use", "who": "drinkers at the table/bar",
                  "activity": "drinking", "support": "table, shelf or bar",
                  "related": "cups, table", "story": "a drink was just poured"},
    "cup":       {"why": "drinking vessel", "who": "an occupant", "activity": "drinking",
                  "support": "table or shelf", "related": "bottle, plate",
                  "story": "interrupted meal or drink"},
    "plate":     {"why": "tableware for a meal", "who": "diners", "activity": "eating",
                  "support": "table", "related": "cup, table", "story": "a meal happens here"},
    "lantern":   {"why": "local light source", "who": "everyone in the room",
                  "activity": "lighting the work/dining area",
                  "support": "table, wall bracket or ceiling hook",
                  "related": "table, wall", "story": "warm pool of light"},
    "lamp":      {"why": "light source", "who": "occupants", "activity": "lighting",
                  "support": "table, wall or ceiling", "related": "desk, bed",
                  "story": "lived-in lighting"},
    "fireplace": {"why": "heat and light source", "who": "everyone in the room",
                  "activity": "warming, gathering", "support": "wall (masonry)",
                  "related": "chairs, mantle props", "story": "primary focal point"},
    "shelf":     {"why": "storage at hand height", "who": "the resident",
                  "activity": "storing and retrieving items", "support": "wall or floor",
                  "related": "books, bottles, tools", "story": "organized daily life"},
    "crate":     {"why": "goods storage", "who": "workers", "activity": "storing supplies",
                  "support": "floor (storage zone)", "related": "barrels, shelves",
                  "story": "commerce and supply"},
    "barrel":    {"why": "bulk liquid/dry storage", "who": "workers",
                  "activity": "storage", "support": "floor (corner or wall)",
                  "related": "crates", "story": "stocked and provisioned"},
    "bucket":    {"why": "utility container", "who": "workers", "activity": "cleaning, carrying",
                  "support": "floor near wall/corner", "related": "tools",
                  "story": "chores in progress"},
    "book":      {"why": "reading or record-keeping", "who": "a literate occupant",
                  "activity": "reading, writing", "support": "table, desk or shelf",
                  "related": "desk, shelf", "story": "knowledge and routine"},
    "tool":      {"why": "work implement", "who": "a worker", "activity": "repair, craft",
                  "support": "workbench, shelf or hook", "related": "desk, workbench",
                  "story": "work interrupted"},
    "poster":    {"why": "wall information/decor", "who": "everyone who passes",
                  "activity": "reading, glancing", "support": "wall",
                  "related": "wall", "story": "world-building detail"},
    "rug":       {"why": "floor comfort and zoning", "who": "occupants",
                  "activity": "walking, defining a zone", "support": "floor",
                  "related": "seating zone", "story": "softens the room"},
    "plant":     {"why": "living decor", "who": "the resident tends it",
                  "activity": "decoration", "support": "floor or shelf",
                  "related": "window", "story": "care and life"},
    "machine":   {"why": "industrial/technical function", "who": "operators",
                  "activity": "operating, monitoring", "support": "floor",
                  "related": "tools, consoles", "story": "purpose of the facility"},
    "beam":      {"why": "structural ceiling support", "who": "(architecture)",
                  "activity": "carrying the roof load", "support": "walls or columns",
                  "related": "walls, columns, ceiling", "story": "believable construction"},
    "column":    {"why": "vertical structural support", "who": "(architecture)",
                  "activity": "carrying beams", "support": "floor",
                  "related": "beams, ceiling", "story": "believable construction"},
    "wall":      {"why": "room enclosure", "who": "(architecture)", "activity": "enclosing",
                  "support": "floor", "related": "doors, windows, beams",
                  "story": "defines the space"},
    "door":      {"why": "entry and exit", "who": "everyone", "activity": "passage",
                  "support": "wall opening", "related": "wall", "story": "the room connects somewhere"},
    "window":    {"why": "light and view", "who": "occupants", "activity": "looking out",
                  "support": "wall opening", "related": "wall", "story": "a world outside"},
    "floor":     {"why": "walkable ground plane", "who": "everyone", "activity": "walking",
                  "support": "foundation", "related": "walls", "story": "base of the room"},
    "ceiling":   {"why": "room cover", "who": "(architecture)", "activity": "enclosing",
                  "support": "walls and beams", "related": "beams", "story": "complete enclosure"},
    "rope":      {"why": "utility rigging", "who": "workers", "activity": "tying, hauling",
                  "support": "hook, beam or floor coil", "related": "tools, crates",
                  "story": "working environment"},
    "hay":       {"why": "animal feed / packing", "who": "workers", "activity": "storage",
                  "support": "floor", "related": "crates, barrels", "story": "rural texture"},
    "pillow":    {"why": "comfort item", "who": "the resident", "activity": "resting",
                  "support": "bed or chair", "related": "bed", "story": "domestic comfort"},
    "vehicle":   {"why": "transport", "who": "drivers", "activity": "loading, hauling",
                  "support": "floor", "related": "crates", "story": "arrivals and departures"},
}


@dataclass
class AssetJustification:
    asset_id:     str
    asset_name:   str
    asset_type:   str
    why_exists:   str = ""
    who_uses:     str = ""
    activity:     str = ""
    supported_by: str = ""
    related_to:   str = ""
    story_value:  str = ""
    justified:    bool = False
    detail:       str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id":     self.asset_id,
            "asset_name":   self.asset_name,
            "asset_type":   self.asset_type,
            "why_exists":   self.why_exists,
            "who_uses":     self.who_uses,
            "activity":     self.activity,
            "supported_by": self.supported_by,
            "related_to":   self.related_to,
            "story_value":  self.story_value,
            "justified":    self.justified,
            "detail":       self.detail,
        }


@dataclass
class HumanReasoningResult:
    justifications: List[AssetJustification] = field(default_factory=list)
    rejected:       List[AssetJustification] = field(default_factory=list)
    justified_count: int = 0
    rejected_count:  int = 0
    all_justified:   bool = True
    findings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "justifications":  [j.to_dict() for j in self.justifications],
            "rejected":        [j.to_dict() for j in self.rejected],
            "justified_count": self.justified_count,
            "rejected_count":  self.rejected_count,
            "all_justified":   self.all_justified,
            "findings":        list(self.findings),
        }


class HumanReasoningEngine:
    """Answers the six §54 questions for every asset. Never raises."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def justify_asset(self, asset: Dict[str, Any]) -> AssetJustification:
        try:
            return self._justify(asset if isinstance(asset, dict) else {})
        except Exception as exc:
            return AssetJustification(
                asset_id="", asset_name="", asset_type="",
                justified=False, detail=f"HumanReasoningEngine internal error: {exc}",
            )

    def justify_scene(self, scene_layout: Dict[str, Any]) -> HumanReasoningResult:
        try:
            result = HumanReasoningResult()
            snap = parse_scene(scene_layout)
            for asset in snap.assets:
                j = self._justify(asset.to_dict())
                result.justifications.append(j)
                if j.justified:
                    result.justified_count += 1
                else:
                    result.rejected.append(j)
                    result.rejected_count += 1
                    result.findings.append(f"UNJUSTIFIED_ASSET: {j.detail}")
            result.all_justified = result.rejected_count == 0
            return result
        except Exception as exc:
            r = HumanReasoningResult(all_justified=False)
            r.findings.append(f"HumanReasoningEngine internal error: {exc}")
            return r

    # ------------------------------------------------------------------

    def _justify(self, asset: Dict[str, Any]) -> AssetJustification:
        name = str(asset.get("asset_name") or asset.get("name") or "")
        asset_type = str(asset.get("asset_type") or "") or infer_asset_type(name)
        j = AssetJustification(
            asset_id=str(asset.get("asset_id") or name),
            asset_name=name,
            asset_type=asset_type,
        )

        profile = _TYPE_PROFILES.get(asset_type)
        if profile is not None:
            j.why_exists   = profile["why"]
            j.who_uses     = profile["who"]
            j.activity     = profile["activity"]
            j.supported_by = profile["support"]
            j.related_to   = profile["related"]
            j.story_value  = profile["story"]
            j.justified    = True
            return j

        # No built-in profile — the asset metadata itself must answer.
        j.why_exists   = str(asset.get("why_exists", "") or asset.get("description", "") or "")
        j.who_uses     = str(asset.get("who_uses", "") or "")
        j.activity     = str(asset.get("activity", "") or "")
        j.supported_by = str(asset.get("supported_by", "") or "")
        j.related_to   = str(asset.get("related_to", "") or "")
        j.story_value  = str(asset.get("story_value", "") or "")
        j.justified = bool(j.why_exists and j.story_value)
        if not j.justified:
            j.detail = (
                f"{name or j.asset_id}: no human would intentionally place this here — "
                "no purpose, user, activity or story value could be determined. "
                "Do not place the asset."
            )
        return j


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[HumanReasoningEngine] = None
_lock = threading.Lock()


def get_human_reasoning_engine() -> HumanReasoningEngine:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = HumanReasoningEngine()
    return _instance


def reset_human_reasoning_engine_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
