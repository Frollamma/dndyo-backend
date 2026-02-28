from typing import Any

from sqlmodel import Session, col, delete, select

from dndyo.app.core.db import engine
from dndyo.app.models.actor import Actor
from dndyo.app.models.game import Game
from dndyo.app.models.game_state import GameState
from dndyo.app.models.live_actor import LiveActor, LiveActorRole
from dndyo.app.models.map import Map

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_state",
            "description": (
                "Read the full current game state: live actors, current map id, "
                "and world state text."
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
                "Create a live actor entry in combat state. "
                "Only enemy role is allowed for now."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "actor_id": {"type": "integer", "minimum": 1},
                    "current_hp": {"type": "integer", "minimum": 0},
                    "state": {"type": "string"},
                    "role": {
                        "type": "string",
                        "description": "Must be 'enemy' or 'Enemy' for now.",
                    },
                },
                "required": ["actor_id", "current_hp", "state"],
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
            "name": "change_world_state",
            "description": (
                "Update the global game/world description text in the current state."
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
    state = session.exec(select(GameState).where(col(GameState.id) == game_id)).first()
    if state is None:
        state = GameState(id=game_id, world_state="")
        session.add(state)
        session.commit()
        session.refresh(state)
    return state


def _read_state(session: Session, game_id: int) -> dict[str, Any]:
    state = _get_or_create_state(session, game_id)
    live_rows = session.exec(
        select(LiveActor)
        .where(LiveActor.game_id == game_id)
        .order_by(col(LiveActor.id))
    ).all()
    return {
        "live_actors": [
            {
                "id": row.id,
                "actor_id": row.actor_id,
                "current_hp": row.current_hp,
                "state": row.state,
                "role": row.role.value,
            }
            for row in live_rows
        ],
        "current_map_id": state.current_map_id,
        "world_state": state.world_state,
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


def get_state(_: dict[str, Any], *, game_id: int) -> dict[str, Any]:
    with Session(engine) as session:
        return _read_state(session, game_id)


def create_live_actor(args: dict[str, Any], *, game_id: int) -> dict[str, Any]:
    actor_id = int(args["actor_id"])
    current_hp = int(args["current_hp"])
    state_text = str(args["state"])
    role = _parse_role(args.get("role", "enemy"))

    if role != LiveActorRole.enemy:
        raise ValueError("Only enemy live actors are supported for now.")
    if current_hp < 0:
        raise ValueError("current_hp must be >= 0.")

    with Session(engine) as session:
        actor = session.exec(
            select(Actor).where(
                Actor.id == actor_id,
                Actor.game_id == game_id,
            )
        ).first()
        if actor is None:
            raise ValueError(f"Actor {actor_id} does not exist in game {game_id}.")

        live_actor = LiveActor(
            actor_id=actor_id,
            current_hp=current_hp,
            state=state_text,
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
                "role": live_actor.role.value,
            }
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


def change_world_state(args: dict[str, Any], *, game_id: int) -> dict[str, Any]:
    description = str(args["description"])
    with Session(engine) as session:
        state = _get_or_create_state(session, game_id)
        state.world_state = description
        session.add(state)
        session.commit()
        return {"world_state": state.world_state}


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
