from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from dndyo.app.core.db import get_session
from dndyo.app.models.game import Game, GameCreate, GameRead
from dndyo.app.models.game_state import GameState

router = APIRouter()


@router.post("/", response_model=GameRead)
def create_game(
    game: GameCreate,
    session: Session = Depends(get_session),
):
    db_game = Game.model_validate(game)
    session.add(db_game)
    session.commit()
    session.refresh(db_game)
    if db_game.id is None:
        raise RuntimeError("Game ID was not generated.")

    db_state = GameState(id=db_game.id, world_state="")
    session.add(db_state)
    db_game.game_state_id = db_state.id
    session.add(db_game)
    session.commit()
    session.refresh(db_game)
    return db_game


@router.get("/", response_model=list[GameRead])
def list_games(session: Session = Depends(get_session)):
    return session.exec(select(Game)).all()


@router.get("/{game_id}", response_model=GameRead)
def get_game(
    game_id: int,
    session: Session = Depends(get_session),
):
    game = session.exec(select(Game).where(Game.id == game_id)).first()
    if game is None:
        raise HTTPException(status_code=404, detail=f"Game {game_id} not found.")
    return game
