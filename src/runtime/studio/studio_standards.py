"""Studio-approved production standards (Tier 11 — §31).

Stores production conventions that every project must follow.
Built-in standards are pre-loaded and cannot be removed (but their
values can be overridden via update_standard).

No persistence — standards are code-defined.  Custom standards can
be registered at runtime per session.
"""

import threading
import time
from typing import Any, Dict, List, Optional

_module_lock = threading.Lock()
_instance: Optional["StudioStandards"] = None

# Built-in production standards — immutable set, overridable values
_BUILTIN_STANDARDS: Dict[str, Dict[str, Any]] = {
    "minimum_review_score": {
        "id": "minimum_review_score",
        "category": "review_threshold",
        "value": 0.75,
        "description": "Minimum production review score for approval.",
        "required": True,
        "builtin": True,
    },
    "minimum_readability_score": {
        "id": "minimum_readability_score",
        "category": "review_threshold",
        "value": 0.60,
        "description": "Minimum scene readability score.",
        "required": True,
        "builtin": True,
    },
    "approved_lighting_styles": {
        "id": "approved_lighting_styles",
        "category": "lighting",
        "value": [
            "cinematic_industrial",
            "cold_scifi",
            "warm_control_room",
            "bladerunner_noir",
            "atmospheric_lab",
        ],
        "description": "Studio-approved lighting presets.",
        "required": False,
        "builtin": True,
    },
    "approved_camera_modes": {
        "id": "approved_camera_modes",
        "category": "camera",
        "value": [
            "cinematic_push_in",
            "orbital_reveal",
            "hero_focus",
            "atmospheric_tracking",
            "handheld_subtle",
        ],
        "description": "Studio-approved camera modes.",
        "required": False,
        "builtin": True,
    },
    "approved_atmosphere_types": {
        "id": "approved_atmosphere_types",
        "category": "atmosphere",
        "value": [
            "industrial_fog",
            "volumetric_scifi",
            "dusty_hangar",
            "cold_atmosphere",
            "cinematic_depth_fog",
        ],
        "description": "Studio-approved atmosphere presets.",
        "required": False,
        "builtin": True,
    },
    "hero_zone_max_assets": {
        "id": "hero_zone_max_assets",
        "category": "environment_quality",
        "value": 3,
        "description": "Maximum assets in hero zone for readability.",
        "required": True,
        "builtin": True,
    },
    "naming_convention": {
        "id": "naming_convention",
        "category": "naming",
        "value": "snake_case",
        "description": "Asset and node naming convention.",
        "required": False,
        "builtin": True,
    },
    "approved_workflows": {
        "id": "approved_workflows",
        "category": "workflow",
        "value": [
            "industrial_hangar_pack",
            "robotics_lab_pack",
            "control_room_pack",
            "sci_fi_corridor_pack",
            "abandoned_factory_pack",
        ],
        "description": "Studio-approved WorkflowPack names.",
        "required": False,
        "builtin": True,
    },
    "minimum_production_threshold": {
        "id": "minimum_production_threshold",
        "category": "review_threshold",
        "value": 0.70,
        "description": "Minimum overall quality score for production_ready=True.",
        "required": True,
        "builtin": True,
    },
}


def get_studio_standards() -> "StudioStandards":
    global _instance
    with _module_lock:
        if _instance is None:
            _instance = StudioStandards()
    return _instance


def reset_studio_standards_for_tests() -> None:
    global _instance
    with _module_lock:
        _instance = None


class StudioStandards:
    """Registry of studio-approved production standards."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # Deep copy so mutations don't affect the module-level dict
        self._standards: Dict[str, Dict[str, Any]] = {
            k: dict(v) for k, v in _BUILTIN_STANDARDS.items()
        }
        self._update_count = 0

    # ------------------------------------------------------------------
    # Write API
    # ------------------------------------------------------------------

    def register_standard(
        self,
        standard_id: str,
        category: str,
        value: Any,
        description: str = "",
        required: bool = False,
    ) -> str:
        with self._lock:
            if (
                standard_id in self._standards
                and self._standards[standard_id].get("builtin")
            ):
                raise ValueError(f"Cannot override built-in standard via register: {standard_id!r}. Use update_standard instead.")
            self._standards[standard_id] = {
                "id": standard_id,
                "category": category,
                "value": value,
                "description": description,
                "required": required,
                "builtin": False,
                "registered_at": time.time(),
            }
            self._update_count += 1
            return standard_id

    def update_standard(
        self, standard_id: str, value: Any, description: str = ""
    ) -> bool:
        with self._lock:
            if standard_id not in self._standards:
                return False
            entry = self._standards[standard_id]
            entry["value"] = value
            if description:
                entry["description"] = description
            if entry.get("builtin"):
                entry["overridden"] = True
            self._update_count += 1
            return True

    def remove_standard(self, standard_id: str) -> bool:
        with self._lock:
            if standard_id not in self._standards:
                return False
            if self._standards[standard_id].get("builtin"):
                raise ValueError(f"Cannot remove built-in standard: {standard_id!r}")
            del self._standards[standard_id]
            self._update_count += 1
            return True

    # ------------------------------------------------------------------
    # Read API
    # ------------------------------------------------------------------

    def get_standard(self, standard_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            s = self._standards.get(standard_id)
            return dict(s) if s else None

    def get_standard_value(self, standard_id: str, default: Any = None) -> Any:
        s = self.get_standard(standard_id)
        return s["value"] if s else default

    def validate_standard(self, standard_id: str) -> Dict[str, Any]:
        with self._lock:
            s = self._standards.get(standard_id)
            if not s:
                return {"valid": False, "error": f"Standard not found: {standard_id!r}", "issues": []}
            issues: List[str] = []
            if s.get("required") and s.get("value") is None:
                issues.append(f"Required standard '{standard_id}' has no value.")
            return {"valid": len(issues) == 0, "issues": issues, "standard": dict(s)}

    def list_standards(
        self,
        category: Optional[str] = None,
        builtin_only: bool = False,
    ) -> List[Dict[str, Any]]:
        with self._lock:
            results = [
                dict(s) for s in self._standards.values()
                if (category is None or s.get("category") == category)
                and (not builtin_only or s.get("builtin"))
            ]
            return sorted(results, key=lambda s: s["id"])

    def get_all_standards(self) -> Dict[str, Any]:
        with self._lock:
            return {k: dict(v) for k, v in self._standards.items()}

    def is_approved(self, category: str, value: str) -> bool:
        """True if value appears in the studio-approved list for category."""
        mapping = {
            "lighting": "approved_lighting_styles",
            "camera": "approved_camera_modes",
            "atmosphere": "approved_atmosphere_types",
            "workflow": "approved_workflows",
        }
        std_id = mapping.get(category)
        if not std_id:
            return True
        approved = self.get_standard_value(std_id, [])
        if isinstance(approved, list):
            return value in approved
        return True

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_standards": len(self._standards),
                "builtin_count": sum(1 for s in self._standards.values() if s.get("builtin")),
                "custom_count": sum(1 for s in self._standards.values() if not s.get("builtin")),
                "update_count": self._update_count,
            }
