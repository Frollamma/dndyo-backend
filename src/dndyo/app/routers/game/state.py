import random
from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, col, delete, select

from dndyo.app.core.db import get_session
from dndyo.app.helpers.battle import (
    apply_damage,
    calculate_damage_from_roll,
    resolve_attack_roll,
)
from dndyo.app.models.actor import Actor
from dndyo.app.models.battle import LiveActorAttackCreate, LiveActorAttackRead
from dndyo.app.models.game_state import (
    CurrentMapUpdate,
    GameState,
    GameStateRead,
    LiveActorsUpdate,
    WorldStateUpdate,
)
from dndyo.app.models.live_actor import LiveActor, LiveActorCreate
from dndyo.app.models.map import Map
from dndyo.app.routers.game.deps import require_game_id

router = APIRouter()


def _get_or_create_state(session: Session, game_id: int) -> GameState:
    state = session.exec(select(GameState).where(col(GameState.id) == game_id)).first()
    if state is None:
        state = GameState(id=game_id, world_state="")
        session.add(state)
        session.commit()
        session.refresh(state)
    return state


def _build_read(state: GameState, live_rows: Sequence[LiveActor]) -> GameStateRead:
    live_actors = []
    for row in live_rows:
        live_actor = LiveActorCreate(
            actor_id=row.actor_id,
            current_hp=row.current_hp,
            state=row.state,
            role=row.role,
        )
        live_actors.append(live_actor)
    return GameStateRead(
        live_actors=live_actors,
        current_map_id=state.current_map_id,
        world_state=state.world_state,
    )


def _read_state(session: Session, game_id: int) -> GameStateRead:
    state = _get_or_create_state(session, game_id)
    live_rows = session.exec(
        select(LiveActor)
        .where(LiveActor.game_id == game_id)
        .order_by(col(LiveActor.id))
    ).all()
    return _build_read(state, live_rows)


@router.get("", response_model=GameStateRead)
def get_state(
    game_id: int = Depends(require_game_id),
    session: Session = Depends(get_session),
):
    return _read_state(session, game_id)


@router.put("/live-actors", response_model=GameStateRead)
def update_live_actors(
    payload: LiveActorsUpdate,
    game_id: int = Depends(require_game_id),
    session: Session = Depends(get_session),
):
    _get_or_create_state(session, game_id)
    session.exec(delete(LiveActor).where(col(LiveActor.game_id) == game_id))
    for actor in payload.live_actors:
        db_actor = session.exec(
            select(Actor).where(
                col(Actor.id) == actor.actor_id,
                col(Actor.game_id) == game_id,
            )
        ).first()
        if db_actor is None:
            raise HTTPException(
                status_code=400,
                detail=f"Actor {actor.actor_id} does not exist in game {game_id}.",
            )
        session.add(
            LiveActor(
                actor_id=actor.actor_id,
                current_hp=actor.current_hp,
                state=actor.state,
                role=actor.role,
                game_id=game_id,
            )
        )
    session.commit()
    return _read_state(session, game_id)


@router.patch("/current-map", response_model=GameStateRead)
def update_current_map(
    payload: CurrentMapUpdate,
    game_id: int = Depends(require_game_id),
    session: Session = Depends(get_session),
):
    state = _get_or_create_state(session, game_id)
    if payload.current_map_id is not None:
        db_map = session.exec(
            select(Map).where(
                col(Map.id) == payload.current_map_id,
                col(Map.game_id) == game_id,
            )
        ).first()
        if db_map is None:
            raise HTTPException(
                status_code=400,
                detail=f"Map {payload.current_map_id} does not exist in game {game_id}.",
            )
    state.current_map_id = payload.current_map_id
    session.add(state)
    session.commit()
    return _read_state(session, game_id)


@router.patch("/world-state", response_model=GameStateRead)
def update_world_state(
    payload: WorldStateUpdate,
    game_id: int = Depends(require_game_id),
    session: Session = Depends(get_session),
):
    state = _get_or_create_state(session, game_id)
    state.world_state = payload.world_state
    session.add(state)
    session.commit()
    return _read_state(session, game_id)


@router.post("/attack-live-actor", response_model=LiveActorAttackRead)
def attack_live_actor(
    payload: LiveActorAttackCreate,
    game_id: int = Depends(require_game_id),
    session: Session = Depends(get_session),
):
    live_actor = session.exec(
        select(LiveActor).where(
            col(LiveActor.id) == payload.live_actor_id,
            col(LiveActor.game_id) == game_id,
        )
    ).first()
    if live_actor is None:
        raise HTTPException(
            status_code=404,
            detail=f"Live actor {payload.live_actor_id} not found in game {game_id}.",
        )

    actor = session.exec(
        select(Actor).where(
            col(Actor.id) == live_actor.actor_id,
            col(Actor.game_id) == game_id,
        )
    ).first()
    if actor is None:
        raise HTTPException(
            status_code=404,
            detail=f"Actor {live_actor.actor_id} not found in game {game_id}.",
        )

    attack_roll = random.randint(1, 20)
    attack_result = resolve_attack_roll(
        attack_roll=attack_roll,
        attack_bonus=payload.attack_bonus,
        target_armor_class=actor.armor_class,
    )

    damage_rolls: list[int] = []
    damage = 0
    if attack_result.hit:
        damage_rolls = [
            random.randint(1, payload.damage_dice_faces)
            for _ in range(payload.damage_num_dice)
        ]
        rolled_damage = sum(damage_rolls)
        damage = calculate_damage_from_roll(
            rolled_damage=rolled_damage,
            damage_bonus=payload.damage_bonus,
            critical=attack_result.critical,
        )
        live_actor.current_hp = apply_damage(
            current_hp=live_actor.current_hp,
            damage=damage,
        )
        session.add(live_actor)
        session.commit()
        session.refresh(live_actor)

    return LiveActorAttackRead(
        live_actor_id=live_actor.id if live_actor.id is not None else payload.live_actor_id,
        actor_id=live_actor.actor_id,
        attack_roll=attack_roll,
        total_to_hit=attack_result.total_to_hit,
        critical=attack_result.critical,
        hit=attack_result.hit,
        damage_rolls=damage_rolls,
        damage=damage,
        remaining_hp=live_actor.current_hp,
    )
