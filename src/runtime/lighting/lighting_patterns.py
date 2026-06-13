"""
Lighting Patterns (Tier 15)
============================
Reusable production lighting recipes matched to environments and moods.
Deterministic, thread-safe, no Houdini dependency.
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_BUILTIN_PATTERNS: List[Dict[str, Any]] = [
    {
        "name": "industrial_hangar",
        "environment": "industrial_hangar",
        "mood": "industrial",
        "key_concept": "industrial_fixture",
        "fill_concept": "bounce_light",
        "rim_concept": "rim_light",
        "volumetrics": True,
        "description": "Heavy overhead industrial fixtures with volumetric haze and cool bounce.",
        "notes": "Use overhead key from industrial_fixture. Bounce off concrete floor. Add volumetric haze for depth.",
        "tags": ["industrial", "hangar", "overhead", "haze", "cool"],
        "color_temperature": "cool",
        "contrast": "high",
    },
    {
        "name": "robotics_lab",
        "environment": "robotics_lab",
        "mood": "clinical",
        "key_concept": "industrial_fixture",
        "fill_concept": "fill_light",
        "rim_concept": "rim_light",
        "volumetrics": False,
        "description": "Clean overhead fluorescents with screen practicals and precise rim separation.",
        "notes": "High key. Screen practicals as warm accent against cool overheads. Sharp rim.",
        "tags": ["robotics", "lab", "clean", "clinical", "screens", "cool"],
        "color_temperature": "cool",
        "contrast": "medium",
    },
    {
        "name": "control_room",
        "environment": "control_room",
        "mood": "tense",
        "key_concept": "motivated_light",
        "fill_concept": "atmospheric_light",
        "rim_concept": "neon_source",
        "volumetrics": False,
        "description": "Screen-motivated lighting with cool atmospheric fill and colored neon accents.",
        "notes": "Let screens be practicals. Cool motivated key from display bank. Subtle neon rim.",
        "tags": ["control", "screens", "monitors", "tense", "cool", "tech"],
        "color_temperature": "cool",
        "contrast": "high",
    },
    {
        "name": "sci_fi_corridor",
        "environment": "sci_fi_corridor",
        "mood": "dramatic",
        "key_concept": "neon_source",
        "fill_concept": "atmospheric_light",
        "rim_concept": "rim_light",
        "volumetrics": True,
        "description": "Neon-lit corridor with volumetric atmosphere and high contrast.",
        "notes": "Neon strips as key color source. Thin volumetric haze. Strong rim for silhouette.",
        "tags": ["sci-fi", "corridor", "neon", "volumetric", "futuristic", "dramatic"],
        "color_temperature": "cool",
        "contrast": "high",
    },
    {
        "name": "abandoned_factory",
        "environment": "abandoned_factory",
        "mood": "tense",
        "key_concept": "window_light",
        "fill_concept": "bounce_light",
        "rim_concept": "atmospheric_light",
        "volumetrics": True,
        "description": "Shaft light through broken windows, heavy dust motes, deep shadows.",
        "notes": "Single directional shaft from window. Heavy volumetric dust. No fill practicals.",
        "tags": ["abandoned", "decay", "shaft_light", "volumetric", "gritty", "tense"],
        "color_temperature": "warm",
        "contrast": "high",
    },
    {
        "name": "night_exterior",
        "environment": "night_exterior",
        "mood": "cinematic",
        "key_concept": "moonlight",
        "fill_concept": "atmospheric_light",
        "rim_concept": "rim_light",
        "volumetrics": True,
        "description": "Cool moonlit exterior with ground fog and strong rim separation.",
        "notes": "Moonlight as key (blue-cool). Subtle cool atmospheric fill. Warm practical for accent.",
        "tags": ["night", "exterior", "moonlight", "fog", "cool", "cinematic"],
        "color_temperature": "cool",
        "contrast": "high",
    },
    {
        "name": "dramatic_interior",
        "environment": "dramatic_interior",
        "mood": "dramatic",
        "key_concept": "key_light",
        "fill_concept": "fill_light",
        "rim_concept": "rim_light",
        "volumetrics": False,
        "description": "Classic Rembrandt-inspired three-point with high contrast and strong directionality.",
        "notes": "Key at 45 degrees high. Fill at 4:1 ratio. Strong warm rim. Chiaroscuro-inspired.",
        "tags": ["dramatic", "interior", "three_point", "rembrandt", "high_contrast"],
        "color_temperature": "warm",
        "contrast": "high",
    },
    {
        "name": "hero_reveal",
        "environment": "hero_reveal",
        "mood": "cinematic",
        "key_concept": "key_light",
        "fill_concept": "fill_light",
        "rim_concept": "rim_light",
        "volumetrics": False,
        "description": "Hero subject reveal: strong rim separation, motivated key, controlled fill.",
        "notes": "High rim intensity for hero separation. Warm key. Reduce fill for drama.",
        "tags": ["hero", "reveal", "character", "cinematic", "strong_rim", "separation"],
        "color_temperature": "warm",
        "contrast": "high",
    },
    # -----------------------------------------------------------------------
    # §39 Environment Expansion Pack — additional builtin patterns
    # -----------------------------------------------------------------------
    {
        "name": "western_room",
        "environment": "western_room",
        "mood": "dramatic",
        "key_concept": "practical_light",
        "fill_concept": "bounce_light",
        "rim_concept": "atmospheric_light",
        "volumetrics": False,
        "description": "Warm lantern-based illumination with low contrast and amber practicals.",
        "notes": "Oil lanterns as key practicals. Warm bounce off wooden walls. Minimal fill for drama.",
        "tags": ["western", "warm", "lantern", "amber", "low_contrast", "rustic"],
        "color_temperature": "warm",
        "contrast": "low",
    },
    {
        "name": "space_station",
        "environment": "space_station",
        "mood": "clinical",
        "key_concept": "industrial_fixture",
        "fill_concept": "fill_light",
        "rim_concept": "neon_source",
        "volumetrics": False,
        "description": "Cool panel-motivated lighting with high readability and blue accent sources.",
        "notes": "Panel practicals as fill key. Cool white overhead. Blue rim from viewport glow.",
        "tags": ["space", "cool", "panel", "technical", "blue_accent", "orbital"],
        "color_temperature": "cool",
        "contrast": "medium",
    },
    {
        "name": "forest",
        "environment": "forest",
        "mood": "hopeful",
        "key_concept": "window_light",
        "fill_concept": "atmospheric_light",
        "rim_concept": "rim_light",
        "volumetrics": True,
        "description": "Dappled sunlight through canopy with volumetric shafts and natural bounce.",
        "notes": "Sun through canopy gaps as key shafts. Sky bounce as fill. Warm rim from sun angle.",
        "tags": ["forest", "dappled", "natural", "volumetric", "green", "hopeful"],
        "color_temperature": "warm",
        "contrast": "medium",
    },
    {
        "name": "military_base",
        "environment": "military_base",
        "mood": "tense",
        "key_concept": "industrial_fixture",
        "fill_concept": "bounce_light",
        "rim_concept": "atmospheric_light",
        "volumetrics": False,
        "description": "Harsh overhead floodlights with minimal fill and military tension.",
        "notes": "Overhead military floodlights. Hard shadows. Minimal fill. Warning lights as accents.",
        "tags": ["military", "harsh", "overhead", "tactical", "tense", "hard_shadows"],
        "color_temperature": "cool",
        "contrast": "high",
    },
    {
        "name": "cyberpunk_city",
        "environment": "cyberpunk_city",
        "mood": "dramatic",
        "key_concept": "neon_source",
        "fill_concept": "atmospheric_light",
        "rim_concept": "motivated_light",
        "volumetrics": True,
        "description": "Neon-saturated night city with rain reflections and volumetric light shafts.",
        "notes": "Neon signs as multiple competing key sources. Rain sheen for reflections. Volumetric haze.",
        "tags": ["cyberpunk", "neon", "rain", "volumetric", "city_glow", "dramatic"],
        "color_temperature": "cool",
        "contrast": "high",
    },
    {
        "name": "castle_hall",
        "environment": "castle_hall",
        "mood": "dramatic",
        "key_concept": "practical_light",
        "fill_concept": "atmospheric_light",
        "rim_concept": "motivated_light",
        "volumetrics": False,
        "description": "Flickering torch light with stained glass color patches and grand shadows.",
        "notes": "Torches as warm practicals. Stained glass window patches. Large dramatic shadows on stone.",
        "tags": ["medieval", "torch", "warm", "dramatic", "stained_glass", "grand"],
        "color_temperature": "warm",
        "contrast": "high",
    },
    {
        "name": "desert",
        "environment": "desert",
        "mood": "cinematic",
        "key_concept": "motivated_light",
        "fill_concept": "bounce_light",
        "rim_concept": "atmospheric_light",
        "volumetrics": True,
        "description": "Harsh overhead sun with bleached ground bounce and heat shimmer haze.",
        "notes": "High noon key from overhead. Sand bounce as warm fill. Heat shimmer volumetric effect.",
        "tags": ["desert", "harsh_sun", "warm", "bleached", "heat_haze", "cinematic"],
        "color_temperature": "warm",
        "contrast": "high",
    },
    {
        "name": "survival_camp",
        "environment": "survival_camp",
        "mood": "hopeful",
        "key_concept": "practical_light",
        "fill_concept": "atmospheric_light",
        "rim_concept": "motivated_light",
        "volumetrics": True,
        "description": "Campfire as central warm key with cool overcast sky and volumetric smoke.",
        "notes": "Campfire as hero light source. Torch practicals around perimeter. Cool grey overcast fill.",
        "tags": ["survival", "campfire", "warm", "hope", "volumetric_smoke", "post_apoc"],
        "color_temperature": "warm",
        "contrast": "medium",
    },
]

_ENV_KEYWORDS: Dict[str, List[str]] = {
    # Original 5 environments
    "industrial_hangar":   ["hangar", "warehouse", "factory", "industrial", "facility"],
    "robotics_lab":        ["lab", "laboratory", "robotics", "research", "workshop", "tech"],
    "control_room":        ["control", "ops", "operation", "monitoring", "command"],
    "sci_fi_corridor":     ["corridor", "hallway", "passage", "sci-fi", "scifi", "futuristic"],
    "abandoned_factory":   ["abandoned", "derelict", "ruin", "decay", "forgotten"],
    # Generic patterns
    "night_exterior":      ["night", "exterior", "outdoor", "moonlit", "outside"],
    "dramatic_interior":   ["interior", "room", "chamber", "inside", "dramatic"],
    "hero_reveal":         ["hero", "reveal", "entrance", "introduction", "character"],
    # §39 New Industrial
    "warehouse":           ["warehouse", "storage", "shelf", "forklift", "pallet", "logistics"],
    "shipyard":            ["shipyard", "dock", "ship", "maritime", "drydock", "vessel"],
    "oil_refinery":        ["refinery", "oil", "petroleum", "distillation", "flare"],
    "power_station":       ["power", "generator", "electrical", "turbine_power", "energy"],
    "mining_facility":     ["mine", "mining", "excavation", "ore", "quarry", "tunnel_mine"],
    "construction_site":   ["construction", "concrete", "scaffold", "crane_construction", "building"],
    # §39 Scientific
    "research_lab":        ["research", "experiment", "bench", "analysis", "laboratory"],
    "medical_lab":         ["medical", "hospital", "surgical", "sterile", "clinical"],
    "clean_room":          ["cleanroom", "semiconductor", "sterile_room", "fabrication"],
    "biohazard_facility":  ["biohazard", "containment", "hazmat", "pathogen", "bsl4"],
    # §39 Military
    "military_base":       ["military", "barracks", "tactical", "base", "armory"],
    "command_center":      ["command", "tactical_room", "briefing", "situation_room"],
    "military_hangar":     ["fighter", "jet", "airforce", "tarmac", "aircraft"],
    "checkpoint":          ["checkpoint", "barrier", "guard", "patrol", "border"],
    "bunker":              ["bunker", "underground_bunker", "blast_door", "shelter", "fortification"],
    # §39 Sci-Fi
    "space_station":       ["space", "orbital", "station", "astronaut", "solar_panel"],
    "spaceship_bridge":    ["bridge", "spaceship", "captain", "helm", "navigation"],
    "engineering_bay":     ["engineering", "engine", "power_core", "reactor", "warp"],
    "alien_facility":      ["alien", "bioluminescent", "organic", "xenomorph", "extraterrestrial"],
    "cyberpunk_city":      ["cyberpunk", "neon", "hologram", "dystopia", "rain_city"],
    # §39 Urban
    "city_street":         ["city", "street", "urban", "traffic", "downtown"],
    "alleyway":            ["alley", "narrow", "dumpster", "graffiti", "back_street"],
    "subway_station":      ["subway", "metro", "platform", "tunnel_subway", "commuter"],
    "parking_garage":      ["parking", "garage", "concrete_parking", "column", "fluorescent"],
    "rooftop":             ["rooftop", "roof", "skyline", "antenna", "hvac"],
    "shopping_mall":       ["mall", "retail", "atrium", "skylight_mall", "commercial"],
    # §39 Interior
    "western_room":        ["western", "cowboy", "frontier", "rustic", "lantern_western"],
    "saloon":              ["saloon", "bar_western", "piano", "poker", "frontier_bar"],
    "living_room":         ["living", "home", "domestic", "cozy", "family"],
    "office":              ["office", "corporate", "desk", "fluorescent_office", "workspace"],
    "hotel_lobby":         ["hotel", "lobby", "chandelier", "luxury", "grand"],
    "restaurant":          ["restaurant", "dining", "candle_dining", "ambiance"],
    "workshop":            ["workshop", "craft", "workbench", "tool", "maker"],
    "library":             ["library", "book", "reading", "scholarly", "quiet"],
    # §39 Nature
    "forest":              ["forest", "tree", "woodland", "canopy", "dappled"],
    "jungle":              ["jungle", "tropical", "vine", "rainforest", "lush"],
    "desert":              ["desert", "sand", "dune", "arid", "heat"],
    "canyon":              ["canyon", "cliff", "gorge", "red_rock", "geological"],
    "mountain":            ["mountain", "alpine", "peak", "snow", "summit"],
    "coastline":           ["coast", "beach", "ocean", "sea", "shore"],
    "swamp":               ["swamp", "bayou", "marsh", "murky", "cypress"],
    # §39 Fantasy
    "castle_hall":         ["castle", "throne", "medieval", "tapestry", "torch_hall"],
    "dungeon":             ["dungeon", "prison", "underground_dark", "chain"],
    "wizard_tower":        ["wizard", "magic", "arcane", "mystical", "magical_glow"],
    "ancient_ruins":       ["ruin", "ancient", "archaeological", "overgrown_stone"],
    "temple":              ["temple", "shrine", "sacred", "spiritual", "incense"],
    # §39 Post-Apocalyptic
    "abandoned_city":      ["apocalyptic", "desolate", "overgrown_city", "collapsed"],
    "destroyed_highway":   ["highway", "wreck", "cracked_road", "post_apoc_road"],
    "ruined_industrial_site": ["toxic", "contamination", "hazard_site", "ruined_factory"],
    "survival_camp":       ["survival", "camp", "makeshift", "campfire", "scavenged"],
}


@dataclass
class LightingPattern:
    pattern_id: str = field(default_factory=lambda: f"lp_{uuid.uuid4().hex[:8]}")
    name: str = ""
    environment: str = ""
    mood: str = ""
    key_concept: str = ""
    fill_concept: str = ""
    rim_concept: str = ""
    volumetrics: bool = False
    description: str = ""
    notes: str = ""
    tags: List[str] = field(default_factory=list)
    color_temperature: str = ""
    contrast: str = ""
    usage_count: int = 0
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern_id":       str(self.pattern_id),
            "name":             str(self.name),
            "environment":      str(self.environment),
            "mood":             str(self.mood),
            "key_concept":      str(self.key_concept),
            "fill_concept":     str(self.fill_concept),
            "rim_concept":      str(self.rim_concept),
            "volumetrics":      bool(self.volumetrics),
            "description":      str(self.description),
            "notes":            str(self.notes),
            "tags":             list(self.tags),
            "color_temperature": str(self.color_temperature),
            "contrast":         str(self.contrast),
            "usage_count":      int(self.usage_count),
            "created_at":       float(self.created_at),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "LightingPattern":
        d = d if isinstance(d, dict) else {}
        return cls(
            pattern_id=str(d.get("pattern_id") or f"lp_{uuid.uuid4().hex[:8]}"),
            name=str(d.get("name", "")),
            environment=str(d.get("environment", "")),
            mood=str(d.get("mood", "")),
            key_concept=str(d.get("key_concept", "")),
            fill_concept=str(d.get("fill_concept", "")),
            rim_concept=str(d.get("rim_concept", "")),
            volumetrics=bool(d.get("volumetrics", False)),
            description=str(d.get("description", "")),
            notes=str(d.get("notes", "")),
            tags=list(d.get("tags") or []),
            color_temperature=str(d.get("color_temperature", "")),
            contrast=str(d.get("contrast", "")),
            usage_count=int(d.get("usage_count") or 0),
            created_at=float(d.get("created_at") or time.time()),
        )


class LightingPatterns:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._patterns: Dict[str, LightingPattern] = {}
        self._register_count = 0
        self._register_builtins()

    def _register_builtins(self) -> None:
        for p in _BUILTIN_PATTERNS:
            pattern = LightingPattern(
                pattern_id=f"builtin_{p['name']}",
                name=p["name"],
                environment=p["environment"],
                mood=p["mood"],
                key_concept=p["key_concept"],
                fill_concept=p["fill_concept"],
                rim_concept=p["rim_concept"],
                volumetrics=p["volumetrics"],
                description=p["description"],
                notes=p["notes"],
                tags=list(p["tags"]),
                color_temperature=p["color_temperature"],
                contrast=p["contrast"],
            )
            self._patterns[pattern.pattern_id] = pattern

    def register_pattern(
        self,
        name: str,
        environment: str,
        mood: str = "",
        key_concept: str = "",
        fill_concept: str = "",
        rim_concept: str = "",
        volumetrics: bool = False,
        description: str = "",
        notes: str = "",
        tags: Optional[List[str]] = None,
        color_temperature: str = "",
        contrast: str = "",
    ) -> LightingPattern:
        pattern = LightingPattern(
            name=str(name),
            environment=str(environment),
            mood=str(mood),
            key_concept=str(key_concept),
            fill_concept=str(fill_concept),
            rim_concept=str(rim_concept),
            volumetrics=bool(volumetrics),
            description=str(description),
            notes=str(notes),
            tags=list(tags or []),
            color_temperature=str(color_temperature),
            contrast=str(contrast),
        )
        with self._lock:
            self._patterns[pattern.pattern_id] = pattern
            self._register_count += 1
        return pattern

    def get_pattern(self, pattern_id: str) -> Optional[LightingPattern]:
        with self._lock:
            return self._patterns.get(pattern_id)

    def search_patterns(self, query: str = "", environment: str = "", mood: str = "") -> List[LightingPattern]:
        with self._lock:
            results = list(self._patterns.values())
        q = str(query or "").lower().strip()
        env = str(environment or "").lower().strip()
        m = str(mood or "").lower().strip()
        if q:
            results = [
                p for p in results
                if q in p.name.lower()
                or q in p.description.lower()
                or any(q in t.lower() for t in p.tags)
                or q in p.environment.lower()
            ]
        if env:
            results = [p for p in results if p.environment.lower() == env]
        if m:
            results = [p for p in results if p.mood.lower() == m]
        return sorted(results, key=lambda p: p.name)

    def rank_patterns(self, scene_dict: Dict[str, Any]) -> List[LightingPattern]:
        """Rank patterns by environment + mood affinity against scene metadata."""
        try:
            scene_dict = scene_dict if isinstance(scene_dict, dict) else {}
            text = " ".join([
                str(scene_dict.get("intent", "")),
                str(scene_dict.get("environment", "")),
                str(scene_dict.get("mood", "")),
                " ".join(str(t) for t in (scene_dict.get("tags") or [])),
            ]).lower()

            scored: List[tuple] = []
            with self._lock:
                patterns = list(self._patterns.values())

            for p in patterns:
                score = 0.0
                env_kws = _ENV_KEYWORDS.get(p.environment, [p.environment])
                for kw in env_kws:
                    if kw in text:
                        score += 0.4
                        break
                if p.mood.lower() in text:
                    score += 0.3
                for tag in p.tags:
                    if tag.lower() in text:
                        score += 0.1
                if p.environment.lower().replace("_", " ") in text:
                    score += 0.2
                scored.append((score, p))

            scored.sort(key=lambda x: (-x[0], x[1].name))
            return [p for _, p in scored]
        except Exception:
            with self._lock:
                return sorted(self._patterns.values(), key=lambda p: p.name)

    def recommend_pattern(self, environment: str = "", mood: str = "") -> Optional[LightingPattern]:
        """Return the best matching pattern for the given environment and/or mood."""
        results = self.search_patterns(environment=environment, mood=mood)
        if not results and environment:
            results = self.rank_patterns({"environment": environment, "mood": mood})
        return results[0] if results else None


_INSTANCE: Optional[LightingPatterns] = None
_INSTANCE_LOCK = threading.Lock()


def get_lighting_patterns() -> LightingPatterns:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = LightingPatterns()
    return _INSTANCE


def reset_lighting_patterns_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
