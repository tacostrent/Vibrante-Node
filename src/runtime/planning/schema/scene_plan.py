"""
Scene Plan Schema (Tier 7 — Scene Planning Runtime)
====================================================
Canonical typed representation of a scene plan, derived deterministically
from a SceneIntent by the Scene Planning Runtime.

This is the contract that every downstream tier receives:
  - Scene Assembly consumes SceneZonePlan and PlacementHint
  - Asset Intelligence consumes AssetQuery
  - Camera Rigs consume CameraTarget
  - Rendering receives CompositionRule guidance
  - Critique loops compare the plan against execution results

DESIGN RULES:
  1. All fields typed — no free-form text blobs in plan fields.
  2. All models have to_dict() / from_dict() / to_json() / from_json().
  3. Schema versioned — SCHEMA_VERSION for forward-compatibility.
  4. Defaults are sensible — partial plans are valid at intermediate pipeline stages.
  5. No Houdini imports. No bridge calls. Pure data model.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Schema version
# ---------------------------------------------------------------------------

SCHEMA_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Enum constants
# ---------------------------------------------------------------------------

ZONE_TYPES = frozenset({
    "foreground", "midground", "background",
    "overhead", "ground", "interior_wall", "ceiling",
})

POPULATION_LEVELS = frozenset({"empty", "sparse", "moderate", "dense", "packed"})

PRIORITY_RANGE = (1, 10)

ASSET_PRIORITIES = frozenset({"required", "recommended", "optional"})

SIZE_HINTS = frozenset({"tiny", "small", "medium", "large", "massive"})

SHOT_TYPES = frozenset({
    "establishing", "hero", "detail", "transition",
    "reaction", "tracking", "aerial",
})

COMPOSITION_RULE_TYPES = frozenset({
    "hero_focal_point",
    "leading_lines",
    "layered_depth",
    "rule_of_thirds",
    "silhouette_preservation",
    "high_contrast",
    "shadow_framing",
    "geometric_lines",
    "perspective_convergence",
    "tension_diagonal",
    "asymmetric_balance",
    "symmetric_balance",
    "horizon_rule",
    "camera_safe_zone",
    "depth_of_field_guidance",
})

COMPLEXITY_LEVELS = frozenset({"simple", "moderate", "complex", "epic"})

# ---------------------------------------------------------------------------
# AssetQuery
# ---------------------------------------------------------------------------

@dataclass
class AssetQuery:
    """A structured asset search request for a single category within a zone.

    Attributes:
        query_id:      Unique identifier.
        category:      Asset semantic category ("building", "vehicle", "vegetation", ...).
        tags:          Search tags ["sci-fi", "damaged", "city"].
        zone:          Target zone type this asset belongs in.
        quantity:      Approximate number of instances needed.
        priority:      "required" | "recommended" | "optional"
        style_hints:   Style descriptors that should filter provider results.
        size_hint:     Spatial footprint hint.
        metadata:      Extra provider-specific data.
    """

    query_id:    str            = field(default_factory=lambda: f"aq_{uuid.uuid4().hex[:10]}")
    category:    str            = ""
    tags:        List[str]      = field(default_factory=list)
    zone:        str            = ""
    quantity:    int            = 1
    priority:    str            = "recommended"
    style_hints: List[str]      = field(default_factory=list)
    size_hint:   str            = "medium"
    metadata:    Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query_id":    self.query_id,
            "category":    self.category,
            "tags":        list(self.tags),
            "zone":        self.zone,
            "quantity":    self.quantity,
            "priority":    self.priority,
            "style_hints": list(self.style_hints),
            "size_hint":   self.size_hint,
            "metadata":    dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AssetQuery":
        return cls(
            query_id=d.get("query_id", f"aq_{uuid.uuid4().hex[:10]}"),
            category=d.get("category", ""),
            tags=list(d.get("tags") or []),
            zone=d.get("zone", ""),
            quantity=int(d.get("quantity", 1)),
            priority=d.get("priority", "recommended"),
            style_hints=list(d.get("style_hints") or []),
            size_hint=d.get("size_hint", "medium"),
            metadata=dict(d.get("metadata") or {}),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_json(cls, s: str) -> "AssetQuery":
        return cls.from_dict(json.loads(s))


# ---------------------------------------------------------------------------
# CameraTarget
# ---------------------------------------------------------------------------

@dataclass
class CameraTarget:
    """A camera focus point with placement guidance.

    Attributes:
        target_id:      Unique identifier.
        name:           Human-readable name ("hero_building", "foreground_vehicle").
        zone:           Which zone this target is in.
        position_hint:  Screen position ("left_third", "center", "right_third").
        look_at_hint:   What part of the target to frame ("center_mass", "damaged_section").
        importance:     0.0–1.0. Higher = primary shot.
        shot_type:      Camera shot classification.
        metadata:       Extra data.
    """

    target_id:     str            = field(default_factory=lambda: f"ct_{uuid.uuid4().hex[:10]}")
    name:          str            = ""
    zone:          str            = ""
    position_hint: str            = "center"
    look_at_hint:  str            = "center_mass"
    importance:    float          = 0.5
    shot_type:     str            = "hero"
    metadata:      Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_id":     self.target_id,
            "name":          self.name,
            "zone":          self.zone,
            "position_hint": self.position_hint,
            "look_at_hint":  self.look_at_hint,
            "importance":    self.importance,
            "shot_type":     self.shot_type,
            "metadata":      dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CameraTarget":
        return cls(
            target_id=d.get("target_id", f"ct_{uuid.uuid4().hex[:10]}"),
            name=d.get("name", ""),
            zone=d.get("zone", ""),
            position_hint=d.get("position_hint", "center"),
            look_at_hint=d.get("look_at_hint", "center_mass"),
            importance=float(d.get("importance", 0.5)),
            shot_type=d.get("shot_type", "hero"),
            metadata=dict(d.get("metadata") or {}),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_json(cls, s: str) -> "CameraTarget":
        return cls.from_dict(json.loads(s))


# ---------------------------------------------------------------------------
# CompositionRule
# ---------------------------------------------------------------------------

@dataclass
class CompositionRule:
    """A single composition guideline for the scene.

    Attributes:
        rule_id:      Unique identifier.
        rule_type:    One of COMPOSITION_RULE_TYPES.
        description:  Human-readable explanation of why this rule applies.
        applies_to:   Scope ("full_scene", "foreground", "midground", "background").
        priority:     0.0–1.0. Higher = more important for this scene.
        metadata:     Extra data.
    """

    rule_id:     str            = field(default_factory=lambda: f"cr_{uuid.uuid4().hex[:10]}")
    rule_type:   str            = ""
    description: str            = ""
    applies_to:  str            = "full_scene"
    priority:    float          = 0.5
    metadata:    Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id":     self.rule_id,
            "rule_type":   self.rule_type,
            "description": self.description,
            "applies_to":  self.applies_to,
            "priority":    self.priority,
            "metadata":    dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CompositionRule":
        return cls(
            rule_id=d.get("rule_id", f"cr_{uuid.uuid4().hex[:10]}"),
            rule_type=d.get("rule_type", ""),
            description=d.get("description", ""),
            applies_to=d.get("applies_to", "full_scene"),
            priority=float(d.get("priority", 0.5)),
            metadata=dict(d.get("metadata") or {}),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_json(cls, s: str) -> "CompositionRule":
        return cls.from_dict(json.loads(s))


# ---------------------------------------------------------------------------
# PlacementHint
# ---------------------------------------------------------------------------

@dataclass
class PlacementHint:
    """Spatial placement guidance for an asset category within a zone.

    Attributes:
        hint_id:         Unique identifier.
        asset_category:  Which asset category this hint applies to.
        zone:            Target zone.
        position:        Lateral placement ("left", "center", "right", "distributed").
        depth_hint:      Z-depth placement ("front", "mid", "rear").
        spacing:         Asset spacing ("tight", "medium", "loose").
        metadata:        Extra data.
    """

    hint_id:        str            = field(default_factory=lambda: f"ph_{uuid.uuid4().hex[:10]}")
    asset_category: str            = ""
    zone:           str            = ""
    position:       str            = "distributed"
    depth_hint:     str            = "mid"
    spacing:        str            = "medium"
    metadata:       Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hint_id":        self.hint_id,
            "asset_category": self.asset_category,
            "zone":           self.zone,
            "position":       self.position,
            "depth_hint":     self.depth_hint,
            "spacing":        self.spacing,
            "metadata":       dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PlacementHint":
        return cls(
            hint_id=d.get("hint_id", f"ph_{uuid.uuid4().hex[:10]}"),
            asset_category=d.get("asset_category", ""),
            zone=d.get("zone", ""),
            position=d.get("position", "distributed"),
            depth_hint=d.get("depth_hint", "mid"),
            spacing=d.get("spacing", "medium"),
            metadata=dict(d.get("metadata") or {}),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_json(cls, s: str) -> "PlacementHint":
        return cls.from_dict(json.loads(s))


# ---------------------------------------------------------------------------
# SceneZonePlan
# ---------------------------------------------------------------------------

@dataclass
class SceneZonePlan:
    """Plan for a single spatial zone within the scene.

    Attributes:
        zone_id:          Unique identifier.
        zone_type:        Spatial layer ("foreground", "midground", "background", ...).
        description:      Human-readable description of this zone's role.
        asset_categories: List of asset categories expected in this zone.
        population:       Density level.
        priority:         Rendering/build priority 1–10 (10 = highest).
        placement_hints:  Per-category placement guidance.
        metadata:         Extra data.
    """

    zone_id:          str                 = field(default_factory=lambda: f"z_{uuid.uuid4().hex[:10]}")
    zone_type:        str                 = ""
    description:      str                 = ""
    asset_categories: List[str]           = field(default_factory=list)
    population:       str                 = "moderate"
    priority:         int                 = 5
    placement_hints:  List[PlacementHint] = field(default_factory=list)
    metadata:         Dict[str, Any]      = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id":          self.zone_id,
            "zone_type":        self.zone_type,
            "description":      self.description,
            "asset_categories": list(self.asset_categories),
            "population":       self.population,
            "priority":         self.priority,
            "placement_hints":  [h.to_dict() for h in self.placement_hints],
            "metadata":         dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SceneZonePlan":
        return cls(
            zone_id=d.get("zone_id", f"z_{uuid.uuid4().hex[:10]}"),
            zone_type=d.get("zone_type", ""),
            description=d.get("description", ""),
            asset_categories=list(d.get("asset_categories") or []),
            population=d.get("population", "moderate"),
            priority=int(d.get("priority", 5)),
            placement_hints=[PlacementHint.from_dict(h)
                             for h in (d.get("placement_hints") or [])],
            metadata=dict(d.get("metadata") or {}),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_json(cls, s: str) -> "SceneZonePlan":
        return cls.from_dict(json.loads(s))


# ---------------------------------------------------------------------------
# ScenePlan
# ---------------------------------------------------------------------------

@dataclass
class ScenePlan:
    """Canonical structured scene plan derived from a SceneIntent.

    Attributes:
        plan_id:                 Unique identifier.
        schema_version:          Schema version for forward-compatibility.
        created_at:              Unix timestamp.
        scene_intent_id:         ID of the source SceneIntent.

        environment:             Inherited from SceneIntent.
        style:                   Inherited from SceneIntent.
        mood:                    Inherited from SceneIntent.

        zones:                   List of spatial zone plans.
        asset_queries:           Structured asset search requests.
        camera_targets:          Camera focus points with placement hints.
        composition_rules:       Compositional guidelines for the scene.
        placement_hints:         Per-category spatial placement guidance.

        estimated_complexity:    "simple" | "moderate" | "complex" | "epic"
        estimated_asset_count:   Sum of all AssetQuery.quantity values.

        recommendations:         List of recommendation dicts from memory/pattern/graph.
        planning_notes:          Human-readable notes from each planning phase.
        metadata:                Extra data.

        validated:               True once ScenePlanValidator has run.
        validation_errors:       Blocking issues found by validator.
        validation_warnings:     Advisory issues found by validator.
    """

    # Identity
    plan_id:          str            = field(default_factory=lambda: f"plan_{uuid.uuid4().hex[:12]}")
    schema_version:   str            = SCHEMA_VERSION
    created_at:       float          = field(default_factory=time.time)
    scene_intent_id:  str            = ""

    # Core descriptors
    environment:      Optional[str]  = None
    style:            Optional[str]  = None
    mood:             Optional[str]  = None

    # Plan content
    zones:             List[SceneZonePlan]   = field(default_factory=list)
    asset_queries:     List[AssetQuery]      = field(default_factory=list)
    camera_targets:    List[CameraTarget]    = field(default_factory=list)
    composition_rules: List[CompositionRule] = field(default_factory=list)
    placement_hints:   List[PlacementHint]   = field(default_factory=list)

    # Estimates
    estimated_complexity:   str = "moderate"
    estimated_asset_count:  int = 0

    # Meta
    recommendations:     List[Dict[str, Any]] = field(default_factory=list)
    planning_notes:      List[str]            = field(default_factory=list)
    metadata:            Dict[str, Any]       = field(default_factory=dict)

    # Validation
    validated:           bool       = False
    validation_errors:   List[str]  = field(default_factory=list)
    validation_warnings: List[str]  = field(default_factory=list)

    # ------------------------------------------------------------------
    # Convenience properties
    # ------------------------------------------------------------------

    @property
    def is_valid(self) -> bool:
        return self.validated and len(self.validation_errors) == 0

    @property
    def zone_types(self) -> List[str]:
        return [z.zone_type for z in self.zones]

    @property
    def has_foreground(self) -> bool:
        return "foreground" in self.zone_types

    @property
    def has_background(self) -> bool:
        return "background" in self.zone_types

    @property
    def total_required_assets(self) -> int:
        return sum(q.quantity for q in self.asset_queries if q.priority == "required")

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id":               self.plan_id,
            "schema_version":        self.schema_version,
            "created_at":            self.created_at,
            "scene_intent_id":       self.scene_intent_id,
            "environment":           self.environment,
            "style":                 self.style,
            "mood":                  self.mood,
            "zones":                 [z.to_dict() for z in self.zones],
            "asset_queries":         [q.to_dict() for q in self.asset_queries],
            "camera_targets":        [c.to_dict() for c in self.camera_targets],
            "composition_rules":     [r.to_dict() for r in self.composition_rules],
            "placement_hints":       [h.to_dict() for h in self.placement_hints],
            "estimated_complexity":  self.estimated_complexity,
            "estimated_asset_count": self.estimated_asset_count,
            "recommendations":       list(self.recommendations),
            "planning_notes":        list(self.planning_notes),
            "metadata":              dict(self.metadata),
            "validated":             self.validated,
            "validation_errors":     list(self.validation_errors),
            "validation_warnings":   list(self.validation_warnings),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ScenePlan":
        return cls(
            plan_id=d.get("plan_id", f"plan_{uuid.uuid4().hex[:12]}"),
            schema_version=d.get("schema_version", SCHEMA_VERSION),
            created_at=float(d.get("created_at", time.time())),
            scene_intent_id=d.get("scene_intent_id", ""),
            environment=d.get("environment"),
            style=d.get("style"),
            mood=d.get("mood"),
            zones=[SceneZonePlan.from_dict(z) for z in (d.get("zones") or [])],
            asset_queries=[AssetQuery.from_dict(q) for q in (d.get("asset_queries") or [])],
            camera_targets=[CameraTarget.from_dict(c) for c in (d.get("camera_targets") or [])],
            composition_rules=[CompositionRule.from_dict(r) for r in (d.get("composition_rules") or [])],
            placement_hints=[PlacementHint.from_dict(h) for h in (d.get("placement_hints") or [])],
            estimated_complexity=d.get("estimated_complexity", "moderate"),
            estimated_asset_count=int(d.get("estimated_asset_count", 0)),
            recommendations=list(d.get("recommendations") or []),
            planning_notes=list(d.get("planning_notes") or []),
            metadata=dict(d.get("metadata") or {}),
            validated=bool(d.get("validated", False)),
            validation_errors=list(d.get("validation_errors") or []),
            validation_warnings=list(d.get("validation_warnings") or []),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_json(cls, s: str) -> "ScenePlan":
        return cls.from_dict(json.loads(s))

    def __repr__(self) -> str:
        env = self.environment or "?"
        return (
            f"ScenePlan({env!r}, zones={len(self.zones)}, "
            f"queries={len(self.asset_queries)}, "
            f"complexity={self.estimated_complexity!r})"
        )


# ---------------------------------------------------------------------------
# PlanningResult
# ---------------------------------------------------------------------------

@dataclass
class PlanningResult:
    """Wrapper returned by ScenePlanner.plan().

    Attributes:
        ok:              True when planning succeeded.
        plan:            The produced ScenePlan, or None on failure.
        errors:          Blocking errors that prevented planning.
        warnings:        Advisory issues.
        planning_time:   Wall-clock time for the planning run (seconds).
        pipeline_stages: Which stages completed ("zones", "composition", ...).
    """

    ok:              bool                  = False
    plan:            Optional[ScenePlan]   = None
    errors:          List[str]             = field(default_factory=list)
    warnings:        List[str]             = field(default_factory=list)
    planning_time:   float                 = 0.0
    pipeline_stages: List[str]             = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok":              self.ok,
            "plan":            self.plan.to_dict() if self.plan else None,
            "errors":          list(self.errors),
            "warnings":        list(self.warnings),
            "planning_time":   self.planning_time,
            "pipeline_stages": list(self.pipeline_stages),
        }
