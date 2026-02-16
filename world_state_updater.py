from __future__ import annotations
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime
import json

from sqlmodel import Session, select

from ..db import engine
from ..models_legacy import World, LoadState
from .optimization_config import OPT


ITEM_KEYWORDS = [
    ("chrome briefcase", ("inventory", "items")),
    ("data shard", ("inventory", "items")),
    ("chronographic lens", ("inventory", "items")),
    ("ktm zx111", ("inventory", "vehicles")),
]

LOCATION_KEYWORDS = [
    # Cyberpunk city
    ("shibuya maglev station", "Shibuya Maglev Station"),
    ("maglev station", "Maglev Station"),
    ("highway", "Highway"),
    ("highway ride", "Highway"),
    ("overpass", "Highway Overpass"),
    ("alley", "Alleyway"),
    ("motel", "Starlight Motel"),
    # Space scenes
    ("bridge", "Ship Bridge"),
    ("cockpit", "Ship Bridge"),
    ("hangar", "Ship Hangar"),
    ("stardust drifter", "Ship Bridge"),
]

WEATHER_KEYWORDS = [
    ("rain", "Rainy"), ("drizzle", "Rainy"), ("storm", "Stormy"), ("fog", "Foggy"), ("sun", "Sunny"), ("snow", "Snowy")
]

TIME_KEYWORDS = [
    ("morning", "Morning"), ("afternoon", "Afternoon"), ("evening", "Evening"), ("night", "Night"),
    ("02:15", "Night"), ("sunrise", "Dawn")
]

NPC_KEYWORDS = [
    ("kaito the fixer", "Kaito the fixer"), ("kaito", "Kaito the fixer"),
]


@dataclass
class WorldChanges:
    location: Optional[str] = None
    time_of_day: Optional[str] = None
    weather: Optional[str] = None
    items_added: List[str] = None
    npcs_seen: List[str] = None

    def __post_init__(self):
        if self.items_added is None:
            self.items_added = []
        if self.npcs_seen is None:
            self.npcs_seen = []


def _detect_from_text(text: str) -> WorldChanges:
    t = (text or "").lower()
    changes = WorldChanges()

    for kw, standard in LOCATION_KEYWORDS:
        if kw in t:
            changes.location = standard
            break

    for kw, standard in WEATHER_KEYWORDS:
        if kw in t:
            changes.weather = standard
            break

    for kw, standard in TIME_KEYWORDS:
        if kw in t:
            changes.time_of_day = standard
            break

    for kw, (bucket, key) in ITEM_KEYWORDS:
        if kw in t:
            changes.items_added.append(kw)

    for kw, standard in NPC_KEYWORDS:
        if kw in t:
            changes.npcs_seen.append(standard)

    return changes


def _merge_inventory(inv_json: Dict[str, Any], items: List[str]) -> Dict[str, Any]:
    inv = inv_json or {}
    items_bucket = inv.setdefault("items", [])
    vehicles_bucket = inv.setdefault("vehicles", [])

    for it in items:
        if it == "ktm zx111":
            if it not in vehicles_bucket:
                vehicles_bucket.append(it)
        else:
            if it not in items_bucket:
                items_bucket.append(it)
    return inv


def update_world_and_load_state(world_id: str, load_state: LoadState, story_response: Dict[str, Any], user_message: str) -> Dict[str, Any]:
    """
    Apply rule-based extraction from center_text + user_message, persist world-level updates, and mutate the provided load_state.
    Returns a summary dict of changes applied.
    """
    center_text = story_response.get("center_text", "")
    # Detect signals separately in user and AI, then combine with guardrails
    user_detect = _detect_from_text(user_message or "")
    ai_detect = _detect_from_text(center_text)
    changes = WorldChanges()
    # Location: take AI if present else user
    changes.location = ai_detect.location or user_detect.location
    # Weather/time under guardrail: require both sides if enabled
    if OPT.STRICT_ENVIRONMENT_GUARDRAIL:
        changes.weather = ai_detect.weather if (ai_detect.weather and user_detect.weather) else None
        changes.time_of_day = ai_detect.time_of_day if (ai_detect.time_of_day and user_detect.time_of_day) else None
    else:
        changes.weather = ai_detect.weather or user_detect.weather
        changes.time_of_day = ai_detect.time_of_day or user_detect.time_of_day
    # Items/NPCs: union
    changes.items_added = list({*(user_detect.items_added or []), *(ai_detect.items_added or [])})
    changes.npcs_seen = list({*(user_detect.npcs_seen or []), *(ai_detect.npcs_seen or [])})

    summary: Dict[str, Any] = {"applied": False, "changes": {}}

    with Session(engine) as session:
        world = session.exec(select(World).where(World.id == world_id)).first()
        if not world:
            return summary

        # Parse existing fields
        stats = json.loads(world.stats) if world.stats else {}
        world_conditions = json.loads(world.world_conditions) if world.world_conditions else {}
        inventory = json.loads(world.inventory) if world.inventory else {}

        mutated = False

        if changes.location:
            load_state.current_location = changes.location
            world_conditions["last_known_location"] = changes.location
            mutated = True

        if changes.time_of_day:
            load_state.time_of_day = changes.time_of_day
            world_conditions["time_of_day"] = changes.time_of_day
            mutated = True

        if changes.weather:
            load_state.weather = changes.weather
            world_conditions["weather"] = changes.weather
            mutated = True

        if changes.items_added:
            inventory = _merge_inventory(inventory, changes.items_added)
            mutated = True

        # Simple NPC tracking
        if changes.npcs_seen:
            world_conditions.setdefault("npcs_seen", [])
            for n in changes.npcs_seen:
                if n not in world_conditions["npcs_seen"]:
                    world_conditions["npcs_seen"].append(n)
            mutated = True

        if mutated and OPT.ENABLE_WORLD_UPDATES:
            world.world_conditions = json.dumps(world_conditions)
            world.inventory = json.dumps(inventory)
            world.updated_at = datetime.utcnow()
            session.add(world)
            session.commit()
            summary["applied"] = True
            summary["changes"] = {
                "location": changes.location,
                "time_of_day": changes.time_of_day,
                "weather": changes.weather,
                "items_added": changes.items_added,
                "npcs_seen": changes.npcs_seen,
            }

    return summary
