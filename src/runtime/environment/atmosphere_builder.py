"""
Atmosphere Builder (§44 — Structural Environment Assembly)
==========================================================
Selects and configures the atmospheric effects for an environment using one
of 8 built-in AtmosphereProfiles. Never creates Houdini nodes — produces
plan dicts for downstream execution.

DESIGN RULES:
  1. No bridge calls. No Houdini imports. Planning only.
  2. Deterministic — same environment always yields the same atmosphere plan.
  3. Never raises — errors captured in AtmospherePlan.errors.
  4. Singleton pattern.
  5. Thread-safe.

Public API:
    AtmosphereProfile
    AtmospherePlan
    AtmosphereBuilder
    get_atmosphere_builder()
    reset_atmosphere_builder_for_tests()
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.runtime.environment.environment_template_library import get_environment_template_library


# ---------------------------------------------------------------------------
# Built-in atmosphere profiles
# ---------------------------------------------------------------------------

@dataclass
class AtmosphereProfile:
    """A named atmospheric effect profile."""

    profile_name: str = ""
    description: str = ""
    primary_effect: str = "none"      # dust / haze / smoke / fog / volumetric_light / none
    density: float = 0.0              # 0.0 – 1.0
    color_tint: str = "warm_white"    # descriptive color name or hex
    light_scattering: bool = False
    effects: List[str] = field(default_factory=list)
    recommended_environments: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "profile_name":             self.profile_name,
            "description":              self.description,
            "primary_effect":           self.primary_effect,
            "density":                  self.density,
            "color_tint":               self.color_tint,
            "light_scattering":         self.light_scattering,
            "effects":                  list(self.effects),
            "recommended_environments": list(self.recommended_environments),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AtmosphereProfile":
        return cls(
            profile_name             = str(d.get("profile_name", "")),
            description              = str(d.get("description", "")),
            primary_effect           = str(d.get("primary_effect", "none")),
            density                  = float(d.get("density", 0.0)),
            color_tint               = str(d.get("color_tint", "warm_white")),
            light_scattering         = bool(d.get("light_scattering", False)),
            effects                  = list(d.get("effects", [])),
            recommended_environments = list(d.get("recommended_environments", [])),
        )


_BUILTIN_PROFILES: List[AtmosphereProfile] = [
    AtmosphereProfile(
        profile_name="western_dust",
        description="Warm dusty atmosphere with floating dust motes and heat shimmer.",
        primary_effect="dust",
        density=0.3,
        color_tint="warm_amber",
        light_scattering=True,
        effects=["dust_motes", "heat_shimmer"],
        recommended_environments=["western_room", "saloon", "desert"],
    ),
    AtmosphereProfile(
        profile_name="industrial_haze",
        description="Cool industrial haze with oil particle suspension.",
        primary_effect="haze",
        density=0.4,
        color_tint="cool_grey",
        light_scattering=True,
        effects=["industrial_haze", "oil_particles"],
        recommended_environments=["industrial_hangar", "warehouse", "abandoned_factory"],
    ),
    AtmosphereProfile(
        profile_name="factory_smoke",
        description="Heavy factory smoke with ember sparks and steam vents.",
        primary_effect="smoke",
        density=0.6,
        color_tint="dark_grey",
        light_scattering=True,
        effects=["smoke_tendrils", "steam_vents", "ember_sparks"],
        recommended_environments=["abandoned_factory"],
    ),
    AtmosphereProfile(
        profile_name="warm_interior",
        description="Soft warm interior light with minimal dust motes.",
        primary_effect="none",
        density=0.1,
        color_tint="warm_white",
        light_scattering=False,
        effects=["dust_motes"],
        recommended_environments=["western_room", "living_room", "restaurant", "hotel_lobby", "castle_hall", "saloon"],
    ),
    AtmosphereProfile(
        profile_name="cold_interior",
        description="Clean cold interior lighting with no atmospheric effects.",
        primary_effect="none",
        density=0.0,
        color_tint="cool_white",
        light_scattering=False,
        effects=[],
        recommended_environments=["office", "control_room", "robotics_lab", "medical_lab", "research_lab", "sci_fi_corridor"],
    ),
    AtmosphereProfile(
        profile_name="sunlit",
        description="Bright outdoor sunlight with sun shafts and dust motes.",
        primary_effect="volumetric_light",
        density=0.2,
        color_tint="warm_yellow",
        light_scattering=True,
        effects=["sun_shafts", "dust_motes"],
        recommended_environments=["city_street", "desert"],
    ),
    AtmosphereProfile(
        profile_name="volumetric_light",
        description="Dense forest volumetric light with god rays and floating particles.",
        primary_effect="volumetric_light",
        density=0.3,
        color_tint="green_diffuse",
        light_scattering=True,
        effects=["god_rays", "floating_particles"],
        recommended_environments=["forest"],
    ),
    AtmosphereProfile(
        profile_name="moonlit",
        description="Cool moonlight atmosphere with subtle moonbeam shafts.",
        primary_effect="none",
        density=0.15,
        color_tint="cool_blue",
        light_scattering=False,
        effects=["moonbeam"],
        recommended_environments=["castle_hall", "city_street"],
    ),
]

_PROFILES_BY_NAME: Dict[str, AtmosphereProfile] = {p.profile_name: p for p in _BUILTIN_PROFILES}

# Environment → preferred profile name
_ENV_PROFILE_MAP: Dict[str, str] = {}
for _prof in _BUILTIN_PROFILES:
    for _env in _prof.recommended_environments:
        if _env not in _ENV_PROFILE_MAP:  # first match wins
            _ENV_PROFILE_MAP[_env] = _prof.profile_name


# ---------------------------------------------------------------------------
# AtmospherePlan
# ---------------------------------------------------------------------------

@dataclass
class AtmospherePlan:
    """The atmospheric configuration for an environment."""

    environment_name: str = ""
    profile: Optional[AtmosphereProfile] = None
    active_effects: List[str] = field(default_factory=list)
    volumetric_enabled: bool = False
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "environment_name":  self.environment_name,
            "profile":           self.profile.to_dict() if self.profile else {},
            "active_effects":    list(self.active_effects),
            "volumetric_enabled": self.volumetric_enabled,
            "errors":            list(self.errors),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AtmospherePlan":
        prof_raw = d.get("profile", {})
        prof = AtmosphereProfile.from_dict(prof_raw) if prof_raw else None
        return cls(
            environment_name  = str(d.get("environment_name", "")),
            profile           = prof,
            active_effects    = list(d.get("active_effects", [])),
            volumetric_enabled = bool(d.get("volumetric_enabled", False)),
            errors            = list(d.get("errors", [])),
        )


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

class AtmosphereBuilder:
    """Select and configure atmosphere for an environment."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def build_atmosphere(
        self,
        environment_name: str,
        profile_name: Optional[str] = None,
    ) -> AtmospherePlan:
        """Build the atmosphere plan.

        Args:
            environment_name: Canonical environment name.
            profile_name: Override the default profile. If not given, the
                          profile is inferred from the environment's blueprint
                          atmosphere_profile field or the environment map.

        Returns:
            AtmospherePlan — never raises.
        """
        with self._lock:
            try:
                return self._build(environment_name, profile_name)
            except Exception as exc:
                return AtmospherePlan(
                    environment_name = environment_name,
                    errors           = [f"Atmosphere build error: {exc}"],
                )

    def _build(
        self,
        environment_name: str,
        profile_name: Optional[str],
    ) -> AtmospherePlan:
        key = (environment_name or "").strip().lower()

        # Resolve profile name
        if not profile_name:
            # Try template library first
            lib = get_environment_template_library()
            tmpl = lib.get_template(key)
            profile_name = tmpl.atmosphere_profile

        # Fall back to env map, then warm_interior
        if not profile_name or profile_name not in _PROFILES_BY_NAME:
            profile_name = _ENV_PROFILE_MAP.get(key, "warm_interior")

        profile = _PROFILES_BY_NAME.get(profile_name)
        if profile is None:
            return AtmospherePlan(
                environment_name = environment_name,
                errors           = [f"Unknown atmosphere profile: {profile_name!r}"],
            )

        volumetric = profile.primary_effect == "volumetric_light" or profile.light_scattering

        return AtmospherePlan(
            environment_name  = environment_name,
            profile           = profile,
            active_effects    = list(profile.effects),
            volumetric_enabled = volumetric,
            errors            = [],
        )

    def recommend_effects(self, environment_name: str) -> List[str]:
        """Return the recommended effects for the environment."""
        plan = self.build_atmosphere(environment_name)
        return list(plan.active_effects)

    def get_profile(self, profile_name: str) -> Optional[AtmosphereProfile]:
        """Return a named profile, or None if not found."""
        return _PROFILES_BY_NAME.get(profile_name)

    def list_profiles(self) -> List[str]:
        """Return all built-in profile names."""
        return sorted(_PROFILES_BY_NAME.keys())


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[AtmosphereBuilder] = None
_LOCK = threading.Lock()


def get_atmosphere_builder() -> AtmosphereBuilder:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = AtmosphereBuilder()
        return _INSTANCE


def reset_atmosphere_builder_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
