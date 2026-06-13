"""
Lighting Environment Mapper (Tier 15)
======================================
Determines lighting requirements by environment type.
Deterministic, thread-safe, no Houdini dependency.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_ENVIRONMENT_PROFILES: Dict[str, Dict[str, Any]] = {
    "industrial_hangar": {
        "recommended_sources": ["industrial_fixture", "window_light", "bounce_light"],
        "volumetrics":         True,
        "exposure_ev":         0.0,
        "contrast":            "high",
        "mood_hints":          ["industrial", "gritty"],
        "color_temperature":   "cool",
        "notes":               "High-bay overhead fixtures dominate. Add volumetric haze for scale.",
    },
    "robotics_lab": {
        "recommended_sources": ["industrial_fixture", "fill_light", "neon_source"],
        "volumetrics":         False,
        "exposure_ev":         0.5,
        "contrast":            "medium",
        "mood_hints":          ["clinical", "tense"],
        "color_temperature":   "cool",
        "notes":               "Clean clinical light. Screen practicals as warm accents. High fill.",
    },
    "control_room": {
        "recommended_sources": ["motivated_light", "atmospheric_light", "neon_source"],
        "volumetrics":         False,
        "exposure_ev":         -0.5,
        "contrast":            "high",
        "mood_hints":          ["tense", "dramatic"],
        "color_temperature":   "cool",
        "notes":               "Screen glow dominates. Minimal ambient. High contrast from monitor banks.",
    },
    "sci_fi_corridor": {
        "recommended_sources": ["neon_source", "atmospheric_light", "rim_light"],
        "volumetrics":         True,
        "exposure_ev":         -1.0,
        "contrast":            "high",
        "mood_hints":          ["dramatic", "cinematic"],
        "color_temperature":   "cool",
        "notes":               "Neon color key. Thin volumetric. Strong rim for silhouette in tunnel.",
    },
    "abandoned_factory": {
        "recommended_sources": ["window_light", "bounce_light", "atmospheric_light"],
        "volumetrics":         True,
        "exposure_ev":         -2.0,
        "contrast":            "high",
        "mood_hints":          ["tense", "industrial"],
        "color_temperature":   "warm",
        "notes":               "Single shaft window. Heavy dust motes. No electric lights. Deep shadows.",
    },
    "night_exterior": {
        "recommended_sources": ["moonlight", "atmospheric_light", "practical_light"],
        "volumetrics":         True,
        "exposure_ev":         -2.5,
        "contrast":            "high",
        "mood_hints":          ["cinematic", "dangerous"],
        "color_temperature":   "cool",
        "notes":               "Moonlight key. Cool ambient. Street practicals as warm accent pops.",
    },
    "dramatic_interior": {
        "recommended_sources": ["key_light", "fill_light", "rim_light"],
        "volumetrics":         False,
        "exposure_ev":         0.0,
        "contrast":            "high",
        "mood_hints":          ["dramatic", "cinematic"],
        "color_temperature":   "warm",
        "notes":               "Three-point setup. Warm key. 4:1 ratio. Strong rim.",
    },
    "hero_reveal": {
        "recommended_sources": ["key_light", "rim_light", "fill_light"],
        "volumetrics":         False,
        "exposure_ev":         0.5,
        "contrast":            "high",
        "mood_hints":          ["cinematic", "dramatic"],
        "color_temperature":   "warm",
        "notes":               "Expose for hero subject. Extra rim intensity for separation.",
    },
    # -----------------------------------------------------------------------
    # §39 Industrial
    # -----------------------------------------------------------------------
    "warehouse": {
        "recommended_sources": ["industrial_fixture", "bounce_light", "window_light"],
        "volumetrics":         True,
        "exposure_ev":         0.0,
        "contrast":            "medium",
        "mood_hints":          ["industrial", "clinical"],
        "color_temperature":   "cool",
        "notes":               "Fluorescent overhead rows. Loading dock diffuse from end. Dust particles.",
    },
    "shipyard": {
        "recommended_sources": ["window_light", "bounce_light", "atmospheric_light"],
        "volumetrics":         True,
        "exposure_ev":         -0.5,
        "contrast":            "high",
        "mood_hints":          ["industrial", "gritty"],
        "color_temperature":   "cool",
        "notes":               "Overcast exterior key. Water bounce. Sea mist volumetric.",
    },
    "oil_refinery": {
        "recommended_sources": ["motivated_light", "atmospheric_light", "practical_light"],
        "volumetrics":         True,
        "exposure_ev":         -1.0,
        "contrast":            "high",
        "mood_hints":          ["industrial", "dangerous"],
        "color_temperature":   "warm",
        "notes":               "Flare stack as warm motivated key. Chemical haze volumetric. Night ops: orange glow.",
    },
    "power_station": {
        "recommended_sources": ["industrial_fixture", "neon_source", "fill_light"],
        "volumetrics":         False,
        "exposure_ev":         0.0,
        "contrast":            "medium",
        "mood_hints":          ["industrial", "tense"],
        "color_temperature":   "cool",
        "notes":               "High-bay industrial. Warning LEDs as accent. Clean technical look.",
    },
    "mining_facility": {
        "recommended_sources": ["motivated_light", "atmospheric_light", "bounce_light"],
        "volumetrics":         True,
        "exposure_ev":         -2.0,
        "contrast":            "high",
        "mood_hints":          ["industrial", "tense"],
        "color_temperature":   "warm",
        "notes":               "Helmet lamps as primary sources. Dust particulate heavy. Deep shadows.",
    },
    "construction_site": {
        "recommended_sources": ["window_light", "bounce_light", "industrial_fixture"],
        "volumetrics":         True,
        "exposure_ev":         0.5,
        "contrast":            "medium",
        "mood_hints":          ["industrial", "hopeful"],
        "color_temperature":   "warm",
        "notes":               "Outdoor daylight key. Dust and cement haze. Crane shadows create drama.",
    },
    # -----------------------------------------------------------------------
    # §39 Scientific
    # -----------------------------------------------------------------------
    "research_lab": {
        "recommended_sources": ["industrial_fixture", "fill_light", "neon_source"],
        "volumetrics":         False,
        "exposure_ev":         0.5,
        "contrast":            "low",
        "mood_hints":          ["clinical", "hopeful"],
        "color_temperature":   "cool",
        "notes":               "Cool flat fluorescents. Task lighting on benches. Instrument glow accents.",
    },
    "medical_lab": {
        "recommended_sources": ["industrial_fixture", "motivated_light", "fill_light"],
        "volumetrics":         False,
        "exposure_ev":         1.0,
        "contrast":            "low",
        "mood_hints":          ["clinical", "tense"],
        "color_temperature":   "cool",
        "notes":               "Surgical overhead as directional key. Very high fill ratio. Pure white clinical.",
    },
    "clean_room": {
        "recommended_sources": ["industrial_fixture", "fill_light"],
        "volumetrics":         False,
        "exposure_ev":         1.5,
        "contrast":            "low",
        "mood_hints":          ["clinical"],
        "color_temperature":   "cool",
        "notes":               "Near-shadowless diffuse. Yellow spectrum for cleanroom (photolithography). Pure flat.",
    },
    "biohazard_facility": {
        "recommended_sources": ["motivated_light", "atmospheric_light", "neon_source"],
        "volumetrics":         False,
        "exposure_ev":         -0.5,
        "contrast":            "high",
        "mood_hints":          ["dangerous", "tense"],
        "color_temperature":   "cool",
        "notes":               "Warning red accents. Clinical overhead. Emergency lighting adds danger.",
    },
    # -----------------------------------------------------------------------
    # §39 Military
    # -----------------------------------------------------------------------
    "military_base": {
        "recommended_sources": ["industrial_fixture", "window_light", "atmospheric_light"],
        "volumetrics":         False,
        "exposure_ev":         0.5,
        "contrast":            "high",
        "mood_hints":          ["industrial", "tense"],
        "color_temperature":   "cool",
        "notes":               "Harsh exterior midday or floodlight night. No softening — military precision.",
    },
    "command_center": {
        "recommended_sources": ["motivated_light", "neon_source", "atmospheric_light"],
        "volumetrics":         False,
        "exposure_ev":         -1.0,
        "contrast":            "high",
        "mood_hints":          ["tense", "dramatic"],
        "color_temperature":   "cool",
        "notes":               "Map table as practical. Screens as fill. Low ambient for drama and focus.",
    },
    "military_hangar": {
        "recommended_sources": ["industrial_fixture", "window_light", "atmospheric_light"],
        "volumetrics":         True,
        "exposure_ev":         0.0,
        "contrast":            "high",
        "mood_hints":          ["industrial", "cinematic"],
        "color_temperature":   "cool",
        "notes":               "High-bay overhead. Aircraft silhouette against back light. Exhaust haze.",
    },
    "checkpoint": {
        "recommended_sources": ["motivated_light", "atmospheric_light", "practical_light"],
        "volumetrics":         True,
        "exposure_ev":         -1.5,
        "contrast":            "high",
        "mood_hints":          ["tense", "dangerous"],
        "color_temperature":   "cool",
        "notes":               "Searchlight as key. Amber warning lights as accents. Night dust haze.",
    },
    "bunker": {
        "recommended_sources": ["practical_light", "atmospheric_light", "motivated_light"],
        "volumetrics":         False,
        "exposure_ev":         -2.0,
        "contrast":            "high",
        "mood_hints":          ["tense", "dangerous"],
        "color_temperature":   "warm",
        "notes":               "Bare bulb practicals. Emergency red. Flicker adds tension. Very low fill.",
    },
    # -----------------------------------------------------------------------
    # §39 Sci-Fi
    # -----------------------------------------------------------------------
    "space_station": {
        "recommended_sources": ["industrial_fixture", "fill_light", "neon_source"],
        "volumetrics":         False,
        "exposure_ev":         0.0,
        "contrast":            "medium",
        "mood_hints":          ["clinical", "cinematic"],
        "color_temperature":   "cool",
        "notes":               "Panel motivated key. Blue neon rim. No atmosphere — clean space station look.",
    },
    "spaceship_bridge": {
        "recommended_sources": ["motivated_light", "neon_source", "atmospheric_light"],
        "volumetrics":         False,
        "exposure_ev":         -0.5,
        "contrast":            "high",
        "mood_hints":          ["cinematic", "dramatic"],
        "color_temperature":   "cool",
        "notes":               "Star-field glow as back key. Console practicals. Strong blue rim for silhouette.",
    },
    "engineering_bay": {
        "recommended_sources": ["motivated_light", "atmospheric_light", "neon_source"],
        "volumetrics":         True,
        "exposure_ev":         -1.0,
        "contrast":            "high",
        "mood_hints":          ["industrial", "tense"],
        "color_temperature":   "warm",
        "notes":               "Core glow as warm motivated key. Emergency amber. Plasma volumetric.",
    },
    "alien_facility": {
        "recommended_sources": ["motivated_light", "atmospheric_light", "neon_source"],
        "volumetrics":         True,
        "exposure_ev":         -1.5,
        "contrast":            "high",
        "mood_hints":          ["dangerous", "mystical"],
        "color_temperature":   "cool",
        "notes":               "Bioluminescent elements as key. Eerie cool fill. Alien mist volumetric.",
    },
    "cyberpunk_city": {
        "recommended_sources": ["neon_source", "atmospheric_light", "motivated_light"],
        "volumetrics":         True,
        "exposure_ev":         -1.5,
        "contrast":            "high",
        "mood_hints":          ["cinematic", "dramatic"],
        "color_temperature":   "cool",
        "notes":               "Neon sources compete as multiple keys. Rain sheen reflections. Heavy volumetric city haze.",
    },
    # -----------------------------------------------------------------------
    # §39 Urban
    # -----------------------------------------------------------------------
    "city_street": {
        "recommended_sources": ["motivated_light", "atmospheric_light", "practical_light"],
        "volumetrics":         True,
        "exposure_ev":         -0.5,
        "contrast":            "medium",
        "mood_hints":          ["cinematic", "dramatic"],
        "color_temperature":   "warm",
        "notes":               "Street lamps as warm practicals. City smog volumetric. Golden hour: warm fill.",
    },
    "alleyway": {
        "recommended_sources": ["motivated_light", "atmospheric_light", "neon_source"],
        "volumetrics":         True,
        "exposure_ev":         -2.0,
        "contrast":            "high",
        "mood_hints":          ["dangerous", "tense"],
        "color_temperature":   "cool",
        "notes":               "Spill light from street. Neon bounce from nearby signs. Deep shadows fill the alley.",
    },
    "subway_station": {
        "recommended_sources": ["industrial_fixture", "motivated_light", "atmospheric_light"],
        "volumetrics":         False,
        "exposure_ev":         -0.5,
        "contrast":            "high",
        "mood_hints":          ["industrial", "tense"],
        "color_temperature":   "cool",
        "notes":               "Flickering fluorescents. Train headlight as motivated key. Tunnel darkness beyond.",
    },
    "parking_garage": {
        "recommended_sources": ["industrial_fixture", "motivated_light", "atmospheric_light"],
        "volumetrics":         False,
        "exposure_ev":         -1.0,
        "contrast":            "high",
        "mood_hints":          ["tense", "dangerous"],
        "color_temperature":   "cool",
        "notes":               "Harsh overhead fluorescents. Headlight practicals. Deep column shadows.",
    },
    "rooftop": {
        "recommended_sources": ["window_light", "atmospheric_light", "practical_light"],
        "volumetrics":         True,
        "exposure_ev":         0.5,
        "contrast":            "medium",
        "mood_hints":          ["cinematic", "hopeful"],
        "color_temperature":   "warm",
        "notes":               "Open sky as key. Golden hour recommended. City glow at night fills horizon.",
    },
    "shopping_mall": {
        "recommended_sources": ["window_light", "industrial_fixture", "motivated_light"],
        "volumetrics":         False,
        "exposure_ev":         0.5,
        "contrast":            "low",
        "mood_hints":          ["hopeful", "clinical"],
        "color_temperature":   "warm",
        "notes":               "Skylight as natural key. Retail warm fill. High brightness consumer atmosphere.",
    },
    # -----------------------------------------------------------------------
    # §39 Interior
    # -----------------------------------------------------------------------
    "western_room": {
        "recommended_sources": ["practical_light", "bounce_light", "atmospheric_light"],
        "volumetrics":         False,
        "exposure_ev":         -1.0,
        "contrast":            "medium",
        "mood_hints":          ["dramatic", "cinematic"],
        "color_temperature":   "warm",
        "notes":               "Oil lanterns as warm practicals. Fireplace as secondary. Low fill for era authenticity.",
    },
    "saloon": {
        "recommended_sources": ["practical_light", "motivated_light", "atmospheric_light"],
        "volumetrics":         False,
        "exposure_ev":         -0.5,
        "contrast":            "medium",
        "mood_hints":          ["dramatic", "cinematic"],
        "color_temperature":   "warm",
        "notes":               "Kerosene lanterns cluster. Window daylight from front. Warm amber throughout.",
    },
    "living_room": {
        "recommended_sources": ["practical_light", "window_light", "fill_light"],
        "volumetrics":         False,
        "exposure_ev":         0.0,
        "contrast":            "low",
        "mood_hints":          ["hopeful"],
        "color_temperature":   "warm",
        "notes":               "Table lamps as practicals. Window as secondary. Fireplace adds warm accent.",
    },
    "office": {
        "recommended_sources": ["industrial_fixture", "window_light", "fill_light"],
        "volumetrics":         False,
        "exposure_ev":         0.5,
        "contrast":            "low",
        "mood_hints":          ["clinical", "tense"],
        "color_temperature":   "cool",
        "notes":               "Fluorescent overhead. Window as natural supplemental. Flat corporate lighting.",
    },
    "hotel_lobby": {
        "recommended_sources": ["practical_light", "motivated_light", "fill_light"],
        "volumetrics":         False,
        "exposure_ev":         0.5,
        "contrast":            "low",
        "mood_hints":          ["hopeful", "cinematic"],
        "color_temperature":   "warm",
        "notes":               "Chandelier as grand key. Pendant fill. Warm luxury tone throughout.",
    },
    "restaurant": {
        "recommended_sources": ["practical_light", "motivated_light", "atmospheric_light"],
        "volumetrics":         False,
        "exposure_ev":         -0.5,
        "contrast":            "medium",
        "mood_hints":          ["cinematic", "hopeful"],
        "color_temperature":   "warm",
        "notes":               "Candle practicals per table. Pendant key. Warm amber fill for intimacy.",
    },
    "workshop": {
        "recommended_sources": ["practical_light", "window_light", "motivated_light"],
        "volumetrics":         False,
        "exposure_ev":         0.0,
        "contrast":            "medium",
        "mood_hints":          ["industrial", "hopeful"],
        "color_temperature":   "warm",
        "notes":               "Task lamp as bench key. Window diffuse fill. Warm practical throughout.",
    },
    "library": {
        "recommended_sources": ["practical_light", "window_light", "fill_light"],
        "volumetrics":         True,
        "exposure_ev":         -0.5,
        "contrast":            "medium",
        "mood_hints":          ["hopeful", "mystical"],
        "color_temperature":   "warm",
        "notes":               "Reading lamps as practicals. Window shafts through dust. Warm scholarly tone.",
    },
    # -----------------------------------------------------------------------
    # §39 Nature
    # -----------------------------------------------------------------------
    "forest": {
        "recommended_sources": ["window_light", "atmospheric_light", "bounce_light"],
        "volumetrics":         True,
        "exposure_ev":         -0.5,
        "contrast":            "medium",
        "mood_hints":          ["hopeful", "mystical"],
        "color_temperature":   "warm",
        "notes":               "Sun shafts through canopy gaps. Green-filtered diffuse fill. Pollen volumetric.",
    },
    "jungle": {
        "recommended_sources": ["atmospheric_light", "bounce_light", "window_light"],
        "volumetrics":         True,
        "exposure_ev":         -1.0,
        "contrast":            "high",
        "mood_hints":          ["dramatic", "dangerous"],
        "color_temperature":   "warm",
        "notes":               "Dense canopy cuts light dramatically. Green cast fill. Occasional shaft breaks through.",
    },
    "desert": {
        "recommended_sources": ["motivated_light", "bounce_light", "atmospheric_light"],
        "volumetrics":         True,
        "exposure_ev":         1.5,
        "contrast":            "high",
        "mood_hints":          ["industrial", "cinematic"],
        "color_temperature":   "warm",
        "notes":               "Harsh overhead key. Bleached sand bounce as hot fill. Heat shimmer haze.",
    },
    "canyon": {
        "recommended_sources": ["motivated_light", "atmospheric_light", "bounce_light"],
        "volumetrics":         True,
        "exposure_ev":         -1.0,
        "contrast":            "high",
        "mood_hints":          ["dramatic", "cinematic"],
        "color_temperature":   "warm",
        "notes":               "Limited sky key from above. Red rock bounce as warm fill. Dust in shaft.",
    },
    "mountain": {
        "recommended_sources": ["window_light", "atmospheric_light", "bounce_light"],
        "volumetrics":         True,
        "exposure_ev":         1.0,
        "contrast":            "high",
        "mood_hints":          ["hopeful", "cinematic"],
        "color_temperature":   "cool",
        "notes":               "High altitude sun key. Snow bounce as bright fill. Cloud shadow drama.",
    },
    "coastline": {
        "recommended_sources": ["window_light", "atmospheric_light", "bounce_light"],
        "volumetrics":         True,
        "exposure_ev":         0.5,
        "contrast":            "medium",
        "mood_hints":          ["hopeful", "cinematic"],
        "color_temperature":   "cool",
        "notes":               "Open sky as key. Sea bounce as fill. Sea spray volumetric. Golden hour prime.",
    },
    "swamp": {
        "recommended_sources": ["atmospheric_light", "motivated_light", "bounce_light"],
        "volumetrics":         True,
        "exposure_ev":         -1.5,
        "contrast":            "medium",
        "mood_hints":          ["mystical", "dangerous"],
        "color_temperature":   "cool",
        "notes":               "Overcast diffuse through canopy. Green-tinted fill. Fog volumetric. Murky water bounce.",
    },
    # -----------------------------------------------------------------------
    # §39 Fantasy
    # -----------------------------------------------------------------------
    "castle_hall": {
        "recommended_sources": ["practical_light", "motivated_light", "atmospheric_light"],
        "volumetrics":         False,
        "exposure_ev":         -1.0,
        "contrast":            "high",
        "mood_hints":          ["dramatic", "mystical"],
        "color_temperature":   "warm",
        "notes":               "Torch practicals as warm key sources. Stained glass color patches. Large dramatic shadow.",
    },
    "dungeon": {
        "recommended_sources": ["practical_light", "atmospheric_light", "motivated_light"],
        "volumetrics":         False,
        "exposure_ev":         -2.5,
        "contrast":            "high",
        "mood_hints":          ["dangerous", "tense"],
        "color_temperature":   "warm",
        "notes":               "Single torch practical. Near-total darkness. Key from one side only.",
    },
    "wizard_tower": {
        "recommended_sources": ["motivated_light", "practical_light", "neon_source"],
        "volumetrics":         True,
        "exposure_ev":         -0.5,
        "contrast":            "medium",
        "mood_hints":          ["mystical", "hopeful"],
        "color_temperature":   "cool",
        "notes":               "Magical orb glow as key. Candle practicals. Arcane mist volumetric particles.",
    },
    "ancient_ruins": {
        "recommended_sources": ["window_light", "atmospheric_light", "bounce_light"],
        "volumetrics":         True,
        "exposure_ev":         -0.5,
        "contrast":            "high",
        "mood_hints":          ["mystical", "cinematic"],
        "color_temperature":   "warm",
        "notes":               "Shafts through collapsed ceiling. Ruin stone bounce. Jungle mist at edges.",
    },
    "temple": {
        "recommended_sources": ["motivated_light", "practical_light", "atmospheric_light"],
        "volumetrics":         True,
        "exposure_ev":         -0.5,
        "contrast":            "medium",
        "mood_hints":          ["mystical", "hopeful"],
        "color_temperature":   "warm",
        "notes":               "Shaft of divine light as key. Candle practicals. Incense smoke volumetric.",
    },
    # -----------------------------------------------------------------------
    # §39 Post-Apocalyptic
    # -----------------------------------------------------------------------
    "abandoned_city": {
        "recommended_sources": ["atmospheric_light", "window_light", "motivated_light"],
        "volumetrics":         True,
        "exposure_ev":         -1.0,
        "contrast":            "medium",
        "mood_hints":          ["tense", "dangerous"],
        "color_temperature":   "cool",
        "notes":               "Overcast grey key. Ash volumetric. Distant fire as motivated warm accent.",
    },
    "destroyed_highway": {
        "recommended_sources": ["atmospheric_light", "window_light", "motivated_light"],
        "volumetrics":         True,
        "exposure_ev":         -0.5,
        "contrast":            "medium",
        "mood_hints":          ["tense", "hopeful"],
        "color_temperature":   "cool",
        "notes":               "Overcast diffuse key. Distant fire accent. Ash drift volumetric.",
    },
    "ruined_industrial_site": {
        "recommended_sources": ["atmospheric_light", "motivated_light", "neon_source"],
        "volumetrics":         True,
        "exposure_ev":         -1.5,
        "contrast":            "high",
        "mood_hints":          ["dangerous", "tense"],
        "color_temperature":   "cool",
        "notes":               "Toxic green glow as motivated accent. Heavy volumetric chemical haze. Grey overcast.",
    },
    "survival_camp": {
        "recommended_sources": ["practical_light", "atmospheric_light", "motivated_light"],
        "volumetrics":         True,
        "exposure_ev":         -1.0,
        "contrast":            "medium",
        "mood_hints":          ["hopeful", "tense"],
        "color_temperature":   "warm",
        "notes":               "Campfire as hero practical. Torch perimeter. Grey overcast fill. Smoke volumetric.",
    },
}

_ENV_ALIASES: Dict[str, str] = {
    # Original environments
    "hangar":          "industrial_hangar",
    "factory":         "industrial_hangar",
    "lab":             "robotics_lab",
    "laboratory":      "research_lab",
    "control":         "control_room",
    "corridor":        "sci_fi_corridor",
    "hallway":         "sci_fi_corridor",
    "sci_fi":          "sci_fi_corridor",
    "scifi":           "sci_fi_corridor",
    "abandoned":       "abandoned_factory",
    "derelict":        "abandoned_factory",
    "night":           "night_exterior",
    "exterior":        "night_exterior",
    "interior":        "dramatic_interior",
    "room":            "dramatic_interior",
    "hero":            "hero_reveal",
    "reveal":          "hero_reveal",
    # §39 Industrial
    "warehouse":       "warehouse",
    "shipyard":        "shipyard",
    "refinery":        "oil_refinery",
    "powerstation":    "power_station",
    "mining":          "mining_facility",
    "quarry":          "mining_facility",
    "construction":    "construction_site",
    # §39 Scientific
    "research":        "research_lab",
    "medical":         "medical_lab",
    "hospital":        "medical_lab",
    "cleanroom":       "clean_room",
    "biohazard":       "biohazard_facility",
    # §39 Military
    "military":        "military_base",
    "barracks":        "military_base",
    "command":         "command_center",
    "fighter":         "military_hangar",
    "checkpoint":      "checkpoint",
    "bunker":          "bunker",
    # §39 Sci-Fi
    "orbital":         "space_station",
    "spaceship":       "spaceship_bridge",
    "starship":        "spaceship_bridge",
    "engineering":     "engineering_bay",
    "alien":           "alien_facility",
    "cyberpunk":       "cyberpunk_city",
    # §39 Urban
    "street":          "city_street",
    "alley":           "alleyway",
    "subway":          "subway_station",
    "metro":           "subway_station",
    "parking":         "parking_garage",
    "rooftop":         "rooftop",
    "mall":            "shopping_mall",
    # §39 Interior
    "western":         "western_room",
    "saloon":          "saloon",
    "living":          "living_room",
    "office":          "office",
    "lobby":           "hotel_lobby",
    "restaurant":      "restaurant",
    "dining":          "restaurant",
    "workshop":        "workshop",
    "library":         "library",
    # §39 Nature
    "forest":          "forest",
    "jungle":          "jungle",
    "desert":          "desert",
    "canyon":          "canyon",
    "mountain":        "mountain",
    "beach":           "coastline",
    "coast":           "coastline",
    "swamp":           "swamp",
    "bayou":           "swamp",
    # §39 Fantasy
    "castle":          "castle_hall",
    "dungeon":         "dungeon",
    "wizard":          "wizard_tower",
    "ruins":           "ancient_ruins",
    "temple":          "temple",
    "shrine":          "temple",
    # §39 Post-Apocalyptic
    "apocalyptic":     "abandoned_city",
    "wasteland":       "abandoned_city",
    "highway":         "destroyed_highway",
    "toxic":           "ruined_industrial_site",
    "survival":        "survival_camp",
    "camp":            "survival_camp",
}


@dataclass
class EnvironmentLightingMapping:
    environment: str = ""
    recommended_sources: List[str] = field(default_factory=list)
    volumetrics: bool = False
    exposure_ev: float = 0.0
    contrast: str = "medium"
    mood_hints: List[str] = field(default_factory=list)
    color_temperature: str = "neutral"
    notes: str = ""
    mapped_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "environment":        str(self.environment),
            "recommended_sources": list(self.recommended_sources),
            "volumetrics":         bool(self.volumetrics),
            "exposure_ev":         float(self.exposure_ev),
            "contrast":            str(self.contrast),
            "mood_hints":          list(self.mood_hints),
            "color_temperature":   str(self.color_temperature),
            "notes":               str(self.notes),
            "mapped_at":           float(self.mapped_at),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "EnvironmentLightingMapping":
        d = d if isinstance(d, dict) else {}
        return cls(
            environment=str(d.get("environment", "")),
            recommended_sources=list(d.get("recommended_sources") or []),
            volumetrics=bool(d.get("volumetrics", False)),
            exposure_ev=float(d.get("exposure_ev") or 0.0),
            contrast=str(d.get("contrast", "medium")),
            mood_hints=list(d.get("mood_hints") or []),
            color_temperature=str(d.get("color_temperature", "neutral")),
            notes=str(d.get("notes", "")),
            mapped_at=float(d.get("mapped_at") or time.time()),
        )


class LightingEnvironmentMapper:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._map_count = 0

    def _resolve_environment(self, environment: str) -> str:
        env = str(environment or "").lower().strip().replace(" ", "_")
        if env in _ENVIRONMENT_PROFILES:
            return env
        return _ENV_ALIASES.get(env, env)

    def map_environment(self, environment: str) -> EnvironmentLightingMapping:
        """Map an environment name to its lighting requirements."""
        try:
            key = self._resolve_environment(environment)
            profile = _ENVIRONMENT_PROFILES.get(key, {})
            with self._lock:
                self._map_count += 1
            if not profile:
                return EnvironmentLightingMapping(
                    environment=str(environment),
                    recommended_sources=["key_light", "fill_light", "rim_light"],
                    notes=f"Unknown environment '{environment}' — using default three-point setup.",
                )
            return EnvironmentLightingMapping(
                environment=key,
                recommended_sources=list(profile.get("recommended_sources", [])),
                volumetrics=bool(profile.get("volumetrics", False)),
                exposure_ev=float(profile.get("exposure_ev", 0.0)),
                contrast=str(profile.get("contrast", "medium")),
                mood_hints=list(profile.get("mood_hints", [])),
                color_temperature=str(profile.get("color_temperature", "neutral")),
                notes=str(profile.get("notes", "")),
            )
        except Exception as exc:
            return EnvironmentLightingMapping(
                environment=str(environment),
                notes=f"map_environment error: {exc}",
            )

    def recommend_sources(self, environment: str) -> List[str]:
        """Return the recommended lighting source concepts for the environment."""
        try:
            return self.map_environment(environment).recommended_sources
        except Exception:
            return ["key_light", "fill_light", "rim_light"]

    def recommend_volumetrics(self, environment: str) -> bool:
        """Return True if volumetrics are recommended for the environment."""
        try:
            return self.map_environment(environment).volumetrics
        except Exception:
            return False

    def recommend_exposure(self, environment: str) -> Dict[str, Any]:
        """Return exposure recommendation for the environment."""
        try:
            mapping = self.map_environment(environment)
            return {
                "exposure_ev":       mapping.exposure_ev,
                "contrast":          mapping.contrast,
                "color_temperature": mapping.color_temperature,
            }
        except Exception:
            return {"exposure_ev": 0.0, "contrast": "medium", "color_temperature": "neutral"}

    def list_environments(self) -> List[str]:
        return sorted(_ENVIRONMENT_PROFILES.keys())

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "map_calls":           self._map_count,
                "known_environments":  len(_ENVIRONMENT_PROFILES),
            }


_INSTANCE: Optional[LightingEnvironmentMapper] = None
_INSTANCE_LOCK = threading.Lock()


def get_lighting_environment_mapper() -> LightingEnvironmentMapper:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = LightingEnvironmentMapper()
    return _INSTANCE


def reset_lighting_environment_mapper_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
