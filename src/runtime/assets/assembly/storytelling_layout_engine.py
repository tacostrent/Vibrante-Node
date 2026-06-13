"""
Storytelling Layout Engine (Tier 9 — Semantic Asset Assembly)
=============================================================
Creates visual storytelling structure from an EnvironmentPlan.

Identifies the narrative hero area, contextual support areas,
visual flow direction, and the path a viewer's eye travels through
the scene.

DESIGN RULES:
  1. Deterministic — same EnvironmentPlan → same layout every time.
  2. No bridge calls.  No Houdini imports.  Planning only.
  3. Layout is driven by zone roles and environment narrative.
  4. Never raises — errors captured in StoryLayout.errors.

Public API:
    StoryBeat
    StoryLayout
    StorytellingLayoutEngine
    get_storytelling_layout_engine()
    reset_storytelling_layout_engine_for_tests()
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.runtime.assets.assembly.environment_builder import EnvironmentPlan
from src.runtime.assets.assembly.placement_templates import get_placement_templates

# ---------------------------------------------------------------------------
# Environment narrative lookup
# ---------------------------------------------------------------------------

_ENV_NARRATIVES: Dict[str, Dict[str, Any]] = {
    "industrial_hangar": {
        "theme":          "industrial operation",
        "hero_beat":      "central machinery commands attention and establishes scale",
        "support_beat":   "flanking equipment contextualizes the industrial purpose",
        "atmosphere_beat": "depth fog and high ceilings reinforce the sense of scale",
        "viewer_path":    ["hero_zone", "midground", "background"],
        "visual_flow":    "centrifugal — eye starts at hero, spirals outward",
    },
    "robotics_lab": {
        "theme":          "precision engineering",
        "hero_beat":      "featured robot at center demonstrates capability",
        "support_beat":   "workstations and tools frame the working environment",
        "atmosphere_beat": "clean diffuse light reinforces precision and control",
        "viewer_path":    ["hero_zone", "workstation_row", "midground", "background"],
        "visual_flow":    "grid — clinical left-to-right scan matches the lab aesthetic",
    },
    "control_room": {
        "theme":          "command authority",
        "hero_beat":      "central console is the decision nexus; all lines lead to it",
        "support_beat":   "surrounding stations establish the command hierarchy",
        "atmosphere_beat": "screen glow creates depth from foreground monitors backward",
        "viewer_path":    ["hero_zone", "console_arc", "midground", "background"],
        "visual_flow":    "convergent — all perspective lines lead to the central console",
    },
    "sci_fi_corridor": {
        "theme":          "corridor traversal",
        "hero_beat":      "corridor element at center frames the journey forward",
        "support_beat":   "wall panels create spatial rhythm and technological texture",
        "atmosphere_beat": "neon accent guides the eye forward through the corridor",
        "viewer_path":    ["hero_zone", "midground", "background"],
        "visual_flow":    "linear — forced perspective down corridor depth",
    },
    "abandoned_factory": {
        "theme":          "post-industrial decay",
        "hero_beat":      "dominant abandoned machinery evokes the scale of past industry",
        "support_beat":   "rubble and smaller props build the decay narrative",
        "atmosphere_beat": "heavy fog reveals and conceals — decay is never fully exposed",
        "viewer_path":    ["hero_zone", "rubble_field", "midground", "background"],
        "visual_flow":    "exploratory — viewer discovers layers of decay progressively",
    },

    # -----------------------------------------------------------------------
    # §39 Industrial
    # -----------------------------------------------------------------------
    "warehouse": {
        "theme":          "logistics operation",
        "hero_beat":      "forklift or pallet rack anchors the center and establishes operational scale",
        "support_beat":   "stacked crates and shelving bays frame the logistics narrative",
        "atmosphere_beat": "fluorescent rows recede into industrial depth",
        "viewer_path":    ["hero_zone", "midground", "background"],
        "visual_flow":    "grid — aisle perspective repeats to depth",
    },
    "shipyard": {
        "theme":          "maritime construction",
        "hero_beat":      "ship hull or drydock crane dominates, asserting monumental industrial scale",
        "support_beat":   "chains, anchors, and scaffolding frame the vessel in progress",
        "atmosphere_beat": "sea mist and overcast sky create maritime atmosphere",
        "viewer_path":    ["hero_zone", "midground", "background"],
        "visual_flow":    "upward — hull scale forces the eye toward the sky",
    },
    "oil_refinery": {
        "theme":          "petrochemical complexity",
        "hero_beat":      "distillation tower or flare stack establishes industrial scale and danger",
        "support_beat":   "pipes, valves, and tanks build the complexity narrative",
        "atmosphere_beat": "chemical haze and flare glow create an ominous industrial mood",
        "viewer_path":    ["hero_zone", "midground", "background"],
        "visual_flow":    "vertical — towers force the eye upward to sky",
    },
    "power_station": {
        "theme":          "energy infrastructure",
        "hero_beat":      "turbine hall or generator shows the source of power",
        "support_beat":   "control panels and transformers contextualize the system",
        "atmosphere_beat": "cooling tower steam and high-bay scale reinforce critical infrastructure",
        "viewer_path":    ["hero_zone", "midground", "background"],
        "visual_flow":    "centrifugal — turbine hall radiates operational importance",
    },
    "mining_facility": {
        "theme":          "underground extraction",
        "hero_beat":      "excavator or drill rig reveals the raw scale of extraction",
        "support_beat":   "conveyors and ore carts tell the story of material flow",
        "atmosphere_beat": "rock dust and deep shadows frame the underground world",
        "viewer_path":    ["hero_zone", "midground", "background"],
        "visual_flow":    "downward — tunnel depth draws the eye into the earth",
    },
    "construction_site": {
        "theme":          "creation in progress",
        "hero_beat":      "tower crane or partially built structure shows ambition and progress",
        "support_beat":   "scaffolding and raw materials contextualize the building process",
        "atmosphere_beat": "cement dust and sky reveal construction as human endeavor",
        "viewer_path":    ["hero_zone", "midground", "background"],
        "visual_flow":    "upward — steel and concrete frame push the eye skyward",
    },
    # -----------------------------------------------------------------------
    # §39 Scientific
    # -----------------------------------------------------------------------
    "research_lab": {
        "theme":          "methodical discovery",
        "hero_beat":      "central bench or key apparatus frames the moment of inquiry",
        "support_beat":   "instruments and reference materials establish scientific context",
        "atmosphere_beat": "clean diffuse light reinforces precision and objectivity",
        "viewer_path":    ["hero_zone", "midground", "background"],
        "visual_flow":    "grid — clinical lab rows invite left-to-right scan",
    },
    "medical_lab": {
        "theme":          "healing and precision",
        "hero_beat":      "operating table or diagnostic scanner commands life-and-death focus",
        "support_beat":   "monitors and IV stands build clinical urgency",
        "atmosphere_beat": "surgical white light removes all ambiguity",
        "viewer_path":    ["hero_zone", "midground", "background"],
        "visual_flow":    "convergent — all tools point toward the patient",
    },
    "clean_room": {
        "theme":          "technological purity",
        "hero_beat":      "fabrication machine or wafer stage reveals the frontier of miniaturization",
        "support_beat":   "containment walls and filters establish the purity contract",
        "atmosphere_beat": "near-shadowless yellow light suggests extreme care",
        "viewer_path":    ["hero_zone", "midground", "background"],
        "visual_flow":    "grid — symmetrical cleanroom lanes enforce ordered scanning",
    },
    "biohazard_facility": {
        "theme":          "contained danger",
        "hero_beat":      "containment chamber or biosafety cabinet makes the threat visible",
        "support_beat":   "hazmat suits and warning signs build the danger narrative",
        "atmosphere_beat": "warning light and clinical cool create tension through contrast",
        "viewer_path":    ["hero_zone", "midground", "background"],
        "visual_flow":    "convergent — all paths lead inward to the containment source",
    },
    # -----------------------------------------------------------------------
    # §39 Military
    # -----------------------------------------------------------------------
    "military_base": {
        "theme":          "tactical readiness",
        "hero_beat":      "armored vehicle or watchtower establishes military authority at a glance",
        "support_beat":   "barriers and equipment rows convey operational preparedness",
        "atmosphere_beat": "harsh light, dust, and perimeter fencing enforce order",
        "viewer_path":    ["hero_zone", "perimeter", "midground", "background"],
        "visual_flow":    "grid — base layout imposes military precision on the eye",
    },
    "command_center": {
        "theme":          "strategic authority",
        "hero_beat":      "tactical table or situation display is the decision nexus",
        "support_beat":   "surrounding monitors and radio equipment build command authority",
        "atmosphere_beat": "low-key dramatic light focuses attention on the mission",
        "viewer_path":    ["hero_zone", "midground", "background"],
        "visual_flow":    "convergent — all sight lines lead to the tactical display",
    },
    "military_hangar": {
        "theme":          "aerial power",
        "hero_beat":      "fighter jet or helicopter defines the military capability",
        "support_beat":   "maintenance rigs and fuel carts frame readiness",
        "atmosphere_beat": "jet exhaust haze and hangar echo reinforce power",
        "viewer_path":    ["hero_zone", "midground", "background"],
        "visual_flow":    "upward — aircraft scale forces the eye toward the roof and sky",
    },
    "checkpoint": {
        "theme":          "controlled boundary",
        "hero_beat":      "barrier gate or guard booth defines the moment of access",
        "support_beat":   "wire fencing and bollards establish the perimeter reality",
        "atmosphere_beat": "searchlight beams and night dust build tension",
        "viewer_path":    ["hero_zone", "midground", "background"],
        "visual_flow":    "linear — forced approach along the single permitted path",
    },
    "bunker": {
        "theme":          "underground fortress",
        "hero_beat":      "blast door or command table asserts the last resort of authority",
        "support_beat":   "supply crates and bunks contextualize long-term survival",
        "atmosphere_beat": "bare bulb flicker and concrete echo reinforce claustrophobia",
        "viewer_path":    ["hero_zone", "midground", "background"],
        "visual_flow":    "tunnel — forced depth into underground safety",
    },
    # -----------------------------------------------------------------------
    # §39 Sci-Fi
    # -----------------------------------------------------------------------
    "space_station": {
        "theme":          "orbital isolation",
        "hero_beat":      "observation window or command console frames humanity in orbit",
        "support_beat":   "equipment racks and module junctions contextualize daily life in space",
        "atmosphere_beat": "cool panel glow and Earth visible through viewport create depth",
        "viewer_path":    ["hero_zone", "module_left", "module_right", "midground", "background"],
        "visual_flow":    "radial — modules extend from central hub outward",
    },
    "spaceship_bridge": {
        "theme":          "command at the frontier",
        "hero_beat":      "captain's chair or viewscreen is the axis of exploration leadership",
        "support_beat":   "crew stations build the sense of collective mission",
        "atmosphere_beat": "star field and console glow place the crew in the cosmos",
        "viewer_path":    ["hero_zone", "midground", "background"],
        "visual_flow":    "convergent — all crew positions face the viewscreen together",
    },
    "engineering_bay": {
        "theme":          "technological heart",
        "hero_beat":      "power core or reactor reveals the source of the ship's life",
        "support_beat":   "conduits and maintenance platforms contextualize the engineers' work",
        "atmosphere_beat": "core glow and plasma heat build tension and wonder",
        "viewer_path":    ["hero_zone", "midground", "background"],
        "visual_flow":    "centrifugal — core radiates energy and story outward",
    },
    "alien_facility": {
        "theme":          "first contact",
        "hero_beat":      "alien structure or bioluminescent growth is the moment of encounter",
        "support_beat":   "organic walls and alien pods build the otherworldly context",
        "atmosphere_beat": "bioluminescent mist and eerie silence enforce the unknown",
        "viewer_path":    ["hero_zone", "midground", "background"],
        "visual_flow":    "exploratory — alien architecture resists familiar reading order",
    },
    "cyberpunk_city": {
        "theme":          "dystopian society",
        "hero_beat":      "megastructure or neon-lit street scene anchors the power imbalance",
        "support_beat":   "street vendors and hologram ads show the human cost",
        "atmosphere_beat": "neon rain and city haze compress layers of story",
        "viewer_path":    ["hero_zone", "midground", "background"],
        "visual_flow":    "centrifugal — neon light radiates outward from hero signage",
    },
    # -----------------------------------------------------------------------
    # §39 Urban
    # -----------------------------------------------------------------------
    "city_street": {
        "theme":          "urban life",
        "hero_beat":      "street-level scene or iconic vehicle places the viewer in the city",
        "support_beat":   "street furniture and building facades frame the urban context",
        "atmosphere_beat": "city haze and golden street light build living atmosphere",
        "viewer_path":    ["hero_zone", "midground", "background"],
        "visual_flow":    "linear — street perspective forces the eye to the vanishing point",
    },
    "alleyway": {
        "theme":          "urban underbelly",
        "hero_beat":      "dumpster or fire escape is the hidden world made visible",
        "support_beat":   "graffiti and brick walls build the back-street narrative",
        "atmosphere_beat": "spill light and rain puddle reflections create atmosphere",
        "viewer_path":    ["hero_zone", "midground", "background"],
        "visual_flow":    "linear — narrow alley depth forces linear progression",
    },
    "subway_station": {
        "theme":          "underground transit",
        "hero_beat":      "arriving train or platform edge frames the commuter drama",
        "support_beat":   "pillars and signage build the transit system reality",
        "atmosphere_beat": "tunnel wind and fluorescent flicker place us underground",
        "viewer_path":    ["hero_zone", "midground", "background"],
        "visual_flow":    "linear — platform extends to tunnel darkness beyond",
    },
    "parking_garage": {
        "theme":          "urban isolation",
        "hero_beat":      "parked vehicle or ramp entrance defines the hidden space",
        "support_beat":   "columns and painted markings build the structural grid",
        "atmosphere_beat": "harsh overhead light and deep column shadow enforce isolation",
        "viewer_path":    ["hero_zone", "midground", "background"],
        "visual_flow":    "grid — column grid imposes urban structural order",
    },
    "rooftop": {
        "theme":          "perspective above",
        "hero_beat":      "skyline view or water tower places us above the city",
        "support_beat":   "HVAC units and antennae ground the urban context",
        "atmosphere_beat": "city glow at night or golden sky create emotional resonance",
        "viewer_path":    ["hero_zone", "midground", "background"],
        "visual_flow":    "panoramic — open sky invites free exploration of the horizon",
    },
    "shopping_mall": {
        "theme":          "consumer culture",
        "hero_beat":      "atrium or escalator frames the commercial world as spectacle",
        "support_beat":   "store displays and signage build the consumer environment",
        "atmosphere_beat": "skylight and retail warmth create the seduction of commerce",
        "viewer_path":    ["hero_zone", "midground", "background"],
        "visual_flow":    "centrifugal — atrium radiates commercial energy outward",
    },
    # -----------------------------------------------------------------------
    # §39 Interior
    # -----------------------------------------------------------------------
    "western_room": {
        "theme":          "frontier gathering",
        "hero_beat":      "central table or bar counter anchors the social drama",
        "support_beat":   "barrels, crates, and period props establish the era",
        "atmosphere_beat": "warm lantern light narrates the time and place without words",
        "viewer_path":    ["hero_zone", "bar_area", "midground", "background"],
        "visual_flow":    "centrifugal — warmth radiates from the central practical light",
    },
    "saloon": {
        "theme":          "frontier social hub",
        "hero_beat":      "bar counter or poker table is the stage for confrontation",
        "support_beat":   "piano and whiskey bottles build the saloon identity",
        "atmosphere_beat": "amber kerosene warmth and sawdust floor tell the era",
        "viewer_path":    ["hero_zone", "bar_area", "midground", "background"],
        "visual_flow":    "centrifugal — bar is the social axis of the scene",
    },
    "living_room": {
        "theme":          "domestic life",
        "hero_beat":      "sofa or fireplace is the heart of domestic comfort",
        "support_beat":   "lamps and books frame personal life in quiet detail",
        "atmosphere_beat": "warm ambient light communicates safety and belonging",
        "viewer_path":    ["hero_zone", "midground", "background"],
        "visual_flow":    "centrifugal — warmth radiates from the domestic center",
    },
    "office": {
        "theme":          "professional pursuit",
        "hero_beat":      "executive desk or conference table is the center of decisions",
        "support_beat":   "monitors and documents frame the corporate reality",
        "atmosphere_beat": "fluorescent cool and corporate neutral reinforce the environment",
        "viewer_path":    ["hero_zone", "midground", "background"],
        "visual_flow":    "grid — desk rows impose corporate order on the viewer",
    },
    "hotel_lobby": {
        "theme":          "luxury arrival",
        "hero_beat":      "grand chandelier or reception desk makes the first impression",
        "support_beat":   "luggage and plants frame the transient gathering",
        "atmosphere_beat": "warm luxury light and marble floor communicate prestige",
        "viewer_path":    ["hero_zone", "midground", "background"],
        "visual_flow":    "upward — chandelier and high ceiling draw the eye skyward",
    },
    "restaurant": {
        "theme":          "social dining",
        "hero_beat":      "table set for dining or open kitchen frames the culinary ritual",
        "support_beat":   "candles and wine glasses build romantic or social context",
        "atmosphere_beat": "warm pendant light and ambient hum create dining magic",
        "viewer_path":    ["hero_zone", "midground", "background"],
        "visual_flow":    "grid — table arrangement guides the eye in social rows",
    },
    "workshop": {
        "theme":          "skilled craft",
        "hero_beat":      "workbench or power tool is the stage of making",
        "support_beat":   "tool racks and blueprints frame expertise and intent",
        "atmosphere_beat": "task lamp warmth and sawdust convey the honesty of craft",
        "viewer_path":    ["hero_zone", "midground", "background"],
        "visual_flow":    "centrifugal — bench radiates the maker's focused attention",
    },
    "library": {
        "theme":          "accumulated knowledge",
        "hero_beat":      "bookshelf wall or reading table holds the accumulated mind",
        "support_beat":   "lamps and catalog drawers frame the system of knowledge",
        "atmosphere_beat": "warm reading light and dust motes convey time and wisdom",
        "viewer_path":    ["hero_zone", "midground", "background"],
        "visual_flow":    "grid — shelf rows invite systematic left-to-right reading",
    },
    # -----------------------------------------------------------------------
    # §39 Nature
    # -----------------------------------------------------------------------
    "forest": {
        "theme":          "nature immersion",
        "hero_beat":      "ancient tree or forest clearing is the still point of the natural world",
        "support_beat":   "ferns, mushrooms, and undergrowth build the layered ecosystem",
        "atmosphere_beat": "volumetric light shafts and mist reveal the forest spirit",
        "viewer_path":    ["hero_zone", "midground", "background"],
        "visual_flow":    "exploratory — scattered trees resist single directional reading",
    },
    "jungle": {
        "theme":          "primal nature",
        "hero_beat":      "waterfall or jungle canopy break commands the sense of discovery",
        "support_beat":   "vines and exotic flora build the lush density narrative",
        "atmosphere_beat": "tropical humidity and diffuse canopy light enforce immersion",
        "viewer_path":    ["hero_zone", "midground", "background"],
        "visual_flow":    "exploratory — dense growth conceals and reveals progressively",
    },
    "desert": {
        "theme":          "elemental isolation",
        "hero_beat":      "dune formation or rock arch commands the desolate horizon",
        "support_beat":   "scattered cacti and rock establish the arid world",
        "atmosphere_beat": "heat shimmer and bleached light enforce elemental harshness",
        "viewer_path":    ["hero_zone", "midground", "background"],
        "visual_flow":    "horizontal — open desert invites horizon-to-horizon scanning",
    },
    "canyon": {
        "theme":          "geological time",
        "hero_beat":      "canyon wall or rock formation makes geological history visible",
        "support_beat":   "layered rock and river stones narrate millions of years",
        "atmosphere_beat": "red dust and canyon shadow enforce the weight of time",
        "viewer_path":    ["hero_zone", "midground", "background"],
        "visual_flow":    "vertical — cliff walls direct the eye upward and downward",
    },
    "mountain": {
        "theme":          "epic journey",
        "hero_beat":      "mountain peak or glacier reveals the summit as narrative goal",
        "support_beat":   "boulders and alpine plants scale the heroic path",
        "atmosphere_beat": "cloud wrap and alpine crisp reinforce the achievement of altitude",
        "viewer_path":    ["hero_zone", "midground", "background"],
        "visual_flow":    "upward — mountain forces the eye toward summit and sky",
    },
    "coastline": {
        "theme":          "boundary of worlds",
        "hero_beat":      "sea cliff or lighthouse marks the edge of land and sea",
        "support_beat":   "rock pools and sea grass bridge the two worlds",
        "atmosphere_beat": "sea spray and coastal wind enforce the meeting of elements",
        "viewer_path":    ["hero_zone", "midground", "background"],
        "visual_flow":    "horizontal — shoreline horizon draws the eye to the vanishing line",
    },
    "swamp": {
        "theme":          "dark mystery",
        "hero_beat":      "cypress tree or murky water surface holds the hidden world",
        "support_beat":   "Spanish moss and mangrove roots build the layered wetland",
        "atmosphere_beat": "swamp fog and murky green enforce the sense of hidden danger",
        "viewer_path":    ["hero_zone", "midground", "background"],
        "visual_flow":    "exploratory — fog conceals and reveals the swamp progressively",
    },
    # -----------------------------------------------------------------------
    # §39 Fantasy
    # -----------------------------------------------------------------------
    "castle_hall": {
        "theme":          "royal authority",
        "hero_beat":      "throne or great fireplace dominates, establishing the seat of power",
        "support_beat":   "tapestries and columns frame the power structure and lineage",
        "atmosphere_beat": "torch light and stone echo medieval grandeur and history",
        "viewer_path":    ["hero_zone", "column_run_left", "column_run_right", "midground", "background"],
        "visual_flow":    "convergent — column rows guide the eye to the throne",
    },
    "dungeon": {
        "theme":          "captivity and consequence",
        "hero_beat":      "prison cell or iron door is the visible instrument of power",
        "support_beat":   "chains and torches build the oppressive reality",
        "atmosphere_beat": "near-total darkness and damp echo enforce claustrophobia",
        "viewer_path":    ["hero_zone", "midground", "background"],
        "visual_flow":    "tunnel — single torch light pulls the eye through darkness",
    },
    "wizard_tower": {
        "theme":          "arcane knowledge",
        "hero_beat":      "crystal orb or magical apparatus is the center of arcane power",
        "support_beat":   "spell books and potion bottles frame the scholar's world",
        "atmosphere_beat": "magical mist and candle glow create mystical wonder",
        "viewer_path":    ["hero_zone", "midground", "background"],
        "visual_flow":    "spiral — tower staircase winds the eye upward through knowledge",
    },
    "ancient_ruins": {
        "theme":          "lost civilization",
        "hero_beat":      "broken column or ancient statue makes the lost world tangible",
        "support_beat":   "overgrown stone and inscriptions fill in the civilization's story",
        "atmosphere_beat": "jungle mist and golden ruin light frame the passage of time",
        "viewer_path":    ["hero_zone", "midground", "background"],
        "visual_flow":    "exploratory — ruins scatter the eye in archaeological discovery",
    },
    "temple": {
        "theme":          "sacred devotion",
        "hero_beat":      "altar or deity statue is the focus of spiritual attention",
        "support_beat":   "incense holders and offerings build the devotional context",
        "atmosphere_beat": "divine shaft light and incense smoke enforce the sacred",
        "viewer_path":    ["hero_zone", "midground", "background"],
        "visual_flow":    "convergent — all ritual paths lead to the altar",
    },
    # -----------------------------------------------------------------------
    # §39 Post-Apocalyptic
    # -----------------------------------------------------------------------
    "abandoned_city": {
        "theme":          "civilization collapse",
        "hero_beat":      "collapsed building or overgrown street makes the fall of civilization visible",
        "support_beat":   "abandoned vehicles and broken glass build the scale of loss",
        "atmosphere_beat": "ash haze and overcast grey enforce desolation",
        "viewer_path":    ["hero_zone", "midground", "background"],
        "visual_flow":    "exploratory — ruins and overgrowth scatter the eye across decay",
    },
    "destroyed_highway": {
        "theme":          "last road",
        "hero_beat":      "wrecked vehicle pile or overpass ruin frames the collapse of infrastructure",
        "support_beat":   "abandoned cars and road debris tell the story of the last journey",
        "atmosphere_beat": "ash drift and grey overcast enforce the silence of the end",
        "viewer_path":    ["hero_zone", "midground", "background"],
        "visual_flow":    "linear — highway perspective extends to the desolate vanishing point",
    },
    "ruined_industrial_site": {
        "theme":          "industrial apocalypse",
        "hero_beat":      "collapsed structure or contaminated zone reveals the cost of collapse",
        "support_beat":   "warning signs and chemical drums build the toxic narrative",
        "atmosphere_beat": "toxic haze and chemical green light enforce the environmental horror",
        "viewer_path":    ["hero_zone", "midground", "background"],
        "visual_flow":    "exploratory — structural failure creates unpredictable sight lines",
    },
    "survival_camp": {
        "theme":          "human resilience",
        "hero_beat":      "campfire or barricade wall holds the survivors in the last community",
        "support_beat":   "scavenged supplies and improvised shelters frame the will to survive",
        "atmosphere_beat": "campfire warmth against grey ash creates hope through contrast",
        "viewer_path":    ["hero_zone", "perimeter", "midground", "background"],
        "visual_flow":    "centrifugal — campfire warmth radiates outward against the grey world",
    },
}

_DEFAULT_NARRATIVE = _ENV_NARRATIVES["industrial_hangar"]


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class StoryBeat:
    """A single narrative moment in the scene layout."""

    beat_id:     str
    beat_type:   str       # hero, support, atmosphere, transition
    zone_name:   str
    description: str
    assets:      List[Dict[str, Any]] = field(default_factory=list)
    priority:    int = 5   # 1 = first seen, 10 = most important
    notes:       List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "beat_id":     self.beat_id,
            "beat_type":   self.beat_type,
            "zone_name":   self.zone_name,
            "description": self.description,
            "assets":      list(self.assets),
            "priority":    self.priority,
            "notes":       list(self.notes),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "StoryBeat":
        return cls(
            beat_id=str(d.get("beat_id", "")),
            beat_type=str(d.get("beat_type", "support")),
            zone_name=str(d.get("zone_name", "")),
            description=str(d.get("description", "")),
            assets=list(d.get("assets") or []),
            priority=int(d.get("priority", 5)),
            notes=list(d.get("notes") or []),
        )


@dataclass
class StoryLayout:
    """Complete storytelling layout for an environment."""

    layout_id:      str = field(default_factory=lambda: f"story_{uuid.uuid4().hex[:10]}")
    environment:    str = ""
    theme:          str = ""
    hero_zone:      str = ""
    support_zones:  List[str] = field(default_factory=list)
    beats:          List[StoryBeat] = field(default_factory=list)
    viewer_path:    List[str] = field(default_factory=list)
    visual_flow:    str = ""
    camera_hint:    str = ""
    ok:             bool = True
    errors:         List[str] = field(default_factory=list)
    warnings:       List[str] = field(default_factory=list)
    generated_at:   float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "layout_id":     self.layout_id,
            "environment":   self.environment,
            "theme":         self.theme,
            "hero_zone":     self.hero_zone,
            "support_zones": list(self.support_zones),
            "beats":         [b.to_dict() for b in self.beats],
            "viewer_path":   list(self.viewer_path),
            "visual_flow":   self.visual_flow,
            "camera_hint":   self.camera_hint,
            "ok":            self.ok,
            "errors":        list(self.errors),
            "warnings":      list(self.warnings),
            "generated_at":  self.generated_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "StoryLayout":
        return cls(
            layout_id=str(d.get("layout_id", f"story_{uuid.uuid4().hex[:10]}")),
            environment=str(d.get("environment", "")),
            theme=str(d.get("theme", "")),
            hero_zone=str(d.get("hero_zone", "")),
            support_zones=list(d.get("support_zones") or []),
            beats=[StoryBeat.from_dict(b) for b in (d.get("beats") or [])],
            viewer_path=list(d.get("viewer_path") or []),
            visual_flow=str(d.get("visual_flow", "")),
            camera_hint=str(d.get("camera_hint", "")),
            ok=bool(d.get("ok", True)),
            errors=list(d.get("errors") or []),
            warnings=list(d.get("warnings") or []),
            generated_at=float(d.get("generated_at", 0.0)),
        )


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class StorytellingLayoutEngine:
    """
    Generates visual storytelling structure from an EnvironmentPlan.
    Identifies hero, support, and atmosphere beats; derives the viewer's path.
    """

    def generate_story_layout(self, env_plan: EnvironmentPlan) -> StoryLayout:
        """
        Build a full StoryLayout from an EnvironmentPlan.
        Never raises — errors captured in StoryLayout.errors.
        """
        layout = StoryLayout(environment=env_plan.environment)
        try:
            narrative = _ENV_NARRATIVES.get(env_plan.environment, _DEFAULT_NARRATIVE)
            layout.theme      = narrative["theme"]
            layout.visual_flow = narrative["visual_flow"]

            # Identify zones
            layout.hero_zone     = self.identify_hero_area(env_plan)
            layout.support_zones = self.identify_support_areas(env_plan)

            # Build story beats
            layout.beats = self._build_beats(env_plan, narrative)

            # Viewer path
            layout.viewer_path = self.generate_viewer_path(env_plan, narrative)

            # Camera hint from template narrative
            tmpl = get_placement_templates().get_template_or_default(env_plan.environment)
            tmpl_narrative = tmpl.get("narrative", {})
            layout.camera_hint = str(tmpl_narrative.get("atmosphere_beat", ""))

            if not layout.hero_zone:
                layout.warnings.append("No hero zone identified — visual storytelling will be weak.")

            layout.ok = True

        except Exception as exc:
            layout.ok = False
            layout.errors.append(f"Story layout failed: {exc}")

        return layout

    def identify_hero_area(self, env_plan: EnvironmentPlan) -> str:
        """Return the name of the primary hero zone."""
        if "hero_zone" in env_plan.zones:
            return "hero_zone"
        # Fallback: zone with 'primary' role
        for name, zone in env_plan.zones.items():
            if zone.role == "primary":
                return name
        return ""

    def identify_support_areas(self, env_plan: EnvironmentPlan) -> List[str]:
        """Return zone names that provide narrative support (non-hero, non-atmosphere)."""
        result = []
        for name, zone in env_plan.zones.items():
            if zone.role in ("support", "detail") and name != "hero_zone":
                result.append(name)
        return result

    def generate_visual_flow(self, env_plan: EnvironmentPlan) -> str:
        """Return the visual flow description for the environment."""
        narrative = _ENV_NARRATIVES.get(env_plan.environment, _DEFAULT_NARRATIVE)
        return str(narrative.get("visual_flow", "centrifugal — eye starts at hero"))

    def generate_viewer_path(
        self,
        env_plan: EnvironmentPlan,
        narrative: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """
        Return the ordered list of zones the viewer's eye traverses.
        Only includes zones that exist in the environment plan.
        """
        if narrative is None:
            narrative = _ENV_NARRATIVES.get(env_plan.environment, _DEFAULT_NARRATIVE)
        raw_path = narrative.get("viewer_path", ["hero_zone", "midground", "background"])
        return [z for z in raw_path if z in env_plan.zones]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build_beats(
        self,
        env_plan: EnvironmentPlan,
        narrative: Dict[str, Any],
    ) -> List[StoryBeat]:
        """Build ordered story beats from zone roles and narrative data."""
        beats: List[StoryBeat] = []

        # Hero beat
        hero_zone = self.identify_hero_area(env_plan)
        if hero_zone and hero_zone in env_plan.zones:
            zone = env_plan.zones[hero_zone]
            beats.append(StoryBeat(
                beat_id=f"beat_hero_{uuid.uuid4().hex[:6]}",
                beat_type="hero",
                zone_name=hero_zone,
                description=narrative.get("hero_beat", "Hero asset establishes scene focus"),
                assets=list(zone.assigned_assets),
                priority=10,
            ))

        # Support beats (one per support zone)
        for zone_name in self.identify_support_areas(env_plan):
            zone = env_plan.zones.get(zone_name)
            if not zone:
                continue
            beats.append(StoryBeat(
                beat_id=f"beat_support_{uuid.uuid4().hex[:6]}",
                beat_type="support",
                zone_name=zone_name,
                description=narrative.get("support_beat", "Support assets contextualise the hero"),
                assets=list(zone.assigned_assets),
                priority=6,
            ))

        # Atmosphere beat (background / atmosphere zones)
        for zone_name, zone in env_plan.zones.items():
            if zone.role == "atmosphere" or zone_name == "background":
                beats.append(StoryBeat(
                    beat_id=f"beat_atm_{uuid.uuid4().hex[:6]}",
                    beat_type="atmosphere",
                    zone_name=zone_name,
                    description=narrative.get("atmosphere_beat", "Atmosphere establishes mood"),
                    assets=list(zone.assigned_assets),
                    priority=3,
                ))
                break  # one atmosphere beat is enough

        return sorted(beats, key=lambda b: -b.priority)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[StorytellingLayoutEngine] = None
_INSTANCE_LOCK = threading.Lock()


def get_storytelling_layout_engine() -> StorytellingLayoutEngine:
    """Return the module-level singleton StorytellingLayoutEngine."""
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = StorytellingLayoutEngine()
    return _INSTANCE


def reset_storytelling_layout_engine_for_tests() -> None:
    """Replace the singleton.  For test isolation only."""
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
