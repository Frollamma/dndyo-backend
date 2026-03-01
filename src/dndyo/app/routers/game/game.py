from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from dndyo.app.core.db import get_session
from dndyo.app.models.actor import Actor
from dndyo.app.models.game import Game, GameCreate, GameRead
from dndyo.app.models.game_state import GameState
from dndyo.app.models.live_actor import LiveActor
from dndyo.app.models.map import Map

router = APIRouter()


@router.post(
    "/",
    response_model=GameRead,
    summary="Create Game",
    description="Create a game and its linked game state row.",
)
def create_game(
    game: GameCreate,
    session: Session = Depends(get_session),
):
    db_game = Game.model_validate(game.model_dump(exclude={"initial_state"}))
    session.add(db_game)
    session.flush()
    if db_game.id is None:
        raise RuntimeError("Game ID was not generated.")

    initial_state = game.initial_state
    db_state = GameState(
        id=db_game.id,
        world_state=initial_state.world_state if initial_state else "",
        current_map_id=initial_state.current_map_id if initial_state else None,
    )
    if db_state.current_map_id is not None:
        db_map = session.exec(
            select(Map).where(
                Map.id == db_state.current_map_id,
                Map.game_id == db_game.id,
            )
        ).first()
        if db_map is None:
            raise HTTPException(
                status_code=400,
                detail=f"Map {db_state.current_map_id} does not exist in game {db_game.id}.",
            )
    session.add(db_state)
    db_game.game_state_id = db_state.id
    session.add(db_game)

    for live_actor in (initial_state.live_actors if initial_state else []):
        actor = session.exec(
            select(Actor).where(
                Actor.id == live_actor.actor_id,
                Actor.game_id == db_game.id,
            )
        ).first()
        if actor is None:
            raise HTTPException(
                status_code=400,
                detail=f"Actor {live_actor.actor_id} does not exist in game {db_game.id}.",
            )
        session.add(
            LiveActor(
                actor_id=live_actor.actor_id,
                current_hp=live_actor.current_hp,
                state=live_actor.state,
                background=live_actor.background,
                role=live_actor.role,
                game_id=db_game.id,
            )
        )

    session.commit()
    session.refresh(db_game)
    return db_game


@router.get(
    "/",
    response_model=list[GameRead],
    summary="List Games",
    description="List all games.",
)
def list_games(session: Session = Depends(get_session)):
    return session.exec(select(Game)).all()


@router.get(
    "/{game_id}",
    response_model=GameRead,
    summary="Get Game",
    description="Return a single game by id.",
)
def get_game(
    game_id: int,
    session: Session = Depends(get_session),
):
    game = session.exec(select(Game).where(Game.id == game_id)).first()
    if game is None:
        raise HTTPException(status_code=404, detail=f"Game {game_id} not found.")
    return game
