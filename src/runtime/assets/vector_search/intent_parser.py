"""
Intent Parser (Tier 12.8)
===========================
Extracts structured production meaning from natural language intent text.

Example:
  Input:  "Industrial Hangar Hero Machinery"
  Output: ParsedIntent(environment="industrial_hangar", role="hero", category="machinery", ...)

Uses the Tier 12.7 semantic constants — no AI, no external API, fully deterministic.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.runtime.assets.semantic.asset_environment_mapper import BUILTIN_ENVIRONMENTS
from src.runtime.assets.semantic.asset_role_classifier import BUILTIN_ROLES, _CATEGORY_ROLE_HINTS
from src.runtime.assets.semantic.asset_storytelling_mapper import STORYTELLING_ROLES
from src.runtime.assets.semantic.asset_lookdev_mapper import LOOKDEV_TAGS
from src.runtime.assets.semantic.asset_cinematic_mapper import CINEMATIC_USAGES

_KNOWN_CATEGORIES = frozenset({
    "prop", "vehicle", "character", "machinery", "architecture", "vegetation",
    "equipment", "furniture", "tool", "electronics", "weapon", "creature",
    "surface", "material", "robot", "particle", "effect",
})

# Multi-word environment aliases → canonical id
_ENV_ALIASES: Dict[str, str] = {
    # Industrial
    "industrial hangar":    "industrial_hangar",
    "industrial_hangar":    "industrial_hangar",
    "abandoned factory":    "abandoned_factory",
    "abandoned_factory":    "abandoned_factory",
    "oil refinery":         "oil_refinery",
    "oil_refinery":         "oil_refinery",
    "power station":        "power_station",
    "power_station":        "power_station",
    "mining facility":      "mining_facility",
    "mining_facility":      "mining_facility",
    "construction site":    "construction_site",
    "construction_site":    "construction_site",
    # Scientific
    "robotics lab":         "robotics_lab",
    "robotics_lab":         "robotics_lab",
    "control room":         "control_room",
    "control_room":         "control_room",
    "research lab":         "research_lab",
    "research_lab":         "research_lab",
    "medical lab":          "medical_lab",
    "medical_lab":          "medical_lab",
    "clean room":           "clean_room",
    "clean_room":           "clean_room",
    "biohazard facility":   "biohazard_facility",
    "biohazard_facility":   "biohazard_facility",
    # Military
    "military base":        "military_base",
    "military_base":        "military_base",
    "command center":       "command_center",
    "command_center":       "command_center",
    "military hangar":      "military_hangar",
    "military_hangar":      "military_hangar",
    # Sci-Fi
    "sci fi corridor":      "sci_fi_corridor",
    "sci-fi corridor":      "sci_fi_corridor",
    "sci_fi_corridor":      "sci_fi_corridor",
    "space station":        "space_station",
    "space_station":        "space_station",
    "spaceship bridge":     "spaceship_bridge",
    "spaceship_bridge":     "spaceship_bridge",
    "ship bridge":          "spaceship_bridge",
    "engineering bay":      "engineering_bay",
    "engineering_bay":      "engineering_bay",
    "alien facility":       "alien_facility",
    "alien_facility":       "alien_facility",
    "cyberpunk city":       "cyberpunk_city",
    "cyberpunk_city":       "cyberpunk_city",
    # Urban
    "city street":          "city_street",
    "city_street":          "city_street",
    "subway station":       "subway_station",
    "subway_station":       "subway_station",
    "parking garage":       "parking_garage",
    "parking_garage":       "parking_garage",
    "shopping mall":        "shopping_mall",
    "shopping_mall":        "shopping_mall",
    # Interior
    "western room":         "western_room",
    "western_room":         "western_room",
    "living room":          "living_room",
    "living_room":          "living_room",
    "hotel lobby":          "hotel_lobby",
    "hotel_lobby":          "hotel_lobby",
    # Nature
    "castle hall":          "castle_hall",
    "castle_hall":          "castle_hall",
    "wizard tower":         "wizard_tower",
    "wizard_tower":         "wizard_tower",
    "ancient ruins":        "ancient_ruins",
    "ancient_ruins":        "ancient_ruins",
    # Post-Apocalyptic
    "abandoned city":       "abandoned_city",
    "abandoned_city":       "abandoned_city",
    "destroyed highway":    "destroyed_highway",
    "destroyed_highway":    "destroyed_highway",
    "ruined industrial site": "ruined_industrial_site",
    "ruined_industrial_site": "ruined_industrial_site",
    "survival camp":        "survival_camp",
    "survival_camp":        "survival_camp",
}

# Single-word hints that strongly suggest an environment
_ENV_SINGLE_HINTS: Dict[str, str] = {
    # Industrial
    "hangar":         "industrial_hangar",
    "factory":        "industrial_hangar",
    "industrial":     "industrial_hangar",
    "warehouse":      "warehouse",
    "shipyard":       "shipyard",
    "refinery":       "oil_refinery",
    "powerplant":     "power_station",
    "mining":         "mining_facility",
    "quarry":         "mining_facility",
    "construction":   "construction_site",
    # Scientific
    "robotics":       "robotics_lab",
    "lab":            "robotics_lab",
    "laboratory":     "research_lab",
    "cleanroom":      "clean_room",
    "biohazard":      "biohazard_facility",
    "hospital":       "medical_lab",
    "medical":        "medical_lab",
    # Military
    "barracks":       "military_base",
    "bunker":         "bunker",
    "checkpoint":     "checkpoint",
    "military":       "military_base",
    "command":        "command_center",
    # Sci-Fi
    "control":        "control_room",
    "corridor":       "sci_fi_corridor",
    "scifi":          "sci_fi_corridor",
    "orbital":        "space_station",
    "spaceship":      "spaceship_bridge",
    "starship":       "spaceship_bridge",
    "cyberpunk":      "cyberpunk_city",
    "alien":          "alien_facility",
    # Urban
    "downtown":       "city_street",
    "alley":          "alleyway",
    "subway":         "subway_station",
    "metro":          "subway_station",
    "rooftop":        "rooftop",
    "mall":           "shopping_mall",
    # Interior
    "saloon":         "saloon",
    "western":        "western_room",
    "cowboy":         "western_room",
    "workshop":       "workshop",
    "library":        "library",
    "restaurant":     "restaurant",
    "office":         "office",
    # Nature
    "forest":         "forest",
    "jungle":         "jungle",
    "desert":         "desert",
    "canyon":         "canyon",
    "mountain":       "mountain",
    "beach":          "coastline",
    "coastline":      "coastline",
    "swamp":          "swamp",
    "bayou":          "swamp",
    # Fantasy
    "castle":         "castle_hall",
    "dungeon":        "dungeon",
    "wizard":         "wizard_tower",
    "ruins":          "ancient_ruins",
    "temple":         "temple",
    "shrine":         "temple",
    # Post-Apocalyptic
    "apocalyptic":    "abandoned_city",
    "wasteland":      "abandoned_city",
    "derelict":       "abandoned_factory",
    "abandoned":      "abandoned_factory",
    "survival":       "survival_camp",
    "postapoc":       "abandoned_city",
}

# Multi-word role aliases
_ROLE_ALIASES: Dict[str, str] = {
    "set dressing":  "set_dressing",
    "set_dressing":  "set_dressing",
    "hero":          "hero",
    "support":       "support",
    "foreground":    "foreground",
    "midground":     "midground",
    "background":    "background",
}

# Multi-word storytelling aliases
_STORY_ALIASES: Dict[str, str] = {
    "hero object":     "hero_object",
    "hero_object":     "hero_object",
    "context builder": "context_builder",
    "context_builder": "context_builder",
    "scale reference": "scale_reference",
    "scale_reference": "scale_reference",
    "visual anchor":   "visual_anchor",
    "visual_anchor":   "visual_anchor",
    "atmosphere builder": "atmosphere_builder",
    "atmosphere_builder": "atmosphere_builder",
}

# Multi-word cinematic aliases
_CINEMATIC_ALIASES: Dict[str, str] = {
    "hero focus":         "hero_focus",
    "hero_focus":         "hero_focus",
    "foreground interest":"foreground_interest",
    "foreground_interest":"foreground_interest",
    "depth layer":        "depth_layer",
    "depth_layer":        "depth_layer",
    "visual balance":     "visual_balance",
    "visual_balance":     "visual_balance",
    "silhouette":         "silhouette",
}


@dataclass
class ParsedIntent:
    raw_text:     str = ""
    environment:  str = ""
    role:         str = ""
    category:     str = ""
    storytelling: str = ""
    lookdev:      str = ""
    cinematic:    str = ""
    keywords:     List[str] = field(default_factory=list)
    confidence:   float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw_text":     str(self.raw_text),
            "environment":  str(self.environment),
            "role":         str(self.role),
            "category":     str(self.category),
            "storytelling": str(self.storytelling),
            "lookdev":      str(self.lookdev),
            "cinematic":    str(self.cinematic),
            "keywords":     list(self.keywords),
            "confidence":   float(self.confidence),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ParsedIntent":
        d = d if isinstance(d, dict) else {}
        return cls(
            raw_text=str(d.get("raw_text", "")),
            environment=str(d.get("environment", "")),
            role=str(d.get("role", "")),
            category=str(d.get("category", "")),
            storytelling=str(d.get("storytelling", "")),
            lookdev=str(d.get("lookdev", "")),
            cinematic=str(d.get("cinematic", "")),
            keywords=list(d.get("keywords") or []),
            confidence=float(d.get("confidence", 0.0)),
        )

    def as_query_text(self) -> str:
        """Build a text representation of parsed intent for embedding."""
        parts = [
            self.environment.replace("_", " "),
            self.role.replace("_", " "),
            self.category,
            self.storytelling.replace("_", " "),
            self.lookdev,
            self.cinematic.replace("_", " "),
            " ".join(self.keywords),
        ]
        return " ".join(p for p in parts if p)

    def to_filter_dict(self) -> Dict[str, str]:
        """Convert to catalog search filter dict."""
        return {k: v for k, v in {
            "environment":  self.environment,
            "role":         self.role,
            "category":     self.category,
            "storytelling": self.storytelling,
            "lookdev":      self.lookdev,
            "cinematic":    self.cinematic,
        }.items() if v}


class IntentParser:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._parse_count = 0

    def parse(self, text: str) -> ParsedIntent:
        """Parse natural language intent into structured fields. Never raises."""
        try:
            return self._do_parse(str(text or "").strip())
        except Exception:
            return ParsedIntent(raw_text=str(text or ""))

    def _do_parse(self, text: str) -> ParsedIntent:
        lower = text.lower()
        # Try multi-word aliases first (longer matches take priority)
        environment  = self._match_aliases(lower, _ENV_ALIASES) or \
                       self.extract_environment(lower)
        role         = self._match_aliases(lower, _ROLE_ALIASES) or \
                       self.extract_role(lower)
        storytelling = self._match_aliases(lower, _STORY_ALIASES) or \
                       self.extract_storytelling(lower)
        cinematic    = self._match_aliases(lower, _CINEMATIC_ALIASES) or \
                       self.extract_cinematic(lower)
        lookdev      = self.extract_lookdev(lower)
        category     = self.extract_category(lower)

        # Keywords = remaining words after known field extraction
        known_tokens = set()
        for val in (environment, role, storytelling, cinematic, lookdev, category):
            known_tokens.update(val.replace("_", " ").split())
        keywords = [
            w for w in lower.split()
            if w not in known_tokens and len(w) > 2
        ]

        # Confidence: fraction of fields resolved
        resolved = sum(bool(v) for v in [environment, role, storytelling, cinematic, lookdev, category])
        confidence = round(resolved / 6, 4)

        with self._lock:
            self._parse_count += 1

        return ParsedIntent(
            raw_text=text,
            environment=environment,
            role=role,
            category=category,
            storytelling=storytelling,
            lookdev=lookdev,
            cinematic=cinematic,
            keywords=keywords,
            confidence=confidence,
        )

    @staticmethod
    def _match_aliases(text: str, aliases: Dict[str, str]) -> str:
        # Try longest match first
        for alias in sorted(aliases.keys(), key=len, reverse=True):
            if alias in text:
                return aliases[alias]
        return ""

    def extract_environment(self, text: str) -> str:
        """Extract environment from text. Never raises."""
        try:
            lower = text.lower()
            # Try multi-word
            result = self._match_aliases(lower, _ENV_ALIASES)
            if result:
                return result
            # Try single-word hints
            for word in lower.split():
                if word in _ENV_SINGLE_HINTS:
                    return _ENV_SINGLE_HINTS[word]
            # Try direct env IDs
            for env in BUILTIN_ENVIRONMENTS:
                if env.replace("_", " ") in lower or env in lower.replace(" ", "_"):
                    return env
            return ""
        except Exception:
            return ""

    def extract_role(self, text: str) -> str:
        """Extract production role. Never raises."""
        try:
            lower = text.lower()
            result = self._match_aliases(lower, _ROLE_ALIASES)
            if result:
                return result
            for role in BUILTIN_ROLES:
                if role.replace("_", " ") in lower:
                    return role
            return ""
        except Exception:
            return ""

    def extract_storytelling(self, text: str) -> str:
        """Extract storytelling role. Never raises."""
        try:
            lower = text.lower()
            result = self._match_aliases(lower, _STORY_ALIASES)
            if result:
                return result
            for role in STORYTELLING_ROLES:
                if role.replace("_", " ") in lower:
                    return role
            return ""
        except Exception:
            return ""

    def extract_lookdev(self, text: str) -> str:
        """Extract primary lookdev tag. Never raises."""
        try:
            lower = text.lower()
            for tag in sorted(LOOKDEV_TAGS):
                if tag in lower:
                    return tag
            return ""
        except Exception:
            return ""

    def extract_cinematic(self, text: str) -> str:
        """Extract cinematic usage. Never raises."""
        try:
            lower = text.lower()
            result = self._match_aliases(lower, _CINEMATIC_ALIASES)
            if result:
                return result
            for usage in CINEMATIC_USAGES:
                if usage.replace("_", " ") in lower:
                    return usage
            return ""
        except Exception:
            return ""

    def extract_category(self, text: str) -> str:
        """Extract asset category from text. Never raises."""
        try:
            lower = text.lower()
            for cat in sorted(_KNOWN_CATEGORIES, key=len, reverse=True):
                if cat in lower:
                    return cat
            return ""
        except Exception:
            return ""

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            return {"parse_count": self._parse_count}


_INSTANCE: Optional[IntentParser] = None
_INSTANCE_LOCK = threading.Lock()


def get_intent_parser() -> IntentParser:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = IntentParser()
    return _INSTANCE


def reset_intent_parser_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
