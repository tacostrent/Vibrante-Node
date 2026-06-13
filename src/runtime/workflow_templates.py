"""
Workflow Templates (Tier 2.75)
================================
Reusable semantic workflow blueprints for common Houdini operations.
Templates are parameterised via {variable} interpolation in op strings
and resolve to concrete operation lists when `apply_template` is called.

Template structure:
    {
        "template_id":            str,
        "description":            str,
        "required_capabilities":  list[str],   # capability ids that must be registered
        "operations":             list[dict],  # op dicts with optional {varname} in values
        "constraints":            list[str],   # policy ids that must NOT fire on these ops
        "estimated_cost":         dict,        # {memory_impact, cook_cost, risk_level}
        "tags":                   list[str],   # searchable labels
    }

Variable interpolation:
    Any string value in the operations list can contain {varname} placeholders.
    `apply_template(template_id, context)` recursively substitutes all
    {varname} occurrences with context[varname] (str conversion applied).
    Missing variables raise KeyError with a clear message.

Public API:
    get_workflow_templates() -> WorkflowTemplates   (singleton)
    reset_workflow_templates_for_tests()

    WorkflowTemplates.register_template(template)
    WorkflowTemplates.get_template(template_id) -> dict | None
    WorkflowTemplates.list_templates(tag=None) -> list[dict]
    WorkflowTemplates.apply_template(template_id, context) -> list[dict]
"""

import copy
import threading
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Built-in templates
# ---------------------------------------------------------------------------

_BUILTIN_TEMPLATES: List[Dict[str, Any]] = [
    # ----- Pyro source -------------------------------------------------------
    {
        "template_id": "pyro_source",
        "description":  "Build a pyro source network: geo container → sphere → scatter → pyro_source.",
        "required_capabilities": ["create_node", "build_node_chain"],
        "tags": ["vfx", "pyro", "fire", "smoke", "simulation"],
        "estimated_cost": {"memory_impact": 0.8, "cook_cost": 0.7, "risk_level": "medium"},
        "constraints": [],
        "operations": [
            {
                "op":   "build_node_chain",
                "spec": {
                    "intent": "pyro_source",
                    "nodes": [
                        {"id": "geo",    "parent": "{parent}", "type": "geo",         "name": "{name}_geo"},
                        {"id": "sphere", "parent": "{parent}/{name}_geo", "type": "sphere", "name": "src_sphere",
                         "params": {"radx": "{radius}", "rady": "{radius}", "radz": "{radius}"}},
                        {"id": "scatter","parent": "{parent}/{name}_geo", "type": "scatter", "name": "src_scatter",
                         "params": {"npts": "1000"}},
                        {"id": "pyrosrc","parent": "{parent}/{name}_geo", "type": "pyro_source", "name": "pyro_source1"},
                    ],
                    "connections": [
                        {"from": "sphere",  "to": "scatter",  "out": 0, "in": 0},
                        {"from": "scatter", "to": "pyrosrc",  "out": 0, "in": 0},
                    ],
                    "layout": True,
                    "cook": False,
                },
            }
        ],
    },

    # ----- USD export --------------------------------------------------------
    {
        "template_id": "usd_export",
        "description":  "Export geometry to USD via a ROP network.",
        "required_capabilities": ["create_node"],
        "tags": ["usd", "export", "pipeline", "solaris"],
        "estimated_cost": {"memory_impact": 0.2, "cook_cost": 0.5, "risk_level": "low"},
        "constraints": [],
        "operations": [
            {
                "op": "create_node",
                "parent": "/out",
                "type":   "usd",
                "name":   "{name}_usd_out",
            },
            {
                "op":   "set_parms",
                "node": "/out/{name}_usd_out",
                "parms": {
                    "lopoutput": "{output_path}",
                    "trange":    "1",
                    "f1":        "{frame_start}",
                    "f2":        "{frame_end}",
                },
            },
        ],
    },

    # ----- Karma renderer ----------------------------------------------------
    {
        "template_id": "karma_render",
        "description":  "Add a Karma render node connected to the Solaris stage.",
        "required_capabilities": ["create_node", "set_parms"],
        "tags": ["render", "karma", "solaris", "usd"],
        "estimated_cost": {"memory_impact": 0.3, "cook_cost": 0.9, "risk_level": "low"},
        "constraints": [],
        "operations": [
            {
                "op":     "create_node",
                "parent": "/out",
                "type":   "karma",
                "name":   "{name}_karma",
            },
            {
                "op":   "set_parms",
                "node": "/out/{name}_karma",
                "parms": {
                    "loppath":   "{stage_path}",
                    "picture":   "{output_path}",
                    "xres":      "{res_x}",
                    "yres":      "{res_y}",
                },
            },
        ],
    },

    # ----- Geometry cache (Alembic) -----------------------------------------
    {
        "template_id": "geometry_cache",
        "description":  "Write geometry to Alembic cache via File Cache SOP.",
        "required_capabilities": ["create_node", "set_parms"],
        "tags": ["cache", "alembic", "geometry", "pipeline"],
        "estimated_cost": {"memory_impact": 0.3, "cook_cost": 0.5, "risk_level": "medium"},
        "constraints": [],
        "operations": [
            {
                "op":     "create_node",
                "parent": "{geo_path}",
                "type":   "filecache",
                "name":   "{name}_cache",
            },
            {
                "op":   "connect_nodes",
                "from_node": "{source_path}",
                "to_node":   "{geo_path}/{name}_cache",
                "output":    0,
                "input_idx": 0,
            },
            {
                "op":   "set_parms",
                "node": "{geo_path}/{name}_cache",
                "parms": {
                    "file":  "{cache_path}",
                    "f1":    "{frame_start}",
                    "f2":    "{frame_end}",
                },
            },
        ],
    },

    # ----- Asset publish container ------------------------------------------
    {
        "template_id": "asset_publish",
        "description":  "Scaffold a standard asset geo container (geo → null → output null).",
        "required_capabilities": ["build_node_chain"],
        "tags": ["asset", "pipeline", "publish", "geometry"],
        "estimated_cost": {"memory_impact": 0.1, "cook_cost": 0.0, "risk_level": "low"},
        "constraints": [],
        "operations": [
            {
                "op":   "build_node_chain",
                "spec": {
                    "intent": "asset_publish",
                    "nodes": [
                        {"id": "geo",    "parent": "{parent}", "type": "geo", "name": "{asset_name}"},
                        {"id": "input",  "parent": "{parent}/{asset_name}", "type": "null", "name": "INPUT"},
                        {"id": "output", "parent": "{parent}/{asset_name}", "type": "null", "name": "OUTPUT"},
                    ],
                    "connections": [
                        {"from": "input", "to": "output", "out": 0, "in": 0},
                    ],
                    "layout": True,
                    "cook":   False,
                },
            }
        ],
    },

    # ----- VFX container (geo + dopnet inside) ------------------------------
    {
        "template_id": "vfx_container",
        "description":  "Create a geo container with an embedded DOP network for simulation.",
        "required_capabilities": ["build_node_chain"],
        "tags": ["vfx", "simulation", "dop", "geometry"],
        "estimated_cost": {"memory_impact": 0.5, "cook_cost": 0.6, "risk_level": "medium"},
        "constraints": [],
        "operations": [
            {
                "op":   "build_node_chain",
                "spec": {
                    "intent": "vfx_container",
                    "nodes": [
                        {"id": "geo",    "parent": "{parent}", "type": "geo",    "name": "{name}_geo"},
                        {"id": "dopnet", "parent": "{parent}/{name}_geo", "type": "dopnet", "name": "{name}_dop"},
                    ],
                    "connections": [],
                    "layout": True,
                    "cook":   False,
                },
            }
        ],
    },

    # ----- Scene from assets (environment assembly) -------------------------
    {
        "template_id": "scene_from_assets",
        "description":  "Build a complete scene from real Megascans assets: intent → catalog search → structural routing → semantic layout → Houdini placement.",
        "required_capabilities": ["build_node_chain"],
        "tags": ["environment", "assets", "scene", "layout", "megascans", "structural_routing"],
        "estimated_cost": {"memory_impact": 0.5, "cook_cost": 0.4, "risk_level": "low"},
        "constraints": [],
        "variables": {
            "intent":        "Natural-language scene description (e.g. 'western saloon with table and chairs')",
            "top_k":         "Maximum number of assets to import (default 10)",
            "parent":        "Houdini parent path for imported assets (default '/obj')",
            "environment":   "Target environment type (e.g. 'western_room', 'saloon', 'castle_hall')",
            "room_half_width": "Half-width of the scene bounding box in metres (default 5.0)",
        },
        "operations": [
            {
                "op":   "build_node_chain",
                "spec": {
                    "intent": "scene_from_assets",
                    "tool":   "build_scene_from_assets",
                    "args": {
                        "intent":          "{intent}",
                        "top_k":           "{top_k}",
                        "parent":          "{parent}",
                        "environment":     "{environment}",
                        "room_half_width": "{room_half_width}",
                    },
                    "notes": "Runs the full Tier 12.8 → 10.3.5 → 9.8 → 9.9 pipeline. Do NOT use primitive geometry nodes for this intent.",
                },
            }
        ],
    },

    # ----- Solaris lighting setup -------------------------------------------
    {
        "template_id": "solaris_lighting_setup",
        "description":  "Add a standard three-point USD lighting rig in the /stage network.",
        "required_capabilities": ["build_node_chain"],
        "tags": ["solaris", "usd", "lighting", "karma"],
        "estimated_cost": {"memory_impact": 0.1, "cook_cost": 0.1, "risk_level": "low"},
        "constraints": [],
        "operations": [
            {
                "op":   "build_node_chain",
                "spec": {
                    "intent": "solaris_lighting_setup",
                    "nodes": [
                        {"id": "key",  "parent": "{stage_path}", "type": "distantlight", "name": "{name}_key",
                         "params": {"intensity": "5.0", "angle": "45"}},
                        {"id": "fill", "parent": "{stage_path}", "type": "distantlight", "name": "{name}_fill",
                         "params": {"intensity": "2.0", "angle": "-45"}},
                        {"id": "rim",  "parent": "{stage_path}", "type": "distantlight", "name": "{name}_rim",
                         "params": {"intensity": "3.0", "angle": "180"}},
                    ],
                    "connections": [],
                    "layout": True,
                    "cook":   False,
                },
            }
        ],
    },
]


# ---------------------------------------------------------------------------
# Variable interpolation
# ---------------------------------------------------------------------------

def _interpolate(obj: Any, context: Dict[str, Any]) -> Any:
    """Recursively substitute {varname} in all string values.

    Raises:
        KeyError: If a {varname} placeholder has no corresponding key in context.
    """
    if isinstance(obj, str):
        # format_map raises KeyError for missing keys (desired behaviour)
        return obj.format_map({k: str(v) for k, v in context.items()})
    if isinstance(obj, dict):
        return {k: _interpolate(v, context) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_interpolate(item, context) for item in obj]
    return obj


# ---------------------------------------------------------------------------
# Registry class
# ---------------------------------------------------------------------------

class WorkflowTemplates:
    def __init__(self):
        self._lock = threading.Lock()
        self._templates: Dict[str, Dict[str, Any]] = {}
        self._load_builtins()

    def _load_builtins(self) -> None:
        for t in _BUILTIN_TEMPLATES:
            self._templates[t["template_id"]] = copy.deepcopy(t)

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_template(self, template: Dict[str, Any]) -> None:
        """Register or replace a workflow template.

        The template dict must include "template_id" and "operations".
        """
        if not isinstance(template, dict):
            raise ValueError("template must be a dict")
        tid = template.get("template_id")
        if not tid:
            raise ValueError("template must have 'template_id'")
        if "operations" not in template:
            raise ValueError("template must have 'operations'")
        with self._lock:
            self._templates[tid] = copy.deepcopy(template)

    def deregister_template(self, template_id: str) -> bool:
        """Remove a template. Returns True if found."""
        with self._lock:
            if template_id in self._templates:
                del self._templates[template_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        """Return a deep copy of the template dict, or None."""
        with self._lock:
            t = self._templates.get(template_id)
            return copy.deepcopy(t) if t else None

    def list_templates(self, tag: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return all templates, optionally filtered by tag.

        Returns copies sorted by template_id.
        """
        with self._lock:
            templates = [copy.deepcopy(t) for t in self._templates.values()]
        if tag:
            templates = [t for t in templates if tag in t.get("tags", [])]
        return sorted(templates, key=lambda t: t["template_id"])

    # ------------------------------------------------------------------
    # Application
    # ------------------------------------------------------------------

    def apply_template(self, template_id: str, context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Resolve template operations with variable substitution.

        Args:
            template_id: The template to apply.
            context:     Dict of variable values for {varname} substitution.

        Returns:
            List of concrete operation dicts (deep-copied, interpolated).

        Raises:
            KeyError: Template not found, or a {varname} has no value in context.
            ValueError: Template or context has wrong shape.
        """
        context = dict(context or {})

        with self._lock:
            template = self._templates.get(template_id)
            if template is None:
                raise KeyError(f"Workflow template not found: {template_id!r}")
            ops_raw = copy.deepcopy(template["operations"])

        # Interpolate
        try:
            return _interpolate(ops_raw, context)
        except KeyError as exc:
            raise KeyError(
                f"Template '{template_id}' requires variable {exc} in context. "
                f"Provided keys: {sorted(context.keys())}"
            ) from exc


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_TEMPLATES: Optional[WorkflowTemplates] = None
_LOCK = threading.Lock()


def get_workflow_templates() -> WorkflowTemplates:
    global _TEMPLATES
    with _LOCK:
        if _TEMPLATES is None:
            _TEMPLATES = WorkflowTemplates()
        return _TEMPLATES


def reset_workflow_templates_for_tests() -> None:
    global _TEMPLATES
    with _LOCK:
        _TEMPLATES = None
