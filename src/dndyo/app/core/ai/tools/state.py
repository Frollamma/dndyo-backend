import random
from typing import Any

from sqlmodel import Session, col, delete, select

from dndyo.app.core.db import engine
from dndyo.app.helpers.map_state import ensure_game_has_map
from dndyo.app.models.actor import Actor, Alignment, Size
from dndyo.app.models.game import Game
from dndyo.app.models.game_state import GameState
from dndyo.app.models.image import Image
from dndyo.app.models.live_actor import LiveActor, LiveActorRole
from dndyo.app.models.map import Map

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_game_state",
            "description": (
                "Read the full current game state: live actors, current map id, "
                "and environment description."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_live_actor",
            "description": (
                "Create a new actor and create a linked live actor entry in combat state."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "state": {"type": "string"},
                    "background": {
                        "type": "string",
                        "description": "Unique description/history for this live actor.",
                    },
                    "role": {
                        "type": "string",
                        "description": "One of: enemy, player, npc. Default: enemy.",
                    },
                    "current_hp": {"type": "integer", "minimum": 1},
                },
                "required": ["name", "state"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_live_actor",
            "description": "Delete live actor entries by actor_id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "actor_id": {"type": "integer", "minimum": 1},
                },
                "required": ["actor_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "unlock_next_chapter",
            "description": (
                "Unlock the next chapter for the current game by appending the next "
                "entry from chapters into current_chapters."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "change_map",
            "description": "Set the current map id in the game state.",
            "parameters": {
                "type": "object",
                "properties": {
                    "current_map_id": {"type": "integer", "minimum": 1},
                },
                "required": ["current_map_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "change_environment_description",
            "description": (
                "Update the global environment description in the current state."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                },
                "required": ["description"],
            },
        },
    },
]


def _get_or_create_state(session: Session, game_id: int) -> GameState:
    default_map_id = ensure_game_has_map(session, game_id)
    state = session.exec(select(GameState).where(col(GameState.id) == game_id)).first()
    if state is None:
        state = GameState(
            id=game_id, environment_description="", current_map_id=default_map_id
        )
        session.add(state)
        session.commit()
        session.refresh(state)
        return state

    db_map = session.exec(
        select(Map).where(
            col(Map.id) == state.current_map_id,
            col(Map.game_id) == game_id,
        )
    ).first()
    if db_map is None:
        state.current_map_id = default_map_id
        session.add(state)
        session.commit()
        session.refresh(state)
    return state


def _read_state(session: Session, game_id: int) -> dict[str, Any]:
    state = _get_or_create_state(session, game_id)
    db_map = session.exec(
        select(Map).where(
            col(Map.id) == state.current_map_id,
            col(Map.game_id) == game_id,
        )
    ).first()
    if db_map is None:
        raise RuntimeError(
            f"Current map {state.current_map_id} does not exist in game {game_id}."
        )
    current_map = {
        "id": db_map.id,
        "name": db_map.name,
        "description": db_map.description,
        "image_id": db_map.image_id,
        "connected_maps_ids": db_map.connected_maps_ids,
    }

    live_rows = session.exec(
        select(LiveActor, Actor)
        .join(Actor, Actor.id == LiveActor.actor_id)
        .where(
            LiveActor.game_id == game_id,
            Actor.game_id == game_id,
        )
        .order_by(col(LiveActor.id))
    ).all()
    return {
        "live_actors": [
            {
                "id": live_actor.id,
                "actor_id": live_actor.actor_id,
                "current_hp": live_actor.current_hp,
                "state": live_actor.state,
                "role": live_actor.role.value,
                "background": live_actor.background,
                "actor": {
                    "id": actor.id,
                    "name": actor.name,
                    "level": actor.level,
                    "armor_class": actor.armor_class,
                    "hit_points": actor.hit_points,
                    "speed": actor.speed,
                    "strength": actor.strength,
                    "dexterity": actor.dexterity,
                    "constitution": actor.constitution,
                    "intelligence": actor.intelligence,
                    "wisdom": actor.wisdom,
                    "charisma": actor.charisma,
                    "proficiency_bonus": actor.proficiency_bonus,
                    "size": actor.size.value,
                    "alignment": actor.alignment.value,
                    "controlled_by_user": actor.controlled_by_user,
                    "can_fight": actor.can_fight,
                    "image_id": actor.image_id,
                    "abilities": actor.abilities,
                },
            }
            for live_actor, actor in live_rows
        ],
        "current_map_id": state.current_map_id,
        "current_map": current_map,
        "environment_description": state.environment_description,
    }


def _parse_role(role: Any) -> LiveActorRole:
    if role is None:
        return LiveActorRole.enemy
    role_text = str(role).strip().lower()
    if role_text == "enemy":
        return LiveActorRole.enemy
    if role_text == "player":
        return LiveActorRole.player
    if role_text == "npc":
        return LiveActorRole.npc
    raise ValueError("Invalid role. Use one of: enemy, player, npc.")


def get_game_state(_: dict[str, Any], *, game_id: int) -> dict[str, Any]:
    with Session(engine) as session:
        return _read_state(session, game_id)


def create_live_actor(args: dict[str, Any], *, game_id: int) -> dict[str, Any]:
    name = str(args["name"]).strip()
    state_text = str(args["state"])
    background = str(args.get("background", ""))
    role = _parse_role(args.get("role", "enemy"))
    if not name:
        raise ValueError("name is required.")

    # Generate actor stats with random values between 1 and 20.
    level = random.randint(1, 20)
    armor_class = random.randint(1, 20)
    hit_points = random.randint(1, 20)
    speed = random.randint(1, 20)
    strength = random.randint(1, 20)
    dexterity = random.randint(1, 20)
    constitution = random.randint(1, 20)
    intelligence = random.randint(1, 20)
    wisdom = random.randint(1, 20)
    charisma = random.randint(1, 20)
    # Proficiency bonus must stay within model bounds.
    proficiency_bonus = min(max(random.randint(1, 20), 2), 9)
    current_hp = int(args.get("current_hp", hit_points))
    if current_hp < 1:
        raise ValueError("current_hp must be >= 1.")

    with Session(engine) as session:
        image_uri_slug = "-".join(name.lower().split()) or "actor"
        image = Image(uri=f"https://example.com/{image_uri_slug}.png")
        session.add(image)
        session.flush()
        if image.id is None:
            raise RuntimeError("Image ID was not generated.")

        actor = Actor(
            game_id=game_id,
            name=name,
            level=level,
            armor_class=armor_class,
            hit_points=hit_points,
            speed=speed,
            strength=strength,
            dexterity=dexterity,
            constitution=constitution,
            intelligence=intelligence,
            wisdom=wisdom,
            charisma=charisma,
            proficiency_bonus=proficiency_bonus,
            size=Size.medium,
            alignment=Alignment.true_neutral,
            controlled_by_user=role == LiveActorRole.player,
            can_fight=True,
            image_id=image.id,
            abilities=[
                {
                    "name": "Basic Attack",
                    "description": "A straightforward attack.",
                    "ability_type": "attack",
                }
            ],
        )
        session.add(actor)
        session.flush()
        if actor.id is None:
            raise RuntimeError("Actor ID was not generated.")

        live_actor = LiveActor(
            actor_id=actor.id,
            current_hp=current_hp,
            state=state_text,
            background=background,
            role=role,
            game_id=game_id,
        )
        session.add(live_actor)
        session.commit()
        session.refresh(live_actor)
        return {
            "created": {
                "id": live_actor.id,
                "actor_id": live_actor.actor_id,
                "current_hp": live_actor.current_hp,
                "state": live_actor.state,
                "background": live_actor.background,
                "role": live_actor.role.value,
            },
            "actor": {
                "id": actor.id,
                "name": actor.name,
                "level": actor.level,
                "armor_class": actor.armor_class,
                "hit_points": actor.hit_points,
                "speed": actor.speed,
                "strength": actor.strength,
                "dexterity": actor.dexterity,
                "constitution": actor.constitution,
                "intelligence": actor.intelligence,
                "wisdom": actor.wisdom,
                "charisma": actor.charisma,
                "proficiency_bonus": actor.proficiency_bonus,
            },
        }


def delete_live_actor(args: dict[str, Any], *, game_id: int) -> dict[str, Any]:
    actor_id = int(args["actor_id"])
    where_clause = (col(LiveActor.actor_id) == actor_id) & (
        col(LiveActor.game_id) == game_id
    )
    with Session(engine) as session:
        existing = session.exec(select(LiveActor).where(where_clause)).all()
        deleted = len(existing)
        session.exec(delete(LiveActor).where(where_clause))
        session.commit()
        return {"deleted": deleted, "actor_id": actor_id}


def change_map(args: dict[str, Any], *, game_id: int) -> dict[str, Any]:
    current_map_id = int(args["current_map_id"])

    with Session(engine) as session:
        db_map = session.exec(
            select(Map).where(
                Map.id == current_map_id,
                Map.game_id == game_id,
            )
        ).first()
        if db_map is None:
            raise ValueError(f"Map {current_map_id} does not exist in game {game_id}.")

        state = _get_or_create_state(session, game_id)
        state.current_map_id = current_map_id
        session.add(state)
        session.commit()
        return {"current_map_id": current_map_id}


def change_environment_description(
    args: dict[str, Any], *, game_id: int
) -> dict[str, Any]:
    description = str(args["description"])
    with Session(engine) as session:
        state = _get_or_create_state(session, game_id)
        state.environment_description = description
        session.add(state)
        session.commit()
        return {"environment_description": state.environment_description}


def unlock_next_chapter(_: dict[str, Any], *, game_id: int) -> dict[str, Any]:
    with Session(engine) as session:
        game = session.exec(select(Game).where(col(Game.id) == game_id)).first()
        if game is None:
            raise ValueError(f"Game {game_id} does not exist.")

        unlocked = list(game.current_chapters)
        all_chapters = list(game.chapters)
        next_index = len(unlocked)
        if next_index >= len(all_chapters):
            return {"message": "Players unlocked all the chapters"}

        unlocked.append(all_chapters[next_index])
        game.current_chapters = unlocked
        session.add(game)
        session.commit()
        return {
            "unlocked_chapter": all_chapters[next_index],
            "current_chapters": unlocked,
        }
