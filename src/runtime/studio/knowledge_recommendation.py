"""Studio-knowledge-driven production recommendations (Tier 11 — §31).

Priority chain for every recommendation:
  1. Studio Standards   (confidence 0.90)
  2. Cross-Project Learning / StudioKnowledgeDB (confidence 0.85)
  3. Production Memory  (confidence 0.80)
  4. Pattern Library    (confidence 0.70)
  5. Built-in defaults  (confidence 0.50)

All failures are silently caught — recommendations always return a result.
"""

import threading
from typing import Any, Dict, List, Optional

_module_lock = threading.Lock()
_instance: Optional["KnowledgeRecommendationEngine"] = None

# Default fallbacks when no knowledge source has data
_DEFAULT_WORKFLOWS: Dict[str, str] = {
    "industrial_hangar": "industrial_hangar_pack",
    "robotics_lab": "robotics_lab_pack",
    "control_room": "control_room_pack",
    "sci_fi_corridor": "sci_fi_corridor_pack",
    "abandoned_factory": "abandoned_factory_pack",
}
_DEFAULT_LIGHTING: Dict[str, str] = {
    "industrial_hangar": "cinematic_industrial",
    "robotics_lab": "cold_scifi",
    "control_room": "warm_control_room",
    "sci_fi_corridor": "bladerunner_noir",
    "abandoned_factory": "atmospheric_lab",
}
_DEFAULT_CAMERA: Dict[str, str] = {
    "industrial_hangar": "cinematic_push_in",
    "robotics_lab": "orbital_reveal",
    "control_room": "hero_focus",
    "sci_fi_corridor": "atmospheric_tracking",
    "abandoned_factory": "handheld_subtle",
}
_DEFAULT_ATMOSPHERE: Dict[str, str] = {
    "industrial_hangar": "industrial_fog",
    "robotics_lab": "volumetric_scifi",
    "control_room": "cinematic_depth_fog",
    "sci_fi_corridor": "cold_atmosphere",
    "abandoned_factory": "dusty_hangar",
}


def get_knowledge_recommendation_engine() -> "KnowledgeRecommendationEngine":
    global _instance
    with _module_lock:
        if _instance is None:
            _instance = KnowledgeRecommendationEngine()
    return _instance


def reset_knowledge_recommendation_engine_for_tests() -> None:
    global _instance
    with _module_lock:
        _instance = None


class KnowledgeRecommendationEngine:
    """Recommends production strategies using the studio knowledge priority chain."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._recommendation_count = 0

    def _inc(self) -> None:
        with self._lock:
            self._recommendation_count += 1

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------

    def recommend_workflow(
        self, environment: str, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        self._inc()

        # 1. Studio Standards
        try:
            from src.runtime.studio.studio_standards import get_studio_standards
            approved = get_studio_standards().get_standard_value("approved_workflows", [])
            if isinstance(approved, list):
                for wf in approved:
                    if environment.lower().replace(" ", "_") in wf.lower():
                        return {
                            "recommended_workflow": wf,
                            "confidence": 0.90,
                            "source": "studio_standards",
                            "reason": "Studio-approved workflow for environment",
                        }
        except Exception:
            pass

        # 2. Cross-project learning
        try:
            from src.runtime.studio.studio_knowledge import get_studio_knowledge_db
            successes = get_studio_knowledge_db().get_studio_successes(
                environment=environment, min_score=0.7, limit=10
            )
            if successes:
                wf = successes[0].get("workflow", "")
                if wf:
                    return {
                        "recommended_workflow": wf,
                        "confidence": 0.85,
                        "source": "cross_project_learning",
                        "reason": f"Highest-scoring workflow for {environment} across projects",
                    }
        except Exception:
            pass

        # 3. Production Memory
        try:
            from src.runtime.production_memory import get_production_memory
            history = get_production_memory().get_scene_history(
                scene_type=environment, status="success", limit=10
            )
            if history:
                wf = history[0].get("workflow") or history[0].get("pack_name", "")
                if wf:
                    return {
                        "recommended_workflow": wf,
                        "confidence": 0.80,
                        "source": "production_memory",
                        "reason": f"Historically successful workflow for {environment}",
                    }
        except Exception:
            pass

        # 4. Pattern Library
        try:
            from src.runtime.pattern_library import get_pattern_library
            patterns = get_pattern_library().search_patterns(
                scene_type=environment, pattern_type="scene_pattern"
            )
            if patterns:
                wf = patterns[0].get("pattern_id", "")
                if wf:
                    return {
                        "recommended_workflow": wf,
                        "confidence": 0.70,
                        "source": "pattern_library",
                        "reason": f"Proven pattern for {environment}",
                    }
        except Exception:
            pass

        # 5. Default
        default = _DEFAULT_WORKFLOWS.get(environment)
        return {
            "recommended_workflow": default,
            "confidence": 0.50,
            "source": "default",
            "reason": f"Default workflow for {environment}",
        }

    # ------------------------------------------------------------------
    # Lighting
    # ------------------------------------------------------------------

    def recommend_lighting(
        self, environment: str, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        self._inc()
        env_default = _DEFAULT_LIGHTING.get(environment)

        try:
            from src.runtime.studio.studio_standards import get_studio_standards
            approved = get_studio_standards().get_standard_value("approved_lighting_styles", [])
            if isinstance(approved, list) and env_default and env_default in approved:
                return {
                    "recommended_lighting": env_default,
                    "confidence": 0.90,
                    "source": "studio_standards",
                    "reason": "Studio-approved lighting for environment",
                }
        except Exception:
            pass

        try:
            from src.runtime.studio.cross_project_learning import get_cross_project_learning
            from src.runtime.studio.studio_knowledge import get_studio_knowledge_db
            successes = get_studio_knowledge_db().get_studio_successes(
                environment=environment, min_score=0.7, limit=20
            )
            best = get_cross_project_learning().extract_best_lighting(successes)
            if best:
                return {
                    "recommended_lighting": best,
                    "confidence": 0.85,
                    "source": "cross_project_learning",
                    "reason": f"Highest-scoring lighting for {environment}",
                }
        except Exception:
            pass

        return {
            "recommended_lighting": env_default,
            "confidence": 0.50,
            "source": "default",
            "reason": f"Default lighting for {environment}",
        }

    # ------------------------------------------------------------------
    # Camera
    # ------------------------------------------------------------------

    def recommend_camera(
        self, environment: str, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        self._inc()
        env_default = _DEFAULT_CAMERA.get(environment)

        try:
            from src.runtime.studio.studio_standards import get_studio_standards
            approved = get_studio_standards().get_standard_value("approved_camera_modes", [])
            if isinstance(approved, list) and env_default and env_default in approved:
                return {
                    "recommended_camera": env_default,
                    "confidence": 0.90,
                    "source": "studio_standards",
                    "reason": "Studio-approved camera mode for environment",
                }
        except Exception:
            pass

        return {
            "recommended_camera": env_default,
            "confidence": 0.50,
            "source": "default",
            "reason": f"Default camera mode for {environment}",
        }

    # ------------------------------------------------------------------
    # Atmosphere
    # ------------------------------------------------------------------

    def recommend_atmosphere(
        self, environment: str, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        self._inc()
        env_default = _DEFAULT_ATMOSPHERE.get(environment)

        try:
            from src.runtime.studio.studio_standards import get_studio_standards
            approved = get_studio_standards().get_standard_value("approved_atmosphere_types", [])
            if isinstance(approved, list) and env_default and env_default in approved:
                return {
                    "recommended_atmosphere": env_default,
                    "confidence": 0.90,
                    "source": "studio_standards",
                    "reason": "Studio-approved atmosphere for environment",
                }
        except Exception:
            pass

        return {
            "recommended_atmosphere": env_default,
            "confidence": 0.50,
            "source": "default",
            "reason": f"Default atmosphere for {environment}",
        }

    # ------------------------------------------------------------------
    # Environment
    # ------------------------------------------------------------------

    def recommend_environment(self, intent: str) -> Dict[str, Any]:
        self._inc()
        intent_lower = intent.lower()
        for env in _DEFAULT_WORKFLOWS:
            if env.replace("_", " ") in intent_lower or env in intent_lower:
                return {
                    "recommended_environment": env,
                    "confidence": 0.85,
                    "source": "keyword_match",
                    "reason": f"Keyword match: {env!r} found in intent",
                }
        return {
            "recommended_environment": "industrial_hangar",
            "confidence": 0.30,
            "source": "fallback",
            "reason": "No environment keyword matched — using industrial_hangar as default",
        }

    # ------------------------------------------------------------------
    # Full production strategy
    # ------------------------------------------------------------------

    def recommend_production_strategy(
        self, environment: str, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Combined recommendation: workflow + lighting + camera + atmosphere."""
        wf  = self.recommend_workflow(environment, context)
        lt  = self.recommend_lighting(environment, context)
        cam = self.recommend_camera(environment, context)
        atm = self.recommend_atmosphere(environment, context)

        overall = (
            wf["confidence"] * 0.4
            + lt["confidence"] * 0.2
            + cam["confidence"] * 0.2
            + atm["confidence"] * 0.2
        )

        return {
            "environment": environment,
            "workflow": wf,
            "lighting": lt,
            "camera": cam,
            "atmosphere": atm,
            "overall_confidence": round(overall, 3),
            "production_ready": overall >= 0.7,
        }

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {"recommendation_count": self._recommendation_count}
